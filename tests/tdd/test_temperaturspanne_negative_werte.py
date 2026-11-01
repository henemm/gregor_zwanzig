"""#2210 AC-3..AC-6: negative Temperaturspannen lesbar ("bis" statt "–")."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from output.renderers.email.helpers import _aggregation_pill_text, format_temp_span

TZ = ZoneInfo("Europe/Berlin")


def _kachel(lo: float, hi: float) -> str:
    ts = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
    vals = [(lo, ts), (hi, ts.replace(hour=12))]
    return _aggregation_pill_text(vals, ["min", "max"], tz=TZ, prefix="", decimals=0)


def test_ac3_beide_negativ():
    text = _kachel(-12.0, -4.0)
    assert "-12 bis -4°C" in text
    assert "-12–-4" not in text


def test_ac4_vorzeichenwechsel():
    assert "-3 bis 5°C" in _kachel(-3.0, 5.0)


def test_ac5_plusgrade_unveraendert():
    assert "8–14°C" in _kachel(8.0, 14.0)
    assert format_temp_span(8.0, 14.0, decimals=0) == "8–14°C"


def test_ac5_minus_null_nach_rundung_loest_kein_bis_aus():
    # "-0" entsteht beim Runden von -0.2; Anzeige "-0" beginnt mit "-" -> Spec: nicht "bis".
    assert " bis " not in format_temp_span(0.2, 3.0, decimals=0)
    assert format_temp_span(0.2, 3.0, decimals=0) == "0–3°C"


def test_ac6_kurzzusammenfassung_gefuehlt():
    from output.renderers.compact_summary import CompactSummaryFormatter

    text = CompactSummaryFormatter._format_felt_temperature(
        None, report_type="morning", hiking_felt_min_c=-12.0, hiking_felt_max_c=-4.0,
    )
    assert "-12 bis -4°C" in text
    assert "-12–-4" not in text
