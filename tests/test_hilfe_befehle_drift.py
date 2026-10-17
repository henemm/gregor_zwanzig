"""Drift-Schutz Hilfeseite <-> Antwort-Befehle (Onboarding S3, Issue #2521, AC-17).

Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md

Die Hilfeseite ``/hilfe`` fuehrt die Antwort-Befehle als statische Kopie im
Textkatalog ``frontend/src/lib/i18n/messages/de.json``. Einzige Quelle der
Befehle ist ``_COMMAND_SPECS`` in ``src/services/trip_command_processor.py``.
Dieser Test ruft ``command_rows()`` ECHT auf (Import, kein Quelltext-Lesen) und
vergleicht die Befehle samt Argumentform mit den Katalogeintraegen. Kommt ein
Befehl hinzu, faellt einer weg oder heisst einer anders, ohne dass der Katalog
nachgezogen wird, ist der Test rot.

Katalog-Vertrag (flache Schluessel, de.json ist ``Record<string, string>``):
    hilfe.befehle.<wort>.befehl   z. B. "PAUSE [2d / 12h]"  (= erste Spalte von command_rows())
    hilfe.befehle.<wort>.text     Beschreibung (nicht leer; Wortlaut frei, die Seite
                                  ist eine kurze Uebersicht, keine Referenz)

``de.json`` wird als DATEN gelesen (json.load), relativ zu dieser Testdatei —
nie ueber einen festen Hauptrepo-Pfad.

    uv run pytest tests/test_hilfe_befehle_drift.py --disable-socket -v -rA
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.services.trip_command_processor import command_rows

KATALOG_DATEI = (
    Path(__file__).resolve().parent.parent / "frontend" / "src" / "lib" / "i18n" / "messages" / "de.json"
)
_BEFEHL_KEY = re.compile(r"^hilfe\.befehle\.([^.]+)\.befehl$")


def _katalog() -> dict[str, str]:
    with KATALOG_DATEI.open(encoding="utf-8") as f:
        return json.load(f)


def katalog_befehle(katalog: dict[str, str]) -> dict[str, str]:
    """``{<wort>: <Befehl inkl. Argumentform>}`` aus den Katalogeintraegen."""
    return {m.group(1): wert for key, wert in katalog.items() if (m := _BEFEHL_KEY.match(key))}


def drift(quelle: list[tuple[str, str]], katalog: dict[str, str]) -> dict[str, list[str]]:
    """Unterschiede Quelle <-> Katalog; leere Listen = kein Drift."""
    soll = {befehl for befehl, _ in quelle}
    ist = set(katalog_befehle(katalog).values())
    return {"fehlt_im_katalog": sorted(soll - ist), "nur_im_katalog": sorted(ist - soll)}


def test_quelle_liefert_befehle():
    """Messaufbau: command_rows() ist die echte, nicht leere Befehlsquelle."""
    rows = command_rows()
    assert len(rows) >= 5
    assert all(befehl and beschreibung for befehl, beschreibung in rows)


def test_katalog_hat_befehlseintraege():
    assert katalog_befehle(_katalog()), (
        "de.json enthaelt keine Eintraege hilfe.befehle.<wort>.befehl — "
        "die Hilfeseite hat keinen Abschnitt Antwort-Befehle"
    )


def test_katalog_und_command_rows_stimmen_ueberein():
    """AC-17: jeder Befehl aus command_rows() steht genau so im Katalog, und umgekehrt."""
    assert drift(command_rows(), _katalog()) == {"fehlt_im_katalog": [], "nur_im_katalog": []}


def test_jeder_katalogbefehl_hat_eine_beschreibung():
    katalog = _katalog()
    ohne = [
        wort
        for wort in katalog_befehle(katalog)
        if not str(katalog.get(f"hilfe.befehle.{wort}.text", "")).strip()
    ]
    assert ohne == []


def test_schluesselwort_passt_zum_befehl():
    """``hilfe.befehle.<wort>`` traegt das kleingeschriebene erste Wort des Befehls."""
    falsch = {
        wort: befehl
        for wort, befehl in katalog_befehle(_katalog()).items()
        if befehl.split()[0].lower() != wort
    }
    assert falsch == {}


# ── Gegenproben: der Vergleich erkennt jede Drift-Art ────────────────────────
def _katalog_aus(rows: list[tuple[str, str]]) -> dict[str, str]:
    kat: dict[str, str] = {}
    for befehl, text in rows:
        wort = befehl.split()[0].lower()
        kat[f"hilfe.befehle.{wort}.befehl"] = befehl
        kat[f"hilfe.befehle.{wort}.text"] = text
    return kat


@pytest.mark.parametrize("art", ["geloescht", "hinzu", "umbenannt"])
def test_gegenprobe_drift_wird_erkannt(art: str):
    rows = command_rows()
    kat = _katalog_aus(rows)
    assert drift(rows, kat) == {"fehlt_im_katalog": [], "nur_im_katalog": []}
    if art == "geloescht":
        wort = rows[0][0].split()[0].lower()
        del kat[f"hilfe.befehle.{wort}.befehl"]
    elif art == "hinzu":
        kat["hilfe.befehle.erfunden.befehl"] = "ERFUNDEN"
    else:
        wort = rows[0][0].split()[0].lower()
        kat[f"hilfe.befehle.{wort}.befehl"] = rows[0][0] + "X"
    d = drift(rows, kat)
    assert d["fehlt_im_katalog"] or d["nur_im_katalog"]
