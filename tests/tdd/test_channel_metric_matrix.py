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
"""
from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

from app.loader import _parse_display_config
from app.metric_catalog import _METRICS, build_default_display_config, get_all_metrics, get_metric
from app.models import AlertMetric, MetricConfig, UnifiedWeatherDisplayConfig, _SELECTABLE_GATE_EXEMPT
from output.renderers.channel_layout import render_for_channel
from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG, get_compare_metric_catalog
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID, resolve_enabled_metrics
from output.renderers.email.helpers import resolve_metric_col_order
from output.renderers.sms_trip import SMS_SYMBOL_BY_METRIC, SMS_MULTI_SYMBOLS_BY_METRIC
from output.renderers.trip_report import TripReportFormatter
from services.weather_change_detection import is_alert_metric_active

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


# --- AC-7 (Pflicht-AC): Widerspruchsfall global AUS + Kanal AN -- MUSS heute ROT sein ---


@pytest.mark.xfail(
    strict=True,
    reason="ADR-0050 Regel 2 -- Kanal darf nicht hinzufuegen; Umbau in #1719 S2",
)
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


# doc-compliance-test
def test_kaskade_ac11_premium_sms_shares_sms_cascade_key():
    premium_sms_src = (_REPO_ROOT / "src" / "output" / "channels" / "premium_sms.py").read_text()
    assert "Der Nachrichtentext ist unveraendert" in premium_sms_src, (
        "AC-11: premium_sms.py dokumentiert nicht mehr, dass der Text unveraendert report.sms_text ist"
    )
    trip_report_src = (_REPO_ROOT / "src" / "output" / "renderers" / "trip_report.py").read_text()
    assert (
        '_sms_metrics_ordered = _dc_uncollapsed.get_metrics_for_channel("sms", report_type)'
        in trip_report_src
    ), "AC-11: trip_report.py liest die SMS-Kaskade nicht mehr unter dem Schluessel 'sms'"

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
