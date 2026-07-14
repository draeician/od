"""obsidian.py — guarded runner for the Obsidian CLI

Purpose:
    The ONLY place that spawns the `obsidian` binary (ap's
    run_atomicparsley pattern).

Public:
    outline(vault) -> str
    daily_read(vault) -> str
    daily_append(vault, text)
    create_overwrite(vault, path, content)
    tasks(vault)
    task_done(vault, ref)

Invariants:
    argv lists only, never shell=True; calls socket.ensure() first;
    Obsidian-not-running -> ObsidianError with actionable message;
    KeyboardInterrupt -> clean termination, exit code 130 propagated as
    exception; stdout/stderr of the child captured, never leaked raw.

Depends on:
    socket, stdlib.
"""

from __future__ import annotations

import shutil
import signal
import subprocess
from typing import Sequence

from od import socket as od_socket

__all__ = [
    "ObsidianError",
    "ObsidianInterrupted",
    "outline",
    "daily_read",
    "daily_append",
    "create_overwrite",
    "tasks",
    "task_done",
    "run",
]

# Default binary name on PATH (Flatpak users often symlink or wrap this).
_DEFAULT_BIN = "obsidian"


class ObsidianError(Exception):
    """Raised when an Obsidian CLI invocation fails or cannot start."""

    def __init__(
        self,
        message: str,
        *,
        returncode: int | None = None,
        stderr: str = "",
        stdout: str = "",
    ) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


class ObsidianInterrupted(ObsidianError):
    """Child was interrupted (Ctrl+C); exit code 130 for the CLI layer."""

    def __init__(self, message: str = "Interrupted.") -> None:
        super().__init__(message, returncode=130)
        self.exit_code = 130


def _obsidian_bin() -> str:
    """Resolve the ``obsidian`` executable on PATH."""
    path = shutil.which(_DEFAULT_BIN)
    if path is None:
        raise ObsidianError(
            "obsidian CLI not found on PATH. Install Obsidian 1.12+ with "
            "Command line interface enabled (Settings → General), and ensure "
            "the `obsidian` binary is on PATH."
        )
    return path


def _vault_prefix(vault: str) -> list[str]:
    if not vault or not str(vault).strip():
        raise ObsidianError("vault name must be non-empty")
    return [f"vault={str(vault).strip()}"]


def _terminate_process(proc: subprocess.Popen[str]) -> None:
    """Stop a child process, escalating from SIGINT to SIGKILL if needed."""
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=2)
    except (subprocess.TimeoutExpired, OSError):
        try:
            proc.kill()
            proc.wait(timeout=2)
        except (subprocess.TimeoutExpired, OSError):
            pass


def _decode(data: str | bytes | None) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


def _not_running_message(detail: str = "") -> str:
    base = (
        "Obsidian CLI failed. Is the Obsidian app running with the official "
        "CLI enabled (Settings → General → Command line interface)?"
    )
    if detail:
        return f"{base}\n{detail}"
    return base


def _classify_failure(
    returncode: int,
    stdout: str,
    stderr: str,
    argv: Sequence[str],
) -> ObsidianError:
    """Build an ObsidianError with actionable text from a failed run."""
    combined = f"{stderr}\n{stdout}".strip().lower()
    detail_parts = [p for p in (stderr.strip(), stdout.strip()) if p]
    detail = "\n".join(detail_parts)

    not_running_hints = (
        "not running",
        "could not connect",
        "connection refused",
        "no such file",
        "socket",
        "econnrefused",
        "enoent",
    )
    if any(h in combined for h in not_running_hints):
        return ObsidianError(
            _not_running_message(detail),
            returncode=returncode,
            stderr=stderr,
            stdout=stdout,
        )

    cmd = " ".join(argv)
    msg = f"obsidian command failed (exit {returncode}): {cmd}"
    if detail:
        msg = f"{msg}\n{detail}"
    return ObsidianError(
        msg,
        returncode=returncode,
        stderr=stderr,
        stdout=stdout,
    )


def run(vault: str, args: Sequence[str]) -> str:
    """Run ``obsidian vault=<vault> …args`` and return captured stdout.

    Calls ``socket.ensure()`` first. Never uses ``shell=True``. Captures
    child stdout/stderr (never streams them raw). On non-zero exit raises
    ``ObsidianError``. On KeyboardInterrupt terminates the child and raises
    ``ObsidianInterrupted`` (exit code 130).

    Args:
        vault: Vault name (passed as ``vault=…`` first parameter).
        args: Remaining CLI arguments (e.g. ``["daily:read"]``).

    Returns:
        Captured stdout text (trailing whitespace stripped of final newline
        only when empty-ish; full stdout is returned stripped of a single
        trailing newline for convenience).

    Raises:
        ObsidianError: Binary missing, socket unhealable, or CLI failure.
        ObsidianInterrupted: User interrupted the child process.
    """
    # Import typed as module attribute so tests can monkeypatch ensure.
    od_socket.ensure()

    bin_path = _obsidian_bin()
    argv: list[str] = [bin_path, *_vault_prefix(vault), *args]

    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise ObsidianError(
            "obsidian CLI not found on PATH. Install Obsidian 1.12+ with "
            "Command line interface enabled, and ensure `obsidian` is on PATH."
        ) from exc
    except OSError as exc:
        raise ObsidianError(
            _not_running_message(str(exc)),
            returncode=None,
        ) from exc

    interrupted = False
    out: str | None = None
    err: str | None = None
    try:
        out, err = proc.communicate()
    except KeyboardInterrupt:
        interrupted = True
        _terminate_process(proc)
        try:
            out, err = proc.communicate(timeout=2)
        except (subprocess.TimeoutExpired, ValueError, OSError):
            pass

    stdout = _decode(out)
    stderr = _decode(err)

    if interrupted:
        raise ObsidianInterrupted()

    rc = proc.returncode if proc.returncode is not None else -1
    if rc != 0:
        raise _classify_failure(rc, stdout, stderr, argv)

    # Preserve content; strip only a single trailing newline common in CLI tools.
    if stdout.endswith("\n"):
        return stdout[:-1]
    return stdout


def outline(vault: str) -> str:
    """Return heading outline for today's daily note in *vault*."""
    path = run(vault, ["daily:path"])
    if not path.strip():
        raise ObsidianError(
            "daily:path returned empty path; is Daily notes configured?"
        )
    return run(vault, ["outline", f"path={path.strip()}"])


def daily_read(vault: str) -> str:
    """Read today's daily note contents for *vault*."""
    return run(vault, ["daily:read"])


def daily_append(vault: str, text: str) -> None:
    """Append *text* to today's daily note (blind end-of-file append)."""
    if text is None:
        raise ObsidianError("append text must not be None")
    run(vault, ["daily:append", f"content={text}"])


def create_overwrite(vault: str, path: str, content: str) -> None:
    """Create or overwrite *path* in *vault* with *content*.

    Used by the vault write path after read-modify in Python.
    """
    if not path or not str(path).strip():
        raise ObsidianError("path must be non-empty")
    if content is None:
        raise ObsidianError("content must not be None")
    run(
        vault,
        [
            "create",
            f"path={str(path).strip()}",
            f"content={content}",
            "overwrite",
        ],
    )


def tasks(vault: str) -> str:
    """List tasks from today's daily note in *vault* (CLI text output)."""
    return run(vault, ["tasks", "daily"])


def task_done(vault: str, ref: str) -> None:
    """Mark the task at *ref* (``path:line``) done in *vault*."""
    if not ref or not str(ref).strip():
        raise ObsidianError("task ref must be non-empty")
    run(vault, ["task", f"ref={str(ref).strip()}", "done"])
