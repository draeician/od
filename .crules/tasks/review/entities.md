# Task: entities.py — OKF bundle

Wave: 2 (last piece)

## Module
`src/od/entities.py`

## Purpose
Entity resolution and auto-stub in `<vault>/entities/`.

## Public Interface
- `resolve_alias(vault, name) -> Entity | None`
- `ensure(vault, slug, type, title) -> (Entity, created: bool)`
- `wikilink(entity) -> str`
- `card(entity) -> str`
- `slugify(text) -> str`
- `parse_frontmatter(text) -> (meta, body)` (minimal YAML subset)

## Acceptance Criteria
- [x] Slugs are stable, lowercase, hyphenated (`slugify`).
- [x] `type` is one of person/organization/system/project/topic.
- [x] `ensure` never modifies an existing entity file; returns `created` flag.
- [x] `resolve_alias` searches frontmatter `aliases` (and slug/title) across the bundle.
- [x] Depends only on `config`, stdlib (frontmatter subset local — sections has no FM API yet).
- [x] Tests in `tests/test_entities.py` (temp vault; no real vault writes required).

## Depends On
config, stdlib.

## Coder Notes

- **Layout:** `<vault>/<entities.dir>/<type-plural>/<slug>.md`  
  person→people, organization→organizations, system→systems,
  project→projects, topic→topics (matches usage example path).
- **API:** first arg is `vault` (name under vault_root or absolute path) so
  multi-vault works without importing `state`.
- **Frontmatter:** minimal subset parser in-module (`parse_frontmatter`);
  module map wanted sections — deferred until a second consumer needs it.
- **`ensure`:** exclusive create (`open("x")`); existing file returned
  unchanged with `created=False`.
- **`resolve_alias`:** case-insensitive; unique slug match preferred when
  multiple keys hit; else `AmbiguousEntity`.
- **Verify:** `pytest tests/test_entities.py -v` → 19 passed; full suite 105.
- **Live:** Obsidian CLI smoke (named vaults `riddell`/`draeician`):
  `socket.ensure` healed symlink; `daily:path` → `daily_notes/2026-07-14.md`.
  Absolute `vault=/path` not accepted by Obsidian CLI (name/id only). No
  `entities/` bundle on those vaults yet — entity tests remain unit-only.
- **No version bump** (hold until release).
- Wave 2 complete: state, obsidian, entities all in review.
