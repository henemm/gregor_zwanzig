"""TDD RED — Issue #1459: Ortsvergleich protokolliert, Mandanten bleiben
getrennt, Bestandsdaten bleiben lesbar.

SPEC: docs/specs/modules/feat_1459_alert_protokoll.md (AC-12, AC-13, AC-14)

RED-Grund heute:
- ``compare_alert.py``/``compare_radar_alert.py``/``compare_official_alert.py``
  schreiben ueberhaupt keinen Protokoll-Eintrag (B1) -> ``alert_log.json``
  bleibt nach drei ausgeloesten Vergleichs-Alarmen leer.
- ``services.alert_log.append_entry()`` existiert nicht (AC-14).

Mock-frei: echte Presets/Orte/Schnappschuesse auf Platte, echte Services,
deterministische DI-Naehte (``weather_source``, ``radar_service``,
``register_official_alert_source``, ``mail_sink``) -- kein Netz.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.loader import get_data_dir, save_location
from app.models import SegmentWeatherSummary
from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import (
    COMPARE_DATA_ROOT, LAT, LON, clean_compare_user, fresh_user, gust_alert_trip,
    read_log, settings_email_only, weather,
)
from tests.helpers.compare_briefings import write_compare_briefings

_PRESET_ID = "cp-1459"


def _point(**summary):
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id="loc-a", name="Vergleichsort", lat=LAT, lon=LON, timeseries=None,
        aggregated=SegmentWeatherSummary(**summary),
        fetched_at=datetime.now(timezone.utc), provider="tdd-1459",
    )


class _ScriptedSource:
    """Deterministische ``LocationWeatherSource`` (Konfigurations-Naht, kein Mock)."""

    def __init__(self, **summary) -> None:
        self._summary = summary

    def fetch(self, point_id: str, lat: float, lon: float):
        return _point(**self._summary)


class _FakeOfficialSource:
    """Echte Quelle im Sinne des Quell-Protokolls (strukturelles Subtyping)."""

    def __init__(self, alerts) -> None:
        self._alerts = alerts

    @property
    def name(self) -> str:
        return "tdd-1459-source"

    def covers(self, lat, lon) -> bool:
        return True

    def fetch(self, lat, lon):
        return list(self._alerts)


def _radar_frames(lat, lon):
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=5.0),
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=8.0),
    ]


def _setup_compare_user(uid: str) -> None:
    """Ort, Preset (Δ + Radar + amtlich aktiv), Premium-Tier (kein Tageslimit)
    und der Δ-Anker-Schnappschuss."""
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    save_location(
        SavedLocation(id="loc-a", name="Vergleichsort", lat=LAT, lon=LON, elevation_m=1000),
        user_id=uid,
    )
    write_compare_briefings(COMPARE_DATA_ROOT / uid, [{
        "id": _PRESET_ID, "name": "Vergleich 1459", "user_id": uid,
        "location_ids": ["loc-a"], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["dummy@example.com"], "created_at": "2026-08-01T00:00:00Z",
        "radar_alert_enabled": True, "alert_cooldown_minutes": 0,
    }])
    user_dir = get_data_dir(uid)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "user.json").write_text(json.dumps({"tier": "premium"}))
    CompareWeatherSnapshotService(user_id=uid).save(
        _PRESET_ID, "loc-a", _point(gust_max_kmh=20.0),
    )


# ───────────────────────────────── AC-12 ───────────────────────────────────

def test_ac12_ortsvergleich_protokolliert_alle_drei_ausloeser():
    """AC-12 GIVEN ein Vergleichs-Preset loest je einmal einen Δ-, einen
    Radar- und einen amtlichen Alarm aus (jeweils erfolgreich)
    WHEN die drei Alarme versendet werden
    THEN entstehen drei Eintraege in ``entries`` mit LEEREM ``trip_id`` und
    gesetztem ``preset_id`` — je mit dem passenden Grund. Heute (B1)
    protokolliert der Ortsvergleich gar nicht."""
    from services.compare_alert import CompareAlertService
    from services.compare_official_alert import CompareOfficialAlertService
    from services.compare_radar_alert import CompareRadarAlertService
    from services.official_alerts import register_official_alert_source
    from services.official_alerts.models import OfficialAlert
    from services.radar_service import RadarNowcastService
    import services.official_alerts.base as base

    uid = fresh_user("ac12")
    clean_compare_user(uid)
    quellen = list(base._REGISTERED_SOURCES)
    base._REGISTERED_SOURCES.clear()
    try:
        _setup_compare_user(uid)
        now = datetime.now(timezone.utc)
        register_official_alert_source(_FakeOfficialSource([OfficialAlert(
            source="tdd-1459", hazard="thunderstorm", level=2, label="Gewitter",
            valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=6),
            region_label="Testregion",
        )]))
        mails: list = []
        sink = lambda subject, body: mails.append((subject, body))  # noqa: E731
        settings = settings_email_only()

        delta = CompareAlertService(
            settings=settings, user_id=uid,
            weather_source=_ScriptedSource(gust_max_kmh=60.0), mail_sink=sink,
        ).check_all_compare_presets()
        radar = CompareRadarAlertService(
            settings=settings, user_id=uid,
            radar_service=RadarNowcastService(frame_source=_radar_frames),
            mail_sink=sink,
        ).check_all_compare_presets()
        amtlich = CompareOfficialAlertService(
            settings=settings, user_id=uid, mail_sink=sink,
        ).check_all_compare_presets()

        assert (delta, radar, amtlich) == (1, 1, 1), (
            f"Voraussetzung: alle drei Vergleichs-Alarme muessen rausgehen, "
            f"erhalten Δ={delta}, Radar={radar}, amtlich={amtlich}."
        )
        entries = read_log(uid)["entries"]
        assert len(entries) == 3, (
            "Der Ortsvergleich protokolliert seine Alarme nicht — erwartet 3 "
            f"Eintraege, erhalten {len(entries)}."
        )
        assert all(e.get("trip_id") == "" for e in entries), (
            "Vergleichs-Eintraege muessen ein LEERES trip_id tragen, sonst "
            f"zaehlt die Archiv-Statistik sie als Tour-Alarme: {entries!r}"
        )
        assert all(e.get("preset_id") == _PRESET_ID for e in entries), (
            f"preset_id fehlt oder ist falsch: {entries!r}"
        )
        assert sorted(e.get("reason") for e in entries) == [
            "forecast_change", "nowcast", "official_alert",
        ], f"Die drei Gruende fehlen oder sind falsch: {entries!r}"
    finally:
        base._REGISTERED_SOURCES.clear()
        base._REGISTERED_SOURCES.extend(quellen)
        clean_compare_user(uid)


# ───────────────────────────────── AC-13 ───────────────────────────────────

def test_ac13_zwei_nutzer_protokollieren_streng_getrennt():
    """AC-13 GIVEN zwei verschiedene Nutzer loesen je einen Alarm aus
    WHEN beide protokolliert werden
    THEN landet jeder Eintrag ausschliesslich in der ``alert_log.json`` seines
    eigenen Nutzers — keine Kreuz-Kontamination."""
    from services.trip_alert import TripAlertService

    alice, bob = fresh_user("alice"), fresh_user("bob")
    for uid, trip_id in ((alice, "trip-alice"), (bob, "trip-bob")):
        mails: list = []
        gesendet = TripAlertService(
            settings=settings_email_only(), user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_and_send_alerts(
            gust_alert_trip(trip_id), [weather(1, gust_max_kmh=20.0)],
            fresh_weather=[weather(1, gust_max_kmh=60.0)],
        )
        assert gesendet is True, f"Voraussetzung: Alarm fuer {uid} muss rausgehen."

    for uid, eigen, fremd in ((alice, "trip-alice", "trip-bob"),
                              (bob, "trip-bob", "trip-alice")):
        log = read_log(uid)
        alle = log["entries"] + log["not_delivered"]
        touren = {e.get("trip_id") for e in alle}
        assert touren == {eigen}, (
            f"Das Protokoll von {uid} enthaelt {touren!r} statt nur {eigen!r} — "
            f"Fremd-Eintrag {fremd!r} waere ein Datenleck zwischen Nutzern."
        )
        assert all(e.get("reason") == "forecast_change" for e in alle), (
            f"Der Grund fehlt im Protokoll von {uid}: {alle!r}"
        )


# ───────────────────────────────── AC-14 ───────────────────────────────────

def test_ac14_alt_eintrag_ohne_neue_felder_bleibt_unveraendert_lesbar():
    """AC-14 GIVEN eine bestehende ``alert_log.json`` mit einem Alt-Eintrag,
    der nur die vier heutigen Felder traegt (und ohne ``not_delivered``-Key)
    WHEN ein neuer Eintrag angehaengt wird
    THEN bleibt der Alt-Eintrag Feld fuer Feld unveraendert (Read-Modify-Write,
    kein Replace) und ``entries`` enthaelt danach genau zwei Eintraege."""
    from services import alert_log

    uid = fresh_user("ac14")
    user_dir = get_data_dir(uid)
    user_dir.mkdir(parents=True, exist_ok=True)
    alt = {"trip_id": "trip-alt", "sent_at": "2026-07-01T08:00:00+00:00",
           "changes_count": 4, "severity": "MAJOR"}
    (user_dir / "alert_log.json").write_text(json.dumps({"entries": [dict(alt)]}))

    alert_log.append_entry(
        uid, trip_id="trip-neu", changes_count=1, severity="MODERATE",
        metrics=[("gust", "max")], reason="forecast_change",
        effective_channels={"email"}, sent_channels=["email"],
    )

    entries = json.loads((user_dir / "alert_log.json").read_text())["entries"]
    assert len(entries) == 2, (
        f"Erwartet Alt- UND Neu-Eintrag, erhalten {len(entries)}: {entries!r}"
    )
    assert entries[0] == alt, (
        f"Der Alt-Eintrag wurde veraendert: {entries[0]!r} statt {alt!r}"
    )
