---
name: on
description: Keep the computer awake and unlocked now, until /keep-unlocked:off or reboot. Use for "keep unlocked on", "don't let the computer sleep", /keep-unlocked:on.
---

# Start a keeper

1. Run on Windows `powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/keep-unlocked.ps1" on`
   (no Python needed), elsewhere `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/keep-unlocked.py" on`.
2. Show its output. The keeper is not tied to this session: it runs until `/keep-unlocked:off` or reboot.
   The script first looks for running keeper processes, also ones without a state file. If a manual or untracked
   one runs, it says so and starts no second one; auto keepers are only listed, since they end with their session.
