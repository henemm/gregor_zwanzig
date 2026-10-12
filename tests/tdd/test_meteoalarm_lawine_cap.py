"""#1430 Lawinenwarnung (MeteoAlarm awareness_type 9): Offline-Tests ohne Netz.

Bewusst NICHT live-markiert (anders als test_meteoalarm_source.py), damit sie im
Default-Lauf (addopts: -m 'not email and not live and not staging') laufen.
Fixture wird relativ zu dieser Datei aufgeloest.
"""
from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_ac4_lawine_typ9_wird_zur_gefahrenart_avalanche_hitze_bleibt_erhalten():
    """#1430 AC-1: GIVEN die aufgezeichnete CAP-Datei mit Lawinenwarnung
    (awareness_type 9, Stufe 3 orange) UND Hitzewarnung (Typ 5, Stufe 2),
    WHEN sie ueber den CAP-Weg eingelesen wird, THEN entstehen ZWEI Warnungen:
    `avalanche` mit Stufe 3 (nicht umgerechnet) und die unveraenderte Hitze."""
    from services.official_alerts.meteoalarm import _extract_alerts_from_cap

    cap_text = _read_fixture("cap_avalanche_plus_heat.xml")
    alerts = _extract_alerts_from_cap(cap_text)

    by_hazard = {a.hazard: a for a in alerts}
    assert len(alerts) == 2, (
        f"erwartet Lawine + Hitze (2 Warnungen), erhalten {len(alerts)}: {alerts}"
    )
    assert by_hazard["avalanche"].level == 3
    assert by_hazard["extreme_heat"].level == 2


def test_ac3_verworfene_typen_hinterlassen_debug_zeile_typ9_bleibt(caplog):
    """#1430 AC-3: GIVEN Eintraege der Typen 4 (Nebel), 7 (Kueste), 99
    (unbekannt) neben einer Typ-9-Warnung, WHEN sie durch die gemeinsame
    Mapper-Stelle laufen, THEN bleibt genau die Typ-9-Warnung uebrig und das
    Log (DEBUG) nennt je Typ Nummer und Stufe; Nebel/Kueste mit dem Vermerk
    'bewusst nicht unterstuetzt'."""
    import logging

    from services.official_alerts.meteoalarm import _group_and_map_info_entries

    def _entry(type_raw: str, level_raw: str) -> dict:
        return {
            "type_raw": type_raw, "level_raw": level_raw,
            "onset": "2026-07-15T00:00:00+02:00", "expires": "2026-07-15T23:59:59+02:00",
            "area_desc": "Villach (Stadt)", "lang": "de-DE",
            "event": f"Typ {type_raw}", "headline": f"Typ {type_raw}",
        }

    entries = [
        _entry("4; fog", "3; orange; Severe"),
        _entry("7; coastal-event", "2; yellow; Moderate"),
        _entry("99; unbekannt", "4; red; Extreme"),
        _entry("9; avalanche", "3; orange; Severe"),
    ]
    with caplog.at_level(logging.DEBUG, logger="meteoalarm"):
        alerts = _group_and_map_info_entries(entries)

    assert [a.hazard for a in alerts] == ["avalanche"], (
        f"nur die Typ-9-Warnung darf uebrig bleiben, erhalten {alerts}"
    )
    log = "\n".join(r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG)
    lines = log.splitlines()
    nebel = [l for l in lines if "4" in l and "nicht unterst" in l]
    kueste = [l for l in lines if "7" in l and "nicht unterst" in l]
    unbekannt = [l for l in lines if "99" in l and "unbekannter awareness_type" in l]
    assert nebel, f"keine Debug-Zeile fuer Nebel (Typ 4, bewusst nicht unterstuetzt): {log!r}"
    assert kueste, f"keine Debug-Zeile fuer Kueste (Typ 7, bewusst nicht unterstuetzt): {log!r}"
    assert unbekannt, f"keine Debug-Zeile 'unbekannter awareness_type' fuer Typ 99: {log!r}"
    assert any("3" in l for l in nebel) and any("2" in l for l in kueste) and any("4" in l for l in unbekannt), (
        f"jede Debug-Zeile muss die Stufe nennen: {log!r}"
    )
