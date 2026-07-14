# od — Usage Specification (UX Contract)

_Status: BRAINSTORMING draft, 2026-07-14. This document is the user-experience contract; the module map and code derive from it. Design flows from user experience backward._

## Philosophy (inherited from ol, via the Design Spirit in CLAUDE.md)

Less typing; do the right thing by default; fail loud, never silently corrupt; deliberate structure. od captures, ol thinks: od stays deterministic — no LLM calls inside od.

## Installation & Shape

- pipx install; package `od` — importable library (`od.vault`, `od.sections`, `od.entities`, `od.config`, `od.socket`) + thin `cli.py`.
- Stdlib only, except `argcomplete` (matching ol).
- Requires the Obsidian app running with official CLI enabled; od self-heals the flatpak socket symlink before every run.

## Configuration (four tiers, TOML everywhere)

Deep-merged in order, later wins (ol-style: partial configs never lose nested keys):

| Tier | File | Scope | Holds |
|---|---|---|---|
| 1 Global | `~/.config/od/config.toml` | machine-local bootstrap | `vault_root` (differs per host), socket quirks |
| 2 Vault root | `<vault_root>/od.toml` | universal, travels with the vault collection | aliases, entity types, default vault |
| 3 Vault | `<vault>/.od.toml` | per-vault overrides | vault-specific aliases, entity dir |
| 4 CLI flags | — | per-invocation | anything |

**Hard rule: every new option must declare its tier at design time** (global / vault root / vault / flag). No agent may add an option without placing it in this table.

```toml
# ~/.config/od/config.toml (tier 1)
vault_root = "~/Documents/vaults"

# <vault_root>/od.toml (tier 2)
[vaults]
default = "draeician"           # fallback when state is empty
[aliases]
t = "truscan modifications"
m = "michael brumit"
p = "personal updates"
c = "daily checks"
[entities]
dir = "entities"
```

- Config loading fails loud if an alias collides with a reserved word.
- `od --config` prints the effective merged config, annotated with which tier each value came from.

## Sticky State

`<vault_root>/od-state.toml` — lives with the vaults so every host/workstation shares it when the root is synced or moved. Separate from config (config = deliberate defaults; state = current mood). Fields: `active_vault`, `sticky_target`, `sticky_prev`, `sticky_set_on` (date).

Known trade-off: a shared state file is a sync hotspot (two hosts writing → last-write-wins conflicts). Accepted for v1 — the file is tiny. Escape hatch designed but NOT implemented: `sticky_scope = "shared" | "host"` (tier 2 option), only if this ever bites.

- `od v <name>` sets `active_vault`; it persists until changed. Config `vaults.default` is only the fallback when state is empty. Vaults are created in the Obsidian GUI only — od never creates vaults (hard boundary).
- Sticky target grammar:

```
od = todo          # set sticky target (alias or heading)
od =               # show current sticky + active vault
od = -             # swap to previous sticky
od = off           # clear
od "text"          # sticky set → append there; unset → loud error, never guess
od t "one-off"     # explicit alias always wins; sticky untouched
```

- **Sticky targets expire at end of day** (daily notes = daily context). Using an expired sticky errors: "sticky 'todo' expired, re-set with `od = todo`". Active vault does not expire.
- Visibility guards: every sticky-routed write echoes its destination to stderr (`→ draeician/todo`); bare `od` glance leads with `vault: draeician  sticky: todo`.
- Only vault and target are sticky. Nothing else.

## Command Surface

Reserved words (never valid as aliases): `vaults`, `todo`, `done`, `new`, `who`, `config` (flag form), plus future verbs.

| Command | Behavior |
|---|---|
| `od` | Today at a glance: today's note outline (H1 headings) + open tasks |
| `od --config` | Show effective merged config |
| `od vaults` (or unambiguous prefix, e.g. `od v`) | List vaults (directories under `vaults.root`), active marked |
| `od v <name>` | Set active vault (sticky, persists in state) |
| `od = …` | Sticky target management (see Sticky State) |
| `od "text"` | Append to sticky target in active vault; error if no sticky set |
| `od <alias\|heading> "text"` | Append under heading, auto-formatted per section style (todo/log/plain); insert entity wikilink if the alias maps to an entity |
| `cmd \| od <alias\|heading>` | Piped stdin → fenced code block under heading |
| `od todo` | List open tasks across today's note |
| `od done <n>` | Mark task n complete |
| `od new "heading"` | Create new H1 section |
| `od who <name\|alias>` | Resolve any alias to its canonical entity; show the entity card |

Resolution rules:

- **Prefix matching**: an unambiguous prefix of a reserved word resolves to it; ambiguous → error listing candidates (git-style). Aliases match exactly.
- **Tab completion**: argcomplete (`eval "$(register-python-argcomplete od)"`) completes reserved words, aliases, vault names, entity slugs.
- Unknown target heading → new H1 at end of file (per daily-note conventions).

## Write Safety (fail loud)

- Heading-targeted writes are read → modify → overwrite (`daily:read` → Python → `create … overwrite`); never blind-append except genuinely new sections.
- Never write back a note that lost content: post-modify sanity check (result contains all prior sections and is not shorter than the original minus nothing) or abort with stderr error.
- Socket dead and unheal-able, Obsidian not running, ambiguous prefix, alias/reserved collision → clear stderr error, non-zero exit, no write.
- stdout carries only useful output (`od … | cb` stays clean); warnings/errors → stderr.

## Entities (OKF integration)

- `entities/` inside the vault is an OKF bundle: one markdown file per concept, YAML frontmatter, path = identity.
- Types (start small): `person`, `organization`, `system`, `project`, `topic`.
- Frontmatter: `type` (required), `title`, `aliases` (list — the Rosetta stone for vocabulary drift: many workplace names → one canonical entity), `tags`, plus `org:` on persons.
- od owns entity creation and slug generation (stable slugs; humans don't hand-name files — renames break links).
- Capture-time linking: when an alias maps to an entity, `od m "discussed migration"` appends the line **and** inserts `[[michael-brumit]]`; missing entity file → OKF stub auto-created.

## Ecosystem

- **Library consumers**: m365cli's `m365 daily` writes through `od.vault`.
- **Distill**: future `od` verb shells out to `ol` (subprocess, optional — degrade with a clear message if absent). ol-as-library is a later ol-repo task, informed by what API od actually needs.
- **Repo scaffolding at birth** (ap-style): canonical `AGENTS.md` (from `../team-conventions/` charter), `.crules/modes/` personas + task pipeline, git policy (conventional commits, SemVer, secret scan, version-string consistency), pytest from day one, one guarded subprocess runner, argv lists only, no `shell=True`.

## Resolved Questions

- **Config format: TOML** (stdlib `tomllib` for reads; od emits its own tiny writer). Layout: see Configuration tiers.
- **No active vault:** TTY → list vaults under `vault_root`, prompt to pick, save to state. Non-TTY (piped/scripted) → stderr `no active vault; run: od v NAME`, exit non-zero. Never prompt in a pipeline.
- **`-v NAME` global flag:** yes, day one — per-invocation vault override (tier 4), does not touch state.
- **Entity commands:** v1 ships only `od who` (lookup) + capture-time auto-stub. No `entity new` verb — creating/enriching entities is an editing task and Obsidian is the editor; the verb can be added later without breakage. Auto-stub always announces itself on stderr (`created entity: people/michael-brumit.md`).
