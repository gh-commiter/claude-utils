---
name: mode
description: Choose how keep-unlocked works - auto (every Claude Code session keeps the computer awake until it ends) or manual (only /keep-unlocked:on and off). Use for "keep-unlocked mode", /keep-unlocked:mode auto|manual.
---

# Set the keep-unlocked mode

- `auto`: the SessionStart hook starts a keeper that ends when that Claude Code process exits.
- `manual`: the hook does nothing; the user runs `/keep-unlocked:on` and `/keep-unlocked:off`.

1. Read `~/.claude/settings.json`. If it is missing, start from `{}`.
2. Find the mode:
   - Use the argument if it is `auto` or `manual` (for example `/keep-unlocked:mode manual`).
   - Otherwise ask with AskUserQuestion. Offer "auto (Recommended)" and "manual".
3. Set `env.KEEP_UNLOCKED_MODE` to the mode. Keep every other key.
4. Write the file back as valid JSON. Check it with `python3 -m json.tool ~/.claude/settings.json`.
5. Tell the user that the mode applies from the next session. Without the setting the mode is `auto`.
6. If the new mode is `auto`, ask with AskUserQuestion whether to keep this computer awake now too. On yes run
   `KEEP_UNLOCKED_MODE=auto python3 "${CLAUDE_PLUGIN_ROOT}/scripts/keep-unlocked.py" session < /dev/null`, then
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/keep-unlocked.py" status` and show its output. That keeper ends with this
   Claude Code session, like the ones the hook starts.
