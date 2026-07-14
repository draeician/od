# Task: cli.py — thin shell

Wave: 4

## Module
`src/od/cli.py`

## Purpose
argparse + argcomplete, TTY prompts, stderr messaging, exit codes.
No business logic — dispatch to resolve / vault / state / entities / config.

## Public Interface
- `main(argv=None) -> None` (sys.exit)
- `run(argv=None, *, stdin, stdout, stderr) -> int` (testable)

## Acceptance Criteria
- [x] `--version` reports package `__version__`
- [x] `-v/--vault` per-invocation override (tier 4); does not touch state
- [x] `--config` / `od config` shows effective config with tiers
- [x] stdout = useful output only; errors/warnings → stderr
- [x] Sticky-routed writes echo `→ vault/target` on stderr
- [x] No active vault: TTY prompt (Glance); non-TTY / other cmds loud error
- [x] Piped stdin → code-style append via resolve `stdin_piped`
- [x] Exit 130 on interrupt; non-zero on errors; UsageError → 2
- [x] Tests in `tests/test_cli.py` (mocked vault/obsidian I/O)

## Depends On
resolve, vault, entities, config, state, (obsidian via vault)

## Coder Notes

- **`run()`** is the testable core; `main()` only `SystemExit(run())`.
- **argparse** streams rebound to caller's stdout/stderr for `--version`/`-h`.
- **Active vault order:** `-v` → state.active_vault → config vaults.default →
  TTY picker (Glance only) / else error.
- **Sticky freshness:** `state.get(check_sticky=False)` by default for vault
  selection; re-check when Append uses sticky or SwapSticky.
  Additive API: `state.get(*, check_sticky=True)`.
- **Entity link:** on append, if `entities.resolve_alias(vault, target)` hits,
  append `[[slug]]` when missing. Auto-stub deferred (no type signal).
- **argcomplete** completers for words + `-v` vault names (best-effort).
- **Verify:** `pytest tests/test_cli.py -v` → 18 passed; full suite 154+.
- **No version bump** (hold until release).
- Wave 4 complete — library modules + thin CLI wired.
