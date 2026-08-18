"""AC-8: die zwei Provider Open-Meteo und Geosphere schreiben fachlich
unterschiedliche Groessen in dasselbe Feld ``wind_chill_c`` — ein Kommentar
an BEIDEN Zuweisungsstellen muss erklaeren, welche Groesse der jeweilige
Provider tatsaechlich liefert. Keine Umbenennung, kein Verhaltens-Test
moeglich (Laufzeitverhalten aendert sich nicht) — Dateiinhalt-Check per
CLAUDE.md-Ausnahme fuer Doku-Nachweise.

SPEC: docs/specs/modules/fix_1887_e6a_sms_kuerzel_register.md, AC-8.

Geprueft werden zwei Stellen EINZELN (Mutations-Gegenprobe Punkt 6): fehlt
eine, wird genau diese gemeldet — der Test darf nicht durch die jeweils
andere Stelle gruen bleiben.

Die Ankerzeile wird zur LAUFZEIT aus der Datei bestimmt (Suche nach der
Zuweisung selbst), nicht literalisiert: eine oberhalb eingefuegte Zeile
verschiebt sonst alles darunter und der Wachhund zeigt ins Leere
(gleiche Lehre wie tests/test_guard_findings_survive_line_shifts.py, #1466).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENMETEO = REPO_ROOT / "src" / "providers" / "openmeteo.py"
GEOSPHERE = REPO_ROOT / "src" / "providers" / "geosphere.py"


def _anker_zeile(pfad: Path, zuweisung: str) -> int:
    """1-basierte Zeilennummer der ersten Zeile, die ``zuweisung`` enthaelt.

    Fehlt die Zuweisung, schlaegt der Test mit klarer Meldung FEHL — kein
    Default-Anker, kein Skip: sonst verloere der Wachhund seine Aussage,
    sobald jemand die Zuweisung umbenennt."""
    zeilen = pfad.read_text(encoding="utf-8").splitlines()
    for nummer, zeile in enumerate(zeilen, start=1):
        if zuweisung in zeile:
            return nummer
    pytest.fail(
        f"Ankerpunkt nicht gefunden: {pfad.name} enthaelt keine Zeile mit "
        f"{zuweisung!r}. Wurde die Zuweisung umbenannt oder entfernt? Dann "
        "muss AC-8 neu verankert werden — der Kommentar-Wachhund kann sonst "
        "nichts mehr pruefen."
    )


def _kommentar_text_im_fenster(pfad: Path, anker_zeile: int, spanne: int = 8) -> str:
    """Nur die KOMMENTAR-Anteile der Zeilen um ``anker_zeile`` (1-basiert) —
    nicht der Quelltext selbst. So kann eine reine Code-Zeile wie
    ``"apparent_temperature": "wind_chill_c",`` das Wort nicht versehentlich
    als "Kommentar vorhanden" durchgehen lassen."""
    zeilen = pfad.read_text(encoding="utf-8").splitlines()
    start = max(0, anker_zeile - spanne - 1)
    ende = min(len(zeilen), anker_zeile + spanne)
    kommentare = []
    for zeile in zeilen[start:ende]:
        if "#" in zeile:
            kommentare.append(zeile.split("#", 1)[1])
    return "\n".join(kommentare)


def test_openmeteo_wind_chill_c_kommentar_nennt_apparent_temperature():  # doc-compliance-test
    """AC-8, Open-Meteo-Seite: an der Zuweisung
    ``"apparent_temperature": "wind_chill_c"`` muss ein KOMMENTAR stehen,
    der 'apparent_temperature' als tatsaechlich gelieferte Groesse nennt."""
    assert OPENMETEO.exists(), f"Erwartete Datei fehlt: {OPENMETEO}"

    anker = _anker_zeile(OPENMETEO, '"apparent_temperature": "wind_chill_c"')
    kommentare = _kommentar_text_im_fenster(OPENMETEO, anker)
    assert re.search(r"apparent[_ ]temperatur", kommentare, re.IGNORECASE), (
        f"openmeteo.py traegt um die wind_chill_c-Zuweisung (Zeile {anker}) "
        "keinen erklaerenden KOMMENTAR, der 'apparent_temperature' als "
        "tatsaechlich gelieferte Groesse benennt (AC-8). Gefundene "
        f"Kommentare im Fenster: {kommentare!r}"
    )


def test_geosphere_wind_chill_c_kommentar_nennt_nordamerikanische_formel():  # doc-compliance-test
    """AC-8, Geosphere-Seite: an der berechneten Groesse
    (``wind_chill = _calculate_wind_chill(...)``) muss ein KOMMENTAR stehen,
    der die nordamerikanische Windchill-Formel UND ihre Gueltigkeitsgrenze
    (T <= 10 °C) benennt — unabhaengig vom (weit entfernten) Docstring der
    Hilfsfunktion selbst, der an der Zuweisungsstelle nicht sichtbar ist."""
    assert GEOSPHERE.exists(), f"Erwartete Datei fehlt: {GEOSPHERE}"

    anker = _anker_zeile(GEOSPHERE, "wind_chill = _calculate_wind_chill(")
    kommentare = _kommentar_text_im_fenster(GEOSPHERE, anker)
    nennt_formel = re.search(r"nordamerik|north american", kommentare, re.IGNORECASE)
    nennt_grenze = "10" in kommentare and re.search(r"°?\s*c\b", kommentare, re.IGNORECASE)

    assert nennt_formel, (
        "geosphere.py traegt um die berechnete wind_chill-Groesse "
        f"(Zeile {anker}) keinen KOMMENTAR, der die nordamerikanische "
        f"Windchill-Formel benennt (AC-8). Gefunden: {kommentare!r}"
    )
    assert nennt_grenze, (
        f"geosphere.py-Kommentar um Zeile {anker} nennt nicht die "
        "Gueltigkeitsgrenze T <= 10 °C der nordamerikanischen "
        f"Windchill-Formel (AC-8). Gefunden: {kommentare!r}"
    )
