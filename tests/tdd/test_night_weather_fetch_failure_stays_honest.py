"""Fix #1339: ``fetch_night_weather()`` faellt bei einem Abruf-Fehler fuer
das Ziel-Nachtwetter fälschlich auf die Zeitreihe der LETZTEN ETAPPE zurueck
(Segment-Start-Geografie), statt ehrlich ``None`` zu liefern. Weil
``compute_has_gap()`` diese Ersatzdaten als "vollstaendig" ansieht, geben
alle vier Versandkanaele eine positive Entwarnung ab, obwohl am Ziel keine
echten Daten vorlagen.

Kein Mock-Theater: ``_ThrowingProvider`` ist ein echter (Nicht-Mock)
Provider-Stellvertreter, der reales Fehlverhalten simuliert (Timeout/Netz-
fehler beim Live-Abruf) -- kein zurueckgespiegeltes Sollverhalten. Fuer den
Scheduler-Delegator (kein ``provider``-Parameter) wird ``monkeypatch`` genutzt,
um die interne ``get_provider()``-Aufloesung zu ersetzen -- dasselbe Muster
wie ``tests/unit/test_preview_night_block.py::test_demo_preview_night_fetch_never_touches_live_openmeteo``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
)
from services.notification_service import compute_has_gap
from services.segment_weather import fetch_night_weather


class _ThrowingProvider:
    """Echter (Nicht-Mock) Provider-Stellvertreter: ``fetch_forecast()``
    wirft immer eine Exception, die NICHT von
    ``SegmentWeatherService.fetch_segment_weather()`` abgefangen wird (dort
    wird nur ``ProviderRequestError`` abgefangen und in eine
    ``SegmentWeatherData(has_error=True)`` uebersetzt) -- ein ``TimeoutError``
    erreicht also echt den ``except Exception``-Block in
    ``fetch_night_weather()``, genau wie ein realer Netz-/Kontingentfehler."""

    name = "throwing-test-double"

    def fetch_forecast(self, location, start=None, end=None,
                        enrich_ensemble=True, enrich_snow=True):
        raise TimeoutError("simulated network timeout fetching night weather")


def _meta():
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )


def _dp(hour: int):
    return ForecastDataPoint(
        ts=datetime(2026, 7, 20, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=5.0, gust_kmh=5.0, precip_1h_mm=0.0,
        pop_pct=0, cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )


def _last_segment(arrival_hour: int = 15):
    """Letzte Etappe, angekommen um ``arrival_hour`` UTC -- mit NICHT-leerer
    Zeitreihe, damit der Bug (Fallback bei vorhandenen Daten) ueberhaupt
    greifen kann."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=datetime(2026, 7, 20, arrival_hour - 4, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 20, arrival_hour, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=200.0, descent_m=0.0,
    )
    data = [_dp(h) for h in range(arrival_hour - 4, arrival_hour + 1)]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(temp_min_c=10.0, temp_max_c=20.0),
        fetched_at=datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


class TestFetchNightWeatherProviderFailureReturnsNone:
    """AC-1: Providerfehler -> ``None``, NICHT die Zeitreihe der letzten
    Etappe."""

    def test_provider_error_returns_none_not_last_segment_timeseries(self):
        last_segment = _last_segment()

        result = fetch_night_weather(last_segment, provider=_ThrowingProvider())

        assert result is None, (
            f"Erwartet None bei Abruf-Fehler, erhalten: {result!r} -- "
            "der stille Fallback auf last_segment.timeseries liegt noch vor "
            "(Bug #1339)"
        )
        # Explizite Wert-Ungleichheit (nicht nur Identitaet): selbst wenn
        # result nicht None waere, duerften die Datenpunkte NICHT mit denen
        # der letzten Etappe uebereinstimmen (Segment-Start-Geografie
        # statt Ziel-Nachtwetter).
        assert result != last_segment.timeseries, (
            "result darf NIE gleich last_segment.timeseries sein -- das "
            "waere exakt der falsche Fallback (Segment-Start statt Ziel)"
        )


class TestFetchNightWeatherFailureFlowsThroughRealRenderPath:
    """AC-2: Wirkung an der Stelle, an der sie zaehlt -- das ``None``-
    Ergebnis muss ueber ``compute_has_gap()`` in
    ``TripReportFormatter.format_email()`` zu einem echten
    Unsicherheitsmarker fuehren (SMS ``TH:?`` oder Klartext-``?``), NICHT zu
    einer positiven Entwarnung."""

    def test_provider_failure_shows_uncertainty_marker_not_false_all_clear(self):
        from output.renderers.trip_report import TripReportFormatter

        segments = [_last_segment(arrival_hour=12)]  # Ankunft 12:00 -> Luecke moeglich
        tz = ZoneInfo("UTC")

        night_weather = fetch_night_weather(segments[0], provider=_ThrowingProvider())
        assert night_weather is None, "Vorbedingung: Providerfehler muss None liefern (AC-1)"

        has_gap = compute_has_gap(segments, night_weather, tz)
        assert has_gap is True, (
            "Vorbedingung: fehlendes Nacht-Wetter am Ziel muss als echte "
            "Luecke erkannt werden"
        )

        report = TripReportFormatter().format_email(
            segments, trip_name="E1", report_type="morning",
            stage_name="E1", tz=tz, has_gap=has_gap,
        )

        assert "TH:?" in report.sms_text, f"SMS zeigt keinen Unsicherheitsmarker: {report.sms_text}"
        assert "kein Gewitter" not in report.email_plain, (
            f"Klartext-Mail zeigt Fehl-Entwarnung trotz Abruf-Fehler:\n{report.email_plain}"
        )
        assert "?" in report.email_plain, f"Klartext-Mail ohne Unsicherheitsmarker:\n{report.email_plain}"


class TestFetchNightWeatherFailureIsConsistentAcrossCallers:
    """AC-3: Versandpfad (Scheduler-Delegator) und Vorschau-Pfad (direkter
    Aufruf mit ``provider=``) muessen bei demselben Fehlerfall BEIDE
    ``None`` liefern -- kein Divergenzrisiko zwischen den zwei Aufrufern
    derselben geteilten Funktion."""

    def test_scheduler_delegator_returns_none_on_provider_error(self, monkeypatch):
        """Versandpfad: ``TripReportSchedulerService._fetch_night_weather()``
        nimmt keinen ``provider``-Parameter entgegen -- sie loest ihn intern
        ueber ``get_provider("openmeteo")`` auf (Live-Pfad). Um denselben
        Fehlerfall wie AC-1 ohne echten Netzzugriff zu erzeugen, wird die
        Aufloesung per ``monkeypatch`` (kein Mock/patch/MagicMock) durch den
        werfenden Provider-Stellvertreter ersetzt -- exakt das Muster aus
        ``tests/unit/test_preview_night_block.py``."""
        import providers.base as providers_base
        from services.trip_report_scheduler import TripReportSchedulerService

        monkeypatch.setattr(
            providers_base, "get_provider", lambda name: _ThrowingProvider()
        )

        last_segment = _last_segment()
        result = TripReportSchedulerService()._fetch_night_weather(last_segment)

        assert result is None, (
            f"Scheduler-Delegator lieferte {result!r} statt None bei "
            "Providerfehler -- Bug #1339 (Fallback auf letzte Etappe)"
        )

    def test_preview_style_direct_call_returns_none_on_provider_error(self):
        """Vorschau-Pfad: direkter Aufruf mit explizitem ``provider=``, wie
        ``preview_service.py:217`` es tut."""
        last_segment = _last_segment()

        result = fetch_night_weather(last_segment, provider=_ThrowingProvider())

        assert result is None, (
            f"Direkter Aufruf (Vorschau-Muster) lieferte {result!r} statt "
            "None bei Providerfehler -- Bug #1339"
        )

    def test_both_callers_agree_on_the_same_failure(self, monkeypatch):
        """Beide Aufrufer MUESSEN beim selben Fehlerfall dasselbe Ergebnis
        (None) liefern -- kein Divergenzrisiko."""
        import providers.base as providers_base
        from services.trip_report_scheduler import TripReportSchedulerService

        monkeypatch.setattr(
            providers_base, "get_provider", lambda name: _ThrowingProvider()
        )

        last_segment = _last_segment()
        scheduler_result = TripReportSchedulerService()._fetch_night_weather(last_segment)
        preview_result = fetch_night_weather(last_segment, provider=_ThrowingProvider())

        assert scheduler_result is None
        assert preview_result is None
        assert scheduler_result == preview_result
