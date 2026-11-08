"""Issue #2009 (Nachmessung): erwartete Vorlaufwerte im 5-Min-Takt.

SPEC: docs/specs/modules/fix_2009_laufender_regen_vorlauf.md (Waechter 6 = AC-6)

Der Radar-Takt `3-58/5` (internal/scheduler/scheduler.go) gegen INCA-Frames im
15-Min-Raster (:00/:15/:30/:45) ergibt vor einem Regenbeginn Vorlaeufe von
2, 7 oder 12 Minuten (mod 15) -- ehrliche Arithmetik, keine Klemmung. Dieser
Waechter schreibt das als ERWARTETEN Wert fest, damit der Verdacht "alles ist
8" (Relikt des alten Takts :07/:22/:37/:52) nicht wiederkehrt.

BEWUSST schon heute gruen: der Fehler aus #2009 sitzt im LAUFENDEN Regen
(Waechter 1/2), nicht im Vorlauf vor einem Regenbeginn. Dieser Waechter ist
die Festschreibung der Arithmetik und zugleich Gegenprobe: eine Korrektur,
die jeden Vorlauf auf 0 (oder auf ein festes Raster) zieht, faellt hier.

Echter Pfad, kein Mock: `check_radar_alerts()` ueber die `AlarmPruefstrecke`
bzw. `CompareRadarAlertService.check_all_compare_presets()`, Frames ueber die
DI-Naht `frame_source=` eines echten `RadarNowcastService`; gelesen wird der
echte Alarmlog. Ort Reykjavik (UTC+0), gestellte Uhr.
"""
from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.loader import save_location
from services.radar_service import RadarNowcastService

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.helpers.nowcast_gate_fixtures import (
    clean_uid, compare_radar_service, location, radar_preset, read_log,
    reset_radar_cache, save_trip, settings_email_only, write_presets,
    write_user_tier,
)
from tests.helpers.radar_vorlauf_strecke import ETAPPE_GANZTAGS, baue_trip

_TAG = datetime(2026, 8, 11, tzinfo=timezone.utc)
_REGENBEGINN = _TAG.replace(hour=12)                   # 12:00 UTC, INCA-Slot
# Alle zwoelf Taktminuten der Stunde vor dem Regenbeginn: 11:03 ... 11:58.
_TAKT = [_TAG.replace(hour=11, minute=m) for m in range(3, 60, 5)]
# Literal (aus der Arithmetik, nicht aus dem Pruefling): Vorlauf mod 15.
_ERLAUBT_MOD_15 = {2, 7, 12}

_ANGELEGT: list[str] = []


@pytest.fixture(autouse=True)
def _aufraeumen():
    _ANGELEGT.clear()
    yield
    for uid in _ANGELEGT:
        clean_uid(uid)


def _uid(tag: str) -> str:
    uid = f"tdd-2009-takt-{tag}-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    return uid


def _inca_regen_ab_mittag(lat: float, lon: float) -> list:
    """INCA-Raster 10:45 .. 15:45, trocken bis 11:45, nass ab 12:00 fuer
    eine Stunde."""
    from providers.brightsky import RadarFrame
    anker = _TAG.replace(hour=10, minute=45)
    frames = []
    for k in range(21):
        ts = anker + timedelta(minutes=15 * k)
        nass = _REGENBEGINN <= ts < _REGENBEGINN + timedelta(hours=1)
        frames.append(RadarFrame(timestamp=ts, precip_mm_h=2.0 if nass else 0.0))
    return frames


def _vorlauf_trip(at: datetime) -> int | None:
    uid = _uid(f"trip-{at:%H%M}")
    clean_uid(uid)
    trip = baue_trip(uid, ETAPPE_GANZTAGS, at=at)
    # Briefing-Zeiten weit weg vom Messzeitraum (Briefing-Naehe-Sperre #1594).
    trip.report_config.morning_time = time(5, 0)
    trip.report_config.evening_time = time(21, 0)
    with freeze_time(at):
        save_trip(trip, uid)
    lauf = AlarmPruefstrecke(user_id=uid, settings=settings_email_only()).lauf(
        at=at, zweig="radar", trip=trip,
        radar_service=RadarNowcastService(frame_source=_inca_regen_ab_mittag),
    )
    eintraege = [
        e for e in read_log(uid)["entries"]
        if e.get("entity_id") == trip.id and e.get("reason") == "nowcast"
    ]
    assert lauf.triggered_count == 1 and len(eintraege) == 1, (
        f"Waechter 6 Vorbedingung (Trip, {at:%H:%M}): genau ein Alarm mit "
        f"Log-Eintrag erwartet (triggered_count={lauf.triggered_count}, "
        f"Eintraege={len(eintraege)})."
    )
    return eintraege[0].get("lead_time_minutes")


def _vorlauf_ortsvergleich(at: datetime) -> int | None:
    uid = _uid(f"cmp-{at:%H%M}")
    clean_uid(uid)
    preset_id = f"cp-{uid}"
    with freeze_time(at):
        write_user_tier(uid, "premium")
        save_location(location("loc-takt", "Takt-Ort"), user_id=uid)
        write_presets(uid, [radar_preset(preset_id, ["loc-takt"], user_id=uid)])
        reset_radar_cache()
        gesendet = compare_radar_service(
            uid, settings_email_only(), _inca_regen_ab_mittag,
            lambda subject, body: None,
        ).check_all_compare_presets()
    reset_radar_cache()
    eintraege = [
        e for e in read_log(uid)["entries"]
        if e.get("entity_id") == preset_id and e.get("reason") == "nowcast"
    ]
    assert gesendet == 1 and len(eintraege) == 1, (
        f"Waechter 6 Vorbedingung (Ortsvergleich, {at:%H:%M}): genau ein Alarm "
        f"mit Log-Eintrag erwartet (gesendet={gesendet}, Eintraege={len(eintraege)})."
    )
    return eintraege[0].get("lead_time_minutes")


_PFADE = {"trip": _vorlauf_trip, "ortsvergleich": _vorlauf_ortsvergleich}


@pytest.mark.parametrize("pfad", sorted(_PFADE))
def test_waechter6_vorlauf_im_takt_3_58_5_liegt_bei_2_7_12_mod_15(pfad):
    """AC-6: zwoelf Laeufe im Takt `3-58/5` vor einem Regenbeginn im
    INCA-Raster -> die protokollierten Vorlaeufe sind exakt (12:00 - Lauf),
    liegen mod 15 nur bei 2/7/12, nehmen ALLE drei Werte an und sind nicht
    durchgehend 8."""
    gemessen = {at: _PFADE[pfad](at) for at in _TAKT}
    erwartet = {at: int((_REGENBEGINN - at).total_seconds() // 60) for at in _TAKT}
    bericht = {f"{at:%H:%M}": v for at, v in gemessen.items()}

    assert gemessen == erwartet, (
        f"AC-6 ({pfad}): Vorlauf muss der Abstand Lauf -> Regenbeginn sein. "
        f"Gemessen {bericht}, erwartet "
        f"{ {f'{at:%H:%M}': v for at, v in erwartet.items()} }."
    )
    reste = {v % 15 for v in gemessen.values()}
    assert reste == _ERLAUBT_MOD_15, (
        f"AC-6 ({pfad}): im Takt `3-58/5` gegen 15-Min-Frames muessen die "
        f"Vorlaeufe mod 15 genau {sorted(_ERLAUBT_MOD_15)} ergeben, gemessen "
        f"{sorted(reste)} ({bericht})."
    )
    assert set(gemessen.values()) != {8} and 8 not in gemessen.values(), (
        f"AC-6 ({pfad}): der Vorlauf 8 ist im Takt `3-58/5` gegen das "
        f"INCA-Raster nicht erreichbar ({bericht})."
    )
