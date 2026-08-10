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
import re

import pytest

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
