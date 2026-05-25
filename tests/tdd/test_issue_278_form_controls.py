"""
TDD RED Tests — Issue #278: Gebrandete Form-Controls (Checkbox & Select)

SPEC: docs/specs/modules/issue_278_form_controls.md

Hintergrund:
  Alle nativen <input type="checkbox"> und <select> in der App rendern als
  system-blaues OS-Default (iOS/macOS). Zwei neue Svelte-5-Primitive
  (Checkbox.svelte, Select.svelte) ersetzen alle nativen Elemente.

RED-Zustand (jetzt):
  - Checkbox.svelte und Select.svelte existieren nicht → Datei-Tests FAIL
  - 35+ native Checkboxen in 11 Dateien → AC-3 FAIL
  - ~20 native Selects in 10 Dateien → AC-4 FAIL
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

CHECKBOX_SVELTE = FRONTEND_SRC / "lib" / "components" / "ui" / "checkbox" / "Checkbox.svelte"
CHECKBOX_INDEX = FRONTEND_SRC / "lib" / "components" / "ui" / "checkbox" / "index.ts"
SELECT_SVELTE = FRONTEND_SRC / "lib" / "components" / "ui" / "select" / "Select.svelte"
SELECT_INDEX = FRONTEND_SRC / "lib" / "components" / "ui" / "select" / "index.ts"


# ---------------------------------------------------------------------------
# AC-1 — Checkbox-Komponente existiert
# ---------------------------------------------------------------------------


def test_ac1_checkbox_svelte_exists():
    """
    GIVEN: das Projekt-Repository
    WHEN:  nach frontend/src/lib/components/ui/checkbox/Checkbox.svelte gesucht wird
    THEN:  die Datei muss existieren (fehlt im RED-Zustand)
    """
    assert CHECKBOX_SVELTE.exists(), (
        f"Checkbox.svelte nicht gefunden: {CHECKBOX_SVELTE}"
    )


def test_ac1_checkbox_index_exists():
    """
    GIVEN: das Projekt-Repository
    WHEN:  nach frontend/src/lib/components/ui/checkbox/index.ts gesucht wird
    THEN:  die Datei muss existieren und den Export enthalten
    """
    assert CHECKBOX_INDEX.exists(), f"checkbox/index.ts nicht gefunden: {CHECKBOX_INDEX}"
    content = CHECKBOX_INDEX.read_text()
    assert "Checkbox" in content, "checkbox/index.ts exportiert keine Checkbox"


def test_ac1_checkbox_has_bindable_checked():
    """
    GIVEN: Checkbox.svelte existiert
    WHEN:  der Svelte-Script-Block gelesen wird
    THEN:  checked = $bindable(false) muss vorhanden sein (Svelte-5-API)
    """
    assert CHECKBOX_SVELTE.exists(), "Checkbox.svelte existiert nicht (RED)"
    content = CHECKBOX_SVELTE.read_text()
    assert "$bindable" in content, (
        "Checkbox.svelte enthält kein $bindable() — Svelte-5-API fehlt"
    )
    assert "checked" in content, "Checkbox.svelte hat keine checked-Prop"


def test_ac1_checkbox_has_rest_props():
    """
    GIVEN: Checkbox.svelte existiert
    WHEN:  die Props-Destrukturierung gelesen wird
    THEN:  ...restProps muss auf dem nativen <input> landen (für data-testid)
    """
    assert CHECKBOX_SVELTE.exists(), "Checkbox.svelte existiert nicht (RED)"
    content = CHECKBOX_SVELTE.read_text()
    assert "...rest" in content, (
        "Checkbox.svelte leitet keine restProps weiter — data-testid wird nicht an input weitergegeben"
    )


def test_ac1_checkbox_native_input_is_opacity_zero():
    """
    GIVEN: Checkbox.svelte mit nativem <input type="checkbox">
    WHEN:  der <style>-Block gelesen wird
    THEN:  input muss opacity: 0 haben und KEIN pointer-events: none
           (Playwright braucht Events auf dem nativen Input)
    """
    assert CHECKBOX_SVELTE.exists(), "Checkbox.svelte existiert nicht (RED)"
    content = CHECKBOX_SVELTE.read_text()
    assert "opacity: 0" in content or "opacity:0" in content, (
        "Checkbox.svelte: nativer input ist nicht mit opacity:0 versteckt"
    )
    assert "pointer-events: none" not in content or (
        content.count("pointer-events: none") == 1
        and "chevron" in content.lower()
    ), (
        "Checkbox.svelte hat pointer-events: none — Playwright-Clicks würden brechen!"
    )


def test_ac1_checkbox_checked_state_uses_ink_token():
    """
    GIVEN: Checkbox.svelte mit Design-Token-CSS
    WHEN:  der <style>-Block auf checked-Zustand geprüft wird
    THEN:  background muss var(--g-ink) sein — kein system-blau, kein Hardcode
    """
    assert CHECKBOX_SVELTE.exists(), "Checkbox.svelte existiert nicht (RED)"
    content = CHECKBOX_SVELTE.read_text()
    assert "--g-ink" in content, (
        "Checkbox.svelte verwendet nicht --g-ink als checked-Hintergrundfarbe"
    )


def test_ac1_checkbox_focus_ring_uses_accent_token():
    """
    GIVEN: Checkbox.svelte mit Focus-Ring
    WHEN:  der <style>-Block auf focus-visible geprüft wird
    THEN:  outline muss var(--g-accent) verwenden
    """
    assert CHECKBOX_SVELTE.exists(), "Checkbox.svelte existiert nicht (RED)"
    content = CHECKBOX_SVELTE.read_text()
    assert "--g-accent" in content, (
        "Checkbox.svelte enthält keinen --g-accent Focus-Ring"
    )


# ---------------------------------------------------------------------------
# AC-2 — Select-Komponente existiert
# ---------------------------------------------------------------------------


def test_ac2_select_svelte_exists():
    """
    GIVEN: das Projekt-Repository
    WHEN:  nach frontend/src/lib/components/ui/select/Select.svelte gesucht wird
    THEN:  die Datei muss existieren (fehlt im RED-Zustand)
    """
    assert SELECT_SVELTE.exists(), f"Select.svelte nicht gefunden: {SELECT_SVELTE}"


def test_ac2_select_index_exists():
    """
    GIVEN: das Projekt-Repository
    WHEN:  nach frontend/src/lib/components/ui/select/index.ts gesucht wird
    THEN:  die Datei muss existieren und den Export enthalten
    """
    assert SELECT_INDEX.exists(), f"select/index.ts nicht gefunden: {SELECT_INDEX}"
    content = SELECT_INDEX.read_text()
    assert "Select" in content, "select/index.ts exportiert kein Select"


def test_ac2_select_has_bindable_value():
    """
    GIVEN: Select.svelte existiert
    WHEN:  der Svelte-Script-Block gelesen wird
    THEN:  value = $bindable() muss vorhanden sein (für bind:value Support)
    """
    assert SELECT_SVELTE.exists(), "Select.svelte existiert nicht (RED)"
    content = SELECT_SVELTE.read_text()
    assert "$bindable" in content, (
        "Select.svelte enthält kein $bindable() — bind:value funktioniert nicht"
    )


def test_ac2_select_has_appearance_none():
    """
    GIVEN: Select.svelte mit nativem <select>
    WHEN:  der <style>-Block gelesen wird
    THEN:  appearance: none muss auf dem nativen <select> gesetzt sein
    """
    assert SELECT_SVELTE.exists(), "Select.svelte existiert nicht (RED)"
    content = SELECT_SVELTE.read_text()
    assert "appearance: none" in content or "-webkit-appearance: none" in content, (
        "Select.svelte hat kein appearance: none — System-Dropdown-Pfeil bleibt sichtbar"
    )


def test_ac2_select_has_custom_chevron():
    """
    GIVEN: Select.svelte mit appearance: none
    WHEN:  das Markup gelesen wird
    THEN:  ein SVG-Chevron-Element muss vorhanden sein
    """
    assert SELECT_SVELTE.exists(), "Select.svelte existiert nicht (RED)"
    content = SELECT_SVELTE.read_text()
    assert "<svg" in content, (
        "Select.svelte enthält kein SVG für den Custom-Chevron"
    )


def test_ac2_select_uses_design_tokens():
    """
    GIVEN: Select.svelte mit Design-Token-CSS
    WHEN:  der <style>-Block gelesen wird
    THEN:  --g-ink-faint (border), --g-paper (background), --g-radius-sm müssen verwendet werden
    """
    assert SELECT_SVELTE.exists(), "Select.svelte existiert nicht (RED)"
    content = SELECT_SVELTE.read_text()
    assert "--g-ink-faint" in content, "Select.svelte verwendet nicht --g-ink-faint als border-color"
    assert "--g-paper" in content, "Select.svelte verwendet nicht --g-paper als background"
    assert "--g-radius-sm" in content, "Select.svelte verwendet nicht --g-radius-sm"


# ---------------------------------------------------------------------------
# AC-3 — Keine nativen Checkboxen außerhalb Checkbox.svelte
# ---------------------------------------------------------------------------


def _find_checkbox_files() -> list[Path]:
    """Gibt alle .svelte-Dateien zurück, die type="checkbox" enthalten."""
    result = subprocess.run(
        ["rg", "--glob=*.svelte", "-l", 'type="checkbox"', str(FRONTEND_SRC)],
        capture_output=True, text=True
    )
    if not result.stdout.strip():
        return []
    return [Path(p) for p in result.stdout.strip().splitlines()]


def test_ac3_no_native_checkboxes_outside_component():
    """
    GIVEN: vollständig migrierte Codebase
    WHEN:  rg 'type="checkbox"' frontend/src --glob='*.svelte' ausgeführt wird
    THEN:  Treffer NUR in Checkbox.svelte — keine anderen Dateien

    Im RED-Zustand: ~11 Dateien mit nativen Checkboxen → FAIL
    """
    checkbox_files = _find_checkbox_files()
    non_component_files = [
        f for f in checkbox_files
        if f.name != "Checkbox.svelte"
    ]
    assert not non_component_files, (
        f"Noch {len(non_component_files)} Datei(en) mit nativen Checkboxen außerhalb Checkbox.svelte:\n"
        + "\n".join(f"  - {f.relative_to(REPO_ROOT)}" for f in non_component_files)
    )


# ---------------------------------------------------------------------------
# AC-4 — Keine nativen Selects außerhalb Select.svelte
# ---------------------------------------------------------------------------


def _find_select_files() -> list[Path]:
    """Gibt alle .svelte-Dateien zurück, die <select enthält."""
    result = subprocess.run(
        ["rg", "--glob=*.svelte", "-l", r"<select\b", str(FRONTEND_SRC)],
        capture_output=True, text=True
    )
    if not result.stdout.strip():
        return []
    return [Path(p) for p in result.stdout.strip().splitlines()]


def test_ac4_no_native_selects_outside_component():
    """
    GIVEN: vollständig migrierte Codebase
    WHEN:  rg '<select\\b' frontend/src --glob='*.svelte' ausgeführt wird
    THEN:  Treffer NUR in Select.svelte — keine anderen Dateien

    Im RED-Zustand: ~10 Dateien mit nativen Selects → FAIL
    """
    select_files = _find_select_files()
    non_component_files = [
        f for f in select_files
        if f.name != "Select.svelte"
    ]
    assert not non_component_files, (
        f"Noch {len(non_component_files)} Datei(en) mit nativen Selects außerhalb Select.svelte:\n"
        + "\n".join(f"  - {f.relative_to(REPO_ROOT)}" for f in non_component_files)
    )


# ---------------------------------------------------------------------------
# AC-6 — data-testid landet auf nativem Element (Playwright-Kompatibilität)
# ---------------------------------------------------------------------------


def test_ac6_checkbox_restprops_on_native_input():
    """
    GIVEN: Checkbox.svelte mit restProps
    WHEN:  der Markup-Bereich gelesen wird
    THEN:  {...rest} muss auf dem nativen <input> stehen (data-testid-Forwarding)
    """
    assert CHECKBOX_SVELTE.exists(), "Checkbox.svelte existiert nicht (RED)"
    content = CHECKBOX_SVELTE.read_text()

    input_block = re.search(r'<input[^>]+>', content, re.DOTALL)
    assert input_block, "Checkbox.svelte enthält keinen <input>-Tag"

    input_html = input_block.group(0)
    has_rest = "{...rest" in input_html
    assert has_rest, (
        f"restProps nicht auf nativem <input> in Checkbox.svelte gefunden.\n"
        f"Input-Tag: {input_html[:200]}"
    )


def test_ac6_select_restprops_on_native_select():
    """
    GIVEN: Select.svelte mit restProps
    WHEN:  der Markup-Bereich gelesen wird
    THEN:  {...rest} muss auf dem nativen <select> stehen (data-testid-Forwarding)
    """
    assert SELECT_SVELTE.exists(), "Select.svelte existiert nicht (RED)"
    content = SELECT_SVELTE.read_text()

    select_block = re.search(r'<select[^>]+>', content, re.DOTALL)
    assert select_block, "Select.svelte enthält keinen <select>-Tag"

    select_html = select_block.group(0)
    has_rest = "{...rest" in select_html
    assert has_rest, (
        f"restProps nicht auf nativem <select> in Select.svelte gefunden.\n"
        f"Select-Tag: {select_html[:200]}"
    )


# ---------------------------------------------------------------------------
# AC-8 — Selects zeigen keinen System-Dropdown-Pfeil
# ---------------------------------------------------------------------------


def test_ac8_select_native_has_appearance_none_not_only_vendor():
    """
    GIVEN: Select.svelte mit CSS
    WHEN:  der <style>-Block auf appearance geprüft wird
    THEN:  appearance: none (ohne Präfix oder mit -webkit-) muss vorhanden sein
    """
    assert SELECT_SVELTE.exists(), "Select.svelte existiert nicht (RED)"
    content = SELECT_SVELTE.read_text()

    has_appearance = bool(
        re.search(r'appearance\s*:\s*none', content)
        or re.search(r'-webkit-appearance\s*:\s*none', content)
    )
    assert has_appearance, (
        "Select.svelte hat kein 'appearance: none' — System-Dropdown-Pfeil bleibt sichtbar"
    )


# ---------------------------------------------------------------------------
# Migrations-Vollständigkeit: Imports in migrierten Dateien
# ---------------------------------------------------------------------------


# Issue #345: EditWeatherSection.svelte gelöscht (Wetter-Editor-Konsolidierung)
# und aus beiden Listen entfernt. Die read-only WeatherSummaryCard.svelte ist
# KEIN Ersatz hier — sie nutzt weder Checkbox noch Select.
_EXPECTED_CHECKBOX_IMPORTS = [
    FRONTEND_SRC / "lib" / "components" / "edit" / "EditReportConfigSection.svelte",
    FRONTEND_SRC / "lib" / "components" / "alert-rules-editor" / "AlertRuleRow.svelte",
    FRONTEND_SRC / "lib" / "components" / "compare" / "LocationsRail.svelte",
    FRONTEND_SRC / "lib" / "components" / "SubscriptionForm.svelte",
]

_EXPECTED_SELECT_IMPORTS = [
    FRONTEND_SRC / "lib" / "components" / "alert-rules-editor" / "AlertRuleRow.svelte",
    FRONTEND_SRC / "lib" / "components" / "alerts-tab" / "AlertMetricRow.svelte",
    FRONTEND_SRC / "lib" / "components" / "compare" / "PresetHeader.svelte",
    FRONTEND_SRC / "lib" / "components" / "SubscriptionForm.svelte",
]


def test_key_files_import_checkbox():
    """
    GIVEN: migrierte Dateien mit der größten Checkbox-Dichte
    WHEN:  ihre Script-Blöcke gelesen werden
    THEN:  jede muss Checkbox aus $lib/components/ui/checkbox importieren

    Im RED-Zustand: kein Import vorhanden → FAIL
    """
    missing = []
    for path in _EXPECTED_CHECKBOX_IMPORTS:
        if not path.exists():
            missing.append(f"{path.relative_to(REPO_ROOT)} (Datei fehlt!)")
            continue
        content = path.read_text()
        if "ui/checkbox" not in content:
            missing.append(str(path.relative_to(REPO_ROOT)))

    assert not missing, (
        "Folgende Dateien importieren Checkbox noch nicht:\n"
        + "\n".join(f"  - {m}" for m in missing)
    )


def test_key_files_import_select():
    """
    GIVEN: migrierte Dateien mit der größten Select-Dichte
    WHEN:  ihre Script-Blöcke gelesen werden
    THEN:  jede muss Select aus $lib/components/ui/select importieren

    Im RED-Zustand: kein Import vorhanden → FAIL
    """
    missing = []
    for path in _EXPECTED_SELECT_IMPORTS:
        if not path.exists():
            missing.append(f"{path.relative_to(REPO_ROOT)} (Datei fehlt!)")
            continue
        content = path.read_text()
        if "ui/select" not in content:
            missing.append(str(path.relative_to(REPO_ROOT)))

    assert not missing, (
        "Folgende Dateien importieren Select noch nicht:\n"
        + "\n".join(f"  - {m}" for m in missing)
    )
