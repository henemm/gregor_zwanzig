"""TDD RED — Gewitter-Herkunft ist kanalabhaengig (Issue #2184, AC-8).

SPEC: docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md
      (AC-8, Implementation Details 5, Mutation 3)

Zielverhalten: Die PO-Abwahl "SMS und Premium-SMS bleiben ohne Herkunft"
(``feat_1680_s5a_…md`` AC-12, ``feat_1680_s5b_…md`` AC-9) war bisher nur
STRUKTURELL gesichert — ``InboundMessage`` hatte genau zwei Erzeuger, also
konnte kein Kommandopfad je mit ``channel="sms"``/``"premium_sms"`` in die drei
Formatierer laufen. Scheibe S4 macht Premium-SMS zum dritten Erzeuger; damit
faellt die Sicherung weg und muss durch einen echten Guard ersetzt werden.

Geprueft werden ALLE DREI Formatierer in BEIDE Richtungen:

  * ``_fmt_day_agg``  (GLANCE-Tageszeile)    <- Kommando ``GLANCE``
  * ``_fmt_gewitter`` (GEWITTER-Antwort)     <- Kommando ``GEWITTER``
  * ``_fmt_timeline`` (Wegpunkt-Timeline)    <- ``### query: timeline_heute``

Ein Guard in nur einem der drei bliebe sonst unbemerkt (Spec-Mutation 3).

RED heute: keiner der drei Formatierer kennt den Anfrageweg — die Herkunft
("CAPE", "Blitzpotenzial") erscheint auf JEDEM Kanal. Die vier
``test_ac8_email_und_telegram_*``-Tests sind die Positivkontrolle und heute
GRUEN: ohne sie waere die Abwesenheit der Herkunft auf SMS auch dann erfuellt,
wenn sie ueberall verschwaende.

Pruefort = Wirkort: jeder Test laeuft bis zu ``CommandResult.
confirmation_body`` aus ``TripCommandProcessor.process()`` — dem Text, den der
Nutzer bekommt. Kein Formatierer wird direkt gerufen; sonst bewachte der Test
die Funktion statt den Draht vom Kanal bis zum Text.

Kein Mock-Theater: Stufen und Traegerlisten entstehen ueber die ECHTE Fusion
(``thunder_enrichment._fuse_thunder_levels`` mit den Leitern aus
``app.model_registry``) und die ECHTE Aggregation
(``WeatherMetricsService.compute_basis_metrics``); der Kommandopfad liest einen
echt gespeicherten Wetter-Schnappschuss von der isolierten Datenwurzel.
Vorbild und Herkunft der Fixture-Bausteine: ``test_thunder_origin_trip.py``.
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import save_trip  # noqa: E402
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
from providers.thunder_enrichment import _fuse_thunder_levels  # noqa: E402
from providers.thunder_routing import thunder_region_for  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage,
    TripCommandProcessor,
)
from services.weather_metrics import WeatherMetricsService  # noqa: E402
from services.weather_snapshot import WeatherSnapshotService  # noqa: E402

#: Die vier Zutat-Beschriftungen aus ``metric_format.THUNDER_SIGNAL_LABEL_DE``.
#: Keine davon darf in einer SMS-/Premium-SMS-Antwort auftauchen.
ALLE_ZUTATEN = ("Wettercode", "Blitzdichte", "CAPE", "Blitzpotenzial")

#: Kanaele OHNE Herkunft (PO-Abwahl) und MIT Herkunft (unveraendert).
KANAELE_OHNE_HERKUNFT = ("sms", "premium_sms")
KANAELE_MIT_HERKUNFT = ("email", "telegram")

_LAT, _LON, _MODELL = 47.0, 12.0, "icon_d2"   # Gebiet DE_ALPEN, Europe/Vienna
_JETZT = datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc)
_HEUTE = _JETZT.date()

#: Die drei Formatierer, jeweils ueber das Kommando, das sie erreicht.
FORMATIERER = {
    "glance": "GLANCE",
    "gewitter": "GEWITTER",
    "timeline": "### query: timeline_heute",
}


# ---------------------------------------------------------------------------
# Fixture-Bausteine: Rohwerte rein, echte Rechnung raus
# ---------------------------------------------------------------------------

def _dp(h: int, *, tag: date = _HEUTE, cape=None, cin=None,
        lpi=None) -> ForecastDataPoint:
    """Ein Stundenpunkt mit ROHWERTEN — Stufe und Traeger rechnet die Fusion."""
    return ForecastDataPoint(
        ts=datetime(tag.year, tag.month, tag.day, h, 0, tzinfo=timezone.utc),
        t2m_c=20.0, wind10m_kmh=8.0, gust_kmh=12.0, precip_1h_mm=0.0,
        cloud_total_pct=40, humidity_pct=50,
        cape_jkg=cape, convective_inhibition_jkg=cin,
        lightning_potential_lpi_jkg=lpi,
    )


def _segment(punkte: list[ForecastDataPoint]) -> SegmentWeatherData:
    """Segment, dessen Aggregat die ECHTE Engine rechnet — nicht von Hand."""
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
        start_time=datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 20, 17, 0, tzinfo=timezone.utc),
        duration_hours=5.0, distance_km=10.0, ascent_m=500.0, descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=reihe,
        aggregated=WeatherMetricsService().compute_basis_metrics(reihe, tz=None),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


@pytest.fixture
def frage():
    """Speichert Trip + Schnappschuss und stellt die Kommandofrage ueber den
    ECHTEN ``TripCommandProcessor.process()`` — derselbe Weg, den eine
    eingehende Nachricht nimmt, nur mit wechselndem ``channel``.

    Die Wetterlage traegt garantiert eine Herkunft: CAPE UND Blitzpotenzial
    erreichen dieselbe Hoechststufe (Spec-Mutation 3 verlangt eine Fixture mit
    sicherem Gewittersignal, sonst ist die Abwesenheit der Herkunft trivial).
    """
    user_id = f"herkunftkanal-{uuid.uuid4().hex[:8]}"
    trip_id = f"herkunft-kanal-{uuid.uuid4().hex[:8]}"
    trip_name = f"Herkunft Kanal {uuid.uuid4().hex[:4]}"

    save_trip(Trip(id=trip_id, name=trip_name, stages=[
        Stage(id="S1", name="Heute", date=_HEUTE, waypoints=[
            Waypoint(id="W1", name="Start", lat=_LAT, lon=_LON,
                     elevation_m=1000),
        ]),
    ]), user_id)
    WeatherSnapshotService(user_id).save(
        trip_id,
        [_segment([_dp(h, cape=1500.0, cin=5.0, lpi=60.0) for h in (14, 15, 16)])],
        _HEUTE,
    )

    def _stelle(kommando: str, *, kanal: str) -> str:
        ergebnis = TripCommandProcessor().process(InboundMessage(
            channel=kanal, trip_name=trip_name, body=kommando,
            sender="4917000000001", received_at=_JETZT, user_id=user_id,
        ))
        assert ergebnis.success, (
            f"Vorbedingung: das Kommando {kommando!r} muss auf Kanal "
            f"{kanal!r} antworten, nicht scheitern: "
            f"{ergebnis.confirmation_body!r}")
        return ergebnis.confirmation_body

    return _stelle


# ---------------------------------------------------------------------------
# Aus der Antwort die Gewitter-Abschnitte herausloesen — je Formatierer
# ---------------------------------------------------------------------------

def _abschnitte(antwort: str, formatierer: str) -> list[str]:
    """Die Gewitter-Abschnitte einer Antwort, in Reihenfolge des Textes.

    GLANCE:   "heute (20.08): ... ⛈ Gewitter: hoch · CAPE" -> "hoch · CAPE"
    GEWITTER: "⛈ Gewitter heute (20.08): hoch · CAPE"      -> "hoch · CAPE"
    Timeline: "   🌡 … ⛈ hoch · CAPE" (je Wegpunkt)         -> "hoch · CAPE"
    """
    if formatierer == "glance":
        teile = [ln.split("⛈ Gewitter: ", 1)[1].strip()
                 for ln in antwort.splitlines() if "⛈ Gewitter: " in ln]
    elif formatierer == "gewitter":
        teile = [antwort.split("): ", 1)[1].strip()] if "): " in antwort else []
    else:
        teile = [ln.split("⛈ ", 1)[1].strip()
                 for ln in antwort.splitlines() if "⛈ " in ln and "🌡" in ln]
    assert teile, (
        f"Vorbedingung: die {formatierer!r}-Antwort muss mindestens einen "
        f"Gewitter-Abschnitt enthalten, gefunden wurde keiner in: {antwort!r}")
    return teile


def _genannte_zutaten(abschnitte: list[str]) -> set[str]:
    return {z for a in abschnitte for z in ALLE_ZUTATEN if z in a}


def _stufenwoerter(abschnitte: list[str]) -> list[str]:
    """Das Stufenwort je Abschnitt — alles vor dem ersten Zusatz-Trenner."""
    return [a.split(" · ", 1)[0].strip() for a in abschnitte]


# ═════════════════ AC-8: SMS und Premium-SMS ohne Herkunft ═════════════════


@pytest.mark.parametrize("formatierer", sorted(FORMATIERER))
@pytest.mark.parametrize("kanal", KANAELE_OHNE_HERKUNFT)
def test_ac8_sms_und_premium_sms_zeigen_keine_gewitter_herkunft(
    frage, formatierer, kanal,
):
    """AC-8 (Richtung "ohne").

    GIVEN eine Wetterlage, deren Hoechststufe nachweislich von CAPE UND
          Blitzpotenzial getragen wird (dieselbe Fixture fuer alle Kanaele).
    WHEN  dieselbe Frage einmal ueber ``sms`` bzw. ``premium_sms`` gestellt
          wird — durch ``TripCommandProcessor.process()``, also den echten
          Draht vom Anfrageweg bis zum Antworttext.
    THEN  nennt die Antwort KEINE der vier Zutat-Beschriftungen, waehrend die
          Gewitterstufe selbst unveraendert sichtbar bleibt.

    Gegenprobe IM SELBEN Test (Pflicht): dieselbe Fixture ueber ``email``
    nennt die Zutaten sehr wohl, und die Stufenwoerter beider Antworten sind
    identisch. Ohne diesen Gegenpol waere das AC auch dann gruen, wenn die
    Herkunft ueberall verschwaende oder die Antwort gar keine Stufe mehr
    zeigte.

    RED heute: der Formatierer kennt den Anfrageweg nicht, die Herkunft
    erscheint auf jedem Kanal. Ein Guard in nur einem der drei Formatierer
    laesst die anderen beiden Parametrisierungen rot (Spec-Mutation 3).
    """
    kommando = FORMATIERER[formatierer]

    ohne = _abschnitte(frage(kommando, kanal=kanal), formatierer)
    mit = _abschnitte(frage(kommando, kanal="email"), formatierer)

    assert _genannte_zutaten(mit), (
        f"Gegenprobe gescheitert: die E-Mail-Antwort DERSELBEN Fixture muss "
        f"die Herkunft nennen, sonst beweist ihre Abwesenheit auf {kanal!r} "
        f"nichts. {formatierer!r}-Abschnitte: {mit!r}")

    assert _genannte_zutaten(ohne) == set(), (
        f"AC-8: die {formatierer!r}-Antwort auf Kanal {kanal!r} darf KEINE "
        f"Gewitter-Herkunft nennen (PO-Abwahl), gefunden wurden "
        f"{sorted(_genannte_zutaten(ohne))} in {ohne!r}")

    assert _stufenwoerter(ohne) == _stufenwoerter(mit), (
        f"AC-8: nur die Herkunft faellt weg — die Gewitterstufe bleibt auf "
        f"{kanal!r} zeichengleich zur E-Mail. {formatierer!r}: "
        f"{_stufenwoerter(ohne)!r} vs. {_stufenwoerter(mit)!r}")


# ═══════ AC-8 (Gegenrichtung): E-Mail und Telegram behalten die Herkunft ════
# Heute GRUEN — Positivkontrolle und Regressionswaechter zugleich: ein Guard,
# der ueber das Ziel hinausschiesst und die Herkunft ueberall unterdrueckt,
# faellt hier auf.


@pytest.mark.parametrize("formatierer", sorted(FORMATIERER))
@pytest.mark.parametrize("kanal", KANAELE_MIT_HERKUNFT)
def test_ac8_email_und_telegram_behalten_die_gewitter_herkunft(
    frage, formatierer, kanal,
):
    """AC-8 (Richtung "mit") — Regressionswaechter, heute GRUEN.

    GIVEN dieselbe Wetterlage mit gesichertem Gewittersignal.
    WHEN  die Frage ueber ``email`` bzw. ``telegram`` gestellt wird.
    THEN  nennt die Antwort die tragenden Zutaten unveraendert — CAPE und
          Blitzpotenzial, beide.

    Wert nach dem Fix: faengt einen Guard, der die Kanalbedingung verdreht
    oder weglaesst und damit die Herkunft auf ALLEN Kanaelen unterdrueckt.
    """
    abschnitte = _abschnitte(frage(FORMATIERER[formatierer], kanal=kanal),
                             formatierer)

    assert _genannte_zutaten(abschnitte) == {"CAPE", "Blitzpotenzial"}, (
        f"AC-8: auf {kanal!r} muss die {formatierer!r}-Antwort BEIDE tragenden "
        f"Zutaten unveraendert nennen, gefunden wurden "
        f"{sorted(_genannte_zutaten(abschnitte))} in {abschnitte!r}")
