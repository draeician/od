"""config.py — tiered configuration

Purpose:
    Load and deep-merge the four tiers (global -> vault root -> vault ->
    flags); TOML reads via tomllib; tiny TOML emitter for od-written files.

Public:
    load(vault: str | None, flag_overrides: dict) -> Config
    effective_with_sources() -> list[(key, value, tier)]
    emit_toml(dict) -> str

Invariants:
    Partial configs never lose nested defaults; alias/reserved-word
    collision raises ConfigError; every option is registered with its
    tier — unknown-tier options are rejected.

Depends on:
    stdlib only. RESERVED_WORDS and the defaults table live here; resolve
    imports config (keeps one source of truth without a cycle).
"""
