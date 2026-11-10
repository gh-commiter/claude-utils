"""Run: python3 tests/test_reply_language.py"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "reply-language.py")
spec = importlib.util.spec_from_file_location("rl", SCRIPT)
rl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rl)

assert rl.detect("ok sedaj bi zelel nov repo s pluginom, ki to nastavi") == "sl"
assert rl.detect("can you check what this hook does") == "en"
assert rl.detect("Proč to nefunguje, když je všechno správně?") == "cs"
assert rl.detect("ok") is None
assert rl.detect("<pasted>the and is to of in that it for you</pasted> poglej kaj je to") == "sl"


def run(mode, data, allowed="sl,en"):
    env = dict(os.environ, REPLY_LANGUAGE_ALLOWED=allowed)
    return subprocess.run([sys.executable, SCRIPT, mode], input=json.dumps(data), text=True,
                          capture_output=True, env=env)


session = f"test-{os.getpid()}"
p = run("prompt", {"session_id": session, "prompt": "kaj je to in zakaj ne deluje"})
assert "Slovenian" in p.stdout, p.stdout
assert run("stop", {"session_id": session, "last_assistant_message": "To je hook, ki preverja jezik in ga lahko nastaviš."}).returncode == 0
assert run("stop", {"session_id": session, "last_assistant_message": "This is the hook that checks the reply."}).returncode == 0
bad = run("stop", {"session_id": session, "last_assistant_message": "Ovo je hook koji provjerava što će biti, jer sada treba ovdje."})
assert bad.returncode == 2 and "Croatian" in bad.stderr, bad
assert run("stop", {"session_id": session, "last_assistant_message": "This is the hook that checks it."}, allowed="sl").returncode == 2  # en ni dovoljen
assert run("stop", {"session_id": session, "stop_hook_active": True,  # le en popravek
                    "last_assistant_message": "Ovo je hook koji provjerava što će biti, jer sada treba ovdje."}).returncode == 0
t = time.perf_counter()
assert rl.strip_code("a/b " + "x" * 20000 + " c") == "  " + "x" * 20000 + " c"
assert time.perf_counter() - t < 0.5  # linearno, ne kvadratno (prej več sekund)
os.remove(os.path.join(tempfile.gettempdir(), f"claude-reply-language-{session}"))
print("ok")
