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

#3237 (Altpfad entfernt): die Kanal-Kaskade ``get_metrics_for_channel`` (globaler
Rueckfall, Kanal-Liste schlaegt global, leere Kanal-Liste ohne Rueckfall) existiert
nicht mehr -- die Tabelle "Was steht wo" ist die einzige Quelle. Entfallen sind
deshalb AC-2, AC-3, AC-4 und AC-7 (reine Kaskaden-Regeln); die Aussagen fuer die
Tabelle bewachen ``tests/tdd/test_3237_placements_aus_grundauswahl.py`` und
``tests/integration/test_issue_448_validator_metrics_for_channel.py``. Der Loader
liest ``channel_layouts`` weiter bis #3277 (AC-1).

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
    """Neuer Trip MIT `channel_layouts` — Email und Telegram haben eigene Listen.

    Issue #1719 Scheibe 2 (ADR-0050): eine Kanal-Ebene darf die globale
    Grundauswahl nur noch verfeinern (schneiden), nicht mehr ergaenzen — die
    globale Liste muss deshalb JEDE Metrik-ID fuehren, die irgendeine
    Kanal-Ebene unten benutzt (sonst schneidet get_metrics_for_channel() sie
    jetzt weg). "metric_0".."metric_9" sind reine Struktur-Test-IDs ohne
    Katalog-Eintrag (AC-5, Telegram-Slot-Limit) und werden hier bewusst
    ebenfalls global gefuehrt, damit sie den Schnitt ueberleben. Alle
    Ergaenzungen bewusst als "primary" mit steigendem `order` -- AC-4
    vergleicht get_metrics_for_channel() (sortiert) gegen
    get_metrics_for_report_type() (unsortiert) auf ID-Gleichheit; ein
    "secondary"-Eintrag dazwischen wuerde die beiden Reihenfolgen
    auseinanderlaufen lassen, ohne dass das etwas mit dieser Scheibe zu tun
    haette.
    """
    return {
        "trip_id": "per-channel-trip",
        "metrics": [
            # Globale Fallback-Liste — wird für Kanäle ohne Eintrag verwendet (Signal, SMS)
            # UND ist seit #1719 S2 das Maximum fuer email/telegram unten.
            {"metric_id": "temperature", "enabled": True, "bucket": "primary", "order": 0},
            {"metric_id": "wind", "enabled": True, "bucket": "primary", "order": 1},
            {"metric_id": "wind_chill", "enabled": True, "bucket": "primary", "order": 2},
            {"metric_id": "gust", "enabled": True, "bucket": "primary", "order": 3},
            {"metric_id": "precipitation", "enabled": True, "bucket": "primary", "order": 4},
            {"metric_id": "cloud_total", "enabled": True, "bucket": "primary", "order": 5},
            *[
                {"metric_id": f"metric_{i}", "enabled": True, "bucket": "primary", "order": 6 + i}
                for i in range(10)
            ],
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


def _parse(data: dict[str, Any]):
    """Convenience: parse display-config-dict to UnifiedWeatherDisplayConfig."""
    from app.loader import _parse_display_config
    return _parse_display_config(data)


# #3277: ``test_ac1_loader_reads_channel_layouts`` und
# ``test_all_empty_channel_layouts_kept_as_dict_not_none`` entfallen mit dem
# Lesen des Altfelds ``channel_layouts`` (Modellfeld ``per_channel_layouts``
# entfernt, ADR-0124 Nr. 8; Nachweis "wird nicht gelesen":
# tests/tdd/test_3277_altfelder_entfernen.py AC-3).


# ---------------------------------------------------------------------------
# AC-5: CHANNEL_LIMITS bleiben durchgesetzt
# ---------------------------------------------------------------------------


def test_ac5_channel_limits_still_applied_with_per_channel_layouts():
    """AC-5: Telegram-Liste mit 10 primaries → max 7 in table_columns (limit 8, Slot 0 = Zeit).

    #3237: ``render_for_channel`` bekommt die fertige Kanal-Liste vom Aufrufer
    (``dc.metrics``, aus der Tabelle "Was steht wo"); die Kanal-Kaskade ist weg.
    Die Telegram-Liste des Trips geht deshalb als ``metrics`` hinein."""
    from src.output.renderers.channel_layout import render_for_channel

    daten = _per_channel_trip_data()
    daten["metrics"] = daten["channel_layouts"]["telegram"]
    dc = _parse(daten)
    layout = render_for_channel("telegram", dc, "evening")

    # CHANNEL_LIMITS["telegram"]["max_table_cols"] = 8 → 7 Metrik-Slots (Slot 0 = Zeit).
    assert len(layout.table_columns) == 7
    # Die 3 überzähligen Metriken werden verdrängt (demoted_count).
    assert layout.demoted_count == 3
    # Reihenfolge in table_columns muss der Telegram-Layout-Reihenfolge entsprechen.
    assert layout.table_columns == [f"metric_{i}" for i in range(7)]


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
    assert layout.demoted_count == 0

    # Telegram: limit 8 → 7 primaries + Rest verdrängt
    layout_tg = render_for_channel("telegram", dc, "evening")
    assert len(layout_tg.table_columns) == 7
    assert layout_tg.demoted_count == 2

    # SMS: 0 Tabellen-Spalten, alle 9 primaries verdrängt
    layout_sms = render_for_channel("sms", dc, "evening")
    assert layout_sms.table_columns == []
    assert layout_sms.demoted_count == 9
