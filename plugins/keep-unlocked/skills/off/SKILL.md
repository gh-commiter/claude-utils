---
name: off
description: Stop every keep-unlocked keeper on this computer (manual and auto ones) and switch to manual mode, so it can sleep and lock again. Use for "keep unlocked off", "let the computer sleep", /keep-unlocked:off.
---

# Stop all keepers

1. Run on Windows `powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/keep-unlocked.ps1" off`
   (no Python needed), elsewhere `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/keep-unlocked.py" off`.
2. Show what was stopped. The script also sets the mode to `manual` (`env.KEEP_UNLOCKED_MODE` in
   `~/.claude/settings.json`), so new sessions do not start keepers again; `/keep-unlocked:mode auto` turns that back on.
