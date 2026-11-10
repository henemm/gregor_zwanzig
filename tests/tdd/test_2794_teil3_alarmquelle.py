"""TDD RED — AC-29: „Alarm ab" in der Ampel macht ein Abo alarmfaehig.

SPEC: docs/specs/modules/feat_2794_s3a_teil3_wetter.md (AC-29, Implementation
Details §3). Ein Trip ohne Altstufen (``metric_alert_levels``), ohne
Alarm-Preset, ohne Regeln und ohne Wetteraenderungs-Alarme
(``report_config.alert_on_changes=False``), aber mit einer AKTIVEN Metrik mit
``alarm_ab`` != ``never`` in der aufgeloesten Ampel, muss alarmieren, wenn der
Wert von gruen auf die Alarmfarbe springt. Ohne eine solche Metrik (oder wenn
sie nicht aktiv ist) bleibt es stumm.

Beide Gate-Bloecke von ``src/services/trip_alert.py`` werden ueber ihre ECHTEN
Einstiege getroffen:
- Block 1: ``TripAlertService.check_and_send_alerts`` (``has_active_rules`` +
  ``alert_on_changes``-Abbruch).
- Block 2: ``TripAlertService.check_all_trips`` (Vorab-Filter ``continue``) —
  mit ausgeschaltetem amtlichen Trigger, sonst liesse der Vorab-Filter den
  Trip wegen der amtlichen Warnungen ohnehin durch und Block 2 waere nicht
  beobachtbar.

Dazu der Vergleichs-Einstieg ``CompareAlertService.check_all_compare_presets``
(laut Spec ohne Code-Aenderung; hier abgesichert, inkl. dass
``_display_config_from_active_metrics`` die Ampel-Metrik nicht wegfiltert).

Beobachtet wird der Versand (``mail_sink``) — aus Nutzersicht. Kein
``Mock()``/``patch()``/``MagicMock``. Wetter kommt ueber die bestehenden
DI-Naehte: direkt uebergebene Segmente (Block 1), ein echter Briefing-Anker
plus eine netzfreie Implementierung der Abruf-Naht ``SegmentWeatherService``
(Haus-Muster aus ``test_alert_channel_anchor_shared_comparison.py``, Block 2),
``weather_source`` (Vergleich). Muster der Trip-/Vergleichs-Laeufe aus
``test_alarm_folgt_ampel_stufenwechsel.py`` (#2793 S2b).

Damit genau EINE Metrik ueber die Alarmfaehigkeit entscheidet, setzt die
Abo-Ampel alle uebrigen aktiven Vorlagen-Metriken mit „Alarm ab" auf
``never`` (die Vorlage „allgemein" hat sonst Temperatur, Wind, Niederschlag
und Gewitter mit „Alarm ab Orange" aktiv).

Erwartetes RED-Bild heute: die beiden Positiv-Faelle des Trips (Block 1 und
Block 2) sind rot, weil das Gate ``alarm_ab`` nicht als Alarmquelle kennt.
Alle Gegenfaelle und der Vergleich sind gruen.
"""
from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import date, datetime, timezone

import pytest

from app.ampel_templates import AMPEL_TEMPLATES
from app.loader import get_data_dir, save_location, save_trip
from app.models import (
    MetricConfig,
    SegmentWeatherSummary,
    TripReportConfig,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import (
    LAT,
    LON,
    clean_compare_user,
    compare_data_root,
    settings_email_only,
    weather,
)
from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
from tests.helpers.compare_briefings import write_compare_briefings
from tests.helpers.ortstag import ortstag

VORLAGE = "allgemein"
# Vorlage „allgemein": Boeen oben gelb 30 / orange 45 / rot 60.
GRUEN = {"gust_max_kmh": 20.0}
ALARMFARBE = {"gust_max_kmh": 50.0}  # orange


def _uid(tag: str) -> str:
    return f"tdd-2794t3-{tag}-{uuid.uuid4().hex[:6]}"


def _premium(uid: str) -> None:
    profil = get_data_dir(uid) / "user.json"
    profil.parent.mkdir(parents=True, exist_ok=True)
    profil.write_text(json.dumps({"tier": "premium"}))


def _ampel(*, boeen: dict) -> dict:
    """Abo-Ampel: alle anderen aktiven Vorlagen-Metriken mit „Alarm ab" auf
    ``never``; ``boeen`` legt die Boeen-Zeile fest."""
    metrics = {
        mid: {"alarm_ab": "never"}
        for mid, e in AMPEL_TEMPLATES[VORLAGE]["metrics"].items()
        if e["enabled"] and e["alarm_ab"] != "never" and mid != "gust"
    }
    metrics["gust"] = boeen
    return {"template": VORLAGE, "metrics": metrics}


MIT_ALARM_AB = {"alarm_ab": "orange"}
OHNE_ALARM_AB = {"alarm_ab": "never"}
NICHT_AKTIV = {"enabled": False, "alarm_ab": "orange"}


def _vorbedingung_ampel(ampel: dict, *, alarmfaehig: bool) -> None:
    """Fixtur-Schutz: die aufgeloeste Ampel hat genau dann eine aktive Metrik
    mit „Alarm ab" != never, wenn der Fall das behauptet."""
    from app.ampel import resolve_ampel

    aufgeloest = resolve_ampel({"display_config": {"ampel": ampel}})
    aktiv_mit_alarm = [
        mid for mid, e in aufgeloest["metrics"].items()
        if e.get("enabled") and e.get("alarm_ab") not in (None, "never")
    ]
    assert bool(aktiv_mit_alarm) is alarmfaehig, aktiv_mit_alarm


# ───────────────────────────── Trip-Bausteine ────────────────────────────────

def _trip(trip_id: str, boeen: dict) -> Trip:
    """Trip OHNE Altstufen, OHNE Alarm-Preset, OHNE Regeln, OHNE
    Wetteraenderungs-Alarme — einzige Alarmquelle ist die Ampel."""
    ampel = _ampel(boeen=boeen)
    stage = Stage(
        id="T1", name="Tag 1", date=ortstag(LAT, LON),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(
        id=trip_id, name=f"Ampel-Quelle {trip_id}", stages=[stage],
        official_warnings=None, corridors=[],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            # Auswahl (metrics[]) und Ampel-enabled konsistent (AC-37).
            metrics=[MetricConfig(metric_id="gust", enabled=boeen.get("enabled", True))],
            metric_alert_levels=None,
            alert_preset=None,
            ampel=ampel,
        ),
    )
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=False,
        morning_time=morgen, evening_time=abend,
    )
    trip.alert_rules = []
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    # Fixtur-Schutz: keine der Alt-Quellen ist gesetzt.
    assert not trip.display_config.metric_alert_levels
    assert not trip.display_config.alert_preset
    assert not any(r.enabled for r in (trip.alert_rules or []))
    assert trip.report_config.alert_on_changes is False
    return trip


def _block1_lauf(uid: str, trip: Trip) -> list[str]:
    """Block 1: ``check_and_send_alerts`` mit Anker gruen, Prognose orange."""
    from services.trip_alert import TripAlertService

    _premium(uid)
    mails: list[str] = []
    TripAlertService(
        settings=settings_email_only(), user_id=uid, throttle_hours=0,
        mail_sink=lambda subject, body, **_kw: mails.append(subject),
    ).check_and_send_alerts(trip, [weather(1, **GRUEN)], fresh_weather=[weather(1, **ALARMFARBE)])
    return mails


def _ortstag_des_trips(trip: Trip) -> date:
    from services.trip_day import trip_local_today

    return trip_local_today(trip, datetime.now(timezone.utc))


def _block2_lauf(uid: str, trip: Trip, monkeypatch) -> tuple[object, list[str]]:
    """Block 2: regulaerer Scheduler-Lauf ``check_all_trips`` — Trip auf
    Platte, taggleicher Briefing-Anker (gruen), frische Prognose (orange)
    ueber eine netzfreie Implementierung der Abruf-Naht."""
    import services.segment_weather as sw_mod
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    _premium(uid)
    save_trip(trip, user_id=uid)
    WeatherSnapshotService(user_id=uid).save(
        trip.id, [weather(1, **GRUEN)], _ortstag_des_trips(trip),
    )

    class _FesteWetterquelle:
        """Echte, netzfreie Implementierung der Abruf-Naht von
        ``_fetch_fresh_weather()`` (kein Mock des Prueflings)."""

        def __init__(self, provider=None) -> None:
            self._provider = provider

        def fetch_segment_weather(self, segment, **kwargs):
            return dataclasses.replace(weather(1, **ALARMFARBE), segment=segment)

    monkeypatch.setattr(sw_mod, "SegmentWeatherService", _FesteWetterquelle)

    mails: list[str] = []
    ergebnis = TripAlertService(
        settings=settings_email_only(), user_id=uid,
        mail_sink=lambda subject, body, **_kw: mails.append(subject),
    ).check_all_trips()
    return ergebnis, mails


# ═══════════════════════ Trip — Block 1 (check_and_send_alerts) ══════════════

def test_ac29_trip_block1_alarm_ab_aktiv_alarmiert():
    """AC-29 GIVEN Trip ohne Altstufen/Preset/Regeln/Wetteraenderungs-Alarme,
    Boeen aktiv mit „Alarm ab Orange" / WHEN Boeen 20 (gruen) -> 50 (orange) /
    THEN geht der Alarm raus.

    RED heute: ``has_active_rules`` kennt ``alarm_ab`` nicht, und
    ``alert_on_changes=False`` bricht vor dem Abruf ab."""
    uid = _uid("b1-an")
    trip = _trip("trip-b1-an", MIT_ALARM_AB)
    _vorbedingung_ampel(trip.display_config.ampel, alarmfaehig=True)
    mails = _block1_lauf(uid, trip)
    assert mails, (
        "AC-29 (Block 1): eine aktive Metrik mit „Alarm ab Orange“ in der "
        "aufgeloesten Ampel macht den Trip alarmfaehig — der Sprung gruen -> "
        "orange muss alarmieren. Heute bricht check_and_send_alerts am "
        "Gate (has_active_rules/alert_on_changes) still ab."
    )


@pytest.mark.parametrize("boeen, tag", [(OHNE_ALARM_AB, "ohne"), (NICHT_AKTIV, "inaktiv")])
def test_ac29_trip_block1_gegenfaelle_bleiben_stumm(boeen, tag):
    """AC-29 Gegenfaelle: ohne aktive Metrik mit „Alarm ab" != never (alle
    „Nie" bzw. Boeen mit „Alarm ab Orange", aber nicht aktiv) bleibt es
    stumm — auch nach dem Fix."""
    uid = _uid(f"b1-{tag}")
    trip = _trip(f"trip-b1-{tag}", boeen)
    _vorbedingung_ampel(trip.display_config.ampel, alarmfaehig=False)
    assert _block1_lauf(uid, trip) == []


# ═══════════════════════ Trip — Block 2 (check_all_trips) ════════════════════

def test_ac29_trip_block2_alarm_ab_aktiv_alarmiert(monkeypatch):
    """AC-29 Block 2: derselbe Trip im regulaeren Scheduler-Lauf. Der
    amtliche Trigger ist aus, damit der Vorab-Filter selbst entscheidet.

    RED heute: der Vorab-Filter in ``check_all_trips`` ueberspringt den Trip
    per ``continue`` (keine aktive Quelle laut Gate) — kein Abruf, kein Alarm."""
    uid = _uid("b2-an")
    trip = _trip("trip-b2-an", MIT_ALARM_AB)
    _vorbedingung_ampel(trip.display_config.ampel, alarmfaehig=True)
    ergebnis, mails = _block2_lauf(uid, trip, monkeypatch)
    assert ergebnis.alerts_sent == 1 and mails, (
        "AC-29 (Block 2): check_all_trips muss den Trip mit aktiver "
        "„Alarm ab“-Metrik pruefen und alarmieren. Erhalten: alerts_sent="
        f"{ergebnis.alerts_sent}, Mails={mails!r} — heute ueberspringt der "
        "Vorab-Filter den Trip."
    )


@pytest.mark.parametrize("boeen, tag", [(OHNE_ALARM_AB, "ohne"), (NICHT_AKTIV, "inaktiv")])
def test_ac29_trip_block2_gegenfaelle_bleiben_stumm(boeen, tag, monkeypatch):
    uid = _uid(f"b2-{tag}")
    trip = _trip(f"trip-b2-{tag}", boeen)
    _vorbedingung_ampel(trip.display_config.ampel, alarmfaehig=False)
    ergebnis, mails = _block2_lauf(uid, trip, monkeypatch)
    assert ergebnis.alerts_sent == 0 and mails == [], (ergebnis, mails)


def test_ac29_trip_bestandsquelle_alert_on_changes_alarmiert_weiter(monkeypatch):
    """Kontrolle (bestehende Gate-Faelle unveraendert): derselbe Aufbau mit
    ``alert_on_changes=True`` alarmiert schon heute ueber beide Bloecke —
    beweist, dass der Testaufbau (Anker, Abruf, Versand) traegt und das Rot
    oben allein am Gate liegt."""
    uid = _uid("kontrolle")
    trip = _trip("trip-kontrolle", MIT_ALARM_AB)
    trip.report_config.alert_on_changes = True
    ergebnis, mails = _block2_lauf(uid, trip, monkeypatch)
    assert ergebnis.alerts_sent == 1 and mails, (ergebnis, mails)


# ═══════════════════════════ Vergleich (compare_alert) ═══════════════════════

_PRESET = "cp-2794t3"


class _Quelle:
    """Deterministische ``LocationWeatherSource`` (DI-Naht, kein Mock)."""

    def __init__(self, **summary) -> None:
        self._summary = summary

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
              elevation_m=None, user_id=None, target_date=None):
        from services.point_weather import PointWeatherData

        return PointWeatherData(
            id=point_id, name="Vergleichsort", lat=lat, lon=lon, timeseries=None,
            aggregated=SegmentWeatherSummary(**self._summary),
            fetched_at=datetime.now(timezone.utc), provider="tdd-2794t3",
        )


def _vergleich_preset(uid: str, boeen: dict) -> dict:
    """Orts-Briefing ohne Altstufen, ohne Alarm-Preset, ohne Regeln; Auswahl
    (``active_metrics``) konsistent zur Ampel."""
    active = ["gust_max_kmh"] if boeen.get("enabled", True) else []
    return {
        "id": _PRESET, "name": "Vergleich 2794 T3", "user_id": uid,
        "location_ids": ["loc-a"], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["dummy@example.com"], "created_at": "2026-08-01T00:00:00Z",
        "alert_cooldown_minutes": 0,
        "display_config": {"active_metrics": active, "ampel": _ampel(boeen=boeen)},
    }


def _vergleich_lauf(uid: str, boeen: dict) -> list[str]:
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    clean_compare_user(uid)
    save_location(
        SavedLocation(id="loc-a", name="Vergleichsort", lat=LAT, lon=LON, elevation_m=1000),
        user_id=uid,
    )
    write_compare_briefings(compare_data_root() / uid, [_vergleich_preset(uid, boeen)])
    _premium(uid)
    CompareWeatherSnapshotService(user_id=uid).save(
        _PRESET, "loc-a", _Quelle(**GRUEN).fetch("loc-a", LAT, LON),
    )
    mails: list[str] = []
    CompareAlertService(
        settings=settings_email_only(), user_id=uid, weather_source=_Quelle(**ALARMFARBE),
        mail_sink=lambda subject, body, **_kw: mails.append(subject),
    ).check_all_compare_presets()
    return mails


def test_ac29_vergleich_alarm_ab_aktiv_alarmiert():
    """AC-29 Vergleich: Orts-Briefing mit Boeen aktiv, „Alarm ab Orange",
    sonst keine Alarmquelle / WHEN 20 -> 50 / THEN Alarm."""
    uid = _uid("cmp-an")
    try:
        assert _vergleich_lauf(uid, MIT_ALARM_AB), (
            "AC-29 (Vergleich): die aktive Ampel-Metrik mit „Alarm ab“ muss "
            "alarmieren."
        )
    finally:
        clean_compare_user(uid)


@pytest.mark.parametrize("boeen, tag", [(OHNE_ALARM_AB, "ohne"), (NICHT_AKTIV, "inaktiv")])
def test_ac29_vergleich_gegenfaelle_bleiben_stumm(boeen, tag):
    uid = _uid(f"cmp-{tag}")
    try:
        assert _vergleich_lauf(uid, boeen) == []
    finally:
        clean_compare_user(uid)


def test_ac29_vergleich_auswahl_filtert_ampel_metrik_nicht_weg():
    """``_display_config_from_active_metrics`` laesst die gewaehlte
    Ampel-Metrik aktiv (Katalog-ID ``gust`` enabled) — sonst waere der
    Vergleichs-Alarm oben ein Zufallstreffer."""
    from services.compare_alert import CompareAlertService

    uid = _uid("cmp-filter")
    svc = CompareAlertService(settings=settings_email_only(), user_id=uid)
    dc = svc._display_config_from_active_metrics(_vergleich_preset(uid, MIT_ALARM_AB))
    assert dc is not None
    aktiv = {m.metric_id for m in dc.metrics if m.enabled}
    assert "gust" in aktiv, aktiv
    dc_aus = svc._display_config_from_active_metrics(_vergleich_preset(uid, NICHT_AKTIV))
    assert "gust" not in {m.metric_id for m in dc_aus.metrics if m.enabled}


# ═══════════ Präzisierung Phase 5 (Spec §3): nur Abos MIT ampel-Schlüssel ════
# Der Gate-Helfer greift nur, wenn das Abo ``display_config.ampel`` traegt;
# dann zaehlt die aufgeloeste Ampel INKLUSIVE Vorlagen-Vorgaben. Abos ohne
# ampel-Schluessel bleiben im Gate wie bisher (stumm bei alert_on_changes=False).

def _trip_nur_vorlage(trip_id: str, *, mit_ampel: bool) -> Trip:
    """Trip ohne Altstufen/Preset/Regeln/Wetteraenderungs-Alarme; Boeen in
    ``metrics[]`` aktiv (Vorlage „allgemein“: Boeen aktiv, „Alarm ab Orange“).
    ``mit_ampel``: ``{"template": "allgemein"}`` ohne Abweichungen, sonst gar
    kein ampel-Schluessel."""
    trip = _trip(trip_id, MIT_ALARM_AB)
    trip.display_config.ampel = {"template": VORLAGE} if mit_ampel else None
    vorlage = AMPEL_TEMPLATES[VORLAGE]["metrics"]["gust"]
    assert vorlage["enabled"] and vorlage["alarm_ab"] == "orange", vorlage
    return trip


def test_ac29_trip_block1_nur_vorlagen_ampel_alarmiert():
    """(a) Block 1: ampel = {"template": "allgemein"} ohne Abweichungen /
    Boeen 20 -> 50 / Alarm. RED heute: Gate kennt die Ampel nicht."""
    uid = _uid("b1-vorlage")
    mails = _block1_lauf(uid, _trip_nur_vorlage("trip-b1-vorlage", mit_ampel=True))
    assert mails, (
        "AC-29 (Block 1, Präzisierung §3): ein Abo mit ampel-Schluessel zaehlt "
        "die Vorlagen-Vorgaben (Boeen „Alarm ab Orange“) — muss alarmieren."
    )


def test_ac29_trip_block1_ohne_ampel_schluessel_bleibt_stumm():
    """(b) Block 1 Waechter: derselbe Trip ohne ampel-Schluessel bleibt stumm."""
    uid = _uid("b1-ohne-ampel")
    assert _block1_lauf(uid, _trip_nur_vorlage("trip-b1-oa", mit_ampel=False)) == []


def test_ac29_trip_block2_nur_vorlagen_ampel_alarmiert(monkeypatch):
    """(a) Block 2: derselbe Fall im Scheduler-Lauf ``check_all_trips``.
    RED heute: der Vorab-Filter ueberspringt den Trip."""
    uid = _uid("b2-vorlage")
    trip = _trip_nur_vorlage("trip-b2-vorlage", mit_ampel=True)
    ergebnis, mails = _block2_lauf(uid, trip, monkeypatch)
    assert ergebnis.alerts_sent == 1 and mails, (
        "AC-29 (Block 2, Präzisierung §3): Abo mit ampel-Schluessel muss im "
        f"Scheduler-Lauf alarmieren. Erhalten: alerts_sent={ergebnis.alerts_sent}, "
        f"Mails={mails!r}"
    )


def test_ac29_trip_block2_ohne_ampel_schluessel_bleibt_stumm(monkeypatch):
    """(b) Block 2 Waechter: ohne ampel-Schluessel bleibt es wie bisher stumm."""
    uid = _uid("b2-ohne-ampel")
    trip = _trip_nur_vorlage("trip-b2-oa", mit_ampel=False)
    ergebnis, mails = _block2_lauf(uid, trip, monkeypatch)
    assert ergebnis.alerts_sent == 0 and mails == [], (ergebnis, mails)
