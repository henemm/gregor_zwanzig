"""Issue #2792 S1c-4b, Fix-Loop 1 (Adversary F001-F008, Koordinator-Entscheide).

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md v1.5 (AC-1, AC-5, AC-7,
AC-15, AC-19 e, AC-25, AC-27; §5 Punkt 4 und 7). Protokoll:
docs/artifacts/feat-2792-s1c4b-umschalten/adversary-dialog.md.

Jeder Test misst dort, wo die Zusicherung WIRKT (gerenderte Zelle, Token,
Bubble), mit einer Vorlage, die sich von „allgemein" unterscheidet -- eine
feste Allgemein-Ampel oder ``resolve_ampel(None)`` am Einstieg macht ihn rot.
Kern-Schicht: echte Domaenenobjekte, keine Mocks, kein Netz.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from bs4 import BeautifulSoup

UTC = timezone.utc
TZ = ZoneInfo("UTC")


def _ampel(vorlage: str) -> dict:
    from app.ampel import resolve_ampel
    return resolve_ampel({"ampel": {"template": vorlage}})


def _dot(level: str) -> str:
    from output.renderers.email.helpers import _AMPEL_DOT_COLORS
    return _AMPEL_DOT_COLORS[level][0]


# ---------------------------------------------------------------------------
# Trip-Tagesreihe (Gehzeit 08-14 UTC), echtes Aggregat aus dem Produktivpfad
# ---------------------------------------------------------------------------

def _segmente(*, gewitter_11=None, tag: date = date(2026, 7, 20), je_stunde=None):
    """``je_stunde(h) -> dict`` ueberschreibt Felder einzelner Stunden."""
    from app.models import (ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
                            Provider, ThunderLevel, TripSegment)
    from providers.openmeteo import OpenMeteoProvider
    from services.segment_weather import SegmentWeatherService
    gewitter_11 = gewitter_11 or ThunderLevel.MED

    def _felder(h: int) -> dict:
        basis = dict(t2m_c=12.0, wind_chill_c=10.0, wind10m_kmh=12.0, gust_kmh=15.0,
                     precip_1h_mm=0.0, pop_pct=0,
                     thunder_level=gewitter_11 if h == 11 else ThunderLevel.NONE,
                     humidity_pct=50, visibility_m=20000, cloud_total_pct=20)
        basis.update((je_stunde or (lambda _h: {}))(h))
        return basis

    punkte = [ForecastDataPoint(ts=datetime(tag.year, tag.month, tag.day, h, tzinfo=UTC),
                                **_felder(h)) for h in range(24)]
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="test",
                        run=datetime(tag.year, tag.month, tag.day, tzinfo=UTC),
                        grid_res_km=1.0, interp="point_grid")
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.05, lon=11.05, elevation_m=1500, distance_from_start_km=6.0),
        start_time=datetime(tag.year, tag.month, tag.day, 8, tzinfo=UTC),
        end_time=datetime(tag.year, tag.month, tag.day, 14, tzinfo=UTC),
        duration_hours=6.0, distance_km=6.0, ascent_m=500, descent_m=0,
    )
    return [SegmentWeatherService(OpenMeteoProvider())._aggregate_for_segment(
        seg, NormalizedTimeseries(meta=meta, data=punkte),
        fetched_at=datetime(tag.year, tag.month, tag.day, 4, tzinfo=UTC))]


def _trip_html(vorlage: str) -> str:
    from app.models import MetricConfig, TripReportConfig, UnifiedWeatherDisplayConfig
    from output.renderers.trip_report import TripReportFormatter
    dc = UnifiedWeatherDisplayConfig(trip_id="fl1", preset_name=vorlage, metrics=[
        MetricConfig(metric_id=m, enabled=True) for m in ("temperature", "wind", "thunder")])
    return TripReportFormatter().format_email(
        _segmente(), trip_name="FL1", report_type="morning", display_config=dc,
        stage_name="E1", tz=TZ,
        report_config=TripReportConfig(trip_id="fl1", email_format="full")).email_html


def _zeile_11(html: str):
    soup = BeautifulSoup(html, "html.parser")
    tab = soup.find("table", attrs={"data-table": "resp"})
    assert tab is not None, "Vorbedingung: Stundentabelle fehlt"
    for tr in tab.find_all("tr"):
        tds = tr.find_all("td")
        if tds and tds[0].get_text(strip=True) == "11":
            return tds
    raise AssertionError("Vorbedingung: Stundenzeile 11 fehlt")


def _span_bg(td) -> str:
    span = td.find("span", style=lambda s: s and "border-radius:50%" in s)
    assert span is not None, f"kein Punkt in {td}"
    return span["style"].split("background:", 1)[1].split(";", 1)[0]


# ---------------------------------------------------------------------------
# F001 + F004: Trip-Stundentabelle, Gewitter „mittel": Zelle UND Zeilenpunkt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reihenfolge", [("wassersport", "allgemein"), ("allgemein", "wassersport")])
def test_trip_tabelle_gewitter_mittel_zelle_und_zeilenpunkt_nach_abo_ampel(reihenfolge):
    """AC-5: „mittel" ist in Wassersport rot, in Allgemein orange -- in der
    Gewitterzelle (Punkt und Toenung, ``fmt_val``/``_thunder_band``) UND im
    Zeilen-Risikopunkt (``_row_risk``); eine Dublette darf nicht abweichen."""
    from output.renderers.email.html import _ampel_cell_bg
    erwartet = {"wassersport": "red", "allgemein": "orange"}
    for vorlage in reihenfolge:
        tds = _zeile_11(_trip_html(vorlage))
        zelle = next(td for td in tds if td.get("data-label") == "Thdr")
        farbe = erwartet[vorlage]
        assert _span_bg(zelle) == _dot(farbe), (vorlage, "Gewitterpunkt")
        assert f"background:{_ampel_cell_bg(farbe)}" in zelle["style"], (vorlage, "Toenung")
        assert _span_bg(tds[-1]) == _dot(farbe), (vorlage, "Zeilen-Risikopunkt")


# ---------------------------------------------------------------------------
# Nachtrag Fix-Loop 1 (Koordinator-Entscheid zum Nebenbefund): Zeilenpunkt der
# Trip-Stundentabelle bewertet Sicht in Metern nach der Abo-Ampel
# ---------------------------------------------------------------------------

def _trip_html_sicht(vorlage: str, sicht_11_m: float) -> str:
    from app.models import MetricConfig, TripReportConfig, UnifiedWeatherDisplayConfig
    from output.renderers.trip_report import TripReportFormatter
    dc = UnifiedWeatherDisplayConfig(trip_id="fl1", preset_name=vorlage, metrics=[
        MetricConfig(metric_id=m, enabled=True) for m in ("temperature", "wind", "visibility")])
    segmente = _segmente(je_stunde=lambda h: {"visibility_m": sicht_11_m} if h == 11 else {})
    return TripReportFormatter().format_email(
        segmente, trip_name="FL1", report_type="morning", display_config=dc,
        stage_name="E1", tz=TZ,
        report_config=TripReportConfig(trip_id="fl1", email_format="full")).email_html


@pytest.mark.parametrize("reihenfolge", [("allgemein", "skitouren"), ("skitouren", "allgemein")])
@pytest.mark.parametrize("sicht_m, erwartet", [
    (80.0, {"allgemein": "red", "skitouren": "red"}),        # dichter Nebel < 100 m
    (1500.0, {"allgemein": "yellow", "skitouren": "green"}),  # Vorlagen-Unterschied
], ids=["nebel_80m", "sicht_1500m"])
def test_trip_tabelle_zeilenpunkt_sicht_in_metern_nach_abo_ampel(reihenfolge, sicht_m, erwartet):
    """Die Zeilen tragen Sicht in Metern (``_dp_to_row``). Eine Vermutung
    „<= 100 heisst km" machte dichten Nebel (80 m) zu 80 km und den
    Zeilenpunkt gruen -- gleicher Fehler wie in ``narrow._gelb`` (F003)."""
    for vorlage in reihenfolge:
        tds = _zeile_11(_trip_html_sicht(vorlage, sicht_m))
        assert _span_bg(tds[-1]) == _dot(erwartet[vorlage]), (vorlage, sicht_m)


@pytest.mark.parametrize("reihenfolge", [("allgemein", "skitouren"), ("skitouren", "allgemein")])
@pytest.mark.parametrize("sicht_m, erwartet", [
    (80.0, {"allgemein": "red", "skitouren": "red"}),
    (1500.0, {"allgemein": "yellow", "skitouren": "green"}),
], ids=["nebel_80m", "sicht_1500m"])
def test_trip_tabelle_roh_modus_sichtzelle_in_metern_nach_abo_ampel(reihenfolge, sicht_m, erwartet):
    """Nachtrag 2: die Zell-Toenung im Roh-Modus (Sicht nicht in
    ``indicator_keys``) bewertet Meter nach der Abo-Ampel; 80 m Nebel darf
    nicht als 80 km ungetoent bleiben."""
    from app.models import MetricConfig, TripReportConfig, UnifiedWeatherDisplayConfig
    from output.renderers.email.html import _ampel_cell_bg
    from output.renderers.trip_report import TripReportFormatter
    for vorlage in reihenfolge:
        dc = UnifiedWeatherDisplayConfig(trip_id="fl1", preset_name=vorlage, metrics=[
            MetricConfig(metric_id="temperature", enabled=True),
            MetricConfig(metric_id="visibility", enabled=True, use_friendly_format=False,
                         format_mode="raw")])
        html = TripReportFormatter().format_email(
            _segmente(je_stunde=lambda h: {"visibility_m": sicht_m} if h == 11 else {}),
            trip_name="FL1", report_type="morning", display_config=dc, stage_name="E1",
            tz=TZ, report_config=TripReportConfig(trip_id="fl1", email_format="full")).email_html
        zelle = next(td for td in _zeile_11(html) if td.get("data-label") == "Visib")
        bg = _ampel_cell_bg(erwartet[vorlage])
        if bg:
            assert f"background:{bg}" in zelle["style"], (vorlage, sicht_m, zelle["style"])
        else:
            assert "background:" not in zelle["style"], (vorlage, sicht_m, zelle["style"])


# ---------------------------------------------------------------------------
# F007: leere Ampel scheitert laut, mit dem konkreten Fehlertyp
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("leer", [{}, {"metrics": {}}, {"template": "allgemein"}],
                         ids=["leer", "metrics_leer", "ohne_metrics"])
def test_leere_ampel_ist_programmierfehler_valueerror(leer):
    """§5 Punkt 4 / AC-27: eine leere Ampel ist ein Programmierfehler, fuer
    jede Metrik (auch ohne Ampel-Leser) -- ``ValueError``, kein stilles ``{}``
    und kein zufaelliger ``KeyError``."""
    from app.ampel import ampel_stufe, schwellen_aus_ampel
    for metrik in ("gust", "cape"):
        with pytest.raises(ValueError, match="Profil-Ampel leer"):
            schwellen_aus_ampel(leer, metrik)
    with pytest.raises(ValueError, match="Profil-Ampel leer"):
        ampel_stufe(leer, "gust", 50.0)


# ---------------------------------------------------------------------------
# F008: die Klammer traegt weiter das Maximum mit Stunde (kein Infoverlust)
# ---------------------------------------------------------------------------

def _hv(*paare):
    from output.tokens.dto import HourlyValue
    return tuple(HourlyValue(h, v) for h, v in paare)


def _sms_token(symbol: str, feld: str, werte, ampel: dict) -> str:
    from output.tokens.builder import build_token_line
    from output.tokens.dto import DailyForecast, MetricSpec, NormalizedForecast
    line = build_token_line(
        NormalizedForecast(days=(DailyForecast(**{feld: werte}),)),
        [MetricSpec(symbol=symbol, enabled=True)],
        report_type="morning", stage_name="E1", ampel=ampel)
    tok = [t for t in line.tokens if t.symbol == symbol and t.category == "forecast"]
    assert len(tok) == 1, tok
    return tok[0].value


@pytest.mark.parametrize("werte, erwartet", [
    # beide rot (Allgemein Boeen rot ab 60): erste Stunde ab Gelb 70@8, Maximum 110@13
    (((6, 20.0), (8, 70.0), (13, 110.0), (15, 40.0)), "70@8(110@13)"),
    # erste Stunde ab Gelb ist zugleich das Maximum -> ohne Klammer
    (((6, 20.0), (10, 45.0), (12, 35.0)), "45@10"),
    # Maximum gleich dem ersten Wert, spaeter wiederholt -> ohne Klammer
    (((9, 45.0), (14, 45.0)), "45@9"),
    # nichts ab Gelb -> Nullform
    (((9, 20.0), (14, 25.0)), "-"),
])
def test_klammer_traegt_maximum_mit_stunde_sms_und_ausblick(werte, erwartet):
    """F008 (Koordinator-Entscheid): geaendert ist nur, AB WANN hervorgehoben
    wird (AC-19 e); die Klammer zeigt weiter den Hoechstwert mit Stunde, wenn
    er ueber dem ersten hervorgehobenen Wert liegt (``G70@8(110@13)``).
    SMS/Premium-SMS (Token-Builder) und Telegram/Mail-Ausblick
    (``format_trend_tokens``) gleich (Paritaet)."""
    from output.renderers.email.helpers import format_trend_tokens
    allg = _ampel("allgemein")
    serie = _hv(*werte)
    assert _sms_token("G", "gust_hourly", serie, allg) == erwartet
    assert format_trend_tokens({"hourly_gust": serie}, ampel=allg)["gust_token"] == erwartet


def test_klammer_maximum_auch_wenn_es_spaeter_und_gleich_schlimm_ist():
    """Gleichstand der Stufe (beide orange bei Allgemein, 45..59) darf das
    hoehere Maximum nicht verschlucken."""
    allg = _ampel("allgemein")
    assert _sms_token("G", "gust_hourly", _hv((8, 46.0), (12, 58.0)), allg) == "46@8(58@12)"


# ---------------------------------------------------------------------------
# F002: Telegram-Verlauf -- Gewitter-Emoji nach der Ampel des TRIPS
# ---------------------------------------------------------------------------

_LAT, _LON = 42.0, 9.0


def _gewitter_segment(now: datetime):
    from app.models import (ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
                            Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
                            TripSegment)
    from datetime import timedelta
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=_LAT, lon=_LON, elevation_m=900.0),
        end_point=GPXPoint(lat=_LAT + 0.1, lon=_LON + 0.1, elevation_m=1500.0),
        start_time=now, end_time=now + timedelta(hours=10),
        duration_hours=10.0, distance_km=12.0, ascent_m=500.0, descent_m=0.0,
    )
    data = [ForecastDataPoint(ts=now + timedelta(hours=h), t2m_c=18.0, wind10m_kmh=10.0,
                              precip_1h_mm=0.0, thunder_level=ThunderLevel.MED)
            for h in range(0, 8)]
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0), data=data)
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(thunder_level_max=ThunderLevel.MED),
        fetched_at=now, provider="openmeteo")


@pytest.fixture
def verlauf_env(tmp_path, monkeypatch):
    """Zwei Trips (Wassersport, Allgemein) mit derselben Gewitterlage
    „mittel"; echte Trip-/Snapshot-/Processor-Pipeline."""
    from app.loader import save_trip
    from app.models import UnifiedWeatherDisplayConfig
    from app.trip import Stage, Trip, Waypoint
    from services.weather_snapshot import WeatherSnapshotService

    redirect = lambda user_id="default": tmp_path / user_id  # noqa: E731
    for ziel in ("app.loader.get_data_dir", "services.trip_command_processor.get_data_dir",
                 "services.weather_extractor.get_data_dir", "services.weather_snapshot.get_data_dir"):
        monkeypatch.setattr(ziel, redirect, raising=False)
    now = datetime.now(tz=UTC)
    for vorlage in ("wassersport", "allgemein"):
        trip = Trip(
            id=f"fl1-{vorlage}", name=f"FL1 {vorlage}",
            stages=[Stage(id="S1", name="Heute", date=now.date(), waypoints=[
                Waypoint(id="W1", name="Start", lat=_LAT, lon=_LON, elevation_m=900)])],
            display_config=UnifiedWeatherDisplayConfig(
                trip_id=f"fl1-{vorlage}", preset_name=vorlage, metrics=[]),
        )
        save_trip(trip, "default")
        WeatherSnapshotService("default").save(trip.id, [_gewitter_segment(now)], now.date())
    return now


def _antwort(vorlage: str, befehl: str, now: datetime) -> str:
    from services.trip_command_processor import InboundMessage, TripCommandProcessor
    res = TripCommandProcessor().process(InboundMessage(
        channel="telegram", trip_name=f"FL1 {vorlage}", body=f"### {befehl}",
        sender="4711", received_at=now, user_id="default"))
    assert res.success, f"{vorlage}/{befehl}: {res.confirmation_body!r}"
    return res.confirmation_body


@pytest.mark.parametrize("befehl", ["dd_thunder_today", "dd_hours_today", "thdr"])
def test_telegram_verlauf_gewitter_emoji_folgt_der_trip_ampel(verlauf_env, befehl):
    """AC-5/AC-25: „mittel" ist im Wassersport-Trip 🔴, im Allgemein-Trip 🟠 --
    an allen drei Einstiegen (Stunden-Drilldown, Stundentabelle, Ad-hoc-Abruf).
    Eine feste Allgemein-Ampel oder ``resolve_ampel(None)`` faerbte beide 🟠."""
    for reihenfolge in (("wassersport", "allgemein"), ("allgemein", "wassersport")):
        bodies = {v: _antwort(v, befehl, verlauf_env) for v in reihenfolge}
        assert "🔴" in bodies["wassersport"] and "🟠" not in bodies["wassersport"], bodies
        assert "🟠" in bodies["allgemein"] and "🔴" not in bodies["allgemein"], bodies


# ---------------------------------------------------------------------------
# F003: Telegram-Kurzuebersicht -- untere Haelfte, Sicht-Einheit, Nachtwert
# ---------------------------------------------------------------------------

def _nacht(tag: date = date(2026, 7, 20), *, tiefst: float):
    """Nacht am Ziel 14:00 -> 06:00 Folgetag, Tiefpunkt 03:00."""
    from datetime import timedelta
    from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
    start = datetime(tag.year, tag.month, tag.day, 14, tzinfo=UTC)
    punkte = []
    for i in range(17):
        ts = start + timedelta(hours=i)
        t = tiefst if ts.hour == 3 else 2.0
        punkte.append(ForecastDataPoint(ts=ts, t2m_c=t, wind_chill_c=t, wind10m_kmh=5.0,
                                        precip_1h_mm=0.0, visibility_m=20000))
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="test", run=start,
                        grid_res_km=1.0, interp="point_grid")
    return NormalizedTimeseries(meta=meta, data=punkte)


def _kurzuebersicht(vorlage: str, je_stunde, *metriken: str, report_type: str = "morning",
                    nacht=None) -> dict[str, str]:
    from app.models import MetricConfig, TripReportConfig, UnifiedWeatherDisplayConfig
    from output.renderers.trip_report import TripReportFormatter
    dc = UnifiedWeatherDisplayConfig(trip_id="fl1", preset_name=vorlage, metrics=[
        MetricConfig(metric_id=m, enabled=True) for m in metriken])
    rep = TripReportFormatter().format_email(
        _segmente(je_stunde=je_stunde), trip_name="FL1", report_type=report_type,
        display_config=dc, stage_name="E1", tz=TZ, night_weather=nacht,
        report_config=TripReportConfig(trip_id="fl1", email_format="full"))
    bubble = next((b for b in rep.telegram_bubbles if "Kurzübersicht" in b), "")
    assert bubble, f"Vorbedingung: Kurzuebersicht fehlt: {rep.telegram_bubbles}"
    zeilen = {}
    for z in bubble.splitlines():
        if " " in z:
            k, v = z.split(" ", 1)
            zeilen.setdefault(k, v)
    return zeilen


@pytest.mark.parametrize("reihenfolge", [("wassersport", "allgemein"), ("allgemein", "wassersport")])
def test_telegram_untere_haelfte_wind_traegt_stunde_bei_wassersport(reihenfolge):
    """AC-7: Wassersport-Wind 3 km/h liegt unter der unteren Gelbgrenze (8)
    -> die untere Haelfte traegt die Stunde; bei Allgemein (keine untere
    Seite) nicht. Die obere Haelfte (15 km/h, gruen) nie."""
    je = lambda h: {"wind10m_kmh": 15.0 if h == 11 else 3.0}  # noqa: E731
    for vorlage in reihenfolge:
        w = _kurzuebersicht(vorlage, je, "wind")["W"]
        if vorlage == "wassersport":
            assert w == "3@08-15", w
        else:
            assert w == "3-15", w


@pytest.mark.parametrize("reihenfolge", [("skitouren", "allgemein"), ("allgemein", "skitouren")])
def test_telegram_untere_haelfte_temperatur_nach_vorlage(reihenfolge):
    """AC-1: -12 °C um 09 ist bei Allgemein orange (unter -5) -> ``@09`` an der
    unteren Haelfte; bei Skitouren gruen (gelb erst unter -15) -> ohne Stunde."""
    je = lambda h: {"t2m_c": -12.0 if h == 9 else 1.0}  # noqa: E731
    for vorlage in reihenfolge:
        t = _kurzuebersicht(vorlage, je, "temperature")["T"]
        erwartet = "-12.0@09-1.0" if vorlage == "allgemein" else "-12.0-1.0"
        assert t == erwartet, (vorlage, t)


@pytest.mark.parametrize("reihenfolge", [("skitouren", "allgemein"), ("allgemein", "skitouren")])
def test_telegram_sicht_bewertet_meter_nach_vorlage(reihenfolge):
    """Die Kurzuebersicht zeigt Sicht in km (1.5), Zeilen und Ampel fuehren
    Meter: 1500 m ist bei Allgemein gelb (unter 2000), bei Skitouren gruen
    (gelb unter 1000) -- die Stunde nur bei Allgemein."""
    je = lambda h: {"visibility_m": 1500 if h == 11 else 20000}  # noqa: E731
    for vorlage in reihenfolge:
        vs = _kurzuebersicht(vorlage, je, "visibility")["VS"]
        lo = vs.split("-", 1)[0]
        if vorlage == "allgemein":
            assert lo.endswith("@11"), (vorlage, vs)
        else:
            assert "@" not in lo, (vorlage, vs)


@pytest.mark.parametrize("vorlage", ["allgemein", "skitouren"])
def test_telegram_dichter_nebel_unter_100_m_ist_rot_nicht_gruen(vorlage):
    """Die Kurzuebersicht-Zeilen fuehren Sicht in METERN (``_dp_to_row``),
    angezeigt in km. 80 m (dichter Nebel) ist in jeder Vorlage rot und traegt
    die Stunde; eine „<= 100 heisst km"-Vermutung machte daraus 80 km (gruen)."""
    je = lambda h: {"visibility_m": 80 if h == 11 else 20000}  # noqa: E731
    vs = _kurzuebersicht(vorlage, je, "visibility")["VS"]
    assert vs.split("-", 1)[0].endswith("@11"), (vorlage, vs)


def test_telegram_abend_nachtwert_traegt_nie_eine_stunde():
    """§5 / AC-1: am Abend ersetzt der Nacht-Tiefstwert die untere Haelfte;
    er traegt nie eine Stunde -- auch wenn er gelb oder schlechter ist
    (-20 °C ist bei Allgemein rot). Die Tageshoechst-Haelfte bleibt bewertet.
    Der Gehzeit-Tiefstwert (-3 °C um 09) ist selbst gelb: ohne den Schutz
    truege der eingesetzte Nachtwert dessen Stunde."""
    je = lambda h: {"t2m_c": 30.0 if h == 12 else -3.0 if h == 9 else 10.0}  # noqa: E731
    t = _kurzuebersicht("allgemein", je, "temperature", "temperature_night",
                        report_type="evening",
                        nacht=_nacht(tiefst=-20.0))["T"]
    assert t.startswith("-20.0-"), t
    lo, hi = t.split("-20.0-", 1)[0], t.split("-20.0-", 1)[1]
    assert lo == "" and hi == "30.0@12", t


# ---------------------------------------------------------------------------
# F005: Vergleichs-Vorschau (Validator) und Debug-CLI loesen das Abo auf
# ---------------------------------------------------------------------------

def _vorschau(profil: str) -> str:
    from types import SimpleNamespace
    from services.validator_render_service import render_compare_email_preview
    return render_compare_email_preview(SimpleNamespace(
        profile=profil, target_date="2026-07-20", time_window=(8, 16),
        hourly_enabled=False, hourly_metrics=None))


def test_vergleichs_vorschau_kopfzelle_folgt_dem_profil():
    """AC-15/AC-25: die Vorschau reicht das (Pflicht-, validierte) Profil des
    Validators als Preset durch; ``summer_trekking`` ergibt die Vorlage
    ``alpen-trekking`` mit ihrem Label in der Kopfzelle „Profil". Ein leeres
    Preset (still „allgemein") wuerde hier sichtbar."""
    assert "Alpen-Trekking" in _vorschau("summer_trekking")
    assert "Alpen-Trekking" not in _vorschau("wintersport")


def test_debug_cli_trip_bericht_loest_die_trip_ampel_auf(tmp_path, capsys):
    """AC-25 (Debug-Einstieg ``cli._run_trip_report``): dieselbe Offline-
    Vorhersage (Fixture-Provider), Boeen 30 km/h -- Skitouren gruen (gelb ab
    40) -> ``G-``, Allgemein gelb (ab 30) -> ``G30@12``."""
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from app.cli import _run_trip_report
    from app.config import Settings
    from app.debug import DebugBuffer
    from providers.fixture import FixtureProvider
    fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo"
    zeilen = {}
    for vorlage in ("skitouren", "allgemein", "skitouren"):
        trip = {"id": f"cli-{vorlage}", "name": f"CLI {vorlage}", "stages": [{
            "id": "T1", "name": "Tag 1", "date": "2026-01-15", "waypoints": [
                {"id": "G1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 1700,
                 "time_window": "08:00-10:00"},
                {"id": "G2", "name": "Gipfel", "lat": 47.05, "lon": 11.05, "elevation_m": 3200,
                 "time_window": "11:00-13:00"}]}],
            "display_config": {"trip_id": f"cli-{vorlage}", "preset_name": vorlage, "metrics": []}}
        pfad = tmp_path / f"{vorlage}.json"
        pfad.write_text(json.dumps(trip))
        rc = _run_trip_report(SimpleNamespace(trip=str(pfad), compact=True),
                              Settings(dry_run=True, channel="console", report_type="evening"),
                              FixtureProvider(str(fixtures)), DebugBuffer())
        assert rc == 0
        zeilen[vorlage] = next(z for z in capsys.readouterr().out.splitlines() if ": N" in z)
    assert " G- " in zeilen["skitouren"], zeilen
    assert " G30@12 " in zeilen["allgemein"], zeilen
