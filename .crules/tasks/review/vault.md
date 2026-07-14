# Task: vault.py — safe read-modify-write orchestration

Wave: 3

## Module
`src/od/vault.py`

## Purpose
Write-safety layer: `daily_read` → sections transform → sanity check →
`create_overwrite`.

## Public Interface
- `append(vault, heading, text, style="auto") -> str`
- `glance(vault) -> Glance`
- `new_section(vault, heading) -> str`
- `complete_task(vault, n) -> str`
- `check_write_safety(original, modified)` (test/helper)

## Acceptance Criteria
- [x] Heading-targeted writes use RMW (`daily:read` → Python → `create … overwrite`).
- [x] Never write back a note that lost content (`WriteSafetyError`; no write).
- [x] Post-transform: all prior H1 headings present; content not shorter than original.
- [x] Unknown heading on append creates new H1 (via sections).
- [x] Depends only on `obsidian`, `sections`.
- [x] Tests in `tests/test_vault.py` (mocked obsidian; no live vault required).

## Depends On
obsidian, sections.

## Coder Notes

- **`_rmw`:** `daily:path` → `daily_read` → transform → `check_write_safety` →
  `create_overwrite`. Shared by append / new_section / complete_task.
- **`WriteSafetyError`:** missing prior H1 or `len(modified) < len(original)`;
  nothing written (create_overwrite not called).
- **`new_section`:** RMW via `sections.add_section` (not blind `daily_append`);
  safer, still contract-compliant. Duplicate → `DuplicateHeadingError`, no write.
- **`glance`:** structured `Glance(vault, path, headings, tasks)` from parse of
  daily note (single read; not CLI `outline`/`tasks` text formats).
- **Verify:** `pytest tests/test_vault.py -v` → 16 passed; full suite green.
- **Live:** read-only `glance("riddell")` after `socket.ensure` OK; no live writes
  (daily notes empty / real vault left untouched).
- **No version bump** (hold until release).
- Wave 3 complete with `resolve` (see review/resolve.md).
