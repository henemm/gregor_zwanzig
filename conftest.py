"""Root-Conftest — fixiert die Prozess-Zeitzone fuer JEDEN Testlauf.

Issue #1402: der Server laeuft auf Weltzeit -- und bislang auch die
Testsuite (289 von 291 Testdateien liefen in der Zeitzone der aufrufenden
Maschine). Ein Zeitzonen-Fehler war dort *zufaellig richtig* und fiel erst
beim Nutzer auf (7 belegte Vorfaelle in vier Wochen: #1312, #1383, #1385,
#1386, #1378, #1399, #1347).

``America/St_Johns`` ist bewusst gewaehlt: Halbstunden-Versatz (-3:30 im
Winter, -2:30 im Sommer, s. Nachweis in PR-Historie) macht auch reine
Rundungsfehler sichtbar, die eine volle-Stunde-Zone verstecken wuerde.

Die Zone wird auf MODUL-EBENE gesetzt (Import-Zeit), also bevor pytest mit
der Testsammlung beginnt -- nicht in einer Fixture, die erst nach der
Sammlung laeuft. ``tests/conftest.py`` liegt unterhalb dieser Datei und wird
danach importiert; Tests, die selbst eine TZ fixieren (z. B.
``tests/tdd/test_compare_local_time_basis.py``), sichern/stellen ihren
eigenen Ausgangswert wieder her und bleiben davon unberuehrt.

``GZ_TEST_PROCESS_TZ`` (Issue #2314, Durchgang 2): additiver Env-Knopf, mit
dem sich "Prozesstag != UTC-Tag" (Nachtfenster 00:00-02:30 UTC) lokal
herstellen laesst, ohne auf die echte Nacht zu warten. Ohne gesetzte
Variable ist das Verhalten byte-identisch zum bisherigen Default
``America/St_Johns`` -- der #1402-Waechter bleibt unangetastet. Ist die
Variable gesetzt, aber die gewaehlte Zone traegt zum Laufzeitpunkt zufaellig
nicht (Prozesstag == UTC-Tag, z. B. weil die Zone das Tagesfenster gerade
nicht abdeckt), bricht der Lauf sichtbar mit Zone und UTC-Zeit in der
Meldung ab -- Selbstschutz gegen ein still gruenes, aber wirkungsloses
Ergebnis.
"""
import os
import time
from datetime import datetime, timezone

_GZ_TEST_PROCESS_TZ = os.environ.get("GZ_TEST_PROCESS_TZ")
os.environ["TZ"] = _GZ_TEST_PROCESS_TZ or "America/St_Johns"
time.tzset()

if _GZ_TEST_PROCESS_TZ:
    _prozess_heute = datetime.now().date()
    _utc_heute = datetime.now(timezone.utc).date()
    if _prozess_heute == _utc_heute:
        _jetzt_utc = datetime.now(timezone.utc)
        raise RuntimeError(
            f"GZ_TEST_PROCESS_TZ={_GZ_TEST_PROCESS_TZ!r} traegt zum "
            f"Laufzeitpunkt NICHT: Prozesstag ({_prozess_heute.isoformat()}) "
            f"== UTC-Tag ({_utc_heute.isoformat()}) bei UTC-Zeit "
            f"{_jetzt_utc.isoformat()}. Eine Zone waehlen, die JETZT eine "
            f"Gestern-Zone ist (docs/specs/modules/"
            f"fix_2314_nachtfenster_utc_tag.md, Messreferenz-Tabelle)."
        )
