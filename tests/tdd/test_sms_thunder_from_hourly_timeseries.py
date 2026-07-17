"""Gewitter-Aussage aus der Stunden-Zeitreihe — SMS, Telegram und E-Mail einig (#1275).

Spec: docs/specs/bugfix/fix_1275_sms_thunder_today.md
ADR:  docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md

TDD RED. Diese Tests MÜSSEN vor der Implementierung rot sein:
  AC-1  `TH:` ist strukturell immer "-", weil _segments_to_normalized_forecast()
        (sms_trip.py:113-122) dp.thunder_level nie liest und thunder_hourly im
        DailyForecast (:157-165) nicht setzt.
  AC-3  Die Stunde in TH+ ist hartkodiert 12 (sms_trip.py:227).
  AC-5  Telegram liest agg.thunder_level_max (narrow.py:164-180) — ungefenstert,
        meldet also auch Gewitter ausserhalb der Wanderzeit.

WICHTIG (ADR-0025, Entscheidung 5): Der Nachweis laeuft durch die echten
Einstiegspunkte der Kanaele — SMSTripFormatter().format_sms() und
render_telegram_bubbles() — NICHT durch build_token_line() mit vorgefertigtem
DailyForecast. Genau diese Abkuerzung (tests/golden/test_sms_golden.py:63-122)
hat den Bug drei Anlaeufe lang ueberleben lassen.

Keine Mocks, keine Dateiinhalt-Checks. Reale Fixtures, reale Aufrufe.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from src.output.renderers.sms_trip import SMSTripFormatter

_YEAR, _MONTH, _DAY = 2026, 7, 15
_TZ = ZoneInfo("UTC")

# Wanderfenster der Etappe: 07:00-17:00 UTC.
_WALK_START_H = 7
_WALK_END_H = 17


def _dp(hour: int, thunder: ThunderLevel = ThunderLevel.NONE) -> ForecastDataPoint:
    """Ein Stunden-Datenpunkt; `thunder` setzt das Gewitter-Level dieser Stunde."""
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, _DAY, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0,
        wind10m_kmh=10.0,
        gust_kmh=20.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=thunder,
        humidity_pct=55,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _segment(thunder_by_hour: dict[int, ThunderLevel] | None = None) -> SegmentWeatherData:
    """Segment mit 24h-Zeitreihe. `thunder_by_hour` setzt Gewitter je Stunde.

    `aggregated.thunder_level_max` wird bewusst wie in der Produktion befuellt:
    `weather_metrics.py:596-598` (`_compute_thunder_level`) rechnet ueber die
    UNGEFENSTERTE Zeitreihe — also inklusive Nachtstunden. Genau dieses Aggregat
    liest Telegram (`narrow.py:164-180`), waehrend SMS/E-Mail auf das Wanderfenster
    einschraenken. Das Fixture bildet diese Asymmetrie ab, statt sie wegzudefinieren.
    """
    tb = thunder_by_hour or {}
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=datetime(_YEAR, _MONTH, _DAY, _WALK_START_H, 0, tzinfo=timezone.utc),
        end_time=datetime(_YEAR, _MONTH, _DAY, _WALK_END_H, 0, tzinfo=timezone.utc),
        duration_hours=float(_WALK_END_H - _WALK_START_H),
        distance_km=12.0,
        ascent_m=300.0,
        descent_m=0.0,
    )
    data = [_dp(h, tb.get(h, ThunderLevel.NONE)) for h in range(0, 24)]
    ts = NormalizedTimeseries(meta=_meta(), data=data)

    # Ungefensterte Aggregation — exakt wie _compute_thunder_level() es tut.
    order = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}
    agg_thunder = max(
        (dp.thunder_level for dp in data if dp.thunder_level is not None),
        key=lambda lvl: order.get(lvl, 0),
        default=ThunderLevel.NONE,
    )

    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=20.0,
            wind_max_kmh=15.0,
            gust_max_kmh=25.0,
            precip_sum_mm=0.0,
            thunder_level_max=agg_thunder,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _sms(segments, report_type="evening", thunder_forecast=None) -> str:
    return SMSTripFormatter().format_sms(
        segments,
        stage_name="E7",
        report_type=report_type,
        tz=_TZ,
        thunder_forecast=thunder_forecast,
    )


class TestThunderTodayReachesSms:
    """AC-1/AC-2: `TH:` spiegelt das Gewitter der berichteten Etappe."""

    def test_thunder_high_at_0800_shows_th_h_at_8(self):
        """
        GIVEN: Etappe mit Gewitter HIGH um 08:00, innerhalb der Wanderzeit (07-17)
        WHEN:  die SMS fuer diese Etappe erzeugt wird
        THEN:  die SMS zeigt `TH:H@8` — nicht `TH:-`

        Das ist der vom PO gemeldete Fall: die E-Mail zeigt "Gewitter ab 08:00 ·
        staerkste 08:00", die SMS zeigt `TH:-`. RED-Erwartung: schlaegt fehl, weil
        `thunder_hourly` nie befuellt wird.
        """
        segments = [_segment({8: ThunderLevel.HIGH})]
        sms = _sms(segments)

        assert "TH:-" not in sms, (
            f"SMS meldet KEIN Gewitter, obwohl um 08:00 ein HIGH-Gewitter in der "
            f"Zeitreihe steht — genau der gemeldete Widerspruch zur E-Mail.\nSMS: {sms}"
        )
        assert "TH:H@8" in sms, f"Erwartet `TH:H@8` in der SMS.\nSMS: {sms}"

    def test_thunder_med_then_high_shows_first_and_peak(self):
        """
        GIVEN: Etappe mit MED um 09:00 und HIGH um 14:00 (beide in der Wanderzeit)
        WHEN:  die SMS erzeugt wird
        THEN:  `TH:M@9(H@14)` — erste Schwellenueberschreitung + Tagesmaximum,
               dieselbe "ab/staerkste"-Aussage wie die E-Mail
        """
        segments = [_segment({9: ThunderLevel.MED, 14: ThunderLevel.HIGH})]
        sms = _sms(segments)

        assert "TH:M@9(H@14)" in sms, (
            f"Erwartet `TH:M@9(H@14)` (erste MED um 9, Maximum HIGH um 14).\nSMS: {sms}"
        )

    def test_no_thunder_shows_dash(self):
        """
        GIVEN: Etappe ohne jedes Gewitter in der gesamten Wanderzeit
        WHEN:  die SMS erzeugt wird
        THEN:  `TH:-` — kein erfundenes Signal, wo keins ist

        GUARD, kein RED: dieser Test ist heute schon gruen — aber aus dem falschen
        Grund (TH: ist immer "-"). Er muss nach dem Fix gruen BLEIBEN.
        """
        segments = [_segment()]
        sms = _sms(segments)

        assert "TH:-" in sms, f"Ohne Gewitter muss `TH:-` stehen.\nSMS: {sms}"

    def test_thunder_outside_walking_window_is_ignored(self):
        """
        GIVEN: Gewitter HIGH ausschliesslich um 02:00 — ausserhalb der Wanderzeit
        WHEN:  die SMS erzeugt wird
        THEN:  `TH:-` — die SMS warnt nicht vor einem Ereignis, das den Wanderer
               nicht betrifft (Fensterung wie bei Regen/Wind/Boeen)
        """
        segments = [_segment({2: ThunderLevel.HIGH})]
        sms = _sms(segments)

        assert "TH:-" in sms, (
            f"Gewitter um 02:00 liegt ausserhalb der Wanderzeit 07-17 und darf die "
            f"SMS nicht ausloesen.\nSMS: {sms}"
        )


class TestAllChannelsAgree:
    """AC-4/AC-5: Telegram sagt dasselbe wie die SMS — auch beim Nacht-Gewitter."""

    @staticmethod
    def _telegram_footer(segments) -> str:
        """Rendert die Telegram-Bubbles durch den ECHTEN Einstiegspunkt.

        ADR-0025, Entscheidung 5: eine Kanal-Aussage wird durch den echten
        Einstiegspunkt bewiesen, nicht durch einen Helfer.
        """
        from src.app.models import MetricConfig, UnifiedWeatherDisplayConfig
        from src.output.renderers.narrow import render_telegram_bubbles

        dc = UnifiedWeatherDisplayConfig(
            trip_id="test-1275",
            metrics=[
                MetricConfig(metric_id="temperature", enabled=True, bucket="primary", order=0),
                MetricConfig(metric_id="thunder", enabled=True, bucket="primary", order=1),
            ],
            updated_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=timezone.utc),
        )
        rows = [[{"time": f"{h:02d}", "temp": 15} for h in range(_WALK_START_H, _WALK_END_H)]]
        bubbles = render_telegram_bubbles(
            segments=segments, seg_tables=rows, dc=dc,
            report_type="evening", tz=_TZ, trip_name="E7",
        )
        return "\n".join(b.text for b in bubbles)

    def test_telegram_silent_when_thunder_only_at_night(self):
        """
        GIVEN: Gewitter HIGH ausschliesslich um 02:00 — ausserhalb der Wanderzeit
        WHEN:  Telegram und SMS fuer dieselbe Etappe erzeugt werden
        THEN:  Telegram meldet `⚡ kein` — genau wie die SMS `TH:-` zeigt

        RED-Erwartung: schlaegt fehl, weil `_tg_day_footer` `agg.thunder_level_max`
        liest, das `weather_metrics.py:596-598` UNGEFENSTERT berechnet — Telegram
        meldet HIGH, waehrend SMS/E-Mail zu Recht schweigen.
        """
        segments = [_segment({2: ThunderLevel.HIGH})]

        sms = _sms(segments)
        telegram = self._telegram_footer(segments)

        assert "TH:-" in sms, f"Vorbedingung: SMS muss schweigen.\nSMS: {sms}"
        assert "⚡ HIGH" not in telegram and "⚡ MED" not in telegram, (
            f"Telegram meldet ein Gewitter um 02:00, das ausserhalb der Wanderzeit "
            f"(07-17) liegt — die SMS schweigt zu Recht. Die Kanaele widersprechen "
            f"sich.\nSMS: {sms}\nTelegram:\n{telegram}"
        )
        assert "⚡ kein" in telegram, f"Erwartet `⚡ kein`.\nTelegram:\n{telegram}"

    def test_telegram_and_sms_agree_on_thunder_in_window(self):
        """
        GIVEN: Gewitter HIGH um 08:00, innerhalb der Wanderzeit
        WHEN:  Telegram und SMS fuer dieselbe Etappe erzeugt werden
        THEN:  beide melden das Gewitter — Telegram `⚡ HIGH`, SMS `TH:H@8`
        """
        segments = [_segment({8: ThunderLevel.HIGH})]

        sms = _sms(segments)
        telegram = self._telegram_footer(segments)

        assert "TH:H@8" in sms, f"SMS muss das Gewitter melden.\nSMS: {sms}"
        assert "⚡ HIGH" in telegram, (
            f"Telegram muss dasselbe Gewitter melden wie die SMS.\n"
            f"SMS: {sms}\nTelegram:\n{telegram}"
        )


class TestEmailAndSmsAgree:
    """AC-6/AC-5: E-Mail und SMS aus EINEM Aufruf, derselben Zeitreihe.

    Der Nachweis laeuft durch `TripReportFormatter.format_email()` — die einzige
    Stelle, die `render_email()` (trip_report.py:148) UND `format_sms()` (:224)
    aus derselben `segments`-Variable speist. Genau diese Kombination fehlte und
    liess `compact_summary.py` als vierte, ungefensterte Gewitter-Quelle
    unentdeckt (Adversary F001/F002).
    """

    @staticmethod
    def _report(segments):
        from src.output.renderers.trip_report import TripReportFormatter

        return TripReportFormatter().format_email(
            segments,
            trip_name="E7",
            report_type="evening",
            stage_name="E7",
            tz=_TZ,
        )

    @staticmethod
    def _compact_line(email_plain: str) -> str:
        """Die Kompakt-Summary-Zeile (email/plain.py:125-126) — Kopf der Mail."""
        for line in email_plain.splitlines():
            if line.startswith("E7:"):
                return line
        return ""

    def test_thunder_in_window_named_by_both_channels(self):
        """
        GIVEN: Gewitter HIGH um 08:00, innerhalb der Wanderzeit (07-17)
        WHEN:  E-Mail und SMS im selben Aufruf erzeugt werden
        THEN:  die SMS zeigt `TH:H@8` UND die E-Mail nennt dieselbe Stunde
        """
        segments = [_segment({8: ThunderLevel.HIGH})]
        report = self._report(segments)
        compact = self._compact_line(report.email_plain)

        assert "TH:H@8" in report.sms_text, f"SMS: {report.sms_text}"
        assert "⚡" in compact, (
            f"Die E-Mail-Kopfzeile verschweigt das Gewitter um 08:00, das die SMS "
            f"meldet.\nSMS: {report.sms_text}\nKopfzeile: {compact!r}"
        )
        assert "8:00" in compact, (
            f"Die E-Mail nennt nicht die Stunde 8, die die SMS als `TH:H@8` meldet — "
            f"die Kanaele widersprechen sich.\nSMS: {report.sms_text}\n"
            f"Kopfzeile: {compact!r}"
        )

    def test_night_thunder_silences_email_headline_too(self):
        """
        GIVEN: Gewitter HIGH ausschliesslich um 02:00 — ausserhalb der Wanderzeit
        WHEN:  E-Mail und SMS im selben Aufruf erzeugt werden
        THEN:  die SMS zeigt `TH:-` UND die E-Mail-Kopfzeile nennt kein Gewitter

        RED-Erwartung (Adversary F001): schlaegt fehl, weil
        `compact_summary.py:332` auf `summary.thunder_level_max` gated — das
        UNGEFENSTERTE Tages-Aggregat (`weather_metrics.py:596-598`), das
        ADR-0025 Entscheidung 1 fuer nutzersichtbare Kanal-Aussagen verbietet.
        Die Mail warnt dann mit `⚡ möglich` vor einem Nacht-Gewitter, waehrend
        SMS und Telegram zu Recht schweigen.
        """
        segments = [_segment({2: ThunderLevel.HIGH})]
        report = self._report(segments)
        compact = self._compact_line(report.email_plain)

        assert "TH:-" in report.sms_text, (
            f"Vorbedingung: die SMS muss schweigen.\nSMS: {report.sms_text}"
        )
        assert "⚡" not in compact and "Gewitter" not in compact, (
            f"Die E-Mail-Kopfzeile warnt vor einem Gewitter um 02:00, das ausserhalb "
            f"der Wanderzeit (07-17) liegt — SMS (`TH:-`) und Telegram (`⚡ kein`) "
            f"schweigen zu Recht fuer dieselbe Etappe.\nSMS: {report.sms_text}\n"
            f"Kopfzeile: {compact!r}"
        )


class TestThunderTomorrowHourIsReal:
    """AC-3: die Stunde in `TH+` kommt aus der Vorhersage, nicht aus dem Code."""

    def test_th_plus_uses_real_hour_not_hardcoded_12(self):
        """
        GIVEN: thunder_forecast["+1"] meldet ein HIGH-Gewitter um 06:00
        WHEN:  die SMS erzeugt wird
        THEN:  `TH+:H@6` — nicht `TH+:H@12`

        RED-Erwartung: schlaegt fehl, weil sms_trip.py:227 die Stunde hartkodiert
        auf 12 setzt (`HourlyValue(12, float(lvl_val))`).
        """
        thunder_forecast = {
            "+1": {
                "date": "16.07.2026",
                "level": ThunderLevel.HIGH,
                "text": "Gewitter moeglich ab 06:00",
                "hour": 6,
            }
        }
        sms = _sms([_segment()], thunder_forecast=thunder_forecast)

        assert "TH+:H@12" not in sms, (
            f"Die Stunde 12 ist hartkodiert und erfunden — das Gewitter ist fuer "
            f"06:00 gemeldet.\nSMS: {sms}"
        )
        assert "TH+:H@6" in sms, f"Erwartet `TH+:H@6`.\nSMS: {sms}"
