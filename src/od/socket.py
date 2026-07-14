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

from __future__ import annotations

import os
import stat
from pathlib import Path

__all__ = [
    "SocketError",
    "ensure",
    "fixit_command",
]


class SocketError(Exception):
    """Raised when the Obsidian CLI IPC socket cannot be made usable."""


def _uid() -> int:
    return os.getuid()


def _cli_sock(uid: int | None = None) -> Path:
    """Path the Obsidian CLI expects: ``/run/user/$UID/.obsidian-cli.sock``."""
    return Path(f"/run/user/{_uid() if uid is None else uid}/.obsidian-cli.sock")


def _flatpak_sock(uid: int | None = None) -> Path:
    """Flatpak-sandboxed real socket path for md.obsidian.Obsidian."""
    u = _uid() if uid is None else uid
    return Path(
        f"/run/user/{u}/.flatpak/md.obsidian.Obsidian/xdg-run/.obsidian-cli.sock"
    )


def fixit_command(uid: int | None = None) -> str:
    """Shell command that recreates the CLI socket symlink (for error text)."""
    u = _uid() if uid is None else uid
    src = f"/run/user/{u}/.flatpak/md.obsidian.Obsidian/xdg-run/.obsidian-cli.sock"
    dst = f"/run/user/{u}/.obsidian-cli.sock"
    return f"ln -sf {src} {dst}"


def _is_live_socket(path: Path) -> bool:
    """True if *path* resolves to an existing Unix domain socket."""
    try:
        if not path.exists():
            # exists() follows symlinks; dead links are not live.
            return False
        mode = path.stat().st_mode
    except OSError:
        return False
    return stat.S_ISSOCK(mode)


def _unhealable_message() -> str:
    return (
        "Obsidian CLI socket unavailable. Is the Obsidian app running with "
        "the official CLI enabled?\n"
        f"If the flatpak socket exists, recreate the symlink with:\n"
        f"  {fixit_command()}"
    )


def _replace_symlink(link: Path, source: Path) -> None:
    """Point *link* at *source*. Only mutates the *link* path itself."""
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(source)


def ensure() -> None:
    """Ensure the Obsidian CLI socket symlink is present and live.

    Idempotent: a live ``/run/user/$UID/.obsidian-cli.sock`` is a no-op.
    When the link is missing or dead, recreate it from the flatpak socket
    path. If the flatpak socket is missing (Obsidian not running / no
    CLI), raise ``SocketError`` including the fix-it ``ln -sf`` command.
    """
    link = _cli_sock()
    source = _flatpak_sock()

    if _is_live_socket(link):
        return

    if not _is_live_socket(source):
        raise SocketError(_unhealable_message())

    try:
        _replace_symlink(link, source)
    except OSError as exc:
        raise SocketError(
            f"Could not create Obsidian CLI socket symlink: {exc}\n"
            f"Try:\n  {fixit_command()}"
        ) from exc

    if not _is_live_socket(link):
        raise SocketError(_unhealable_message())
