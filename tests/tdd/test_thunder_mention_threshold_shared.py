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
from tests.helpers.ampel_allgemein import AMPEL_ALLGEMEIN
from app.ampel import resolve_ampel

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models import ForecastDataPoint, ThunderLevel

TZ = ZoneInfo("Europe/Berlin")

# #1493: der Uhrzeit-Satz der Gewitter-Pille traegt seit Issue #1493 das
# Stufenwort ("Gewitter mittel ab 14:00 · staerkste 18:00"). Abwesenheit
# wird deshalb gegen dieses MUSTER geprueft -- die alte Zeichenkette
# "Gewitter ab" ist heute auch im Positivfall abwesend und als
# Negativ-Assertion damit blind.
_UHRZEIT_SATZ_RE = re.compile(r"Gewitter (?:leicht|mittel|hoch) ab \d{2}:00")


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
    import output.tokens.builder as builder
    from output.tokens.builder import FORECAST_TH, _mk_metric

    # Issue #2792 S1c-4b (E1, AC-19 e): `DEFAULTS` ist entfallen; Gewitter
    # zaehlt fest ab „leicht" (gelb oder schlechter, P2) -- dasselbe Ergebnis.
    assert not hasattr(builder, "DEFAULTS"), "E1: builder.DEFAULTS darf nicht mehr wirken"

    samples = (
        _hv(6, 0.0),
        _hv(10, 1.0),  # LOW (Ordinal 1, thunder_label_value)
        _hv(18, 0.0),
    )
    token = _mk_metric(FORECAST_TH, samples, spec=None, rt="evening", is_level=True, ampel=AMPEL_ALLGEMEIN)

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

    result = _pill_for_metric("thunder", {}, _dps_only_low(), tz=TZ, ampel=resolve_ampel(None))
    assert result is not None, "Erwartet ein (text, tone)-Tupel, erhalten None"
    text, _tone = result
    # #1493 trug das Stufenwort nach, #2176 nimmt die Ereignisbehauptung
    # heraus. Geprueft bleibt die Schwelle: der Uhrzeit-Satz erscheint bei
    # reinem LOW -- die Stunde ist deshalb mitgebunden.
    assert "Schwaches Signal (leicht) ab 12:00" in text, (
        "AC-5: Ein Trip ohne eigene Gewitter-Schwelle muss den Uhrzeit-Satz "
        f"schon bei reinem 'leicht' zeigen. Erhalten: {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 (rot): eingestellte Schwelle 2.0 ("mittel") haelt BEIDE -- Prosa-Pille
# UND Trend-Block -- bei reinem LOW still.
# ---------------------------------------------------------------------------

def test_ac6_konfigurierte_schwelle_haelt_prosa_pille_bei_leicht_nicht_mehr_still():
    """Issue #2792 S1c-4b (E1, AC-19 e) -- umgekehrt: die eingestellte
    Schwelle 2.0 wirkt nicht mehr; die Pille meldet ab „leicht" (P2)."""
    from output.renderers.email.helpers import _pill_for_metric

    result = _pill_for_metric(
        "thunder", {"thunder": 2.0}, _dps_only_low(), tz=TZ, ampel=resolve_ampel(None),
    )
    assert result is not None
    text, _tone = result
    assert "Schwaches Signal (leicht) ab 12:00" in text, (
        "E1: Trotz eingestellter Schwelle 2.0 ('mittel') muss die Prosa-"
        f"Pille bei reinem 'leicht' den Uhrzeit-Satz zeigen. Erhalten: {text!r}"
    )


def test_ac6_konfigurierte_schwelle_ueber_med_haelt_prosa_pille_bei_med_nicht_still():
    """Issue #2792 S1c-4b (E1, AC-19 e) -- umgekehrt: die eingestellte
    Schwelle 3.0 wirkt nicht mehr; bei MED meldet die Pille „Gewitter mittel
    ab …". Historie (vor E1) -- AC-6, WIRKUNGS-Nachweis (PO-Nachbesserung 2026-08-04): der obige Test
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
        "thunder", {"thunder": 3.0}, _dps_reaching_med(), tz=TZ, ampel=resolve_ampel(None),
    )
    assert result is not None
    text, _tone = result
    # #1493: Muster statt Wortlaut (siehe oben).
    assert _UHRZEIT_SATZ_RE.search(text) is not None, (
        "E1: Trotz eingestellter Schwelle 3.0 ('hoch') muss die Prosa-Pille "
        f"bei einer Stundenreihe, die MED erreicht, ausloesen. Erhalten: {text!r}"
    )


def test_ac6_konfigurierte_schwelle_haelt_trend_block_bei_leicht_nicht_mehr_still():
    """Issue #2792 S1c-4b (E1, AC-19 e) -- umgekehrt: `sms_threshold_thunder`
    in der Zeile wirkt nicht mehr; der Trend-Block meldet ab „leicht"."""
    from output.renderers.email.helpers import format_trend_tokens

    stage = {
        "hourly_thunder": (_hv(10, 1.0),),  # LOW
        "sms_threshold_thunder": 2.0,
    }
    result = format_trend_tokens(stage, ampel=AMPEL_ALLGEMEIN)
    thunder_token = result["thunder_token"]
    assert thunder_token == "leicht@10", (
        "E1: Trotz eingestellter Schwelle 2.0 ('mittel') muss der Trend-"
        f"Block bei reinem 'leicht' ausloesen. Erhalten: {thunder_token!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 (rot): der Trend-Block war bisher NICHT konfigurierbar (Literal 1.0
# fest verdrahtet) -- jetzt muss dieselbe Stundenreihe bei unterschiedlicher
# Trip-Schwelle unterschiedliche Ergebnisse liefern.
# ---------------------------------------------------------------------------

def test_ac7_trend_block_reagiert_nicht_mehr_auf_konfigurierte_schwelle():
    """Issue #2792 S1c-4b (E1, AC-19 e) -- umgekehrt: dieselbe Stundenreihe
    liefert bei jeder `sms_threshold_thunder` dasselbe Token (ab „leicht")."""
    from output.renderers.email.helpers import format_trend_tokens

    hourly = (
        _hv(10, 1.0),  # LOW
        _hv(14, 2.0),  # MED
    )
    stage_low_thr = {"hourly_thunder": hourly, "sms_threshold_thunder": 1.0}
    stage_med_thr = {"hourly_thunder": hourly, "sms_threshold_thunder": 2.0}

    token_at_1_0 = format_trend_tokens(stage_low_thr, ampel=AMPEL_ALLGEMEIN)["thunder_token"]
    token_at_2_0 = format_trend_tokens(stage_med_thr, ampel=AMPEL_ALLGEMEIN)["thunder_token"]

    assert token_at_1_0 == token_at_2_0 == "leicht@10(mittel@14)", (
        "E1: Dieselbe Stundenreihe muss bei Schwelle 1.0 und 2.0 dasselbe "
        f"Trend-Token ab 'leicht' liefern: {token_at_1_0!r} / {token_at_2_0!r}"
    )
