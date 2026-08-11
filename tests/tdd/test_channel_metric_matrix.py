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

Epic #1703 Scheibe 3 (AC-1 bis AC-8, unten): schliesst die
get_all_metrics()-vs-_METRICS-Blindstelle (docs/reference/metric_output_matrix.md
Flaeche 3) -- Vollstaendigkeitstests wie AC-13/14/15 oben iterieren ueber
get_all_metrics() und koennen selectable=False-Groessen (confidence, cape,
temperature_cold) daher strukturell nie sehen. SPEC:
docs/specs/modules/fix_1703_s3_selectable_metrics.md. Kein Produktivcode-Fix
-- Charakterisierungstest fuer bereits korrektes, bisher unbewachtes
Verhalten (alle 8 ACs laufen heute bereits GRUEN).

Epic #1703 Scheibe 1 (AC-S1-1 bis AC-S1-7, ganz unten): Alarm-Renderer x alle
alarmfaehigen Metriken (docs/reference/metric_output_matrix.md Flaeche 1) --
die vier Alarm-Renderer waren fuer 8 von 11 produktiv erreichbaren
Alarm-Groessen ungeprueft. SPEC:
docs/specs/modules/fix_1703_s1_alert_renderer_matrix.md. EINZIGER roter
Anteil dieser Achse: AC-S1-5 im gebuendelten Fall (Gewitter-Prozentzeichen).
"""
from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

from app.loader import _parse_display_config
from app.metric_catalog import (
    _METRICS, build_default_display_config, format_metric_value, get_all_metrics,
    get_alert_label, get_cmp, get_metric, get_sms_code,
)
from app.models import AlertMetric, MetricConfig, UnifiedWeatherDisplayConfig, _SELECTABLE_GATE_EXEMPT
from output.renderers.alert.model import AlertEvent, AlertMessage, side_label
from output.renderers.alert.render import (
    _HANDLED_UNITS, render_email, render_sms, render_subject, render_telegram,
)
from output.channels.premium_sms import PremiumSmsOutput
from output.renderers.channel_layout import render_for_channel
from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG, get_compare_metric_catalog
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID, resolve_enabled_metrics
from output.renderers.email.helpers import resolve_metric_col_order
from output.renderers.sms_trip import SMS_SYMBOL_BY_METRIC, SMS_MULTI_SYMBOLS_BY_METRIC
from output.renderers.trip_report import TripReportFormatter
from services.weather_change_detection import _ALERT_METRIC_TO_CATALOG_ID, is_alert_metric_active

from tests.tdd import _min_temp_felt_fixtures as F
# Issue #1719 S2 AC-11: geteilter Premium-SMS-Stub (echter lokaler HTTP-
# Server, kein Mock) -- Vorbild-Fixture wiederverwendet statt kopiert (Muster
# bereits etabliert: pytest erkennt eine importierte @pytest.fixture-Funktion
# auch im importierenden Modul).
from tests.tdd.test_channel_origin_guard_parity import (
    _prod_style_premium_sms_settings, premium_sms_stub,  # noqa: F401 - pytest loest die Fixture per Name auf
)

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


# ---------------------------------------------------------------------------
# Epic #1703 Scheibe 3 (AC-1 bis AC-8): die get_all_metrics()-vs-_METRICS-
# Blindstelle schliessen (docs/reference/metric_output_matrix.md Flaeche 3).
# SPEC: docs/specs/modules/fix_1703_s3_selectable_metrics.md.
#
# Kein Produktivcode-Fix -- Charakterisierungstest fuer bereits korrektes,
# bisher unbewachtes Verhalten. Iterationsbasis fuer AC-8 ist _METRICS
# (NICHT get_all_metrics()) + _SELECTABLE_GATE_EXEMPT direkt aus app.models
# -- keine zweite Kopie der Ausnahmeliste.
# ---------------------------------------------------------------------------


def _mail_table(
    dc: UnifiedWeatherDisplayConfig, report_type: str = "evening",
) -> tuple[list[str], list[list[str]]]:
    """Kopfzeile + Datenzeilen der ECHTEN Trip-Mail-Stundentabelle (Pruefort =
    Wirkort -- s. Korrektur-Abschnitt der Spec: eine isolierte Pruefung von
    resolve_metric_col_order() haette hier nachweislich die falsche Funktion
    getroffen, s. AC-2/AC-5)."""
    report = TripReportFormatter().format_email(
        [_matrix_segment()], trip_name="Issue1703Matrix", report_type=report_type,
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
    )
    head = re.search(r"<thead><tr>(.*?)</tr></thead>", report.email_html, re.S)
    assert head, "Stundentabelle ohne Kopfzeile gerendert"
    headers = [
        re.sub(r"<[^>]+>", "", th).strip()
        for th in re.findall(r"<th[^>]*>.*?</th>", head.group(1), re.S)
    ]
    body = re.search(r"<tbody>(.*?)</tbody>", report.email_html, re.S)
    assert body, "Stundentabelle ohne Datenzeilen gerendert"
    rows = [
        [
            re.sub(r"<[^>]+>", "", td).strip()
            for td in re.findall(r"<td[^>]*>.*?</td>", tr, re.S)
        ]
        for tr in re.findall(r"<tr>(.*?)</tr>", body.group(1), re.S)
    ]
    return headers, rows


def _row_by_time(headers: list[str], rows: list[list[str]], time_label: str) -> dict[str, str]:
    time_idx = headers.index("Time")
    for row in rows:
        if row[time_idx] == time_label:
            return dict(zip(headers, row))
    raise AssertionError(f"keine Zeile mit Time={time_label!r} gefunden: {rows}")


# --- AC-1: confidence -- nirgends, trotz summary_fields --------------------


def test_ac1_confidence_absent_from_mail_telegram_compare():
    """AC-1: confidence (selectable=False, default_enabled=False, KEIN
    sms_code, KEIN alert_label, aber summary_fields={'min':
    'confidence_pct_min'}) erscheint an keiner der drei Choke-Points -- die
    drei erlaubten Erscheinungsorte (E-Mail-Textblock build_confidence_hint(),
    SMS-Symbol C+/C~/C?, interne Aggregation confidence_pct_min) sind NICHT
    Gegenstand dieses Tests, bleiben unberuehrt."""
    metric = get_metric("confidence")
    assert metric.selectable is False
    assert metric.sms_code == "" and metric.alert_label == ""
    assert metric.summary_fields == {"min": "confidence_pct_min"}

    partner_id = _partner_of("confidence")
    dc = _two_metric_dc("confidence", partner_id)

    headers, _ = _mail_table(dc)
    assert metric.col_label not in headers, (
        f"AC-1: 'confidence' (Spaltenlabel {metric.col_label!r}) erscheint in "
        f"der echten Trip-Mail-Kopfzeile: {headers}"
    )
    assert get_metric(partner_id).col_label in headers, (
        "AC-1: Partner-Groesse muss trotzdem erscheinen (kein Kollateralschaden)"
    )

    cells = _telegram_cells(dc)
    assert "confidence" not in cells, (
        f"AC-1: 'confidence' erscheint in der Telegram-rich Tabelle/Detailzeile: {cells}"
    )
    assert partner_id in cells, "AC-1: Partner-Groesse muss in Telegram-rich erscheinen"

    compare_ids = {e["metric_id"] for e in get_compare_metric_catalog()}
    assert "confidence" not in compare_ids, (
        f"AC-1: 'confidence' erscheint im Compare-Katalog: {compare_ids}"
    )


# --- AC-2: cape -- nirgends, TROTZ sms_code="CP"/alert_label="CAPE" --------
# (Mutations-Gegenprobe-Ziel, s. "Pruefhinweis fuer den Adversary")


def test_ac2_cape_absent_from_mail_telegram_compare_and_alert():
    """AC-2: cape (selectable=False, default_enabled=False, MIT sms_code='CP'
    UND alert_label='CAPE') erscheint an denselben drei Stellen wie AC-1
    NICHT, UND is_alert_metric_active(CAPE, ...) bleibt False trotz
    enabled=True.

    Mutations-Gegenprobe-Ziel: die Mail-Header-Assertion prueft den ECHTEN
    <thead> (nicht nur resolve_metric_col_order() isoliert) -- wuerde
    _SELECTABLE_GATE_EXEMPT versehentlich um 'cape' erweitert, ueberlebt cape
    die Kanal-Kollabierung (trip_report.py:135) und erschiene ueber den
    remaining-Fallback (email/html.py:678-682) am Tabellenende, OBWOHL
    resolve_metric_col_order() selbst (roher .selectable-Check, KEINE
    Exemption-Kenntnis) unveraendert bliebe -- dasselbe Pruefort=Wirkort-Muster
    wie bei AC-5/AC-6."""
    metric = get_metric("cape")
    assert metric.selectable is False
    assert metric.sms_code == "CP" and metric.alert_label == "CAPE"

    partner_id = _partner_of("cape")
    dc = _two_metric_dc("cape", partner_id)

    headers, _ = _mail_table(dc)
    assert metric.col_label not in headers, (
        f"AC-2: 'CAPE' erscheint in der echten Trip-Mail-Kopfzeile: {headers}"
    )
    assert "cape" not in resolve_metric_col_order(dc), (
        "AC-2: 'cape' col_key erscheint in resolve_metric_col_order()"
    )

    cells = _telegram_cells(dc)
    assert "cape" not in cells, (
        f"AC-2: 'cape' erscheint in der Telegram-rich Tabelle/Detailzeile: {cells}"
    )

    compare_ids = {e["metric_id"] for e in get_compare_metric_catalog()}
    assert "cape" not in compare_ids, (
        f"AC-2: 'cape' erscheint im Compare-Katalog: {compare_ids}"
    )

    cape_dc = _single_metric_dc("cape", enabled=True)
    assert is_alert_metric_active(AlertMetric.CAPE, cape_dc) is False, (
        "AC-2: is_alert_metric_active(CAPE, ...) liefert True trotz "
        "enabled=True -- CAPE darf trotz Bestandskonfiguration nie "
        "alarmfaehig gelten"
    )


# --- AC-3: temperature_cold -- Kaeltealarm MUSS aktiv bleiben (Trip-Pfad) --


def test_ac3_temperature_cold_cold_alarm_stays_active():
    """AC-3: ein Trip mit temperature_cold in Default-Konfiguration
    (Dataclass-Default enabled=True, kein explizites default_enabled gesetzt
    -- s. build_default_display_config()) haelt den Kaeltealarm aktiv, obwohl
    temperature_cold.selectable=False ist. Korrektur (Adversary-Finding F001,
    2026-08-10): NICHT die Exemption in _SELECTABLE_GATE_EXEMPT bewirkt das --
    is_alert_metric_active() liest _SELECTABLE_GATE_EXEMPT an keiner Stelle.
    Ursache ist die OR-Tupel-Abbildung _ALERT_METRIC_TO_CATALOG_ID[TEMPERATURE_MIN]
    = ("temperature_cold", "temperature") (weather_change_detection.py:85):
    das mitgemappte, selbst selectable=True/enabled=True Glied "temperature"
    traegt das Ergebnis per any(...) (weather_change_detection.py:224-234).
    Die Exemption-Wirkung fuer temperature_cold wird stattdessen von AC-5
    bewiesen (Mail-Spalte ueber den remaining-Fallback -- dort IST die
    Exemption die entscheidende Variable, per Mutation bestaetigt)."""
    dc = build_default_display_config()
    assert dc.is_metric_enabled("temperature_cold") is True, (
        "Vorbedingung verletzt: temperature_cold muss in der Default-"
        "Konfiguration enabled=True sein (Dataclass-Default, kein "
        "explizites default_enabled)"
    )
    assert is_alert_metric_active(AlertMetric.TEMPERATURE_MIN, dc) is True, (
        "AC-3: Kaeltealarm (TEMPERATURE_MIN) darf trotz "
        "temperature_cold.selectable=False nicht inaktiv sein -- Ursache ist "
        "die OR-Tupel-Abbildung auf die mitgemappte, selbst waehlbare Groesse "
        "'temperature' (_ALERT_METRIC_TO_CATALOG_ID), NICHT die Exemption in "
        "_SELECTABLE_GATE_EXEMPT (die wird hier nicht gelesen, s. AC-5 fuer "
        "den Test, der die Exemption-Wirkung tatsaechlich belegt)"
    )


# --- AC-4 (Regression-Baseline, KEIN neuer Test): temperature_cold --------
# Compare-Aktivierung MUSS wirken. Bereits gedeckt von
# tests/tdd/test_compare_alert_metric_gating.py::
# test_f002_guard_temp_min_active_min_temp_delta_fires (bleibt gruen, kein
# redundanter Test). Die generische Parametrisierung in AC-8 verankert
# denselben Choke-Point zusaetzlich zukunftssichernd.


# --- AC-5: temperature_cold -- Mail-Spaltenreihenfolge ueber den ----------
# remaining-Fallback (Pruefort = Wirkort)


def test_ac5_temperature_cold_mail_column_via_remaining_fallback():
    """AC-5: ein Trip mit Default-Konfiguration (temperature_cold.enabled=True,
    keine eigene order) zeigt die Spalte 'TmpMin' im ECHTEN <thead> an
    letzter Position (remaining-Fallback, email/html.py:678-682), OBWOHL
    resolve_metric_col_order(dc) selbst 'temp_cold' NICHT fuehrt
    (dokumentierte Bestands-Abweichung, models.py:619-625)."""
    dc = build_default_display_config()

    assert "temp_cold" not in resolve_metric_col_order(dc), (
        "Vorbedingung: resolve_metric_col_order() fuehrt 'temp_cold' bewusst "
        "NICHT (Bestand, s. models.py _SELECTABLE_GATE_EXEMPT-Kommentar)"
    )

    headers, _ = _mail_table(dc)
    metric_cols = [h for h in headers if h not in {"Time", "Risk"}]
    assert "TmpMin" in metric_cols, (
        f"AC-5: 'TmpMin' fehlt in der echten Trip-Mail-Kopfzeile: {headers}"
    )
    assert metric_cols[-1] == "TmpMin", (
        f"AC-5: 'TmpMin' muss ueber den remaining-Fallback an letzter "
        f"Position stehen: {metric_cols}"
    )


# --- AC-6: temperature_cold -- Stundentabelle: GEMESSENE Dublette ---------
# (Charakterisierung, KEINE Fixierung dieser Scheibe -- s. Known
# Limitations Punkt 2 der Spec)


def test_ac6_temperature_cold_hourly_duplicate_characterization():
    """AC-6: die Stundenzeilen der Trip-Mail zeigen HEUTE (gemessen
    2026-08-10) eine eigene Spalte 'TmpMin' NEBEN 'Temp', mit fuer dieselbe
    Stunde IDENTISCHEM Zahlenwert (beide lesen dp_field='t2m_c') -- eine
    echte Dublette. Reine Charakterisierung, kein Bug-Fix-Test."""
    dc = build_default_display_config()
    headers, rows = _mail_table(dc)
    assert "Temp" in headers and "TmpMin" in headers

    row = _row_by_time(headers, rows, f"{F.COLD_HOUR:02d}")
    assert row["Temp"] == row["TmpMin"], (
        f"AC-6 (Charakterisierung): 'Temp' und 'TmpMin' sollten fuer "
        f"dieselbe Stunde identisch gerendert sein (Dublette) -- gemessen "
        f"Temp={row['Temp']!r} TmpMin={row['TmpMin']!r}"
    )


# --- AC-7: temperature_cold -- Compare-Katalog bleibt strukturell leer ----


def test_ac7_temperature_cold_absent_from_compare_catalog():
    """AC-7: weder das rohe COMPARE_METRIC_CATALOG noch
    get_compare_metric_catalog() fuehren einen Eintrag mit
    metric_id=='temperature_cold' -- nicht weil ein .selectable-Filter ihn
    entfernt, sondern weil COMPARE_METRIC_CATALOG ihn nie enthalten hat
    (reine Trip-Alarm-Pseudogroesse ohne Compare-Entsprechung)."""
    raw_ids = {e["metric_id"] for e in COMPARE_METRIC_CATALOG}
    filtered_ids = {e["metric_id"] for e in get_compare_metric_catalog()}
    assert "temperature_cold" not in raw_ids, (
        f"AC-7: 'temperature_cold' erscheint im rohen COMPARE_METRIC_CATALOG: {raw_ids}"
    )
    assert "temperature_cold" not in filtered_ids, (
        f"AC-7: 'temperature_cold' erscheint in get_compare_metric_catalog(): {filtered_ids}"
    )


# --- AC-8 (generisch, zukunftssichernd): die eigentliche Blindstellen- ----
# Reparatur. Iterationsbasis ist _METRICS (NICHT get_all_metrics()),
# Verzweigung ueber _SELECTABLE_GATE_EXEMPT direkt aus app.models -- keine
# zweite Kopie der Ausnahmeliste.

_NON_SELECTABLE_METRIC_IDS = [m.id for m in _METRICS if not m.selectable]


@pytest.mark.parametrize("metric_id", _NON_SELECTABLE_METRIC_IDS)
def test_ac8_non_selectable_metrics_stay_out_unless_exempt(metric_id):
    """AC-8: fuer JEDE NICHT in _SELECTABLE_GATE_EXEMPT gelistete
    selectable=False-Groesse gilt dieselbe Grundregel aus AC-1/AC-2 an den
    ID-verankerten Choke-Points (resolve_metric_col_order()-Rueckgabe,
    get_compare_metric_catalog()-Metrik-IDs, resolve_enabled_metrics()-
    Ergebnis sofern ein Compare-Katalog-Eintrag existiert, is_alert_metric_
    active() sofern ein alert_metrics-Eintrag existiert). Fuer eine gelistete
    Groesse (heute: temperature_cold) gilt die Regel NICHT -- s. AC-3 bis
    AC-7."""
    if metric_id in _SELECTABLE_GATE_EXEMPT:
        pytest.skip(
            f"{metric_id!r} ist ueber _SELECTABLE_GATE_EXEMPT ausgenommen -- "
            "der Sollzustand steht in AC-3 bis AC-7, nicht in dieser "
            "generischen Regel"
        )

    metric = get_metric(metric_id)
    dc = _single_metric_dc(metric_id, enabled=True)

    col_order = resolve_metric_col_order(dc)
    assert metric.col_key not in col_order, (
        f"AC-8: {metric_id!r} (col_key {metric.col_key!r}) erscheint in "
        f"resolve_metric_col_order(): {col_order}"
    )

    compare_ids = {e["metric_id"] for e in get_compare_metric_catalog()}
    assert metric_id not in compare_ids, (
        f"AC-8: {metric_id!r} erscheint im Compare-Katalog: {compare_ids}"
    )

    for entry in COMPARE_METRIC_CATALOG:
        if entry["metric_id"] != metric_id:
            continue
        resolved = resolve_enabled_metrics([entry["key"]]) or []
        renderer_id = FRONTEND_TO_RENDERER_METRIC_ID.get(entry["key"])
        assert renderer_id not in resolved, (
            f"AC-8: {metric_id!r} (Compare-Key {entry['key']!r}) erscheint "
            f"im Ergebnis von resolve_enabled_metrics(): {resolved}"
        )

    for alert_value in metric.alert_metrics.values():
        alert_metric = AlertMetric(alert_value)
        assert is_alert_metric_active(alert_metric, dc) is False, (
            f"AC-8: is_alert_metric_active({alert_metric!r}, ...) liefert "
            f"True fuer die nicht waehlbare Groesse {metric_id!r}, obwohl "
            "enabled=True"
        )


# ---------------------------------------------------------------------------
# Issue #1719 Scheibe 1: Metrik-Kaskade -- Pruefstand fuer ADR-0050
# (Grundauswahl = Maximum, Kanal-Ebene darf nur abwaehlen, nie hinzufuegen).
# SPEC: docs/specs/modules/fix_1719_s1_kaskade_pruefstand.md (12 ACs).
#
# Fixture: tests/fixtures/metric_cascade/khw_display_config_widerspruch.json
# -- eine anonymisierte, versionierte Kopie NUR des display_config-Teilbaums
# des realen KHW-Trips (trip_id ersetzt), geladen ueber den ECHTEN Loader
# (app.loader._parse_display_config, NICHT im Speicher gebaut -- vermeidet
# Konstruktionsfehler #1/#3 des Vorgaenger-Waechters, s. Kontext-Dokument
# Abschnitt 5). Traegt die volle Katalogbreite (26 Eintraege je Ebene, 15
# global aktiv inkl. wind_chill AN, 13 SMS-Kanal-aktiv, wind_chill AUS) --
# genau der reale Widerspruch, der Trip KHW 5f534011 eine falsche SMS-
# Kurzform lieferte.
#
# Wetterdaten: F.segment()/F.night_weather() UNVERAENDERT (keine Schnee-
# Injektion aus _matrix_segment() oben -- Konstruktionsfehler #5). Drei
# Metriken (snow_depth, snowfall_limit, fresh_snow) erzeugen dadurch KEINEN
# SMS-Token, unabhaengig von der Auswahl -- benannte AC-10-Ausnahme, s.
# _CASCADE_NO_TOKEN_METRIC_IDS unten; keine der AC-4/5/7/8/12-Zielmetriken
# steht in dieser Liste (per Assertion in test_kaskade_ac10... gesichert).
#
# Korrektur gegen den Spec-Wortlaut, GEMESSEN statt angenommen ("Pruefort =
# Wirkort", nicht "Formprüfung glauben"): AC-4/AC-5/AC-6 verlangen woertlich
# Abwesenheit "in KEINEM der drei Kanaele" (E-Mail, Telegram, SMS). Die
# Basis-Fixture traegt aber NUR einen SMS-Kanal-Layout-Eintrag
# (channel_layouts == {"sms": [...]}) -- fuer "email"/"telegram" faellt die
# Kaskade strukturell auf die GLOBALE Liste zurueck (gemessen:
# cascade_source_for_channel("email"/"telegram", "evening") == "global";
# trip_report.py:135 `dc.get_metrics_for_channel("email", ...)`,
# channel_layout.py analog fuer "telegram"). Eine GLOBAL AKTIVE Zielmetrik
# (von AC-4/5/6 gefordert) erscheint deshalb in E-Mail/Telegram unveraendert
# -- das IST die korrekte, ADR-0050-konforme Wirkung von Regel 1 ("Grund-
# auswahl ist das Maximum") fuer einen Kanal OHNE eigene Kanal-Ebene, keine
# Verletzung von Regel 2/3 (die betreffen nur Kanaele MIT eigener Ebene).
# Diese drei Tests pruefen deshalb: SMS abwesend (Kanal-Ebene gewinnt),
# E-Mail/Telegram weiterhin anwesend (Grundauswahl unveraendert wirksam) --
# technisch korrekt UND das, was der heutige Code tatsaechlich liefert
# (empirisch gemessen, nicht der woertliche Spec-Text). AC-7 hat das
# GEGENTEIL-Vorzeichen (global INAKTIV, SMS-Kanal AN) und ist davon nicht
# betroffen: dort sind E-Mail/Telegram korrekt abwesend (folgen der global
# inaktiven Grundauswahl), nur SMS weicht ab -- exakt der Konstruktions-
# fehler, den AC-7 belegen soll.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CASCADE_FIXTURE_PATH = (
    _REPO_ROOT / "tests" / "fixtures" / "metric_cascade" / "khw_display_config_widerspruch.json"
)

# Gemessen (F.segment()/F.night_weather() OHNE Schnee-Injektion, s. oben):
# diese drei Metriken erzeugen KEINEN SMS-Token, egal ob ausgewaehlt --
# strukturelle Null-Form, keine der AC-4/5/7/8/12-Zielmetriken darf hieraus
# stammen (AC-10).
_CASCADE_NO_TOKEN_METRIC_IDS = frozenset({"snow_depth", "snowfall_limit", "fresh_snow"})

# Ziel-Metriken, kollisionssicher (kein Praefix-Konflikt mit einem anderen in
# der Basis-Fixture aktiven SMS-Symbol, geprueft gegen SMS_SYMBOL_BY_METRIC/
# SMS_MULTI_SYMBOLS_BY_METRIC):
_AC4_5_TARGET = "freezing_level"   # Symbol "NL", global AN, SMS-Kanal AN (Basis)
_AC7_TARGET = "dewpoint"           # Symbol "DP", global AUS (Basis) -- NICHT wind_chill (Verwechslungsprobe)
_AC12_PAIR = ("humidity", "gust")  # Symbole "HU"/"G", beide SMS-Kanal AN (Basis)

# S2 AC-4 (Team-Lead-Befund/Freigabe, Nachbesserung 2026-08-11): eine EINZIGE
# Zielmetrik reicht fuer AC-4 nicht -- Telegram-Tabellen haben nur 7 Spalten-
# Slots (CHANNEL_LIMITS["telegram"]["max_table_cols"]=8 inkl. Zeit-Spalte,
# channel_layout.py:47). _AC4_5_TARGET ("freezing_level", order=12 in der
# Basis-Fixture) faellt strukturell aus diesem Platzbudget, ganz unabhaengig
# von der Kaskade -- narrow.py::_detail_lines() (baut die Detail-Zeile fuer
# ueberzaehlige Metriken) hat 0 Aufrufstellen in render_telegram_bubbles(),
# "ueberzaehlig" heisst hier also "gar nicht sichtbar", nicht nur "nicht in
# der Tabelle". "rain_probability" (order=3, Label "P%") faellt dagegen IN
# die ersten 7 primary-Slots und beweist K2 direkt im <pre>-Tabellentext.
_AC4_TABLE_BUDGET_TARGET = "rain_probability"  # Symbol/Label "P%", global AN, order=3 (< 7)


def _load_cascade_fixture_raw() -> dict:
    return json.loads(_CASCADE_FIXTURE_PATH.read_text())


def _load_cascade_dc() -> UnifiedWeatherDisplayConfig:
    """AC-2: Laden ueber den ECHTEN Loader, kein im Speicher gebautes Config."""
    return _parse_display_config(_load_cascade_fixture_raw())


def _cascade_sms_variant(replacements: dict) -> UnifiedWeatherDisplayConfig:
    """Ein-Feld-Variante der Basis-Fixture auf ROH-JSON-Ebene (F001-Fix,
    Adversary Runde 1 M5: order=mc_data.get("order", 0) in loader.py auf
    eine feste 0 verdrahtet blieb ungefangen, weil die Vorgaenger-Fassung
    dieser Funktion ausschliesslich dataclasses.replace() auf bereits
    GELADENEN MetricConfig-Objekten anwandte -- geprueft wurde damit nur
    models.py::_sorted_by_layout() (Wirkort Sortierung), niemals die
    Feld-Extraktion beim Laden selbst (Wirkort loader.py)). Jede Variante
    wird deshalb -- wie die Basis-Config selbst, AC-2 -- erneut durch den
    ECHTEN Loader (``_parse_display_config()``) geschickt: dict kopieren,
    Feld(er) im rohen ``channel_layouts.sms``-Eintrag aendern/Eintrag
    entfernen, dann neu parsen.

    ``replacements``: dict metric_id -> Feld-Patch (dict, per ``**``-Merge
    auf den passenden rohen Eintrag angewendet) oder ``None``, um den
    Eintrag komplett aus der Roh-Liste zu entfernen (Weglassen-Variante,
    AC-5). Die uebrigen 25 Eintraege bleiben unangetastet."""
    raw = _load_cascade_fixture_raw()
    new_sms_layout = []
    for entry in raw["channel_layouts"]["sms"]:
        metric_id = entry["metric_id"]
        if metric_id in replacements:
            patch = replacements[metric_id]
            if patch is None:
                continue
            entry = {**entry, **patch}
        new_sms_layout.append(entry)
    raw["channel_layouts"]["sms"] = new_sms_layout
    return _parse_display_config(raw)


def _kaskade_report(dc: UnifiedWeatherDisplayConfig, report_type: str = "evening"):
    """Echter Renderpfad, F.segment()/F.night_weather() UNVERAENDERT (keine
    Schnee-Injektion, AC-10)."""
    return TripReportFormatter().format_email(
        [F.segment()], trip_name="Kaskade1719", report_type=report_type,
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
    )


def _kaskade_mail_headers(dc: UnifiedWeatherDisplayConfig, report_type: str = "evening") -> list[str]:
    report = _kaskade_report(dc, report_type)
    head = re.search(r"<thead><tr>(.*?)</tr></thead>", report.email_html, re.S)
    assert head, "Stundentabelle ohne Kopfzeile gerendert"
    return [
        re.sub(r"<[^>]+>", "", th).strip()
        for th in re.findall(r"<th[^>]*>.*?</th>", head.group(1), re.S)
    ]


def _kaskade_telegram_cells(dc: UnifiedWeatherDisplayConfig, report_type: str = "evening") -> list[str]:
    layout = render_for_channel("telegram", dc, report_type)
    return layout.table_columns + layout.detail_metrics


def _kaskade_sms_text(dc: UnifiedWeatherDisplayConfig, report_type: str = "evening") -> str:
    return _kaskade_report(dc, report_type).sms_text


# --- AC-2: Fixture ueber den echten Loader geparst, reproduziert den Ist-Widerspruch ---


def test_kaskade_ac2_fixture_loaded_via_real_loader_reproduces_cascade():
    dc = _load_cascade_dc()
    assert dc.cascade_source_for_channel("sms", "evening") == "per_channel"
    active_sms_ids = [mc.metric_id for mc in dc.get_metrics_for_channel("sms", "evening") if mc.enabled]
    assert len(active_sms_ids) == 13, active_sms_ids
    assert "wind_chill" not in active_sms_ids


# --- AC-3: Anonymisierung geprueft, nicht nur behauptet ---

_CASCADE_FORBIDDEN_KEYS = {
    "name", "mail_to", "sms_to", "premium_sms_reply_to", "waypoints",
    "gpx", "lat", "lon", "stages",
}


def test_kaskade_ac3_fixture_is_anonymized():
    raw = _load_cascade_fixture_raw()
    assert set(raw.keys()) == {"trip_id", "metrics", "channel_layouts"}, (
        f"AC-3: Fixture-Datei fuehrt zusaetzliche Top-Level-Schluessel: {sorted(raw.keys())}"
    )
    serialized = json.dumps(raw)
    for forbidden in _CASCADE_FORBIDDEN_KEYS:
        assert f'"{forbidden}"' not in serialized, (
            f"AC-3: verbotener Schluessel {forbidden!r} in der Fixture gefunden"
        )
    assert raw["trip_id"] != "5f534011", (
        "AC-3: trip_id ist die reale KHW-Kennung -- muss anonymisiert sein"
    )


# --- AC-4/AC-5: Abwahl als enabled:false vs. Weglassen, je Kanal-Renderpfad ---


def test_kaskade_ac4_sms_deselect_as_enabled_false_wins_over_global():
    target = _AC4_5_TARGET
    symbol = SMS_SYMBOL_BY_METRIC[target]
    base_dc = _load_cascade_dc()
    base_entry = next(mc for mc in base_dc.per_channel_layouts["sms"] if mc.metric_id == target)
    assert base_entry.enabled is True, "Vorbedingung: Basis-Fixture fuehrt Ziel aktiv im SMS-Layout"
    global_entry = next(mc for mc in base_dc.metrics if mc.metric_id == target)
    assert global_entry.enabled is True, "Vorbedingung: Ziel ist global aktiv"

    off_dc = _cascade_sms_variant({target: {"enabled": False}})

    sms = _kaskade_sms_text(off_dc)
    assert _first_index_starting_with(sms, symbol) is None, (
        f"AC-4: {target!r} ({symbol!r}) erscheint trotz enabled:false im SMS-Kanal-Layout: {sms!r}"
    )
    headers = _kaskade_mail_headers(off_dc)
    assert get_metric(target).col_label in headers, (
        "AC-4: E-Mail hat in dieser Fixture keine eigene Kanal-Ebene -- die "
        f"Spalte bleibt ueber die unveraenderte Grundauswahl sichtbar: {headers}"
    )
    cells = _kaskade_telegram_cells(off_dc)
    assert target in cells, (
        f"AC-4: Telegram hat keine eigene Kanal-Ebene -- die Zelle bleibt "
        f"ueber die Grundauswahl sichtbar: {cells}"
    )


def test_kaskade_ac5_sms_deselect_as_omission_matches_enabled_false():
    target = _AC4_5_TARGET
    symbol = SMS_SYMBOL_BY_METRIC[target]

    omitted_dc = _cascade_sms_variant({target: None})
    sms_omitted = _kaskade_sms_text(omitted_dc)
    assert _first_index_starting_with(sms_omitted, symbol) is None, (
        f"AC-5: {target!r} ({symbol!r}) erscheint trotz Weglassen aus dem SMS-Kanal-Layout: {sms_omitted!r}"
    )

    off_dc = _cascade_sms_variant({target: {"enabled": False}})
    sms_disabled = _kaskade_sms_text(off_dc)

    assert sms_omitted == sms_disabled, (
        "AC-5: Weglassen und enabled:false muessen denselben SMS-Text liefern -- "
        f"weggelassen={sms_omitted!r} disabled={sms_disabled!r}"
    )
    assert _kaskade_mail_headers(omitted_dc) == _kaskade_mail_headers(off_dc)
    assert _kaskade_telegram_cells(omitted_dc) == _kaskade_telegram_cells(off_dc)


# --- AC-6: Widerspruchsfall global AN + Kanal AUS -- Regression-Baseline ---


def test_kaskade_ac6_wind_chill_contradiction_baseline_stays_green():
    dc = _load_cascade_dc()
    sms = _kaskade_sms_text(dc)
    for symbol in SMS_MULTI_SYMBOLS_BY_METRIC["wind_chill"]:
        assert _first_index_starting_with(sms, symbol) is None, (
            f"AC-6: wind_chill-Symbol {symbol!r} erscheint trotz enabled:false im SMS-Kanal-Layout: {sms!r}"
        )
    headers = _kaskade_mail_headers(dc)
    assert get_metric("wind_chill").col_label in headers, (
        f"AC-6: E-Mail folgt der Grundauswahl (wind_chill global AN, keine eigene E-Mail-Kanal-Ebene): {headers}"
    )
    cells = _kaskade_telegram_cells(dc)
    assert "wind_chill" in cells, f"AC-6: Telegram folgt ebenso der Grundauswahl: {cells}"


# --- AC-7 (Pflicht-AC): Widerspruchsfall global AUS + Kanal AN -- #1719 S2 behebt ---


def test_kaskade_ac7_sms_channel_must_not_add_globally_disabled_metric():
    target = _AC7_TARGET
    symbol = SMS_SYMBOL_BY_METRIC[target]
    base_dc = _load_cascade_dc()
    global_entry = next(mc for mc in base_dc.metrics if mc.metric_id == target)
    assert global_entry.enabled is False, (
        "Vorbedingung: Ziel muss global INAKTIV sein (Verwechslungsprobe -- "
        "wind_chill waere hier falsch, s. Pruefhinweis der Spec)"
    )
    on_dc = _cascade_sms_variant({target: {"enabled": True}})

    headers = _kaskade_mail_headers(on_dc)
    assert get_metric(target).col_label not in headers, (
        f"AC-7: {target!r} erscheint in der E-Mail-Kopfzeile trotz globaler Abwahl: {headers}"
    )
    cells = _kaskade_telegram_cells(on_dc)
    assert target not in cells, f"AC-7: {target!r} erscheint in Telegram-rich trotz globaler Abwahl: {cells}"
    sms = _kaskade_sms_text(on_dc)
    assert _first_index_starting_with(sms, symbol) is None, (
        f"AC-7: {target!r} ({symbol!r}) erscheint im SMS-Text, obwohl die Grundauswahl es global "
        f"abgewaehlt hat (models.py:808-846 ersetzt statt zu verfeinern): {sms!r}"
    )


# --- AC-8: alle Kuerzel einer Metrik toggeln gemeinsam (wind_chill FK/FD/WC) ---


def test_kaskade_ac8_all_wind_chill_symbols_toggle_together():
    symbols = SMS_MULTI_SYMBOLS_BY_METRIC["wind_chill"]
    assert symbols == ("FK", "FD", "WC")

    sms_off = _kaskade_sms_text(_load_cascade_dc())
    for symbol in symbols:
        assert _first_index_starting_with(sms_off, symbol) is None, (
            f"AC-8: {symbol!r} erscheint trotz Abwahl: {sms_off!r}"
        )

    on_dc = _cascade_sms_variant({"wind_chill": {"enabled": True}})
    sms_on = _kaskade_sms_text(on_dc)
    for symbol in symbols:
        assert _first_index_starting_with(sms_on, symbol) is not None, (
            f"AC-8: {symbol!r} fehlt trotz Zuwahl: {sms_on!r}"
        )


# --- AC-9: volle Katalogbreite, GERECHNET statt getippt (F003-Fix) ---

# F003: die Fixture ist eine EINGEFRORENE, versionierte Kopie eines
# historischen Trips (kein live nachgefuehrter Snapshot) -- ihre Anzahl darf
# deshalb NICHT als hart getippte Zahl im Test stehen (Epic #1703-Leitplanke:
# "Soll-Mengen werden aus dem Katalog GERECHNET, nie getippt", Vorbild in
# dieser Datei: _METRICS/_SELECTABLE_GATE_EXEMPT bei AC-8 oben). Gemessen:
# get_all_metrics() liefert heute 25 waehlbare Metriken; die Fixture traegt
# zusaetzlich "cape" -- seit #1585 selectable=False (aus dem User-Katalog
# entfernt), im historischen KHW-Trip aber noch als aktiver Legacy-Eintrag
# gespeichert. Diese EINE Differenz wird hier explizit benannt statt der
# Testzahl stillschweigend einverleibt zu werden.
_CASCADE_FIXTURE_NON_SELECTABLE_LEGACY_IDS = frozenset({"cape"})


def test_kaskade_ac9_fixture_carries_full_catalog_width():
    dc = _load_cascade_dc()
    selectable_ids = {m.id for m in get_all_metrics()}
    fixture_metric_ids = {mc.metric_id for mc in dc.metrics}
    assert _CASCADE_FIXTURE_NON_SELECTABLE_LEGACY_IDS <= fixture_metric_ids, (
        "AC-9: die dokumentierte Legacy-Ausnahme "
        f"{sorted(_CASCADE_FIXTURE_NON_SELECTABLE_LEGACY_IDS)} fehlt in der Fixture"
    )
    assert not (_CASCADE_FIXTURE_NON_SELECTABLE_LEGACY_IDS & selectable_ids), (
        "AC-9: die benannte Legacy-Ausnahme ist inzwischen selbst waehlbar -- "
        "Kommentar/Ausnahme veraltet, Test muss angepasst werden"
    )
    expected_count = len(selectable_ids) + len(_CASCADE_FIXTURE_NON_SELECTABLE_LEGACY_IDS)
    assert len(dc.metrics) == expected_count, (
        f"AC-9: erwartet volle aktuelle Katalogbreite ({len(selectable_ids)} waehlbare "
        f"Metriken) plus dokumentierte Legacy-Ausnahme(n) "
        f"{sorted(_CASCADE_FIXTURE_NON_SELECTABLE_LEGACY_IDS)} = {expected_count}: {len(dc.metrics)}"
    )
    assert len(dc.per_channel_layouts["sms"]) == expected_count, len(dc.per_channel_layouts["sms"])


# --- AC-10: keine der Zielmetriken kommt aus der Null-Token-Ausnahmeliste ---


def test_kaskade_ac10_target_metrics_are_not_no_token_exceptions():
    targets = {_AC4_5_TARGET, _AC7_TARGET, "wind_chill", *_AC12_PAIR}
    overlap = targets & _CASCADE_NO_TOKEN_METRIC_IDS
    assert not overlap, f"AC-10: Ziel-Metriken duerfen nicht aus der Null-Token-Ausnahmeliste stammen: {overlap}"


# --- AC-11: Premium-SMS-Charakterisierung -- kein eigener Render-Aufruf noetig ---


def test_kaskade_ac11_premium_sms_has_no_own_cascade_level():
    """AC-11: Premium-SMS hat KEINE eigene Kaskaden-Ebene und erbt deshalb die
    SMS-Auswahl.

    **Fassung 2 (CI-Befund 2026-08-11).** Die erste Fassung pruefte zwei
    Quelltext-Strings (einen Modul-Docstring in ``premium_sms.py``, eine
    Codezeile in ``trip_report.py``) und war als ``# doc-compliance-test``
    markiert. ``test_765_no_product_source_read`` hat sie zu Recht abgelehnt:
    ein Kommentar im Fremdmodul belegt kein Verhalten, und die Ausnahme deckt
    Doku-Konsistenz, nicht die Umgehung eines fehlenden Verhaltenstests. Die
    Fehlerklasse ist genau die, gegen die diese Scheibe antritt -- geprueft
    wurde, wo der Code STEHT, nicht wo er WIRKT.

    Was hier verhaltensbasiert bleibt: solange die geladene Konfiguration
    keine eigene ``premium_sms``-Ebene traegt, gibt es keinen zweiten
    Auswahlweg, der von der SMS-Auswahl abweichen koennte. Die inhaltliche
    Gleichheit des Textes selbst (Premium-SMS versendet ``report.sms_text``,
    ADR-0049/Spec D5) ist am Wirkort durch
    ``test_kaskade_f002_sms_global_fallback_is_not_restricted_by_email_layout``
    gedeckt -- der prueft den tatsaechlich gerenderten SMS-Text, nicht seine
    Herkunft im Quelltext.

    Bekannte Grenze: entsteht spaeter eine eigene ``premium_sms``-Kaskadenebene
    (offene Frage der Spec), schlaegt dieser Test an und erzwingt einen echten
    eigenen Renderpfad-Test.
    """
    dc = _load_cascade_dc()
    assert "premium_sms" not in (dc.per_channel_layouts or {}), (
        "AC-11: es existiert bereits eine eigene Kaskaden-Ebene fuer premium_sms -- "
        "AC-11 (kein eigener Render-Test) ist damit ueberholt"
    )


# --- F002 (Adversary Runde 1, HIGH): AC-11s implizite Transitivitaets-
# Zusicherung ("gilt strukturell auch fuer Premium-SMS") ist fuer den
# GLOBALEN SMS-Fallback real durch den Renderpfad geprueft, nicht nur per
# String-Match (AC-11 selbst ist korrekt als doc-compliance-test markiert,
# bleibt unveraendert). trip_report.py:295 MUSS die SMS-Kaskade auf
# ``_dc_uncollapsed`` (dem Original-Config VOR der E-Mail-Kollabierung,
# Kommentar Z. 129-131) berechnen -- nicht auf dem bereits email-
# kollabierten ``dc``. Sonst erbt SMS im globalen Fallback faelschlich die
# Email-Kanal-Restriktion. Konstellation (eine Kanal-Ebene MIT eigenem
# Layout, eine ANDERE OHNE -> Fallback auf global) ist das seit #429 im
# Bestand dokumentierte Referenzmuster (test_issue_429_channel_layouts.py::
# _per_channel_trip_data: "Signal + SMS bewusst NICHT eingetragen ->
# Fallback auf globale Liste") -- die Basis-Fixture dieser Scheibe deckt es
# NICHT ab (channel_layouts traegt ausschliesslich "sms").
# ---------------------------------------------------------------------------


def _cascade_email_only_layout_dc() -> UnifiedWeatherDisplayConfig:
    """Variante der Basis-Fixture MIT eigener 'email'-Kanal-Ebene (nur die
    erste _AC12_PAIR-Metrik), aber bewusst OHNE eigene 'sms'-Ebene --
    cascade_source_for_channel('sms', ...) faellt strukturell auf 'global'
    zurueck."""
    dc = _load_cascade_dc()
    email_only_id, _ = _AC12_PAIR
    email_entry = next(mc for mc in dc.metrics if mc.metric_id == email_only_id)
    assert email_entry.enabled is True, "Vorbedingung: Ziel ist global aktiv"
    return dataclasses.replace(dc, per_channel_layouts={"email": [email_entry]})


def test_kaskade_f002_sms_global_fallback_is_not_restricted_by_email_layout():
    email_only_id, global_only_id = _AC12_PAIR  # "humidity" (eigene Email-Ebene), "gust" (nur global)
    email_only_symbol = SMS_SYMBOL_BY_METRIC[email_only_id]
    global_only_symbol = SMS_SYMBOL_BY_METRIC[global_only_id]

    dc = _cascade_email_only_layout_dc()
    assert dc.cascade_source_for_channel("email", "evening") == "per_channel"
    assert dc.cascade_source_for_channel("sms", "evening") == "global", (
        "Vorbedingung: SMS-Kanal-Ebene fehlt bewusst -- muss auf 'global' fallen"
    )

    sms = _kaskade_sms_text(dc)
    assert _first_index_starting_with(sms, email_only_symbol) is not None, (
        f"F002: {email_only_id!r} ({email_only_symbol!r}) fehlt im globalen SMS-Fallback: {sms!r}"
    )
    assert _first_index_starting_with(sms, global_only_symbol) is not None, (
        f"F002: {global_only_id!r} ({global_only_symbol!r}) fehlt im globalen SMS-Fallback -- SMS "
        "erbt faelschlich die Email-Kanal-Restriktion (trip_report.py:295 muss _dc_uncollapsed "
        f"statt dc verwenden): {sms!r}"
    )


# --- AC-12: Reihenfolge wird mitgeprueft, nicht nur die Menge ---


def test_kaskade_ac12_sms_order_is_applied_not_positional():
    first_id, second_id = _AC12_PAIR
    first_symbol = SMS_SYMBOL_BY_METRIC[first_id]
    second_symbol = SMS_SYMBOL_BY_METRIC[second_id]

    base_dc = _load_cascade_dc()
    sms_layout = {mc.metric_id: mc for mc in base_dc.per_channel_layouts["sms"]}
    assert sms_layout[first_id].enabled and sms_layout[second_id].enabled

    # F001-Fix: order-Werte werden als Roh-JSON-Patch gesetzt und erneut
    # durch _parse_display_config() geladen (_cascade_sms_variant) -- damit
    # deckt diese Variante auch loader.py's order=mc_data.get("order", 0)
    # ab, nicht nur models.py::_sorted_by_layout().
    dc_ab = _cascade_sms_variant({
        first_id: {"order": 0},
        second_id: {"order": 1},
    })
    dc_ba = _cascade_sms_variant({
        first_id: {"order": 1},
        second_id: {"order": 0},
    })

    sms_ab = _kaskade_sms_text(dc_ab)
    sms_ba = _kaskade_sms_text(dc_ba)
    ia_first = _first_index_starting_with(sms_ab, first_symbol)
    ia_second = _first_index_starting_with(sms_ab, second_symbol)
    ib_first = _first_index_starting_with(sms_ba, first_symbol)
    ib_second = _first_index_starting_with(sms_ba, second_symbol)
    assert ia_first is not None and ia_second is not None and ia_first < ia_second, (
        f"AC-12: Reihenfolge A ({first_id} vor {second_id}) nicht umgesetzt: {sms_ab!r}"
    )
    assert ib_first is not None and ib_second is not None and ib_second < ib_first, (
        f"AC-12: Reihenfolge B ({second_id} vor {first_id}) nicht umgesetzt: {sms_ba!r}"
    )


# ---------------------------------------------------------------------------
# Issue #1719 Scheibe 2: Metrik-Kaskade -- Verfeinerungsfilter (ADR-0050
# Regeln 1-3/5 im Produktivcode). SPEC:
# docs/specs/modules/fix_1719_s2_kaskade_verfeinerung.md (12 ACs).
#
# AC-1 ist der bereits bestehende test_kaskade_ac7_... oben -- die
# xfail(strict)-Markierung aus der S1-RED-Phase ist mit dieser Scheibe
# ENTFERNT (der Test lief zuvor per `pytest --runxfail` als RED-Beleg,
# s. Spec AC-1 "Wichtiger Konstruktionshinweis"; jetzt regulaer GRUEN).
# Die restlichen elf ACs bekommen die eigene Namensform
# `test_kaskade_s2_ac<n>_...`, damit sie NICHT mit den S1-Funktionsnamen
# (test_kaskade_ac2_..., test_kaskade_ac4_..., ...) kollidieren -- S1 und S2
# zaehlen ihre ACs unabhaengig voneinander, S2 AC-2 ist NICHT S1 AC-2.
#
# Gemessener RED/GRUEN-Start je AC (diese Session, 2026-08-11): S2-AC-2/3/11/12
# starten GRUEN (Regressionsschutz/Charakterisierung, kein Mangel). S2-AC-4/5/
# 9/10 starten ROT (echte, gemessene Bugs). S2-AC-7/8 starten -- ENTGEGEN der
# urspruenglichen Erwartung -- ebenfalls GRUEN: der heutige Code schneidet
# ueberhaupt nicht (weder gegen global noch gegen per_channel), die beiden
# Kanten werden erst durch die kommende Implementierung ueberhaupt beruehrbar.
# Details dazu im Bericht an den Product Owner.
# ---------------------------------------------------------------------------


def _global_entry(raw: dict, metric_id: str) -> dict:
    return next(e for e in raw["metrics"] if e["metric_id"] == metric_id)


def _cascade_channel_variant(channel_layouts: dict) -> UnifiedWeatherDisplayConfig:
    """Roh-JSON-Variante der Basis-Fixture mit VOLLSTAENDIG ersetztem
    channel_layouts (statt einzelner Feld-Patches wie _cascade_sms_variant) --
    fuer die email-/telegram-Kanal-Ebenen dieser Scheibe, die die Basis-
    Fixture nicht traegt. Erneut durch den ECHTEN Loader (S1 AC-2)."""
    raw = _load_cascade_fixture_raw()
    raw["channel_layouts"] = channel_layouts
    return _parse_display_config(raw)


_S2_LABEL_TOKEN_RE_CACHE: dict[str, "re.Pattern[str]"] = {}


def _label_token_present(text: str, label: str) -> bool:
    """Sucht `label` als abgegrenzten Token (Leerraum-/Zeilengrenzen) in
    `text` -- robust gegen Zeilenumbrueche durch die Telegram-Bubble-Breite
    (_TG_TABLE_WIDTH=32, narrow.py), die einzelne Woerter/Kuerzel nie mitten
    zerschneidet (narrow.py::_wrap)."""
    pattern = _S2_LABEL_TOKEN_RE_CACHE.setdefault(
        label, re.compile(rf"(?<!\S){re.escape(label)}(?!\S)"),
    )
    return pattern.search(text) is not None


def _kaskade_telegram_table_text(report) -> str:
    """Der <pre>-Textblock der (ersten) Telegram-Segment-Tabellenbubble --
    echter End-zu-End-Pfad (report.telegram_bubbles), NICHT render_for_channel()
    direkt (Konstruktionshinweis AC-4/AC-5 der Spec: der direkte Aufruf geht
    nie durch format_email()s Kollabierungsschritt und kann K2 strukturell
    nicht sehen)."""
    for bubble in report.telegram_bubbles:
        if "<pre>" in bubble:
            return bubble.split("<pre>", 1)[1].split("</pre>", 1)[0]
    raise AssertionError(f"keine Telegram-Tabellenbubble gefunden: {report.telegram_bubbles!r}")


# --- S2 AC-2: Kanal-Grenze bleibt dicht -- SMS-Abwahl aendert email/telegram nicht ---


def test_kaskade_s2_ac2_sms_deselect_cannot_affect_email_or_telegram_source():
    """S2 AC-2 (Regressions-Bestaetigung + global-Zweig-Beleg): die S1-Faelle
    AC-4/AC-6 oben bleiben nach dem Umbau unveraendert gruen (nicht dupliziert
    -- diese Funktion ergaenzt nur die fehlende Zusicherung, dass E-Mail und
    Telegram strukturell auf der GLOBALEN Ebene antworten; der Schnitt aus D1
    greift ausschliesslich in den per_report-/per_channel-Zweigen)."""
    dc = _load_cascade_dc()
    assert dc.cascade_source_for_channel("email", "evening") == "global"
    assert dc.cascade_source_for_channel("telegram", "evening") == "global"


# --- S2 AC-3: Telegram MIT eigener Ebene = Telegram ∩ Grundauswahl ---


def test_kaskade_s2_ac3_telegram_own_layer_intersects_base_selection():
    """S2 AC-3: geprueft ueber render_for_channel() direkt (wie
    _kaskade_telegram_cells) -- bewusst UNABHAENGIG von format_email()s
    Kollabierungsschritt (D5), weil eine EIGENE Telegram-Ebene die
    Ersetzungssemantik des heutigen Codes bereits korrekt behandelt (der
    per_channel-Zweig liest self.metrics gar nicht)."""
    target = _AC4_5_TARGET  # "freezing_level", global AN in der Basis-Fixture
    raw = _load_cascade_fixture_raw()
    telegram_layout = [
        {**e, "enabled": False} if e["metric_id"] == target else e
        for e in raw["metrics"]
    ]
    dc = _cascade_channel_variant({"telegram": telegram_layout})
    assert dc.cascade_source_for_channel("telegram", "evening") == "per_channel"

    cells = _kaskade_telegram_cells(dc)
    assert target not in cells, (
        f"S2 AC-3: {target!r} bleibt trotz eigener Telegram-Abwahl sichtbar: {cells}"
    )
    assert "wind_chill" in cells, (
        f"S2 AC-3: eine andere global aktive Metrik faellt faelschlich mit weg: {cells}"
    )


# --- S2 AC-4/AC-5: Telegram OHNE eigene Ebene -- K2 (Spalte + echter Wert) ---


def test_kaskade_s2_ac4_telegram_without_own_layer_follows_base_not_email():
    """S2 AC-4 (K2): der ECHTE Renderpfad -- report.telegram_bubbles, NICHT
    render_for_channel() direkt (s. Konstruktionshinweis der Spec: der
    direkte Aufruf geht nie durch die E-Mail-Kollabierung und kann K2
    strukturell nicht sehen).

    ZWEI Zielmetriken (Team-Lead-Befund/Freigabe, Nachbesserung 2026-08-11):
    Telegram-Tabellen haben nur 7 Metrik-Slots (Platzbudget, s.
    ``_AC4_TABLE_BUDGET_TARGET``-Kommentar oben) -- eine Metrik jenseits
    dieses Budgets verschwindet aus dem <pre>-Tabellentext, UNABHAENGIG
    davon, ob die Kaskade sie korrekt durchlaesst. Ein einzelner
    Tabellen-Check koennte deshalb aus dem falschen Grund rot werden (Budget
    statt Kaskade) oder aus dem falschen Grund gruen bleiben, wenn die
    Zielmetrik zufaellig im Budget liegt. Deshalb zwei Assertions:
    ``_AC4_TABLE_BUDGET_TARGET`` (im Budget) beweist K2 direkt im
    Tabellentext; ``_AC4_5_TARGET`` (ausserhalb des Budgets) beweist, dass
    der Schnitt sie trotzdem in der Kanal-AUSWAHL belaesst (table_columns +
    detail_metrics) -- verschwindet sie DORT auch, liegt es an der Kaskade,
    nicht am Platzbudget.
    """
    table_target = _AC4_TABLE_BUDGET_TARGET
    capacity_target = _AC4_5_TARGET
    raw = _load_cascade_fixture_raw()
    email_layout = [
        {**e, "enabled": False} if e["metric_id"] in (table_target, capacity_target) else e
        for e in raw["metrics"]
    ]
    dc = _cascade_channel_variant({"email": email_layout})
    assert dc.cascade_source_for_channel("email", "evening") == "per_channel"
    assert dc.cascade_source_for_channel("telegram", "evening") == "global", (
        "Vorbedingung: Telegram hat keine eigene Ebene -- muss auf 'global' fallen"
    )

    report = _kaskade_report(dc)
    table_text = _kaskade_telegram_table_text(report)
    assert _label_token_present(table_text, get_metric(table_target).compact_label), (
        f"S2 AC-4 (K2): {table_target!r} fehlt in der Telegram-Tabelle trotz globaler Aktivierung "
        f"-- Telegram folgt faelschlich der E-Mail-Kollabierung statt der Grundauswahl: {table_text!r}"
    )

    cells = _kaskade_telegram_cells(dc)
    assert capacity_target in cells, (
        f"S2 AC-4: {capacity_target!r} muss trotz Telegram-Tabellen-Platzbudget Teil der "
        f"Kanal-AUSWAHL bleiben (table_columns+detail_metrics) -- fehlt sie auch DORT, liegt es "
        f"an der Kaskade (E-Mail-Kollabierung), nicht am Platzbudget: {cells}"
    )


def test_kaskade_s2_ac5_telegram_own_layer_shows_real_value_not_dash():
    """S2 AC-5 (D5, zweite Haelfte -- eigene Telegram-Zeilenmenge): 'humidity'
    ist in F.segment() KONSTANT 55 (humidity_pct, s. _min_temp_felt_fixtures)
    -- die Telegram-Zelle muss diesen echten Wert zeigen, nicht '-'.

    Adversary F001-Nachbesserung (Pflicht-Mutationsprobe (a) der Spec, "Schnitt
    aus D1 weglassen" muss AC-1 UND AC-5 rot machen): 'humidity' allein ist
    global AN und bleibt deshalb auch OHNE den D1-Schnitt sichtbar -- ein Fix,
    der nur D5 (Wert) umsetzt, aber D1 (Schnitt) weglaesst, blieb bislang
    unbemerkt. Zweite Zielmetrik 'cloud_mid' (Muster AC-1/_AC7_TARGET: global
    AUS, eigene Telegram-Ebene AN) prueft D1 unabhaengig vom Wert-Nachweis."""
    target = "humidity"
    d1_target = "cloud_mid"
    raw = _load_cascade_fixture_raw()
    global_entry = _global_entry(raw, target)
    assert global_entry.get("enabled", True) is True, "Vorbedingung: Ziel global aktiv"
    d1_global_entry = _global_entry(raw, d1_target)
    assert d1_global_entry.get("enabled", True) is False, (
        "Vorbedingung: D1-Zielmetrik muss global INAKTIV sein (Muster AC-1)"
    )

    dc = _cascade_channel_variant({
        "telegram": [
            {**global_entry, "enabled": True},
            {**d1_global_entry, "enabled": True},
        ],
        "email": [{**global_entry, "enabled": False}],
    })
    assert dc.cascade_source_for_channel("telegram", "evening") == "per_channel"
    assert dc.cascade_source_for_channel("email", "evening") == "per_channel"

    report = _kaskade_report(dc)
    table_text = _kaskade_telegram_table_text(report)
    assert _label_token_present(table_text, get_metric(target).compact_label), (
        f"S2 AC-5: Spalte {get_metric(target).compact_label!r} fehlt in der Telegram-Tabelle: {table_text!r}"
    )
    assert _label_token_present(table_text, "55"), (
        f"S2 AC-5: Zelle zeigt nicht den echten Messwert 55 (humidity_pct, F.segment() konstant) "
        f"-- vermutlich '-' statt Wert (D5 fehlt): {table_text!r}"
    )

    cells = _kaskade_telegram_cells(dc)
    assert d1_target not in cells, (
        f"S2 AC-5 (F001): {d1_target!r} erscheint trotz globaler Abwahl in der Telegram-Kanal-Auswahl "
        f"-- die eigene Telegram-Ebene darf die globale Grundauswahl nur einschraenken, nie erweitern "
        f"(D1-Schnitt fehlt): {cells}"
    )


# --- S2 AC-5-Nachbesserung (F003): Force-Enable-Schritt der D5-Konstruktion ---


def test_kaskade_s2_ac5b_evening_override_forces_real_telegram_value():
    """Adversary F003: 'temperature' ist global INAKTIV (enabled:false), aber
    evening_enabled=true hebt sie fuer den Abend-Report an (D2, kein eigenes
    Telegram-Layout -- Kaskade faellt auf 'global'). trip_report.py erzwingt
    beim Bau von _dc_telegram enabled=True auf jeder Metrik aus dem D2-Schnitt
    (dataclasses.replace(mc, enabled=True)) -- OHNE diesen Schritt bliebe das
    urspruengliche enabled=False stehen, und _dp_to_row() traegt nur Metriken
    ein, die in der uebergebenen dc enabled sind: die Telegram-Zelle zeigte
    '-' statt des echten Messwerts, obwohl die Spalte (ueber evening_enabled)
    korrekt erscheint."""
    target = "temperature"
    raw = _load_cascade_fixture_raw()
    raw["metrics"] = [
        {**e, "enabled": False, "evening_enabled": True} if e["metric_id"] == target else e
        for e in raw["metrics"]
    ]
    dc = _parse_display_config(raw)
    assert dc.cascade_source_for_channel("telegram", "evening") == "global", (
        "Vorbedingung: keine eigene Telegram-Ebene -- Kaskade faellt auf 'global'"
    )

    report = _kaskade_report(dc)
    table_text = _kaskade_telegram_table_text(report)
    assert _label_token_present(table_text, get_metric(target).compact_label), (
        f"F003: Spalte {get_metric(target).compact_label!r} fehlt trotz evening_enabled=True: "
        f"{table_text!r}"
    )
    assert _label_token_present(table_text, "15.0"), (
        f"F003: Zelle zeigt nicht den echten Messwert 15.0 (t2m_c, F.segment() Basisstunde) -- "
        f"vermutlich '-' statt Wert (Force-Enable-Schritt in trip_report.py fehlt): {table_text!r}"
    )


# --- S2 AC-6: E-Mail-Stundentabelle bleibt bei horizon=None exakt bei der eigenen Auswahl ---


def test_kaskade_s2_ac6_email_stays_within_own_selection_at_horizon_none_stage():
    """S2 AC-6 (Waechter gegen den verworfenen Ansatz 'seg_tables global
    verbreitern'): die Telegram-Ebene ist echte Obermenge der E-Mail-Ebene
    (zusaetzlich 'humidity'); geprueft an einer Etappe mit horizon=None
    (Tag 4+, delta>=3 zum Report-Datum, email/html.py:924-947) -- dort
    filtert _allowed_col_keys_for_horizon() NICHT, visible_cols() liest die
    Spalten direkt aus den Zeilen-Schluesseln (email/helpers.py:296-299).
    Eine distinkte segment_id ("SEG 4") isoliert die Kopfzeile GENAU dieser
    Etappe -- sonst faende re.search blind das erste <thead> im HTML."""
    dc = _cascade_channel_variant({
        "email": [{"metric_id": "wind_chill", "enabled": True}],
        "telegram": [
            {"metric_id": "wind_chill", "enabled": True},
            {"metric_id": "humidity", "enabled": True},
        ],
    })
    assert dc.cascade_source_for_channel("email", "evening") == "per_channel"
    assert dc.cascade_source_for_channel("telegram", "evening") == "per_channel"

    seg_today = F.segment(day=F.DAY)
    seg_horizon_none = F.segment(day=F.DAY + 3)
    seg_horizon_none = dataclasses.replace(
        seg_horizon_none,
        segment=dataclasses.replace(seg_horizon_none.segment, segment_id=4),
    )
    report = TripReportFormatter().format_email(
        [seg_today, seg_horizon_none], trip_name="Kaskade1719S2AC6", report_type="evening",
        night_weather=None, display_config=dc, stage_name=F.STAGE_NAME, tz=F.TZ,
    )
    html = report.email_html
    start = html.index("SEG 4")
    rest = html[start:]
    nxt = re.search(r"SEG \d", rest[1:])
    block = rest[: nxt.start() + 1] if nxt else rest
    head = re.search(r"<thead><tr>(.*?)</tr></thead>", block, re.S)
    assert head, "S2 AC-6: keine Kopfzeile fuer die horizon=None-Etappe (SEG 4) gefunden"
    headers = [
        re.sub(r"<[^>]+>", "", th).strip()
        for th in re.findall(r"<th[^>]*>.*?</th>", head.group(1), re.S)
    ]
    metric_cols = [h for h in headers if h not in {"Time", "Risk"}]
    assert metric_cols == [get_metric("wind_chill").col_label], (
        f"S2 AC-6: Kopfzeile der horizon=None-Etappe enthaelt mehr als die E-Mail-Auswahl "
        f"(Telegram-exklusive Metrik 'humidity' darf hier NICHT auftauchen): {headers}"
    )


# --- S2 AC-7 (D4): leere/fehlende Grundauswahl schneidet nicht ---


def test_kaskade_s2_ac7_empty_base_selection_does_not_cut_sms_channel():
    """S2 AC-7 (D4): eine SMS-Kanal-Ebene MIT MEHREREN AKTIVEN Eintraegen
    (bewusst kein Mix aus aktiv/inaktiv wie in der Basis-Fixture -- eine
    Vergleichs-Laenge gegen deren VOLLE, gemischte per_channel_layouts-Liste
    waere strukturell IMMER falsch, weil inaktive Eintraege ohnehin nie
    zurueckkommen, unabhaengig vom Schnitt) bleibt bei LEERER globaler Liste
    vollstaendig erhalten -- kein Totalausfall."""
    raw = {
        "trip_id": "x1719s2ac7",
        "metrics": [],
        "channel_layouts": {"sms": [
            {"metric_id": "uv_index", "enabled": True},
            {"metric_id": "cloud_low", "enabled": True},
            {"metric_id": "visibility", "enabled": True},
        ]},
    }
    dc = _parse_display_config(raw)
    assert dc.cascade_source_for_channel("sms", "evening") == "per_channel"

    result = dc.get_metrics_for_channel("sms", "evening")
    assert len(result) == len(dc.per_channel_layouts["sms"]), (
        f"S2 AC-7: leere Grundauswahl schneidet die SMS-Kanal-Ebene auf {len(result)} von "
        f"{len(dc.per_channel_layouts['sms'])} Eintraegen -- D4 fehlt: "
        f"{[mc.metric_id for mc in result]}"
    )


# --- S2 AC-8 (D3): per_report_layouts wird gegen GLOBAL geschnitten, nicht gegen per_channel ---


def test_kaskade_s2_ac8_per_report_layer_cuts_against_global_not_per_channel():
    """S2 AC-8 (D3): 'uv_index' ist global aktiv, aber im ALLGEMEINEN
    per_channel_layouts.sms NICHT enthalten -- der per_report-Override fuer
    'evening' fuehrt sie trotzdem. Eine Verkettung mit per_channel (statt des
    in D3 vorgeschriebenen Schnitts gegen die globale Menge) wuerde sie
    faelschlich ausschliessen."""
    raw = _load_cascade_fixture_raw()
    global_entry = _global_entry(raw, "uv_index")
    assert global_entry.get("enabled", True) is True, "Vorbedingung: Ziel global aktiv"
    raw["channel_layouts"]["sms"] = [
        e for e in raw["channel_layouts"]["sms"] if e["metric_id"] != "uv_index"
    ]
    raw["channel_layouts_per_report"] = {
        "evening": {"sms": [{"metric_id": "uv_index", "enabled": True}]},
    }
    dc = _parse_display_config(raw)
    assert dc.cascade_source_for_channel("sms", "evening") == "per_report"

    result_ids = [mc.metric_id for mc in dc.get_metrics_for_channel("sms", "evening")]
    assert "uv_index" in result_ids, (
        f"S2 AC-8: 'uv_index' faellt aus dem per_report-Ergebnis, obwohl es global aktiv ist "
        f"(Schnitt darf nur gegen die globale Menge pruefen, nicht gegen per_channel): {result_ids}"
    )


# --- S2 AC-9 (D2): Report-Typ-Flags wirken im Schnitt ---


def test_kaskade_s2_ac9_evening_disabled_globally_excludes_from_evening_sms():
    """S2 AC-9 (D2): der globale Eintrag fuehrt evening_enabled=False, der
    SMS-Kanal-Eintrag ist unveraendert enabled=true OHNE eigenen
    evening_enabled-Override -- ein Schnitt gegen rohe enabled-Flags (statt
    gegen get_metrics_for_report_type()) liesse die Metrik faelschlich
    durch."""
    target = "cloud_low"  # aktiv im SMS-Kanal-Layout der Basis-Fixture, kollisionssicheres Symbol 'CL'
    symbol = SMS_SYMBOL_BY_METRIC[target]
    raw = _load_cascade_fixture_raw()
    global_entry = _global_entry(raw, target)
    assert global_entry.get("enabled", True) is True, "Vorbedingung: Ziel ist heute global aktiv"
    raw["metrics"] = [
        {**e, "evening_enabled": False} if e["metric_id"] == target else e
        for e in raw["metrics"]
    ]
    dc = _parse_display_config(raw)

    sms = _kaskade_sms_text(dc)
    assert _first_index_starting_with(sms, symbol) is None, (
        f"S2 AC-9: {target!r} ({symbol!r}) erscheint im Abend-SMS-Text trotz globalem "
        f"evening_enabled=False -- der Schnitt muss gegen get_metrics_for_report_type"
        f"('evening') pruefen, nicht gegen rohes enabled: {sms!r}"
    )


# --- S2 AC-10 Test A: Editor-Sequenz -- SMS-Snapshot, dann NUR Grundauswahl abwaehlen ---


def _cascade_editor_sequence_variant(target: str) -> UnifiedWeatherDisplayConfig:
    """K1-Reproduktionsfolge (Kontext-Dokument): SMS-Tab oeffnen -> Kanal-
    Ebene wird zur exakten Kopie der Grundauswahl (WeatherMetricsTab.svelte:638,
    startChannelOverride) -> zurueck zur Grundauswahl -> NUR der globale
    Eintrag wird geaendert, die SMS-Kopie bleibt unberuehrt."""
    raw = _load_cascade_fixture_raw()
    raw["channel_layouts"] = {"sms": [dict(e) for e in raw["metrics"]]}
    raw["metrics"] = [
        {**e, "enabled": False} if e["metric_id"] == target else e
        for e in raw["metrics"]
    ]
    return _parse_display_config(raw)


def test_kaskade_s2_ac10_editor_sequence_global_deselect_after_channel_snapshot():
    target = _AC4_5_TARGET  # global AN in der Basis-Fixture, wird hier NACH dem Snapshot AUS gesetzt
    symbol = SMS_SYMBOL_BY_METRIC[target]
    dc = _cascade_editor_sequence_variant(target)

    sms_copy_entry = next(mc for mc in dc.per_channel_layouts["sms"] if mc.metric_id == target)
    assert sms_copy_entry.enabled is True, "Vorbedingung: die SMS-Kopie blieb unveraendert aktiv"
    global_entry = next(mc for mc in dc.metrics if mc.metric_id == target)
    assert global_entry.enabled is False, "Vorbedingung: NUR die Grundauswahl wurde abgewaehlt"

    sms = _kaskade_sms_text(dc)
    assert _first_index_starting_with(sms, symbol) is None, (
        f"S2 AC-10 Test A: {target!r} ({symbol!r}) verschwindet nicht aus dem SMS-Kanal, obwohl "
        f"die real erreichbare Editor-Sequenz (Kanal-Snapshot -> Grundauswahl-Abwahl) das "
        f"verlangt: {sms!r}"
    )


# --- S2 AC-11: Premium-SMS am ECHTEN Versandweg gemessen, nicht als Struktur-Behauptung ---


def test_kaskade_s2_ac11_premium_sms_forwards_the_cut_sms_text(
    premium_sms_stub,  # noqa: F811 - pytest loest die Fixture per Name auf
):
    """S2 AC-11 (D7 -- Premium-SMS hat keine eigene Kaskaden-Ebene): am
    echten lokalen HTTP-Empfaenger gemessen (Muster premium_sms_stub aus
    test_channel_origin_guard_parity.py), nicht per String-Vergleich im
    Quelltext. Bewusst dieselbe Vorbedingung wie S1 AC-1/S2 AC-1 (dewpoint
    global AUS, SMS-Kanal AN): solange der Kern-Fix aussteht, muss
    Premium-SMS denselben Fehler REPRODUZIEREN (transitiv geerbt), nicht
    zufaellig verdecken."""
    target = _AC7_TARGET
    symbol = SMS_SYMBOL_BY_METRIC[target]
    on_dc = _cascade_sms_variant({target: {"enabled": True}})
    report = _kaskade_report(on_dc)

    settings = _prod_style_premium_sms_settings(
        premium_sms_stub.port, seven_sandbox_key="sandbox-key",
    )
    PremiumSmsOutput(settings).send("Betreff", report.sms_text)

    assert len(premium_sms_stub.received) == 1, (
        f"Erwartet genau EINEN POST, bekommen: {premium_sms_stub.received!r}"
    )
    sent_text = premium_sms_stub.received[0]["payload"]["text"]
    assert sent_text == report.sms_text, (
        f"S2 AC-11: Premium-SMS-Text weicht vom SMS-Text ab: {sent_text!r} != {report.sms_text!r}"
    )
    assert _first_index_starting_with(sent_text, symbol) is None, (
        f"S2 AC-11: {target!r} ({symbol!r}) erscheint im Premium-SMS-Text trotz globaler Abwahl "
        f"-- Premium-SMS erbt die (noch ungefixte) SMS-Kaskade transitiv: {sent_text!r}"
    )


# --- S2 AC-12: abgeleitete Nachtgroesse (temperature_night) faellt nicht aus dem Schnitt ---


def test_kaskade_s2_ac12_derived_night_metric_survives_the_cut():
    """S2 AC-12 (D2, ID-basiert): 'temperature_night' wird hier ERZWUNGEN
    ABGELEITET (kein expliziter Eintrag in raw['metrics'], loader.py:810-819
    haengt sie an self.metrics), die SMS-Kanal-Ebene fuehrt sie zusaetzlich
    explizit mit enabled:true -- die ID muss trotzdem im Schnitt-Ergebnis
    bleiben, weil sie bereits Teil des abgeleiteten globalen Maximums ist."""
    raw = _load_cascade_fixture_raw()
    raw["metrics"] = [
        {**e, "enabled": True} if e["metric_id"] == "temperature" else e
        for e in raw["metrics"]
        if e["metric_id"] != "temperature_night"
    ]
    raw["channel_layouts"]["sms"] = [
        e for e in raw["channel_layouts"]["sms"] if e["metric_id"] != "temperature_night"
    ] + [{"metric_id": "temperature_night", "enabled": True}]
    dc = _parse_display_config(raw)

    global_tn = next(mc for mc in dc.metrics if mc.metric_id == "temperature_night")
    assert global_tn.derived is True, "Vorbedingung: die Nachtgroesse muss ABGELEITET sein"
    assert global_tn.enabled is True, "Vorbedingung: Ableitung erbt den AN-Zustand von 'temperature'"

    result_ids = [mc.metric_id for mc in dc.get_metrics_for_channel("sms", "evening")]
    assert "temperature_night" in result_ids, (
        f"S2 AC-12: die abgeleitete Nachtgroesse faellt aus dem Schnitt heraus: {result_ids}"
    )


# --- S2 AC-13 (Adversary F004-Regression): Telegram-Kurzuebersicht respektiert evening_enabled ---


def test_kaskade_s2_ac13_telegram_overview_respects_evening_enabled_without_own_layer():
    """S2 AC-13 (F004): 'visibility' ist global AN, evening_enabled=False,
    OHNE eigene Telegram-Ebene (Kaskade faellt auf 'global'). Der D1-D4-Schnitt
    (get_metrics_for_channel) schliesst sie fuer report_type='evening' korrekt
    aus -- render_telegram_bubbles() bekam bis zu diesem Fix jedoch
    dc=_dc_uncollapsed (die UNGEFILTERTE Grundauswahl) statt dc=_dc_telegram.
    narrow.py:735/741/776 lesen dc.get_enabled_metric_ids() DIREKT, ohne durch
    get_metrics_for_channel() zu gehen -- die Telegram-Kurzuebersicht zeigte
    die Metrik deshalb trotzdem (als '-'-Geisterzeile, weil seg_tables_telegram
    bereits korrekt gefiltert war). Muss ueber den ECHTEN Pfad format_email()
    -> report.telegram_bubbles laufen (Konstruktionshinweis der Spec, nicht
    render_for_channel() direkt -- der geht nie durch die Kollabierung)."""
    target = "visibility"
    raw = _load_cascade_fixture_raw()
    global_entry = _global_entry(raw, target)
    assert global_entry.get("enabled", True) is True, "Vorbedingung: Ziel global aktiv"
    raw["metrics"] = [
        {**e, "evening_enabled": False} if e["metric_id"] == target else e
        for e in raw["metrics"]
    ]
    dc = _parse_display_config(raw)
    assert dc.cascade_source_for_channel("telegram", "evening") == "global", (
        "Vorbedingung: keine eigene Telegram-Ebene -- Kaskade faellt auf 'global'"
    )

    report = _kaskade_report(dc, "evening")
    overview = F.overview_bubble(report)
    assert overview, f"Keine Kurzuebersicht-Bubble gefunden: {report.telegram_bubbles!r}"
    assert F.overview_line(report, get_metric(target).compact_label) == "", (
        f"S2 AC-13: {target!r} erscheint in der Telegram-Kurzuebersicht trotz "
        f"evening_enabled=False (ohne eigene Kanal-Ebene) -- render_telegram_bubbles() muss die "
        f"report-typ-/kanal-kaskadierte dc lesen, nicht die ungefilterte Grundauswahl: {overview!r}"
    )


# ---------------------------------------------------------------------------
# Epic #1703 Scheibe 1 (AC-S1-1 bis AC-S1-7): Alarm-Renderer x alle
# alarmfaehigen Metriken (docs/reference/metric_output_matrix.md Flaeche 1).
# SPEC: docs/specs/modules/fix_1703_s1_alert_renderer_matrix.md.
#
# Eigene AC-Nummerierung (AC-S1-n), damit sie weder mit AC-13/14/15 (#1677 B)
# noch mit AC-1..AC-8 (Scheibe 3) kollidiert.
#
# EINZIGER roter Anteil: AC-S1-5 im gebuendelten Fall. _unit_display()
# (render.py:75-86) haengt fuer 'thunder' hart ein '%' an, obwohl der
# Alarmwert eine STUFE ist (alert_metrics={'max': 'thunder_level'},
# metric_catalog.py:340) -- PO-Entscheidung #1585 (genau zwei
# Gewitter-Metriken: 'thunder' = Staerke, 'thunder_probability' =
# Wahrscheinlichkeit) loest die aeltere Design-Vorlage aus #978 ab.
#
# ZWEI Assertion-Familien statt einer (Kontext-Dokument, Tabelle "Welcher
# Renderer welchen Helfer nutzt"): Betreff/E-Mail/Telegram beziehen die
# Beschriftung ueber _label() -> get_alert_label(); render_sms kennt weder
# Beschriftung noch Einheit, nur _code() -> get_sms_code(). Geprueft wird
# ausschliesslich an den vier ECHTEN Renderern (Pruefort = Wirkort) -- nie an
# _val()/_unit_display() isoliert, denn das pruefte den Helfer statt die
# Verdrahtung (s. Korrektur-Abschnitt der Scheibe-3-Spec).
# ---------------------------------------------------------------------------


def _alarm_soll_ids() -> set[str]:
    """Die alarmfaehigen Katalog-Kennungen -- GERECHNET aus dem Produktivmodul
    (``_ALERT_METRIC_TO_CATALOG_ID``, weather_change_detection.py:82-99), nie
    im Test aufgezaehlt (AC-S1-3). Wer ueber diese Menge iteriert, braucht
    keine Ausnahmeliste: humidity/rain_probability (is_precursor) und
    uv_index/snow_depth (kein Mapping-Eintrag) fallen strukturell heraus."""
    return {cid for ids in _ALERT_METRIC_TO_CATALOG_ID.values() for cid in ids}


_ALARM_SOLL_IDS = sorted(_alarm_soll_ids())

# Vakuum-Schutz-Untergrenze (Muster tests/helpers/hourly_columns.py:130-158):
# ein Waechter, der ueber eine leere oder stark geschrumpfte Menge iteriert,
# ist immer gruen und bewacht nichts. Gemessen 2026-08-11: 11 Kennungen.
_ALARM_SOLL_MINDESTGROESSE = 8

# Gewitter-Kennung aus dem Produktivmodul gelesen statt getippt.
_GEWITTER_ID = _ALERT_METRIC_TO_CATALOG_ID[AlertMetric.THUNDER_LEVEL][0]

_UNIT_PROBE_VALUE = 12.0
_EINHEITEN_UNTER_BEOBACHTUNG = sorted({m.unit for m in _METRICS} | set(_HANDLED_UNITS))

# Alarm-SMS-Tokengrammatik (render.py:596-601 ``_sms_token``,
# render.py:136-137 ``_sms_corridor_token``): {Vorzeichen}{Kuerzel}{Wert}[@HH],
# optional mit vorangestellter Ortsposition "{n}:". Eine reine Teilstring-Suche
# waere hier unbrauchbar -- 'N' (temperature_cold) ist Wortanfang von 'NL'
# (freezing_level) und 'NS' (fresh_snow), s. AC-S1-2-Gegenprobe.
_ALERT_SMS_TOKEN = re.compile(r"^(?:\d+:)?[+\-!]([A-Za-z][A-Za-z/]*)-?\d+(?:@\d+)?$")


def _alert_sms_codes(sms: str) -> list[str]:
    """Die Kuerzel einer Alarm-Kurznachricht in Token-Reihenfolge -- Token fuer
    Token zerlegt, nie per Teilstring gesucht."""
    body = sms.split(": ", 1)[1] if ": " in sms else sms
    codes = []
    for token in body.split(" "):
        hit = _ALERT_SMS_TOKEN.match(token)
        if hit:
            codes.append(hit.group(1))
    return codes


def _alarm_kontroll_id(metric_id: str) -> str:
    """Fremd-Groesse fuer die Verwechslungs-Gegenprobe: ihre Beschriftung darf
    in der Ausgabe NICHT vorkommen. 'Wind'/'Boeen' sind mit keiner anderen
    Alarm-Beschriftung teilstring-verwandt; dass beide zur Soll-Menge gehoeren,
    prueft AC-S1-3."""
    return "wind" if metric_id != "wind" else "gust"


def _alert_event(
    metric_id: str, *, value_from: float = 10.0, value_to: float = 20.0,
    threshold: float = 5.0,
) -> AlertEvent:
    """Ein Abweichungs-Ereignis. ``cmp`` kommt aus dem Katalog (get_cmp), damit
    der Test die Richtung nicht erfindet."""
    return AlertEvent(
        metric_id=metric_id, value_from=value_from, value_to=value_to,
        threshold=threshold, cmp=get_cmp(metric_id), occurred_at="09:00",
        km_from=0.0, km_to=5.0,
    )


def _alert_message(*events: AlertEvent) -> AlertMessage:
    return AlertMessage(trip_short="T1703S1", stand_at="08:00", events=tuple(events))


def _label_kanaele(msg: AlertMessage) -> dict[str, str]:
    """Die drei Ausgaben, die die Beschriftung fuehren -- ECHTE Renderer.
    Der sichtbare HTML-Text entsteht durch Entfernen der Tags: Auszeichnung wie
    ``width="100%"`` ist keine Ausgabe (relevant fuer AC-S1-5)."""
    html, plain = render_email(msg)
    return {
        "Betreff": render_subject(msg),
        "E-Mail (Klartext)": plain,
        "E-Mail (HTML-Text)": re.sub(r"<[^>]+>", "", html),
        "Telegram": render_telegram(msg),
    }


# --- AC-S1-1: Beschriftung in Betreff/E-Mail/Telegram ---------------------


@pytest.mark.parametrize("metric_id", _ALARM_SOLL_IDS)
def test_ac_s1_1_alarm_beschriftung_in_betreff_mail_telegram(metric_id):
    """AC-S1-1: ein Alarm zu genau einer alarmfaehigen Groesse nennt sie in
    Betreff, E-Mail UND Telegram mit der Katalog-Beschriftung -- gelesen aus
    get_alert_label(), nie im Test getippt. Die Gegenprobe (Beschriftung einer
    fremden Groesse darf NICHT erscheinen) macht die Zusicherung
    mutationsempfindlich; fuer das gleichnamige Paar temperature/
    temperature_cold gilt sie nur eingeschraenkt -- das haelt AC-S1-7 fest."""
    label = get_alert_label(metric_id)
    kontroll_label = get_alert_label(_alarm_kontroll_id(metric_id))
    ausgaben = _label_kanaele(_alert_message(_alert_event(metric_id)))

    for kanal, text in ausgaben.items():
        assert label in text, (
            f"AC-S1-1: {kanal} nennt die Groesse {metric_id!r} nicht mit ihrer "
            f"Katalog-Beschriftung {label!r}: {text!r}"
        )
        assert kontroll_label not in text, (
            f"AC-S1-1 (Gegenprobe): {kanal} traegt die Beschriftung "
            f"{kontroll_label!r} einer gar nicht alarmierten Groesse: {text!r}"
        )


# --- AC-S1-2: SMS-Kuerzel als abgegrenzter Token --------------------------


@pytest.mark.parametrize("metric_id", _ALARM_SOLL_IDS)
def test_ac_s1_2_sms_kuerzel_als_eigenstaendiger_token(metric_id):
    """AC-S1-2: die Kurznachricht traegt das Kuerzel der Groesse als
    eigenstaendigen Token. Geprueft wird mit Token-Grammatik statt
    Teilstring-Suche, und es darf KEIN fremdes Kuerzel mitgelesen werden."""
    code = get_sms_code(metric_id)
    assert code, (
        f"Vorbedingung: {metric_id!r} hat kein sms_code -- _code() fiele auf "
        "die metric_id zurueck (render.py:89-90), der Test pruefte dann etwas "
        "anderes als das Kuerzel"
    )
    sms = render_sms(_alert_message(_alert_event(metric_id)))
    codes = _alert_sms_codes(sms)

    assert code in codes, (
        f"AC-S1-2: Kurznachricht fuehrt fuer {metric_id!r} keinen Token mit "
        f"dem Kuerzel {code!r}: {sms!r} (erkannte Kuerzel: {codes})"
    )
    fremde = {get_sms_code(other) for other in _ALARM_SOLL_IDS if other != metric_id}
    mitgelesen = sorted(fremde & set(codes) - {code})
    assert not mitgelesen, (
        f"AC-S1-2: Kurznachricht zu {metric_id!r} fuehrt zusaetzlich fremde "
        f"Kuerzel {mitgelesen}: {sms!r}"
    )


def _sms_praefix_kollisionen() -> list[tuple[str, str]]:
    """Paare (kurz, lang) aus der Soll-Menge, bei denen ein Kuerzel echter
    Wortanfang eines anderen ist -- gerechnet, nicht getippt. Gemessen
    2026-08-11: N/NL (temperature_cold vs. freezing_level) und N/NS
    (temperature_cold vs. fresh_snow)."""
    return [
        (kurz_id, lang_id)
        for kurz_id in _ALARM_SOLL_IDS
        for lang_id in _ALARM_SOLL_IDS
        if get_sms_code(kurz_id)
        and get_sms_code(lang_id)
        and get_sms_code(kurz_id) != get_sms_code(lang_id)
        and get_sms_code(lang_id).startswith(get_sms_code(kurz_id))
    ]


_SMS_PRAEFIX_KOLLISIONEN = _sms_praefix_kollisionen()


@pytest.mark.parametrize("kurz_id,lang_id", _SMS_PRAEFIX_KOLLISIONEN)
def test_ac_s1_2_sms_praefix_gegenprobe(kurz_id, lang_id):
    """AC-S1-2 (Pflicht-Gegenprobe): ein Alarm, der NUR die Groesse mit dem
    laengeren Kuerzel traegt, darf fuer das kuerzere KEINEN Treffer liefern.
    Genau hier schluege eine Teilstring-Suche falsch an -- ersetzt man die
    Token-Grammatik in ``_alert_sms_codes()`` durch ``code in sms``, muss
    dieser Test rot werden."""
    kurz, lang = get_sms_code(kurz_id), get_sms_code(lang_id)
    sms = render_sms(_alert_message(_alert_event(lang_id)))
    codes = _alert_sms_codes(sms)

    assert lang in codes, (
        f"Vorbedingung: {lang_id!r} muss sein eigenes Kuerzel {lang!r} tragen "
        f"(sonst prueft die Gegenprobe ins Leere): {sms!r}"
    )
    assert kurz not in codes, (
        f"AC-S1-2 (Gegenprobe): das Kuerzel {kurz!r} ({kurz_id!r}) wird in "
        f"einer Kurznachricht mitgelesen, die nur {lang_id!r} ({lang!r}) "
        f"enthaelt: {sms!r}"
    )


# --- AC-S1-3: Soll-Menge stammt aus dem Produktivmodul (Vakuum-Schutz) ----


def test_ac_s1_3_soll_menge_wird_gerechnet_und_ist_plausibel():
    """AC-S1-3: die geprueften Groessen stammen ausschliesslich aus
    ``_ALERT_METRIC_TO_CATALOG_ID``. Der Plausibilitaets-Waechter schlaegt an,
    wenn die Menge leer ist, unter die Mindestgroesse faellt oder von der
    parametrisierten Konstante abweicht -- die Konstante ist der Mutations-Ort
    (sie speist alle parametrize-Achsen), die Neuberechnung hier ist der
    unabhaengige Pruefort."""
    frisch = {cid for ids in _ALERT_METRIC_TO_CATALOG_ID.values() for cid in ids}

    assert frisch, (
        "Vakuum: das Produktivmodul fuehrt keine einzige alarmfaehige "
        "Katalog-Kennung -- jede Achse dieser Scheibe liefe ueber null Faelle"
    )
    assert len(frisch) >= _ALARM_SOLL_MINDESTGROESSE, (
        f"Vakuum-Schutz: nur {len(frisch)} alarmfaehige Kennungen "
        f"({sorted(frisch)}) -- erwartet mindestens "
        f"{_ALARM_SOLL_MINDESTGROESSE}. Entweder ist das Mapping geschrumpft "
        "oder die Soll-Rechnung greift daneben."
    )
    assert set(_ALARM_SOLL_IDS) == frisch, (
        f"Die parametrisierte Soll-Menge {sorted(_ALARM_SOLL_IDS)} weicht vom "
        f"Produktivmodul {sorted(frisch)} ab -- eine im Test aufgezaehlte oder "
        "gekuerzte Liste ist genau das, was AC-S1-3 verbietet"
    )

    katalog_ids = {m.id for m in _METRICS}
    assert frisch <= katalog_ids, (
        f"Kennungen ohne Katalog-Eintrag: {sorted(frisch - katalog_ids)}"
    )
    # Unabhaengige Gegenrichtung: der Katalog kennt die Alarmfaehigkeit selbst
    # (alert_metrics, ohne die is_precursor-Vorboten). Faellt eine solche
    # Groesse aus dem Mapping, schrumpfen sonst BEIDE Seiten gemeinsam und
    # keine Assertion oben wuerde anschlagen. Grenze, bewusst: die drei
    # Groessen, die nur ueber die Rueckwaerts-Abbildung erreichbar sind
    # (snowfall_limit/temperature_cold via OR-Tupel, wind via WIND_CHANGE),
    # deklarieren im Katalog kein alert_metrics und sind so nicht abgedeckt.
    katalog_alarmfaehig = {
        m.id for m in _METRICS if m.alert_metrics and not m.is_precursor
    }
    assert katalog_alarmfaehig <= frisch, (
        f"Der Katalog fuehrt {sorted(katalog_alarmfaehig - frisch)} als "
        "alarmfaehig (alert_metrics gesetzt, kein Vorbote), das Produktivmodul "
        "_ALERT_METRIC_TO_CATALOG_ID kennt die Kennung(en) aber nicht -- "
        "entweder ist das Mapping geschrumpft oder der Katalog ist gewachsen, "
        "ohne dass die Alarm-Renderer-Achse davon erfaehrt"
    )
    ohne_kuerzel = sorted(cid for cid in frisch if not get_sms_code(cid))
    assert not ohne_kuerzel, (
        f"Alarmfaehige Groessen ohne sms_code: {ohne_kuerzel} -- _code() faellt "
        "dort auf die metric_id zurueck, AC-S1-2 pruefte dann das Falsche"
    )
    ohne_beschriftung = sorted(cid for cid in frisch if get_alert_label(cid) == cid)
    assert not ohne_beschriftung, (
        f"Alarmfaehige Groessen ohne Katalog-Beschriftung: {ohne_beschriftung} "
        "-- get_alert_label() gibt dort die Kennung selbst zurueck"
    )

    kontroll_ids = {_alarm_kontroll_id(cid) for cid in _ALARM_SOLL_IDS}
    assert kontroll_ids <= frisch, (
        f"Kontroll-Groessen ausserhalb der Soll-Menge: "
        f"{sorted(kontroll_ids - frisch)} -- die Gegenprobe in AC-S1-1 haette "
        "keine Grundlage"
    )
    assert _SMS_PRAEFIX_KOLLISIONEN, (
        "Keine Praefix-Kollision mehr unter den Kuerzeln -- dann laeuft die "
        "AC-S1-2-Gegenprobe ueber null Faelle und bewacht nichts"
    )
    assert _GEWITTER_ID in frisch, (
        f"Die Gewitter-Kennung {_GEWITTER_ID!r} steht nicht in der Soll-Menge "
        "-- AC-S1-5/AC-S1-6 haetten keinen Gegenstand"
    )
    assert _HANDLED_UNITS and len(_EINHEITEN_UNTER_BEOBACHTUNG) >= 8, (
        f"Vakuum-Schutz AC-S1-4: {len(_EINHEITEN_UNTER_BEOBACHTUNG)} Einheiten "
        f"unter Beobachtung, _HANDLED_UNITS={_HANDLED_UNITS}"
    )


# --- AC-S1-4: _HANDLED_UNITS deckt sich mit der Katalog-Formatierung ------


def _katalog_haengt_einheit_an(unit: str) -> bool:
    """Gemessen statt behauptet: haengt ``format_metric_value()`` diese Einheit
    tatsaechlich an den Wert an? Der else-Zweig (metric_catalog.py:1025-1026)
    liefert ``str(value)`` ganz ohne Einheit."""
    if not unit:
        return False
    return format_metric_value(unit, _UNIT_PROBE_VALUE).endswith(" " + unit)


@pytest.mark.parametrize(
    "unit", _EINHEITEN_UNTER_BEOBACHTUNG, ids=lambda u: u or "ohne-einheit",
)
def test_ac_s1_4_handled_units_deckt_sich_mit_der_katalog_formatierung(unit):
    """AC-S1-4: ``_HANDLED_UNITS`` (render.py:35) ist eine wortgleiche Kopie
    der Einheiten, die ``format_metric_value()`` mit Suffix formatiert. Diese
    Doppelung driftet lautlos: waechst die eine Liste ohne die andere, faellt
    der Alarm-Renderer still in den Ersatzpfad (render.py:51-52) und verliert
    dort die deutsche Zahlformatierung. Geprueft wird in BEIDE Richtungen --
    Katalog-Einheiten und Listen-Einheiten stehen gemeinsam in der Achse."""
    haengt_an = _katalog_haengt_einheit_an(unit)
    gelistet = unit in _HANDLED_UNITS
    assert haengt_an == gelistet, (
        f"AC-S1-4: Einheit {unit!r} -- Katalog haengt sie "
        f"{'an' if haengt_an else 'NICHT an'} "
        f"(format_metric_value({unit!r}, {_UNIT_PROBE_VALUE}) = "
        f"{format_metric_value(unit, _UNIT_PROBE_VALUE)!r}), _HANDLED_UNITS "
        f"fuehrt sie {'' if gelistet else 'NICHT '}-- die beiden Listen sind "
        "auseinandergelaufen"
    )


# --- AC-S1-5: Gewitter ohne Prozentzeichen (DER rote Anteil) --------------


def _gewitter_event() -> AlertEvent:
    """value_from=0.0 -> ``delta_pct()`` ist definitionsgemaess None
    (model.py:92-96), die Ausgabe traegt also KEINE Aenderungs-Prozentzahl.
    Jedes verbleibende '%' ist damit zwangslaeufig eine EINHEIT -- genau das
    misst AC-S1-5. Werte 0->2 bilden die Gewitter-STUFE ab (0-3)."""
    return _alert_event(_GEWITTER_ID, value_from=0.0, value_to=2.0, threshold=1.0)


def _alle_vier_ausgaben(msg: AlertMessage) -> dict[str, str]:
    ausgaben = _label_kanaele(msg)
    ausgaben["Kurznachricht"] = render_sms(msg)
    return ausgaben


def test_ac_s1_5_gewitter_allein_ohne_prozentzeichen():
    """AC-S1-5 (Einzel-Alarm): heute bereits gruen -- der Einzelpfad liest
    ``get_metric().unit`` direkt (render.py:47, :365) und umgeht damit den
    ``_unit_display()``-Sonderfall."""
    assert get_metric(_GEWITTER_ID).unit == "", (
        f"Vorbedingung: der Katalog fuehrt {_GEWITTER_ID!r} ohne Einheit "
        "(Stufe 0-3, metric_catalog.py:333) -- sonst waere ein Einheiten-"
        "Suffix keine Fehlanzeige"
    )
    msg = _alert_message(_gewitter_event())
    ausgaben = _alle_vier_ausgaben(msg)

    assert get_alert_label(_GEWITTER_ID) in ausgaben["Betreff"], (
        "Vorbedingung: der Betreff muss den Gewitter-Alarm ueberhaupt nennen"
    )
    assert get_sms_code(_GEWITTER_ID) in _alert_sms_codes(ausgaben["Kurznachricht"]), (
        "Vorbedingung: die Kurznachricht muss den Gewitter-Token tragen"
    )
    for kanal, text in ausgaben.items():
        assert "%" not in text, (
            f"AC-S1-5: {kanal} haengt an den Gewitter-Wert ein Prozentzeichen "
            f"an -- Gewitter ist eine STUFE (alert_metrics="
            "{'max': 'thunder_level'}), die Prozent-Achse waere "
            f"'thunder_probability' (PO-Entscheidung #1585): {text!r}"
        )


def test_ac_s1_5_gewitter_gebuendelt_ohne_prozentzeichen():
    """AC-S1-5 (Buendel-Alarm): DER rote Anteil dieser Scheibe. Der
    Mehr-Metrik-Pfad nutzt ``_unit_display()`` (render.py:75-86), das fuer
    'thunder' hart '%' liefert -- gemessen 2026-08-11: 'Gewitter 10->20%'."""
    partner_id = _alarm_kontroll_id(_GEWITTER_ID)
    assert get_metric(partner_id).unit != "%", (
        f"Vorbedingung: die Partner-Groesse {partner_id!r} darf selbst keine "
        "Prozent-Einheit tragen -- sonst waere nicht zuzuordnen, woher ein "
        "'%' stammt"
    )
    msg = _alert_message(
        _gewitter_event(),
        _alert_event(partner_id, value_from=0.0, value_to=30.0, threshold=10.0),
    )
    ausgaben = _alle_vier_ausgaben(msg)

    assert get_alert_label(_GEWITTER_ID) in ausgaben["Betreff"], (
        "Vorbedingung: der Betreff muss den Gewitter-Alarm ueberhaupt nennen"
    )
    for kanal, text in ausgaben.items():
        assert "%" not in text, (
            f"AC-S1-5: {kanal} haengt im gebuendelten Alarm an den "
            "Gewitter-Wert ein Prozentzeichen an -- Gewitter ist eine STUFE, "
            "keine Prozentzahl (PO-Entscheidung #1585; der Sonderfall in "
            f"_unit_display() stammt aus der aelteren #978-Vorlage): {text!r}"
        )


# --- AC-S1-6: der Fix schiesst nicht ueber sein Ziel hinaus ---------------


def _buendel_zeile(plain: str, label: str) -> str:
    zeilen = [z for z in plain.splitlines() if z.startswith(f"{label} · ")]
    assert len(zeilen) == 1, (
        f"Erwartet genau eine Datenzeile zur Beschriftung {label!r}, gefunden "
        f"{len(zeilen)}: {zeilen}"
    )
    return zeilen[0]


@pytest.mark.parametrize("metric_id", _ALARM_SOLL_IDS)
def test_ac_s1_6_uebrige_groessen_behalten_ihre_katalog_einheit(metric_id):
    """AC-S1-6: im gebuendelten Alarm traegt jede uebrige Groesse weiterhin
    genau ihre Katalog-Einheit -- der Gewitter-Fix darf sie nicht mitreissen.
    Fuer Gewitter selbst greift ein umgekehrter Zweig (kein pytest.skip,
    Muster ``_TELEGRAM_NIGHT_SCALAR_EXCEPTIONS`` weiter oben): dort gilt die
    Regel dieses Tests gerade NICHT, der Sollzustand steht in AC-S1-5."""
    if metric_id == _GEWITTER_ID:
        assert get_metric(metric_id).unit == "", (
            f"Umgekehrter Zweig: {metric_id!r} traegt im Katalog bewusst keine "
            "Einheit -- daraus folgt der Sollzustand aus AC-S1-5 (keine "
            "Prozent-Ausgabe). Traegt der Katalog hier ploetzlich eine "
            "Einheit, ist die Grundlage beider ACs weg."
        )
        return

    unit = get_metric(metric_id).unit
    ereignis = _alert_event(metric_id, value_from=0.0, value_to=20.0)
    _, plain = render_email(_alert_message(ereignis, _gewitter_event()))
    zeile = _buendel_zeile(plain, get_alert_label(metric_id))
    erwartetes_ende = f"{unit} {side_label(ereignis)}"

    assert zeile.endswith(erwartetes_ende), (
        f"AC-S1-6: die Datenzeile zu {metric_id!r} endet nicht auf ihre "
        f"Katalog-Einheit ({erwartetes_ende!r}): {zeile!r}"
    )


def test_ac_s1_6_prozentzeichen_bleibt_wo_die_einheit_es_verlangt():
    """AC-S1-6: Groessen, deren Katalog-Einheit tatsaechlich '%' ist (Feuchte
    und Regenwahrscheinlichkeit -- beide is_precursor und daher NICHT in der
    Soll-Menge, als AlertEvent aber sehr wohl renderbar), behalten ihr
    Prozentzeichen. Ein Fix, der ``_unit_display()`` pauschal entschaerft
    statt nur den thunder-Sonderfall zu entfernen, wird hier rot."""
    prozent_ids = [m.id for m in _METRICS if m.unit == "%" and m.alert_label]
    assert prozent_ids, (
        "Vakuum: der Katalog fuehrt keine Prozent-Groesse mit Alarm-"
        "Beschriftung -- dieser Test bewachte nichts"
    )
    partner_id = _alarm_kontroll_id(_GEWITTER_ID)

    for metric_id in prozent_ids:
        ereignis = _alert_event(metric_id, value_from=0.0, value_to=80.0, threshold=20.0)
        _, plain = render_email(_alert_message(
            ereignis,
            _alert_event(partner_id, value_from=0.0, value_to=30.0, threshold=10.0),
        ))
        zeile = _buendel_zeile(plain, get_alert_label(metric_id))
        assert zeile.endswith(f"% {side_label(ereignis)}"), (
            f"AC-S1-6: {metric_id!r} hat die Katalog-Einheit '%' verloren: "
            f"{zeile!r}"
        )


# --- AC-S1-7: gleiche Beschriftung -- Doppeldeutigkeit ausdruecklich ------


def _beschriftungs_kollisionen() -> dict[str, tuple[str, ...]]:
    """Gruppen von Soll-Groessen, die sich EINE Alarm-Beschriftung teilen --
    gerechnet, nicht getippt. Gemessen 2026-08-11: {'Temp': ('temperature',
    'temperature_cold')}."""
    nach_label: dict[str, list[str]] = {}
    for metric_id in _ALARM_SOLL_IDS:
        nach_label.setdefault(get_alert_label(metric_id), []).append(metric_id)
    return {lab: tuple(ids) for lab, ids in nach_label.items() if len(ids) > 1}


_BESCHRIFTUNGS_KOLLISIONEN = sorted(_beschriftungs_kollisionen().items())


def test_ac_s1_7_doppeldeutige_beschriftung_ist_benannt():
    """AC-S1-7: die Doppeldeutigkeit wird ausdruecklich festgehalten statt
    stillschweigend uebergangen. Wird sie eines Tages aufgeloest (eigene
    Beschriftung fuer temperature_cold), muss dieser Zweig bewusst entfernt
    werden -- er verschwindet nicht von selbst."""
    assert _BESCHRIFTUNGS_KOLLISIONEN, (
        "Keine gleichnamigen Alarm-Groessen mehr -- der umgekehrte Pruefzweig "
        "AC-S1-7 laeuft dann ueber null Faelle. Entweder ist die "
        "Doppeldeutigkeit behoben (dann diesen Zweig samt Begruendung "
        "entfernen) oder die Soll-Menge ist kaputt."
    )


@pytest.mark.parametrize("label,metric_ids", _BESCHRIFTUNGS_KOLLISIONEN)
def test_ac_s1_7_gleichnamige_groessen_trennt_nur_die_kurznachricht(label, metric_ids):
    """AC-S1-7 (umgekehrter Pruefzweig): fuer gleichnamige Groessen gilt die
    Zusicherung aus AC-S1-1 nur eingeschraenkt -- Betreff, E-Mail und Telegram
    sind byte-identisch und koennen sie NICHT unterscheiden. Allein das
    Kurznachrichten-Kuerzel trennt sie. Wer eine Mutation nur an diesen drei
    Kanaelen misst, hat nichts bewiesen (s. Pruefhinweis der Spec).

    Adversary-Finding F001, #1703 S1: dieser Test (wie auch
    test_ac_s1_7_doppeldeutige_beschriftung_ist_benannt oben) beweist nur,
    dass sich die Kuerzel fuer 'temperature' und 'temperature_cold'
    UNTERSCHEIDEN -- er kann NICHT beweisen, dass sie richtig herum
    zugeordnet sind (also 'D' zu temperature, 'N' zu temperature_cold),
    denn Pruefling (get_sms_code ueber _alert_sms_codes/render_sms) und
    Massstab (_ALARM_SOLL_IDS/get_alert_label, ebenfalls aus dem Katalog)
    lesen hier denselben Katalog. Eine Vertauschung der beiden sms_code-
    Werte direkt im Katalog wuerde Soll und Ist gemeinsam mitwandern lassen
    und bliebe hier gruen. Die Zuordnung selbst sichert stattdessen
    tests/tdd/test_issue_917_alert_renderer.py::TestAC6CatalogSmsCodes ab,
    die die Kuerzel 'D' und 'N' hart als Literal schreibt (Zeile 465ff).
    Wird jene Klasse geloescht, faellt diese Deckung ersatzlos weg und muss
    hier (oder an vergleichbarer Stelle) ersetzt werden."""
    ausgaben = [_label_kanaele(_alert_message(_alert_event(mid))) for mid in metric_ids]
    for mid, weitere in zip(metric_ids[1:], ausgaben[1:]):
        for kanal, text in ausgaben[0].items():
            assert weitere[kanal] == text, (
                f"AC-S1-7: {kanal} unterscheidet {metric_ids[0]!r} und {mid!r} "
                f"doch -- der Waechter geht davon aus, dass beide unter der "
                f"Beschriftung {label!r} ununterscheidbar sind. Wenn das jetzt "
                "nicht mehr stimmt, ist die Doppeldeutigkeit behoben und "
                f"dieser Zweig gehoert entfernt.\n{text!r}\n{weitere[kanal]!r}"
            )

    kuerzel = []
    for mid in metric_ids:
        codes = _alert_sms_codes(render_sms(_alert_message(_alert_event(mid))))
        assert len(codes) == 1, (
            f"Vorbedingung: genau ein Token erwartet fuer {mid!r}, erkannt: {codes}"
        )
        kuerzel.append(codes[0])
    assert len(set(kuerzel)) == len(kuerzel), (
        f"AC-S1-7: allein die Kurznachricht trennt die gleichnamigen Groessen "
        f"{list(metric_ids)} -- hier tut sie es nicht: {kuerzel}"
    )
