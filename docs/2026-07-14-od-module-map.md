# od — Module Map (Compartmentalization Plan)

_Status: IMPLEMENTED (as of 0.2.2+). Derives from `2026-07-14-od-usage-spec.md`. Per the team charter: one module = one responsibility = one owner-task; interfaces are contracts; two tasks must never require editing the same file._

## Layout

```text
od/
├── AGENTS.md                  # copied from ../team-conventions charter
├── project_spec.md            # usage spec distilled; single source of truth
├── DECISIONS.md               # append-only decision log
├── pyproject.toml             # pipx entry point: od = od.cli:main
├── src/od/
│   ├── __init__.py            # __version__ only; import is side-effect-free
│   ├── config.py
│   ├── state.py
│   ├── socket.py
│   ├── obsidian.py
│   ├── sections.py
│   ├── vault.py
│   ├── entities.py
│   ├── resolve.py
│   └── cli.py
└── tests/                     # one test file per module, same names
```

## Dependency Direction (strict, no cycles)

```text
cli → resolve, vault, entities, config, state
vault → obsidian, sections
entities → sections (frontmatter), config
obsidian → socket
resolve → config, state
sections, socket, config, state → (stdlib only, no od imports)
```

Lower modules never import upper ones. `cli.py` is the only module allowed to print help/prompts or call `sys.exit`; every library module raises typed exceptions instead.

## Module Contracts

### config.py — tiered configuration
- **Purpose:** load and deep-merge the four tiers (global → vault root → vault → flags); TOML reads via `tomllib`; tiny TOML emitter for od-written files.
- **Public:** `load(vault: str|None, flag_overrides: dict) -> Config`; `effective_with_sources() -> list[(key, value, tier)]` (for `--config`); `emit_toml(dict) -> str`.
- **Invariants:** partial configs never lose nested defaults; alias↔reserved-word collision raises `ConfigError`; every option is registered with its tier — unknown-tier options are rejected.
- **Depends on:** stdlib only. Reserved-word list is imported *from* `resolve`? No — defined here in a plain constants table both use? **Decision: constants live in `config.py` (`RESERVED_WORDS`, defaults table); `resolve` imports config.** Keeps one source of truth without a cycle.

### state.py — sticky state
- **Purpose:** read/write `<vault_root>/od-state.toml`: `active_vault`, `sticky_target`, `sticky_prev`, `sticky_set_on`.
- **Public:** `get() -> State`; `set_vault(name)`; `set_sticky(target)`; `swap_sticky()`; `clear_sticky()`.
- **Invariants:** sticky reads compare `sticky_set_on` to today — expired sticky raises `StickyExpired` (caller decides messaging); writes are atomic (temp file + rename); missing file = empty state, never an error.
- **Depends on:** config (for `vault_root`), stdlib.

### socket.py — flatpak socket self-heal
- **Purpose:** ensure the Obsidian CLI IPC socket symlink exists and is alive before any CLI call.
- **Public:** `ensure() -> None` (raises `SocketError` with the fix-it command text if unhealable).
- **Invariants:** idempotent; recreates `/run/user/$UID/.obsidian-cli.sock` symlink when dead; never touches anything else in `/run`.
- **Depends on:** stdlib only.

### obsidian.py — guarded runner for the Obsidian CLI
- **Purpose:** the ONLY place that spawns the `obsidian` binary (ap's `run_atomicparsley` pattern).
- **Public:** `outline(vault) -> str`; `daily_read(vault) -> str`; `daily_append(vault, text)`; `create_overwrite(vault, path, content)`; `tasks(vault)`; `task_done(vault, ref)`.
- **Invariants:** argv lists only, never `shell=True`; calls `socket.ensure()` first; Obsidian-not-running → `ObsidianError` with actionable message; KeyboardInterrupt → clean termination, exit code 130 propagated as exception; stdout/stderr of the child captured, never leaked raw.
- **Depends on:** socket, stdlib.

### sections.py — daily-note markdown (pure functions, no I/O)
- **Purpose:** parse and modify note text: H1 sections, todo items, timestamped log lines, fenced code blocks. The daily-note conventions live here and only here.
- **Public:** `parse(text) -> Note`; `append_to_section(note, heading, line, style) -> Note`; `add_section(note, heading) -> Note`; `open_tasks(note) -> list[Task]`; `mark_done(note, n) -> Note`; `render(note) -> str`.
- **Invariants:** pure — no file/network/subprocess I/O, fully unit-testable; `render(parse(x)) == x` for untouched notes (round-trip fidelity); style auto-detection (todo/log/plain) follows the conventions table in CLAUDE.md; write transforms (`append_to_section` / `add_section`) leave a blank line between consecutive H1 sections; re-append to an existing heading mutates that section (no duplicate H1).
- **Depends on:** stdlib only. **The most parallel-safe module — hand to any agent in isolation.**

### vault.py — safe read-modify-write orchestration
- **Purpose:** the write-safety layer: `daily_read` → `sections` transform → sanity check → `create_overwrite`.
- **Public:** `append(vault, heading, text, style=auto)`; `glance(vault) -> Glance` (outline + open tasks); `new_section(vault, heading)`; `complete_task(vault, n)`.
- **Invariants:** **never write back a note that lost content** — post-transform check verifies all prior headings present and content not shrunk except by explicit edit; violation raises `WriteSafetyError` and nothing is written; new-section appends are the only blind appends.
- **Depends on:** obsidian, sections.

### entities.py — OKF bundle
- **Purpose:** entity resolution and auto-stub in `<vault>/entities/`.
- **Public:** `resolve_alias(name) -> Entity|None` (searches frontmatter `aliases` across the bundle); `ensure(slug, type, title) -> (Entity, created: bool)`; `wikilink(entity) -> str`; `card(entity) -> str` (for `od who`).
- **Invariants:** slugs generated by od only (stable, lowercase, hyphenated); `type` is one of person/organization/system/project/topic; created stubs announced by caller via the `created` flag; never modifies an existing entity file.
- **Depends on:** config, sections (frontmatter parsing), stdlib.

### resolve.py — command-line word resolution
- **Purpose:** classify argv words: reserved word (with git-style unambiguous-prefix matching), heading alias, `=` grammar, bare text.
- **Public:** `resolve(words, config, state) -> Command` (a typed intent: Glance, SetVault, SetSticky, Append, Todo, Done, New, Who, …); `AmbiguousPrefix` error carries the candidate list; `match_reserved`; `expand_target`.
- **Invariants:** argument-count rule (one positional = text for sticky, two = target + text); resolution order exact positional reserved → exact alias → reserved prefix → free target; exact alias beats reserved prefix; `config` is flag-only (not positional); sticky set expands aliases; explicit alias always beats sticky; no sticky and bare text → `NoTargetError`; pure, no I/O.
- **Depends on:** config, state (types only), stdlib.

### cli.py — thin shell
- **Purpose:** argparse + argcomplete wiring, TTY prompts (vault picker), stderr messaging, exit codes. No business logic.
- **Public:** `main()`, `run()`.
- **Invariants:** the only module that prints or exits; stdout = useful output only (`od … | cb` clean), everything else stderr; `--help` epilog documents the full command surface; `--config` is flag-only (never injected as a positional verb); unrouted piped stdin → error exit; sticky destination echo uses resolved heading; completers pull from config (positional reserved words, aliases), state, vault list; TTY-only prompting.
- **Depends on:** everything above.

## Task Slicing (parallel-safe build order)

| Wave | Tasks (independent within a wave) |
|---|---|
| 1 | `sections.py` + tests; `socket.py` + tests; `config.py` + tests |
| 2 | `state.py`; `obsidian.py`; `entities.py` (each + tests) |
| 3 | `vault.py`; `resolve.py` (each + tests) |
| 4 | `cli.py` + integration smoke against a scratch note |

Each task touches exactly one module file and its test file. Shared files (`DECISIONS.md`) are append-only. Interface changes to any module require consultation per the charter.
