# Python coding style (od)

Apply on any `*.py` edit under this repository.

## Language and packaging

- Python `>=3.12` (`requires-python` in `pyproject.toml`).
- Package: `od` under `src/od/` (src layout).
- Prefer existing production dependencies; do not add new ones without an
  explicit task or user request. **Stdlib only except `argcomplete`.**
- Ad-hoc execution: `PYTHONPATH=src python3 -c "…"` or `pipx install -e .`
  then `od …`.

## Style

1. PEP 8 / Ruff-friendly layout; 4-space indent.
2. Type hints on public functions; return types included.
3. Google-style docstrings for public callables (module header contracts
   already used in this repo — preserve that pattern).
4. f-strings for formatting.
5. `snake_case` functions and variables; `PascalCase` classes.
6. Prefer explicit `is None` checks for singletons.
7. Narrow `except` clauses; preserve causes when re-raising.
8. Use `with` for resources; no bare `open` without context managers.
9. Side-effect-free imports (`__init__.py` holds `__version__` only).

## Subprocess and safety

- Always pass argv **lists** to `subprocess` — never `shell=True`.
- Only `obsidian.py` may spawn the `obsidian` binary; call `socket.ensure()` first.
- Do not use `pip install --break-system-packages`.
- Install with `pipx` or a project venv; ad-hoc via `PYTHONPATH=src`.

## Structure preference

Keep changes local to existing modules until size or clarity demands a split.
If splitting, preserve public CLI/API surfaces. Honor the module map dependency
direction (no cycles; lower modules never import upper ones).

`cli.py` is the only module allowed to print help/prompts or call `sys.exit`;
library modules raise typed exceptions.

## Tests

- Prefer pure-function unit tests for parsers, helpers, and pure logic
  (`sections.py` is the purest / most parallel-safe).
- One test file per module under `tests/` matching module names.
- Do not weaken tests to pass a bad change.
- Name tests clearly; one concern per test function.
- Default command: `PYTHONPATH=src python3 -m pytest`
