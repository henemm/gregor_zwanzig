"""TDD RED — Issue #1599: EINE Umrechnung "Endstunde -> Zeitgrenze".
SPEC: fix_1599_tagesfenster_randstunde.md (AC-7, AC-8, AC-9, AC-20).

AC-7..AC-9 pruefen den gemeinsamen Helfer ``window_end_utc_exclusive()`` gegen
HART hinterlegte Erwartungswerte — nie mit derselben Formel nachgerechnet, die
der Pruefling benutzt (sonst brechen Test und Pruefling gemeinsam).

AC-20 prueft nicht den Helfer, sondern seine REICHWEITE: wird er verfaelscht,
muessen sich alle drei Alarm-Pfade (Trip-Ziel-Segment, Compare-Δ-Alarm,
Compare-amtliche-Warnungen) gleichermassen verschieben. Ein Pfad mit eigener
Inline-Rechnung faellt genau hier auf. Bewusst NICHT Trip-Ergebnis gegen
Compare-Ergebnis verglichen — beide haengen am selben Helfer, ein Fehler darin
braeche beide gleich und der Vergleich bliebe gruen.

Ausfuehrung:
    uv run pytest tests/unit/test_tagesfenster_grenzen.py -v \
        --disable-socket --allow-hosts=127.0.0.1
"""
from __future__ import annotations

import importlib
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

WIEN = ZoneInfo("Europe/Vienna")

# Heimat des Helfers + jeder Verbraucher. Ein Modul-Import auf Modulebene
# (``from app.day_window import ...``) bindet den Namen lokal — deshalb wird
# beides gepatcht.
_HELFER_MODULE = (
    "app.day_window",
    "services.trip_segments",
    "services.compare_location_weather_source",
    "services.compare_official_alert",
)


def _helfer():
    from app.day_window import window_end_utc_exclusive

    return window_end_utc_exclusive


def test_ac7_endstunde_19_endet_um_20_uhr_ortszeit():
    """AC-7: ``end_hour = 19`` -> exklusive Obergrenze 20:00 Ortszeit desselben
    Kalendertags. 12.07.2026 ist in Europe/Vienna Sommerzeit (UTC+2), also
    18:00 UTC. Hart hinterlegt."""
    assert _helfer()(date(2026, 7, 12), 19, WIEN) == datetime(
        2026, 7, 12, 18, 0, tzinfo=timezone.utc)


def test_ac8_endstunde_23_endet_um_mitternacht_des_folgetags():
    """AC-8: ``end_hour = 23`` -> 00:00 Ortszeit des FOLGETAGS (``time(24)``
    existiert nicht) = 13.07.2026 00:00 Wien = 12.07.2026 22:00 UTC."""
    assert _helfer()(date(2026, 7, 12), 23, WIEN) == datetime(
        2026, 7, 12, 22, 0, tzinfo=timezone.utc)


def test_ac9_sommerzeitumstellung_wird_nach_der_utc_umrechnung_addiert():
    """AC-9: Am realen Umstellungsdatum 25.10.2026 (Europe/Vienna, Rueckstellung
    03:00 CEST -> 02:00 CET um 01:00 UTC) muss die ``+1 h`` NACH der
    UTC-Umrechnung wirken.

    ``end_hour = 2`` ist der diskriminierende Fall: 02:00 Ortszeit ist an diesem
    Tag mehrdeutig, die erste Auslegung (``fold=0``, CEST) ergibt 00:00 UTC, plus
    eine Stunde 01:00 UTC. Vor der Umrechnung addiert (Ortszeit 03:00) kaeme
    02:00 UTC heraus — eine Stunde daneben. Nur an einem Umstellungstag trennen
    sich die Reihenfolgen.

    ``end_hour = 19`` am selben Tag liegt bereits in der Winterzeit (CET):
    20:00 Ortszeit = 19:00 UTC. Belegt, dass der tatsaechlich gueltige Versatz
    DIESES Tages benutzt wird, nicht ein fester Sommer-Versatz. Beide Werte aus
    den echten ``zoneinfo``-Daten abgeleitet, keine gestellte Umstellung.
    """
    tag = date(2026, 10, 25)
    assert _helfer()(tag, 2, WIEN) == datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)
    assert _helfer()(tag, 19, WIEN) == datetime(2026, 10, 25, 19, 0, tzinfo=timezone.utc)


def _alte_exklusive_grenze(local_date, end_hour, tz):
    """Die VERFAELSCHTE Fassung: Fenster endet exklusiv bei ``end_hour:00`` —
    genau die Rechnung, die vor #1599 dreifach dupliziert war. Kein Mock,
    sondern eine echte Funktion mit derselben Signatur."""
    return (datetime.combine(local_date, time(end_hour))
            .replace(tzinfo=tz).astimezone(timezone.utc))


def _verfaelsche_helfer(monkeypatch) -> list[str]:
    """Setzt ``window_end_utc_exclusive`` ueberall auf die alte Grenze. Leer =
    der Helfer existiert nicht, dann bewacht der Test nichts und muss scheitern."""
    getroffen: list[str] = []
    for name in _HELFER_MODULE:
        modul = importlib.import_module(name)
        if hasattr(modul, "window_end_utc_exclusive"):
            monkeypatch.setattr(modul, "window_end_utc_exclusive", _alte_exklusive_grenze)
            getroffen.append(name)
    assert getroffen, (
        f"AC-20: `window_end_utc_exclusive` ist in keinem der Module "
        f"{_HELFER_MODULE} erreichbar — der gemeinsame Helfer existiert nicht."
    )
    return getroffen


def test_ac20_trip_alarm_folgt_dem_gemeinsamen_helfer(monkeypatch):
    """AC-20 (1/3): Mit auf die alte Grenze verfaelschtem Helfer darf ein Gewitter
    in der Randstunde 19 KEINEN Trip-Alarm mehr ausloesen."""
    from tests.unit.test_alarm_zeitfenster_ziel import (
        ALPEN_LAT, ALPEN_LON, _alarm_mails)

    _verfaelsche_helfer(monkeypatch)
    mails = _alarm_mails(ALPEN_LAT, ALPEN_LON, "13:18", 19)
    assert not mails, (
        "AC-20: Der Trip-Alarmpfad reagiert nicht auf den verfaelschten Helfer "
        f"({[s for s, _ in mails]}) — das Ziel-Segment-Ende wird inline berechnet."
    )


def test_ac20_compare_delta_alarm_folgt_dem_gemeinsamen_helfer(monkeypatch, tmp_path):
    """AC-20 (2/3): Dasselbe fuer den Ortsvergleich-Δ-Alarm — Aenderung in der
    Randstunde 19, verfaelschter Helfer, kein Versand."""
    from tests.tdd.test_compare_alert_day_window import (
        ALPEN_LAT, ALPEN_LON, REGEN_MM, Szenario, flach)

    sz = Szenario(monkeypatch, tmp_path, ALPEN_LAT, ALPEN_LON, fenster=(4, 19))
    sz.anker(flach(sz), 7)
    _verfaelsche_helfer(monkeypatch)
    mails = sz.lauf(flach(sz, ((0, 19, REGEN_MM),)), 15)
    assert not mails, (
        "AC-20: Der Compare-Δ-Alarmpfad reagiert nicht auf den verfaelschten "
        f"Helfer ({[s for s, _ in mails]}) — `_window_bound()` rechnet selbst."
    )


def test_ac20_amtliche_warnungen_folgen_dem_gemeinsamen_helfer(monkeypatch):
    """AC-20 (3/3): Dasselbe fuer den Sichtbarkeits-Horizont der amtlichen
    Warnungen — Gueltigkeitsbeginn 19:45 Ortszeit, verfaelschter Helfer, kein
    Versand."""
    from tests.tdd.test_compare_alert_day_window import _amtliche_warnung_mails

    _verfaelsche_helfer(monkeypatch)
    mails = _amtliche_warnung_mails(
        monkeypatch,
        datetime(2026, 7, 12, 17, 45, tzinfo=timezone.utc),
        datetime(2026, 7, 12, 19, 0, tzinfo=timezone.utc))
    assert not mails, (
        "AC-20: Der Pfad der amtlichen Warnungen reagiert nicht auf den "
        f"verfaelschten Helfer ({[s for s, _ in mails]}) — `_day_window_end()` "
        "rechnet selbst."
    )
