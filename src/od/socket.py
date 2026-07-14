"""socket.py — flatpak socket self-heal

Purpose:
    Ensure the Obsidian CLI IPC socket symlink exists and is alive before
    any CLI call.

Public:
    ensure() -> None (raises SocketError with the fix-it command text if
    unhealable)

Invariants:
    Idempotent; recreates /run/user/$UID/.obsidian-cli.sock symlink when
    dead; never touches anything else in /run.

Depends on:
    stdlib only.
"""
