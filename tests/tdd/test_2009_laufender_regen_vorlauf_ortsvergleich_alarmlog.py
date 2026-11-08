"""TDD RED — Issue #2009 (Nachmessung): laufender Regen im Ortsvergleichs-Alarmlog.

SPEC: docs/specs/modules/fix_2009_laufender_regen_vorlauf.md (Waechter 2 = AC-2)

Der Ortsvergleichs-Pfad (`check_all_compare_presets`) schreibt heute
`lead_time_minutes = nowcast.onset_minutes` und `event_at = jetzt +
onset_minutes` -- bei laufendem Regen also den Abstand zum NAECHSTEN nassen
Frame. Verlangt ist dieselbe geteilte Ableitung wie im Trip (ADR-0021):
Vorlauf 0, Beginn = Lauf-Zeitpunkt, und zwar DERSELBE Wert wie im Trip.

Kein Mock()/patch(): echter `CompareRadarAlertService` mit echtem
`RadarNowcastService(frame_source=...)`, echter Ort/Preset auf der isolierten
Datenwurzel, Zustellung ueber `mail_sink`. Der Trip-Vergleichswert kommt aus
einem echten `check_radar_alerts()`-Lauf ueber die `AlarmPruefstrecke`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.loader import save_location
from services.radar_service import RadarNowcastService

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.helpers.nowcast_gate_fixtures import (
    clean_uid, compare_radar_service, location, radar_preset, read_log,
    reset_radar_cache, settings_email_only, write_presets, write_user_tier,
)
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels, _write_premium_profile,
)

_SLOT = _AT                                  # 10:00 UTC, laufender Rasterslot
_LAUF = _SLOT + timedelta(minutes=8)         # 10:08 UTC, Taktminute aus `3-58/5`
_NAECHSTER_VIERTELSTUNDENPUNKT = _SLOT + timedelta(minutes=15)

_ANGELEGT: list[str] = []


@pytest.fixture(autouse=True)
def _aufraeumen():
    _ANGELEGT.clear()
    yield
    for uid in _ANGELEGT:
        clean_uid(uid)
        _clean_user(uid)


def _uid(tag: str) -> str:
    uid = f"tdd-2009-laufend-cmp-{tag}-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    return uid


def _laeuft_bereits(lat: float, lon: float) -> list:
    """Laufendes (10:00) und naechstes Frame (10:15) nass, Ende 10:45 --
    `already_running` mit `onset_minutes` = 7 (nicht `None`)."""
    from providers.brightsky import RadarFrame
    return [
        RadarFrame(timestamp=_SLOT + timedelta(minutes=15 * k),
                   precip_mm_h=2.0 if k < 3 else 0.0)
        for k in range(13)
    ]


def _zeit(raw) -> datetime | None:
    if raw is None:
        return None
    ts = datetime.fromisoformat(str(raw))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _ortsvergleich_lauf(uid: str, preset_id: str) -> tuple[int, dict]:
    with freeze_time(_AT):
        write_user_tier(uid, "premium")
        save_location(location("loc-2009", "Laufend-Ort"), user_id=uid)
        write_presets(uid, [radar_preset(preset_id, ["loc-2009"], user_id=uid)])
    with freeze_time(_LAUF):
        reset_radar_cache()
        mails: list = []
        gesendet = compare_radar_service(
            uid, settings_email_only(), _laeuft_bereits,
            lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()
    reset_radar_cache()
    eintraege = [
        e for e in read_log(uid)["entries"]
        if e.get("entity_id") == preset_id and e.get("reason") == "nowcast"
    ]
    assert gesendet == 1 and len(eintraege) == 1, (
        f"Waechter 2 Vorbedingung: der Ortsvergleich muss genau einmal "
        f"ausloesen und protokollieren (gesendet={gesendet}, "
        f"Eintraege={eintraege!r})."
    )
    return gesendet, eintraege[0]


def _trip_lauf(uid: str) -> dict:
    trip_id = "trip-2009-w2-ref"
    _clean_user(uid)
    _write_premium_profile(uid, _AT)
    with freeze_time(_AT):
        trip = _radar_trip(uid, trip_id, send_email=True)
    lauf = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels()).lauf(
        at=_LAUF, zweig="radar", trip=trip,
        radar_service=RadarNowcastService(frame_source=_laeuft_bereits),
    )
    eintraege = [
        e for e in read_log(uid)["entries"]
        if e.get("entity_id") == trip_id and e.get("reason") == "nowcast"
    ]
    assert lauf.triggered_count == 1 and len(eintraege) == 1, (
        f"Waechter 2 Vorbedingung (Trip-Referenz): genau ein Alarm erwartet "
        f"(triggered_count={lauf.triggered_count}, Eintraege={eintraege!r})."
    )
    return eintraege[0]


def test_waechter2_laufender_regen_ortsvergleich_alarmlog_vorlauf_null_wie_trip():
    """AC-2: laufender Regen am Ort, Lauf 10:08 -> Alarmlog des Ortsvergleichs
    traegt Vorlauf 0 und Beginn 10:08 -- und DENSELBEN Vorlauf/Beginn wie der
    Trip bei denselben Frames zum selben Zeitpunkt."""
    _gesendet, eintrag = _ortsvergleich_lauf(_uid("w2"), "cp-2009-w2")

    assert eintrag.get("lead_time_minutes") == 0, (
        f"AC-2: bei laufendem Regen muss der Vorlauf im Ortsvergleichs-Log 0 "
        f"sein, protokolliert ist {eintrag.get('lead_time_minutes')!r}."
    )
    beginn = _zeit(eintrag.get("event_at"))
    assert beginn != _NAECHSTER_VIERTELSTUNDENPUNKT, (
        f"AC-2: Beginn ist der naechste Viertelstundenpunkt "
        f"{_NAECHSTER_VIERTELSTUNDENPUNKT.isoformat()}, nicht der Lauf-Zeitpunkt."
    )
    assert beginn == _LAUF, (
        f"AC-2: Beginn muss {_LAUF.isoformat()} sein, ist "
        f"{eintrag.get('event_at')!r}."
    )

    trip_eintrag = _trip_lauf(_uid("w2-trip"))
    assert (
        eintrag.get("lead_time_minutes"), _zeit(eintrag.get("event_at")),
    ) == (
        trip_eintrag.get("lead_time_minutes"), _zeit(trip_eintrag.get("event_at")),
    ), (
        f"AC-2: Ortsvergleich und Trip muessen fuer dieselbe Lage denselben "
        f"Vorlauf und Beginn protokollieren (geteilte Ableitung). Ortsvergleich="
        f"({eintrag.get('lead_time_minutes')!r}, {eintrag.get('event_at')!r}), "
        f"Trip=({trip_eintrag.get('lead_time_minutes')!r}, "
        f"{trip_eintrag.get('event_at')!r})."
    )
