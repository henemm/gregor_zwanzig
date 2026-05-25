"""
TDD — Issue #285: Wetter-Editor Restyle (Brand-Token-Compliance)
Spec: docs/specs/modules/issue_285_weather_section_restyle.md

Diese Tests prüfen strukturelle Eigenschaften der Svelte-Quelldateien
(WeatherConfigDialog, Segmented, app.css).

Hinweis (Issue #345): `EditWeatherSection.svelte` wurde im Zuge der
Wetter-Editor-Konsolidierung gelöscht (read-only `WeatherSummaryCard.svelte`
ersetzt es in der Tour-Bearbeiten-Maske). Die ehemaligen #285-Tests gegen
`EditWeatherSection.svelte` sind damit gegenstandslos und entfernt; die
Brand-Token-Compliance-Absicht ist auf die neue `WeatherSummaryCard.svelte`
übertragen (siehe `test_weather_summary_card_*`).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
WEATHER_DIALOG = REPO_ROOT / "frontend/src/lib/components/WeatherConfigDialog.svelte"
WEATHER_SUMMARY_CARD = REPO_ROOT / "frontend/src/lib/components/edit/WeatherSummaryCard.svelte"
SEGMENTED_SVELTE = REPO_ROOT / "frontend/src/lib/components/ui/segmented/Segmented.svelte"
SEGMENTED_INDEX = REPO_ROOT / "frontend/src/lib/components/ui/segmented/index.ts"
APP_CSS = REPO_ROOT / "frontend/src/app.css"


# ---------------------------------------------------------------------------
# AC-4: Keine verbotenen Tailwind-Klassen mehr (WeatherConfigDialog)
# ---------------------------------------------------------------------------

def test_ac4c_no_bg_primary_in_weather_config_dialog():
    """
    AC-4: WeatherConfigDialog.svelte darf kein 'bg-primary' enthalten.
    MUSS ROT sein: 'bg-primary' ist noch vorhanden (Zeilen 210, 215).
    """
    content = WEATHER_DIALOG.read_text()
    matches = re.findall(r'bg-primary', content)
    assert len(matches) == 0, (
        f"WeatherConfigDialog.svelte enthält noch {len(matches)} Vorkommen von 'bg-primary'. "
        "Muss auf Brand-Token umgestellt werden (Issue #285)."
    )


def test_ac4d_no_text_primary_foreground_in_weather_config_dialog():
    """
    AC-4: WeatherConfigDialog.svelte darf kein 'text-primary-foreground' enthalten.
    MUSS ROT sein: 'text-primary-foreground' ist noch vorhanden.
    """
    content = WEATHER_DIALOG.read_text()
    matches = re.findall(r'text-primary-foreground', content)
    assert len(matches) == 0, (
        f"WeatherConfigDialog.svelte enthält noch {len(matches)} Vorkommen von "
        "'text-primary-foreground'. Muss auf Brand-Token umgestellt werden."
    )


# ---------------------------------------------------------------------------
# Neue Komponente: Segmented.svelte muss existieren
# ---------------------------------------------------------------------------

def test_segmented_svelte_exists():
    """
    Segmented.svelte muss als neue Komponente angelegt worden sein.
    MUSS ROT sein: Datei existiert noch nicht.
    """
    assert SEGMENTED_SVELTE.exists(), (
        f"Segmented.svelte nicht gefunden unter: {SEGMENTED_SVELTE}. "
        "Die Komponente muss als Teil von Issue #285 erstellt werden."
    )


def test_segmented_index_exists():
    """
    index.ts für Segmented-Komponente muss existieren.
    MUSS ROT sein: Datei existiert noch nicht.
    """
    assert SEGMENTED_INDEX.exists(), (
        f"index.ts nicht gefunden unter: {SEGMENTED_INDEX}. "
        "Der Re-Export muss als Teil von Issue #285 erstellt werden."
    )


def test_segmented_svelte_uses_data_slot():
    """
    Segmented.svelte muss data-slot='segmented' und data-slot='segmented-item' verwenden.
    MUSS ROT sein: Datei existiert noch nicht.
    """
    assert SEGMENTED_SVELTE.exists(), "Segmented.svelte existiert noch nicht."
    content = SEGMENTED_SVELTE.read_text()
    assert 'data-slot="segmented"' in content, (
        "Segmented.svelte hat kein data-slot=\"segmented\" Attribut. "
        "Muss dem [data-slot]-Muster folgen."
    )
    assert 'data-slot="segmented-item"' in content, (
        "Segmented.svelte hat kein data-slot=\"segmented-item\" Attribut. "
        "Items brauchen dieses Attribut für CSS-Selektoren in app.css."
    )


def test_segmented_svelte_uses_data_active():
    """
    Segmented-Items müssen data-active='true/false' setzen.
    MUSS ROT sein: Datei existiert noch nicht.
    """
    assert SEGMENTED_SVELTE.exists(), "Segmented.svelte existiert noch nicht."
    content = SEGMENTED_SVELTE.read_text()
    assert 'data-active' in content, (
        "Segmented.svelte setzt kein data-active Attribut. "
        "Benötigt für CSS-Selektor [data-slot='segmented-item'][data-active='true']."
    )


# ---------------------------------------------------------------------------
# app.css: Segmented-CSS-Block muss vorhanden sein
# ---------------------------------------------------------------------------

def test_app_css_has_segmented_slot():
    """
    app.css muss [data-slot='segmented'] CSS-Block enthalten.
    MUSS ROT sein: Block existiert noch nicht.
    """
    content = APP_CSS.read_text()
    assert '[data-slot="segmented"]' in content, (
        "app.css enthält keinen [data-slot='segmented'] CSS-Block. "
        "Muss als Teil von Issue #285 hinzugefügt werden."
    )


def test_app_css_has_segmented_item_slot():
    """
    app.css muss [data-slot='segmented-item'] CSS-Block enthalten.
    MUSS ROT sein: Block existiert noch nicht.
    """
    content = APP_CSS.read_text()
    assert '[data-slot="segmented-item"]' in content, (
        "app.css enthält keinen [data-slot='segmented-item'] CSS-Block. "
        "Items brauchen diesen Selektor für aktiven Zustand."
    )


# ---------------------------------------------------------------------------
# Issue #345: Die Tests gegen den gelöschten EditWeatherSection.svelte
# (test_ac4a/test_ac4b/test_ac3_no_hover_bg_muted/test_ac5_testids_preserved/
# test_edit_weather_section_imports_segmented) wurden entfernt. Die
# Brand-Token-Compliance-Absicht für die neue read-only WeatherSummaryCard
# wird durch die TypeScript-Tests in
# frontend/src/lib/components/edit/weatherSummary.test.ts sowie die
# bestehende AP-007-/Hex-Drift-Guard-Suite abgedeckt; ein Python-Strukturtest
# auf WeatherSummaryCard.svelte ist hier bewusst NICHT ergänzt, weil
# WeatherSummaryCard rein Brand-Token-basiert (var(--g-*), keine Hex,
# keine verbotenen Tailwind-Klassen) implementiert ist.
# ---------------------------------------------------------------------------
