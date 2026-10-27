"""Geteilte Hilfen fuer die Lawinen-Lagebericht-Tests (Issue #1441 Slice 1).

SPEC: docs/specs/modules/avalanche_report_bulletin.md
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md

Kein Mock-Theater: der Fixture-Transport ist ein ECHTER ``httpx.BaseTransport``, der die
AUFGEZEICHNETEN Bulletin-Bytes (``tests/fixtures/avalanche_report/``) ausliefert, den 301-Redirect
von ``static.avalanche.report`` auf ``avalanche.report`` genauso nachbildet wie der echte Dienst
und jeden Zugriff zaehlt. Er wird der echten Quelle ueber den Konstruktor-Parameter ``transport``
uebergeben; die Abrufschicht ``warn_egress.cached_fetch`` laeuft unveraendert.
(Bewusst KEIN lokaler ``http.server``: ``--disable-socket`` sperrt auch Loopback.)

Alle Importe der zu pruefenden Module stehen INNERHALB der Funktionen, damit ein fehlendes
Modul im RED nur den jeweiligen Test (an der Assertion/dem Import) rot macht, nicht das Sammeln.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "avalanche_report"
BULLETINS = FIXTURES / "bulletins"
DERIVED = FIXTURES / "derived"
REGIONS = FIXTURES / "regions"
UTC = timezone.utc

# Anzeigenamen der Tabellenzeilen (Vertrag Abschnitt 1)
DISPLAY_NAMES = {
    "AT-07": "Lawinenwarndienst Tirol",
    "IT-32-BZ": "Lawinenwarndienst Südtirol",
    "IT-32-TN": "Lawinenwarndienst Trentino",
    "AT-02": "Lawinenwarndienst Kärnten",
}
DEFAULT_URL_PATTERN = "https://static.avalanche.report/bulletins/latest/{X}_de_CAAMLv6.json"

# Innere Punkte, je genau EINE Mikroregion (siehe README.md der Fixtures)
P_TIROL_AT_07_28 = (46.9394, 12.6844)   # AC-1; liegt zugleich in der Bounding-Box von AT-02
P_TIROL_AT_07_25 = (46.9599, 12.4007)   # Stufe 4 ab Waldgrenze (2026-02-19/20/21)
P_TIROL_AT_07_20 = (46.8831, 10.8102)   # Split 2026-04-06
P_TIROL_AT_07_05 = (47.4987, 11.7957)   # Waldgrenze Stufe 3 (2026-03-01), Gleichstand (2026-02-26), Mai
P_KAERNTEN_AT_02_05_02 = (46.8947, 14.1901)   # Stufe 1 (2026-03-01)
P_SUEDTIROL_BZ_16 = (46.4266, 11.2584)
P_TRENTINO_TN_09 = (46.3281, 11.5104)
P_BORDER = (47.38545333996563, 11.770177360497602)   # AT-07-04-02 | AT-07-16
P_ZELL_AM_SEE = (47.3257, 12.7953)   # Bounding-Box AT-07 ja, Polygon nein
P_MUENCHEN = (48.1371, 11.5754)
P_ZUERICH = (47.3769, 8.5417)
P_SALZBURG = (47.8095, 13.0550)


def doc(relative: str) -> dict:
    """Lade eine Bulletin-Fixture (relativ zu ``bulletins/`` oder ``derived/`` per Praefix)."""
    path = (BULLETINS / relative) if not relative.startswith("derived/") else (FIXTURES / relative)
    return json.loads(path.read_text(encoding="utf-8"))


def raw(relative: str) -> bytes:
    path = (BULLETINS / relative) if not relative.startswith("derived/") else (FIXTURES / relative)
    return path.read_bytes()


def day_file(day: str, key: str = "AT-07") -> str:
    return f"{day}_{key}_de_CAAMLv6.json"


def parse_alert(document_name: str, region_id: str, *, source: str = "avalanche_report"):
    """Echter Parser auf eine aufgezeichnete Datei."""
    from services.official_alerts.avalanche_report import parse_region_alert

    return parse_region_alert(doc(document_name), region_id, source=source)


def fixture_table(keys: tuple[str, ...] = ("AT-07", "IT-32-BZ", "IT-32-TN", "AT-02"),
                  extra: tuple = ()):
    """Konfigurationstabelle mit den EINGECHECKTEN Fixture-Regionsdateien."""
    from services.official_alerts.avalanche_report import AvalancheRegionConfig

    rows = tuple(
        AvalancheRegionConfig(
            key=k, url_pattern=DEFAULT_URL_PATTERN,
            regions_file=REGIONS / f"{k}_micro-regions.geojson.json",
            display_name=DISPLAY_NAMES[k],
        )
        for k in keys
    )
    return rows + tuple(extra)


@dataclass
class Reply:
    status: int = 200
    body: bytes = b""
    error: Optional[Exception] = None


def ok(relative: str) -> Reply:
    return Reply(200, raw(relative))


class FixtureTransport(httpx.BaseTransport):
    """Liefert aufgezeichnete Bytes je Tabellenzeile (``latest/{X}_de_CAAMLv6.json``).

    ``static.avalanche.report`` antwortet - wie der echte Dienst - mit 301 auf ``avalanche.report``;
    nur das Ziel liefert 200/404/5xx. ``requests`` haelt JEDEN Zugriff als ``(host, key)``.
    """

    _PATH = re.compile(r"^/bulletins/latest/(?P<key>[A-Za-z0-9\-]+)_de_CAAMLv6\.json$")

    def __init__(self, routes: Optional[dict[str, Reply]] = None) -> None:
        self.routes: dict[str, Reply] = dict(routes or {})
        self.requests: list[tuple[str, str]] = []

    def set(self, key: str, reply: Reply) -> None:
        self.routes[key] = reply

    def served(self, key: Optional[str] = None) -> int:
        """Anzahl der Zugriffe auf das Redirect-ZIEL (``avalanche.report``) -- ein echter Abruf."""
        return sum(1 for host, k in self.requests
                   if host == "avalanche.report" and (key is None or k == key))

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        match = self._PATH.match(request.url.path)
        key = match.group("key") if match else request.url.path
        self.requests.append((host, key))
        if host == "static.avalanche.report":
            return httpx.Response(
                301, headers={"Location": str(request.url.copy_with(host="avalanche.report"))},
                request=request,
            )
        if host != "avalanche.report":
            raise httpx.ConnectError(f"unerwarteter Host {host}", request=request)
        reply = self.routes.get(key, Reply(404, b""))
        if reply.error is not None:
            raise reply.error
        headers = {"Content-Type": "application/json"} if reply.body else {}
        return httpx.Response(reply.status, content=reply.body, headers=headers, request=request)


class FakeClock:
    """Eine Uhr fuer beides: ``clock`` (Sekunden, Cache-TTL) und ``now_fn`` (aware datetime)."""

    def __init__(self, base: datetime) -> None:
        self.base = base
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds

    def now(self) -> datetime:
        return self.base + timedelta(seconds=self.t - 1000.0)


def make_source(transport: FixtureTransport, clock: FakeClock, *, table=None):
    from services.official_alerts.avalanche_report import AvalancheReportSource

    return AvalancheReportSource(
        table if table is not None else fixture_table(),
        transport=transport, clock=clock, now_fn=clock.now, cache={},
    )


def only_source(monkeypatch, *sources) -> None:
    """Registry auf die geprueften Quellen reduzieren (sonst zaehlen geblockte GeoSphere-/
    MeteoAlarm-Quellen als ausgefallen und verfaelschen ``unavailable``)."""
    from services.official_alerts import base

    monkeypatch.setattr(base, "_REGISTERED_SOURCES", list(sources))


def alerts_with_status(lat: float, lon: float, now: datetime, *, window=None):
    """Der Trip-Briefing-Abruf wie in ``trip_report_scheduler`` (Fenster = Segmentzeitraum)."""
    from services.official_alerts import get_official_alerts_with_status

    start, end = window if window else (now - timedelta(hours=2), now + timedelta(hours=6))
    return get_official_alerts_with_status(lat, lon, window_start=start, window_end=end, now=now)


class RecordedSource:
    """Gibt vorab geparste Alerts aus (Parser-Ergebnis aufgezeichneter Daten) -- fuer
    Zusammenfuehrungs-Tests mit zwei Quellen. Erfuellt das ``OfficialAlertSource``-Protokoll."""

    def __init__(self, name: str, alerts: list) -> None:
        self._name = name
        self._alerts = list(alerts)

    @property
    def name(self) -> str:
        return self._name

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list:
        return list(self._alerts)


def notice(alert, *, sms_scope: str = "ges.Route"):
    from output.renderers.alert.official_alerts import OfficialAlertNotice

    return OfficialAlertNotice(
        alert=alert, scope_label="gesamte Route", sms_scope=sms_scope,
        affected_chips=["gesamte Route"], free_chips=[],
    )


def source_label(alert) -> str:
    from output.renderers.alert.official_alerts import official_alert_source_label

    return official_alert_source_label(alert.source)


def render_trip_mail(alerts: list, *, lat: float = 46.94, lon: float = 12.68,
                     start: datetime = datetime(2026, 1, 30, 6, 0, tzinfo=UTC)) -> str:
    """Echter Trip-Briefing-Renderer (``render_html``) mit echten Segment-Objekten."""
    from app.metric_catalog import build_default_display_config
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    from output.renderers.email.html import render_html
    from zoneinfo import ZoneInfo

    def _dp(h: int) -> ForecastDataPoint:
        return ForecastDataPoint(
            ts=start.replace(hour=h), t2m_c=-4.0, wind10m_kmh=10.0, gust_kmh=20.0,
            precip_1h_mm=0.0, pop_pct=10, cloud_total_pct=40, thunder_level=ThunderLevel.NONE,
            visibility_m=20000, freezing_level_m=2000,
        )

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1500.0, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=lat, lon=lon, elevation_m=2300.0, distance_from_start_km=5.0),
        start_time=start, end_time=start + timedelta(hours=4),
        duration_hours=4.0, distance_km=5.0, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3)
    agg = SegmentWeatherSummary(
        temp_min_c=-8.0, temp_max_c=0.0, temp_avg_c=-4.0, wind_max_kmh=20.0, gust_max_kmh=30.0,
        precip_sum_mm=0.0, cloud_avg_pct=40, humidity_avg_pct=55, thunder_level_max=ThunderLevel.NONE,
    )
    segs = [SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=[_dp(6), _dp(7), _dp(8)]),
        aggregated=agg, fetched_at=datetime.now(UTC), provider="demo",
        official_alerts=list(alerts),
    )]
    return render_html(
        segments=segs, seg_tables=[[{"time": "06", "temp": "-4°", "risk_color": "#2f8a3e"}]],
        trip_name="Tirol Test", report_type="morning", dc=build_default_display_config(),
        night_rows=[], thunder_forecast=None, changes=None, stage_name=None, stage_stats=None,
        multi_day_trend=None, compact_summary="Kalt und klar.", tz=ZoneInfo("Europe/Vienna"),
        friendly_keys=set(),
    )


def render_compare_mail(alerts: list, *, lat: float = 46.94, lon: float = 12.68) -> str:
    """Echte Ortsvergleich-Mail (`render_compare_html`): ein Ort mit den Warnungen, ein Ort ohne."""
    from app.models import ForecastDataPoint
    from app.profile import ActivityProfile
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from output.renderers.email.compare_html import render_compare_html
    from datetime import date

    def _loc(loc_id: str, name: str, dy: float, warns: list) -> LocationResult:
        saved = SavedLocation(id=loc_id, name=name, lat=lat + dy, lon=lon, elevation_m=1800)
        dp = ForecastDataPoint(ts=datetime(2026, 2, 20, 9, 0), t2m_c=-3.0)
        return LocationResult(location=saved, score=70, official_alerts=list(warns), hourly_data=[dp])

    result = ComparisonResult(
        locations=[_loc("loc-tirol", "Tirol-Hütte", 0.0, alerts), _loc("loc-frei", "Talort", 0.3, [])],
        time_window=(9, 16), target_date=date(2026, 2, 20),
    )
    return render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)


def wb_count_texts(html: str) -> list[str]:
    """Inhalt aller `wb-count`-Spans (die Zeile "N aktiv · Stufe ROT (2/3)" des WarnBlocks)."""
    return re.findall(r'class="wb-count"[^>]*>([^<]*)<', html)


def embedded_block(alerts: list, *, count_line: Optional[str] = None) -> str:
    """Warn-Block genau wie ``email/html.py`` ihn baut (dedupe -> bundle -> notices -> embedded)."""
    from output.renderers.alert.official_alerts import (
        OfficialAlertNotice, _bundle_by_hazard_level, dedupe_official_alerts, render_warn_block,
    )

    deduped = _bundle_by_hazard_level(dedupe_official_alerts([(a, ["1"]) for a in alerts]))
    notices = [
        OfficialAlertNotice(alert=a, scope_label="Segment 1", sms_scope="", affected_chips=["Segment 1"],
                            free_chips=[], regions=regions)
        for a, _sids, regions in deduped
    ]
    leading = max((a for a, _, _ in deduped), key=lambda a: a.level)
    return render_warn_block(notices, variant="embedded", source_label=source_label(leading),
                             source_url=leading.url, count_line=count_line)


def lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def call_log() -> list[dict[str, Any]]:
    """Zeilen des Warn-Dienst-Journals dieses Tests (autouse-Fixture lenkt auf tmp um)."""
    from services.official_alerts import warn_egress

    return lines(warn_egress.warn_calls_path())
