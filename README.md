# reply-language

A Claude Code plugin that keeps replies in the user's language.

- **UserPromptSubmit**: detects the language of the prompt (short prompts keep the previous one) and tells Claude
  to reply and think in it.
- **Stop**: when the visible reply is clearly in another language, Claude writes it again. Code, inline code,
  paths and URLs are not counted. Thinking is not checked.

Detected languages: Slovenian, English, Czech, Slovak, Croatian, German.

## Install

```
/plugin marketplace add gh-commiter/claude-reply-language
/plugin install reply-language@reply-language
/reply-language:setup sl,en
```

`/reply-language:setup` writes `REPLY_LANGUAGE_ALLOWED` (always-allowed languages, the first one is the default)
to `~/.claude/settings.json` and removes an older standalone copy of the hook. Without it, only English and the
user's language are allowed.

## Test

```
python3 tests/test_reply_language.py
```

Requires `python3` (standard library only).
