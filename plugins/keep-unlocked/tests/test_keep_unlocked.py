"""Run: python3 tests/test_keep_unlocked.py"""
import importlib.util
import json
import os
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "keep-unlocked.py")
spec = importlib.util.spec_from_file_location("ku", SCRIPT)
ku = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ku)

# mode: unset or garbage -> auto
assert ku.mode({}) == "auto"
assert ku.mode({"KEEP_UNLOCKED_MODE": "auto"}) == "auto"
assert ku.mode({"KEEP_UNLOCKED_MODE": " Manual "}) == "manual"
assert ku.mode({"KEEP_UNLOCKED_MODE": "off"}) == "auto"

# commands per platform
assert ku.keeper_cmd("Darwin", 42) == ["caffeinate", "-dimsu", "-w", "42"]
assert ku.keeper_cmd("Darwin") == ["caffeinate", "-dimsu"]
win = ku.keeper_cmd("Windows", 42)
assert win[0] == "powershell" and "-NoLogo" in win and "2147483651" in win[-1] and "Get-Process -Id 42" in win[-1], win
assert "keybd_event(0x7E, 0, 0," in win[-1] and "keybd_event(0x7E, 0, 2," in win[-1] and "Start-Sleep 30" in win[-1]
assert "if ($false)" in ku.keeper_cmd("Windows")[-1]

# Windows spawn: breakaway from the job first, without it when the job forbids it
calls = []
def fake_popen(cmd, creationflags, **kw):
    calls.append(creationflags)
    if creationflags & ku.WIN_BREAKAWAY:
        raise PermissionError("access denied")
    return "proc"
assert ku.spawn_windows(["x"], fake_popen) == "proc"
assert calls == [ku.WIN_FLAGS | ku.WIN_BREAKAWAY, ku.WIN_FLAGS], calls
calls.clear()
assert ku.spawn_windows(["x"], lambda cmd, creationflags, **kw: calls.append(creationflags) or "p") == "p"
assert calls == [ku.WIN_FLAGS | ku.WIN_BREAKAWAY]
has = lambda name: "/usr/bin/" + name
assert ku.keeper_cmd("Linux", 42, has)[-4:] == ["tail", "--pid=42", "-f", "/dev/null"]
assert ku.keeper_cmd("Linux", None, has)[0] == "systemd-inhibit" and ku.keeper_cmd("Linux", None, has)[-2:] == ["sleep", "infinity"]
assert ku.keeper_cmd("Linux", 42, lambda name: None) is None
assert ku.keeper_cmd("FreeBSD", 42) is None

# ancestor walk: hook python <- sh -c <- claude (native or node) <- login shell; rows are (ppid, name, command line)
table = {
    100: (90, "/bin/sh", "/bin/sh -c python3 /Users/u/.claude/plugins/x/keep-unlocked.py session"),
    90: (80, "claude", "claude --resume"),
    80: (1, "-zsh", "-zsh"),
}
assert ku.find_claude(table, 100) == (90, True)
table[90] = (80, "/usr/local/bin/node", "/usr/local/bin/node /usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js")
assert ku.find_claude(table, 100) == (90, True)
table[90] = (80, "2.1.0", "/Users/u/.local/share/claude/versions/2.1.0 --continue")  # Linux comm of the native binary
assert ku.find_claude(table, 100) == (90, True)
table[90] = (80, "/Applications/My Tools/node", "/Applications/My Tools/node /opt/claude-code/cli.js")  # space in path
assert ku.find_claude(table, 100) == (90, True)
table[90] = (80, "/opt/editor/bin/editor", "/opt/editor/bin/editor")  # no Claude: nearest non-shell ancestor
assert ku.find_claude(table, 100) == (90, False)
assert ku.find_claude({100: (1, "bash", "bash")}, 100) == (None, False)
assert ku.find_claude({100: (100, "sh", "sh")}, 100) == (None, False)  # loop safety

# Windows: quoted paths with spaces, Git Bash wrapper between the hook and Claude
win_table = {
    300: (200, "bash.exe", r'"C:\Program Files\Git\bin\bash.exe" -c "python3 C:/Users/u/.claude/plugins/x/keep-unlocked.py session"'),
    200: (150, "node.exe", r'"C:\Program Files\nodejs\node.exe" C:\Users\u\AppData\Roaming\npm\node_modules\@anthropic-ai\claude-code\cli.js'),
    150: (1, "explorer.exe", r"C:\Windows\explorer.exe"),
}
assert ku.find_claude(win_table, 300) == (200, True)
win_table[200] = (150, "claude.exe", r'"C:\Users\u\.local\bin\claude.exe"')
assert ku.find_claude(win_table, 300) == (200, True)
win_table[200] = (150, "Code.exe", r'"C:\Program Files\Microsoft VS Code\Code.exe"')
assert ku.find_claude(win_table, 300) == (200, False)  # bash.exe is skipped as a shell
assert ku.first_token(r'"C:\Program Files\Git\bin\bash.exe" -c x') == r"C:\Program Files\Git\bin\bash.exe"

# running: only a keeper's own command line counts, not a reused pid or a record without pid
assert ku.running({"pid": 5, "cmd": "caffeinate"}, lambda pid: "caffeinate -dimsu -w 9")
assert ku.running({"pid": 5}, lambda pid: "systemd-inhibit --what=idle:sleep --who=keep-unlocked --why=x tail")
assert ku.running({"pid": 5}, lambda pid: " ".join(ku.keeper_cmd("Windows", 9)))
assert not ku.running({"pid": 5, "cmd": "powershell"}, lambda pid: "powershell.exe -NoExit")  # user's own PowerShell
assert not ku.running({"pid": 5, "cmd": "caffeinate"}, lambda pid: "caffeinate -i make")
assert not ku.running({"pid": 5}, lambda pid: "")  # gone
assert not ku.running({"pid": 5}, lambda pid: "zsh -c pgrep -fl 'caffeinate -dimsu'")  # shell mentioning the marker
assert ku.running({"pid": 5}, lambda pid: '"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command KeepUnlocked')
assert not ku.running({"cmd": "caffeinate"}, lambda pid: "caffeinate -dimsu")
assert not ku.running({"pid": True}, lambda pid: "caffeinate -dimsu")

# Windows loop takes the Claude process once, so a reused pid does not keep it running
w = ku.keeper_cmd("Windows", 42)[-1]
assert w.startswith("$p = Get-Process -Id 42") and "$null = $p.Handle;" in w and "-not $p -or $p.HasExited" in w, w

# stale pidfiles are removed, running ones kept
state = tempfile.mkdtemp()
for pid in (1, 2):
    with open(os.path.join(state, f"{pid}.json"), "w") as f:
        json.dump({"pid": pid, "cmd": "caffeinate", "mode": "manual"}, f)
with open(os.path.join(state, "junk.json"), "w") as f:
    f.write("not json")
live = ku.keepers(state, alive=lambda r: r.get("pid") == 1)
assert [r["pid"] for r in live] == [1], live
assert os.listdir(state) == ["1.json"], os.listdir(state)
# off: a keeper that already ended does not stop the others, and its file is removed
import subprocess
dead = subprocess.Popen(["true"]); dead.wait()
os.remove(os.path.join(state, "1.json"))
open(os.path.join(state, f"{dead.pid}.json"), "w").close()
ku.STATE = state
ku.stop({"pid": dead.pid})  # ProcessLookupError is ignored
assert os.listdir(state) == [], os.listdir(state)
os.rmdir(state)
print("ok")
