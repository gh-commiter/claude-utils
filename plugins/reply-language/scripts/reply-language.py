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
# jeziki, v katerih se vidi spol govorca: Claude o sebi v moškem spolu (primer: moška, ne ženska oblika)
SELF = {"sl": "'sem naredil', not 'sem naredila'", "cs": "'udělal jsem', not 'udělala jsem'",
        "sk": "'urobil som', not 'urobila som'", "hr": "'napravio sam', not 'napravila sam'"}
# črke poleg a-z, ki jih jezik ima (velike se primerjajo kot male)
ALPHABETS = {"sl": set("čšž"), "en": set(), "cs": set("áčďéěíňóřšťúůýž"), "sk": set("áäčďéíĺľňóôŕšťúýž"),
             "hr": set("čćđšž"), "de": set("äöüß")}
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


# navedki (vsaj 15 znakov): uporabnik pogosto citira Claudov tuji odgovor, to ni njegov jezik
QUOTED = re.compile(r"'[^'\n]{15,}'|\"[^\"\n]{15,}\"|„[^“\n]{15,}“|“[^”\n]{15,}”|«[^»\n]{15,}»|»[^«\n]{15,}«")


def own_words(text):
    """Uporabnikovo besedilo brez prilepljenih izpisov, obvestil, izhoda ukazov (<tag>…</tag>) in navedkov."""
    text = re.sub(r"<([A-Za-z][\w-]*)[^>]*>.*?</\1>", " ", text, flags=re.S)
    return QUOTED.sub(" ", re.sub(r"<[^>]+>", " ", text))


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
    """Besedila asistenta (vsak blok posebej) od zadnjega pravega uporabnikovega sporočila."""
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
    return texts


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
                                 f"and do your thinking in {name} too. Code, commands and quoted text stay as they are."
                                 + (f" Refer to yourself in the masculine grammatical gender ({SELF[lang]})." if lang in SELF else "")}}))
    return 0


def foreign(text, allowed):
    """Tuji jezik, v katerem je besedilo jasno napisano, ali None (posamezne tuje besede in imena so dovoljeni)."""
    # abeceda dovoljenih jezikov: 3 ali več besed s črko zunaj nje (ř ů ý, ć đ, cirilica …) je tuj stavek, tudi sredi
    # odstavka, kjer bi ga štetje besed razredčilo; eno ali dve imeni (Dvořák) sta dovoljeni
    letters = set("abcdefghijklmnopqrstuvwxyz").union(*(ALPHABETS[k] for k in allowed if k in ALPHABETS))
    odd = [w for w in re.findall(r"[^\W\d_]+", strip_code(text).lower()) if not set(w) <= letters]
    if len(odd) >= 3:
        extra = set("".join(odd)) - letters
        fits = [k for k in NAMES if k not in allowed and extra <= ALPHABETS[k]]
        s, _ = scores(text)
        return max(fits, key=lambda k: s[k]) if fits else "other"
    s, _ = scores(text)
    s["cs"] += len(SHARED.findall(strip_code(text)))
    s["sk"] += len(SHARED.findall(strip_code(text)))
    other, hits = max(((k, v) for k, v in s.items() if k not in allowed), key=lambda kv: kv[1], default=(None, 0))
    return other if other and hits >= 4 and hits > max(s[k] for k in allowed if k in s) else None


def on_stop(data):
    try:
        lang = open(state_file(data.get("session_id", "default"))).read().strip()
    except OSError:
        lang = ALLOWED[0]
    texts = [data.get("last_assistant_message") or ""]
    # stop_hook_active: Claude nadaljuje zaradi Stop hooka (tega ali drugega vtičnika). Prepis vsebuje še zavrnjeni
    # tuji odgovor, zato se oceni le zadnje sporočilo; prej se je preverjanje takrat preskočilo in tuj odgovor je ušel.
    if data.get("transcript_path") and not data.get("stop_hook_active"):
        try:
            texts = last_turn(data["transcript_path"]) or texts
        except OSError:
            pass
    allowed = set(ALLOWED) | {lang}
    # vsak blok posebej: tuj odstavek sredi daljšega slovenskega dela poteze se ne razredči
    other = next(filter(None, (foreign(t, allowed) for t in texts)), None)
    if other:
        want = NAMES.get(lang, NAMES[ALLOWED[0]])
        sys.stderr.write(f"The reply is in {NAMES.get(other, 'another language')}. Only {', '.join(NAMES[k] for k in ALLOWED)} or the user's language ({want}) "
                         f"are allowed. Write the last reply again in {want}, without apologizing or explaining why.\n")
        return 2
    return 0

if __name__ == "__main__":
    data = json.load(sys.stdin)
    sys.exit(on_prompt(data) if sys.argv[1:] == ["prompt"] else on_stop(data))
