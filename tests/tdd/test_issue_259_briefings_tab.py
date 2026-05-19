"""
TDD RED Tests fuer Issue #259 — Trip-Uebersicht: Briefing-Zeitplan-Tab implementieren.

Jeder Test mappt 1:1 auf ein AC aus
docs/specs/modules/issue_259_briefings_tab.md.

Da Issue #259 rein Frontend ist (Svelte), pruefen diese Tests:
  1. Datei-Existenz der neuen Svelte-Komponente
  2. Inhalts-Invarianten (Imports, data-testids, API-Calls, Patterns)
  3. TripTabs-Integration (Branch vorhanden, Platzhalter entfernt)

In RED-Phase schlagen Tests mit AssertionError fehl,
weil BriefingsTab.svelte noch nicht existiert und TripTabs.svelte noch nicht
den briefings-Branch enthaelt.
"""
from __future__ import annotations

from pathlib import Path

BRIEFINGS_TAB_DIR = Path("frontend/src/lib/components/briefings-tab")
BRIEFINGS_TAB = BRIEFINGS_TAB_DIR / "BriefingsTab.svelte"
TRIP_TABS = Path("frontend/src/lib/components/trip-detail/TripTabs.svelte")


# ---------------------------------------------------------------------------
# AC-1: BriefingsTab.svelte existiert (Tab rendert, kein Platzhalter)
# ---------------------------------------------------------------------------

def test_ac1_briefings_tab_svelte_exists():
    """AC-1: BriefingsTab.svelte muss im briefings-tab-Verzeichnis existieren."""
    assert BRIEFINGS_TAB.exists(), \
        "BriefingsTab.svelte wurde noch nicht erstellt"


def test_ac1_trip_tabs_has_briefings_branch():
    """AC-1: TripTabs.svelte muss einen {:else if tab.value === 'briefings'}-Branch haben."""
    content = TRIP_TABS.read_text()
    assert "briefings" in content and "BriefingsTab" in content, \
        "TripTabs.svelte verdrahtet BriefingsTab noch nicht (kein briefings-Branch)"


def test_ac1_placeholder_removed_from_trip_tabs():
    """AC-1: Der Platzhalter-Text 'Inhalt folgt mit Issue #159' muss aus TripTabs.svelte entfernt sein."""
    content = TRIP_TABS.read_text()
    assert "Inhalt folgt mit Issue #159" not in content, \
        "Platzhalter-Text ist noch in TripTabs.svelte vorhanden"


# ---------------------------------------------------------------------------
# AC-2: EditReportConfigSection eingebunden
# ---------------------------------------------------------------------------

def test_ac2_briefings_tab_imports_edit_report_config():
    """AC-2: BriefingsTab.svelte importiert EditReportConfigSection fuer die Formularfelder."""
    content = BRIEFINGS_TAB.read_text()
    assert "EditReportConfigSection" in content, \
        "BriefingsTab.svelte importiert EditReportConfigSection nicht"


def test_ac2_briefings_tab_binds_report_config():
    """AC-2: BriefingsTab.svelte bindet reportConfig per bind:reportConfig an EditReportConfigSection."""
    content = BRIEFINGS_TAB.read_text()
    assert "bind:reportConfig" in content or "reportConfig" in content, \
        "BriefingsTab.svelte uebergibt reportConfig nicht an EditReportConfigSection"


# ---------------------------------------------------------------------------
# AC-3: PUT-Call mit report_config im Payload
# ---------------------------------------------------------------------------

def test_ac3_briefings_tab_calls_api_put():
    """AC-3: BriefingsTab.svelte enthaelt api.put fuer den Speichern-Call."""
    content = BRIEFINGS_TAB.read_text()
    assert "api.put" in content, \
        "BriefingsTab.svelte enthaelt keinen api.put-Aufruf"


def test_ac3_briefings_tab_puts_report_config():
    """AC-3: BriefingsTab.svelte uebergibt report_config im PUT-Payload."""
    content = BRIEFINGS_TAB.read_text()
    assert "report_config" in content, \
        "BriefingsTab.svelte enthaelt report_config nicht im PUT-Payload"


def test_ac3_briefings_tab_uses_trip_id():
    """AC-3: BriefingsTab.svelte baut die PUT-URL mit trip.id."""
    content = BRIEFINGS_TAB.read_text()
    assert "trip.id" in content, \
        "BriefingsTab.svelte verwendet trip.id nicht in der API-URL"


# ---------------------------------------------------------------------------
# AC-4: Erfolgs-Flash mit data-testid
# ---------------------------------------------------------------------------

def test_ac4_briefings_tab_has_save_success_testid():
    """AC-4: BriefingsTab.svelte enthaelt data-testid='briefings-tab-save-success' fuer den Erfolgs-Flash."""
    content = BRIEFINGS_TAB.read_text()
    assert "briefings-tab-save-success" in content, \
        "BriefingsTab.svelte enthaelt kein data-testid fuer den Erfolgs-Flash"


def test_ac4_briefings_tab_has_save_success_state():
    """AC-4: BriefingsTab.svelte verwaltet saveSuccess-State fuer den 3-Sekunden-Flash."""
    content = BRIEFINGS_TAB.read_text()
    assert "saveSuccess" in content, \
        "BriefingsTab.svelte hat keinen saveSuccess-State"


# ---------------------------------------------------------------------------
# AC-5: Fehleranzeige mit data-testid
# ---------------------------------------------------------------------------

def test_ac5_briefings_tab_has_save_error_testid():
    """AC-5: BriefingsTab.svelte enthaelt data-testid='briefings-tab-save-error' fuer die Fehlermeldung."""
    content = BRIEFINGS_TAB.read_text()
    assert "briefings-tab-save-error" in content, \
        "BriefingsTab.svelte enthaelt kein data-testid fuer die Fehlermeldung"


def test_ac5_briefings_tab_has_save_error_state():
    """AC-5: BriefingsTab.svelte verwaltet saveError-State fuer Inline-Fehlermeldung."""
    content = BRIEFINGS_TAB.read_text()
    assert "saveError" in content, \
        "BriefingsTab.svelte hat keinen saveError-State"


# ---------------------------------------------------------------------------
# AC-6: Button disabled waehrend des Speicherns
# ---------------------------------------------------------------------------

def test_ac6_briefings_tab_has_save_button_testid():
    """AC-6: BriefingsTab.svelte enthaelt data-testid='briefings-tab-save' am Speichern-Button."""
    content = BRIEFINGS_TAB.read_text()
    assert "briefings-tab-save" in content, \
        "BriefingsTab.svelte enthaelt kein data-testid='briefings-tab-save'"


def test_ac6_briefings_tab_button_disabled_while_saving():
    """AC-6: BriefingsTab.svelte setzt disabled={saving} am Speichern-Button."""
    content = BRIEFINGS_TAB.read_text()
    assert "saving" in content and "disabled" in content, \
        "BriefingsTab.svelte implementiert disabled-while-saving nicht"
