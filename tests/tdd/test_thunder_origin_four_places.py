"""TDD RED — Issue #1680 Scheibe 3: Herkunft der Gewitterstufe an vier
weiteren Ausgabeorten.

SPEC: docs/specs/modules/feat_1680_s3_gewitter_herkunft_vier_orte.md
(AC-1 bis AC-16)
KONTEXT: docs/context/feat-1680-s3-herkunft-vier-orte.md

Die vier Ausgabeorte dieser Scheibe:
  1. Pille im Metriken-Ueberblick der Trip-Mail
     (``output.renderers.email.helpers._pill_for_metric``, thunder-Zweig)
  2. Kommando-Timeline je Wegpunkt
     (``services.trip_command_processor.TripCommandProcessor._fmt_timeline``)
  3. GLANCE-Tageszeile (``..._fmt_day_agg``)
  4. Ortsvergleich-Stundentabelle
     (``email.compare_html._render_hour_row`` HTML +
      ``renderers.comparison.render_comparison_text`` Klartext)

RED-Ursache (heute, gemessen 2026-08-13): keiner der vier Orte liest die
bereits vorhandene Traegerliste.
  - die Pille baut ihren Text ausschliesslich aus ``dp.thunder_level``
    (``helpers.py:1713-1757``) und nennt keine Zutat,
  - ``_fmt_timeline()`` (``trip_command_processor.py:933-937``) liest nur
    ``m.thunder_level_max``, nicht ``m.thunder_level_max_signals``,
  - ``_fmt_day_agg()`` (``:844-854``) laesst den seit Scheibe 2 vorhandenen
    Aggregat-Schluessel ``"thunder_signals"`` bewusst liegen (die dortige
    Entscheidung hebt der PO mit dieser Scheibe auf),
  - ``_render_hour_row()`` (``compare_html.py:982-983``) und die
    Klartext-Stundenschleife (``comparison.py:329-333``) rufen
    ``_fmt_thunder(value, hail)`` OHNE den seit Scheibe 1 vorhandenen dritten
    Parameter.

Prueford = Wirkort, ohne Ausnahme: JEDER Test laeuft bis zu dem Text, den der
Nutzer bekommt -- ``TripReport.email_plain``/``email_html``/``sms_text``,
``CommandResult.confirmation_body`` aus ``TripCommandProcessor.process()``
bzw. ``html_body``/``text_body`` aus ``render_compare_email()``. Kein
Zwischenwert steht stellvertretend fuer einen Text.

Kein Mock-Theater: Stufen und Traegerlisten entstehen ueber die ECHTE Fusion
(``thunder_enrichment._fuse_thunder_levels`` mit den Leitern aus
``app.model_registry``) und die ECHTE Aggregation
(``WeatherMetricsService.compute_basis_metrics``). Der Kommandopfad laeuft
ueber einen echt gespeicherten und wieder geladenen Wetter-Schnappschuss.

🔴 Abweichung von der Spec bei AC-12 -- s. Docstring von
``test_ac12_compare_sms_und_telegram_zeigen_keine_stunden_herkunft``.

#1493: die Pille nennt die Gewitterstufe als Wort ("Gewitter hoch ab
14:00 ..."); die Soll-Texte unten tragen es entsprechend. Herkunft und
Zeitfenster -- der Gegenstand dieser Datei -- sind unveraendert.
"""
from __future__ import annotations

import html as _html
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.loader import get_snapshots_dir, save_trip  # noqa: E402
from app.metric_catalog import build_default_display_config  # noqa: E402
from app.model_registry import (  # noqa: E402
    cape_ladder_thresholds_jkg, lpi_thresholds_jkg,
)
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, ThunderLevel, TripSegment,
)
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from app.user import ComparisonResult, LocationResult, SavedLocation  # noqa: E402
from output.renderers.comparison import (  # noqa: E402
    render_compare_email, render_compare_sms, render_compare_telegram,
)
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage, TripCommandProcessor,
)
from services.weather_metrics import WeatherMetricsService  # noqa: E402
from services.weather_snapshot import WeatherSnapshotService  # noqa: E402

# Die VIER Zutaten der Fusion in ihrer deutschen Beschriftung
# (``metric_format.THUNDER_SIGNAL_LABEL_DE``). Keine davon darf in der
# Trip-SMS (AC-13) oder in der Compare-SMS (AC-12) auftauchen.
ALLE_ZUTATEN = ("Wettercode", "Blitzdichte", "CAPE", "Blitzpotenzial")

_TZ = ZoneInfo("UTC")
_LAT, _LON, _MODELL = 47.0, 12.0, "icon_d2"   # Gebiet DE_ALPEN
_ETAPPE = "Test-Etappe"
_TAG = date(2026, 8, 20)

_TRIP_ID = "herkunft-vier-orte"
_TRIP_NAME = "Herkunft Vier Orte Tour"
_USER = "default"

_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_TBODY = re.compile(r"<tbody>(.*?)</tbody>", re.S)
_SPAN = re.compile(r"<span[^>]*>(.*?)</span>", re.S)


# ---------------------------------------------------------------------------
# Trip-Fixturen: Rohwerte rein, echte Rechnung raus
# ---------------------------------------------------------------------------

def _dp(h: int, *, tag: date = _TAG, cape=None, cin=None, lpi=None,
        dichte=None) -> ForecastDataPoint:
    """Ein Stundenpunkt mit ROHWERTEN -- Stufe und Traeger rechnet die Fusion."""
    return ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, h, 0, tzinfo=timezone.utc),
        t2m_c=20.0, wind10m_kmh=8.0, gust_kmh=12.0, precip_1h_mm=0.0,
        cloud_total_pct=40, humidity_pct=50,
        cape_jkg=cape, convective_inhibition_jkg=cin,
        lightning_potential_lpi_jkg=lpi, lightning_density_per_km2_3h=dichte,
    )


def _reihe(punkte: list[ForecastDataPoint]) -> NormalizedTimeseries:
    """Zeitreihe, deren Punkte durch die ECHTE Fusion gelaufen sind: Gebiet aus
    ``thunder_routing``, Leitern aus ``model_registry`` -- keine im Test
    getippte Schwelle (sonst prueft er eine Welt, die es nicht gibt)."""
    region = thunder_region_for(_LAT, _LON)
    _fuse_thunder_levels(
        punkte, cape_ladder_thresholds_jkg(_MODELL, region),
        lpi_thresholds_jkg(region),
    )
    return NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                          grid_res_km=1.0),
        data=punkte,
    )


def _segment(punkte: list[ForecastDataPoint], *, tag: date = _TAG,
             start_h: int = 6, end_h: int = 17,
             seg_id: int = 1) -> SegmentWeatherData:
    """Segment, dessen Aggregat die ECHTE Engine rechnet
    (``compute_basis_metrics`` -> ``thunder_level_max``/
    ``thunder_level_max_signals``) -- nicht von Hand gesetzt."""
    reihe = _reihe(punkte)
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=_LAT, lon=_LON, elevation_m=1000.0),
        end_point=GPXPoint(lat=_LAT + 0.1, lon=_LON + 0.1, elevation_m=1200.0),
        start_time=datetime(tag.year, tag.month, tag.day, start_h, 0,
                            tzinfo=timezone.utc),
        end_time=datetime(tag.year, tag.month, tag.day, end_h, 0,
                          tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h), distance_km=10.0,
        ascent_m=500.0, descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=reihe,
        aggregated=WeatherMetricsService().compute_basis_metrics(reihe, tz=None),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _mail(segmente):
    """Der ECHTE Trip-Bericht (HTML + Klartext + SMS) ueber den produktiven
    Formatierer -- Prueford = Wirkort."""
    return TripReportFormatter().format_email(
        segmente, "Test-Trip", "evening",
        display_config=build_default_display_config(),
        tz=_TZ, stage_name=_ETAPPE,
    )


def _pille(bericht) -> str:
    """Die EINE Gewitter-Pille aus dem Metriken-Ueberblick der Klartext-Mail.

    Zusaetzlich wird geprueft, dass derselbe Text auch im HTML-Teil DERSELBEN
    Mail steht -- die Pille ist ein geteilter Baustein (``compact.py:176``,
    ``plain.py:205``, ``html.py:1432``); ein Test nur auf dem Klartext liesse
    offen, ob der HTML-Leser dieselbe Angabe bekommt.
    """
    block = bericht.email_plain.split("Metriken-Überblick ━━", 1)[1]
    zeilen = [ln.strip() for ln in block.split("\n\n", 1)[0].splitlines()
              if "Gewitter" in ln]
    assert len(zeilen) == 1, (
        f"Erwartet genau EINE Gewitter-Pille im Metriken-Ueberblick, "
        f"gefunden: {zeilen!r}")
    assert zeilen[0] in bericht.email_html, (
        f"HTML- und Klartext-Teil derselben Mail muessen dieselbe Pille "
        f"zeigen: {zeilen[0]!r} fehlt im HTML-Teil")
    return zeilen[0]


# ---------------------------------------------------------------------------
# Kommandopfad: echter Trip + echter Schnappschuss + echter Prozessor
# ---------------------------------------------------------------------------

def _alt_schnappschuss() -> None:
    """Macht den gespeicherten Schnappschuss zu einem ALT-Schnappschuss (vor
    Scheibe 1): beide Traeger-Schluessel raus, alles andere unberuehrt."""
    pfad = get_snapshots_dir(_USER) / f"{_TRIP_ID}.json"
    roh = json.loads(pfad.read_text())
    for seg in roh["segments"]:
        seg["aggregated"].pop("thunder_level_max_signals", None)
        for stunde in seg.get("hourly", []):
            stunde.pop("thunder_level_signals", None)
    pfad.write_text(json.dumps(roh, indent=2))


@pytest.fixture
def kommando():
    """Speichert Trip + Wetter-Schnappschuss und stellt die Kommando-Frage
    ueber ``TripCommandProcessor.process()`` -- derselbe Weg, den eine
    eingehende Telegram-/E-Mail-Nachricht nimmt.

    Fix #1795 AC-9: ``jetzt`` war ``datetime.now(tz=timezone.utc)`` --
    ``_handle_query`` bestimmt den Kalendertag seit #1795 ueber den ORTStag
    (``trip_local_now``, Koordinaten 47.0/12.0 = Europe/Vienna). Im
    Mismatch-Fenster (22:00-24:00 UTC im Sommer) waere der Ortstag ein
    anderer als ``heute`` (= UTC-Tag der echten Systemuhr) -- die Fixtur
    haengt jetzt auf einem festen, zonensicheren Zeitpunkt statt an der
    Systemuhr.
    """
    jetzt = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
    heute = jetzt.date()

    def frage(segmente, *, body: str = "GLANCE", alt: bool = False) -> str:
        save_trip(Trip(id=_TRIP_ID, name=_TRIP_NAME, stages=[
            Stage(id="S1", name="Heute", date=heute, waypoints=[
                Waypoint(id="W1", name="Start", lat=_LAT, lon=_LON,
                         elevation_m=1000),
            ]),
        ]), _USER)
        WeatherSnapshotService(_USER).save(_TRIP_ID, segmente, heute)
        if alt:
            _alt_schnappschuss()
        ergebnis = TripCommandProcessor().process(InboundMessage(
            channel="telegram", trip_name=_TRIP_NAME, body=body,
            sender="4711", received_at=jetzt, user_id=_USER,
        ))
        assert ergebnis.success, (
            f"Das Kommando {body!r} muss antworten, nicht scheitern: "
            f"{ergebnis.confirmation_body!r}")
        return ergebnis.confirmation_body

    return SimpleNamespace(heute=heute, morgen=heute + timedelta(days=1),
                           frage=frage)


_TIMELINE_HEUTE = "### query: timeline_heute"


def _timeline_gewitter(antwort: str) -> list[str]:
    """Der Gewitter-Abschnitt JEDER Wegpunkt-Zeile, in Wegpunkt-Reihenfolge.

    "   🌡 20–20 °C  💨 8 km/h  🌧 0.0 mm  ⛈ hoch · CAPE" -> "hoch · CAPE".
    """
    return [ln.split("⛈ ", 1)[1].strip()
            for ln in antwort.splitlines() if "⛈ " in ln and "🌡" in ln]


def _glance_gewitter(antwort: str, tag_label: str) -> str:
    """Der Gewitter-Abschnitt der GLANCE-Zeile eines Tages ("heute"/"morgen").

    "heute (13.08): ... ⛈ Gewitter: hoch · CAPE" -> "hoch · CAPE".
    """
    zeilen = [ln for ln in antwort.splitlines()
              if ln.startswith(f"{tag_label} (") and "⛈ Gewitter: " in ln]
    assert len(zeilen) == 1, (
        f"Erwartet genau EINE GLANCE-Zeile fuer {tag_label!r}: {antwort!r}")
    return zeilen[0].split("⛈ Gewitter: ", 1)[1].strip()


# ---------------------------------------------------------------------------
# Ortsvergleich-Fixturen
# ---------------------------------------------------------------------------

def _cdp(h: int, *, cape=None, cin=None, lpi=None,
         dichte=None) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 8, 6, h, 0, tzinfo=timezone.utc), t2m_c=20.0,
        cape_jkg=cape, convective_inhibition_jkg=cin,
        lightning_potential_lpi_jkg=lpi, lightning_density_per_km2_3h=dichte,
    )


def _ort(name: str, punkte: list, *, lat: float = _LAT, lon: float = _LON,
         modell: str = _MODELL, **felder) -> LocationResult:
    """Ort, dessen Stunden durch die ECHTE Fusion gelaufen sind."""
    region = thunder_region_for(lat, lon)
    _fuse_thunder_levels(
        punkte, cape_ladder_thresholds_jkg(modell, region),
        lpi_thresholds_jkg(region),
    )
    return LocationResult(
        location=SavedLocation(id=name.lower(), name=name, lat=lat, lon=lon,
                               elevation_m=1000),
        score=50, hourly_data=punkte, **felder,
    )


def _vergleich(*orte: LocationResult) -> ComparisonResult:
    return ComparisonResult(
        locations=list(orte), time_window=(12, 20),
        target_date=date(2026, 8, 6), created_at=datetime(2026, 8, 5, 18, 0),
    )


def _compare_mail(*orte: LocationResult) -> tuple[str, str]:
    """(html_body, text_body) des Ortsvergleichs MIT Stundentabelle."""
    return render_compare_email(
        _vergleich(*orte), enabled_metrics=["thunder_max"],
        hourly_metrics=["thunder_level"], hourly_enabled=True,
    )


def _html_stunden(html: str) -> dict[str, list[list[str]]]:
    """{Ortsname: [[Zeit, Gewitterzelle], ...]} aus den HTML-Stundentabellen."""
    ergebnis: dict[str, list[list[str]]] = {}
    for block in html.split("STUNDEN", 1)[1].split(">ORT</span>")[1:]:
        name = _html.unescape(_SPAN.findall(block)[0]).strip()
        koerper = _TBODY.search(block)
        ergebnis[name] = [
            [_html.unescape(c).strip() for c in _TD.findall(zeile)]
            for zeile in (_TR.findall(koerper.group(1)) if koerper else [])
        ]
    return ergebnis


def _text_stunden(text: str) -> dict[str, list[str]]:
    """{Ortsname: ["16:00  Thdr hoch", ...]} aus dem Klartext-Stundenverlauf."""
    ergebnis: dict[str, list[str]] = {}
    aktuell = None
    for zeile in text.split("STUNDENVERLAUF", 1)[1].splitlines():
        kopf = re.match(r"^(\S.*?) \([A-Z]+\)$", zeile)
        if kopf:
            aktuell = kopf.group(1)
            ergebnis[aktuell] = []
        elif aktuell is not None and re.match(r"^\s+\d\d:\d\d\s\s", zeile):
            ergebnis[aktuell].append(zeile.strip())
    return ergebnis


def _html_uebersicht(html: str) -> list[str]:
    """Zellentexte der Gewitter-Zeile der HTML-Uebersicht (Ortsreihenfolge)."""
    rest = html.split(">Gewitter</td>", 1)[1]
    return [_html.unescape(c) for c in _TD.findall(rest.split("</tr>", 1)[0])]


def _text_uebersicht(text: str) -> list[str]:
    """Gewitter-Zellen der Klartext-Uebersicht (Ortsreihenfolge)."""
    return [ln.split("Gewitter: ", 1)[1].strip()
            for ln in text.split("STUNDENVERLAUF", 1)[0].splitlines()
            if "Gewitter: " in ln]


# ===========================================================================
# Ort 1 — Pille im Metriken-Ueberblick
# ===========================================================================

def test_ac1_pille_nennt_die_tragende_zutat():
    """AC-1: Given das Gewitterfenster der Pille kommt ausschliesslich ueber
    CAPE zustande, When die Trip-Mail gerendert wird, Then nennt die Pille die
    Zutat neben dem Zeitfenster."""
    seg = _segment([_dp(h, cape=1500.0, cin=5.0) for h in (14, 15, 16)])
    assert _pille(_mail([seg])) == "Gewitter hoch ab 14:00 · stärkste 14:00 · CAPE", (
        f"Die Pille muss die tragende Zutat neben dem Zeitfenster nennen: "
        f"{_pille(_mail([seg]))!r}")


def test_ac5_pille_nennt_beide_zutaten_derselben_stunde():
    """AC-5: Given CAPE UND Blitzpotenzial erreichen in DERSELBEN Stunde die
    Hoechststufe, When die Pille gerendert wird, Then werden BEIDE in der
    Katalogreihenfolge aus ``THUNDER_SIGNAL_LABEL_DE`` genannt -- kein
    Gewinner wird gekuert (PO-Auslegung (ii))."""
    seg = _segment([_dp(14, cape=1500.0, cin=5.0, lpi=60.0)])
    zutaten = seg.timeseries.data[0].thunder_level_signals
    assert zutaten == ["cape", "blitzpotenzial"], (
        f"Vorbedingung: die ECHTE Fusion muss BEIDE Zutaten als tragend "
        f"ausweisen -- sonst prueft dieser Test nichts: {zutaten!r}")
    assert _pille(_mail([seg])) == (
        "Gewitter hoch ab 14:00 · stärkste 14:00 · CAPE, Blitzpotenzial"), (
        f"Beide Traeger der Hoechststufe muessen erscheinen, CAPE vor "
        f"Blitzpotenzial (Katalogreihenfolge): {_pille(_mail([seg]))!r}")


def test_ac6_pille_vereinigt_die_zutaten_zweier_stunden():
    """AC-6: Given ZWEI Stunden desselben Tagesfensters erreichen die
    Hoechststufe ueber VERSCHIEDENE Zutaten (14 Uhr CAPE, 17 Uhr
    Blitzpotenzial), When die Pille gerendert wird, Then nennt sie BEIDE --
    nicht nur die der Spitzenstunde.

    Das ist die Gegenprobe zur Mutation (a) der Spec ("nur der Datenpunkt der
    Spitzenstunde"): die Spitzenstunde ist hier 14:00 und traegt allein CAPE.
    """
    seg = _segment([_dp(14, cape=1500.0, cin=5.0), _dp(17, lpi=60.0)])
    fruehe, spaete = (dp.thunder_level_signals for dp in seg.timeseries.data)
    assert (fruehe, spaete) == (["cape"], ["blitzpotenzial"]), (
        f"Vorbedingung: die beiden Stunden muessen VERSCHIEDENE Zutaten "
        f"tragen -- sonst belegt die Vereinigung nichts: {fruehe!r}/{spaete!r}")
    assert _pille(_mail([seg])) == (
        "Gewitter hoch ab 14:00 · stärkste 14:00 · CAPE, Blitzpotenzial"), (
        f"Die Pille muss die Traeger ALLER Stunden mit der Hoechststufe "
        f"vereinigen: {_pille(_mail([seg]))!r}")


def test_ac8_pille_nennt_keine_zutat_ausserhalb_des_tagesfensters():
    """AC-8 (Kohaerenz Pille): Given eine dritte Zutat traegt die Hoechststufe
    NUR in einer Stunde AUSSERHALB des Tagesfensters (02:00), When die Pille
    gerendert wird, Then erscheint sie NICHT -- Stufe und Herkunft stammen aus
    DERSELBEN gefensterten Liste, ohne zweiten Datenzugriff.

    Vorbedingung im selben Test: das SEGMENT-Aggregat kennt die dritte Zutat
    sehr wohl. Ohne diese Zusicherung waere der Test auch dann gruen, wenn die
    Fixture die dritte Zutat gar nicht erst erzeugte.
    """
    seg = _segment(
        [_dp(2, dichte=0.5)] + [_dp(h, cape=1500.0, cin=5.0) for h in (14, 15)],
        start_h=6, end_h=17,
    )
    assert seg.aggregated.thunder_level_max_signals == ["blitzdichte", "cape"], (
        f"Vorbedingung: das Segment-Aggregat MUSS die dritte Zutat kennen -- "
        f"sonst belegt dieser Test nichts: "
        f"{seg.aggregated.thunder_level_max_signals!r}")
    assert _pille(_mail([seg])) == "Gewitter hoch ab 14:00 · stärkste 14:00 · CAPE", (
        f"Nur Zutaten aus dem Tagesfenster 04-19 duerfen erscheinen -- die "
        f"Blitzdichte liegt bei 02:00 ausserhalb: {_pille(_mail([seg]))!r}")


# ===========================================================================
# Ort 2 — Kommando-Timeline je Wegpunkt
# ===========================================================================

def test_ac2_timeline_wegpunkt_nennt_die_tragende_zutat(kommando):
    """AC-2: Given die Stufe eines Wegpunkts kommt ausschliesslich ueber CAPE
    zustande, When der Nutzer die Timeline abruft, Then zeigt die
    Wegpunkt-Zeile "⛈ leicht · CAPE" statt nur "⛈ leicht"."""
    seg = _segment([_dp(10, tag=kommando.heute, cape=400.0, cin=5.0)],
                   tag=kommando.heute, start_h=6, end_h=10)
    antwort = kommando.frage([seg], body=_TIMELINE_HEUTE)
    assert _timeline_gewitter(antwort) == ["leicht · CAPE"], (
        f"Die Wegpunkt-Zeile muss die tragende Zutat neben der Stufe nennen: "
        f"{antwort!r}")


def test_ac10_timeline_zeigt_je_wegpunkt_nur_die_eigene_zutat(kommando):
    """AC-10 (Kohaerenz Timeline): Given zwei Wegpunkte desselben Tages tragen
    ihre Stufe ueber VERSCHIEDENE Zutaten, When die Timeline gerendert wird,
    Then zeigt JEDE Zeile ausschliesslich die Zutat ihres EIGENEN
    Segment-Aggregats -- keine Vermischung zwischen Wegpunkten.

    Gegenprobe zur Mutation (e) der Spec (eine EINMAL ausserhalb der Schleife
    berechnete, globale Traegerliste): die wuerde beide Zeilen gleich machen.
    """
    heute = kommando.heute
    wegpunkte = [
        _segment([_dp(10, tag=heute, cape=1500.0, cin=5.0)],
                 tag=heute, start_h=6, end_h=10, seg_id=1),
        _segment([_dp(14, tag=heute, lpi=60.0)],
                 tag=heute, start_h=11, end_h=14, seg_id=2),
    ]
    traeger = [s.aggregated.thunder_level_max_signals for s in wegpunkte]
    assert traeger == [["cape"], ["blitzpotenzial"]], (
        f"Vorbedingung: die beiden Wegpunkt-Aggregate muessen VERSCHIEDENE "
        f"Zutaten tragen -- sonst belegt der Test keine Trennung: {traeger!r}")
    antwort = kommando.frage(wegpunkte, body=_TIMELINE_HEUTE)
    assert _timeline_gewitter(antwort) == ["hoch · CAPE", "hoch · Blitzpotenzial"], (
        f"Jede Wegpunkt-Zeile darf NUR die Zutat ihres eigenen Aggregats "
        f"nennen: {antwort!r}")


def test_ac15_alt_schnappschuss_zeigt_die_stufe_ohne_herkunft(kommando):
    """AC-15: Given ein gespeicherter Schnappschuss OHNE
    ``thunder_level_max_signals`` (vor Scheibe 1/2) wird fuer die Timeline
    geladen, When der Nutzer die Timeline abruft, Then zeigt die
    Wegpunkt-Zeile die Stufe unveraendert, aber OHNE Herkunfts-Zusatz -- kein
    "unbekannt", kein leerer Trenner, kein Fehler.

    Gegenprobe im selben Test (Spec-Pflicht, sonst waere die zugesicherte
    ABWESENHEIT von Anfang an gruen): derselbe Trip mit VOLLSTAENDIGEM
    Schnappschuss nennt die Zutat sehr wohl.
    """
    heute = kommando.heute
    segmente = [_segment([_dp(10, tag=heute, cape=1500.0, cin=5.0)],
                         tag=heute, start_h=6, end_h=10)]

    vollstaendig = kommando.frage(segmente, body=_TIMELINE_HEUTE)
    assert _timeline_gewitter(vollstaendig) == ["hoch · CAPE"], (
        f"Gegenprobe gescheitert: der VOLLSTAENDIGE Schnappschuss MUSS die "
        f"Herkunft tragen, sonst beweist die Abwesenheit unten nichts: "
        f"{vollstaendig!r}")

    alt = kommando.frage(segmente, body=_TIMELINE_HEUTE, alt=True)
    assert _timeline_gewitter(alt) == ["hoch"], (
        f"Ein Alt-Schnappschuss ohne Traegerfeld zeigt die Stufe unveraendert "
        f"und KEINEN Zusatz: {alt!r}")


# ===========================================================================
# Ort 3 — GLANCE-Tageszeile (in Scheibe 2 bewusst ausgelassen, jetzt abgeloest)
# ===========================================================================

def test_ac3_glance_tageszeile_nennt_die_tragende_zutat(kommando):
    """AC-3 (abgeloeste Entscheidung): Given die Tages-Gewitterstufe kommt
    ausschliesslich ueber CAPE zustande, When der Nutzer GLANCE sendet, Then
    zeigt die Zeile "⛈ Gewitter: leicht · CAPE" statt -- wie bis
    einschliesslich Scheibe 2 -- nur "⛈ Gewitter: leicht".

    Das ist die zentrale Gegenprobe der in dieser Scheibe aufgehobenen
    Scheibe-2-Entscheidung (dortige D3/Known Limitation 4) und zugleich die
    Gegenprobe zur Mutation (b) der Spec.
    """
    seg = _segment([_dp(10, tag=kommando.heute, cape=400.0, cin=5.0)],
                   tag=kommando.heute, start_h=6, end_h=10)
    antwort = kommando.frage([seg], body="GLANCE")
    assert _glance_gewitter(antwort, "heute") == "leicht · CAPE", (
        f"Die GLANCE-Tageszeile muss die tragende Zutat nennen: {antwort!r}")


def test_ac7_glance_vereinigt_die_zutaten_zweier_wegpunkte(kommando):
    """AC-7: Given zwei Wegpunkte desselben Kalendertags erreichen die
    Tages-Hoechststufe ueber VERSCHIEDENE Zutaten, When der Nutzer GLANCE
    sendet, Then nennt die Zeile BEIDE -- nicht nur die des zeitlich ersten
    Wegpunkts."""
    heute = kommando.heute
    antwort = kommando.frage([
        _segment([_dp(10, tag=heute, cape=1500.0, cin=5.0)],
                 tag=heute, start_h=6, end_h=10, seg_id=1),
        _segment([_dp(14, tag=heute, lpi=60.0)],
                 tag=heute, start_h=11, end_h=14, seg_id=2),
    ], body="GLANCE")
    assert _glance_gewitter(antwort, "heute") == "hoch · CAPE, Blitzpotenzial", (
        f"Die GLANCE-Zeile muss die Traeger ALLER Wegpunkte mit der "
        f"Tages-Hoechststufe vereinigen: {antwort!r}")


def test_ac11_glance_nennt_keine_zutat_eines_anderen_kalendertags(kommando):
    """AC-11 (Kohaerenz GLANCE): Given ein Wegpunkt eines ANDEREN
    Kalendertags traegt eine dritte, abweichende Zutat auf DERSELBEN
    Hoechststufe, When der Nutzer GLANCE sendet, Then erscheint sie in der
    Zeile des Zieltags NICHT.

    Gegenprobe im selben Lauf: die "morgen"-Zeile derselben Antwort nennt die
    dritte Zutat sehr wohl -- die Zutat existiert also, sie ist nur dem
    anderen Tag zugeordnet.
    """
    heute, morgen = kommando.heute, kommando.morgen
    antwort = kommando.frage([
        _segment([_dp(10, tag=heute, cape=1500.0, cin=5.0)],
                 tag=heute, start_h=6, end_h=10, seg_id=1),
        _segment([_dp(14, tag=morgen, dichte=0.5)],
                 tag=morgen, start_h=6, end_h=14, seg_id=2),
    ], body="GLANCE")
    assert _glance_gewitter(antwort, "morgen") == "hoch · Blitzdichte", (
        f"Gegenprobe gescheitert: die dritte Zutat MUSS am anderen Tag "
        f"erscheinen, sonst belegt ihre Abwesenheit heute nichts: {antwort!r}")
    assert _glance_gewitter(antwort, "heute") == "hoch · CAPE", (
        f"Die Herkunft muss aus den Wegpunkten DES Zieltags kommen -- die "
        f"Blitzdichte von morgen darf heute nicht erscheinen: {antwort!r}")


# ===========================================================================
# Ort 4 — Ortsvergleich-Stundentabelle (HTML + Klartext)
# ===========================================================================

def test_ac4_stundentabelle_nennt_die_zutat_in_html_und_klartext():
    """AC-4: Given eine Stunde eines verglichenen Ortes zeigt eine Stufe, die
    ausschliesslich ueber CAPE zustande kommt, When die Vergleichsmail
    gerendert wird, Then zeigt die Stundenzelle "leicht · CAPE" -- an BEIDEN
    Stellen (HTML und Klartext) DERSELBEN Mail.

    HTML und Klartext werden getrennt zugesichert (Mutationsproben (c) und
    (d) der Spec): sie haben zwei unabhaengige Aufrufstellen
    (``compare_html._render_hour_row`` bzw. die Stundenschleife in
    ``comparison.render_comparison_text``).
    """
    ort = _ort("Capeort", [_cdp(14, cape=400.0, cin=5.0)])
    assert ort.hourly_data[0].thunder_level_signals == ["cape"], (
        f"Vorbedingung: die ECHTE Fusion muss CAPE als alleinigen Traeger "
        f"ausweisen: {ort.hourly_data[0].thunder_level_signals!r}")
    html, text = _compare_mail(ort)
    assert _html_stunden(html)["Capeort"] == [["16", "leicht · CAPE"]], (
        f"Die HTML-Stundenzelle muss die tragende Zutat nennen: "
        f"{_html_stunden(html)['Capeort']!r}")
    assert _text_stunden(text)["Capeort"] == ["16:00  Thdr leicht · CAPE"], (
        f"Der Klartext-Teil DERSELBEN Mail muss dieselbe Herkunft zeigen: "
        f"{_text_stunden(text)['Capeort']!r}")


def test_ac9_jede_stundenzeile_zeigt_nur_die_zutat_ihres_datenpunkts():
    """AC-9 (Kohaerenz Stundentabelle): Given zwei benachbarte Stunden
    desselben Ortes tragen ihre Stufe ueber VERSCHIEDENE Zutaten, When die
    Stundentabelle gerendert wird, Then zeigt JEDE Zeile ausschliesslich die
    Zutat IHRES EIGENEN Datenpunkts -- keine Vermischung zwischen benachbarten
    Zeilen, in HTML wie im Klartext."""
    ort = _ort("Zweistundenort",
               [_cdp(14, cape=1500.0, cin=5.0), _cdp(15, dichte=0.5)])
    traeger = [dp.thunder_level_signals for dp in ort.hourly_data]
    assert traeger == [["cape"], ["blitzdichte"]], (
        f"Vorbedingung: die beiden Stunden muessen VERSCHIEDENE Zutaten "
        f"tragen -- sonst belegt der Test keine Trennung: {traeger!r}")

    html, text = _compare_mail(ort)
    assert _html_stunden(html)["Zweistundenort"] == [
        ["16", "hoch · CAPE"], ["17", "hoch · Blitzdichte"],
    ], (f"Jede HTML-Stundenzeile darf nur die Zutat ihres eigenen "
        f"Datenpunkts zeigen: {_html_stunden(html)['Zweistundenort']!r}")
    assert _text_stunden(text)["Zweistundenort"] == [
        "16:00  Thdr hoch · CAPE", "17:00  Thdr hoch · Blitzdichte",
    ], (f"Dasselbe im Klartext-Teil derselben Mail: "
        f"{_text_stunden(text)['Zweistundenort']!r}")


def test_ac12_compare_sms_und_telegram_zeigen_keine_stunden_herkunft():
    """AC-12 (kein Leck Compare-SMS/Telegram): Given die Stundentabelle zeigt
    eine Zutat, die NUR auf Stundenebene existiert (Blitzdichte, unterhalb der
    Tages-Hoechststufe), When derselbe Vergleich als SMS oder Telegram
    gerendert wird, Then taucht sie dort NICHT auf -- beide Kanaele zeigen
    ausschliesslich die Uebersichtszeile.

    🔴 ABWEICHUNG VON DER SPEC (belegt, kein Ermessen): der Spec-Testhinweis
    zu AC-12 verlangt woertlich, dass "keiner der beiden Texte" eine der vier
    Zutat-Bezeichnungen enthaelt. Fuer ``render_compare_telegram()`` ist das
    seit Scheibe 1 nachweislich falsch: dort zeigt die Uebersichtszeile die
    Herkunft ausdruecklich (S1 AC-4, live seit 2026-08-12, bewacht von
    ``test_thunder_origin_compare.py::test_ac4_telegram_zeigt_dieselbe_
    herkunft_wie_die_mail``). Die woertliche Fassung waere also ein Test, der
    NUR gruen werden koennte, wenn eine ausgelieferte Zusage bricht. Geprueft
    wird deshalb die Aussage, die AC-12 traegt: eine Zutat, die ausschliesslich
    aus den NEUEN Stundentabellen-Aufrufstellen dieser Scheibe stammen kann,
    darf weder in der SMS noch im Telegram erscheinen. Fuer die SMS bleibt die
    absolute Fassung (keine der vier Zutaten) erhalten -- das ist die
    Gegenprobe zur Mutation (f) der Spec, die die SMS-Zelle probeweise ueber
    die Herkunfts-Aufrufstelle baut.
    """
    ort = _ort("Leckort", [_cdp(14, cape=1500.0, cin=5.0),
                           _cdp(15, dichte=0.005)])
    stufen = [(dp.thunder_level, dp.thunder_level_signals)
              for dp in ort.hourly_data]
    assert stufen == [(ThunderLevel.HIGH, ["cape"]),
                      (ThunderLevel.LOW, ["blitzdichte"])], (
        f"Vorbedingung: die Blitzdichte darf NUR unterhalb der "
        f"Tages-Hoechststufe tragen -- sonst stuende sie legitim auch in der "
        f"Uebersicht: {stufen!r}")

    ergebnis = _vergleich(ort)
    sms = render_compare_sms(ergebnis, enabled_metrics=["thunder_max"])
    telegram = render_compare_telegram(ergebnis, enabled_metrics=["thunder_max"])
    html, text = _compare_mail(ort)

    assert "Blitzdichte" in text.split("STUNDENVERLAUF", 1)[1], (
        f"Gegenprobe gescheitert: die stundenweise Zutat MUSS in der "
        f"Stundentabelle erscheinen, sonst beweist ihre Abwesenheit in "
        f"SMS/Telegram nichts: {_text_stunden(text)!r}")

    assert "hoch" in sms, f"Die Stufe selbst muss in der SMS stehen: {sms!r}"
    for zutat in ALLE_ZUTATEN:
        assert zutat not in sms, (
            f"Compare-SMS ist bewusst OHNE Herkunft (PO-Entscheidung) -- "
            f"'{zutat}' darf nicht vorkommen: {sms!r}")

    assert "CAPE" in telegram, (
        f"Gegenprobe gescheitert: Telegram MUSS die Herkunft der "
        f"Uebersichtszeile weiterhin zeigen (Scheibe 1 AC-4): {telegram!r}")
    assert "Blitzdichte" not in telegram, (
        f"Telegram zeigt ausschliesslich die Uebersichtszeile -- die nur "
        f"stundenweise tragende Blitzdichte darf dort nicht auftauchen: "
        f"{telegram!r}")


def test_ac14_s1_uebersichtszeile_bleibt_zeichengleich():
    """AC-14: Given die Ortsvergleich-Uebersichtszeile zeigte vor dieser
    Scheibe bereits eine Herkunft (Scheibe 1), When diese Scheibe
    ausgeliefert ist, Then bleibt ihr Text fuer eine unveraenderte Fixture
    zeichengleich -- die Aenderung an den Stundentabellen-Aufrufstellen (D4)
    ruehrt den Rumpf von ``_fmt_thunder()`` NICHT an.

    Beides in DERSELBEN gerenderten Vergleichsmail: die Uebersicht bleibt
    Zeichen fuer Zeichen wie in Scheibe 1, die Stundentabelle bekommt die
    Herkunft neu (Gegenprobe -- ohne sie waere die Zeichengleichheit von
    Anfang an gruen).

    Der zweite Ort ist der Drift-Fall aus Scheibe 1 AC-12: Engine-Stufe
    ``HIGH``, aus den Stundenwerten abgeleitet ``MED`` -> die Uebersicht zeigt
    dort BEWUSST keine Herkunft. Eine Herkunfts-Logik, die faelschlich in den
    ``_fmt_thunder()``-Rumpf oder in die Uebersichts-Aufrufstelle wanderte,
    braeche genau hier -- waehrend die Stundenzeile desselben Ortes ihre
    eigene Zutat sehr wohl zeigt.
    """
    orte = (
        _ort("Alpenort", [_cdp(14, cape=1500.0, cin=5.0)]),
        _ort("Driftort", [_cdp(14, cape=800.0, cin=5.0)],
             thunder_level_max=ThunderLevel.HIGH),
    )
    html, text = _compare_mail(*orte)

    assert _html_uebersicht(html) == ["hoch · CAPE", "hoch"], (
        f"Die HTML-Uebersichtszeile muss zeichengleich zu Scheibe 1 bleiben: "
        f"{_html_uebersicht(html)!r}")
    assert _text_uebersicht(text) == ["hoch · CAPE", "hoch"], (
        f"Die Klartext-Uebersichtszeile muss zeichengleich zu Scheibe 1 "
        f"bleiben: {_text_uebersicht(text)!r}")

    assert _html_stunden(html) == {
        "Alpenort": [["16", "hoch · CAPE"]],
        "Driftort": [["16", "mittel · CAPE"]],
    }, (f"Gegenprobe gescheitert: die Stundentabelle DERSELBEN Mail MUSS die "
        f"Herkunft je Datenpunkt zeigen -- auch beim Drift-Ort, dessen "
        f"Uebersicht bewusst keine nennt: {_html_stunden(html)!r}")


# ===========================================================================
# Zeichengleichheit ohne Gewitter — alle vier Orte (AC-16)
# ===========================================================================

def test_ac16_ohne_gewitter_bleiben_pille_timeline_und_glance_zeichengleich(
        kommando):
    """AC-16 (Trip-Teil): Given kein Datenpunkt erreicht eine Stufe ueber
    NONE, When Pille, Timeline und GLANCE-Zeile gerendert werden, Then bleibt
    die Ausgabe an allen drei Orten zeichengleich zu vor dieser Scheibe --
    kein Herkunfts-Zusatz. Besonders GLANCE, weil diese Scheibe dort erstmals
    ueberhaupt Herkunft anzeigt (AC-3).

    Gegenprobe im selben Test (Spec-Pflicht): dieselben Fixturen mit CAPE
    ueber der Leiter zeigen die Herkunft an allen drei Orten sehr wohl.
    """
    heute = kommando.heute
    ruhig = _segment([_dp(h, tag=heute, cape=50.0, cin=5.0) for h in (10, 11)],
                     tag=heute, start_h=6, end_h=11)
    laut = _segment([_dp(h, tag=heute, cape=1500.0, cin=5.0) for h in (10, 11)],
                    tag=heute, start_h=6, end_h=11)

    assert _pille(_mail([ruhig])) == "kein Gewitter", (
        f"Ohne Gewitter bleibt die Pille zeichengleich: "
        f"{_pille(_mail([ruhig]))!r}")
    assert _timeline_gewitter(
        kommando.frage([ruhig], body=_TIMELINE_HEUTE)) == ["kein"], (
        "Ohne Gewitter bleibt die Timeline-Zeile zeichengleich")
    assert _glance_gewitter(
        kommando.frage([ruhig], body="GLANCE"), "heute") == "kein", (
        "Ohne Gewitter bleibt die GLANCE-Zeile zeichengleich")

    assert _pille(_mail([laut])) == "Gewitter hoch ab 10:00 · stärkste 10:00 · CAPE", (
        f"Gegenprobe gescheitert: mit erreichter Stufe MUSS die Pille die "
        f"Herkunft zeigen: {_pille(_mail([laut]))!r}")
    assert _timeline_gewitter(
        kommando.frage([laut], body=_TIMELINE_HEUTE)) == ["hoch · CAPE"], (
        "Gegenprobe gescheitert: die Timeline MUSS die Herkunft zeigen")
    assert _glance_gewitter(
        kommando.frage([laut], body="GLANCE"), "heute") == "hoch · CAPE", (
        "Gegenprobe gescheitert: GLANCE MUSS die Herkunft zeigen")


def test_ac16_ohne_gewitter_bleibt_die_compare_stundenzelle_zeichengleich():
    """AC-16 (Compare-Teil): Given eine Stunde zeigt kein Gewitter, When die
    Stundentabelle gerendert wird, Then bleibt die Zelle zeichengleich ("—",
    ohne Trenner) -- in HTML wie im Klartext.

    Gegenprobe im selben Vergleich: der zweite Ort mit erreichter Stufe zeigt
    seine Herkunft sehr wohl.
    """
    ruhig = _ort("Ruhigort", [_cdp(14, cape=50.0, cin=5.0)])
    laut = _ort("Sturmort", [_cdp(14, cape=1500.0, cin=5.0)])
    assert ruhig.hourly_data[0].thunder_level == ThunderLevel.NONE, (
        f"Vorbedingung: der ruhige Ort muss die ECHTE Stufe NONE tragen: "
        f"{ruhig.hourly_data[0].thunder_level!r}")

    html, text = _compare_mail(ruhig, laut)
    assert _html_stunden(html)["Ruhigort"] == [["16", "—"]], (
        f"Ohne erreichte Stufe bleibt die HTML-Stundenzelle zeichengleich: "
        f"{_html_stunden(html)['Ruhigort']!r}")
    assert _text_stunden(text)["Ruhigort"] == ["16:00  Thdr —"], (
        f"Dasselbe im Klartext: {_text_stunden(text)['Ruhigort']!r}")

    assert _html_stunden(html)["Sturmort"] == [["16", "hoch · CAPE"]], (
        f"Gegenprobe gescheitert: der Ort MIT erreichter Stufe MUSS die "
        f"Herkunft zeigen: {_html_stunden(html)['Sturmort']!r}")


# ===========================================================================
# Kein Leck in Trip-SMS/Premium-SMS (AC-13)
# ===========================================================================

def test_ac13_trip_sms_zeigt_die_stufe_aber_keine_herkunft():
    """AC-13: Given die Pille traegt ab dieser Scheibe eine Herkunft, die in
    ``email_plain`` landet, When der Trip-Bericht versendet wird, Then
    enthaelt weder ``report.sms_text`` noch -- ueber den Rueckfallweg
    ``sms_text or email_plain`` (``notification_service.py:428``/``446``) --
    die tatsaechlich zugestellte SMS/Premium-SMS eine der vier
    Zutat-Bezeichnungen; die Gewitterstufe selbst bleibt sichtbar.

    ``report.sms_text`` muss zusaetzlich NICHT-LEER sein: nur dann ist belegt,
    dass der Rueckfall auf ``email_plain`` strukturell nicht greift (#868,
    analog Scheibe 2 AC-8).

    Gegenprobe im selben Lauf (Spec-Pflicht): die Pille DERSELBEN Mail zeigt
    die Herkunft sehr wohl -- sonst waere dieses AC auch dann gruen, wenn die
    Herkunft nirgends erschiene.
    """
    seg = _segment([_dp(h, cape=1500.0, cin=5.0, lpi=60.0) for h in (14, 15, 16)])
    bericht = _mail([seg])

    assert bericht.sms_text, (
        "sms_text muss immer erzeugt werden (#868) -- sonst greift der "
        "Rueckfall `sms_text or email_plain` und traegt die neue Herkunft in "
        "SMS/Premium-SMS, entgegen der PO-Entscheidung")
    zugestellt = bericht.sms_text or bericht.email_plain
    assert "TH:H" in zugestellt, (
        f"Die Gewitterstufe selbst bleibt in der SMS sichtbar: {zugestellt!r}")
    for zutat in ALLE_ZUTATEN:
        assert zutat not in zugestellt, (
            f"SMS/Premium-SMS sind bewusst OHNE Herkunft (PO-Entscheidung) -- "
            f"'{zutat}' darf nicht vorkommen: {zugestellt!r}")

    assert _pille(bericht) == (
        "Gewitter hoch ab 14:00 · stärkste 14:00 · CAPE, Blitzpotenzial"), (
        f"Gegenprobe gescheitert: die Mail DERSELBEN Fixture MUSS die "
        f"Herkunft zeigen, sonst beweist die SMS-Abwesenheit nichts: "
        f"{_pille(bericht)!r}")
