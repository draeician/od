"""Tests for od.cli — thin shell dispatch (mocked vault I/O)."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from od import __version__, cli as cli_mod
from od import config as config_mod
from od import state as state_mod
from od.config import Config
from od.state import State, StickyExpired
from od.sections import Task
from od.vault import Glance as VaultGlance


@pytest.fixture
def conf_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated HOME + vault_root with vaults work and side."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    root = tmp_path / "vaults"
    root.mkdir()
    (root / "work").mkdir()
    (root / "side").mkdir()

    global_dir = home / ".config" / "od"
    global_dir.mkdir(parents=True)
    (global_dir / "config.toml").write_text(
        f'vault_root = "{root}"\n',
        encoding="utf-8",
    )
    # vaults.default + aliases are vault_root tier (not global).
    (root / "od.toml").write_text(
        '[vaults]\n'
        'default = "work"\n'
        "[aliases]\n"
        't = "truscan modifications"\n'
        'm = "michael brumit"\n'
        'p = "personal updates"\n'
        'c = "daily checks"\n',
        encoding="utf-8",
    )
    config_mod._LAST_CONFIG = None
    config_mod._LAST_SOURCES = None
    return root


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> date:
    today = date(2026, 7, 14)
    monkeypatch.setattr(state_mod, "_today", lambda: today)
    return today


def _run(
    argv: list[str],
    *,
    stdin_data: str = "",
    isatty: bool = True,
) -> tuple[int, str, str]:
    stdin = io.StringIO(stdin_data)
    stdin.isatty = lambda: isatty  # type: ignore[method-assign]
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = cli_mod.run(argv, stdin=stdin, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def test_version_flag(conf_home: Path) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    # argparse version exits via SystemExit inside parse_args path — run catches it
    code = cli_mod.run(
        ["--version"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
    )
    # argparse may write version to stdout and return 0
    combined = stdout.getvalue() + stderr.getvalue()
    assert code == 0
    assert __version__ in combined


def test_help_documents_command_surface(conf_home: Path) -> None:
    """--help epilog stays aligned with the usage contract."""
    code, out, err = _run(["--help"])
    combined = out + err
    assert code == 0
    assert "od --config" in combined
    assert "flag-only" in combined or "flag only" in combined
    assert "exact alias beats" in combined
    assert "cmd | od" in combined or "pipe" in combined.lower()
    assert "vaults" in combined
    assert "sticky" in combined.lower()
    assert "todo" in combined
    # config is not advertised as a positional verb path
    assert "use --config" in combined or "--config" in combined


def test_show_config_flag(conf_home: Path, fixed_today: date) -> None:
    code, out, err = _run(["--config"])
    assert code == 0
    assert "vault_root" in out
    assert "aliases.t" in out or "truscan" in out
    assert err == ""


def test_set_and_show_sticky(conf_home: Path, fixed_today: date) -> None:
    code, out, err = _run(["=", "t"])
    assert code == 0
    assert "sticky:" in err
    assert "truscan modifications" in err

    code, out, err = _run(["="])
    assert code == 0
    assert "truscan modifications" in out
    assert "vault:" in out


def test_set_vault(conf_home: Path, fixed_today: date) -> None:
    code, out, err = _run(["v", "side"])
    assert code == 0
    assert "side" in err
    st = state_mod.get(check_sticky=False)
    assert st.active_vault == "side"


def test_list_vaults(conf_home: Path, fixed_today: date) -> None:
    state_mod.set_vault("work")
    code, out, err = _run(["vaults"])
    assert code == 0
    assert "work" in out
    assert "side" in out
    assert "*" in out


def test_no_target_error(conf_home: Path, fixed_today: date) -> None:
    code, out, err = _run(["hello there"])
    assert code == 1
    assert "sticky" in err.lower()
    assert out == ""


def test_append_via_sticky_echoes_stderr(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_mod.set_vault("work")
    state_mod.set_sticky("personal updates")
    calls: list[tuple] = []

    def fake_append(vault: str, heading: str, text: str, style: str = "auto") -> str:
        calls.append((vault, heading, text, style))
        return "ok"

    monkeypatch.setattr(cli_mod.vault, "append", fake_append)
    code, out, err = _run(["shipped it"])
    assert code == 0
    assert calls == [("work", "personal updates", "shipped it", "auto")]
    assert "→ work/personal updates" in err
    assert out == ""


def test_append_explicit_alias(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_mod.set_vault("work")
    calls: list[Any] = []

    def fake_append(vault: str, heading: str, text: str, style: str = "auto") -> str:
        calls.append((vault, heading, text, style))
        return "ok"

    monkeypatch.setattr(cli_mod.vault, "append", fake_append)
    monkeypatch.setattr(
        cli_mod.entities,
        "resolve_alias",
        lambda vault, name: None,
    )
    code, out, err = _run(["t", "note"])
    assert code == 0
    assert calls[0][1] == "truscan modifications"
    assert calls[0][2] == "note"
    # explicit alias does not echo sticky arrow
    assert "→" not in err


def test_piped_stdin_code_append(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_mod.set_vault("work")
    calls: list[Any] = []

    def fake_append(vault: str, heading: str, text: str, style: str = "auto") -> str:
        calls.append((vault, heading, text, style))
        return "ok"

    monkeypatch.setattr(cli_mod.vault, "append", fake_append)
    monkeypatch.setattr(cli_mod.entities, "resolve_alias", lambda *a, **k: None)
    code, out, err = _run(
        ["t"],
        stdin_data="line1\nline2\n",
        isatty=False,
    )
    assert code == 0
    assert calls[0][1] == "truscan modifications"
    assert calls[0][2] == "line1\nline2\n"
    assert calls[0][3] == "code"


def test_piped_alias_c_is_code_not_config(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``echo … | od c`` must append under alias heading, not show config."""
    state_mod.set_vault("work")
    calls: list[Any] = []

    def fake_append(vault: str, heading: str, text: str, style: str = "auto") -> str:
        calls.append((vault, heading, text, style))
        return "ok"

    monkeypatch.setattr(cli_mod.vault, "append", fake_append)
    monkeypatch.setattr(cli_mod.entities, "resolve_alias", lambda *a, **k: None)
    code, out, err = _run(
        ["c"],
        stdin_data="df -h output\n",
        isatty=False,
    )
    assert code == 0
    assert calls == [("work", "daily checks", "df -h output\n", "code")]
    assert "vault_root" not in out
    assert out == ""


def test_piped_stdin_discard_is_loud_error(
    conf_home: Path,
    fixed_today: date,
) -> None:
    """Piped stdin that cannot be routed must error; never silent discard."""
    state_mod.set_vault("work")
    # Reserved verb does not consume stdin
    code, out, err = _run(
        ["todo"],
        stdin_data="should not be discarded silently\n",
        isatty=False,
    )
    assert code != 0
    assert "piped" in err.lower() or "destination" in err.lower()
    assert out == ""

    # Glance (no words) with pipe also errors
    code, out, err = _run(
        [],
        stdin_data="orphan pipe\n",
        isatty=False,
    )
    assert code != 0
    assert "piped" in err.lower() or "destination" in err.lower()

    # --config with pipe must not swallow stdin
    code, out, err = _run(
        ["--config"],
        stdin_data="orphan\n",
        isatty=False,
    )
    assert code != 0
    assert "piped" in err.lower() or "destination" in err.lower()


def test_destination_echo_shows_resolved_heading(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sticky-routed writes echo the heading, not the raw alias token."""
    state_mod.set_vault("work")
    # Store alias key in state (as if expand was skipped on set).
    state_mod.set_sticky("p")
    calls: list[tuple] = []

    def fake_append(vault: str, heading: str, text: str, style: str = "auto") -> str:
        calls.append((vault, heading, text, style))
        return "ok"

    monkeypatch.setattr(cli_mod.vault, "append", fake_append)
    monkeypatch.setattr(cli_mod.entities, "resolve_alias", lambda *a, **k: None)
    code, out, err = _run(["shipped it"])
    assert code == 0
    assert calls == [("work", "personal updates", "shipped it", "auto")]
    # Exact destination line (avoid substring false-positive on ``…/p``).
    assert "→ work/personal updates\n" in err or err.strip() == "→ work/personal updates"
    assert not any(
        line.strip() == "→ work/p" for line in err.splitlines()
    )
    assert out == ""


def test_glance(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_mod.set_vault("work")
    state_mod.set_sticky("todo")

    def fake_glance(vault: str) -> VaultGlance:
        return VaultGlance(
            vault=vault,
            path="daily_notes/2026-07-14.md",
            headings=("personal updates",),
            tasks=(Task(index=1, text="buy milk", heading="personal updates"),),
        )

    monkeypatch.setattr(cli_mod.vault, "glance", fake_glance)
    code, out, err = _run([])
    assert code == 0
    assert "vault: work" in out
    assert "sticky: todo" in out
    assert "personal updates" in out
    assert "buy milk" in out


def test_todo_and_done(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_mod.set_vault("work")

    def fake_glance(vault: str) -> VaultGlance:
        return VaultGlance(
            vault=vault,
            path="d.md",
            headings=(),
            tasks=(Task(index=1, text="a", heading="x"),),
        )

    done_calls: list[int] = []

    monkeypatch.setattr(cli_mod.vault, "glance", fake_glance)
    monkeypatch.setattr(
        cli_mod.vault,
        "complete_task",
        lambda vault, n: done_calls.append(n) or "ok",
    )

    code, out, err = _run(["todo"])
    assert code == 0
    assert "1. a" in out

    code, out, err = _run(["done", "1"])
    assert code == 0
    assert done_calls == [1]
    assert "done 1" in err


def test_new_section(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_mod.set_vault("work")
    calls: list[str] = []
    monkeypatch.setattr(
        cli_mod.vault,
        "new_section",
        lambda vault, heading: calls.append(heading) or "ok",
    )
    code, out, err = _run(["new", "daily checks"])
    assert code == 0
    assert calls == ["daily checks"]
    assert "daily checks" in err


def test_who(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_mod.set_vault("work")
    from od.entities import Entity

    ent = Entity(
        slug="michael-brumit",
        type="person",
        title="Michael Brumit",
        relpath="entities/people/michael-brumit.md",
        aliases=("m",),
    )
    monkeypatch.setattr(
        cli_mod.entities,
        "resolve_alias",
        lambda vault, name: ent if name == "m" else None,
    )
    code, out, err = _run(["who", "m"])
    assert code == 0
    assert "Michael Brumit" in out
    assert "michael-brumit" in out

    code, out, err = _run(["who", "nobody"])
    assert code == 1
    assert "no entity" in err


def test_usage_error_exit_2(conf_home: Path, fixed_today: date) -> None:
    code, out, err = _run(["done"])
    assert code == 2
    assert err


def test_expired_sticky_blocks_append(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_mod.set_vault("work")
    # Write sticky for yesterday via raw path
    root = conf_home
    (root / "od-state.toml").write_text(
        'active_vault = "work"\n'
        'sticky_target = "todo"\n'
        'sticky_set_on = "2026-07-13"\n',
        encoding="utf-8",
    )
    code, out, err = _run(["hello"])
    assert code == 1
    assert "expired" in err.lower()


def test_glance_works_with_expired_sticky(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (conf_home / "od-state.toml").write_text(
        'active_vault = "work"\n'
        'sticky_target = "todo"\n'
        'sticky_set_on = "2026-07-13"\n',
        encoding="utf-8",
    )

    def fake_glance(vault: str) -> VaultGlance:
        return VaultGlance(
            vault=vault,
            path="d.md",
            headings=(),
            tasks=(),
        )

    monkeypatch.setattr(cli_mod.vault, "glance", fake_glance)
    code, out, err = _run([])
    assert code == 0
    assert "vault: work" in out


def test_vault_override_flag(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_mod.set_vault("work")
    seen: list[str] = []

    def fake_glance(vault: str) -> VaultGlance:
        seen.append(vault)
        return VaultGlance(vault=vault, path="d.md", headings=(), tasks=())

    monkeypatch.setattr(cli_mod.vault, "glance", fake_glance)
    code, out, err = _run(["-v", "side"])
    assert code == 0
    assert seen == ["side"]
    # state unchanged
    assert state_mod.get(check_sticky=False).active_vault == "work"


def test_entity_wikilink_on_append(
    conf_home: Path,
    fixed_today: date,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from od.entities import Entity

    state_mod.set_vault("work")
    ent = Entity(
        slug="michael-brumit",
        type="person",
        title="Michael Brumit",
        relpath="entities/people/michael-brumit.md",
    )
    monkeypatch.setattr(
        cli_mod.entities,
        "resolve_alias",
        lambda vault, name: ent,
    )
    calls: list[Any] = []

    def fake_append(vault: str, heading: str, text: str, style: str = "auto") -> str:
        calls.append(text)
        return "ok"

    monkeypatch.setattr(cli_mod.vault, "append", fake_append)
    code, out, err = _run(["m", "discussed migration"])
    assert code == 0
    assert "[[michael-brumit]]" in calls[0]
    assert "discussed migration" in calls[0]


def test_bootstrap_creates_template_when_no_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    config_mod._LAST_CONFIG = None
    config_mod._LAST_SOURCES = None

    code, out, err = _run([], isatty=False)
    assert code == 1
    cfg_path = home / ".config" / "od" / "config.toml"
    assert cfg_path.is_file()
    assert "created config template" in err or "vault_root" in err
    assert "vault_root" in cfg_path.read_text(encoding="utf-8")


def test_bootstrap_yn_sets_vault_root_from_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    config_mod._LAST_CONFIG = None
    config_mod._LAST_SOURCES = None

    collection = tmp_path / "obsidian"
    collection.mkdir()
    (collection / "work").mkdir()
    (collection / "side").mkdir()

    seen: list[str] = []

    def fake_glance(vault: str) -> VaultGlance:
        seen.append(vault)
        return VaultGlance(vault=vault, path="d.md", headings=(), tasks=())

    monkeypatch.setattr(cli_mod.vault, "glance", fake_glance)

    # y → set vault_root; then no active vault → need default or -v vault name
    # After y with collection path, override cleared; vaults.default missing → error or pick
    code, out, err = _run(
        ["-v", str(collection)],
        stdin_data="y\n",
        isatty=True,
    )
    cfg_path = home / ".config" / "od" / "config.toml"
    assert cfg_path.is_file()
    text = cfg_path.read_text(encoding="utf-8")
    assert str(collection) in text
    assert "wrote vault_root" in err
    # Should progress past missing vault_root (may still fail no active vault)
    assert "vault_root is not set; cannot read/write state" not in err


def test_bootstrap_n_leaves_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    config_mod._LAST_CONFIG = None
    config_mod._LAST_SOURCES = None

    collection = tmp_path / "obsidian"
    collection.mkdir()

    code, out, err = _run(
        ["-v", str(collection)],
        stdin_data="n\n",
        isatty=True,
    )
    assert code == 1
    cfg_path = home / ".config" / "od" / "config.toml"
    assert cfg_path.is_file()
    # template without vault_root assignment (commented only)
    body = cfg_path.read_text(encoding="utf-8")
    assert "wrote vault_root" not in err
    assert "ok; edit" in err or "edit" in err
