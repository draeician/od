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
- [ ] Partial configs never lose nested defaults (deep-merge, not shallow).
- [ ] Alias/reserved-word collision raises `ConfigError`.
- [ ] Every option is registered with its tier; unknown-tier options are rejected.
- [ ] `RESERVED_WORDS` and the defaults table are defined here as the single source of truth (`resolve` imports from `config`, no cycle).
- [ ] Tests added in `tests/test_config.py`.

## Depends On
stdlib only.
