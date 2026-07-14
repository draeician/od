"""vault.py — safe read-modify-write orchestration

Purpose:
    The write-safety layer: daily_read -> sections transform -> sanity
    check -> create_overwrite.

Public:
    append(vault, heading, text, style=auto)
    glance(vault) -> Glance
    new_section(vault, heading)
    complete_task(vault, n)

Invariants:
    Never write back a note that lost content — post-transform check
    verifies all prior headings present and content not shrunk except by
    explicit edit; violation raises WriteSafetyError and nothing is
    written; new-section appends are the only blind appends.

Depends on:
    obsidian, sections.
"""
