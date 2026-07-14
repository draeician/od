# Task: resolve.py — command-line word resolution

Wave: 3

## Module
`src/od/resolve.py`

## Purpose
Classify argv words into typed Command intents (pure, no I/O).

## Public Interface
- `resolve(words, config, state, *, stdin_piped=False) -> Command`
- `match_reserved(word)`, `expand_target(word, config)`
- Errors: `ResolveError`, `AmbiguousPrefix`, `NoTargetError`, `UsageError`
- Commands: Glance, ShowConfig, ListVaults, SetVault, ShowSticky, SetSticky,
  SwapSticky, ClearSticky, Append, Todo, Done, New, Who

## Acceptance Criteria
- [x] Reserved words support git-style unambiguous prefix matching.
- [x] Exact alias match beats reserved prefix (e.g. alias `t` vs `todo`).
- [x] Sticky grammar: `=`, `= target`, `= -`, `= off`.
- [x] One positional (TTY) = sticky text; no sticky → `NoTargetError`.
- [x] Two positionals = target + text; alias expanded to heading.
- [x] One positional + `stdin_piped` = target for code-style append.
- [x] Pure — no file/network/subprocess I/O; depends on config + State type only.
- [x] Tests in `tests/test_resolve.py`.

## Depends On
config, state (types only), stdlib.

## Coder Notes

- **Classify order** for free words: exact reserved → exact alias → reserved
  prefix → free heading. Alias `t` therefore beats `todo` prefix.
- **`stdin_piped`:** pure flag (no I/O inside resolve); cli detects pipe and
  passes it. Piped single word → `Append(..., text=None, style="code")`.
- **Sticky set** expands aliases to headings for stable sticky storage.
- **`vaults` / `v`:** no args → ListVaults; one arg → SetVault.
- **Verify:** `pytest tests/test_resolve.py -v` → 15 passed; full suite 136.
- **No version bump** (hold until release).
- Wave 3 complete (vault + resolve). Wave 4 next: `cli.py`.
