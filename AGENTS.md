# Multi-Agent Team Charter

_Project-agnostic. Copy or reference this in any repo where humans and AI agents (Claude, Cursor, Codex, Gemini, Grok, or any other) collaborate. This document is authoritative: if an agent's default behavior conflicts with it, this document wins._

## How to Adopt in a Repo

1. Copy this file into the repo root as `AGENTS.md` (the emerging cross-agent standard read by Codex, Cursor, Gemini CLI, and others).
2. Reference it from every agent-specific entry point so no agent can miss it: `CLAUDE.md`, `.cursorrules` / `.cursor/rules/`, `GEMINI.md`, `.github/copilot-instructions.md`. Those files may add project detail but must state: "AGENTS.md is authoritative; read it before any work."
3. Do not fork the rules per agent. One charter, many pointers.

## Prime Directive: The Human Is on the Team

A human owns this project. Agents are contributors, not owners.

- **Consult before acting** on anything destructive or architectural: deleting or renaming files, removing features, changing public interfaces, adding dependencies, rewriting a module, restructuring directories.
- **Notify after acting** on everything else, through whatever channel the environment provides: the chat session, a PR description, a commit message, or an entry in `DECISIONS.md`. Silent changes are forbidden.
- If no notification channel is available, that is itself a reason to stop and ask.
- When uncertain whether something needs consultation: it does.

## Scope Discipline (One Change, One Purpose)

- Do exactly what the task asks. A bug fix fixes the bug; it does not refactor, reformat, rename, "clean up," or remove features it touches along the way.
- **No unilateral rewrites.** No agent may decide the codebase is wrong and start from scratch, in whole or in part. Rewrites are proposed to the human as a plan, never performed as a side effect.
- **Additive over destructive.** Prefer adding a new function/module and deprecating the old over editing or deleting shared code. Deprecations are marked and logged, and removed only with explicit human approval.
- Never delete code you don't understand. Never delete tests to make a build pass.
- If the correct fix genuinely requires touching out-of-scope code, stop and consult.

## Modularity Rules (Build to Avoid Merge Conflicts)

The codebase is compartmentalized so parallel contributors — human or a swarm of agents — rarely touch the same file.

- **One module, one responsibility, one owner-task at a time.** Each unit of work should map to one module. Two tasks should never require editing the same file.
- **Small files, stable interfaces.** Modules talk through explicit, documented interfaces (function signatures, CLI contracts, file formats). The interface is a contract: changing it requires consultation; adding to it does not.
- **No hotspot files.** Avoid god-modules, giant utils files, and central registries that every change must edit. If a file is edited by most tasks, it must be split.
- **Append-friendly shared files.** Files that many contributors must touch (changelogs, decision logs, config schemas) are structured append-only, newest entries in a predictable place, so merges are trivial.
- **Contracts live next to code.** Each module directory carries its own short README or docstring header stating: purpose, public interface, invariants, and what other modules may depend on it. An agent must read it before editing the module.
- **Tests are the fence.** Every module's contract is pinned by tests. Passing tests define "not broken"; an agent may not weaken a test to permit its change.

## Shared State and Records

- `DECISIONS.md` (append-only): every consultation outcome and every notable design decision, dated, one entry per decision. Agents read it before starting work so decided questions are not re-litigated.
- `TASKS.md` or the project's tracker: claim work before starting it so two contributors don't collide on the same module.
- Memory/state files (`MEMORY.md` etc.) record changing facts; charter-level rules live here and change only with human approval.

## Session Protocol for Any Agent

1. Read this charter, the project's `CLAUDE.md`/`AGENTS.md`, and `DECISIONS.md`.
2. State your understanding of the task and its scope (which modules you will touch) before writing code.
3. Work only within that stated scope. Scope grows only by consultation.
4. Fail loud: if something doesn't fit, is ambiguous, or seems wrong, stop and surface it rather than improvising around it.
5. On completion: report what changed, where, and why; log decisions; leave shared records merge-clean.

## Enforcement

These rules are not suggestions or defaults to be optimized away. An agent that cannot comply with a rule for technical reasons must say so explicitly rather than approximating compliance.
