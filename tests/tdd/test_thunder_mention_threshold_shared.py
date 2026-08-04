"""TDD RED -- Issue #1474b (Folge-Scheibe zu #1474 S3).

SPEC: docs/specs/modules/fix_1474b_gewitterschwelle_cockpit.md, Haelfte A.

Drei Stellen beantworten heute unterschiedlich, ab welcher Gewitterstufe
gemeldet wird: das SMS-/Telegram-Kuerzel `TH:` (konfigurierbar, Standard
"ab leicht"), die Mail-Prosa-Pille "Gewitter ab HH:00" (fest an MED
gebunden) und der Mail-Trend-Block (fest auf 1.0 verdrahtet, ignoriert die
Trip-Einstellung). Diese Datei belegt den Ist-Zustand (AC-1, Regression,
MUSS gruen sein) und die drei Luecken (AC-5/AC-6/AC-7, MUESSEN rot sein).

Keine Mocks: echte ForecastDataPoint-/HourlyValue-Reihen durch die echten
Renderfunktionen `_mk_metric()` (SMS-Token, unveraendert seit dieser
Scheibe), `_pill_for_metric()` (Mail-Prosa-Pille) und `format_trend_tokens()`
(Mail-Trend-Block). Kein Netz.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models import ForecastDataPoint, ThunderLevel

TZ = ZoneInfo("Europe/Berlin")


def _dps_only_low() -> list:
    """Stundenreihe, die NUR ThunderLevel.LOW traegt -- nie MED/HIGH."""
    base = datetime(2026, 8, 3, 6, 0, tzinfo=timezone.utc)
    return [
        ForecastDataPoint(ts=base, thunder_level=ThunderLevel.NONE),
        ForecastDataPoint(ts=base.replace(hour=10), thunder_level=ThunderLevel.LOW),
        ForecastDataPoint(ts=base.replace(hour=14), thunder_level=ThunderLevel.LOW),
        ForecastDataPoint(ts=base.replace(hour=18), thunder_level=ThunderLevel.NONE),
    ]


def _dps_reaching_med() -> list:
    """Stundenreihe, die MINDESTENS eine Stunde ThunderLevel.MED erreicht
    (nie HIGH) -- Ordinal 2, nicht nur LOW (Ordinal 1)."""
    base = datetime(2026, 8, 3, 6, 0, tzinfo=timezone.utc)
    return [
        ForecastDataPoint(ts=base, thunder_level=ThunderLevel.NONE),
        ForecastDataPoint(ts=base.replace(hour=10), thunder_level=ThunderLevel.LOW),
        ForecastDataPoint(ts=base.replace(hour=14), thunder_level=ThunderLevel.MED),
        ForecastDataPoint(ts=base.replace(hour=18), thunder_level=ThunderLevel.NONE),
    ]


def _hv(hour: int, value: float):
    from output.tokens.dto import HourlyValue
    return HourlyValue(hour=hour, value=value)


# ---------------------------------------------------------------------------
# AC-1 (Regression, MUSS SOFORT gruen sein und gruen BLEIBEN): das SMS-/
# Telegram-Kuerzel TH: fuer einen Trip OHNE eigene Gewitter-Schwelle ist
# bit-identisch -- diese Scheibe ruehrt tokens/builder.py nicht an.
# ---------------------------------------------------------------------------

def test_ac1_unconfigured_trip_sms_thunder_token_default_threshold_unchanged():
    """AC-1: `_mk_metric("TH:", ..., spec=None, ...)` (= Trip ohne eigene
    Schwellen-Einstellung, `MetricSpec` folglich `None`) rendert das TH:-Token
    weiterhin mit dem builder-eigenen DEFAULTS-Schwellenwert (1.0, "ab
    leicht") -- unveraendert durch diese Scheibe, die ausschliesslich
    `email/helpers.py` und `services/stage_weather.py` aendert, nie
    `output/tokens/builder.py`."""
    from output.tokens.builder import DEFAULTS, FORECAST_TH, _mk_metric

    assert DEFAULTS[FORECAST_TH] == 1.0, (
        "Vorbedingung verletzt: DEFAULTS['TH:'] ist nicht mehr 1.0 -- "
        "Testannahme fuer AC-1 muesste ueberprueft werden"
    )

    samples = (
        _hv(6, 0.0),
        _hv(10, 1.0),  # LOW (Ordinal 1, thunder_label_value)
        _hv(18, 0.0),
    )
    token = _mk_metric(FORECAST_TH, samples, spec=None, rt="evening", is_level=True)

    assert token is not None
    assert token.value == "L@10", (
        f"Erwartet bit-identisches TH:-Token 'L@10' (Schwelle 1.0, LOW ab "
        f"Stunde 10), erhalten: {token.value!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 (rot): Prosa-Pille meldet am Standard-Trip (keine eigene Einstellung)
# schon ab "leicht" -- heute schweigt sie bei reinem LOW.
# ---------------------------------------------------------------------------

def test_ac5_prosa_pille_meldet_gewitter_ab_leicht_am_standard_trip():
    from output.renderers.email.helpers import _pill_for_metric

    result = _pill_for_metric("thunder", {}, _dps_only_low(), tz=TZ)
    assert result is not None, "Erwartet ein (text, tone)-Tupel, erhalten None"
    text, _tone = result
    assert "Gewitter ab" in text, (
        "AC-5: Ein Trip ohne eigene Gewitter-Schwelle muss den Uhrzeit-Satz "
        f"schon bei reinem 'leicht' zeigen. Erhalten: {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 (rot): eingestellte Schwelle 2.0 ("mittel") haelt BEIDE -- Prosa-Pille
# UND Trend-Block -- bei reinem LOW still.
# ---------------------------------------------------------------------------

def test_ac6_konfigurierte_schwelle_haelt_prosa_pille_bei_leicht_still():
    from output.renderers.email.helpers import _pill_for_metric

    result = _pill_for_metric(
        "thunder", {"thunder": 2.0}, _dps_only_low(), tz=TZ,
    )
    assert result is not None
    text, _tone = result
    assert "Gewitter ab" not in text, (
        "AC-6: Mit eingestellter Schwelle 2.0 ('mittel') darf die Prosa-"
        f"Pille bei reinem 'leicht' NICHT ausloesen. Erhalten: {text!r}"
    )


def test_ac6_konfigurierte_schwelle_ueber_med_haelt_prosa_pille_bei_med_still():
    """AC-6, WIRKUNGS-Nachweis (PO-Nachbesserung 2026-08-04): der obige Test
    (`..._bei_leicht_still`) ist heute zufaellig gruen -- die Pille schweigt
    bei reinem LOW, WEIL sie fest gegen MED vergleicht, nicht weil sie die
    Schwelle 2.0 tatsaechlich liest. Er kann "liest die Schwelle" nicht von
    "haengt fest an MED" unterscheiden.

    Dieser Test waehlt eine Schwelle OBERHALB von MED (3.0, "hoch") bei einer
    Stundenreihe, die MED (nicht nur LOW) erreicht:
    - Heute: die feste Bindung `>= thunder_ordinal(MED)` (Ordinal 2) feuert
      bei MED -- die Pille SPRICHT ("Gewitter ab"), unabhaengig von der
      uebergebenen Schwelle 3.0. -> Test ist ROT.
    - Nach der Umsetzung: die Pille liest `_sms_mention_threshold("thunder",
      {"thunder": 3.0})` = 3.0; MED (Ordinal 2) < 3.0 -> die Pille SCHWEIGT.
      -> Test wird GRUEN.

    Gegenprobe (PO-Frage): bindet die Implementierung den Prosa-Zweig wieder
    fest an MED und ignoriert den Schwellenparameter, feuert die Pille bei
    MED unveraendert ("Gewitter ab...") -- die Assertion "not in text" schlaegt
    fehl -- dieser Test wird ROT. Er unterscheidet also tatsaechlich zwischen
    "liest die Schwelle" und "haengt fest an MED"."""
    from output.renderers.email.helpers import _pill_for_metric

    result = _pill_for_metric(
        "thunder", {"thunder": 3.0}, _dps_reaching_med(), tz=TZ,
    )
    assert result is not None
    text, _tone = result
    assert "Gewitter ab" not in text, (
        "AC-6 (WIRKUNGS-Nachweis): Mit eingestellter Schwelle 3.0 ('hoch') "
        "darf die Prosa-Pille bei einer Stundenreihe, die nur MED erreicht "
        f"(unter der Schwelle), NICHT ausloesen. Erhalten: {text!r} -- "
        "deutet darauf hin, dass die Pille weiterhin fest gegen MED "
        "vergleicht statt die uebergebene Schwelle zu lesen."
    )


def test_ac6_konfigurierte_schwelle_haelt_trend_block_bei_leicht_still():
    from output.renderers.email.helpers import format_trend_tokens

    stage = {
        "hourly_thunder": (_hv(10, 1.0),),  # LOW
        "sms_threshold_thunder": 2.0,
    }
    result = format_trend_tokens(stage)
    thunder_token = result["thunder_token"]
    assert thunder_token == "-", (
        "AC-6: Mit eingestellter Schwelle 2.0 ('mittel') darf der Trend-"
        f"Block bei reinem 'leicht' KEINEN Ausloeser zeigen. Erhalten: "
        f"{thunder_token!r} (erwartet '-')"
    )


# ---------------------------------------------------------------------------
# AC-7 (rot): der Trend-Block war bisher NICHT konfigurierbar (Literal 1.0
# fest verdrahtet) -- jetzt muss dieselbe Stundenreihe bei unterschiedlicher
# Trip-Schwelle unterschiedliche Ergebnisse liefern.
# ---------------------------------------------------------------------------

def test_ac7_trend_block_reagiert_auf_unterschiedliche_konfigurierte_schwelle():
    from output.renderers.email.helpers import format_trend_tokens

    hourly = (
        _hv(10, 1.0),  # LOW
        _hv(14, 2.0),  # MED
    )
    stage_low_thr = {"hourly_thunder": hourly, "sms_threshold_thunder": 1.0}
    stage_med_thr = {"hourly_thunder": hourly, "sms_threshold_thunder": 2.0}

    token_at_1_0 = format_trend_tokens(stage_low_thr)["thunder_token"]
    token_at_2_0 = format_trend_tokens(stage_med_thr)["thunder_token"]

    assert token_at_1_0 != token_at_2_0, (
        "AC-7: Dieselbe Stundenreihe muss bei Schwelle 1.0 vs. 2.0 "
        f"unterschiedliche Trend-Token liefern. Beide waren: {token_at_1_0!r} "
        "-- deutet auf den fest verdrahteten Literal threshold=1.0 hin "
        "(helpers.py:865), der `stage['sms_threshold_thunder']` ignoriert."
    )
