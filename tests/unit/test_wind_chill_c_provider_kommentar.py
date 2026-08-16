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
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENMETEO = REPO_ROOT / "src" / "providers" / "openmeteo.py"
GEOSPHERE = REPO_ROOT / "src" / "providers" / "geosphere.py"


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
    """AC-8, Open-Meteo-Seite: an der Zuweisung um Zeile 394
    (``"apparent_temperature": "wind_chill_c"``) muss ein KOMMENTAR stehen,
    der 'apparent_temperature' als tatsaechlich gelieferte Groesse nennt."""
    assert OPENMETEO.exists(), f"Erwartete Datei fehlt: {OPENMETEO}"

    kommentare = _kommentar_text_im_fenster(OPENMETEO, 394)
    assert re.search(r"apparent[_ ]temperatur", kommentare, re.IGNORECASE), (
        "openmeteo.py traegt um die wind_chill_c-Zuweisung (Zeile ~394) "
        "keinen erklaerenden KOMMENTAR, der 'apparent_temperature' als "
        "tatsaechlich gelieferte Groesse benennt (AC-8). Gefundene "
        f"Kommentare im Fenster: {kommentare!r}"
    )


def test_geosphere_wind_chill_c_kommentar_nennt_nordamerikanische_formel():  # doc-compliance-test
    """AC-8, Geosphere-Seite: an der berechneten Groesse um Zeile 552
    (``wind_chill = _calculate_wind_chill(...)``) muss ein KOMMENTAR stehen,
    der die nordamerikanische Windchill-Formel UND ihre Gueltigkeitsgrenze
    (T <= 10 °C) benennt — unabhaengig vom (weit entfernten) Docstring der
    Hilfsfunktion selbst, der an der Zuweisungsstelle nicht sichtbar ist."""
    assert GEOSPHERE.exists(), f"Erwartete Datei fehlt: {GEOSPHERE}"

    kommentare = _kommentar_text_im_fenster(GEOSPHERE, 552)
    nennt_formel = re.search(r"nordamerik|north american", kommentare, re.IGNORECASE)
    nennt_grenze = "10" in kommentare and re.search(r"°?\s*c\b", kommentare, re.IGNORECASE)

    assert nennt_formel, (
        "geosphere.py traegt um die berechnete wind_chill-Groesse "
        "(Zeile ~552) keinen KOMMENTAR, der die nordamerikanische "
        f"Windchill-Formel benennt (AC-8). Gefunden: {kommentare!r}"
    )
    assert nennt_grenze, (
        "geosphere.py-Kommentar um Zeile ~552 nennt nicht die "
        "Gueltigkeitsgrenze T <= 10 °C der nordamerikanischen "
        f"Windchill-Formel (AC-8). Gefunden: {kommentare!r}"
    )
