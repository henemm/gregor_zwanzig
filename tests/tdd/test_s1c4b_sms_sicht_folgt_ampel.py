"""Issue #2792 S1c-4b, Nachtrag VS (Spec v1.4 §5 Punkt 5 + 9, AC-19 e):
Die Invers-Min-Token der Kurzkanaele folgen der Abo-Ampel.

- ``VS`` (Sicht, Ampel-Metrik ``visibility``, untere Seite): Tiefstwert mit
  Stunde NUR, wenn er nach der Ampel gelb oder schlechter ist -- sonst
  Nullform ``-``. Dasselbe Praedikat wie die Mail-Erwaehnung
  (``helpers._erwaehnt("visibility")``).
- ``TF`` (gefuehlte Temperatur, Ampel-Metrik ``wind_chill``): gleiches Praedikat.
- ``FZ`` (Nullgradgrenze) hat KEINEN Ampel-Leser und bleibt unveraendert
  (Tiefstwert mit Stunde, wie bisher).

Echter ``build_token_line()``-Pfad, kein Mock. Skitouren und Allgemein
nacheinander im selben Prozess, beide Reihenfolgen.
"""
from __future__ import annotations

import pytest

from app.ampel import resolve_ampel
from output.tokens.builder import build_token_line
from output.tokens.dto import DailyForecast, HourlyValue, MetricSpec, NormalizedForecast

ALLGEMEIN = resolve_ampel({"ampel": {"template": "allgemein"}})
SKITOUREN = resolve_ampel({"ampel": {"template": "skitouren"}})


def _wert(symbol: str, day: DailyForecast, ampel: dict) -> str:
    line = build_token_line(
        NormalizedForecast(days=(day,)), [MetricSpec(symbol=symbol, enabled=True)],
        report_type="evening", stage_name="E1", ampel=ampel,
    )
    toks = [t for t in line.tokens if t.symbol == symbol and t.category == "forecast"]
    assert len(toks) == 1, toks
    return toks[0].value


def _sicht(meter_min: float) -> DailyForecast:
    # Tiefstwert um 14 Uhr, sonst klare Sicht.
    return DailyForecast(visibility_hourly=(
        HourlyValue(9, 20000.0), HourlyValue(14, meter_min), HourlyValue(17, 15000.0),
    ))


def _gefuehlt(min_c: float) -> DailyForecast:
    return DailyForecast(wind_chill_hourly=(
        HourlyValue(8, min_c), HourlyValue(12, min_c + 6), HourlyValue(16, min_c + 4),
    ))


@pytest.mark.parametrize("reihenfolge", ["allgemein_zuerst", "skitouren_zuerst"])
def test_vs_tiefstwert_nur_ab_gelb_der_abo_ampel(reihenfolge):
    """Allgemein: Sicht gelb unter 2000 m; Skitouren: gelb unter 1000 m.
    1500 m ist bei Allgemein hervorgehoben, bei Skitouren nicht; 800 m bei
    beiden; 20 km (klare Sicht) bei keiner -> Nullform."""
    faelle = [(ALLGEMEIN, "allgemein"), (SKITOUREN, "skitouren")]
    if reihenfolge == "skitouren_zuerst":
        faelle.reverse()
    erwartet = {
        ("allgemein", 1500.0): "1.5@14", ("skitouren", 1500.0): "-",
        ("allgemein", 800.0): "0.8@14", ("skitouren", 800.0): "0.8@14",
        ("allgemein", 12000.0): "-", ("skitouren", 12000.0): "-",
    }
    for ampel, name in faelle:
        for meter in (1500.0, 800.0, 12000.0):
            assert _wert("VS", _sicht(meter), ampel) == erwartet[(name, meter)], (
                name, meter)


def test_vs_ohne_daten_bleibt_nullform():
    assert _wert("VS", DailyForecast(visibility_hourly=()), ALLGEMEIN) == "-"


@pytest.mark.parametrize("reihenfolge", ["allgemein_zuerst", "skitouren_zuerst"])
def test_tf_tiefstwert_nur_ab_gelb_der_abo_ampel(reihenfolge):
    """wind_chill: Allgemein gelb unter 0 °C, Skitouren gelb unter -15 °C."""
    faelle = [(ALLGEMEIN, "allgemein"), (SKITOUREN, "skitouren")]
    if reihenfolge == "skitouren_zuerst":
        faelle.reverse()
    erwartet = {
        ("allgemein", -5.0): "-5@8", ("skitouren", -5.0): "-",
        ("allgemein", -20.0): "-20@8", ("skitouren", -20.0): "-20@8",
        ("allgemein", 6.0): "-", ("skitouren", 6.0): "-",
    }
    for ampel, name in faelle:
        for grad in (-5.0, -20.0, 6.0):
            assert _wert("TF", _gefuehlt(grad), ampel) == erwartet[(name, grad)], (
                name, grad)


def test_fz_ohne_ampel_leser_bleibt_unveraendert():
    """FZ (Nullgradgrenze) hat keinen Ampel-Leser: Tiefstwert mit Stunde,
    unabhaengig von der Vorlage (wie vor S1c-4b)."""
    day = DailyForecast(freezing_level_hourly=(HourlyValue(10, 2900.0), HourlyValue(15, 2400.0)))
    assert _wert("FZ", day, ALLGEMEIN) == "2400@15"
    assert _wert("FZ", day, SKITOUREN) == "2400@15"
