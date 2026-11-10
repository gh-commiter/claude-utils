# claude-utils

Small Claude Code plugins in one marketplace.

| Plugin | What it does |
| --- | --- |
| [reply-language](#reply-language) | Keeps Claude's replies in the user's language. |
| [keep-unlocked](#keep-unlocked) | Keeps the computer awake and unlocked while Claude Code runs. |

```
/plugin marketplace add gh-commiter/claude-utils
/plugin install reply-language@claude-utils
/plugin install keep-unlocked@claude-utils
```

Both need `python3` (standard library only), except keep-unlocked on Windows, which uses only PowerShell.

**Upgrading from the old `reply-language` marketplace** (`gh-commiter/claude-reply-language`): remove it with
`/plugin marketplace remove reply-language`, then add `gh-commiter/claude-utils` and install
`reply-language@claude-utils` as above.

## reply-language

- **UserPromptSubmit**: detects the language of the prompt (short prompts keep the previous one) and tells Claude
  to reply and think in it.
- **Stop**: when the visible reply is clearly in another language, Claude writes it again. Code, inline code,
  paths and URLs are not counted. Thinking is not checked.

Detected languages: Slovenian, English, Czech, Slovak, Croatian, German.

**Setup:** `/reply-language:setup sl,en` writes `env.REPLY_LANGUAGE_ALLOWED` (always-allowed languages, the first
one is the default) to `~/.claude/settings.json` and removes an older standalone copy of the hook. Without it,
only English and the user's language are allowed.

**Test:** `python3 plugins/reply-language/tests/test_reply_language.py` prints `ok`.

## keep-unlocked

While you work with Claude, the computer does not sleep, start the screen saver or lock itself for being idle.

| Skill | What it does |
| --- | --- |
| `/keep-unlocked:mode auto\|manual` | Sets `env.KEEP_UNLOCKED_MODE` in `~/.claude/settings.json`. Applies from the next session. |
| `/keep-unlocked:on` | Starts a keeper now. It runs until `/keep-unlocked:off` or reboot. |
| `/keep-unlocked:off` | Stops every keeper the plugin started (manual and auto). |

- **auto** (default): a SessionStart hook starts a keeper that ends when that Claude Code process exits.
- **manual**: the hook does nothing; use `on` and `off`.

Status: `python3 plugins/keep-unlocked/scripts/keep-unlocked.py status`, on Windows
`powershell -ExecutionPolicy Bypass -File plugins/keep-unlocked/scripts/keep-unlocked.ps1 status`. Keepers are tracked in
`~/.claude/keep-unlocked/`.

| OS | Keeper |
| --- | --- |
| macOS | `caffeinate -dimsu` (`-w <Claude pid>` in auto mode) |
| Windows | `keep-unlocked.ps1`, no Python: a scheduled task in `\keep-unlocked\` (one per keeper, removed when it ends) runs windowless PowerShell (`conhost --headless`) that every 30 s calls `SetThreadExecutionState(ES_CONTINUOUS \| ES_SYSTEM_REQUIRED \| ES_DISPLAY_REQUIRED)` and sends a harmless F15 key press, which resets the screen saver and lock idle timer |
| Linux | `systemd-inhibit --what=idle:sleep` if installed; otherwise the plugin reports that the system is not supported |

**Limits:** it prevents the *idle* sleep and lock only. It cannot unlock a locked computer, and a lock enforced by
policy on a fixed schedule (MDM, Group Policy) may still win.
- Windows: the hook needs Git Bash (Claude Code's default hook shell there). An auto keeper ends within a few seconds
  after Claude ends.
- Linux: GNOME and KDE screen lockers may ignore logind idle inhibitors; over SSH, blocking sleep may need polkit.

Tested on macOS and Windows 11 (Claude Code not elevated; running as administrator is untested).

**Test:** `python3 plugins/keep-unlocked/tests/test_keep_unlocked.py` prints `ok`; on Windows
`powershell -ExecutionPolicy Bypass -File plugins/keep-unlocked/scripts/keep-unlocked.ps1 selftest` prints `ok`.
