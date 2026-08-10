"""
Shared segment helper — extracts trip waypoints into TripSegment DTOs.

Issue #822: SSoT for segment conversion, shared between briefing
(TripReportSchedulerService) and radar alert (TripAlertService).

Extracted 1:1 from TripReportSchedulerService._convert_trip_to_segments
so that the briefing behaviour is bit-identical after the refactor.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, List, Optional

from app.day_window import resolve_configured_window
from app.models import GPXPoint, TripSegment
from utils.geo import haversine_km
from utils.timezone import tz_for_coords

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger("trip_segments")


def _parse_hhmm(value: str) -> Optional[time]:
    """Parse 'HH:MM' to a time object; returns None on malformed input."""
    try:
        return time.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _known_time_for_index(
    waypoints: List, idx: int, stage, default_start: time
) -> Optional[time]:
    """Massgebliche Startzeit eines Wegpunkts nach der #1004-Prioritaetskette
    (arrival_override > stage.start_time bei idx==0 > arrival_calculated >
    Default bei idx==0) — ``None`` wenn keine dieser Quellen greift."""
    wp = waypoints[idx]
    override_str = getattr(wp, "arrival_override", None)
    override = _parse_hhmm(override_str) if override_str else None
    if override is not None:
        return override
    if idx == 0 and stage.start_time:
        return stage.start_time
    calculated_str = wp.arrival_calculated
    calculated = _parse_hhmm(calculated_str) if calculated_str else None
    if calculated is not None:
        return calculated
    if idx == 0:
        return default_start
    return None


def _interpolate_missing_times(known_times: List[Optional[time]]) -> List[Optional[time]]:
    """Issue #1004/F001: lineare Interpolation fuer Wegpunkte ohne
    ``arrival_override``/``arrival_calculated`` zwischen zwei bekannten
    Zeitpunkten. Bei k aufeinanderfolgenden Unbekannten wird das Intervall
    gleichmaessig in k+1 Schritte geteilt (monotone Zeitfolge statt stiller
    Duplikat-Startzeit).

    Issue #1091: Rechnet mit vollen datetime-Objekten, damit fallende
    Zeitangaben ueber die Tagesgrenze (z. B. 22:00 -> 00:30) korrekt als
    naechster Tag interpretiert werden und die Zwischenzeiten monoton bleiben.
    Fehlt ein bekannter Zeitpunkt danach, bleibt die Luecke offen — der
    bestehende cumulative_time-Fallback greift dann."""
    result = list(known_times)
    n = len(result)
    i = 1
    while i < n:
        if result[i] is not None:
            i += 1
            continue
        gap_start = i
        while i < n and result[i] is None:
            i += 1
        gap_end = i
        prev_time = result[gap_start - 1]
        if gap_end < n and prev_time is not None:
            next_time = result[gap_end]
            # Issue #1091: Mit vollen datetime rechnen, damit eine fallende
            # Uhrzeit ueber Mitternacht (next < prev) als naechster Tag gilt.
            base = datetime(2000, 1, 1, prev_time.hour, prev_time.minute)
            nxt = datetime(2000, 1, 1, next_time.hour, next_time.minute)
            if nxt < base:
                nxt += timedelta(days=1)
            span_minutes = (nxt - base).total_seconds() / 60
            steps = gap_end - gap_start + 1
            # F002: kaufmaennische Rundung statt Python-Banker's-Rounding —
            # round(0.5) wuerde auf 0 abrunden und den interpolierten Punkt
            # auf die Vorgaengerzeit kollabieren lassen. Bei span < steps
            # (mehr Luecken als Minuten Spanne) sind Duplikate in Minuten-
            # aufloesung unvermeidbar; die betroffenen Segmente kollabieren
            # dann geloggt am end_dt<=start_dt-Guard (Grenzverhalten wie
            # die Mitternachts-Klemme in AC-5), nicht still.
            for offset, idx in enumerate(range(gap_start, gap_end), start=1):
                interpolated = base + timedelta(
                    minutes=math.floor(span_minutes * offset / steps + 0.5)
                )
                result[idx] = interpolated.time()
    return result


def convert_trip_to_segments(trip: "Trip", target_date: date) -> List[TripSegment]:
    """Convert Trip waypoints to TripSegment DTOs for a given date.

    Extracted 1:1 from TripReportSchedulerService._convert_trip_to_segments.
    Briefing behaviour is bit-identical (AC-1 roundtrip guarantee).

    Returns an empty list when:
    - No stage matches target_date
    - Stage has fewer than 2 waypoints
    """
    stage = trip.get_stage_for_date(target_date)
    if stage is None:
        return []

    if len(stage.waypoints) < 2:
        logger.warning(f"Stage {stage.id} has less than 2 waypoints")
        return []

    # Self-Heal: if all arrival_calculated are None, compute via Naismith.
    if all(wp.arrival_calculated is None for wp in stage.waypoints):
        from core.naismith import compute_stage_arrivals
        stage = compute_stage_arrivals(stage, trip.activity)

    segments: List[TripSegment] = []
    waypoints = stage.waypoints
    default_start = stage.start_time if stage.start_time else time(8, 0)

    # Issue #1004/F001: die massgebliche Startzeit pro Wegpunkt wird VORAB
    # fuer die ganze Etappe bestimmt und Luecken (weder arrival_override
    # noch arrival_calculated) linear zwischen den umgebenden bekannten
    # Zeitpunkten interpoliert — verhindert, dass ein unbekannter Zwischen-
    # Wegpunkt zwei Segmente auf denselben Zeitpunkt kollabieren laesst.
    known_times = [
        _known_time_for_index(waypoints, idx, stage, default_start)
        for idx in range(len(waypoints))
    ]
    wp_times = _interpolate_missing_times(known_times)

    # Issue #1098: Tages-Offset-Vektor parallel zu wp_times. _interpolate_missing_times
    # loest ueber Mitternacht laufende Zeiten intern zwar monoton auf (#1091), gibt aber
    # nackte time zurueck — der Tages-Rollover ginge sonst beim Kombinieren mit einem
    # einzigen target_date verloren. Der Tag wird NUR bei STRIKT fallender Uhrzeit (< prev)
    # erhoeht = echte Tagesgrenze; gleiche (==) Zeiten rollen NICHT und laufen weiter in
    # den end_dt<=start_dt-Klemm-Guard (AC-5 Mitternachts-Klemme, #1004).
    day = 0
    prev = None
    wp_days: List[int] = []
    for t in wp_times:
        if t is not None and prev is not None and t < prev:  # strikt fallend = Tagesgrenze
            day += 1
        wp_days.append(day)
        if t is not None:
            prev = t

    cumulative_time = default_start
    cumulative_dist_km = 0.0

    for i in range(len(waypoints) - 1):
        wp1 = waypoints[i]
        wp2 = waypoints[i + 1]

        wp1_start = wp_times[i]
        if wp1_start is None:
            logger.warning(
                f"Kein arrival_calculated fuer {wp1.id}, verwende letzten bekannten Zeitpunkt"
            )
            wp1_start = cumulative_time

        cumulative_time = wp1_start

        wp2_start = wp_times[i + 1]
        if wp2_start is None:
            logger.warning(f"Kein arrival_calculated/override fuer {wp2.id}")
            wp2_start = wp1_start

        seg_tz = tz_for_coords(wp1.lat, wp1.lon)
        start_dt = (
            datetime.combine(target_date + timedelta(days=wp_days[i]), wp1_start)
            .replace(tzinfo=seg_tz)
            .astimezone(timezone.utc)
        )
        end_dt = (
            datetime.combine(target_date + timedelta(days=wp_days[i + 1]), wp2_start)
            .replace(tzinfo=seg_tz)
            .astimezone(timezone.utc)
        )

        if end_dt <= start_dt:
            # Issue #1004/AC-5: Wegpunkt-Paare mit nicht vorwaerts laufender
            # Zeit werden bewusst uebersprungen, statt die komplette Etappe
            # stumm verschwinden zu lassen.
            # Die frueher haeufigste Ursache — die Mitternachts-Klemme in
            # core/naismith.py (_format_hhmm klemmte auf 23:59, wodurch mehrere
            # Wegpunkte auf denselben Zeitpunkt fielen) — EXISTIERT SEIT
            # Issue #1667 S2 NICHT MEHR: _format_hhmm wickelt jetzt per Modulo
            # ueber Mitternacht. Der Guard bleibt trotzdem bestehen, weil er
            # weiterhin gleiche/rueckwaerts laufende Zeiten aus der
            # Interpolation und aus manuellen arrival_override-Werten faengt
            # (#1091). Greift er heute, ist das ein echter Befund und keine
            # Formatierungs-Nebenwirkung mehr.
            logger.warning(
                f"Segment {wp1.id}->{wp2.id} kollabiert (wp1_start={wp1_start}, "
                f"wp2_start={wp2_start}) — Zeit laeuft nicht vorwaerts, "
                "wird uebersprungen"
            )
            continue

        duration_hours = (end_dt - start_dt).total_seconds() / 3600

        elev1 = wp1.elevation_m if wp1.elevation_m else 0
        elev2 = wp2.elevation_m if wp2.elevation_m else 0
        elev_diff = elev2 - elev1
        dist_km = haversine_km(wp1.lat, wp1.lon, wp2.lat, wp2.lon)

        segment = TripSegment(
            segment_id=i + 1,
            start_point=GPXPoint(
                lat=wp1.lat,
                lon=wp1.lon,
                elevation_m=float(elev1),
                distance_from_start_km=cumulative_dist_km,
            ),
            end_point=GPXPoint(
                lat=wp2.lat,
                lon=wp2.lon,
                elevation_m=float(elev2),
                distance_from_start_km=cumulative_dist_km + round(dist_km, 1),
            ),
            start_time=start_dt,
            end_time=end_dt,
            duration_hours=duration_hours,
            distance_km=round(dist_km, 1),
            ascent_m=float(max(0, elev_diff)),
            descent_m=float(max(0, -elev_diff)),
        )
        cumulative_dist_km += round(dist_km, 1)
        segments.append(segment)

    # Destination segment (Zielort)
    if segments and waypoints:
        last_wp = waypoints[-1]
        arrival_time = segments[-1].end_time
        elev = float(last_wp.elevation_m) if last_wp.elevation_m else 0.0

        # Issue #1584: Das Ziel-Segment endete bisher hart bei
        # arrival_time + 2 h. Beide Alarmpfade (weather_change_detection,
        # Radar-/NowCast-Check in trip_alert) und die Aggregation
        # (segment_weather) lesen ausschliesslich segment.end_time — die
        # Gefahren-Ueberwachung fuer das Tagesziel war damit strukturell zwei
        # Stunden nach Ankunft abgeschaltet. Das Ende folgt jetzt derselben
        # Tagesfenster-Quelle wie Anzeige und Bewertung (ADR-0035), damit es
        # KEINEN zweiten Zeitbegriff gibt.
        # PO-Entscheidung 2026-08-08: Ein Tagesfenster ueber Mitternacht
        # (start_hour > end_hour, seit #1361 gueltig) wird hier BEWUSST nicht
        # abgebildet — ein solches Fenster hat ein Loch (z. B. 2-22 Uhr), das
        # ein einzelnes zusammenhaengendes Segment nicht darstellen kann. Es
        # greift dann der Randfall-Guard unten (Mindestfenster). Deshalb wird
        # start_hour hier nicht gebraucht. Details: Known Limitations der Spec.
        _rc = getattr(trip, "report_config", None)
        _, end_hour = resolve_configured_window(
            getattr(_rc, "day_window_start_hour", None) if _rc else None,
            getattr(_rc, "day_window_end_hour", None) if _rc else None,
        )
        dest_tz = tz_for_coords(last_wp.lat, last_wp.lon)
        # Der Kalendertag ist der LOKALE Ankunftstag am Ziel, nicht der
        # UTC-Tag: bei einem Ziel westlich von Greenwich faellt die Ankunft
        # in UTC schon auf den Folgetag, waehrend es am Ziel noch derselbe
        # Tag ist — der UTC-Tag wuerde das Fenster um 24 h verschieben.
        arrival_local_date = arrival_time.astimezone(dest_tz).date()
        window_end = (
            datetime.combine(arrival_local_date, time(end_hour))
            .replace(tzinfo=dest_tz)
            .astimezone(timezone.utc)
        )

        if window_end <= arrival_time:
            # Ankunft liegt bereits nach day_window_end_hour (Spaetankunft,
            # z. B. 20:30 bei Fenster bis 19:00) — oder das Fenster laeuft
            # ueber Mitternacht (s. o.). Anders als der Mitternachts-
            # Guard oben wird hier NICHT uebersprungen: ein fehlendes
            # Ziel-Segment laesst den Trip still aus der Ueberwachung fallen
            # (genau der Fehler aus #1584). Stattdessen ein minimales, aber
            # gueltiges Fenster.
            logger.warning(
                f"Ziel-Segment: Ankunft {arrival_time.isoformat()} liegt nach "
                f"dem Tagesfenster-Ende ({end_hour}:00 Ortszeit) — minimales "
                "Fenster von 1 h wird verwendet"
            )
            dest_end_time = arrival_time + timedelta(hours=1)
        else:
            dest_end_time = window_end

        destination_segment = TripSegment(
            segment_id="Ziel",
            start_point=GPXPoint(
                lat=last_wp.lat,
                lon=last_wp.lon,
                elevation_m=elev,
                distance_from_start_km=cumulative_dist_km,
            ),
            end_point=GPXPoint(
                lat=last_wp.lat,
                lon=last_wp.lon,
                elevation_m=elev,
                distance_from_start_km=cumulative_dist_km,
            ),
            start_time=arrival_time,
            end_time=dest_end_time,
            duration_hours=(dest_end_time - arrival_time).total_seconds() / 3600,
            distance_km=0.0,
            ascent_m=0.0,
            descent_m=0.0,
        )
        segments.append(destination_segment)

    return segments
