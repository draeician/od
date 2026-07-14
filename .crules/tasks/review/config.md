# Task: config.py — tiered configuration

Wave: 1

## Module
`src/od/config.py`

## Purpose
Load and deep-merge the four tiers (global -> vault root -> vault ->
flags); TOML reads via `tomllib`; tiny TOML emitter for od-written files.

## Public Interface
- `load(vault: str | None, flag_overrides: dict) -> Config`
- `effective_with_sources() -> list[(key, value, tier)]`
- `emit_toml(dict) -> str`

## Acceptance Criteria
- [x] Partial configs never lose nested defaults (deep-merge, not shallow).
- [x] Alias/reserved-word collision raises `ConfigError`.
- [x] Every option is registered with its tier; unknown-tier options are rejected.
- [x] `RESERVED_WORDS` and the defaults table are defined here as the single source of truth (`resolve` imports from `config`, no cycle).
- [x] Tests added in `tests/test_config.py`.

## Depends On
stdlib only.

## Coder Notes

- **Tiers:** defaults → `~/.config/od/config.toml` (global) →
  `<vault_root>/od.toml` (vault_root) → `<vault>/.od.toml` (vault) →
  `flag_overrides` (flag). Missing files skipped.
- **Registry:** `OPTION_TIERS` maps dotted options to allowed tiers;
  unknown keys / wrong-tier keys → `ConfigError`.
- **Constants:** `RESERVED_WORDS`, `DEFAULTS` live here for resolve/cli.
- **Aliases:** deep-merged maps; keys colliding with reserved words fail loud.
- **`effective_with_sources()`:** rows from last `load()` for `od --config`.
- **`emit_toml`:** minimal writer (tables/scalars/arrays); `None` omitted;
  round-trips via `tomllib`.
- **Verify:** `pytest tests/test_config.py -v` → 14 passed.
- **No version bump** (hold until release).
- Wave 1 complete once this lands (sections + socket + config).
