"""resolve.py — command-line word resolution

Purpose:
    Classify argv words: reserved word (with git-style unambiguous-prefix
    matching), heading alias, `=` grammar, bare text.

Public:
    resolve(words, config, state) -> Command (a typed intent: Glance,
    SetVault, SetSticky, Append, Todo, Done, New, Who, ...)
    AmbiguousPrefix error carries the candidate list.

Invariants:
    Argument-count rule (one positional = text for sticky, two = target +
    text); resolution order: exact positional reserved -> exact alias ->
    reserved prefix -> free target; config is flag-only (not positional);
    exact alias always beats reserved prefix and sticky; no sticky and
    bare text -> NoTargetError; pure, no I/O.

Depends on:
    config, state (types only), stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Union

from od.config import RESERVED_WORDS, Config
from od.state import State

__all__ = [
    "ResolveError",
    "AmbiguousPrefix",
    "NoTargetError",
    "UsageError",
    "Glance",
    "ShowConfig",
    "ListVaults",
    "SetVault",
    "ShowSticky",
    "SetSticky",
    "SwapSticky",
    "ClearSticky",
    "Append",
    "Todo",
    "Done",
    "New",
    "Who",
    "Command",
    "resolve",
    "match_reserved",
    "expand_target",
]


class ResolveError(Exception):
    """Base error for command-line word resolution."""


class AmbiguousPrefix(ResolveError):
    """Reserved-word prefix matches more than one candidate (git-style)."""

    def __init__(self, prefix: str, candidates: Sequence[str]) -> None:
        self.prefix = prefix
        self.candidates = tuple(candidates)
        listed = ", ".join(self.candidates)
        super().__init__(
            f"ambiguous prefix {prefix!r}; candidates: {listed}"
        )


class NoTargetError(ResolveError):
    """Bare text with no sticky target and no explicit heading."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or "no sticky target; set one with `od = <alias|heading>` "
            "or pass an explicit target: `od <alias|heading> \"text\"`"
        )


class UsageError(ResolveError):
    """Wrong arity or invalid argument shape for a resolved verb."""


# ---------------------------------------------------------------------------
# Command intents (cli dispatches on type)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Glance:
    """Bare ``od`` — today at a glance."""


@dataclass(frozen=True)
class ShowConfig:
    """Effective config listing — produced only by the ``--config`` flag in cli."""


@dataclass(frozen=True)
class ListVaults:
    """``od vaults`` / unambiguous prefix (e.g. ``od v``)."""


@dataclass(frozen=True)
class SetVault:
    """``od vaults <name>`` / ``od v <name>`` — set active vault."""

    name: str


@dataclass(frozen=True)
class ShowSticky:
    """``od =`` — show sticky target and active vault."""


@dataclass(frozen=True)
class SetSticky:
    """``od = <target>`` — set sticky target for today."""

    target: str


@dataclass(frozen=True)
class SwapSticky:
    """``od = -`` — swap sticky with previous."""


@dataclass(frozen=True)
class ClearSticky:
    """``od = off`` — clear sticky target."""


@dataclass(frozen=True)
class Append:
    """Append text under a heading (sticky or explicit).

    ``text`` is ``None`` when the CLI should read stdin (piped code block).
    """

    target: str
    text: str | None
    style: str = "auto"
    via_sticky: bool = False


@dataclass(frozen=True)
class Todo:
    """``od todo`` — list open tasks in today's note."""


@dataclass(frozen=True)
class Done:
    """``od done <n>`` — mark open task n complete."""

    index: int


@dataclass(frozen=True)
class New:
    """``od new <heading>`` — create a new H1 section."""

    heading: str


@dataclass(frozen=True)
class Who:
    """``od who <name|alias>`` — show entity card."""

    name: str


Command = Union[
    Glance,
    ShowConfig,
    ListVaults,
    SetVault,
    ShowSticky,
    SetSticky,
    SwapSticky,
    ClearSticky,
    Append,
    Todo,
    Done,
    New,
    Who,
]


# Flag-only tokens: listed in config.RESERVED_WORDS so aliases cannot collide
# with them, but they are never positional verbs (use ``od --config``).
_FLAG_ONLY_RESERVED: frozenset[str] = frozenset({"config"})


def _positional_reserved() -> frozenset[str]:
    """Reserved words that may appear as positional argv verbs."""
    return frozenset(w for w in RESERVED_WORDS if w not in _FLAG_ONLY_RESERVED)


def expand_target(word: str, config: Config) -> str:
    """Map an exact alias to its heading; otherwise return *word* unchanged."""
    aliases = config.aliases
    if word in aliases:
        return aliases[word]
    return word


def match_reserved(word: str) -> str | None:
    """Return the positional reserved word for *word*, or None if no match.

    Exact match wins. Otherwise git-style unambiguous prefix. Raises
    ``AmbiguousPrefix`` when more than one reserved word shares the prefix.

    Does not consult aliases — callers decide alias-vs-prefix order.
    ``config`` is flag-only (``--config``) and never matches positionally.
    """
    reserved_set = _positional_reserved()
    if word in reserved_set:
        return word
    if not word:
        return None
    candidates = sorted(r for r in reserved_set if r.startswith(word))
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise AmbiguousPrefix(word, candidates)
    return None


def _classify_first(word: str, config: Config) -> tuple[str, str | None]:
    """Classify a free word: ('reserved', name) | ('target', None).

    Order: exact positional reserved → exact alias → reserved prefix → free
    target. Exact alias beats reserved prefix (alias ``t`` wins over ``todo``;
    alias ``c`` wins over any residual prefix and never becomes ``config``).
    """
    reserved_set = _positional_reserved()
    if word in reserved_set:
        return "reserved", word
    if word in config.aliases:
        return "target", None
    reserved = match_reserved(word)
    if reserved is not None:
        return "reserved", reserved
    return "target", None


def _resolve_sticky(rest: Sequence[str], config: Config) -> Command:
    if len(rest) == 0:
        return ShowSticky()
    if len(rest) > 1:
        raise UsageError(
            "sticky grammar takes at most one argument "
            "(`od =`, `od = <target>`, `od = -`, `od = off`)"
        )
    arg = rest[0]
    if arg == "-":
        return SwapSticky()
    if arg == "off":
        return ClearSticky()
    if not str(arg).strip():
        raise UsageError("sticky target must be non-empty")
    # Store expanded heading when the token is a known alias so sticky
    # display and writes use the canonical section name.
    return SetSticky(target=expand_target(str(arg).strip(), config))


def _resolve_reserved(
    verb: str,
    rest: Sequence[str],
) -> Command:
    if verb == "vaults":
        if len(rest) == 0:
            return ListVaults()
        if len(rest) == 1:
            name = str(rest[0]).strip()
            if not name:
                raise UsageError("vault name must be non-empty")
            return SetVault(name=name)
        raise UsageError("usage: od vaults [<name>]")

    if verb == "todo":
        if rest:
            raise UsageError("todo takes no arguments")
        return Todo()

    if verb == "done":
        if len(rest) != 1:
            raise UsageError("usage: od done <n>")
        raw = rest[0]
        try:
            index = int(raw)
        except (TypeError, ValueError) as exc:
            raise UsageError(
                f"done requires an integer task index, got {raw!r}"
            ) from exc
        if index < 1:
            raise UsageError(f"task index must be >= 1, got {index}")
        return Done(index=index)

    if verb == "new":
        if len(rest) != 1:
            raise UsageError("usage: od new <heading>")
        heading = str(rest[0]).strip()
        if not heading:
            raise UsageError("heading must be non-empty")
        return New(heading=heading)

    if verb == "who":
        if len(rest) != 1:
            raise UsageError("usage: od who <name|alias>")
        name = str(rest[0]).strip()
        if not name:
            raise UsageError("name must be non-empty")
        return Who(name=name)

    raise UsageError(f"unhandled reserved word: {verb!r}")


def resolve(
    words: Sequence[str],
    config: Config,
    state: State,
    *,
    stdin_piped: bool = False,
) -> Command:
    """Resolve *words* into a typed Command intent.

    Pure: no I/O. *state* is consulted only for ``sticky_target`` (expiry
    is the caller's responsibility via ``state.get()``).

    Args:
        words: Positional argv tokens after flags (e.g. without ``-v``).
        config: Effective config (aliases, reserved constants).
        state: Current sticky/vault state snapshot.
        stdin_piped: When True, a single non-reserved word is a heading
            target for a fenced code append (stdin body filled by cli).

    Returns:
        A frozen Command dataclass instance.

    Raises:
        AmbiguousPrefix: Reserved prefix matches multiple verbs.
        NoTargetError: Bare text with no sticky target.
        UsageError: Wrong arguments for a verb.
        ResolveError: Other resolution failures.
    """
    tokens = [str(w) for w in words]

    if not tokens:
        return Glance()

    # Sticky grammar: leading "=" (possibly glued as "=target").
    first = tokens[0]
    if first == "=" or first.startswith("="):
        if first == "=":
            rest = tokens[1:]
        else:
            glued = first[1:]
            rest = ([glued] if glued else []) + tokens[1:]
        return _resolve_sticky(rest, config)

    kind, reserved = _classify_first(first, config)
    if kind == "reserved":
        assert reserved is not None
        return _resolve_reserved(reserved, tokens[1:])

    # Free target / sticky text path.
    if len(tokens) == 1:
        word = tokens[0]
        if stdin_piped:
            return Append(
                target=expand_target(word, config),
                text=None,
                style="code",
                via_sticky=False,
            )
        sticky = state.sticky_target
        if not sticky:
            raise NoTargetError()
        return Append(
            target=expand_target(sticky, config),
            text=word,
            style="auto",
            via_sticky=True,
        )

    if len(tokens) == 2:
        target_word, text = tokens[0], tokens[1]
        return Append(
            target=expand_target(target_word, config),
            text=text,
            style="auto",
            via_sticky=False,
        )

    raise UsageError(
        "too many arguments; expected `od \"text\"` or "
        "`od <alias|heading> \"text\"`"
    )
