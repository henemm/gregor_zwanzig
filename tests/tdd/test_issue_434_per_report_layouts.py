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

#3237 (Altpfad entfernt): die dreistufige Kaskade ``get_metrics_for_channel``
(per_report > per_channel > global) existiert nicht mehr; die Tabelle "Was steht
wo" ist die einzige Quelle und gilt fuer beide Briefings (ADR-0124). Entfallen
sind AC-2 bis AC-5 (Kaskaden-Regeln) und AC-7/AC-7b (Quelltext-Pruefung, dass
``format_email`` die Kaskade aufruft -- sie war nach der Loeschung nur noch
durch einen Kommentar erfuellt). Loader und Serialisierung der Altfelder
bleiben bis #3277 (AC-1, AC-6).
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Test-Fixtures
# ---------------------------------------------------------------------------


def _per_report_trip_data() -> dict[str, Any]:
    """Trip MIT channel_layouts_per_report — Morning und Evening haben verschiedene Email-Listen.

    Issue #1719 Scheibe 2 (ADR-0050): die globale Liste ist das Maximum, gegen
    das jede Kanal-/Report-Ebene unten geschnitten wird -- sie muss deshalb
    jede unten verwendete Metrik-ID fuehren (precipitation, gust, wind_chill
    kamen sonst nur in channel_layouts/channel_layouts_per_report vor). Alle
    Ergaenzungen bewusst "primary" mit steigendem `order` -- AC-4 vergleicht
    den (sortierten) globalen Fallback von get_metrics_for_channel() gegen
    das (unsortierte) get_metrics_for_report_type() auf ID-Gleichheit.
    """
    return {
        "trip_id": "per-report-trip-434",
        "metrics": [
            # Globale Fallback-Liste
            {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
            {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
            {"metric_id": "precipitation", "enabled": True, "bucket": "primary", "order": 2},
            {"metric_id": "gust", "enabled": True, "bucket": "primary", "order": 3},
            {"metric_id": "wind_chill", "enabled": True, "bucket": "primary", "order": 4},
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
    # Issue #1728 DEC-6b: abgeleitete Groessen werden auch hier angehaengt
    # (s. test_issue_429_channel_layouts). Geprueft wird die GESPEICHERTE
    # Liste — die Zusicherung „per-Report-Ebene kommt unverfaelscht und in
    # Reihenfolge aus der Datei" ist unveraendert.
    morning_email = [m for m in dc.per_report_layouts["morning"]["email"]
                     if not m.derived]
    assert len(morning_email) == 2
    assert morning_email[0].metric_id == "temperature"
    assert morning_email[1].metric_id == "precipitation"

    assert "evening" in dc.per_report_layouts
    assert "email" in dc.per_report_layouts["evening"]
    evening_email = [m for m in dc.per_report_layouts["evening"]["email"]
                     if not m.derived]
    assert len(evening_email) == 3
    assert evening_email[0].metric_id == "wind"
    assert evening_email[1].metric_id == "gust"
    assert evening_email[2].metric_id == "wind_chill"


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
