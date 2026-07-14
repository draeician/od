# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-14

First feature release of `od`: full module stack from pure daily-note
sections through the thin CLI shell. Version was held at `0.1.0` during
build-out (see `DECISIONS.md`); this minor bump marks the release cut.

### Added

- **sections** — pure daily-note parse/render, H1 sections, todo/log/plain/code append, open tasks, mark done
- **socket** — Flatpak Obsidian CLI IPC socket self-heal before every CLI call
- **config** — four-tier TOML load (global → vault root → vault → flags), deep-merge, `emit_toml`
- **state** — sticky vault/target in `od-state.toml` with end-of-day sticky expiry; atomic writes
- **obsidian** — sole guarded subprocess runner for the Obsidian CLI (`daily:read`, outline, create overwrite, tasks)
- **entities** — OKF entity bundle resolve/ensure/wikilink/card with od-owned slugs
- **vault** — safe RMW orchestration with write-safety (no dropped headings, no silent shrink)
- **resolve** — pure argv → typed Command classifier (reserved prefixes, aliases, sticky `=` grammar)
- **cli** — argparse + argcomplete shell: glance, append, todo/done/new, vaults, sticky, who, `--config`, `-v`

### Notes

- Stdlib only except `argcomplete`
- Runtime version: `src/od/__init__.py` `__version__` (must match `pyproject.toml`)
- Obsidian app must be running with official CLI enabled for live vault ops

## [0.1.0] - 2026-07-14

### Added

- Package scaffold (`src/od/`, tests, `pyproject.toml` entry point)
