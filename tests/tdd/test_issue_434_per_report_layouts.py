"""TDD RED — Issue #434: Per-Report-Layout-Overrides (Abend ≠ Morgen).

SPEC: docs/specs/modules/issue_434_per_report_layouts.md (AC-1..AC-7).

Testet die NOCH NICHT existierende API:
  - src/app/models.py: UnifiedWeatherDisplayConfig.per_report_layouts (neues Feld)
  - src/app/models.py: get_metrics_for_channel() mit dreistufiger Kaskade (#434 > #429 > global)
  - src/app/loader.py: _parse_display_config liest channel_layouts_per_report-Zweig
  - src/app/loader.py: _trip_to_dict schreibt per_channel_layouts + per_report_layouts zurück
  - src/formatters/trip_report.py: Zeile 73 nutzt get_metrics_for_channel("email", ...) statt get_metrics_for_report_type

Alle Tests MÜSSEN in der RED-Phase scheitern:
  AC-1, AC-3, AC-5: AttributeError (per_report_layouts nicht vorhanden)
  AC-4: AttributeError (per_report_layouts nicht vorhanden)
  AC-2: AttributeError (per_report_layouts nicht vorhanden)
  AC-6: AssertionError (per_channel_layouts + per_report_layouts werden nicht serialisiert)
  AC-7: AssertionError (trip_report.py ruft get_metrics_for_report_type, nicht get_metrics_for_channel)

KEINE Mocks — reine Datenstrukturen + echte Aufrufe.
"""

from __future__ import annotations

import inspect
from typing import Any


# ---------------------------------------------------------------------------
# Test-Fixtures
# ---------------------------------------------------------------------------


def _legacy_trip_data() -> dict[str, Any]:
    """Alter Trip ohne channel_layouts_per_report (backward-compat)."""
    return {
        "trip_id": "legacy-trip-434",
        "metrics": [
            {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
            {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
            {"metric_id": "rain_probability", "enabled": True, "bucket": "secondary", "order": 0},
        ],
        "updated_at": "2026-05-29T10:00:00",
    }


def _per_report_trip_data() -> dict[str, Any]:
    """Trip MIT channel_layouts_per_report — Morning und Evening haben verschiedene Email-Listen."""
    return {
        "trip_id": "per-report-trip-434",
        "metrics": [
            # Globale Fallback-Liste
            {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
            {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
        ],
        "channel_layouts": {
            # Per-Kanal-Fallback (#429)
            "email": [
                {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
                {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
                {"metric_id": "gust", "enabled": True, "bucket": "secondary", "order": 0},
            ],
        },
        "channel_layouts_per_report": {
            "morning": {
                "email": [
                    # Morgen-spezifisch: nur Temperatur + Regen
                    {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
                    {"metric_id": "precipitation", "enabled": True, "bucket": "primary", "order": 1},
                ]
            },
            "evening": {
                "email": [
                    # Abend-spezifisch: Wind-fokussiert
                    {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 0},
                    {"metric_id": "gust", "enabled": True, "bucket": "primary", "order": 1},
                    {"metric_id": "wind_chill", "enabled": True, "bucket": "secondary", "order": 0},
                ]
            },
        },
        "updated_at": "2026-05-29T10:00:00",
    }


def _per_report_empty_evening_data() -> dict[str, Any]:
    """Trip mit explizit leerer per_report_layouts["evening"]["email"]-Liste."""
    return {
        "trip_id": "empty-per-report-trip",
        "metrics": [
            {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
        ],
        "channel_layouts": {
            "email": [
                {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
            ],
        },
        "channel_layouts_per_report": {
            "evening": {
                "email": [],  # explizit leer — kein Fallback
            },
        },
        "updated_at": "2026-05-29T10:00:00",
    }


def _parse(data: dict[str, Any]):
    """Convenience: parse display-config-dict to UnifiedWeatherDisplayConfig."""
    from app.loader import _parse_display_config
    return _parse_display_config(data)


# ---------------------------------------------------------------------------
# AC-1: Loader liest channel_layouts_per_report und befüllt per_report_layouts
# ---------------------------------------------------------------------------


def test_ac1_loader_reads_channel_layouts_per_report():
    """AC-1: Trip-JSON mit channel_layouts_per_report → per_report_layouts korrekt befüllt."""
    dc = _parse(_per_report_trip_data())

    # NEUE API — existiert in der RED-Phase noch nicht.
    assert hasattr(dc, "per_report_layouts"), (
        "UnifiedWeatherDisplayConfig braucht ein per_report_layouts-Feld (Issue #434)."
    )
    assert dc.per_report_layouts is not None

    assert "morning" in dc.per_report_layouts
    assert "email" in dc.per_report_layouts["morning"]
    morning_email = dc.per_report_layouts["morning"]["email"]
    assert len(morning_email) == 2
    assert morning_email[0].metric_id == "temperature"
    assert morning_email[1].metric_id == "precipitation"

    assert "evening" in dc.per_report_layouts
    assert "email" in dc.per_report_layouts["evening"]
    evening_email = dc.per_report_layouts["evening"]["email"]
    assert len(evening_email) == 3
    assert evening_email[0].metric_id == "wind"
    assert evening_email[1].metric_id == "gust"
    assert evening_email[2].metric_id == "wind_chill"


# ---------------------------------------------------------------------------
# AC-2: Backward-Compat — Trip ohne channel_layouts_per_report → per_report_layouts ist None
# ---------------------------------------------------------------------------


def test_ac2_legacy_trip_has_no_per_report_layouts():
    """AC-2: Alter Trip → per_report_layouts is None, Fallback-Verhalten bleibt unverändert."""
    dc = _parse(_legacy_trip_data())

    assert hasattr(dc, "per_report_layouts"), (
        "UnifiedWeatherDisplayConfig braucht per_report_layouts (auch wenn None)."
    )
    assert dc.per_report_layouts is None

    # Verhalten: get_metrics_for_channel muss auf globale Liste zurückfallen
    via_channel = dc.get_metrics_for_channel("email", "evening")
    via_report = dc.get_metrics_for_report_type("evening")
    assert [m.metric_id for m in via_channel] == [m.metric_id for m in via_report], (
        "Ohne per_report_layouts muss get_metrics_for_channel('email', 'evening') "
        "dasselbe liefern wie get_metrics_for_report_type('evening')."
    )


# ---------------------------------------------------------------------------
# AC-3: per_report schlägt per_channel (Prioritätskaskade)
# ---------------------------------------------------------------------------


def test_ac3_per_report_wins_over_per_channel():
    """AC-3: per_report_layouts["morning"]["email"] schlägt per_channel_layouts["email"]."""
    dc = _parse(_per_report_trip_data())

    morning_metrics = dc.get_metrics_for_channel("email", "morning")
    ids = [m.metric_id for m in morning_metrics]

    # Morgen-Override: nur temperature + precipitation (nicht das per_channel email-Layout)
    assert ids == ["temperature", "precipitation"], (
        f"Morgen-Override sollte [temperature, precipitation] liefern, "
        f"nicht das per_channel-Layout [temperature, wind, gust]. Erhalten: {ids}"
    )

    evening_metrics = dc.get_metrics_for_channel("email", "evening")
    evening_ids = [m.metric_id for m in evening_metrics]

    # Abend-Override: wind + gust + wind_chill (nicht das per_channel email-Layout)
    assert "wind" in evening_ids and "gust" in evening_ids and "wind_chill" in evening_ids, (
        f"Abend-Override sollte [wind, gust, wind_chill] liefern. Erhalten: {evening_ids}"
    )
    assert "temperature" not in evening_ids, (
        "Das per_channel email-Layout enthält temperature, aber der Abend-Override nicht — "
        f"per_report muss gewinnen. Erhalten: {evening_ids}"
    )


# ---------------------------------------------------------------------------
# AC-4: Kein per_report-Eintrag → Fallback auf per_channel oder global
# ---------------------------------------------------------------------------


def test_ac4_no_per_report_falls_back_to_per_channel():
    """AC-4: per_report_layouts["morning"]["telegram"] fehlt → Fallback auf global."""
    dc = _parse(_per_report_trip_data())

    # Telegram: per_report_layouts hat keinen telegram-Eintrag
    # per_channel_layouts hat auch keinen telegram-Eintrag → Fallback auf global
    telegram_morning = dc.get_metrics_for_channel("telegram", "morning")
    global_morning = dc.get_metrics_for_report_type("morning")

    assert [m.metric_id for m in telegram_morning] == [m.metric_id for m in global_morning], (
        "Ohne per_report_layouts für Telegram muss auf globale Liste zurückgefallen werden."
    )


# ---------------------------------------------------------------------------
# AC-5: Explizit leere per_report_layouts → kein Fallback
# ---------------------------------------------------------------------------


def test_ac5_empty_per_report_no_fallback():
    """AC-5: per_report_layouts["evening"]["email"] == [] → leere Liste, kein Fallback."""
    dc = _parse(_per_report_empty_evening_data())

    evening_metrics = dc.get_metrics_for_channel("email", "evening")
    assert evening_metrics == [], (
        "Explizit leere per_report_layouts-Liste darf nicht auf per_channel oder global "
        f"zurückfallen. Erhalten: {[m.metric_id for m in evening_metrics]}"
    )


# ---------------------------------------------------------------------------
# AC-6: Roundtrip — per_channel_layouts + per_report_layouts werden serialisiert
# ---------------------------------------------------------------------------


def test_ac6_roundtrip_per_channel_and_per_report_layouts():
    """AC-6: Laden → Trip bauen → _trip_to_dict → _parse → per_report_layouts identisch."""
    from datetime import date
    from app.loader import _parse_display_config, _trip_to_dict
    from app.trip import Trip, Stage, Waypoint, AggregationConfig
    from app.profile import ActivityProfile

    # Trip-Objekt mit per_report_layouts aufbauen
    dc = _parse_display_config(_per_report_trip_data())

    agg = AggregationConfig.for_profile(ActivityProfile.SUMMER_TREKKING)
    stage = Stage(
        id="s1", name="Etappe 1",
        date=date(2026, 7, 1),
        waypoints=[Waypoint(id="w1", name="Start", lat=42.0, lon=9.0, elevation_m=100)],
    )
    trip = Trip(
        id="test-434-roundtrip",
        name="Test Trip #434",
        stages=[stage],
        aggregation=agg,
        display_config=dc,
    )

    # Serialisieren
    trip_dict = _trip_to_dict(trip)
    dc_dict = trip_dict.get("display_config", {})

    # per_channel_layouts muss enthalten sein (latenter Bug aus #429 wird mitgefixt)
    assert "channel_layouts" in dc_dict, (
        "per_channel_layouts muss als channel_layouts serialisiert werden "
        "(latenter Bug seit #429)."
    )

    # per_report_layouts muss enthalten sein
    assert "channel_layouts_per_report" in dc_dict, (
        "per_report_layouts muss als channel_layouts_per_report serialisiert werden."
    )

    # Roundtrip: reparsen und vergleichen
    dc2 = _parse_display_config(dc_dict)

    assert dc2.per_report_layouts is not None
    assert "morning" in dc2.per_report_layouts
    assert [m.metric_id for m in dc2.per_report_layouts["morning"]["email"]] == (
        [m.metric_id for m in dc.per_report_layouts["morning"]["email"]]
    ), "Roundtrip für morning.email muss bit-identisch sein."

    assert "evening" in dc2.per_report_layouts
    assert [m.metric_id for m in dc2.per_report_layouts["evening"]["email"]] == (
        [m.metric_id for m in dc.per_report_layouts["evening"]["email"]]
    ), "Roundtrip für evening.email muss bit-identisch sein."

    # per_channel_layouts Roundtrip
    assert dc2.per_channel_layouts is not None
    assert [m.metric_id for m in dc2.per_channel_layouts["email"]] == (
        [m.metric_id for m in dc.per_channel_layouts["email"]]
    ), "Roundtrip für per_channel_layouts.email muss bit-identisch sein."


# ---------------------------------------------------------------------------
# AC-7: Email-Renderer-Fix — trip_report.py nutzt get_metrics_for_channel
# ---------------------------------------------------------------------------


def test_ac7_trip_report_uses_get_metrics_for_channel():
    """AC-7: trip_report.py:73 soll get_metrics_for_channel("email", ...) nutzen.

    Strukturtest: Verifiziert, dass der Email-Formatter den kanal-bewussten Pfad
    nimmt, nicht den globalen. Ohne diesen Fix haben per_report_layouts-Overrides
    für Email null Wirkung.
    """
    from src.formatters.trip_report import TripReportFormatter

    source = inspect.getsource(TripReportFormatter.format_email)

    assert "get_metrics_for_channel" in source, (
        "trip_report.py muss dc.get_metrics_for_channel('email', report_type) aufrufen, "
        "um per_report_layouts und per_channel_layouts für Email zu respektieren. "
        "Aktuell: get_metrics_for_report_type() — muss auf get_metrics_for_channel() umgestellt werden."
    )


def test_ac7_trip_report_does_not_bypass_channel_logic():
    """AC-7b: trip_report.py:73 darf get_metrics_for_report_type NICHT mehr direkt aufrufen."""
    from src.formatters.trip_report import TripReportFormatter

    source = inspect.getsource(TripReportFormatter.format_email)

    # Zeile 73 lautet aktuell: active_metrics = dc.get_metrics_for_report_type(report_type)
    # Nach Fix: get_metrics_for_channel("email", report_type) — get_metrics_for_report_type
    # taucht danach nicht mehr in format_email auf.
    assert "get_metrics_for_report_type" not in source, (
        "Nach dem Fix darf trip_report.py nicht mehr dc.get_metrics_for_report_type() aufrufen — "
        "das umgeht die per_report_layouts-Kaskade. Stattdessen: get_metrics_for_channel('email', ...)."
    )
