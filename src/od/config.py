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

from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "ConfigError",
    "Config",
    "RESERVED_WORDS",
    "DEFAULTS",
    "OPTION_TIERS",
    "load",
    "effective_with_sources",
    "emit_toml",
    "global_config_path",
    "ensure_global_config_dir",
    "write_global_config_template",
    "write_global_vault_root",
    "GLOBAL_CONFIG_TEMPLATE",
]

# ---------------------------------------------------------------------------
# Constants (single source of truth for resolve / cli)
# ---------------------------------------------------------------------------

RESERVED_WORDS: frozenset[str] = frozenset(
    {
        "vaults",
        "todo",
        "done",
        "new",
        "who",
        "config",
    }
)

# Defaults applied as the implicit base layer before any file/flag tier.
DEFAULTS: dict[str, Any] = {
    "vault_root": None,
    "vaults": {
        "default": None,
    },
    "aliases": {},
    "entities": {
        "dir": "entities",
    },
}

# Dotted option path -> tiers that may set it.
# Nested maps: "aliases" is registered as a whole table; leaf keys under it
# are alias names (not separate options) and may not be reserved words.
OPTION_TIERS: dict[str, frozenset[str]] = {
    "vault_root": frozenset({"global", "flag"}),
    "vaults.default": frozenset({"vault_root", "flag"}),
    "aliases": frozenset({"vault_root", "vault", "flag"}),
    "entities.dir": frozenset({"vault_root", "vault", "flag"}),
}

_TIER_ORDER = ("default", "global", "vault_root", "vault", "flag")


class ConfigError(Exception):
    """Raised when configuration is invalid or unusable."""


@dataclass(frozen=True)
class Config:
    """Effective configuration after deep-merging all tiers."""

    data: dict[str, Any]

    @property
    def vault_root(self) -> str | None:
        value = self.data.get("vault_root")
        if value is None or value == "":
            return None
        return str(value)

    @property
    def vaults_default(self) -> str | None:
        vaults = self.data.get("vaults") or {}
        value = vaults.get("default")
        if value is None or value == "":
            return None
        return str(value)

    @property
    def aliases(self) -> dict[str, str]:
        raw = self.data.get("aliases") or {}
        return {str(k): str(v) for k, v in raw.items()}

    @property
    def entities_dir(self) -> str:
        entities = self.data.get("entities") or {}
        return str(entities.get("dir", "entities"))


# Last successful load — backs effective_with_sources() for `od --config`.
_LAST_CONFIG: Config | None = None
_LAST_SOURCES: list[tuple[str, Any, str]] | None = None


def global_config_path() -> Path:
    """Return ``~/.config/od/config.toml`` (tier-1 global config path)."""
    return Path.home() / ".config" / "od" / "config.toml"


def _global_config_path() -> Path:
    """Internal alias kept for existing call sites."""
    return global_config_path()


def _vault_root_config_path(vault_root: Path) -> Path:
    return vault_root / "od.toml"


# Template written when the user has no global config yet. Comments only —
# vault_root must be set by the user (or interactive bootstrap in cli).
GLOBAL_CONFIG_TEMPLATE = """\
# od global config (tier 1) — machine-local bootstrap
# https://github.com/draeician/od
#
# Set vault_root to the directory that *contains* your Obsidian vaults
# (the parent of each vault folder). Paths may use ~ for home.
#
# Example:
#   vault_root = "~/Documents/vaults"
#
# Then open a vault in Obsidian, and either:
#   od v <vault-name>     # sticky active vault
#   od -v <vault-name>    # one-shot override
#
# Optional collection defaults live in <vault_root>/od.toml (tier 2), e.g.:
#   [vaults]
#   default = "my-vault"
#   [aliases]
#   t = "truscan modifications"
#   m = "michael brumit"
#   p = "personal updates"
#   c = "daily checks"
#
# vault_root = "~/path/to/vaults"
"""


def ensure_global_config_dir() -> Path:
    """Create ``~/.config/od`` if missing. Returns the directory path.

    Raises:
        ConfigError: If the directory cannot be created.
    """
    path = global_config_path().parent
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigError(f"cannot create config directory {path}: {exc}") from exc
    return path


def write_global_config_template(*, overwrite: bool = False) -> tuple[Path, bool]:
    """Ensure global config dir exists and write a template config.toml if needed.

    Args:
        overwrite: When True, replace an existing config.toml with the template.

    Returns:
        ``(path, written)`` where *written* is True only if this call created
        or replaced the file.

    Raises:
        ConfigError: On I/O failure.
    """
    ensure_global_config_dir()
    path = global_config_path()
    if path.is_file() and not overwrite:
        return path, False
    try:
        path.write_text(GLOBAL_CONFIG_TEMPLATE, encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot write config template {path}: {exc}") from exc
    return path, True


def write_global_vault_root(vault_root: str) -> Path:
    """Write (or replace) global config.toml with *vault_root* set.

    Preserves a short header comment. Does not create Obsidian vaults.

    Args:
        vault_root: Absolute or ``~``-prefixed path to the vault collection.

    Returns:
        Path to the written config.toml.

    Raises:
        ConfigError: If *vault_root* is empty or write fails.
    """
    if not vault_root or not str(vault_root).strip():
        raise ConfigError("vault_root must be non-empty")
    root = str(vault_root).strip()
    ensure_global_config_dir()
    path = global_config_path()
    body = (
        "# od global config (tier 1) — machine-local bootstrap\n"
        f"vault_root = {_toml_string(root)}\n"
    )
    try:
        path.write_text(body, encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot write config {path}: {exc}") from exc
    return path


def _vault_config_path(vault_dir: Path) -> Path:
    return vault_dir / ".od.toml"


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge *overlay* onto *base* without dropping nested keys from base."""
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _is_plain_map(value: Any) -> bool:
    return isinstance(value, dict)


def _validate_aliases(aliases: Any, *, context: str) -> dict[str, str]:
    if not isinstance(aliases, dict):
        raise ConfigError(f"{context}: aliases must be a table")
    out: dict[str, str] = {}
    for key, value in aliases.items():
        name = str(key)
        if name in RESERVED_WORDS:
            raise ConfigError(
                f"{context}: alias {name!r} collides with reserved word"
            )
        if not isinstance(value, (str, int, float, bool)):
            raise ConfigError(
                f"{context}: alias {name!r} value must be a string, got {type(value).__name__}"
            )
        out[name] = str(value)
    return out


def _validate_and_normalize(data: dict[str, Any], tier: str) -> dict[str, Any]:
    """Reject unknown keys and keys not allowed at *tier*; normalize shapes."""
    if not isinstance(data, dict):
        raise ConfigError(f"{tier} config must be a table")

    normalized: dict[str, Any] = {}

    for key, value in data.items():
        if key == "vault_root":
            _require_tier("vault_root", tier)
            if value is not None and not isinstance(value, str):
                raise ConfigError("vault_root must be a string")
            normalized["vault_root"] = value
        elif key == "vaults":
            if not _is_plain_map(value):
                raise ConfigError("vaults must be a table")
            vaults_out: dict[str, Any] = {}
            for sub_key, sub_val in value.items():
                path = f"vaults.{sub_key}"
                if path not in OPTION_TIERS:
                    raise ConfigError(f"unknown option: {path}")
                _require_tier(path, tier)
                if sub_val is not None and not isinstance(sub_val, str):
                    raise ConfigError(f"{path} must be a string")
                vaults_out[sub_key] = sub_val
            normalized["vaults"] = vaults_out
        elif key == "aliases":
            _require_tier("aliases", tier)
            normalized["aliases"] = _validate_aliases(
                value, context=f"{tier} config"
            )
        elif key == "entities":
            if not _is_plain_map(value):
                raise ConfigError("entities must be a table")
            entities_out: dict[str, Any] = {}
            for sub_key, sub_val in value.items():
                path = f"entities.{sub_key}"
                if path not in OPTION_TIERS:
                    raise ConfigError(f"unknown option: {path}")
                _require_tier(path, tier)
                if not isinstance(sub_val, str):
                    raise ConfigError(f"{path} must be a string")
                entities_out[sub_key] = sub_val
            normalized["entities"] = entities_out
        else:
            raise ConfigError(f"unknown option: {key}")

    return normalized


def _require_tier(option: str, tier: str) -> None:
    allowed = OPTION_TIERS.get(option)
    if allowed is None:
        raise ConfigError(f"unknown option: {option}")
    if tier not in allowed:
        raise ConfigError(
            f"option {option!r} is not allowed at tier {tier!r} "
            f"(allowed: {sorted(allowed)})"
        )


def _read_toml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc
    if not raw.strip():
        return {}
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config root must be a table: {path}")
    return data


def _expand_vault_root(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return str(Path(value).expanduser())


def _resolve_vault_dir(vault: str, vault_root: str | None) -> Path:
    path = Path(vault).expanduser()
    if path.is_absolute():
        return path
    # Relative multi-part paths treated as filesystem paths, not bare names.
    if len(path.parts) > 1:
        return path
    if not vault_root:
        raise ConfigError(
            "vault_root is not set; cannot resolve vault name "
            f"{vault!r} (set vault_root in ~/.config/od/config.toml)"
        )
    return Path(vault_root).expanduser() / vault


def _record_leaves(
    data: dict[str, Any],
    tier: str,
    sources: dict[str, tuple[Any, str]],
    prefix: str = "",
) -> None:
    """Update leaf source map for every scalar / alias entry in *data*."""
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if path == "aliases" and isinstance(value, dict):
            for alias, heading in value.items():
                sources[f"aliases.{alias}"] = (heading, tier)
        elif isinstance(value, dict):
            _record_leaves(value, tier, sources, path)
        else:
            sources[path] = (value, tier)


def _sources_list(sources: dict[str, tuple[Any, str]]) -> list[tuple[str, Any, str]]:
    items = [(key, val, tier) for key, (val, tier) in sources.items()]
    items.sort(key=lambda row: (_TIER_ORDER.index(row[2]), row[0]))
    return items


def load(vault: str | None, flag_overrides: dict | None = None) -> Config:
    """Load and deep-merge config tiers into a Config.

    Order: defaults → global → vault_root → vault → flags.
    Missing files are skipped. *vault* is a vault directory name under
    ``vault_root``, or an absolute/relative filesystem path. Pass ``None``
    to skip the per-vault tier.
    """
    if flag_overrides is None:
        flag_overrides = {}
    if not isinstance(flag_overrides, dict):
        raise ConfigError("flag_overrides must be a dict")

    sources: dict[str, tuple[Any, str]] = {}
    merged = copy.deepcopy(DEFAULTS)
    _record_leaves(DEFAULTS, "default", sources)

    # Tier 1 — global
    global_raw = _read_toml_file(_global_config_path())
    if global_raw:
        global_norm = _validate_and_normalize(global_raw, "global")
        merged = _deep_merge(merged, global_norm)
        _record_leaves(global_norm, "global", sources)

    vault_root = _expand_vault_root(merged.get("vault_root"))
    if vault_root is not None:
        merged["vault_root"] = vault_root
        # Keep source entry value expanded when present.
        if "vault_root" in sources:
            _, tier = sources["vault_root"]
            sources["vault_root"] = (vault_root, tier)

    # Tier 2 — vault collection root
    if vault_root is not None:
        root_raw = _read_toml_file(_vault_root_config_path(Path(vault_root)))
        if root_raw:
            root_norm = _validate_and_normalize(root_raw, "vault_root")
            merged = _deep_merge(merged, root_norm)
            _record_leaves(root_norm, "vault_root", sources)

    # Tier 3 — per-vault
    if vault is not None and vault != "":
        vault_dir = _resolve_vault_dir(vault, merged.get("vault_root"))
        vault_raw = _read_toml_file(_vault_config_path(vault_dir))
        if vault_raw:
            vault_norm = _validate_and_normalize(vault_raw, "vault")
            merged = _deep_merge(merged, vault_norm)
            _record_leaves(vault_norm, "vault", sources)

    # Tier 4 — CLI flags
    if flag_overrides:
        flag_norm = _validate_and_normalize(flag_overrides, "flag")
        merged = _deep_merge(merged, flag_norm)
        _record_leaves(flag_norm, "flag", sources)

    # Final alias sweep (merged view) — reserved words never allowed.
    _validate_aliases(merged.get("aliases") or {}, context="effective config")

    config = Config(data=merged)
    global _LAST_CONFIG, _LAST_SOURCES
    _LAST_CONFIG = config
    _LAST_SOURCES = _sources_list(sources)
    return config


def effective_with_sources() -> list[tuple[str, Any, str]]:
    """Return ``(dotted_key, value, tier)`` rows from the last ``load()``.

    Used by ``od --config``. Raises if ``load`` has not been called yet.
    """
    if _LAST_SOURCES is None:
        raise ConfigError("no config loaded; call load() first")
    return list(_LAST_SOURCES)


def emit_toml(data: dict) -> str:
    """Serialize a plain dict to a minimal TOML document string.

    Supports nested tables, strings, ints, floats, bools, and homogeneous
    arrays of those scalars. ``None`` values are omitted. Sufficient for
    od-written state/config files (stdlib has no TOML writer).
    """
    if not isinstance(data, dict):
        raise ConfigError("emit_toml expects a dict")
    lines: list[str] = []
    _emit_table(data, lines, path=())
    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def _toml_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return _toml_string(value)
    raise ConfigError(f"unsupported TOML value type: {type(value).__name__}")


def _emit_table(
    data: dict[str, Any],
    lines: list[str],
    path: tuple[str, ...],
) -> None:
    scalars: list[tuple[str, Any]] = []
    tables: list[tuple[str, dict[str, Any]]] = []
    arrays: list[tuple[str, list[Any]]] = []

    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            tables.append((key, value))
        elif isinstance(value, list):
            arrays.append((key, value))
        else:
            scalars.append((key, value))

    if path and (scalars or arrays):
        header = ".".join(path)
        lines.append(f"[{header}]")

    for key, value in scalars:
        lines.append(f"{key} = {_toml_scalar(value)}")

    for key, value in arrays:
        rendered = ", ".join(_toml_scalar(item) for item in value)
        lines.append(f"{key} = [{rendered}]")

    for key, value in tables:
        if lines and lines[-1] != "":
            lines.append("")
        _emit_table(value, lines, path + (key,))
