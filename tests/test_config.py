"""Tests for od.config — tiered TOML configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from od import config as config_mod
from od.config import (
    DEFAULTS,
    OPTION_TIERS,
    RESERVED_WORDS,
    ConfigError,
    effective_with_sources,
    emit_toml,
    load,
)


@pytest.fixture(autouse=True)
def _reset_last_load() -> None:
    config_mod._LAST_CONFIG = None
    config_mod._LAST_SOURCES = None


@pytest.fixture
def conf_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated HOME + vault collection layout for load()."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    vault_root = tmp_path / "vaults"
    vault_root.mkdir()
    (vault_root / "draeician").mkdir()

    global_dir = home / ".config" / "od"
    global_dir.mkdir(parents=True)
    (global_dir / "config.toml").write_text(
        f'vault_root = "{vault_root}"\n',
        encoding="utf-8",
    )
    return vault_root


def test_reserved_words_and_defaults_are_defined() -> None:
    assert "todo" in RESERVED_WORDS
    assert "vaults" in RESERVED_WORDS
    assert "who" in RESERVED_WORDS
    assert "config" in RESERVED_WORDS
    assert DEFAULTS["entities"]["dir"] == "entities"
    assert "vault_root" in OPTION_TIERS
    assert "aliases" in OPTION_TIERS


def test_deep_merge_preserves_nested_defaults(conf_tree: Path) -> None:
    (conf_tree / "od.toml").write_text(
        '[aliases]\nt = "truscan modifications"\n',
        encoding="utf-8",
    )
    cfg = load(None, {})
    # Partial vault-root file must not wipe entities.dir default.
    assert cfg.entities_dir == "entities"
    assert cfg.aliases["t"] == "truscan modifications"
    assert cfg.vault_root == str(conf_tree)


def test_later_tier_overrides_leaf_keeps_siblings(conf_tree: Path) -> None:
    (conf_tree / "od.toml").write_text(
        '[aliases]\n'
        't = "truscan modifications"\n'
        'm = "michael brumit"\n'
        '[entities]\n'
        'dir = "entities"\n',
        encoding="utf-8",
    )
    vault = conf_tree / "draeician"
    (vault / ".od.toml").write_text(
        '[aliases]\n'
        'm = "michael override"\n'
        '[entities]\n'
        'dir = "people"\n',
        encoding="utf-8",
    )
    cfg = load("draeician", {})
    assert cfg.aliases["t"] == "truscan modifications"
    assert cfg.aliases["m"] == "michael override"
    assert cfg.entities_dir == "people"


def test_alias_reserved_word_collision_raises(conf_tree: Path) -> None:
    (conf_tree / "od.toml").write_text(
        '[aliases]\ntodo = "my todos"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="reserved word"):
        load(None, {})


def test_unknown_option_rejected(conf_tree: Path) -> None:
    (conf_tree / "od.toml").write_text("mystery = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown option"):
        load(None, {})


def test_option_at_wrong_tier_rejected(conf_tree: Path) -> None:
    # vault_root is global/flag only — not allowed in vault-root od.toml
    (conf_tree / "od.toml").write_text(
        'vault_root = "/somewhere"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="not allowed at tier"):
        load(None, {})


def test_flag_overrides_win(conf_tree: Path) -> None:
    (conf_tree / "od.toml").write_text(
        '[vaults]\ndefault = "draeician"\n',
        encoding="utf-8",
    )
    cfg = load(None, {"vaults": {"default": "other"}})
    assert cfg.vaults_default == "other"


def test_effective_with_sources_tracks_tiers(conf_tree: Path) -> None:
    (conf_tree / "od.toml").write_text(
        '[vaults]\ndefault = "draeician"\n'
        '[aliases]\nt = "truscan modifications"\n',
        encoding="utf-8",
    )
    load(None, {"aliases": {"x": "extra"}})
    rows = effective_with_sources()
    by_key = {key: (value, tier) for key, value, tier in rows}
    assert by_key["vault_root"][1] == "global"
    assert by_key["vaults.default"] == ("draeician", "vault_root")
    assert by_key["aliases.t"] == ("truscan modifications", "vault_root")
    assert by_key["aliases.x"] == ("extra", "flag")
    assert by_key["entities.dir"][1] == "default"


def test_effective_with_sources_before_load_raises() -> None:
    with pytest.raises(ConfigError, match="no config loaded"):
        effective_with_sources()


def test_emit_toml_round_trip() -> None:
    data = {
        "vault_root": "/tmp/vaults",
        "vaults": {"default": "draeician"},
        "aliases": {"t": "truscan modifications", "m": "michael brumit"},
        "entities": {"dir": "entities"},
        "flag": True,
        "count": 3,
    }
    text = emit_toml(data)
    parsed = tomllib.loads(text)
    assert parsed["vault_root"] == "/tmp/vaults"
    assert parsed["vaults"]["default"] == "draeician"
    assert parsed["aliases"]["t"] == "truscan modifications"
    assert parsed["entities"]["dir"] == "entities"
    assert parsed["flag"] is True
    assert parsed["count"] == 3


def test_emit_toml_omits_none() -> None:
    text = emit_toml({"vault_root": None, "entities": {"dir": "entities"}})
    parsed = tomllib.loads(text)
    assert "vault_root" not in parsed
    assert parsed["entities"]["dir"] == "entities"


def test_missing_files_use_defaults_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    cfg = load(None, {})
    assert cfg.vault_root is None
    assert cfg.aliases == {}
    assert cfg.entities_dir == "entities"
    assert cfg.vaults_default is None


def test_vault_name_requires_vault_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    (home / ".config" / "od").mkdir(parents=True)
    # global config present but no vault_root
    (home / ".config" / "od" / "config.toml").write_text("", encoding="utf-8")
    with pytest.raises(ConfigError, match="vault_root is not set"):
        load("draeician", {})


def test_absolute_vault_path_skips_name_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    (home / ".config" / "od").mkdir(parents=True)
    (home / ".config" / "od" / "config.toml").write_text("", encoding="utf-8")

    vault = tmp_path / "standalone"
    vault.mkdir()
    (vault / ".od.toml").write_text(
        '[aliases]\np = "personal updates"\n',
        encoding="utf-8",
    )
    cfg = load(str(vault), {})
    assert cfg.aliases["p"] == "personal updates"


def test_write_global_config_template_creates_dir_and_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    path, written = config_mod.write_global_config_template()
    assert written is True
    assert path == home / ".config" / "od" / "config.toml"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "vault_root" in text
    assert path.parent.is_dir()

    # Second call is a no-op
    path2, written2 = config_mod.write_global_config_template()
    assert written2 is False
    assert path2 == path


def test_write_global_vault_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    root = tmp_path / "vaults"
    root.mkdir()
    path = config_mod.write_global_vault_root(str(root))
    assert path.is_file()
    cfg = load(None, {})
    assert cfg.vault_root == str(root)
