"""
TDD RED Tests fuer Issue #180 — Alert-Konfigurator: Schwellwert-Tabelle.

Jeder Test mappt 1:1 auf ein AC aus
docs/specs/modules/issue_180_alert_metric_table.md.

Da Issue #180 rein Frontend ist (Svelte), pruefen diese Tests:
  1. Datei-Existenz der neuen Svelte-Komponenten
  2. Inhalts-Invarianten (Imports, data-testids, API-Calls)

In RED-Phase schlagen alle Tests mit FileNotFoundError fehl,
weil die Svelte-Dateien noch nicht existieren.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ALERTS_TAB = Path("frontend/src/lib/components/alerts-tab")
TRIP_TABS = Path("frontend/src/lib/components/trip-detail/TripTabs.svelte")


# ---------------------------------------------------------------------------
# AC-1: AlertsTab.svelte existiert
# ---------------------------------------------------------------------------

def test_ac1_alerts_tab_svelte_exists():
    """AC-1: AlertsTab.svelte muss im alerts-tab-Verzeichnis existieren."""
    assert (ALERTS_TAB / "AlertsTab.svelte").exists(), \
        "AlertsTab.svelte wurde noch nicht erstellt"


# ---------------------------------------------------------------------------
# AC-1: AlertMetricTable.svelte existiert
# ---------------------------------------------------------------------------

def test_ac1_alert_metric_table_svelte_exists():
    """AC-1: AlertMetricTable.svelte muss im alerts-tab-Verzeichnis existieren."""
    assert (ALERTS_TAB / "AlertMetricTable.svelte").exists(), \
        "AlertMetricTable.svelte wurde noch nicht erstellt"


# ---------------------------------------------------------------------------
# AC-1: AlertMetricRow.svelte existiert
# ---------------------------------------------------------------------------

def test_ac1_alert_metric_row_svelte_exists():
    """AC-1: AlertMetricRow.svelte muss im alerts-tab-Verzeichnis existieren."""
    assert (ALERTS_TAB / "AlertMetricRow.svelte").exists(), \
        "AlertMetricRow.svelte wurde noch nicht erstellt"


# ---------------------------------------------------------------------------
# AC-1: AlertMetricRow hat data-testid fuer Zeilen
# ---------------------------------------------------------------------------

def test_ac1_metric_row_has_testid():
    """AC-1: AlertMetricRow.svelte enthaelt data-testid='alert-metric-row-' fuer Zeilenidentifikation."""
    content = (ALERTS_TAB / "AlertMetricRow.svelte").read_text()
    assert "alert-metric-row-" in content, \
        "AlertMetricRow.svelte enthaelt kein data-testid='alert-metric-row-{metric}'"


# ---------------------------------------------------------------------------
# AC-2: Delta-only Metriken werden erkannt (DELTA_ONLY_METRICS)
# ---------------------------------------------------------------------------

def test_ac2_delta_only_metrics_referenced():
    """AC-2: AlertMetricRow.svelte importiert DELTA_ONLY_METRICS fuer Delta-only-Erkennung."""
    content = (ALERTS_TAB / "AlertMetricRow.svelte").read_text()
    assert "DELTA_ONLY_METRICS" in content, \
        "AlertMetricRow.svelte nutzt DELTA_ONLY_METRICS nicht"


# ---------------------------------------------------------------------------
# AC-3: AlertMetricTable liest alert_rules
# ---------------------------------------------------------------------------

def test_ac3_table_references_alert_rules():
    """AC-3: AlertMetricTable.svelte referenziert alert_rules (Daten-Prop vom Trip)."""
    content = (ALERTS_TAB / "AlertMetricTable.svelte").read_text()
    assert "alert_rules" in content, \
        "AlertMetricTable.svelte referenziert alert_rules nicht"


# ---------------------------------------------------------------------------
# AC-4: AlertsTab ruft api.put auf
# ---------------------------------------------------------------------------

def test_ac4_tab_calls_api_put():
    """AC-4: AlertsTab.svelte enthaelt api.put fuer den Speichern-Call."""
    content = (ALERTS_TAB / "AlertsTab.svelte").read_text()
    assert "api.put" in content, \
        "AlertsTab.svelte enthaelt keinen api.put-Aufruf"


# ---------------------------------------------------------------------------
# AC-4: AlertsTab-Payload enthaelt alert_rules
# ---------------------------------------------------------------------------

def test_ac4_tab_includes_alert_rules_in_payload():
    """AC-4: AlertsTab.svelte uebergibt alert_rules im PUT-Payload."""
    content = (ALERTS_TAB / "AlertsTab.svelte").read_text()
    assert "alert_rules" in content, \
        "AlertsTab.svelte enthaelt alert_rules nicht im Payload"


# ---------------------------------------------------------------------------
# AC-6: AlertCooldownCard eingebunden
# ---------------------------------------------------------------------------

def test_ac6_tab_imports_cooldown_card():
    """AC-6: AlertsTab.svelte importiert AlertCooldownCard."""
    content = (ALERTS_TAB / "AlertsTab.svelte").read_text()
    assert "AlertCooldownCard" in content, \
        "AlertsTab.svelte importiert AlertCooldownCard nicht"


# ---------------------------------------------------------------------------
# AC-7: AlertQuietHoursCard eingebunden
# ---------------------------------------------------------------------------

def test_ac7_tab_imports_quiet_hours_card():
    """AC-7: AlertsTab.svelte importiert AlertQuietHoursCard."""
    content = (ALERTS_TAB / "AlertsTab.svelte").read_text()
    assert "AlertQuietHoursCard" in content, \
        "AlertsTab.svelte importiert AlertQuietHoursCard nicht"


# ---------------------------------------------------------------------------
# AC-8: Cooldown-Wert wird gespeichert
# ---------------------------------------------------------------------------

def test_ac8_tab_includes_cooldown_minutes():
    """AC-8: AlertsTab.svelte uebergibt alert_cooldown_minutes im PUT-Payload."""
    content = (ALERTS_TAB / "AlertsTab.svelte").read_text()
    assert "alert_cooldown_minutes" in content, \
        "AlertsTab.svelte enthaelt alert_cooldown_minutes nicht"


# ---------------------------------------------------------------------------
# TripTabs verdrahtet AlertsTab (Platzhalter entfernt)
# ---------------------------------------------------------------------------

def test_trip_tabs_wires_alerts_tab():
    """TripTabs.svelte importiert und rendert AlertsTab statt Platzhalter-Text."""
    content = TRIP_TABS.read_text()
    assert "AlertsTab" in content, \
        "TripTabs.svelte enthaelt noch keinen AlertsTab-Import (Platzhalter nicht ersetzt)"
