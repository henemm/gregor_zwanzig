"""TDD RED: Issue #1677 Scheibe B -- Vollstaendigkeits-Matrix Metrik-Katalog x
Kanal, damit die Fehlerklasse "Bedienelement ohne Wirkung" (#1450, #1362,
#1660 A/B, #1677) strukturell bewacht ist statt fallweise entdeckt zu werden.

SPEC: docs/specs/modules/fix_1677_sms_reihenfolge.md AC-13/AC-14/AC-15.

Parametrisiert ueber ``app.metric_catalog.get_all_metrics()`` (26
waehlbare Metriken). Pro Kanal wird gegen die Funktion getestet, die der
jeweilige Produktivpfad TATSAECHLICH aufruft (kein Duplikat-Rendering):
- E-Mail:        ``resolve_metric_col_order`` (email/html.py:1021 ``_col_order``)
- Telegram-rich: ``render_for_channel`` (narrow.py:644)
- SMS-Kurzform:  ``TripReportFormatter().format_email() -> report.sms_text``
  (derselbe Wirkort wie test_sms_user_metric_order.py)

AC-Zuordnung:
- AC-13 (E-Mail):        test_ac13_email_column_selection_and_order       -> GRUEN (Bestand, #1575)
- AC-14 (Telegram-rich):  test_ac14_telegram_rich_selection_and_order      -> GRUEN (Bestand, #429/#1575)
- AC-15 (SMS-Kurzform):   test_ac15_sms_kurzform_selection_deselection_and_order
    - (a)/(b) Auswahl/Abwahl -> GRUEN (Bestand, Bug-#944-Muster + #1415/#1660B)
    - (c) Nutzer-Reihenfolge -> RED (exakt die Luecke aus #1677)
    - (d) ohne SMS-Layout   -> GRUEN (Charakterisierung, wie AC-2)

E-Mail/Telegram sind bewusste GRUEN-Ausnahmen (Bestandsfunktion, hier nur
strukturell abgesichert) -- der SMS-Kurzform-Reihenfolge-Teil ist der
einzige neue, heute rote Anteil dieser Datei.
"""
from __future__ import annotations

import dataclasses
import re

import pytest

from app.metric_catalog import get_all_metrics, get_metric
from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from output.renderers.channel_layout import render_for_channel
from output.renderers.email.helpers import resolve_metric_col_order
from output.renderers.sms_trip import SMS_SYMBOL_BY_METRIC, SMS_MULTI_SYMBOLS_BY_METRIC
from output.renderers.trip_report import TripReportFormatter

from tests.tdd import _min_temp_felt_fixtures as F

_ALL_METRIC_IDS = [m.id for m in get_all_metrics()]

# #1484/#1660 A: Nachtfenster-Skalare sind bewusst NIE eine Telegram-rich-
# Tabellen-/Detailzelle (channel_layout.py:85-89 ``_NIGHT_SCALAR_IDS``) --
# strukturelle Ausnahme, kein Auswahl-Bug.
_TELEGRAM_NIGHT_SCALAR_EXCEPTIONS = {"temperature_night", "wind_chill_night"}


def _partner_of(metric_id: str) -> str:
    """Sichere Partner-Metrik ohne Symbol-Praefix-Kollision (K ist bei
    keinem anderen Katalog-Kuerzel Praefix, s. Kollisionsanalyse im Kontext-
    Dokument der Spec)."""
    return "wind" if metric_id == "temperature" else "temperature"


def _single_metric_dc(metric_id: str, *, enabled: bool, order: int = 0) -> UnifiedWeatherDisplayConfig:
    return UnifiedWeatherDisplayConfig(
        trip_id="x1677",
        metrics=[MetricConfig(metric_id=metric_id, enabled=enabled, order=order)],
    )


def _two_metric_dc(first: str, second: str) -> UnifiedWeatherDisplayConfig:
    return UnifiedWeatherDisplayConfig(
        trip_id="x1677",
        metrics=[
            MetricConfig(metric_id=first, enabled=True, order=0),
            MetricConfig(metric_id=second, enabled=True, order=1),
        ],
    )


# ---------------------------------------------------------------------------
# AC-13: E-Mail -- resolve_metric_col_order(dc), Bestand (#1575)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("metric_id", _ALL_METRIC_IDS)
def test_ac13_email_column_selection_and_order(metric_id):
    col_key = get_metric(metric_id).col_key
    other_id = _partner_of(metric_id)
    other_key = get_metric(other_id).col_key

    assert col_key in resolve_metric_col_order(_single_metric_dc(metric_id, enabled=True)), (
        f"(a) {metric_id} aktiv -> Spalte {col_key!r} muss erscheinen"
    )
    assert col_key not in resolve_metric_col_order(_single_metric_dc(metric_id, enabled=False)), (
        f"(b) {metric_id} inaktiv -> Spalte {col_key!r} darf nicht erscheinen"
    )

    order_a = resolve_metric_col_order(_two_metric_dc(metric_id, other_id))
    order_b = resolve_metric_col_order(_two_metric_dc(other_id, metric_id))
    assert order_a.index(col_key) < order_a.index(other_key), (
        f"(c) Reihenfolge A ({metric_id} vor {other_id}): {order_a}"
    )
    assert order_b.index(other_key) < order_b.index(col_key), (
        f"(c) Reihenfolge B ({other_id} vor {metric_id}): {order_b}"
    )


# ---------------------------------------------------------------------------
# AC-14: Telegram-rich -- render_for_channel("telegram", ...), Bestand (#429/#1575)
# ---------------------------------------------------------------------------


def _telegram_cells(dc: UnifiedWeatherDisplayConfig) -> list[str]:
    layout = render_for_channel("telegram", dc, "evening")
    return layout.table_columns + layout.detail_metrics


@pytest.mark.parametrize("metric_id", _ALL_METRIC_IDS)
def test_ac14_telegram_rich_selection_and_order(metric_id):
    if metric_id in _TELEGRAM_NIGHT_SCALAR_EXCEPTIONS:
        assert metric_id not in _telegram_cells(_single_metric_dc(metric_id, enabled=True))
        assert metric_id not in _telegram_cells(_single_metric_dc(metric_id, enabled=False))
        return

    other_id = _partner_of(metric_id)
    assert metric_id in _telegram_cells(_single_metric_dc(metric_id, enabled=True)), (
        f"(a) {metric_id} aktiv -> muss in Telegram-rich Tabelle/Detail erscheinen"
    )
    assert metric_id not in _telegram_cells(_single_metric_dc(metric_id, enabled=False)), (
        f"(b) {metric_id} inaktiv -> darf nicht erscheinen"
    )

    cells_a = _telegram_cells(_two_metric_dc(metric_id, other_id))
    cells_b = _telegram_cells(_two_metric_dc(other_id, metric_id))
    assert cells_a.index(metric_id) < cells_a.index(other_id), (
        f"(c) Reihenfolge A ({metric_id} vor {other_id}): {cells_a}"
    )
    assert cells_b.index(other_id) < cells_b.index(metric_id), (
        f"(c) Reihenfolge B ({other_id} vor {metric_id}): {cells_b}"
    )


# ---------------------------------------------------------------------------
# AC-15: SMS-Kurzform -- report.sms_text, EINZIGER roter Anteil dieser Datei
# ---------------------------------------------------------------------------


def _matrix_segment():
    """EIN Trip-Fixture (Spec-Vorgabe "effizient halten"): F.segment() plus
    reale (nicht-None) Wintersport-Aggregate -- ohne das haben snow_depth/
    snowfall_limit/fresh_snow KEINE Null-Form (anders als die 14 erweiterten
    Metriken aus #1660 B) und wuerden bei F.segment() pur gar keinen Token
    erzeugen, unabhaengig von der Auswahl -- das waere ein Messfehler, kein
    Befund zu #1677."""
    seg = F.segment()
    agg = dataclasses.replace(
        seg.aggregated, snow_depth_cm=20.0, snowfall_limit_m=1800.0, snow_new_sum_cm=3.0,
    )
    return dataclasses.replace(seg, aggregated=agg)


def _render_sms(dc: UnifiedWeatherDisplayConfig) -> str:
    report = TripReportFormatter().format_email(
        [_matrix_segment()], trip_name="Issue1677Matrix", report_type="evening",
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
    )
    return report.sms_text


def _representative_symbol(metric_id: str) -> str:
    if metric_id in SMS_MULTI_SYMBOLS_BY_METRIC:
        return SMS_MULTI_SYMBOLS_BY_METRIC[metric_id][0]
    return SMS_SYMBOL_BY_METRIC[metric_id]


# sms_format.md §5: der Threshold+Peak-Block traegt '(' ')' und '%'
# (Prozent-Schreibweise, "Wahrscheinlichkeit (%)"), und TH:/TH+: sind
# is_level (builder.py LEVELS = {0:'-',1:'L',2:'M',3:'H'}) -- ohne diese
# Zeichen/Buchstaben fand die urspruengliche Grammatik weder die
# Kern-Vorhersage-Token (R/PR/W/G, die ueber render_threshold_peak_value()
# mit Default-Schwellwert IMMER den Peak-Block tragen) noch das Gewitter-
# Stufen-Token 'TH:M@11' (Testfehler gegen sms_format.md §5/§3, Erwartung
# unveraendert). Die Stufen-Buchstaben stehen bewusst nur unmittelbar vor
# '@'/Ende/Klammer-Ende (Praefix-Kollisionsschutz z.B. 'N' vs. 'NL-'
# unveraendert, s. test_sms_user_metric_order.py::_VALUE_GRAMMAR).
_GRAMMAR_SUFFIX = re.compile(
    r"(?:(?:\d+(?:\.\d+)?%?|[LMH])(?:@\d+(?:\((?:\d+(?:\.\d+)?%?|[LMH])@\d+\))?)?|-|\?)$"
)


def _first_index_starting_with(sms: str, symbol: str) -> int | None:
    """Index des ersten Tokens, der mit ``symbol`` beginnt und danach nur aus
    Wert-Grammatik-Zeichen besteht (Praefix-Kollisionen sind fuer die hier
    verwendeten Partner-Paare ausgeschlossen, s. ``_partner_of``)."""
    body = sms.split(": ", 1)[1] if ": " in sms else sms
    for i, tok in enumerate(body.split(" ")):
        if tok.startswith(symbol) and _GRAMMAR_SUFFIX.fullmatch(tok[len(symbol):]):
            return i
    return None


def _sms_order_dc(order: list[str]) -> UnifiedWeatherDisplayConfig:
    metrics = [MetricConfig(metric_id=m, enabled=True) for m in order]
    sms_layout = [
        MetricConfig(metric_id=m, enabled=True, bucket="primary", order=i)
        for i, m in enumerate(order)
    ]
    return UnifiedWeatherDisplayConfig(
        trip_id="x1677", metrics=metrics, per_channel_layouts={"sms": sms_layout},
    )


@pytest.mark.parametrize("metric_id", _ALL_METRIC_IDS)
def test_ac15_sms_kurzform_selection_deselection_and_order(metric_id):
    symbol = _representative_symbol(metric_id)
    partner_id = _partner_of(metric_id)
    partner_symbol = _representative_symbol(partner_id)

    # (a)/(b) Auswahl/Abwahl -- heute bereits GRUEN (Bug-#944-Muster +
    # #1415/#1660 B bewachen das schon).
    sms_on = _render_sms(_two_metric_dc(metric_id, partner_id))
    sms_off = _render_sms(_single_metric_dc(partner_id, enabled=True))
    assert _first_index_starting_with(sms_on, symbol) is not None, (
        f"(a) {metric_id} aktiv -> Symbol {symbol!r} muss erscheinen: {sms_on!r}"
    )
    assert _first_index_starting_with(sms_off, symbol) is None, (
        f"(b) {metric_id} nicht gewaehlt -> kein {symbol!r}-Token: {sms_off!r}"
    )

    # (c) Nutzer-Reihenfolge -- DER rote Anteil: heute wird jede SMS-Kanal-
    # Layout-Reihenfolge auf dieselbe feste POSITIONAL-Tabelle abgebildet.
    sms_a = _render_sms(_sms_order_dc([metric_id, partner_id]))
    sms_b = _render_sms(_sms_order_dc([partner_id, metric_id]))
    ia_m = _first_index_starting_with(sms_a, symbol)
    ia_p = _first_index_starting_with(sms_a, partner_symbol)
    ib_m = _first_index_starting_with(sms_b, symbol)
    ib_p = _first_index_starting_with(sms_b, partner_symbol)
    assert ia_m is not None and ia_p is not None and ia_m < ia_p, (
        f"(c) Reihenfolge A ({metric_id} vor {partner_id}) nicht umgesetzt: {sms_a!r}"
    )
    assert ib_m is not None and ib_p is not None and ib_p < ib_m, (
        f"(c) Reihenfolge B ({partner_id} vor {metric_id}) nicht umgesetzt: {sms_b!r}"
    )

    # (d) ohne SMS-Layout -- Charakterisierung wie AC-2: heutiges Verhalten
    # bleibt der Bezugspunkt, kein RED.
    sms_default = _render_sms(_two_metric_dc(metric_id, partner_id))
    assert _first_index_starting_with(sms_default, symbol) is not None
