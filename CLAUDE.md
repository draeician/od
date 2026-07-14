# CLAUDE.md — od (Obsidian Daily) Workstation

## Identity

This workstation builds and maintains `od`, a Python CLI for fast, low-typing updates to Obsidian daily notes. It wraps the official Obsidian CLI (v1.12+) to add heading-targeted appends, quick task capture, timestamped log lines, and piped code blocks. Philosophy mirrors the user's `ol` wrapper: sane defaults, single-letter shortcuts, zero ceremony.

## Resources

| Resource | Location / Value | Notes |
|---|---|---|
| Project code | `od/` (this folder) and `~/git/personal/` clone | Package: library (`src/od/`) + thin CLI, stdlib only, pipx-installable |
| Obsidian install | Flatpak `md.obsidian.Obsidian`, v1.12.7 | Official CLI enabled, binary `obsidian` on PATH |
| Socket fix | `ln -sf /run/user/$(id -u)/.flatpak/md.obsidian.Obsidian/xdg-run/.obsidian-cli.sock /run/user/$(id -u)/.obsidian-cli.sock` | Flatpak sandboxes the IPC socket; link dies on reboot; `od` must self-heal it before every run |
| Obsidian CLI docs | https://obsidian.md/help/cli | `outline`, `daily:read`, `daily:append`, `create ... overwrite`, `tasks`, `task ref=...` |
| Heading alias config | `~/.config/od/config` (planned) | Maps letters to headings: t=truscan modifications, m=michael brumit, p=personal updates, c=daily checks |
| Daily note sample | `Resources/` | Real daily note showing formatting conventions |
| Related project | `../m365cli/` | Future `m365 daily` writes through od's vault-writing code path |

## Team Charter (authoritative)

All work here follows `../team-conventions/2026-07-14-multi-agent-team-charter.md`: human-in-the-loop consultation before anything destructive or architectural, strict scope discipline (no drive-by refactors, no feature removal during bug fixes, no rewrites), and compartmentalized modules with stable documented interfaces so parallel contributors avoid merge conflicts. When the od repo is created, copy the charter in as `AGENTS.md`. This section may not be removed by any agent.

## Design Spirit (inherited from ol)

1. **Less typing.** Sane defaults in `~/.config/od/config`; single-letter heading aliases; bare `od` does something useful; piped input just works.
2. **Do the right thing by default.** Input type implies behavior: piped output → fenced code block, `done <n>` → task toggle, unknown heading → new H1 section.
3. **Fail loud, never silently corrupt.** Self-heal the flatpak socket before every run; verify the target heading after read; never write back a note that lost content — abort with a clear stderr error. stdout carries only useful output so `od ... | cb` stays clean.
4. **Deliberate structure.** Stdlib-only, side-effect-free imports, deep-merged config, no `shell=True`, sanitized filenames.

## Workflow

1. One step at a time; explicit "start here"; wait for approval before multi-step execution.
2. The Obsidian app must be running for the CLI to work — never assume headless operation.
3. Heading-targeted appends are implemented as: `daily:read` → modify section in Python → `create path=... overwrite`. Never blind-append to end of file except for genuinely new sections.
4. Test commands against a scratch note before touching the real daily note.
5. Package layout: importable library modules + thin `cli.py`, stdlib only (argcomplete is the one permitted exception, matching ol). No other third-party dependencies.
6. Repository edits stay separate from live-system changes; no package installs without approval.

## Daily Note Conventions (must be preserved by all writes)

- One H1 (`#`) heading per context section.
- Blank line between consecutive H1 sections (enforced on od writes).
- Todo items: `- [ ] text` under project headings.
- Log lines: `- YYYY-MM-DD HH:MM :message` (timestamp auto-generated).
- Terminal output: fenced code blocks under the relevant heading.
- Unknown target heading → create new H1 section at end of file; existing heading → append under it (no duplicate H1).

## Editorial Rules

- Direct communication; no meta-headers before code blocks.
- Standard Markdown output; never Canvas/Artifacts.
- Linux Mint; `vi` only, never `nano`.
- File-creation scripts use heredoc format: `cat << 'EOF' > filename`.
- `pipx` for installs; `cb` clipboard utility available (`| cb`, `cb -a files`, `cb -t file`).
- New non-code files use `YYYY-MM-DD-descriptive-name` naming.
- Python 3.12; prefer full-file replacements over fragmented edits for substantial changes.
