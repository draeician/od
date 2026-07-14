"""Tests for od.entities — OKF bundle resolve / ensure / card."""

from __future__ import annotations

from pathlib import Path

import pytest

from od import entities as ent_mod
from od.entities import (
    ENTITY_TYPES,
    AmbiguousEntity,
    EntitiesError,
    Entity,
    card,
    ensure,
    parse_frontmatter,
    resolve_alias,
    slugify,
    wikilink,
)


@pytest.fixture
def vault_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated HOME + vault_root with one vault named ``work``."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    root = tmp_path / "vaults"
    root.mkdir()
    vault = root / "work"
    vault.mkdir()

    global_dir = home / ".config" / "od"
    global_dir.mkdir(parents=True)
    (global_dir / "config.toml").write_text(
        f'vault_root = "{root}"\n',
        encoding="utf-8",
    )
    return vault


def _write_entity(
    vault: Path,
    rel: str,
    *,
    entity_type: str,
    title: str,
    aliases: list[str] | None = None,
    tags: list[str] | None = None,
    org: str | None = None,
) -> Path:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"type: {entity_type}", f"title: {title}"]
    if aliases:
        lines.append("aliases:")
        for a in aliases:
            lines.append(f"  - {a}")
    else:
        lines.append("aliases: []")
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {t}")
    if org:
        lines.append(f"org: {org}")
    lines.extend(["---", "", f"# {title}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_slugify_stable_lowercase_hyphenated() -> None:
    assert slugify("Michael Brumit") == "michael-brumit"
    assert slugify("  Foo_Bar  Baz ") == "foo-bar-baz"
    assert slugify("ABC-123") == "abc-123"


def test_slugify_empty_raises() -> None:
    with pytest.raises(EntitiesError):
        slugify("")
    with pytest.raises(EntitiesError):
        slugify("   ")
    with pytest.raises(EntitiesError):
        slugify("!!!")


def test_entity_types_match_spec() -> None:
    assert ENTITY_TYPES == frozenset(
        {"person", "organization", "system", "project", "topic"}
    )


def test_parse_frontmatter_basic() -> None:
    text = (
        "---\n"
        "type: person\n"
        "title: Michael Brumit\n"
        "aliases:\n"
        "  - m\n"
        "  - michael\n"
        "org: Truscan\n"
        "---\n"
        "\n"
        "# Michael Brumit\n"
    )
    meta, body = parse_frontmatter(text)
    assert meta["type"] == "person"
    assert meta["title"] == "Michael Brumit"
    assert meta["aliases"] == ["m", "michael"]
    assert meta["org"] == "Truscan"
    assert body.startswith("\n# Michael Brumit")


def test_parse_frontmatter_inline_list() -> None:
    text = "---\ntype: topic\ntitle: X\naliases: [a, b]\n---\nbody\n"
    meta, body = parse_frontmatter(text)
    assert meta["aliases"] == ["a", "b"]
    assert body == "body\n"


def test_parse_frontmatter_absent() -> None:
    meta, body = parse_frontmatter("# just a note\n")
    assert meta == {}
    assert body == "# just a note\n"


def test_ensure_creates_stub(vault_tree: Path) -> None:
    ent, created = ensure("work", "michael-brumit", "person", "Michael Brumit")
    assert created is True
    assert ent.slug == "michael-brumit"
    assert ent.type == "person"
    assert ent.title == "Michael Brumit"
    assert ent.relpath == "entities/people/michael-brumit.md"
    path = vault_tree / ent.relpath
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "type: person" in text
    assert "title: Michael Brumit" in text
    assert "# Michael Brumit" in text


def test_ensure_never_modifies_existing(vault_tree: Path) -> None:
    path = _write_entity(
        vault_tree,
        "entities/people/michael-brumit.md",
        entity_type="person",
        title="Michael Brumit",
        aliases=["m"],
    )
    original = path.read_text(encoding="utf-8")
    ent, created = ensure("work", "michael-brumit", "person", "OTHER TITLE")
    assert created is False
    assert ent.title == "Michael Brumit"
    assert ent.aliases == ("m",)
    assert path.read_text(encoding="utf-8") == original


def test_ensure_invalid_type(vault_tree: Path) -> None:
    with pytest.raises(EntitiesError, match="invalid entity type"):
        ensure("work", "x", "human", "X")


def test_ensure_rejects_path_slug(vault_tree: Path) -> None:
    with pytest.raises(EntitiesError, match="invalid slug"):
        ensure("work", "../escape", "person", "X")


def test_resolve_alias_by_frontmatter_alias(vault_tree: Path) -> None:
    _write_entity(
        vault_tree,
        "entities/people/michael-brumit.md",
        entity_type="person",
        title="Michael Brumit",
        aliases=["m", "michael"],
        org="Truscan",
    )
    ent = resolve_alias("work", "m")
    assert ent is not None
    assert ent.slug == "michael-brumit"
    assert ent.org == "Truscan"
    assert resolve_alias("work", "MICHAEL") is not None
    assert resolve_alias("work", "michael-brumit") is not None
    assert resolve_alias("work", "Michael Brumit") is not None
    assert resolve_alias("work", "nobody") is None


def test_resolve_alias_ambiguous(vault_tree: Path) -> None:
    _write_entity(
        vault_tree,
        "entities/people/alice.md",
        entity_type="person",
        title="Alice",
        aliases=["shared"],
    )
    _write_entity(
        vault_tree,
        "entities/people/bob.md",
        entity_type="person",
        title="Bob",
        aliases=["shared"],
    )
    with pytest.raises(AmbiguousEntity) as ei:
        resolve_alias("work", "shared")
    assert len(ei.value.matches) == 2


def test_resolve_prefers_unique_slug_among_matches(vault_tree: Path) -> None:
    _write_entity(
        vault_tree,
        "entities/people/shared.md",
        entity_type="person",
        title="Shared Person",
        aliases=["x"],
    )
    _write_entity(
        vault_tree,
        "entities/topics/other.md",
        entity_type="topic",
        title="Other",
        aliases=["shared"],
    )
    # name "shared" matches person slug and topic alias → prefer slug hit
    ent = resolve_alias("work", "shared")
    assert ent is not None
    assert ent.slug == "shared"
    assert ent.type == "person"


def test_wikilink_and_card(vault_tree: Path) -> None:
    ent, _ = ensure("work", "truscan", "organization", "Truscan")
    assert wikilink(ent) == "[[truscan]]"
    text = card(ent)
    assert "Truscan" in text
    assert "type: organization" in text
    assert "slug: truscan" in text
    assert "entities/organizations/truscan.md" in text
    assert "aliases: (none)" in text


def test_card_includes_aliases_tags_org() -> None:
    ent = Entity(
        slug="m",
        type="person",
        title="M",
        relpath="entities/people/m.md",
        aliases=("mike",),
        tags=("work",),
        org="Acme",
    )
    text = card(ent)
    assert "aliases: mike" in text
    assert "tags: work" in text
    assert "org: Acme" in text


def test_absolute_vault_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    (home / ".config" / "od").mkdir(parents=True)
    (home / ".config" / "od" / "config.toml").write_text(
        'vault_root = "/unused"\n',
        encoding="utf-8",
    )
    vault = tmp_path / "direct-vault"
    vault.mkdir()
    ent, created = ensure(str(vault), "topic-a", "topic", "Topic A")
    assert created
    assert (vault / ent.relpath).is_file()
    found = resolve_alias(str(vault), "topic-a")
    assert found is not None
    assert found.title == "Topic A"


def test_custom_entities_dir(vault_tree: Path, tmp_path: Path) -> None:
    root = vault_tree.parent
    (root / "od.toml").write_text(
        '[entities]\ndir = "okf"\n',
        encoding="utf-8",
    )
    ent, created = ensure("work", "sys-one", "system", "Sys One")
    assert created
    assert ent.relpath == "okf/systems/sys-one.md"
    assert (vault_tree / ent.relpath).is_file()


def test_missing_bundle_resolve_returns_none(vault_tree: Path) -> None:
    assert resolve_alias("work", "anything") is None


def test_empty_lookup_raises(vault_tree: Path) -> None:
    with pytest.raises(EntitiesError, match="lookup name"):
        resolve_alias("work", "")
