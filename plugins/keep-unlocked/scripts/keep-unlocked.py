#!/usr/bin/env python3
"""Keeps the computer awake and unlocked while Claude Code runs.

  keep-unlocked.py session   SessionStart hook: in auto mode starts a keeper that ends with this Claude process.
  keep-unlocked.py on        starts a manual keeper; it runs until `off` or reboot.
  keep-unlocked.py off       stops every keeper this plugin started.
  keep-unlocked.py status    lists running keepers.

KEEP_UNLOCKED_MODE: "auto" (default) or "manual" (the hook does nothing).
Keepers: macOS caffeinate, Linux systemd-inhibit. Windows uses keep-unlocked.ps1 instead of this script.
State: one JSON file per keeper in ~/.claude/keep-unlocked/.
"""
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time

STATE = os.path.join(os.path.expanduser("~"), ".claude", "keep-unlocked")
SHELLS = {"sh", "bash", "zsh", "dash", "fish", "ksh", "cmd", "powershell", "pwsh", "python", "python3", "py", "env"}
# only processes whose command line has one of these are this plugin's keepers
MARKERS = ("caffeinate -dimsu", "--who=keep-unlocked")  # caffeinate -dimsu: keepers started before 0.2.1
# macOS: caffeinate -dims keeps it awake, but the screen saver and its lock follow the HID idle timer, which neither
# caffeinate -d nor -u resets. So a sh loop posts a real input event every 60 s, like the F15 press on Windows:
# a mouse move to where the pointer already is (nothing visible; F15 would change the brightness on a Mac).
# caffeinate -u -t 2 also turns the display on. A mouse move needs no permission (Accessibility or Automation);
# a key press would need Accessibility.
# TERM (off) and the end of caffeinate (Claude exited, -w) stop at once the loop and all its children (kill 0: own group).
DARWIN_START = 'trap "trap - TERM; kill 0" TERM; (caffeinate -dims "$@"; kill 0) & '  # also how running() knows it
DARWIN_MOVE = ('ObjC.import("CoreGraphics"); $.CGEventPost($.kCGHIDEventTap, $.CGEventCreateMouseEvent(null, '
               '$.kCGEventMouseMoved, $.CGEventGetLocation($.CGEventCreate(null)), 0))')
DARWIN_LOOP = (DARWIN_START + "while :; do caffeinate -u -t 2; osascript -l JavaScript -e '" + DARWIN_MOVE +
               "' >/dev/null 2>&1; sleep 60 & wait $!; done")


def mode(env=os.environ):
    value = env.get("KEEP_UNLOCKED_MODE", "").strip().lower()
    return value if value in ("auto", "manual") else "auto"


def first_token(args):
    """Program of a command line; a quoted first token may contain spaces: '"C:\\Program Files\\x.exe" -c' -> path."""
    args = args.strip()
    if args.startswith('"'):
        return args[1:].split('"', 1)[0]
    return (args.split() or [""])[0]


def base(path):
    """Executable name without directory, extension, version or login-shell dash: '/usr/bin/python3.12' -> 'python3'."""
    name = os.path.basename(path.replace("\\", "/")).lower().lstrip("-")
    if name.endswith(".exe"):
        name = name[:-4]
    return name.split(".")[0]


def is_claude(name, args):
    paths = [name.replace("\\", "/").lower(), first_token(args).replace("\\", "/").lower()]
    return ("claude" in (base(name), base(paths[1])) or any("claude/versions/" in x for x in paths)
            or (base(name) == "node" and "claude" in args.lower()))


def find_claude(table, start):
    """(pid, found): the first ancestor from `start` that is Claude Code, else the nearest non-shell one.
    table: {pid: (ppid, executable name or path, command line)}."""
    fallback, pid, seen = None, start, set()
    while pid in table and pid not in seen and pid > 1:
        seen.add(pid)
        ppid, name, args = table[pid]
        if is_claude(name, args):
            return pid, True
        if fallback is None and base(name or first_token(args)) not in SHELLS:
            fallback = pid
        pid = ppid
    return fallback, False


def process_table():
    """{pid: (ppid, name, command line)}."""
    # comm and args in separate calls: both may contain spaces, each is the last column
    run = lambda col: subprocess.run(["ps", "-A", "-o", f"pid=,ppid=,{col}="], capture_output=True, text=True,
                                     timeout=5).stdout.splitlines()
    args = {r[0]: r[2] if len(r) > 2 else "" for r in (line.split(None, 2) for line in run("args")) if r}
    rows = [r + [args.get(r[0], "")] for r in (line.split(None, 2) for line in run("comm")) if len(r) == 3]
    return {int(r[0]): (int(r[1]), r[2], r[3] if len(r) > 3 else "") for r in rows
            if len(r) >= 3 and r[0].strip().isdigit() and r[1].strip().isdigit()}


def keeper_cmd(system, claude_pid=None, which=shutil.which):
    """Command that keeps the machine awake; with claude_pid it exits when that process ends. None: unsupported."""
    if system == "Darwin":
        return ["sh", "-c", DARWIN_LOOP, "keep-unlocked"] + (["-w", str(claude_pid)] if claude_pid else [])
    if system == "Linux" and which("systemd-inhibit"):
        wait = ["tail", f"--pid={claude_pid}", "-f", "/dev/null"] if claude_pid else ["sleep", "infinity"]
        return ["systemd-inhibit", "--what=idle:sleep", "--who=keep-unlocked", "--why=Claude Code", "--mode=block"] + wait
    return None


def command_line(pid):
    return subprocess.run(["ps", "-o", "args=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout


def running(rec, cmdline=command_line):
    """True only if the pid still runs a keeper of this plugin (a reused pid does not count)."""
    pid = rec.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool):
        return False
    line = cmdline(pid) or ""
    # the keeper program itself, not e.g. a shell whose command line mentions the marker
    prog = base(first_token(line))
    return (prog in ("caffeinate", "systemd-inhibit") and any(m in line for m in MARKERS)
            or prog == "sh" and DARWIN_START in line)  # 0.2.1 keepers too


def keepers(state=STATE, alive=running):
    """Running keepers; files of keepers that are gone are removed."""
    result = []
    for f in sorted(os.listdir(state)) if os.path.isdir(state) else []:
        path = os.path.join(state, f)
        try:
            with open(path) as fh:
                rec = json.load(fh)
        except (OSError, ValueError):
            rec = {}
        if isinstance(rec, dict) and alive(rec):
            result.append(rec)
        else:
            try:
                os.remove(path)
            except OSError:
                pass
    return result


def start(kind, claude_pid=None, found=True):
    cmd = keeper_cmd(platform.system(), claude_pid)
    if not cmd:
        return (f"keep-unlocked: {platform.system()} is not supported (Linux needs systemd-inhibit; "
                "Windows uses keep-unlocked.ps1).")
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True, close_fds=True)
    rec = {"pid": proc.pid, "mode": kind, "claude_pid": claude_pid, "claude_found": found,
           "cmd": base(cmd[0]), "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    os.makedirs(STATE, exist_ok=True)
    with open(os.path.join(STATE, f"{proc.pid}.json"), "w") as fh:
        json.dump(rec, fh)
    return "started " + describe(rec)


def describe(rec):
    if rec.get("mode") == "manual":
        until = "until off or reboot"
    else:
        until = f"while Claude pid {rec.get('claude_pid')} runs"
        if not rec.get("claude_found"):
            until += " (Claude process not identified, nearest parent process used)"
    return f"keeper pid {rec['pid']} ({rec.get('cmd')}, {rec.get('mode')}) {until}, since {rec.get('started')}"


def stop(rec):
    try:  # the keeper may have ended meanwhile; its file goes anyway
        os.kill(rec["pid"], signal.SIGTERM)
    except OSError:
        pass
    try:
        os.remove(os.path.join(STATE, f"{rec['pid']}.json"))
    except OSError:
        pass


def on_session():
    try:
        json.load(sys.stdin)
    except ValueError:
        pass
    if mode() != "auto":
        return
    table = process_table()
    claude_pid, found = find_claude(table, os.getppid())
    if not claude_pid:
        print("keep-unlocked: Claude process not found, nothing started.", file=sys.stderr)
        return
    if any(r.get("mode") == "auto" and r.get("claude_pid") == claude_pid
           for r in keepers(alive=lambda rec: running(rec, lambda pid: table.get(pid, (0, "", ""))[2]))):
        return
    msg = start("auto", claude_pid, found)
    if not msg.startswith("started"):
        print(msg, file=sys.stderr)


def main(cmd):
    if cmd == "session":
        try:
            on_session()
        except Exception as e:  # the hook must never block or fail the session
            print(f"keep-unlocked: {e}", file=sys.stderr)
        return 0
    if cmd == "on":
        manual = [r for r in keepers() if r.get("mode") == "manual"]
        print("already running: " + describe(manual[0]) if manual else start("manual"))
    elif cmd == "off":
        found = keepers()
        for r in found:
            stop(r)
            print("stopped " + describe(r))
        if not found:
            print("no keeper running")
    elif cmd == "status":
        print(f"mode: {mode()}")
        found = keepers()
        for r in found:
            print(describe(r))
        if not found:
            print("no keeper running")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
