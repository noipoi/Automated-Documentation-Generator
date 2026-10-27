# Demonstration script (about 8-10 minutes)

Prepare: terminal open in the project folder with the virtual environment active
(`source .venv/bin/activate`), your GitHub repository open in the browser.

1. **Problem (1 min).** "Documentation goes stale. I built a tool that generates it from the code and a pipeline that refuses to accept stale docs."
2. **Generate (1 min).** `python generate_docs.py --src src --output DOCUMENTATION.md`, then open `DOCUMENTATION.md`. Point at the table of contents, a parameter table and a method.
3. **It does not run the code (30 s).** Mention the unit test `test_analysed_code_is_never_executed`; contrast with pdoc, which imports modules.
4. **Error handling (1 min).** `python generate_docs.py --src examples/broken` -> file name and line number; then `echo $?` -> `1`. Also `python generate_docs.py --src nope` -> exit 2.
5. **Tests (1 min).** `python -m unittest` -> show the count and `OK`.
6. **Freshness gate (2 min).** Add a function to `src/example_package/utils/text.py`, run
   `python generate_docs.py --src src --output DOCUMENTATION.md --check` -> fails with a diff. Regenerate, run `--check` again -> passes.
7. **CI (2 min).** Show the workflow file, then the Actions tab: a green run, the step list, and the downloadable artifact. If you prepared one, show a red run where the freshness step failed. **Only show runs that really exist in your repository.**
8. **pdoc comparison (1 min).** Show `build/pdoc/index.html` next to `DOCUMENTATION.md`; state the key difference (static vs. import-based) and your measured benchmark numbers, if you ran them.
9. **Limitations (30 s).** No inheritance/nested classes/module variables; Python version sensitivity of `ast.unparse`.

Backup: if the internet fails, demo steps 2-6 locally and show screenshots of earlier real runs.
