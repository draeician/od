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
