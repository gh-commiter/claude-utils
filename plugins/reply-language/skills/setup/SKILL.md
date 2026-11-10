---
name: setup
description: Set up the reply-language plugin - choose the always-allowed languages and remove an older standalone copy of the hook. Use for "set up reply language", "nastavi jezik odgovorov", /reply-language:setup.
---

# Set up reply-language

The plugin's hooks are active once the plugin is installed. This skill sets the always-allowed languages
and removes an older copy of the hook, so the check does not run twice.

Supported codes: `sl` Slovenian, `en` English, `cs` Czech, `sk` Slovak, `hr` Croatian, `de` German.

1. Read `~/.claude/settings.json`. If it is missing, start from `{}`.
2. Find the always-allowed languages:
   - Use the codes from the arguments if they were given (for example `/reply-language:setup sl,en`).
   - Otherwise ask with AskUserQuestion. Offer "<user's language>,en (Recommended)" and "en". The first code is
     the default until a session's language is known.
3. Set `env.REPLY_LANGUAGE_ALLOWED` to the codes joined with commas, for example `"sl,en"`. Keep every other key.
4. Look in `hooks.UserPromptSubmit` and `hooks.Stop` for commands that run a different `reply-language.py` or
   `reply-language.ps1`, not the one from `${CLAUDE_PLUGIN_ROOT}`. List them and, after the user confirms, remove
   only those entries. Remove an event key or a matcher group that ends up empty. Leave the script file alone.
5. Write the file back as valid JSON. Check it: on Windows (Python may be missing there)
   `powershell -NoProfile -Command "Get-Content ~/.claude/settings.json -Raw | ConvertFrom-Json | Out-Null"`,
   elsewhere `python3 -m json.tool ~/.claude/settings.json`.
6. Check the scripts; each must print `ok`. With Python 3 installed:
   `python3 "${CLAUDE_PLUGIN_ROOT}/tests/test_reply_language.py"` (on Windows `python -X utf8` or `py -3 -X utf8`;
   never the Microsoft Store `python3` stub). On Windows also the fallback
   `powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scripts/reply-language.ps1" selftest`.
7. Tell the user that the new settings apply from the next session or after `/hooks` is reloaded.
