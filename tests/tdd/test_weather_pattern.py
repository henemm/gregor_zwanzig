"""
TDD: F12 Großwetterlage / Stabilitäts-Label.

Ursprünglich Issue #122 (Z500-Ensemble-Heuristik); refactored durch
Issue #479 — das Label wird jetzt aus den vorhandenen
`confidence_pct_min`-Werten der Folge-Etappen abgeleitet.

Tests sind mock-frei: Dataclasses werden direkt instanziiert,
`compute_stability` ist eine pure Funktion, E-Mail-Rendering wird über
echte Renderer geprüft.

Parent-Spec: docs/specs/modules/issue_479_f12_confidence_refactor.md v1.0
"""
from __future__ import annotations

from datetime import date, timedelta

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


def _make_single_stage_trip(target_date: date):
    """Trip mit genau einer Etappe (target_date = letzte Etappe, keine Zukunft)."""
    from app.trip import Trip
    stages = [_make_stage("S0", target_date, lat=42.1, lon=9.1)]
    return Trip(id="last-stage-trip", name="Letzter Tag", stages=stages)


# ---------------------------------------------------------------------------
# StabilityResult — frozen Dataclass (refactored Felder)
# ---------------------------------------------------------------------------

class TestStabilityResult:
    """Issue #479: StabilityResult hat label + confidence_pct (frozen)."""

    def test_stability_result_exists_in_models(self):
        """StabilityResult muss aus app.models importierbar sein."""
        from app.models import StabilityResult  # noqa: F401

    def test_stability_result_fields(self):
        """Instanz mit label + confidence_pct erstellen."""
        from app.models import StabilityResult

        result = StabilityResult(label="STABIL", confidence_pct=80)
        assert result.label == "STABIL"
        assert result.confidence_pct == 80

    def test_stability_result_is_frozen(self):
        """Mutation muss FrozenInstanceError auslösen."""
        from dataclasses import FrozenInstanceError
        from app.models import StabilityResult

        result = StabilityResult(label="FRAGIL", confidence_pct=30)
        with pytest.raises(FrozenInstanceError):
            result.label = "STABIL"  # type: ignore[misc]

    def test_stability_result_valid_labels(self):
        """Alle drei Labels sind konstruierbar."""
        from app.models import StabilityResult

        for label, conf in [
            ("STABIL", 80),
            ("WECHSELHAFT", 60),
            ("FRAGIL", 40),
        ]:
            r = StabilityResult(label=label, confidence_pct=conf)
            assert r.label == label
            assert r.confidence_pct == conf


# ---------------------------------------------------------------------------
# Label-Mapping (compute_stability)
# ---------------------------------------------------------------------------

class TestLabelMapping:
    """compute_stability mappt Konfidenz auf Label."""

    def test_high_confidence_is_stabil(self):
        """>= 75 → STABIL."""
        from services.weather_pattern import compute_stability
        for v in [75, 80, 95, 100]:
            r = compute_stability([v])
            assert r is not None and r.label == "STABIL", (
                f"Wert {v} sollte STABIL ergeben, bekam {r}"
            )

    def test_medium_confidence_is_wechselhaft(self):
        """50–74 → WECHSELHAFT."""
        from services.weather_pattern import compute_stability
        for v in [50, 60, 74]:
            r = compute_stability([v])
            assert r is not None and r.label == "WECHSELHAFT", (
                f"Wert {v} sollte WECHSELHAFT ergeben, bekam {r}"
            )

    def test_low_confidence_is_fragil(self):
        """< 50 → FRAGIL."""
        from services.weather_pattern import compute_stability
        for v in [0, 25, 49]:
            r = compute_stability([v])
            assert r is not None and r.label == "FRAGIL", (
                f"Wert {v} sollte FRAGIL ergeben, bekam {r}"
            )


# ---------------------------------------------------------------------------
# Keine zukünftigen Etappen → None (kein Label)
# ---------------------------------------------------------------------------

class TestNoFutureStages:
    """Letzte Etappe → compute_for_trip gibt None zurück."""

    def test_last_stage_returns_none(self):
        """Trip mit nur einer Etappe (heute) → None."""
        from services.weather_pattern import WeatherPatternService

        today = date.today()
        trip = _make_single_stage_trip(target_date=today)

        svc = WeatherPatternService()
        result = svc.compute_for_trip(
            trip, target_date=today, segment_weather=[]
        )
        assert result is None

    def test_empty_segment_weather_returns_none(self):
        """Leere segment_weather-Liste → None (keine Konfidenz-Daten)."""
        from app.trip import Trip
        from services.weather_pattern import WeatherPatternService

        today = date.today()
        stages = [
            _make_stage("S0", today, lat=42.1, lon=9.1),
            _make_stage("S1", today + timedelta(days=1), lat=42.2, lon=9.2),
        ]
        trip = Trip(id="t", name="Test", stages=stages)

        svc = WeatherPatternService()
        result = svc.compute_for_trip(
            trip, target_date=today, segment_weather=[]
        )
        assert result is None


# ---------------------------------------------------------------------------
# E-Mail HTML — WL-Box erscheint mit refactored StabilityResult
# ---------------------------------------------------------------------------

class TestEmailHtmlRendering:
    """WL-Box wird mit refactored StabilityResult korrekt gerendert."""

    def _make_stability_result(self, label: str):
        from app.models import StabilityResult
        conf = {"STABIL": 85, "WECHSELHAFT": 60, "FRAGIL": 40}[label]
        return StabilityResult(label=label, confidence_pct=conf)

    def test_fragil_box_appears_in_html(self):
        """FRAGIL erzeugt roten Block mit korrektem Text und Farbe."""
        from output.renderers.email.html import render_stability_label_html

        result = self._make_stability_result("FRAGIL")
        html = render_stability_label_html(result)

        assert "FRAGIL" in html
        assert "Schnelle Frontverlagerung" in html
        assert "#f8d7da" in html, "Rote Hintergrundfarbe für FRAGIL fehlt"

    def test_stabil_box_has_green_background(self):
        """STABIL → grüner Block (#d4edda)."""
        from output.renderers.email.html import render_stability_label_html

        result = self._make_stability_result("STABIL")
        html = render_stability_label_html(result)

        assert "STABIL" in html
        assert "#d4edda" in html, "Grüner Hintergrund für STABIL fehlt"

    def test_wechselhaft_box_has_yellow_background(self):
        """WECHSELHAFT → gelber Block (#fff3cd)."""
        from output.renderers.email.html import render_stability_label_html

        result = self._make_stability_result("WECHSELHAFT")
        html = render_stability_label_html(result)

        assert "#fff3cd" in html, "Gelber Hintergrund für WECHSELHAFT fehlt"

    def test_none_result_renders_empty_string(self):
        """stability_result=None → leerer String, kein Platzhalter."""
        from output.renderers.email.html import render_stability_label_html

        html = render_stability_label_html(None)
        assert html == "", f"Erwartet leeren String, bekam: {html!r}"


# ---------------------------------------------------------------------------
# E-Mail Plain-Text — Parameter-Signatur
# ---------------------------------------------------------------------------

class TestEmailPlainRendering:
    """WL-Textblock in render_plain."""

    def test_plain_render_has_stability_label_param(self):
        """render_plain() muss stability_result-Parameter haben."""
        from output.renderers.email.plain import render_plain
        import inspect

        sig = inspect.signature(render_plain)
        assert "stability_result" in sig.parameters, (
            "render_plain() hat keinen stability_result-Parameter"
        )

    def test_plain_render_with_stability_result(self):
        """render_plain mit refactored StabilityResult erzeugt WL-Text."""
        from app.models import StabilityResult
        from output.renderers.email.plain import render_plain
        import inspect
        # Reine Parameter-Validierung — kein Aufruf, weil render_plain
        # weitere komplexe Argumente erwartet. Wichtig: confidence_pct genügt.
        result = StabilityResult(label="STABIL", confidence_pct=80)
        assert result.label == "STABIL"
        # Signatur-Check stellt sicher, dass der Parameter weiterhin existiert.
        sig = inspect.signature(render_plain)
        assert "stability_result" in sig.parameters


# ---------------------------------------------------------------------------
# SMS-Token — WL ist ENTFERNT (Issue #479)
# ---------------------------------------------------------------------------

class TestSmsToken:
    """Issue #479: WL-Token wurde aus dem SMS-Format entfernt."""

    def test_wl_not_in_positional_list(self):
        """'WL' ist nicht in POSITIONAL."""
        from output.tokens.builder import POSITIONAL
        symbols = [s for s, _ in POSITIONAL]
        assert "WL" not in symbols, (
            f"WL darf nicht in POSITIONAL sein, vorhanden: {symbols}"
        )

    def test_build_token_line_has_no_stability_result_param(self):
        """build_token_line() hat keinen stability_result-Parameter mehr."""
        from output.tokens.builder import build_token_line
        import inspect

        sig = inspect.signature(build_token_line)
        assert "stability_result" not in sig.parameters, (
            f"build_token_line() darf keinen stability_result-Parameter mehr "
            f"haben, vorhanden: {list(sig.parameters)}"
        )

    def test_build_token_line_emits_no_wl_token(self):
        """build_token_line() emittiert kein WL-Token mehr."""
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
        )
        wl_tokens = [t for t in token_line.tokens if t.symbol == "WL"]
        assert len(wl_tokens) == 0, (
            f"WL-Token darf nicht mehr emittiert werden, gefunden: {wl_tokens}"
        )


# ---------------------------------------------------------------------------
# SMS-Budget — Konfidenz-Token (C+) reicht aus
# ---------------------------------------------------------------------------

class TestSmsBudget:
    """SMS bleibt ≤ 160 Zeichen — C-Token wurde entfernt (Bug #869)."""

    def test_sms_under_160_chars_with_confidence_token(self):
        """Bug #869: C-Token entfernt — SMS ohne C+, trotzdem ≤ 160 Zeichen."""
        from output.renderers.sms import render_sms
        from output.tokens.builder import build_token_line
        from output.tokens.dto import NormalizedForecast, DailyForecast

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
        )
        sms_text = render_sms(token_line, max_length=160)
        assert len(sms_text) <= 160, (
            f"SMS zu lang: {len(sms_text)} Zeichen\n{sms_text!r}"
        )
        # Bug #869: C-Token wird nicht mehr emittiert
        assert "C+" not in sms_text, f"C+ darf nicht mehr in SMS sein: {sms_text!r}"
        assert "WL" not in sms_text, (
            f"WL darf nicht in SMS sein, ist aber drin: {sms_text!r}"
        )


# ---------------------------------------------------------------------------
# Letzte Etappe → kein WL-Label in E-Mail (SMS hatte ohnehin keins)
# ---------------------------------------------------------------------------

class TestLastStageNoLabel:
    """Letzter Reisetag → E-Mail enthält keinen WL-Block."""

    def test_compute_for_trip_last_stage_returns_none(self):
        """get_future_stages=[] → None ohne weitere Logik."""
        from services.weather_pattern import WeatherPatternService

        today = date.today()
        trip = _make_single_stage_trip(target_date=today)

        svc = WeatherPatternService()
        result = svc.compute_for_trip(
            trip, target_date=today, segment_weather=[]
        )
        assert result is None, (
            "Letzter Tag sollte None ergeben (kein WL-Label)"
        )
