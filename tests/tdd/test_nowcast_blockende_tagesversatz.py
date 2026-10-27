"""TDD RED — Issue #2051 S1: asymmetrischer Tagesversatz von Beginn und Ende.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-6.

Fachlicher Kern: `onset_time`/`event_end_time` sind reines "HH:MM" ohne
Datum. Beginn und Ende koennen auf VERSCHIEDENE Kalendertage fallen (Beginn
23:50 ohne Versatz, Ende 00:40 am Folgetag). Der Tagesversatz des Endes muss
deshalb aus dem ENDE-Zeitpunkt abgeleitet werden (#2009-Muster:
`day_offset(now_utc, _end_dt, tz)`) — vom Beginn kopiert waere er still
falsch, und "00:40" ohne Tagesbezug ist mehrdeutig (heute Nacht oder in ueber
23 Stunden?).

RED heute: `NowcastResult` kennt `event_end_minutes` nicht (`TypeError` beim
Konstruktor), `OnsetEvent` kennt `event_end_time`/`event_end_day_offset`
nicht (`AttributeError`).

Mock-frei: echte `RadarFrame`/`NowcastResult`/`OnsetEvent`-Objekte durch die
echte Projektion. Die Uhr steht fest — im Ableitungsteil per `now=`,
im Projektionsteil per `freeze_time`, weil der Buendel-Konstruktor
`onset_time` selbst aus `datetime.now()` bildet.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from output.renderers.alert.project import to_multi_location_onset_alert_message
from providers.brightsky import RadarFrame
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import NowcastResult, RadarNowcastService

# 23:40 Ortszeit Wien am 2026-08-21 (CEST = UTC+2) -> 21:40 UTC.
_TZ = ZoneInfo("Europe/Vienna")
_NOW = datetime(2026, 8, 21, 21, 40, tzinfo=timezone.utc)
_FROZEN_UTC = "2026-08-21 21:40:00+00:00"

_UNSET = object()


def _frames(raster: dict[int, float]) -> list[RadarFrame]:
    return [
        RadarFrame(timestamp=_NOW + timedelta(minutes=minute), precip_mm_h=rate)
        for minute, rate in sorted(raster.items())
    ]


def _result(raster: dict[int, float]):
    svc = RadarNowcastService(cache=RadarNowcastCacheService())
    return svc._derive_result(_frames(raster), "radar", now=_NOW)


def _nowcast(*, event_end_minutes: object = _UNSET) -> NowcastResult:
    """Beginn in 10 Minuten (23:50 Ortszeit); die neuen Felder nur auf
    ausdruecklichen Wunsch setzen (Sentinel-Muster)."""
    fields = dict(
        onset_minutes=10, intensity_label="Starker Regen", source="radar",
        is_convective=False,
    )
    if event_end_minutes is not _UNSET:
        fields["event_end_minutes"] = event_end_minutes
    return NowcastResult(**fields)


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Nowcast-Dienst und Projektion werden RELATIV
    ZU DIESER Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still
    die Dateien des Hauptrepos."""
    from output.renderers.alert import project as project_module
    from services import radar_service as radar_module

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (radar_module, project_module):
        modul_pfad = Path(inspect.getfile(modul)).resolve()
        assert modul_pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
        )


# ---------------------------------------------------------------------------
# AC-6 (a) — die Ableitung ueber Mitternacht
# ---------------------------------------------------------------------------


def test_ac6_block_ueber_mitternacht_wird_vollstaendig_abgeleitet():
    """AC-6 (Vorstufe) GIVEN Frames, die den Uebergang ueber Mitternacht
    abbilden (jetzt 23:40 Ortszeit; nass von 23:50 bis 00:40 des Folgetags,
    danach trocken)
    WHEN `_derive_result` Beginn und Ende ableitet
    THEN steht der Beginn bei 10 Minuten und das Ende bei 60 Minuten — die
    Ableitung stolpert nicht ueber die Tagesgrenze.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht."""
    raster = {m: (1.0 if 10 <= m <= 60 else 0.0) for m in range(0, 121, 5)}

    result = _result(raster)

    assert result.onset_minutes == 10, (
        f"Vorbedingung: Beginn bei Minute 10, bekam {result.onset_minutes}"
    )
    assert result.event_end_minutes == 60, (
        f"RED: Ende bei Minute 60 (00:40 Ortszeit) erwartet, bekam "
        f"{result.event_end_minutes!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 (b) — Beginn und Ende tragen VERSCHIEDENE Tagesversaetze
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac6_beginn_ohne_versatz_ende_mit_versatz():
    """AC-6 GIVEN einen Onset-Alarm mit Beginn um 23:50 Ortszeit (kein
    Tagesversatz) und einem daraus abgeleiteten Ende um 00:40 des Folgetags
    WHEN Beginn und Ende in das Renderer-Modell projiziert werden
    THEN traegt `onset_day_offset=0`, waehrend `event_end_day_offset=1` ist —
    der Tagesversatz des Endes ist eigenstaendig aus dem Ende-Zeitpunkt
    abgeleitet, NICHT vom Beginn kopiert.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht (`TypeError`)
    und `OnsetEvent` kennt `event_end_day_offset` nicht."""
    msg = to_multi_location_onset_alert_message(
        [("Sillian", _nowcast(event_end_minutes=60))],
        tz=_TZ, stand_at="23:40",
    )
    event = msg.events[0]

    assert event.onset_time == "23:50", (
        f"Vorbedingung: Beginn 23:50 Ortszeit erwartet, bekam "
        f"{event.onset_time!r}"
    )
    assert event.onset_day_offset == 0, (
        f"Der Beginn liegt noch am heutigen Tag: {event.onset_day_offset!r}"
    )
    assert event.event_end_time == "00:40", (
        f"RED: Ende-Uhrzeit 00:40 Ortszeit erwartet, bekam "
        f"{getattr(event, 'event_end_time', None)!r}"
    )
    assert event.event_end_day_offset == 1, (
        f"RED: das Ende liegt am Folgetag — erwartet Tagesversatz 1, bekam "
        f"{getattr(event, 'event_end_day_offset', None)!r}"
    )
    assert event.event_end_day_offset != event.onset_day_offset, (
        "Der Tagesversatz des Endes ist offenbar vom Beginn kopiert — die "
        "Ableitung muss asymmetrisch sein."
    )


@freeze_time(_FROZEN_UTC)
def test_ac6_ende_am_selben_tag_traegt_keinen_versatz():
    """AC-6 (Gegenprobe) GIVEN denselben Beginn um 23:50 Ortszeit, aber ein
    Ende bereits um 23:55 (5 Minuten spaeter, derselbe Kalendertag)
    WHEN Beginn und Ende projiziert werden
    THEN tragen BEIDE den Tagesversatz 0 — der Ende-Versatz ist nicht
    pauschal 1, sondern haengt am tatsaechlichen Zeitpunkt.

    Ohne diese Gegenprobe waere ein fest verdrahtetes `event_end_day_offset=1`
    von der Zusicherung oben nicht zu unterscheiden.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht (`TypeError`)."""
    msg = to_multi_location_onset_alert_message(
        [("Sillian", _nowcast(event_end_minutes=15))],
        tz=_TZ, stand_at="23:40",
    )
    event = msg.events[0]

    assert event.event_end_time == "23:55", (
        f"RED: Ende-Uhrzeit 23:55 Ortszeit erwartet, bekam "
        f"{getattr(event, 'event_end_time', None)!r}"
    )
    assert event.event_end_day_offset == 0, (
        f"Ein Ende am selben Kalendertag darf keinen Tagesversatz tragen: "
        f"{getattr(event, 'event_end_day_offset', None)!r}"
    )
