# One-week implementation and demonstration plan

| Day | Goal | Done when |
| --- | --- | --- |
| 1 | Set up macOS tools (Python 3.12, git, VS Code), create the GitHub repository, run the provided project once. Read `generate_docs.py` top to bottom. | `python -m unittest` passes locally; repo pushed |
| 2 | Understand `ast`: use `ast.dump(ast.parse("def f(a: int): ..."))` in a Python shell; trace how `_extract_function` reads a node. Research pdoc (read its docs, install it). | You can explain parsing vs. importing |
| 3 | Run the generator on the sample project and on a project of your own; tweak one small feature (e.g. a new line in the Summary) and update tests. | Own change merged, tests green |
| 4 | Push and watch the GitHub Actions run; fix problems; download the artifact. Practise failure scenarios 2-5 from `docs/evaluation.md` (E4). | Screenshots of real runs saved |
| 5 | Run the pdoc comparison and benchmark; fill in `docs/evaluation.md` with real observations only. | Tables completed |
| 6 | Finish README (add your name, repo link, real screenshots); write the limitations/future work in your own words; rehearse the viva questions. | README reviewed |
| 7 | Dry-run the demo (`docs/demo_script.md`) twice; tag a release (`git tag v1.0`); submit. | Demo fits in 8-10 minutes |
