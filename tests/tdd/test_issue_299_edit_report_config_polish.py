"""
TDD RED — Issue #299: EditReportConfigSection UI-Polish
Spec: docs/specs/modules/issue_299_edit_report_config_section_polish.md

Diese Tests prüfen strukturelle Eigenschaften der Svelte-Quelldatei.
Sie MÜSSEN rot sein vor der Implementierung — die Brand-Token-Klassen,
Card.Root-Wrapper und Ghost-Btn existieren in der Datei noch nicht.

KEINE MOCKS — liest echte Dateisystem-Inhalte.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
COMPONENT = REPO_ROOT / "frontend/src/lib/components/edit/EditReportConfigSection.svelte"


# ---------------------------------------------------------------------------
# AC-1: Quick-Chips — Brand-Token statt Raw-Tailwind
# ---------------------------------------------------------------------------

def test_ac1_quick_chips_no_raw_tailwind_hover_bg_accent():
    """
    AC-1: Kein 'hover:bg-accent' mehr auf Quick-Chip-Buttons.
    MUSS ROT sein: 'hover:bg-accent' ist in 4 Buttons noch vorhanden.
    """
    content = COMPONENT.read_text()
    matches = re.findall(r'hover:bg-accent', content)
    assert len(matches) == 0, (
        f"EditReportConfigSection.svelte enthält noch {len(matches)} Vorkommen "
        "von 'hover:bg-accent'. Muss durch '.g-quick-chip' Brand-Token-Styling "
        "ersetzt werden (Issue #299 AC-1)."
    )


def test_ac1_quick_chips_have_g_quick_chip_class():
    """
    AC-1: Alle Quick-Chip-Buttons tragen die Klasse 'g-quick-chip'.
    MUSS ROT sein: '.g-quick-chip' ist noch nicht im Template vorhanden.
    """
    content = COMPONENT.read_text()
    # Erwarte genau 4 Quick-Chip-Buttons (2 × Morgen, 2 × Abend)
    matches = re.findall(r'g-quick-chip', content)
    assert len(matches) >= 4, (
        f"EditReportConfigSection.svelte hat {len(matches)} Vorkommen von "
        "'g-quick-chip' — erwartet mindestens 4 (je 2 für Morgen und Abend). "
        "Die Klasse muss im Template und im <style>-Block definiert sein (Issue #299 AC-1)."
    )


def test_ac1_style_block_defines_g_quick_chip():
    """
    AC-1: Der <style>-Block muss '.g-quick-chip' mit Brand-Token definieren.
    MUSS ROT sein: <style>-Block mit g-quick-chip existiert noch nicht.
    """
    content = COMPONENT.read_text()
    assert '.g-quick-chip' in content, (
        "EditReportConfigSection.svelte hat keinen <style>-Block mit '.g-quick-chip'. "
        "CSS-Klasse muss mit var(--g-radius-pill) und var(--g-font-data) definiert werden "
        "(Issue #299 AC-1)."
    )
    assert 'g-radius-pill' in content, (
        "Der <style>-Block enthält kein 'g-radius-pill'. Die Pill-Form "
        "ist Pflicht für Quick-Chips gemäß Design-System (Issue #299 AC-1)."
    )


# ---------------------------------------------------------------------------
# AC-2: Channel-Hint-Links — Accent-Orange statt Browser-Blau
# ---------------------------------------------------------------------------

def test_ac2_hint_links_no_hover_text_primary():
    """
    AC-2: Kein 'hover:text-primary' auf Channel-Hint-Links.
    MUSS ROT sein: 'hover:text-primary' ist in 3 Links noch vorhanden.
    """
    content = COMPONENT.read_text()
    matches = re.findall(r'hover:text-primary', content)
    assert len(matches) == 0, (
        f"EditReportConfigSection.svelte enthält noch {len(matches)} Vorkommen "
        "von 'hover:text-primary'. Channel-Hint-Links müssen auf "
        "style=\"color:var(--g-accent)...\" umgestellt werden (Issue #299 AC-2)."
    )


def test_ac2_hint_links_use_g_accent():
    """
    AC-2: Channel-Hint-Links nutzen var(--g-accent) als Inline-Style.
    MUSS ROT sein: 'g-accent' kommt in Hint-Link-Kontext noch nicht vor.
    """
    content = COMPONENT.read_text()
    # Mindestens 3 Vorkommen (email, signal, telegram hint links)
    matches = re.findall(r'g-accent', content)
    assert len(matches) >= 3, (
        f"EditReportConfigSection.svelte hat nur {len(matches)} Vorkommen von 'g-accent'. "
        "Alle 3 Channel-Hint-Links (email, signal, telegram) müssen "
        "style=\"color:var(--g-accent)...\" erhalten (Issue #299 AC-2)."
    )


# ---------------------------------------------------------------------------
# AC-3: Advanced-Toggle — Ghost-Btn statt Plain-Button
# ---------------------------------------------------------------------------

def test_ac3_advanced_toggle_no_plain_button_with_text_primary():
    """
    AC-3: Der Advanced-Toggle darf kein 'text-primary hover:underline' mehr haben.
    MUSS ROT sein: Plain-Button mit diesen Klassen ist noch vorhanden.
    """
    content = COMPONENT.read_text()
    matches = re.findall(r'font-semibold text-primary hover:underline', content)
    assert len(matches) == 0, (
        f"EditReportConfigSection.svelte enthält noch {len(matches)} Vorkommen "
        "von 'font-semibold text-primary hover:underline'. Der Advanced-Toggle-Button "
        "muss durch <Btn variant=\"ghost\" size=\"sm\"> ersetzt werden (Issue #299 AC-3)."
    )


def test_ac3_advanced_toggle_imports_btn():
    """
    AC-3: Btn muss importiert sein für den Advanced-Toggle.
    MUSS ROT sein: Btn-Import ist noch nicht vorhanden.
    """
    content = COMPONENT.read_text()
    # Akzeptiert sowohl atoms/-Barrel (bevorzugt seit #470) als auch alten ui/-Pfad
    has_btn = (
        "from '$lib/components/atoms'" in content
        or 'from "$lib/components/atoms"' in content
        or "from '$lib/components/ui/btn" in content
        or 'from "$lib/components/ui/btn' in content
    )
    assert has_btn, (
        "EditReportConfigSection.svelte importiert Btn noch nicht. "
        "Import muss aus $lib/components/atoms oder $lib/components/ui/btn kommen."
    )


def test_ac3_advanced_toggle_imports_chevron_down():
    """
    AC-3+AC-4: ChevronDown muss importiert sein.
    MUSS ROT sein: ChevronDown-Import ist noch nicht vorhanden.
    """
    content = COMPONENT.read_text()
    assert 'chevron-down' in content or 'ChevronDown' in content, (
        "EditReportConfigSection.svelte importiert ChevronDown noch nicht. "
        "Import aus '@lucide/svelte/icons/chevron-down' muss ergänzt werden "
        "(Issue #299 AC-3, AC-4)."
    )


# ---------------------------------------------------------------------------
# AC-5: Wind-Exposition — g-num-with-unit Wrapper + m-Suffix
# ---------------------------------------------------------------------------

def test_ac5_wind_exposition_has_g_num_with_unit_wrapper():
    """
    AC-5: Wind-Exposition-Input muss von g-num-with-unit-Label umschlossen sein.
    MUSS ROT sein: g-num-with-unit ist noch nicht vorhanden.
    """
    content = COMPONENT.read_text()
    assert 'g-num-with-unit' in content, (
        "EditReportConfigSection.svelte enthält kein 'g-num-with-unit'. "
        "Der Wind-Exposition-Input muss in <label class=\"g-num-with-unit ...\"> "
        "eingeschlossen werden (Issue #299 AC-5)."
    )


def test_ac5_wind_exposition_has_m_unit_span():
    """
    AC-5: Ein <span class='g-num-unit'> mit 'm' muss als Einheitenbeschriftung vorhanden sein.
    MUSS ROT sein: g-num-unit ist noch nicht vorhanden.
    """
    content = COMPONENT.read_text()
    assert 'g-num-unit' in content, (
        "EditReportConfigSection.svelte enthält kein 'g-num-unit'. "
        "Der m-Suffix-Span muss als Einheitenbeschriftung für Wind-Exposition "
        "ergänzt werden (Issue #299 AC-5)."
    )


def test_ac5_style_block_defines_g_num_unit():
    """
    AC-5: Der <style>-Block muss '.g-num-unit' und '.g-num-with-unit' definieren.
    MUSS ROT sein: <style>-Block mit diesen Klassen existiert noch nicht.
    """
    content = COMPONENT.read_text()
    assert '.g-num-unit' in content, (
        "EditReportConfigSection.svelte hat keinen <style>-Block mit '.g-num-unit'. "
        "CSS-Klasse muss spiegelbildlich zu EditStagesSection.svelte definiert werden "
        "(Issue #299 AC-5)."
    )


# ---------------------------------------------------------------------------
# AC-6: Sektions-Container — Card.Root statt section border-input
# ---------------------------------------------------------------------------

def test_ac6_no_section_with_border_input():
    """
    AC-6: Keine <section class='... border border-input ...'> mehr vorhanden.
    MUSS ROT sein: 3 solcher section-Elemente sind noch vorhanden.
    """
    content = COMPONENT.read_text()
    matches = re.findall(r'<section[^>]*border\s+border-input', content)
    assert len(matches) == 0, (
        f"EditReportConfigSection.svelte enthält noch {len(matches)} <section>-Elemente "
        "mit 'border border-input'. Alle Sektions-Container müssen zu <Card.Root> "
        "umgewandelt werden (Issue #299 AC-6)."
    )


def test_ac6_imports_card_component():
    """
    AC-6: Card muss importiert sein für die Sektions-Container.
    MUSS ROT sein: Card-Import ist noch nicht vorhanden.
    """
    content = COMPONENT.read_text()
    assert "from '$lib/components/ui/card" in content or 'from "$lib/components/ui/card' in content, (
        "EditReportConfigSection.svelte importiert Card noch nicht. "
        "import * as Card from '$lib/components/ui/card/index.js' muss ergänzt werden "
        "(Issue #299 AC-6)."
    )


def test_ac6_card_root_present_at_least_3_times():
    """
    AC-6: Mindestens 3 <Card.Root>-Elemente (Morgen, Abend, Kanäle).
    MUSS ROT sein: Card.Root ist noch nicht vorhanden.
    """
    content = COMPONENT.read_text()
    matches = re.findall(r'<Card\.Root', content)
    assert len(matches) >= 3, (
        f"EditReportConfigSection.svelte enthält nur {len(matches)} <Card.Root>-Elemente. "
        "Erwartet mindestens 3 (Morgen-, Abend- und Kanal-Sektion). "
        "Card.Root muss mit 'hover:translate-y-0 hover:shadow-none' verwendet werden "
        "(Issue #299 AC-6)."
    )


# ---------------------------------------------------------------------------
# AC-7: Zeit-Inputs — g-num-input Mono-Font
# ---------------------------------------------------------------------------

def test_ac7_morning_time_input_has_g_num_input():
    """
    AC-7: Beide Zeit-Inputs müssen Klasse 'g-num-input' haben.
    MUSS ROT sein: g-num-input ist noch nicht auf time-Inputs gesetzt.
    """
    content = COMPONENT.read_text()
    time_input_matches = re.findall(
        r'<input[^>]*type="time"[^>]*class="[^"]*g-num-input[^"]*"',
        content
    )
    assert len(time_input_matches) >= 2, (
        f"Nur {len(time_input_matches)} von 2 Zeit-Inputs haben die Klasse 'g-num-input'. "
        "Beide (report-morning-time und report-evening-time) müssen 'g-num-input' tragen "
        "für JetBrains Mono + tabular-nums (Issue #299 AC-7)."
    )


# ---------------------------------------------------------------------------
# Regression: data-testids müssen erhalten bleiben
# ---------------------------------------------------------------------------

def test_regression_all_required_testids_present():
    """
    Regression-Guard: Alle 20 data-testids aus dem E2E-Test müssen erhalten bleiben.
    Startet GREEN — darf nach Implementierung nicht brechen.
    """
    content = COMPONENT.read_text()
    required_testids = [
        "morning-master-switch",
        "report-morning-time",
        "report-morning-quickpick-07",
        "report-morning-quickpick-18",
        "report-morning-trend",
        "evening-master-switch",
        "report-evening-time",
        "report-evening-quickpick-07",
        "report-evening-quickpick-18",
        "report-evening-trend",
        "channel-email",
        "channel-email-hint",
        "channel-signal",
        "channel-signal-hint",
        "channel-telegram",
        "channel-telegram-hint",
        "report-show-advanced",
        "report-compact-summary",
        "report-show-daylight",
        "report-wind-exposition",
    ]
    missing = [tid for tid in required_testids if f'data-testid="{tid}"' not in content]
    assert not missing, (
        f"Folgende data-testids fehlen in EditReportConfigSection.svelte: {missing}. "
        "Diese Testids werden von frontend/e2e/issue-88-report-config-dialog.spec.ts verwendet "
        "und dürfen nicht entfernt werden (Issue #299 AC-8)."
    )
