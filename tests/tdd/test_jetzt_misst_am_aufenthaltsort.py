"""``/jetzt`` misst am Aufenthaltsort, nicht am Etappenstart (Issue #2052).

SPEC: docs/specs/modules/fix_2052_now_aufenthaltsort.md

RED-Zustand: ``TripCommandProcessor._show_now`` liest heute unveraendert
``stage.waypoints[0]`` und fragt den Nowcast dort ab — egal, wie weit der
Wanderer zum Abfragezeitpunkt auf der Etappe schon gekommen ist. Kuenftig
wird ueber ``resolve_current_segment()`` + ``position_at_time()`` an der zu
``now_utc`` interpolierten Position gemessen.

Mock-frei nach Hausnorm: der Radar-Dienst ist eine echte
``RadarNowcastService``-UNTERKLASSE, die die Aufrufargumente mitschreibt und
danach ``super()`` mit dem vorhandenen ``frame_source``-DI-Seam laufen laesst
— die gesamte Ableitungslogik (Cache, Region, ``_derive_result``,
``format_now_text``) bleibt die echte, es geht kein Byte ins Netz. Kein
``Mock()``/``patch()``.

``_show_now`` importiert ``RadarNowcastService`` LOKAL in der Methode
(``trip_command_processor.py:1511``) und hat keinen Konstruktor-DI-Seam —
deshalb wird die Klasse an ihrem Wohnort ersetzt
(``services.radar_service.RadarNowcastService``), s.
``tests/unit/test_radar_budget_and_priority.py:243-248``.

Die Sollwerte werden ANALYTISCH aus Wegpunkt-Geometrie und Zeitanteil
gerechnet (:func:`_erwarteter_punkt`) — bewusst OHNE ``position_at_time()``
bzw. ``_interpolate_point()``. Ein aus dem Pruefling abgeleiteter
Erwartungswert machte jede Verfaelschung des Prueflings unsichtbar, weil der
Test sie mitmachte.

Zeitachse: die Etappe liegt in Atlantic/Reykjavik (ganzjaehrig UTC+0, s.
``nowcast_gate_fixtures.TRIP_LAT``) — die HH:MM-Angaben der Wegpunkte sind
damit direkt als UTC lesbar. :func:`_erwarteter_punkt` prueft diese Annahme,
statt sie zu setzen.
"""
from __future__ import annotations

import dataclasses
import logging
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from freezegun import freeze_time

from services.trip_command_processor import TripCommandProcessor
from tests.helpers.nowcast_gate_fixtures import CountingFrameSource, make_trip

# Pfadregel #1409: der Arbeitsbaum wird relativ zu DIESER Datei bestimmt, nie
# ueber einen festen Hauptrepo-Pfad — sonst prueft ein Worktree-Lauf still den
# Code des Hauptrepos und ist gruen aus dem falschen Grund.
_ARBEITSBAUM = Path(__file__).resolve().parents[2]

_TAG = date(2026, 8, 11)
# Geh-Segment 11:00-13:00 Ortszeit (= UTC), Abfrage um 11:30 -> Zeitanteil 0,25.
# Bewusst zwei Stunden statt eines ganzen Tages: damit unterscheiden sich die
# Positionen zu `now_utc` und zu den beiden Fenstermitte-Offsets (s. AC-2)
# deutlich messbar statt nur in der vierten Nachkommastelle.
_START, _ENDE = "11:00", "13:00"
_JETZT = datetime(2026, 8, 11, 11, 30, tzinfo=timezone.utc)
# Vor dem ersten Segment des Tages (AC-8).
_VORHER = datetime(2026, 8, 11, 9, 0, tzinfo=timezone.utc)
# Nach dem Ende des Ziel-Segments (Tagesfenster-Ende 20:00 Ortszeit) — und
# damit hinter der gesamten Vorrangkette von `resolve_current_segment()`
# (AC-9). Der Test verifiziert das ausdruecklich, statt es anzunehmen.
_NACH_TAGESENDE = datetime(2026, 8, 11, 21, 30, tzinfo=timezone.utc)


# ─────────────────────────────── Bausteine ──────────────────────────────────


def _trip(trip_id: str):
    """Zwei-Wegpunkt-Etappe aus dem geteilten Helfer (Start 500 m, Ende 600 m,
    Endpunkt +0.1°/+0.1°) — kein Nachbau aus ``Stage``/``Waypoint``."""
    return make_trip(
        trip_id, stage_date=_TAG, arrival_start=_START, arrival_end=_ENDE,
    )


def _wegpunkte(trip):
    stage = trip.get_stage_for_date(_TAG)
    return stage.waypoints[0], stage.waypoints[-1]


def _setze_wegpunkt(trip, idx: int, **felder):
    """``Waypoint``/``Stage`` sind ``frozen`` — der Austausch laeuft ueber
    ``dataclasses.replace`` in der (mutablen) Wegpunktliste der Etappe."""
    stage = trip.get_stage_for_date(_TAG)
    stage.waypoints[idx] = dataclasses.replace(stage.waypoints[idx], **felder)


def _erwarteter_punkt(trip, at: datetime):
    """``(lat, lon, hoehe, p)`` zum Zeitpunkt ``at`` — ANALYTISCH gerechnet.

    Nur Wegpunkt-Geometrie, Wegpunkt-Zeiten und die lineare Formel; kein
    Aufruf von ``position_at_time()``/``_interpolate_point()``.
    """
    from utils.timezone import tz_for_coords

    a, b = _wegpunkte(trip)
    zone = tz_for_coords(a.lat, a.lon)
    versatz = datetime.combine(_TAG, time(12, 0), tzinfo=zone).utcoffset()
    assert versatz == timedelta(0), (
        f"Testvoraussetzung: die Etappe muss in einer UTC+0-Zone liegen, damit "
        f"die HH:MM-Wegpunktzeiten direkt als UTC gelten — gemessen {versatz}"
    )
    start = datetime.combine(
        _TAG, time.fromisoformat(a.arrival_calculated), tzinfo=timezone.utc,
    )
    ende = datetime.combine(
        _TAG, time.fromisoformat(b.arrival_calculated), tzinfo=timezone.utc,
    )
    spanne = (ende - start).total_seconds()
    assert spanne > 0, "Testvoraussetzung: das Segment braucht eine echte Dauer"
    p = max(0.0, min(1.0, (at - start).total_seconds() / spanne))
    hoehe = None
    if a.elevation_m is not None and b.elevation_m is not None:
        hoehe = a.elevation_m + p * (b.elevation_m - a.elevation_m)
    return (
        a.lat + p * (b.lat - a.lat),
        a.lon + p * (b.lon - a.lon),
        hoehe,
        p,
    )


def _aufzeichnender_typ(calls: list, *, onset_minutes: int = 8):
    """Echte ``RadarNowcastService``-Unterklasse, die die Aufrufargumente
    mitschreibt und danach die ECHTE Ableitung laufen laesst.

    Eigener ``RadarNowcastCacheService`` je Instanz: der geteilte Prozess-Cache
    ist ein Singleton mit 300 s TTL — zwei Laeufe im selben Test wuerden sich
    sonst Zustand teilen und der zweite maesse einen Cache-Treffer statt des
    Verhaltens.
    """
    from services.radar_cache import RadarNowcastCacheService
    from services.radar_service import RadarNowcastService

    class _Aufzeichnend(RadarNowcastService):
        def __init__(self, *_a, **_kw) -> None:
            super().__init__(
                frame_source=CountingFrameSource(onset_minutes),
                cache=RadarNowcastCacheService(),
            )

        def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing"):
            calls.append({
                "lat": lat, "lon": lon,
                "elevation_m": elevation_m, "priority": priority,
            })
            return super().get_nowcast(
                lat, lon, elevation_m=elevation_m, priority=priority,
            )

    return _Aufzeichnend


def _jetzt(monkeypatch, trip, now_utc: datetime):
    """Ein echter ``_show_now``-Lauf; liefert ``(CommandResult, ruf)``."""
    import services.trip_command_processor as tcp

    assert Path(tcp.__file__).resolve().is_relative_to(_ARBEITSBAUM), (
        f"Pfadregel #1409: der Pruefling wurde aus {tcp.__file__} geladen, "
        f"nicht aus dem Arbeitsbaum {_ARBEITSBAUM} dieser Testdatei"
    )
    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService", _aufzeichnender_typ(calls),
    )
    with freeze_time(now_utc):
        ergebnis = TripCommandProcessor()._show_now(trip, now_utc)
    assert len(calls) == 1, (
        f"Testvoraussetzung: genau EIN get_nowcast()-Abruf je /jetzt erwartet, "
        f"gesehen {len(calls)} — Antwort: {ergebnis.confirmation_body!r}"
    )
    return ergebnis, calls[0]


def _fenstermitte_offsets() -> list[int]:
    """Die Zieloffsets, die Alarm- bzw. Briefing-Pfad benutzen (#2017).

    Ueber die MODUL-Referenz gelesen, nie beim Import gebunden: der
    Laufzeit-Drift-Waechter aus #2009 setzt ``RADAR_ONSET_THRESHOLD_MIN`` zur
    Laufzeit um; eine gebundene Kopie liefe still daran vorbei.
    """
    from services import radar_service as rs

    return [rs.RADAR_ONSET_THRESHOLD_MIN // 2, rs.NOWCAST_HORIZON_MIN // 2]


# ──────────────────────────────── AC-1 ──────────────────────────────────────


def test_ac1_jetzt_misst_an_der_interpolierten_position(monkeypatch):
    """AC-1.

    GIVEN eine heutige Etappe 11:00-13:00, deren Segment um 11:30 laeuft,
    WHEN  ``/jetzt`` aufgerufen wird,
    THEN  traegt der ``get_nowcast()``-Aufruf die zu ``now_utc`` interpolierte
          Position — nicht ``stage.waypoints[0]``, den Ort vom Morgen.
    """
    trip = _trip("jetzt-2052-ac1")
    start_wp, _ziel_wp = _wegpunkte(trip)
    soll_lat, soll_lon, _h, p = _erwarteter_punkt(trip, _JETZT)

    _ergebnis, ruf = _jetzt(monkeypatch, trip, _JETZT)

    assert (abs(ruf["lat"] - soll_lat) < 1e-9
            and abs(ruf["lon"] - soll_lon) < 1e-9), (
        f"AC-1: /jetzt fragte den Nowcast an ({ruf['lat']:.5f}, "
        f"{ruf['lon']:.5f}) ab; erwartet der um {_JETZT:%H:%M} UTC "
        f"interpolierte Aufenthaltsort ({soll_lat:.5f}, {soll_lon:.5f}), "
        f"Zeitanteil p={p:.4f}. ({start_wp.lat:.5f}, {start_wp.lon:.5f}) ist "
        f"der Etappenstart — der Ort, den der Wanderer am Morgen verlassen hat."
    )


# ──────────────────────────────── AC-2 ──────────────────────────────────────


def test_ac2_zielzeitpunkt_ist_now_utc_und_nicht_die_fenstermitte(monkeypatch):
    """AC-2.

    GIVEN dieselbe laufende Etappe,
    WHEN  ``/jetzt`` um 11:30 aufgerufen wird,
    THEN  ist der Messzeitpunkt ``now_utc`` SELBST — nicht die Fenstermitte
          (``RADAR_ONSET_THRESHOLD_MIN // 2`` bzw. ``NOWCAST_HORIZON_MIN // 2``),
          mit der Alarm- und Briefing-Pfad vorauswaehlen. ``/jetzt`` ist keine
          Vorwarnung: der Nutzer fragt nach dem Ort, an dem er STEHT.

    Der Fall ist bewusst so gebaut, dass sich die Positionen zu ``now_utc`` und
    zu beiden Fenstermitten messbar unterscheiden — ein Aufbau, bei dem beide
    Zeitpunkte denselben Punkt lieferten, bewiese nichts.
    """
    trip = _trip("jetzt-2052-ac2")
    soll_lat, soll_lon, _h, _p = _erwarteter_punkt(trip, _JETZT)

    mitten = {}
    for offset in _fenstermitte_offsets():
        m_lat, m_lon, _mh, _mp = _erwarteter_punkt(
            trip, _JETZT + timedelta(minutes=offset),
        )
        assert abs(m_lat - soll_lat) > 0.005 and abs(m_lon - soll_lon) > 0.005, (
            f"Testvoraussetzung: der Punkt zur Fenstermitte (+{offset} min, "
            f"{m_lat:.5f}/{m_lon:.5f}) muss sich vom Punkt zu now_utc "
            f"({soll_lat:.5f}/{soll_lon:.5f}) messbar unterscheiden — sonst "
            f"kann der Test die beiden Zeitpunkte gar nicht trennen"
        )
        mitten[offset] = (round(m_lat, 5), round(m_lon, 5))

    _ergebnis, ruf = _jetzt(monkeypatch, trip, _JETZT)

    assert (abs(ruf["lat"] - soll_lat) < 1e-9
            and abs(ruf["lon"] - soll_lon) < 1e-9), (
        f"AC-2: gemessen wurde an ({ruf['lat']:.5f}, {ruf['lon']:.5f}); "
        f"erwartet der Ort zum Abfragezeitpunkt now_utc "
        f"({soll_lat:.5f}, {soll_lon:.5f}). Die Fenstermitte-Punkte des "
        f"Alarm-/Briefing-Pfads waeren {mitten} — eine Vorausmessung koennte "
        f"'trocken' melden, waehrend der Nutzer im Regen steht."
    )


# ──────────────────────────────── AC-3 ──────────────────────────────────────


def test_ac3_messpunkt_wandert_mit_dem_zielwegpunkt(monkeypatch):
    """AC-3 (Nicht-Trivialitaet / Gegenprobe).

    GIVEN zwei sonst gleiche Touren, deren ZIELwegpunkt verschoben ist,
    WHEN  ``/jetzt`` jeweils zum selben Zeitpunkt laeuft,
    THEN  verschiebt sich der abgefragte Messpunkt mit — und er liegt in beiden
          Laeufen > 0.01° vom Etappenstart entfernt.

    Ohne diese Gegenprobe waere AC-1 trivial erfuellbar (ein Messpunkt, der
    zufaellig am Start klebt, bestuende sie ebenfalls).
    """
    trip_a = _trip("jetzt-2052-ac3a")
    trip_b = _trip("jetzt-2052-ac3b")
    start_wp, ziel_wp = _wegpunkte(trip_b)
    _setze_wegpunkt(trip_b, -1, lat=start_wp.lat + 0.3, lon=start_wp.lon - 0.2)
    assert _wegpunkte(trip_b)[1] != ziel_wp, "Testaufbau: Ziel nicht verschoben"

    soll_a = _erwarteter_punkt(trip_a, _JETZT)
    soll_b = _erwarteter_punkt(trip_b, _JETZT)

    _erg_a, ruf_a = _jetzt(monkeypatch, trip_a, _JETZT)
    _erg_b, ruf_b = _jetzt(monkeypatch, trip_b, _JETZT)

    for name, ruf, soll, trip in (
        ("A", ruf_a, soll_a, trip_a), ("B", ruf_b, soll_b, trip_b),
    ):
        s_wp = _wegpunkte(trip)[0]
        assert (abs(soll[0] - s_wp.lat) > 0.01
                and abs(soll[1] - s_wp.lon) > 0.01), (
            f"Testvoraussetzung Lauf {name}: interpolierter Punkt "
            f"({soll[0]:.5f}, {soll[1]:.5f}) und Etappenstart "
            f"({s_wp.lat:.5f}, {s_wp.lon:.5f}) muessen sich um > 0.01° "
            f"unterscheiden, p={soll[3]:.4f}"
        )
        assert (abs(ruf["lat"] - soll[0]) < 1e-9
                and abs(ruf["lon"] - soll[1]) < 1e-9), (
            f"AC-3 Lauf {name}: gemessen an ({ruf['lat']:.5f}, "
            f"{ruf['lon']:.5f}), erwartet ({soll[0]:.5f}, {soll[1]:.5f}) — "
            f"Etappenstart waere ({s_wp.lat:.5f}, {s_wp.lon:.5f})"
        )

    assert (ruf_a["lat"], ruf_a["lon"]) != (ruf_b["lat"], ruf_b["lon"]), (
        f"AC-3: beide Laeufe fragten dieselbe Koordinate ab "
        f"({ruf_a['lat']:.5f}, {ruf_a['lon']:.5f}), obwohl der Zielwegpunkt "
        f"verschoben wurde — der Messpunkt folgt der Geometrie also gar nicht"
    )


# ──────────────────────────────── AC-4 ──────────────────────────────────────


def test_ac4_hoehe_wandert_mit_und_ist_ganzzahlig(monkeypatch):
    """AC-4.

    GIVEN ein Segment mit 500 m am Start und 600 m am Ziel,
    WHEN  ``/jetzt`` bei Zeitanteil 0,25 laeuft,
    THEN  traegt ``get_nowcast(elevation_m=...)`` die MITGEWANDERTE Hoehe,
          an der Aufrufstelle auf ganze Meter normalisiert (``int``).

    Der Typ wird mitgeprueft, nicht nur der Wert: ``get_nowcast`` fuehrt
    ``elevation_m`` roh im Cache-Schluessel — ``1000`` vs. ``1000.0`` erzeugte
    in #1991 zwei Eintraege fuer denselben Punkt.
    """
    trip = _trip("jetzt-2052-ac4")
    start_wp, ziel_wp = _wegpunkte(trip)
    _lat, _lon, soll_hoehe, p = _erwarteter_punkt(trip, _JETZT)
    assert soll_hoehe is not None and abs(soll_hoehe - start_wp.elevation_m) > 5.0, (
        f"Testvoraussetzung: interpolierte Hoehe {soll_hoehe} und Start-Hoehe "
        f"{start_wp.elevation_m} muessen sich unterscheiden (p={p:.4f})"
    )

    _ergebnis, ruf = _jetzt(monkeypatch, trip, _JETZT)

    assert ruf["elevation_m"] == int(round(soll_hoehe)), (
        f"AC-4: get_nowcast mit elevation_m={ruf['elevation_m']}; erwartet die "
        f"interpolierte Hoehe {int(round(soll_hoehe))} m (zwischen "
        f"{start_wp.elevation_m} m und {ziel_wp.elevation_m} m). "
        f"{start_wp.elevation_m} m waere die Hoehe des verlassenen "
        f"Startpunkts — neuer Ort, alte Hoehe."
    )
    assert isinstance(ruf["elevation_m"], int), (
        f"AC-4: elevation_m ist {type(ruf['elevation_m']).__name__} "
        f"({ruf['elevation_m']!r}), erwartet int — die Normalisierung auf ganze "
        f"Meter wohnt an der Aufrufstelle (#1991: 1000 vs. 1000.0 sind zwei "
        f"Cache-Eintraege fuer denselben Punkt)"
    )


def test_ac4_hoehe_bleibt_none_wenn_die_wegpunkte_keine_tragen(monkeypatch):
    """AC-4 (zweite Haelfte: ``None`` bleibt ``None``).

    GIVEN eine Etappe, deren Wegpunkte keine Hoehe tragen, und eine Abfrage
          nach Tagesende (Rueckfall auf ``stage.waypoints[-1]``, AC-9),
    WHEN  ``/jetzt`` laeuft,
    THEN  wird ``elevation_m=None`` uebergeben statt einer erfundenen Zahl.

    Bewusst ueber den Rueckfall-Zweig und nicht ueber die Interpolation:
    ``convert_trip_to_segments()`` ersetzt eine fehlende Wegpunkt-Hoehe beim
    Segmentbau durch ``0.0`` (``trip_segments.py:222``) — ueber den
    Segment-Pfad ist ``None`` strukturell unerreichbar, ueber den
    Wegpunkt-Rueckfall nicht.
    """
    trip = _trip("jetzt-2052-ac4-none")
    for idx in (0, -1):
        _setze_wegpunkt(trip, idx, elevation_m=None)
    _start_wp, ziel_wp = _wegpunkte(trip)

    _ergebnis, ruf = _jetzt(monkeypatch, trip, _NACH_TAGESENDE)

    assert ruf["elevation_m"] is None, (
        f"AC-4: elevation_m={ruf['elevation_m']!r}; ohne Wegpunkt-Hoehe muss "
        f"None durchgereicht werden, nicht 0 oder ein gerundeter Ersatzwert"
    )
    assert (ruf["lat"], ruf["lon"]) == (ziel_wp.lat, ziel_wp.lon), (
        f"AC-4/AC-9: gemessen an ({ruf['lat']}, {ruf['lon']}), erwartet der "
        f"letzte Wegpunkt ({ziel_wp.lat}, {ziel_wp.lon})"
    )


# ──────────────────────────────── AC-5 ──────────────────────────────────────


def test_ac5_zeitzone_wird_am_messpunkt_bestimmt(monkeypatch):
    """AC-5.

    GIVEN eine laufende Etappe,
    WHEN  ``/jetzt`` laeuft,
    THEN  wird ``tz_for_coords()`` auf die INTERPOLIERTEN Koordinaten
          angewandt, nicht mehr auf ``stage.waypoints[0]`` — die Onset-Uhrzeit
          im Antworttext gilt fuer den Messpunkt.

    Aufgezeichnet wird ueber einen durchreichenden Wrapper auf
    ``utils.timezone.tz_for_coords``; die echte Aufloesung laeuft weiter. Eine
    Etappe ueber eine echte Zeitzonengrenze ist als Nachweis nicht noetig
    (eigener Randfall, s. Known Limitations der Spec).
    """
    import utils.timezone as tzmod

    echt = tzmod.tz_for_coords
    tz_aufrufe: list[tuple[float, float]] = []

    def _aufzeichnend(lat, lon):
        tz_aufrufe.append((lat, lon))
        return echt(lat, lon)

    trip = _trip("jetzt-2052-ac5")
    start_wp, _ziel_wp = _wegpunkte(trip)
    soll_lat, soll_lon, _h, _p = _erwarteter_punkt(trip, _JETZT)

    monkeypatch.setattr(tzmod, "tz_for_coords", _aufzeichnend)
    _ergebnis, _ruf = _jetzt(monkeypatch, trip, _JETZT)

    treffer = [
        (la, lo) for la, lo in tz_aufrufe
        if abs(la - soll_lat) < 1e-9 and abs(lo - soll_lon) < 1e-9
    ]
    assert treffer, (
        f"AC-5: tz_for_coords() wurde mit {tz_aufrufe} gerufen — der "
        f"interpolierte Messpunkt ({soll_lat:.5f}, {soll_lon:.5f}) ist nicht "
        f"darunter. ({start_wp.lat:.5f}, {start_wp.lon:.5f}) ist der "
        f"Etappenstart; die Onset-Uhrzeit gaelte dann fuer den falschen Ort."
    )


# ──────────────────────────────── AC-8 ──────────────────────────────────────


def test_ac8_vor_dem_ersten_segment_bitgleich_zum_startpunkt(monkeypatch):
    """AC-8 (Vorschau, Bitgleichheit).

    GIVEN eine Abfrage um 09:00, also VOR dem ersten Segment des Tages,
    WHEN  ``/jetzt`` laeuft und die Vorschau-Stufe von
          ``resolve_current_segment()`` greift,
    THEN  sind die abgefragten Koordinaten IDENTISCH (``==``, nicht bloss nah)
          mit ``stage.waypoints[0]`` — bitgleich zum Verhalten vor dieser
          Aenderung.
    """
    from services.trip_day import trip_local_today
    from services.trip_segments import resolve_current_segment

    trip = _trip("jetzt-2052-ac8")
    start_wp, _ziel_wp = _wegpunkte(trip)

    aufgeloest = resolve_current_segment(
        trip, _VORHER, trip_local_today(trip, _VORHER),
    )
    assert aufgeloest is not None, (
        "Testvoraussetzung: um 09:00 muss die Vorschau-Stufe greifen — sonst "
        "prueft der Fall den Rueckfall-Zweig statt der Vorschau"
    )

    _ergebnis, ruf = _jetzt(monkeypatch, trip, _VORHER)

    assert (ruf["lat"], ruf["lon"]) == (start_wp.lat, start_wp.lon), (
        f"AC-8: vor dem Etappenstart gemessen an ({ruf['lat']!r}, "
        f"{ruf['lon']!r}); erwartet bitgleich der erste Wegpunkt "
        f"({start_wp.lat!r}, {start_wp.lon!r}) — der Wanderer ist noch nicht "
        f"losgelaufen"
    )


# ──────────────────────────────── AC-9 ──────────────────────────────────────


def test_ac9_nach_tagesende_wird_am_letzten_wegpunkt_gemessen(monkeypatch):
    """AC-9 (Randfall nach Tagesende).

    GIVEN eine Abfrage nach dem Ende des Tagesfensters — so gelegt, dass auch
          der Vortags-Rueckgriff (Stufe 2) nicht greift,
    WHEN  ``resolve_current_segment()`` damit ``None`` liefert,
    THEN  wird am LETZTEN Wegpunkt der heutigen Etappe gemessen, nicht am
          ersten: ``None`` heisst hier eindeutig "der Etappentag ist
          abgelaufen", der Wanderer ist am Tagesziel.

    Dass wirklich ``None`` herauskommt, wird im Aufbau verifiziert — sonst
    pruefte der Fall einen anderen Zweig als gemeint.
    """
    from services.trip_day import trip_local_today
    from services.trip_segments import resolve_current_segment

    trip = _trip("jetzt-2052-ac9")
    start_wp, ziel_wp = _wegpunkte(trip)

    aufgeloest = resolve_current_segment(
        trip, _NACH_TAGESENDE, trip_local_today(trip, _NACH_TAGESENDE),
    )
    assert aufgeloest is None, (
        f"Testvoraussetzung: um {_NACH_TAGESENDE:%H:%M} UTC muss die "
        f"Vorrangkette None liefern, tatsaechlich {aufgeloest!r} — sonst "
        f"prueft der Fall die Interpolation statt des Tagesende-Rueckfalls"
    )

    _ergebnis, ruf = _jetzt(monkeypatch, trip, _NACH_TAGESENDE)

    assert (ruf["lat"], ruf["lon"]) == (ziel_wp.lat, ziel_wp.lon), (
        f"AC-9: nach Tagesende gemessen an ({ruf['lat']!r}, {ruf['lon']!r}); "
        f"erwartet das Tagesziel ({ziel_wp.lat!r}, {ziel_wp.lon!r}). "
        f"({start_wp.lat!r}, {start_wp.lon!r}) ist der Etappenstart — die "
        f"volle Etappenlaenge daneben."
    )


# ─────────────────────────────── AC-10 ──────────────────────────────────────


def test_ac10_fehlgeschlagene_positionsbestimmung_faellt_zurueck_und_loggt(
    monkeypatch, caplog,
):
    """AC-10 (Fehlerpfad).

    GIVEN ``position_at_time()`` wirft wider Erwarten,
    WHEN  ``/jetzt`` laeuft,
    THEN  bekommt der Nutzer TROTZDEM eine Nowcast-Antwort (``success=True``),
          gemessen am bisherigen Ort ``stage.waypoints[0]``, und der Fehler
          steht als ``logger.error`` im Protokoll.

    Der Fall bewacht zusaetzlich die Fehlerpfad-TRENNUNG (F-ADV1 aus #2017):
    das ``try`` darf ausschliesslich die Positionsbestimmung umschliessen.
    Wuerde jemand spaeter den ganzen Block inklusive ``get_nowcast()``
    einpacken, bliebe der Abruf aus und der Antworttext leer — genau das
    faengt die Kombination aus "genau ein Abruf" und "Antwort vorhanden".
    """
    import services.trip_segments as segmente

    aufrufe: list = []

    def _wirft(trip, active, segment_date, at):
        aufrufe.append(at)
        raise RuntimeError("Positionsbestimmung kaputt (Testfall AC-10)")

    monkeypatch.setattr(segmente, "position_at_time", _wirft)

    trip = _trip("jetzt-2052-ac10")
    start_wp, _ziel_wp = _wegpunkte(trip)

    with caplog.at_level(logging.ERROR):
        ergebnis, ruf = _jetzt(monkeypatch, trip, _JETZT)

    assert aufrufe, (
        "AC-10: position_at_time() wurde ueberhaupt nicht gerufen — /jetzt "
        "bestimmt die Position also gar nicht ueber den geteilten Baustein "
        "(heutiger Zustand: es liest stage.waypoints[0] direkt)"
    )
    assert ergebnis.success is True and ergebnis.confirmation_body.strip(), (
        f"AC-10: der Nutzer muss trotz Fehler eine Antwort bekommen — "
        f"success={ergebnis.success}, body={ergebnis.confirmation_body!r}"
    )
    assert (ruf["lat"], ruf["lon"]) == (start_wp.lat, start_wp.lon), (
        f"AC-10: Rueckfall muss am bisherigen Ort messen "
        f"({start_wp.lat!r}, {start_wp.lon!r}), gemessen wurde "
        f"({ruf['lat']!r}, {ruf['lon']!r})"
    )
    fehler = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert fehler, (
        "AC-10: kein logger.error-Aufruf — eine fehlgeschlagene "
        "Positionsbestimmung darf nicht stumm auf den Etappenstart "
        "zurueckfallen"
    )
    assert any("osition" in r.getMessage() for r in fehler), (
        f"AC-10: die Fehlermeldung muss die POSITIONSbestimmung benennen "
        f"(unterscheidbar von 'Radar nowcast failed'), gesehen: "
        f"{[r.getMessage() for r in fehler]}"
    )
