"""Gemeinsame Bausteine der Ad-hoc-Abruf-Tests (Issue #2134, Epic #2133).

SPEC: docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md

Mock-frei: echter `Trip` ueber `save_trip()`, echter Stunden-Snapshot ueber
`WeatherSnapshotService.save()` (also echter JSON-Roundtrip inkl.
Enum-Serialisierung), echter `TripCommandProcessor().process()`. Kein
`Mock()`/`patch()`.

Datenwurzel: die autouse-Fixture `_isolate_data_root` (tests/conftest.py,
#1133) lenkt `app.loader._DATA_ROOT` fuer JEDEN Kern-Test auf einen eigenen
tmp-Baum um. Deshalb ist hier KEIN eigenes `monkeypatch.setattr` auf
`get_data_dir` noetig — und die Mandantentrennung liegt zusaetzlich in der je
Test frisch gewuerfelten `user_id`.

Zeitfenster-Vorsicht: `_day_window(trip, "today", received_at)` liefert
`(received_at, 12h)`. Welches Fenster ein Ad-hoc-Wort nach der Umsetzung
benutzt, steht noch nicht fest — deshalb legen die Fixturen 24 Stundenpunkte
ab `now` an und die Tests pruefen Werte, die auf ALLEN Punkten gleich sind.
So haengt keine Zusicherung an einer Fensterbreite, die diese Scheibe gar
nicht festlegt.
"""
from __future__ import annotations

import re
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from app.loader import save_trip
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
)
from services.weather_snapshot import WeatherSnapshotService

# Vizzavona/Korsika -> Europe/Paris. Bewusst NICHT UTC, damit Ortszeit und
# Weltzeit unterscheidbar bleiben (siehe #1470).
WP_LAT, WP_LON = 42.1, 9.0
TRIP_TZ = ZoneInfo("Europe/Paris")

# So viele Stundenpunkte legt die Fixtur an — deutlich mehr als das
# 12-Stunden-Fenster von "heute", damit auch ein Ortstags-Fenster traegt.
STUNDEN = 24


def frische_kennung(praefix: str) -> str:
    """Eigene Mandanten-Kennung je Test (CLAUDE.md: Mandantentrennung)."""
    return f"tdd-2134-{praefix}-{uuid.uuid4().hex[:6]}"


def normalisiere(wort: str) -> str:
    """Normalisierung des Abrufworts laut Spec (Sektion "Normalisierung").

    kleingeschrieben, ``%`` -> ``pct``, ``°`` getilgt, uebrige
    Nicht-Alphanumerik getilgt. ``Rain%`` -> ``rainpct``, ``0°Line`` ->
    ``0line``.
    """
    w = wort.strip().lower().replace("%", "pct").replace("°", "")
    return re.sub(r"[^a-z0-9]", "", w)


def katalog_abrufwoerter() -> dict[str, str]:
    """Normalisiertes ``col_label`` -> ``metric.id``, aus ``get_all_metrics()``.

    Strukturell aus dem Katalog abgeleitet (AC-8/AC-18) — bewusst KEINE im
    Test eingetippte 29er-Liste.
    """
    from app.metric_catalog import get_all_metrics

    return {normalisiere(m.col_label): m.id for m in get_all_metrics()}


@dataclass
class Fixtur:
    """Was ein Test zum Absenden eines Ad-hoc-Worts braucht."""
    user_id: str
    trip_id: str
    trip_name: str
    now: datetime


def _trip(trip_id: str, trip_name: str, tag: date) -> Trip:
    """Drei Etappen (gestern/heute/morgen) — der Tages-Bezug soll nicht an
    einer Zeitzonen-Grenze kippen."""
    return Trip(
        id=trip_id,
        name=trip_name,
        stages=[
            Stage(
                id=f"S{i}",
                name=f"Etappe {i}",
                date=tag + timedelta(days=i - 1),
                waypoints=[
                    Waypoint(
                        id=f"W{i}a", name="Start",
                        lat=WP_LAT, lon=WP_LON, elevation_m=900,
                    ),
                    Waypoint(
                        id=f"W{i}b", name="Ziel",
                        lat=WP_LAT + 0.05, lon=WP_LON + 0.05, elevation_m=600,
                    ),
                ],
            )
            for i in range(3)
        ],
    )


def standard_felder(i: int) -> dict:
    """Vorbelegung eines Stundenpunkts: die vier heute abrufbaren Groessen."""
    return {
        "t2m_c": 10.0 + i,
        "wind10m_kmh": float(20 + i),
        "precip_1h_mm": 0.3,
        "thunder_level": (ThunderLevel.MED, ThunderLevel.HIGH)[i % 2],
    }


def _segmente(now: datetime, felder: Callable[[int], dict]) -> list[SegmentWeatherData]:
    punkte = [
        ForecastDataPoint(ts=now + timedelta(hours=i), **felder(i))
        for i in range(STUNDEN)
    ]
    segment = TripSegment(
        segment_id="seg-1",
        start_point=GPXPoint(lat=WP_LAT, lon=WP_LON, elevation_m=900),
        end_point=GPXPoint(lat=WP_LAT + 0.05, lon=WP_LON + 0.05, elevation_m=600),
        start_time=now,
        end_time=now + timedelta(hours=6),
        duration_hours=6.0,
        distance_km=15.0,
        ascent_m=200.0,
        descent_m=400.0,
    )
    return [
        SegmentWeatherData(
            segment=segment,
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(
                    provider=Provider.OPENMETEO, model="test", grid_res_km=0.0,
                ),
                data=punkte,
            ),
            aggregated=SegmentWeatherSummary(
                temp_min_c=10.0, temp_max_c=22.0,
                thunder_level_max=ThunderLevel.HIGH,
                wind_max_kmh=31.0,
                precip_sum_mm=3.3,
                pop_max_pct=60,
            ),
            fetched_at=now,
            provider=Provider.OPENMETEO.value,
        )
    ]


#: Oeffentlicher Name derselben Fixtur — die E-Mail-Renderer-Tests (AC-11)
#: brauchen die Segmente direkt, ohne Trip/Snapshot.
segmente = _segmente


def lege_trip_an(
    praefix: str,
    felder: Optional[Callable[[int], dict]] = None,
    *,
    mit_snapshot: bool = True,
    user_id: Optional[str] = None,
) -> Fixtur:
    """Echter Trip + echter Stunden-Snapshot unter der isolierten Datenwurzel."""
    now = datetime.now(tz=timezone.utc)
    user_id = user_id or frische_kennung(praefix)
    trip_id = f"adhoc-{praefix}"
    trip_name = f"Adhoc {praefix} Tour"

    trip = _trip(trip_id, trip_name, now.astimezone(TRIP_TZ).date())
    save_trip(trip, user_id)
    if mit_snapshot:
        WeatherSnapshotService(user_id).save(
            trip_id, _segmente(now, felder or standard_felder), now.date(),
        )
    return Fixtur(user_id=user_id, trip_id=trip_id, trip_name=trip_name, now=now)


def sende(fix: Fixtur, body: str, channel: str = "telegram") -> CommandResult:
    """Ein getipptes Wort durch den ECHTEN Eingang schicken."""
    msg = InboundMessage(
        trip_name=fix.trip_name,
        body=body,
        sender="4711" if channel == "telegram" else "wanderer@example.invalid",
        channel=channel,
        received_at=fix.now,
        user_id=fix.user_id,
    )
    return TripCommandProcessor().process(msg)


def ist_unbekannt(result: CommandResult) -> bool:
    """Hat der Prozessor mit "unbekannter Befehl"/Hilfe-Verweis geantwortet?"""
    text = (
        f"{result.confirmation_subject or ''}\n{result.confirmation_body or ''}"
    ).lower()
    return (
        "unbekannter befehl" in text
        or "kein gueltiger befehl" in text
        or "kein gültiger befehl" in text
        or "befehlsformat" in text
    )


def stundenzeilen(body: str) -> list[str]:
    """Zeilen, die mit einer zweistelligen Stunde beginnen."""
    return [z for z in body.splitlines() if re.match(r"^\s*\d{2}[:\s]", z)]


# ---------------------------------------------------------------------------
# Zugriff auf die beiden NEUEN Einzelquellen der Spec. Beide existieren im
# RED-Stand noch nicht — der Zugriff scheitert deshalb mit einer Meldung, die
# die FEHLENDE FUNKTIONALITAET benennt (und nicht mit einem ImportError beim
# Einsammeln der Testdatei).
# ---------------------------------------------------------------------------

def metrik_abrufwoerter() -> dict:
    """``metric_command_words()`` aus ``src/app/metric_catalog.py``."""
    from app import metric_catalog as cat

    fn = getattr(cat, "metric_command_words", None)
    assert fn is not None, (
        "src/app/metric_catalog.py hat keine Funktion `metric_command_words()` "
        "— das Ad-hoc-Abrufvokabular wird noch nicht aus dem Katalog "
        "abgeleitet (Spec-Sektion 'Metrik-Abrufwoerter werden abgeleitet')."
    )
    return fn()


def command_specs():
    """``_COMMAND_SPECS`` aus ``src/services/trip_command_processor.py``."""
    from services import trip_command_processor as tcp

    specs = getattr(tcp, "_COMMAND_SPECS", None)
    assert specs is not None, (
        "src/services/trip_command_processor.py hat keine Konstante "
        "`_COMMAND_SPECS` — es gibt noch keine Einzelquelle fuer die "
        "Steuerbefehle (Spec-Sektion 'Einzelquelle fuer Steuerbefehle')."
    )
    return specs


def wort_von(eintrag) -> str:
    """Normalisiertes Befehlswort eines ``_COMMAND_SPECS``-Eintrags.

    Formtolerant: die Spec legt Inhalt (Wort, Argumentform, Beschreibung),
    aber nicht die Traegerform fest. Ein unbekannter Aufbau faellt mit
    Klartext auf, statt still ein leeres Vokabular zu liefern (das jede
    Mengenpruefung trivial wahr machen wuerde).
    """
    if isinstance(eintrag, str):
        return normalisiere(eintrag)
    if isinstance(eintrag, (tuple, list)) and eintrag:
        return normalisiere(str(eintrag[0]))
    for attribut in ("wort", "word", "keyword", "key", "name", "befehl", "cmd"):
        wert = getattr(eintrag, attribut, None)
        if isinstance(wert, str) and wert:
            return normalisiere(wert)
    raise AssertionError(
        f"Unbekannte Form eines _COMMAND_SPECS-Eintrags: {eintrag!r} — der "
        "Test kann das Befehlswort nicht ablesen."
    )


def steuerbefehl_woerter() -> set[str]:
    """Menge der normalisierten Steuerbefehlswoerter aus ``_COMMAND_SPECS``."""
    specs = command_specs()
    roh = specs.keys() if isinstance(specs, dict) else specs
    woerter = {wort_von(e) for e in roh}
    assert woerter, "_COMMAND_SPECS ist leer — kein Befehlsvokabular ablesbar."
    return woerter


def specs_ohne(wort: str):
    """``_COMMAND_SPECS`` ohne den Eintrag ``wort`` (Mutations-Gegenprobe)."""
    specs = command_specs()
    ziel = normalisiere(wort)
    if isinstance(specs, dict):
        rest = {k: v for k, v in specs.items() if normalisiere(str(k)) != ziel}
    else:
        rest = type(specs)(e for e in specs if wort_von(e) != ziel)
    assert len(rest) < len(specs), (
        f"Mutations-Gegenprobe unwirksam: {wort!r} steht gar nicht in "
        f"_COMMAND_SPECS."
    )
    return rest


def text_woerter(text: str) -> set[str]:
    """Alle normalisierten Woerter eines Textes (fuer Mengenvergleiche)."""
    roh = re.split(r"[^0-9A-Za-zÄÖÜäöüß%°]+", text or "")
    return {normalisiere(t) for t in roh if normalisiere(t)}


@contextmanager
def katalog_eintrag_ersetzt(monkeypatch, metric_id: str, **felder):
    """Ersetzt Felder EINER Katalog-Groesse in allen Registern (Gegenprobe).

    Bewusst ueber ``dataclasses.replace`` statt per String-Ersetzung in der
    Quelldatei: ``MetricDefinition`` ist frozen, und ein ``importlib.reload``
    liesse die per ``from ... import`` gebundenen Referenzen anderer Module
    auf dem alten Modulzustand zurueck — die Gegenprobe waere blind und der
    Sitzungszustand vergiftet. Diese Fassung veraendert die DATEN (nicht die
    Erwartung des Tests) und stellt sie garantiert wieder her; weil keine
    Datei angefasst wird, eruebrigt sich eine externe Sicherungskopie.
    """
    import dataclasses

    from app import metric_catalog as cat

    alt = cat._METRICS_BY_ID[metric_id]
    neu = dataclasses.replace(alt, **felder)

    monkeypatch.setattr(
        cat, "_METRICS",
        [neu if m.id == metric_id else m for m in cat._METRICS],
    )
    monkeypatch.setitem(cat._METRICS_BY_ID, metric_id, neu)
    monkeypatch.setitem(cat._METRICS_BY_COL_KEY, neu.col_key, neu)
    caches_leeren()
    try:
        yield neu
    finally:
        caches_leeren()


def caches_leeren() -> None:
    """Alle ``lru_cache``-Huellen der beiden beteiligten Module leeren.

    Noetig, weil die Mutations-Gegenproben (AC-19/AC-13/AC-10) den Katalog
    bzw. die Befehlsquelle zur Laufzeit veraendern. Ohne Invalidierung wuerde
    ein zwischengespeichertes Vokabular die Aenderung verschlucken und der
    Test waere blind gegenueber genau der Ableitung, die er nachweisen soll.
    """
    from app import metric_catalog as cat
    from services import trip_command_processor as tcp

    for modul in (cat, tcp):
        for name in dir(modul):
            obj = getattr(modul, name, None)
            leeren = getattr(obj, "cache_clear", None)
            if callable(leeren):
                leeren()
