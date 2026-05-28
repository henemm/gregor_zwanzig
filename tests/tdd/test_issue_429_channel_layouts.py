"""TDD RED — Issue #429: Datenmodell „Layout pro Kanal" + Backward-Compat.

SPEC: docs/specs/modules/issue_429_channel_layouts.md (AC-1..AC-8).
TEST-MANIFEST: docs/specs/tests/issue_429_channel_layouts_tests.md.

Diese Tests beschreiben die NOCH NICHT existierende API:
  - src/app/models.py: UnifiedWeatherDisplayConfig.per_channel_layouts
  - src/app/models.py: UnifiedWeatherDisplayConfig.get_metrics_for_channel(channel, report_type)
  - src/app/loader.py: _parse_display_config liest channel_layouts-Zweig
  - src/output/renderers/channel_layout.py: render_for_channel nutzt get_metrics_for_channel

Alle "Forward-Tests" (AC-1, AC-3, AC-4, AC-5, AC-7) MÜSSEN in der RED-Phase rot sein
(AttributeError, weil per_channel_layouts und get_metrics_for_channel noch nicht existieren).

AC-2 scheitert ebenfalls mit AttributeError beim Aufruf der neuen Methode.

AC-6 (Backward-Compat-Garantie) läuft heute schon grün — Regression-Sentinel für die
GREEN-Phase: nach dem Refactor darf das Rendering für alte Trips nicht abweichen.

AC-8 (Frontend-Types) wird separat per `tsc --noEmit` geprüft, nicht in diesem Python-Suite.

KEINE Mocks — reine Datenstrukturen + echte Aufrufe der (zu bauenden) Funktionen.
Builder-Pattern und Test-Trip-JSON sind aus tests/tdd/test_issue_360_channel_renderer.py
und tests/integration/test_config_persistence.py übernommen.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Helpers — Test-Fixtures
# ---------------------------------------------------------------------------


def _legacy_trip_data() -> dict[str, Any]:
    """Alter Trip ohne `channel_layouts` — nur globale `metrics`-Liste.

    Genau das Schema, das #429 backward-kompatibel halten muss.
    """
    return {
        "trip_id": "legacy-trip",
        "metrics": [
            {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
            {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
            {"metric_id": "gust", "enabled": True, "bucket": "primary", "order": 2},
            {"metric_id": "rain_probability", "enabled": True, "bucket": "primary", "order": 3},
            {"metric_id": "precipitation", "enabled": True, "bucket": "primary", "order": 4},
            {"metric_id": "wind_chill", "enabled": True, "bucket": "primary", "order": 5},
            {"metric_id": "cloud_total", "enabled": True, "bucket": "primary", "order": 6},
            {"metric_id": "thunder", "enabled": True, "bucket": "primary", "order": 7},
            {"metric_id": "fresh_snow", "enabled": True, "bucket": "primary", "order": 8},
            {"metric_id": "visibility", "enabled": True, "bucket": "secondary", "order": 0},
        ],
        "updated_at": "2026-05-28T10:00:00",
    }


def _per_channel_trip_data() -> dict[str, Any]:
    """Neuer Trip MIT `channel_layouts` — Email und Telegram haben eigene Listen."""
    return {
        "trip_id": "per-channel-trip",
        "metrics": [
            # Globale Fallback-Liste — wird für Kanäle ohne Eintrag verwendet (Signal, SMS).
            {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
            {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
        ],
        "channel_layouts": {
            "email": [
                # Email: 6 Spalten, eigene Reihenfolge
                {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
                {"metric_id": "wind_chill",  "enabled": True, "bucket": "primary", "order": 1},
                {"metric_id": "wind",        "enabled": True, "bucket": "primary", "order": 2},
                {"metric_id": "gust",        "enabled": True, "bucket": "primary", "order": 3},
                {"metric_id": "precipitation", "enabled": True, "bucket": "primary", "order": 4},
                {"metric_id": "cloud_total", "enabled": True, "bucket": "secondary", "order": 0},
            ],
            "telegram": [
                # Telegram: 10 Spalten — Limit 7 Slots (Slot 0 = Zeit). 3 müssen demoted werden.
                {"metric_id": f"metric_{i}", "enabled": True, "bucket": "primary", "order": i}
                for i in range(10)
            ],
            # Signal + SMS bewusst NICHT eingetragen → Fallback auf globale Liste.
        },
        "updated_at": "2026-05-28T10:00:00",
    }


def _empty_sms_layout_trip_data() -> dict[str, Any]:
    """Trip mit explizit leerer SMS-Liste (User hat alle SMS-Metriken deaktiviert)."""
    return {
        "trip_id": "empty-sms-trip",
        "metrics": [
            {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
        ],
        "channel_layouts": {
            "email": [
                {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
            ],
            "sms": [],  # explizit leer — kein Fallback
        },
        "updated_at": "2026-05-28T10:00:00",
    }


def _parse(data: dict[str, Any]):
    """Convenience: parse display-config-dict to UnifiedWeatherDisplayConfig."""
    from app.loader import _parse_display_config
    return _parse_display_config(data)


# ---------------------------------------------------------------------------
# AC-1: Loader liest `channel_layouts` und befüllt `per_channel_layouts`
# ---------------------------------------------------------------------------


def test_ac1_loader_reads_channel_layouts():
    """AC-1: Trip-JSON mit channel_layouts → per_channel_layouts ist nicht None."""
    dc = _parse(_per_channel_trip_data())

    # NEUE API — existiert in der RED-Phase noch nicht.
    assert hasattr(dc, "per_channel_layouts"), (
        "UnifiedWeatherDisplayConfig braucht ein per_channel_layouts-Feld (Issue #429)."
    )
    assert dc.per_channel_layouts is not None
    assert "email" in dc.per_channel_layouts
    assert "telegram" in dc.per_channel_layouts

    email_layout = dc.per_channel_layouts["email"]
    assert len(email_layout) == 6
    # Reihenfolge muss erhalten bleiben
    assert email_layout[0].metric_id == "temperature"
    assert email_layout[1].metric_id == "wind_chill"
    assert email_layout[0].bucket == "primary"
    assert email_layout[5].bucket == "secondary"


def test_ac1_all_empty_channel_layouts_treated_as_none():
    """AC-1 Invariante: alle Kanal-Listen leer → per_channel_layouts = None."""
    data = {
        "trip_id": "all-empty",
        "metrics": [
            {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
        ],
        "channel_layouts": {"email": [], "telegram": [], "signal": [], "sms": []},
        "updated_at": "2026-05-28T10:00:00",
    }
    dc = _parse(data)
    # Wenn ALLE Kanal-Listen leer sind, ist channel_layouts effektiv „nicht gesetzt" → None.
    assert dc.per_channel_layouts is None


# ---------------------------------------------------------------------------
# AC-2: Backward-Compat — Trip ohne channel_layouts → per_channel_layouts ist None
# ---------------------------------------------------------------------------


def test_ac2_legacy_trip_has_no_per_channel_layouts():
    """AC-2: Alter Trip → per_channel_layouts is None, get_metrics_for_channel = global."""
    dc = _parse(_legacy_trip_data())

    assert hasattr(dc, "per_channel_layouts")
    assert dc.per_channel_layouts is None

    # Fallback-Verhalten: get_metrics_for_channel == get_metrics_for_report_type
    assert hasattr(dc, "get_metrics_for_channel"), (
        "UnifiedWeatherDisplayConfig braucht get_metrics_for_channel(channel, report_type)."
    )
    via_channel = dc.get_metrics_for_channel("email", "evening")
    via_report = dc.get_metrics_for_report_type("evening")
    via_channel_ids = [m.metric_id for m in via_channel]
    via_report_ids = [m.metric_id for m in via_report]
    assert via_channel_ids == via_report_ids


# ---------------------------------------------------------------------------
# AC-3: Per-Channel-Liste schlägt globale Liste
# ---------------------------------------------------------------------------


def test_ac3_per_channel_layout_wins_over_global():
    """AC-3: Email-Layout gespeichert → get_metrics_for_channel("email", ...) liefert Email-Liste."""
    dc = _parse(_per_channel_trip_data())

    metrics = dc.get_metrics_for_channel("email", "evening")
    ids = [m.metric_id for m in metrics]

    # Email-spezifische Reihenfolge (nicht die globale Reihenfolge!)
    assert ids[0] == "temperature"
    assert ids[1] == "wind_chill"
    assert ids[2] == "wind"
    assert ids[3] == "gust"
    assert ids[4] == "precipitation"
    assert "cloud_total" in ids  # secondary, aber in der Liste enthalten


# ---------------------------------------------------------------------------
# AC-4: Fehlender Kanal-Eintrag → Fallback auf globale Liste
# ---------------------------------------------------------------------------


def test_ac4_missing_channel_falls_back_to_global():
    """AC-4: Signal nicht in channel_layouts → Fallback auf globale Metriken."""
    dc = _parse(_per_channel_trip_data())

    signal_metrics = dc.get_metrics_for_channel("signal", "morning")
    global_metrics = dc.get_metrics_for_report_type("morning")
    assert [m.metric_id for m in signal_metrics] == [m.metric_id for m in global_metrics]


# ---------------------------------------------------------------------------
# AC-5: CHANNEL_LIMITS bleiben durchgesetzt
# ---------------------------------------------------------------------------


def test_ac5_channel_limits_still_applied_with_per_channel_layouts():
    """AC-5: Telegram-Layout mit 10 primaries → max 7 in table_columns (limit 8, Slot 0 = Zeit)."""
    from src.output.renderers.channel_layout import render_for_channel

    dc = _parse(_per_channel_trip_data())
    layout = render_for_channel("telegram", dc, "evening")

    # CHANNEL_LIMITS["telegram"]["max_table_cols"] = 8 → 7 Metrik-Slots (Slot 0 = Zeit).
    assert len(layout.table_columns) == 7
    # Die 3 überzähligen Metriken wandern in detail_metrics.
    assert layout.demoted_count == 3
    # Reihenfolge in table_columns muss der Telegram-Layout-Reihenfolge entsprechen.
    assert layout.table_columns == [f"metric_{i}" for i in range(7)]
    assert layout.detail_metrics[:3] == [f"metric_{i}" for i in range(7, 10)]


# ---------------------------------------------------------------------------
# AC-6: Alte Trips bit-identisch (Backward-Compat-Garantie / Regression-Sentinel)
# ---------------------------------------------------------------------------


def test_ac6_legacy_trip_render_bit_identical():
    """AC-6: Alter Trip ohne channel_layouts → render_for_channel-Ergebnis unverändert.

    Sentinel-Test: definiert das ERWARTETE Verhalten für alte Trips. Heute (vor
    Implement) läuft die Pipeline bereits über get_metrics_for_report_type — nach
    dem Refactor muss das Ergebnis bit-identisch bleiben. Bleibt also in der RED-
    UND GREEN-Phase grün und schützt vor versehentlicher Verhaltensänderung.
    """
    from src.output.renderers.channel_layout import render_for_channel

    dc = _parse(_legacy_trip_data())

    # Email: alle 9 primaries + 1 secondary
    layout = render_for_channel("email", dc, "evening")
    assert layout.table_columns == [
        "temperature", "wind", "gust", "rain_probability", "precipitation",
        "wind_chill", "cloud_total", "thunder", "fresh_snow",
    ]
    assert layout.detail_metrics == ["visibility"]
    assert layout.demoted_count == 0

    # Telegram: limit 8 → 7 primaries + Rest in detail
    layout_tg = render_for_channel("telegram", dc, "evening")
    assert len(layout_tg.table_columns) == 7
    assert layout_tg.demoted_count == 2
    assert layout_tg.detail_metrics == ["thunder", "fresh_snow", "visibility"]

    # SMS: 0 Tabellen-Spalten
    layout_sms = render_for_channel("sms", dc, "evening")
    assert layout_sms.table_columns == []
    assert len(layout_sms.detail_metrics) >= 9  # alles in Detail


# ---------------------------------------------------------------------------
# AC-7: Leere Liste = leere Liste (kein Fallback)
# ---------------------------------------------------------------------------


def test_ac7_empty_channel_layout_no_fallback():
    """AC-7: per_channel_layouts["sms"] == [] → leere Liste, kein Fallback."""
    dc = _parse(_empty_sms_layout_trip_data())

    sms_metrics = dc.get_metrics_for_channel("sms", "evening")
    assert sms_metrics == [], (
        "Eine explizit leere channel_layouts-Liste muss leer bleiben — "
        "kein Fallback auf globale Metrik-Liste."
    )
