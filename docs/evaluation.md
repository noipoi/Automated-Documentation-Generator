# Evaluation plan and results template

Everything in the **Expected** columns is what the implementation is designed to do (and what
the unit tests assert). Everything in the **Observed** columns is **blank on purpose**: fill it in
only with what you actually saw when you ran the experiment. Do not copy numbers from anyone else.

Environment used for the experiments (fill in):

| Item | Value |
| --- | --- |
| Date | |
| Machine / macOS version | |
| Python version (`python --version`) | |
| pdoc version (`pip show pdoc`) | |
| Git commit (`git rev-parse --short HEAD`) | |

## Part 1 - Unit test inventory (`python -m unittest`)

| Area | Tests (class.method) | Expected outcome |
| --- | --- | --- |
| Functions and parameters | `TestExtraction.test_function_and_parameters`, `test_positional_only_and_keyword_only_markers`, `test_async_function` | Names, defaults, `*args`, `**kwargs`, keyword-only and `/` markers extracted; async functions flagged |
| Classes and methods | `test_class_and_methods`, `test_self_hidden_from_parameter_table_but_not_for_static_methods`, `test_private_names_hidden_unless_requested` | Bases, methods (incl. static/class/async) found; `self`/`cls` hidden from the table; private names excluded unless requested |
| Docstrings | `test_module_docstring`, `test_function_and_class_docstrings`, `test_missing_docstrings_are_reported`, `test_unicode_docstring` | Docstrings extracted and rendered as block quotes; missing ones noted; Unicode preserved |
| Type annotations | `test_type_annotations_and_return_type` | Parameter and return annotations extracted; `\|` escaped in tables |
| Nested directories | `TestProjectLayout.test_nested_directories`, `test_cache_and_hidden_directories_are_skipped` | Dotted module names built from paths; `__pycache__`/hidden dirs skipped |
| Table of contents | `test_table_of_contents_links_match_headings`, `test_duplicate_headings_get_unique_anchors` | TOC links match GitHub-style anchors, duplicates get `-1`, `-2` suffixes |
| Empty / missing source | `TestErrorHandling.test_empty_directory`, `test_missing_source_directory`, `test_source_path_is_a_file` | Empty: exit 0 with a note; missing or not a directory: exit 2 with a clear message |
| Invalid syntax | `test_invalid_syntax_reports_file_and_line`, `test_all_syntax_errors_are_reported`, `test_undecodable_file_is_reported`, `test_null_bytes_are_reported` | Exit 1; `file:line: SyntaxError ...` for every bad file; no output file written |
| Safety | `TestSafetyAndDeterminism.test_analysed_code_is_never_executed` | A file with side effects is parsed but never run |
| Reproducibility | `test_generation_is_reproducible`, `test_output_does_not_depend_on_file_creation_order` | Identical output on repeated runs and regardless of file creation order |
| Freshness check | `TestCheckMode.*` (4 tests) | Missing file -> exit 1; unchanged -> exit 0; changed source -> exit 1 with a diff; CRLF tolerated |
| Command line | `TestCommandLine.*` | Real subprocess runs: exit 0 on the example project, exit 1 on `examples/broken` |

Observed: `python -m unittest` -> tests run: ____ , failures: ____ , errors: ____ .

## Part 2 - Experiments

### E1. Successful documentation generation
Command: `python generate_docs.py --src src --output DOCUMENTATION.md`
Expected: exit code 0; file created; summary line reports 4 modules, 6 functions, 1 class.

| Observed exit code | Observed summary line | File created? |
| --- | --- | --- |
| | | |

### E2. Correctness of extraction (manual ground truth)
Count the items **by reading `src/` yourself first**, then compare with `DOCUMENTATION.md`.
Expected counts for the sample project (public names only): see the "Expected" column.

| Item | Expected (from source) | Found in DOCUMENTATION.md | Match? |
| --- | --- | --- | --- |
| Modules (incl. `__init__.py`) | 4 | | |
| Module-level functions (incl. 1 async) | 6 | | |
| Classes | 1 | | |
| Methods of `Calculator` (incl. static, class, async) | 6 | | |
| Parameters with a type annotation | count by hand | | |
| Functions with a return annotation | count by hand | | |

Extraction accuracy = matching items / expected items = ____ / ____ (compute only from your table).

### E3. Malformed source files
Command: `python generate_docs.py --src examples/broken`
Expected: exit code 1; stderr shows `examples/broken/bad_syntax.py:11: SyntaxError: ...`; no output written.

| Observed exit code | Observed error message | Output file written? |
| --- | --- | --- |
| | | |

### E4. CI/CD success and failure behaviour (needs a GitHub repository)
Run each scenario on a branch/pull request and record the workflow result. Never record a result you did not see.

| # | Scenario | Expected workflow result | Failing step expected | Observed result | Run link |
| --- | --- | --- | --- | --- | --- |
| 1 | Push the project as provided | Success | - | | |
| 2 | Edit a test so it fails | Failure | Run unit tests | | |
| 3 | Add a function in `src/` without regenerating | Failure | Check committed documentation is up to date | | |
| 4 | Introduce a syntax error in `src/` | Failure | Generate documentation | | |
| 5 | Regenerate `DOCUMENTATION.md`, commit, push | Success | - | | |
| 6 | Open the finished run, download the artifact | Artifact `generated-documentation` present | - | | |

### E5. Documentation freshness check (local)
```bash
python generate_docs.py --src src --output DOCUMENTATION.md --check     # expect exit 0
echo "def extra(): ..." >> src/example_package/utils/text.py
python generate_docs.py --src src --output DOCUMENTATION.md --check     # expect exit 1 + diff
git checkout src/example_package/utils/text.py                          # undo the edit
```
Check the exit code with `echo $?` straight after each command.

| Observed exit (unchanged) | Observed exit (after edit) | Diff shown? |
| --- | --- | --- |
| | | |

### E6. Comparison with pdoc (feature checklist, same sample project)
Follow [`comparison.md`](comparison.md), then tick what you actually see in each output.

| Feature | Custom (Markdown) | pdoc (HTML) |
| --- | --- | --- |
| Module docstrings shown | | |
| Function signatures with annotations | | |
| Async functions identified | | |
| Class methods listed | | |
| Table of contents / navigation | | |
| Private names hidden by default | | |
| Source code view | | |
| Search | | |
| Runs without importing the project | | |

### E7. Execution time
Command: `python scripts/benchmark.py --runs 10` (prints the numbers for your machine).

| Tool | Runs | Mean (s) | Median (s) | Min (s) | Max (s) |
| --- | --- | --- | --- | --- | --- |
| Custom generator | | | | | |
| pdoc | | | | | |

Interpretation (write only after you have numbers; mention that both include interpreter start-up and that the
sample project is tiny, so the result says little about large projects): ______________________
