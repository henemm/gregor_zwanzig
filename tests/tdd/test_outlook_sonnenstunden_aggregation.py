"""TDD RED — #2098 Befund A: Sonnenstunden fallen bei der Etappen-Aggregation weg.

SPEC: docs/specs/modules/fix_2098_ausblick_acc_und_sonnenstunden.md (AC-1..AC-4)
KONTEXT: docs/context/fix-2098-ausblick-acc-und-sonnenstunden.md

Fehlerbild aus Nutzersicht: die Spalte "Sonnenstunden" im 3-Tages-Ausblick der
Trip-Briefing-Mail zeigt in JEDER Zeile "–", obwohl der Wert je Segment
vorhanden ist. Ursache: ``aggregate_stage()`` (weather_metrics.py:1384) baut
das Etappen-Aggregat ausschliesslich aus Feldern, die in der
``aggregation_config`` des ersten Segment-Summarys eine Regel tragen --
``sunny_hours`` hat dort keine (weather_metrics.py:555-572).

🔴 Zwei Fallen, die falsches Gruen erzeugt haetten:

1. **Einzelsegment.** ``CompactSummaryFormatter._aggregate()``
   (compact_summary.py:262-268) ruft ``aggregate_stage()`` nur bei MEHR ALS
   EINEM Segment; bei einem Segment reicht es das Aggregat unbeschaedigt
   durch. Ein Einzelsegment-Fixture zeigt den Wert also auch heute schon.
   Jeder Nachweis hier laeuft deshalb ueber eine MEHRSEGMENT-Etappe (AC-3
   sichert genau diese Unterscheidung ab).

2. **Eigene ``aggregation_config`` im Test.** Wer die Regeln im Test selbst
   hinschreibt (so wie ``tests/helpers/trip_outlook_selection._summary()``),
   prueft seine eigene Kopie statt des Erzeugers. Die Segment-Summaries
   entstehen hier deshalb aus dem ECHTEN Erzeuger
   ``WeatherMetricsService.compute_basis_metrics()`` / ``compute_extended_metrics()``
   -- nur der Zahlenwert ``sunny_hours`` wird ueber ``dataclasses.replace``
   auf unterscheidbare Werte gesetzt, damit die Aggregationsregel (Summe vs.
   Maximum vs. erstes Segment) ueberhaupt unterscheidbar ist.

Kern-Schicht, deterministisch: keine Mocks/``patch()``/``MagicMock``, kein
Netz, kein Dateiinhalt-Check. Echte ``ForecastDataPoint``-/
``SegmentWeatherSummary``-/``SegmentWeatherData``-Objekte, echter Renderpfad.
"""
from __future__ import annotations

import dataclasses
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen -- sonst
# pruefte ein Worktree-Lauf die unveraenderte Hauptrepo-Kopie.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

TZ = ZoneInfo("Europe/Berlin")

# Drei unterscheidbare Segmentwerte: die Summe (7.0) ist von jeder anderen
# denkbaren Regel verschieden -- Maximum waere 3.5, erstes Segment 2.0,
# Mittelwert 2.33, Minimum 1.5. Bei zwei gleichen Werten koennte ein Treffer
# Zufall sein.
_SONNE_JE_SEGMENT = (2.0, 3.5, 1.5)
_SONNE_SUMME = 7.0

# Ausblick-Auswahl im Neuformat (#1848 A2: reine Kennungen). "sunshine" ist
# die Kennung, deren Spalte den Fehler zeigt; "precipitation" steht daneben,
# damit ein Spaltenversatz sichtbar wuerde.
_AUSWAHL = ["precipitation", "sunshine"]


# ---------------------------------------------------------------------------
# Echte Domaenen-Objekte
# ---------------------------------------------------------------------------

def _punkte(tag: int = 12):
    from app.models import ForecastDataPoint, ThunderLevel

    return [
        ForecastDataPoint(
            ts=datetime(2026, 7, tag, stunde, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + stunde * 0.2, wind10m_kmh=12.0, wind_direction_deg=270,
            gust_kmh=25.0, precip_1h_mm=0.5, pop_pct=30, cloud_total_pct=40,
            thunder_level=ThunderLevel.NONE, visibility_m=15000.0,
            dni_wm2=400.0, humidity_pct=55,
        )
        for stunde in range(8, 14)
    ]


def _segment(segment_id: int, sunny_hours: float):
    """Ein echtes ``SegmentWeatherData`` -- Aggregat vom ECHTEN Erzeuger.

    ``compute_basis_metrics()``/``compute_extended_metrics()`` liefern die
    ``aggregation_config``, um die es in dieser Spec geht. Nur ``sunny_hours``
    wird auf einen unterscheidbaren Wert gesetzt (der Erzeuger rechnet aus
    ``dni_wm2`` fuer alle drei Segmente denselben Wert aus, damit waere Summe
    von Maximum nicht unterscheidbar).
    """
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, TripSegment,
    )
    from services.weather_metrics import WeatherMetricsService

    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=46.65, lon=12.85, elevation_m=1400.0),
        end_point=GPXPoint(lat=46.70, lon=12.95, elevation_m=2100.0),
        start_time=datetime(2026, 7, 12, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 12, 13, 0, tzinfo=timezone.utc),
        duration_hours=5.0, distance_km=10.0, ascent_m=700.0, descent_m=120.0,
    )
    zeitreihe = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                          grid_res_km=2.2),
        data=_punkte(),
    )
    dienst = WeatherMetricsService()
    aggregat = dienst.compute_extended_metrics(
        zeitreihe, dienst.compute_basis_metrics(zeitreihe, tz=TZ),
    )
    assert aggregat.sunny_hours is not None, (
        "Vorbedingung: der Erzeuger muss auf SEGMENT-Ebene ueberhaupt "
        "Sonnenstunden liefern -- sonst prueft dieser Test die falsche Stufe."
    )
    return SegmentWeatherData(
        segment=segment, timeseries=zeitreihe,
        aggregated=dataclasses.replace(aggregat, sunny_hours=sunny_hours),
        fetched_at=datetime(2026, 7, 12, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _mehrsegment_etappe():
    """Drei Segmente einer Etappe mit unterscheidbaren Sonnenstunden."""
    return [_segment(i + 1, wert) for i, wert in enumerate(_SONNE_JE_SEGMENT)]


def _ausblick_zeile(summary):
    from output.renderers.email.outlook import build_outlook_row

    return build_outlook_row(summary, _punkte(), "Mo", TZ, metrics=_AUSWAHL)


def _spalten_und_zellen(summary) -> tuple[list[str], list[str]]:
    """Kopfzeilen-Beschriftungen und Zellentexte der gerenderten Tabelle.

    Der konfigurierbare Zweig (``metrics`` gesetzt) ist der Zweig, ueber den
    der Trip seit #1848 A3 praktisch immer laeuft (AC-14).
    """
    import re

    from output.renderers.email.outlook import render_outlook_table

    html = render_outlook_table([_ausblick_zeile(summary)], show_acc=True,
                                metrics=_AUSWAHL)
    kopf = [re.sub(r"<[^>]+>", "", t).strip()
            for t in re.findall(r"<th[^>]*>(.*?)</th>", html, re.DOTALL)]
    zellen = [re.sub(r"<[^>]+>", "", t).strip()
              for t in re.findall(r"<td[^>]*>(.*?)</td>", html, re.DOTALL)]
    return kopf, zellen


def _sonnen_zelle(summary) -> str:
    kopf, zellen = _spalten_und_zellen(summary)
    assert "Sonnenstunden" in kopf, (
        f"Vorbedingung: die Sonnenstunden-Spalte muss ueberhaupt im Kopf "
        f"stehen, sonst prueft der Test nichts. Kopf: {kopf!r}"
    )
    assert len(zellen) == len(kopf), (
        f"Kopf und Datenzeile laufen auseinander: {kopf!r} vs. {zellen!r}"
    )
    return zellen[kopf.index("Sonnenstunden")]


# ---------------------------------------------------------------------------
# AC-1 — Mehrsegment-Etappe zeigt einen Zahlenwert statt "–"
# ---------------------------------------------------------------------------

def test_ac1_mehrsegment_etappe_zeigt_sonnenstunden_statt_strich():
    """AC-1: Given eine Trip-Etappe mit mehr als einem Segment und
    unterschiedlichen Sonnenstunden je Segment / When das Trip-Briefing
    gerendert wird / Then zeigt die Sonnenstunden-Spalte im 3-Tages-Ausblick
    einen konkreten Zahlenwert statt "–".

    RED-Grund: ``aggregate_stage()`` iteriert nur ueber Felder mit
    Aggregationsregel; ``sunny_hours`` hat keine und faellt auf den
    Dataclass-Default ``None`` -- die Zelle zeigt "–".
    """
    from services.weather_metrics import aggregate_stage

    segmente = _mehrsegment_etappe()
    assert len(segmente) > 1, (
        "Vorbedingung: der Nachweis MUSS ueber eine Mehrsegment-Etappe "
        "laufen -- bei einem Segment wird gar nicht aggregiert (AC-3)."
    )

    zelle = _sonnen_zelle(aggregate_stage(segmente))

    assert zelle != "–", (
        "Die Sonnenstunden-Spalte des 3-Tages-Ausblicks zeigt weiterhin "
        f"{zelle!r} -- der Segmentwert geht in aggregate_stage() verloren "
        "(#2098 Befund A)."
    )


# ---------------------------------------------------------------------------
# AC-2 — der Wert ist die SUMME der Segmentwerte, nicht irgendeine Zahl
# ---------------------------------------------------------------------------

def test_ac2_sonnenstunden_sind_die_summe_der_segmentwerte():
    """AC-2: Given dieselbe Mehrsegment-Etappe / When die Sonnenstunden-Spalte
    geprueft wird / Then entspricht der angezeigte Wert der SUMME der
    Segment-Sonnenstunden (Katalog-Definition ``summary_fields={"sum":
    "sunny_hours"}``) und nicht einem Platzhalter oder dem Wert nur eines
    Segments.

    Die drei Segmentwerte 2.0/3.5/1.5 sind so gewaehlt, dass jede andere
    denkbare Regel einen anderen Wert ergaebe (Maximum 3.5, erstes Segment
    2.0, Mittelwert 2.3, Minimum 1.5) -- ein "irgendeine Zahl"-Test waere
    gegen die falsche Regel blind.
    """
    from services.weather_metrics import aggregate_stage

    etappe = aggregate_stage(_mehrsegment_etappe())

    assert etappe.sunny_hours == _SONNE_SUMME, (
        f"Etappen-Aggregat traegt {etappe.sunny_hours!r} statt der Summe "
        f"{_SONNE_SUMME} aus {_SONNE_JE_SEGMENT} (Maximum waere "
        f"{max(_SONNE_JE_SEGMENT)}, erstes Segment {_SONNE_JE_SEGMENT[0]})."
    )
    assert _sonnen_zelle(etappe) == f"{_SONNE_SUMME:.1f} h", (
        f"Die gerenderte Zelle zeigt {_sonnen_zelle(etappe)!r} statt "
        f"{_SONNE_SUMME:.1f} h -- die Summe erreicht die Mail nicht."
    )


# ---------------------------------------------------------------------------
# AC-3 — Einzelsegment war nie betroffen (und taugt deshalb nicht als Beleg)
# ---------------------------------------------------------------------------

def test_ac3_einzelsegment_unveraendert_mehrsegment_erst_nach_dem_fix():
    """AC-3: Given eine Trip-Etappe mit genau einem Segment / When das
    Briefing gerendert wird / Then bleibt die Sonnenstunden-Anzeige
    unveraendert -- dieser Pfad war nie betroffen, weil
    ``CompactSummaryFormatter._aggregate()`` bei einem Segment gar nicht
    aggregiert (compact_summary.py:262-268).

    Positivkontrolle statt Ausbleiben-Test: Teil 1 (Einzelsegment) ist die
    Kontrolle -- sie zeigt, dass Fixture und Wertepfad tragen und der Wert
    ohne Aggregationsschritt ankommt. Teil 2 (drei Segmente, dieselbe
    Etappe) ist die eigentliche Behauptung und heute rot. Ohne Teil 1 waere
    Teil 2 auch dann "erklaerbar", wenn das Fixture gar keine Sonnenstunden
    truege; ohne Teil 2 waere der Test von Anfang an gruen und bewachte
    nichts.
    """
    from output.renderers.compact_summary import CompactSummaryFormatter

    einzeln = CompactSummaryFormatter._aggregate([_segment(1, _SONNE_JE_SEGMENT[0])])
    assert einzeln is not None and einzeln.sunny_hours == _SONNE_JE_SEGMENT[0], (
        "Kontrolle gescheitert: schon der Einzelsegment-Pfad liefert keine "
        f"Sonnenstunden ({einzeln.sunny_hours if einzeln else None!r}) -- dann "
        "misst dieser Test nicht den Aggregationsfehler, sondern ein kaputtes "
        "Fixture."
    )

    mehrere = CompactSummaryFormatter._aggregate(_mehrsegment_etappe())
    assert mehrere is not None and mehrere.sunny_hours == _SONNE_SUMME, (
        f"Einzelsegment liefert {einzeln.sunny_hours!r}, dieselbe Etappe auf "
        f"drei Segmente verteilt aber {mehrere.sunny_hours if mehrere else None!r} "
        f"statt {_SONNE_SUMME} -- genau dieser Unterschied ist der Fehler "
        "(#2098 Befund A). Ein Einzelsegment-Test allein waere falsch gruen."
    )


# ---------------------------------------------------------------------------
# AC-4 — Invariante: keine WEITERE Metrik ohne Aggregationsregel
# ---------------------------------------------------------------------------

def test_ac4_jede_katalog_metrik_mit_summary_field_hat_eine_aggregationsregel():
    """AC-4: Given den vollstaendigen Metrik-Katalog mit ``summary_fields`` /
    When alle Zielfelder gegen die ``aggregation_config`` des echten
    Erzeugers abgeglichen werden / Then traegt jedes Zielfeld eine
    Aggregationsregel -- ``sunny_hours`` ist die einzige heutige Luecke und
    bleibt nach der Behebung die einzige Aenderung an der Konfiguration.

    Geprueft wird die Vereinigung beider Erzeugerstellen: ``aggregation_config``
    aus ``compute_basis_metrics()`` (weather_metrics.py:555-572) und der
    Extended-Merge in ``compute_extended_metrics()`` (:1032-1062), der jene
    Basis-Regeln uebernimmt. Ein Zielfeld ohne Regel faellt bei jeder
    Mehrsegment-Etappe still auf ``None`` -- dieselbe Fehlerklasse wie
    Befund A, nur an einer anderen Groesse.
    """
    from app.metric_catalog import get_all_metrics
    from app.models import ForecastMeta, NormalizedTimeseries, Provider
    from services.weather_metrics import WeatherMetricsService

    zeitreihe = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                          grid_res_km=2.2),
        data=_punkte(),
    )
    dienst = WeatherMetricsService()
    basis = dienst.compute_basis_metrics(zeitreihe, tz=TZ)
    regeln = dict(dienst.compute_extended_metrics(zeitreihe, basis).aggregation_config)

    ohne_regel = [
        (metrik.id, auswertung, feld)
        for metrik in get_all_metrics()
        for auswertung, feld in (metrik.summary_fields or {}).items()
        if feld not in regeln
    ]

    assert ohne_regel == [], (
        "Diese Katalog-Metriken haben ein summary_fields-Zielfeld OHNE "
        "Aggregationsregel und verlieren ihren Wert bei jeder "
        f"Mehrsegment-Etappe: {ohne_regel!r}"
    )
