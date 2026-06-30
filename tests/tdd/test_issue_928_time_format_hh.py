"""
TDD RED tests for Issue #928 — Stundentabelle-Zeitformat zurueck auf `HH`.

Root Cause (verifiziert): Commit 2505711a (#838) stellte die Zeit-Zelle der
Briefing-Stundentabelle von `HH` auf `HH:00` um, weil der briefing_mail_validator
(seit #807) `HH:00` verlangte. Der Zeilenbauer `src/formatters/trip_report.py`
(`_aggregate_night_block`, `_dp_to_row`) ist geteilt -> `HH:00` erscheint in Plain
UND HTML.

PO-Entscheidung (#928): beide Mail-Varianten zeigen wieder reine `HH`; der Validator
akzeptiert `HH` (Distinct-Hours-Substanz bleibt).

Diese Tests treiben den ECHTEN Renderpfad (TripReportFormatter().format_email(...))
und die ECHTE Validator-Funktion. Keine Mocks.

Erwartet bei RED-Zeit:
    AC-3 (HTML-Zellen `HH`)              -> FAIL (Renderer liefert HH:00)
    AC-4 (Validator akzeptiert `HH`)     -> FAIL (Validator verlangt HH:00)
    AC-4b (Distinctness bleibt)          -> PASS (gleiche Stunde wird abgelehnt)
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from formatters.trip_report import TripReportFormatter

# Reuse the real fixture builders from the bug_397 suite (module-level helpers).
from tdd.test_bug_397_output_localtime import (  # type: ignore
    _CEST,
    _night_timeseries,
    _segment_weather,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VALIDATOR_PATH = _REPO_ROOT / ".claude" / "hooks" / "briefing_mail_validator.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("bmv_928", _VALIDATOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _evening_html() -> str:
    seg = _segment_weather(start_hour=14, end_hour=18)
    report = TripReportFormatter().format_email(
        segments=[seg],
        trip_name="AC3 Trip",
        report_type="evening",
        night_weather=_night_timeseries(),
        tz=_CEST,
    )
    return report.email_html


# ---------------------------------------------------------------------------
# AC-3: HTML <td> Zeit-Zellen zeigen `HH`, nicht `HH:00`.
# ---------------------------------------------------------------------------
class TestAC3HtmlTimeCellsAreBareHour:
    def test_html_time_cells_have_no_colon_zero_zero(self):
        html = _evening_html()
        # Zeit-Zellen sind ueber data-label="Time" verankert.
        cells = re.findall(r'data-label="Time">\s*([^<]+?)\s*</td>', html)
        assert cells, "Keine Time-Zellen im HTML gefunden"
        # Mindestens eine Datenzeile mit reiner Stunde, KEINE mit ':00'.
        bad = [c for c in cells if re.search(r"\d{1,2}:00", c)]
        assert not bad, (
            f"HTML-Zeit-Zellen enthalten weiterhin HH:00: {bad[:5]} "
            f"(#928: erwartet reine Stunde HH)"
        )
        good = [c for c in cells if re.fullmatch(r"[012]?\d", c.strip())]
        assert good, f"Keine reine HH-Zeit-Zelle gefunden, alle: {cells[:5]}"


# ---------------------------------------------------------------------------
# AC-4: briefing_mail_validator erkennt Stundentabelle auch im `HH`-Format,
#       behaelt aber die Distinct-Hours-Pruefung.
# ---------------------------------------------------------------------------
class TestAC4ValidatorAcceptsBareHour:
    _HEAD = '<table><tr><td data-label="Time">{a}</td><td>12C</td></tr>' \
            '<tr><td data-label="Time">{b}</td><td>13C</td></tr></table>'

    def test_validator_detects_hourly_table_with_bare_hour(self):
        bmv = _load_validator()
        html = self._HEAD.format(a="08", b="09")
        assert bmv._has_hourly_table(html), (
            "Validator erkennt HH-formatierte Stundentabelle nicht "
            "(#928: muss reine Stunde HH akzeptieren)"
        )

    def test_validator_still_rejects_single_distinct_hour(self):
        bmv = _load_validator()
        # Beide Zeilen tragen dieselbe Stunde -> KEINE echte Stundentabelle.
        html = self._HEAD.format(a="08", b="08")
        assert not bmv._has_hourly_table(html), (
            "Distinct-Hours-Pruefung muss erhalten bleiben: identische Stunden "
            "duerfen NICHT als Stundentabelle gelten"
        )
