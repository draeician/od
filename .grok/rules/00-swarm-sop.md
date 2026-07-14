# Swarm SOP (always on)

You operate in a multi-agent (Skeleton Swarm) repository. Native Grok rules
are loaded; also obey root `AGENTS.md`.

## Priority

`project_spec.md` > `AGENTS.md` > `.crules/modes/*` > this file

## Personas

| Mode | When | File |
|------|------|------|
| Manager | planning, backlog, commit/branch/release | `.crules/modes/MANAGER.md` |
| Coder | implementation and tests | `.crules/modes/CODER.md` |
| Git policy | any VCS mutation | `.crules/modes/GIT_POLICY.md` |
| Bootstrapper | only if `AGENTS.md` is `[TEMPLATE]` | `.crules/modes/BOOTSTRAPPER.md` |

Default for coding requests: **Coder**.  
Default for “commit” / “release” / roadmap: **Manager**.

This repo’s `AGENTS.md` is the multi-agent **team charter** (already project-
specific). Prefer Manager/Coder modes; do not re-run Bootstrapper unless the
user asks.

## Session checklist

1. Read `AGENTS.md` and `project_spec.md` when starting non-trivial work.
2. Track non-trivial work as Markdown under `.crules/tasks/wip/` with acceptance criteria.
3. Do not implement speculative features outside the request or active task.
4. Never use `--break-system-packages`. Prefer `pipx`, venv, or module execution under `src/`.

## Important files

| File | Use |
|------|-----|
| `project_spec.md` | Scope, stack, conventions |
| `AGENTS.md` | Team charter and hard boundaries |
| `GROK.md` | Grok entrypoint |
| `CLAUDE.md` | Workstation identity and design spirit |
| `docs/` | Usage spec + module map |
| `DECISIONS.md` | Append-only decision log |
| `.grok/agents/` | Optional named agent profiles |

## Verification

Before claiming done:

- Smoke: `PYTHONPATH=src python3 -c "from od import __version__; print(__version__)"`
- Tests: `PYTHONPATH=src python3 -m pytest` when a suite exists and the change warrants it
- If version touched: runtime version matches metadata (`pyproject.toml`)
