# Task: obsidian.py — guarded Obsidian CLI runner

Wave: 2

## Module
`src/od/obsidian.py`

## Purpose
The ONLY place that spawns the `obsidian` binary (ap's `run_atomicparsley`
pattern).

## Public Interface
- `outline(vault) -> str`
- `daily_read(vault) -> str`
- `daily_append(vault, text)`
- `create_overwrite(vault, path, content)`
- `tasks(vault)`
- `task_done(vault, ref)`
- `run(vault, args) -> str` (additive internal primitive used by the above)

## Acceptance Criteria
- [x] Argv lists only, never `shell=True`.
- [x] Calls `socket.ensure()` first on every run.
- [x] Obsidian-not-running / missing binary → `ObsidianError` with actionable message.
- [x] KeyboardInterrupt → clean child termination; exit code 130 as exception.
- [x] Child stdout/stderr captured, never leaked raw.
- [x] Tests added in `tests/test_obsidian.py` (mocked subprocess; no live vault).

## Depends On
socket, stdlib.

## Coder Notes

- **`run(vault, args)`:** core primitive — `socket.ensure()` → `shutil.which("obsidian")`
  → `Popen` argv list with `vault=<name>` first, capture stdout/stderr, never
  `shell=True`. Non-zero → `ObsidianError`; interrupt → `ObsidianInterrupted`
  (`exit_code=130`) after SIGINT→SIGKILL terminate.
- **CLI mapping:** `daily:read`, `daily:append content=…`, `create path=…
  content=… overwrite`, `tasks daily`, `task ref=… done`.
- **`outline`:** `daily:path` then `outline path=…` (two `ensure`/`run` calls).
- **Errors:** missing binary and IPC/socket-ish stderr get “Is the Obsidian
  app running…” guidance; `SocketError` from ensure propagates unchanged.
- **Additive API:** public `run()` for vault/library callers without expanding
  every CLI surface here.
- **Verify:** `pytest tests/test_obsidian.py -v` → 19 passed; full suite green.
- **No version bump** (hold until release).
- Wave 2 remaining: `entities`.
