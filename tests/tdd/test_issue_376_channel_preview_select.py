"""
TDD RED Tests — Issue #376: ChannelPreviewBlock auf Select.svelte migrieren

SPEC: docs/specs/modules/issue_376_channel_preview_select.md
MANIFEST: docs/specs/tests/issue_376_channel_preview_select_tests.md

Hintergrund:
  Mit #365 wurde die mobile Kanal-Auswahl in ChannelPreviewBlock.svelte als
  natives <select> eingeführt. Das verletzt die #278-Regel ("native <select>
  nur in Select.svelte") und macht test_ac4_no_native_selects_outside_component
  rot → blockiert jeden sauberen Backend-Commit über das Pre-Commit-Gate.

RED-Zustand (jetzt):
  - ChannelPreviewBlock.svelte enthält ein natives <select> → AC-1/AC-5 FAIL
  - Kein Import von Select aus $lib/components/ui/select → AC-1-Import FAIL
  - data-testid sitzt auf nativem <select>, nicht auf <Select> → AC-3 FAIL
  - Kein scoped :global(.gz-select select)-iOS-Guard → AC-4 FAIL

Reine statische Datei-Inhaltsprüfungen (Stil wie test_issue_278_form_controls.py).
Keine Mocks, keine API-Calls.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

CHANNEL_PREVIEW_BLOCK = (
    FRONTEND_SRC / "lib" / "components" / "trip-detail" / "ChannelPreviewBlock.svelte"
)
TESTID = "channel-preview-mobile-select"


# ---------------------------------------------------------------------------
# AC-1 — Kein natives <select> mehr in ChannelPreviewBlock
# ---------------------------------------------------------------------------


def test_ac1_no_native_select_in_channel_preview_block():
    """
    GIVEN: ChannelPreviewBlock.svelte
    WHEN:  der Datei-Inhalt nach einem nativen <select-Tag durchsucht wird
    THEN:  es darf KEIN natives <select> mehr vorkommen (RED: enthält <select>)
    """
    assert CHANNEL_PREVIEW_BLOCK.exists(), f"Datei fehlt: {CHANNEL_PREVIEW_BLOCK}"
    content = CHANNEL_PREVIEW_BLOCK.read_text()
    assert not re.search(r"<select\b", content), (
        "ChannelPreviewBlock.svelte enthält noch ein natives <select> "
        "(muss durch <Select> ersetzt werden)"
    )


def test_ac1_imports_select_component():
    """
    GIVEN: ChannelPreviewBlock.svelte
    WHEN:  der <script>-Block gelesen wird
    THEN:  Select muss aus $lib/components/ui/select importiert sein (RED: kein Import)
    """
    content = CHANNEL_PREVIEW_BLOCK.read_text()
    assert "ui/select" in content, (
        "ChannelPreviewBlock.svelte importiert Select nicht aus $lib/components/ui/select"
    )


# ---------------------------------------------------------------------------
# AC-3 — data-testid bleibt erhalten, jetzt auf <Select>
# ---------------------------------------------------------------------------


def test_ac3_testid_on_select_component():
    """
    GIVEN: ChannelPreviewBlock.svelte
    WHEN:  nach dem Mobile-Dropdown-Element gesucht wird
    THEN:  data-testid="channel-preview-mobile-select" muss auf einem <Select>-Tag
           stehen (RED: sitzt aktuell auf nativem <select>)
    """
    content = CHANNEL_PREVIEW_BLOCK.read_text()
    # Das öffnende <Select ...>-Tag, das die testid trägt
    select_tag = re.search(r"<Select\b[^>]*>", content, re.DOTALL)
    assert select_tag, "Kein <Select>-Tag in ChannelPreviewBlock.svelte gefunden"
    assert TESTID in select_tag.group(0), (
        f'data-testid="{TESTID}" steht nicht auf dem <Select>-Tag '
        "(Playwright-Selektor-Kompatibilität)"
    )


# ---------------------------------------------------------------------------
# AC-4 — Scoped iOS-Zoom-Guard (#272) für das migrierte Dropdown
# ---------------------------------------------------------------------------


def test_ac4_scoped_ios_zoom_guard_present():
    """
    GIVEN: ChannelPreviewBlock.svelte nach der Migration
    WHEN:  der <style>-Block gelesen wird
    THEN:  ein scoped Override .ch-select :global(.gz-select select) muss font-size:16px
           setzen, damit Select.sveltes 13px auf iOS nicht zum Auto-Zoom führt (#272)
           (RED: kein :global(.gz-select select)-Override vorhanden)
    """
    content = CHANNEL_PREVIEW_BLOCK.read_text()
    assert ":global(.gz-select select)" in content, (
        "Kein scoped Override .ch-select :global(.gz-select select) gefunden "
        "(iOS-Zoom-Guard #272 für das migrierte Dropdown)"
    )
    # 16px muss im Override-Kontext gesetzt sein
    guard = re.search(
        r":global\(\.gz-select select\)\s*\{[^}]*font-size:\s*16px",
        content,
        re.DOTALL,
    )
    assert guard, (
        "Der scoped Override setzt keine font-size: 16px "
        "(überschreibt --g-text-sm=13px aus Select.svelte nicht)"
    )


# ---------------------------------------------------------------------------
# AC-5 — #278-Regel app-weit erfüllt (Gate entsperrt)
# ---------------------------------------------------------------------------


def _svelte_files_with_native_select() -> list[Path]:
    """Alle .svelte-Dateien mit nativem <select>, identisch zu #278 test_ac4."""
    result = subprocess.run(
        ["rg", "--glob=*.svelte", "-l", r"<select\b", str(FRONTEND_SRC)],
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def test_ac5_no_native_selects_outside_component():
    """
    GIVEN: das Projekt-Repository
    WHEN:  rg '<select\\b' über frontend/src läuft
    THEN:  Treffer NUR in Select.svelte — ChannelPreviewBlock darf nicht mehr
           auftauchen (RED: ChannelPreviewBlock ist noch in der Liste)
    """
    offenders = [
        f for f in _svelte_files_with_native_select() if f.name != "Select.svelte"
    ]
    assert not offenders, (
        "Noch Datei(en) mit nativem <select> außerhalb Select.svelte:\n"
        + "\n".join(f"    - {p}" for p in offenders)
    )
