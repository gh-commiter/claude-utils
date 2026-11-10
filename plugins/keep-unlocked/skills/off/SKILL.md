---
name: off
description: Stop every keep-unlocked keeper on this computer (manual and auto ones), so it can sleep and lock again. Use for "keep unlocked off", "let the computer sleep", /keep-unlocked:off.
---

# Stop all keepers

1. Run on Windows `powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/keep-unlocked.ps1" off`
   (no Python needed), elsewhere `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/keep-unlocked.py" off`.
2. Show what was stopped. In auto mode the next session starts a new keeper; use `/keep-unlocked:mode manual`
   to stop that.
