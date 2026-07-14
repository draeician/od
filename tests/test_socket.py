"""Tests for od.socket — flatpak Obsidian CLI socket self-heal."""

from __future__ import annotations

import socket
import stat
from pathlib import Path

import pytest

from od import socket as od_socket
from od.socket import SocketError, ensure, fixit_command


def _bind_unix(path: Path) -> socket.socket:
    """Create a live AF_UNIX stream socket at *path* (caller must close)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        path.unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(path))
    srv.listen(1)
    return srv


@pytest.fixture
def sock_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point path helpers at short temp paths (AF_UNIX has a ~108-byte limit)."""
    # Keep names tiny: pytest tmp dirs are already long under /tmp/pytest-of-...
    link = tmp_path / "c.sock"
    source = tmp_path / "f.sock"
    monkeypatch.setattr(od_socket, "_cli_sock", lambda uid=None: link)
    monkeypatch.setattr(od_socket, "_flatpak_sock", lambda uid=None: source)
    monkeypatch.setattr(
        od_socket,
        "fixit_command",
        lambda uid=None: f"ln -sf {source} {link}",
    )
    return link, source


def test_fixit_command_matches_claude_layout() -> None:
    uid = 1000
    cmd = fixit_command(uid)
    assert cmd == (
        "ln -sf /run/user/1000/.flatpak/md.obsidian.Obsidian/"
        "xdg-run/.obsidian-cli.sock /run/user/1000/.obsidian-cli.sock"
    )


def test_ensure_noop_when_link_already_live(sock_paths) -> None:
    link, source = sock_paths
    srv = _bind_unix(source)
    try:
        link.symlink_to(source)
        ensure()
        ensure()  # idempotent
        assert link.is_symlink()
        assert link.resolve() == source.resolve()
        assert stat.S_ISSOCK(link.stat().st_mode)
    finally:
        srv.close()


def test_ensure_creates_symlink_when_missing(sock_paths) -> None:
    link, source = sock_paths
    srv = _bind_unix(source)
    try:
        assert not link.exists()
        ensure()
        assert link.is_symlink()
        assert link.resolve() == source.resolve()
        assert stat.S_ISSOCK(link.stat().st_mode)
    finally:
        srv.close()


def test_ensure_replaces_dead_symlink(sock_paths) -> None:
    link, source = sock_paths
    # Dead link first (target never created).
    missing = link.parent / "gone.sock"
    link.symlink_to(missing)
    assert link.is_symlink()
    assert not link.exists()

    srv = _bind_unix(source)
    try:
        ensure()
        assert link.is_symlink()
        assert link.resolve() == source.resolve()
        assert stat.S_ISSOCK(link.stat().st_mode)
    finally:
        srv.close()


def test_ensure_raises_when_flatpak_socket_missing(sock_paths) -> None:
    link, source = sock_paths
    with pytest.raises(SocketError) as excinfo:
        ensure()
    msg = str(excinfo.value)
    assert "ln -sf" in msg
    assert str(source) in msg
    assert str(link) in msg
    assert not link.exists()


def test_ensure_raises_when_flatpak_socket_dead(sock_paths) -> None:
    link, source = sock_paths
    source.symlink_to(source.parent / "missing-target")
    with pytest.raises(SocketError) as excinfo:
        ensure()
    assert "ln -sf" in str(excinfo.value)


def test_ensure_only_mutates_cli_sock_path(sock_paths, tmp_path: Path) -> None:
    """Self-heal must not create/delete unrelated paths under the runtime dir."""
    link, source = sock_paths
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("keep\n", encoding="utf-8")
    other = tmp_path / "other.txt"
    other.write_text("leave\n", encoding="utf-8")

    srv = _bind_unix(source)
    try:
        ensure()
        assert sentinel.read_text(encoding="utf-8") == "keep\n"
        assert other.read_text(encoding="utf-8") == "leave\n"
        assert link.is_symlink()
    finally:
        srv.close()


def test_ensure_heals_after_source_returns(sock_paths) -> None:
    link, source = sock_paths
    with pytest.raises(SocketError):
        ensure()
    srv = _bind_unix(source)
    try:
        ensure()
        assert stat.S_ISSOCK(link.stat().st_mode)
    finally:
        srv.close()
