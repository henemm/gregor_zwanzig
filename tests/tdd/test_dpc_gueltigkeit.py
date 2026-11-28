"""TDD RED -- Issue #2221: DPC-Warnungen erhalten das Gueltigkeitsfenster des
Bezugstags (00:00:00-23:59:59 Europe/Rome, gespeichert als aware UTC).

SPEC: docs/specs/modules/fix_2221_dpc_gueltigkeit.md, AC-1 bis AC-7.

Kern-Schicht (kein Netz, keine Mocks): das echte aufgezeichnete Bulletin-Zip
wird ueber den echten Parser ``_parse_bulletin_zip`` gelesen (echte
``httpx.Response`` mit den Fixture-Bytes); nur der Netzabruf
``_get_cached_bulletin`` wird durch diesen echten Parse ersetzt, die Uhr ueber
den vorgesehenen Haken ``_NOW_FN``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

import services.official_alerts.dpc as dpc
from services.official_alerts.base import filter_alerts_to_window
from output.renderers.alert.official_alerts import (
    _format_validity,
    official_alert_state_key,
    official_alerts_to_sms_entries,
)

ROME = ZoneInfo("Europe/Rome")
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "dpc"
KHW_TREN_A = (46.7248, 12.2254)          # Tren-A, GIALLA nur im tomorrow-Datensatz
SICI_A_GIALLA = (38.114738, 15.158302)   # Unwettertag: Temporali GIALLA
SARD_A_FLOOD_ROSSA = (39.121980, 8.609139)  # Unwettertag: Idrogeo ROSSA


def _use_fixture(monkeypatch, name: str, now_utc: datetime) -> None:
    payload = (FIXTURES / name).read_bytes()
    bulletin = dpc._parse_bulletin_zip(httpx.Response(200, content=payload))
    monkeypatch.setattr(dpc, "_get_cached_bulletin", lambda: bulletin)
    monkeypatch.setattr(dpc, "_NOW_FN", lambda: now_utc)


def _rome_day(y: int, m: int, d: int) -> tuple[datetime, datetime]:
    start = datetime(y, m, d, 0, 0, 0, tzinfo=ROME)
    end = datetime(y, m, d, 23, 59, 59, tzinfo=ROME)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _fetch(lat_lon) -> list:
    return dpc.DpcSource().fetch(*lat_lon)


def _assert_window(alert, y: int, m: int, d: int) -> None:
    exp_from, exp_to = _rome_day(y, m, d)
    assert alert.valid_from is not None and alert.valid_to is not None, (
        f"DPC-Warnung ohne Gueltigkeitsfenster: {alert}"
    )
    assert alert.valid_from.utcoffset() == timedelta(0), "valid_from nicht als aware UTC"
    assert alert.valid_to.utcoffset() == timedelta(0), "valid_to nicht als aware UTC"
    assert alert.valid_from == exp_from
    assert alert.valid_to == exp_to


def test_ac1_today_datensatz_fenster_ausgabetag_rom(monkeypatch):
    """AC-1: Abruf am Ausgabetag 18.01.2026 -> Fenster 18.01. Rom-Tag."""
    _use_fixture(monkeypatch, "unwettertag_20260118_1515.zip",
                 datetime(2026, 1, 18, 16, 0, tzinfo=timezone.utc))
    for point in (SICI_A_GIALLA, SARD_A_FLOOD_ROSSA):
        alerts = _fetch(point)
        assert alerts, f"keine Warnung fuer {point}"
        for alert in alerts:
            _assert_window(alert, 2026, 1, 18)


def test_ac2_tomorrow_datensatz_fenster_folgetag(monkeypatch):
    """AC-2: Bulletin vom 30.07., Abruf 31.07. 08:00 Rom -> Fenster 31.07."""
    _use_fixture(monkeypatch, "ruhetag_20260730_1511.zip",
                 datetime(2026, 7, 31, 8, 0, tzinfo=ROME).astimezone(timezone.utc))
    alerts = _fetch(KHW_TREN_A)
    assert [a.hazard for a in alerts] == ["thunderstorm"]
    _assert_window(alerts[0], 2026, 7, 31)


def test_ac3_mitternachtsgrenze_rom_kalendertag(monkeypatch):
    """AC-3: 30.07. 22:30 UTC = 31.07. 00:30 Rom -> tomorrow-Datensatz,
    Tren-A erscheint mit Fenster 31.07. (bisher: UTC-Datum 30.07. -> today
    -> keine Warnung)."""
    _use_fixture(monkeypatch, "ruhetag_20260730_1511.zip",
                 datetime(2026, 7, 30, 22, 30, tzinfo=timezone.utc))
    alerts = _fetch(KHW_TREN_A)
    assert [a.hazard for a in alerts] == ["thunderstorm"], (
        "um 00:30 italienischer Zeit gilt bereits der Folgetag (tomorrow-Datensatz)"
    )
    _assert_window(alerts[0], 2026, 7, 31)


def test_ac4_darstellung_ganztaegig_und_sms_ohne_stunde(monkeypatch):
    """AC-4: Gueltig-Zeile 'Fr 31.07. · ganztägig', SMS-Eintrag ohne Stunde."""
    _use_fixture(monkeypatch, "ruhetag_20260730_1511.zip",
                 datetime(2026, 7, 31, 8, 0, tzinfo=ROME).astimezone(timezone.utc))
    alert = _fetch(KHW_TREN_A)[0]
    assert _format_validity(alert, ROME, lang="de") == "Fr 31.07. · ganztägig"
    entries = official_alerts_to_sms_entries([alert], tz=ROME, min_level=2)
    assert len(entries) == 1
    assert entries[0][2] is None, f"ganztaegig darf keine SMS-Stunde tragen: {entries}"


def test_ac5_zwei_bezugstage_verschiedene_gedaechtnis_schluessel(monkeypatch):
    """AC-5: gleiche Zone+Gefahr (Sard-A, Hochwasser) an zwei Bezugstagen:
    Unwetter-Bulletin am Ausgabetag 18.01. (today) und am Folgetag 19.01.
    (tomorrow) -> verschiedene Melde-Gedaechtnis-Schluessel."""
    _use_fixture(monkeypatch, "unwettertag_20260118_1515.zip",
                 datetime(2026, 1, 18, 16, 0, tzinfo=timezone.utc))
    day1 = [a for a in _fetch(SARD_A_FLOOD_ROSSA) if a.hazard == "flood"]
    _use_fixture(monkeypatch, "unwettertag_20260118_1515.zip",
                 datetime(2026, 1, 19, 8, 0, tzinfo=timezone.utc))
    day2 = [a for a in _fetch(SARD_A_FLOOD_ROSSA) if a.hazard == "flood"]
    assert day1 and day2, "Sard-A muss an beiden Bezugstagen eine Hochwasser-Warnung tragen"
    assert official_alert_state_key(day1[0]) != official_alert_state_key(day2[0])
    _assert_window(day1[0], 2026, 1, 18)
    _assert_window(day2[0], 2026, 1, 19)


def test_ac6_fensterfilter_verwirft_vortag_behaelt_bezugstag(monkeypatch):
    """AC-6: Warnung vom 31.07.: Fenster am 01.08. -> verworfen; Fenster am
    31.07. -> behalten."""
    _use_fixture(monkeypatch, "ruhetag_20260730_1511.zip",
                 datetime(2026, 7, 31, 8, 0, tzinfo=ROME).astimezone(timezone.utc))
    alert = _fetch(KHW_TREN_A)[0]
    next_from, next_to = _rome_day(2026, 8, 1)
    assert filter_alerts_to_window([alert], next_from + timedelta(hours=8), next_to) == []
    same_from, same_to = _rome_day(2026, 7, 31)
    assert filter_alerts_to_window(
        [alert], same_from + timedelta(hours=8), same_from + timedelta(hours=16)
    ) == [alert]


def test_ac7_regression_stufen_und_veraltetes_bulletin(monkeypatch):
    """AC-7: Stufen unveraendert (Sard-A Hochwasser ROSSA = 4 im tomorrow-
    Datensatz, Bezugstag 19.01.), veraltetes Bulletin (zwei Tage nach
    Ausgabe) -> leere Liste."""
    _use_fixture(monkeypatch, "unwettertag_20260118_1515.zip",
                 datetime(2026, 1, 19, 5, 0, tzinfo=timezone.utc))
    flood = [a for a in _fetch(SARD_A_FLOOD_ROSSA) if a.hazard == "flood"]
    assert [a.level for a in flood] == [4]
    _use_fixture(monkeypatch, "unwettertag_20260118_1515.zip",
                 datetime(2026, 1, 20, 12, 0, tzinfo=timezone.utc))
    assert _fetch(SARD_A_FLOOD_ROSSA) == []
