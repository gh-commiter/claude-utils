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
# stop_hook_active (tudi zaradi drugega vtičnika): oceni se zadnje sporočilo, ne preskoči
assert run("stop", {"session_id": session, "stop_hook_active": True,
                    "last_assistant_message": "Ovo je hook koji provjerava što će biti, jer sada treba ovdje."}).returncode == 2
assert run("stop", {"session_id": session, "stop_hook_active": True,
                    "last_assistant_message": "Popravljeno, zdaj deluje."}).returncode == 0
# češki odstavek sredi dolge slovenske poteze se ne razredči
cz = ("Všechny potomky mají `NePrikaziKotDogodek = 0`, takže ani tento příznak neodliší událost od číselníku. "
      "Nebudu to odhadovat: strom uložím do KB jako „číselníky, které používají pole“, bez třídění.")
sl = "Zdaj je to narejeno, ker je treba, da se to lahko preveri in da je prav. " * 10
tr = os.path.join(tempfile.gettempdir(), f"claude-reply-language-transcript-{os.getpid()}.jsonl")
with open(tr, "w", encoding="utf-8") as f:
    for o in ({"type": "user", "message": {"content": "zakaj"}},
              {"type": "assistant", "message": {"content": [{"type": "text", "text": cz}]}},
              {"type": "assistant", "message": {"content": [{"type": "text", "text": sl}]}}):
        f.write(json.dumps(o) + "\n")
bad = run("stop", {"session_id": session, "transcript_path": tr, "last_assistant_message": sl})
assert bad.returncode == 2 and "Czech" in bad.stderr, bad
os.remove(tr)
# češki stavek sredi slovenskega odstavka: črke, ki jih slovenščina nima
assert rl.foreign(sl[:300] + "Přepíšu skript na kurzor s dynamickým SQL přes všechny tyto databáze.", {"sl", "en"}) == "cs"
assert rl.foreign("Skladbo je napisal Dvořák, ki je bil češki skladatelj, in to je zdaj tudi v tej datoteki prav, kot je treba.", {"sl", "en"}) is None  # imena
assert rl.foreign("Přepíšu skript s dynamickým SQL přes databáze.", {"sl", "en", "cs"}) is None  # uporabnik piše češko
# citiran tuji odgovor ne spremeni jezika seje
assert rl.detect("zakaj hook ne ujame tega tvojega sranja ... '" + cz + "'") == "sl"
assert rl.detect("Proč to nefunguje, když je všechno správně?") == "cs"
t = time.perf_counter()
assert rl.strip_code("a/b " + "x" * 20000 + " c") == "  " + "x" * 20000 + " c"
assert time.perf_counter() - t < 0.5  # linearno, ne kvadratno (prej več sekund)
os.remove(os.path.join(tempfile.gettempdir(), f"claude-reply-language-{session}"))
print("ok")
