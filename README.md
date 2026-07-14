# od

Fast, low-typing CLI for Obsidian daily notes. Heading-targeted appends,
sticky targets, task toggles, and piped code blocks — with sane defaults and
fail-loud safety.

Requires **Obsidian 1.12+** with the official CLI enabled and the app running.

## Install

```bash
pipx install -e .
# after pulls / local changes:
pipx install -e . --force
```

Tab completion (optional):

```bash
eval "$(register-python-argcomplete od)"
```

## Quick start

```bash
# Tier-1: where vaults live
# ~/.config/od/config.toml
#   vault_root = "/path/to/vaults"

# Tier-2: aliases + default vault (travels with the collection)
# <vault_root>/od.toml
```

```toml
[vaults]
default = "draeician"

[aliases]
t = "truscan modifications"
m = "michael brumit"
p = "personal updates"
c = "daily checks"
```

```bash
od v draeician                 # active vault (persists)
od = p                         # sticky → personal updates
od "shipped the fix"           # append under sticky
echo "df -h" | od c            # code block under daily checks
od todo                        # list open tasks
od done 1                      # mark task complete
od --help                      # full command surface
od --config                    # effective merged config + tiers
```

## Commands

| Command | Behavior |
|--------|----------|
| `od` | Today at a glance (H1s + open tasks) |
| `od --config` | Effective merged config (flag only) |
| `od vaults` / `od v` | List vaults (`*` = active) |
| `od v NAME` | Set active vault |
| `od = TARGET` | Set sticky heading (alias expanded) |
| `od =` / `od = -` / `od = off` | Show / swap / clear sticky |
| `od "text"` | Append to sticky (error if unset) |
| `od ALIAS\|HEADING "text"` | Append under heading (`style=auto`) |
| `cmd \| od ALIAS\|HEADING` | Pipe → fenced code block |
| `od todo` / `od done N` | List / complete open tasks |
| `od new "heading"` | Create empty H1 |
| `od who NAME\|ALIAS` | Entity card |
| `-v NAME` | Per-invocation vault override |

### Resolution rules

- **Exact alias** beats reserved-word **prefix** (`c` with alias → heading, never `config`).
- Positional reserved verbs: `vaults`, `todo`, `done`, `new`, `who` (unambiguous prefixes OK).
- **`config` is flag-only** (`od --config`). Not a positional reserved word.
- Unknown heading → new H1 at end of today’s note; re-using a name **appends** under the existing H1.
- Writes leave a **blank line between consecutive H1 sections**.
- Sticky-routed writes echo `→ vault/resolved-heading` on stderr.
- Piped stdin must be routed (`cmd | od <alias|heading>`); otherwise **stderr error**, non-zero exit.

## Config tiers

Later tiers win (deep merge):

1. `~/.config/od/config.toml` — `vault_root`
2. `<vault_root>/od.toml` — aliases, default vault, entities
3. `<vault>/.od.toml` — per-vault overrides
4. CLI flags (`-v`, `--config`)

State (mood, not config): `<vault_root>/od-state.toml` — active vault, sticky target (expires end of day).

## Daily note conventions

- One H1 per context section; blank line between H1 sections on write
- Todos: `- [ ] text`
- Log lines: `- YYYY-MM-DD HH:MM :message`
- Terminal: fenced code blocks under the heading
- `style=auto` follows the existing section (todo / log / plain)

## Development

```bash
PYTHONPATH=src python3 -c "from od import __version__; print(__version__)"
PYTHONPATH=src python3 -m pytest
```

- Package: `src/od/` (stdlib + `argcomplete` only)
- UX contract: [`docs/2026-07-14-od-usage-spec.md`](docs/2026-07-14-od-usage-spec.md)
- Module map: [`docs/2026-07-14-od-module-map.md`](docs/2026-07-14-od-module-map.md)
- Spec / team: [`project_spec.md`](project_spec.md), [`AGENTS.md`](AGENTS.md)

## Flatpak socket

If the Obsidian CLI socket is sandboxed, od self-heals the symlink before each run. The app must still be running with **Settings → General → Command line interface** enabled.
