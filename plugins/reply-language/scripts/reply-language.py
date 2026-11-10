#!/usr/bin/env python3
"""Claude odgovarja (in razmišlja) v jeziku uporabnikovega vprašanja.

  reply-language.py prompt   UserPromptSubmit: prepozna jezik sporočila, ga shrani za sejo in
                             Claudu doda navodilo (kratka sporočila obdržijo jezik prejšnjega).
  reply-language.py stop     Stop: vidni odgovor v drugem jeziku → exit 2, Claude ga napiše znova.

REPLY_LANGUAGE_ALLOWED (npr. "sl,en"): jeziki, ki so vedno dovoljeni; prvi je privzeti, dokler jezik seje ni znan.

Prepoznava: črke, značilne za jezik (češke ě ř ů, hrvaške ć đ), in pogoste besede; koda in `...` se ne štejeta.
"""
import json
import os
import re
import sys
import tempfile

NAMES = {"sl": "Slovenian", "en": "English", "cs": "Czech", "sk": "Slovak", "hr": "Croatian", "de": "German"}
# vedno dovoljeni; poleg njih le jezik uporabnikovega vprašanja
ALLOWED = [k for k in os.environ.get("REPLY_LANGUAGE_ALLOWED", "en").replace(" ", "").split(",") if k in NAMES] or ["en"]
WORDS = {
    "sl": "je da se na ne ki za pa kaj ali bi sem mi kot tudi še že ker lahko naj kako samo bo tega tem "
          "ta te ti zdaj sedaj potem nato ampak vendar ko če kje zakaj moram moraš imam dela deluje treba prav dobro "
          "tu tukaj kar nekaj tole tisto vse dej daj sam pol rabim rabiš mora morajo dodaj naredi objavi poglej preveri "
          "nadaljuj popravi zakaj kje kateri katera mapo mapa datoteko verzijo novo ni lepo poravnano primerjaj "
          "sem si smo ste ga jo jih mu jim nekje desno levo zgoraj spodaj pa naredil dodal spremeni pogledam",
    "en": "the and is to of in that it for you this with be are not on have what how can was will would "
          "should there their which when then also just only but from about into does do",
    "cs": "jsem které který není jak co ale pro když také jako bude mít tak teď protože jestli tady",
    "sk": "sa som si ako čo ktorý ktorá nie alebo pre môže tiež keď teraz pretože len už ešte",
    "hr": "što će nije treba kad mogu ovo ovaj biti jer sada ovdje zašto trebam može",
    "de": "der die das und ist nicht ich ein eine mit auf für sie wir auch wenn dann aber noch",
}
WORDS = {k: set(v.split()) for k, v in WORDS.items()}
SL_CHARS = re.compile(r"[čšžČŠŽ]")  # tudi češčina/hrvaščina, zato le, ko njunih črk ni
CHARS = {"cs": re.compile(r"[ěřůĚŘŮ]"), "sk": re.compile(r"[ľĺŕôĽĹŔÔ]"), "hr": re.compile(r"[ćđĆĐ]"),
         "de": re.compile(r"[öüßÖÜ]")}
SHARED = re.compile(r"[ťďňýáíéúŤĎŇÝÁÍÉÚ]")  # češčina in slovaščina: slovenščina jih nima


def strip_code(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", " ", text)
    # URL-ji in poti: beseda s / ali \ med znaki; (?<!\S) jo zasidra na začetek, sicer je čas kvadraten
    return re.sub(r"(?<!\S)\S+[/\\]\S+", " ", text)


def scores(text):
    words = re.findall(r"[^\W\d_]+", strip_code(text).lower())
    s = {k: sum(w in ws for w in words) for k, ws in WORDS.items()}
    for k, rx in CHARS.items():
        s[k] += 3 * len(rx.findall(text))
    if not any(rx.search(text) for rx in CHARS.values()):
        s["sl"] += min(len(SL_CHARS.findall(strip_code(text))), 3)
    return s, len(words)


def own_words(text):
    """Uporabnikovo besedilo brez prilepljenih izpisov, obvestil in izhoda ukazov (<tag>…</tag>)."""
    text = re.sub(r"<([A-Za-z][\w-]*)[^>]*>.*?</\1>", " ", text, flags=re.S)
    return re.sub(r"<[^>]+>", " ", text)


def detect(text):
    """Jezik uporabnikovega besedila ali None (premalo besed: obdrži prejšnjega).
    Neangleški jezik ima prednost: angleščina je pogosto le prilepljen izpis ukaza ali napake."""
    s, _ = scores(own_words(text))
    native = sorted(((v, k) for k, v in s.items() if k != "en"), reverse=True)
    if native[0][0] >= 2 and native[0][0] > native[1][0]:
        return native[0][1]
    # angleščina le iz kratkega sporočila: daljše besedilo brez domačih besed je prilepljen izpis
    lines = [l for l in own_words(text).splitlines() if l.strip()]
    return "en" if s["en"] >= 3 and native[0][0] == 0 and len(lines) <= 3 else None


def state_file(session):
    return os.path.join(tempfile.gettempdir(), f"claude-reply-language-{re.sub(r'[^A-Za-z0-9_-]', '', session)}")


def user_text(o):
    content = (o.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def last_turn(path):
    """Besedilo asistenta od zadnjega pravega uporabnikovega sporočila."""
    texts = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("type") == "user" and user_text(o).strip() and not o.get("isMeta"):
                texts = []
            elif o.get("type") == "assistant":
                content = (o.get("message") or {}).get("content")
                if isinstance(content, list):
                    texts += [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(texts)


def on_prompt(data):
    path = state_file(data.get("session_id", "default"))
    lang = detect(data.get("prompt", ""))
    if lang:
        with open(path, "w") as f:
            f.write(lang)
    else:
        try:
            lang = open(path).read().strip() or None
        except OSError:
            lang = None
    if lang:
        name = NAMES[lang]
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": f"The user writes in {name}. Write every reply to the user in {name}, "
                                 f"and do your thinking in {name} too. Code, commands and quoted text stay as they are."}}))
    return 0


def on_stop(data):
    # le en popravek: povratna informacija hooka je v prepisu isMeta, zato bi se prvi tuji odgovor ocenjeval znova
    if data.get("stop_hook_active"):
        return 0
    try:
        lang = open(state_file(data.get("session_id", "default"))).read().strip()
    except OSError:
        lang = ALLOWED[0]
    text = data.get("last_assistant_message") or ""
    if data.get("transcript_path"):
        try:
            text = last_turn(data["transcript_path"]) or text
        except OSError:
            pass
    s, _ = scores(text)
    s["cs"] += len(SHARED.findall(strip_code(text)))
    s["sk"] += len(SHARED.findall(strip_code(text)))
    allowed = set(ALLOWED) | {lang}
    other, hits = max(((k, v) for k, v in s.items() if k not in allowed), key=lambda kv: kv[1], default=(None, 0))
    ok = max(s[k] for k in allowed if k in s)
    # le jasen primer: posamezne tuje besede ali imena v odgovoru so dovoljeni
    if other and hits >= 4 and hits > ok:
        want = NAMES.get(lang, NAMES[ALLOWED[0]])
        sys.stderr.write(f"The reply is in {NAMES[other]}. Only {', '.join(NAMES[k] for k in ALLOWED)} or the user's language ({want}) "
                         f"are allowed. Write the last reply again in {want}, without apologizing or explaining why.\n")
        return 2
    return 0


if __name__ == "__main__":
    data = json.load(sys.stdin)
    sys.exit(on_prompt(data) if sys.argv[1:] == ["prompt"] else on_stop(data))
