"""Profil-Ampel S1a (#2792) Fix-Loop F-D: ``ampel_templates.py`` == §4.4.

# doc-compliance-test
Die Erwartung kommt NICHT aus dem Pruefling, sondern aus der SSOT der Zahlen:
den sieben Vorlagen-Tabellen in ``docs/context/einstellungen_neu.md`` §4.4.
Geparst werden alle 7 x 20 Zeilen (Grenzen unten/oben, im Briefing, Alarm ab)
plus die Gewitterzeile; verglichen wird die GANZE Vorlage. Aendert sich eine
Grenze, ``enabled`` oder ``alarm_ab`` in einer Vorlage, wird der Test rot.
Doku relativ zur Testdatei aufgeloest.
"""

import re
from pathlib import Path

from app.ampel_templates import AMPEL_TEMPLATES

DOKU = Path(__file__).resolve().parents[2] / "docs" / "context" / "einstellungen_neu.md"
_KOPF = re.compile(r"^##### .*\(`([a-z-]+)`\)")
_ZEILE = re.compile(r"^\| .*\(`(\w+)`\) \| (\*\*an\*\*|aus) \| (.*) \| (.*) \| (.*) \|$")
_ALARM = {"Orange": "orange", "Gelb": "yellow", "Rot": "red"}
_FARBE = {"gelb": "yellow", "orange": "orange", "rot": "red"}


def _grenzen(zelle: str, keys: tuple) -> dict:
    werte = [None if t.strip() in ("–", "") else float(t.strip().replace(",", "."))
             for t in zelle.split("/")]
    werte += [None] * (3 - len(werte))
    return dict(zip(keys, werte))


def _alarm(zelle: str) -> str:
    return _ALARM.get(zelle.strip(), "never")  # „Nie", „kein Alarm", „kein Alarm (Vorbote)"


def _vorlagen_aus_doku() -> dict:
    zeilen = DOKU.read_text(encoding="utf-8").split("### 4.4", 1)[1].split("## 5.", 1)[0]
    vorlagen, cur = {}, None
    for z in zeilen.splitlines():
        if m := _KOPF.match(z):
            cur = m.group(1)
            vorlagen[cur] = {"template": cur, "metrics": {}, "thunder": {}}
            continue
        m = _ZEILE.match(z)
        if not cur or not m:
            continue
        mid, an, unten, oben, alarm = m.groups()
        if mid == "thunder":
            vorlagen[cur]["thunder"] = {
                "mittel": _FARBE[re.search(r"mittel = (\w+)", unten).group(1)],
                "hoch": _FARBE[re.search(r"hoch = (\w+)", oben).group(1)]}
            unten = oben = "–"
        vorlagen[cur]["metrics"][mid] = {
            "enabled": an != "aus",
            "lower": _grenzen(unten, ("red", "orange", "yellow")),
            "upper": _grenzen(oben, ("yellow", "orange", "red")),
            "alarm_ab": _alarm(alarm)}
    return vorlagen


def test_alle_vorlagen_gleichen_den_tabellen_in_paragraph_4_4():  # doc-compliance-test
    doku = _vorlagen_aus_doku()
    # Positiv-Kontrolle gegen einen kaputten Parser (sonst vakuum-gruen).
    assert len(doku) == 7 and all(len(v["metrics"]) == 20 for v in doku.values())
    assert all(v["thunder"] for v in doku.values())
    assert sorted(doku) == sorted(AMPEL_TEMPLATES)
    for tid, erwartet in doku.items():
        assert AMPEL_TEMPLATES[tid] == erwartet, tid
