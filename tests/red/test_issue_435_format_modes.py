"""
TDD RED — Issue #435 Metrik-Format-Modi (Roh/Skala/Vereinfacht/Symbol).

SPEC: docs/specs/modules/issue_435_metric_format_modes.md (AC-1..AC-10)
CONTEXT: docs/context/issue-435-metric-format-modes.md

Diese Tests scheitern, weil das Feature noch nicht implementiert ist:
    - MetricDefinition kennt format_modes / default_format_mode noch nicht
    - MetricConfig hat noch kein format_mode-Feld
    - loader._resolve_format_mode() existiert noch nicht
    - Schreib-Pfade speichern nur use_friendly_format
    - fmt_val() verzweigt am bool, nicht am String-Mode
    - Wind-Dir-Merge an use_friendly_format gekoppelt, nicht an scale
    - Token-Builder kennt nur use_friendly_format
    - _build_friendly_keys ist noch in zwei Stellen dupliziert

NO MOCKS — echte DTOs, echter FastAPI TestClient, echte Renderer-Aufrufe,
echte Source-Datei-Inspektion via ast.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest



# ---------------------------------------------------------------------------
# Shared helpers (parallel zu tests/integration/test_friendly_format_email_and_alerts.py)
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)


def _make_segment(segment_id: int = 1):
    from app.models import GPXPoint, TripSegment

    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1200.0),
        start_time=_NOW,
        end_time=_NOW + timedelta(hours=2),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=200.0,
        descent_m=0.0,
    )


def _make_meta():
    from app.models import ForecastMeta, Provider

    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=_NOW,
        grid_res_km=1.0,
        interp="point_grid",
    )


def _make_dp(
    *,
    hour: int = 10,
    temp: float = 15.0,
    wind: float = 12.0,
    gust: float = 25.0,
    precip: float = 0.0,
    cloud: float = 50.0,
    cape: float = 800.0,
    visibility: float = 5000.0,
    humidity: float = 65.0,
    wind_chill: float = 10.0,
    pressure: float = 1013.0,
    dewpoint: float = 8.0,
    pop: float = 30.0,
    uv_index: float | None = None,
    wind_dir_deg: float | None = 180.0,
):
    from app.models import ForecastDataPoint, ThunderLevel

    kwargs = dict(
        ts=_NOW.replace(hour=hour),
        t2m_c=temp,
        wind10m_kmh=wind,
        gust_kmh=gust,
        precip_1h_mm=precip,
        cloud_total_pct=cloud,
        cape_jkg=cape,
        visibility_m=visibility,
        thunder_level=ThunderLevel.NONE,
        humidity_pct=humidity,
        wind_chill_c=wind_chill,
        pressure_msl_hpa=pressure,
        dewpoint_c=dewpoint,
        pop_pct=pop,
        uv_index=uv_index,
    )
    # Optional wind direction (best effort — if field exists in DTO)
    try:
        return ForecastDataPoint(**kwargs, wind_dir_deg=wind_dir_deg)  # type: ignore[arg-type]
    except TypeError:
        return ForecastDataPoint(**kwargs)


def _make_summary(
    *,
    temp_max: float = 18.0,
    wind_max: float = 20.0,
    gust_max: float = 30.0,
    precip_sum: float = 0.0,
    cloud_avg: float = 50.0,
    cape_max: float = 800.0,
    visibility_min: float = 5000.0,
    humidity_avg: float = 65.0,
    wind_chill_min: float = 8.0,
    pressure_avg: float = 1013.0,
    dewpoint_avg: float = 8.0,
    pop_max: float = 30.0,
    uv_index_max: float | None = None,
    freezing_level: float = 2500.0,
    snow_depth: float = 0.0,
    wind_dir_deg_avg: float | None = 180.0,
):
    from app.models import SegmentWeatherSummary, ThunderLevel

    kwargs = dict(
        temp_min_c=temp_max - 5,
        temp_max_c=temp_max,
        temp_avg_c=temp_max - 2.5,
        wind_max_kmh=wind_max,
        gust_max_kmh=gust_max,
        precip_sum_mm=precip_sum,
        cloud_avg_pct=cloud_avg,
        cape_max_jkg=cape_max,
        visibility_min_m=visibility_min,
        thunder_level_max=ThunderLevel.NONE,
        humidity_avg_pct=humidity_avg,
        wind_chill_min_c=wind_chill_min,
        pressure_avg_hpa=pressure_avg,
        dewpoint_avg_c=dewpoint_avg,
        pop_max_pct=pop_max,
        uv_index_max=uv_index_max,
        freezing_level_m=freezing_level,
        snow_depth_cm=snow_depth,
    )
    try:
        return SegmentWeatherSummary(**kwargs, wind_dir_deg_avg=wind_dir_deg_avg)  # type: ignore[arg-type]
    except TypeError:
        return SegmentWeatherSummary(**kwargs)


def _make_segment_weather(
    segment_id: int = 1,
    summary=None,
    dp_kwargs: dict | None = None,
):
    from app.models import NormalizedTimeseries, SegmentWeatherData

    seg = _make_segment(segment_id)
    dp = _make_dp(**(dp_kwargs or {}))
    ts = NormalizedTimeseries(meta=_make_meta(), data=[dp])
    agg = summary or _make_summary()
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=agg,
        fetched_at=_NOW,
        provider="openmeteo",
    )


# ===========================================================================
# AC-1: Katalog liefert format_modes pro Metrik
# ===========================================================================

class TestAC1CatalogFormatModes:
    """
    GIVEN der /metrics-Endpoint wird aufgerufen
    WHEN eine Metrik mit Friendly-Render existiert (cloud_total)
    THEN enthält Response format_modes-Liste und default_format_mode-String.
    """

    def test_ac1_catalog_endpoint_returns_format_modes_per_metric(self):
        """AC-1: /metrics-Endpoint exponiert format_modes + default_format_mode."""
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        resp = client.get("/metrics")
        assert resp.status_code == 200, f"Unerwarteter Status: {resp.status_code}"

        catalog = resp.json()
        # cloud_total in der Atmosphere/Sky-Kategorie suchen
        cloud_total = None
        for cat_metrics in catalog.values():
            for entry in cat_metrics:
                if entry.get("id") == "cloud_total":
                    cloud_total = entry
                    break
            if cloud_total:
                break

        assert cloud_total is not None, "cloud_total nicht im /metrics-Output"
        assert "format_modes" in cloud_total, (
            "AC-1 RED: Feld 'format_modes' fehlt im /metrics-Endpoint"
        )
        assert "default_format_mode" in cloud_total, (
            "AC-1 RED: Feld 'default_format_mode' fehlt im /metrics-Endpoint"
        )
        assert cloud_total["format_modes"] == ["raw", "symbol"], (
            f"AC-1: cloud_total muss format_modes=['raw','symbol'] haben, "
            f"war {cloud_total['format_modes']}"
        )
        assert cloud_total["default_format_mode"] == "symbol", (
            f"AC-1: cloud_total muss default_format_mode='symbol' haben, "
            f"war {cloud_total['default_format_mode']}"
        )

    def test_ac1_catalog_definition_has_format_modes_field(self):
        """AC-1 (Backend-Pfad): MetricDefinition trägt format_modes als Tuple."""
        from app.metric_catalog import get_metric

        # Cloud → ("raw","symbol"), default symbol
        cloud = get_metric("cloud_total")
        assert hasattr(cloud, "format_modes"), (
            "AC-1 RED: MetricDefinition hat kein Feld 'format_modes'"
        )
        assert hasattr(cloud, "default_format_mode"), (
            "AC-1 RED: MetricDefinition hat kein Feld 'default_format_mode'"
        )
        assert tuple(cloud.format_modes) == ("raw", "symbol")
        assert cloud.default_format_mode == "symbol"

        # Wind-Direction → ("raw","scale"), default scale
        wdir = get_metric("wind_direction")
        assert tuple(wdir.format_modes) == ("raw", "scale")
        assert wdir.default_format_mode == "scale"

        # Visibility → ("raw",), default raw (Issue #819: numerisch-only, kein Einfach-Modus)
        vis = get_metric("visibility")
        assert tuple(vis.format_modes) == ("raw",)
        assert vis.default_format_mode == "raw"

        # Temperature → ("raw",), default raw (keine andere Option)
        temp = get_metric("temperature")
        assert tuple(temp.format_modes) == ("raw",)
        assert temp.default_format_mode == "raw"


# ===========================================================================
# AC-3: Loader-Read-Adapter resolved Legacy use_friendly_format
# ===========================================================================

class TestAC3LoaderResolveFormatMode:
    """
    GIVEN bestehende MetricConfig mit use_friendly_format=true und ohne format_mode
    WHEN _resolve_format_mode den Modus auflöst
    THEN landet er auf dem Katalog-default_format_mode der Metrik.
    """

    def test_ac3_loader_resolves_legacy_use_friendly_format_to_catalog_default(self):
        """AC-3: use_friendly_format=True → Katalog-Default (symbol/scale/simplified)."""
        from app import loader

        assert hasattr(loader, "_resolve_format_mode"), (
            "AC-3 RED: loader._resolve_format_mode() existiert noch nicht"
        )

        # cloud_total → symbol
        mode = loader._resolve_format_mode(
            {"metric_id": "cloud_total", "use_friendly_format": True},
            "cloud_total",
        )
        assert mode == "symbol", f"cloud_total True → 'symbol' erwartet, war '{mode}'"

        # wind_direction → scale
        mode = loader._resolve_format_mode(
            {"metric_id": "wind_direction", "use_friendly_format": True},
            "wind_direction",
        )
        assert mode == "scale", f"wind_direction True → 'scale' erwartet, war '{mode}'"

        # visibility → raw (Issue #819: kein Einfach-Modus, Katalog-Default ist jetzt "raw")
        mode = loader._resolve_format_mode(
            {"metric_id": "visibility", "use_friendly_format": True},
            "visibility",
        )
        assert mode == "raw", (
            f"visibility True → 'raw' erwartet (Issue #819), war '{mode}'"
        )

        # temperature (nur raw) → raw
        mode = loader._resolve_format_mode(
            {"metric_id": "temperature", "use_friendly_format": True},
            "temperature",
        )
        assert mode == "raw", f"temperature True → 'raw' erwartet, war '{mode}'"

    def test_ac3_loader_resolves_false_to_raw(self):
        """AC-3: use_friendly_format=False → IMMER 'raw', metrikunabhängig."""
        from app import loader

        for metric_id in ("cloud_total", "wind_direction", "visibility", "cape"):
            mode = loader._resolve_format_mode(
                {"metric_id": metric_id, "use_friendly_format": False},
                metric_id,
            )
            assert mode == "raw", (
                f"AC-3: use_friendly_format=False für {metric_id} muss 'raw' "
                f"sein, war '{mode}'"
            )

    def test_ac3_loader_explicit_format_mode_wins(self):
        """AC-3: explizites format_mode hat Vorrang vor use_friendly_format."""
        from app import loader

        mode = loader._resolve_format_mode(
            {"metric_id": "cloud_total", "format_mode": "raw",
             "use_friendly_format": True},
            "cloud_total",
        )
        assert mode == "raw", (
            f"AC-3: explizites format_mode='raw' muss gewinnen, war '{mode}'"
        )


# ===========================================================================
# AC-4: Schreib-Pfade persistieren beide Felder parallel
# ===========================================================================

class TestAC4WriterPersistsBothFields:
    """
    GIVEN ein Trip mit cloud_total format_mode='symbol' wird gespeichert
    WHEN er als JSON serialisiert wird
    THEN steht format_mode UND use_friendly_format im Output (Backward-Compat).
    """

    def test_ac4_writer_persists_both_fields_in_parallel(self, tmp_path):
        """AC-4: save_trip schreibt format_mode + use_friendly_format parallel."""
        import json
        from datetime import date as date_type, time as time_type

        from app import loader
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig
        from app.trip import Stage, TimeWindow, Trip, Waypoint

        wp = Waypoint(
            id="A1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0,
            time_window=TimeWindow(start=time_type(8, 0), end=time_type(10, 0)),
        )
        stage = Stage(
            id="S1", name="Tag 1", date=date_type(2026, 6, 1), waypoints=[wp],
        )
        trip = Trip(id="test-ac4-trip", name="AC4 Test", stages=[stage])

        # WICHTIG: format_mode='symbol' direkt setzen → muss als kwarg unterstützt sein
        mc = MetricConfig(
            metric_id="cloud_total",
            enabled=True,
            aggregations=["avg"],
            format_mode="symbol",  # neues Feld
        )
        trip.display_config = UnifiedWeatherDisplayConfig(
            trip_id="test-ac4-trip",
            metrics=[mc],
        )

        save_path = loader.save_trip(trip, user_id="default-ac4",
                                     data_dir=str(tmp_path))

        with open(save_path, encoding="utf-8") as f:
            raw = json.load(f)

        metrics_dump = raw["display_config"]["metrics"]
        assert len(metrics_dump) == 1, "Genau 1 Metrik erwartet"
        m_data = metrics_dump[0]
        assert m_data.get("format_mode") == "symbol", (
            f"AC-4 RED: format_mode='symbol' nicht im JSON, war {m_data!r}"
        )
        assert m_data.get("use_friendly_format") is True, (
            f"AC-4: use_friendly_format=True (BC) muss parallel persistiert "
            f"sein, war {m_data.get('use_friendly_format')!r}"
        )


# ===========================================================================
# AC-5: Renderer respektiert format_mode='raw' für cloud_total
# ===========================================================================

class TestAC5RendererRawMode:
    """
    GIVEN MetricConfig(cloud_total, format_mode='raw')
    WHEN E-Mail-Report gerendert wird
    THEN steht '50' in HTML, NICHT das Wolken-Emoji.
    """

    def test_ac5_renderer_raw_mode_shows_numeric_cloud_percent(self):
        """AC-5: format_mode='raw' für cloud_total → Zahl statt Emoji."""
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig
        from output.renderers.trip_report import TripReportFormatter

        # MetricConfig mit format_mode='raw' (NEUES FELD, schlägt fehl wenn fehlt)
        mc = MetricConfig(
            metric_id="cloud_total",
            enabled=True,
            aggregations=["avg"],
            format_mode="raw",  # NEU
            use_friendly_format=True,  # Legacy True — format_mode soll gewinnen
        )
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test-ac5",
            metrics=[
                MetricConfig(metric_id="temperature", enabled=True,
                             aggregations=["min", "max"]),
                mc,
            ],
        )

        seg = _make_segment_weather(
            dp_kwargs={"cloud": 50.0},
            summary=_make_summary(cloud_avg=50.0),
        )
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="AC-5 Trip",
            report_type="evening",
            display_config=dc,
        )
        html = report.email_html

        cloud_emojis = ("☀️", "🌤️", "⛅", "🌥️", "☁️")
        found_emoji = next((e for e in cloud_emojis if e in html), None)
        assert found_emoji is None, (
            f"AC-5 RED: format_mode='raw' soll Wolken-Emoji unterdrücken, "
            f"aber '{found_emoji}' im HTML gefunden"
        )
        assert "50" in html, (
            "AC-5: Roh-Prozentwert '50' muss im HTML stehen"
        )


# ===========================================================================
# AC-6: Simplified-Kürzel in HTML-Tabelle (Wind)
# ===========================================================================

class TestAC6SimplifiedWindKuerzel:
    """
    GIVEN MetricConfig(wind, format_mode='simplified')
    WHEN E-Mail-Report gerendert wird
    THEN Wind-Zelle zeigt 'schwach'/'mäßig'/'stark' OHNE Zahl.
    """

    @pytest.mark.xfail(reason="bekannter Rest: simplified-Wind im HTML-Pfad, s. docs/specs/modules/issue_1214_metric_format_slice4.md", strict=False)
    def test_ac6_simplified_wind_renders_kuerzel_in_html_table(self):
        """AC-6: format_mode='simplified' für wind → Adjektiv-Kürzel ohne km/h."""
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig
        from output.renderers.trip_report import TripReportFormatter

        mc_wind = MetricConfig(
            metric_id="wind",
            enabled=True,
            aggregations=["max"],
            format_mode="simplified",  # NEU
        )
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test-ac6",
            metrics=[mc_wind],
        )

        # Wind 12 km/h → laut compact_summary.py:271 = "schwach" / "leicht"
        seg = _make_segment_weather(
            dp_kwargs={"wind": 12.0},
            summary=_make_summary(wind_max=12.0),
        )
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="AC-6 Trip",
            report_type="evening",
            display_config=dc,
        )
        html = report.email_html

        # Erwarte ein Kürzel-Adjektiv aus {schwach, mäßig, stark, leicht}
        kuerzel_set = ("schwach", "mäßig", "stark", "leicht")
        found_kuerzel = any(k in html.lower() for k in kuerzel_set)
        assert found_kuerzel, (
            "AC-6 RED: Wind-Spalte muss in simplified-Modus ein Kürzel "
            "(schwach/mäßig/stark/leicht) zeigen"
        )

        # In der HTML-Tabellen-Zelle soll NICHT die nackte Zahl '12' direkt stehen.
        # Strategie: Suche nach '>12<' (Zellinhalt nur die Zahl) — falls
        # in irgendeiner <td> "12" alleine steht, ist Render falsch.
        # Toleranter: Suche nach '<td' Bereichen und prüfe, ob darin '12' OHNE
        # Adjektiv vorkommt (häufiges Pattern). Wir machen das simpel mit
        # einer Substring-Suche auf '>12 km/h' und '>12<' direkt.
        assert ">12 km/h<" not in html, (
            "AC-6: simplified soll keine 'km/h'-Zahl in Wind-Zelle haben"
        )


# ===========================================================================
# AC-7: Wind-Direction-Merge an scale-Modus gekoppelt
# ===========================================================================

class TestAC7WindDirectionMergeScale:
    """
    GIVEN wind_direction.format_mode='scale' → Kompass im Wind-Zelltext.
    GIVEN wind_direction.format_mode='raw'   → eigene Grad-Spalte, kein Merge.
    """

    def test_ac7_wind_direction_merge_triggered_by_scale_mode(self):
        """AC-7: scale → Merge; raw → eigene Spalte."""
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig
        from output.renderers.trip_report import TripReportFormatter

        def _build_html(wdir_mode: str) -> str:
            mc_wind = MetricConfig(metric_id="wind", enabled=True,
                                   aggregations=["max"])
            mc_wdir = MetricConfig(
                metric_id="wind_direction",
                enabled=True,
                aggregations=["avg"],
                format_mode=wdir_mode,  # NEU
            )
            dc = UnifiedWeatherDisplayConfig(
                trip_id=f"test-ac7-{wdir_mode}",
                metrics=[mc_wind, mc_wdir],
            )
            seg = _make_segment_weather(
                dp_kwargs={"wind": 20.0, "wind_dir_deg": 90.0},  # 90° = E
                summary=_make_summary(wind_max=20.0, wind_dir_deg_avg=90.0),
            )
            report = TripReportFormatter().format_email(
                segments=[seg],
                trip_name=f"AC-7 Trip ({wdir_mode})",
                report_type="evening",
                display_config=dc,
            )
            return report.email_html

        # 1) format_mode='scale' → Wind-Zelle enthält Kompass-Kürzel
        html_scale = _build_html("scale")
        compass_in_scale = any(c in html_scale for c in ("N", "NE", "E", "SE",
                                                         "S", "SW", "W", "NW"))
        assert compass_in_scale, (
            "AC-7 RED: scale-Modus soll Kompass-Kürzel im HTML zeigen"
        )

        # 2) format_mode='raw' → KEIN Kompass-Kürzel in Wind-Spalte,
        # stattdessen Grad-Wert (90 oder 90°) als separate Spalte.
        html_raw = _build_html("raw")
        # Bei raw soll der Grad-Wert sichtbar sein (90 / 90°)
        has_degree = ("90°" in html_raw) or (">90<" in html_raw) or (" 90 " in html_raw)
        assert has_degree, (
            "AC-7 RED: raw-Modus soll Grad-Wert (90 / 90°) in eigener Spalte zeigen"
        )

        # raw-Modus darf den Wind-Wert NICHT mit Kompass-Kürzel mergen.
        # Indikator: Substring '20 E' (Wind 20 km/h + Compass E direkt nebeneinander)
        # darf nicht im Rendering vorkommen.
        assert "20 E" not in html_raw, (
            "AC-7 RED: raw-Modus soll Wind nicht mit Kompass-Kürzel mergen"
        )


# ===========================================================================
# AC-8: SMS-Token-Pfad bit-identisch zwischen format_mode='symbol' und legacy
# ===========================================================================

class TestAC8SMSTokenSymbolParity:
    """
    GIVEN MetricSpec mit format_mode='symbol' für CAPE
    WHEN ein SMS-Token gebaut wird
    THEN ist Token-Output bit-identisch zur legacy use_friendly_format=True-Variante.
    """

    def test_ac8_sms_token_bit_identical_for_symbol_mode(self):
        """AC-8: format_mode='symbol' → identischer Token wie legacy True."""
        from output.tokens.builder import build_token_line
        from output.tokens.dto import (
            DailyForecast,
            HourlyValue,
            MetricSpec,
            NormalizedForecast,
        )

        # CAPE-Friendly-Label aus Katalog: \U0001f7e2\U0001f7e1\U0001f534
        cape_friendly = "\U0001f7e2\U0001f7e1\U0001f534"

        # Wir nehmen den Symbol "TH" als Stand-In für CAPE-äquivalente Friendly-
        # Token-Logik im Builder (CAPE ist nicht im Standard-Token-Set, aber das
        # Friendly-Companion-Pattern in builder.py:222 funktioniert für custom
        # Symbole). Wir testen das mit einem Custom-Symbol "CA" + friendly_label.

        thunder_hourly = tuple(HourlyValue(hour=h, value=0.0) for h in range(24))
        day = DailyForecast(
            temp_min_c=10.0,
            temp_max_c=18.0,
            thunder_hourly=thunder_hourly,
        )
        forecast = NormalizedForecast(days=(day,))

        # Variante A: legacy use_friendly_format=True
        spec_legacy = MetricSpec(
            symbol="CA",
            enabled=True,
            morning_enabled=True,
            evening_enabled=True,
            use_friendly_format=True,
            friendly_label=cape_friendly,
        )

        # Variante B: neuer format_mode='symbol' (Feld muss neu im MetricSpec sein)
        spec_new = MetricSpec(
            symbol="CA",
            enabled=True,
            morning_enabled=True,
            evening_enabled=True,
            format_mode="symbol",  # NEU
            friendly_label=cape_friendly,
        )

        line_legacy = build_token_line(
            forecast, [spec_legacy],
            report_type="morning", stage_name="AC8-Stage",
        )
        line_new = build_token_line(
            forecast, [spec_new],
            report_type="morning", stage_name="AC8-Stage",
        )

        # Filter nur die CAPE-Token raus (beide Renderings müssen dieselbe
        # CA-Token-Ausgabe haben)
        ca_legacy = [t for t in line_legacy.tokens if t.symbol == "CA"]
        ca_new = [t for t in line_new.tokens if t.symbol == "CA"]

        assert ca_legacy and ca_new, (
            f"AC-8 RED: CA-Token in beiden Varianten erwartet — "
            f"legacy={ca_legacy!r}, new={ca_new!r}"
        )
        assert ca_legacy[0].value == ca_new[0].value, (
            f"AC-8: Token-Value muss bit-identisch sein "
            f"(legacy={ca_legacy[0].value!r}, new={ca_new[0].value!r})"
        )
        # render() muss ebenfalls bit-identisch sein
        assert ca_legacy[0].render() == ca_new[0].render(), (
            f"AC-8: Token.render() muss bit-identisch sein "
            f"(legacy={ca_legacy[0].render()!r}, new={ca_new[0].render()!r})"
        )


# ===========================================================================
# AC-10: Konsolidierung — _build_friendly_keys nur noch in helpers.py
# ===========================================================================

class TestAC10ConsolidatedFriendlyKeys:
    """
    GIVEN _build_friendly_keys existiert heute in trip_report.py UND helpers.py
    WHEN Spec umgesetzt ist
    THEN trip_report.py hat KEINE eigene Definition mehr, sondern importiert
         aus email/helpers.py.
    """

    def test_ac10_build_friendly_keys_consolidated(self):
        """AC-10: trip_report.py darf _build_friendly_keys nicht mehr selbst definieren."""
        import ast
        import inspect

        from output.renderers import trip_report

        src = inspect.getsource(trip_report)
        tree = ast.parse(src)

        # Suche alle FunctionDef + AsyncFunctionDef (inkl. in Klassen verschachtelt)
        # mit Name 'build_friendly_keys' oder '_build_friendly_keys'.
        defs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in ("_build_friendly_keys", "build_friendly_keys"):
                    defs.append(node.name)

        assert len(defs) == 0, (
            f"AC-10 RED: trip_report.py definiert noch "
            f"{defs!r} — sollte aus email/helpers.py importiert werden"
        )

        # Zusätzlich: Prüfen, dass ein Import aus helpers.py existiert
        # (entweder 'from ...helpers import build_friendly_keys' oder
        # 'from output.renderers.email.helpers import build_friendly_keys').
        import_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "helpers" in node.module:
                    for alias in node.names:
                        if alias.name in ("build_friendly_keys",
                                          "_build_friendly_keys",
                                          "build_format_modes"):
                            import_found = True
                            break
        assert import_found, (
            "AC-10 RED: trip_report.py muss build_friendly_keys (oder "
            "build_format_modes) aus email/helpers.py importieren"
        )


# ---------------------------------------------------------------------------
# Issue #444 — Delegation: _effective_format_mode → loader._resolve_format_mode
# SPEC: docs/specs/modules/issue_444_format_mode_consolidation.md
# ---------------------------------------------------------------------------

class TestAC444DelegationToResolveFormatMode:
    """
    Issue #444: _effective_format_mode muss an loader._resolve_format_mode
    delegieren (Thin Wrapper). Kein eigener Präzedenz-Code mehr in helpers.py.
    """

    def test_ac444_a_delegates_to_resolve_format_mode(self):
        """AC-444-A: Body von _effective_format_mode enthält einen Aufruf von
        _resolve_format_mode (strukturelle Verifikation via ast).
        """
        import ast
        import inspect
        from output.renderers.email import helpers

        src = inspect.getsource(helpers._effective_format_mode)
        tree = ast.parse(src)
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name)
                 and node.func.id == "_resolve_format_mode")
                or (isinstance(node.func, ast.Attribute)
                    and node.func.attr == "_resolve_format_mode")
            )
        ]
        assert calls, (
            "AC-444-A: _effective_format_mode enthält keinen "
            "_resolve_format_mode-Aufruf — Delegation nicht implementiert"
        )

    def test_ac444_b_parity_all_three_precedence_cases(self):
        """AC-444-B: Für alle drei Präzedenzfälle liefert _effective_format_mode
        dasselbe Ergebnis wie loader._resolve_format_mode mit äquivalentem Dict.
        """
        from app import loader
        from app.models import MetricConfig
        from output.renderers.email.helpers import _effective_format_mode

        cases = [
            MetricConfig(metric_id="cloud_total", format_mode="raw",
                         use_friendly_format=True),
            MetricConfig(metric_id="cloud_total", format_mode=None,
                         use_friendly_format=False),
            MetricConfig(metric_id="cloud_total", format_mode=None,
                         use_friendly_format=True),
        ]
        for mc in cases:
            expected = loader._resolve_format_mode(
                {
                    "format_mode": mc.format_mode,
                    "use_friendly_format": mc.use_friendly_format,
                },
                mc.metric_id,
            )
            got = _effective_format_mode(mc)
            assert got == expected, (
                f"AC-444-B: Parität verletzt für "
                f"format_mode={mc.format_mode!r}, "
                f"use_friendly_format={mc.use_friendly_format!r}: "
                f"got {got!r}, erwartet {expected!r}"
            )

    def test_ac444_c_no_duplicate_catalog_lookup(self):
        """AC-444-C: Body von _effective_format_mode enthält keinen direkten
        Katalog-Lookup (kein 'default_format_mode' im Quelltext).
        """
        import inspect
        from output.renderers.email import helpers

        src = inspect.getsource(helpers._effective_format_mode)
        assert "default_format_mode" not in src, (
            "AC-444-C: _effective_format_mode enthält noch einen direkten "
            "Katalog-Lookup (default_format_mode) — Delegation nicht umgebaut"
        )


# ===========================================================================
# AC-446: Strikte format_mode-Validierung gegen MetricDefinition.format_modes
# SPEC: docs/specs/modules/issue_446_format_mode_validation.md
# ===========================================================================

class TestAC446FormatModeValidation:
    """
    Issue #446: _resolve_format_mode muss unbekannte format_mode-Strings
    gegen MetricDefinition.format_modes validieren.

    Bei unbekanntem Modus und bekannter Metrik: WARNING + Fallback auf
    default_format_mode. Bei unbekannter metric_id: Original-String bleibt.
    """

    def test_ac446_1_unknown_capitalized_falls_back_with_warning(self):
        """AC-1: format_mode='Symbol' (Großbuchstabe) für cloud_total → 'symbol' + WARNING."""
        from app import loader

        with self.assert_warning_logged("app.loader"):
            mode = loader._resolve_format_mode(
                {"format_mode": "Symbol"},
                "cloud_total",
            )
        assert mode == "symbol", (
            f"AC-446-1: 'Symbol' muss auf catalog default 'symbol' fallen, war '{mode}'"
        )

    def test_ac446_2_unknown_all_caps_falls_back_to_catalog_default(self):
        """AC-2: format_mode='RAW' (Caps) für cloud_total → 'symbol' (catalog default)."""
        from app import loader

        mode = loader._resolve_format_mode(
            {"format_mode": "RAW"},
            "cloud_total",
        )
        assert mode == "symbol", (
            f"AC-446-2: 'RAW' ist nicht in ('raw','symbol') für cloud_total → "
            f"Fallback auf 'symbol', war '{mode}'"
        )

    def test_ac446_3_valid_mode_returned_unchanged(self):
        """AC-3: format_mode='raw' (valide) für cloud_total → 'raw' unverändert, kein Log."""
        from app import loader

        with self.assert_no_warning_logged("app.loader"):
            mode = loader._resolve_format_mode(
                {"format_mode": "raw"},
                "cloud_total",
            )
        assert mode == "raw", (
            f"AC-446-3: Valides 'raw' muss unverändert zurückgegeben werden, war '{mode}'"
        )

    def test_ac446_4_unknown_metric_id_returns_raw_unchanged(self):
        """AC-4: format_mode='raw_v2' für unbekannte Metrik → 'raw_v2' bleibt (KeyError → pass)."""
        from app import loader

        mode = loader._resolve_format_mode(
            {"format_mode": "raw_v2"},
            "nonexistent_metric_xyz",
        )
        assert mode == "raw_v2", (
            f"AC-446-4: Unbekannte metric_id → raw bleibt 'raw_v2', war '{mode}'"
        )

    def test_ac446_5_mode_not_in_restricted_format_modes_falls_back(self):
        """AC-5: format_mode='symbol' für temperature (nur 'raw') → 'raw' (Fallback).

        Issue #814: thunder hat seit AC-6 ('Roh = deutsches Wort') den Modus 'raw'
        legitimate in format_modes=('raw','symbol'). Testbeispiel auf temperature
        umgestellt (nur 'raw', kein 'symbol') um das Fallback-Verhalten zu belegen.
        """
        from app import loader

        mode = loader._resolve_format_mode(
            {"format_mode": "symbol"},
            "temperature",
        )
        assert mode == "raw", (
            f"AC-446-5: temperature hat nur format_modes=('raw',) → "
            f"'symbol' muss auf 'raw' fallen, war '{mode}'"
        )

    # --- Hilfsmethoden ---

    from contextlib import contextmanager

    @contextmanager
    def assert_warning_logged(self, logger_name: str):
        import logging

        records: list = []

        class _Cap(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _Cap()
        handler.setLevel(logging.WARNING)
        log = logging.getLogger(logger_name)
        log.addHandler(handler)
        try:
            yield
        finally:
            log.removeHandler(handler)

        warnings = [r for r in records if r.levelno >= logging.WARNING]
        assert warnings, (
            f"AC-446: Kein WARNING über Logger '{logger_name}' geloggt — "
            f"erwartet bei unbekanntem format_mode"
        )

    @contextmanager
    def assert_no_warning_logged(self, logger_name: str):
        import logging

        records: list = []

        class _Cap(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _Cap()
        handler.setLevel(logging.WARNING)
        log = logging.getLogger(logger_name)
        log.addHandler(handler)
        try:
            yield
        finally:
            log.removeHandler(handler)

        warnings = [r for r in records if r.levelno >= logging.WARNING]
        assert not warnings, (
            f"AC-446: Unerwartetes WARNING über Logger '{logger_name}' bei "
            f"validen format_mode-Werten: {[r.getMessage() for r in warnings]}"
        )
