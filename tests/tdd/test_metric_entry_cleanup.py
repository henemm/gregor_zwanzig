"""
TDD RED Tests for Issue #445: MetricEntry-Duplikate konsolidieren.

Prüft statisch, dass nach dem Cleanup:
- Keine lokale `interface MetricEntry` mehr in den 3 trip-detail-Komponenten existiert
- Jede Datei `MetricEntry` aus `$lib/types` importiert
- scoreToggleHelpers.ts NICHT von $lib/types abhängt (bleibt unverändert)

SPEC: docs/specs/modules/issue_445_metric_entry_cleanup.md
TEST-MANIFEST: docs/specs/tests/issue_445_metric_entry_cleanup_tests.md
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIP_DETAIL = REPO_ROOT / "frontend/src/lib/components/trip-detail"


# ---------------------------------------------------------------------------
# AC-1: Keine lokale interface MetricEntry in den 3 Komponenten
# ---------------------------------------------------------------------------

def test_save_preset_dialog_no_local_metric_entry():
    """AC-1: SavePresetDialog.svelte darf keine lokale interface MetricEntry haben."""
    content = (TRIP_DETAIL / "SavePresetDialog.svelte").read_text()
    assert "interface MetricEntry" not in content, (
        "SavePresetDialog.svelte hat noch eine lokale 'interface MetricEntry' — "
        "löschen und aus $lib/types importieren"
    )


def test_table_preview_no_local_metric_entry():
    """AC-1: TablePreview.svelte darf keine lokale interface MetricEntry haben."""
    content = (TRIP_DETAIL / "TablePreview.svelte").read_text()
    assert "interface MetricEntry" not in content, (
        "TablePreview.svelte hat noch eine lokale 'interface MetricEntry' — "
        "löschen und aus $lib/types importieren"
    )


def test_metric_checkbox_no_local_metric_entry():
    """AC-1: MetricCheckbox.svelte darf keine lokale interface MetricEntry haben."""
    content = (TRIP_DETAIL / "MetricCheckbox.svelte").read_text()
    assert "interface MetricEntry" not in content, (
        "MetricCheckbox.svelte hat noch eine lokale 'interface MetricEntry' — "
        "löschen und aus $lib/types importieren"
    )


# ---------------------------------------------------------------------------
# AC-2: MetricEntry aus $lib/types importiert
# ---------------------------------------------------------------------------

def test_save_preset_dialog_imports_metric_entry_from_types():
    """AC-2: SavePresetDialog.svelte muss MetricEntry aus $lib/types importieren."""
    content = (TRIP_DETAIL / "SavePresetDialog.svelte").read_text()
    has_import = re.search(
        r"import\s+(?:type\s+)?\{[^}]*\bMetricEntry\b[^}]*\}\s+from\s+['\"]\\?\$lib/types['\"]",
        content
    )
    assert has_import, (
        "SavePresetDialog.svelte importiert MetricEntry nicht aus '$lib/types'"
    )


def test_table_preview_imports_metric_entry_from_types():
    """AC-2: TablePreview.svelte muss MetricEntry aus $lib/types importieren."""
    content = (TRIP_DETAIL / "TablePreview.svelte").read_text()
    has_import = re.search(
        r"import\s+(?:type\s+)?\{[^}]*\bMetricEntry\b[^}]*\}\s+from\s+['\"]\\?\$lib/types['\"]",
        content
    )
    assert has_import, (
        "TablePreview.svelte importiert MetricEntry nicht aus '$lib/types'"
    )


def test_metric_checkbox_imports_metric_entry_from_types():
    """AC-2: MetricCheckbox.svelte muss MetricEntry aus $lib/types importieren."""
    content = (TRIP_DETAIL / "MetricCheckbox.svelte").read_text()
    has_import = re.search(
        r"import\s+(?:type\s+)?\{[^}]*\bMetricEntry\b[^}]*\}\s+from\s+['\"]\\?\$lib/types['\"]",
        content
    )
    assert has_import, (
        "MetricCheckbox.svelte importiert MetricEntry nicht aus '$lib/types'"
    )


# ---------------------------------------------------------------------------
# AC-5: scoreToggleHelpers.ts bleibt unverändert
# ---------------------------------------------------------------------------

def test_score_toggle_helpers_not_importing_metric_entry_from_lib_types():
    """AC-5: scoreToggleHelpers.ts darf MetricEntry NICHT aus $lib/types importieren."""
    helpers = REPO_ROOT / "frontend/src/lib/utils/scoreToggleHelpers.ts"
    content = helpers.read_text()
    assert "MetricEntry" in content, (
        "scoreToggleHelpers.ts hat keine MetricEntry-Definition mehr — "
        "wurde versehentlich verändert"
    )
    imports_from_types = re.search(
        r"import\s+(?:type\s+)?\{[^}]*\bMetricEntry\b[^}]*\}\s+from\s+['\"]\\?\$lib/types['\"]",
        content
    )
    assert not imports_from_types, (
        "scoreToggleHelpers.ts importiert MetricEntry aus $lib/types — das ist unerwünscht"
    )
