"""Unit tests for generate_docs.py (standard-library unittest only).

Run from the repository root with:  python -m unittest
"""

import contextlib
import io
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_docs as gd  # noqa: E402


def write_project(root: Path, files: dict) -> None:
    """Create ``files`` ({relative path: source text}) below ``root``."""
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")


def run_main(*argv):
    """Call gd.main and return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = gd.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class GeneratorTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.src = self.tmp / "src"
        self.src.mkdir()

    def generate(self, files, **kwargs):
        """Write ``files`` into src, parse them and return (modules, markdown)."""
        write_project(self.src, files)
        modules, errors = gd.collect_modules(self.src, **kwargs)
        self.assertEqual(errors, [])
        return modules, gd.render_markdown(modules, "src")


class TestExtraction(GeneratorTestCase):
    def test_function_and_parameters(self):
        modules, md = self.generate({"m.py": '''
            def greet(name, greeting="Hello", *args, flag=False, **kwargs):
                """Say hello."""
        '''})
        fn = modules[0].functions[0]
        self.assertEqual([p.name for p in fn.params], ["name", "greeting", "*args", "flag", "**kwargs"])
        self.assertEqual(fn.params[1].default, "'Hello'")
        self.assertEqual(fn.header, "def greet(name, greeting='Hello', *args, flag=False, **kwargs)")
        self.assertIn("| `greeting` | - | `'Hello'` |", md)

    def test_positional_only_and_keyword_only_markers(self):
        modules, _ = self.generate({"m.py": "def f(a, /, b, *, c=1): pass\n"})
        self.assertEqual(modules[0].functions[0].header, "def f(a, /, b, *, c=1)")

    def test_async_function(self):
        modules, md = self.generate({"m.py": "async def fetch(url: str) -> bytes:\n    '''Get it.'''\n"})
        self.assertTrue(modules[0].functions[0].is_async)
        self.assertIn("async def fetch(url: str) -> bytes", md)
        self.assertIn("Async function `m.fetch`", md)

    def test_class_and_methods(self):
        modules, md = self.generate({"m.py": '''
            class Base: pass

            class Shape(Base):
                """A shape."""
                def area(self) -> float: ...
                async def load(self): ...
                @staticmethod
                def unit(x): ...
                @classmethod
                def make(cls): ...
        '''})
        shape = next(c for c in modules[0].classes if c.name == "Shape")
        self.assertEqual(shape.bases, ["Base"])
        self.assertEqual([m.name for m in shape.methods], ["area", "load", "unit", "make"])
        self.assertTrue(shape.methods[1].is_async)
        self.assertEqual(shape.methods[2].decorators, ["staticmethod"])
        self.assertIn("class Shape(Base)", md)
        self.assertIn("Method `m.Shape.area`", md)
        self.assertIn("Async method `m.Shape.load`", md)

    def test_self_hidden_from_parameter_table_but_not_for_static_methods(self):
        _, md = self.generate({"m.py": '''
            class K:
                def inst(self, a): ...
                @staticmethod
                def stat(first, b): ...
        '''})
        self.assertNotIn("| `self` |", md)
        self.assertIn("| `a` |", md)
        self.assertIn("| `first` |", md)

    def test_module_docstring(self):
        modules, md = self.generate({"m.py": '"""Module summary line.\n\nMore detail."""\n'})
        self.assertEqual(modules[0].docstring, "Module summary line.\n\nMore detail.")
        self.assertIn("> Module summary line.", md)
        self.assertIn("> More detail.", md)

    def test_function_and_class_docstrings(self):
        modules, md = self.generate({"m.py": '''
            def f():
                """Function doc."""
            class C:
                """Class doc."""
                def g(self):
                    """Method doc."""
        '''})
        self.assertEqual(modules[0].functions[0].docstring, "Function doc.")
        self.assertEqual(modules[0].classes[0].docstring, "Class doc.")
        self.assertEqual(modules[0].classes[0].methods[0].docstring, "Method doc.")
        self.assertIn("> Function doc.", md)

    def test_missing_docstrings_are_reported(self):
        _, md = self.generate({"m.py": "def f(): pass\n"})
        self.assertIn("_No module docstring._", md)
        self.assertIn("_No docstring._", md)

    def test_type_annotations_and_return_type(self):
        modules, md = self.generate({"m.py": '''
            def f(a: int, b: list[str] | None = None) -> dict[str, int]: ...
            def g(x): ...
        '''})
        f, g = modules[0].functions
        self.assertEqual(f.params[0].annotation, "int")
        self.assertEqual(f.params[1].annotation, "list[str] | None")
        self.assertEqual(f.returns, "dict[str, int]")
        self.assertIsNone(g.returns)
        self.assertIsNone(g.params[0].annotation)
        # a pipe inside a table cell must be escaped
        self.assertIn("`list[str] \\| None`", md)
        self.assertIn("**Returns:** `dict[str, int]`", md)

    def test_private_names_hidden_unless_requested(self):
        files = {
            "m.py": "def _hidden(): ...\ndef shown(): ...\nclass _P: ...\n"
            "class Q:\n    def _m(self): ...\n    def __init__(self): ...\n"
        }
        modules, _ = self.generate(files)
        self.assertEqual([f.name for f in modules[0].functions], ["shown"])
        self.assertEqual([c.name for c in modules[0].classes], ["Q"])
        self.assertEqual([m.name for m in modules[0].classes[0].methods], ["__init__"])
        with_private, _ = gd.collect_modules(self.src, include_private=True)
        self.assertEqual([f.name for f in with_private[0].functions], ["_hidden", "shown"])


class TestProjectLayout(GeneratorTestCase):
    def test_nested_directories(self):
        modules, md = self.generate({
            "pkg/__init__.py": '"""Package."""\n',
            "pkg/a.py": "def top(): ...\n",
            "pkg/sub/deep/b.py": "def bottom(): ...\n",
        })
        self.assertEqual([m.name for m in modules], ["pkg", "pkg.a", "pkg.sub.deep.b"])
        self.assertIn("Module `pkg.sub.deep.b`", md)
        self.assertIn("Source file: `pkg/sub/deep/b.py`", md)

    def test_cache_and_hidden_directories_are_skipped(self):
        modules, _ = self.generate({
            "ok.py": "def f(): ...\n",
            "__pycache__/x.py": "def junk(): ...\n",
            ".hidden/y.py": "def junk(): ...\n",
        })
        self.assertEqual([m.name for m in modules], ["ok"])

    def test_table_of_contents_links_match_headings(self):
        _, md = self.generate({"pkg/m.py": "def f(): ...\nclass C:\n    def g(self): ...\n"})
        self.assertIn("## Table of Contents", md)
        self.assertIn("- [Module `pkg.m`](#module-pkgm)", md)
        self.assertIn("  - [Function `pkg.m.f`](#function-pkgmf)", md)
        self.assertIn("    - [Method `pkg.m.C.g`](#method-pkgmcg)", md)

    def test_duplicate_headings_get_unique_anchors(self):
        _, md = self.generate({
            "m.py": "class C:\n    @property\n    def x(self): ...\n    @x.setter\n    def x(self, v): ...\n"
        })
        self.assertIn("(#method-mcx)", md)
        self.assertIn("(#method-mcx-1)", md)

    def test_unicode_docstring(self):
        _, md = self.generate({"m.py": '"""Größe – 数据 ✓."""\n'})
        self.assertIn("Größe – 数据 ✓.", md)


class TestErrorHandling(GeneratorTestCase):
    def test_empty_directory(self):
        out_file = self.tmp / "o.md"
        code, _, err = run_main("--src", str(self.src), "--output", str(out_file))
        self.assertEqual(code, gd.EXIT_OK)
        self.assertIn("No Python source files were found", out_file.read_text())
        self.assertIn("warning", err)

    def test_missing_source_directory(self):
        out_file = self.tmp / "o.md"
        code, _, err = run_main("--src", str(self.tmp / "nope"), "--output", str(out_file))
        self.assertEqual(code, gd.EXIT_USAGE)
        self.assertIn("does not exist", err)
        self.assertFalse(out_file.exists())

    def test_source_path_is_a_file(self):
        f = self.tmp / "file.py"
        f.write_text("x = 1\n")
        code, _, err = run_main("--src", str(f), "--output", str(self.tmp / "o.md"))
        self.assertEqual(code, gd.EXIT_USAGE)
        self.assertIn("not a directory", err)

    def test_invalid_syntax_reports_file_and_line(self):
        write_project(self.src, {"pkg/bad.py": "def ok():\n    pass\n\ndef broken(:\n    pass\n"})
        out_file = self.tmp / "o.md"
        code, _, err = run_main("--src", str(self.src), "--output", str(out_file))
        self.assertEqual(code, gd.EXIT_FAILED)
        self.assertIn("bad.py:4", err)
        self.assertIn("SyntaxError", err)
        self.assertFalse(out_file.exists(), "no documentation must be written for broken sources")

    def test_all_syntax_errors_are_reported(self):
        write_project(self.src, {"a.py": "x = (\n", "b.py": "def f(:\n", "good.py": "y = 1\n"})
        modules, errors = gd.collect_modules(self.src)
        self.assertEqual(len(errors), 2)
        self.assertEqual([m.name for m in modules], ["good"])
        self.assertTrue(all(e.lineno for e in errors))

    def test_undecodable_file_is_reported(self):
        (self.src / "latin.py").write_bytes(b"x = '\xe9'\n")
        _, errors = gd.collect_modules(self.src)
        self.assertEqual(len(errors), 1)
        self.assertIn("UTF-8", errors[0].message)

    def test_null_bytes_are_reported(self):
        (self.src / "nul.py").write_bytes(b"x = 1\x00\n")
        _, errors = gd.collect_modules(self.src)
        self.assertEqual(len(errors), 1)


class TestSafetyAndDeterminism(GeneratorTestCase):
    def test_analysed_code_is_never_executed(self):
        marker = self.tmp / "executed.txt"
        write_project(self.src, {"danger.py": f'''
            from pathlib import Path
            Path(r"{marker}").write_text("boom")
            raise SystemExit("must never run")
        '''})
        modules, errors = gd.collect_modules(self.src)
        self.assertEqual((len(modules), errors), (1, []))
        self.assertFalse(marker.exists())

    def test_generation_is_reproducible(self):
        write_project(self.src, {"b.py": "def f(a: int) -> int: ...\n", "a/c.py": "class C:\n    def m(self): ...\n"})
        first = gd.render_markdown(gd.collect_modules(self.src)[0], "src")
        second = gd.render_markdown(gd.collect_modules(self.src)[0], "src")
        self.assertEqual(first, second)
        self.assertNotIn("\r", first)
        self.assertTrue(first.endswith("\n") and not first.endswith("\n\n"))

    def test_output_does_not_depend_on_file_creation_order(self):
        other = self.tmp / "other"
        other.mkdir()
        files = {"z.py": "def z(): ...\n", "a.py": "def a(): ...\n", "m/k.py": "def k(): ...\n"}
        write_project(self.src, files)
        write_project(other, dict(reversed(list(files.items()))))
        one = gd.render_markdown(gd.collect_modules(self.src)[0], "src")
        two = gd.render_markdown(gd.collect_modules(other)[0], "src")
        self.assertEqual(one, two)


class TestCheckMode(GeneratorTestCase):
    def setUp(self):
        super().setUp()
        write_project(self.src, {"m.py": "def f(): ...\n"})
        self.out = self.tmp / "DOCUMENTATION.md"

    def test_check_fails_when_documentation_missing(self):
        code, _, err = run_main("--src", str(self.src), "--output", str(self.out), "--check")
        self.assertEqual(code, gd.EXIT_FAILED)
        self.assertIn("does not exist", err)
        self.assertFalse(self.out.exists(), "--check must never write the file")

    def test_check_passes_when_up_to_date(self):
        self.assertEqual(run_main("--src", str(self.src), "--output", str(self.out))[0], 0)
        code, out, _ = run_main("--src", str(self.src), "--output", str(self.out), "--check")
        self.assertEqual(code, gd.EXIT_OK)
        self.assertIn("up to date", out)

    def test_check_fails_when_source_changes(self):
        run_main("--src", str(self.src), "--output", str(self.out))
        write_project(self.src, {"m.py": "def f(): ...\ndef added(): ...\n"})
        code, _, err = run_main("--src", str(self.src), "--output", str(self.out), "--check")
        self.assertEqual(code, gd.EXIT_FAILED)
        self.assertIn("out of date", err)
        self.assertIn("added", err)

    def test_check_tolerates_windows_line_endings(self):
        run_main("--src", str(self.src), "--output", str(self.out))
        self.out.write_bytes(self.out.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(run_main("--src", str(self.src), "--output", str(self.out), "--check")[0], 0)


class TestCommandLine(unittest.TestCase):
    """End-to-end tests that run the script as a real subprocess."""

    def test_cli_generates_documentation_for_example_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "DOC.md"
            result = subprocess.run(
                [sys.executable, str(ROOT / "generate_docs.py"), "--src", str(ROOT / "src"), "--output", str(out)],
                capture_output=True, text=True, cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            text = out.read_text(encoding="utf-8")
            self.assertIn("Module `example_package.calculator`", text)
            self.assertIn("Class `example_package.calculator.Calculator`", text)
            self.assertIn("Function `example_package.utils.text.slugify`", text)

    def test_cli_exit_code_for_broken_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(ROOT / "generate_docs.py"), "--src", "examples/broken",
                 "--output", str(Path(tmp) / "never.md")],
                capture_output=True, text=True, cwd=ROOT,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("examples/broken/bad_syntax.py:", result.stderr)


if __name__ == "__main__":
    unittest.main()
