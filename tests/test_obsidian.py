"""Tests for od.obsidian — guarded Obsidian CLI runner."""

from __future__ import annotations

import signal
import subprocess
from typing import Any

import pytest

from od import obsidian as obs_mod
from od.obsidian import (
    ObsidianError,
    ObsidianInterrupted,
    create_overwrite,
    daily_append,
    daily_read,
    outline,
    run,
    task_done,
    tasks,
)
from od.socket import SocketError


@pytest.fixture
def ensure_ok(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Stub socket.ensure(); record call count."""
    calls: list[int] = []

    def _ensure() -> None:
        calls.append(1)

    monkeypatch.setattr(obs_mod.od_socket, "ensure", _ensure)
    return calls


@pytest.fixture
def fake_bin(monkeypatch: pytest.MonkeyPatch) -> str:
    """Point shutil.which at a fixed binary path."""
    path = "/usr/bin/obsidian"
    monkeypatch.setattr(obs_mod.shutil, "which", lambda name: path)
    return path


class _FakeProc:
    """Minimal Popen stand-in."""

    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        on_communicate: Any = None,
    ) -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._on_communicate = on_communicate
        self.signals: list[int] = []
        self.killed = False
        self._alive = True

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        if self._on_communicate is not None:
            return self._on_communicate(self, timeout)
        self._alive = False
        return self._stdout, self._stderr

    def poll(self) -> int | None:
        return None if self._alive else self.returncode

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)
        self._alive = False
        self.returncode = 130 if sig == signal.SIGINT else -9

    def kill(self) -> None:
        self.killed = True
        self._alive = False
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self._alive = False
        return self.returncode


@pytest.fixture
def popen_queue(monkeypatch: pytest.MonkeyPatch):
    """Queue of FakeProc responses; records each Popen call."""
    calls: list[dict[str, Any]] = []
    queue: list[_FakeProc] = []

    def _popen(argv: list[str], **kwargs: Any) -> _FakeProc:
        calls.append({"argv": list(argv), "kwargs": dict(kwargs)})
        if not queue:
            raise AssertionError(f"unexpected Popen: {argv}")
        return queue.pop(0)

    monkeypatch.setattr(obs_mod.subprocess, "Popen", _popen)

    def enqueue(*procs: _FakeProc) -> None:
        queue.extend(procs)

    return calls, enqueue


def test_run_calls_ensure_and_builds_argv(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    calls, enqueue = popen_queue
    enqueue(_FakeProc(stdout="hello\n", stderr=""))
    out = run("draeician", ["daily:read"])
    assert out == "hello"
    assert len(ensure_ok) == 1
    assert calls[0]["argv"] == [fake_bin, "vault=draeician", "daily:read"]
    assert calls[0]["kwargs"]["shell"] is False
    assert calls[0]["kwargs"]["stdout"] is subprocess.PIPE
    assert calls[0]["kwargs"]["stderr"] is subprocess.PIPE
    assert calls[0]["kwargs"]["text"] is True


def test_run_never_shell_true(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    calls, enqueue = popen_queue
    enqueue(_FakeProc(stdout="ok"))
    run("v", ["version"])
    assert calls[0]["kwargs"].get("shell") is False


def test_run_empty_vault_raises(ensure_ok: list[int], fake_bin: str) -> None:
    with pytest.raises(ObsidianError, match="vault name must be non-empty"):
        run("", ["daily:read"])
    with pytest.raises(ObsidianError, match="vault name must be non-empty"):
        run("   ", ["daily:read"])


def test_missing_binary_raises(
    ensure_ok: list[int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(obs_mod.shutil, "which", lambda name: None)
    with pytest.raises(ObsidianError, match="not found on PATH"):
        run("v", ["daily:read"])


def test_nonzero_exit_raises_obsidian_error(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    _, enqueue = popen_queue
    enqueue(_FakeProc(returncode=1, stdout="", stderr="boom"))
    with pytest.raises(ObsidianError) as ei:
        run("v", ["daily:read"])
    assert ei.value.returncode == 1
    assert ei.value.stderr == "boom"
    assert "boom" in str(ei.value)


def test_not_running_hints_actionable_message(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    _, enqueue = popen_queue
    enqueue(
        _FakeProc(
            returncode=1,
            stderr="Error: could not connect to Obsidian IPC socket",
        )
    )
    with pytest.raises(ObsidianError, match="Is the Obsidian app running"):
        run("v", ["daily:read"])


def test_socket_ensure_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
    fake_bin: str,
) -> None:
    def boom() -> None:
        raise SocketError("unhealable")

    monkeypatch.setattr(obs_mod.od_socket, "ensure", boom)
    with pytest.raises(SocketError, match="unhealable"):
        run("v", ["daily:read"])


def test_keyboard_interrupt_raises_130(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    _, enqueue = popen_queue
    state = {"n": 0}

    def on_communicate(proc: _FakeProc, timeout: float | None = None):
        state["n"] += 1
        if state["n"] == 1:
            raise KeyboardInterrupt
        return "", ""

    proc = _FakeProc(on_communicate=on_communicate)
    enqueue(proc)

    with pytest.raises(ObsidianInterrupted) as ei:
        run("v", ["daily:read"])
    assert ei.value.exit_code == 130
    assert ei.value.returncode == 130
    assert signal.SIGINT in proc.signals


def test_daily_read(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    calls, enqueue = popen_queue
    enqueue(_FakeProc(stdout="# note\n"))
    assert daily_read("mine") == "# note"
    assert calls[0]["argv"][-1] == "daily:read"
    assert "vault=mine" in calls[0]["argv"]


def test_daily_append(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    calls, enqueue = popen_queue
    enqueue(_FakeProc(stdout=""))
    daily_append("mine", "- [ ] buy milk")
    assert calls[0]["argv"] == [
        fake_bin,
        "vault=mine",
        "daily:append",
        "content=- [ ] buy milk",
    ]


def test_create_overwrite(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    calls, enqueue = popen_queue
    enqueue(_FakeProc(stdout=""))
    body = "# Title\n\nbody line"
    create_overwrite("mine", "Daily/2026-07-14.md", body)
    argv = calls[0]["argv"]
    assert argv[0] == fake_bin
    assert argv[1] == "vault=mine"
    assert argv[2] == "create"
    assert "path=Daily/2026-07-14.md" in argv
    assert f"content={body}" in argv
    assert "overwrite" in argv


def test_create_overwrite_empty_path_raises(
    ensure_ok: list[int],
    fake_bin: str,
) -> None:
    with pytest.raises(ObsidianError, match="path must be non-empty"):
        create_overwrite("v", "", "x")


def test_outline_uses_daily_path(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    calls, enqueue = popen_queue
    enqueue(
        _FakeProc(stdout="Daily notes/2026-07-14.md\n"),
        _FakeProc(stdout="# Heading\n## Sub\n"),
    )
    text = outline("mine")
    assert text == "# Heading\n## Sub"
    assert calls[0]["argv"] == [fake_bin, "vault=mine", "daily:path"]
    assert calls[1]["argv"] == [
        fake_bin,
        "vault=mine",
        "outline",
        "path=Daily notes/2026-07-14.md",
    ]
    assert len(ensure_ok) == 2


def test_outline_empty_path_raises(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    _, enqueue = popen_queue
    enqueue(_FakeProc(stdout="\n"))
    with pytest.raises(ObsidianError, match="daily:path returned empty"):
        outline("mine")


def test_tasks(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    calls, enqueue = popen_queue
    enqueue(_FakeProc(stdout="- [ ] a\n- [ ] b\n"))
    assert tasks("mine") == "- [ ] a\n- [ ] b"
    assert calls[0]["argv"] == [fake_bin, "vault=mine", "tasks", "daily"]


def test_task_done(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    calls, enqueue = popen_queue
    enqueue(_FakeProc(stdout=""))
    task_done("mine", "Daily/2026-07-14.md:12")
    assert calls[0]["argv"] == [
        fake_bin,
        "vault=mine",
        "task",
        "ref=Daily/2026-07-14.md:12",
        "done",
    ]


def test_task_done_empty_ref_raises(ensure_ok: list[int], fake_bin: str) -> None:
    with pytest.raises(ObsidianError, match="task ref must be non-empty"):
        task_done("v", "")


def test_popen_file_not_found(
    ensure_ok: list[int],
    fake_bin: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_a: Any, **_k: Any) -> None:
        raise FileNotFoundError("gone")

    monkeypatch.setattr(obs_mod.subprocess, "Popen", boom)
    with pytest.raises(ObsidianError, match="not found on PATH"):
        run("v", ["daily:read"])


def test_stdout_without_trailing_newline(
    ensure_ok: list[int],
    fake_bin: str,
    popen_queue,
) -> None:
    _, enqueue = popen_queue
    enqueue(_FakeProc(stdout="no-nl"))
    assert run("v", ["daily:read"]) == "no-nl"
