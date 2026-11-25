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
# #3277: AC-1 (Loader liest channel_layouts_per_report) und AC-6 (Roundtrip
# der Kanal-/Bericht-Ebenen) entfallen mit dem Lesen und Schreiben dieser
# Altfelder (ADR-0124 Nr. 8: die Tabelle "Was steht wo" ist die einzige
# Quelle). Verbleibende Zusicherung: der Bestand laedt fehlerfrei, das Modell
# traegt die Ebenen nicht, und Serialisieren schreibt sie nicht zurueck.
# ---------------------------------------------------------------------------


def test_3277_bestand_mit_bericht_ebenen_laedt_ohne_altfelder():
    from datetime import date
    from app.loader import _trip_to_dict
    from app.trip import AggregationConfig, Stage, Trip, Waypoint
    from app.profile import ActivityProfile

    dc = _parse(_per_report_trip_data())
    assert not hasattr(dc, "per_report_layouts")
    assert not hasattr(dc, "per_channel_layouts")
    trip = Trip(
        id="test-434-roundtrip", name="Test Trip #434",
        stages=[Stage(id="s1", name="Etappe 1", date=date(2026, 7, 1),
                      waypoints=[Waypoint(id="w1", name="Start", lat=42.0, lon=9.0,
                                          elevation_m=100)])],
        aggregation=AggregationConfig.for_profile(ActivityProfile.SUMMER_TREKKING),
        display_config=dc,
    )
    dc_dict = _trip_to_dict(trip)["display_config"]
    assert "channel_layouts" not in dc_dict
    assert "channel_layouts_per_report" not in dc_dict
    assert [m.metric_id for m in dc.metrics if not m.derived] == [
        e["metric_id"] for e in _per_report_trip_data()["metrics"]]
