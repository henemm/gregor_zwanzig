"""Issue #2242: Zeitstempel aus Mail-Vergleichen maskieren, ohne sonst etwas
zu entschaerfen.

ROOT CAUSE: ``plain.py:388``/``compact.py:164,315`` schreiben eine Fusszeile
``Generated: YYYY-MM-DD HH:MM UTC`` aus ``datetime.now(timezone.utc)``;
``html.py`` schreibt DREI eigene, unabhaengig aus ``sent_at``/der Wanduhr
abgeleitete Zeitangaben (gemessen, nicht nur aus dem Issue-Text uebernommen):

1. Kopfzeile (AC-2, #890): ``"Mi · 15.07.2026 · 12:00 UTC"``
   (``html.py`` ~Z.1114-1116, ``f"{wd} · {datum} · {uhrzeit} {tz_abbrev}"``).
2. Footer-Markenzeile (``_render_footer``, ``html.py`` ~Z.534/536): nackte
   ``"YYYY-MM-DD HH:MM UTC"`` OHNE "Generated:"-Praefix.
3. Footer-Kontextlabel (AC-6, #899, ``html.py`` ~Z.1433): ``"gesendet Mi ·
   12:00"``.

Der im Issue genannte Regelsatz ("Generated: ..." und "gesendet ... ")
deckt NUR Klartext-Footer und Kontextlabel ab. Ein Minutengrenzen-Nachweis
(Scratch-Lauf, #2242 Bericht) hat gezeigt: OHNE Maskierung von (1) und (2)
bleibt ``test_ac9_briefing_mail_bleibt_mit_und_ohne_die_neuen_rohwerte_
identisch`` ueber eine Minutengrenze hinweg rot, weil zwei nacheinander
gerenderte Mails (``mit``/``ohne``) je einen frischen ``datetime.now()``-Wert
in die Kopf- und Footer-Zeile schreiben. Diese Datei maskiert deshalb ALLE
VIER Formen — nicht nur die zwei im Issue genannten Beispiele ("z.B.").

Jede Maske ersetzt NUR den Zeitanteil, nie umgebenden Text — sonst prueft der
Vergleich am Ende nichts mehr. ``hat_minutenstempel()`` ist die
Positivkontrolle: schlaegt sie fehl, hat sich das Footer-/Kopfzeilen-Format
geaendert und die Maske liefe still ins Leere (veralteter Regex).
"""
from __future__ import annotations

import re

_PLATZHALTER = "<zeitstempel>"

# Reihenfolge ist wichtig: das spezifischere "Generated: ..." zuerst, damit
# die generische nackte ISO-Form (Footer-Markenzeile) nur noch die WIRKLICH
# unpraefigierten Vorkommen trifft.
_GENERATED_RE = re.compile(r"Generated: \d{4}-\d\d-\d\d \d\d:\d\d UTC")
_NACKTE_ISO_RE = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d UTC")
_KOPFZEILE_RE = re.compile(
    r"[A-Za-z]{2} · \d\d\.\d\d\.\d{4} · \d\d:\d\d [A-Za-z]+"
)
_GESENDET_RE = re.compile(r"gesendet [A-Za-z]{2} · \d\d:\d\d")

_ALLE_MUSTER = (_GENERATED_RE, _NACKTE_ISO_RE, _KOPFZEILE_RE, _GESENDET_RE)


def ohne_minutenstempel(text: str) -> str:
    """``text`` mit allen vier bekannten Wanduhr-Zeitangaben durch einen
    festen Platzhalter ersetzt. Alles andere bleibt zeichengleich."""
    ergebnis = _GENERATED_RE.sub(f"Generated: {_PLATZHALTER}", text)
    ergebnis = _NACKTE_ISO_RE.sub(_PLATZHALTER, ergebnis)
    ergebnis = _KOPFZEILE_RE.sub(_PLATZHALTER, ergebnis)
    ergebnis = _GESENDET_RE.sub(f"gesendet {_PLATZHALTER}", ergebnis)
    return ergebnis


def hat_minutenstempel(text: str) -> bool:
    """Positivkontrolle: traegt ``text`` MINDESTENS eine der vier bekannten
    Zeitformen? Liefert dies ``False``, hat sich das Footer-/Kopfzeilen-
    Format geaendert und ``ohne_minutenstempel`` maskiert nichts mehr — der
    Aufrufer MUSS das dann als Fixture-/Ratschen-Fehler werten, nicht als
    bestandenen Test."""
    return any(muster.search(text) for muster in _ALLE_MUSTER)
