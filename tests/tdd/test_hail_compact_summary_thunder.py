"""TDD RED — Issue #1475 Nachbesserung (Epic #1419), AC-4:
`compact_summary.py::_format_thunder()` muss den Hagel-Hinweis
(`format_hail_note`/`hail_priority`) ECHT aufrufen -- nicht nur behaupten
(S5a hat genau das faelschlich behauptet, ohne Code-Beleg).

SPEC: docs/specs/modules/feat_1475_hagel_luecken_nachbesserung.md, AC-4,
Implementation Details Punkt 3.

RED-Ursache (heute): `_format_thunder()` sammelt nur `thunder_hours`, liest
`dp.hail_flag` nirgends und ruft `format_hail_note`/`hail_priority` nirgends
auf -- der zurueckgegebene String enthaelt daher KEINEN Hagel-Zusatz.

Zwei Nachweisebenen (Spec-Pflicht): (1) Verhaltensnachweis am oeffentlichen
Renderpfad `format_weather_summary()` (friendly UND Text-Variante), (2) ein
struktureller Beleg (Quelltext-Inspektion der `_format_thunder`-Funktion),
der einen Aufruf von `format_hail_note`/`hail_priority` VERLANGT -- eine
Funktion, die nur existiert, ohne den Rueckgabewert zu aendern, erfuellt
diesen AC nicht.

Keine Mocks/patch()/MagicMock — echte ForecastDataPoint-DTOs, echter
CompactSummaryFormatter.
"""
from __future__ import annotations

import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.metric_catalog import build_default_display_config  # noqa: E402
from app.models import ForecastDataPoint, ThunderLevel  # noqa: E402

_TZ = ZoneInfo("Europe/Berlin")


def _hourly_mit_hagel(hail_flag) -> list[ForecastDataPoint]:
    """Vier Stunden Gewitter (HIGH), NUR die letzte traegt `hail_flag`."""
    return [
        ForecastDataPoint(
            ts=datetime(2026, 8, 5, h, 0, tzinfo=timezone.utc),
            t2m_c=18.0, thunder_level=ThunderLevel.HIGH,
            hail_flag=hail_flag if h == 17 else None,
        )
        for h in range(15, 18)
    ]


def _nur_thunder_metric_dc():
    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = mc.metric_id == "thunder"
    return dc


def _render(hail_flag, *, friendly: bool) -> str:
    from output.renderers.compact_summary import CompactSummaryFormatter

    dc = _nur_thunder_metric_dc()
    for mc in dc.metrics:
        if mc.metric_id == "thunder":
            mc.use_friendly_format = friendly
    return CompactSummaryFormatter().format_weather_summary(
        summary=None, hourly=_hourly_mit_hagel(hail_flag), title="Etappe1",
        dc=dc, tz=_TZ,
    )


# =============================================================================
# AC-4 — Verhaltensnachweis: friendly- UND Text-Variante zeigen den Hinweis
# =============================================================================

def test_ac4_friendly_variante_zeigt_hagel_hinweis_bei_true():
    text_true = _render(True, friendly=True)
    text_unbekannt = _render(None, friendly=True)

    assert "Hagel: ja" in text_true, (
        f"Die friendly-Kurzzusammenfassung mit hail_flag=True in der "
        f"gewitternden Stunde muss 'Hagel: ja' enthalten, bekam: {text_true!r}"
    )
    assert "Hagel: ja" not in text_unbekannt, (
        f"Eine Etappe mit hail_flag=None (unbekannt) darf KEINEN Hagel-"
        f"Zusatztext zeigen (kein Rauschen), bekam: {text_unbekannt!r}"
    )


def test_ac4_text_variante_zeigt_hagel_hinweis_bei_true():
    text_true = _render(True, friendly=False)
    text_unbekannt = _render(None, friendly=False)

    assert "Hagel: ja" in text_true, (
        f"Die Text-Kurzzusammenfassung mit hail_flag=True in der "
        f"gewitternden Stunde muss 'Hagel: ja' enthalten, bekam: {text_true!r}"
    )
    assert "Hagel: ja" not in text_unbekannt, (
        f"Eine Etappe mit hail_flag=None (unbekannt) darf KEINEN Hagel-"
        f"Zusatztext zeigen (kein Rauschen), bekam: {text_unbekannt!r}"
    )


# =============================================================================
# AC-4 — Struktureller Beleg: KEIN unbelegtes "ist schon abgedeckt" wie S5a
# =============================================================================

def test_ac4_struktureller_beleg_format_thunder_ruft_hail_helfer_auf():
    """S5a-Lehre: eine Behauptung ohne Code-Beleg ("ist bereits abgedeckt")
    war schlicht falsch. Dieser Test liest den TATSAECHLICHEN Quelltext der
    Funktion und verlangt einen Aufruf von `format_hail_note` ODER
    `hail_priority` -- eine bloss existierende Funktion ohne diesen Aufruf
    laesst den Test rot."""
    from output.renderers.compact_summary import CompactSummaryFormatter

    source = inspect.getsource(CompactSummaryFormatter._format_thunder)
    assert ("format_hail_note" in source) or ("hail_priority" in source), (
        "compact_summary.py::_format_thunder() ruft weder 'format_hail_note' "
        "noch 'hail_priority' auf -- die S5a-Behauptung 'bereits abgedeckt' "
        "war ohne Code-Beleg falsch, AC-4 verlangt einen ECHTEN Aufruf. "
        f"Quelltext:\n{source}"
    )
