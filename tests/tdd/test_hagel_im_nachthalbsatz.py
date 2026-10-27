"""TDD RED — Hagel im Nacht-Halbsatz "…, nachts starkes Gewitter ab HH:00"
der Gewitter-Vorschau (Issue #2205, AC-9/AC-10).

SPEC: docs/specs/modules/fix_2205_hagel_im_text_wettercode_bleibt.md

Zielverhalten: Wettercode 95/96/99 bleibt Gewitterstufe hoch. Der Nacht-
Halbsatz (Wortlaut ``app.day_window.format_night_addendum``, Z. 267) traegt
bei einer Nachtstunde mit 96/99 die bestehende Hagelaussage
(``format_hail_note`` -> "Hagel: ja"), bei 95 nicht.

Pruefort = Wirkort: der fertige Vorschau-Eintrag ``forecast["+1"]["text"]``
aus ``TripReportSchedulerService._build_thunder_forecast_from_trend_or_fetch``
-- ueber BEIDE Bauwege (Trend-Zeile = Primaerpfad, Rueckfall-Fetch), die den
Halbsatz unabhaengig voneinander anhaengen. Geprueft wird genau der
Halbsatz-Teil ab ", nachts ".

Fixture diskriminiert Tag vs. Nacht: im Tagesfenster (04-19, 14 Uhr) und
AUSSERHALB (22 Uhr) liegen je ein Gewitter mit eigenem Code. AC-9: Tag 95,
Nacht 96/99. AC-10: Nacht 95, Tag 95 ODER 96 -- der Fall "Tag 96 / Nacht 95"
faengt eine Implementierung, die den Hagelwert des Tages bzw. des ganzen
Kalendertags (``forecast["+1"]["hail"]``; im Trendweg ist er kalendertags-
weit, ``build_outlook_row``) statt den der Nachtstunde liest.

Nachgebildet ist nur der Netzabruf (Unterklasse ``_ZeitplanerOhneNetz``,
Muster ``tests/tdd/test_thunder_origin_preview.py``), kein Mock.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.day_window import resolve_configured_window  # noqa: E402
from app.model_registry import (  # noqa: E402
    cape_ladder_thresholds_jkg,
    lpi_thresholds_jkg,
)
from app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    TripSegment,
)
from output.metric_format import format_hail_note  # noqa: E402
from output.renderers.email.outlook import build_outlook_row  # noqa: E402
from providers.openmeteo import OpenMeteoProvider  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.trip_report_scheduler import TripReportSchedulerService  # noqa: E402
from services.weather_metrics import (  # noqa: E402
    WeatherMetricsService,
    summarize_points,
)

HAGEL = format_hail_note(True)
HAGEL_CODES = (96, 99)
OHNE_HAGEL_CODE = 95
WEGE = ("rueckfall", "primaer")

_TZ = ZoneInfo("UTC")
_LAT, _LON, _MODELL = 47.0, 12.0, "icon_d2"
_HEUTE = date(2026, 8, 20)
_JETZT = datetime(2026, 8, 20, 6, 0, tzinfo=timezone.utc)
_MORGEN = date(2026, 8, 21)
_TAGSTUNDE = 14      # im Fenster 04-19, Code 95
_NACHTSTUNDE = 22    # ausserhalb des Fensters, Code je Test


_PROVIDER = OpenMeteoProvider()


def _dp(h: int, code: int) -> ForecastDataPoint:
    provider = _PROVIDER
    return ForecastDataPoint(
        ts=datetime(_MORGEN.year, _MORGEN.month, _MORGEN.day, h, 0, tzinfo=timezone.utc),
        t2m_c=18.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.5,
        cloud_total_pct=80, humidity_pct=70, pop_pct=60, wmo_code=code,
        thunder_level=provider._parse_thunder_level(code),
        hail_flag=provider._parse_hail_flag(code),
    )


def _punkte(tag_code: int, nacht_code: int) -> list[ForecastDataPoint]:
    """Frische, fusionierte Stundenreihe des Folgetags 00-23 Uhr."""
    def code_fuer(h: int) -> int:
        if h == _TAGSTUNDE:
            return tag_code
        if h == _NACHTSTUNDE:
            return nacht_code
        return 3
    punkte = [_dp(h, code_fuer(h)) for h in range(0, 24)]
    region = thunder_region_for(_LAT, _LON)
    _fuse_thunder_levels(
        punkte, cape_ladder_thresholds_jkg(_MODELL, region),
        lpi_thresholds_jkg(region),
    )
    return punkte


def _etappe(punkte: list[ForecastDataPoint]) -> SegmentWeatherData:
    reihe = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                          grid_res_km=1.0),
        data=punkte,
    )
    seg = TripSegment(
        segment_id=2,
        start_point=GPXPoint(lat=_LAT, lon=_LON, elevation_m=1000.0),
        end_point=GPXPoint(lat=_LAT + 0.1, lon=_LON + 0.1, elevation_m=1200.0),
        start_time=datetime(_MORGEN.year, _MORGEN.month, _MORGEN.day, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(_MORGEN.year, _MORGEN.month, _MORGEN.day, 17, 0, tzinfo=timezone.utc),
        duration_hours=11.0, distance_km=10.0, ascent_m=500.0, descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=reihe,
        aggregated=WeatherMetricsService().compute_basis_metrics(reihe, tz=None),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


class _TripAttrappe:
    """Echtes Datenobjekt: die zwei Zugriffe der Weiche auf den Trip."""
    report_config = None

    def get_future_stages(self, target_date):
        return []


class _ZeitplanerOhneNetz(TripReportSchedulerService):
    """Produktiver Zeitplaner, einzig der Netzabruf liefert fertige Segmente."""

    def __init__(self, segmente: list[SegmentWeatherData]) -> None:
        super().__init__(user_id="default")
        self._segmente = list(segmente)

    def _collect_future_stage_weather(self, trip, target_date, now_utc,
                                      wanted_dates=None):
        return list(self._segmente)


def _eintrag(tag_code: int, nacht_code: int, weg: str, *, punkte=None,
             night_weather=None) -> dict:
    """Der "+1"-Vorschau-Eintrag -- nachweislich aus dem gewaehlten Bauweg.

    ``punkte``/``night_weather`` (optional): eigene Etappen-Stundenreihe bzw.
    die separate Nacht-Zeitreihe (00-06 Uhr Folgetag), wie der Versandpfad sie
    uebergibt."""
    if punkte is None:
        punkte = _punkte(tag_code, nacht_code)
    extra = {} if night_weather is None else {"night_weather": night_weather}
    if weg == "rueckfall":
        zeitplaner = _ZeitplanerOhneNetz([_etappe(punkte)])
        trend = None
    else:
        win_start, win_end = resolve_configured_window(None, None)
        zeile = build_outlook_row(
            summarize_points(punkte), punkte, "Fr", _TZ,
            day_window_start_hour=win_start, day_window_end_hour=win_end,
        )
        zeile["date"] = _MORGEN
        zeile["name"] = "Etappe B"
        trend = [zeile]
        # Leere Segmentliste: der Rueckfall kann strukturell nichts liefern,
        # ein "+1"-Eintrag stammt also sicher aus der Trend-Zeile.
        zeitplaner = _ZeitplanerOhneNetz([])
    forecast = zeitplaner._build_thunder_forecast_from_trend_or_fetch(
        _TripAttrappe(), _HEUTE, now_utc=_JETZT, tz=_TZ, multi_day_trend=trend,
        **extra,
    )
    assert forecast and "+1" in forecast, (
        f"Vorbedingung ({weg}): '+1'-Eintrag erwartet, erhalten {forecast!r}")
    return forecast["+1"]


def _nacht_halbsatz(eintrag: dict, weg: str) -> str:
    """Der Halbsatz ab ", nachts " -- und belegen, dass er mit einer
    Gewitteraussage entsteht (kein leeres Gruen)."""
    text = eintrag["text"]
    assert ", nachts " in text, (
        f"Vorbedingung ({weg}): Nacht-Halbsatz fehlt, Text {text!r}")
    _tagesteil, halbsatz = text.split(", nachts ", 1)
    assert "Gewitter" in halbsatz, (
        f"Vorbedingung ({weg}): Halbsatz ohne Gewitteraussage: {halbsatz!r}")
    return halbsatz


@pytest.mark.parametrize("weg", WEGE)
@pytest.mark.parametrize("code", HAGEL_CODES)
def test_ac9_nacht_halbsatz_nennt_hagel_bei_96_99(code, weg):
    """AC-9.

    GIVEN ein Folgetag mit Gewitter Code 95 im Tagesfenster und einer
          Nachtstunde (22 Uhr, ausserhalb des Fensters) mit Code 96 bzw. 99.
    WHEN  der Vorschau-Eintrag samt Nacht-Halbsatz gebaut wird (Trend- UND
          Rueckfallweg).
    THEN  enthaelt der Halbsatz "nachts starkes Gewitter ab 22:00" die
          bestehende Hagelaussage.

    RED heute: ``night_addendum``/``format_night_addendum`` kennen nur
    (Stufe, Stunde), keinen Hagelwert.
    """
    halbsatz = _nacht_halbsatz(_eintrag(OHNE_HAGEL_CODE, code, weg), weg)
    assert "Hagel" in halbsatz, (
        f"AC-9 ({weg}): Nacht-Halbsatz muss bei Code {code} die Hagelaussage "
        f"{HAGEL!r} tragen, ist {halbsatz!r}")


@pytest.mark.parametrize("weg", WEGE)
@pytest.mark.parametrize("tag_code", (OHNE_HAGEL_CODE, 96))
def test_ac10_nacht_halbsatz_ohne_hagel_bei_95(tag_code, weg):
    """AC-10.

    GIVEN derselbe Aufbau, die Nachtstunde traegt ausschliesslich Code 95;
          das Tagesgewitter traegt 95 bzw. 96 (Diskriminator: Hagel am Tag
          darf nicht in den Nacht-Halbsatz wandern).
    WHEN  der Vorschau-Eintrag gebaut wird.
    THEN  entsteht der Nacht-Halbsatz (kein leeres Gruen), aber ohne
          Hagelaussage.
    """
    halbsatz = _nacht_halbsatz(_eintrag(tag_code, OHNE_HAGEL_CODE, weg), weg)
    assert "Hagel" not in halbsatz, (
        f"AC-10 ({weg}): bei Code 95 keine Hagelaussage im Halbsatz: "
        f"{halbsatz!r}")


# ═══════ Zugestellte Vorschau-Zeile: Tages- und Nacht-Hagel getrennt ═══════
#
# Pruefort = Wirkort: die fertig gerenderte Zeile der Gewitter-Vorschau in
# Klartext UND HTML (``TripReportFormatter.format_email``). Faengt die
# Doppelung "· Hagel: ja · Hagel: ja" und einen Tages-Hagel, der hinter dem
# Nacht-Halbsatz klebt (Renderer-Suffix aus ``fc["hail"]``).

_KLARTEXT_KOPF = "━━ Gewitter-Vorschau ━━"


def _heutige_etappe() -> SegmentWeatherData:
    """Gewitterfreie Etappe des Briefing-Tags -- nur Traeger der Mail."""
    punkte = [
        ForecastDataPoint(
            ts=datetime(_HEUTE.year, _HEUTE.month, _HEUTE.day, h, 0,
                        tzinfo=timezone.utc),
            t2m_c=18.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.0,
            cloud_total_pct=20, humidity_pct=50, pop_pct=0, wmo_code=1,
            thunder_level=_PROVIDER._parse_thunder_level(1),
            hail_flag=_PROVIDER._parse_hail_flag(1),
        )
        for h in range(6, 18)
    ]
    etappe = _etappe(punkte)
    etappe.segment.start_time = etappe.segment.start_time.replace(day=_HEUTE.day)
    etappe.segment.end_time = etappe.segment.end_time.replace(day=_HEUTE.day)
    return etappe


def _gerenderte_zeilen(tag_code: int, nacht_code: int, weg: str) -> dict[str, str]:
    """Die Vorschau-Zeile des Folgetags aus Klartext und HTML der Mail."""
    from bs4 import BeautifulSoup

    from app.metric_catalog import build_default_display_config
    from output.renderers.trip_report import TripReportFormatter

    eintrag = _eintrag(tag_code, nacht_code, weg)
    bericht = TripReportFormatter().format_email(
        [_heutige_etappe()], "Hagel-Trip", "morning",
        display_config=build_default_display_config(), tz=_TZ,
        stage_name="Etappe A", thunder_forecast={"+1": eintrag},
    )
    datum = eintrag["date"]
    klartext = [ln.strip() for ln in bericht.email_plain.split(_KLARTEXT_KOPF, 1)[1]
                .splitlines() if ln.strip().startswith(f"{datum}:")]
    suppe = BeautifulSoup(bericht.email_html, "html.parser")
    html = [li.get_text() for li in suppe.find_all("li")
            if li.get_text().startswith(f"{datum}:")]
    assert len(klartext) == 1 and len(html) == 1, (
        f"Vorbedingung ({weg}): genau eine Vorschau-Zeile je Fassung, "
        f"Klartext {klartext!r}, HTML {html!r}")
    for fassung, zeile in (("Klartext", klartext[0]), ("HTML", html[0])):
        assert ", nachts " in zeile, (
            f"Vorbedingung ({weg}, {fassung}): Nacht-Halbsatz fehlt: {zeile!r}")
    return {"Klartext": klartext[0], "HTML": html[0]}


@pytest.mark.parametrize("weg", WEGE)
def test_zeile_tageshagel_steht_einmal_vor_dem_nacht_halbsatz(weg):
    """GIVEN Tag 96 / Nacht 95. THEN "Hagel: ja" genau einmal, VOR ", nachts"."""
    for fassung, zeile in _gerenderte_zeilen(96, OHNE_HAGEL_CODE, weg).items():
        tagesteil, nachtteil = zeile.split(", nachts ", 1)
        assert zeile.count(HAGEL) == 1 and HAGEL in tagesteil, (
            f"{weg}/{fassung}: Tages-Hagel genau einmal im Tagesteil erwartet, "
            f"ist {zeile!r}")


@pytest.mark.parametrize("weg", WEGE)
def test_zeile_nachthagel_steht_einmal_im_nacht_halbsatz(weg):
    """GIVEN Tag 95 / Nacht 96. THEN "Hagel: ja" genau einmal, im Halbsatz."""
    for fassung, zeile in _gerenderte_zeilen(OHNE_HAGEL_CODE, 96, weg).items():
        tagesteil, nachtteil = zeile.split(", nachts ", 1)
        assert zeile.count(HAGEL) == 1 and HAGEL in nachtteil, (
            f"{weg}/{fassung}: Nacht-Hagel genau einmal im Nacht-Halbsatz "
            f"erwartet, ist {zeile!r}")


@pytest.mark.parametrize("weg", WEGE)
def test_zeile_tag_und_nachthagel_je_teil_einmal(weg):
    """GIVEN Tag 96 / Nacht 96. THEN genau zweimal, je Teil einmal."""
    for fassung, zeile in _gerenderte_zeilen(96, 96, weg).items():
        tagesteil, nachtteil = zeile.split(", nachts ", 1)
        assert (zeile.count(HAGEL) == 2 and tagesteil.count(HAGEL) == 1
                and nachtteil.count(HAGEL) == 1), (
            f"{weg}/{fassung}: je Teil genau eine Hagelaussage erwartet, "
            f"ist {zeile!r}")


# ═══════ Separate Nacht-Zeitreihe ``night_weather`` (F002-A) ═══════
#
# Der Versandpfad reicht die Nacht-Reihe (00-06 Uhr Folgetag) getrennt von der
# Etappen-Reihe durch; fuer ihre Stunden schlaegt sie die Etappe -- fuer die
# Stufe UND fuer Hagel (``night_addendum``). Die Stunde 02:00 liegt ausserhalb
# des Tagesfensters 04-19, nur dort entsteht der Halbsatz.

_NACHT_REIHE_STUNDE = 2


def _fusionierte_reihe(codes: dict[int, int], stunden) -> list[ForecastDataPoint]:
    """Stundenpunkte des Folgetags (Code 3 ausser ``codes``), echt fusioniert."""
    punkte = [_dp(h, codes.get(h, 3)) for h in stunden]
    region = thunder_region_for(_LAT, _LON)
    _fuse_thunder_levels(punkte, cape_ladder_thresholds_jkg(_MODELL, region),
                         lpi_thresholds_jkg(region))
    return punkte


def _nachtreihe(code: int) -> NormalizedTimeseries:
    """``night_weather``: 00-06 Uhr des Folgetags, Gewitter ``code`` um 02:00."""
    return NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model=_MODELL, grid_res_km=2.0),
        data=_fusionierte_reihe({_NACHT_REIHE_STUNDE: code}, range(0, 7)),
    )


def _etappe_mit_nachtstunde(code: int) -> list[ForecastDataPoint]:
    """Etappen-Reihe 00-23: Tagesgewitter 95 um 14 Uhr, Code ``code`` um 02:00."""
    return _fusionierte_reihe(
        {_TAGSTUNDE: OHNE_HAGEL_CODE, _NACHT_REIHE_STUNDE: code}, range(0, 24))


@pytest.mark.parametrize("weg", WEGE)
@pytest.mark.parametrize("code", HAGEL_CODES)
def test_nachthagel_nur_in_nachtreihe_steht_einmal_im_halbsatz(code, weg):
    """AC-9 ueber die separate Nacht-Reihe.

    GIVEN Etappe ohne Gewitter um 02:00, ``night_weather`` meldet um 02:00
          Code 96 bzw. 99.
    WHEN  der Vorschau-Eintrag mit ``night_weather`` gebaut wird.
    THEN  traegt der Nacht-Halbsatz "Hagel: ja" genau einmal.
    """
    halbsatz = _nacht_halbsatz(_eintrag(
        0, 0, weg, punkte=_etappe_mit_nachtstunde(3),
        night_weather=_nachtreihe(code)), weg)
    assert halbsatz.count(HAGEL) == 1, (
        f"F002-A ({weg}): Nacht-Hagel aus night_weather muss genau einmal im "
        f"Halbsatz stehen, ist {halbsatz!r}")


@pytest.mark.parametrize("weg", WEGE)
def test_nachtreihe_95_schlaegt_etappenhagel_derselben_stunde(weg):
    """AC-10 ueber die separate Nacht-Reihe (widersprechende Quellen).

    GIVEN Etappe meldet um 02:00 Code 96, ``night_weather`` fuer DIESELBE
          Stunde Code 95.
    WHEN  der Vorschau-Eintrag mit ``night_weather`` gebaut wird.
    THEN  entsteht der Nacht-Halbsatz ohne Hagelaussage -- die Nacht-Reihe
          ist fuer ihre Stunden die massgebliche Quelle (#1498/#1653).
    """
    halbsatz = _nacht_halbsatz(_eintrag(
        0, 0, weg, punkte=_etappe_mit_nachtstunde(96),
        night_weather=_nachtreihe(OHNE_HAGEL_CODE)), weg)
    assert "Hagel" not in halbsatz, (
        f"F002-A ({weg}): night_weather Code 95 muss den Etappen-Hagel derselben "
        f"Stunde ueberstimmen, Halbsatz {halbsatz!r}")
