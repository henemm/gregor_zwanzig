"""Track-Auflösung fuer Bestandstrips ohne gemessene Wegstrecke (Issue #2036).

Wegpunkte importierter Etappen SIND Original-Trackpunkte -- gemessener
Abstand 0,0 m. Liegt der zugehoerige GPX-Track noch im Bestand des Nutzers
(``data/users/<user_id>/gpx/``), laesst sich die beim Import verworfene
Wegstrecke deshalb eindeutig nachtragen, statt sie aus Luftlinie zu
schaetzen.

Zwei Regeln machen das Nachtragen belastbar statt raterisch:

* **Vollstaendigkeit** -- ein Track passt nur, wenn er JEDEN Wegpunkt der
  Etappe innerhalb der Toleranz enthaelt. Ein einziger manuell verschobener
  oder ergaenzter Wegpunkt (>10 m abseits) laesst die GANZE Etappe
  unvermessen (AC-12).
* **Ergebnisgleichheit** -- passen mehrere Dateien, entscheidet nicht ihre
  ANZAHL, sondern ob sie zu derselben Wegstrecke fuehren: liefern alle
  Kandidaten je Wegpunkt dieselben (auf den Etappenstart normierten)
  Kilometer, darf die Aufloesung sich entscheiden; erst bei wirklich
  abweichenden Ergebnissen wird KEINE geraten (Issue #2073, vorher AC-11 aus
  #2036: "mehr als eine passende Datei" genuegte fuer den Abbruch, womit eine
  blosse Kopie derselben Datei die Etappe unnoetig ausfallen liess).

Ohne verwertbaren Treffer liefert die Auflösung ``None``; die Ortsangabe
bleibt dann byte-identisch bei ``Segment N`` (AC-10).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from utils.geo import haversine_km

logger = logging.getLogger("track_resolution")

# Toleranz Wegpunkt <-> Trackpunkt. Original-Trackpunkte liegen bei 0,0 m,
# die naechstbeste (falsche) Datei im gemessenen Bestand bei >= 4.672 m --
# 10 m deckt Koordinatenrundung ab und liegt drei Groessenordnungen unter
# dem Fehlerfall (Spec "Festgelegte Schwellenwerte").
DEFAULT_TOLERANCE_M = 10.0

# Hoechstabstand, bis zu dem zwei Kandidaten als ergebnisgleich gelten
# (Issue #2073). Bewusst von der Zuordnungstoleranz ABGELEITET statt neu
# hingeschrieben: verglichen wird derselbe Ortsabstand, es gibt nur EINE
# 10-m-Zahl im Modul.
RESULT_EQUALITY_TOLERANCE_M = DEFAULT_TOLERANCE_M


def _match_track(
    waypoints: List, points: List, tolerance_m: float,
    *, out: Optional[Dict[str, float]] = None,
) -> Optional[Dict[str, float]]:
    """Distanz je Wegpunkt aus DIESEM Track -- oder ``None``, wenn auch nur
    ein Wegpunkt weiter als die Toleranz vom naechstgelegenen Trackpunkt
    entfernt liegt (alles oder nichts, AC-12).

    Args:
        out: optionaler Ausgabebeutel (Issue #2073 S2). Scheitert die
            Zuordnung, landet unter ``"miss_km"`` der Abstand des ERSTEN
            Wegpunkts jenseits der Toleranz -- die Schleife kehrt dort um und
            kennt damit nur eine UNTERGRENZE des schlechtesten Abstands. Er
            genuegt fuer die Melderegel, die nur wissen muss, ob dieser
            Kandidat ueberhaupt plausibel zur Route gehoert. Additiv: ohne
            ``out`` ist das Verhalten unveraendert (Bestandsaufrufer).
    """
    result: Dict[str, float] = {}
    for wp in waypoints:
        best_km: Optional[float] = None
        best_dist: Optional[float] = None
        for pt in points:
            d = haversine_km(wp.lat, wp.lon, pt.lat, pt.lon)
            if best_dist is None or d < best_dist:
                best_dist = d
                best_km = pt.distance_from_start_km
        if best_dist is None or best_dist * 1000.0 > tolerance_m:
            if out is not None and best_dist is not None:
                out["miss_km"] = best_dist
            return None
        result[wp.id] = best_km
    return result


def _normalisiert(hit: Dict[str, float], waypoints: List) -> List[float]:
    """Wegpunkt-Kilometer eines Kandidaten, auf den Etappenstart normiert.

    ``distance_from_start_km`` kumuliert ab dem Anfang des jeweiligen GPX-
    Tracks, nicht ab dem Etappenstart: eine Einzeletappen-GPX beginnt bei
    0 km, eine durchlaufende Gesamt-Tour-GPX fuer dieselbe Etappe z. B. bei
    50 km. Verglichen wird deshalb dasselbe, was der Nutzer spaeter sieht --
    ``trip_segments.stage_measured_distances`` (:150-151) normiert genauso.
    """
    werte = [hit[wp.id] for wp in waypoints]
    return [w - werte[0] for w in werte]


def _ergebnisse_sind_gleich(
    matches: List[Dict[str, float]], waypoints: List,
    *, out: Optional[Dict[str, float]] = None,
) -> bool:
    """Liefern ALLE Kandidaten praktisch dieselbe Wegstrecke (Issue #2073)?

    Geprueft wird PAARWEISE ueber alle ``n*(n-1)/2`` Paare, nicht gegen einen
    Referenzkandidaten: bei einer harten Schwelle ist Gleichheit nicht
    transitiv. Laege B 9 m ueber A und C 9 m unter A, bestuenden beide den
    Referenzvergleich gegen A, laegen aber 18 m auseinander -- das wuerde die
    Toleranz stillschweigend verdoppeln.

    Args:
        out: optionaler Ausgabebeutel (Issue #2073 S2) -- nimmt unter
            ``"abweichung_km"`` die GROESSTE Abweichung ueber alle Paare auf.
            Deshalb laeuft die Schleife durch, statt beim ersten Verstoss
            umzukehren; der Rueckgabewert ist derselbe (das Maximum ueber alle
            Paare ueberschreitet die Grenze genau dann, wenn irgendein Paar
            sie ueberschreitet), und die Kandidatenzahl je Etappe ist klein.
    """
    normiert = [_normalisiert(hit, waypoints) for hit in matches]
    grenze_km = RESULT_EQUALITY_TOLERANCE_M / 1000.0
    groesste_abweichung_km = 0.0
    for i in range(len(normiert)):
        for j in range(i + 1, len(normiert)):
            for a, b in zip(normiert[i], normiert[j]):
                groesste_abweichung_km = max(groesste_abweichung_km, abs(a - b))
    if out is not None:
        out["abweichung_km"] = groesste_abweichung_km
    return groesste_abweichung_km <= grenze_km


def resolve_stage_track_km(
    stage, gpx_dir, tolerance_m: float = DEFAULT_TOLERANCE_M,
    *, out: Optional[Dict[str, object]] = None,
) -> Optional[Dict[str, float]]:
    """Gemessene Wegstrecke je Wegpunkt der Etappe aus dem GPX-Bestand.

    Args:
        stage: Etappe mit ``waypoints`` (je ``id``/``lat``/``lon``).
        gpx_dir: Verzeichnis des Nutzer-GPX-Bestands.
        tolerance_m: Hoechstabstand Wegpunkt <-> Trackpunkt in Metern.
        out: optionaler Ausgabebeutel (Issue #2073 S2). Scheitert die
            Aufloesung, traegt er ``"reason"`` (Gruende-Vokabular aus
            ``track_resolution_health``), ``"detail"`` (Abstand bzw.
            Abweichung in METERN) und bei fehlendem Treffer zusaetzlich
            ``"best_distance_km"`` fuer die Melderegel. Additiv: ohne ``out``
            ist das Verhalten unveraendert.

    Returns:
        ``{waypoint_id: distance_from_start_km}``, sobald alle passenden
        Tracks dieselbe Wegstrecke liefern -- die ROHEN, unnormierten Werte
        des ersten Kandidaten in ``sorted(...)``-Reihenfolge (die Normierung
        ist ausschliesslich Vergleichs-Hilfsmittel, kein Rueckgabeformat).
        Sonst ``None`` (kein Treffer, abweichende Ergebnisse, oder mindestens
        ein Wegpunkt abseits).
    """
    from core.gpx_parser import parse_gpx

    waypoints = list(getattr(stage, "waypoints", None) or [])
    directory = Path(gpx_dir)
    if not waypoints or not directory.is_dir():
        return None

    matches: List[Dict[str, float]] = []
    bester_abstand_km: Optional[float] = None
    for path in sorted(directory.glob("*.gpx")):
        try:
            track = parse_gpx(path)
        except Exception as e:
            logger.warning(
                "Track-Aufloesung: %s nicht lesbar, uebersprungen (%s)",
                path.name, e,
            )
            continue
        probe: Dict[str, float] = {}
        hit = _match_track(waypoints, track.points or [], tolerance_m, out=probe)
        if hit is not None:
            matches.append(hit)
            continue
        verfehlt_km = probe.get("miss_km")
        if verfehlt_km is not None and (
            bester_abstand_km is None or verfehlt_km < bester_abstand_km
        ):
            bester_abstand_km = verfehlt_km
    if not matches:
        if out is not None and bester_abstand_km is not None:
            out["reason"] = "no_candidate_within_tolerance"
            out["detail"] = round(bester_abstand_km * 1000.0, 1)
            out["best_distance_km"] = bester_abstand_km
        return None
    vergleich: Dict[str, float] = {}
    if not _ergebnisse_sind_gleich(matches, waypoints, out=vergleich):
        if out is not None:
            out["reason"] = "ambiguous_result"
            out["detail"] = round(vergleich.get("abweichung_km", 0.0) * 1000.0, 1)
        return None  # widerspruechliche Ergebnisse -- nicht raten (#2073)
    return matches[0]


# Etappen, fuer die in DIESEM Prozess bereits erfolglos gesucht wurde. Ohne
# diese Sperre parst jeder Alarmlauf den kompletten GPX-Bestand des Nutzers
# neu, obwohl das Ergebnis feststeht -- der Lauf hat eine Zeitobergrenze.
# Ein Neustart (oder ein frisch hochgeladener Track nach einem Neustart)
# hebt sie auf; das ist die "lazy"-Grenze aus den Known Limitations der Spec.
_failed_lookups: set = set()

# Grund-Freitext fuer Stelle 2 (bereits vermessen, aber unplausibel). Anders
# als bei den beiden Aufloesungs-Gruenden gibt es hier keine einzelne Zahl:
# `stage_measured_distances` verwirft die Etappe, sobald IRGENDEIN Paar gegen
# Monotonie oder Luftlinie verstoesst, und sagt nicht, welches.
_IMPLAUSIBLE_DETAIL = (
    "gespeicherte Wegpunkt-Distanzen unplausibel (nicht streng monoton oder "
    "kuerzer als die Luftlinie)"
)


def _melde_unplausible_messung(trip, stage, user_id: str) -> None:
    """Stelle 2: die Etappe gilt als vermessen, ihre Werte taugen aber nicht.

    Das Kriterium wird NICHT nachgebaut, sondern bei der einen vorhandenen
    Definition erfragt (``trip_segments.stage_measured_distances``): liefert
    sie ``None``, obwohl jeder Wegpunkt einen Wert traegt, ist genau dieser
    Fall erkannt. Eine zweite Kopie der Regel liefe beim naechsten
    Schwellen-Wechsel still auseinander.

    Bewusst OHNE eigene Daempfung: wie beim Zwilling
    ``alert_anchor_rejected.jsonl`` ist jede Zeile die Beobachtung EINES
    Laufs; genau daraus waechst das Betreiber-Signal.
    """
    from services.track_resolution_health import record_track_resolution_failure
    from services.trip_segments import stage_measured_distances

    if stage_measured_distances(list(stage.waypoints)) is not None:
        return
    record_track_resolution_failure(
        user_id=user_id, trip_id=trip.id, stage_id=stage.id,
        reason="implausible_measurement", detail=_IMPLAUSIBLE_DETAIL,
    )


def _melde_fehlschlag(trip, stage, user_id: str, diagnose: Dict[str, object]) -> None:
    """Stelle 1: die Aufloesung ist gescheitert und kennt den Grund.

    Gemeldet wird nur, wenn der beste Kandidat plausibel zu dieser Route
    gehoert (Melderegel, ``fehlschlag_ist_meldewuerdig``). Bei
    ``ambiguous_result`` entfaellt die Pruefung: dort haben ALLE Kandidaten
    jeden Wegpunkt innerhalb der 10-m-Zuordnungstoleranz getroffen und liegen
    damit zwei Groessenordnungen unter der Meldegrenze.
    """
    from services.track_resolution_health import (
        fehlschlag_ist_meldewuerdig,
        record_track_resolution_failure,
    )

    grund = diagnose.get("reason")
    if grund is None:
        return
    if grund == "no_candidate_within_tolerance" and not fehlschlag_ist_meldewuerdig(
        float(diagnose.get("best_distance_km"))
    ):
        return
    record_track_resolution_failure(
        user_id=user_id, trip_id=trip.id, stage_id=stage.id,
        reason=str(grund), detail=diagnose.get("detail"),
    )


def backfill_stage_distances(
    trip, user_id: str, target_date, *, persist: bool = True,
) -> object:
    """Traegt die gemessene Wegstrecke der Etappe zu ``target_date`` einmalig
    nach und schreibt sie additiv an den Trip zurueck (Issue #2036 AC-7).

    Der Rueckschreibweg ist ``save_trip`` -- Read-Modify-Write mit Merge
    (``loader._deep_merge_preserve_unknown``); Felder, die Python nicht
    modelliert (Go-/Legacy-Felder), bleiben erhalten. Betroffen ist NUR die
    eine Etappe: die uebrigen Wegpunkte werden unveraendert durchgereicht.

    Fail-soft: jeder Fehler laesst den Trip unveraendert -- eine fehlende
    Kilometerangabe ist ein Schoenheitsfehler, ein ausgefallener Alarm nicht.

    Args:
        persist: Bei ``False`` (Issue #2036 CI-Nachschlag, PR #2055) wird die
            aufgeloeste Distanz nur INS RUECKGABEOBJEKT geschrieben, nicht
            via ``save_trip`` auf die Platte. Fuer reine Vorschau-Pfade
            (``PreviewService`` -- "kein Versand, nur Render"): eine Ansicht
            darf den Trip-Bestand nicht als Seiteneffekt veraendern, egal
            welcher ``user_id`` sie zugerechnet wird. Alarm- und
            Briefing-Versandpfade lassen den Default (persistieren).

    Returns:
        Den (ggf. ergaenzten) Trip -- immer ein verwendbares Objekt.
    """
    try:
        import dataclasses

        from app.loader import get_data_dir

        stage = trip.get_stage_for_date(target_date)
        if stage is None or not stage.waypoints:
            return trip
        if all(
            getattr(wp, "distance_from_start_km", None) is not None
            for wp in stage.waypoints
        ):
            if persist:
                _melde_unplausible_messung(trip, stage, user_id)
            return trip  # bereits vermessen -- nichts zu tun
        key = (user_id, trip.id, stage.id)
        if key in _failed_lookups:
            return trip
        diagnose: Dict[str, object] = {}
        distances = resolve_stage_track_km(
            stage, get_data_dir(user_id) / "gpx", out=diagnose,
        )
        if distances is None or any(
            wp.id not in distances for wp in stage.waypoints
        ):
            _failed_lookups.add(key)
            # Nur der Versandpfad protokolliert (Issue #2073 S2): eine reine
            # Vorschau darf keine Spur hinterlassen. Die Daempfung ueber
            # `_failed_lookups` gilt weiter -- hoechstens EINE Zeile je Etappe
            # und Prozess, ohne neue Daempfungslogik.
            if persist:
                _melde_fehlschlag(trip, stage, user_id, diagnose)
            return trip
        new_stage = dataclasses.replace(stage, waypoints=[
            dataclasses.replace(wp, distance_from_start_km=distances[wp.id])
            for wp in stage.waypoints
        ])
        updated = dataclasses.replace(trip, stages=[
            new_stage if s.id == stage.id else s for s in trip.stages
        ])
        if persist:
            from app.loader import save_trip

            save_trip(updated, user_id=user_id)
        logger.info(
            "Track-Aufloesung: Etappe %s von Trip %s nachtraeglich vermessen "
            "(%d Wegpunkte, persist=%s)", stage.id, trip.id, len(distances), persist,
        )
        return updated
    except Exception as e:
        logger.warning(
            "Track-Aufloesung fuer Trip %s fehlgeschlagen, Etappe bleibt "
            "unvermessen (%s)", getattr(trip, "id", "?"), e,
        )
        return trip
