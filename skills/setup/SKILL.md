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
4. Look in `hooks.UserPromptSubmit` and `hooks.Stop` for commands that run a different `reply-language.py`,
   not the one from `${CLAUDE_PLUGIN_ROOT}`. List them and, after the user confirms, remove only those entries.
   Remove an event key or a matcher group that ends up empty. Leave the script file alone.
5. Write the file back as valid JSON. Check it with `python3 -m json.tool ~/.claude/settings.json`.
6. Check the script: `python3 "${CLAUDE_PLUGIN_ROOT}/tests/test_reply_language.py"` must print `ok`.
7. Tell the user that the new settings apply from the next session or after `/hooks` is reloaded.
