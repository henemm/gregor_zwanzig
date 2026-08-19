"""TDD RED — Issue #1680 Scheibe 2: Herkunft der Gewitterstufe auf der Trip-Seite.

SPEC: docs/specs/modules/feat_1680_s2_gewitter_herkunft_trip.md (AC-1 bis AC-10)
KONTEXT: docs/context/feat-1680-s2-herkunft-trip.md

RED-Ursache (heute): ``output.metric_format.union_of_max_carriers()`` existiert
nicht; ``_aggregate_day()`` hat keinen Schluessel fuer die Traeger,
``_fmt_gewitter()`` und ``_format_thunder()`` haengen kein Herkunfts-Suffix an,
und ``day_window._merge_hour()`` laesst ``thunder_level_signals`` unveraendert
bei ``base`` stehen (Kontext "Neuer Befund 1") -> beide Trip-Ausgabeorte nennen
die tragende Zutat gar nicht.

Prueforte = Wirkorte: JEDER Test laeuft bis zum Text, den der Nutzer bekommt --
``TripReport.email_plain``/``sms_text`` bzw. ``CommandResult.confirmation_body``
aus ``TripCommandProcessor.process()``. Kein Zwischenwert steht fuer einen Text.

Kein Mock-Theater: die Stufen und Traegerlisten entstehen ueber die ECHTE
Fusion (``thunder_enrichment._fuse_thunder_levels`` mit den Leitern aus
``app.model_registry``) und die ECHTE Aggregation
(``WeatherMetricsService.compute_basis_metrics``) -- kein im Test getippter
Wert, keine getippte Schwelle. Der Kommandopfad laeuft ueber einen echt
gespeicherten und wieder geladenen Wetter-Schnappschuss.
"""
from __future__ import annotations

import dataclasses
import json
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
from output.metric_format import union_of_max_carriers  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage, TripCommandProcessor,
)
from services.weather_metrics import WeatherMetricsService  # noqa: E402
from services.weather_snapshot import WeatherSnapshotService  # noqa: E402

# Die VIER Zutaten der Fusion in ihrer deutschen Beschriftung
# (``metric_format.THUNDER_SIGNAL_LABEL_DE``). Keine davon darf in der SMS
# oder im GLANCE-Kommando auftauchen (AC-8, AC-10).
ALLE_ZUTATEN = ("Wettercode", "Blitzdichte", "CAPE", "Blitzpotenzial")

_TZ = ZoneInfo("UTC")
_LAT, _LON, _MODELL = 47.0, 12.0, "icon_d2"   # Gebiet DE_ALPEN
_ETAPPE = "Test-Etappe"
_TAG = date(2026, 8, 20)

_TRIP_ID = "herkunft-trip-kommando"
_TRIP_NAME = "Herkunft Trip Tour"
_USER = "default"


# ---------------------------------------------------------------------------
# Fixture-Bausteine: Rohwerte rein, echte Rechnung raus
# ---------------------------------------------------------------------------

def _dp(h: int, *, tag: date = _TAG, cape=None, cin=None, lpi=None,
        dichte=None, precip=0.0, gust=12.0) -> ForecastDataPoint:
    """Ein Stundenpunkt mit ROHWERTEN -- Stufe und Traeger rechnet die Fusion.

    ``precip``/``gust`` sind nur fuer AC-5 interessant: sie entscheiden den
    Tie-Break in ``_merge_hour()``.
    """
    return ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, h, 0, tzinfo=timezone.utc),
        t2m_c=20.0, wind10m_kmh=8.0, gust_kmh=gust, precip_1h_mm=precip,
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
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
        data=punkte,
    )


def _segment(punkte: list[ForecastDataPoint], *, tag: date = _TAG,
             start_h: int = 6, end_h: int = 17, seg_id: int = 1) -> SegmentWeatherData:
    """Segment, dessen Aggregat die ECHTE Engine rechnet
    (``compute_basis_metrics`` -> ``thunder_level_max``/
    ``thunder_level_max_signals``) -- nicht von Hand gesetzt."""
    reihe = _reihe(punkte)
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=_LAT, lon=_LON, elevation_m=1000.0),
        end_point=GPXPoint(lat=_LAT + 0.1, lon=_LON + 0.1, elevation_m=1200.0),
        start_time=datetime(tag.year, tag.month, tag.day, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(tag.year, tag.month, tag.day, end_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h), distance_km=10.0,
        ascent_m=500.0, descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=reihe,
        aggregated=WeatherMetricsService().compute_basis_metrics(reihe, tz=None),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _dc(friendly: bool = False):
    """Standard-Anzeigekonfiguration; nur die Schreibweise der Gewitterzeile
    wird gesteuert (``False`` -> "Gewitter moeglich ...", ``True`` -> "⚡ ...").
    Beide Zweige von ``_format_thunder()`` muessen die Herkunft tragen."""
    dc = build_default_display_config()
    return dataclasses.replace(dc, metrics=[
        dataclasses.replace(m, use_friendly_format=friendly)
        if m.metric_id == "thunder" else m
        for m in dc.metrics
    ])


def _mail(segmente, *, night=None, friendly: bool = False):
    """Der ECHTE Trip-Bericht (HTML + Klartext + SMS) ueber den produktiven
    Formatierer -- Prueford = Wirkort."""
    return TripReportFormatter().format_email(
        segmente, "Test-Trip", "evening", display_config=_dc(friendly),
        night_weather=night, tz=_TZ, stage_name=_ETAPPE,
    )


def _kurzfassung(bericht) -> str:
    """Die EINE Kurzzusammenfassungs-Zeile der Klartext-Mail."""
    zeilen = [ln for ln in bericht.email_plain.splitlines()
              if ln.startswith(f"{_ETAPPE}: ")]
    assert len(zeilen) == 1, (
        f"Erwartet genau EINE Kurzzusammenfassungs-Zeile in der Klartext-Mail, "
        f"gefunden: {zeilen!r}")
    return zeilen[0]


def _gewitter_teil(zeile: str) -> str:
    """"...: 20–20°C, ..., Gewitter möglich 14:00–17:00 · CAPE" -> "14:00–17:00
    · CAPE". Der Gewitter-Abschnitt steht immer am Ende des Satzes."""
    for marker in ("Gewitter möglich ", "⚡ möglich "):
        if marker in zeile:
            return zeile.split(marker, 1)[1]
    return ""


def _zutaten(zeile: str) -> set[str]:
    """Die im Gewitter-Abschnitt genannten Zutat-Beschriftungen."""
    _, _, rest = _gewitter_teil(zeile).partition(" · ")
    return {t.strip() for t in rest.split(",") if t.strip()}


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

    def frage(segmente, *, body: str = "GEWITTER", alt: bool = False) -> str:
        save_trip(Trip(id=_TRIP_ID, name=_TRIP_NAME, stages=[
            Stage(id="S1", name="Heute", date=heute, waypoints=[
                Waypoint(id="W1", name="Start", lat=_LAT, lon=_LON, elevation_m=1000),
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
            f"Das {body}-Kommando muss antworten, nicht scheitern: "
            f"{ergebnis.confirmation_body!r}")
        return ergebnis.confirmation_body

    return SimpleNamespace(heute=heute, morgen=heute + timedelta(days=1), frage=frage)


def test_ac1_kurzzusammenfassung_nennt_die_tragende_zutat():
    """AC-1: Given das Gewitterfenster kommt ausschliesslich ueber CAPE
    zustande, When die Trip-Mail gerendert wird, Then lautet der Satz
    "Gewitter möglich 14:00–17:00 · CAPE" statt nur "... 14:00–17:00"."""
    seg = _segment([_dp(h, cape=1500.0, cin=5.0) for h in (14, 15, 16)])
    zeile = _kurzfassung(_mail([seg]))
    assert _gewitter_teil(zeile) == "14:00–17:00 · CAPE", (
        f"Die Kurzzusammenfassung muss die tragende Zutat neben dem "
        f"Zeitfenster nennen: {zeile!r}")


def test_ac1_auch_die_freundliche_schreibweise_traegt_die_herkunft():
    """AC-1 (zweiter Zweig): ``_format_thunder()`` hat zwei Textvarianten.
    Die Herkunft haengt an BEIDEN -- sonst zeigt jeder Trip mit der
    Default-Einstellung (``use_friendly_format=True``) weiterhin nichts."""
    seg = _segment([_dp(h, cape=1500.0, cin=5.0) for h in (14, 15, 16)])
    zeile = _kurzfassung(_mail([seg], friendly=True))
    assert "⚡ möglich 14:00–17:00 · CAPE" in zeile, (
        f"Auch die freundliche Schreibweise muss die Herkunft tragen: {zeile!r}")


def test_ac2_gewitter_kommando_nennt_die_tragende_zutat(kommando):
    """AC-2: Given die Tagesstufe kommt ausschliesslich ueber CAPE zustande,
    When der Nutzer GEWITTER sendet, Then lautet die Antwort
    "⛈ Gewitter heute (dd.mm): leicht · CAPE" statt nur "... leicht"."""
    seg = _segment([_dp(h, tag=kommando.heute, cape=400.0, cin=5.0) for h in (10, 11)],
                   tag=kommando.heute, start_h=6, end_h=12)
    antwort = kommando.frage([seg])
    assert antwort == f"⛈ Gewitter heute ({kommando.heute:%d.%m}): leicht · CAPE", (
        f"Die GEWITTER-Antwort muss die tragende Zutat neben der Stufe "
        f"nennen: {antwort!r}")


def test_ac3_beide_zutaten_derselben_stunde_werden_in_katalogreihenfolge_genannt():
    """AC-3: Given CAPE UND Blitzpotenzial erreichen in derselben Stunde die
    Hoechststufe, When die Kurzzusammenfassung gerendert wird, Then werden
    BEIDE in der Reihenfolge aus ``THUNDER_SIGNAL_LABEL_DE`` genannt -- kein
    Gewinner wird gekuert (PO-Auslegung (ii))."""
    seg = _segment([_dp(h, cape=1500.0, cin=5.0, lpi=60.0) for h in (14, 15, 16)])
    zeile = _kurzfassung(_mail([seg]))
    assert _gewitter_teil(zeile) == "14:00–17:00 · CAPE, Blitzpotenzial", (
        f"Beide Traeger der Hoechststufe muessen erscheinen, CAPE vor "
        f"Blitzpotenzial (Katalogreihenfolge): {zeile!r}")


def test_ac4_gewitter_kommando_vereinigt_die_zutaten_mehrerer_wegpunkte(kommando):
    """AC-4: Given zwei Wegpunkte desselben Tages erreichen die Tages-
    Hoechststufe ueber VERSCHIEDENE Zutaten, When der Nutzer GEWITTER sendet,
    Then nennt die Antwort BEIDE -- nicht nur die des zeitlich ersten.

    Der dritte Wegpunkt traegt eine dritte Zutat auf NIEDRIGERER Stufe: er
    darf NICHT genannt werden. Ohne ihn waere dieselbe Zusicherung auch dann
    gruen, wenn die Vereinigung ueber ALLE Wegpunkte liefe statt nur ueber die
    am Maximum (Mutationsprobe (a) der Spec).
    """
    heute = kommando.heute
    wegpunkte = [
        _segment([_dp(10, tag=heute, cape=1500.0, cin=5.0)],
                 tag=heute, start_h=6, end_h=10, seg_id=1),
        _segment([_dp(14, tag=heute, lpi=60.0)],
                 tag=heute, start_h=11, end_h=14, seg_id=2),
        _segment([_dp(16, tag=heute, dichte=0.005)],
                 tag=heute, start_h=15, end_h=16, seg_id=3),
    ]
    antwort = kommando.frage(wegpunkte)
    assert antwort == f"⛈ Gewitter heute ({heute:%d.%m}): hoch · CAPE, Blitzpotenzial", (
        f"Die Antwort muss die Traeger ALLER Wegpunkte mit der Hoechststufe "
        f"vereinigen -- und nur diese: {antwort!r}")


def test_ac5_ankunftsstunde_behaelt_beide_zutaten():
    """AC-5: Given an der Ankunftsstunde ueberschneiden sich Segment- und
    Nachtfenster mit zwei Punkten derselben Hoechststufe ueber verschiedene
    Zutaten, When die Kurzzusammenfassung sie zu EINEM Punkt zusammenfuehrt,
    Then traegt der Satz BEIDE Zutaten.

    Der Segmentpunkt gewinnt den Tie-Break in ``_merge_hour()`` (mehr Regen,
    staerkere Boeen) -- ein fuer die Herkunft sachfremdes Kriterium
    (Kontext "Neuer Befund 1"). Die fruehere Stunde 12:00 traegt eine dritte
    Zutat auf niedrigerer Stufe und darf nicht mitgenannt werden.
    """
    seg = _segment(
        [_dp(12, dichte=0.005), _dp(16, cape=1500.0, cin=5.0, precip=5.0, gust=90.0)],
        start_h=6, end_h=16,
    )
    night = _reihe([_dp(16, lpi=60.0, precip=0.0, gust=1.0), _dp(18)])
    zeile = _kurzfassung(_mail([seg], night=night))
    assert _zutaten(zeile) == {"CAPE", "Blitzpotenzial"}, (
        f"Die zusammengefuehrte Ankunftsstunde muss BEIDE Traeger der "
        f"Hoechststufe behalten (und nur diese): {zeile!r}")


def test_ac6_zutat_ausserhalb_des_tagesfensters_erscheint_nicht():
    """AC-6: Given eine dritte Zutat traegt die Hoechststufe NUR in einer
    Stunde ausserhalb des Tagesfensters (02:00), When die Kurzzusammenfassung
    gerendert wird, Then erscheint sie NICHT -- Zeitfenster und Herkunft
    stammen aus derselben gefensterten Liste, ohne zweiten Datenzugriff."""
    seg = _segment(
        [_dp(2, dichte=0.5)] + [_dp(h, cape=1500.0, cin=5.0) for h in (14, 15)],
        start_h=6, end_h=17,
    )
    assert seg.aggregated.thunder_level_max_signals == ["blitzdichte", "cape"], (
        f"Vorbedingung: das SEGMENT-Aggregat kennt die dritte Zutat sehr wohl "
        f"-- sonst belegt dieser Test nichts: "
        f"{seg.aggregated.thunder_level_max_signals!r}")
    zeile = _kurzfassung(_mail([seg]))
    assert _gewitter_teil(zeile) == "14:00–16:00 · CAPE", (
        f"Nur Zutaten aus dem gefensterten Stundenbereich duerfen erscheinen "
        f"-- 'Blitzdichte' liegt bei 02:00 ausserhalb: {zeile!r}")


def test_ac7_zutat_eines_anderen_kalendertags_erscheint_nicht(kommando):
    """AC-7: Given ein Wegpunkt eines ANDEREN Kalendertags traegt eine dritte
    Zutat, When der Nutzer GEWITTER sendet, Then nennt die Antwort nur Zutaten
    von Wegpunkten des Zieltags."""
    heute, morgen = kommando.heute, kommando.morgen
    antwort = kommando.frage([
        _segment([_dp(14, tag=heute, cape=1500.0, cin=5.0)],
                 tag=heute, start_h=6, end_h=14, seg_id=1),
        _segment([_dp(14, tag=morgen, dichte=0.5)],
                 tag=morgen, start_h=6, end_h=14, seg_id=2),
    ])
    assert antwort == f"⛈ Gewitter heute ({heute:%d.%m}): hoch · CAPE", (
        f"Die Herkunft muss aus den Wegpunkten DES Zieltags kommen -- die "
        f"Blitzdichte von morgen darf nicht erscheinen: {antwort!r}")


def test_ac8_sms_zeigt_die_stufe_aber_keine_herkunft():
    """AC-8: Given derselbe Bericht erzeugt Mail UND SMS, When er versendet
    wird, Then traegt weder ``sms_text`` noch der tatsaechlich zugestellte
    Rueckfallausdruck ``sms_text or email_plain`` eine der vier Zutat-
    Bezeichnungen; die Gewitterstufe selbst bleibt sichtbar.

    Gegenprobe im selben Lauf (Spec-Pflicht): die Mail DERSELBEN Fixture zeigt
    die Herkunft sehr wohl -- sonst waere dieses AC auch dann gruen, wenn die
    Herkunft nirgends erschiene. Und ``sms_text`` muss nicht-leer sein: nur
    dann ist belegt, dass der Rueckfall auf ``email_plain``
    (``notification_service.py:417,433``) strukturell nicht greift (#868).
    """
    seg = _segment([_dp(h, cape=1500.0, cin=5.0, lpi=60.0) for h in (14, 15, 16)])
    bericht = _mail([seg])

    assert bericht.sms_text, (
        "sms_text muss immer erzeugt werden (#868) -- sonst greift der "
        "Rueckfall `sms_text or email_plain` und traegt die Herkunft in die "
        "SMS/Premium-SMS, entgegen der PO-Entscheidung")
    zugestellt = bericht.sms_text or bericht.email_plain
    assert "TH:H" in zugestellt, (
        f"Die Gewitterstufe selbst bleibt in der SMS sichtbar: {zugestellt!r}")
    for zutat in ALLE_ZUTATEN:
        assert zutat not in zugestellt, (
            f"SMS/Premium-SMS sind bewusst OHNE Herkunft (PO-Entscheidung) -- "
            f"'{zutat}' darf nicht vorkommen: {zugestellt!r}")

    zeile = _kurzfassung(bericht)
    assert _zutaten(zeile) == {"CAPE", "Blitzpotenzial"}, (
        f"Gegenprobe gescheitert: die Mail DERSELBEN Fixture MUSS die Herkunft "
        f"zeigen, sonst beweist die SMS-Abwesenheit nichts: {zeile!r}")


def test_ac9_alt_schnappschuss_zeigt_die_stufe_ohne_herkunft(kommando):
    """AC-9: Given ein gespeicherter Schnappschuss OHNE
    ``thunder_level_max_signals`` (vor Scheibe 1) wird geladen, When der
    Nutzer GEWITTER sendet, Then zeigt die Antwort die Stufe unveraendert,
    aber OHNE Zusatz -- kein "unbekannt", kein leerer Trenner, kein Fehler.

    Gegenprobe im selben Test: derselbe Trip mit VOLLSTAENDIGEM Schnappschuss
    nennt die Zutat sehr wohl.
    """
    heute = kommando.heute
    segmente = [_segment([_dp(h, tag=heute, cape=1500.0, cin=5.0) for h in (14, 15)],
                         tag=heute, start_h=6, end_h=16)]

    vollstaendig = kommando.frage(segmente)
    assert vollstaendig == f"⛈ Gewitter heute ({heute:%d.%m}): hoch · CAPE", (
        f"Gegenprobe gescheitert: der vollstaendige Schnappschuss MUSS die "
        f"Herkunft tragen: {vollstaendig!r}")

    alt = kommando.frage(segmente, alt=True)
    assert alt == f"⛈ Gewitter heute ({heute:%d.%m}): hoch", (
        f"Ein Alt-Schnappschuss ohne Traegerfeld zeigt die Stufe unveraendert "
        f"und KEINEN Zusatz: {alt!r}")


def test_ac10_ohne_gewitter_bleiben_beide_ausgabeorte_zeichengleich(kommando):
    """AC-10 (erste Haelfte; die zweite ist abgeloest, s. Hinweis unter dieser
    Funktion): Given kein Datenpunkt erreicht eine Stufe ueber NONE, When
    Kurzzusammenfassung und GEWITTER-Kommando gerendert werden, Then bleibt
    die Ausgabe an BEIDEN Orten zeichengleich zu heute.

    Gegenprobe im selben Test: dieselbe Etappe mit CAPE ueber der Leiter zeigt
    die Herkunft an beiden Orten sehr wohl.
    """
    heute = kommando.heute
    ruhig = _segment([_dp(h, tag=heute, cape=50.0, cin=5.0) for h in (14, 15)],
                     tag=heute, start_h=6, end_h=16)
    laut = _segment([_dp(h, tag=heute, cape=1500.0, cin=5.0) for h in (14, 15)],
                    tag=heute, start_h=6, end_h=16)

    ruhige_zeile = _kurzfassung(_mail([ruhig]))
    assert "möglich" not in ruhige_zeile, (
        f"Ohne Gewitter bleibt die Kurzzusammenfassung ohne Gewitterteil "
        f"(und damit ohne Herkunft): {ruhige_zeile!r}")
    assert kommando.frage([ruhig]) == f"⛈ Gewitter heute ({heute:%d.%m}): kein", (
        "Ohne Gewitter bleibt die GEWITTER-Antwort zeichengleich zu heute")

    laute_zeile = _kurzfassung(_mail([laut]))
    assert _zutaten(laute_zeile) == {"CAPE"} and "· CAPE" in kommando.frage([laut]), (
        f"Gegenprobe gescheitert: mit erreichter Stufe MUSS die Herkunft an "
        f"beiden Orten erscheinen: {laute_zeile!r}")


# 🔴 Entfernt am 2026-08-13 (Issue #1680 Scheibe 3): hier stand
# ``test_ac10_glance_bleibt_ohne_herkunft`` -- die zweite Haelfte von AC-10.
# Sie sicherte zu, dass die GLANCE-Tageszeile den seit Scheibe 2 vorhandenen
# Traeger-Schluessel bewusst NICHT liest und zeichengleich bleibt (dortige
# Spec D3, Known Limitation 4). Der PO hat diese Entscheidung mit Scheibe 3
# ausdruecklich abgeloest: GLANCE zeigt die Herkunft jetzt genau wie das
# GEWITTER-Kommando. Der Test prueft damit veraltetes Verhalten und ist
# ersatzlos entfallen -- die Erwartung bloss umzudrehen haette dieselbe
# Zusicherung in zwei Dateien gestellt, die beim naechsten Wechsel
# auseinanderlaufen. Neuer Sollzustand:
# ``test_thunder_origin_four_places.py``, dort
# ``test_ac3_glance_tageszeile_nennt_die_tragende_zutat`` (Einzelzutat) und
# ``test_ac7_glance_vereinigt_die_zutaten_zweier_wegpunkte`` (Vereinigung);
# die NONE-Zeichengleichheit von GLANCE bewacht dort
# ``test_ac16_ohne_gewitter_bleiben_pille_timeline_und_glance_zeichengleich``.
# Die einzige weitere Zusicherung der entfernten Funktion war eine Gegenprobe
# ("die GEWITTER-Antwort derselben Fixture nennt CAPE"); sie bleibt
# eigenstaendig bewacht von
# ``test_ac2_gewitter_kommando_nennt_die_tragende_zutat`` weiter oben.


# ---------------------------------------------------------------------------
# Zusicherung des Helfers selbst (Adversary-Befund F001 zu Scheibe 2)
# ---------------------------------------------------------------------------

def test_hoechststufe_none_hat_keine_herkunft_auch_mit_gefuellten_traegern():
    """Given die Hoechststufe eines Aggregats ist ``NONE``, When Traeger
    mitgeliefert werden, Then ist das Ergebnis ``None`` -- "kein Gewitter" hat
    keine Herkunft.

    Wirkort ist hier die Funktion selbst: kein heutiger Aufrufer erzeugt zu
    einem ``NONE``-Punkt eine gefuellte Traegerliste, der Docstring sagt die
    Eigenschaft aber als Eigenschaft der FUNKTION zu. Der Helfer ist laut
    Spec D1 ausdruecklich fuer die Wiederverwendung gebaut (kuenftiger
    ``aggregate_stage()``-Anschluss) -- eine Zusicherung, die nur aus dem
    Verhalten der Aufrufer folgt, bricht genau dort.
    """
    assert union_of_max_carriers([(ThunderLevel.NONE, ["cape"])]) is None, (
        "Ein einzelner NONE-Punkt mit Traeger darf keine Herkunft nennen")
    assert union_of_max_carriers([
        (ThunderLevel.NONE, ["cape"]),
        (ThunderLevel.NONE, ["wettercode", "lightning"]),
    ]) is None, (
        "Auch mehrere NONE-Punkte mit Traegern nennen keine Herkunft")

    # Gegenprobe: sobald irgendein Punkt ueber NONE liegt, traegt NUR er bei --
    # unveraendertes Verhalten, nicht durch die neue Zusicherung mit-erschlagen.
    assert union_of_max_carriers([
        (ThunderLevel.NONE, ["cape"]),
        (ThunderLevel.LOW, ["wettercode"]),
    ]) == ["wettercode"], (
        "Liegt das Maximum ueber NONE, bleibt die Vereinigung der Traeger am "
        "Maximum unveraendert")
