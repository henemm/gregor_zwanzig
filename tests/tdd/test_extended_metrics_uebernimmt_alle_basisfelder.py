"""TDD RED — Der erweiterte Tageswert verliert keine Basisfelder (Issue #2195).

SPEC: docs/specs/modules/bug_2195_tageswert_feldverlust.md (AC-1 bis AC-9, AC-11)
KONTEXT: docs/context/fix-2195-extended-metrics-feldverlust.md
AC-10 bewachen die bestehenden Tests in ``tests/unit/test_weather_metrics.py``
(``test_extended_preserves_basis_metrics``, ``test_extended_aggregation_config_merged``).

Zwei Naehte, beide am WIRKORT geprueft:

1. ``WeatherMetricsService.compute_extended_metrics()`` baut ein NEUES Summary
   aus einer festen Feldliste und laesst ``thunder_level_max_signals`` (die
   Zutaten der Gewitter-Hoechststufe) und ``hail_flag`` fallen. Das Ergebnis
   ist ``seg.aggregated`` jedes Trip-Segments (``SegmentWeatherService``) —
   also das, was der Schnappschuss speichert und der Kommando-Pfad liest.
2. ``aggregate_stage()`` kennt die Regel ``union_of_max_carriers`` nicht und
   faellt auf ``values[0]`` zurueck: die Traeger des ERSTEN Segments mit einem
   Wert, nicht die des Hoechststufen-Segments.

RED heute (erwartet): AC-1, AC-2, AC-3 (Feld-fuer-Feld-Teil), AC-4, AC-5,
AC-6, AC-7 (Hagel-Teil), AC-8 (Hagel-Teil). Waechter (gruen): AC-3
Nichtueberschneidung, AC-9 (#2186-Workaround), AC-11.

Kein Mock-Theater: Stufen und Traegerlisten entstehen ueber die ECHTE Fusion
(``thunder_enrichment._fuse_thunder_levels`` mit den Leitern aus
``app.model_registry``), Aggregate ueber die ECHTEN Rechenstufen, der
Kommando-Pfad ueber einen echt gespeicherten Wetter-Schnappschuss und
``TripCommandProcessor.process()``. Der einzige Test-Baustein ist ein kleiner
Provider, der feste Zeitreihen liefert (echte Protokoll-Erfuellung, Muster
``_KeyedFakeProvider`` aus ``test_stage_weather_parity.py``).
Fixture-Bausteine nach ``test_thunder_origin_trip.py``,
``test_gewitter_herkunft_kanalabhaengig.py``, ``test_thunder_origin_outlook.py``
und ``test_tageswert_fenster_erhaelt_alle_metriken.py``.
"""
from __future__ import annotations

import dataclasses
import json
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Pfadregel #1409: Pruefling relativ zur EIGENEN Testdatei aufloesen.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from bs4 import BeautifulSoup  # noqa: E402

from app.day_window import (  # noqa: E402
    resolve_configured_window, segment_window_points,
)
from app.loader import get_snapshots_dir, save_trip  # noqa: E402
from app.metric_catalog import build_default_display_config, get_metric  # noqa: E402
from app.model_registry import (  # noqa: E402
    cape_ladder_thresholds_jkg, lpi_thresholds_jkg,
)
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
    PrecipType, Provider, SegmentWeatherData, SegmentWeatherSummary,
    ThunderLevel, TripSegment,
)
from app.thunder_scale import THUNDER_SIGNAL_LABEL_DE  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from output.metric_format import (  # noqa: E402
    format_hail_note, thunder_signal_label,
)
from output.renderers.email.outlook import build_outlook_row  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.segment_weather import SegmentWeatherService  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage, TripCommandProcessor, _thunder_words,
)
from services.weather_cache import WeatherCacheService  # noqa: E402
from services.weather_extractor import WeatherExtractor  # noqa: E402
from services.weather_metrics import (  # noqa: E402
    WeatherMetricsService, aggregate_stage,
)
from services.weather_snapshot import WeatherSnapshotService  # noqa: E402
from utils.timezone import location_tz  # noqa: E402

_LAT, _LON, _MODELL = 47.0, 12.0, "icon_d2"   # Gebiet DE_ALPEN, Europe/Vienna
_JETZT = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
_HEUTE = _JETZT.date()
_MORGEN = date(2026, 8, 21)
_UTC = ZoneInfo("UTC")

ALLE_ZUTATEN = tuple(THUNDER_SIGNAL_LABEL_DE.values())


# ---------------------------------------------------------------------------
# Fixture-Bausteine: Rohwerte rein, echte Rechnung raus
# ---------------------------------------------------------------------------

def _dp(h: int, *, tag: date = _HEUTE, cape=None, cin=None, lpi=None,
        dichte=None, hail=None, **extra) -> ForecastDataPoint:
    """Ein Stundenpunkt mit ROHWERTEN — Stufe und Traeger rechnet die Fusion.

    Geeichte Leitern DE_ALPEN/icon_d2 (am Code gemessen): ``cape=1500, cin=5``
    -> hoch ['cape']; ``cape=400, cin=5`` -> leicht ['cape']; ``lpi=60`` ->
    hoch ['blitzpotenzial']; ``dichte=0.005`` -> leicht ['blitzdichte'];
    ``cape=100`` -> kein Gewitter.
    """
    werte = dict(t2m_c=20.0, wind10m_kmh=8.0, gust_kmh=12.0, precip_1h_mm=0.0,
                 cloud_total_pct=40, humidity_pct=50)
    werte.update(extra)
    return ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, h, 0, tzinfo=timezone.utc),
        cape_jkg=cape, convective_inhibition_jkg=cin,
        lightning_potential_lpi_jkg=lpi, lightning_density_per_km2_3h=dichte,
        hail_flag=hail, **werte,
    )


def _reihe(punkte: list[ForecastDataPoint]) -> NormalizedTimeseries:
    """Zeitreihe, deren Punkte durch die ECHTE Fusion gelaufen sind."""
    region = thunder_region_for(_LAT, _LON)
    _fuse_thunder_levels(
        punkte, cape_ladder_thresholds_jkg(_MODELL, region),
        lpi_thresholds_jkg(region),
    )
    return NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model=_MODELL, grid_res_km=1.0),
        data=punkte,
    )


def _trip_segment(*, tag: date, start_h: int, end_h: int, seg_id: int = 1,
                  lon: float = _LON) -> TripSegment:
    return TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=_LAT, lon=lon, elevation_m=1000.0),
        end_point=GPXPoint(lat=_LAT + 0.1, lon=lon + 0.1, elevation_m=1200.0),
        start_time=datetime(tag.year, tag.month, tag.day, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(tag.year, tag.month, tag.day, end_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h), distance_km=10.0,
        ascent_m=500.0, descent_m=200.0,
    )


class _FesteReiheProvider:
    """Echte WeatherProvider-Implementierung (kein unittest.mock): liefert je
    Startkoordinate eine vorab gebaute Zeitreihe. Kein Netzzugriff."""

    name = "feste-reihe"

    def __init__(self, reihen: dict[tuple[float, float], NormalizedTimeseries]) -> None:
        self._reihen = reihen

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble: bool = True,
                       enrich_snow: bool = True) -> NormalizedTimeseries:
        return self._reihen[(location.latitude, location.longitude)]


def _segment_ueber_service(punkte: list[ForecastDataPoint], *, tag: date,
                           start_h: int, end_h: int, seg_id: int = 1,
                           lon: float = _LON) -> SegmentWeatherData:
    """Segment, dessen ``aggregated`` der PRODUKTIVE Segment-Pfad rechnet:
    ``SegmentWeatherService`` -> ``compute_basis_metrics()`` ->
    ``compute_extended_metrics()`` (segment_weather.py). Eigener Cache je
    Aufruf — der Default ist ein prozessweiter Singleton."""
    reihe = _reihe(punkte)
    segment = _trip_segment(tag=tag, start_h=start_h, end_h=end_h,
                            seg_id=seg_id, lon=lon)
    service = SegmentWeatherService(
        _FesteReiheProvider({(_LAT, lon): reihe}), cache=WeatherCacheService(),
    )
    ergebnis = service.fetch_segment_weather(segment)
    assert not ergebnis.has_error, (
        f"Vorbedingung: der Segment-Abruf darf nicht scheitern "
        f"(z.B. Budget-Drossel): {ergebnis.error_message!r}")
    return ergebnis


def _segment_mit_basis(punkte: list[ForecastDataPoint], *, seg_id: int = 1,
                       tag: date = _HEUTE) -> SegmentWeatherData:
    """Segment, dessen ``aggregated`` NUR die Basisstufe rechnet — beide
    Felder sind damit sicher gesetzt. Fuer die ``aggregate_stage()``-ACs, die
    die Etappen-Regel isoliert von der Extended-Naht pruefen."""
    reihe = _reihe(punkte)
    return SegmentWeatherData(
        segment=_trip_segment(tag=tag, start_h=6, end_h=17, seg_id=seg_id),
        timeseries=reihe,
        aggregated=WeatherMetricsService().compute_basis_metrics(reihe, tz=None),
        fetched_at=datetime(2026, 8, 20, 5, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _gewitter_hagel_punkte(tag: date = _HEUTE) -> list[ForecastDataPoint]:
    """12-16 Uhr UTC: Hoechststufe um 14 Uhr allein ueber CAPE, bestaetigte
    Hagelstunde um 15 Uhr, sonst ruhig."""
    return [
        _dp(12, tag=tag, cape=100.0, cin=5.0),
        _dp(13, tag=tag, cape=100.0, cin=5.0),
        _dp(14, tag=tag, cape=1500.0, cin=5.0),
        _dp(15, tag=tag, cape=100.0, cin=5.0, hail=True),
        _dp(16, tag=tag, cape=100.0, cin=5.0),
    ]


class _Kommando:
    """Speichert Trip + Schnappschuss und stellt die Kommandofrage ueber den
    ECHTEN ``TripCommandProcessor.process()`` (Muster
    ``test_gewitter_herkunft_kanalabhaengig.py``)."""

    def __init__(self) -> None:
        self.user_id = f"feldverlust-{uuid.uuid4().hex[:8]}"
        self.trip_id = f"feldverlust-{uuid.uuid4().hex[:8]}"
        self.trip_name = f"Feldverlust {uuid.uuid4().hex[:4]}"

    def speichere(self, segmente: list[SegmentWeatherData]) -> None:
        save_trip(Trip(id=self.trip_id, name=self.trip_name, stages=[
            Stage(id="S1", name="Heute", date=_HEUTE, waypoints=[
                Waypoint(id="W1", name="Start", lat=_LAT, lon=_LON, elevation_m=1000),
            ]),
        ]), self.user_id)
        WeatherSnapshotService(self.user_id).save(self.trip_id, segmente, _HEUTE)

    def frage(self, kommando: str = "GEWITTER", *, kanal: str = "telegram") -> str:
        ergebnis = TripCommandProcessor().process(InboundMessage(
            channel=kanal, trip_name=self.trip_name, body=kommando,
            sender="4917000000001", received_at=_JETZT, user_id=self.user_id,
        ))
        assert ergebnis.success, (
            f"Vorbedingung: {kommando!r} auf {kanal!r} muss antworten: "
            f"{ergebnis.confirmation_body!r}")
        return ergebnis.confirmation_body

    def als_alt_schnappschuss(self) -> None:
        """Schnappschuss wie VOR diesem Fix/vor #1680: beide Felder fehlen im
        Aggregat, die Stundentraeger ebenso (Muster ``_alt_schnappschuss``
        aus ``test_thunder_origin_trip.py``)."""
        pfad = get_snapshots_dir(self.user_id) / f"{self.trip_id}.json"
        roh = json.loads(pfad.read_text())
        for seg in roh["segments"]:
            seg["aggregated"].pop("thunder_level_max_signals", None)
            seg["aggregated"].pop("hail_flag", None)
            for stunde in seg.get("hourly", []):
                stunde.pop("thunder_level_signals", None)
        pfad.write_text(json.dumps(roh, indent=2))


def _gesetzte_felder(summary: SegmentWeatherSummary) -> dict:
    return {
        f.name: getattr(summary, f.name)
        for f in dataclasses.fields(SegmentWeatherSummary)
        if f.name != "aggregation_config" and getattr(summary, f.name) is not None
    }


# ═══════════════ AC-1: seg.aggregated traegt beide Basisfelder ═══════════════

def test_ac1_segment_aggregat_traegt_traeger_und_hagel_wie_die_basisstufe():
    """AC-1.

    GIVEN ein Segment mit Gewitter-Hoechststufe (Traeger CAPE) und einer
          Hagelstunde in seiner Stundenreihe,
    WHEN  ``SegmentWeatherService`` das Segment ueber
          ``compute_basis_metrics()`` -> ``compute_extended_metrics()``
          verarbeitet,
    THEN  tragen ``seg.aggregated.thunder_level_max_signals`` und
          ``seg.aggregated.hail_flag`` denselben Wert wie das direkte Ergebnis
          von ``compute_basis_metrics()`` derselben gefilterten Reihe.

    RED heute: beide Felder sind am Segment-Aggregat ``None``.
    """
    seg = _segment_ueber_service(_gewitter_hagel_punkte(), tag=_HEUTE,
                                 start_h=12, end_h=17)

    gefiltert = NormalizedTimeseries(
        meta=seg.timeseries.meta,
        data=segment_window_points(seg.segment.start_time, seg.segment.end_time,
                                   seg.timeseries.data),
    )
    fenster = resolve_configured_window(seg.segment.day_window_start_hour,
                                        seg.segment.day_window_end_hour)
    basis = WeatherMetricsService().compute_basis_metrics(
        gefiltert, tz=location_tz(seg.segment.start_point),
        day_window_start_hour=fenster[0], day_window_end_hour=fenster[1],
    )
    assert basis.thunder_level_max_signals == ["cape"] and basis.hail_flag is True, (
        f"Vorbedingung: die Basisstufe muss beide Felder setzen, sonst beweist "
        f"der Vergleich nichts: {basis.thunder_level_max_signals!r}, "
        f"{basis.hail_flag!r}")

    assert seg.aggregated.thunder_level_max_signals == basis.thunder_level_max_signals, (
        f"AC-1: seg.aggregated hat die Gewitter-Traeger der Basisstufe verloren: "
        f"{seg.aggregated.thunder_level_max_signals!r} statt "
        f"{basis.thunder_level_max_signals!r}")
    assert seg.aggregated.hail_flag == basis.hail_flag, (
        f"AC-1: seg.aggregated hat das Hagel-Kennzeichen der Basisstufe "
        f"verloren: {seg.aggregated.hail_flag!r} statt {basis.hail_flag!r}")


# ═══════════ AC-2: Kommando-Pfad liest das gespeicherte Aggregat ═══════════

def test_ac2_gewitter_kommando_nennt_traeger_und_hagel_aus_gespeichertem_aggregat():
    """AC-2.

    GIVEN ein Segment (12-17 Uhr UTC), das zum Anfragezeitpunkt (09 Uhr UTC)
          noch nicht begonnen hat — sein gespeichertes Aggregat wird also
          UNVERAENDERT gelesen, ohne #2186-Neuberechnung —, mit Gewitter-
          Hoechststufe samt Traeger CAPE und einer Hagelstunde, das Aggregat
          vom produktiven ``SegmentWeatherService`` gerechnet,
    WHEN  der Nutzer ``GEWITTER`` ueber Telegram sendet (``_fmt_gewitter()``
          aus ``_aggregate_day()``),
    THEN  lautet die Antwort
          ``⛈ Gewitter heute (DD.MM): {stufe} · {herkunft} · {hagel}``.

    RED heute: ``agg["thunder_signals"]``/``agg["hail_flag"]`` stammen aus
    einem feldlosen ``seg.aggregated`` — beide Zusaetze bleiben leer.
    """
    seg = _segment_ueber_service(_gewitter_hagel_punkte(), tag=_HEUTE,
                                 start_h=12, end_h=17)
    # Marke: ueberlebt sie bis in die Timeline, wurde NICHT neu gerechnet.
    marke = 37.5
    seg = dataclasses.replace(seg, aggregated=dataclasses.replace(
        seg.aggregated, temp_max_c=marke))
    kommando = _Kommando()
    kommando.speichere([seg])

    zeitachse = WeatherExtractor(user_id=kommando.user_id).timeline(
        kommando.trip_id, from_time=_JETZT)
    assert [p.metrics.temp_max_c for p in zeitachse.points] == [marke], (
        "Vorbedingung: das Segment darf NICHT ueber den #2186-Neuberechnungs-"
        "pfad laufen (der Workaround zoege beide Felder nach = falsches Gruen)")

    antwort = kommando.frage("GEWITTER", kanal="telegram")

    stufe = _thunder_words()[ThunderLevel.HIGH.name]
    erwartet = (f"⛈ Gewitter heute ({_HEUTE:%d.%m}): {stufe} · "
                f"{thunder_signal_label('cape')} · {format_hail_note(True)}")
    assert antwort == erwartet, (
        f"AC-2: die GEWITTER-Antwort muss Herkunft UND Hagel-Zusatz aus dem "
        f"gespeicherten Tageswert tragen.\n  erwartet: {erwartet!r}\n"
        f"  erhalten: {antwort!r}")


# ═════════════ AC-3: generischer Waechter ueber alle Basisfelder ═════════════

def _vollstaendige_reihe() -> NormalizedTimeseries:
    """Eine Reihe, in der die Basisstufe JEDES ihrer Felder setzt."""
    punkte = []
    for h in range(8, 14):
        punkte.append(_dp(
            h, cape=1500.0 if h == 10 else 100.0, cin=5.0,
            hail=True if h == 11 else None,
            precip_1h_mm=6.0 if h == 12 else 0.2, visibility_m=20000,
            wmo_code=95 if h == 10 else 2, is_day=1, dni_wm2=300.0,
            dewpoint_c=10.0, pressure_msl_hpa=1010.0, wind_chill_c=18.0,
            pop_pct=50, uv_index=5.0, cloud_low_pct=20, cloud_mid_pct=20,
            cloud_high_pct=20, snowfall_limit_m=3000, freezing_level_m=3500,
        ))
    return _reihe(punkte)


def test_ac3_jedes_von_der_basis_gesetzte_feld_ueberlebt_die_erweiterung():
    """AC-3 (Feld-fuer-Feld).

    GIVEN eine Stundenreihe, in der die Basisstufe JEDES Feld mit einer
          Aggregationsregel setzt (inkl. Traeger und Hagel),
    WHEN  ``compute_basis_metrics()`` gefolgt von ``compute_extended_metrics()``
          laeuft,
    THEN  ist jedes von der Basis gesetzte Feld (ueber
          ``dataclasses.fields()``, ausser ``aggregation_config``) im
          erweiterten Ergebnis identisch — ohne Feldliste im Test, also auch
          fuer ein kuenftiges Basisfeld.

    RED heute: ``thunder_level_max_signals`` und ``hail_flag`` fehlen.
    """
    reihe = _vollstaendige_reihe()
    svc = WeatherMetricsService()
    basis = svc.compute_basis_metrics(reihe, tz=location_tz(GPXPoint(lat=_LAT, lon=_LON)))
    gesetzt = _gesetzte_felder(basis)

    ungesetzt = sorted(set(basis.aggregation_config) - set(gesetzt))
    assert not ungesetzt, (
        f"Vorbedingung: die Fixture muss jedes Basisfeld setzen, sonst bleibt "
        f"der Waechter dort blind: {ungesetzt}")
    assert "thunder_level_max_signals" in gesetzt and "hail_flag" in gesetzt

    erweitert = svc.compute_extended_metrics(reihe, basis)
    verloren = {
        name: (wert, getattr(erweitert, name))
        for name, wert in gesetzt.items()
        if getattr(erweitert, name) != wert
    }
    assert not verloren, (
        f"AC-3: compute_extended_metrics() verliert/veraendert Basisfelder "
        f"(Feld: (Basis, Erweitert)): {verloren}")


def test_ac3_kein_feld_wird_von_basis_und_erweiterung_zugleich_gesetzt():
    """AC-3 (Nichtueberschneidung).

    GIVEN dieselbe vollstaendige Stundenreihe,
    WHEN  die Felder der Basisstufe mit den Feldern verglichen werden, die die
          Erweiterung SELBST berechnet (bestimmt ueber einen Lauf auf einer
          leeren Basis — ohne Quelltext zu parsen),
    THEN  ueberschneiden sich beide Mengen nicht. Ein kuenftig doppelt
          gesetztes Feld erzwingt damit eine bewusste Entscheidung, statt still
          zu divergieren.

    Waechter: heute bereits gruen.
    """
    reihe = _vollstaendige_reihe()
    svc = WeatherMetricsService()
    basis = svc.compute_basis_metrics(reihe, tz=location_tz(GPXPoint(lat=_LAT, lon=_LON)))
    eigene = _gesetzte_felder(svc.compute_extended_metrics(reihe, SegmentWeatherSummary()))

    assert eigene, "Vorbedingung: die Erweiterung muss eigene Felder berechnen"
    doppelt = sorted(set(_gesetzte_felder(basis)) & set(eigene))
    assert not doppelt, (
        f"AC-3: diese Felder setzen Basis- UND Extended-Stufe — "
        f"bewusst entscheiden, welche gewinnt: {doppelt}")


# ═════════════ AC-4 bis AC-6: Etappen-Vereinigung der Traeger ═════════════

def test_ac4_etappe_nennt_nur_die_traeger_des_hoechststufen_segments():
    """AC-4.

    GIVEN eine Etappe mit zwei Segmenten — eines auf niedrigerer Stufe
          (leicht, Traeger Blitzdichte), eines auf der Etappen-Hoechststufe
          (hoch, Traeger CAPE) —,
    WHEN  ``aggregate_stage()`` laeuft, in BEIDEN Reihenfolgen
          (Vertauschungsprobe),
    THEN  nennt ``thunder_level_max_signals`` nur CAPE.

    RED heute: der ``values[0]``-Fallback nimmt die Traeger des ersten
    Segments — mit dem niedrigeren Segment vorn kommt "blitzdichte" heraus.
    """
    niedrig = _segment_mit_basis([_dp(10, dichte=0.005)], seg_id=1)
    hoch = _segment_mit_basis([_dp(14, cape=1500.0, cin=5.0)], seg_id=2)
    assert niedrig.aggregated.thunder_level_max == ThunderLevel.LOW
    assert hoch.aggregated.thunder_level_max == ThunderLevel.HIGH

    ergebnisse = {
        "niedrig-zuerst": aggregate_stage([niedrig, hoch]).thunder_level_max_signals,
        "hoch-zuerst": aggregate_stage([hoch, niedrig]).thunder_level_max_signals,
    }
    assert ergebnisse == {"niedrig-zuerst": ["cape"], "hoch-zuerst": ["cape"]}, (
        f"AC-4: die Etappe darf nur die Traeger des Hoechststufen-Segments "
        f"nennen, unabhaengig von der Reihenfolge: {ergebnisse}")


def test_ac5_segmente_auf_gleicher_hoechststufe_werden_vereinigt():
    """AC-5.

    GIVEN eine Etappe mit drei Segmenten auf derselben Hoechststufe (hoch):
          CAPE, Blitzpotenzial, noch einmal CAPE,
    WHEN  ``aggregate_stage()`` laeuft,
    THEN  ist das Ergebnis die deduplizierte Vereinigung in Erstauftritts-/
          Katalogreihenfolge ``["cape", "blitzpotenzial"]`` — als ``list``.

    RED heute: ``values[0]`` liefert nur ``["cape"]``.
    """
    segmente = [
        _segment_mit_basis([_dp(10, cape=1500.0, cin=5.0)], seg_id=1),
        _segment_mit_basis([_dp(13, lpi=60.0)], seg_id=2),
        _segment_mit_basis([_dp(16, cape=1500.0, cin=5.0)], seg_id=3),
    ]
    assert {s.aggregated.thunder_level_max for s in segmente} == {ThunderLevel.HIGH}

    traeger = aggregate_stage(segmente).thunder_level_max_signals
    assert type(traeger) is list, (
        f"AC-5: Rueckgabe muss eine list sein (Snapshot-JSON, #1405): "
        f"{type(traeger).__name__}")
    assert traeger == ["cape", "blitzpotenzial"], (
        f"AC-5: Vereinigung aller Traeger der Hoechststufen-Segmente, "
        f"dedupliziert, in Katalogreihenfolge: {traeger!r}")


def test_ac6_hoechststufe_ohne_traeger_nennt_nie_den_traeger_eines_niedrigeren_segments():
    """AC-6.

    GIVEN (a) ein Hoechststufen-Segment OHNE Traeger (Alt-Schnappschuss vor
          #1680) und ein niedrigeres Segment MIT Traeger, bzw. (b) eine Etappe,
          deren Hoechststufe "kein Gewitter" ist (mit einer verirrten
          Traegerliste an einem Segment),
    WHEN  ``aggregate_stage()`` laeuft (beide Reihenfolgen),
    THEN  ist das Ergebnis jeweils ``None`` — keine Aussage, niemals der
          Traeger des niedrigeren Segments.

    RED heute: der Vorfilter nimmt das traegerlose Segment heraus, und
    ``values[0]`` liefert den Traeger des niedrigeren.
    """
    hoch_basis = _segment_mit_basis([_dp(14, cape=1500.0, cin=5.0)], seg_id=1)
    hoch_ohne = dataclasses.replace(hoch_basis, aggregated=dataclasses.replace(
        hoch_basis.aggregated, thunder_level_max_signals=None))
    niedrig = _segment_mit_basis([_dp(10, dichte=0.005)], seg_id=2)
    assert niedrig.aggregated.thunder_level_max_signals == ["blitzdichte"]

    ruhig = _segment_mit_basis([_dp(10, cape=100.0, cin=5.0)], seg_id=3)
    ruhig_verirrt = dataclasses.replace(ruhig, aggregated=dataclasses.replace(
        ruhig.aggregated, thunder_level_max_signals=["cape"]))
    assert ruhig.aggregated.thunder_level_max == ThunderLevel.NONE

    ergebnisse = {
        "a: hoch-ohne zuerst": aggregate_stage([hoch_ohne, niedrig]).thunder_level_max_signals,
        "a: niedrig zuerst": aggregate_stage([niedrig, hoch_ohne]).thunder_level_max_signals,
        "b: kein Gewitter": aggregate_stage([ruhig_verirrt, ruhig]).thunder_level_max_signals,
    }
    assert ergebnisse == {k: None for k in ergebnisse}, (
        f"AC-6: ohne Traeger am Maximum (oder bei 'kein Gewitter') gibt es "
        f"keine Herkunft: {ergebnisse}")


# ═══════════════ AC-7: Ausblick-Mail zeigt Traeger und Hagel ═══════════════

def test_ac7_ausblick_zelle_zeigt_traeger_und_hagel_aus_der_etappe():
    """AC-7.

    GIVEN eine kuenftige Etappe, deren Segmente der produktive
          ``SegmentWeatherService`` rechnet, mit Gewitter-Hoechststufe (CAPE)
          und Hagelstunde,
    WHEN  die Ausblick-Zeile wie im Zeitplaner gebaut wird
          (``aggregate_stage()`` -> ``build_outlook_row(...,
          trip_display_config=dc, segments=...)``,
          ``trip_report_scheduler.py:2528-2591``) und die Trip-Mail rendert,
    THEN  zeigt die Gewitter-Zelle der Ausblick-Tabelle sowohl die Herkunft
          (CAPE) als auch den Hagel-Zusatz — Herkunft vor Hagel.

    RED heute: ``aggregate_stage()`` liest ``hail_flag`` aus feldlosen
    Segment-Aggregaten, der Hagel-Zusatz fehlt.
    """
    segmente = [
        _segment_ueber_service(_gewitter_hagel_punkte(_MORGEN)[:3], tag=_MORGEN,
                               start_h=12, end_h=15, seg_id=1, lon=_LON),
        _segment_ueber_service(_gewitter_hagel_punkte(_MORGEN)[3:], tag=_MORGEN,
                               start_h=15, end_h=17, seg_id=2, lon=_LON + 0.2),
    ]
    agg = aggregate_stage(segmente)
    dc = build_default_display_config()
    fenster = resolve_configured_window(None, None)
    zeile = build_outlook_row(
        agg, [dp for s in segmente for dp in s.timeseries.data], "Fr", _UTC,
        sms_thresholds={}, trip_display_config=dc, report_type="evening",
        day_window_start_hour=fenster[0], day_window_end_hour=fenster[1],
        segments=segmente,
    )
    zeile["date"] = _MORGEN
    zeile["name"] = "Etappe B"

    ruhig = _segment_mit_basis([_dp(h, cape=200.0) for h in range(6, 18)])
    bericht = TripReportFormatter().format_email(
        [ruhig], "Test-Trip", "evening", display_config=dc, tz=_UTC,
        stage_name="Etappe A", multi_day_trend=[zeile],
    )

    # #2136/ADR-0068: der Ausblick-Spaltenkopf ist seither `col_label`
    # ("Thdr"), nicht mehr der deutsche Compare-Katalog-Langname ("Gewitter").
    gewitter_kopf = get_metric("thunder").col_label
    suppe = BeautifulSoup(bericht.email_html, "html.parser")
    tabellen = [
        t for t in suppe.find_all("table")
        if {"Tag", gewitter_kopf} <= {th.get_text(strip=True) for th in t.find_all("th")}
    ]
    assert len(tabellen) == 1, f"Vorbedingung: genau EINE Ausblick-Tabelle, {len(tabellen)}"
    koepfe = [th.get_text(strip=True) for th in tabellen[0].find_all("th")]
    zellen = [td.get_text(strip=True)
              for td in tabellen[0].find("tbody").find_all("tr")[0].find_all("td")]
    zelle = zellen[koepfe.index(gewitter_kopf)]

    herkunft = thunder_signal_label("cape")
    hagel = format_hail_note(True)
    assert hagel in zelle, (
        f"AC-7: die Ausblick-Gewitterzelle muss den Hagel-Zusatz der Etappe "
        f"tragen: {zelle!r}")
    assert f" · {herkunft} · {hagel}" in zelle, (
        f"AC-7: Herkunft UND Hagel, Herkunft vor Hagel: {zelle!r}")


# ═════════ AC-8: SMS/Premium-SMS — Hagel ja, Traeger bewusst nein ═════════

def test_ac8_sms_und_premium_sms_zeigen_hagel_aber_keine_traeger():
    """AC-8.

    GIVEN dieselbe Wetterlage wie AC-2 (Aggregat vom produktiven
          ``SegmentWeatherService``, Segment noch nicht begonnen),
    WHEN  der Nutzer ``GEWITTER`` ueber ``sms`` bzw. ``premium_sms`` sendet,
    THEN  traegt die Antwort den Hagel-Zusatz aus dem Tageswert, aber KEINE
          Gewitter-Herkunft (PO-Abwahl #2184) — Gegenprobe im selben Test:
          dieselbe Fixture ueber ``email`` nennt die Herkunft.

    RED heute: der Hagel-Zusatz fehlt (feldloses ``seg.aggregated``); die
    Traeger-Abwesenheit auf SMS ist schon heute wahr und bleibt es.
    """
    seg = _segment_ueber_service(_gewitter_hagel_punkte(), tag=_HEUTE,
                                 start_h=12, end_h=17)
    kommando = _Kommando()
    kommando.speichere([seg])
    stufe = _thunder_words()[ThunderLevel.HIGH.name]
    hagel = format_hail_note(True)

    for kanal in ("sms", "premium_sms"):
        antwort = kommando.frage("GEWITTER", kanal=kanal)
        assert antwort == f"⛈ Gewitter heute ({_HEUTE:%d.%m}): {stufe} · {hagel}", (
            f"AC-8: auf {kanal!r} gehoert der Hagel-Zusatz in die Antwort, die "
            f"Herkunft nicht: {antwort!r}")
        assert not [z for z in ALLE_ZUTATEN if z in antwort], (
            f"AC-8: {kanal!r} darf keine Gewitter-Herkunft nennen: {antwort!r}")

    mit = kommando.frage("GEWITTER", kanal="email")
    assert thunder_signal_label("cape") in mit, (
        f"Gegenprobe: dieselbe Fixture ueber E-Mail muss die Herkunft nennen, "
        f"sonst beweist ihre Abwesenheit auf SMS nichts: {mit!r}")


# ═════════════ AC-9: #2186-Neuberechnung behaelt beide Felder ═════════════

def test_ac9_neuberechnung_ab_anfragezeit_behaelt_traeger_und_hagel():
    """AC-9.

    GIVEN ein teilweise vergangenes Segment (06-14 Uhr UTC), Anfrage um
          10 Uhr, Restfenster mit Gewitter-Hoechststufe (CAPE, 11 Uhr) und
          Hagelstunde (12 Uhr); gespeichertes Aggregat bewusst leer,
    WHEN  ``WeatherExtractor.timeline(from_time=...)`` das Segment ueber
          ``compute_basis_metrics()`` -> ``compute_extended_metrics()`` neu
          berechnet,
    THEN  traegt das neu berechnete Aggregat ``thunder_level_max_signals ==
          ["cape"]`` und ``hail_flag is True``.

    Waechter: heute gruen durch den Nachzug-Workaround in
    ``weather_extractor.py``; muss nach dessen Entfernen gruen bleiben
    (dann durch den Wurzel-Fix). Gleiche Zusicherung wie die beiden
    Neuberechnungs-Tests in ``test_tageswert_fenster_erhaelt_alle_metriken.py``,
    hier neben der Aenderung als Mutations-Waechter.
    """
    punkte = (
        [_dp(h, cape=100.0, cin=5.0, t2m_c=3.0) for h in (6, 7, 8, 9, 10)]
        + [_dp(11, cape=1500.0, cin=5.0), _dp(12, cape=100.0, cin=5.0, hail=True),
           _dp(13, cape=100.0, cin=5.0)]
    )
    reihe = _reihe(punkte)
    seg = SegmentWeatherData(
        segment=_trip_segment(tag=_HEUTE, start_h=6, end_h=14),
        timeseries=reihe,
        aggregated=SegmentWeatherSummary(temp_max_c=99.9),
        fetched_at=datetime(2026, 8, 20, 5, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )
    kommando = _Kommando()
    kommando.speichere([seg])

    zehn = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)
    m = WeatherExtractor(user_id=kommando.user_id).timeline(
        kommando.trip_id, from_time=zehn).points[0].metrics

    assert m.temp_max_c == 20.0 and m.thunder_level_max == ThunderLevel.HIGH, (
        f"Vorbedingung: das Segment muss ueber das Restfenster neu gerechnet "
        f"worden sein: temp_max={m.temp_max_c!r}, stufe={m.thunder_level_max!r}")
    assert m.thunder_level_max_signals == ["cape"], (
        f"AC-9: Traeger bei der Neuberechnung verloren: "
        f"{m.thunder_level_max_signals!r}")
    assert m.hail_flag is True, (
        f"AC-9: Hagel-Kennzeichen bei der Neuberechnung verloren: {m.hail_flag!r}")


# ═══════════════ AC-11: Alt-Schnappschuss ohne beide Felder ═══════════════

def test_ac11_alt_schnappschuss_ohne_beide_felder_laedt_und_zeigt_keinen_zusatz():
    """AC-11.

    GIVEN ein gespeicherter Schnappschuss, dessen Aggregat beide Felder
          traegt (Gegenprobe: die Antwort zeigt Herkunft und Hagel), der
          anschliessend zu einem ALT-Schnappschuss ohne beide Felder gemacht
          wird,
    WHEN  der Nutzer ``GEWITTER`` sendet,
    THEN  laedt der Schnappschuss fehlerfrei und die Zeile zeigt nur die
          Stufe — ohne Traeger-/Hagel-Zusatz, ohne Absturz.

    Waechter: heute gruen.
    """
    seg = _segment_mit_basis(_gewitter_hagel_punkte())
    seg = dataclasses.replace(seg, segment=_trip_segment(tag=_HEUTE, start_h=12, end_h=17))
    kommando = _Kommando()
    kommando.speichere([seg])
    stufe = _thunder_words()[ThunderLevel.HIGH.name]

    vorher = kommando.frage("GEWITTER", kanal="telegram")
    assert vorher == (f"⛈ Gewitter heute ({_HEUTE:%d.%m}): {stufe} · "
                      f"{thunder_signal_label('cape')} · {format_hail_note(True)}"), (
        f"Gegenprobe: mit beiden Feldern muss die Zeile beide Zusaetze tragen, "
        f"sonst beweist ihre Abwesenheit nichts: {vorher!r}")

    kommando.als_alt_schnappschuss()
    nachher = kommando.frage("GEWITTER", kanal="telegram")
    assert nachher == f"⛈ Gewitter heute ({_HEUTE:%d.%m}): {stufe}", (
        f"AC-11: ein Alt-Schnappschuss ohne beide Felder zeigt nur die Stufe: "
        f"{nachher!r}")


# ═══════ AC-10: kein Extended-eigenes Feld faellt beim Merge weg ═══════

def _dp_alle_extended_rohdaten(h: int, *, tag: date = _HEUTE) -> ForecastDataPoint:
    """Stundenpunkt mit ROHWERTEN fuer JEDES Feld, das die Erweiterungs-
    stufe SELBST berechnet (nicht die Basisfelder aus AC-3). Mutations-
    Waechter fuer Fix-Loop 1 / Finding F001 (M6): faellt ein einzelnes
    kwarg aus dem ``dataclasses.replace(...)``-Aufruf in
    ``compute_extended_metrics()``, bleibt genau dieses Feld ``None`` --
    das Basis-Objekt setzt Extended-eigene Felder nie, AC-3 kann das also
    nicht fangen (dort explizit ausgenommen)."""
    return _dp(
        h, tag=tag, cape=100.0, cin=5.0,
        dewpoint_c=10.0 + h, pressure_msl_hpa=1000.0 + h,
        wind_chill_c=5.0 + h, snow_depth_cm=20.0 + h,
        freezing_level_m=2500 + h * 10, pop_pct=30 + h,
        uv_index=3.0 + h * 0.1, snow_new_24h_cm=1.0 + h * 0.1,
        wind_direction_deg=(h * 15) % 360,
        precip_type=PrecipType.RAIN if h % 2 else PrecipType.SNOW,
        confidence_pct=90 - h, snowfall_limit_m=2000 + h * 5,
        cloud_low_pct=10 + h, cloud_mid_pct=20 + h, cloud_high_pct=30 + h,
    )


# Feld -> zustaendige Einzelberechnung (``WeatherMetricsService._compute_*``).
# ``cape_model_id`` bewusst ausgenommen: keine Stundenreihen-Berechnung,
# sondern ``effective_cape_model_id(timeseries.meta)`` (Metadaten-Herkunft),
# eigener Mechanismus (Issue #1592), nicht Gegenstand dieses Waechters.
_EXTENDED_FELD_ZU_METHODE = {
    "dewpoint_avg_c": "_compute_dewpoint",
    "pressure_avg_hpa": "_compute_pressure",
    "wind_chill_min_c": "_compute_wind_chill",
    "wind_chill_max_c": "_compute_wind_chill_max",
    "snow_depth_cm": "_compute_snow_depth",
    "freezing_level_m": "_compute_freezing_level",
    "pop_max_pct": "_compute_pop",
    "cape_max_jkg": "_compute_cape",
    "uv_index_max": "_compute_uv_index",
    "snow_new_sum_cm": "_compute_fresh_snow",
    "wind_direction_avg_deg": "_compute_wind_direction",
    "precip_type_dominant": "_compute_precip_type",
    "confidence_pct_min": "_compute_confidence_min",
    "snowfall_limit_m": "_compute_snowfall_limit",
    "cloud_low_avg_pct": "_compute_cloud_low",
    "cloud_mid_avg_pct": "_compute_cloud_mid",
    "cloud_high_avg_pct": "_compute_cloud_high",
}


def test_ac10_jedes_extended_feld_ueberlebt_den_merge_in_compute_extended_metrics():
    """AC-10 (Mutations-Waechter, Adversary Fix-Loop 1, Finding F001/M6).

    GIVEN eine Stundenreihe mit Rohdaten fuer JEDES von der Erweiterungs-
          stufe selbst berechnete Feld,
    WHEN  ``compute_extended_metrics()`` laeuft,
    THEN  ist jedes dieser Felder ungleich ``None`` UND identisch zum
          direkten Ergebnis der zustaendigen Einzelberechnung
          (``svc._compute_*`` auf DERSELBEN Zeitreihe) -- ohne den Umweg
          ueber ``compute_extended_metrics()`` selbst.

    Faengt Mutation M6 (ein einzelnes kwarg, z.B.
    ``cloud_high_avg_pct=cloud_high_avg``, aus dem
    ``dataclasses.replace(...)``-Aufruf entfernt): das betroffene Feld
    bliebe dann bei ``None``, dieser Test schlaegt fehl. Generisch pro
    Feld, nicht nur fuer eine einzelne Stichprobe -- jedes der 17
    gepruefen Felder faengt seine eigene Auslassung.
    """
    reihe = _reihe([_dp_alle_extended_rohdaten(h) for h in range(6, 14)])
    svc = WeatherMetricsService()
    basis = svc.compute_basis_metrics(
        reihe, tz=location_tz(GPXPoint(lat=_LAT, lon=_LON)))
    erweitert = svc.compute_extended_metrics(reihe, basis)

    neu = set(erweitert.aggregation_config) - set(basis.aggregation_config)
    fehlend_in_zuordnung = neu - set(_EXTENDED_FELD_ZU_METHODE) - {"cape_model_id"}
    assert not fehlend_in_zuordnung, (
        f"Vorbedingung: die Feld-zu-Methode-Zuordnung muss ALLE von der "
        f"Erweiterung neu hinzugefuegten Config-Schluessel abdecken: "
        f"{fehlend_in_zuordnung}")

    fehler = {}
    for feld, methode_name in _EXTENDED_FELD_ZU_METHODE.items():
        referenz = getattr(svc, methode_name)(reihe)
        assert referenz is not None, (
            f"Vorbedingung: die Fixture muss Rohdaten fuer {feld!r} tragen, "
            f"sonst beweist der Vergleich nichts (Referenz ist None)")
        wert = getattr(erweitert, feld)
        if wert != referenz:
            fehler[feld] = (referenz, wert)
    assert not fehler, (
        f"AC-10: diese Extended-Felder gehen beim Merge verloren oder "
        f"weichen vom Referenzwert ab (Feld: (Referenz, Erweitert)): {fehler}")
