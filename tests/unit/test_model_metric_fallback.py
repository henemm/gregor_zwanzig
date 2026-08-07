"""
Unit tests for WEATHER-05b: Model-Metric-Fallback.

Four test classes, 11 tests total, all deterministic without network:
1. TestForecastMetaFallbackFields -- ForecastMeta has fallback tracking fields
2. TestFindFallbackModel -- _find_fallback_model selects correct fallback
   (reads a local JSON cache via monkeypatch/tmp_path, no HTTP)
3. TestMergeFallback -- _merge_fallback fills None fields without overwriting
   (pure in-memory)
4. TestFooterFallbackInfo -- TripReportFormatter().format_email renders
   fallback info (pure rendering, no HTTP)

SPEC: docs/specs/modules/model_metric_fallback.md v1.0
SPEC: docs/specs/modules/rework_1302_merge_contract_extraction.md (AC-4)
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
)


# ---------------------------------------------------------------------------
# Wortlaut (Issue #1492 Scheibe 2b, PO-freigegeben)
# SPEC: docs/specs/modules/feat_1492_s2b_fallback_sichtbarkeit.md
# ---------------------------------------------------------------------------

# Kollisionsfall (R3): die Gewitterzeile nennt KEINEN Quellennamen, weil
# `fallback_model` dann bereits vom Grundvorhersage-Fallback belegt ist.
_GEWITTER_OHNE_QUELLE = "Gewitterdaten von einer Ersatzquelle (gröbere Auflösung)"
# R4: die Klammer traegt die Metrikliste OHNE die Gewitter-Feldnamen.
_WETTER_ICON_EU = (
    "Einzelne Wetterwerte von Ersatzmodell: DWD Europa (Gewitterenergie, Sicht)"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_meta(model: str = "meteofrance_arome") -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model=model,
        run=datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3,
        interp="grid_point",
    )


def _make_dp(hour: int, cape: float | None = None, visibility: float | None = None) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 2, 17, hour, 0, tzinfo=timezone.utc),
        t2m_c=10.0,
        wind10m_kmh=15.0,
        gust_kmh=25.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        humidity_pct=60,
        cape_jkg=cape,
        visibility_m=visibility,
    )


def _make_timeseries(model: str = "meteofrance_arome", cape: float | None = None, visibility: float | None = None) -> NormalizedTimeseries:
    meta = _make_meta(model)
    data = [_make_dp(h, cape=cape, visibility=visibility) for h in range(8, 11)]
    return NormalizedTimeseries(meta=meta, data=data)


# ---------------------------------------------------------------------------
# Test 1: ForecastMeta fallback fields
# ---------------------------------------------------------------------------

class TestForecastMetaFallbackFields:
    """ForecastMeta must have fallback tracking fields."""

    def test_fallback_model_field_exists(self) -> None:
        meta = _make_meta()
        assert hasattr(meta, 'fallback_model')
        assert meta.fallback_model is None

    def test_fallback_metrics_field_exists(self) -> None:
        meta = _make_meta()
        assert hasattr(meta, 'fallback_metrics')
        assert meta.fallback_metrics == []

    def test_fallback_fields_settable(self) -> None:
        meta = _make_meta()
        meta.fallback_model = "icon_eu"
        meta.fallback_metrics = ["cape", "visibility"]
        assert meta.fallback_model == "icon_eu"
        assert len(meta.fallback_metrics) == 2


# ---------------------------------------------------------------------------
# Test 2: _find_fallback_model
# ---------------------------------------------------------------------------

class TestFindFallbackModel:
    """_find_fallback_model must select the right fallback."""

    def test_finds_fallback_for_arome_coords(self, tmp_path, monkeypatch) -> None:
        """AROME at Mallorca should fall back to ICON-EU or ECMWF."""
        import providers.openmeteo as om
        fake_cache = tmp_path / "model_availability.json"
        monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", fake_cache)

        from providers.openmeteo import OpenMeteoProvider

        # Write a fake cache with AROME missing cape, icon_eu having it
        cache = {
            "probe_date": date.today().isoformat(),
            "models": {
                "meteofrance_arome": {"available": ["temperature_2m"], "unavailable": ["cape", "visibility"]},
                "icon_eu": {"available": ["temperature_2m", "cape", "visibility"], "unavailable": []},
                "ecmwf_ifs04": {"available": ["temperature_2m", "cape"], "unavailable": ["visibility"]},
            }
        }
        fake_cache.write_text(json.dumps(cache))

        provider = OpenMeteoProvider()
        result = provider._find_fallback_model("meteofrance_arome", 39.7, 2.6, ["cape", "visibility"])

        assert result is not None
        fb_model_id, fb_grid_res_km, fb_endpoint = result
        # Should pick icon_eu (has both cape AND visibility, lower priority than ecmwf)
        assert fb_model_id == "icon_eu"

    def test_returns_none_without_cache(self, tmp_path, monkeypatch) -> None:
        """No cache → no fallback."""
        import providers.openmeteo as om
        # Point to non-existent file — no .unlink() on real path!
        monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", tmp_path / "model_availability.json")

        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        result = provider._find_fallback_model("meteofrance_arome", 39.7, 2.6, ["cape"])

        assert result is None


# ---------------------------------------------------------------------------
# Test 3: _merge_fallback
# ---------------------------------------------------------------------------

class TestMergeFallback:
    """_merge_fallback must fill None fields without overwriting."""

    def test_fills_none_fields(self) -> None:
        from providers.openmeteo import OpenMeteoProvider

        primary = _make_timeseries(cape=None, visibility=None)
        fallback = _make_timeseries(model="icon_eu", cape=500.0, visibility=10000.0)

        provider = OpenMeteoProvider()
        filled = provider._merge_fallback(primary, fallback, ["cape", "visibility"])

        assert "cape" in filled
        assert primary.data[0].cape_jkg == 500.0

    def test_does_not_overwrite_existing(self) -> None:
        from providers.openmeteo import OpenMeteoProvider

        primary = _make_timeseries(cape=200.0, visibility=None)
        fallback = _make_timeseries(model="icon_eu", cape=500.0, visibility=10000.0)

        provider = OpenMeteoProvider()
        provider._merge_fallback(primary, fallback, ["cape", "visibility"])

        # cape was 200 in primary — must NOT be overwritten
        assert primary.data[0].cape_jkg == 200.0
        # visibility was None — must be filled
        assert primary.data[0].visibility_m == 10000.0


# ---------------------------------------------------------------------------
# Test 4: Footer rendering
# ---------------------------------------------------------------------------

class TestFooterFallbackInfo:
    """Footer must show fallback info when present."""

    def _make_segment_data(
        self, fallback_model=None, fallback_metrics=None, fallback_reason=None,
        segment_id=1, with_timeseries=True, has_error=False,
    ):
        """Helper to create a SegmentWeatherData with fallback meta.

        ``fallback_reason`` (Issue #1492 Scheibe 2b): unterscheidet die
        Gewitter-Vertretung (``thunder_source_unavailable``) vom
        Grundvorhersage-Fallback (``metric_gap``/``model_5xx``) — R1 der Spec
        `feat_1492_s2b_fallback_sichtbarkeit.md` haengt daran, welche der
        beiden Zeilen erscheint.
        """
        from app.models import SegmentWeatherData, SegmentWeatherSummary, TripSegment, GPXPoint

        today = date.today()
        meta = _make_meta()
        meta.fallback_model = fallback_model
        meta.fallback_metrics = fallback_metrics or []
        meta.fallback_reason = fallback_reason

        ts = NormalizedTimeseries(meta=meta, data=[_make_dp(8)]) if with_timeseries else None
        seg = TripSegment(
            segment_id=segment_id,
            start_point=GPXPoint(lat=39.7, lon=2.6, elevation_m=100.0),
            end_point=GPXPoint(lat=39.8, lon=2.7, elevation_m=200.0),
            start_time=datetime(today.year, today.month, today.day, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(today.year, today.month, today.day, 10, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            distance_km=5.0,
            ascent_m=100.0,
            descent_m=0.0,
        )
        return SegmentWeatherData(
            segment=seg,
            timeseries=ts,
            aggregated=SegmentWeatherSummary(
                temp_min_c=10.0, temp_max_c=12.0, wind_max_kmh=15.0,
                gust_max_kmh=25.0, precip_sum_mm=0.0, cloud_avg_pct=50,
            ),
            fetched_at=datetime.now(timezone.utc),
            provider="openmeteo",
            has_error=has_error,
        )

    def _alle_vier_ausgaben(self, segments) -> dict:
        """HTML-, Plain-, Kompakt-Mail und Telegram-Langform fuer DENSELBEN
        Trip — echte Renderer-Aufrufe, kein Mock."""
        from app.models import TripReportConfig
        from output.renderers.trip_report import TripReportFormatter

        full = TripReportFormatter().format_email(segments, "Test Trip", "morning")
        compact = TripReportFormatter().format_email(
            segments, "Test Trip", "morning",
            report_config=TripReportConfig(email_format="compact"),
        )
        overview = [b for b in full.telegram_bubbles if "Kurz" in b]
        assert overview, "Kurzuebersicht-Bubble nicht gefunden"
        return {
            "html": full.email_html,
            "plain": full.email_plain,
            "compact": compact.email_plain,
            "telegram": overview[0],
        }

    def test_html_footer_shows_fallback(self) -> None:
        """Issue #1492 S2b AC-1/AC-4: Die HTML-Vollversion zeigt den
        Herkunftshinweis in deutschem Klartext.

        Umgestellt vom technischen Bestandswortlaut (`"fallback" in html` +
        Rohkennung `"icon_eu"`) auf den PO-freigegebenen Wortlaut. Das Segment
        traegt zusaetzlich einen Gewitter-Feldnamen, damit BEIDE Zeilen
        geprueft werden (Kollisionsfall, R3: die Gewitterzeile nennt dabei
        keinen Quellennamen).
        """
        from output.renderers.trip_report import TripReportFormatter

        seg = self._make_segment_data(
            fallback_model="icon_eu",
            fallback_metrics=["cape", "visibility", "lightning_potential_lpi_jkg"],
            fallback_reason="model_5xx",
        )
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test Trip", "morning")
        html = report.email_html

        assert _GEWITTER_OHNE_QUELLE in html, (
            f"AC-1: Gewitterzeile fehlt im HTML-Body:\n{html[-1500:]}"
        )
        assert _WETTER_ICON_EU in html, (
            f"AC-4: Wetterzeile in Klartext fehlt im HTML-Body:\n{html[-1500:]}"
        )
        assert "icon_eu" not in html, "AC-4: Rohkennung 'icon_eu' bleibt sichtbar"
        assert "Fallback" not in html, "AC-4: technisches Wort 'Fallback' bleibt sichtbar"

    def test_plain_footer_shows_fallback(self) -> None:
        """Issue #1492 S2b AC-1/AC-4: dasselbe fuer die Plaintext-Vollversion."""
        from output.renderers.trip_report import TripReportFormatter

        seg = self._make_segment_data(
            fallback_model="icon_eu",
            fallback_metrics=["cape", "visibility", "lightning_potential_lpi_jkg"],
            fallback_reason="model_5xx",
        )
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test Trip", "morning")
        plain = report.email_plain

        assert _GEWITTER_OHNE_QUELLE in plain, (
            f"AC-1: Gewitterzeile fehlt im Text-Body:\n{plain[-1500:]}"
        )
        assert _WETTER_ICON_EU in plain, (
            f"AC-4: Wetterzeile in Klartext fehlt im Text-Body:\n{plain[-1500:]}"
        )
        assert "icon_eu" not in plain, "AC-4: Rohkennung 'icon_eu' bleibt sichtbar"
        assert "Fallback" not in plain, "AC-4: technisches Wort 'Fallback' bleibt sichtbar"

    def test_footer_empty_metrics_no_colon_artifact(self) -> None:
        """#1145 (Zusicherung erhalten, Wortlaut eingedeutscht): leere
        `fallback_metrics` duerfen kein `' : '`- oder Klammer-Artefakt
        erzeugen. Nach R4 entfaellt die Klammer ersatzlos."""
        from output.renderers.trip_report import TripReportFormatter

        seg = self._make_segment_data(
            fallback_model="icon_eu", fallback_metrics=[], fallback_reason="model_5xx",
        )
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test Trip", "morning")

        for name, body in (("html", report.email_html), ("plain", report.email_plain)):
            assert "Einzelne Wetterwerte von Ersatzmodell: DWD Europa" in body, (
                f"{name}: Wetterzeile in Klartext fehlt:\n{body[-1500:]}"
            )
            assert "icon_eu" not in body, f"{name}: Rohkennung 'icon_eu' sichtbar"
            assert " : " not in body, f"{name}: #1145-Artefakt ' : ' vorhanden"
            assert "Ersatzmodell: ()" not in body, f"{name}: leere Klammer"
            assert "DWD Europa ()" not in body, f"{name}: leere Klammer"

    def test_no_fallback_no_hint(self) -> None:
        """AC-6 Regelfall: ohne jeden Fallback erscheint KEINE Herkunfts-/
        Ersatzzeile.

        Bewusst auf die DEUTSCHEN Begriffe umgestellt: die alte Assertion
        (`"fallback" not in body.lower()`) koennte nach der Eindeutschung
        nicht mehr scheitern — das Wort kommt im neuen Text ohnehin nie vor.
        Ein Test, der nicht scheitern KANN, bewacht nichts. Geprueft wird
        deshalb, dass weder 'Ersatzquelle' noch 'Ersatzmodell' noch ein
        Quellen-Klartextname auftaucht.
        """
        from output.renderers.trip_report import TripReportFormatter

        seg = self._make_segment_data(fallback_model=None)
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test Trip", "morning")

        for name, body in (("html", report.email_html), ("plain", report.email_plain)):
            assert "Ersatzquelle" not in body, (
                f"{name}: Gewitter-Ersatzzeile ohne Fallback:\n{body[-1500:]}"
            )
            assert "Ersatzmodell" not in body, (
                f"{name}: Wetter-Ersatzzeile ohne Fallback:\n{body[-1500:]}"
            )
            assert "DWD Europa" not in body, (
                f"{name}: Quellen-Klartextname ohne Fallback:\n{body[-1500:]}"
            )
            assert "fallback" not in body.lower(), (
                f"{name}: technischer Bestandshinweis ohne Fallback:\n{body[-1500:]}"
            )

    # -- Issue #1492 S2b: bisher ungedeckte Ausgaben ------------------------

    def test_compact_footer_shows_fallback(self) -> None:
        """AC-2: Given ein Segment mit gesetztem `fallback_model`, When die
        KOMPAKT-Mail gerendert wird, Then enthaelt der Body die deutsche
        Wetterzeile.

        Heute (RED): die Kompakt-Mail zeigt gar keinen Hinweis — 0 Treffer
        (Kontext-Doc „Der Hinweis erscheint heute in 2 von 7 Ausgaben").
        `render_compact` faltet den Body per `fold_ascii()` auf reines ASCII,
        deshalb wird die Erwartung mit derselben Produktionsfunktion gefaltet
        statt eine zweite Schreibweise zu erfinden.
        """
        from app.models import TripReportConfig
        from output.renderers.trip_report import TripReportFormatter
        from utils.ascii_fold import fold_ascii

        seg = self._make_segment_data(
            fallback_model="icon_eu",
            fallback_metrics=["cape", "visibility"],
            fallback_reason="model_5xx",
        )
        report = TripReportFormatter().format_email(
            [seg], "Test Trip", "morning",
            report_config=TripReportConfig(email_format="compact"),
        )
        body = report.email_plain

        assert report.email_html == "", "Kompakt-Format darf keinen HTML-Body liefern"
        assert fold_ascii(_WETTER_ICON_EU) in body, (
            f"AC-2: Kompakt-Mail zeigt keine Herkunfts-Klartextzeile:\n{body[-800:]}"
        )
        assert "icon_eu" not in body, "AC-2/AC-4: Rohkennung in der Kompakt-Mail"

    def test_sms_stays_free_of_fallback_notice(self) -> None:
        """AC-7: Given DASSELBE Segment, das in AC-1/AC-5 den Hinweis erzeugt,
        When die SMS gerendert wird, Then enthaelt der SMS-Text weder
        'Ersatzquelle' noch 'Ersatzmodell' noch einen Quellen-Klartextnamen,
        und bleibt <= 160 Zeichen.

        Strukturell erfuellt (die Kurzform sendet `report.sms_text`, laeuft
        also nie durch `narrow.py`/`_tg_day_footer`) — dieser Test bewacht,
        dass die Umsetzung der drei Langform-Ausgaben das nicht aufweicht.
        Kein Dateiinhalt-Check: geprueft wird der ECHT gerenderte SMS-Text.
        """
        from output.renderers.trip_report import TripReportFormatter

        seg = self._make_segment_data(
            fallback_model="icon_eu",
            fallback_metrics=["cape", "visibility", "lightning_potential_lpi_jkg"],
            fallback_reason="model_5xx",
        )
        sms = TripReportFormatter().format_email([seg], "Test Trip", "morning").sms_text

        assert "Ersatzquelle" not in sms, f"AC-7: Fallback-Hinweis in der SMS: {sms!r}"
        assert "Ersatzmodell" not in sms, f"AC-7: Fallback-Hinweis in der SMS: {sms!r}"
        assert "DWD Europa" not in sms, f"AC-7: Quellenname in der SMS: {sms!r}"
        assert "Gewitterdaten" not in sms, f"AC-7: Gewitterzeile in der SMS: {sms!r}"
        assert len(sms) <= 160, f"AC-7: SMS-Budget gesprengt ({len(sms)} Zeichen): {sms!r}"

    def test_same_core_wording_in_html_plain_compact_and_telegram(self) -> None:
        """AC-10: Given derselbe Fallback-Zustand (Kollision), When HTML-Mail,
        Plain-Mail, Kompakt-Mail und Telegram-Langform fuer DASSELBE Segment
        gerendert werden, Then tragen alle vier denselben Kern-Wortlaut —
        nur die Verpackung unterscheidet sich.

        Vergleich auf normalisierter Ebene (Zeilenumbrueche gefaltet, ASCII
        gefaltet), weil Telegram bei 56 Zeichen umbricht und die Kompakt-Mail
        per `fold_ascii()` Umlaute aufloest. Beides ist Verpackung, nicht
        Wortlaut. Die Erwartung stammt aus der geteilten Funktion selbst —
        damit prueft der Test genau die Zusicherung „EIN Modul, drei
        Verpackungen" statt vier handgeschriebener Zeichenketten.
        """
        from app.models import TripReportConfig
        from output.renderers.fallback_notice import build_fallback_lines
        from output.renderers.trip_report import TripReportFormatter
        from utils.ascii_fold import fold_ascii

        def _norm(text: str) -> str:
            return " ".join(fold_ascii(text).split())

        seg = self._make_segment_data(
            fallback_model="icon_eu",
            fallback_metrics=["cape", "visibility", "lightning_potential_lpi_jkg"],
            fallback_reason="model_5xx",
        )
        expected = build_fallback_lines(seg.timeseries.meta)
        assert len(expected) == 2, (
            f"Vorbedingung: der Kollisionsfall muss zwei Zeilen liefern — war {expected!r}"
        )

        full = TripReportFormatter().format_email([seg], "Test Trip", "morning")
        compact = TripReportFormatter().format_email(
            [seg], "Test Trip", "morning",
            report_config=TripReportConfig(email_format="compact"),
        )
        overview = [b for b in full.telegram_bubbles if "Kurz" in b]
        assert overview, "Kurzuebersicht-Bubble nicht gefunden"

        ausgaben = {
            "html": full.email_html,
            "plain": full.email_plain,
            "compact": compact.email_plain,
            "telegram": overview[0],
        }
        for name, body in ausgaben.items():
            haystack = _norm(body)
            for line in expected:
                # L4: ANZAHL statt blossem Vorkommen. Ein doppelt gerenderter
                # Hinweis waere fuer den Nutzer sichtbar, wurde aber von keinem
                # Test gefangen — `in` findet den Wortlaut auch beim zweiten
                # Mal. Gemessen: `+ fallback_row + fallback_row` in html.py
                # liess alle Tests gruen. Geprueft wird deshalb `== 1` und
                # nicht `>= 1`; das deckt „fehlt" und „doppelt" zugleich ab.
                treffer = haystack.count(_norm(line))
                assert treffer == 1, (
                    f"AC-10: '{line}' erscheint {treffer}x in der Ausgabe "
                    f"'{name}' — erwartet genau einmal (0 = die vier Ausgaben "
                    f"tragen nicht denselben Kern-Wortlaut, >1 = der Hinweis "
                    f"steht doppelt in der Nutzer-Ausgabe).\n"
                    f"Ausgabe (Ende):\n{body[-900:]}"
                )

    # -- F001: Mehrsegment-Trips — die Vertretung kann eine SPAETERE Etappe
    #    betreffen. Vorher las die Mail starr `segments[0]`, Telegram das
    #    erste fehlerfreie Segment — beide verschwiegen den Fall still
    #    (ADR-0018/ADR-0047: Fallback ohne Kaschieren).

    def test_multi_segment_fallback_after_broken_first_segment(self) -> None:
        """F001: Given Segment 1 hat einen Provider-Fehler (keine Zeitreihe)
        und Segment 2 traegt einen echten Fallback, When alle vier Ausgaben
        gerendert werden, Then zeigen ALLE VIER die Klartext-Wetterzeile.

        Vorher: Telegram zeigte sie, HTML/Plain/Kompakt nicht.
        """
        from utils.ascii_fold import fold_ascii

        segments = [
            self._make_segment_data(segment_id=1, with_timeseries=False, has_error=True),
            self._make_segment_data(
                segment_id=2, fallback_model="icon_eu",
                fallback_metrics=["cape", "visibility"], fallback_reason="model_5xx",
            ),
        ]

        for name, body in self._alle_vier_ausgaben(segments).items():
            haystack = " ".join(fold_ascii(body).split())
            assert " ".join(fold_ascii(_WETTER_ICON_EU).split()) in haystack, (
                f"F001: '{name}' verschweigt die Vertretung aus Segment 2, "
                f"obwohl Segment 1 nur einen Abruffehler hat.\n{body[-900:]}"
            )

    def test_multi_segment_fallback_after_clean_first_segment(self) -> None:
        """F001: Given Segment 1 ist fehlerfrei UND ohne Fallback, Segment 2
        traegt einen Fallback, When alle vier Ausgaben gerendert werden, Then
        zeigen ALLE VIER die Klartext-Wetterzeile.

        Das ist der Fall, den BEIDE frueheren Auswahlregeln verschluckt haben
        — `segments[0]` ebenso wie „erstes fehlerfreies Segment".
        """
        from utils.ascii_fold import fold_ascii

        segments = [
            self._make_segment_data(segment_id=1),
            self._make_segment_data(
                segment_id=2, fallback_model="icon_eu",
                fallback_metrics=["cape", "visibility"], fallback_reason="model_5xx",
            ),
        ]

        for name, body in self._alle_vier_ausgaben(segments).items():
            haystack = " ".join(fold_ascii(body).split())
            assert " ".join(fold_ascii(_WETTER_ICON_EU).split()) in haystack, (
                f"F001: '{name}' verschweigt die Vertretung aus Segment 2.\n{body[-900:]}"
            )

    def test_multi_segment_thunder_fallback_in_later_segment(self) -> None:
        """F001/AC-1: Dasselbe fuer die GEWITTER-Vertretung — sie zeigt sich
        allein in `fallback_metrics` (R2) und darf in keiner der vier
        Ausgaben verschwinden, nur weil sie eine spaetere Etappe betrifft."""
        from utils.ascii_fold import fold_ascii

        segments = [
            self._make_segment_data(segment_id=1),
            self._make_segment_data(
                segment_id=2, fallback_model="eu_direct",
                fallback_metrics=["lightning_potential_lpi_jkg"],
                fallback_reason="thunder_source_unavailable",
            ),
        ]
        erwartet = "Gewitterdaten von Ersatzquelle: DWD Europa (gröbere Auflösung)"

        for name, body in self._alle_vier_ausgaben(segments).items():
            haystack = " ".join(fold_ascii(body).split())
            assert " ".join(fold_ascii(erwartet).split()) in haystack, (
                f"F001: '{name}' verschweigt die Gewitter-Vertretung aus "
                f"Segment 2.\n{body[-900:]}"
            )

    def test_multi_segment_without_fallback_shows_nothing(self) -> None:
        """F001 GEGENPROBE: Given KEIN Segment traegt eine Vertretung (eines
        davon mit Abruffehler), When alle vier Ausgaben gerendert werden, Then
        erscheint nirgends eine Ersatz-Zeile — die erweiterte Suche darf nicht
        zum Dauer-Hinweis werden."""
        segments = [
            self._make_segment_data(segment_id=1),
            self._make_segment_data(segment_id=2, with_timeseries=False, has_error=True),
            self._make_segment_data(segment_id=3),
        ]

        for name, body in self._alle_vier_ausgaben(segments).items():
            assert "Ersatzquelle" not in body, f"{name}: Ersatzzeile ohne Fallback"
            assert "Ersatzmodell" not in body, f"{name}: Ersatzzeile ohne Fallback"
            assert "DWD Europa" not in body, f"{name}: Quellenname ohne Fallback"
