# Ten likely viva questions

**1. What problem does your project solve?**
Hand-written documentation becomes outdated. The tool generates it from source code, and the CI pipeline fails when the committed documentation no longer matches the code.

**2. Why use `ast` instead of importing the modules?**
`ast` parses source text into a tree without running it, so it is safe on broken or untrusted code and needs no project dependencies. Importing (what pdoc does) executes top-level code.

**3. What is an AST?**
An abstract syntax tree: a tree of Python objects (`FunctionDef`, `ClassDef`, `arguments`, ...) that represents the structure of the program. I walk it to find functions, classes, parameters and annotations.

**4. How do you make the output deterministic, and why does it matter?**
No timestamps, files and modules are sorted, newlines are always `\n`. If the output changed on every run, the freshness check would always fail, and commits would be full of noise.

**5. How does the freshness check work?**
`--check` regenerates the documentation in memory and compares it with the committed file. If the file is missing or different, the program exits with code 1 and prints a diff; the CI step fails.

**6. Walk me through your GitHub Actions workflow.**
Check out the repo, set up Python 3.12, install requirements, run `unittest`, generate documentation into `build/`, generate pdoc HTML (non-blocking), run the `--check` gate, then upload `build/` as an artifact (even on failure, so a fresh copy can be downloaded).

**7. What do the exit codes mean?**
0 = success, 1 = syntax errors or stale/missing documentation, 2 = usage error such as a missing source directory. CI treats any non-zero code as failure.

**8. How did you test it?**
31 `unittest` tests covering functions, classes, docstrings, annotations, nested folders, empty and missing directories, syntax errors, reproducibility, the check mode and the command line. They run with `python -m unittest`.

**9. How is your tool different from pdoc, and which is better?**
Mine is static, produces Markdown, has a built-in staleness check and is small enough to explain fully; pdoc is more complete (inheritance, search, HTML, cross-links) but imports your code. Neither is "better" in general; they suit different needs.

**10. What are the limitations and what would you improve?**
It ignores inheritance, nested classes and module-level variables, and shows docstrings as plain text. `ast.unparse` can format some code differently across Python versions, so CI pins 3.12. Future work (not implemented): parse Google/NumPy docstring sections, document variables, support config files, auto-commit docs from CI.
