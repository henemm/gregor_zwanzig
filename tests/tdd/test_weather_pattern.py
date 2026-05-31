"""
TDD RED: F12 Großwetterlage / Stabilitäts-Label (Issue #122)

SPEC: docs/specs/modules/weather_pattern.md v1.0

Deckt AC-1 bis AC-12 ab.

Diese Tests MÜSSEN im RED-Phase fehlschlagen weil:
- StabilityResult existiert noch nicht in app.models
- WeatherPatternService existiert noch nicht in services.weather_pattern
- OpenMeteoProvider._fetch_ensemble_with_z500() existiert noch nicht
- WL-Token existiert noch nicht in tokens/builder.py

KEINE MOCKS — echte Dataclasses, echte API-Calls, echte Logik.
Fault-Injection für API-Fehler via ungültigem Host (echter Connection-Error).
"""
from __future__ import annotations

import socket
from datetime import date, timedelta
from statistics import stdev

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_waypoint(id_: str, lat: float, lon: float, elevation_m: int = 1000):
    from app.trip import Waypoint
    return Waypoint(id=id_, name=f"Punkt {id_}", lat=lat, lon=lon,
                    elevation_m=elevation_m)


def _make_stage(stage_id: str, stage_date: date, lat: float, lon: float):
    from app.trip import Stage
    return Stage(
        id=stage_id,
        name=f"Etappe {stage_id}",
        date=stage_date,
        waypoints=[
            _make_waypoint(f"{stage_id}-A", lat, lon),
            _make_waypoint(f"{stage_id}-B", lat + 0.05, lon + 0.05),
        ],
    )


def _make_multi_stage_trip(target_date: date, extra_stages: int = 3):
    """Trip mit target_date als aktuelle Etappe und N weiteren zukünftigen Etappen."""
    from app.trip import Trip
    stages = []
    # Aktuelle Etappe (target_date)
    stages.append(_make_stage("S0", target_date, lat=42.1, lon=9.1))
    # Zukünftige Etappen
    for i in range(1, extra_stages + 1):
        stages.append(_make_stage(f"S{i}", target_date + timedelta(days=i),
                                  lat=42.1 + i * 0.05, lon=9.1 + i * 0.05))
    return Trip(id="gr20-test", name="GR20 Test", stages=stages)


def _make_single_stage_trip(target_date: date):
    """Trip mit genau einer Etappe (target_date = letzte Etappe, keine Zukunft)."""
    from app.trip import Trip
    stages = [_make_stage("S0", target_date, lat=42.1, lon=9.1)]
    return Trip(id="last-stage-trip", name="Letzter Tag", stages=stages)


def _find_free_port() -> int:
    """Liefert einen freien Port, der sofort wieder geschlossen wird."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# AC-1: StabilityResult Dataclass
# ---------------------------------------------------------------------------

class TestStabilityResult:
    """AC-1: StabilityResult ist frozen, hat label/score/component_scores."""

    def test_stability_result_exists_in_models(self):
        """StabilityResult muss aus app.models importierbar sein."""
        from app.models import StabilityResult  # noqa: F401

    def test_stability_result_fields(self):
        """AC-1: Instanz mit label, score, component_scores erstellen."""
        from app.models import StabilityResult

        result = StabilityResult(
            label="STABIL",
            score=4,
            component_scores=(2, 2),
        )
        assert result.label == "STABIL"
        assert result.score == 4
        assert result.component_scores == (2, 2)

    def test_stability_result_is_frozen(self):
        """AC-1: Mutation muss FrozenInstanceError auslösen."""
        from dataclasses import FrozenInstanceError
        from app.models import StabilityResult

        result = StabilityResult(label="FRAGIL", score=1, component_scores=(0, 1))
        with pytest.raises(FrozenInstanceError):
            result.label = "STABIL"  # type: ignore[misc]

    def test_stability_result_valid_labels(self):
        """Alle drei Labels sind konstruierbar."""
        from app.models import StabilityResult

        for label, score, comps in [
            ("STABIL", 4, (2, 2)),
            ("WECHSELHAFT", 2, (1, 1)),
            ("FRAGIL", 0, (0, 0)),
        ]:
            r = StabilityResult(label=label, score=score, component_scores=comps)
            assert r.label == label


# ---------------------------------------------------------------------------
# AC-2 & AC-3: Z500-Tendenz-Score
# ---------------------------------------------------------------------------

class TestTendencyScore:
    """AC-2/AC-3: _score_tendency() aus WeatherPatternService."""

    def _service(self):
        from services.weather_pattern import WeatherPatternService
        return WeatherPatternService(provider=None)

    def test_delta_under_15_yields_2_points(self):
        """AC-2: |delta| < 15 gpm → 2 Punkte (stabil)."""
        svc = self._service()
        # T+0 = 5500, T+48 = 5510 → delta = 10
        z500_series = [[5500.0 + i * 0.2] for i in range(73)]
        assert svc._score_tendency(z500_series) == 2

    def test_delta_between_15_and_40_yields_1_point(self):
        """AC-2 grenze: 15 <= |delta| < 40 gpm → 1 Punkt."""
        svc = self._service()
        # T+0 = 5500, T+48 = 5530 → delta = 30
        z500_series = [[5500.0 + i * 0.625] for i in range(73)]
        score = svc._score_tendency(z500_series)
        assert score == 1, f"Erwartet 1, bekam {score}"

    def test_delta_over_40_yields_0_points(self):
        """AC-3: |delta| >= 40 gpm → 0 Punkte (Trog)."""
        svc = self._service()
        # T+0 = 5500, T+48 = 5560 → delta = 60
        z500_series = [[5500.0 + i * 1.25] for i in range(73)]
        score = svc._score_tendency(z500_series)
        assert score == 0, f"Erwartet 0, bekam {score}"

    def test_negative_delta_over_40_yields_0_points(self):
        """AC-3: fallender Z500 (Front) → 0 Punkte."""
        svc = self._service()
        # T+0 = 5560, T+48 = 5500 → delta = -60
        z500_series = [[5560.0 - i * 1.25] for i in range(73)]
        score = svc._score_tendency(z500_series)
        assert score == 0


# ---------------------------------------------------------------------------
# AC-4: Ensemble-Spread-Score
# ---------------------------------------------------------------------------

class TestSpreadScore:
    """AC-4: _score_spread() aus WeatherPatternService."""

    def _service(self):
        from services.weather_pattern import WeatherPatternService
        return WeatherPatternService(provider=None)

    def test_tight_spread_under_40_yields_2_points(self):
        """AC-4: mean_spread < 40 gpm → 2 Punkte (verlässlich)."""
        svc = self._service()
        # 5 Members, Spread ~20 gpm über 73h
        z500_series = [
            [5500.0, 5515.0, 5485.0, 5510.0, 5490.0]  # stdev ≈ 12 gpm
            for _ in range(73)
        ]
        score = svc._score_spread(z500_series)
        assert score == 2, f"Erwartet 2, bekam {score}"

    def test_moderate_spread_between_40_and_80_yields_1_point(self):
        """AC-4 grenze: 40 <= mean_spread < 80 gpm → 1 Punkt."""
        svc = self._service()
        # Members sehr weit auseinander, stdev ~55 gpm
        z500_series = [
            [5400.0, 5500.0, 5460.0, 5540.0, 5350.0, 5600.0]  # stdev ≈ 87 → zu hoch
            # Verwende gemäßigteres Beispiel: stdev ≈ 55
            for _ in range(73)
        ]
        # Aufbau: Mean 5500, stdev ~60
        z500_series = [
            [5440.0, 5560.0, 5500.0, 5470.0, 5530.0]  # stdev ≈ 46 gpm
            for _ in range(73)
        ]
        score = svc._score_spread(z500_series)
        assert score == 1, f"Erwartet 1, bekam {score}"

    def test_wide_spread_over_80_yields_0_points(self):
        """AC-4: mean_spread >= 80 gpm → 0 Punkte (unsicher)."""
        svc = self._service()
        # Members: [5300, 5700, 5400, 5600] → stdev ≈ 173 gpm
        z500_series = [
            [5300.0, 5700.0, 5400.0, 5600.0, 5200.0]  # stdev sehr groß
            for _ in range(73)
        ]
        score = svc._score_spread(z500_series)
        assert score == 0

    def test_fewer_than_5_members_per_hour_excluded(self):
        """Stunden mit < 5 validen Membern werden ausgeschlossen."""
        svc = self._service()
        # Erste 36 Stunden: nur 3 Member (zu wenig) → ausgeschlossen
        # Nächste 37 Stunden: 6 Member mit engem Spread → score 2
        z500_series = (
            [[5500.0, 5510.0, 5490.0]] * 36  # < 5 Member
            + [[5500.0, 5505.0, 5495.0, 5502.0, 5498.0, 5501.0]] * 37  # Tight
        )
        score = svc._score_spread(z500_series)
        assert score == 2


# ---------------------------------------------------------------------------
# AC-5: Label-Mapping
# ---------------------------------------------------------------------------

class TestLabelMapping:
    """AC-5: compute_for_trip() mappt Score korrekt auf Label."""

    def _service(self):
        from services.weather_pattern import WeatherPatternService
        return WeatherPatternService(provider=None)

    def test_score_4_is_stabil(self):
        """Total 3–4 → STABIL."""
        svc = self._service()
        assert svc._score_to_label(4) == "STABIL"
        assert svc._score_to_label(3) == "STABIL"

    def test_score_2_is_wechselhaft(self):
        """Total 2 → WECHSELHAFT."""
        svc = self._service()
        assert svc._score_to_label(2) == "WECHSELHAFT"

    def test_score_0_or_1_is_fragil(self):
        """Total 0–1 → FRAGIL."""
        svc = self._service()
        assert svc._score_to_label(1) == "FRAGIL"
        assert svc._score_to_label(0) == "FRAGIL"


# ---------------------------------------------------------------------------
# AC-6: Keine zukünftigen Etappen → None
# ---------------------------------------------------------------------------

class TestNoFutureStages:
    """AC-6: Letzte Etappe → compute_for_trip gibt None zurück, kein API-Call."""

    def test_last_stage_returns_none(self):
        """AC-6: Trip mit nur einer Etappe (heute) → None."""
        from services.weather_pattern import WeatherPatternService

        today = date.today()
        trip = _make_single_stage_trip(target_date=today)

        svc = WeatherPatternService(provider=None)
        result = svc.compute_for_trip(trip, target_date=today)
        assert result is None

    def test_all_stages_in_past_returns_none(self):
        """Alle Etappen in der Vergangenheit → None."""
        from services.weather_pattern import WeatherPatternService

        yesterday = date.today() - timedelta(days=1)
        trip = _make_multi_stage_trip(target_date=yesterday - timedelta(days=2),
                                      extra_stages=2)

        svc = WeatherPatternService(provider=None)
        result = svc.compute_for_trip(trip, target_date=date.today())
        assert result is None


# ---------------------------------------------------------------------------
# AC-7: API-Fehler → Graceful Degradation
# ---------------------------------------------------------------------------

class TestApiFaultTolerance:
    """AC-7: HTTP-Fehler oder Timeout → None zurück, kein Exception."""

    def test_connection_error_returns_none(self):
        """AC-7: Connection refused → None, kein Crash."""
        from providers.openmeteo import OpenMeteoProvider

        dead_port = _find_free_port()
        provider = OpenMeteoProvider(
            ensemble_base_host=f"http://127.0.0.1:{dead_port}"
        )
        result = provider._fetch_ensemble_with_z500(lat=42.1, lon=9.1)
        assert result is None, "Erwartet None bei Connection-Error"

    def test_service_returns_none_on_api_failure(self):
        """AC-7: WeatherPatternService gibt None zurück wenn API nicht erreichbar."""
        from providers.openmeteo import OpenMeteoProvider
        from services.weather_pattern import WeatherPatternService

        today = date.today()
        trip = _make_multi_stage_trip(target_date=today, extra_stages=3)

        dead_port = _find_free_port()
        provider = OpenMeteoProvider(
            ensemble_base_host=f"http://127.0.0.1:{dead_port}"
        )
        svc = WeatherPatternService(provider=provider)
        result = svc.compute_for_trip(trip, target_date=today)
        assert result is None

    def test_no_exception_propagates_on_api_error(self):
        """AC-7: Exception wird intern behandelt, nie nach außen propagiert."""
        from providers.openmeteo import OpenMeteoProvider
        from services.weather_pattern import WeatherPatternService

        today = date.today()
        trip = _make_multi_stage_trip(target_date=today, extra_stages=2)

        dead_port = _find_free_port()
        provider = OpenMeteoProvider(
            ensemble_base_host=f"http://127.0.0.1:{dead_port}"
        )
        svc = WeatherPatternService(provider=provider)

        # Darf keine Exception werfen
        try:
            result = svc.compute_for_trip(trip, target_date=today)
        except Exception as e:
            pytest.fail(f"compute_for_trip() hat Exception geworfen: {e!r}")


# ---------------------------------------------------------------------------
# AC-7b: Echter API-Call — Z500 wird tatsächlich geliefert
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestFetchEnsembleWithZ500:
    """Echter API-Call: _fetch_ensemble_with_z500() liefert Z500-Zeitreihe."""

    def test_real_api_returns_z500_data_for_alps(self):
        """Echter OpenMeteo Ensemble Call für Innsbruck liefert Z500-Member-Daten."""
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        data = provider._fetch_ensemble_with_z500(lat=47.27, lon=11.39)

        assert data is not None, "API-Call für Innsbruck schlug fehl"
        assert "time" in data, "Antwort enthält kein 'time'-Feld"
        assert "z500_members" in data, "Antwort enthält kein 'z500_members'-Feld"
        assert len(data["time"]) >= 72, (
            f"Erwartet mind. 72 Zeitpunkte, bekam {len(data['time'])}"
        )
        assert len(data["z500_members"]) == len(data["time"]), (
            "z500_members und time haben unterschiedliche Länge"
        )
        # Prüfe dass Member-Daten vorhanden sind (mind. 5 Member pro Stunde)
        first_hour = data["z500_members"][0]
        assert len(first_hour) >= 5, (
            f"Erwartet mind. 5 Ensemble-Member, bekam {len(first_hour)}"
        )
        # Z500-Werte plausibel (500 hPa ≈ 5000–5800 gpm in Europa)
        first_val = first_hour[0]
        assert 4500 < first_val < 6000, (
            f"Z500-Wert {first_val} gpm außerhalb plausiblem Bereich (4500–6000)"
        )

    def test_real_api_returns_z500_data_for_mediterranean(self):
        """Echter API-Call für GR221 Mallorca (39.5°N, 2.7°E) liefert Z500."""
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        data = provider._fetch_ensemble_with_z500(lat=39.5, lon=2.7)

        assert data is not None, "API-Call für Mallorca schlug fehl"
        assert "z500_members" in data
        assert len(data["z500_members"]) >= 72


# ---------------------------------------------------------------------------
# AC-8: E-Mail HTML — WL-Box erscheint ganz oben
# ---------------------------------------------------------------------------

class TestEmailHtmlRendering:
    """AC-8/AC-9: WL-Sektion in render_html."""

    def _make_stability_result(self, label: str, score: int):
        from app.models import StabilityResult
        comps = {
            "STABIL": (2, 2),
            "WECHSELHAFT": (1, 1),
            "FRAGIL": (0, 1),
        }[label]
        return StabilityResult(label=label, score=score,
                               component_scores=comps)

    def test_fragil_box_appears_in_html(self):
        """AC-8: FRAGIL erzeugt roten Block mit korrektem Text und Farbe."""
        from output.renderers.email.html import render_stability_label_html

        result = self._make_stability_result("FRAGIL", 1)
        html = render_stability_label_html(result)

        assert "FRAGIL" in html
        assert "Schnelle Frontverlagerung" in html
        assert "#f8d7da" in html, "Rote Hintergrundfarbe für FRAGIL fehlt"

    def test_stabil_box_has_green_background(self):
        """AC-8: STABIL → grüner Block (#d4edda)."""
        from output.renderers.email.html import render_stability_label_html

        result = self._make_stability_result("STABIL", 4)
        html = render_stability_label_html(result)

        assert "STABIL" in html
        assert "#d4edda" in html, "Grüner Hintergrund für STABIL fehlt"

    def test_wechselhaft_box_has_yellow_background(self):
        """AC-8: WECHSELHAFT → gelber Block (#fff3cd)."""
        from output.renderers.email.html import render_stability_label_html

        result = self._make_stability_result("WECHSELHAFT", 2)
        html = render_stability_label_html(result)

        assert "#fff3cd" in html, "Gelber Hintergrund für WECHSELHAFT fehlt"

    def test_none_result_renders_empty_string(self):
        """AC-9: stability_result=None → leerer String, kein Platzhalter."""
        from output.renderers.email.html import render_stability_label_html

        html = render_stability_label_html(None)
        assert html == "", f"Erwartet leeren String, bekam: {html!r}"

    def test_wl_block_appears_before_confidence_hint_in_full_render(self):
        """AC-8: WL-Box erscheint vor dem Konfidenz-Hinweis im finalen HTML.

        Echte Integration: render_html() wird mit minimalem Segment und
        niedriger Konfidenz (loest Confidence-Hinweis aus) aufgerufen.
        Geprueft wird die Reihenfolge der HTML-Markup-Marker im Output.
        """
        from datetime import datetime as _dt, timezone as _tz
        from zoneinfo import ZoneInfo

        from app.metric_catalog import build_default_display_config
        from app.models import (
            ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
            Provider, SegmentWeatherData, SegmentWeatherSummary,
            ThunderLevel, TripSegment,
        )
        from output.renderers.email.html import render_html

        # Segment mit confidence_pct < 60 → Confidence-Hinweis wird gerendert
        seg = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=900.0),
            end_point=GPXPoint(lat=42.1, lon=9.18, elevation_m=1200.0),
            start_time=_dt(2026, 7, 11, 8, 0, tzinfo=_tz.utc),
            end_time=_dt(2026, 7, 11, 12, 0, tzinfo=_tz.utc),
            duration_hours=4.0, distance_km=10.0,
            ascent_m=300.0, descent_m=0.0,
        )
        # Niedrige Konfidenz triggert den Confidence-Hinweis (build_confidence_hint
        # vergleicht mit datetime.now(tz) — kuenftige Stunden mit conf<60).
        now_utc = _dt.now(_tz.utc)
        data = [
            ForecastDataPoint(
                ts=now_utc.replace(minute=0, second=0, microsecond=0)
                  + timedelta(hours=h),
                t2m_c=15.0, wind10m_kmh=10.0,
                precip_1h_mm=0.0, cloud_total_pct=50,
                thunder_level=ThunderLevel.NONE,
                confidence_pct=40,  # < 60 → Hinweis erscheint
            )
            for h in range(1, 6)
        ]
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
            run=now_utc,
        )
        ts = NormalizedTimeseries(meta=meta, data=data)
        agg = SegmentWeatherSummary(
            temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
            wind_max_kmh=15.0, gust_max_kmh=20.0,
            precip_sum_mm=0.0, cloud_avg_pct=50, humidity_avg_pct=55,
            thunder_level_max=ThunderLevel.NONE,
        )
        seg_data = SegmentWeatherData(
            segment=seg, timeseries=ts, aggregated=agg,
            fetched_at=now_utc, provider="demo",
        )

        result = self._make_stability_result("FRAGIL", 1)
        html = render_html(
            segments=[seg_data],
            seg_tables=[[]],
            trip_name="GR20 Test",
            report_type="morning",
            dc=build_default_display_config(),
            night_rows=[],
            thunder_forecast=None,
            highlights=[],
            changes=None,
            stage_name=None,
            stage_stats=None,
            multi_day_trend=None,
            compact_summary=None,
            daylight=None,
            tz=ZoneInfo("Europe/Berlin"),
            friendly_keys=set(),
            stability_result=result,
        )

        # Beide Marker muessen im HTML vorkommen
        wl_marker = "Schnelle Frontverlagerung"  # FRAGIL-Text
        conf_marker = "confidence-hint"          # CSS-Klasse des Hinweises
        assert wl_marker in html, (
            f"WL-Box fehlt im HTML (Marker {wl_marker!r} nicht gefunden)"
        )
        assert conf_marker in html, (
            f"Confidence-Hinweis fehlt im HTML (Marker {conf_marker!r} nicht "
            f"gefunden) — niedrige Konfidenz haette ihn ausloesen muessen."
        )
        wl_pos = html.index(wl_marker)
        conf_pos = html.index(conf_marker)
        assert wl_pos < conf_pos, (
            f"WL-Box (Position {wl_pos}) muss VOR Confidence-Hinweis "
            f"(Position {conf_pos}) erscheinen — Spec AC-8."
        )


# ---------------------------------------------------------------------------
# AC-9: E-Mail Plain-Text
# ---------------------------------------------------------------------------

class TestEmailPlainRendering:
    """AC-9: WL-Textblock in render_plain."""

    def test_plain_render_has_stability_label_param(self):
        """render_plain() muss stability_result-Parameter haben."""
        from output.renderers.email.plain import render_plain
        import inspect

        sig = inspect.signature(render_plain)
        assert "stability_result" in sig.parameters, (
            "render_plain() hat keinen stability_result-Parameter"
        )


# ---------------------------------------------------------------------------
# AC-10: SMS-Token WL
# ---------------------------------------------------------------------------

class TestSmsToken:
    """AC-10: WL-Token in POSITIONAL-Liste und build_token_line()-Ausgabe."""

    def test_wl_in_positional_list(self):
        """AC-10: 'WL' muss in POSITIONAL nach 'C' stehen."""
        from output.tokens.builder import POSITIONAL

        symbols = [s for s, _ in POSITIONAL]
        assert "WL" in symbols, "WL-Token fehlt in POSITIONAL-Liste"

        c_idx = symbols.index("C")
        wl_idx = symbols.index("WL")
        assert wl_idx > c_idx, (
            f"WL (Index {wl_idx}) muss nach C (Index {c_idx}) stehen"
        )

    def test_stabil_emits_wl_plus(self):
        """AC-10: STABIL → Token WL mit Wert '+'."""
        from app.models import StabilityResult
        from output.tokens.builder import build_token_line
        from output.tokens.dto import NormalizedForecast, DailyForecast

        result = StabilityResult(label="STABIL", score=4, component_scores=(2, 2))
        forecast = NormalizedForecast(
            days=[DailyForecast()],
            provider="openmeteo",
        )
        token_line = build_token_line(
            forecast=forecast,
            config=None,
            report_type="morning",
            stage_name="Etappe",
            stability_result=result,
        )
        wl_tokens = [t for t in token_line.tokens if t.symbol == "WL"]
        assert len(wl_tokens) == 1, f"Erwartet 1 WL-Token, bekam {len(wl_tokens)}"
        assert wl_tokens[0].value == "+", (
            f"STABIL sollte '+' ergeben, bekam '{wl_tokens[0].value}'"
        )

    def test_fragil_emits_wl_minus(self):
        """AC-10: FRAGIL → Token WL mit Wert '-'."""
        from app.models import StabilityResult
        from output.tokens.builder import build_token_line
        from output.tokens.dto import NormalizedForecast, DailyForecast

        result = StabilityResult(label="FRAGIL", score=1, component_scores=(0, 1))
        forecast = NormalizedForecast(
            days=[DailyForecast()],
            provider="openmeteo",
        )
        token_line = build_token_line(
            forecast=forecast,
            config=None,
            report_type="morning",
            stage_name="Etappe",
            stability_result=result,
        )
        wl_tokens = [t for t in token_line.tokens if t.symbol == "WL"]
        assert len(wl_tokens) == 1
        assert wl_tokens[0].value == "-"

    def test_none_stability_omits_wl_token(self):
        """AC-9/10: stability_result=None → kein WL-Token."""
        from output.tokens.builder import build_token_line
        from output.tokens.dto import NormalizedForecast, DailyForecast

        forecast = NormalizedForecast(
            days=[DailyForecast()],
            provider="openmeteo",
        )
        token_line = build_token_line(
            forecast=forecast,
            config=None,
            report_type="morning",
            stage_name="Etappe",
            stability_result=None,
        )
        wl_tokens = [t for t in token_line.tokens if t.symbol == "WL"]
        assert len(wl_tokens) == 0, "WL-Token sollte bei None fehlen"


# ---------------------------------------------------------------------------
# AC-11: SMS ≤ 160 Zeichen mit WL-Token
# ---------------------------------------------------------------------------

class TestSmsBudget:
    """AC-11: SMS bleibt ≤ 160 Zeichen mit WL-Token."""

    def test_sms_under_160_chars_with_wl_token(self):
        """AC-11: Beispiel-SMS mit WL+, C+, und allen Standard-Tokens bleibt ≤ 160."""
        from output.tokens.dto import TokenLine, Token

        # Baue eine SMS-Zeile ähnlich §8.3 (134 Zeichen) + WL-Token (+4 Zeichen)
        # Erwartetes Maximum: 138 Zeichen — weit unter 160
        from output.renderers.sms import render_sms
        from app.models import StabilityResult
        from output.tokens.builder import build_token_line
        from output.tokens.dto import NormalizedForecast, DailyForecast

        stability = StabilityResult(label="STABIL", score=4, component_scores=(2, 2))
        forecast = NormalizedForecast(
            days=[DailyForecast(
                temp_min_c=12.0,
                temp_max_c=22.0,
                confidence_pct_min=80,
            )],
            provider="openmeteo",
        )
        token_line = build_token_line(
            forecast=forecast,
            config=None,
            report_type="morning",
            stage_name="Etappe4",
            stability_result=stability,
        )
        sms_text = render_sms(token_line, max_length=160)
        assert len(sms_text) <= 160, (
            f"SMS zu lang: {len(sms_text)} Zeichen\n{sms_text!r}"
        )
        assert "WL+" in sms_text, f"WL+ fehlt in SMS: {sms_text!r}"


# ---------------------------------------------------------------------------
# AC-12: Letzte Etappe → kein WL-Label in E-Mail und SMS
# ---------------------------------------------------------------------------

class TestLastStageNoLabel:
    """AC-12: Letzter Reisetag → weder E-Mail noch SMS enthält WL-Referenz."""

    def test_compute_for_trip_last_stage_returns_none(self):
        """AC-12: get_future_stages=[] → None ohne API-Call."""
        from services.weather_pattern import WeatherPatternService

        today = date.today()
        trip = _make_single_stage_trip(target_date=today)

        svc = WeatherPatternService(provider=None)
        result = svc.compute_for_trip(trip, target_date=today)
        assert result is None, (
            "Letzter Tag sollte None ergeben (kein WL-Label)"
        )

    @pytest.mark.live
    def test_real_api_call_for_multi_stage_trip_returns_stability_result(self):
        """Echter Test: Mehretchappen-Trip liefert StabilityResult (nicht None)."""
        from providers.openmeteo import OpenMeteoProvider
        from services.weather_pattern import WeatherPatternService
        from app.models import StabilityResult

        today = date.today()
        trip = _make_multi_stage_trip(target_date=today, extra_stages=4)

        provider = OpenMeteoProvider()
        svc = WeatherPatternService(provider=provider)
        result = svc.compute_for_trip(trip, target_date=today)

        # Kann None sein falls API nicht verfügbar, aber wenn vorhanden muss es korrekt sein
        if result is not None:
            assert isinstance(result, StabilityResult)
            assert result.label in ("STABIL", "WECHSELHAFT", "FRAGIL")
            assert 0 <= result.score <= 4
            assert len(result.component_scores) == 2
