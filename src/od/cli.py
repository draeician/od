"""cli.py — thin shell

Purpose:
    argparse + argcomplete wiring, TTY prompts (vault picker), stderr
    messaging, exit codes. No business logic.

Public:
    main()

Invariants:
    The only module that prints or exits; stdout = useful output only
    (`od ... | cb` clean), everything else stderr; completers pull from
    config (aliases, reserved words), state, vault list, entity slugs;
    TTY-only prompting.

Depends on:
    everything above.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence, TextIO

import argcomplete

from od import __version__, config, entities, resolve, state, vault
from od.config import RESERVED_WORDS, Config, ConfigError
from od.entities import AmbiguousEntity, EntitiesError
from od.obsidian import ObsidianError, ObsidianInterrupted
from od.resolve import (
    Append,
    ClearSticky,
    Command,
    Done,
    Glance,
    ListVaults,
    New,
    NoTargetError,
    ResolveError,
    SetSticky,
    SetVault,
    ShowConfig,
    ShowSticky,
    SwapSticky,
    Todo,
    UsageError,
    Who,
)
from od.sections import DuplicateHeadingError, SectionsError, TaskIndexError
from od.socket import SocketError
from od.state import State, StateError, StickyExpired
from od.vault import VaultError, WriteSafetyError

__all__ = [
    "main",
    "run",
]


# ---------------------------------------------------------------------------
# argparse + completion
# ---------------------------------------------------------------------------


def _list_vault_names(cfg: Config) -> list[str]:
    root = cfg.vault_root
    if not root:
        return []
    root_path = Path(root).expanduser()
    if not root_path.is_dir():
        return []
    names = sorted(
        p.name
        for p in root_path.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name != "od-state.toml"
    )
    return names


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="od",
        description="Fast, low-typing CLI for Obsidian daily notes",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-v",
        "--vault",
        dest="vault_override",
        metavar="NAME",
        default=None,
        help="per-invocation vault override (does not change sticky state)",
    )
    parser.add_argument(
        "--config",
        dest="show_config",
        action="store_true",
        help="print effective merged config with source tiers",
    )
    parser.add_argument(
        "words",
        nargs="*",
        help="command words (reserved verbs, aliases, sticky '=', text)",
    )
    return parser


def _attach_completers(parser: argparse.ArgumentParser) -> None:
    """Best-effort completers; failures must not break the CLI."""

    def complete_words(
        prefix: str,
        parsed_args: argparse.Namespace,
        **_kwargs: object,
    ) -> list[str]:
        try:
            cfg = config.load(parsed_args.vault_override, {})
        except ConfigError:
            cfg = Config(data=dict(config.DEFAULTS))
        # ``config`` is flag-only (``--config``); not a positional completer.
        positional = sorted(w for w in RESERVED_WORDS if w != "config")
        choices = positional + sorted(cfg.aliases.keys())
        choices.extend(["=", "off", "-"])
        try:
            choices.extend(_list_vault_names(cfg))
        except OSError:
            pass
        return [c for c in choices if c.startswith(prefix)]

    def complete_vault(
        prefix: str,
        parsed_args: argparse.Namespace,
        **_kwargs: object,
    ) -> list[str]:
        try:
            cfg = config.load(None, {})
            return [n for n in _list_vault_names(cfg) if n.startswith(prefix)]
        except (ConfigError, OSError):
            return []

    try:
        words_action = next(a for a in parser._actions if a.dest == "words")
        words_action.completer = complete_words  # type: ignore[attr-defined]
        vault_action = next(
            a for a in parser._actions if a.dest == "vault_override"
        )
        vault_action.completer = complete_vault  # type: ignore[attr-defined]
    except (StopIteration, AttributeError):
        pass


# ---------------------------------------------------------------------------
# vault selection
# ---------------------------------------------------------------------------


def _is_interactive() -> bool:
    return bool(sys.stdin.isatty() and sys.stdout.isatty())


def _looks_like_filesystem_path(value: str) -> bool:
    """True if *value* is meant as a path (absolute, ~, or multi-part)."""
    p = Path(value).expanduser()
    if value.startswith("~") or p.is_absolute():
        return True
    return len(p.parts) > 1


def _propose_vault_root_from_path(path: Path) -> tuple[str, str | None]:
    """Infer (vault_root, vault_name|None) from an existing directory path.

    A directory containing ``.obsidian`` is treated as a single vault (root =
    parent). Otherwise the path is treated as the vault collection root.
    """
    path = path.expanduser().resolve()
    if (path / ".obsidian").is_dir():
        return str(path.parent), path.name
    return str(path), None


def _prompt_yn(prompt: str, *, stdin: TextIO, stderr: TextIO) -> bool | None:
    """Ask y/n on stderr. Returns True/False, or None on EOF/empty."""
    print(prompt, end="", file=stderr, flush=True)
    line = stdin.readline()
    if not line:
        return None
    answer = line.strip().casefold()
    if answer in ("y", "yes"):
        return True
    if answer in ("n", "no"):
        return False
    return None


def _bootstrap_missing_vault_root(
    *,
    vault_override: str | None,
    stdin: TextIO,
    stderr: TextIO,
) -> tuple[Config, str | None]:
    """Create config paths/template; optionally set vault_root interactively.

    Returns:
        ``(config, vault_override)`` after bootstrap. *vault_override* may be
        rewritten when the user pointed ``-v`` at a vault collection path
        (that path becomes vault_root, not a vault name).
    """
    path, written = config.write_global_config_template()
    if written:
        _err(f"created config template: {path}", stderr)
    else:
        _err(f"vault_root is not set (config: {path})", stderr)

    # Prompt on stderr; only require stdin to be a TTY (stdout may be piped).
    interactive = bool(stdin.isatty())
    proposed_root: str | None = None
    proposed_vault: str | None = None
    override_out = vault_override

    if vault_override and _looks_like_filesystem_path(vault_override):
        candidate = Path(vault_override).expanduser()
        if candidate.is_dir():
            proposed_root, proposed_vault = _propose_vault_root_from_path(
                candidate
            )
        else:
            _err(
                f"path not found: {candidate}\n"
                f"edit {path} and set vault_root, then re-run",
                stderr,
            )
            return config.load(None, {}), override_out

    if proposed_root and interactive:
        msg = (
            f"Set vault_root to {proposed_root!r} in {path}? [y/n] "
        )
        answer = _prompt_yn(msg, stdin=stdin, stderr=stderr)
        if answer is True:
            config.write_global_vault_root(proposed_root)
            _err(f"wrote vault_root = {proposed_root!r}", stderr)
            # -v pointed at collection root → not a vault name.
            if proposed_vault is None and vault_override:
                override_out = None
            elif proposed_vault is not None:
                override_out = proposed_vault
            return config.load(override_out, {}), override_out
        if answer is False:
            _err(
                f"ok; edit {path} and set vault_root, then re-run",
                stderr,
            )
            return config.load(None, {}), override_out
        _err("expected y or n", stderr)
        return config.load(None, {}), override_out

    if interactive and not proposed_root:
        _err(
            f"edit {path} and set vault_root to your vaults directory, "
            "then re-run (example: vault_root = \"~/Documents/vaults\")",
            stderr,
        )
    elif not interactive:
        _err(
            f"set vault_root in {path} (non-interactive; no prompt)",
            stderr,
        )

    return config.load(None, {}), override_out


def _pick_vault_interactive(
    names: list[str],
    *,
    stdin: TextIO,
    stderr: TextIO,
) -> str:
    print("no active vault; pick one:", file=stderr)
    for i, name in enumerate(names, start=1):
        print(f"  {i}) {name}", file=stderr)
    print("vault number (or name): ", end="", file=stderr, flush=True)
    line = stdin.readline()
    if not line:
        raise VaultError("no active vault; run: od v NAME")
    choice = line.strip()
    if not choice:
        raise VaultError("no active vault; run: od v NAME")
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(names):
            return names[idx - 1]
        raise VaultError(f"invalid vault selection: {choice!r}")
    if choice in names:
        return choice
    raise VaultError(f"unknown vault: {choice!r}")


def _resolve_vault_name(
    override: str | None,
    st: State,
    cfg: Config,
    *,
    stdin: TextIO,
    stderr: TextIO,
    allow_prompt: bool,
) -> str:
    if override and str(override).strip():
        return str(override).strip()
    if st.active_vault and str(st.active_vault).strip():
        return str(st.active_vault).strip()
    if cfg.vaults_default and str(cfg.vaults_default).strip():
        return str(cfg.vaults_default).strip()

    names = _list_vault_names(cfg)
    if not names:
        raise VaultError(
            "no vaults found; set vault_root in ~/.config/od/config.toml "
            "and open a vault in Obsidian"
        )
    if not allow_prompt or not _is_interactive():
        raise VaultError("no active vault; run: od v NAME")
    chosen = _pick_vault_interactive(names, stdin=stdin, stderr=stderr)
    try:
        state.set_vault(chosen)
    except StateError as exc:
        # Still use the choice for this invocation.
        print(f"warning: could not persist vault: {exc}", file=stderr)
    return chosen


# ---------------------------------------------------------------------------
# dispatch helpers
# ---------------------------------------------------------------------------


def _err(msg: str, stderr: TextIO) -> None:
    print(msg, file=stderr)


def _out(msg: str, stdout: TextIO) -> None:
    print(msg, file=stdout)


def _format_glance(g: vault.Glance, st: State, vault_name: str) -> str:
    sticky = st.sticky_target or "(none)"
    lines = [f"vault: {vault_name}  sticky: {sticky}", f"path: {g.path}"]
    if g.headings:
        lines.append("headings:")
        for h in g.headings:
            lines.append(f"  # {h}")
    else:
        lines.append("headings: (none)")
    if g.tasks:
        lines.append("open tasks:")
        for t in g.tasks:
            where = f" [{t.heading}]" if t.heading else ""
            lines.append(f"  {t.index}. {t.text}{where}")
    else:
        lines.append("open tasks: (none)")
    return "\n".join(lines)


def _maybe_entity_link(vault_name: str, target: str, text: str) -> str:
    """If *target* resolves to an entity, append a wikilink when missing."""
    try:
        ent = entities.resolve_alias(vault_name, target)
    except (EntitiesError, AmbiguousEntity, OSError, ConfigError):
        return text
    if ent is None:
        return text
    link = entities.wikilink(ent)
    if link in text:
        return text
    if not text.strip():
        return link
    return f"{text} {link}"


def _dispatch(
    cmd: Command,
    *,
    vault_name: str,
    cfg: Config,
    st: State,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    if isinstance(cmd, Glance):
        g = vault.glance(vault_name)
        _out(_format_glance(g, st, vault_name), stdout)
        return 0

    if isinstance(cmd, ShowConfig):
        # Ensure sources recorded for this vault context.
        config.load(vault_name, {})
        rows = config.effective_with_sources()
        if not rows:
            _out("(empty config)", stdout)
            return 0
        width = max(len(k) for k, _, _ in rows)
        for key, value, tier in rows:
            _out(f"{key:<{width}}  {value!r}  ({tier})", stdout)
        return 0

    if isinstance(cmd, ListVaults):
        names = _list_vault_names(cfg)
        active = vault_name
        if not names:
            _err("no vaults under vault_root", stderr)
            return 1
        for name in names:
            mark = "*" if name == active else " "
            _out(f"{mark} {name}", stdout)
        return 0

    if isinstance(cmd, SetVault):
        state.set_vault(cmd.name)
        _err(f"active vault: {cmd.name}", stderr)
        return 0

    if isinstance(cmd, ShowSticky):
        sticky = st.sticky_target or "(none)"
        prev = st.sticky_prev or "(none)"
        active = st.active_vault or vault_name or "(none)"
        set_on = st.sticky_set_on.isoformat() if st.sticky_set_on else "(none)"
        _out(f"vault: {active}", stdout)
        _out(f"sticky: {sticky}", stdout)
        _out(f"prev: {prev}", stdout)
        _out(f"set_on: {set_on}", stdout)
        return 0

    if isinstance(cmd, SetSticky):
        state.set_sticky(cmd.target)
        _err(f"sticky: {cmd.target}", stderr)
        return 0

    if isinstance(cmd, SwapSticky):
        state.swap_sticky()
        fresh = state.get(check_sticky=False)
        _err(f"sticky: {fresh.sticky_target or '(none)'}", stderr)
        return 0

    if isinstance(cmd, ClearSticky):
        state.clear_sticky()
        _err("sticky: off", stderr)
        return 0

    if isinstance(cmd, Append):
        text = cmd.text
        style = cmd.style
        # Always expand aliases so writes and the destination echo use the
        # canonical heading (e.g. sticky ``p`` → ``personal updates``).
        heading = resolve.expand_target(cmd.target, cfg)
        if text is None:
            text = stdin.read()
            if text is None:
                text = ""
            style = "code"
        text = _maybe_entity_link(vault_name, heading, text)
        if cmd.via_sticky:
            _err(f"→ {vault_name}/{heading}", stderr)
        vault.append(vault_name, heading, text, style=style)
        return 0

    if isinstance(cmd, Todo):
        g = vault.glance(vault_name)
        if not g.tasks:
            _out("(no open tasks)", stdout)
            return 0
        for t in g.tasks:
            where = f"  [{t.heading}]" if t.heading else ""
            _out(f"{t.index}. {t.text}{where}", stdout)
        return 0

    if isinstance(cmd, Done):
        vault.complete_task(vault_name, cmd.index)
        _err(f"done {cmd.index}", stderr)
        return 0

    if isinstance(cmd, New):
        vault.new_section(vault_name, cmd.heading)
        _err(f"new section: {cmd.heading}", stderr)
        return 0

    if isinstance(cmd, Who):
        ent = entities.resolve_alias(vault_name, cmd.name)
        if ent is None:
            _err(f"no entity matching {cmd.name!r}", stderr)
            return 1
        _out(entities.card(ent), stdout)
        return 0

    _err(f"unhandled command: {type(cmd).__name__}", stderr)
    return 1


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------


def run(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the CLI and return an exit code (does not call ``sys.exit``)."""
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    stderr = stderr if stderr is not None else sys.stderr

    parser = _build_parser()
    _attach_completers(parser)
    argcomplete.autocomplete(parser)

    # argparse --version/--help write to sys.stdout; bind to caller's streams.
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = stdout, stderr
        try:
            args = parser.parse_args(list(argv) if argv is not None else None)
        except SystemExit as exc:
            code = exc.code
            if code is None:
                return 0
            return int(code) if isinstance(code, int) else 1
    finally:
        sys.stdout, sys.stderr = old_out, old_err

    words: list[str] = list(args.words or [])
    show_config = bool(args.show_config)
    vault_override: str | None = args.vault_override

    # --config is flag-only (never a positional reserved word).
    if show_config:
        if words:
            _err("--config does not take additional arguments", stderr)
            return 2

    stdin_piped = not stdin.isatty()

    try:
        flag_overrides: dict = {}
        # -v is tier-4 vault selection only; not written into config file
        # (except interactive bootstrap when vault_root is missing).
        cfg = config.load(vault_override, flag_overrides)

        if not cfg.vault_root:
            cfg, vault_override = _bootstrap_missing_vault_root(
                vault_override=vault_override,
                stdin=stdin,
                stderr=stderr,
            )
            if not cfg.vault_root:
                return 1

        # State: vault-only load first; sticky freshness enforced when needed.
        try:
            st = state.get(check_sticky=False)
        except StateError as exc:
            _err(str(exc), stderr)
            return 1

        if show_config:
            cmd: Command = ShowConfig()
        else:
            cmd = resolve.resolve(
                words,
                cfg,
                st,
                stdin_piped=stdin_piped,
            )

        needs_fresh_sticky = isinstance(cmd, Append) and cmd.via_sticky
        needs_fresh_sticky = needs_fresh_sticky or isinstance(
            cmd, (SwapSticky,)
        )
        if needs_fresh_sticky:
            try:
                st = state.get(check_sticky=True)
            except StickyExpired as exc:
                _err(str(exc), stderr)
                return 1
            # Re-resolve with fresh state so sticky target is current.
            cmd = resolve.resolve(
                words,
                cfg,
                st,
                stdin_piped=stdin_piped,
            )

        # Piped stdin must be routed to a code-block append; never discard.
        if stdin_piped and not (
            isinstance(cmd, Append) and cmd.text is None
        ):
            _err(
                "piped stdin has no destination; "
                "use: cmd | od <alias|heading>",
                stderr,
            )
            return 1

        # Commands that never need a vault filesystem context.
        if isinstance(cmd, (SetVault, ShowSticky, SetSticky, ClearSticky)):
            return _dispatch(
                cmd,
                vault_name=st.active_vault or cfg.vaults_default or "",
                cfg=cfg,
                st=st,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
            )

        if isinstance(cmd, SwapSticky):
            return _dispatch(
                cmd,
                vault_name=st.active_vault or "",
                cfg=cfg,
                st=st,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
            )

        if isinstance(cmd, ShowConfig):
            # Config display can use override or active vault for tier-3.
            name = vault_override or st.active_vault or cfg.vaults_default
            if name:
                config.load(name, flag_overrides)
            else:
                config.load(None, flag_overrides)
            return _dispatch(
                cmd,
                vault_name=name or "",
                cfg=cfg,
                st=st,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
            )

        allow_prompt = isinstance(cmd, (Glance, ListVaults)) or (
            not stdin_piped
        )
        vault_name = _resolve_vault_name(
            vault_override,
            st,
            cfg,
            stdin=stdin,
            stderr=stderr,
            allow_prompt=allow_prompt and isinstance(cmd, Glance),
        )
        # ListVaults: still need a name for active mark; may be empty.
        if isinstance(cmd, ListVaults):
            try:
                vault_name = _resolve_vault_name(
                    vault_override,
                    st,
                    cfg,
                    stdin=stdin,
                    stderr=stderr,
                    allow_prompt=False,
                )
            except VaultError:
                vault_name = st.active_vault or cfg.vaults_default or ""

        return _dispatch(
            cmd,
            vault_name=vault_name,
            cfg=cfg,
            st=st,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        )

    except BrokenPipeError:
        try:
            stdout.close()
        except Exception:
            pass
        return 0
    except KeyboardInterrupt:
        _err("Interrupted.", stderr)
        return 130
    except ObsidianInterrupted as exc:
        _err(str(exc), stderr)
        return int(getattr(exc, "exit_code", 130) or 130)
    except (
        ResolveError,
        NoTargetError,
        UsageError,
        StickyExpired,
        StateError,
        ConfigError,
        VaultError,
        WriteSafetyError,
        SectionsError,
        DuplicateHeadingError,
        TaskIndexError,
        EntitiesError,
        AmbiguousEntity,
        SocketError,
        ObsidianError,
    ) as exc:
        _err(str(exc), stderr)
        if isinstance(exc, UsageError):
            return 2
        return 1
    except Exception as exc:  # noqa: BLE001 — last-resort CLI boundary
        _err(f"error: {exc}", stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point (``od = od.cli:main``)."""
    raise SystemExit(run(argv))


if __name__ == "__main__":
    main()
