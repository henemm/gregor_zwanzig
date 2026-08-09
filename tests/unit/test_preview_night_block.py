"""Bug #1315: die E-Mail-Vorschau muss "Nacht am Ziel" zeigen, wenn ein
Trip ``show_night_block=True`` hat und Nacht-Wetter vorliegt -- genau wie
die versendete Mail (Issue #1313). Vorher rief
``PreviewService._render_email`` ``format_email()`` OHNE ``night_weather``
auf, daher fehlte die Sektion in der Vorschau immer.

Kein Netz: night_weather wird als echtes, konstruiertes Fixture-Objekt
uebergeben -- kein Live-Fetch, kein Mock.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import dataclasses

from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
    TripSegment,
)
from app.trip import AggregationConfig, Stage, Trip, Waypoint
from services.preview_service import PreviewService

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo"


def _meta():
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )


def _dp(dt):
    return ForecastDataPoint(
        ts=dt, t2m_c=8.0, wind10m_kmh=5.0, gust_kmh=5.0, precip_1h_mm=0.0,
        pop_pct=0, cloud_total_pct=30, thunder_level=ThunderLevel.NONE,
        humidity_pct=60,
    )


def _last_segment(arrival_hour: int = 15, base_date: date = date(2026, 7, 20)):
    """Segment ankommend um ``arrival_hour`` UTC am ``base_date`` (Default:
    2026-07-20, fest fuer die meisten Tests -- diese bauen ``night_weather``
    direkt/synthetisch und sind vom Datum unabhaengig)."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=1500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1800.0),
        start_time=datetime.combine(base_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=arrival_hour - 4),
        end_time=datetime.combine(base_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=arrival_hour),
        duration_hours=4.0, distance_km=8.0, ascent_m=400.0, descent_m=0.0,
    )
    ts = NormalizedTimeseries(meta=_meta(), data=[
        _dp(datetime.combine(base_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=h)) for h in range(arrival_hour - 4, arrival_hour + 1)
    ])
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(temp_min_c=5.0, temp_max_c=10.0),
        fetched_at=datetime.combine(base_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=6),
        provider="openmeteo",
    )


def _night_weather(arrival_hour: int = 15):
    """Deckt Ankunft bis 06:00 am naechsten Tag ab (arrival→23 + 0→6)."""
    hours_day1 = [datetime(2026, 7, 20, h, 0, tzinfo=timezone.utc) for h in range(arrival_hour, 24)]
    hours_day2 = [datetime(2026, 7, 21, h, 0, tzinfo=timezone.utc) for h in range(0, 7)]
    return NormalizedTimeseries(meta=_meta(), data=[_dp(dt) for dt in hours_day1 + hours_day2])


def _trip(show_night_block: bool) -> Trip:
    dc = build_default_display_config()
    dc = dataclasses.replace(dc, show_night_block=show_night_block)
    return Trip(
        id="t1", name="Testtour", stages=[],
        aggregation=AggregationConfig(),
        display_config=dc,
        report_config=None,
    )


class TestPreviewRenderEmailNightBlock:
    """AC-1/AC-2 (#1315): der Durchreich-Pfad in
    ``PreviewService._render_email`` muss ``night_weather`` an
    ``format_email`` weitergeben."""

    def test_night_weather_shows_night_section_when_enabled(self):
        segment_weather = [_last_segment()]
        night_weather = _night_weather()
        trip = _trip(show_night_block=True)

        report = PreviewService()._render_email(
            scheduler=None,
            segment_weather=segment_weather,
            trip=trip,
            report_type="evening",
            stage_name="Etappe 1",
            stage_stats=None,
            trip_tz=ZoneInfo("UTC"),
            stability_result=None,
            night_weather=night_weather,
        )

        assert "Nacht am Ziel" in report.email_html, (
            f"Erwartete Nacht-Sektion fehlt in der Vorschau-HTML:\n{report.email_html[:2000]}"
        )

    def test_no_night_section_when_show_night_block_false(self):
        """Gegenprobe (AC-2): show_night_block=False -> keine Nacht-Sektion,
        auch wenn night_weather technisch vorhanden waere."""
        segment_weather = [_last_segment()]
        night_weather = _night_weather()
        trip = _trip(show_night_block=False)

        report = PreviewService()._render_email(
            scheduler=None,
            segment_weather=segment_weather,
            trip=trip,
            report_type="evening",
            stage_name="Etappe 1",
            stage_stats=None,
            trip_tz=ZoneInfo("UTC"),
            stability_result=None,
            night_weather=night_weather,
        )

        assert "Nacht am Ziel" not in report.email_html


class _SpyProvider:
    """Echter (Nicht-Mock) Provider-Stellvertreter: wickelt FixtureProvider
    ein und zaehlt fetch_forecast-Aufrufe. Liefert echte, offline erzeugte
    Fixture-Daten -- kein Netz, kein Mock/patch/MagicMock."""

    def __init__(self, fixture_dir: str):
        from providers.fixture import FixtureProvider
        self._inner = FixtureProvider(fixture_dir)
        self.calls = 0

    @property
    def name(self) -> str:
        return self._inner.name

    def fetch_forecast(self, location, start=None, end=None,
                        enrich_ensemble=True, enrich_snow=True):
        self.calls += 1
        return self._inner.fetch_forecast(
            location, start, end, enrich_ensemble, enrich_snow,
        )


def test_fetch_night_weather_uses_injected_provider_not_live_openmeteo():
    """Adversary-Fix F001 (#1315, Issue #483): wird ``provider`` explizit
    uebergeben (Demo-Modus), MUSS ``fetch_night_weather`` GENAU diesen
    nutzen statt ``get_provider("openmeteo")`` (Live-API) -- garantiert
    durch den ``provider or get_provider(...)``-Kurzschluss. Beweis: der
    Spy wird exakt einmal aufgerufen, kein Netzzugriff moeglich.

    ``base_date`` = heutiges UTC-Datum: ``FixtureProvider`` stempelt seine
    72 Fixpunkte immer ab dem aktuellen UTC-Tag (start/end werden ignoriert,
    siehe ``providers/fixture.py``) -- ein fest kodiertes Vergangenheits-
    datum wuerde nach dem Filtern auf das Nachtfenster leer laufen und
    faelschlich als Providerfehler erscheinen (Fund bei Fix #1339)."""
    from services.segment_weather import fetch_night_weather

    last_segment = _last_segment(base_date=datetime.now(timezone.utc).date())
    spy = _SpyProvider(str(_FIXTURE_DIR))

    result = fetch_night_weather(last_segment, provider=spy)

    assert spy.calls == 1, "Injizierter Provider wurde nicht (oder mehrfach) genutzt"
    assert result is not None


def _demo_trip_single_stage(target: date, show_night_block: bool = True) -> Trip:
    """Ein-Etappen-Trip (keine Folge-Etappen -> keine Trend-/Gewitter-
    Fetches ausserhalb des Nacht-Pfads), damit die Live-Falle unten NUR
    auf die Nacht-Wetter-Beschaffung reagieren kann."""
    wp1 = Waypoint(id="G1", name="Start", lat=47.2692, lon=11.4041, elevation_m=600)
    wp2 = Waypoint(id="G2", name="Ziel", lat=47.3010, lon=11.4500, elevation_m=1200)
    stage = Stage(id="T1", name="Etappe 1", date=target, waypoints=[wp1, wp2])
    dc = build_default_display_config(trip_id="demo-night-trip")
    dc = dataclasses.replace(dc, show_night_block=show_night_block)
    return Trip(
        id="demo-night-trip", name="Demo-Night-Trip", stages=[stage],
        display_config=dc,
    )


def test_demo_preview_night_fetch_never_touches_live_openmeteo(monkeypatch):
    """Adversary-Fund F001 (#1315, Issue #483): eine Demo-Vorschau
    (``demo=True``) eines Trips mit ``show_night_block=True`` darf fuer das
    Nacht-Segment NIEMALS ``get_provider("openmeteo")`` (Live-API)
    aufrufen -- sonst verletzt sie den Quota-/API-unabhaengigen
    Demo-Vertrag (#483).

    Falle: ``get_provider`` wird durch eine Funktion ersetzt, die JEDEN
    Aufruf in einer Liste protokolliert (nicht nur per Exception) -- so wird
    der Fund auch dann sichtbar, wenn ``fetch_night_weather`` einen Fehler
    intern abfaengt (broad ``except Exception`` -- Fallback-Pfad). Deshalb
    wird NACH dem Aufruf explizit ``calls == []`` geprueft statt auf eine
    durchschlagende Exception zu vertrauen."""
    import providers.base as providers_base

    calls: list[str] = []

    def _trap(name):
        calls.append(name)
        raise AssertionError(f"Live get_provider({name!r}) aufgerufen")

    monkeypatch.setattr(providers_base, "get_provider", _trap)

    target = date.today()
    trip = _demo_trip_single_stage(target, show_night_block=True)

    report, _segments, _stage_name, _tz = PreviewService()._build_report(
        trip, target, "evening", demo=True,
    )

    assert calls == [], (
        f"get_provider() waehrend Demo-Vorschau live aufgerufen: {calls} -- "
        "der injizierte FixtureProvider haette fuer das Nacht-Segment "
        "genutzt werden muessen (Issue #483)"
    )
    assert "Nacht am Ziel" in report.email_html, (
        f"Nacht-Sektion fehlt trotz show_night_block=True + Nacht-Fixture-Daten:\n"
        f"{report.email_html[:2000]}"
    )


def test_preview_night_fetch_follows_night_metric_selection(monkeypatch):
    """#1484 AC-8 an der WIRKSTELLE (nicht nur am Praedikat): ist die
    Nacht-Stundentabelle aus (``show_night_block=False``), aber die Groesse
    "Nacht-Tiefsttemperatur" gewaehlt, beschafft die Vorschau trotzdem
    Nachtdaten — sonst zeigt ``N`` dort still den Tageswert, waehrend der
    Versand den echten Nachtwert traegt.

    Muster wie die F001-Falle oben: die ECHTE ``fetch_night_weather`` wird
    nur mit einem Aufruf-Rekorder umwickelt (kein Mock-Rueckgabewert) und
    laeuft im Demo-Modus gegen den FixtureProvider — kein Netz.
    """
    import services.segment_weather as sw

    calls: list[int] = []
    real_fetch = sw.fetch_night_weather

    def _recording_fetch(seg, provider=None):
        calls.append(1)
        return real_fetch(seg, provider=provider)

    monkeypatch.setattr(sw, "fetch_night_weather", _recording_fetch)

    target = date.today()
    trip = _demo_trip_single_stage(target, show_night_block=False)
    assert trip.display_config.is_metric_enabled("temperature_night"), (
        "Vorbedingung: die Default-Konfiguration muss die Nachtgroesse "
        "aktiviert haben (build_default_display_config, #1484)."
    )

    PreviewService()._build_report(trip, target, "evening", demo=True)

    assert calls, (
        "Die Vorschau beschafft KEINE Nachtdaten, obwohl die "
        "Nacht-Tiefsttemperatur gewaehlt ist (#1484 AC-8) — N faellt dort "
        "still auf den Tageswert zurueck."
    )


def test_preview_skips_night_fetch_when_neither_selected(monkeypatch):
    """Gegenprobe zu AC-8: ist KEINER der Gruende gegeben, die Nachtdaten
    noetig machen -> die Vorschau beschafft keine (kein unnoetiger
    Provider-Aufruf).

    #1651 hat die Liste dieser Gruende um die Gewitter-Metrik erweitert: ab
    dieser Scheibe speisen Nachtdaten auch den Nacht-Zusatz des
    Vorschau-Satzes ("nachts starkes Gewitter ab HH:MM"), und ohne sie
    divergierte die Vorschau vom Versand (AC-11). Der Test schaltet sie
    deshalb mit ab -- er bewacht weiterhin, dass kein PAUSCHALER Zusatz-Abruf
    fuer jeden Trip entsteht, jetzt gegen den vollstaendigen Bedingungssatz.
    """
    import services.segment_weather as sw

    calls: list[int] = []
    real_fetch = sw.fetch_night_weather

    def _recording_fetch(seg, provider=None):
        calls.append(1)
        return real_fetch(seg, provider=provider)

    monkeypatch.setattr(sw, "fetch_night_weather", _recording_fetch)

    target = date.today()
    trip = _demo_trip_single_stage(target, show_night_block=False)
    trip.display_config.metrics = [
        dataclasses.replace(mc, enabled=False)
        if mc.metric_id in ("temperature_night", "thunder") else mc
        for mc in trip.display_config.metrics
    ]

    PreviewService()._build_report(trip, target, "evening", demo=True)

    assert calls == [], (
        "Die Vorschau beschafft Nachtdaten, obwohl weder Nacht-Tabelle noch "
        "Nacht-Tiefsttemperatur noch Gewitter-Metrik gewaehlt sind."
    )
