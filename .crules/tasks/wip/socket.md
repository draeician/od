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
- [ ] Idempotent — safe to call repeatedly.
- [ ] Recreates `/run/user/$UID/.obsidian-cli.sock` symlink when dead.
- [ ] Never touches anything else in `/run`.
- [ ] Raises `SocketError` (with fix-it command text) when unhealable.
- [ ] Tests added in `tests/test_socket.py`.

## Depends On
stdlib only.
