"""TDD RED — Hagel im GLANCE-Kommando, in der HEUTE-Timeline und in der
Telegram-Metrikzeile (Issue #2205, AC-13 bis AC-16).

SPEC: docs/specs/modules/fix_2205_hagel_im_text_wettercode_bleibt.md

Zielverhalten: Wettercode 95/96/99 bleibt auf der hoechsten Gewitterstufe
("hoch"). Unterscheidbar werden die Codes ueber die BESTEHENDE Hagelaussage
(``metric_format.format_hail_note`` -> "Hagel: ja"): 96/99 tragen sie, 95 nicht.

Pruefort = Wirkort:
  * AC-13/14: ``TripCommandProcessor.process()`` -> ``confirmation_body`` fuer
    ``GLANCE`` (``_fmt_day_agg``) und ``### query: timeline_heute``
    (``_fmt_timeline``). Der Kommandopfad liest einen echt gespeicherten
    Wetter-Schnappschuss von der isolierten Datenwurzel und sendet nichts.
  * AC-15/16: die fertigen Telegram-Bubbles aus
    ``TripReportFormatter.format_email()`` -- geprueft wird genau die
    Kurzuebersichts-Gewitterzeile (heute ``TH hoch``, ``narrow._overview_line``), NICHT die
    Fusszeile derselben Bubble, die "Hagel: ja" schon heute traegt.

Positivkontrolle im selben Test: das ``GEWITTER``-Kommando zeigt fuer
dieselbe Fixture schon heute "Hagel: ja" (``_fmt_gewitter``) -- damit ist
belegt, dass der Hagelwert im Tagesaggregat ANKOMMT und nur GLANCE/Timeline
ihn ignorieren.

Fixture ohne Handwerte: Stufe und Hagel-Kennzeichen jedes Stundenpunkts
entstehen aus dem Wettercode ueber die ECHTEN Provider-Uebersetzungen
(``OpenMeteoProvider._parse_thunder_level`` / ``_parse_hail_flag``), die
Stufe laeuft danach durch die echte Fusion, das Aggregat durch
``WeatherMetricsService.compute_basis_metrics``.
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import save_trip  # noqa: E402
from app.metric_catalog import build_default_display_config  # noqa: E402
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
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from output.metric_format import format_hail_note  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402
from providers.openmeteo import OpenMeteoProvider  # noqa: E402
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage,
    TripCommandProcessor,
)
from services.weather_metrics import WeatherMetricsService  # noqa: E402
from services.weather_snapshot import WeatherSnapshotService  # noqa: E402

_LAT, _LON, _MODELL = 47.0, 12.0, "icon_d2"
_JETZT = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
_HEUTE = _JETZT.date()

#: Die bestehende Hagelaussage -- aus der EINEN Wortlautquelle, nicht getippt.
HAGEL = format_hail_note(True)
HAGEL_CODES = (96, 99)
OHNE_HAGEL_CODE = 95
KANAELE = ("telegram", "email")


# ---------------------------------------------------------------------------
# Fixture-Bausteine: Wettercode rein, echte Uebersetzung + Aggregation raus
# ---------------------------------------------------------------------------

_PROVIDER = OpenMeteoProvider()


def _dp(h: int, code: int, *, tag: date = _HEUTE) -> ForecastDataPoint:
    provider = _PROVIDER
    return ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, h, 0, tzinfo=timezone.utc),
        t2m_c=20.0, wind10m_kmh=8.0, gust_kmh=12.0, precip_1h_mm=0.5,
        cloud_total_pct=80, humidity_pct=70, wmo_code=code,
        thunder_level=provider._parse_thunder_level(code),
        hail_flag=provider._parse_hail_flag(code),
    )


def _segment(punkte: list[ForecastDataPoint], tag: date = _HEUTE,
             start_h: int = 12, end_h: int = 17) -> SegmentWeatherData:
    region = thunder_region_for(_LAT, _LON)
    _fuse_thunder_levels(
        punkte, cape_ladder_thresholds_jkg(_MODELL, region),
        lpi_thresholds_jkg(region),
    )
    reihe = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                          grid_res_km=1.0),
        data=punkte,
    )
    seg = TripSegment(
        segment_id=1,
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


def _frage_fuer(code: int):
    """Trip + Schnappschuss (Gewitter mit ``code`` 14-16 Uhr) speichern und
    eine Funktion liefern, die Kommandos ueber ``process()`` stellt."""
    user_id = f"hagelkommando-{uuid.uuid4().hex[:8]}"
    trip_id = f"hagel-kommando-{uuid.uuid4().hex[:8]}"
    trip_name = f"Hagel Kommando {uuid.uuid4().hex[:4]}"
    save_trip(Trip(id=trip_id, name=trip_name, stages=[
        Stage(id="S1", name="Heute", date=_HEUTE, waypoints=[
            Waypoint(id="W1", name="Start", lat=_LAT, lon=_LON,
                     elevation_m=1000),
        ]),
    ]), user_id)
    WeatherSnapshotService(user_id).save(
        trip_id, [_segment([_dp(h, code) for h in (14, 15, 16)])], _HEUTE,
    )

    def _stelle(kommando: str, *, kanal: str) -> str:
        ergebnis = TripCommandProcessor().process(InboundMessage(
            channel=kanal, trip_name=trip_name, body=kommando,
            sender="4917000000001", received_at=_JETZT, user_id=user_id,
        ))
        assert ergebnis.success, (
            f"Vorbedingung: {kommando!r} auf {kanal!r} muss antworten: "
            f"{ergebnis.confirmation_body!r}")
        return ergebnis.confirmation_body

    return _stelle


def _glance_abschnitte(antwort: str) -> list[str]:
    teile = [ln.split("⛈ Gewitter: ", 1)[1].strip()
             for ln in antwort.splitlines() if "⛈ Gewitter: " in ln]
    assert teile, f"Vorbedingung: GLANCE ohne Gewitterzeile: {antwort!r}"
    return teile


def _timeline_abschnitte(antwort: str) -> list[str]:
    teile = [ln.split("⛈ ", 1)[1].strip()
             for ln in antwort.splitlines() if "⛈ " in ln and "🌡" in ln]
    assert teile, f"Vorbedingung: Timeline ohne Gewitterspalte: {antwort!r}"
    return teile


def _hoch_abschnitte(abschnitte: list[str], wo: str) -> list[str]:
    """Nur die Abschnitte auf Stufe "hoch" -- und belegen, dass es sie gibt
    (sonst waere jede Hagel-Abwesenheit trivial)."""
    hoch = [a for a in abschnitte if a.split(" · ", 1)[0].strip() == "hoch"]
    assert hoch, (
        f"Vorbedingung: {wo} muss Gewitterstufe 'hoch' zeigen (Code 95/96/99 "
        f"bleibt HIGH), gefunden: {abschnitte!r}")
    return hoch


# ═══════════════ AC-13: GLANCE + Timeline zeigen Hagel bei 96/99 ═══════════════


@pytest.mark.parametrize("kommando", ("GLANCE", "### query: timeline_heute"))
@pytest.mark.parametrize("code", HAGEL_CODES)
def test_ac13_glance_und_timeline_nennen_hagel_bei_96_99(code, kommando):
    """AC-13 (je Kommando ein eigener Testfall, damit ein Fix in nur einem
    der beiden Formatierer den anderen rot laesst).

    GIVEN ein Trip, dessen heutiges Tagesaggregat Gewitterstufe hoch mit
          Wettercode 96 bzw. 99 traegt (``agg["hail_flag"]`` wahr).
    WHEN  GLANCE und die HEUTE-Timeline ueber ``TripCommandProcessor.process()``
          als Kommandoantwort (Telegram und E-Mail) gerendert werden.
    THEN  enthalten beide Antworttexte im Gewitter-Abschnitt der Stufe hoch
          die bestehende Hagelaussage aus ``format_hail_note``.

    Positivkontrolle: ``GEWITTER`` derselben Fixture nennt Hagel schon heute.
    RED heute: ``_fmt_day_agg``/``_fmt_timeline`` werten den Hagelwert nicht aus.
    """
    frage = _frage_fuer(code)
    for kanal in KANAELE:
        gewitter = frage("GEWITTER", kanal=kanal)
        assert HAGEL in gewitter, (
            f"Positivkontrolle: GEWITTER-Antwort muss fuer Code {code} schon "
            f"heute {HAGEL!r} nennen (Hagelwert kommt im Aggregat an): "
            f"{gewitter!r}")

        antwort = frage(kommando, kanal=kanal)
        if kommando == "GLANCE":
            abschnitte = _hoch_abschnitte(_glance_abschnitte(antwort), "GLANCE")
        else:
            abschnitte = _hoch_abschnitte(_timeline_abschnitte(antwort), "Timeline")
        assert all("Hagel" in a for a in abschnitte), (
            f"AC-13: {kommando!r} ({kanal}) muss bei Code {code} neben 'hoch' "
            f"die Hagelaussage {HAGEL!r} tragen, Abschnitte: {abschnitte!r}")


# ═══════════════ AC-14: GLANCE + Timeline ohne Hagel bei 95 ═══════════════════


def test_ac14_glance_und_timeline_ohne_hagel_bei_95():
    """AC-14.

    GIVEN dasselbe Tagesaggregat mit ausschliesslich Wettercode 95
          (``agg["hail_flag"]`` nicht wahr).
    WHEN  GLANCE und HEUTE-Timeline gerendert werden (Telegram und E-Mail).
    THEN  zeigen beide die Stufe hoch, aber keine Hagelaussage.
    """
    frage = _frage_fuer(OHNE_HAGEL_CODE)
    for kanal in KANAELE:
        glance = _hoch_abschnitte(
            _glance_abschnitte(frage("GLANCE", kanal=kanal)), "GLANCE")
        timeline = _hoch_abschnitte(
            _timeline_abschnitte(frage("### query: timeline_heute", kanal=kanal)),
            "Timeline")
        gesamt = frage("GLANCE", kanal=kanal) + frage(
            "### query: timeline_heute", kanal=kanal)
        assert "Hagel" not in gesamt, (
            f"AC-14: bei Code 95 darf weder GLANCE noch Timeline ({kanal}) "
            f"Hagel nennen. GLANCE {glance!r}, Timeline {timeline!r}")


# ═══════════ AC-15/16: Telegram-Kurzuebersicht (Metrikzeile ⚡) ═══════════════


def _telegram_bubbles(code: int) -> list[str]:
    """Das echte Trip-Briefing einer Etappe mit Gewitter ``code`` 14-15 Uhr
    (uebrige Stunden Code 3, bedeckt) -- Telegram-Bubbles."""
    tag = date(2026, 8, 21)
    punkte = [_dp(h, code if h in (14, 15) else 3, tag=tag) for h in range(6, 18)]
    bericht = TripReportFormatter().format_email(
        [_segment(punkte, tag=tag, start_h=8, end_h=16)], "Hagel-Trip", "morning",
        display_config=build_default_display_config(), tz=ZoneInfo("UTC"),
        stage_name="Etappe A",
    )
    assert bericht.telegram_bubbles, "Vorbedingung: keine Telegram-Bubbles"
    return bericht.telegram_bubbles


def _metrikzeile_und_fusszeile(bubbles: list[str]) -> tuple[str, str]:
    """Die Kurzuebersichts-Gewitterzeile (``_overview_line``) und die
    Fusszeile (``_tg_day_footer``) -- als VERSCHIEDENE Zeilen belegt."""
    for bubble in bubbles:
        zeilen = bubble.splitlines()
        if "Kurzübersicht" not in [z.strip() for z in zeilen]:
            continue
        start = [z.strip() for z in zeilen].index("Kurzübersicht") + 1
        block = []
        for z in zeilen[start:]:
            if not z.strip():
                break
            block.append(z.strip())
        # Die Gewitter-Metrikzeile ist "<Kuerzel> <Stufenwort>[...]" -- das
        # Kuerzel ist Katalog-/Anzeigesache, gefunden wird sie am Stufenwort.
        metrik = [z for z in block
                  if " " in z and z.split(" ", 1)[1].startswith("hoch")]
        fuss = [z.strip() for z in zeilen[start + len(block):]
                if z.strip().startswith("⚡ ")]
        assert len(metrik) == 1, (
            f"Vorbedingung: genau EINE Gewitter-Metrikzeile in der Kurzuebersicht "
            f"erwartet, gefunden {metrik!r} in {block!r}")
        assert fuss, f"Vorbedingung: Fusszeile fehlt in Bubble {bubble!r}"
        return metrik[0], fuss[0]
    raise AssertionError(f"Vorbedingung: keine Kurzuebersicht in {bubbles!r}")


@pytest.mark.parametrize("code", HAGEL_CODES)
def test_ac15_telegram_metrikzeile_kennzeichnet_hagel_bei_96_99(code):
    """AC-15.

    GIVEN eine Etappe mit Gewitterstufe hoch, deren Spitzenstunden Code 96
          bzw. 99 tragen.
    WHEN  die Telegram-Bubbles des Trip-Briefings gerendert werden.
    THEN  enthaelt die Kurzuebersichts-Zeile ``⚡ hoch`` selbst eine
          Hagelkennzeichnung -- nicht nur die Fusszeile darunter.

    Positivkontrolle: die Fusszeile derselben Bubble nennt Hagel schon heute.
    RED heute: ``_overview_line`` ignoriert den Hagelwert.
    """
    metrik, fuss = _metrikzeile_und_fusszeile(_telegram_bubbles(code))
    assert "hoch" in metrik, f"Vorbedingung: Metrikzeile nicht 'hoch': {metrik!r}"
    assert HAGEL in fuss, (
        f"Positivkontrolle: Fusszeile muss bei Code {code} schon heute "
        f"{HAGEL!r} tragen: {fuss!r}")
    assert "Hagel" in metrik, (
        f"AC-15: Telegram-Metrikzeile muss bei Code {code} eine "
        f"Hagelkennzeichnung tragen, ist aber {metrik!r}")


def test_ac16_telegram_metrikzeile_ohne_hagel_bei_95():
    """AC-16.

    GIVEN dieselbe Etappe mit ausschliesslich Code 95 in den Spitzenstunden.
    WHEN  die Telegram-Bubbles gerendert werden.
    THEN  zeigt die Kurzuebersichts-Zeile ``⚡ hoch`` ohne Hagelkennzeichnung
          (und auch die Fusszeile nennt keinen Hagel).
    """
    metrik, fuss = _metrikzeile_und_fusszeile(_telegram_bubbles(OHNE_HAGEL_CODE))
    assert "hoch" in metrik, f"Vorbedingung: Metrikzeile nicht 'hoch': {metrik!r}"
    assert "Hagel" not in metrik and "Hagel" not in fuss, (
        f"AC-16: bei Code 95 keine Hagelkennzeichnung. Metrikzeile {metrik!r}, "
        f"Fusszeile {fuss!r}")


def test_metrikzeile_ohne_gewitterstufe_nennt_keinen_hagel():
    """AC-15/16-Waechter (F003): der Hagel-Zusatz haengt nur an einer
    Gewitterstufe, nie an "kein".

    GIVEN eine Etappe, deren Tagesfenster-Stunden Gewitterstufe NONE tragen,
          aber ein Hagel-Kennzeichen ``True`` (ueber den WMO-Weg heute nicht
          erreichbar: 96/99 ergeben immer HIGH und die Fusion stuft nie herab
          -- der Waechter sichert die Kopplung fuer kuenftige Hagelquellen).
    WHEN  die Telegram-Bubbles des Trip-Briefings gerendert werden.
    THEN  lautet die Kurzuebersichts-Gewitterzeile auf "kein" ohne Hagel --
          kein widerspruechliches "kein · Hagel: ja".
    """
    tag = date(2026, 8, 21)
    punkte = [_dp(h, 3, tag=tag) for h in range(6, 18)]
    for p in punkte:
        p.hail_flag = True
    bericht = TripReportFormatter().format_email(
        [_segment(punkte, tag=tag, start_h=8, end_h=16)], "Hagel-Trip", "morning",
        display_config=build_default_display_config(), tz=ZoneInfo("UTC"),
        stage_name="Etappe A",
    )
    kurz = [b for b in bericht.telegram_bubbles
            if "Kurzübersicht" in [z.strip() for z in b.splitlines()]]
    assert kurz, f"Vorbedingung: keine Kurzuebersicht in {bericht.telegram_bubbles!r}"
    zeilen = [z.strip() for z in kurz[0].splitlines()]
    block = zeilen[zeilen.index("Kurzübersicht") + 1:]
    block = block[:block.index("")] if "" in block else block
    metrik = [z for z in block if " " in z and z.split(" ", 1)[1].startswith("kein")]
    assert len(metrik) == 1, (
        f"Vorbedingung: genau EINE Gewitter-Metrikzeile 'kein' erwartet, {block!r}")
    assert "Hagel" not in metrik[0], (
        f"F003: ohne Gewitterstufe kein Hagel-Zusatz in der Metrikzeile, "
        f"ist {metrik[0]!r}")
