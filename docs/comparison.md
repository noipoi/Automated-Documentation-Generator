# Comparison: custom generator vs. pdoc

> Statements about pdoc below describe its documented, general behaviour. Check them
> against the documentation of the pdoc version you install (`pdoc --version`) before
> you present them. Anything about *this* project's behaviour is covered by the unit tests.

## What pdoc does

[pdoc](https://pdoc.dev) is an API-documentation generator for Python. You point it at an
importable module or package; it **imports** the code, inspects the live objects (and their
docstrings and type hints), and produces browsable **HTML** pages. Run without `-o` it starts a
local web server with live reload; run with `-o DIR` it writes static HTML files. It needs almost
no configuration, renders Markdown inside docstrings, and can show inherited members and source code.

## How the custom generator works

`generate_docs.py` reads each `.py` file as **text**, parses it into an abstract syntax tree
with Python's `ast` module, and walks the tree to collect modules, functions, async functions,
classes, methods, parameters, annotations and docstrings. It renders those into one deterministic
Markdown file. The analysed code is **never imported or executed**.
A `--check` mode compares fresh output with the committed file, which is what CI uses to detect stale documentation.

## Similarities

- Both extract docstrings, signatures and type annotations from Python source.
- Both need no AI service, no paid tool and no network access to run.
- Both can run unattended inside a CI job.

## Differences

| Aspect | Custom generator | pdoc |
| --- | --- | --- |
| Analysis method | Static: parses source text with `ast` | Dynamic: imports modules and introspects objects |
| Executes project code? | No | Yes (importing runs top-level code) |
| Needs project dependencies installed? | No | Yes, so that imports succeed |
| Output | One Markdown file (readable on GitHub, easy to diff in a pull request) | HTML site (or live server) |
| Deterministic output by design | Yes: no timestamps, sorted order, tested | Not something this project verifies |
| Staleness check for committed docs | Built in (`--check`) | Not built in; you would script it |
| Syntax-error reporting | File and line number, all files listed, exit code 1 | Not the purpose of the tool |
| Inheritance, nested classes | Not supported | Supported |
| Module-level variables / constants | Not documented | Documented |
| Cross-reference links, search, themes | None | Yes |
| Docstring formats | Shown verbatim as a block quote | Markdown rendered; other formats via options |
| Maturity and testing | Small, written for this project | Widely used, actively maintained |

## Advantages and limitations

**Custom generator** - *Advantages:* safe on untrusted or broken code, no dependencies, Markdown
output that lives in the repository, byte-for-byte reproducible, tiny enough to explain line by
line in a viva, and it makes the CI idea concrete (generate -> compare -> fail). *Limitations:*
no inheritance or nested classes, no module-level variables, no docstring parsing (Google/NumPy
sections are shown as plain text), no cross-links, no HTML, and `ast.unparse` formatting can
differ slightly between Python versions (so CI pins Python 3.12).

**pdoc** - *Advantages:* far more complete and polished output, inheritance, search, links,
rendered docstrings, zero configuration. *Limitations:* the code must be importable (and is
executed when imported), HTML output is awkward to review as a diff, and a stale-docs check
has to be built around it.

## Why the custom implementation is useful for learning CI/CD automation

The interesting engineering is not parsing; it is the **pipeline contract**: a tool with
well-defined exit codes (0 / 1 / 2), deterministic output, a read-only `--check` mode, tests that
run with one command, and a workflow that turns all of that into a pass/fail gate and an
artifact. Building the tool yourself lets you see exactly why each of those properties is needed.

## Reproducible comparison steps (same sample project)

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt

# 1. Custom generator -> Markdown
python generate_docs.py --src src --output build/DOCUMENTATION.md

# 2. pdoc -> HTML (PYTHONPATH lets pdoc import the package under src/)
PYTHONPATH=src python -m pdoc --output-directory build/pdoc example_package

# 3. Inspect
open build/DOCUMENTATION.md          # or open it in VS Code
open build/pdoc/index.html

# 4. Timing (prints measured numbers for YOUR machine)
python scripts/benchmark.py --runs 10
```

Record what you observe in the feature checklist and benchmark table in
[`evaluation.md`](evaluation.md). Do not copy numbers from anywhere else.
