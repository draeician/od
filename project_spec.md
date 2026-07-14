# Project Specification — od

Single source of truth for scope, stack, and conventions. UX contract detail:
`docs/2026-07-14-od-usage-spec.md`. Module contracts: `docs/2026-07-14-od-module-map.md`.
Team rules: `AGENTS.md`. Workstation notes: `CLAUDE.md`.

## Overview

- **Name**: od
- **Summary**: Fast, low-typing CLI for Obsidian daily notes
- **Package / module**: `od` (`src/od/`)
- **CLI entry**: `od = od.cli:main` (pipx)

## Tech stack

- **Primary language(s)**: Python 3.12+
- **Framework / runtime**: stdlib CLI wrapping the official Obsidian CLI (v1.12+)
- **Packaging**: `pyproject.toml` (setuptools, src layout)
- **Runtime version source**: `src/od/__init__.py` (`__version__`)
- **Dependencies**: stdlib only, except `argcomplete` (matching ol). No other third-party deps without human approval.
- **Environment**: Linux Mint; Obsidian Flatpak `md.obsidian.Obsidian` with CLI enabled; app must be running for live vault ops

## Commands

- **Smoke**: `PYTHONPATH=src python3 -c "from od import __version__; print(__version__)"`
- **Tests**: `PYTHONPATH=src python3 -m pytest`
- **Install**: `pipx install -e .` (or reinstall after changes); no `pip install --break-system-packages`
- **Lint**: match project style (PEP 8 / Ruff-friendly); no mandatory CI yet

## Architecture and conventions

- **Layout**: importable library modules under `src/od/` + thin `cli.py`; one test file per module under `tests/`
- **Module boundaries** (strict, no cycles; lower never imports upper):

  ```text
  cli → resolve, vault, entities, config, state
  vault → obsidian, sections
  entities → sections, config
  obsidian → socket
  resolve → config, state
  sections, socket, config, state → stdlib only
  ```

  `cli.py` is the only module that may print help/prompts or call `sys.exit`;
  library modules raise typed exceptions.

- **Write path**: heading-targeted appends = `daily:read` → modify in Python →
  `create path=... overwrite`. Never blind-append except genuinely new sections.
  Never write back a note that lost content (`WriteSafetyError`).
- **Socket**: self-heal Flatpak IPC symlink before every Obsidian CLI call
  (`socket.ensure()`).
- **Config**: four TOML tiers (global → vault root → vault → flags), deep-merged;
  every option declares its tier at design time.
- **Daily note conventions** (must be preserved):
  - One H1 (`#`) per context section
  - Blank line between consecutive H1 sections on write
  - Todos: `- [ ] text`
  - Log lines: `- YYYY-MM-DD HH:MM :message`
  - Terminal output: fenced code blocks under the relevant heading
  - Unknown target heading → new H1 at end of file; existing heading → append in place
- **Resolution** (see usage spec): exact alias beats reserved prefix; `config` is `--config` only; unrouted piped stdin fails loud
- **CLI help**: `od --help` epilog is the user-facing command surface; keep it aligned with the usage spec

## Hard rules

- No `pip install --break-system-packages`
- No secrets in git
- No `shell=True` in subprocess calls
- No new third-party dependencies without human approval (argcomplete is the sole exception)
- No LLM calls inside od (deterministic capture only)
- Never create Obsidian vaults — GUI only
- Never assume headless Obsidian; the app must be running for live CLI
- Repository edits stay separate from live-system / real daily-note writes unless explicitly testing with a scratch note
- Human-in-the-loop for destructive or architectural changes (`AGENTS.md`)
- Scope discipline: one change, one purpose; no drive-by refactors or rewrites

## Design spirit (inherited from ol)

1. **Less typing** — sane defaults, single-letter aliases, bare `od` is useful, pipes work.
2. **Do the right thing by default** — piped input → fenced code; `done <n>` → toggle; unknown heading → new H1; re-use heading → append.
3. **Fail loud, never silently corrupt** — self-heal socket; verify headings; abort unsafe writes; unrouted pipes error; stdout clean for `| cb`.
4. **Deliberate structure** — side-effect-free imports, deep-merged config, sanitized filenames.

## Status

- [x] Stack, package, version sources, and commands verified from repo files
- [x] Architecture and hard rules distilled from CLAUDE.md + docs (usage/module map)
- Grok layer scaffolded via `/init` (2026-07-14). `AGENTS.md` remains the multi-agent team charter (not the stock Grok `[TEMPLATE]` gate form).
