"""Vollstaendigkeits-Matrix Metrik-Katalog x Kanal, damit die Fehlerklasse
"Bedienelement ohne Wirkung" (#1450, #1362, #1660 A/B, #1677) strukturell
bewacht ist statt fallweise entdeckt zu werden. Angelegt als TDD RED zu Issue
#1677 Scheibe B, seither um mehrere Achsen von Epic #1703 gewachsen -- welcher
Anteil ROT war, steht bei der jeweiligen Scheibe unten.

SPEC: docs/specs/modules/fix_1677_sms_reihenfolge.md AC-13/AC-14/AC-15.

Parametrisiert ueber ``app.metric_catalog.get_all_metrics()`` (25 waehlbare
Metriken, gemessen 2026-08-14). Pro Kanal wird gegen die Funktion getestet,
die der jeweilige Produktivpfad TATSAECHLICH aufruft (kein Duplikat-Rendering):
- E-Mail:        ``resolve_metric_col_order`` (email/html.py:1021 ``_col_order``)
- Telegram-rich: ``render_for_channel`` (narrow.py:644)
- SMS-Kurzform:  ``TripReportFormatter().format_email() -> report.sms_text``
  (derselbe Wirkort wie test_sms_user_metric_order.py)

AC-Zuordnung:
- AC-13 (E-Mail):        test_ac13_email_column_selection_and_order       -> GRUEN (Bestand, #1575)
- AC-14 (Telegram-rich):  test_ac14_telegram_rich_selection_and_order      -> GRUEN (Bestand, #429/#1575)
- AC-15 (SMS-Kurzform):   test_ac15_sms_kurzform_selection_deselection_and_order
    - (a)/(b) Auswahl/Abwahl -> GRUEN (Bestand, Bug-#944-Muster + #1415/#1660B)
    - (c) Nutzer-Reihenfolge -> GRUEN seit dem Fix zu #1677/#1660 B
      (``_POSITION_SORTABLE_CATEGORIES`` in output/tokens/builder.py,
      ``MetricSpec.position``); beim Schreiben dieser Datei war sie ROT
    - (d) ohne SMS-Layout   -> GRUEN (Charakterisierung, wie AC-2)

Alle drei Achsen laufen heute GRUEN: E-Mail/Telegram waren von Anfang an
Bestandsfunktion (hier nur strukturell abgesichert), die SMS-Kurzform-
Reihenfolge ist seit #1677 gefixt. Hier stand bis 2026-08-14, sie sei "der
einzige neue, heute rote Anteil dieser Datei" -- das galt zum Schreibzeitpunkt
und war seither ueberholt; der Satz liess den Zuschnitt von Epic #1703
Scheibe 7 zunaechst zu breit erscheinen.

Epic #1703 Scheibe 3 (AC-1 bis AC-8, unten): schliesst die
get_all_metrics()-vs-_METRICS-Blindstelle (docs/reference/metric_output_matrix.md
Flaeche 3) -- Vollstaendigkeitstests wie AC-13/14/15 oben iterieren ueber
get_all_metrics() und koennen selectable=False-Groessen (confidence, cape,
temperature_cold) daher strukturell nie sehen. SPEC:
docs/specs/modules/fix_1703_s3_selectable_metrics.md. Kein Produktivcode-Fix
-- Charakterisierungstest fuer bereits korrektes, bisher unbewachtes
Verhalten (alle 8 ACs laufen heute bereits GRUEN).

Epic #1703 Scheibe 1 (AC-S1-1 bis AC-S1-7, weiter unten): Alarm-Renderer x alle
alarmfaehigen Metriken (docs/reference/metric_output_matrix.md Flaeche 1) --
die vier Alarm-Renderer waren fuer 8 von 11 produktiv erreichbaren
Alarm-Groessen ungeprueft. SPEC:
docs/specs/modules/fix_1703_s1_alert_renderer_matrix.md. EINZIGER roter
Anteil dieser Achse: AC-S1-5 im gebuendelten Fall (Gewitter-Prozentzeichen).

Epic #1703 Scheibe 2 (AC-S2-1 bis AC-S2-7, ganz unten): Ausblick-Tabelle des
Ortsvergleichs x alle 25 waehlbaren Katalog-Paare
(docs/reference/metric_output_matrix.md Flaeche 2) -- bewacht war bisher nur
das Auswahl-PRINZIP mit zwei fest getippten Auswahlen
(test_compare_outlook_metric_selection.py), nicht die Katalog-DECKUNG. SPEC:
docs/specs/modules/fix_1703_s2_ausblick_matrix.md. Compare-only (die drei
Trip-Aufrufstellen des geteilten Ausblick-Renderers uebergeben kein
``metrics``-Argument, s. Spec "Korrektur der Scheiben-Praemisse"). ROTER
Anteil: AC-S2-4 (fuenf dauerhaft leere Spalten) und AC-S2-5 (die beiden
Tages-Aggregationspfade sind auseinandergelaufen).

Epic #1703 Scheibe 7 (AC-S7-1 bis AC-S7-9, weiter unten): die REIHENFOLGE
derselben 25 Uebersichts-Groessen ueber alle Ausgabeorte
(docs/reference/metric_output_matrix.md) -- bewacht war bisher, DASS eine
gewaehlte Groesse erscheint, nicht AN WELCHER STELLE. Die Soll-Menge wird aus
``get_compare_metric_catalog()`` GERECHNET, nie getippt (AC-S7-1, mit
Vakuum-Schutz AC-S7-1b). SPEC:
docs/specs/modules/fix_1703_s7_reihenfolge_matrix.md. Achsen: HTML- und
Klartext-Zwilling derselben Compare-Mail (AC-S7-2/3), Altbestand ohne
gespeicherte Auswahl (AC-S7-4, Charakterisierung der HTML/Klartext-Divergenz),
je Kanal eine EIGENE Reihenfolge in EINER Sendung -- am echten Versand- UND
Vorschaupfad (AC-S7-5/5b, Gegenprobe zum Label-Vergleich AC-S7-5c),
Trip-Kurzuebersicht und ihre zwei Reihenfolge-Quellen (AC-S7-7/7b),
Compare-Telegram/-SMS unter Kappung (AC-S7-8a/8b/8c), Kompakt-Fliesstext als
benannte Ausnahme ohne Reihenfolge-Achse (AC-S7-9). EINZIGER roter Anteil:
AC-S7-6 -- die Pillen der Kurz-E-Mail verwarfen die eingestellte Ordnung
(``build_metrics_summary_pills()`` kollabierte die geordnete Liste zu einer
Menge).
"""
from __future__ import annotations

import dataclasses
import importlib
import itertools
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app.loader import _parse_display_config
from app.metric_catalog import (
    _METRICS, build_default_display_config, format_metric_value, get_all_metrics,
    get_alert_label, get_cmp, get_metric, get_sms_code,
)
from app.models import (
    AlertMetric, ForecastDataPoint, ForecastMeta, MetricConfig, NormalizedTimeseries,
    PrecipType, Provider, ThunderLevel, UnifiedWeatherDisplayConfig,
    _SELECTABLE_GATE_EXEMPT,
)
from output.renderers.alert.model import AlertEvent, AlertMessage, side_label
from output.renderers.alert.render import (
    _HANDLED_UNITS, render_email, render_sms, render_subject, render_telegram,
)
from output.channels.premium_sms import PremiumSmsOutput
from output.renderers.channel_layout import (
    CHANNEL_LIMITS, VISIBILITY_GATE_IDS, render_for_channel,
)
from output.renderers.email.compare_html import CV2_METRICS, derive_row_labels
from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG, get_compare_metric_catalog
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID, resolve_enabled_metrics
from output.renderers.comparison import (
    _PLAIN_ROWS_BY_ID, render_compare_email, render_compare_sms, render_compare_telegram,
)
from output.renderers.email.helpers import _PILL_CATALOG_ORDER, resolve_metric_col_order
from output.renderers.email.html import _render_mobile_compact_rows
from output.renderers.sms_trip import SMS_SYMBOL_BY_METRIC, SMS_MULTI_SYMBOLS_BY_METRIC
from output.renderers.trip_metric_ids import DEFAULT_TRIP_METRIC_IDS
from output.renderers.trip_report import TripReportFormatter
from services.report_config_resolver import ReportRenderOptions
from services.weather_change_detection import _ALERT_METRIC_TO_CATALOG_ID, is_alert_metric_active
from services.weather_metrics import WeatherMetricsService, summarize_points

from tests.helpers.compare_order import (
    assert_compare_order_soll_ist_plausibel, compare_order_soll_metriken,
    html_uebersicht_labels, klartext_uebersicht_labels, partner_von,
    sms_index, sms_kuerzel, telegram_zellen, uebersichts_label,
)
from tests.helpers.outlook_columns import (
    assert_soll_menge_ist_plausibel, compare_outlook_soll_paare,
    compare_outlook_soll_spalten,
)
from tests.tdd import _min_temp_felt_fixtures as F
# Issue #1719 S2 AC-11: geteilter Premium-SMS-Stub (echter lokaler HTTP-
# Server, kein Mock) -- Vorbild-Fixture wiederverwendet statt kopiert (Muster
# bereits etabliert: pytest erkennt eine importierte @pytest.fixture-Funktion
# auch im importierenden Modul).
from tests.tdd.test_channel_origin_guard_parity import (
    _prod_style_premium_sms_settings, premium_sms_stub,  # noqa: F401 - pytest loest die Fixture per Name auf
)
# Issue #1703 S7 AC-S7-5: geteilter Daten-/Engine-Rahmen des Scheibe-8-
# Waechters -- echte ComparisonEngine-Subklasse, echte Renderer, kein Netz,
# kein Mock. Wiederverwendet statt kopiert (dasselbe Muster wie oben).
from tests.unit.test_compare_channel_metrics_reach_the_renderer import (
    LOCATION as _S7_LOCATION, TARGET_DATE as _S7_TARGET_DATE,
    env,  # noqa: F401 - pytest loest die Fixture per Name auf
)

_ALL_METRIC_IDS = [m.id for m in get_all_metrics()]

# #1484/#1660 A/#1728 S1: reine Sichtbarkeits-Gates sind bewusst NIE eine
# Telegram-rich-Tabellen-/Detailzelle (channel_layout.VISIBILITY_GATE_IDS) --
# strukturelle Ausnahme, kein Auswahl-Bug. Aus der Produktivmenge GELESEN
# statt hier zweitgepflegt: eine Erweiterung dort soll diese Ausnahme
# automatisch mitnehmen, sonst laufen zwei Listen auseinander.
_TELEGRAM_NIGHT_SCALAR_EXCEPTIONS = set(VISIBILITY_GATE_IDS)

# Teilmenge davon: die Groessen, die in der Telegram-KURZUEBERSICHT gar keine
# Zeile tragen. Die zwei Nachtfenster-Skalare sind hier ausgenommen -- sie
# bekommen abends sehr wohl eine eigene Zeile, wenn die Tages-Groesse nicht
# mitgewaehlt ist (narrow.py:745-760).
_TELEGRAM_NO_OVERVIEW_ROW = set(VISIBILITY_GATE_IDS) - {
    "temperature_night", "wind_chill_night",
}


def _partner_of(metric_id: str) -> str:
    """Sichere Partner-Metrik ohne Symbol-Praefix-Kollision (K ist bei
    keinem anderen Katalog-Kuerzel Praefix, s. Kollisionsanalyse im Kontext-
    Dokument der Spec)."""
    return "wind" if metric_id == "temperature" else "temperature"


# Issue #1728 Scheibe 1: ``temperature`` fuehrt in der Kurzform SELBST kein
# Kuerzel mehr -- 'K'/'D' haengen an ``temperature_day_low``/``_high``, die
# als eigene Parametrisierungen derselben Matrix geprueft werden. Eine
# Auswahl-/Reihenfolge-Assertion gegen ein Kuerzel, das die Groesse nicht
# fuehrt, waere strukturell unerfuellbar -- die Zusicherung ist nicht
# entfallen, sie ist umgezogen.
# Fix #1887 E6 Scheibe A (PO-Entscheid): 'WC' entfaellt ERSATZLOS
# (verdoppelte nachweislich 'FK') -- ``wind_chill`` fuehrt seither wie
# ``temperature`` kein eigenes Kurzform-Kuerzel mehr; 'FK'/'FD' haengen an
# ``wind_chill_day_low``/``_high``, die als eigene Parametrisierungen
# geprueft werden.
_SMS_WITHOUT_OWN_SYMBOL = {"temperature", "wind_chill"}

# Die zwei Groessen, deren Kuerzel bei gemeinsamer Auswahl zu EINEM
# Bereichs-Token verschmelzen (#1824: 'K3 D20' -> 'D3/20'). Sie duerfen
# einander in dieser Matrix nicht als Partner bekommen, sonst misst der Test
# die Verschmelzung statt der Reihenfolge.
_SMS_MERGING_SIBLINGS = {"temperature_day_low", "temperature_day_high"}


def _sms_partner_of(metric_id: str) -> str:
    """Partner fuer die KURZFORM-Matrix: er muss selbst ein Token tragen und
    darf mit dem Prueflings-Kuerzel nicht verschmelzen.

    Issue #1728 Scheibe 1: bis dahin war ``temperature`` der Partner (trug
    'K'/'D'); seit die Tages-Token an eigenen Groessen haengen, erzeugt
    ``temperature`` allein kein Token mehr. Der Pruefgegenstand
    (Nutzer-Reihenfolge schlaegt die feste Tabelle) ist unveraendert, nur der
    Bezugspartner traegt jetzt selbst ein Kuerzel. 'W' ist bei keinem anderen
    Kuerzel Praefix, 'D' nur bei sich selbst — die Kollisionsfreiheit der
    urspruenglichen Analyse bleibt gewahrt.
    """
    return "wind" if metric_id in _SMS_MERGING_SIBLINGS else "temperature_day_high"


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


# Issue #1824 (A): sind Tiefst- UND Hoechstwert gewaehlt, steht die Temperatur
# als EIN Bereichs-Token unter dem HOECHSTWERT-Kuerzel ('D3/20').
# Issue #1728 Scheibe 1: seit jede Groesse GENAU EIN Kuerzel traegt, kann die
# Verschmelzung in dieser Matrix nicht mehr auftreten — der Partner ist nie
# die verschmelzende Schwester (s. _sms_partner_of). Die Stellvertreter-
# Tabelle ist damit leer statt geraten; sie bleibt als benannte Stelle
# stehen, falls je wieder eine Groesse mehrere Wert-Kuerzel fuehrt.
_RANGE_REPRESENTATIVE: dict[str, str] = {}


def _representative_symbol(metric_id: str) -> str:
    if metric_id in _RANGE_REPRESENTATIVE:
        return _RANGE_REPRESENTATIVE[metric_id]
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
# Issue #1824 (A): zusaetzlich die Bereichsform ('D3/20', 'D-12/-4', 'D-/-',
# 'D?/?') -- zwei Haelften, durch '/' getrennt.
_RANGE_HALF = r"-?\d+|-|\?"
_GRAMMAR_SUFFIX = re.compile(
    rf"(?:(?:{_RANGE_HALF})/(?:{_RANGE_HALF})"
    r"|(?:\d+(?:\.\d+)?%?|[LMH])(?:@\d+(?:\((?:\d+(?:\.\d+)?%?|[LMH])@\d+\))?)?|-|\?)$"
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
    if metric_id in _SMS_WITHOUT_OWN_SYMBOL:
        assert metric_id not in SMS_MULTI_SYMBOLS_BY_METRIC, (
            f"{metric_id!r} fuehrt wieder ein eigenes Kurzform-Kuerzel — dann "
            f"gehoert es zurueck in diese Matrix statt in die Ausnahme."
        )
        return
    symbol = _representative_symbol(metric_id)
    partner_id = _sms_partner_of(metric_id)
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
# Abschnitt 5). Traegt die volle Katalogbreite (26 Eintraege in der globalen
# Ebene, 15 global aktiv inkl. wind_chill AN, 13 SMS-Kanal-aktiv, wind_chill
# AUS) -- genau der reale Widerspruch, der Trip KHW 5f534011 eine falsche
# SMS-Kurzform lieferte. Fix #1887 E6 Scheibe A: die SMS-Kanal-Ebene traegt
# seither 28 Eintraege (26 + zwei ergaenzte, disabled-per-Default:
# wind_chill_day_low/-high, s. AC-8-Zuwahl-Nachweis unten -- die
# urspruengliche Fixture kannte diese beiden erst seit #1728 Scheibe 1
# eigenstaendig waehlbaren Groessen noch nicht).
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
    # Fix #1887 E6 Scheibe A (PO-Entscheid): 'WC' entfaellt ERSATZLOS --
    # "wind_chill" fuehrt seither UEBERHAUPT keinen Eintrag mehr in
    # SMS_MULTI_SYMBOLS_BY_METRIC (nicht nur ein leeres Tupel). `.get(...,
    # ())` haelt die Schleife wirkungslos statt mit KeyError abzustuerzen --
    # sie hat nichts mehr zu pruefen, weil die Groesse kein Kuerzel mehr
    # traegt, das trotz Abwahl auftauchen koennte.
    for symbol in SMS_MULTI_SYMBOLS_BY_METRIC.get("wind_chill", ()):
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


# --- AC-8: alle Kuerzel einer Metrik toggeln gemeinsam (wind_chill FK/FD) ---

# Issue #1824 (A): das gefuehlte Bereichs-Token ('FD1/18') traegt den
# Tiefstwert in seiner ersten Haelfte.
_RANGE_TOKEN_FD = re.compile(rf"(?:^|\s)FD(?:{_RANGE_HALF})/(?:{_RANGE_HALF})(?:\s|$)")


def test_kaskade_ac8_all_wind_chill_symbols_toggle_together():
    """Issue #1728 Scheibe 1: 'FK'/'FD' haengen seit dieser Scheibe an eigenen
    Groessen. Fix #1887 E6 Scheibe A (PO-Entscheid, docs/specs/modules/
    fix_1887_e6a_sms_kuerzel_register.md): 'WC' (vormals an ``wind_chill``
    selbst) entfaellt ERSATZLOS -- ``wind_chill`` traegt danach ueberhaupt
    keinen Eintrag mehr in SMS_MULTI_SYMBOLS_BY_METRIC, deshalb bleibt nur
    noch dieser Traeger uebrig. Die Zusicherung dieses AC — die Zuwahl der
    gefuehlten Temperatur macht ALLE ihre Kuerzel sichtbar, die Abwahl
    entfernt sie alle — gilt unveraendert; sie umfasst zwei Groessen, und
    genau deshalb wird sie hier aus der Kuerzel-Tabelle GELESEN statt
    getippt."""
    traeger = ("wind_chill_day_low", "wind_chill_day_high")
    symbols = tuple(
        sym for mid in traeger for sym in SMS_MULTI_SYMBOLS_BY_METRIC[mid]
    )
    # Fix #1926: wind_chill_day_low SMS-Wire-Token FK->FL.
    assert set(symbols) == {"FL", "FD"}, (
        f"Die gefuehlten Tages-Kuerzel haben ihren Traeger gewechselt: "
        f"{symbols!r}"
    )
    assert "wind_chill" not in SMS_MULTI_SYMBOLS_BY_METRIC, (
        "'wind_chill' fuehrt weiterhin einen Eintrag in "
        "SMS_MULTI_SYMBOLS_BY_METRIC — 'WC' sollte ersatzlos entfallen "
        f"(PO-Entscheid): {SMS_MULTI_SYMBOLS_BY_METRIC.get('wind_chill')!r}"
    )

    sms_off = _kaskade_sms_text(_load_cascade_dc())
    for symbol in symbols:
        assert _first_index_starting_with(sms_off, symbol) is None, (
            f"AC-8: {symbol!r} erscheint trotz Abwahl: {sms_off!r}"
        )

    on_dc = _cascade_sms_variant({
        mid: {"enabled": True} for mid in traeger
    })
    sms_on = _kaskade_sms_text(on_dc)
    for symbol in symbols:
        # Issue #1824 (A): sind beide Auswertungen gewaehlt, steht der
        # gefuehlte Tiefstwert nicht mehr als eigenes 'FL'-Token (Fix #1926:
        # vormals 'FK'), sondern als ERSTE HAELFTE des Bereichs-Tokens
        # 'FD{min}/{max}'. Die Zusicherung dieses AC bleibt dieselbe -- die
        # Groesse muss mit ihrer Zuwahl sichtbar werden -- nur ihr Traeger
        # hat sich geaendert.
        if symbol == "FL" and _RANGE_TOKEN_FD.search(sms_on):
            continue
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

# Alarm-SMS-Tokengrammatik (render.py ``_sms_token`` / ``_sms_corridor_token``),
# vier Formen -- die Grammatik muss alle vier zerlegen, ohne zur Teilstring-
# Suche zu verwaessern ('N' (temperature_cold) ist Wortanfang von 'NS'
# (fresh_snow), s. AC-S1-2-Gegenprobe):
#
#   {n}:{+|-}{Kuerzel}{Bis}[@HH]      Ortsvergleich-Aenderung (#1467 S2 AG3b)
#   !{Kuerzel}{Wert}                  Schwellen-Treffer (#1444 S1)
#   {Kuerzel}{Von}->{Bis}[@HH]        Trip-Δ numerisch (#1935/#1779, #1948 S3)
#   {Kuerzel}:{Stufe}->{Stufe}[@HH]   Trip-Δ Stufenleiter (#1948 S3, LEVELS)
#
# Issue #1948 S3 hat die beiden Trip-Δ-Formen geaendert: das Vorzeichen-Praefix
# ist dort entfallen (es las sich als Rechenzeichen) und Stufen-Groessen tragen
# Doppelpunkt + Buchstaben statt Rohzahlen. Der Ortsvergleich-Aenderungspfad
# behaelt sein Vorzeichen -- eine vorangestellte Ortsposition ist deshalb NUR
# zusammen mit einem Vorzeichen zulaessig.
_ALERT_SMS_TOKEN = re.compile(
    r"^(?:(?:\d+:)?[+-]|!)?"
    r"([A-Za-z][A-Za-z/]*)"
    r"(?::[-LMH]->[-LMH]|-?\d+(?:->-?\d+)?)"
    r"(?:@\d+)?$"
)


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


# ---------------------------------------------------------------------------
# Epic #1703 Scheibe 2 (AC-S2-1 bis AC-S2-7): Ausblick-Tabelle des
# Ortsvergleichs x alle waehlbaren Katalog-Paare
# (docs/reference/metric_output_matrix.md Flaeche 2).
# SPEC: docs/specs/modules/fix_1703_s2_ausblick_matrix.md.
#
# Eigene AC-Nummerierung (AC-S2-n), damit sie weder mit AC-13/14/15 (#1677 B)
# noch mit AC-1..AC-8 (Scheibe 3) oder AC-S1-n (Scheibe 1) kollidiert.
#
# Compare-only: die drei Trip-Aufrufstellen des geteilten Ausblick-Renderers
# (email/html.py:1357, email/plain.py:338, trip_report_scheduler.py:1844)
# uebergeben KEIN ``metrics``-Argument und laufen im festen Legacy-Spaltenpfad
# -- der Trip-Ausblick hat keine waehlbaren Spalten und damit keine
# Metrik-x-Kanal-Flaeche (Spec "Korrektur der Scheiben-Praemisse"). Sein Schutz
# ist der Byte-Golden tests/tdd/test_trip_outlook_parity.py.
#
# Pruefort = Wirkort: alle Ist-Werte stammen aus ``render_compare_email()`` --
# EIN Aufruf liefert HTML UND Klartext, damit ist der Klartext-blinde Fleck des
# Pflicht-Mail-Validators mit abgedeckt (#1366). Nie an ``outlook_columns()``
# isoliert gemessen; der Massstab kommt aus dem Katalog (tests/helpers/
# outlook_columns.py), nicht aus derselben Funktion.
#
# ABHAENGIGKEIT, die nicht weggeraeumt werden darf (AC-S2-7): die einzelne
# Streichung einer Katalog-Zeile faengt diese Achse NICHT -- ihre Soll-Menge
# schrumpft dann einfach mit. Sie faengt der unabhaengige, GETIPPTE
# Groessenanker tests/tdd/test_compare_metric_catalog_endpoint.py::
# TestUnknownMetricIdFailsVisibly::test_real_catalog_resolves_completely
# (``len(get_compare_metric_catalog()) == 25``, Zeile 519). Wird jene Zeile bei
# einer kuenftigen Aufraeumaktion als "hartcodiert, unschoen" entfernt, faellt
# diese Deckung ersatzlos weg (Lehre aus Scheibe 1, Finding F001).
# ---------------------------------------------------------------------------

# Zwei Striche, die im Terminal gleich aussehen und NICHT gleichgesetzt werden
# duerfen (Spec "Die Fehlzeichen-Falle"):
_S2_FEHLZEICHEN = "–"      # – format_outlook_value(None, ...): Wert FEHLT
_S2_KEINE_ANGABE = "—"     # — Gewitterstufe "keine" / Niederschlagsart unbekannt

# Eindeutiger Marker der Ausblick-Tabelle (nur auf dieser einen Tabelle
# gesetzt, identisch zu test_compare_outlook_metric_selection.py:27).
_S2_TABELLEN_MARKER = "border-top:2px solid #1d1c1a"
_S2_KLARTEXT_UEBERSCHRIFT = "3-Tages-Ausblick"

_S2_SOLL = compare_outlook_soll_spalten()
_S2_SOLL_PAARE = compare_outlook_soll_paare()
_S2_SOLL_IDS = [f"{s['metric_id']}:{s['aggregation']}" for s in _S2_SOLL]

_S2_STARTTAG = date(2026, 7, 20)
_S2_TAGE = ((6.0, 18.0), (9.0, 27.0), (11.0, 23.0))

# Die fuenf Tagesfelder, deren Ausblick-Zelle vor dem Fix dauerhaft das
# Fehlzeichen trug (gemessen 2026-08-11 an der echten Vergleichs-Mail, HTML wie
# Klartext, an jedem der drei Tage) -- der ROTE Anteil von AC-S2-4. Die Liste
# bleibt nach dem Fix stehen: sie begrenzt die Charakterisierung in AC-S2-6 auf
# die 20 bereits gefuellten Zellen und bleibt der Beleg des roten Anteils.
_S2_DEFEKTE_FELDER = frozenset({
    "snow_depth_cm", "snow_new_sum_cm", "wind_direction_avg_deg",
    "wind_chill_min_c", "wind_chill_max_c",
})


def _s2_punkt(tag: date, stunde: int, temp: float, thunder) -> ForecastDataPoint:
    """Ein REICH besetzter Stundenpunkt: jedes Quellfeld, aus dem eine der 25
    Ausblick-Spalten ihren Tageswert zieht, traegt einen Wert. Nur so heisst
    eine Strichzelle "der Aggregationspfad fuellt das Feld nicht" statt
    "der Test hat nichts hineingelegt" (AC-S2-4)."""
    return ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, stunde, 0, tzinfo=timezone.utc),
        t2m_c=temp, wind10m_kmh=15.0, wind_direction_deg=210, gust_kmh=25.0,
        precip_1h_mm=1.1, precip_rate_mmph=1.1, cloud_total_pct=50,
        thunder_level=thunder, cape_jkg=400.0, pop_pct=55,
        pressure_msl_hpa=1013.0, humidity_pct=70, dewpoint_c=5.0, uv_index=4.0,
        snow_depth_cm=30.0, snow_new_24h_cm=4.0, snowfall_limit_m=2200,
        precip_type=PrecipType.RAIN, freezing_level_m=3000,
        wind_chill_c=temp - 2.0, visibility_m=20000,
        cloud_low_pct=30, cloud_mid_pct=40, cloud_high_pct=20,
        wmo_code=61, is_day=1, dni_wm2=300.0, confidence_pct=80, hail_flag=False,
    )


def _s2_punkte(thunder) -> list[ForecastDataPoint]:
    """Drei Kalendertage a vier Stundenpunkte (UTC 02/08/14/20 = Ortszeit
    04/10/16/22 in Europe/Vienna -- derselbe Kalendertag, kein Tagesuebergang)."""
    punkte: list[ForecastDataPoint] = []
    for versatz, (tief, hoch) in enumerate(_S2_TAGE):
        tag = _S2_STARTTAG + timedelta(days=versatz)
        for stunde, temp in zip((2, 8, 14, 20), (tief, (tief + hoch) / 2, hoch, (tief + hoch) / 2)):
            punkte.append(_s2_punkt(tag, stunde, temp, thunder))
    return punkte


@lru_cache(maxsize=None)
def _s2_mail(thunder_name: str = "MED") -> tuple[str, str]:
    """Die ECHTE Vergleichs-Mail mit ALLEN waehlbaren Ausblick-Groessen.
    Gecacht, weil jede parametrisierte Achse dieselbe Mail liest."""
    from app.user import ComparisonResult, LocationResult, SavedLocation

    punkte = _s2_punkte(ThunderLevel[thunder_name])
    heute = [p for p in punkte if p.ts.date() == _S2_STARTTAG]
    ort = LocationResult(
        location=SavedLocation(
            id="innsbruck", name="Innsbruck", lat=47.27, lon=11.40,
            elevation_m=574, timezone="Europe/Vienna",
        ),
        score=50, hourly_data=heute, outlook_hourly_data=punkte,
    )
    ergebnis = ComparisonResult(
        locations=[ort], time_window=(9, 16), target_date=_S2_STARTTAG,
        created_at=datetime(2026, 7, 20, 4, 1),
    )
    return render_compare_email(
        ergebnis, outlook_enabled=True, outlook_metrics=list(_S2_SOLL_PAARE),
    )


def _s2_html_ausblick(html: str) -> tuple[list[str], list[list[str]]]:
    """Kopfzeile + Tageszeilen der Ausblick-Tabelle der echten HTML-Mail."""
    soup = BeautifulSoup(html, "html.parser")
    tabellen = [t for t in soup.find_all("table")
                if _S2_TABELLEN_MARKER in str(t.get("style", ""))]
    assert len(tabellen) == 1, (
        f"Erwartet genau eine Ausblick-Tabelle (Marker {_S2_TABELLEN_MARKER!r}), "
        f"gefunden {len(tabellen)}"
    )
    kopf = [th.get_text(strip=True) for th in tabellen[0].find_all("th")]
    zeilen = [[td.get_text(strip=True) for td in tr.find_all("td")]
              for tr in tabellen[0].find("tbody").find_all("tr")]
    return kopf, zeilen


def _s2_klartext_ausblick(text: str) -> list[dict[str, str]]:
    """Je Tageszeile des Klartext-Ausblicks eine Zuordnung Ueberschrift -> Wert.

    Der Renderer schreibt ``f"{Wochentag:<3} " + "  ".join(f"{Label} {Wert}")``
    (email/outlook.py:344-350) -- die Paare trennen ZWEI Leerzeichen, Label und
    Wert eines. Beide enthalten selbst Leerzeichen ("Temperatur Maximum",
    "15 km/h"), deshalb wird je Token die LAENGSTE passende Soll-Ueberschrift
    abgespalten: "Wind" ist echter Wortanfang von "Windrichtung".
    """
    ueberschriften = sorted((s["ueberschrift"] for s in _S2_SOLL), key=len, reverse=True)
    zeilen = text.split("\n")
    start = next(
        (i for i, z in enumerate(zeilen) if z.strip() == _S2_KLARTEXT_UEBERSCHRIFT),
        None,
    )
    assert start is not None, (
        f"Im Klartext derselben Mail ist kein Ausblick-Block auffindbar "
        f"(gesucht: {_S2_KLARTEXT_UEBERSCHRIFT!r}).\n{text}"
    )
    ergebnis: list[dict[str, str]] = []
    for zeile in zeilen[start + 1:]:
        if not zeile.strip():
            break
        zellen: dict[str, str] = {}
        for token in zeile.split("  ")[1:]:
            token = token.strip()
            treffer = next((u for u in ueberschriften if token.startswith(u)), None)
            assert treffer is not None, (
                f"Klartext-Ausblick fuehrt den Abschnitt {token!r}, der zu "
                f"keiner Soll-Ueberschrift passt: {zeile!r}"
            )
            zellen[treffer] = token[len(treffer):].strip()
        ergebnis.append(zellen)
    return ergebnis


def _s2_zelle_ist_fehlwert(zellentext: str) -> bool:
    """NUR das Fehlzeichen U+2013 zaehlt als "Wert fehlt".

    Der Gedankenstrich U+2014 ist eine INHALTLICHE Aussage (Gewitterstufe
    "keine", unbekannte Niederschlagsart) und ausdruecklich KEIN Verstoss --
    s. test_ac_s2_4_keine_gewitterstufe_ist_kein_fehlwert. Wer beide gleichsetzt,
    macht aus einem gewitterfreien Tag faelschlich einen Fehler; wer den
    Unterschied ganz aufgibt, uebersieht den echten Fehlwert.
    """
    return zellentext.strip() == _S2_FEHLZEICHEN


# --- AC-S2-1: jede waehlbare Groesse ergibt genau eine Spalte -------------


@pytest.mark.parametrize("soll", _S2_SOLL, ids=_S2_SOLL_IDS)
def test_ac_s2_1_jede_waehlbare_groesse_ergibt_genau_eine_spalte(soll):
    """AC-S2-1: waehlt der Nutzer alle im Vergleich waehlbaren Ausblick-Groessen,
    traegt der Ausblick fuer JEDE genau eine Spalte -- in der HTML-Tabelle UND
    im Klartext derselben Mail. Die erwartete Ueberschrift kommt aus dem
    Katalog (label + aggregation_label), nicht aus ``outlook_columns()``."""
    html, text = _s2_mail()
    kopf, _ = _s2_html_ausblick(html)
    erwartet = soll["ueberschrift"]

    assert kopf.count(erwartet) == 1, (
        f"AC-S2-1: die HTML-Kopfzeile fuehrt die Ueberschrift {erwartet!r} "
        f"({soll['key']}) {kopf.count(erwartet)}x statt genau einmal: {kopf}"
    )
    for nummer, zellen in enumerate(_s2_klartext_ausblick(text), start=1):
        assert erwartet in zellen, (
            f"AC-S2-1: Tageszeile {nummer} des KLARTEXT-Ausblicks fuehrt keine "
            f"Spalte {erwartet!r} ({soll['key']}), obwohl das HTML sie zeigt -- "
            f"vorhanden: {sorted(zellen)}"
        )


def test_ac_s2_1_html_und_klartext_zeigen_dieselbe_spaltenmenge():
    """AC-S2-1 (Gegenrichtung): keine Groesse darf im Klartext fehlen, die im
    HTML steht -- und keine darf dort ZUSAETZLICH stehen. Ohne diese Richtung
    bliebe eine ueberzaehlige Spalte unbemerkt."""
    html, text = _s2_mail()
    kopf, zeilen = _s2_html_ausblick(html)
    erwartet = [s["ueberschrift"] for s in _S2_SOLL]

    assert kopf == ["Tag"] + erwartet, (
        f"AC-S2-1: die HTML-Kopfzeile weicht von der Katalog-Soll-Menge ab.\n"
        f"Ist:      {kopf}\nErwartet: {['Tag'] + erwartet}"
    )
    assert len(zeilen) == len(_S2_TAGE), (
        f"AC-S2-1: erwartet {len(_S2_TAGE)} Ausblick-Tageszeilen, erhalten "
        f"{len(zeilen)}"
    )
    for zeile in zeilen:
        assert len(zeile) == len(erwartet) + 1, (
            f"AC-S2-1: Tageszeile traegt {len(zeile)} Zellen statt "
            f"{len(erwartet) + 1} (Tag + {len(erwartet)} Groessen): {zeile}"
        )
    klartext = _s2_klartext_ausblick(text)
    assert len(klartext) == len(_S2_TAGE), (
        f"AC-S2-1: der Klartext-Ausblick hat {len(klartext)} Tageszeilen statt "
        f"{len(_S2_TAGE)}"
    )
    for nummer, zellen in enumerate(klartext, start=1):
        assert sorted(zellen) == sorted(erwartet), (
            f"AC-S2-1: Tageszeile {nummer} des Klartexts zeigt andere Spalten "
            f"als der Katalog verlangt.\nNur im Klartext: "
            f"{sorted(set(zellen) - set(erwartet))}\nFehlt im Klartext: "
            f"{sorted(set(erwartet) - set(zellen))}"
        )


# --- AC-S2-2: Soll-Menge gerechnet, nie getippt (Vakuum-Schutz) -----------


def test_ac_s2_2_soll_menge_wird_gerechnet_und_ist_plausibel():
    """AC-S2-2: die geprueften Groessen stammen ausschliesslich aus
    ``get_compare_metric_catalog()``. Der Plausibilitaets-Waechter schlaegt an,
    wenn die Menge leer ist, unter die Mindestgroesse faellt, die Rechnung
    "roh minus nicht-waehlbar = ausgeliefert" nicht aufgeht oder ein Paar kein
    ``SegmentWeatherSummary``-Feld aufloest. Die parametrisierte Konstante ist
    der Mutations-Ort, die Neuberechnung hier der unabhaengige Pruefort."""
    frisch = assert_soll_menge_ist_plausibel()

    assert [s["key"] for s in frisch] == [s["key"] for s in _S2_SOLL], (
        f"Die parametrisierte Soll-Menge {[s['key'] for s in _S2_SOLL]} weicht "
        f"vom Katalog {[s['key'] for s in frisch]} ab -- eine im Test "
        "aufgezaehlte oder gekuerzte Liste ist genau das, was AC-S2-2 verbietet"
    )
    # Zweite Aufloesungsbedingung: ``outlook_columns()`` verlangt NEBEN dem
    # Katalog-Treffer ein ``summary_field_for()``-Ergebnis
    # (compare_outlook_metric_ids.py:98-100). Beide Bedingungen sind heute
    # deckungsgleich, aber nicht per Konstruktion -- genau deshalb geprueft.
    from output.renderers.compare_outlook_metric_ids import resolve_outlook_metrics

    aufgeloest = resolve_outlook_metrics(list(_S2_SOLL_PAARE))
    assert aufgeloest is not None and len(aufgeloest) == len(_S2_SOLL), (
        f"AC-S2-2: ``resolve_outlook_metrics()`` verwirft "
        f"{len(_S2_SOLL) - len(aufgeloest or [])} der {len(_S2_SOLL)} "
        "Katalog-Paare -- Katalog-Zugehoerigkeit und Feld-Aufloesung sind "
        "auseinandergelaufen, die verworfenen Groessen haetten gar keine Spalte"
    )
    kinds = Counter(s["kind"] for s in _S2_SOLL)
    assert kinds["ordinal"] >= 1 and kinds["enum"] >= 1 and kinds["range"] >= 1, (
        f"AC-S2-2: die Soll-Menge belegt nicht mehr alle drei Formzweige von "
        f"``format_outlook_value()`` (gemessen 2026-08-11: 1 ordinal, 1 enum, "
        f"23 range) -- gezaehlt: {dict(kinds)}"
    )


# --- AC-S2-3: keine zwei Spalten mit derselben Beschriftung ---------------


def test_ac_s2_3_keine_zwei_spalten_mit_gleicher_beschriftung():
    """AC-S2-3: bei voller Auswahl traegt keine zwei Spalten dieselbe
    Beschriftung. Die Unterscheidung entsteht dadurch, dass die Auswertung
    angehaengt wird, sobald derselbe Name mehrfach vorkommt -- die
    Vakuum-Gegenprobe stellt sicher, dass dieser Zweig ueberhaupt greift
    (sonst prueft der Test eine Regel, die nie zur Anwendung kommt)."""
    mehrfach = [n for n, anzahl in Counter(s["label"] for s in _S2_SOLL).items()
                if anzahl > 1]
    assert mehrfach, (
        "Vakuum: keine Groesse kommt im Ausblick-Katalog mehrfach vor -- die "
        "Auswertungs-Unterscheidung waere nie aktiv und dieser Test bewachte "
        "nichts (gemessen 2026-08-11: 'Temperatur' und 'Gefuehlte Temperatur')"
    )

    html, _ = _s2_mail()
    kopf, _ = _s2_html_ausblick(html)
    doppelt = [n for n, anzahl in Counter(kopf).items() if anzahl > 1]
    assert not doppelt, (
        f"AC-S2-3: die Ausblick-Tabelle traegt mehrfach dieselbe Spalten-"
        f"beschriftung {doppelt} -- zwei ununterscheidbare Spalten: {kopf}"
    )


# --- AC-S2-4: jede Zelle traegt einen Wert (DER rote Anteil) --------------


@pytest.mark.parametrize("soll", _S2_SOLL, ids=_S2_SOLL_IDS)
def test_ac_s2_4_jede_zelle_traegt_einen_wert(soll):
    """AC-S2-4: enthalten die Stundendaten fuer eine gewaehlte Groesse Werte,
    zeigt die zugehoerige Zelle einen Wert und NICHT das Fehlzeichen -- in HTML
    und Klartext, an jedem der drei Ausblickstage.

    HEUTE ROT fuer fuenf Groessen (Schneehoehe, Neuschnee, Windrichtung,
    Gefuehlte Temperatur Minimum/Maximum): ``summarize_points()``
    (weather_metrics.py:1071) verdrahtet die zugehoerigen ``_compute_*``-Regeln
    nicht, obwohl sie existieren und im Trip-Pfad angeschlossen sind -- s.
    AC-S2-5."""
    html, text = _s2_mail()
    kopf, zeilen = _s2_html_ausblick(html)
    spalte = kopf.index(soll["ueberschrift"])

    for nummer, zeile in enumerate(zeilen, start=1):
        assert not _s2_zelle_ist_fehlwert(zeile[spalte]), (
            f"AC-S2-4: die HTML-Zelle der Spalte {soll['ueberschrift']!r} "
            f"({soll['key']} -> SegmentWeatherSummary.{soll['summary_field']}) "
            f"zeigt am Ausblickstag {nummer} das Fehlzeichen "
            f"{_S2_FEHLZEICHEN!r}, obwohl die Stundendaten den Wert hergeben "
            "-- der Tages-Aggregationspfad des Vergleichs fuellt das Feld nicht"
        )
    for nummer, zellen in enumerate(_s2_klartext_ausblick(text), start=1):
        assert not _s2_zelle_ist_fehlwert(zellen[soll["ueberschrift"]]), (
            f"AC-S2-4: die KLARTEXT-Zelle der Spalte {soll['ueberschrift']!r} "
            f"({soll['key']} -> SegmentWeatherSummary.{soll['summary_field']}) "
            f"zeigt am Ausblickstag {nummer} das Fehlzeichen "
            f"{_S2_FEHLZEICHEN!r}"
        )


def test_ac_s2_4_keine_gewitterstufe_ist_kein_fehlwert():
    """AC-S2-4 (Pflicht-Gegenprobe): ein Tag OHNE Gewitter zeigt in der
    Gewitter-Zelle den Gedankenstrich U+2014 -- eine inhaltliche Aussage
    ("keine Stufe"), KEIN fehlender Wert. Verkuerzt man die Unterscheidung in
    ``_s2_zelle_ist_fehlwert()`` auf "irgendein Strich", muss dieser Test rot
    werden; bliebe er gruen, prueft AC-S2-4 die Zellen nicht wirklich."""
    gewitter = next((s for s in _S2_SOLL if s["kind"] == "ordinal"), None)
    assert gewitter is not None, (
        "Vakuum: der Compare-Katalog fuehrt keine ordinale Groesse mehr -- die "
        "Gegenprobe haette keinen Gegenstand"
    )

    html, _ = _s2_mail("NONE")
    kopf, zeilen = _s2_html_ausblick(html)
    zelle = zeilen[0][kopf.index(gewitter["ueberschrift"])]

    assert zelle == _S2_KEINE_ANGABE, (
        f"Vorbedingung: ohne Gewitter erwartet die Zelle {_S2_KEINE_ANGABE!r} "
        f"(U+2014, inhaltlich 'keine Stufe'), gemessen: {zelle!r}"
    )
    assert not _s2_zelle_ist_fehlwert(zelle), (
        f"AC-S2-4 (Gegenprobe): {zelle!r} (U+2014) wird als fehlender Wert "
        f"gewertet -- U+2014 und das Fehlzeichen {_S2_FEHLZEICHEN!r} (U+2013) "
        "sind zwei verschiedene Aussagen und duerfen nicht gleichgesetzt werden"
    )


# --- AC-S2-5: die beiden Tages-Aggregationspfade decken sich --------------

# Namentlich gefuehrte, bewusste Abweichungen der beiden Pfade (gemessen
# 2026-08-11 auf demselben Stundensatz). Eine NICHT gelistete Abweichung ist
# ein Befund -- genau daran ist die Fuenferluecke aus AC-S2-4 entstanden.
_S2_NUR_TRIP_ERLAUBT = {
    "confidence_pct_min": (
        "Vorhersage-Verlaesslichkeit ist keine waehlbare Vergleichs-Groesse "
        "(confidence.selectable=False, ADR-0005/#710) und hat im Ausblick "
        "keine Spalte -- eine Verdrahtung in summarize_points() waere "
        "Scope-Zuwachs ohne Nutzerwirkung"
    ),
}
_S2_NUR_COMPARE_ERLAUBT = {
    "hail_flag": (
        "``compute_extended_metrics()`` baut ein NEUES Summary und kopiert "
        "hail_flag nicht aus dem Basis-Aggregat mit (weather_metrics.py:774ff, "
        "gesetzt wird es in compute_basis_metrics:459) -- eigener Befund an "
        "derselben Naht, nicht Gegenstand dieser Scheibe"
    ),
}


def _s2_aggregat_felder(summary) -> set[str]:
    return {
        f.name for f in dataclasses.fields(summary)
        if f.name != "aggregation_config" and getattr(summary, f.name) is not None
    }


def test_ac_s2_5_beide_tagesaggregationen_fuellen_dieselben_felder():
    """AC-S2-5: auf DEMSELBEN Stundensatz fuellt der Vergleichspfad
    (``summarize_points()``) jedes Tagesfeld, das der Trip-Pfad
    (``compute_extended_metrics()``) fuellt -- und umgekehrt. Abweichungen sind
    nur zulaessig, wenn sie oben namentlich gefuehrt sind.

    Beide Seiten laufen mit DERSELBEN neutralen Provider-Kennung
    (``model="aggregate"``, wie ``summarize_points()`` sie selbst setzt), damit
    das rein metadaten-abgeleitete ``cape_model_id`` keine Schein-Abweichung
    erzeugt.

    HEUTE ROT: fuenf Felder fehlen dem Vergleichspfad -- dieselben fuenf, deren
    Ausblick-Zellen in AC-S2-4 das Fehlzeichen tragen. Damit faellt die naechste
    Drift der beiden handgepflegten Listen auf, statt erneut als Strichspalte
    beim Nutzer zu landen (#1324/#1391/#1392 sind drei Flicken an derselben
    Naht)."""
    punkte = [p for p in _s2_punkte(ThunderLevel.MED) if p.ts.date() == _S2_STARTTAG]
    dienst = WeatherMetricsService()
    reihe = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="aggregate", grid_res_km=0.0),
        data=list(punkte),
    )
    trip = _s2_aggregat_felder(
        dienst.compute_extended_metrics(reihe, dienst.compute_basis_metrics(reihe, tz=None))
    )
    vergleich = _s2_aggregat_felder(summarize_points(punkte))

    assert trip and vergleich, (
        f"Vakuum: ein Pfad liefert gar keine Felder (Trip {len(trip)}, "
        f"Vergleich {len(vergleich)}) -- der Mengenvergleich waere sinnlos"
    )
    fehlt_im_vergleich = sorted(trip - vergleich - set(_S2_NUR_TRIP_ERLAUBT))
    assert not fehlt_im_vergleich, (
        f"AC-S2-5: der Vergleichspfad ``summarize_points()`` fuellt "
        f"{fehlt_im_vergleich} nicht, der Trip-Pfad ``compute_extended_metrics()`` "
        "schon. Jedes dieser Felder ist im Ausblick des Ortsvergleichs eine "
        "dauerhaft leere Spalte. Entweder die fehlende ``_compute_*``-Regel "
        "verdrahten oder die Abweichung in _S2_NUR_TRIP_ERLAUBT begruenden."
    )
    fehlt_im_trip = sorted(vergleich - trip - set(_S2_NUR_COMPARE_ERLAUBT))
    assert not fehlt_im_trip, (
        f"AC-S2-5 (Gegenrichtung): der Trip-Pfad fuellt {fehlt_im_trip} nicht, "
        "der Vergleichspfad schon -- dieselbe Drift, nur spiegelbildlich "
        "(so entstand #1391). Ohne diese Richtung bliebe eine gestrichene Zeile "
        "in ``compute_extended_metrics()`` unbemerkt."
    )
    unnoetig = sorted((set(_S2_NUR_TRIP_ERLAUBT) & vergleich)
                      | (set(_S2_NUR_COMPARE_ERLAUBT) & trip))
    assert not unnoetig, (
        f"AC-S2-5: die Ausnahmen {unnoetig} sind gegenstandslos geworden -- "
        "beide Pfade fuellen die Felder inzwischen. Eintraege streichen, sonst "
        "deckt die Ausnahmeliste kuenftige Drift zu."
    )


# --- AC-S2-6: der Fix schiesst nicht ueber sein Ziel hinaus ---------------

# Die 20 Zellen, die schon VOR dem Fix einen Wert trugen -- gemessen
# 2026-08-11 am ersten Ausblickstag der Mail aus ``_s2_mail()``. Schluessel ist
# der ``SegmentWeatherSummary``-Feldname (stabiler als die Beschriftung, die
# AC-S2-1 ohnehin bewacht).
_S2_UNVERAENDERTE_ZELLEN = {
    "sunny_hours": "4.0 h", "wind_max_kmh": "15 km/h", "cloud_avg_pct": "50 %",
    "visibility_min_m": "20000 m", "precip_sum_mm": "4.4 mm", "uv_index_max": "4",
    "temp_max_c": "18 °C", "thunder_level_max": "mittel", "temp_min_c": "6 °C",
    "gust_max_kmh": "25 km/h", "freezing_level_m": "3000 m", "pop_max_pct": "55 %",
    "humidity_avg_pct": "70 %", "dewpoint_avg_c": "5 °C",
    "snowfall_limit_m": "2200 m", "precip_type_dominant": "Regen",
    "cloud_low_avg_pct": "30 %", "cloud_mid_avg_pct": "40 %",
    "cloud_high_avg_pct": "20 %", "pressure_avg_hpa": "1013 hPa",
}


def test_ac_s2_6_bereits_gefuellte_zellen_behalten_ihre_werte():
    """AC-S2-6: der Fix an der Vergleichs-Aggregation darf ueber sein Ziel nicht
    hinausschiessen -- die 20 heute bereits gefuellten Ausblick-Zellen behalten
    Wert und Schreibweise. (Die Trip-Mail schuetzt zusaetzlich der Byte-Golden
    tests/tdd/test_trip_outlook_parity.py; ``summarize_points()`` ist nicht der
    Trip-Aggregator, ein Bruch dort waere ein Signal, kein Nachziehgrund.)"""
    alle_felder = {s["summary_field"] for s in _S2_SOLL}
    assert set(_S2_UNVERAENDERTE_ZELLEN) | set(_S2_DEFEKTE_FELDER) == alle_felder, (
        "Die Charakterisierung deckt den Katalog nicht mehr ab.\nNicht "
        f"charakterisiert: {sorted(alle_felder - set(_S2_UNVERAENDERTE_ZELLEN) - set(_S2_DEFEKTE_FELDER))}\n"
        f"Nicht mehr im Katalog: {sorted(set(_S2_UNVERAENDERTE_ZELLEN) | set(_S2_DEFEKTE_FELDER) - alle_felder)}"
    )

    html, _ = _s2_mail()
    kopf, zeilen = _s2_html_ausblick(html)
    for soll in _S2_SOLL:
        erwartet = _S2_UNVERAENDERTE_ZELLEN.get(soll["summary_field"])
        if erwartet is None:
            continue
        ist = zeilen[0][kopf.index(soll["ueberschrift"])]
        assert ist == erwartet, (
            f"AC-S2-6: die Zelle {soll['ueberschrift']!r} ({soll['key']}) des "
            f"ersten Ausblickstags zeigt {ist!r} statt {erwartet!r} -- der Fix "
            "an der Vergleichs-Aggregation hat einen bereits korrekten Wert "
            "veraendert"
        )


# --- AC-S2-7: Streichungen aus dem Katalog fallen auf ---------------------


def test_ac_s2_7_mindestgroesse_faengt_groessere_streichungen():
    """AC-S2-7 (erste Haelfte): der Vakuum-Schutz aus AC-S2-2 schlaegt an, wenn
    der Katalog deutlich schrumpft. Geprueft ueber DIESELBE Funktion, die der
    echte Waechter aufruft (injizierte Katalogkopie statt Monkeypatch) -- eine
    im Test nachgebaute Pruflogik bewiese nichts."""
    gekuerzt = COMPARE_METRIC_CATALOG[:len(COMPARE_METRIC_CATALOG) // 2]
    with pytest.raises(AssertionError) as fehler:
        assert_soll_menge_ist_plausibel(entries=gekuerzt)
    assert "Vakuum-Schutz" in str(fehler.value), (
        f"AC-S2-7: der Plausibilitaets-Waechter scheitert an einem halbierten "
        f"Katalog aus dem falschen Grund: {fehler.value}"
    )


def test_ac_s2_7_groessenanker_faengt_die_einzelne_streichung():
    """AC-S2-7 (zweite Haelfte): eine EINZELNE gestrichene Katalog-Zeile faengt
    diese Achse nicht -- ihre Soll-Menge schruempfte lautlos mit. Sie faengt der
    unabhaengige, getippte Groessenanker in
    ``test_compare_metric_catalog_endpoint.py`` (``== 25``, Zeile 519).

    Dieser Test macht die Abhaengigkeit pruefbar statt nur behauptet: wird der
    Anker bei einer kuenftigen Aufraeumaktion als "hartcodiert, unschoen"
    entfernt, faellt HIER auf, dass die Deckung ersatzlos weg ist (Lehre aus
    Scheibe 1, Finding F001 -- dort verwies der Kommentar auf einen Anker, den
    niemand gegen Loeschung sicherte)."""
    try:
        from tests.tdd import test_compare_metric_catalog_endpoint as anker
    except ImportError as exc:  # pragma: no cover - Datei geloescht
        raise AssertionError(
            "AC-S2-7: das Ankermodul tests/tdd/"
            "test_compare_metric_catalog_endpoint.py ist nicht mehr importierbar "
            f"-- die einzelne Katalog-Streichung ist damit unbewacht: {exc}"
        ) from exc

    klasse = getattr(anker, "TestUnknownMetricIdFailsVisibly", None)
    pruefung = getattr(klasse, "test_real_catalog_resolves_completely", None)
    assert pruefung is not None, (
        "AC-S2-7: der getippte Groessenanker "
        "TestUnknownMetricIdFailsVisibly::test_real_catalog_resolves_completely "
        "existiert nicht mehr. Er ist die EINZIGE Stelle, die das Streichen "
        "einer einzelnen Compare-Katalog-Zeile bemerkt -- diese Achse rechnet "
        "ihr Soll aus demselben Katalog und schrumpft stillschweigend mit. "
        "Ersatz schaffen, bevor der Anker verschwindet."
    )
    pruefung(klasse())


# --- AC-S2-8: die fuenf neuen Zellen tragen den RICHTIGEN Wert ------------

# Adversary-Finding F001 (Scheibe 2, HIGH): AC-S2-4 prueft "die Zelle traegt
# nicht das Fehlzeichen", AC-S2-5 "welche Felder sind ueberhaupt befuellt" --
# KEINER von beiden prueft, WELCHER Wert drinsteht. Vertauscht man in
# ``summarize_points()`` (weather_metrics.py:1121-1122) die Zuweisungen
# ``wind_chill_min_c`` und ``wind_chill_max_c`` gegeneinander, bleibt diese
# ganze Achse gruen -- und repo-weit prueft kein Test die Zahlenwerte dieser
# fuenf Felder. Genau dort ist ein Vertauscher am wahrscheinlichsten: es sind
# die einzigen zwei der fuenf mit nahezu gleichnamigen Helferfunktionen
# (``_compute_wind_chill`` / ``_compute_wind_chill_max``), und beide Zellen
# zeigen danach einen plausiblen Wert -- der Fehler ist unsichtbar.
#
# Massstab: die Erwartung wird aus den STUNDENWERTEN der Fixture gerechnet --
# weder aus ``_compute_*`` noch aus der Ausgabe von ``summarize_points()``.
# Beides hielte die Ausgabe gegen sich selbst und fiele auf denselben
# Vertauscher erneut herein.
_S2_NEUE_FELDER_REGEL = {
    "snow_depth_cm": "MAXIMUM ueber die Stundenwerte snow_depth_cm",
    "snow_new_sum_cm": "SUMME ueber die Stundenwerte snow_new_24h_cm",
    "wind_direction_avg_deg": "Tagesmittel ueber die Stundenwerte wind_direction_deg",
    "wind_chill_min_c": "MINIMUM ueber die Stundenwerte wind_chill_c",
    "wind_chill_max_c": "MAXIMUM ueber die Stundenwerte wind_chill_c",
}

_S2_ZELLENZAHL = re.compile(r"^-?\d+(?:[.,]\d+)?")


def _s2_erwartete_tageswerte(tagespunkte: list[ForecastDataPoint]) -> dict[str, float]:
    """Die fuenf Tageswerte, aus den Stundenwerten GERECHNET (Regeln oben).

    Die Windrichtung wird bewusst NICHT als Kreismittel nachgebaut: die Fixture
    haelt sie ueber den Tag konstant, und der Tageswert einer konstanten Reihe
    ist genau dieser Wert -- unabhaengig von der Mittelungsvorschrift. Ein hier
    nachgebautes ``atan2`` waere eine Kopie der Implementierung, kein
    unabhaengiger Massstab.
    """
    richtungen = {p.wind_direction_deg for p in tagespunkte}
    assert len(richtungen) == 1, (
        f"Vorbedingung: die Fixture haelt die Windrichtung ueber den Tag "
        f"konstant, gemessen {sorted(richtungen)} -- ohne Konstanz traegt die "
        f"vorschriftsfreie Erwartung fuer wind_direction_avg_deg nicht"
    )
    return {
        "snow_depth_cm": max(p.snow_depth_cm for p in tagespunkte),
        "snow_new_sum_cm": sum(p.snow_new_24h_cm for p in tagespunkte),
        "wind_direction_avg_deg": float(richtungen.pop()),
        "wind_chill_min_c": min(p.wind_chill_c for p in tagespunkte),
        "wind_chill_max_c": max(p.wind_chill_c for p in tagespunkte),
    }


def _s2_erwartungen_je_ausblickstag() -> list[tuple[date, dict[str, float]]]:
    """Je Ausblickstag der Mail ein Paar (Tag, gerechnete Soll-Werte)."""
    punkte = _s2_punkte(ThunderLevel.MED)
    tage = sorted({p.ts.date() for p in punkte})
    return [
        (tag, _s2_erwartete_tageswerte([p for p in punkte if p.ts.date() == tag]))
        for tag in tage
    ]


def _s2_erwartungen_sind_unterscheidbar(
    erwartungen: list[tuple[date, dict[str, float]]],
) -> None:
    """Vakuum-Gegenprobe: eine Wert-Zusicherung faengt eine Vertauschung nur,
    wenn die vertauschten Werte ueberhaupt verschieden sind. Sind sie gleich,
    ist AC-S2-8 blind -- dann muss der Test scheitern und das sagen, statt
    stillschweigend nichts zu bewachen."""
    for tag, werte in erwartungen:
        if werte["wind_chill_min_c"] == werte["wind_chill_max_c"]:
            pytest.fail(
                f"Vakuum: am Ausblickstag {tag} liefert die Fixture fuer "
                f"wind_chill_min_c und wind_chill_max_c denselben Wert "
                f"({werte['wind_chill_min_c']!r}) -- eine Vertauschung der "
                "beiden Zuweisungen in summarize_points() waere damit "
                "unsichtbar und AC-S2-8 blind. Die Stundenreihe des Tages "
                "braucht eine Temperaturspreizung."
            )
    felder = list(_S2_NEUE_FELDER_REGEL)
    for nummer, eins in enumerate(felder):
        for zwei in felder[nummer + 1:]:
            if all(werte[eins] == werte[zwei] for _, werte in erwartungen):
                pytest.fail(
                    f"Vakuum: {eins} und {zwei} tragen an JEDEM Ausblickstag "
                    "denselben Soll-Wert. Waeren ihre Zuweisungen in "
                    "summarize_points() vertauscht oder beide auf dieselbe "
                    "``_compute_*``-Regel gelegt, bliebe AC-S2-8 gruen -- die "
                    "Fixture muss die fuenf Felder unterscheidbar machen."
                )


def test_ac_s2_8_die_fuenf_neuen_felder_tragen_den_gerechneten_wert():
    """AC-S2-8: ``summarize_points()`` liefert fuer die fuenf mit dieser Scheibe
    verdrahteten Tagesfelder GENAU den Wert, den die Stundenwerte hergeben --
    nicht nur "kein Fehlzeichen" (AC-S2-4) und nicht nur "ueberhaupt befuellt"
    (AC-S2-5). Schliesst Adversary-Finding F001: die Zuweisungen duerfen weder
    vertauscht noch auf die falsche ``_compute_*``-Regel gelegt sein."""
    erwartungen = _s2_erwartungen_je_ausblickstag()
    _s2_erwartungen_sind_unterscheidbar(erwartungen)
    punkte = _s2_punkte(ThunderLevel.MED)

    for tag, soll in erwartungen:
        aggregat = summarize_points([p for p in punkte if p.ts.date() == tag])
        ist = {feld: getattr(aggregat, feld) for feld in _S2_NEUE_FELDER_REGEL}
        for feld, regel in _S2_NEUE_FELDER_REGEL.items():
            assert ist[feld] == soll[feld], (
                f"AC-S2-8: ``summarize_points()`` liefert am Ausblickstag {tag} "
                f"fuer {feld} den Wert {ist[feld]!r}; aus den Stundenwerten "
                f"gerechnet ({regel}) sind es {soll[feld]!r}.\n"
                f"Ist:  {ist}\nSoll: {soll}\n"
                "Haeufigster Grund: in weather_metrics.py sind zwei Zuweisungen "
                "VERTAUSCHT -- bei wind_chill_min_c/wind_chill_max_c "
                "(``_compute_wind_chill`` vs. ``_compute_wind_chill_max``) "
                "faellt das sonst nirgends auf, weil danach beide Zellen einen "
                "plausiblen Wert zeigen."
            )


def _s2_zellenzahl(zelle: str) -> float:
    """Die fuehrende Zahl eines Ausblick-Zellentexts ("16 cm" -> 16.0).

    Geprueft wird der WERT, nicht die Schreibweise -- Einheit und
    Nachkommastellen bewacht AC-S2-6.
    """
    treffer = _S2_ZELLENZAHL.match(zelle.strip())
    assert treffer is not None, (
        f"AC-S2-8: die Ausblick-Zelle {zelle!r} beginnt nicht mit einer Zahl -- "
        "ohne Zahl ist der Wert nicht pruefbar"
    )
    return float(treffer.group().replace(",", "."))


def test_ac_s2_8_ausblick_zelle_zeigt_den_gerechneten_wert():
    """AC-S2-8 (Wirkort): derselbe gerechnete Tageswert steht in der Zelle der
    ECHTEN Vergleichs-Mail -- HTML UND Klartext, an jedem der drei Tage. Der
    Nachweis an ``summarize_points()`` allein zeigte nur, dass das Aggregat
    stimmt, nicht dass der Nutzer den richtigen Wert sieht (Pruefort =
    Wirkort)."""
    erwartungen = _s2_erwartungen_je_ausblickstag()
    _s2_erwartungen_sind_unterscheidbar(erwartungen)
    nach_feld = {s["summary_field"]: s for s in _S2_SOLL}
    dezimalen = {e["key"]: e.get("decimals") or 0 for e in get_compare_metric_catalog()}

    html, text = _s2_mail()
    kopf, zeilen = _s2_html_ausblick(html)
    klartext = _s2_klartext_ausblick(text)
    assert len(zeilen) == len(klartext) == len(erwartungen), (
        f"AC-S2-8: {len(zeilen)} HTML-Tageszeilen, {len(klartext)} "
        f"Klartext-Tageszeilen, {len(erwartungen)} Ausblickstage in den "
        "Stundendaten -- ohne 1:1-Zuordnung ist kein Tageswert pruefbar"
    )

    for nummer, (tag, soll) in enumerate(erwartungen):
        for feld, regel in _S2_NEUE_FELDER_REGEL.items():
            spalte = nach_feld[feld]
            erwartet = round(soll[feld], dezimalen[spalte["key"]])
            for form, zelle in (
                ("HTML", zeilen[nummer][kopf.index(spalte["ueberschrift"])]),
                ("KLARTEXT", klartext[nummer][spalte["ueberschrift"]]),
            ):
                assert _s2_zellenzahl(zelle) == erwartet, (
                    f"AC-S2-8: die {form}-Zelle der Spalte "
                    f"{spalte['ueberschrift']!r} ({spalte['key']} -> "
                    f"SegmentWeatherSummary.{feld}) zeigt am Ausblickstag {tag} "
                    f"{zelle!r}; aus den Stundenwerten gerechnet ({regel}) "
                    f"gehoert dort {erwartet!r} hin.\nSoll des Tages: {soll}\n"
                    "Haeufigster Grund: vertauschte Zuweisungen in "
                    "summarize_points() -- bei Gefuehlter Temperatur "
                    "Minimum/Maximum zeigen dann beide Spalten einen "
                    "plausiblen, aber getauschten Wert."
                )


# ===========================================================================
# Epic #1703 Scheibe 4 (AC-S4-1 bis AC-S4-15): Kompaktform-Varianten und
# Telegram-Kurzform. Vier Ausgabeorte -- Kurz-E-Mail (render_compact),
# mobile Kompaktzeilen (_render_mobile_compact_rows), Fliesstext-Kompakt-
# Zusammenfassung (CompactSummaryFormatter.format_stage_summary), Telegram-
# Kurzform (render_telegram_bubbles). Reine Charakterisierung, kein
# Produktivcode-Fix. Spec: docs/specs/modules/fix_1703_s4_kompaktform_matrix.md
#
# KORREKTUR ggue. Spec (waehrend TDD-RED empirisch gemessen, 2026-08-12):
# - Ort 1 (render_compact) ist SELBST threshold-/fixture-gated: von den 15
#   _PILL_CATALOG_ORDER-Metriken feuern mit _matrix_segment() nur 10
#   zuverlaessig (cloud_low/visibility/uv_index/freezing_level/dewpoint
#   liefern mit dieser Fixture keinen Wert -- Fixture-Grenze, kein Befund
#   dieser Scheibe). AC-S4-1 ist auf die 10 zuverlaessig feuernden skaliert.
# - wind_direction erzeugt NIRGENDS (weder Ort 1 -- ohnehin nicht im
#   Pillen-Katalog -- noch Ort 3) einen sichtbaren Unterschied -- echter,
#   gemessener Noop. Eigene Charakterisierung AC-S4-6b statt Aufnahme in die
#   generische AC-S4-6-Parametrisierung.
# - Ort 5 (render_telegram_bubbles) ist ENTGEGEN der urspruenglichen Annahme
#   VOLL generisch: alle 25 waehlbaren Metriken erzeugen zuverlaessig eine
#   Kurzuebersicht-Zeile (kein Dash-/Threshold-Ausfall) -- robusterer Befund
#   als angenommen, AC-S4-12 deckt den vollen Katalog ab, keine Restriktion.
# ===========================================================================


def _s4_compact_render_options(dc: UnifiedWeatherDisplayConfig) -> ReportRenderOptions:
    return ReportRenderOptions(
        email_format="compact", show_outlook=True, show_stage_stats=True,
        show_stability=True, show_compact_summary=True,
        show_multi_day_trend=False, show_yesterday_comparison=True,
        display_config=dc,
    )


def _s4_email_compact_text(dc: UnifiedWeatherDisplayConfig) -> str:
    """Ort 1 -- echtes Rendering ueber render_compact() via format_email()
    (Pruefort=Wirkort, s. Spec 'Bindende Test-Architektur-Entscheidung')."""
    report = TripReportFormatter().format_email(
        [_matrix_segment()], trip_name="Issue1703S4", report_type="evening",
        night_weather=F.night_weather(), display_config=dc, stage_name=F.STAGE_NAME,
        tz=F.TZ, render_options=_s4_compact_render_options(dc),
    )
    return report.email_plain


def _s4_pill_lines(text: str) -> list[str]:
    if "== Metriken-Ueberblick ==" not in text:
        return []
    section = text.split("== Metriken-Ueberblick ==")[1].split("-" * 10)[0]
    return [line for line in section.splitlines() if line.strip()]


def _s4_compact_summary_text(dc: UnifiedWeatherDisplayConfig) -> str:
    """Ort 3 -- echtes Rendering ueber format_stage_summary() via
    format_email(). Extraktion der isolierten Zeile ueber ihre feste
    Position (email/plain.py:148-167: Icon/Eyebrow, Trip-Report-Zeile,
    Etappenname, Datum, Leerzeile, DANN die Zusammenfassung) -- in den hier
    genutzten Fixtures ist stage_stats immer None, die Position ist damit
    deterministisch."""
    report = TripReportFormatter().format_email(
        [_matrix_segment()], trip_name="Issue1703S4", report_type="evening",
        night_weather=F.night_weather(), display_config=dc, stage_name=F.STAGE_NAME,
        tz=F.TZ,
    )
    lines = report.email_plain.splitlines()
    idx = lines.index("")
    return lines[idx + 1]


def _s4_telegram_bubbles(dc: UnifiedWeatherDisplayConfig) -> list[str]:
    """Ort 5 -- echtes Rendering ueber render_telegram_bubbles() via
    format_email(); Telegram bekommt intern eine eigens vorgefilterte
    _dc_telegram (trip_report.py:270-281, Adversary-Fix einer frueheren
    Scheibe)."""
    report = TripReportFormatter().format_email(
        [_matrix_segment()], trip_name="Issue1703S4", report_type="evening",
        night_weather=F.night_weather(), display_config=dc, stage_name=F.STAGE_NAME,
        tz=F.TZ,
    )
    return report.telegram_bubbles


def _s4_kurzuebersicht(dc: UnifiedWeatherDisplayConfig) -> list[str]:
    bubbles = _s4_telegram_bubbles(dc)
    assert len(bubbles) >= 2, f"AC-S4: Kurzuebersicht-Bubble fehlt: {bubbles!r}"
    kb = bubbles[1]
    return [
        line for line in kb.splitlines()
        if line.strip() and line.strip() != "Kurzübersicht"
    ]


# --- Ort 1 -- render_compact() (Kurz-E-Mail) --------------------------------

_S4_PILL_RELIABLE = [
    "temperature", "wind_chill", "wind", "gust", "precipitation",
    "rain_probability", "thunder", "cloud_total", "humidity", "sunshine",
]


@pytest.mark.parametrize("metric_id", _S4_PILL_RELIABLE)
def test_ac_s4_1_email_compact_selection(metric_id):
    """AC-S4-1: eine aktivierte, zuverlaessig feuernde Katalog-Metrik erzeugt
    genau eine Pillen-Zeile im Kurz-E-Mail-Ueberblick; deaktiviert erscheint
    keine."""
    on_lines = _s4_pill_lines(_s4_email_compact_text(_single_metric_dc(metric_id, enabled=True)))
    off_lines = _s4_pill_lines(_s4_email_compact_text(_single_metric_dc(metric_id, enabled=False)))
    assert len(on_lines) == 1, (
        f"AC-S4-1: {metric_id!r} aktiv -> genau 1 Pillen-Zeile erwartet, "
        f"gemessen {on_lines!r}"
    )
    assert off_lines == [], (
        f"AC-S4-1: {metric_id!r} deaktiviert -> keine Pillen-Zeile erwartet, "
        f"gemessen {off_lines!r}"
    )


def test_ac_s4_2_email_compact_fallback_on_empty_selection():
    """AC-S4-2: leere Metrikliste (Altbestand-Pfad) laesst render_compact()
    ueber resolve_trip_active_metrics() auf DEFAULT_TRIP_METRIC_IDS
    zurueckfallen -- keine leere Ausgabe."""
    dc = UnifiedWeatherDisplayConfig(trip_id="s4-empty", metrics=[])
    lines = _s4_pill_lines(_s4_email_compact_text(dc))
    assert lines, (
        "AC-S4-2: leere Metrikliste (altbestand=True) soll auf "
        f"DEFAULT_TRIP_METRIC_IDS={DEFAULT_TRIP_METRIC_IDS} zurueckfallen -- "
        "gemessen keine einzige Pillen-Zeile"
    )


def test_ac_s4_3_email_compact_confidence_absent():
    """AC-S4-3: confidence (selectable=False) erscheint nicht im Kurz-E-Mail-
    Text.

    Korrektur (Adversary-Finding F001, 2026-08-12): die fruehere Docstring-
    Behauptung "das vorgelagerte _is_selectable()-Gate (models.py:684) wirkt
    auch hier" ist per Mutations-Gegenprobe widerlegt -- mit "confidence" in
    _SELECTABLE_GATE_EXEMPT laesst das Gate die Metrik durch, und dieser
    Test bleibt trotzdem GRUEN. Die tatsaechliche Schutzursache ist lokal
    und vom zentralen Gate unabhaengig: build_metrics_summary_pills()
    iteriert ueber die feste Whitelist _PILL_CATALOG_ORDER
    (email/helpers.py:1271-1276, Schleife Z. 1872-1874) und ueberspringt
    jede Metrik, die dort nicht steht -- "confidence" steht dort nicht drin.
    Der Test bleibt als Regression-Baseline des Kurz-E-Mail-Choke-Points
    bestehen, beweist aber NICHT die Gate-Wirkung; die beweist AC-S4-14
    (Telegram)."""
    lines = _s4_pill_lines(_s4_email_compact_text(_single_metric_dc("confidence", enabled=True)))
    assert lines == [], (
        f"AC-S4-3: 'confidence' erscheint im Kurz-E-Mail-Ueberblick: {lines!r}"
    )


# --- Ort 2 -- _render_mobile_compact_rows() (mobile Kompaktzeilen) --------

def test_ac_s4_5_mobile_compact_rows_no_own_selection_logic():
    """AC-S4-5: _render_mobile_compact_rows() hat keine eigene
    Selektionslogik -- sie rendert exakt die vom Aufrufer uebergebene
    allowed_col_keys-Menge. Charakterisierung, keine eigene Achse (deckt
    sich mit Bestand AC-13)."""
    rows = [{"time": "12", "temp": 15.0, "wind": 20.0, "precip": 2.0}]
    html = _render_mobile_compact_rows(rows, friendly_keys=set(), allowed_col_keys={"temp"})
    temp_label = get_metric("temperature").col_label
    wind_label = get_metric("wind").col_label
    assert temp_label in html, (
        f"AC-S4-5: erlaubte Spalte {temp_label!r} fehlt im HTML-Fragment"
    )
    assert wind_label not in html, (
        f"AC-S4-5: nicht erlaubte Spalte {wind_label!r} erscheint trotzdem: {html}"
    )


# --- Ort 3 -- format_stage_summary() (Fliesstext-Kompakt-Zusammenfassung) --

_S4_POSITIVLIST = [
    "temperature", "temperature_night", "wind_chill", "wind_chill_night",
    "cloud_total", "precipitation", "rain_probability", "wind", "gust",
    "wind_direction", "thunder",
]
_S4_POSITIVLIST_OBSERVABLE = [m for m in _S4_POSITIVLIST if m != "wind_direction"]
_S4_NICHTSCOPE = [m for m in _ALL_METRIC_IDS if m not in _S4_POSITIVLIST]


def _s4_baseline_summary() -> str:
    return _s4_compact_summary_text(UnifiedWeatherDisplayConfig(trip_id="s4-base", metrics=[]))


@pytest.mark.parametrize("metric_id", _S4_POSITIVLIST_OBSERVABLE)
def test_ac_s4_6_compact_summary_positivlist_selection(metric_id):
    """AC-S4-6: jede der 10 beobachtbaren Positivlisten-Metriken (alle ausser
    wind_direction, s. AC-S4-6b) erzeugt aktiviert einen vom Basissatz (nur
    Etappenname) abweichenden Fliesstext; deaktiviert bleibt der Basissatz."""
    baseline = _s4_baseline_summary()
    on_text = _s4_compact_summary_text(_single_metric_dc(metric_id, enabled=True))
    off_text = _s4_compact_summary_text(_single_metric_dc(metric_id, enabled=False))
    assert on_text != baseline, (
        f"AC-S4-6: {metric_id!r} aktiv soll den Fliesstext gegenueber dem "
        f"Basissatz {baseline!r} veraendern -- gemessen identisch"
    )
    assert off_text == baseline, (
        f"AC-S4-6: {metric_id!r} deaktiviert soll den Basissatz {baseline!r} "
        f"liefern -- gemessen {off_text!r}"
    )


def test_ac_s4_6b_compact_summary_wind_direction_is_noop():
    """AC-S4-6b (Charakterisierung eines gemessenen Noops): wind_direction
    steht in der Positivliste (Source Punkt 3), veraendert den Fliesstext
    aber weder aktiviert noch deaktiviert -- die Kompassrichtung wird an
    keiner Stelle des Fliesstext-Formulierers ausgegeben. Kein Fix (Auftrag
    dieser Scheibe ist reine Charakterisierung). Faellt dieser Test rot,
    hat sich das Produktivverhalten geaendert -- dann Spec-Korrektur statt
    Test-Anpassung pruefen."""
    baseline = _s4_baseline_summary()
    on_text = _s4_compact_summary_text(_single_metric_dc("wind_direction", enabled=True))
    assert on_text == baseline, (
        f"AC-S4-6b: 'wind_direction' aktiv veraendert den Fliesstext entgegen "
        f"der Messung -- gemessen {on_text!r} statt Basissatz {baseline!r}"
    )


@pytest.mark.parametrize("metric_id", _S4_NICHTSCOPE)
def test_ac_s4_7_compact_summary_nichtscope_metrics_never_appear(metric_id):
    """AC-S4-7 (Charakterisierung des Dauerzustands, PO-Entscheid 2026-08-12,
    Anschluss an #1214 Scheibe 5c): eine waehlbare Metrik ausserhalb der
    Positivliste erscheint nie im Fliesstext -- kein Bug, keine Erweiterung
    in dieser Scheibe."""
    baseline = _s4_baseline_summary()
    text = _s4_compact_summary_text(_single_metric_dc(metric_id, enabled=True))
    assert text == baseline, (
        f"AC-S4-7: {metric_id!r} (ausserhalb Positivliste) veraendert den "
        f"Fliesstext: {text!r} statt Basissatz {baseline!r}"
    )


@pytest.mark.parametrize("metric_id", ["confidence", "temperature_cold", "cape"])
def test_ac_s4_8_10_compact_summary_non_selectable_absent(metric_id):
    """AC-S4-8/9/10: confidence/temperature_cold/cape (selectable=False)
    erscheinen nie im Fliesstext. Anders als beim Mail-Spalten-Fallback
    (Scheibe 3, AC-5) hat format_stage_summary() keinen remaining-Fallback-
    Mechanismus -- die Exemption von temperature_cold wirkt hier nicht,
    weil die Metrik schlicht nicht in der Positivliste steht (AC-S4-9).

    Korrektur fuer den confidence-Fall (Adversary-Finding F001,
    2026-08-12): auch AC-S4-8 belegt NICHT die Wirkung des zentralen
    _is_selectable()-Gates -- unter der Mutations-Gegenprobe ("confidence"
    in _SELECTABLE_GATE_EXEMPT) bleibt dieser Fall GRUEN. Die Schutzursache
    ist dieselbe strukturelle Positivlisten-Mechanik wie bei
    AC-S4-9/AC-S4-10: compact_summary.py enthaelt ueberhaupt keinen
    if/elif-Zweig fuer "confidence" (0 Treffer in der Datei), unabhaengig
    vom Gate-Zustand. Regression-Baseline, kein Gate-Nachweis -- den fuehrt
    AC-S4-14 (Telegram)."""
    baseline = _s4_baseline_summary()
    text = _s4_compact_summary_text(_single_metric_dc(metric_id, enabled=True))
    assert text == baseline, (
        f"AC-S4-8/9/10: {metric_id!r} erscheint im Fliesstext: {text!r}"
    )


# Ort 4 (format_location_summary(), Compare-Wrapper): bewusst KEIN Test.
# Seit Rework #1300 (2026-07-17) von keinem Aufrufer mehr erreicht (grep in
# compare_html.py/comparison.py: keine Treffer) -- ein Test wuerde totes
# Verhalten pruefen, keinen Nutzerpfad. S. Spec Known Limitations Punkt 1.


# --- Ort 5 -- render_telegram_bubbles() (Telegram-Kurzform) ---------------

@pytest.mark.parametrize("metric_id", _ALL_METRIC_IDS)
def test_ac_s4_12_telegram_narrow_selection(metric_id):
    """AC-S4-12: eine aktivierte waehlbare Metrik erzeugt genau eine Zeile
    (Kuerzel am Zeilenanfang) in der Telegram-Kurzuebersicht; deaktiviert
    keine. Generisch ueber alle 25 waehlbaren Metriken -- anders als Ort 1
    (Pillen, threshold-/fixture-gated) liefert _overview_line() fuer jede
    Metrik zuverlaessig einen Wert oder einen Platzhalter-Strich (gemessen)."""
    label = get_metric(metric_id).compact_label
    on_lines = _s4_kurzuebersicht(_single_metric_dc(metric_id, enabled=True))
    off_lines = _s4_kurzuebersicht(_single_metric_dc(metric_id, enabled=False))
    if metric_id in _TELEGRAM_NO_OVERVIEW_ROW:
        # Issue #1728 Scheibe 1: reine Sichtbarkeits-Gates der Kurzform. Sie
        # tragen in der Telegram-Kurzuebersicht KEINEN eigenen Wert -- die
        # T-/TF-Zeile zeigt die Spanne dort unbedingt. Ohne diesen Filter
        # entstuenden vier wertlose Zeilen ("K –", "D –", "FK –", "FD –").
        # Ausdrueckliche Abwesenheits-Assertion statt Ueberspringen.
        assert not any(line.startswith(label + " ") for line in on_lines), (
            f"AC-S4-12/#1728: {metric_id!r} erzeugt eine eigene "
            f"Kurzuebersicht-Zeile ({label!r}), obwohl es nur ein "
            f"Sichtbarkeits-Gate ist: {on_lines!r}"
        )
        assert not any(line.startswith(label + " ") for line in off_lines)
        return
    assert any(line.startswith(label + " ") for line in on_lines), (
        f"AC-S4-12: {metric_id!r} aktiv -> keine Zeile mit Kuerzel {label!r} "
        f"in der Kurzuebersicht: {on_lines!r}"
    )
    assert not any(line.startswith(label + " ") for line in off_lines), (
        f"AC-S4-12: {metric_id!r} deaktiviert -> Zeile mit Kuerzel {label!r} "
        f"erscheint trotzdem: {off_lines!r}"
    )


def test_ac_s4_13_telegram_narrow_no_fallback_on_empty_selection():
    """AC-S4-13 (Resolver-Divergenz-Charakterisierung, Ist-Zustand, kein
    Fix): leere Metrikliste laesst render_telegram_bubbles() -- anders als
    Ort 1 (AC-S4-2, DEFAULT_TRIP_METRIC_IDS-Fallback) -- OHNE jede
    Metrik-Zeile. get_enabled_metric_ids() (models.py:802-804) kennt
    keinen Fallback. Nebenbefund zur strukturellen Divergenz gebucht in
    #1199 (Eintrag vom 2026-08-12)."""
    dc = UnifiedWeatherDisplayConfig(trip_id="s4-empty-tg", metrics=[])
    lines = _s4_kurzuebersicht(dc)
    assert lines == [], (
        "AC-S4-13: leere Metrikliste soll KEINE Kurzuebersicht-Zeile "
        f"erzeugen (kein Fallback, anders als Ort 1) -- gemessen {lines!r}"
    )


def test_ac_s4_14_telegram_narrow_confidence_absent():
    """AC-S4-14: confidence erscheint nicht in der Telegram-Kurzuebersicht --
    render_telegram_bubbles() liest dc.get_enabled_metric_ids() ohne
    eigenes selectable-Gate, aber die vorgelagerte _dc_telegram-Filterung
    (trip_report.py:270-281, Adversary-Fix einer frueheren Scheibe) faengt
    'confidence' bereits ab, bevor render_telegram_bubbles() sie sieht."""
    lines = _s4_kurzuebersicht(_single_metric_dc("confidence", enabled=True))
    assert lines == [], f"AC-S4-14: 'confidence' erscheint: {lines!r}"


# ===========================================================================
# Epic #1703 Scheibe 5 (AC-S5-1 bis AC-S5-6): Compare-Zellwert-
# Vollstaendigkeit der Uebersichtstabelle (CV2_METRICS,
# docs/reference/metric_output_matrix.md Flaeche 4). Reine
# Charakterisierung, kein Produktivcode-Fix.
# SPEC: docs/specs/modules/fix_1703_s5_compare_zellwerte.md
#
# Korrektur der Scheiben-Praemisse (s. Spec): 15 der 25 Uebersichtszeilen
# sind bereits wertgeprueft (#1296/#1324/#1351, Gewitter-Suite) -- AC-S5-6
# haelt den Abhaengigkeits-Anker darauf. Diese Scheibe schliesst die
# restlichen 10 Zeilen (AC-S5-2, Engine-Vorrang-Stichprobe AC-S5-3) und
# ergaenzt zwei generische Achsen, die KEINER der 25 Bestandstests prueft:
# Formatierungs-Konsistenz (AC-S5-4) und Fehlzeichen-Divergenz (AC-S5-5).
#
# Pruefort = Wirkort (Bindende Test-Architektur-Entscheidung der Spec):
# AC-S5-2/3/5 laufen ueber ``render_compare_email()`` -- EIN Aufruf liefert
# HTML UND Klartext derselben Mail, kein isolierter Doppelaufruf (sonst
# Klartext-blinder Fleck, #1366).
# ===========================================================================

_S5_CV2_BY_KEY: dict[str, dict] = {m["key"]: m for m in CV2_METRICS}


def _s5_label(key: str) -> str:
    """Beschriftung derselben Zeile wie im Renderer -- ueber den Katalog
    abgeleitet (``label_de``, Muster ``derive_row_labels``), nicht
    getippt. Innerhalb JEDER in dieser Scheibe gefilterten Zeilenauswahl
    ist jede der zehn Metrik-IDs paarweise verschieden (s. unten), daher
    ohne Kollisions-Zusatz ('Maximum'/'Minimum')."""
    return get_metric(_S5_CV2_BY_KEY[key]["metric_id"]).label_de


_S5_TAGS = re.compile(r"<[^>]+>")


def _s5_overview_rows(html: str) -> list[dict]:
    """Zeilen der Uebersichtstabelle als {'label': str, 'cells': [...]}} --
    Muster ``_overview_rows()`` aus ``test_compare_metric_parity.py`` (Spec
    AC-S5-2 Test-Hinweis)."""
    start = html.index("min-width:760px")
    body = html[html.index("<tbody>", start) + len("<tbody>"):html.index("</tbody>", start)]
    rows = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [
            _S5_TAGS.sub("", c).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
        ]
        if cells:
            rows.append({"label": cells[0], "cells": cells[1:]})
    return rows


def _s5_html_wert(html: str, label: str) -> str:
    zeilen = _s5_overview_rows(html)
    treffer = [r for r in zeilen if r["label"] == label]
    assert len(treffer) == 1, (
        f"AC-S5: erwartet genau eine HTML-Zeile mit Beschriftung {label!r}, "
        f"gefunden {len(treffer)}: {[r['label'] for r in zeilen]}"
    )
    assert len(treffer[0]["cells"]) == 1, (
        f"AC-S5: erwartet genau eine Wertzelle (ein Ort) fuer {label!r}, "
        f"gefunden {treffer[0]['cells']!r}"
    )
    return treffer[0]["cells"][0]


def _s5_klartext_wert(text: str, label: str) -> str:
    """Klartext-Zeilenwert -- Muster ``_plain_row_value()`` aus
    ``test_compare_metric_parity.py`` (Spec AC-S5-2 Test-Hinweis), hier per
    Label-PRAEFIX statt Schluesselwort-Enthaltensein: die Beschriftung ist
    innerhalb der gefilterten Auswahl dieser Scheibe eindeutig."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{label}:"):
            return stripped.split(":", 1)[1].strip()
    pytest.fail(
        f"AC-S5: im Klartext derselben Mail ist keine Zeile {label!r} "
        f"auffindbar.\n{text}"
    )
    return ""  # unreachable, haelt Typpruefer ruhig


_S5_ZELLENZAHL = re.compile(r"^-?\d+(?:[.,]\d+)?")


def _s5_zellenzahl(zelle: str) -> float:
    """Die fuehrende Zahl einer Uebersichts-Zelle ("22°C" -> 22.0). Geprueft
    wird der WERT, nicht die Schreibweise -- Einheit/Nachkommastellen
    bewacht AC-S5-4."""
    treffer = _S5_ZELLENZAHL.match(zelle.strip())
    assert treffer is not None, (
        f"AC-S5: die Zelle {zelle!r} beginnt nicht mit einer Zahl -- ohne "
        "Zahl ist der Wert nicht pruefbar"
    )
    return float(treffer.group().replace(",", "."))


# Klasse-A-Felder ohne Trip-Regel (snow_depth_cm/snow_new_cm, s. Spec
# Implementation Details): unterscheidbarer Literalwert statt Aggregation --
# die ComparisonEngine, die diese Felder aus Stundendaten befuellt, liegt
# ausserhalb dieses Renderers (Known Limitations Punkt 2).
_S5_SNOW_DEPTH_CM = 12.0
_S5_SNOW_NEW_CM = 7.0

# Vier reich besetzte Stundenpunkte EINES Tages (Spalten: Stunde, Temp,
# Wind, Wolken, Regen, PoP, UV, Sicht_m, DNI) -- jedes der zehn Felder
# unterschiedlich ueber die Stunden verteilt, damit MIN/MAX/SUM/AVG sich
# unterscheiden (Vakuum-Gegenprobe unten, Lehre AC-S2-8).
_S5_STUNDENWERTE = (
    (6, 10.0, 15.0, 20, 1.0, 30, 2.0, 15000, 100.0),
    (10, 18.0, 25.0, 50, 2.0, 50, 6.0, 12000, 500.0),
    (14, 22.0, 35.0, 60, 1.4, 65, 9.0, 8000, 700.0),
    (18, 15.0, 20.0, 30, 0.0, 40, 3.0, 20000, 200.0),
)


def _s5_punkte() -> list[ForecastDataPoint]:
    return [
        ForecastDataPoint(
            ts=datetime(2026, 8, 12, stunde, 0, tzinfo=timezone.utc),
            t2m_c=temp, wind10m_kmh=wind, cloud_total_pct=wolken,
            precip_1h_mm=regen, pop_pct=pop, uv_index=uv, visibility_m=sicht,
            dni_wm2=dni, is_day=1, thunder_level=ThunderLevel.NONE,
        )
        for stunde, temp, wind, wolken, regen, pop, uv, sicht, dni in _S5_STUNDENWERTE
    ]


def _s5_timeseries(hourly: list[ForecastDataPoint]) -> NormalizedTimeseries:
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="s5-test", grid_res_km=1.0)
    return NormalizedTimeseries(meta=meta, data=hourly)


def _s5_location(hourly: list[ForecastDataPoint]):
    """Klasse A (temp_max/wind_max/cloud_avg/sunny_hours): derselbe Trip-Weg
    wie die 15 bereits gedeckten Zeilen (``WeatherMetricsService``, s. Spec
    Implementation Details) -- diese Werte werden wie von der
    ComparisonEngine VORGEGEBEN behandelt, der Renderer liest sie nur per
    ``getattr`` (Klasse A hat keine eigene Aggregation). snow_depth_cm/
    snow_new_cm: unterscheidbarer Literalwert (Klasse A ohne Trip-Regel).
    Klasse-B-Felder (precip_sum_mm etc.) bleiben BEWUSST auf ihrem Default
    None -- AC-S5-2 prueft damit den Live-Ableitungspfad, AC-S5-3 separat
    den Engine-Vorrang."""
    from app.user import LocationResult, SavedLocation

    basis = WeatherMetricsService().compute_basis_metrics(_s5_timeseries(hourly), tz=None)
    return LocationResult(
        location=SavedLocation(
            id="s5-ort", name="S5-Ort", lat=47.0, lon=11.0, elevation_m=500,
        ),
        score=50,
        temp_max=basis.temp_max_c, wind_max=basis.wind_max_kmh,
        cloud_avg=basis.cloud_avg_pct, sunny_hours=basis.sunny_hours,
        snow_depth_cm=_S5_SNOW_DEPTH_CM, snow_new_cm=_S5_SNOW_NEW_CM,
        hourly_data=hourly,
    )


_S5_NEU_GEPRUEFT_ORDER = (
    "temp_max", "wind_max", "cloud_avg", "sunny_hours",
    "snow_depth_cm", "snow_new_cm", "precip_sum", "pop_max", "uv_max",
    "visibility_min",
)

_S5_DECIMALS: dict[str, int] = {
    "temp_max": 0, "wind_max": 0, "cloud_avg": 0, "sunny_hours": 1,
    "snow_depth_cm": 0, "snow_new_cm": 0, "precip_sum": 1, "pop_max": 0,
    "uv_max": 0, "visibility_min": 1,
}
# visibility_min: HTML/Klartext zeigen km, die Fixture traegt m (Faktor
# 1000, s. Spec "visibility_min Einheiten-Hinweis").
_S5_FAKTOR: dict[str, float] = {"visibility_min": 0.001}


def _s5_erwartete_werte(hourly: list[ForecastDataPoint]) -> dict[str, float]:
    """Die zehn Soll-Tageswerte, UNABHAENGIG von der Uebersichtstabelle
    gerechnet (Spec Implementation Details, Klasse A/B).

    Klasse A (temp_max/wind_max/cloud_avg/sunny_hours) kommt aus derselben
    Trip-Regel, mit der ``_s5_location`` das ``LocationResult`` befuellt --
    der Renderer hat hierfuer keine eigene Aggregation, ein Fehler koennte
    nur in der Zellzuordnung/Formatierung stecken.

    Klasse B (precip_sum/pop_max/uv_max/visibility_min) wird HANDFEST aus
    den Stundenwerten gerechnet (SUM/MAX/MAX/MIN) -- NICHT ueber
    ``summarize_points()``/``compute_basis_metrics()``: sonst hielte ein
    Fehler in deren ``_compute_*``-Regeln die Renderer-Ausgabe gegen sich
    selbst, und eine vertauschte Zuweisung bliebe unsichtbar (Lehre
    AC-S2-8/F001)."""
    basis = WeatherMetricsService().compute_basis_metrics(_s5_timeseries(hourly), tz=None)
    return {
        "temp_max": basis.temp_max_c,
        "wind_max": basis.wind_max_kmh,
        "cloud_avg": basis.cloud_avg_pct,
        "sunny_hours": basis.sunny_hours,
        "snow_depth_cm": _S5_SNOW_DEPTH_CM,
        "snow_new_cm": _S5_SNOW_NEW_CM,
        "precip_sum": sum(p.precip_1h_mm for p in hourly),
        "pop_max": max(p.pop_pct for p in hourly),
        "uv_max": max(p.uv_index for p in hourly),
        "visibility_min": min(p.visibility_m for p in hourly),
    }


def _s5_werte_sind_unterscheidbar(soll: dict[str, float]) -> None:
    """Vakuum-Gegenprobe (Muster ``_s2_erwartungen_sind_unterscheidbar``):
    eine Wert-Zusicherung faengt eine Feldvertauschung nur, wenn die
    vertauschten Werte ueberhaupt verschieden sind."""
    felder = list(soll)
    for i, eins in enumerate(felder):
        for zwei in felder[i + 1:]:
            if soll[eins] == soll[zwei]:
                pytest.fail(
                    f"Vakuum: {eins} und {zwei} tragen denselben Soll-Wert "
                    f"({soll[eins]!r}) -- eine Vertauschung waere damit "
                    "unsichtbar und AC-S5-2 blind. Die Fixture muss die "
                    "zehn Felder unterscheidbar machen."
                )


@lru_cache(maxsize=None)
def _s5_mail_neue_felder() -> tuple[str, str]:
    """Die ECHTE Vergleichs-Mail (``render_compare_email``) mit genau den
    zehn neu geprueften Zeilen (Filterung ueber ``enabled_metrics`` -- alle
    zehn Katalog-IDs sind paarweise verschieden, daher keine Label-Kollision/
    -Zusatz durch ``derive_row_labels``). Gecacht, weil jede AC-S5-2-Instanz
    dieselbe Mail liest."""
    from app.user import ComparisonResult

    hourly = _s5_punkte()
    ort = _s5_location(hourly)
    ergebnis = ComparisonResult(
        locations=[ort], time_window=(6, 18), target_date=date(2026, 8, 12),
        created_at=datetime(2026, 8, 12, 4, 1),
    )
    return render_compare_email(ergebnis, enabled_metrics=list(_S5_NEU_GEPRUEFT_ORDER))


# --- AC-S5-1: Soll-Menge gerechnet, Bucket-Vollstaendigkeit ---------------

_S5_BEREITS_GEDECKT = frozenset({
    # tests/unit/test_compare_extra_daily_metrics.py (#1296)
    "temp_min", "gust_max", "freezing_level",
    # tests/unit/test_compare_metric_parity.py (#1324)
    "wind_direction_avg", "wind_chill_min", "cloud_low_avg", "cloud_mid_avg",
    "cloud_high_avg", "humidity_avg", "dewpoint_avg", "pressure_avg",
    "precip_type", "snowfall_limit",
    # tests/test_wind_chill_max_selectable.py
    "wind_chill_max",
    # tests/tdd/test_thunder_low_output_channels.py (AC-11)
    "thunder_max",
})


def test_ac_s5_1_soll_menge_gerechnet_und_vollstaendig():
    """AC-S5-1: die 25 Compare-Uebersichtszeilen (CV2_METRICS ohne ``warn``)
    zerfallen VOLLSTAENDIG und UEBERSCHNEIDUNGSFREI in die 15 bereits
    wertgeprueften (AC-S5-6) und die 10 neu geprueften (AC-S5-2) Zeilen --
    beide Mengen kommen aus dem Produktivmodul, nicht getippt."""
    ist_keys = {m["key"] for m in CV2_METRICS if m["key"] != "warn"}
    assert len(ist_keys) == 25 >= 20, (
        f"Vakuum: {len(ist_keys)} Compare-Uebersichtszeilen (ohne 'warn') -- "
        "unter der Mindestgroesse waere die Bucket-Aufteilung unten trivial"
    )
    neu_gepr = frozenset(_S5_NEU_GEPRUEFT_ORDER)
    assert len(neu_gepr) == 10, f"Vakuum: {sorted(neu_gepr)} enthaelt Duplikate"
    assert _S5_BEREITS_GEDECKT.isdisjoint(neu_gepr), (
        f"AC-S5-1: {sorted(_S5_BEREITS_GEDECKT & neu_gepr)} stehen in BEIDEN "
        "Buckets -- Ueberschneidung statt Aufteilung"
    )
    vereinigung = _S5_BEREITS_GEDECKT | neu_gepr
    assert vereinigung == ist_keys, (
        f"AC-S5-1: 15+10 deckt nicht die vollen 25 CV2_METRICS-Zeilen.\n"
        f"Fehlt in 15+10: {sorted(ist_keys - vereinigung)}\n"
        f"Zusaetzlich in 15+10 (existiert nicht mehr in CV2_METRICS): "
        f"{sorted(vereinigung - ist_keys)}"
    )


# --- AC-S5-2: die zehn ungeprueften Zeilen zeigen den gerechneten Wert ----


@pytest.mark.parametrize("key", _S5_NEU_GEPRUEFT_ORDER)
def test_ac_s5_2_die_zehn_ungeprueften_zeilen_zeigen_den_gerechneten_wert(key):
    """AC-S5-2: die zehn bislang ungeprueften Compare-Uebersichtszeilen
    zeigen in der ECHTEN Vergleichs-Mail (``render_compare_email``) sowohl
    HTML als auch Klartext exakt den unabhaengig gerechneten Tageswert --
    kein Fehlzeichen, kein vertauschtes Feld."""
    hourly = _s5_punkte()
    soll = _s5_erwartete_werte(hourly)
    _s5_werte_sind_unterscheidbar(soll)
    label = _s5_label(key)
    erwartet = round(soll[key] * _S5_FAKTOR.get(key, 1.0), _S5_DECIMALS[key])

    html, text = _s5_mail_neue_felder()
    html_zelle = _s5_html_wert(html, label)
    assert _s5_zellenzahl(html_zelle) == erwartet, (
        f"AC-S5-2: die HTML-Zelle {label!r} ({key}) zeigt {html_zelle!r}; "
        f"aus den Stundenwerten gerechnet gehoert dort {erwartet!r} hin "
        f"(Soll-Rohwert {soll[key]!r})."
    )
    klartext_zelle = _s5_klartext_wert(text, label)
    assert _s5_zellenzahl(klartext_zelle) == erwartet, (
        f"AC-S5-2: die KLARTEXT-Zeile {label!r} ({key}) zeigt "
        f"{klartext_zelle!r}; aus den Stundenwerten gerechnet gehoert dort "
        f"{erwartet!r} hin (Soll-Rohwert {soll[key]!r})."
    )


# --- AC-S5-3: Klasse B -- Engine-Feld hat Vorrang vor Live-Ableitung ------

_S5_VORRANG_FELDER = ("precip_sum", "pop_max")


@pytest.mark.parametrize("key", _S5_VORRANG_FELDER)
def test_ac_s5_3_engine_feld_hat_vorrang_vor_live_ableitung(key):
    """AC-S5-3: ist am ``LocationResult`` ein Engine-Tagesfeld gesetzt UND
    ``hourly_data`` mit einem ABWEICHENDEN Wert vorhanden, zeigt die Zelle
    (HTML wie Klartext) den Engine-Wert -- der generische, feldunabhaengige
    Vorrang-Zweig in ``_metric_value()`` (compare_html.py:648-651). Zwei
    Felder genuegen als Stichprobe (Spec 'Engine-Vorrang')."""
    from app.user import ComparisonResult, LocationResult, SavedLocation

    hourly = _s5_punkte()
    if key == "precip_sum":
        live_wert = sum(p.precip_1h_mm for p in hourly)
        engine_feld, engine_wert = "precip_sum_mm", live_wert + 50.0
    else:
        live_wert = max(p.pop_pct for p in hourly)
        engine_feld, engine_wert = "pop_max_pct", min(100, round(live_wert / 2))
    assert engine_wert != live_wert, (
        "Vakuum: Engine- und Live-Wert muessen sich unterscheiden, sonst "
        "waere ein fehlender Vorrang unsichtbar"
    )

    ort = LocationResult(
        location=SavedLocation(
            id="s5-vorrang", name="S5-Vorrang", lat=47.0, lon=11.0, elevation_m=500,
        ),
        score=50, hourly_data=hourly, **{engine_feld: engine_wert},
    )
    ergebnis = ComparisonResult(
        locations=[ort], time_window=(6, 18), target_date=date(2026, 8, 12),
        created_at=datetime(2026, 8, 12, 4, 1),
    )
    html, text = render_compare_email(ergebnis, enabled_metrics=[key])
    label = _s5_label(key)
    erwartet = round(engine_wert, _S5_DECIMALS[key])

    html_zelle = _s5_html_wert(html, label)
    assert _s5_zellenzahl(html_zelle) == erwartet, (
        f"AC-S5-3: die HTML-Zelle {label!r} ({key}) zeigt {html_zelle!r} -- "
        f"erwartet den Engine-Wert {erwartet!r}, nicht den Live-Wert "
        f"{live_wert!r}"
    )
    klartext_zelle = _s5_klartext_wert(text, label)
    assert _s5_zellenzahl(klartext_zelle) == erwartet, (
        f"AC-S5-3: die KLARTEXT-Zeile {label!r} ({key}) zeigt "
        f"{klartext_zelle!r} -- erwartet den Engine-Wert {erwartet!r}, "
        f"nicht den Live-Wert {live_wert!r}"
    )


# --- AC-S5-4: Formatierungs-Konsistenz format_value <-> CV2_METRICS -------

_S5_FORMAT_FELDER: dict[str, str] = {
    # CV2-Key -> Katalog-Metrik-ID, die der Klartext-Lambda TATSAECHLICH
    # uebergibt (comparison.py _PLAIN_ROWS/_DAILY_PLAIN_ROWS, s. Spec
    # "Formatierungs-Konsistenz"). wind_chill_min/wind_chill_max/
    # dewpoint_avg rufen "temperature" statt der eigenen ID -- Nebenbefund
    # (#1199): heute folgenlos, weil beide Seiten bei 0 Nachkommastellen
    # liegen, faellt aber bei kuenftiger Katalog-Aenderung dieser drei IDs
    # nicht mehr auf.
    "temp_max": "temperature",
    "temp_min": "temperature",
    "wind_max": "wind",
    "gust_max": "wind",
    "wind_chill_min": "temperature",
    "wind_chill_max": "temperature",
    "dewpoint_avg": "temperature",
    "cloud_avg": "cloud_total",
    "snow_depth_cm": "snow_depth",
    "sunny_hours": "sunshine",
}


@pytest.mark.parametrize("cv2_key,klartext_metric_id", sorted(_S5_FORMAT_FELDER.items()))
def test_ac_s5_4_formatierung_katalog_und_uebersicht_bleiben_synchron(cv2_key, klartext_metric_id):
    """AC-S5-4: fuer jedes der zehn ``format_value``-getriebenen Felder
    stimmen die Nachkommastellen des Katalogs (Klartext-Pfad,
    ``get_metric(...).decimals``) und von ``CV2_METRICS``/``_fmt_metric``
    (HTML-Pfad) EINZELN ueberein -- rein struktureller Vergleich, kein
    Rendering noetig. Ein Fehlschlag benennt genau das betroffene Feld
    (Feld-Granularitaets-Fang).

    Issue #1848 Scheibe B: der HTML-Wert wird dort gelesen, wo
    ``_render_overview_row`` ihn holt -- aus der von ``derive_row_labels()``
    zurueckgegebenen Zeilen-Kopie. ``CV2_METRICS`` selbst tippt seit dieser
    Scheibe kein ``decimals`` mehr; ein Zugriff direkt auf die Modul-Konstante
    laese jetzt still ``0`` statt des tatsaechlich gerenderten Wertes.

    🔴 ENTSCHEIDENDE FOLGE -- dieser Waechter beweist seit Scheibe B nur noch
    fuer 4 der 10 Faelle etwas. Die Kopie holt ihr ``decimals`` aus
    ``get_metric(row["metric_id"])``; wo diese ID mit ``klartext_metric_id``
    ZUSAMMENFAELLT, vergleicht der Test dieselbe Katalogquelle mit sich selbst
    und kann strukturell nicht mehr fehlschlagen. TAUTOLOGISCH sind diese 6:
    ``temp_max`` (temperature), ``temp_min`` (temperature), ``wind_max``
    (wind), ``cloud_avg`` (cloud_total), ``snow_depth_cm`` (snow_depth),
    ``sunny_hours`` (sunshine) -- sie duerfen NICHT als Absicherung der
    Formatierung gelesen werden. Nachgewiesen: Register-``sunshine.decimals``
    von 1 auf 4 verbogen, dieser Test bleibt gruen, obwohl die gerenderte
    Zelle dann ``5.6000 h`` statt ``5.6 h`` zeigt.

    Echten Biss behalten die 4 Zeilen, in denen ZWEI VERSCHIEDENE Metrik-IDs
    gegeneinander stehen -- ``gust_max`` (gust vs. wind),
    ``wind_chill_min`` und ``wind_chill_max`` (wind_chill vs. temperature),
    ``dewpoint_avg`` (dewpoint vs. temperature). Fuer sie ist der Test eine
    ABBILDUNGS-Pruefung: er faengt, wenn der Klartext-Lambda eine fremde
    Groesse zum Formatieren heranzieht, deren Nachkommastellen von der
    tatsaechlich gezeigten Groesse abweichen (Nebenbefund #1199 oben).

    Der echte Formatier-Waechter ist seit Scheibe B
    ``tests/unit/test_compare_mail_metric_format_from_register.py``, AC-7:
    alle 22 Zeilen mit ``metric_id``, gemessen am GERENDERTEN HTML gegen fest
    hinterlegte Erwartungswerte vom Stand VOR der Aenderung -- also gegen eine
    Referenz ausserhalb des Prueflings, die eine Register-Verfaelschung
    tatsaechlich rot faerbt."""
    katalog_decimals = get_metric(klartext_metric_id).decimals or 0
    cv2_eintrag = next(
        m for m in derive_row_labels(CV2_METRICS, form="long")
        if m["key"] == cv2_key
    )
    cv2_decimals = cv2_eintrag.get("decimals") or 0
    assert katalog_decimals == cv2_decimals, (
        f"AC-S5-4: {cv2_key!r} zeigt im Klartext "
        f"get_metric({klartext_metric_id!r}).decimals={katalog_decimals}, "
        f"in der HTML-Uebersicht aber CV2_METRICS[{cv2_key!r}]"
        f"['decimals']={cv2_decimals} -- die beiden Formatierungswege sind "
        "auseinandergelaufen."
    )


# --- AC-S5-5: Fehlzeichen-Charakterisierung -- HTML EM DASH, Klartext HYPHEN

_S5_FEHLZEICHEN_FELDER = ("temp_max", "cloud_avg")


@pytest.mark.parametrize("key", _S5_FEHLZEICHEN_FELDER)
def test_ac_s5_5_fehlzeichen_html_em_dash_klartext_hyphen(key):
    """AC-S5-5 (Charakterisierung, kein Fix -- PO-Entscheidung, s. Spec
    Purpose): fehlt der Wert einer generischen ``_fmt_metric``-Zeile, zeigt
    HTML das EM DASH U+2014, Klartext den ASCII HYPHEN U+002D --
    bytegenauer Codepoint-Vergleich, keine 'sieht aus wie ein Strich'-
    Pruefung. Der dritte, im Modul existierende En-Dash-Zweig
    (``format_value``s ``_NO_VALUE``) ist hier NICHT Gegenstand (im
    Compare-Uebersichtspfad strukturell unerreichbar, s. Spec)."""
    from app.user import ComparisonResult, LocationResult, SavedLocation

    ort = LocationResult(
        location=SavedLocation(
            id="s5-fehlwert", name="S5-Fehlwert", lat=47.0, lon=11.0, elevation_m=500,
        ),
        score=50,  # temp_max/cloud_avg bleiben auf ihrem Default None
    )
    ergebnis = ComparisonResult(
        locations=[ort], time_window=(6, 18), target_date=date(2026, 8, 12),
        created_at=datetime(2026, 8, 12, 4, 1),
    )
    html, text = render_compare_email(ergebnis, enabled_metrics=[key])
    label = _s5_label(key)

    html_zelle = _s5_html_wert(html, label)
    assert len(html_zelle) == 1 and ord(html_zelle) == 0x2014, (
        f"AC-S5-5: HTML-Zelle {label!r} ({key}) ohne Wert zeigt {html_zelle!r} "
        f"(Codepoints {[hex(ord(c)) for c in html_zelle]}) -- erwartet genau "
        "U+2014 EM DASH"
    )
    klartext_zelle = _s5_klartext_wert(text, label)
    assert len(klartext_zelle) == 1 and ord(klartext_zelle) == 0x2D, (
        f"AC-S5-5: KLARTEXT-Zeile {label!r} ({key}) ohne Wert zeigt "
        f"{klartext_zelle!r} (Codepoints {[hex(ord(c)) for c in klartext_zelle]}) "
        "-- erwartet genau U+002D ASCII HYPHEN"
    )


# --- AC-S5-6: Abhaengigkeits-Anker auf die 15 bereits gedeckten Zeilen ----

_S5_ANKER_MODULE: dict[str, tuple[str, ...]] = {
    "tests.unit.test_compare_metric_parity": (
        "test_selected_wind_direction_metric_appears_in_overview_matrix",
        "test_selected_wind_chill_min_metric_appears_in_overview_matrix",
        "test_selected_cloud_low_metric_appears_in_overview_matrix",
        "test_selected_cloud_mid_metric_appears_in_overview_matrix",
        "test_selected_cloud_high_metric_appears_in_overview_matrix",
        "test_selected_humidity_metric_appears_in_overview_matrix",
        "test_selected_dewpoint_metric_appears_in_overview_matrix",
        "test_selected_pressure_metric_appears_in_overview_matrix",
        "test_selected_precip_type_metric_appears_in_overview_matrix",
        "test_selected_snowfall_limit_metric_appears_in_overview_matrix",
        "test_plaintext_shows_all_ten_new_rows",
    ),
    "tests.unit.test_compare_extra_daily_metrics": (
        "test_selected_temp_min_metric_appears_in_overview_matrix",
        "test_selected_gust_max_metric_appears_in_overview_matrix",
        "test_selected_freezing_level_metric_appears_in_overview_matrix",
        "test_plaintext_shows_the_three_remaining_new_rows",
    ),
    "tests.test_wind_chill_max_selectable": (
        "test_compare_html_renderer_shows_wind_chill_max_value",
        "test_compare_plain_renderer_shows_wind_chill_max_value",
    ),
    "tests.tdd.test_thunder_low_output_channels": (
        "test_ac11_compare_html_zeigt_leicht",
    ),
}


@pytest.mark.parametrize("modulname", sorted(_S5_ANKER_MODULE))
def test_ac_s5_6_abhaengigkeits_anker_auf_die_15_bereits_gedeckten_zeilen(modulname):
    """AC-S5-6: die vier Testdateien, die heute 15 der 25 CV2_METRICS-Zeilen
    wertgeprueft halten, muessen importierbar bleiben und die genannten
    Testfunktionen weiterhin fuehren -- verschwindet eine, reisst diese
    Scheibe eine unbemerkte Deckungsluecke (Lehre Scheibe 1/2 F001)."""
    try:
        modul = importlib.import_module(modulname)
    except ImportError as exc:
        pytest.fail(
            f"AC-S5-6: {modulname} ist nicht mehr importierbar ({exc}) -- "
            "die Wertpruefung fuer einen Teil der 15 bereits gedeckten "
            "Compare-Uebersichtszeilen ist verwaist."
        )
        return
    for name in _S5_ANKER_MODULE[modulname]:
        assert hasattr(modul, name), (
            f"AC-S5-6: {modulname} fuehrt keine Testfunktion {name!r} mehr -- "
            "die Wertpruefung fuer eine der 15 bereits gedeckten Compare-"
            "Uebersichtszeilen ist verwaist."
        )


# ===========================================================================
# Epic #1703 Scheibe 7 (AC-S7-1 bis AC-S7-9): Reihenfolge-Waechter jenseits
# E-Mail-Vollformat und Telegram-rich (docs/reference/metric_output_matrix.md
# Flaeche 5). SPEC: docs/specs/modules/fix_1703_s7_reihenfolge_matrix.md
#
# Korrektur der Scheiben-Praemisse (s. Spec): Flaeche 5 nennt die
# Trip-SMS-Reihenfolge als Luecke -- sie ist seit #1677/#1660 B ueber
# AC-15 (c) oben bewacht. Bewacht war dagegen NICHT die Katalog-DECKUNG der
# Compare-Uebersicht (Bestand `tests/unit/test_compare_metric_order.py`:
# 4 fest getippte von 25 Groessen, EINE globale Liste) und gar nicht die
# Kanal-Achse aus Scheibe 8.
#
# Pruefmuster durchgehend PAARWEISE: dieselbe Metrik-MENGE in zwei
# Reihenfolgen rendern und die Positionen vergleichen. Ein Test gegen eine
# einzelne feste Erwartung faengt "intern nach eigener Prioritaet umsortiert"
# nicht.
#
# Pruefort = Wirkort: gemessen wird die zugestellte Ausgabe je Kanal, nie der
# Rueckgabewert von `resolve_channel_enabled_metrics()` (Lehre Scheibe 8:
# viermal war die reine Funktion geprueft und die Aufrufstelle nicht).
#
# ROTER Anteil: AC-S7-6 (die Kurz-E-Mail-Pillen verwerfen die Reihenfolge,
# `build_metrics_summary_pills()` kollabiert die geordnete Liste zu einer
# Menge). Alles Uebrige ist Charakterisierung bisher ungeprueften, aber
# korrekten Verhaltens.
# ===========================================================================

_S7_SOLL = compare_order_soll_metriken()


def _s7_dp(hour: int, temp: float, wind: float) -> ForecastDataPoint:
    """EIN reich besetzter Stundenpunkt -- jede der 25 Uebersichts-Groessen
    muss an jedem Ort einen Wert haben, sonst entfaellt ihre Zeile/Zelle und
    der Test misst das Fehlen statt der Reihenfolge."""
    return ForecastDataPoint(
        ts=datetime(2026, 8, 12, hour, 0, tzinfo=timezone.utc),
        t2m_c=temp, wind10m_kmh=wind, wind_direction_deg=180, gust_kmh=wind + 10,
        precip_1h_mm=1.0, cloud_total_pct=40, cloud_low_pct=10, cloud_mid_pct=20,
        cloud_high_pct=30, pop_pct=50, uv_index=4.0, visibility_m=9000,
        pressure_msl_hpa=1013.0, humidity_pct=70, dewpoint_c=8.0,
        snow_depth_cm=3.0, snow_new_24h_cm=2.0, snowfall_limit_m=1800,
        freezing_level_m=3200, precip_type=PrecipType.RAIN,
        thunder_level=ThunderLevel.MED, wind_chill_c=temp - 2, is_day=1,
        dni_wm2=300.0,
    )


def _s7_location(loc_id: str, name: str):
    from app.user import LocationResult, SavedLocation

    return LocationResult(
        location=SavedLocation(
            id=loc_id, name=name, lat=47.0, lon=11.0, elevation_m=600,
        ),
        score=1,
        temp_max=22.0, temp_min=11.0, wind_max=15.0, gust_max=30.0,
        wind_direction_avg=180, wind_chill_min=8.0, wind_chill_max=18.0,
        cloud_avg=40, cloud_low_avg=10, cloud_mid_avg=20, cloud_high_avg=30,
        sunny_hours=5, snow_depth_cm=3.0, snow_new_cm=2.0,
        precip_sum_mm=2.0, pop_max_pct=50, uv_index_max=4.0,
        visibility_min_m=9000, thunder_level_max=ThunderLevel.MED,
        hourly_data=[_s7_dp(9, 12.0, 10.0), _s7_dp(12, 22.0, 15.0), _s7_dp(15, 18.0, 12.0)],
        official_alerts=[],
    )


@lru_cache(maxsize=None)
def _s7_result(anzahl: int = 3):
    """``ComparisonResult`` mit ``anzahl`` gleich befuellten Orten. Gecacht --
    die Renderer sind reine Funktionen, jede Achse liest dasselbe Ergebnis."""
    from app.user import ComparisonResult

    namen = ["Aachen", "Bremen", "Chemnitz"][:anzahl]
    return ComparisonResult(
        locations=[_s7_location(f"s7-{i}", nm) for i, nm in enumerate(namen)],
        time_window=(0, 23), target_date=date(2026, 8, 12),
        created_at=datetime(2026, 8, 12, 4, 0),
    )


@lru_cache(maxsize=None)
def _s7_mail_paar(metric_id: str):
    """Beide Reihenfolgen EINES Metrik-Paares als ((html_a, text_a),
    (html_b, text_b)). EIN ``render_compare_email()``-Aufruf je Richtung
    liefert HTML UND Klartext derselben Mail -- AC-S7-2 und AC-S7-3 lesen
    denselben Aufruf, damit eine Divergenz zwischen beiden Formen nicht durch
    getrennte Aufrufe verdeckt wird."""
    partner = partner_von(metric_id)
    return (
        render_compare_email(_s7_result(), enabled_metrics=[metric_id, partner]),
        render_compare_email(_s7_result(), enabled_metrics=[partner, metric_id]),
    )


# --- AC-S7-1: Soll-Menge gerechnet, Vakuum-geschuetzt ----------------------

def test_ac_s7_1_soll_menge_gerechnet_und_vakuumgeschuetzt():
    """AC-S7-1: die geprueften Groessen stammen ausschliesslich aus
    ``get_compare_metric_catalog()`` (26 rohe Katalog-Zeilen minus der nicht
    waehlbaren ``cape_max_jkg`` = 25), nie aus einer getippten Liste; unter
    20 Eintraegen scheitert der Vakuum-Schutz ausdruecklich."""
    soll = assert_compare_order_soll_ist_plausibel()
    assert soll == _S7_SOLL, (
        "AC-S7-1: die Modul-Konstante _S7_SOLL und die frisch gerechnete "
        f"Soll-Menge laufen auseinander: {_S7_SOLL} vs. {soll}"
    )


def test_ac_s7_1b_vakuum_schutz_schlaegt_bei_leerem_katalog_an():
    """AC-S7-1 (Pflicht-Gegenprobe, Spec Mutation 5): waere der Katalog leer
    oder stark geschrumpft, MUSS der Vakuum-Schutz scheitern statt
    stillschweigend zu bestehen -- sonst liefe die ganze Achse ueber null
    Faelle und waere immer gruen. Geprueft ueber die Katalog-Injektion
    (``entries=``), ohne den echten Katalog anzufassen."""
    with pytest.raises(AssertionError):
        assert_compare_order_soll_ist_plausibel(entries=[])
    with pytest.raises(AssertionError):
        assert_compare_order_soll_ist_plausibel(
            entries=[e for e in COMPARE_METRIC_CATALOG[:3]]
        )


# --- AC-S7-2: Compare-HTML folgt der Reihenfolge, ueber den ganzen Katalog -

@pytest.mark.parametrize("metric_id", _S7_SOLL)
def test_ac_s7_2_compare_html_folgt_der_reihenfolge(metric_id):
    """AC-S7-2: dieselbe Vergleichs-Mail, einmal mit [A, B] und einmal mit
    [B, A] gerendert, zeigt in der HTML-Uebersichtstabelle die beiden Zeilen
    in genau dieser Reihenfolge -- fuer JEDE der 25 waehlbaren Groessen
    gegen einen festen Partner, nicht nur fuer vier ausgewaehlte (Bestand
    #1359)."""
    partner = partner_von(metric_id)
    sichtbare = [metric_id, partner]
    label_m = uebersichts_label(metric_id, sichtbare)
    label_p = uebersichts_label(partner, sichtbare)
    assert label_m != label_p, (
        f"Vakuum: {metric_id!r} und Partner {partner!r} teilen sich die "
        f"Beschriftung {label_m!r} -- eine Positionsaussage waere mehrdeutig"
    )
    (html_a, _text_a), (html_b, _text_b) = _s7_mail_paar(metric_id)
    assert html_uebersicht_labels(html_a) == [label_m, label_p], (
        f"AC-S7-2: Reihenfolge [{metric_id}, {partner}] ergibt in der "
        f"HTML-Uebersicht {html_uebersicht_labels(html_a)}"
    )
    assert html_uebersicht_labels(html_b) == [label_p, label_m], (
        f"AC-S7-2: Reihenfolge [{partner}, {metric_id}] ergibt in der "
        f"HTML-Uebersicht {html_uebersicht_labels(html_b)} -- dieselbe MENGE "
        "in zwei Reihenfolgen muss zwei verschiedene Zeilenfolgen ergeben"
    )


# --- AC-S7-3: Compare-Klartext folgt derselben Reihenfolge ----------------

@pytest.mark.parametrize("metric_id", _S7_SOLL)
def test_ac_s7_3_compare_klartext_folgt_derselben_reihenfolge(metric_id):
    """AC-S7-3: der Klartext-Teil DERSELBEN Mail (ein Aufruf, zwei Formen)
    zeigt dieselbe Metrik-Reihenfolge wie der HTML-Teil -- und zwar
    zugeordnet, nicht nur gleich lang (Lehre Scheibe 2 F001: Rechnen sichert
    Vollstaendigkeit, nie Zuordnung)."""
    partner = partner_von(metric_id)
    sichtbare = [metric_id, partner]
    label_m = uebersichts_label(metric_id, sichtbare)
    label_p = uebersichts_label(partner, sichtbare)
    (html_a, text_a), (html_b, text_b) = _s7_mail_paar(metric_id)
    for richtung, html, text, erwartet in (
        ("A", html_a, text_a, [label_m, label_p]),
        ("B", html_b, text_b, [label_p, label_m]),
    ):
        klartext = klartext_uebersicht_labels(text)
        assert klartext == erwartet, (
            f"AC-S7-3 (Richtung {richtung}): der Klartext-Teil zeigt "
            f"{klartext} statt {erwartet}"
        )
        assert klartext == html_uebersicht_labels(html), (
            f"AC-S7-3 (Richtung {richtung}): Klartext {klartext} weicht vom "
            f"HTML {html_uebersicht_labels(html)} DERSELBEN Mail ab"
        )


# --- AC-S7-4: Altbestand ohne gespeicherte Auswahl (Charakterisierung) ----

def test_ac_s7_4_altbestand_html_und_klartext_divergieren_charakterisiert():
    """AC-S7-4 (CHARAKTERISIERUNG, kein Fix -- Spec 'Bewusst NICHT in dieser
    Scheibe'): ohne gespeicherte Auswahl (``enabled_metrics=None``) behaelt
    jede Form derselben Mail ihre eigene Quellcode-Ordnung. Die MENGEN sind
    identisch (25 Zeilen), die ORDNUNG nicht -- erste Abweichung an Position
    3: HTML fuehrt dort ``precip_sum`` (CV2_METRICS), der Klartext
    ``temp_min`` (_PLAIN_ROWS).

    Ein Fix zoege den Bestandstest ``test_compare_metric_order.py`` AC-7 mit,
    der die _PLAIN_ROWS-Ordnung ausdruecklich als Altbestands-Standard
    einfriert -- eigene Entscheidung, Nebenbefund #1199. Faellt dieser Test
    rot, hat sich das Produktivverhalten geaendert: dann Spec-Korrektur statt
    Test-Anpassung pruefen."""
    html, text = render_compare_email(_s7_result(), enabled_metrics=None)
    html_labels = html_uebersicht_labels(html)
    text_labels = klartext_uebersicht_labels(text)
    assert len(html_labels) == len(_S7_SOLL) == len(text_labels), (
        f"AC-S7-4: {len(html_labels)} HTML- und {len(text_labels)} "
        f"Klartext-Zeilen bei {len(_S7_SOLL)} Katalog-Groessen"
    )
    assert set(html_labels) == set(text_labels), (
        "AC-S7-4: HTML und Klartext zeigen NICHT dieselbe Menge -- das waere "
        "ein anderer, schwererer Befund als die reine Ordnungs-Divergenz.\n"
        f"nur HTML: {sorted(set(html_labels) - set(text_labels))}\n"
        f"nur Klartext: {sorted(set(text_labels) - set(html_labels))}"
    )
    assert html_labels != text_labels, (
        "AC-S7-4: die Altbestands-Divergenz ist verschwunden -- gut moeglich "
        "ein bewusster Fix, dann gehoert diese Charakterisierung ersetzt "
        "(und der Bestandstest AC-7 mitgezogen)."
    )
    erste_abweichung = next(
        i for i, (h, t) in enumerate(zip(html_labels, text_labels)) if h != t
    )
    assert erste_abweichung == 2, (
        f"AC-S7-4: erste Abweichung an Position {erste_abweichung + 1}, "
        "gemessen 2026-08-13 war es Position 3"
    )
    assert html_labels[2] == uebersichts_label("precip_sum", _S7_SOLL), (
        f"AC-S7-4: HTML-Position 3 traegt {html_labels[2]!r}"
    )
    assert text_labels[2] == uebersichts_label("temp_min", _S7_SOLL), (
        f"AC-S7-4: Klartext-Position 3 traegt {text_labels[2]!r}"
    )


# --- AC-S7-5: kanalweise unterschiedliche Reihenfolge in EINER Sendung ----
#
# Die drei Kanal-Listen fuehren DIESELBE Menge in DREI verschiedenen
# Reihenfolgen, die Grundauswahl (= MAXIMUM, ADR-0050 Regel 1) in einer
# VIERTEN. Faellt eine der acht Aufrufstellen auf die gemeinsame
# `opts.enabled_metrics` zurueck, zeigt genau dieser Kanal die vierte
# Ordnung und faellt EINZELN auf -- ein Nachweis auf
# `resolve_channel_enabled_metrics()` faenge das nicht (dort ist die
# Mechanik korrekt, die Wirkung haengt an der Aufrufstelle).
#
# Der Daten-/Engine-Rahmen (`env`, oben importiert) ist der Waechter aus
# Scheibe 8: echte Engine-Subklasse, echte Renderer, kein Mock/patch, kein Netz.

_S7_KANAL_ORDNUNG: dict[str, list[str]] = {
    "email": ["temp_max_c", "sunny_hours_h", "uv_index_max"],
    "telegram": ["sunny_hours_h", "uv_index_max", "temp_max_c"],
    "sms": ["uv_index_max", "temp_max_c", "sunny_hours_h"],
}
_S7_GRUNDAUSWAHL = ["temp_max_c", "uv_index_max", "sunny_hours_h"]


def _s7_kanal_preset(preset_id: str, user_id: str) -> dict:
    return {
        "id": preset_id, "name": "S7-Reihenfolge", "user_id": user_id,
        "kind": "vergleich", "location_ids": [_S7_LOCATION.id], "schedule": "daily",
        "profil": "ALLGEMEIN", "created_at": "2026-07-01T00:00:00Z",
        "send_telegram": True, "send_sms": True,
        # Stundenverlauf/Ausblick aus: diese Achse betrifft NUR die
        # Uebersicht -- beide Bloecke wuerden die Kuerzel-Suche stoeren.
        "hourly_enabled": False, "outlook_enabled": False,
        "display_config": {
            "active_metrics": list(_S7_GRUNDAUSWAHL),
            "channel_active_metrics": {k: list(v) for k, v in _S7_KANAL_ORDNUNG.items()},
        },
    }


def _s7_erwartete_renderer_ids(kanal: str) -> list[str]:
    return [FRONTEND_TO_RENDERER_METRIC_ID[k] for k in _S7_KANAL_ORDNUNG[kanal]]


def _s7_pruefe_kanal_reihenfolge(
    kanal: str, ausgabe: str, wo: str, ids: list[str] | None = None,
) -> None:
    """Die Reihenfolge-Aussage je Kanal an der jeweils ZUGESTELLTEN Ausgabe --
    HTML-Zeilenfolge, Telegram-Zellfolge, SMS-Tokenfolge.

    ``ids`` injiziert eine andere Soll-Folge als die des Kanals (Vorbild
    ``assert_compare_order_soll_ist_plausibel(entries=...)``), damit die
    Gegenprobe unten den Vergleich selbst pruefen kann."""
    ids = _s7_erwartete_renderer_ids(kanal) if ids is None else ids
    if kanal == "email":
        erwartet = [uebersichts_label(m, ids) for m in ids]
        assert html_uebersicht_labels(ausgabe) == erwartet, (
            f"{wo}: die E-Mail zeigt {html_uebersicht_labels(ausgabe)} statt "
            f"{erwartet} -- vermutlich liest die Aufrufstelle wieder die "
            f"gemeinsame `opts.enabled_metrics` ({_S7_GRUNDAUSWAHL})"
        )
    elif kanal == "telegram":
        zellen = telegram_zellen(ausgabe)
        erwartet = [_PLAIN_ROWS_BY_ID[m][1] for m in ids]
        # Das GANZE Label tragen, nie nur sein erstes Wort (Adversary S7 F001):
        # "Gefuehlte Temp. min"/"Gefuehlte Temp. max" und "Wolken"/"Wolken
        # tief" teilen sich den Wortanfang -- ein Wortanfang-Vergleich hielte
        # ihre Vertauschung fuer richtig (Gegenproben: AC-S7-5c/5d unten).
        # Muster AC-S7-8a: volles Label per ``startswith``.
        #
        # Das angehaengte Leerzeichen ist Haertung gegen eine VERTAUSCHTE
        # GROESSE ("Wolken " faengt nicht auf "Wolken tief 10%" an), nicht
        # gegen eine vertauschte REIHENFOLGE: auf einer Permutation derselben
        # Menge sind beide Formen gleichwertig, weil ein Label nur Praefix
        # eines echt laengeren sein kann und die Gesamtlaenge erhalten bleibt.
        # 5c/5d unterscheiden es deshalb NICHT (gemessen 2026-08-14: das
        # Leerzeichen entfernt -> alle fuenf S7-5-Achsen bleiben gruen). Es
        # kostet nichts, weil jede der 25 Uebersichts-Zellen die Form
        # "<Label> <Wert>" hat (ebenfalls gemessen).
        assert len(zellen) == len(erwartet) and all(
            z.startswith(f"{e} ") for z, e in zip(zellen, erwartet)
        ), f"{wo}: Telegram zeigt {zellen} statt der Reihenfolge {erwartet}"
    else:
        ort = _s7_result(1).locations[0]
        positionen = [sms_index(ausgabe, sms_kuerzel(ort, m)) for m in ids]
        assert all(p is not None for p in positionen), (
            f"{wo}: nicht jede gewaehlte Groesse steht in der SMS "
            f"({positionen}) -- {ausgabe!r}"
        )
        assert positionen == sorted(positionen), (
            f"{wo}: die SMS-Token-Folge {positionen} widerspricht der "
            f"eingestellten Reihenfolge {ids} -- {ausgabe!r}"
        )


def test_ac_s7_5_versand_traegt_je_kanal_eine_eigene_reihenfolge(
    env,  # noqa: F811 - pytest loest die Fixture per Name auf
    tmp_path,
):
    """AC-S7-5: GIVEN ein Vergleich, dessen drei Kanaele DIESELBEN Groessen in
    DREI verschiedenen Reihenfolgen fuehren / WHEN der echte Versandpfad
    laeuft / THEN traegt jede zugestellte Nachricht die Reihenfolge IHRES
    Kanals."""
    from app.config import Settings
    from services.scheduler_dispatch_service import send_one_compare_preset

    ordnungen = [tuple(v) for v in _S7_KANAL_ORDNUNG.values()] + [tuple(_S7_GRUNDAUSWAHL)]
    assert len(set(ordnungen)) == 4, (
        "Vakuum: die drei Kanal-Reihenfolgen und die Grundauswahl muessen "
        f"paarweise verschieden sein, sind aber {ordnungen}"
    )

    versandt: dict[str, list[str]] = {"email": [], "telegram": [], "sms": []}
    send_one_compare_preset(
        _s7_kanal_preset("cp-s7-dispatch", env),
        Settings(
            smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
            mail_to="dummy@example.invalid", telegram_bot_token="dummy-token",
            telegram_chat_id="123456", sms_gateway_url="https://sms.invalid",
            seven_api_key="k", sms_to="+491700000000",
        ),
        env, str(tmp_path), all_locations_cache=[_S7_LOCATION],
        target_date=_S7_TARGET_DATE, tage_ab_ortstag=0,
        mail_sink=lambda subject, body: versandt["email"].append(body),
        telegram_sink=versandt["telegram"].append,
        sms_sink=versandt["sms"].append,
    )
    for kanal, zugestellt in versandt.items():
        assert len(zugestellt) == 1, (
            f"{kanal}: eine Zustellung erwartet, waren {len(zugestellt)}"
        )
        _s7_pruefe_kanal_reihenfolge(kanal, zugestellt[0], "Versandpfad")


def test_ac_s7_5b_vorschau_zeigt_dieselbe_reihenfolge_wie_der_versand(
    env,  # noqa: F811 - pytest loest die Fixture per Name auf
):
    """AC-S7-5 (zweiter Leser derselben Optionen): die Vorschau MUSS je Kanal
    dieselbe Reihenfolge zeigen wie der Versand -- sonst verspricht der Editor
    eine andere Zeilenfolge, als ankommt. Deckt die uebrigen fuenf der acht
    Aufrufstellen (`compare_preview_service.py`)."""
    from app.loader import get_data_dir, save_location
    from services.compare_preview_service import ComparePreviewService
    from tests.helpers.compare_briefings import write_compare_briefings

    save_location(_S7_LOCATION, user_id=env)
    write_compare_briefings(get_data_dir(env), [_s7_kanal_preset("cp-s7-preview", env)])

    service = ComparePreviewService()
    args = dict(user_id=env, target_date=_S7_TARGET_DATE.isoformat())
    payload = service.render_all_channels("cp-s7-preview", **args)
    for kanal, key in (("email", "email_html"), ("telegram", "telegram"), ("sms", "sms")):
        _s7_pruefe_kanal_reihenfolge(kanal, payload[key], f"Vorschau[{key}]")
    _s7_pruefe_kanal_reihenfolge(
        "telegram", service.render_telegram_preview("cp-s7-preview", **args),
        "Vorschau render_telegram_preview",
    )
    _s7_pruefe_kanal_reihenfolge(
        "sms", service.render_sms_preview("cp-s7-preview", **args),
        "Vorschau render_sms_preview",
    )


def test_ac_s7_5c_telegram_vergleich_faengt_praefix_kollision():
    """AC-S7-5 (Pflicht-Gegenprobe, Adversary S7 F001): der Telegram-Zweig von
    ``_s7_pruefe_kanal_reihenfolge`` MUSS eine Vertauschung auch dann sehen,
    wenn beide Labels denselben Wortanfang haben.

    Gemessen an einer ECHT vertauschten Render-Ausgabe, nicht an einem
    gebastelten String: der frueher benutzte Wortanfang-Vergleich haelt sie
    fuer richtig, der Label-Vergleich schlaegt an. Ohne diese Achse waere der
    Fix eine Vermutung."""
    ids = ["wind_chill_min", "wind_chill_max"]
    erwartet = [_PLAIN_ROWS_BY_ID[m][1] for m in ids]
    assert len(set(e.split(" ")[0] for e in erwartet)) == 1, (
        f"Vakuum: {ids} teilen sich ihren Wortanfang nicht mehr ({erwartet}) "
        "-- die Gegenprobe pruefte dann eine Kollision, die es nicht gibt"
    )
    assert len(set(erwartet)) == len(erwartet), (
        f"Vakuum: {ids} teilen sich das GANZE Telegram-Label ({erwartet}) -- "
        "auch ein Label-Vergleich koennte ihre Reihenfolge nicht sehen"
    )

    vertauscht = render_compare_telegram(
        _s7_result(), enabled_metrics=list(reversed(ids)),
    )
    zellen = telegram_zellen(vertauscht)
    assert [z.split(" ")[0] for z in zellen] == [e.split(" ")[0] for e in erwartet], (
        f"Vakuum: der ALTE Wortanfang-Vergleich muss auf {zellen} gruen sein, "
        "sonst belegt die Gegenprobe nichts"
    )
    with pytest.raises(AssertionError):
        _s7_pruefe_kanal_reihenfolge("telegram", vertauscht, "Gegenprobe", ids=ids)


@pytest.mark.parametrize(
    "ids",
    [
        ["cloud_avg", "cloud_low_avg"],
        ["cloud_avg", "cloud_low_avg", "cloud_mid_avg"],
    ],
    ids=["paar", "tripel"],
)
def test_ac_s7_5d_telegram_vergleich_faengt_die_wolken_kollision(ids):
    """AC-S7-5 (zweite Pflicht-Gegenprobe, Adversary S7 F002): die Wolken-
    Familie ist die haertere Kollision -- "Wolken" ist nicht nur
    wortanfangsgleich mit "Wolken tief"/"Wolken mittel", sondern deren echtes
    PRAEFIX. AC-S7-5c oben deckt nur das wind_chill-Paar; die Wolken-Familie
    stand bisher bloss im Kommentar.

    Die drei sind so gewaehlt, dass ALLE denselben Wortanfang "Wolken" tragen
    -- der frueher benutzte Wortanfang-Vergleich ist damit auf JEDER
    Vertauschung gruen und kann keine einzige sehen. Geprueft werden alle
    Vertauschungen statt nur der umgekehrten Folge, und der Tripel-Fall
    zusaetzlich zum Paar: bei zwei Elementen liesse sich ein Fang noch mit dem
    Sonderfall der Vollvertauschung erklaeren, bei drei nicht mehr."""
    erwartet = [_PLAIN_ROWS_BY_ID[m][1] for m in ids]
    assert len({e.split(" ")[0] for e in erwartet}) == 1, (
        f"Vakuum: {ids} teilen sich ihren Wortanfang nicht mehr ({erwartet}) "
        "-- die Gegenprobe pruefte dann eine Kollision, die es nicht gibt"
    )
    assert len(set(erwartet)) == len(erwartet), (
        f"Vakuum: {ids} teilen sich das GANZE Telegram-Label ({erwartet})"
    )

    for folge in itertools.permutations(ids):
        if list(folge) == ids:
            continue
        vertauscht = render_compare_telegram(
            _s7_result(), enabled_metrics=list(folge),
        )
        zellen = telegram_zellen(vertauscht)
        assert [z.split(" ")[0] for z in zellen] == [
            e.split(" ")[0] for e in erwartet
        ], (
            f"Vakuum: der ALTE Wortanfang-Vergleich muss auf {zellen} gruen "
            "sein, sonst belegt die Gegenprobe nichts"
        )
        with pytest.raises(AssertionError):
            _s7_pruefe_kanal_reihenfolge(
                "telegram", vertauscht, f"Gegenprobe {list(folge)}", ids=ids,
            )


# --- AC-S7-6: DER FIX -- die Kurz-E-Mail folgt der eingestellten Ordnung --

def _s7_email_layout_dc(reihenfolge: list[str]) -> UnifiedWeatherDisplayConfig:
    """Trip mit E-Mail-KANAL-Layout in ``reihenfolge``. ``format_email()``
    kollabiert `dc.metrics` vor dem Rendern auf
    ``get_metrics_for_channel("email", ...)`` (trip_report.py:133-138) --
    diese Reihenfolge ist damit genau die, die ``render_compact()`` sieht
    (gemessen 2026-08-13)."""
    return UnifiedWeatherDisplayConfig(
        trip_id="s7-pillen",
        metrics=[
            MetricConfig(metric_id=m, enabled=True, order=i)
            for i, m in enumerate(sorted(reihenfolge))
        ],
        per_channel_layouts={
            "email": [
                MetricConfig(metric_id=m, enabled=True, bucket="primary", order=i)
                for i, m in enumerate(reihenfolge)
            ],
        },
    )


def _s7_pillen(reihenfolge: list[str]) -> list[str]:
    return [
        zeile.strip()
        for zeile in _s4_pill_lines(_s4_email_compact_text(_s7_email_layout_dc(reihenfolge)))
    ]


def _s7_pill_partner(metric_id: str) -> str:
    """``temperature`` steht als erste Groesse der Katalog-Ordnung
    (``_PILL_CATALOG_ORDER``) vor jeder anderen -- als Partner macht sie den
    Unterschied zwischen Katalog- und Nutzer-Ordnung in BEIDEN Richtungen
    sichtbar."""
    return "wind" if metric_id == "temperature" else "temperature"


@pytest.mark.parametrize("metric_id", _S4_PILL_RELIABLE)
def test_ac_s7_6_kurz_email_pillen_folgen_der_eingestellten_reihenfolge(metric_id):
    """AC-S7-6 (DER Produktivcode-Fix dieser Scheibe -- heute ROT): fuehrt das
    E-Mail-Kanal-Layout zwei Groessen in einer von der Katalogordnung
    abweichenden Reihenfolge, erscheinen die beiden Pillen im
    Metriken-Ueberblick der Kurz-E-Mail heute trotzdem in KATALOGORDNUNG:
    ``build_metrics_summary_pills()`` (email/helpers.py:1899-1901) kollabiert
    die geordnete Liste zu ``ids_set = set(metric_ids)`` und iteriert
    anschliessend ``_PILL_CATALOG_ORDER``. Die im Editor eingestellte
    Reihenfolge kann diesen Ausgabeort strukturell nicht erreichen -- ein
    Bedienelement ohne Wirkung."""
    partner = _s7_pill_partner(metric_id)
    a = _s7_pillen([metric_id, partner])
    b = _s7_pillen([partner, metric_id])
    assert len(a) == 2 and len(b) == 2, (
        f"Vakuum: {metric_id!r}/{partner!r} ergeben {a} bzw. {b} statt je "
        "zwei Pillen -- ohne zwei Pillen ist keine Reihenfolge messbar"
    )
    assert a[0] != a[1], (
        f"Vakuum: beide Pillen tragen denselben Text {a[0]!r}"
    )
    assert a == list(reversed(b)), (
        f"AC-S7-6: Layout [{metric_id}, {partner}] ergibt {a}, Layout "
        f"[{partner}, {metric_id}] ergibt {b} -- dieselbe MENGE in zwei "
        "Reihenfolgen muss zwei verschiedene Pillenfolgen ergeben"
    )
    assert a != b, (
        f"AC-S7-6: beide Layouts ergeben dieselbe Pillenfolge {a} -- die "
        "eingestellte Reihenfolge wird verworfen"
    )


# Am 2026-08-13 am unveraenderten Renderer abgenommen: Text UND Ampelstufe je
# Pille bei KATALOG-Ordnung. Der Fix aus AC-S7-6 aendert ausschliesslich die
# Reihenfolge -- bleibt diese Erwartung gruen, sind Auswahl, Abwahl,
# Schwellenlogik und Ampelstufen nachweislich unberuehrt.
#
# Fix #1801 S2 (2026-08-14): EIN Eintrag fortgeschrieben, sonst nichts.
# helpers._pill_for_metric() liest den Gewitter-Ton seither aus derselben
# SSoT wie die Stundentabelle (thunder_ampel_band(), ADR-0025, AC-5) statt
# fest "ampel_red" zu liefern -- fuer die Testdaten dieser Datei ist das
# Ergebnis "orange" (zwei Ausrufezeichen), vorher hart "!!!"/rot. NACHGEMESSEN
# per echtem Testlauf, nicht angenommen: die uebrigen neun Eintraege sind
# byte-identisch geblieben (nur Index 6 wich ab). Reichweite gemessen: diese
# Pillenform (`build_metrics_summary_pills`) wird ausschliesslich von den
# E-Mail-Renderern erzeugt (email/compact.py, email/plain.py, email/html.py);
# SMS laeuft ueber den eigenstaendigen SMSTripFormatter (sms_trip.py), Telegram
# ueber compact_summary.py/trip_report.py -- keiner der beiden importiert
# build_metrics_summary_pills. Betrifft also nur den E-Mail-Kanal.
_S7_PILLEN_BASIS_KATALOGORDNUNG = [
    "3-20C - Max 11:00",
    "gef. 1.0-18.0C - Max 11:00",
    "! Wind >10 km/h ab 04:00 - max 45 (10:00)",
    "!!! Boeen >20 km/h ab 04:00 - max 70 (10:00)",
    "!! Regen ab 05:00 - 8.9 mm",
    "!!! Regen-W. >20% ab 05:00 - max 95% (11:00)",
    # #1493: Stufenwort in der Pille (Ampelpraefix und Reihenfolge unveraendert).
    "!! Gewitter mittel ab 11:00 - staerkste 11:00",
    "50% bewoelkt - Max 08:00",
    "Feuchte 55-55% - Max 08:00",
    "Sonne 150 min",
]


def test_ac_s7_6b_pilleninhalt_bleibt_bei_katalogordnung_bytegleich():
    """AC-S7-6 (Begleitschutz): bei einem E-Mail-Layout IN Katalogordnung
    bleiben die Pillen byte-gleich zum heutigen Zustand -- Text, Ampel-
    Praefix und Reihenfolge. Der Fix darf nur die Ausgabereihenfolge einer
    ABWEICHENDEN Nutzerliste aendern, nichts sonst."""
    katalog_ordnung = [m for m in _PILL_CATALOG_ORDER if m in _S4_PILL_RELIABLE]
    assert len(katalog_ordnung) == len(_S4_PILL_RELIABLE), (
        "Vakuum: nicht jede zuverlaessig feuernde Pillen-Metrik steht in "
        f"_PILL_CATALOG_ORDER: {sorted(set(_S4_PILL_RELIABLE) - set(katalog_ordnung))}"
    )
    assert _s7_pillen(katalog_ordnung) == _S7_PILLEN_BASIS_KATALOGORDNUNG, (
        "AC-S7-6b: der Pillen-INHALT hat sich geaendert, nicht nur die "
        f"Reihenfolge:\n{_s7_pillen(katalog_ordnung)}"
    )


# --- AC-S7-7: Trip-Telegram-Kurzuebersicht folgt der Reihenfolge ----------

# temperature_night/wind_chill_night unterdruecken ihre eigene Zeile, sobald
# die Tages-Groesse mitgewaehlt ist (narrow.py:745-760) -- mit einem festen
# Partner waere ihr Verhalten von der Partnerwahl abhaengig und der Test
# maesse die Unterdrueckung statt der Reihenfolge. Ihre ANWESENHEIT deckt
# AC-S4-12.
# Issue #1728 Scheibe 1: die vier Tagesrichtungen tragen in der
# Kurzuebersicht ueberhaupt keine Zeile (narrow.py filtert sie ueber
# VISIBILITY_GATE_IDS) -- die T-/TF-Zeile zeigt die Spanne dort bereits
# unbedingt. Ihre ABWESENHEIT wird in AC-S4-12 ausdruecklich geprueft; eine
# Reihenfolge-Aussage ueber eine Zeile, die es nicht gibt, waere sinnlos.
_S7_TELEGRAM_ORDER_METRIKEN = [
    m for m in _ALL_METRIC_IDS
    if m not in ("temperature_night", "wind_chill_night")
    and m not in _TELEGRAM_NO_OVERVIEW_ROW
]


def _s7_telegram_layout_dc(reihenfolge: list[str]) -> UnifiedWeatherDisplayConfig:
    return UnifiedWeatherDisplayConfig(
        trip_id="s7-telegram",
        metrics=[
            MetricConfig(metric_id=m, enabled=True, order=i)
            for i, m in enumerate(sorted(reihenfolge))
        ],
        per_channel_layouts={
            "telegram": [
                MetricConfig(metric_id=m, enabled=True, bucket="primary", order=i)
                for i, m in enumerate(reihenfolge)
            ],
        },
    )


def _s7_kurzuebersicht_index(zeilen: list[str], metric_id: str) -> int:
    """Position der Kurzuebersicht-Zeile einer Groesse. Gesucht wird ueber
    ``compact_label`` + Leerzeichen -- ohne das Leerzeichen faende "T" auch
    "TN"/"TH" (Praefix-Kollision, dieselbe Falle wie im SMS-Pfad)."""
    label = get_metric(metric_id).compact_label
    treffer = [i for i, z in enumerate(zeilen) if z.startswith(label + " ")]
    assert len(treffer) == 1, (
        f"AC-S7-7: {metric_id!r} (Kuerzel {label!r}) kommt {len(treffer)}-mal "
        f"in der Kurzuebersicht vor: {zeilen!r}"
    )
    return treffer[0]


@pytest.mark.parametrize("metric_id", _S7_TELEGRAM_ORDER_METRIKEN)
def test_ac_s7_7_telegram_kurzuebersicht_folgt_der_reihenfolge(metric_id):
    """AC-S7-7: die Telegram-Kurzuebersicht-Bubble folgt der im
    Telegram-Kanal eingestellten Reihenfolge -- paarweise ueber alle
    waehlbaren Groessen."""
    partner = "temperature" if metric_id == "wind" else "wind"
    zeilen_a = _s4_kurzuebersicht(_s7_telegram_layout_dc([metric_id, partner]))
    zeilen_b = _s4_kurzuebersicht(_s7_telegram_layout_dc([partner, metric_id]))
    assert _s7_kurzuebersicht_index(zeilen_a, metric_id) < _s7_kurzuebersicht_index(
        zeilen_a, partner
    ), f"AC-S7-7: [{metric_id}, {partner}] ergibt {zeilen_a}"
    assert _s7_kurzuebersicht_index(zeilen_b, partner) < _s7_kurzuebersicht_index(
        zeilen_b, metric_id
    ), f"AC-S7-7: [{partner}, {metric_id}] ergibt {zeilen_b}"


def test_ac_s7_7b_zwei_reihenfolge_quellen_in_einem_renderer():
    """AC-S7-7 (benanntes Driftrisiko, Charakterisierung): ``render_telegram_
    bubbles()`` bezieht die Reihenfolge der KURZUEBERSICHT aus
    ``dc.get_enabled_metric_ids()`` -- der reinen LISTENPOSITION -- und die
    der TABELLEN-Bubbles zwei Zeilen weiter aus ``render_for_channel()``,
    das nach dem ``order``-FELD sortiert. Im Versandpfad fallen beide
    zusammen, weil ``get_metrics_for_channel()`` die Liste vorher nach
    ``order`` sortiert (models.py:751-770); widersprechen sich die beiden
    Angaben, laufen sie auseinander. Solange beide Quellen bestehen, soll das
    benannt sein statt unbemerkt."""
    from output.renderers.narrow import render_telegram_bubbles

    dc = UnifiedWeatherDisplayConfig(
        trip_id="s7-drift",
        metrics=[
            MetricConfig(metric_id="wind", enabled=True, bucket="primary", order=1),
            MetricConfig(metric_id="temperature", enabled=True, bucket="primary", order=0),
        ],
    )
    assert dc.get_enabled_metric_ids() == ["wind", "temperature"], (
        "AC-S7-7b: Quelle 1 (Listenposition) hat sich geaendert"
    )
    assert render_for_channel("telegram", dc, "evening").table_columns == [
        "temperature", "wind",
    ], "AC-S7-7b: Quelle 2 (order-Feld) hat sich geaendert"

    bubbles = render_telegram_bubbles(
        segments=[_matrix_segment()], seg_tables=[[]], dc=dc,
        report_type="evening", tz=F.TZ, trip_name="Issue1703S7",
        night_weather=F.night_weather(),
    )
    zeilen = [
        z.strip() for z in bubbles[1].text.splitlines()
        if z.strip() and z.strip() != "Kurzübersicht"
    ]
    assert _s7_kurzuebersicht_index(zeilen, "wind") < _s7_kurzuebersicht_index(
        zeilen, "temperature"
    ), (
        "AC-S7-7b: die Kurzuebersicht folgt nicht mehr der Listenposition, "
        f"sondern offenbar dem order-Feld: {zeilen!r}"
    )


# --- AC-S7-8: Compare-Telegram und -SMS unter Kappung ---------------------

@pytest.mark.parametrize("metric_id", _S7_SOLL)
def test_ac_s7_8a_compare_telegram_folgt_der_reihenfolge(metric_id):
    """AC-S7-8 (Telegram): die Zellfolge je Ort folgt der eingestellten
    Reihenfolge. Paarweise mit ZWEI Groessen geprueft -- mit der vollen
    Auswahl maesse der Test die 7-Spalten-Kappung statt der Reihenfolge
    (``CHANNEL_LIMITS["telegram"]["max_table_cols"]``)."""
    partner = partner_von(metric_id)
    label_m = _PLAIN_ROWS_BY_ID[metric_id][1]
    label_p = _PLAIN_ROWS_BY_ID[partner][1]
    assert label_m != label_p, (
        f"Vakuum: {metric_id!r} und {partner!r} teilen sich das Telegram-Label"
    )
    zellen_a = telegram_zellen(
        render_compare_telegram(_s7_result(), enabled_metrics=[metric_id, partner])
    )
    zellen_b = telegram_zellen(
        render_compare_telegram(_s7_result(), enabled_metrics=[partner, metric_id])
    )
    assert [z.startswith(label_m) for z in zellen_a] == [True, False], (
        f"AC-S7-8: [{metric_id}, {partner}] ergibt {zellen_a}"
    )
    assert [z.startswith(label_p) for z in zellen_b] == [True, False], (
        f"AC-S7-8: [{partner}, {metric_id}] ergibt {zellen_b}"
    )


@pytest.mark.parametrize("metric_id", _S7_SOLL)
def test_ac_s7_8b_compare_sms_folgt_der_reihenfolge(metric_id):
    """AC-S7-8 (SMS): die Kuerzel-Token-Folge je Ort folgt der eingestellten
    Reihenfolge. Ebenfalls paarweise -- die SMS kappt am Zeichenbudget
    (``CHANNEL_LIMITS["sms"]["max_chars"]``, gemessen 153)."""
    partner = partner_von(metric_id)
    ort = _s7_result().locations[0]
    kuerzel_m, kuerzel_p = sms_kuerzel(ort, metric_id), sms_kuerzel(ort, partner)
    assert kuerzel_m != kuerzel_p, (
        f"Vakuum: {metric_id!r} und {partner!r} teilen sich das SMS-Kuerzel "
        f"{kuerzel_m!r}"
    )
    sms_a = render_compare_sms(_s7_result(), enabled_metrics=[metric_id, partner])
    sms_b = render_compare_sms(_s7_result(), enabled_metrics=[partner, metric_id])
    ia_m, ia_p = sms_index(sms_a, kuerzel_m), sms_index(sms_a, kuerzel_p)
    ib_m, ib_p = sms_index(sms_b, kuerzel_m), sms_index(sms_b, kuerzel_p)
    assert None not in (ia_m, ia_p, ib_m, ib_p), (
        f"AC-S7-8: nicht beide Kuerzel in beiden SMS auffindbar "
        f"({kuerzel_m}/{kuerzel_p}):\nA: {sms_a!r}\nB: {sms_b!r}"
    )
    assert ia_m < ia_p, f"AC-S7-8: [{metric_id}, {partner}] ergibt {sms_a!r}"
    assert ib_p < ib_m, f"AC-S7-8: [{partner}, {metric_id}] ergibt {sms_b!r}"


def test_ac_s7_8c_kappung_folgt_der_reihenfolge_und_wird_zum_inhaltsfehler():
    """AC-S7-8 (Kappungs-Anteil): oberhalb der Kappungsgrenze entscheidet die
    Reihenfolge, WELCHE Groesse ueberhaupt erhalten bleibt -- in der SMS ist
    ein Reihenfolgefehler damit ein INHALTSfehler, kein Schoenheitsfehler."""
    metrik_slots = CHANNEL_LIMITS["telegram"]["max_table_cols"] - 1  # Slot 0 = Zeit
    assert len(_S7_SOLL) > 2 * metrik_slots, (
        f"Vakuum: {len(_S7_SOLL)} Groessen reichen nicht, um zwei disjunkte "
        f"Kappungsfenster von je {metrik_slots} zu belegen"
    )
    vorwaerts = telegram_zellen(
        render_compare_telegram(_s7_result(), enabled_metrics=list(_S7_SOLL))
    )
    rueckwaerts = telegram_zellen(
        render_compare_telegram(_s7_result(), enabled_metrics=list(reversed(_S7_SOLL)))
    )
    assert len(vorwaerts) == len(rueckwaerts) == metrik_slots, (
        f"AC-S7-8c: Telegram zeigt {len(vorwaerts)}/{len(rueckwaerts)} Zellen "
        f"statt der erwarteten {metrik_slots}"
    )
    assert set(vorwaerts).isdisjoint(rueckwaerts), (
        "AC-S7-8c: die ersten und die letzten sieben Groessen der Auswahl "
        f"ueberschneiden sich: {sorted(set(vorwaerts) & set(rueckwaerts))}"
    )

    ort = _s7_result().locations[0]
    letzte = _S7_SOLL[-1]
    kuerzel_letzte = sms_kuerzel(ort, letzte)
    sms_vorwaerts = render_compare_sms(_s7_result(), enabled_metrics=list(_S7_SOLL))
    sms_rueckwaerts = render_compare_sms(
        _s7_result(), enabled_metrics=list(reversed(_S7_SOLL))
    )
    max_chars = CHANNEL_LIMITS["sms"]["max_chars"]
    for text in (sms_vorwaerts, sms_rueckwaerts):
        assert len(text) <= max_chars, f"SMS zu lang ({len(text)}): {text!r}"
    assert sms_index(sms_vorwaerts, kuerzel_letzte) is None, (
        f"AC-S7-8c: {letzte!r} steht am Listenende und muesste vom "
        f"Zeichenbudget verdraengt sein: {sms_vorwaerts!r}"
    )
    kuerzel_vorletzte = sms_kuerzel(ort, _S7_SOLL[-2])
    position_letzte = sms_index(sms_rueckwaerts, kuerzel_letzte)
    position_vorletzte = sms_index(sms_rueckwaerts, kuerzel_vorletzte)
    assert position_letzte is not None and position_vorletzte is not None, (
        f"AC-S7-8c: dieselbe Groesse muesste an erster Listenposition "
        f"erscheinen: {sms_rueckwaerts!r}"
    )
    assert position_letzte < position_vorletzte, (
        f"AC-S7-8c: {letzte!r} steht in der umgedrehten Liste vor "
        f"{_S7_SOLL[-2]!r}, erscheint in der SMS aber dahinter: "
        f"{sms_rueckwaerts!r}"
    )


# --- AC-S7-9: Kompakt-Zusammenfassung -- benannte Ausnahme ----------------

def test_ac_s7_9_kompakt_zusammenfassung_hat_keine_reihenfolge_achse():
    """AC-S7-9 (benannte, begruendete Ausnahme -- KEIN Fix): der Fliesstext
    ``format_stage_summary()`` folgt einer festen Positivliste und kennt
    keine nutzergesteuerte Reihenfolge. Dieselben zwei Groessen in zwei
    Reihenfolgen ergeben denselben Satz. Anschluss an AC-S4-6/AC-S4-7
    (feste Positivliste als akzeptierter Dauerzustand, PO-Entscheid
    2026-08-12) -- hier ausdruecklich festgehalten statt stillschweigend
    ausgelassen."""
    basis = _s4_baseline_summary()
    satz_a = _s4_compact_summary_text(_two_metric_dc("wind", "temperature"))
    satz_b = _s4_compact_summary_text(_two_metric_dc("temperature", "wind"))
    assert satz_a != basis, (
        "Vakuum: die beiden Groessen veraendern den Fliesstext gar nicht -- "
        f"dann sagt der Reihenfolge-Vergleich unten nichts. Basis: {basis!r}"
    )
    assert satz_a == satz_b, (
        "AC-S7-9: der Fliesstext hat entgegen der Messung eine "
        f"Reihenfolge-Achse bekommen:\nA: {satz_a!r}\nB: {satz_b!r}"
    )
