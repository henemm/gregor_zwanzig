"""TDD RED — Issue #2073 Scheibe 2: der stille Fehlschlag der Track-Auflösung
wird sichtbar (AC-1 bis AC-9, AC-14).

SPEC: docs/specs/modules/fix_2073_s2_sichtbarer_fehlschlag.md

RED-VERTRAG
-----------
Heute wirft ``backfill_stage_distances`` den Grund eines Fehlschlags weg: die
Etappe bleibt unvermessen, die Ortsangabe fällt auf ``Segment N`` zurück,
niemand erfährt davon. Jeder Test unten prüft eine Journalzeile, die es noch
nicht gibt — der RED-Grund ist deshalb durchweg "0 Zeilen statt 1" bzw. der
fehlende Import des noch nicht existierenden Schreibmoduls (nur AC-14).

ENTWORFENE SCHNITTSTELLE (Auftrag an die GREEN-Phase)
-----------------------------------------------------
Neues Modul ``src/services/track_resolution_health.py``:

* ``FAILURE_REPORT_TOLERANCE_KM = 1.0`` — Meldegrenze auf dem Abstand des
  BESTEN Kandidaten (kleinster maximaler Wegpunkt-Abstand über alle GPX).
* ``fehlschlag_ist_meldewuerdig(bester_abstand_km: float) -> bool`` — die
  Melderegel als eigene, direkt prüfbare Funktion: ``True``, solange
  ``bester_abstand_km <= FAILURE_REPORT_TOLERANCE_KM``. Sie existiert, damit
  der INKLUSIVE Grenzfall "genau 1 km" ohne Geometrie prüfbar ist (AC-14).
* Journal: ``get_data_dir(user_id) / "diagnostics" /
  "track_resolution_failures.jsonl"``, eine JSON-Zeile je Fehlschlag.
* Felder je Zeile: ``ts`` (UTC ISO 8601, mit Zeitzone), ``trip_id``,
  ``stage_id``, ``reason``, ``detail``.
* ``reason`` ∈ {``no_candidate_within_tolerance``, ``ambiguous_result``,
  ``implausible_measurement``}.
* ``detail`` ist bei den beiden ersten Gründen eine **Zahl in METERN**
  (gemessener Abstand bzw. maximale Abweichung zwischen Kandidaten); bei
  ``implausible_measurement`` beliebiger, aber nicht leerer Inhalt.
* Fail-soft: ein Schreibfehler wird IM SCHREIBER gefangen und geloggt, er
  darf nicht bis zum ``except Exception`` in ``backfill_stage_distances``
  durchschlagen (AC-8 prüft genau das über das Log).

TESTDATEN-ENTWURF (offener Punkt für den Adversary)
---------------------------------------------------
``_match_track`` kehrt beim ERSTEN Wegpunkt jenseits der Toleranz zurück und
kennt damit nur eine UNTERGRENZE des schlechtesten Abstands. Alle Fälle hier
sind deshalb so gebaut, dass entweder genau EIN Wegpunkt abweicht oder ALLE
gleich weit abweichen — dann ist der erste verfehlende Wegpunkt zugleich der
schlechteste, und der Test hängt nicht an einer ungeklärten Entscheidung über
die Schleifenreihenfolge. Bei mehreren, unterschiedlich weit abweichenden
Wegpunkten ist die Melderegel heute unterbestimmt.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

import pytest

_JOURNAL_DATEI = "track_resolution_failures.jsonl"
_ZIELDATUM = date(2026, 8, 25)

# Nord-Süd-Gitter: 0,01° Breite ≈ 1.112 m, unabhängig vom Längengrad.
_BASIS_LAT = 47.0
_BASIS_LON = 12.0
_SCHRITT = 0.01
_PUNKTE = 21                      # 21 Trackpunkte (>= 10, Parser-Mindestmaß)
_WP_INDIZES = [0, 5, 10, 20]      # G1..G4 liegen EXAKT auf Trackpunkten


# ---------------------------------------------------------------------------
# Prozess-Zustand: `_failed_lookups` ist modulweit und überlebt den Test.
# Ohne diese Fixture dämpft ein früherer Test den nächsten weg und die
# Wächter wären wirkungslos. AC-5 leert bewusst NICHT zwischen seinen beiden
# Aufrufen — genau das ist dort der Prüfgegenstand.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _prozess_cache_leeren():
    from services import track_resolution

    track_resolution._failed_lookups.clear()
    yield
    track_resolution._failed_lookups.clear()


# ---------------------------------------------------------------------------
# Bau-Hilfen — echte GPX-Dateien, echte Trip-Objekte, kein Mock
# ---------------------------------------------------------------------------

def _lon_versatz(lat: float, ziel_m: float) -> float:
    """Längengrad-Differenz, die bei ``lat`` genau ``ziel_m`` entspricht.

    Bisektion gegen die ECHTE ``haversine_km`` — dieselbe Funktion, mit der
    ``_match_track`` misst. Eine handgerechnete Gradzahl wäre eine zweite,
    still abweichende Messgrundlage.
    """
    from utils.geo import haversine_km

    if ziel_m <= 0.0:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if haversine_km(lat, _BASIS_LON, lat, _BASIS_LON + mid) * 1000.0 < ziel_m:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _gitter() -> list:
    """Trackpunkte (lat, lon, Höhe) der Basisroute."""
    return [
        (round(_BASIS_LAT + i * _SCHRITT, 8), _BASIS_LON, 1000.0 + i)
        for i in range(_PUNKTE)
    ]


def _gpx_schreiben(pfad: Path, punkte) -> None:
    trkpts = "".join(
        f'<trkpt lat="{lat:.9f}" lon="{lon:.9f}"><ele>{ele:.1f}</ele></trkpt>'
        for lat, lon, ele in punkte
    )
    pfad.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="tdd-2073-s2" '
        'xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><name>{pfad.stem}</name><trkseg>{trkpts}</trkseg></trk></gpx>",
        encoding="utf-8",
    )


def _gpx_dir(user_id: str) -> Path:
    from app.loader import get_data_dir

    d = get_data_dir(user_id) / "gpx"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _trip(user_id: str, waypoints, trip_id: str = "tour-2073-s2"):
    from app.trip import Stage, Trip

    stage = Stage(id="T1", name="Etappe 1", date=_ZIELDATUM, waypoints=waypoints)
    return Trip(id=trip_id, name="Testtour 2073 S2", stages=[stage])


def _waypoints(versatz_je_index=None, distanzen=None):
    """G1..G4 auf den Gitterpunkten; ``versatz_je_index`` verschiebt einzelne
    davon um n Meter nach Osten (quer zur Route, damit der ursprüngliche
    Trackpunkt der nächstgelegene bleibt)."""
    from app.trip import Waypoint

    versatz_je_index = versatz_je_index or {}
    gitter = _gitter()
    wps = []
    for n, idx in enumerate(_WP_INDIZES):
        lat, lon, ele = gitter[idx]
        lon += _lon_versatz(lat, versatz_je_index.get(n, 0.0))
        wps.append(Waypoint(
            id=f"G{n + 1}", name=f"Punkt {n + 1}", lat=lat, lon=lon,
            elevation_m=int(ele),
            distance_from_start_km=None if distanzen is None else distanzen[n],
        ))
    return wps


def _journal(user_id: str) -> list:
    """Geparste Journalzeilen des Nutzers — nie ein String-Check auf dem
    Dateiinhalt, sondern echtes ``json.loads`` je Zeile."""
    from app.loader import get_data_dir

    pfad = get_data_dir(user_id) / "diagnostics" / _JOURNAL_DATEI
    if not pfad.exists():
        return []
    return [
        json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]


def _lauf(user_id: str, trip, *, persist: bool = True):
    from services.track_resolution import backfill_stage_distances

    return backfill_stage_distances(trip, user_id, _ZIELDATUM, persist=persist)


def _fall_ein_wegpunkt_daneben(user_id: str, versatz_m: float):
    """Basisroute liegt im Bestand; genau EIN Wegpunkt (G3) liegt
    ``versatz_m`` daneben — der beste Kandidat verfehlt also die 10-m-
    Zuordnungstoleranz um exakt diesen Abstand."""
    _gpx_schreiben(_gpx_dir(user_id) / "route.gpx", _gitter())
    return _trip(user_id, _waypoints({2: versatz_m}))


def _fall_ganzer_track_versetzt(user_id: str, versatz_m: float):
    """Der einzige Kandidat im Bestand liegt als GANZES ``versatz_m`` neben
    der Route — jeder Wegpunkt ist gleich weit weg, der schlechteste Abstand
    ist damit eindeutig ``versatz_m`` (unabhängig von der Schleifenordnung)."""
    punkte = [
        (lat, round(lon + _lon_versatz(lat, versatz_m), 9), ele)
        for lat, lon, ele in _gitter()
    ]
    _gpx_schreiben(_gpx_dir(user_id) / "route.gpx", punkte)
    return _trip(user_id, _waypoints())


def _pruefe_grundfelder(eintrag: dict, *, trip_id: str, reason: str) -> None:
    assert eintrag["trip_id"] == trip_id, eintrag
    assert eintrag["stage_id"] == "T1", eintrag
    assert eintrag["reason"] == reason, eintrag
    ts = datetime.fromisoformat(eintrag["ts"])
    assert ts.tzinfo is not None, f"ts ohne Zeitzone (UTC verlangt): {eintrag['ts']}"


# ---------------------------------------------------------------------------
# AC-1 — knapp verfehlter Wegpunkt wird als Fehlschlag protokolliert
# ---------------------------------------------------------------------------

def test_knapp_verfehlter_wegpunkt_erzeugt_journalzeile_mit_abstand():
    """AC-1: Given eine Etappe, deren GPX-Bestand bis auf einen einzelnen,
    knapp abseits liegenden Wegpunkt passt (111 m — der real gemessene
    Beinahe-Treffer aus #2070) / When ``backfill_stage_distances(...,
    persist=True)`` läuft / Then entsteht genau eine Journalzeile mit
    ``reason="no_candidate_within_tolerance"`` und dem Abstand in Metern."""
    uid = "tdd-2073-s2-ac1"
    trip = _fall_ein_wegpunkt_daneben(uid, 111.0)

    ergebnis = _lauf(uid, trip)

    assert all(wp.distance_from_start_km is None
               for wp in ergebnis.stages[0].waypoints), (
        "Vorbedingung verletzt: die Auflösung hat trotz 111-m-Abweichung "
        "gemessen — dann prüft der Test nicht den Fehlschlagspfad"
    )
    zeilen = _journal(uid)
    assert len(zeilen) == 1, f"genau eine Journalzeile erwartet, bekam: {zeilen}"
    _pruefe_grundfelder(zeilen[0], trip_id=trip.id,
                        reason="no_candidate_within_tolerance")
    assert float(zeilen[0]["detail"]) == pytest.approx(111.0, abs=2.0), (
        f"detail soll den gemessenen Abstand in Metern tragen: {zeilen[0]}"
    )


# ---------------------------------------------------------------------------
# AC-2 — jenseits der Meldegrenze bleibt es still (mit Positivkontrolle)
# ---------------------------------------------------------------------------

def test_kandidat_jenseits_der_meldegrenze_erzeugt_keine_zeile():
    """AC-2: Given ein Trip ohne jede passende Aufzeichnung (bester Kandidat
    4.673 m entfernt — der real gemessene nächste UNBETEILIGTE Kandidat) /
    When dieselbe Auflösung läuft / Then entsteht keine Journalzeile.

    Positivkontrolle im selben Testkörper (Pflicht): derselbe Aufbau mit
    einem Kandidaten in 111 m Entfernung erzeugt sehr wohl eine Zeile. Ohne
    diesen Gegenbeweis wäre die 0 auch bei komplett kaputtem Journalschreiber
    grün.
    """
    uid_fern = "tdd-2073-s2-ac2-fern"
    _lauf(uid_fern, _fall_ganzer_track_versetzt(uid_fern, 4673.0))

    uid_nah = "tdd-2073-s2-ac2-nah"
    _lauf(uid_nah, _fall_ganzer_track_versetzt(uid_nah, 111.0))

    assert len(_journal(uid_nah)) == 1, (
        "Positivkontrolle gescheitert: auch der NAHE Kandidat erzeugt keine "
        "Zeile — die '0' beim fernen Kandidaten beweist damit nichts"
    )
    assert _journal(uid_fern) == [], (
        "ein Kandidat 4.673 m abseits gehört nicht zu dieser Route und darf "
        f"kein Signal erzeugen: {_journal(uid_fern)}"
    )


# ---------------------------------------------------------------------------
# AC-3 — widersprüchliche Kandidaten
# ---------------------------------------------------------------------------

def test_widerspruechliche_kandidaten_erzeugen_ambiguous_zeile():
    """AC-3: Given zwei GPX-Kandidaten, die BEIDE jeden Wegpunkt treffen,
    aber zu unterschiedlichen Wegstrecken führen (der zweite nimmt zwischen
    G3 und G4 einen Umweg) / When die Auflösung läuft / Then entsteht eine
    Zeile mit ``reason="ambiguous_result"`` und der maximalen Abweichung in
    Metern."""
    from core.gpx_parser import parse_gpx
    from services.track_resolution import _match_track, _normalisiert

    uid = "tdd-2073-s2-ac3"
    gpx_dir = _gpx_dir(uid)
    gerade = _gitter()
    _gpx_schreiben(gpx_dir / "a_direkt.gpx", gerade)
    # Umweg: ein zusätzlicher Punkt weit östlich zwischen Index 10 und 11 --
    # verlängert die Strecke zu G4, ohne je nächstgelegener Punkt eines
    # Wegpunkts zu werden (er liegt > 1,5 km von jedem Wegpunkt entfernt).
    umweg = gerade[:11] + [(47.105, 12.02, 1010.0)] + gerade[11:]
    _gpx_schreiben(gpx_dir / "b_umweg.gpx", umweg)

    waypoints = _waypoints()
    trip = _trip(uid, waypoints)

    # Erwartungswert aus den ECHTEN geparsten Tracks ableiten, nicht raten.
    treffer = [
        _match_track(waypoints, parse_gpx(p).points, 10.0)
        for p in sorted(gpx_dir.glob("*.gpx"))
    ]
    assert all(t is not None for t in treffer), (
        "Vorbedingung verletzt: beide Kandidaten müssen JEDEN Wegpunkt "
        "treffen, sonst prüft der Test 'kein Treffer' statt 'mehrdeutig'"
    )
    norm = [_normalisiert(t, waypoints) for t in treffer]
    erwartet_m = max(abs(a - b) for a, b in zip(norm[0], norm[1])) * 1000.0
    assert erwartet_m > 1000.0, (
        f"Testdaten degeneriert: Abweichung nur {erwartet_m:.1f} m"
    )

    _lauf(uid, trip)

    zeilen = _journal(uid)
    assert len(zeilen) == 1, f"genau eine Journalzeile erwartet, bekam: {zeilen}"
    _pruefe_grundfelder(zeilen[0], trip_id=trip.id, reason="ambiguous_result")
    assert float(zeilen[0]["detail"]) == pytest.approx(erwartet_m, rel=0.02), (
        f"detail soll die maximale Abweichung in Metern tragen "
        f"(erwartet ~{erwartet_m:.0f} m): {zeilen[0]}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Erfolg schweigt (mit Positivkontrolle)
# ---------------------------------------------------------------------------

def test_erfolgreiche_aufloesung_erzeugt_keine_zeile():
    """AC-4: Given eine Etappe, deren Track sich eindeutig auflösen lässt /
    When ``backfill_stage_distances`` erfolgreich vermisst / Then bleibt das
    Journal leer.

    Positivkontrolle im selben Testkörper: derselbe Aufbau mit einem um
    111 m verschobenen Wegpunkt schreibt sehr wohl eine Zeile.
    """
    uid_ok = "tdd-2073-s2-ac4-ok"
    _gpx_schreiben(_gpx_dir(uid_ok) / "route.gpx", _gitter())
    ergebnis = _lauf(uid_ok, _trip(uid_ok, _waypoints()))

    assert all(wp.distance_from_start_km is not None
               for wp in ergebnis.stages[0].waypoints), (
        "Vorbedingung verletzt: die Auflösung war gar nicht erfolgreich"
    )

    uid_fehler = "tdd-2073-s2-ac4-fehler"
    _lauf(uid_fehler, _fall_ein_wegpunkt_daneben(uid_fehler, 111.0))
    assert len(_journal(uid_fehler)) == 1, (
        "Positivkontrolle gescheitert: auch der Fehlschlag erzeugt keine "
        "Zeile — das leere Journal des Erfolgsfalls beweist damit nichts"
    )

    assert _journal(uid_ok) == [], (
        f"erfolgreiche Auflösung darf nichts protokollieren: {_journal(uid_ok)}"
    )


# ---------------------------------------------------------------------------
# AC-5 — der bestehende Prozess-Cache dämpft weiterhin
# ---------------------------------------------------------------------------

def test_zweiter_versuch_im_selben_prozess_erzeugt_keine_zweite_zeile():
    """AC-5: Given eine Etappe, deren Auflösung im selben Prozess bereits
    fehlgeschlagen ist / When ein zweiter Versuch mit identischen Argumenten
    läuft / Then bleibt es bei genau einer Journalzeile.

    Zwischen den beiden Aufrufen wird ``_failed_lookups`` BEWUSST nicht
    geleert — die Dämpfung selbst ist hier der Prüfgegenstand.
    """
    uid = "tdd-2073-s2-ac5"
    trip = _fall_ein_wegpunkt_daneben(uid, 111.0)

    _lauf(uid, trip)
    assert len(_journal(uid)) == 1, (
        f"schon der ERSTE Lauf schreibt keine Zeile: {_journal(uid)}"
    )

    _lauf(uid, trip)
    assert len(_journal(uid)) == 1, (
        f"der Cache dämpft nicht — zweite Zeile entstanden: {_journal(uid)}"
    )


# ---------------------------------------------------------------------------
# AC-6 — der Vorschau-Pfad hinterlässt nichts (mit Positivkontrolle)
# ---------------------------------------------------------------------------

def test_vorschau_pfad_ohne_persistenz_erzeugt_keine_zeile():
    """AC-6: Given eine Etappe, deren Auflösung scheitert / When
    ``persist=False`` (Vorschau) / Then entsteht keine Journalzeile.

    Positivkontrolle: derselbe Fehlschlag mit ``persist=True`` schreibt eine.
    Zwei getrennte Nutzer sind Pflicht — ``_failed_lookups`` wird auch im
    Vorschau-Pfad gefüllt und würde den zweiten Lauf sonst kurzschließen.
    """
    uid_vorschau = "tdd-2073-s2-ac6-vorschau"
    _lauf(uid_vorschau, _fall_ein_wegpunkt_daneben(uid_vorschau, 111.0),
          persist=False)

    uid_versand = "tdd-2073-s2-ac6-versand"
    _lauf(uid_versand, _fall_ein_wegpunkt_daneben(uid_versand, 111.0))

    assert len(_journal(uid_versand)) == 1, (
        "Positivkontrolle gescheitert: auch mit persist=True entsteht keine "
        "Zeile — das leere Vorschau-Journal beweist damit nichts"
    )
    assert _journal(uid_vorschau) == [], (
        f"eine Vorschau darf nichts hinterlassen: {_journal(uid_vorschau)}"
    )


# ---------------------------------------------------------------------------
# AC-7 — Mandantentrennung
# ---------------------------------------------------------------------------

def test_journale_zweier_nutzer_bleiben_getrennt():
    """AC-7: Given zwei verschiedene Nutzer mit je einem Fehlschlag / When
    beide Auflösungen laufen / Then liegt jede Zeile ausschließlich im
    Diagnose-Verzeichnis des eigenen Nutzers, ohne Vermischung."""
    uid_a, uid_b = "tdd-2073-s2-ac7-anna", "tdd-2073-s2-ac7-bodo"
    _gpx_schreiben(_gpx_dir(uid_a) / "route.gpx", _gitter())
    _gpx_schreiben(_gpx_dir(uid_b) / "route.gpx", _gitter())
    trip_a = _trip(uid_a, _waypoints({2: 111.0}), trip_id="tour-anna")
    trip_b = _trip(uid_b, _waypoints({2: 111.0}), trip_id="tour-bodo")

    _lauf(uid_a, trip_a)
    _lauf(uid_b, trip_b)

    zeilen_a, zeilen_b = _journal(uid_a), _journal(uid_b)
    assert [z["trip_id"] for z in zeilen_a] == ["tour-anna"], zeilen_a
    assert [z["trip_id"] for z in zeilen_b] == ["tour-bodo"], zeilen_b

    from app.loader import get_data_root

    global_journal = get_data_root() / "diagnostics" / _JOURNAL_DATEI
    assert not global_journal.exists(), (
        f"das Journal gehört unter data/users/<uid>/, nie global: {global_journal}"
    )


# ---------------------------------------------------------------------------
# AC-8 — Fail-soft bei nicht beschreibbarem Diagnose-Verzeichnis
# ---------------------------------------------------------------------------

@pytest.mark.skipif(os.geteuid() == 0, reason="als root greift kein Schreibschutz")
def test_nicht_beschreibbares_diagnoseverzeichnis_bleibt_folgenlos(caplog):
    """AC-8: Given das Diagnose-Verzeichnis ist nicht beschreibbar / When die
    Auflösung fehlschlägt und protokollieren will / Then liefert
    ``backfill_stage_distances`` unverändert den unvermessenen Trip, kein
    Fehler dringt nach außen.

    Zusätzlich zur Rückgabe wird das LOG geprüft: schlüge der Schreibfehler
    bis zum äußeren ``except Exception`` in ``backfill_stage_distances``
    durch, erschiene dessen Warnung ("Etappe bleibt unvermessen"). Ohne diese
    Unterscheidung wäre der Test wertlos — der äußere Fänger liefert
    denselben Rückgabewert, und die Zusicherung "fail-soft IM SCHREIBER"
    bliebe ungeprüft.
    """
    from app.loader import get_data_dir

    uid = "tdd-2073-s2-ac8"
    trip = _fall_ein_wegpunkt_daneben(uid, 111.0)
    diag = get_data_dir(uid) / "diagnostics"
    diag.mkdir(parents=True, exist_ok=True)
    diag.chmod(0o500)
    try:
        with caplog.at_level(logging.WARNING):
            ergebnis = _lauf(uid, trip)
    finally:
        diag.chmod(0o700)

    assert all(wp.distance_from_start_km is None
               for wp in ergebnis.stages[0].waypoints)
    assert [s.id for s in ergebnis.stages] == [s.id for s in trip.stages]
    assert _journal(uid) == [], "Vorbedingung: nichts konnte geschrieben werden"
    durchgeschlagen = [
        r.getMessage() for r in caplog.records
        if "Etappe bleibt" in r.getMessage()
    ]
    assert durchgeschlagen == [], (
        "der Schreibfehler ist bis zum äußeren Fänger von "
        f"backfill_stage_distances durchgeschlagen: {durchgeschlagen}"
    )
    geloggt = [
        r.getMessage() for r in caplog.records
        if _JOURNAL_DATEI in r.getMessage() or "Diagnose" in r.getMessage()
    ]
    assert geloggt, (
        "der Schreibfehler wurde stillschweigend verschluckt — fail-soft "
        f"heißt gefangen UND geloggt: {[r.getMessage() for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# AC-9 — bereits vermessen, aber unplausibel
# ---------------------------------------------------------------------------

def test_unplausibel_vermessene_etappe_erzeugt_implausible_zeile():
    """AC-9: Given eine Etappe mit bereits gespeicherten, aber unplausiblen
    Distanzen (G1->G2 sind 5,5 km Luftlinie, gespeichert sind 100 m) / When
    ``backfill_stage_distances`` den Kurzschluss "bereits vermessen" nimmt /
    Then entsteht eine Zeile mit ``reason="implausible_measurement"``.

    Das Kriterium wird NICHT nachgebaut: die Vorbedingung wird gegen die
    eine vorhandene Definition ``trip_segments.stage_measured_distances``
    geprüft.
    """
    from services.trip_segments import stage_measured_distances

    uid = "tdd-2073-s2-ac9"
    waypoints = _waypoints(distanzen=[0.0, 0.1, 0.2, 0.3])
    assert stage_measured_distances(waypoints) is None, (
        "Vorbedingung verletzt: diese Distanzen gelten als plausibel"
    )
    trip = _trip(uid, waypoints)

    _lauf(uid, trip)

    zeilen = _journal(uid)
    assert len(zeilen) == 1, f"genau eine Journalzeile erwartet, bekam: {zeilen}"
    _pruefe_grundfelder(zeilen[0], trip_id=trip.id,
                        reason="implausible_measurement")
    assert zeilen[0].get("detail") not in (None, ""), (
        f"auch hier gehört ein Grund-Detail in die Zeile: {zeilen[0]}"
    )


# ---------------------------------------------------------------------------
# AC-6 an der ZWEITEN Einhängestelle (Adversary-Finding F001)
#
# Der AC-6-Test oben fährt ausschließlich über Stelle 1 ("Auflösung
# gescheitert"). Die `if persist:`-Wache vor der Meldung an Stelle 2 ("bereits
# vermessen, aber unplausibel") war damit ungetestet: entfernt man sie, bleiben
# alle Tests grün. AC-6 gilt aber für BEIDE Stellen — eine Vorschau darf auch
# hier nichts hinterlassen.
# ---------------------------------------------------------------------------

def test_vorschau_pfad_meldet_auch_unplausible_messung_nicht():
    """AC-6 (Stelle 2): Given eine bereits vermessene Etappe mit unplausiblen
    Distanzen — derselbe Aufbau wie AC-9 / When ``persist=False`` (Vorschau) /
    Then entsteht keine Journalzeile.

    Positivkontrolle im selben Testkörper (Pflicht): derselbe Aufbau mit
    ``persist=True`` schreibt sehr wohl eine Zeile. Ohne diesen Gegenbeweis
    wäre die 0 auch dann grün, wenn Stelle 2 überhaupt nicht meldete.
    Zwei getrennte Nutzer, damit sich die Journale nicht vermischen.
    """
    from services.trip_segments import stage_measured_distances

    waypoints = _waypoints(distanzen=[0.0, 0.1, 0.2, 0.3])
    assert stage_measured_distances(waypoints) is None, (
        "Vorbedingung verletzt: diese Distanzen gelten als plausibel — dann "
        "prüft der Test nicht Stelle 2"
    )

    uid_vorschau = "tdd-2073-s2-f001-vorschau"
    _lauf(uid_vorschau, _trip(uid_vorschau, waypoints), persist=False)

    uid_versand = "tdd-2073-s2-f001-versand"
    _lauf(uid_versand, _trip(uid_versand, _waypoints(distanzen=[0.0, 0.1, 0.2, 0.3])))

    zeilen_versand = _journal(uid_versand)
    assert len(zeilen_versand) == 1, (
        "Positivkontrolle gescheitert: auch mit persist=True meldet Stelle 2 "
        f"nichts — das leere Vorschau-Journal beweist damit nichts: {zeilen_versand}"
    )
    assert zeilen_versand[0]["reason"] == "implausible_measurement", zeilen_versand
    assert _journal(uid_vorschau) == [], (
        "eine Vorschau darf auch bei unplausibel vermessener Etappe nichts "
        f"hinterlassen: {_journal(uid_vorschau)}"
    )


# ---------------------------------------------------------------------------
# AC-14 — Grenzwert-Wächter der Melderegel
#
# Zwei Ebenen, weil keine allein reicht:
#   (a) die Melderegel SELBST, mit exakten Zahlen statt Geometrie — nur so ist
#       der von AC-14 wörtlich verlangte INKLUSIVE Grenzfall "genau 1 km"
#       prüfbar. Eine Bisektion trifft nie exakt 1000,000 m; ein Vergleich auf
#       die Konstante (``FAILURE_REPORT_TOLERANCE_KM == 1.0``) prüft eine Zahl
#       statt eines Verhaltens und bliebe grün, wenn die Regel ``<`` statt
#       ``<=`` benutzt — also genau im Grenzfall.
#   (b) derselbe Grenzwert im ECHTEN Aufrufpfad. Ebene (a) allein bewiese
#       nicht, dass ``backfill_stage_distances`` die Regel überhaupt erreicht.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("abstand_km,meldewuerdig", [
    (0.0, True),        # Volltreffer-Nähe -- immer eine Nachricht wert
    (0.999, True),      # klar innerhalb
    (1.0, True),        # DIE inklusive Grenze (AC-14 wörtlich)
    (1.000001, False),  # kleinster Schritt darüber -- Schweigen
    (4.0, False),       # klar darüber
])
def test_melderegel_meldet_die_grenze_von_genau_einem_kilometer(
    abstand_km, meldewuerdig,
):
    """AC-14 (Regel-Ebene): Given ein bester Kandidatenabstand an, unter oder
    über der Meldegrenze / When die Melderegel angewendet wird / Then gilt
    genau 1 km noch als meldewürdig, alles darüber nicht.

    ``1.0 -> True`` ist der eigentliche Prüfgegenstand: er trennt ``<=`` von
    ``<``. ``1.000001 -> False`` schließt die Grenze von der anderen Seite ein.
    """
    from services.track_resolution_health import fehlschlag_ist_meldewuerdig

    assert fehlschlag_ist_meldewuerdig(abstand_km) is meldewuerdig


@pytest.mark.parametrize("versatz_m,erwartete_zeilen", [
    (999.9, 1),    # knapp innerhalb der Meldegrenze -> Nachricht
    (1000.1, 0),   # knapp darüber -> Schweigen
    (4000.0, 0),   # klar darüber (AC-14 Beispielwert) -> Schweigen
])
def test_meldegrenze_wirkt_im_echten_aufloesungspfad(versatz_m, erwartete_zeilen):
    """AC-14 (Pfad-Ebene): Given ein GPX-Bestand, dessen bester Kandidat
    999,9 / 1000,1 / 4000,0 m neben der Route liegt / When
    ``backfill_stage_distances`` läuft / Then entsteht 1 bzw. 0 Journalzeilen.

    Hier bewusst KEIN Grenzfall auf 1000,000 m: Bisektion und Rundung der
    geschriebenen GPX-Koordinaten arbeiten auf Millimeter-Ebene, eine
    Messerschneide wäre flatterhaft. Das Paar 999,9 / 1000,1 klemmt die im
    Produktionspfad WIRKSAME Grenze auf +/- 0,1 m ein; der exakte Grenzfall
    steckt im Regel-Test darüber. Die Zusicherung unten hält beide Ebenen
    zusammen — sonst könnte der Pfad eine zweite, abweichende Regel benutzen.
    """
    from services.track_resolution_health import fehlschlag_ist_meldewuerdig

    assert fehlschlag_ist_meldewuerdig(versatz_m / 1000.0) is (erwartete_zeilen == 1), (
        "Regel und Pfad-Erwartung widersprechen sich -- einer von beiden "
        "prüft die falsche Grenze"
    )

    uid = f"tdd-2073-s2-ac14-{int(versatz_m * 10)}"
    _lauf(uid, _fall_ganzer_track_versetzt(uid, versatz_m))

    zeilen = _journal(uid)
    assert len(zeilen) == erwartete_zeilen, (
        f"bester Kandidat {versatz_m} m entfernt: {erwartete_zeilen} Zeile(n) "
        f"erwartet, bekam {len(zeilen)} — {zeilen}"
    )
