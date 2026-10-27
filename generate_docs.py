#!/usr/bin/env python3
"""Automated Documentation Generator for CI/CD pipelines.

Reads Python source files with the standard-library ``ast`` module and writes
a Markdown reference (``DOCUMENTATION.md`` by default).

Key properties
--------------
* The analysed code is **parsed, never imported or executed**.
* Output is **deterministic**: no timestamps, sorted modules, ``\\n`` newlines,
  so unchanged code always yields byte-identical documentation.
* ``--check`` compares freshly generated output with the committed file and
  exits non-zero when it is missing or stale (used by the CI workflow).

Exit codes
----------
0  success (documentation written, or up to date in ``--check`` mode)
1  one or more files could not be parsed, or documentation is stale/missing
2  usage problem, e.g. the source directory does not exist
"""

from __future__ import annotations

import argparse
import ast
import difflib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

# Directory names that never contain project source worth documenting.
EXCLUDED_DIRS = frozenset(
    {"__pycache__", ".git", ".venv", "venv", "env", "node_modules", "build", "dist"}
)


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------
@dataclass
class Param:
    """One function parameter (``name`` includes ``*``/``**`` prefixes)."""

    name: str
    annotation: str | None
    default: str | None


@dataclass
class FunctionInfo:
    name: str
    is_async: bool
    is_method: bool
    decorators: list[str]
    params: list[Param]
    signature: str          # text between the parentheses
    returns: str | None
    docstring: str | None
    lineno: int

    @property
    def header(self) -> str:
        prefix = "async def" if self.is_async else "def"
        text = f"{prefix} {self.name}({self.signature})"
        if self.returns is not None:
            text += f" -> {self.returns}"
        return text


@dataclass
class ClassInfo:
    name: str
    bases: list[str]
    decorators: list[str]
    docstring: str | None
    methods: list[FunctionInfo]
    lineno: int

    @property
    def header(self) -> str:
        return f"class {self.name}({', '.join(self.bases)})" if self.bases else f"class {self.name}"


@dataclass
class ModuleInfo:
    name: str               # dotted module name, e.g. example_package.calculator
    path: str               # path relative to the source directory (POSIX style)
    docstring: str | None
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)


@dataclass
class SourceError:
    """A file that could not be read or parsed."""

    path: str
    lineno: int | None
    message: str

    def __str__(self) -> str:
        location = f"{self.path}:{self.lineno}" if self.lineno else self.path
        return f"{location}: {self.message}"


# --------------------------------------------------------------------------
# Extraction (ast only - the analysed code is never executed)
# --------------------------------------------------------------------------
def _unparse(node: ast.AST | None) -> str | None:
    return None if node is None else ast.unparse(node)


def _is_public(name: str) -> bool:
    """Public = no leading underscore, except dunder names such as __init__."""
    return not name.startswith("_") or (name.startswith("__") and name.endswith("__"))


def _arg_text(name: str, annotation: str | None, default: str | None) -> str:
    text = name
    if annotation is not None:
        text += f": {annotation}"
    if default is not None:
        text += f" = {default}" if annotation is not None else f"={default}"
    return text


def _build_params(args: ast.arguments) -> tuple[list[Param], str]:
    """Return the parameter list and the signature text for ``args``."""
    params: list[Param] = []
    parts: list[str] = []

    def add(prefix: str, arg: ast.arg, default: ast.expr | None) -> None:
        param = Param(prefix + arg.arg, _unparse(arg.annotation), _unparse(default))
        params.append(param)
        parts.append(_arg_text(param.name, param.annotation, param.default))

    positional = list(args.posonlyargs) + list(args.args)
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults))
    defaults += list(args.defaults)
    for index, (arg, default) in enumerate(zip(positional, defaults)):
        add("", arg, default)
        if args.posonlyargs and index == len(args.posonlyargs) - 1:
            parts.append("/")

    if args.vararg:
        add("*", args.vararg, None)
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        add("", arg, default)
    if args.kwarg:
        add("**", args.kwarg, None)
    return params, ", ".join(parts)


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool
) -> FunctionInfo:
    params, signature = _build_params(node.args)
    return FunctionInfo(
        name=node.name,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        is_method=is_method,
        decorators=[ast.unparse(d) for d in node.decorator_list],
        params=params,
        signature=signature,
        returns=_unparse(node.returns),
        docstring=ast.get_docstring(node),
        lineno=node.lineno,
    )


def _extract_class(node: ast.ClassDef, include_private: bool) -> ClassInfo:
    bases = [ast.unparse(b) for b in node.bases]
    bases += [ast.unparse(k) for k in node.keywords]  # e.g. metaclass=Meta
    methods = [
        _extract_function(child, is_method=True)
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        and (include_private or _is_public(child.name))
    ]
    return ClassInfo(
        name=node.name,
        bases=bases,
        decorators=[ast.unparse(d) for d in node.decorator_list],
        docstring=ast.get_docstring(node),
        methods=methods,
        lineno=node.lineno,
    )


def parse_source(
    source: str,
    module_name: str,
    rel_path: str,
    filename: str = "<unknown>",
    include_private: bool = False,
) -> ModuleInfo:
    """Parse ``source`` text into a :class:`ModuleInfo`.

    Raises ``SyntaxError`` if the source is not valid Python.
    """
    tree = ast.parse(source, filename=filename)
    info = ModuleInfo(name=module_name, path=rel_path, docstring=ast.get_docstring(tree))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if include_private or _is_public(node.name):
                info.functions.append(_extract_function(node, is_method=False))
        elif isinstance(node, ast.ClassDef):
            if include_private or _is_public(node.name):
                info.classes.append(_extract_class(node, include_private))
    return info


# --------------------------------------------------------------------------
# File discovery and collection
# --------------------------------------------------------------------------
def find_python_files(src_dir: Path) -> list[Path]:
    """All ``*.py`` files below ``src_dir`` (recursive), in sorted order."""
    files = []
    for path in src_dir.rglob("*.py"):
        parts = path.relative_to(src_dir).parts[:-1]
        if any(p in EXCLUDED_DIRS or p.startswith(".") for p in parts):
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(src_dir).as_posix())


def module_name_for(rel_path: Path) -> str:
    parts = list(rel_path.with_suffix("").parts)
    if parts and parts[-1] == "__init__" and len(parts) > 1:
        parts.pop()
    return ".".join(parts)


def collect_modules(
    src_dir: Path, include_private: bool = False, label: str | None = None
) -> tuple[list[ModuleInfo], list[SourceError]]:
    """Parse every Python file; collect all errors instead of stopping at the first."""
    label = label if label is not None else src_dir.as_posix()
    modules: list[ModuleInfo] = []
    errors: list[SourceError] = []
    for path in find_python_files(src_dir):
        rel = path.relative_to(src_dir)
        shown = f"{label.rstrip('/')}/{rel.as_posix()}"
        try:
            source = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            errors.append(SourceError(shown, None, f"cannot decode file as UTF-8 ({exc.reason})"))
            continue
        except OSError as exc:
            errors.append(SourceError(shown, None, f"cannot read file ({exc.strerror})"))
            continue
        try:
            modules.append(
                parse_source(source, module_name_for(rel), rel.as_posix(), shown, include_private)
            )
        except SyntaxError as exc:
            errors.append(SourceError(shown, exc.lineno, f"SyntaxError: {exc.msg}"))
        except ValueError as exc:  # e.g. source contains null bytes
            errors.append(SourceError(shown, None, f"cannot parse file ({exc})"))
    modules.sort(key=lambda m: m.name)
    return modules, errors


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------
def _slugify(text: str) -> str:
    """Approximate GitHub's heading-anchor rule (lowercase, drop punctuation)."""
    kept = [c for c in text.lower() if c.isalnum() or c in "_- "]
    return "".join(kept).replace(" ", "-")


class _Anchors:
    """Hands out unique anchors the way GitHub does (``slug``, ``slug-1``, ...)."""

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def allocate(self, heading: str) -> str:
        slug = _slugify(heading)
        count = self._seen.get(slug, 0)
        self._seen[slug] = count + 1
        return slug if count == 0 else f"{slug}-{count}"


def _quote(text: str) -> list[str]:
    """Render a docstring as a block quote so it cannot break heading structure."""
    return [f"> {line}" if line else ">" for line in text.splitlines()] + [""]


def _cell(text: str | None) -> str:
    return "-" if text is None else "`" + text.replace("|", "\\|") + "`"


def render_markdown(
    modules: Sequence[ModuleInfo], src_label: str, title: str = "API Documentation"
) -> str:
    """Build the full Markdown document (deterministic for the same input)."""
    anchors = _Anchors()
    for fixed in (title, "Table of Contents", "Summary"):
        anchors.allocate(fixed)

    toc: list[str] = []
    body: list[str] = []

    def heading(level: int, text: str, toc_level: int) -> None:
        anchor = anchors.allocate(text)
        body.extend([f"{'#' * level} {text}", ""])
        toc.append(f"{'  ' * toc_level}- [{text}](#{anchor})")

    def render_function(fn: FunctionInfo, qualname: str, level: int, toc_level: int) -> None:
        if fn.is_method:
            kind = "Async method" if fn.is_async else "Method"
        else:
            kind = "Async function" if fn.is_async else "Function"
        heading(level, f"{kind} `{qualname}`", toc_level)
        body.append("```python")
        body.extend(f"@{d}" for d in fn.decorators)
        body.extend([fn.header, "```", ""])
        body.extend(_quote(fn.docstring) if fn.docstring else ["_No docstring._", ""])

        params = fn.params
        if fn.is_method and "staticmethod" not in fn.decorators:
            if params and not params[0].name.startswith("*"):
                params = params[1:]  # hide self / cls
        if params:
            body.extend(["| Parameter | Type | Default |", "| --- | --- | --- |"])
            for p in params:
                body.append(f"| `{p.name}` | {_cell(p.annotation)} | {_cell(p.default)} |")
            body.append("")
        if fn.returns is not None:
            body.extend([f"**Returns:** `{fn.returns}`", ""])

    n_functions = sum(len(m.functions) for m in modules)
    n_classes = sum(len(m.classes) for m in modules)
    n_methods = sum(len(c.methods) for m in modules for c in m.classes)

    for module in modules:
        heading(2, f"Module `{module.name}`", 0)
        body.extend([f"Source file: `{module.path}`", ""])
        body.extend(_quote(module.docstring) if module.docstring else ["_No module docstring._", ""])
        for fn in module.functions:
            render_function(fn, f"{module.name}.{fn.name}", 3, 1)
        for cls in module.classes:
            qual = f"{module.name}.{cls.name}"
            heading(3, f"Class `{qual}`", 1)
            body.append("```python")
            body.extend(f"@{d}" for d in cls.decorators)
            body.extend([cls.header, "```", ""])
            body.extend(_quote(cls.docstring) if cls.docstring else ["_No docstring._", ""])
            for method in cls.methods:
                render_function(method, f"{qual}.{method.name}", 4, 2)

    lines = [
        f"# {title}",
        "",
        f"Generated by `generate_docs.py` from the `{src_label}` directory. "
        "Do not edit by hand; regenerate it instead.",
        "",
        "## Summary",
        "",
        f"- Modules: {len(modules)}",
        f"- Functions: {n_functions}",
        f"- Classes: {n_classes}",
        f"- Methods: {n_methods}",
        "",
    ]
    if not modules:
        lines += [f"No Python source files were found in `{src_label}`.", ""]
    else:
        lines += ["## Table of Contents", ""] + toc + [""] + body
    return "\n".join(lines).rstrip("\n") + "\n"


# --------------------------------------------------------------------------
# Command-line interface
# --------------------------------------------------------------------------
def _read_normalised(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_docs.py",
        description="Generate Markdown documentation from Python source using the ast module.",
    )
    parser.add_argument("--src", default="src", help="source directory to scan (default: src)")
    parser.add_argument(
        "--output", "-o", default="DOCUMENTATION.md", help="output Markdown file (default: DOCUMENTATION.md)"
    )
    parser.add_argument("--title", default="API Documentation", help="document title")
    parser.add_argument(
        "--include-private", action="store_true", help="also document names starting with an underscore"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if the output file is missing or differs from freshly generated docs",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    src = Path(args.src)
    out = Path(args.output)

    if not src.exists():
        print(f"error: source directory '{args.src}' does not exist", file=sys.stderr)
        return EXIT_USAGE
    if not src.is_dir():
        print(f"error: '{args.src}' is not a directory", file=sys.stderr)
        return EXIT_USAGE

    modules, errors = collect_modules(src, args.include_private, label=Path(args.src).as_posix())
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        print(f"{len(errors)} file(s) could not be parsed; documentation was not written.", file=sys.stderr)
        return EXIT_FAILED

    content = render_markdown(modules, Path(args.src).as_posix(), args.title)

    if args.check:
        if not out.is_file():
            print(
                f"error: '{args.output}' does not exist. Generate and commit it with:\n"
                f"  python generate_docs.py --src {args.src} --output {args.output}",
                file=sys.stderr,
            )
            return EXIT_FAILED
        committed = _read_normalised(out)
        if committed != content:
            diff = list(
                difflib.unified_diff(
                    committed.splitlines(), content.splitlines(),
                    fromfile=f"{args.output} (committed)", tofile=f"{args.output} (freshly generated)",
                    lineterm="",
                )
            )
            print(f"error: '{args.output}' is out of date. First differences:", file=sys.stderr)
            print("\n".join(diff[:40]), file=sys.stderr)
            print(
                f"\nRegenerate and commit it with:\n  python generate_docs.py --src {args.src} --output {args.output}",
                file=sys.stderr,
            )
            return EXIT_FAILED
        print(f"OK: '{args.output}' is up to date.")
        return EXIT_OK

    if not modules:
        print(f"warning: no Python files found in '{args.src}'", file=sys.stderr)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    n_fn = sum(len(m.functions) for m in modules)
    n_cls = sum(len(m.classes) for m in modules)
    print(f"Wrote {args.output}: {len(modules)} module(s), {n_fn} function(s), {n_cls} class(es).")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
