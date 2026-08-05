"""TDD RED — Issue #1475 Nachbesserung (Epic #1419), AC-1: SMS-Kuerzel-
Umbenennung `+HG` -> `+HL`.

SPEC: docs/specs/modules/feat_1475_hagel_luecken_nachbesserung.md, AC-1,
Implementation Details Punkt 1.

RED-Ursache (heute): `output.tokens.builder.FORECAST_TH_HAIL_SUFFIX == "+HG"`
-- ein gerendertes SMS-Token traegt daher noch `+HG`, nicht `+HL`.
`docs/reference/sms_format.md` beschreibt an derselben Zeile ebenfalls noch
`+HG`.

Keine Mocks/patch()/MagicMock — echte DailyForecast/NormalizedForecast-DTOs,
echter Token-Builder.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from output.tokens.builder import FORECAST_TH_HAIL_SUFFIX, build_token_line  # noqa: E402
from output.tokens.dto import DailyForecast, HourlyValue, NormalizedForecast  # noqa: E402

_SMS_FORMAT_MD = Path(__file__).resolve().parents[2] / "docs" / "reference" / "sms_format.md"


def _forecast_mit_bestaetigtem_hagel() -> NormalizedForecast:
    today = DailyForecast(
        temp_min_c=10.0, temp_max_c=18.0,
        thunder_hourly=(HourlyValue(hour=16, value=3.0),),
        hail_flag=True,
    )
    return NormalizedForecast(days=(today,))


# =============================================================================
# AC-1 — Golden-String: gerendertes SMS-Token traegt +HL, NICHT mehr +HG
# =============================================================================

def test_ac1_gerendertes_token_traegt_hl_suffix():
    line = build_token_line(
        _forecast_mit_bestaetigtem_hagel(), config=None,
        report_type="evening", stage_name="Etappe1",
    )
    rendered = line.render()

    assert "+HL" in rendered, (
        f"Erwarte den neuen Hagel-Suffix '+HL' im gerenderten Gewitter-Token, "
        f"bekam: {rendered!r}"
    )


def test_ac1_negativer_beleg_altes_hg_kuerzel_verschwindet():
    """Negativer Beleg (Spec-Pflicht): das ALTE Kuerzel darf NICHT mehr im
    gerenderten Output auftauchen -- eine Umbenennung ist nur bewiesen, wenn
    das Alte nachweisbar weg ist, nicht nur, wenn das Neue da ist."""
    line = build_token_line(
        _forecast_mit_bestaetigtem_hagel(), config=None,
        report_type="evening", stage_name="Etappe1",
    )
    rendered = line.render()

    assert "+HG" not in rendered, (
        f"Das alte Kuerzel '+HG' darf nach der Umbenennung nicht mehr im "
        f"gerenderten SMS-Token auftauchen, bekam: {rendered!r}"
    )


def test_ac1_konstante_selbst_traegt_bereits_hl():
    """Direkter Beleg an der Quelle: die Konstante selbst muss auf '+HL'
    umgestellt sein (nicht nur eine zusaetzliche String-Ersetzung an der
    Aufrufstelle)."""
    assert FORECAST_TH_HAIL_SUFFIX == "+HL", (
        f"FORECAST_TH_HAIL_SUFFIX muss '+HL' sein (nicht mehr '+HG'), "
        f"bekam {FORECAST_TH_HAIL_SUFFIX!r}"
    )


# =============================================================================
# AC-1 — Dokumentations-Abgleich (# doc-compliance-test, kein Verhaltensnachweis)
# =============================================================================

# doc-compliance-test
def test_ac1_sms_format_md_beschreibt_dasselbe_kuerzel_wie_die_konstante():
    """Spiegelt die Tabellenzeile in `sms_format.md` gegen die aktive
    Konstante `FORECAST_TH_HAIL_SUFFIX` -- ausdruecklich NUR ein
    Dokumentations-Abgleich, kein Verhaltensnachweis (Spec AC-1)."""
    text = _SMS_FORMAT_MD.read_text(encoding="utf-8")
    zeile = next(
        (ln for ln in text.splitlines() if "Hagel-Kennzeichen" in ln and "TH:" in ln),
        None,
    )
    assert zeile is not None, (
        "Keine Tabellenzeile mit 'Hagel-Kennzeichen' in docs/reference/"
        "sms_format.md gefunden -- Doku-Abgleich nicht moeglich"
    )
    assert FORECAST_TH_HAIL_SUFFIX in zeile, (
        f"docs/reference/sms_format.md beschreibt nicht das aktive Kuerzel "
        f"{FORECAST_TH_HAIL_SUFFIX!r} -- Zeile: {zeile!r}"
    )
    assert "+HG" not in zeile, (
        f"docs/reference/sms_format.md nennt noch das alte Kuerzel '+HG' in "
        f"derselben Zeile: {zeile!r}"
    )
