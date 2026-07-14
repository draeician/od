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
    text); explicit alias always beats sticky; no sticky and bare text ->
    NoTargetError; pure, no I/O.

Depends on:
    config, state (types only), stdlib.
"""
