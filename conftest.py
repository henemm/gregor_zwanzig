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
"""
import os
import time

os.environ["TZ"] = "America/St_Johns"
time.tzset()
