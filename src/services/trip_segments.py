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
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, List, Optional, Tuple

import app.day_window as day_window
from app.day_window import resolve_configured_window
from app.models import GPXPoint, TripSegment
from utils.geo import haversine_km
from utils.timezone import local_dt, to_utc, tz_for_coords

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
    # Issue #1468 (E2): die eingestellten Fenstergrenzen der Tour, unveraendert
    # weitergereicht. Die AUFLOESUNG (Default 4-19, Gueltigkeitsregeln) wohnt
    # am Auswertungsort (`segment_weather._aggregate_for_segment`) -- eine
    # zweite Aufloesung hier waere genau die Doppelung, die ADR-0035 vermeidet.
    _trip_rc = getattr(trip, "report_config", None)
    _win_start = getattr(_trip_rc, "day_window_start_hour", None)
    _win_end = getattr(_trip_rc, "day_window_end_hour", None)
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
        start_dt = to_utc(
            datetime.combine(target_date + timedelta(days=wp_days[i]), wp1_start)
            .replace(tzinfo=seg_tz)
        )
        end_dt = to_utc(
            datetime.combine(target_date + timedelta(days=wp_days[i + 1]), wp2_start)
            .replace(tzinfo=seg_tz)
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

        # Issue #1468 (E2): das Auswertungsfenster der Tour reist mit dem
        # Segment -- jeder spaetere Aggregations-Aufrufer erbt es dadurch.
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
            day_window_start_hour=_win_start,
            day_window_end_hour=_win_end,
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
        arrival_local_date = local_dt(arrival_time, dest_tz).date()
        # Issue #1599: Die Obergrenze ist INKLUSIV — die Endstunde zaehlt
        # vollstaendig mit, das Fenster endet zeitlich bei (end_hour+1):00
        # Ortszeit. Die Umrechnung wohnt in app/day_window.py, damit sie nicht
        # zum vierten Mal auseinanderlaeuft.
        window_end = day_window.window_end_utc_exclusive(
            arrival_local_date, end_hour, dest_tz
        )

        # Issue #1599: Mindestfenster von 1 h ab Ankunft — UNABHAENGIG von der
        # Fenstergrenze. Vorher griff es nur, wenn das Fenster zur Ankunft
        # schon zu war; mit der eine Stunde spaeteren Grenze haette eine
        # Ankunft um 19:30 nur noch 30 Minuten Ueberwachung statt garantiert
        # 60. Anders als der Mitternachts-Guard oben wird hier NICHT
        # uebersprungen: ein fehlendes Ziel-Segment laesst den Trip still aus
        # der Ueberwachung fallen (genau der Fehler aus #1584).
        min_end_time = arrival_time + timedelta(hours=1)
        if window_end <= min_end_time:
            logger.warning(
                f"Ziel-Segment: Ankunft {arrival_time.isoformat()} laesst bis "
                f"zum Tagesfenster-Ende (bis einschliesslich {end_hour}:00 "
                "Ortszeit) weniger als eine Stunde — minimales Fenster von "
                "1 h wird verwendet"
            )
            dest_end_time = min_end_time
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
            # Dasselbe Fenster wie die uebrigen Segmente. Das ZEIT-Ende oben
            # (`window_end`) folgt bereits dem Fenster (#1584) -- die
            # Auswertungsgrenzen gehoeren trotzdem mit, weil die Aggregation
            # in ORTSZEIT filtert und nicht am Segment-Ende haengt.
            day_window_start_hour=_win_start,
            day_window_end_hour=_win_end,
        )
        segments.append(destination_segment)

    return segments


def select_active_segment(
    segments: List[TripSegment], now_utc: datetime
) -> Optional[TripSegment]:
    """Das gerade massgebliche Segment EINES Tages (Issue #822, 1:1
    extrahiert aus ``TripAlertService.check_radar_alerts``).

    Reihenfolge: erstes zeitlich aktives Segment; sonst — wenn ``now_utc``
    noch vor allen Segmenten liegt — das erste als Vorschau; sonst ``None``
    (alle Segmente vorbei).
    """
    for seg in segments:
        if seg.start_time <= now_utc <= seg.end_time:
            return seg
    if segments and now_utc < segments[0].start_time:
        return segments[0]
    return None


def resolve_current_segment(
    trip: "Trip", now_utc: datetime, today: date
) -> Optional[Tuple[TripSegment, date]]:
    """Tagesuebergreifende Segment-Auswahl (Issue #1667 S3).

    Vorrangkette, erste zutreffende Stufe gewinnt:

    1. AKTIVES Segment von ``today``           -> ``(segment, today)``
    2. AKTIVES Segment von ``today - 1 Tag``   -> ``(segment, gestern)``
    3. Vorschau auf ``heute[0]`` (nur wenn ``now_utc`` davor liegt)
                                               -> ``(segment, today)``
    4. sonst ``None``

    Warum "heute schlaegt gestern": das Ziel-Segment von gestern ist ein
    ortsfestes Fenster an der Unterkunft — laeuft heute ein Segment, ist der
    Wanderer in Bewegung und dessen Koordinate die informativere. Solange
    heute etwas aktiv ist, ist das Ergebnis bitgleich zum Zustand vor S3.

    Aus GESTERN wird nie eine Vorschau genommen (Stufe 2 nimmt ausschliesslich
    ein aktives Segment) — ein Segment von ``today - 1`` kann bei ``now_utc``
    ohnehin nicht in der Zukunft liegen. Der Rueckgriff endet beim
    unmittelbaren Vortag, es gibt keine mehrtaegige Rueckwaertssuche.

    Bewusst KEINE zusammengefuehrte Liste (``gestern + heute``): die
    degradierte die Vorrangregel zu "Listenreihenfolge + break", in der das
    gestrige Ziel-Segment bei echter Ueberlappung faelschlich gewaenne.

    Der Vortagsbau ist LAZY — ``convert_trip_to_segments(trip, gestern)``
    laeuft nur, wenn heute kein aktives Segment liefert.

    Zurueck kommt das Segment MIT dem Datum, dem es entstammt; Aufrufer
    duerfen dieses Datum nicht durch ``today`` ersetzen (der
    Briefing-Schnappschuss wird darunter gelesen, ``trip_alert.py``).
    """
    segments_today = convert_trip_to_segments(trip, today)
    active_today = next(
        (s for s in segments_today if s.start_time <= now_utc <= s.end_time), None
    )
    if active_today is not None:
        return (active_today, today)

    yesterday = today - timedelta(days=1)
    segments_yesterday = convert_trip_to_segments(trip, yesterday)
    active_yesterday = next(
        (s for s in segments_yesterday if s.start_time <= now_utc <= s.end_time), None
    )
    if active_yesterday is not None:
        return (active_yesterday, yesterday)

    preview = select_active_segment(segments_today, now_utc)
    return (preview, today) if preview is not None else None


# Issue #2017: die Vorwaertssuche laedt hoechstens EINEN Folgetag nach. Die im
# Betrieb verwendeten Zieloffsets sind <= 90 Minuten (NOWCAST_HORIZON_MIN // 2),
# ein zweiter Tagessprung ist damit strukturell unerreichbar.
_LOOKAHEAD_DAYS = 1


def _interpolate_point(seg: TripSegment, at: datetime) -> GPXPoint:
    """Linear zwischen ``seg.start_point`` und ``seg.end_point`` nach dem
    Zeitanteil von ``at``, Fortschritt auf ``[0,1]`` geklemmt.

    Dieselbe Naeherung wie die Zeit-Interpolation in
    ``_interpolate_missing_times()`` — dort fuer Zeiten, hier fuer Geometrie.
    """
    span_s = (seg.end_time - seg.start_time).total_seconds()
    p = 0.0 if span_s <= 0 else (at - seg.start_time).total_seconds() / span_s
    p = max(0.0, min(1.0, p))

    a, b = seg.start_point, seg.end_point
    if a.elevation_m is None and b.elevation_m is None:
        elev = None
    else:
        elev_a = a.elevation_m if a.elevation_m is not None else b.elevation_m
        elev_b = b.elevation_m if b.elevation_m is not None else a.elevation_m
        elev = elev_a + p * (elev_b - elev_a)

    return GPXPoint(
        lat=a.lat + p * (b.lat - a.lat),
        lon=a.lon + p * (b.lon - a.lon),
        elevation_m=elev,
        distance_from_start_km=(
            a.distance_from_start_km
            + p * (b.distance_from_start_km - a.distance_from_start_km)
        ),
    )


def position_at_time(
    trip: "Trip", active: TripSegment, segment_date: date, at: datetime,
) -> GPXPoint:
    """Interpolierte Position innerhalb/nach dem aktiven Segment zum Zeitpunkt `at`.

    Onset-frei (#2017): `at` ist ein FESTER Zeitpunkt (Fenstermitte), kein aus
    dem Nowcast-Ergebnis abgeleiteter — sonst Zirkelschluss (siehe Spec).

    Die Segmentwahl bleibt beim Aufrufer: ``active``/``segment_date`` kommen
    unveraendert aus ``resolve_current_segment()`` bzw. der lokalen Auswahl in
    ``trip_report_scheduler.py``. Geteilt wird ausschliesslich die
    Positionsberechnung.

    Fail-soft: der Aufrufer bekommt in JEDEM Fall einen ``GPXPoint`` — laeuft
    ``at`` ueber alle bekannten Segmente hinaus, wird auf den zuletzt
    erreichten ``end_point`` geklemmt und der Grund geloggt.

    Die Hoehe wird roh interpoliert (keine Rundung) — die Normalisierung auf
    ganze Meter fuer ``get_nowcast(elevation_m=...)`` wohnt an der Aufrufstelle.
    """
    # 1. Ortsfestes Ziel-Segment: dort bewegt sich der Wanderer nicht.
    if not isinstance(active.segment_id, int) or active.distance_km == 0.0:
        return active.start_point

    # 2. Vorschau-Zweig: noch nicht losgelaufen → Fortschritt 0.
    if at <= active.start_time:
        return active.start_point

    # 3. Innerhalb des aktiven Segments.
    if at <= active.end_time:
        return _interpolate_point(active, at)

    # 4. Vorwaertssuche ueber Segment- und Tagesgrenze. Bereits durchlaufene
    #    Segmente werden ueber ihr Ende erkannt, nicht ueber Objektidentitaet —
    #    ``active`` stammt aus einer frueheren Konversion und ist mit den hier
    #    frisch erzeugten Segmenten wertgleich, nicht identisch.
    last_end_time = active.end_time
    last_end_point = active.end_point
    for day_offset in range(_LOOKAHEAD_DAYS + 1):
        day = segment_date + timedelta(days=day_offset)
        for seg in convert_trip_to_segments(trip, day):
            if seg.end_time <= last_end_time:
                continue  # liegt vollstaendig hinter uns
            if at < seg.start_time:
                # 5. Luecke zwischen zwei Segmenten (Tagesende/Unterkunft):
                #    der Wanderer bleibt am zuletzt erreichten Punkt.
                logger.debug(
                    "position_at_time: %s liegt in der Luecke vor Segment %s "
                    "(%s) — klemme auf letzten Endpunkt",
                    at.isoformat(), seg.segment_id, day.isoformat(),
                )
                return last_end_point
            if at <= seg.end_time:
                return _interpolate_point(seg, at)
            last_end_time = seg.end_time
            last_end_point = seg.end_point

    # 5. Fail-soft: kein Folgesegment, kein Folgetag (Tour zu Ende, Ruhetag
    #    ohne Stage, uebersprungene Segmentkette) — klemmen statt werfen.
    logger.warning(
        "position_at_time: %s liegt hinter dem letzten bekannten Segment "
        "(Trip %s, ab %s, %d Tag(e) vorausgeschaut) — klemme auf letzten "
        "Endpunkt (%.4f, %.4f)",
        at.isoformat(), getattr(trip, "id", "?"), segment_date.isoformat(),
        _LOOKAHEAD_DAYS, last_end_point.lat, last_end_point.lon,
    )
    return last_end_point
