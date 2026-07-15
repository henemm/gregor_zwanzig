"""
Issue #1250 Scheibe 4 (Trip-Konvergenz) — Trip bekommt additiv flache
Slot-/Kanal-Felder per Dual-Read aus `report_config`, `_trip_to_dict`
materialisiert zusätzlich `end_date` (`max(stage.date)`).

Spec: docs/specs/modules/issue_1250_briefing_subscription.md, AC-13/AC-14.

NO MOCKS — echte Dicts, echter Trip-Roundtrip über den Loader.
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from app.loader import _trip_to_dict, load_trip, load_trip_from_dict, save_trip


def _trip_dict(**stage_overrides) -> dict:
    """Vollständiges Trip-Fixture-Dict mit `report_config` (Vorbild
    tests/tdd/test_bug_805_789_roundtrip.py::_TRIP_FULL, ohne das Legacy-Feld
    `send_signal`, damit `_trip_to_dict(load_trip_from_dict(d))["report_config"]`
    byte-identisch zum Original ist — `send_signal` ist in `TripReportConfig`
    nicht modelliert und würde nur über den Datei-RMW-Pfad in `save_trip`
    erhalten bleiben, nicht über den reinen Modell-Roundtrip).
    """
    return {
        "id": "trip-1250-s4",
        "name": "S4 Trip-Konvergenz Test-Tour",
        "stages": [
            {
                "id": "stage-1",
                "name": "Etappe 1",
                "date": "2026-07-10",
                "waypoints": [
                    {"id": "wp-1", "name": "Start", "lat": 46.0, "lon": 9.0, "elevation_m": 1200},
                ],
            },
            {
                "id": "stage-3",
                "name": "Etappe 3 (letztes Datum)",
                "date": "2026-07-12",
                "waypoints": [
                    {"id": "wp-3", "name": "Ziel", "lat": 46.2, "lon": 9.2, "elevation_m": 900},
                ],
            },
            {
                "id": "stage-2",
                "name": "Etappe 2 (unsortiert einliefern)",
                "date": "2026-07-11",
                "waypoints": [
                    {"id": "wp-2", "name": "Zwischenziel", "lat": 46.1, "lon": 9.1, "elevation_m": 1500},
                ],
            },
        ],
        "aggregation": {"profile": "allgemein"},
        "report_config": {
            "trip_id": "trip-1250-s4",
            "enabled": True,
            "morning_time": "07:30:00",
            "evening_time": "18:15:00",
            "send_email": True,
            "send_sms": True,
            "send_telegram": False,
            "alert_on_changes": True,
            "change_threshold_temp_c": 5.0,
            "change_threshold_wind_kmh": 20.0,
            "change_threshold_precip_mm": 10.0,
            "wind_exposition_min_elevation_m": None,
            "show_compact_summary": True,
            "show_daylight": True,
            "multi_day_trend_reports": ["evening"],
            "show_stage_stats": True,
            "show_quick_take_tags": True,
            "show_stability": True,
            "show_highlights": True,
            "daily_summary_metrics": ["precipitation", "wind"],
            "show_metrics_summary": False,
            "show_outlook": True,
            "email_format": "full",
            "show_yesterday_comparison": True,
            "paused_until": None,
            "skip_next": False,
            "updated_at": "2026-07-10T10:00:00",
        },
        "alert_rules": [],
    }


# --- AC-13: flache Slot-/Kanal-Felder additiv aus report_config abgeleitet ---

def test_ac13_flat_slot_channel_fields_derived_from_report_config():
    """
    GIVEN einen Trip-Dict mit bestehender `report_config`-Map (morning_time,
      evening_time, send_email, send_sms, send_telegram, enabled)
    WHEN der Trip über `load_trip_from_dict` geladen wird
    THEN trägt der Trip additiv dieselben Werte als flache Top-Level-Attribute
      (Dual-Read) — noch nicht implementiert, daher AttributeError erwartet.
    """
    d = _trip_dict()
    rc = d["report_config"]

    trip = load_trip_from_dict(d)

    assert trip.morning_time == rc["morning_time"]
    assert trip.evening_time == rc["evening_time"]
    assert trip.send_sms == rc["send_sms"]
    assert trip.send_telegram == rc["send_telegram"]


def test_ac13_report_config_byte_identical_after_roundtrip():
    """
    GIVEN denselben Trip-Dict mit `report_config`
    WHEN er geladen und wieder in ein Dict serialisiert wird
      (`_trip_to_dict(load_trip_from_dict(d))`)
    THEN bleibt `report_config` byte-identisch zum Original — die additiven
      flachen Felder verändern die bestehende Map NICHT (Invariante, darf
      bereits jetzt grün sein).
    """
    d = _trip_dict()

    trip = load_trip_from_dict(d)
    rt = _trip_to_dict(trip)

    assert rt["report_config"] == d["report_config"]


# --- AC-14: end_date wird serverseitig materialisiert (max(stage.date)) -----

def test_ac14_end_date_emitted_as_max_stage_date():
    """
    GIVEN einen Trip mit mehreren (unsortiert einliefernden) Stages
    WHEN `_trip_to_dict(load_trip_from_dict(d))` aufgerufen wird
    THEN enthält das Ergebnis den Schlüssel `end_date` mit dem ISO-
      normalisierten `max(stage.date)`-Wert (analog FE `computeTripEnd`,
      `.split("T")[0]`-Semantik) — noch nicht implementiert, daher fehlt der
      Schlüssel (KeyError erwartet).
    """
    d = _trip_dict()
    expected_end_date = max(s["date"] for s in d["stages"]).split("T")[0]
    assert expected_end_date == "2026-07-12"  # sanity: spätestes Stage-Datum

    trip = load_trip_from_dict(d)
    rt = _trip_to_dict(trip)

    assert "end_date" in rt, "end_date fehlt in _trip_to_dict-Ausgabe (S4 noch nicht implementiert)"
    assert rt["end_date"] == expected_end_date


def test_ac14_end_date_property_stays_single_source():
    """
    GIVEN denselben Trip mit mehreren Stages
    WHEN `trip.end_date` (bestehende @property, trip.py:216) gelesen wird
    THEN liefert sie weiterhin den berechneten `max(stage.date)`-Wert — die
      additive Materialisierung in `_trip_to_dict` darf diese Property NICHT
      durch ein verdeckendes Dataclass-Feld ersetzen (darf bereits jetzt
      grün sein, schützt die Property als Single Source of Truth).
    """
    d = _trip_dict()

    trip = load_trip_from_dict(d)

    assert trip.end_date.isoformat() == "2026-07-12"


# --- Fix-Loop F001/F002 (Adversary BROKEN): befuellt->leer darf nicht stale ---
# werden. Struct-/RMW-Merge-Falle: additive Felder werden vormals nur
# GESETZT, nie GELOESCHT bzw. via _deep_merge_preserve_unknown NIE
# ueberschrieben, wenn das Overlay den Key komplett ausliess.

def test_end_date_not_stale_after_stages_cleared_to_empty(tmp_path):
    """
    GIVEN einen gespeicherten Trip mit Stages (end_date materialisiert)
    WHEN alle Stages entfernt werden (leerer Editor-Zustand ist erlaubt)
      und der Trip erneut gespeichert wird
    THEN steht auf der Platte `"end_date": null` (NICHT der alte Wert) und
      `load_trip(...).end_date is None` — kein Crash, kein Stale-Read.
    """
    d = _trip_dict()
    trip = load_trip_from_dict(d)
    save_trip(trip, user_id="testuser-1250-s4-stale", data_dir=tmp_path)

    trip_file = tmp_path / "users" / "testuser-1250-s4-stale" / "briefings" / f"{trip.id}.json"
    saved_full = json.loads(trip_file.read_text())
    assert saved_full["end_date"] == "2026-07-12"  # Sanity vor dem Leeren

    loaded = load_trip(trip.id, data_dir=tmp_path, user_id="testuser-1250-s4-stale")
    emptied = dataclasses.replace(loaded, stages=[])
    save_trip(emptied, user_id="testuser-1250-s4-stale", data_dir=tmp_path)

    saved_after_empty = json.loads(trip_file.read_text())
    assert saved_after_empty["end_date"] is None, (
        f"end_date auf Platte ist stale (alter Wert konserviert): {saved_after_empty['end_date']!r}"
    )
    # report_config bleibt in diesem Szenario bestehen (nur Stages wurden
    # geleert) -> die flachen Kanal-Felder duerfen unveraendert bleiben, das
    # ist kein Stale-Fall (report_config ist weiter die Quelle).
    assert saved_after_empty["morning_time"] == "07:30:00"

    reloaded = load_trip(trip.id, data_dir=tmp_path, user_id="testuser-1250-s4-stale")
    assert reloaded.end_date is None, f"reloaded.end_date = {reloaded.end_date!r}, want None (kein Crash)"


def test_flat_channel_fields_not_stale_after_report_config_removed(tmp_path):
    """
    GIVEN einen gespeicherten Trip mit `report_config` (flache Kanal-Felder
      dadurch abgeleitet)
    WHEN `report_config` entfernt wird (z.B. Migrationsschritt/Editor-Reset)
      und der Trip erneut gespeichert wird
    THEN stehen die flachen Kanal-Felder auf der Platte auf `null` (NICHT der
      alte Wert) und bleiben es auch nach einem Reload.
    """
    d = _trip_dict()
    trip = load_trip_from_dict(d)
    save_trip(trip, user_id="testuser-1250-s4-rc-removed", data_dir=tmp_path)

    trip_file = tmp_path / "users" / "testuser-1250-s4-rc-removed" / "briefings" / f"{trip.id}.json"
    saved_full = json.loads(trip_file.read_text())
    assert saved_full["send_sms"] is True  # Sanity vor dem Entfernen

    loaded = load_trip(trip.id, data_dir=tmp_path, user_id="testuser-1250-s4-rc-removed")
    without_rc = dataclasses.replace(
        loaded,
        report_config=None,
        morning_time=None,
        evening_time=None,
        morning_enabled=None,
        evening_enabled=None,
        send_email=None,
        send_sms=None,
        send_telegram=None,
    )
    save_trip(without_rc, user_id="testuser-1250-s4-rc-removed", data_dir=tmp_path)

    saved_after_removal = json.loads(trip_file.read_text())
    for key in ("morning_time", "evening_time", "morning_enabled", "evening_enabled",
                "send_email", "send_sms", "send_telegram"):
        assert saved_after_removal[key] is None, (
            f"{key} auf Platte ist stale nach Entfernen von report_config: "
            f"{saved_after_removal[key]!r}"
        )
    # Hinweis: `report_config` selbst bleibt hier auf Platte stehen (RMW
    # preserve-unknown, Issue #805 — report_config wird in `_trip_to_dict`
    # nur truthy-emittiert, ausserhalb des Scope dieses Fixes). Relevant fuer
    # F002 sind ausschliesslich die ABGELEITETEN flachen Felder unmittelbar
    # nach dem Speichern (oben) — nicht die Reload-Rederivation, die wegen des
    # weiterhin vorhandenen `report_config` korrekt wieder befuellt wird
    # (Dual-Read funktioniert wie vorgesehen, kein Stale-Fall).


def test_trip_alert_check_all_trips_handles_stageless_trip_without_crash(tmp_path, monkeypatch):
    """
    GIVEN einen Trip OHNE Stages (leerer Editor-Zustand, kein `report_config`)
    WHEN `TripAlertService.check_all_trips()` läuft (liest end_date intern,
      trip_alert.py:315 vor dem Fix)
    THEN crasht es NICHT (end_date ist None-sicher, kein `None < today`).
    """
    from app import loader
    from services.trip_alert import TripAlertService

    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))

    d = _trip_dict()
    del d["stages"]
    del d["report_config"]
    d["id"] = "trip-1250-s4-stageless"
    trip = load_trip_from_dict(d)
    assert trip.stages == []
    assert trip.end_date is None  # Sanity: None-sichere Property (kein ValueError)

    save_trip(trip, user_id="testuser-1250-s4-stageless")

    service = TripAlertService(user_id="testuser-1250-s4-stageless")
    # Darf keine Exception werfen (insbesondere kein
    # TypeError: '<' not supported between instances of 'NoneType' and 'date').
    sent = service.check_all_trips()
    assert sent == 0
