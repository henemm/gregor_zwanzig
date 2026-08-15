"""Tages-Tief/Tages-Hoch sind eigene waehlbare Groessen (Issue #1728 S1).

Spec: ``docs/specs/modules/feat_1728_s1_temp_aufloesung.md`` — AC-1 bis AC-7,
AC-14, AC-15, AC-16. Kontext/Messlage: ``docs/context/feat-1728-temp-aufloesung.md``.

🔴 Pruefort = Wirkort. Alle Kurzform- und Kachel-Nachweise laufen ueber
``TripReportFormatter().format_email()`` (``.sms_text`` / ``.email_html`` /
``.email_plain``), NIE ueber ``build_metrics_summary_pills()`` direkt — die vier
Bestands-Pillen-Tests rufen genau diesen Helfer direkt auf und durchlaufen
``render_html``/``render_plain``/``render_compact`` nie; eine Aenderung an den
Pillen kann dort gruen durchlaufen und trotzdem wirkungslos sein.

Kern-Schicht, deterministisch: kein ``Mock()``, kein ``patch()``, kein Netz,
kein Transport. Wertelandschaft aus ``_min_temp_felt_fixtures`` (sechs
unterscheidbare Temperaturen, damit jede Verwechslung sichtbar wird).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.models import (  # noqa: E402
    MetricConfig, TripReportConfig, UnifiedWeatherDisplayConfig,
)
from output.renderers.trip_report import TripReportFormatter  # noqa: E402

from tests.tdd import _min_temp_felt_fixtures as F  # noqa: E402

TEMP_LOW = "temperature_day_low"
TEMP_HIGH = "temperature_day_high"
FELT_LOW = "wind_chill_day_low"
FELT_HIGH = "wind_chill_day_high"
NEW_IDS = (TEMP_LOW, TEMP_HIGH, FELT_LOW, FELT_HIGH)

# Die Metriken-Ueberblick-Kachel der Temperatur in ihren zwei moeglichen
# Gestalten. Beide aus den Fixture-Konstanten gebaut, damit ein geaenderter
# Fixture-Wert nicht still an einem Literal vorbeilaeuft.
SPAN_RICH = f"{int(F.HIKE_MIN_C)}–{int(F.HIKE_MAX_C)}°C · Max {F.WARM_HOUR:02d}:00"
ONLY_MAX_RICH = f"max {int(F.HIKE_MAX_C)}°C · {F.WARM_HOUR:02d}:00"
SPAN_ASCII = f"{int(F.HIKE_MIN_C)}-{int(F.HIKE_MAX_C)}C - Max {F.WARM_HOUR:02d}:00"
ONLY_MAX_ASCII = f"max {int(F.HIKE_MAX_C)}C - {F.WARM_HOUR:02d}:00"


def _dc(*specs: tuple[str, bool]) -> UnifiedWeatherDisplayConfig:
    """Displaykonfiguration aus (metric_id, enabled)-Paaren."""
    metrics = [
        MetricConfig(metric_id=mid, enabled=on)
        for mid, on in specs
    ]
    return UnifiedWeatherDisplayConfig(trip_id="i1728-s1", metrics=metrics)


def _report(dc: UnifiedWeatherDisplayConfig, *, email_format: str = "full"):
    """Echtes Briefing-Rendering — der Weg, den der Versand nimmt."""
    return TripReportFormatter().format_email(
        [F.segment()], trip_name="I1728", report_type="evening",
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
        report_config=TripReportConfig(email_format=email_format),
    )


# ---------------------------------------------------------------------------
# AC-1 / AC-2 — die vier Tagesrichtungen gaten die SMS-Token einzeln
# ---------------------------------------------------------------------------

class TestSmsTokensFollowDayDirectionMetrics:
    """Die Sichtbarkeit von K/D haengt an ``temperature_day_low``/``_high``,
    nicht mehr an ``MetricConfig.aggregations`` der Elterngroesse."""

    def test_only_day_high_selected_shows_d_without_k(self):
        """AC-1: ``temperature_day_high`` AN, ``temperature_day_low`` AUS ->
        die SMS traegt D und kein K. Die Elterngroesse behaelt bewusst ihre
        Vorgabe-Auswertung (min+max): waere sie auf ["max"] gesetzt, erledigte
        das alte Aggregations-Gate die Arbeit und der Test bewiese nichts
        ueber die neue Steuerung."""
        dc = _dc(("temperature", True), (TEMP_LOW, False), (TEMP_HIGH, True),
                 ("temperature_night", True), ("precipitation", True))
        sms = _report(dc).sms_text

        assert F.sms_token_value(sms, "D") == str(int(F.HIKE_MAX_C)), (
            f"D fehlt oder traegt den falschen Wert, obwohl "
            f"{TEMP_HIGH!r} gewaehlt ist.\nSMS: {sms}"
        )
        # Uebernommen aus dem geloeschten test_sms_temp_aggregation_gate.py:
        # die Abwahl EINER Tagesrichtung darf die eigene Nachtgroesse
        # (#1484) nicht mitnehmen.
        assert F.sms_token_value(sms, "N") == str(int(F.NIGHT_MIN_C)), (
            f"N (eigene Groesse, #1484) ist von der Abwahl einer "
            f"Tagesrichtung mitgenommen worden.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "K") is None, (
            f"K erscheint, obwohl {TEMP_LOW!r} abgewaehlt ist — die "
            f"SMS-Kette gated die Tages-Token noch ueber "
            f"MetricConfig.aggregations der Elterngroesse statt ueber die "
            f"eigene Groesse.\nSMS: {sms}"
        )

    def test_only_day_low_selected_shows_k_without_d(self):
        """AC-2: gegenlaeufige Auswahl — K ja, D nein."""
        dc = _dc(("temperature", True), (TEMP_LOW, True), (TEMP_HIGH, False),
                 ("precipitation", True))
        sms = _report(dc).sms_text

        assert F.sms_token_value(sms, "K") == str(int(F.HIKE_MIN_C)), (
            f"K fehlt oder traegt den falschen Wert, obwohl {TEMP_LOW!r} "
            f"gewaehlt ist.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "D") is None, (
            f"D erscheint, obwohl {TEMP_HIGH!r} abgewaehlt ist.\nSMS: {sms}"
        )


# ---------------------------------------------------------------------------
# AC-3 / AC-4 — E3: 'WC' bleibt an der Elterngroesse "wind_chill"
# ---------------------------------------------------------------------------

class TestWindChillDayDirectionsLeaveWcAlone:

    def test_felt_day_high_off_keeps_fk_and_wc(self):
        """AC-3: ``wind_chill_day_low`` AN, ``wind_chill_day_high`` AUS ->
        FK und WC stehen, FD nicht. Die Abwahl EINER Tagesrichtung darf die
        Wintersport-Tageskennzahl nicht mitnehmen (Regression #1450)."""
        dc = _dc(("wind_chill", True), (FELT_LOW, True), (FELT_HIGH, False),
                 ("wind_chill_night", True), ("precipitation", True))
        sms = _report(dc).sms_text

        assert F.sms_token_value(sms, "FK") == str(int(F.FELT_HIKE_MIN_C)), (
            f"FK fehlt, obwohl {FELT_LOW!r} gewaehlt ist.\nSMS: {sms}"
        )
        # Uebernommen aus dem geloeschten test_sms_temp_aggregation_gate.py:
        # FN (#1660 A) bleibt von der Abwahl einer Tagesrichtung unberuehrt.
        assert F.sms_token_value(sms, "FN") == str(int(F.FELT_NIGHT_MIN_C)), (
            f"FN (eigene Groesse, #1660 A) ist von der Abwahl einer "
            f"Tagesrichtung mitgenommen worden.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "FD") is None, (
            f"FD erscheint, obwohl {FELT_HIGH!r} abgewaehlt ist.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "WC") is not None, (
            f"WC ist verschwunden, obwohl „Gefuehlte Temperatur“ selbst "
            f"aktiv ist — E3 verletzt (WC haengt an der Elterngroesse, "
            f"nicht an einer Tagesrichtung).\nSMS: {sms}"
        )

    def test_parent_off_removes_wc_but_day_direction_stays(self):
        """AC-4 (korrigierte Fassung, PO 2026-08-15): Elterngroesse AUS,
        ``wind_chill_day_high`` ausdruecklich AN -> WC fehlt, FD erscheint
        dennoch. Gegenstueck zu AC-3, das denselben Sachverhalt (E3) aus der
        anderen Richtung misst: WC haengt an der Elterngroesse, die
        Tagesrichtungen haengen an sich selbst.

        PO 2026-08-15: Tagesrichtungen sind unabhaengig von der Elterngroesse
        (DEC-3/DEC-4, generische Gate-Schleife ueber
        ``SMS_MULTI_SYMBOLS_BY_METRIC``) — dasselbe Verhalten, das
        ``temperature_night`` seit #1484 zeigt. WC bleibt unveraendert an
        ``wind_chill`` gebunden (haelt Regression #1450).
        """
        dc = _dc(("wind_chill", False), (FELT_HIGH, True),
                 ("temperature", True), ("precipitation", True))
        sms = _report(dc).sms_text

        assert F.sms_token_value(sms, "FD") == str(int(F.FELT_HIKE_MAX_C)), (
            f"FD fehlt oder traegt den falschen Wert, obwohl {FELT_HIGH!r} "
            f"ausdruecklich gewaehlt ist — eine eigenstaendige Groesse darf "
            f"nicht an der Elterngroesse haengen (PO 2026-08-15).\n"
            f"SMS: {sms}"
        )
        assert F.sms_token_value(sms, "WC") is None, (
            f"WC erscheint trotz abgewaehlter Elterngroesse — genau die "
            f"Regression, die #1450 behoben hat.\nSMS: {sms}"
        )


# ---------------------------------------------------------------------------
# AC-5 / AC-6 / AC-7 — DEC-5: die drei Pillen-Wirkorte zeigen die Spanne
# unbedingt, unabhaengig von jeder gespeicherten Auswertungswahl
# ---------------------------------------------------------------------------

def _dc_stored_max_only() -> UnifiedWeatherDisplayConfig:
    """Bestandslage mit abgewaehltem ``temperature_day_low``: die Kachel muss
    die Spanne trotzdem zeigen."""
    return _dc(
        ("temperature", True), (TEMP_LOW, False), (TEMP_HIGH, True),
        ("precipitation", True),
    )


class TestOverviewPillAlwaysShowsSpan:

    def test_html_pill_shows_full_span(self):
        """AC-5: HTML-Kachel zeigt die Min–Max-Spanne, nicht nur den
        Hoechstwert. Gemessen an ``format_email().email_html``."""
        html = _report(_dc_stored_max_only()).email_html

        assert SPAN_RICH in html, (
            f"Die HTML-Kachel zeigt {SPAN_RICH!r} nicht — der Pillen-Wirkort "
            f"liest offenbar weiterhin MetricConfig.aggregations "
            f"(email/html.py:1443-1454).\nGefunden: "
            f"{ONLY_MAX_RICH in html and ONLY_MAX_RICH or '(keine Kachel)'}"
        )
        assert ONLY_MAX_RICH not in html, (
            f"Die HTML-Kachel zeigt die Einzelwert-Form {ONLY_MAX_RICH!r} — "
            f"die Kachel ist kein Bedienelement mehr (DEC-5)."
        )

    def test_plain_pill_shows_full_span(self):
        """AC-6: Klartext-Kachel, gemessen an ``.email_plain``."""
        plain = _report(_dc_stored_max_only()).email_plain

        assert SPAN_RICH in plain, (
            f"Die Klartext-Kachel zeigt {SPAN_RICH!r} nicht "
            f"(email/plain.py:202-212).\nMail:\n{plain[:800]}"
        )
        assert ONLY_MAX_RICH not in plain, (
            f"Die Klartext-Kachel zeigt die Einzelwert-Form "
            f"{ONLY_MAX_RICH!r}.\nMail:\n{plain[:800]}"
        )

    def test_compact_pill_shows_full_span(self):
        """AC-7: Kompaktform (``email_format="compact"`` -> der Text steht in
        ``.email_plain``, ``.email_html`` ist leer)."""
        report = _report(_dc_stored_max_only(), email_format="compact")
        assert report.email_html == "", (
            "Die Kompaktform darf keinen HTML-Teil erzeugen — der Test misst "
            "sonst die Vollmail."
        )
        compact = report.email_plain

        assert SPAN_ASCII in compact, (
            f"Die Kompaktform-Kachel zeigt {SPAN_ASCII!r} nicht "
            f"(email/compact.py:206-216).\nMail:\n{compact[:800]}"
        )
        assert ONLY_MAX_ASCII not in compact, (
            f"Die Kompaktform-Kachel zeigt die Einzelwert-Form "
            f"{ONLY_MAX_ASCII!r}.\nMail:\n{compact[:800]}"
        )


class TestStoredAverageHasNoOutputLeft:
    """E1 (PO 2026-08-11): „``avg`` faellt ersatzlos" — nach dieser Scheibe
    hat der Mittelwert keinen Ausgabeort mehr."""

    def test_stored_avg_only_still_renders_the_span_everywhere(self):
        """Given ein Trip mit beiden Tagesrichtungen (frueher konnte eine
        gespeicherte Auswertungswahl ``["avg"]`` die Kachel auf ``Ø 15°C``
        zwingen) / When alle drei Mailformen und die Kurznachricht erzeugt
        werden / Then erscheint nirgends ein Mittelwert; die Kachel zeigt die
        Spanne, die SMS ihre Tages-Token.

        Seit #1728 S3 ist ``MetricConfig.aggregations`` abgeschafft — der
        Mittelwert hat damit endgueltig keinen Ausgabeort mehr."""
        dc = _dc(("temperature", True), (TEMP_LOW, True), (TEMP_HIGH, True),
                 ("precipitation", True))
        voll = _report(dc)
        kompakt = _report(dc, email_format="compact")

        for name, text in (("HTML", voll.email_html),
                           ("Klartext", voll.email_plain),
                           ("Kompaktform", kompakt.email_plain)):
            assert "Ø" not in text, (
                f"Die {name}-Ausgabe zeigt einen Mittelwert (Zeichen 'Ø'), "
                f"obwohl 'avg' ersatzlos entfallen ist (E1)."
            )
        assert SPAN_RICH in voll.email_html and SPAN_RICH in voll.email_plain, (
            f"Die Vollmail zeigt trotz gespeichertem ['avg'] nicht die Spanne "
            f"{SPAN_RICH!r}."
        )
        assert SPAN_ASCII in kompakt.email_plain, (
            f"Die Kompaktform zeigt trotz gespeichertem ['avg'] nicht "
            f"{SPAN_ASCII!r}."
        )
        sms = voll.sms_text
        assert F.sms_token_value(sms, "D") == str(int(F.HIKE_MAX_C)), (
            f"Die SMS verliert ihr Tages-Hoch, obwohl beide Tagesrichtungen "
            f"gewaehlt sind — 'avg' darf nichts mehr gaten.\nSMS: {sms}"
        )


# ---------------------------------------------------------------------------
# AC-14 — DEC-8: sms_code bleibt global eindeutig ("TD", nicht "D")
# ---------------------------------------------------------------------------

class TestCatalogSmsCodesStayUnique:

    def test_new_metrics_carry_collision_free_sms_codes(self):
        """AC-14: die vier neuen Eintraege existieren, liegen in der Kategorie
        „temperature" und brechen die Eindeutigkeits-Ratsche nicht.
        ``temperature_day_high`` traegt "TD" — "D" ist seit #914 von
        ``temperature`` selbst belegt."""
        from app.metric_catalog import _METRICS, _METRICS_BY_ID

        missing = [mid for mid in NEW_IDS if mid not in _METRICS_BY_ID]
        assert not missing, (
            f"Katalog-Eintraege fehlen: {missing} — der Katalog "
            f"(src/app/metric_catalog.py) ist die SSoT dieser Scheibe."
        )
        for mid in NEW_IDS:
            assert _METRICS_BY_ID[mid].category == "temperature", (
                f"{mid!r} liegt in Kategorie "
                f"{_METRICS_BY_ID[mid].category!r} statt 'temperature' — der "
                f"Editor gruppiert die Groesse sonst nicht neben ihrer Eltern."
            )
        assert _METRICS_BY_ID[TEMP_HIGH].sms_code == "TD", (
            f"{TEMP_HIGH!r} traegt sms_code "
            f"{_METRICS_BY_ID[TEMP_HIGH].sms_code!r} statt 'TD' (DEC-8) — "
            f"'D' ist bereits von 'temperature' belegt."
        )
        codes = [m.sms_code for m in _METRICS if m.sms_code]
        doppelt = sorted({c for c in codes if codes.count(c) > 1})
        assert not doppelt, (
            f"sms_code nicht mehr global eindeutig: {doppelt} — die Ratsche "
            f"tests/tdd/test_issue_917_alert_renderer.py::TestAC6CatalogSmsCodes"
            f"::test_all_sms_codes_globally_unique bricht damit ebenfalls."
        )


# ---------------------------------------------------------------------------
# AC-15 — GET /api/metrics fuehrt die vier Groessen
# ---------------------------------------------------------------------------

@pytest.fixture
def metrics_client():
    """Echter FastAPI-TestClient fuer den config-Router (kein Mock)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routers import config

    app = FastAPI()
    app.include_router(config.router, prefix="/api")
    return TestClient(app)


class TestApiMetricsExposesDayDirections:

    def test_all_four_appear_with_empty_aggregations(self, metrics_client):
        """AC-15: alle vier in Kategorie „temperature", ``aggregations`` leer
        (DEC-2: reine Sichtbarkeits-Gates ohne ``summary_fields``), die beiden
        gemessenen mit ``trip_default_enabled: true``, die beiden gefuehlten
        mit ``false`` (DEC-7)."""
        resp = metrics_client.get("/api/metrics")
        assert resp.status_code == 200, resp.text
        by_id = {m["id"]: m for m in resp.json().get("temperature", [])}

        fehlen = [mid for mid in NEW_IDS if mid not in by_id]
        assert not fehlen, (
            f"/api/metrics fuehrt {fehlen} nicht in der Kategorie "
            f"'temperature'. Vorhanden: {sorted(by_id)}"
        )
        for mid in NEW_IDS:
            assert by_id[mid]["aggregations"] == [], (
                f"{mid!r} bietet Auswertungen an "
                f"({by_id[mid]['aggregations']!r}) — DEC-2 verlangt eine "
                f"reine An/Aus-Groesse ohne summary_fields."
            )
        erwartet = {TEMP_LOW: True, TEMP_HIGH: True,
                    FELT_LOW: False, FELT_HIGH: False}
        ist = {mid: by_id[mid]["trip_default_enabled"] for mid in NEW_IDS}
        assert ist == erwartet, (
            f"trip_default_enabled falsch: {ist} statt {erwartet} — die "
            f"gemessenen Tagesrichtungen tragen trip_default_rank 8/9, die "
            f"gefuehlten keinen (DEC-7)."
        )


# ---------------------------------------------------------------------------
# AC-16 — keine Geisterspalte: die vier IDs landen in keinem Bucket
# ---------------------------------------------------------------------------

class TestDayDirectionsNeverBecomeColumns:

    def test_render_for_channel_places_none_of_them_in_a_bucket(self):
        """AC-16: ein Trip mit aktivierten Tagesrichtungen erzeugt im
        E-Mail-Layout weder Tabellenspalte noch Detail-Zeile fuer sie —
        analog dem bestehenden Filter fuer die zwei Nachtfenster-Skalare
        (``channel_layout.py:94-95``). Ohne diesen Filter entstuende eine
        Spalte, die mit der Elterngroesse kollidiert."""
        from output.renderers.channel_layout import render_for_channel

        dc = _dc(("temperature", True), (TEMP_LOW, True), (TEMP_HIGH, True),
                 ("wind_chill", True), (FELT_LOW, True), (FELT_HIGH, True),
                 ("precipitation", True))
        layout = render_for_channel("email", dc, "evening")

        in_spalten = [m for m in NEW_IDS if m in layout.table_columns]
        in_details = [m for m in NEW_IDS if m in layout.detail_metrics]
        assert not in_spalten, (
            f"Geisterspalte(n) {in_spalten} im E-Mail-Layout: "
            f"{layout.table_columns!r}"
        )
        assert not in_details, (
            f"Geister-Detailzeile(n) {in_details} im E-Mail-Layout: "
            f"{layout.detail_metrics!r}"
        )

    @pytest.mark.parametrize("channel", ["telegram", "sms"])
    def test_other_channels_place_none_of_them_in_a_bucket(self, channel):
        """Dieselbe Zusicherung fuer Telegram und SMS. „Laeuft durch dieselbe
        Funktion" ist eine Annahme, kein Nachweis: beide Kanaele haben eigene
        Spaltenlimits (``CHANNEL_LIMITS``), und SMS verschiebt seine
        ``primary``-Menge komplett in ``detail_metrics`` — ein Filter, der nur
        die Tabellenspalten saeuberte, waere hier sichtbar."""
        from output.renderers.channel_layout import render_for_channel

        dc = _dc(("temperature", True), (TEMP_LOW, True), (TEMP_HIGH, True),
                 ("wind_chill", True), (FELT_LOW, True), (FELT_HIGH, True),
                 ("precipitation", True))
        layout = render_for_channel(channel, dc, "evening")

        gefunden = [m for m in NEW_IDS
                    if m in layout.table_columns or m in layout.detail_metrics]
        assert not gefunden, (
            f"[{channel}] Sichtbarkeits-Gates {gefunden} landen in einem "
            f"Bucket. Spalten: {layout.table_columns!r}, "
            f"Detail: {layout.detail_metrics!r}"
        )


# ---------------------------------------------------------------------------
# Bestandsschutz Telegram-Kurzuebersicht (``narrow.py``, kein AC)
# ---------------------------------------------------------------------------

class TestTelegramOverviewSurvivesTheCatalogChange:

    def test_overview_keeps_span_and_grows_no_empty_gate_rows(self):
        """Die Telegram-Kurzuebersicht nennt ``temperature``/``wind_chill``
        literal (``narrow.py:499-522,749-758``) und zeigt die Spanne schon
        heute unbedingt. Belegt am echten Renderpfad
        (``format_email()`` -> ``report.telegram_bubbles``), dass die vier
        neuen Katalog-Groessen sie weder veraendern noch vier eigene
        (wertlose) Zeilen erzeugen.

        # BESTANDSSCHUTZ: prueft, dass Scheibe 1 die Telegram-Uebersicht
        # nicht kippt. Kein AC, kein RED-Nachweis.
        """
        dc = _dc(("temperature", True), (TEMP_LOW, True), (TEMP_HIGH, True),
                 ("wind_chill", True), (FELT_LOW, True), (FELT_HIGH, True),
                 ("precipitation", True))
        report = _report(dc)
        bubble = F.overview_bubble(report)

        erwartet_t = (f"T {F.HIKE_MIN_C:.1f}-{F.HIKE_MAX_C:.1f}"
                      f"@{F.WARM_HOUR}")
        erwartet_tf = (f"TF {F.FELT_HIKE_MIN_C:.1f}-{F.FELT_HIKE_MAX_C:.1f}"
                       f"@{F.WARM_HOUR}")
        assert F.overview_line(report, "T") == erwartet_t, (
            f"Die T-Zeile der Kurzuebersicht hat sich veraendert: "
            f"{F.overview_line(report, 'T')!r} statt {erwartet_t!r}.\n"
            f"Bubble:\n{bubble}"
        )
        assert F.overview_line(report, "TF") == erwartet_tf, (
            f"Die TF-Zeile hat sich veraendert: "
            f"{F.overview_line(report, 'TF')!r} statt {erwartet_tf!r}.\n"
            f"Bubble:\n{bubble}"
        )
        leere = [z for z in bubble.splitlines()
                 if z.split(" ")[0] in ("K", "D", "FK", "FD")]
        assert not leere, (
            f"Die vier Sichtbarkeits-Gates erzeugen eigene Zeilen in der "
            f"Kurzuebersicht: {leere!r} — sie tragen dort keinen Wert.\n"
            f"Bubble:\n{bubble}"
        )


# ---------------------------------------------------------------------------
# Stundenverlaufs-Ausschluss (Adversary-Befund F002)
#
# Die zwei Ausschluss-Mengen waren bis hierher nur ZUFAELLIG bewacht: fremde
# Bestandstests wurden bei ihrer Entfernung rot, weil die vier neuen Groessen
# `dp_field`/`col_label` mit ihren Eltern teilen. Ein Ausschluss, der nur
# durch Kollision auffaellt, ist unbewacht — hier steht er gezielt.
# ---------------------------------------------------------------------------

class TestDayDirectionsAreNoHourlyColumn:

    def test_trip_hourly_row_carries_no_day_direction_column(self):
        """Trip-Stundentabelle: ``dp_to_row()`` ist die EINZIGE Stelle, die
        ``NO_HOURLY_COLUMN_METRIC_IDS`` liest (``email/helpers.py:98-105``) —
        also der Wirkort, nicht nur der Ort des Codes. Die vier Groessen
        haben keinen eigenen Stundenwert; erschienen sie als Spalte, staende
        dort der Elternwert unter falschem Namen."""
        from app.metric_catalog import get_metric
        from output.renderers.email.helpers import dp_to_row

        dc = _dc(("temperature", True), (TEMP_LOW, True), (TEMP_HIGH, True),
                 ("wind_chill", True), (FELT_LOW, True), (FELT_HIGH, True),
                 ("precipitation", True))
        dp = F.segment().timeseries.data[F.WARM_HOUR]
        zeile = dp_to_row(dp, dc, tz=F.TZ)

        for mid in NEW_IDS:
            col_key = get_metric(mid).col_key
            assert col_key not in zeile, (
                f"{mid!r} erzeugt die Stundenspalte {col_key!r} "
                f"(Wert {zeile.get(col_key)!r}) — die Groesse hat keinen "
                f"eigenen Stundenwert.\nZeile: {sorted(zeile)}"
            )
        # Gegenprobe: die Elterngroessen tragen ihre Spalte weiter, sonst
        # waere die Abwesenheit oben aus dem falschen Grund erfuellt.
        for eltern in ("temperature", "wind_chill"):
            assert get_metric(eltern).col_key in zeile, (
                f"{eltern!r} hat seine Stundenspalte verloren — der "
                f"Ausschluss trifft die falsche Groesse.\n"
                f"Zeile: {sorted(zeile)}"
            )

    def test_compare_hourly_never_offers_or_accepts_them(self):
        """Ortsvergleich-Stundenverlauf: die Bedienflaeche bietet die vier
        nicht an (``hourly_selectable_metric_ids()``), und eine gespeicherte
        Auswahl, die sie doch enthaelt, verwirft sie beim Laden
        (``normalize_hourly_metrics()``). Beides sind echte Aufrufer von
        ``HOURLY_EXCLUDED_METRIC_IDS``."""
        from output.renderers.compare_hourly_metric_ids import (
            HOURLY_EXCLUSION_REASON, hourly_selectable_metric_ids,
            normalize_hourly_metrics,
        )

        angeboten = hourly_selectable_metric_ids()
        drin = [m for m in NEW_IDS if m in angeboten]
        assert not drin, (
            f"Der Stundenverlauf bietet {drin} zur Auswahl an — sie haben "
            f"dort keinen Wert."
        )
        assert "temperature" in angeboten and "wind_chill" in angeboten, (
            "Die Elterngroessen fehlen im Stundenverlauf — der Ausschluss "
            "greift zu weit."
        )

        gespeichert = ["temperature", *NEW_IDS, "wind"]
        assert normalize_hourly_metrics(gespeichert) == ["temperature", "wind"], (
            f"Eine gespeicherte Stundenauswahl mit den vier Tagesrichtungen "
            f"wird nicht bereinigt: "
            f"{normalize_hourly_metrics(gespeichert)!r}"
        )
        ohne_grund = [m for m in NEW_IDS if not HOURLY_EXCLUSION_REASON.get(m)]
        assert not ohne_grund, (
            f"{ohne_grund} sind ausgeschlossen, ohne dass die Bedienflaeche "
            f"einen Grund nennen kann."
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
