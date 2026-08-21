"""
TDD tests for Issue #1653 — Mehrtages-Ausblick: Gewitter-Zelle trennt Tag
und Nacht.

RED phase: All tests fail until implementation is complete.

SPEC: docs/specs/modules/fix_1653_ausblick_tag_nacht_trennung.md AC-1..AC-8
IMPORTANT: NO mocks, NO patch, NO MagicMock. Real function calls only.

Die drei gemessenen Fehler (Issue #1653):
  1. Wort (Gehzeit-geklemmt) und Uhrzeit (ungefiltert 24h) stammen aus
     verschiedenen Zeitfenstern.
  2. Nur der 24h-Peak wird gezeigt — Tag oder Nacht verschwindet.
  3. Rohe Programmnamen MED/HIGH in der Klartext-Mail — AUSSER SCOPE (#1654).

Fall-Bezeichnungen wie in der Issue-Messtabelle:
  Fall A: kein Tagesgewitter, Nacht hoch 00:00
  Fall B: Tag mittel 14:00, Nacht hoch 00:00 (beide Level unterschiedlich)
  Fall C: Tag hoch 14:00, Nacht mittel 22:00
"""
from __future__ import annotations

from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

def _hv(hour: int, value: float):
    """Shorthand for HourlyValue. LOW=1, MED=2, HIGH=3 (thunder_label_value())."""
    from src.output.tokens.dto import HourlyValue
    return HourlyValue(hour=hour, value=value)


def _stage(
    weekday="Di", name="Test-Etappe", temp_lo=12, temp_hi=15,
    precip_mm=0.0, wind_dir="W", wind_kmh=10, thunder="NONE", note=None,
    hourly_thunder=None, day_window_start_hour=None, day_window_end_hour=None,
):
    """Ausblick-Zeile wie build_outlook_row() sie liefert (Ausschnitt)."""
    row = dict(
        weekday=weekday, name=name, temp_lo=temp_lo, temp_hi=temp_hi,
        precip_mm=precip_mm, wind_dir=wind_dir, wind_kmh=wind_kmh,
        thunder=thunder, note=note,
        hourly_precip=(), hourly_wind=(), hourly_gust=(),
        hourly_thunder=hourly_thunder or (),
    )
    if day_window_start_hour is not None:
        row["day_window_start_hour"] = day_window_start_hour
    if day_window_end_hour is not None:
        row["day_window_end_hour"] = day_window_end_hour
    return row


# Fall B: Tag "mittel" 14 Uhr (im Default-Fenster 04-19), Nacht "hoch" 0 Uhr
# (ausserhalb).
_FALL_B_HOURLY = (_hv(14, 2.0), _hv(0, 3.0))
# Fall A: kein Tagesgewitter, Nacht "hoch" 0 Uhr.
_FALL_A_HOURLY = (_hv(0, 3.0),)
# Fall C: Tag "hoch" 14 Uhr, Nacht "mittel" 22 Uhr.
_FALL_C_HOURLY = (_hv(14, 3.0), _hv(22, 2.0))


def _render_html(trend):
    from tests.unit.test_renderers_email import _common_kwargs, _make_token_line
    from src.output.renderers.email.html import render_html

    kw = _common_kwargs()
    tl = _make_token_line()
    return render_html(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name=tl.trip_name or "Test-Trip", report_type="evening",
        dc=kw["display_config"], night_rows=[], thunder_forecast=None,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=trend, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None, stability_result=None,
        sent_at=None,
    )


def _render_telegram(trend):
    from tests.unit.test_renderers_email import _common_kwargs
    from src.output.renderers.narrow import render_telegram_bubbles

    kw = _common_kwargs()
    bubbles = render_telegram_bubbles(
        segments=kw["segments"], seg_tables=kw["seg_tables"], dc=kw["display_config"],
        report_type="evening", tz=ZoneInfo("Europe/Berlin"), trip_name="Test-Trip",
        friendly_keys=kw["friendly_keys"], multi_day_trend=trend,
    )
    return "\n".join(b.text for b in bubbles)


# ---------------------------------------------------------------------------
# AC-1 + AC-2 (Token-Ebene): format_trend_tokens liefert Tag/Nacht getrennt
# ---------------------------------------------------------------------------

class TestFormatTrendTokensDayNightSplit:
    """format_trend_tokens() muss thunder_day_token/thunder_night_token
    additiv liefern, jeweils ausschliesslich aus dem eigenen Zeitfenster."""

    def test_day_night_token_keys_exist(self):
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _stage(hourly_thunder=_FALL_B_HOURLY, thunder="MED")
        tok = format_trend_tokens(stage)
        assert "thunder_day_token" in tok, f"Keys: {sorted(tok.keys())}"
        assert "thunder_night_token" in tok, f"Keys: {sorted(tok.keys())}"

    def test_day_token_ignores_night_hour_fall_b(self):
        """Fehler 1: die Tages-Uhrzeit darf NICHT aus der Nachtstunde stammen,
        obwohl die Nacht (hoch, 24h-Peak) staerker ist als der Tag (mittel)."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _stage(hourly_thunder=_FALL_B_HOURLY, thunder="MED")
        tok = format_trend_tokens(stage)
        dt = tok["thunder_day_token"]
        assert "@14" in dt, f"Tagestoken sollte @14 zeigen: {dt!r}"
        assert "@0" not in dt, f"Tagestoken zeigt faelschlich Nachtstunde: {dt!r}"
        assert "mittel" in dt, f"Tagestoken sollte 'mittel' zeigen: {dt!r}"

    def test_night_token_ignores_day_hour_fall_b(self):
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _stage(hourly_thunder=_FALL_B_HOURLY, thunder="MED")
        tok = format_trend_tokens(stage)
        nt = tok["thunder_night_token"]
        assert "@0" in nt, f"Nachttoken sollte @0 zeigen: {nt!r}"
        assert "@14" not in nt, f"Nachttoken zeigt faelschlich Tagesstunde: {nt!r}"
        assert "hoch" in nt, f"Nachttoken sollte 'hoch' zeigen: {nt!r}"

    def test_night_token_present_without_day_fall_a(self):
        """Fall A: kein Tagesgewitter, aber Nachtgewitter -- Nachttoken muss
        trotzdem gefuellt sein (nicht nur wenn auch Tag vorliegt)."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _stage(hourly_thunder=_FALL_A_HOURLY, thunder="NONE")
        tok = format_trend_tokens(stage)
        assert tok["thunder_day_token"] == "-"
        assert "@0" in tok["thunder_night_token"]
        assert "hoch" in tok["thunder_night_token"]

    def test_day_token_present_fall_c_stronger_day(self):
        """Fall C: Tag staerker als Nacht -- beide Token muessen trotzdem
        unabhaengig gefuellt sein (nicht nur der Peak)."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _stage(hourly_thunder=_FALL_C_HOURLY, thunder="HIGH")
        tok = format_trend_tokens(stage)
        assert "@14" in tok["thunder_day_token"]
        assert "hoch" in tok["thunder_day_token"]
        assert "@22" in tok["thunder_night_token"]
        assert "mittel" in tok["thunder_night_token"]

    def test_no_thunder_both_tokens_dash(self):
        """AC-5 Regressionsschutz: kein Gewitter -- beide Token bleiben '-'."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _stage(hourly_thunder=(), thunder="NONE")
        tok = format_trend_tokens(stage)
        assert tok["thunder_day_token"] == "-"
        assert tok["thunder_night_token"] == "-"

    def test_legacy_thunder_token_unchanged(self):
        """AC-7 (Kontrollprobe): das bestehende thunder_token (24h-Peak) muss
        byte-identisch weiter existieren -- bestehende Tests
        (test_issue_640_trend_threshold_times.py) pruefen es weiterhin."""
        from src.output.renderers.email.helpers import format_trend_tokens
        stage = _stage(hourly_thunder=_FALL_B_HOURLY, thunder="MED")
        tok = format_trend_tokens(stage)
        assert tok["thunder_token"] == "hoch@0", f"Got: {tok['thunder_token']!r}"

    def test_custom_day_window_respected(self):
        """Ein individuelles Tagesfenster (statt Default 4-19) muss den Split
        beeinflussen -- additive Stage-Keys day_window_start_hour/end_hour."""
        from src.output.renderers.email.helpers import format_trend_tokens
        # Fenster 20-23: Stunde 22 liegt jetzt im Tag, Stunde 14 in der Nacht.
        stage = _stage(
            hourly_thunder=_FALL_C_HOURLY, thunder="HIGH",
            day_window_start_hour=20, day_window_end_hour=23,
        )
        tok = format_trend_tokens(stage)
        assert "@22" in tok["thunder_day_token"], f"Got: {tok['thunder_day_token']!r}"
        assert "@14" in tok["thunder_night_token"], f"Got: {tok['thunder_night_token']!r}"


# ---------------------------------------------------------------------------
# AC-1, AC-2, AC-4, AC-5: HTML-Ausblick-Zelle (render_outlook_table)
# ---------------------------------------------------------------------------

class TestHtmlCellDayNight:
    def test_cell_shows_only_the_day_part_fall_b(self):
        """⚠️ AC-2 UMGEDREHT (#1848 A3): frueher "Tag UND Nacht gleichzeitig
        sichtbar, nicht nur der Peak". Die 3-Tages-Vorschau zeigt seither
        ausschliesslich das TAGESFENSTER (s. Modul-Kopf). Was bleibt: der
        Tagesteil verschwindet NICHT hinter dem staerkeren Nachtwert -- genau
        der Fehler 2, den #1653 behoben hat."""
        from src.output.renderers.email.outlook import render_outlook_table
        html = render_outlook_table([_stage(hourly_thunder=_FALL_B_HOURLY, thunder="MED")])
        assert "mittel" in html and "@14" in html, (
            "Der Tagesteil fehlt in der Zelle -- er darf nicht hinter dem "
            f"staerkeren Nachtwert verschwinden: {html!r}"
        )
        assert "hoch" not in html and "nachts" not in html, (
            f"Die Vorschau zeigt eine Nachtangabe (#1848 A3): {html!r}"
        )

    def test_cell_day_word_paired_with_day_hour_fall_b(self):
        """Fehler 1 behoben: 'mittel' und '@14' muessen NAH beieinander
        stehen (dieselbe Zelle, derselbe Tagesteil) -- keine Vermischung mit
        der Nachtstunde."""
        from src.output.renderers.email.outlook import render_outlook_table
        import re
        html = render_outlook_table([_stage(hourly_thunder=_FALL_B_HOURLY, thunder="MED")])
        # Der Tagesteil ("mittel @14") darf nicht "mittel @0" lauten.
        assert not re.search(r"mittel\s*@0\b", html), (
            f"Tageswort mit Nachtstunde vermischt: {html!r}"
        )

    def test_cell_night_only_fall_a_zeigt_kein_gewitter(self):
        """⚠️ AC-4 UMGEDREHT (#1848 A3): frueher "Zelle zeigt die Nachtangabe
        statt eines reinen '-'". Ein rein naechtliches Gewitter erscheint in
        der Vorschau seither gar nicht mehr; die Zelle sagt ausdruecklich
        "kein Gewitter" (fix_1841 AC-2) und behauptet vor allem KEINE
        Tagesstufe.

        🔴 Bekannte Grenze, vom PO getragen (A3 Known Limitations): dieser
        Fall ist damit von "gar kein Gewitter" nicht mehr zu unterscheiden."""
        from src.output.renderers.email.compare_html import _fmt_thunder
        from src.output.renderers.email.outlook import render_outlook_table
        import re
        html = render_outlook_table([_stage(hourly_thunder=_FALL_A_HOURLY, thunder="NONE")])
        zelle = re.findall(r">([^<>]*)</td>", html)[7]
        assert zelle == _fmt_thunder(None), (
            f"Erwartet das ausdrueckliche 'kein Gewitter'-Zeichen, erhalten: "
            f"{zelle!r}"
        )
        assert "hoch" not in html and "nachts" not in html, (
            f"Die Vorschau zeigt das Nachtgewitter (#1848 A3): {html!r}"
        )

    def test_cell_unchanged_without_thunder(self):
        """AC-5 Regressionsschutz: ohne jedes Gewitter bleibt die Zelle wie
        bisher (kein neuer Text)."""
        from src.output.renderers.email.outlook import render_outlook_table
        html_before = render_outlook_table([_stage(hourly_thunder=(), thunder="NONE")])
        assert "nachts" not in html_before


# ---------------------------------------------------------------------------
# AC-3: Klartext-Zeile (render_outlook_plain) -- der Kernauftrag des Issues
# ---------------------------------------------------------------------------

class TestPlainLineDayNight:
    def test_plain_line_ohne_nachtangabe_fall_a(self):
        """⚠️ UMGEDREHT (#1848 A3): frueher "fuer Fall A erscheint erstmals
        eine Nachtangabe mit Uhrzeit". Die Vorschau zeigt seither nur das
        Tagesfenster -- ein rein naechtliches Gewitter erscheint nicht."""
        from src.output.renderers.email.outlook import render_outlook_plain
        plain = render_outlook_plain([_stage(hourly_thunder=_FALL_A_HOURLY, thunder="NONE")])
        assert "hoch" not in plain and "nachts" not in plain, (
            f"Die Klartext-Vorschau zeigt eine Nachtangabe (#1848 A3):\n{plain}"
        )

    def test_plain_line_zeigt_nur_den_tagesteil_fall_b(self):
        """⚠️ UMGEDREHT (#1848 A3): frueher wurde hier die Nachtangabe
        eingefordert. Geblieben ist die #1653-Substanz: der Tagesteil steht
        da und verschwindet nicht hinter dem staerkeren Nachtwert."""
        from src.output.renderers.email.outlook import render_outlook_plain
        plain = render_outlook_plain([_stage(hourly_thunder=_FALL_B_HOURLY, thunder="MED")])
        assert "mittel" in plain and "@14" in plain, (
            f"Der Tagesteil fehlt in der Klartext-Zeile:\n{plain}"
        )
        assert "hoch" not in plain and "nachts" not in plain, (
            f"Die Klartext-Vorschau zeigt eine Nachtangabe (#1848 A3):\n{plain}"
        )

    def test_plain_line_unchanged_without_thunder(self):
        """AC-5 Regressionsschutz."""
        from src.output.renderers.email.outlook import render_outlook_plain
        plain = render_outlook_plain([_stage(hourly_thunder=(), thunder="NONE")])
        assert "nachts" not in plain


# ---------------------------------------------------------------------------
# AC-2, AC-4: Telegram-Ausblick-Bubble (narrow.render_telegram_bubbles)
# ---------------------------------------------------------------------------

class TestTelegramDayNight:
    def test_telegram_shows_only_the_day_part_fall_b(self):
        """⚠️ AC-2 UMGEDREHT (#1848 A3): frueher mussten Tag UND Nacht
        erscheinen. Geblieben ist die #1653-Substanz: bei Fall B zeigte
        Telegram frueher NUR '⚡hoch@0' -- das Tagesgewitter 'mittel' um
        14 Uhr kam nie durch, weil nur der 24h-Peak gezeigt wurde. Genau das
        bleibt abgewehrt."""
        body = _render_telegram([_stage(hourly_thunder=_FALL_B_HOURLY, thunder="MED")])
        assert "mittel" in body and "@14" in body, (
            f"Tagesgewitter fehlt in Telegram:\n{body}"
        )
        assert "hoch" not in body and "nachts" not in body, (
            f"Die Telegram-Vorschau zeigt eine Nachtangabe (#1848 A3):\n{body}"
        )

    def test_telegram_night_only_fall_a_zeigt_kein_gewitter(self):
        """⚠️ UMGEDREHT (#1848 A3): ein rein naechtliches Gewitter erscheint
        in der Vorschau nicht mehr."""
        body = _render_telegram([_stage(hourly_thunder=_FALL_A_HOURLY, thunder="NONE")])
        assert "hoch" not in body and "nachts" not in body, (
            f"Die Telegram-Vorschau zeigt das Nachtgewitter (#1848 A3):\n{body}"
        )

    def test_telegram_day_word_not_invented_from_aggregate(self):
        """F004 im dritten Kanal: Aggregat "HIGH", im Tagesfenster aber keine
        Gewitterstunde. Die Bubble zeigte "⚡HIGH · nachts hoch@0" -- ein
        Tagesgewitter, das es dort nie gab.

        #1848 A3: der Nachtzusatz entfaellt, die Zusicherung selbst bleibt --
        aus dem Aggregat darf kein Tagesgewitter entstehen."""
        body = _render_telegram([_stage(hourly_thunder=_FALL_A_HOURLY, thunder="HIGH")])
        assert "⚡HIGH" not in body, (
            f"Telegram erfindet ein Tagesgewitter aus dem Aggregat:\n{body}"
        )
        assert "⚡–" in body, f"Got:\n{body}"
        assert "nachts" not in body, (
            f"Die Telegram-Vorschau zeigt eine Nachtangabe (#1848 A3):\n{body}"
        )

    def test_telegram_structurally_correct_fall_c(self):
        """Fall C zeigte bisher zufaellig richtig (Tag zufaellig staerker).
        Nach dem Fix ist das Ergebnis strukturell garantiert.

        ⚠️ #1848 A3: geprueft wird jetzt nur noch der Tagesteil -- der
        Nachtteil ('mittel @22') entfaellt aus der Vorschau. Die Fixture
        bleibt Fall C (Tag staerker als Nacht), damit weiterhin belegt ist,
        dass die Zelle dem TAGESFENSTER folgt und nicht dem 24h-Peak."""
        body = _render_telegram([_stage(hourly_thunder=_FALL_C_HOURLY, thunder="HIGH")])
        assert "hoch" in body and "@14" in body
        assert "@22" not in body and "nachts" not in body, (
            f"Die Telegram-Vorschau zeigt eine Nachtangabe (#1848 A3):\n{body}"
        )


# ---------------------------------------------------------------------------
# Wiring: build_outlook_row() reicht das Tagesfenster additiv durch
# ---------------------------------------------------------------------------

class TestBuildOutlookRowWindowPassthrough:
    def test_window_params_are_additive(self):
        """Zwei neue optionale Keyword-Parameter duerfen die bestehende,
        byte-exakte Parity (test_trip_outlook_parity.py) nicht veraendern,
        wenn sie NICHT gesetzt werden."""
        from datetime import datetime, timezone
        from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
        from output.renderers.email.outlook import build_outlook_row
        from zoneinfo import ZoneInfo

        summary = SegmentWeatherSummary(
            temp_min_c=9.4, temp_max_c=21.6, precip_sum_mm=3.5,
            wind_max_kmh=28.0, thunder_level_max=ThunderLevel.MED, pop_max_pct=60,
        )
        points = [
            ForecastDataPoint(ts=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
                              gust_kmh=42.0, thunder_level=ThunderLevel.MED,
                              precip_1h_mm=1.5, wind10m_kmh=22.0),
        ]
        row = build_outlook_row(summary, points, "Mo", ZoneInfo("Europe/Berlin"))
        assert "day_window_start_hour" not in row, (
            "Ohne uebergebenes Fenster darf kein neuer Schluessel entstehen "
            "(Parity zu test_trip_outlook_parity.py)"
        )
        assert "day_window_end_hour" not in row

    def test_window_params_propagate_when_given(self):
        from datetime import datetime, timezone
        from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
        from output.renderers.email.outlook import build_outlook_row
        from zoneinfo import ZoneInfo

        summary = SegmentWeatherSummary(
            temp_min_c=9.4, temp_max_c=21.6, precip_sum_mm=3.5,
            wind_max_kmh=28.0, thunder_level_max=ThunderLevel.MED, pop_max_pct=60,
        )
        points = [
            ForecastDataPoint(ts=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
                              gust_kmh=42.0, thunder_level=ThunderLevel.MED,
                              precip_1h_mm=1.5, wind10m_kmh=22.0),
        ]
        row = build_outlook_row(
            summary, points, "Mo", ZoneInfo("Europe/Berlin"),
            day_window_start_hour=6, day_window_end_hour=18,
        )
        assert row.get("day_window_start_hour") == 6
        assert row.get("day_window_end_hour") == 18


# ---------------------------------------------------------------------------
# Adversary F001: _build_stage_trend() reicht das INDIVIDUELLE Tagesfenster
# des Trips bis in die gerenderte Zeile durch
# ---------------------------------------------------------------------------

class _TrendSchedulerWithFixedWeather:
    """Echter Scheduler, nur die drei Netz-/Fetch-Schritte durch aufgezeichnete
    Werte ersetzt (Unterklasse mit echten DTOs, kein Mock-Objekt): der zu
    pruefende Code -- Fensteraufloesung und Uebergabe an build_outlook_row --
    laeuft unveraendert."""

    @staticmethod
    def build(weather):
        from src.services.trip_report_scheduler import TripReportSchedulerService

        class _Fixed(TripReportSchedulerService):
            def _convert_trip_to_segments(self, trip, target_date):
                return ["ein-segment"]

            def _fetch_weather(self, segments, provider=None):
                return weather

            def _enrich_ensemble_for_trip(self, trip, weather_data):
                return None

        return _Fixed()


def _weather_with_thunder_hours():
    """Eine Etappe, deren Gewitter um 14 Uhr (hoch) und um 22 Uhr (mittel)
    liegt -- die beiden Stunden fallen bei Default-Fenster (4-19) und bei
    Fenster 20-23 auf GEGENUEBERLIEGENDE Seiten der Tag/Nacht-Grenze."""
    from datetime import datetime, timezone
    from src.app.models import (
        ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
    )

    day = datetime.now(timezone.utc).date()
    points = [
        ForecastDataPoint(
            ts=datetime(day.year, day.month, day.day, 14, 0, tzinfo=timezone.utc),
            thunder_level=ThunderLevel.HIGH, precip_1h_mm=0.0,
            wind10m_kmh=10.0, gust_kmh=20.0,
        ),
        ForecastDataPoint(
            ts=datetime(day.year, day.month, day.day, 22, 0, tzinfo=timezone.utc),
            thunder_level=ThunderLevel.MED, precip_1h_mm=0.0,
            wind10m_kmh=8.0, gust_kmh=15.0,
        ),
    ]
    return [SegmentWeatherData(
        segment=None,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=points,
        ),
        aggregated=SegmentWeatherSummary(temp_min_c=10.0, temp_max_c=20.0),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )]


def _trip_with_day_window(start_hour, end_hour):
    from datetime import date, timedelta
    from src.app.models import TripReportConfig
    from src.app.trip import Stage, Trip, Waypoint

    today = date.today()
    trip = Trip(
        id="tw-1653", name="Fenster-Trip",
        stages=[Stage(
            id="S2", name="Morgen",
            date=today + timedelta(days=1),
            waypoints=[Waypoint(id="W1", name="Ort", lat=42.0, lon=9.0, elevation_m=500)],
        )],
    )
    trip.report_config = TripReportConfig(
        trip_id=trip.id,
        day_window_start_hour=start_hour, day_window_end_hour=end_hour,
    )
    return trip


class TestStageTrendUsesConfiguredDayWindow:
    def _tokens_for_window(self, start_hour, end_hour):
        from datetime import date, datetime, timezone
        from zoneinfo import ZoneInfo
        from src.output.renderers.email.helpers import format_trend_tokens

        service = _TrendSchedulerWithFixedWeather.build(_weather_with_thunder_hours())
        result = service._build_stage_trend(
            _trip_with_day_window(start_hour, end_hour),
            date.today(), now_utc=datetime.now(timezone.utc), tz=ZoneInfo("UTC"),
        )
        assert result.rows, (
            f"Kein Ausblick gebaut (state={result.state}) -- der Test misst "
            "sonst nichts."
        )
        return format_trend_tokens(result.rows[0])

    def test_individual_window_moves_the_day_night_border(self):
        """Fenster 20-23: 22 Uhr ist Tag, 14 Uhr ist Nacht. Faellt die
        Fensteruebergabe an build_outlook_row() weg, gilt still der Default
        4-19 und die beiden Stunden tauschen die Seiten."""
        tok = self._tokens_for_window(20, 23)
        assert "@22" in tok["thunder_day_token"], (
            "Das individuelle Tagesfenster 20-23 wirkt nicht -- die Zeile "
            f"faellt auf den Default 4-19 zurueck: {tok['thunder_day_token']!r}"
        )
        assert "@14" in tok["thunder_night_token"], (
            f"Got: {tok['thunder_night_token']!r}"
        )

    def test_default_window_is_the_other_way_round(self):
        """Kontrollprobe am selben Wetter: mit dem Default-Fenster liegen die
        beiden Stunden genau andersherum -- der Unterschied oben stammt also
        wirklich aus der Konfiguration und nicht aus den Daten."""
        tok = self._tokens_for_window(4, 19)
        assert "@14" in tok["thunder_day_token"]
        assert "@22" in tok["thunder_night_token"]

    def test_rendered_cell_carries_the_individual_window(self):
        """Wirkung statt Faehigkeit: bis in die gerenderte Zelle der Mail."""
        from datetime import date, datetime, timezone
        from zoneinfo import ZoneInfo
        from src.output.renderers.email.outlook import render_outlook_table
        import re

        service = _TrendSchedulerWithFixedWeather.build(_weather_with_thunder_hours())
        result = service._build_stage_trend(
            _trip_with_day_window(20, 23), date.today(),
            now_utc=datetime.now(timezone.utc), tz=ZoneInfo("UTC"),
        )
        assert result.rows
        html = render_outlook_table(result.rows)
        cell = re.findall(r">([^<>]*)</td>", html)[7]
        # #1848 A3: der Nachtteil ('nachts hoch @14' -- die 14-Uhr-Stunde
        # liegt AUSSERHALB des konfigurierten Fensters 20-23) entfaellt aus
        # der Vorschau. Die Zusicherung wird dadurch sogar schaerfer: die
        # Zelle darf ausschliesslich Stunden des konfigurierten Fensters
        # nennen.
        assert cell == "mittel @22", (
            f"Gewitter-Zelle folgt nicht dem konfigurierten Fenster 20-23: {cell!r}"
        )
        assert "@14" not in cell, (
            f"Die Zelle nennt eine Stunde ausserhalb des Fensters 20-23: {cell!r}"
        )


# ---------------------------------------------------------------------------
# AC-1 (Adversary F002): das Tageswort stammt aus DEMSELBEN Token wie die
# Tages-Uhrzeit -- nicht aus `stage["thunder"]`
# ---------------------------------------------------------------------------

class TestDayWordComesFromDayToken:
    """`stage["thunder"]` ist das auf die Gehzeit geklemmte Aggregat,
    `thunder_day_token` die nach Tagesfenster gefilterte Stundenreihe. Zwei
    verschiedene Rechnungen: solange das Wort aus der ersten und die Uhrzeit
    aus der zweiten kam, stimmten sie nur zufaellig ueberein."""

    def test_day_shown_although_aggregate_says_none(self):
        """Gegenlaeufige Quellen: Aggregat "NONE", Tagesfenster "mittel @16".
        Die Zelle muss dem Tagesfenster folgen -- vorher verschwand das
        Tagesgewitter vollstaendig."""
        from src.output.renderers.email.outlook import render_outlook_table
        html = render_outlook_table([
            _stage(hourly_thunder=(_hv(16, 2.0),), thunder="NONE"),
        ])
        assert "mittel @16" in html, (
            "Das Tagesgewitter der Stundenreihe fehlt, weil die Zelle dem "
            f"geklemmten Aggregat folgt statt dem Tagesfenster:\n{html}"
        )

    def test_day_hidden_although_aggregate_says_high(self):
        """Umgekehrte Richtung: Aggregat "HIGH", im Tagesfenster liegt aber
        keine einzige Gewitterstunde (nur nachts um 0 Uhr). Die Zelle darf
        kein Tagesgewitter erfinden."""
        from src.output.renderers.email.outlook import render_outlook_table
        import re
        html = render_outlook_table([
            _stage(hourly_thunder=_FALL_A_HOURLY, thunder="HIGH"),
        ])
        cell = re.findall(r">([^<>]*)</td>", html)[7]
        # #1848 A3: die Nachtangabe entfaellt aus der Vorschau -- geblieben
        # ist die eigentliche Zusicherung: aus dem Aggregat entsteht kein
        # Tagesgewitter. Der Strich ist das ausdrueckliche "kein Gewitter".
        from src.output.renderers.email.compare_html import _fmt_thunder
        assert cell == _fmt_thunder(None), (
            f"Zelle behauptet ein Tagesgewitter aus dem Aggregat: {cell!r}"
        )
        assert "hoch" not in cell, (
            f"Die Vorschau zeigt die Nachtstufe (#1848 A3): {cell!r}"
        )

    def test_day_word_follows_token_not_aggregate_level(self):
        """Aggregat sagt "hoch", das Tagesfenster nur "leicht" -- gezeigt wird
        das Wort des Tokens, damit Wort und Uhrzeit zusammenpassen."""
        from src.output.renderers.email.outlook import render_outlook_table
        import re
        html = render_outlook_table([
            _stage(hourly_thunder=(_hv(9, 1.0),), thunder="HIGH"),
        ])
        cell = re.findall(r">([^<>]*)</td>", html)[7]
        assert cell == "leicht @9", (
            f"Wort und Uhrzeit stammen aus verschiedenen Quellen: {cell!r}"
        )

    def test_aggregate_still_used_without_any_hourly_series(self):
        """Ohne Stundenreihe kann der Split nichts sagen -- dann bleibt es bei
        der Stufe des Aggregats ohne Uhrzeit (Alt-Fixtures, Compare)."""
        from src.output.renderers.email.outlook import render_outlook_table
        import re
        html = render_outlook_table([_stage(hourly_thunder=(), thunder="MED")])
        cell = re.findall(r">([^<>]*)</td>", html)[7]
        assert cell == "mittel", f"Got: {cell!r}"


# ---------------------------------------------------------------------------
# AC-1/AC-3 (Adversary F004): dasselbe fuer die KLARTEXT-Zeile -- das
# Tageswort stammt aus `thunder_day_token`, nicht aus `stage["thunder"]`
# ---------------------------------------------------------------------------

class TestPlainDayWordComesFromDayToken:
    """Die Klartext-Mail ist der eigentliche fachliche Auftrag dieser Scheibe
    (Spec Purpose: Konsistenz in allen drei Kanaelen). Sie baute ihr Tageswort
    weiterhin aus `tok['thunder_plain']` -- also aus dem auf die Gehzeit
    geklemmten Aggregat -- waehrend HTML und Telegram laengst dem Tagesfenster
    folgten."""

    @staticmethod
    def _first_row(plain: str) -> str:
        # Zeile 0 leer, Zeile 1 Ueberschrift, ab Zeile 2 die Etappen.
        return plain.split("\n")[2]

    def test_plain_day_shown_although_aggregate_says_none(self):
        """Gegenlaeufige Quellen: Aggregat "NONE", Tagesfenster "mittel @16".
        Vorher zeigte die Zeile '⚡–' und das Tagesgewitter verschwand."""
        from src.output.renderers.email.outlook import render_outlook_plain
        row = self._first_row(render_outlook_plain([
            _stage(hourly_thunder=(_hv(16, 2.0),), thunder="NONE"),
        ]))
        assert "⚡mittel" in row, (
            "Das Tagesgewitter der Stundenreihe fehlt, weil die Klartext-Zeile "
            f"dem geklemmten Aggregat folgt statt dem Tagesfenster: {row!r}"
        )
        assert "⚡–" not in row, f"Alte Aggregat-Marke steht noch da: {row!r}"

    def test_plain_day_hidden_although_aggregate_says_high(self):
        """Umgekehrte Richtung: Aggregat "HIGH", im Tagesfenster liegt aber
        keine Gewitterstunde (nur nachts um 0 Uhr). Die Zeile darf kein
        Tagesgewitter erfinden."""
        from src.output.renderers.email.outlook import render_outlook_plain
        row = self._first_row(render_outlook_plain([
            _stage(hourly_thunder=_FALL_A_HOURLY, thunder="HIGH"),
        ]))
        # #1848 A3: der Nachtzusatz entfaellt; die Zusicherung bleibt --
        # aus dem Aggregat entsteht kein Tagesgewitter.
        assert row.endswith("⚡–"), (
            f"Zeile behauptet ein Tagesgewitter aus dem Aggregat: {row!r}"
        )
        assert "nachts" not in row, (
            f"Die Vorschau zeigt eine Nachtangabe (#1848 A3): {row!r}"
        )

    def test_plain_day_word_follows_token_not_aggregate_level(self):
        """Aggregat sagt "HIGH", das Tagesfenster nur "leicht" -- gezeigt wird
        das Wort des Tokens."""
        from src.output.renderers.email.outlook import render_outlook_plain
        row = self._first_row(render_outlook_plain([
            _stage(hourly_thunder=(_hv(9, 1.0),), thunder="HIGH"),
        ]))
        # #1493: das Tageswort traegt jetzt die Onset-Stunde -- geprueft
        # bleibt, dass Wort UND Stunde aus dem Tagestoken stammen (Stunde 9),
        # nicht aus dem Aggregat ("HIGH").
        assert row.endswith("⚡leicht@9"), (
            f"Wort stammt nicht aus dem Tagestoken: {row!r}"
        )

    def test_plain_aggregate_still_used_without_any_hourly_series(self):
        """Rueckwaertskompatibilitaet (Alt-Aufrufer/Compare): ohne Stundenreihe
        bleibt es beim Aggregatwort."""
        from src.output.renderers.email.outlook import render_outlook_plain
        row = self._first_row(render_outlook_plain([
            _stage(hourly_thunder=(), thunder="MED"),
        ]))
        # Issue #1488 B: Aggregatwort kommt aus THUNDER_LABEL_DE ("mittel").
        assert row.endswith("⚡mittel"), f"Got: {row!r}"


# ---------------------------------------------------------------------------
# Adversary F003: Compare-Klartext-Zweig von render_outlook_plain()
# ---------------------------------------------------------------------------

class TestComparePlainMetricsBranch:
    """`render_outlook_plain(rows, metrics=[...])` ist der Klartext-Ausblick
    der Ortsvergleich-Mail (comparison.py). Eigener Zweig, eigener Ausstieg --
    faellt der Ausstieg weg, haengt an jede Zeile eine zweite, im Trip-Format
    gebaute Zeile mit lauter Leerwerten."""

    _METRICS = [
        {"metric_id": "temperature", "aggregation": "max"},
        {"metric_id": "wind", "aggregation": "max"},
    ]

    def _rows(self):
        return [
            {"weekday": "Mo", "cells": ["21", "25"],
             "thunder": "MED", "hourly_thunder": (_hv(16, 2.0),)},
            {"weekday": "Di", "cells": ["19", "12"],
             "thunder": "NONE", "hourly_thunder": ()},
        ]

    def test_compare_plain_has_exactly_one_line_per_row(self):
        from src.output.renderers.email.outlook import render_outlook_plain
        out = render_outlook_plain(
            self._rows(), show_acc=False, metrics=self._METRICS,
            heading="3-Tages-Ausblick", show_name=False,
        )
        assert out.split("\n") == [
            "",
            "3-Tages-Ausblick",
            "Mo  Temperatur 21  Wind 25",
            "Di  Temperatur 19  Wind 12",
            "",
        ], f"Compare-Klartext-Ausblick unerwartet:\n{out!r}"

    def test_compare_plain_carries_no_trip_format_remnants(self):
        """Die Trip-Formatierung (Temperaturspanne, Gewitter-Token, Notiz-Pfeil)
        darf im Ortsvergleich nicht mit auftauchen -- dort gibt es weder
        Etappennamen noch die feste Sieben-Spalten-Zeile."""
        from src.output.renderers.email.outlook import render_outlook_plain
        out = render_outlook_plain(
            self._rows(), show_acc=False, metrics=self._METRICS,
            heading="3-Tages-Ausblick", show_name=False,
        )
        for fremd in ("⚡", "°C", "↳", "nachts"):
            assert fremd not in out, (
                f"Trip-Formatierung {fremd!r} in der Compare-Klartext-Ausgabe:\n{out!r}"
            )


# ---------------------------------------------------------------------------
# AC-6: Compare-Pfad (metrics-Auswahl) bleibt unberuehrt
# ---------------------------------------------------------------------------

class TestComparePathUnaffected:
    def test_compare_metrics_cells_unaffected_by_day_night_split(self):
        """Der Compare-Zweig (metrics is not None) liest 'cells' ueber
        format_outlook_value(), nicht ueber format_trend_tokens() --
        die Tag/Nacht-Trennung darf diesen Pfad nicht veraendern."""
        from datetime import datetime, timezone
        from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
        from output.renderers.email.outlook import build_outlook_row
        from zoneinfo import ZoneInfo

        summary = SegmentWeatherSummary(
            temp_min_c=9.4, temp_max_c=21.6, precip_sum_mm=3.5,
            wind_max_kmh=28.0, thunder_level_max=ThunderLevel.HIGH, pop_max_pct=60,
        )
        points = [
            ForecastDataPoint(ts=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
                              gust_kmh=42.0, thunder_level=ThunderLevel.HIGH,
                              precip_1h_mm=1.5, wind10m_kmh=22.0),
            ForecastDataPoint(ts=datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc),
                              gust_kmh=30.0, thunder_level=ThunderLevel.MED,
                              precip_1h_mm=0.0, wind10m_kmh=15.0),
        ]
        row_without_window = build_outlook_row(
            summary, points, "Mo", ZoneInfo("Europe/Berlin"),
            metrics=[{"metric_id": "thunder", "aggregation": "max"}],
        )
        row_with_window = build_outlook_row(
            summary, points, "Mo", ZoneInfo("Europe/Berlin"),
            metrics=[{"metric_id": "thunder", "aggregation": "max"}],
            day_window_start_hour=4, day_window_end_hour=19,
        )
        assert row_without_window["cells"] == row_with_window["cells"], (
            "Die Compare-Spaltenauswahl darf sich durch das neue Tagesfenster "
            "nicht aendern (AC-6)."
        )


# ---------------------------------------------------------------------------
# F005 (Adversary Runde 3): Eskalation INNERHALB eines Fensters
# ---------------------------------------------------------------------------
# `render_threshold_peak_value` liefert dann `leicht@5(hoch@15)`. HTML- und
# Klartext-Mail lasen bisher nur die erste Gruppe und verwarfen den
# Spitzenwert -- ein ueber den Nachmittag von "leicht" auf "hoch"
# eskalierendes Gewitter erschien als harmlos.

# Tagesfenster (Default 04-19): erst leicht @5, Spitze hoch @15.
_ESCALATION_DAY_HOURLY = (_hv(5, 1.0), _hv(15, 3.0))
# Nachtfenster: erst leicht @1, Spitze hoch @3.
_ESCALATION_NIGHT_HOURLY = (_hv(1, 1.0), _hv(3, 3.0))


class TestEscalationWithinWindowShowsPeak:
    def test_day_token_carries_both_stages(self):
        """Vorbedingung: der Token traegt beide Stufen -- der Verlust
        entsteht erst beim Rendern."""
        from src.output.renderers.email.helpers import format_trend_tokens
        tok = format_trend_tokens(
            _stage(hourly_thunder=_ESCALATION_DAY_HOURLY, thunder="HIGH")
        )
        assert tok["thunder_day_token"] == "leicht@5(hoch@15)"

    def test_html_day_shows_peak_stage(self):
        from src.output.renderers.email.outlook import render_outlook_table
        html = render_outlook_table(
            [_stage(hourly_thunder=_ESCALATION_DAY_HOURLY, thunder="HIGH")]
        )
        assert "hoch" in html, (
            f"Spitzenstufe des Tagesgewitters unterschlagen:\n{html}"
        )
        assert "@15" in html, f"Stunde der Spitzenstufe fehlt:\n{html}"
        assert "leicht" in html, f"Erst-Ueberschreitung verloren:\n{html}"

    def test_plain_day_shows_peak_stage(self):
        from src.output.renderers.email.outlook import render_outlook_plain
        plain = render_outlook_plain(
            [_stage(hourly_thunder=_ESCALATION_DAY_HOURLY, thunder="HIGH")]
        )
        assert "hoch" in plain, (
            f"Spitzenstufe des Tagesgewitters unterschlagen:\n{plain}"
        )
        assert "@15" in plain, f"Stunde der Spitzenstufe fehlt:\n{plain}"

    def test_html_night_peak_erscheint_nicht_in_der_vorschau(self):
        """⚠️ UMGEDREHT (#1848 A3): frueher wurde hier die Spitzenstufe des
        NACHT-Gewitters eingefordert ('nachts leicht @1 (hoch @3)'). Die
        3-Tages-Vorschau zeigt seither nur das Tagesfenster -- die
        Eskalations-Zusicherung bleibt fuer den TAGES-Fall unveraendert in
        Kraft (s. ``test_html_day_shows_peak_stage`` oben)."""
        from src.output.renderers.email.outlook import render_outlook_table
        html = render_outlook_table(
            [_stage(hourly_thunder=_ESCALATION_NIGHT_HOURLY, thunder="HIGH")]
        )
        assert "nachts" not in html, (
            f"Die Vorschau zeigt eine Nachtangabe (#1848 A3):\n{html}"
        )

    def test_plain_night_peak_erscheint_nicht_in_der_vorschau(self):
        """Klartext-Pendant zum Test darueber."""
        from src.output.renderers.email.outlook import render_outlook_plain
        plain = render_outlook_plain(
            [_stage(hourly_thunder=_ESCALATION_NIGHT_HOURLY, thunder="HIGH")]
        )
        assert "nachts" not in plain, (
            f"Die Vorschau zeigt eine Nachtangabe (#1848 A3):\n{plain}"
        )

    def test_no_escalation_no_extra_text(self):
        """Regressionsschutz: bleibt es bei einer Stufe, kommt kein
        Klammer-Zusatz dazu (Golden-Fixtures unveraendert)."""
        from src.output.renderers.email.outlook import (
            render_outlook_plain, render_outlook_table,
        )
        stage = _stage(hourly_thunder=(_hv(14, 2.0),), thunder="MED")
        html = render_outlook_table([stage])
        plain = render_outlook_plain([stage])
        assert "mittel @14" in html and "(" not in html.split("mittel @14")[1][:6]
        assert "⚡mittel" in plain and "(" not in plain

    def test_telegram_untouched_still_shows_full_token(self):
        """Kontrastfolie: Telegram gab den vollen Token schon vorher aus und
        bleibt unveraendert."""
        tg = _render_telegram(
            [_stage(hourly_thunder=_ESCALATION_DAY_HOURLY, thunder="HIGH")]
        )
        assert "leicht@5(hoch@15)" in tg, tg
