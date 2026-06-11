# doc-compliance-test
"""
Test-Hygiene-Compliance-Gate (Issues #754 + #755).

Dieser Test prüft die TEST-ARTEFAKTE selbst — nicht Produkt-Verhalten. Er ist
nach der dokumentierten CLAUDE.md-Ausnahme als `# doc-compliance-test` markiert
und verhindert Regress des Datei-Inhalt-Anti-Patterns sowie toter Signal-Locator.

RED (vor Sweep): die 19 #754-Dateien enthalten `read_text()`-Asserts auf
`.svelte`/`.ts`-Quelltext; `channel-signal` taucht in E2E-Specs auf.
GREEN (nach Sweep): kein Quelltext-`read_text` mehr in den Zieldateien (gelöscht
oder auf echtes Verhalten umgestellt); keine `channel-signal`-Referenz mehr.

CLAUDE.md: "Dateiinhalt-Checks sind VERBOTEN" + Ausnahme für Workflow-/Test-
Artefakt-Compliance-Tests (`# doc-compliance-test`).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TDD = _REPO / "tests" / "tdd"

# Die 19 in Issue #754 gelisteten Dateien mit verbotenem Datei-Inhalt-Anti-Pattern.
_ISSUE_754_FILES = [
    "test_bug_272_ios_input_font_size.py",
    "test_bug_281_290_stagestrip.py",
    "test_bug_328_savepreset_tokens.py",
    "test_bug_330_modecard_fontsize.py",
    "test_bug_382_select_ios_zoom.py",
    "test_bug_541_543_544.py",
    "test_bug590_signal_removal_telegram_start.py",
    "test_bug707_trip_datum_overwrite.py",
    "test_issue_180_alert_metric_table.py",
    "test_issue_259_briefings_tab.py",
    "test_issue_278_form_controls.py",
    "test_issue_285_weather_section_restyle.py",
    "test_issue_315_icon_guide.py",
    "test_issue_323_hex_fallbacks.py",
    "test_issue_326_alert_font_tokens.py",
    "test_issue_339_verify_timing.py",
    "test_issue_456_auto_briefings.py",
    "test_metric_entry_cleanup.py",
    "test_trips_naming.py",
]

# Erkennt Quelltext-Inhalt-Asserts:
#   1) `.read_text()` — direktes Lesen von Dateiinhalt
#   2) `--include=*.svelte` / `--include=*.ts` — grep-Subprozess auf Produkt-Quelltext
#   3) `--glob=*.svelte` / `--glob=*.ts`       — rg-Subprozess auf Produkt-Quelltext
# Alle drei Formen sind dasselbe Anti-Pattern: Code-Analyse statt Nutzerverhalten.
_FORBIDDEN_READ = re.compile(r"\.read_text\s*\(")
_FORBIDDEN_GLOB = re.compile(
    r"""(--include=['"*]?\*\.(svelte|ts)['"*]?|--glob=['"*]?\*\.(svelte|ts)['"*]?)"""
)


def _is_source_content_analysis(src: str) -> list[str]:
    """Gibt alle verbotenen Treffer zurück (read_text + Quelltext-Glob-Greps)."""
    hits: list[str] = []
    hits.extend(_FORBIDDEN_READ.findall(src))
    hits.extend(m.group(0) for m in _FORBIDDEN_GLOB.finditer(src))
    return hits


@pytest.mark.parametrize("name", _ISSUE_754_FILES)
def test_754_no_source_content_read(name: str) -> None:
    """Jede #754-Datei: entweder gelöscht, oder ohne Quelltext-Analyse-Assert."""
    path = _TDD / name
    if not path.exists():
        # Ersatzlos gelöscht (Verhalten durch E2E gedeckt / obsolet) → konform.
        return
    src = path.read_text(encoding="utf-8")
    head = "\n".join(src.splitlines()[:3])
    if "# doc-compliance-test" in head:
        return  # Selbst als Compliance-Test markiert → Ausnahme.
    hits = _is_source_content_analysis(src)
    assert not hits, (
        f"{name} enthält noch {len(hits)} Quelltext-Analyse-Pattern(s) "
        f"({hits!r}) — (read_text / grep-glob auf .svelte/.ts ist "
        f"Datei-Inhalt-Anti-Pattern, CLAUDE.md). Löschen (wenn E2E-gedeckt) "
        f"oder auf echtes Verhalten umstellen."
    )


def test_755_no_channel_signal_in_e2e_and_tests() -> None:
    """Kein `channel-signal`-Locator mehr in E2E-Specs oder Python-Tests (#610/#755)."""
    roots = [_REPO / "frontend" / "e2e", _REPO / "tests"]
    offenders: list[str] = []
    self_name = Path(__file__).name
    for root in roots:
        if not root.exists():
            continue
        for f in root.rglob("*"):
            if not f.is_file() or f.suffix not in (".ts", ".py"):
                continue
            if f.name == self_name:
                continue  # dieser Compliance-Test selbst
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "channel-signal" in text:
                offenders.append(str(f.relative_to(_REPO)))
    assert not offenders, (
        f"Toter Signal-Locator `channel-signal` (entfernt in #610) noch in: {offenders}"
    )
