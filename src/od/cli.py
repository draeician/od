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
