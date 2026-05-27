"""
TDD RED — Issue #403: TripTabs Tab-Leiste auf Segmented-Atom migrieren.

Alle Tests MÜSSEN vor der Implementierung FEHLSCHLAGEN.
Spec: docs/specs/modules/issue_403_triptabs_segmented.md
"""

import os
import re
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

TRIPTABS = os.path.join(PROJECT_ROOT, 'frontend/src/lib/components/trip-detail/TripTabs.svelte')
ATOMS_INDEX = os.path.join(PROJECT_ROOT, 'frontend/src/lib/components/atoms/index.ts')
ATOMS_TEST = os.path.join(PROJECT_ROOT, 'frontend/src/lib/components/atoms/atoms.test.ts')
SEGMENTED_ATOM = os.path.join(PROJECT_ROOT, 'frontend/src/lib/components/atoms/Segmented.svelte')
SEGMENTED_UI = os.path.join(PROJECT_ROOT, 'frontend/src/lib/components/ui/segmented/Segmented.svelte')


def read(path: str) -> str:
    with open(path, encoding='utf-8') as f:
        return f.read()


class TestAC1_NoBitsUiInTripTabs:
    """AC-1: TripTabs.svelte darf kein bits-ui mehr importieren."""

    def test_no_bits_ui_import(self):
        src = read(TRIPTABS)
        assert 'bits-ui' not in src, (
            "FAIL (erwartet): TripTabs.svelte importiert noch bits-ui — Migration noch nicht erfolgt."
        )

    def test_uses_segmented_from_atoms(self):
        src = read(TRIPTABS)
        assert '$lib/components/atoms' in src, (
            "FAIL (erwartet): TripTabs.svelte importiert Segmented noch nicht aus $lib/components/atoms."
        )


class TestAC2_StructuralMigration:
    """AC-2: Tab-Wechsel über Segmented-Atom — strukturelle Voraussetzung."""

    def test_no_tabs_root_in_markup(self):
        src = read(TRIPTABS)
        assert '<Tabs.Root' not in src, (
            "FAIL (erwartet): TripTabs.svelte enthält noch <Tabs.Root> — bits-ui nicht entfernt."
        )

    def test_no_tabs_content_in_markup(self):
        src = read(TRIPTABS)
        assert '<Tabs.Content' not in src, (
            "FAIL (erwartet): TripTabs.svelte enthält noch <Tabs.Content> — panels nicht umgestellt."
        )

    def test_has_segmented_component_in_markup(self):
        src = read(TRIPTABS)
        assert '<Segmented' in src, (
            "FAIL (erwartet): TripTabs.svelte nutzt <Segmented> noch nicht im Markup."
        )


class TestAC3_BadgeConditionInDerived:
    """AC-3: Badge-Zähler werden via segmentedOptions derived array übergeben."""

    def test_has_segmented_options_variable(self):
        src = read(TRIPTABS)
        assert 'segmentedOptions' in src, (
            "FAIL (erwartet): TripTabs.svelte hat noch kein derived segmentedOptions Array."
        )

    def test_badge_condition_uses_gte_1(self):
        src = read(TRIPTABS)
        # Der Badge-Guard muss (badges[X] ?? 0) >= 1 verwenden
        assert re.search(r'badges\[[^\]]+\]\s*\?\?\s*0\)\s*>=\s*1', src), (
            "FAIL (erwartet): segmentedOptions Badge-Bedingung fehlt: (badges[X] ?? 0) >= 1"
        )

    def test_no_not_undefined_badge_pattern(self):
        src = read(TRIPTABS)
        assert not re.search(r'badges\[[^\]]+\]\s*!==\s*undefined', src), (
            "badges[X] !== undefined ist verboten — (badges[X] ?? 0) >= 1 verwenden."
        )


class TestAC4_CssSelectors:
    """AC-4: CSS-Selektoren in TripTabs.svelte targeten data-slot Attribute statt Klassen."""

    def test_has_segmented_item_css_selector(self):
        src = read(TRIPTABS)
        assert 'segmented-item' in src, (
            "FAIL (erwartet): TripTabs <style> enthält noch keinen [data-slot='segmented-item']-Selektor."
        )

    def test_no_class_trip_tab_trigger(self):
        src = read(TRIPTABS)
        assert '.trip-tab-trigger' not in src, (
            "FAIL (erwartet): CSS-Klasse .trip-tab-trigger noch vorhanden — auf data-slot migrieren."
        )

    def test_no_class_trip_tabs_list(self):
        src = read(TRIPTABS)
        assert '.trip-tabs-list' not in src, (
            "FAIL (erwartet): CSS-Klasse .trip-tabs-list noch vorhanden — auf data-slot migrieren."
        )


class TestAC5_SegmentedInAtoms:
    """AC-5: Segmented als 14. Atom im Barrel und als Wrapper-Datei."""

    def test_segmented_exported_from_atoms_index(self):
        src = read(ATOMS_INDEX)
        assert 'Segmented' in src, (
            "FAIL (erwartet): atoms/index.ts exportiert Segmented noch nicht."
        )

    def test_segmented_atom_file_exists(self):
        assert os.path.exists(SEGMENTED_ATOM), (
            f"FAIL (erwartet): atoms/Segmented.svelte existiert noch nicht ({SEGMENTED_ATOM})."
        )

    def test_atoms_test_references_14(self):
        src = read(ATOMS_TEST)
        assert '14' in src, (
            "FAIL (erwartet): atoms.test.ts erwartet noch 13 Atome — muss auf 14 erhöht werden."
        )

    def test_atoms_test_mentions_segmented(self):
        src = read(ATOMS_TEST)
        assert 'Segmented' in src, (
            "FAIL (erwartet): atoms.test.ts erwähnt Segmented noch nicht."
        )


class TestSegmentedBadgeSupport:
    """ui/segmented/Segmented.svelte muss badge? im Option-Typ unterstützen."""

    def test_option_type_has_badge(self):
        src = read(SEGMENTED_UI)
        assert 'badge' in src, (
            "FAIL (erwartet): Segmented.svelte definiert badge im Option-Typ noch nicht."
        )

    def test_renders_segmented_badge_slot(self):
        src = read(SEGMENTED_UI)
        assert 'segmented-badge' in src, (
            "FAIL (erwartet): Segmented.svelte rendert data-slot='segmented-badge' noch nicht."
        )
