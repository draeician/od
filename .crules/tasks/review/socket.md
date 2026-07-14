# Task: socket.py — flatpak socket self-heal

Wave: 1

## Module
`src/od/socket.py`

## Purpose
Ensure the Obsidian CLI IPC socket symlink exists and is alive before any
CLI call.

## Public Interface
- `ensure() -> None` (raises `SocketError` with the fix-it command text if unhealable)

## Acceptance Criteria
- [x] Idempotent — safe to call repeatedly.
- [x] Recreates `/run/user/$UID/.obsidian-cli.sock` symlink when dead.
- [x] Never touches anything else in `/run`.
- [x] Raises `SocketError` (with fix-it command text) when unhealable.
- [x] Tests added in `tests/test_socket.py`.

## Depends On
stdlib only.

## Coder Notes

- **`ensure()`:** if CLI sock is a live Unix socket → return; else if flatpak
  sock is live → replace only the CLI path with `ln -sf`-equivalent symlink;
  else raise `SocketError` including `fixit_command()` text.
- **Paths:** `_cli_sock` = `/run/user/$UID/.obsidian-cli.sock`;
  `_flatpak_sock` = `/run/user/$UID/.flatpak/md.obsidian.Obsidian/xdg-run/.obsidian-cli.sock`.
- **Live check:** path resolves and `S_ISSOCK` (dead symlinks fail).
- **Tests:** monkeypatch path helpers to short temp names (AF_UNIX path limit);
  bind real AF_UNIX servers for positive cases.
- **Verify:** `PYTHONPATH=src .venv/bin/python -m pytest tests/test_socket.py -v` → 8 passed.
- **No version bump** (hold until release per human).
