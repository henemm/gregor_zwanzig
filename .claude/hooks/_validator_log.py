#!/usr/bin/env python3
"""Gemeinsame Ablage der Validator-Protokolle (#1408 F005).

Alle vier Mail-Validatoren (briefing, email_spec/compare, radar_alert,
official_alert) erzeugen ihren Log-INHALT unterschiedlich, legen ihn aber
identisch ab. Genau dieser gemeinsame Teil steht hier EINMAL -- vier Kopien
derselben Ablage-Logik waeren die Doppelpflege, die in #1408 schon zweimal
auseinandergelaufen ist.

Der Fehler, den diese Datei schliesst: der Dateiname trug nur Sekunden
(``%Y%m%d_%H%M%S``) und wurde per ``os.rename`` gesetzt. Zwei Laeufe in
derselben Sekunde belegten dieselbe Datei, der zweite ueberschrieb den ersten
lautlos -- in der Staging-Verifikation zu #1408 hat so ein fehlgeschlagener
Lauf den Beleg eines bestandenen geloescht. Diese Protokolle sind der Nachweis,
den ``renderer_mail_gate.py`` (Commit-Gate #811) und die Staging-Attestation
lesen.

Zwei Vorkehrungen, weil parallele Sitzungen hier der Normalfall sind:

1. Mikrosekunden im Namen -- deckt denselben Prozess ab.
2. ``os.link`` statt ``os.rename``: der Link schlaegt ATOMAR mit
   ``FileExistsError`` fehl, wenn der Name schon belegt ist, und weicht dann
   auf ``_1``, ``_2`` ... aus. Mikrosekunden allein waeren nur praktisch
   sicher, nicht garantiert -- zwei Prozesse koennen dieselbe Mikrosekunde
   treffen.

**Der Namensvertrag der Abnehmer ist unantastbar.** Sie suchen per
``glob("*_<kind>_validation.yaml")`` -- also nach der WOERTLICHEN Endung -- und
sortieren nach mtime. Der Kollisions-Zaehler gehoert deshalb in den PRAEFIX,
niemals hinter die Endung: eine Datei ``..._email_validation_1.yaml`` waere
fuer das Gate unsichtbar, und ein ausgewichener bestandener Lauf zaehlte nicht
-- derselbe Schaden wie das Ueberschreiben, nur anders verpackt. Der Praefix
dagegen ist frei; der Bestand belegt das selbst
(``tests/tdd/test_issue_930_golden_gate.py:119`` schreibt ein Log ganz ohne
Zeitstempel im Namen und wird gefunden).

Namensschema::

    20260728_143443_812004_<workflow>_email_validation.yaml      (Normalfall)
    20260728_143443_812004_1_<workflow>_email_validation.yaml    (Kollision)
"""

import os
from datetime import datetime
from pathlib import Path


def place_exclusively(tmp_path, log_dir, workflow_id: str, kind: str,
                      timestamp: "str | None" = None) -> Path:
    """Legt die fertig geschriebene Temp-Datei ab, ohne je eine bestehende
    Datei zu ueberschreiben -- und ohne die Endung anzutasten.

    ``kind`` ist z.B. ``"email_validation"`` oder ``"briefing_validation"``;
    daraus entsteht die Endung ``_<kind>.yaml``, nach der die Abnehmer suchen.
    Ist der Name belegt, waechst der PRAEFIX (``..._1_``, ``..._2_`` ...).
    ``os.link`` ist der Schiedsrichter: es scheitert atomar, wenn der Zielname
    zwischen Pruefung und Anlegen von einem anderen Prozess belegt wurde.

    ``timestamp`` ist eine Naht fuer Tests, die eine Kollision erzwingen
    wollen; im Betrieb wird die aktuelle UTC-Zeit mit Mikrosekunden benutzt.

    Rueckgabe: der tatsaechlich benutzte Pfad.
    """
    tmp_path = str(tmp_path)
    log_dir = Path(log_dir)
    if timestamp is None:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")

    try:
        counter = 0
        while True:
            zaehler_teil = "" if counter == 0 else f"_{counter}"
            ziel = log_dir / f"{timestamp}{zaehler_teil}_{workflow_id}_{kind}.yaml"
            try:
                os.link(tmp_path, str(ziel))
                return ziel
            except FileExistsError:
                counter += 1
    finally:
        # Auch wenn os.link aus einem anderen Grund scheitert (z.B. Dateisystem
        # ohne Hardlinks): die Temp-Datei darf nicht liegenbleiben.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
