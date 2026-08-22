"""Projektion WeatherChange → AlertMessage (Issue #917, AC-1).

field→metric_id via Reverse-Lookup über den Katalog `summary_fields`, mit
Disambiguierung mehrdeutiger Felder (`temp_min_c` → `temperature` *und*
`temperature_cold`) anhand der WeatherChange-`direction`. Kein stiller Fallback.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.metric_catalog import (
    _METRICS, ONSET_AGGREGATION, get_cmp, metric_and_aggregation_for_field,
)
from utils.timezone import (
    _as_utc, day_offset, local_dt, local_fmt, resolve_location_tz,
)
from .model import (
    AlertEvent, AlertMessage, CorridorEvent, OnsetEvent, OnsetShiftEvent,
)
# Issue #2020 Scheibe 2: EIN Wochentagskuerzel-Erzeuger fuer die Kurzform --
# derselbe, den die amtliche Warnung schon benutzt (kein Nachbau).
from .official_alerts import _de_weekday_short
from .segments import normalize_segment_id

logger = logging.getLogger("alert_project")

# Marker im `source`-Feld eines Ortsvergleich-Onset-Alarms (Issue #1948 S4).
# Gesetzt in `to_multi_location_onset_alert_message`, GELESEN in
# `render._render_sms_onset` — nur so kann der Ein-Ort-Fall (Invariante:
# `location_label is None`) den Ortsnamen aus `trip_short` zeigen statt der
# sinnlosen km-0-0-Spanne. Benannte Konstante statt Freitext, damit ein
# Auseinanderdriften von Setz- und Lesestelle sichtbar bricht.
COMPARE_RADAR_SOURCE = "compare-radar"


def event_end_display(
    now_utc: datetime, nowcast, tz,
) -> tuple[str | None, int, bool]:
    """Anzeigefassung des Ereignis-Endes (Issue #2051 S1):
    `("HH:MM", Versatz, Untergrenze?)`.

    EINE Fassung fuer BEIDE Onset-Pfade (Trip-Radar-Alarm und
    Ortsvergleich-Buendel, ADR-0021) — zwei Kopien dieser vier Zeilen wuerden
    genau so auseinanderlaufen wie die Uhrzeit-/Tagesbezugs-Ableitung des
    Beginns es koennte.

    `(None, 0, False)` heisst "es gibt kein Ende" — das Nowcast-Ergebnis
    traegt keines (kein Beginn erkannt, keine Frames).

    Das dritte Feld ist der R4-Waechter `event_ongoing_beyond_horizon`. Seit
    dem PO-Entscheid vom 2026-08-22 (Spec v1.1) unterdrueckt er die
    Ende-Angabe NICHT mehr, sondern waehlt ihre FORM: `True` heisst "der
    genannte Zeitpunkt ist eine belegte Untergrenze, kein bekanntes Ende".
    Er reist deshalb GEMEINSAM mit der Uhrzeit — eine Textstelle, die nur die
    Uhrzeit bekaeme, wuerde eine Untergrenze als bekanntes Ende ausgeben und
    damit das Gegenteil der Datenlage behaupten (AC-20).

    Der Tagesversatz stammt aus dem ENDE-Zeitpunkt, nicht vom Beginn: Beginn
    23:50 und Ende 00:40 liegen an verschiedenen Kalendertagen.
    """
    end_minutes = getattr(nowcast, "event_end_minutes", None)
    if end_minutes is None:
        return None, 0, False
    ongoing = bool(getattr(nowcast, "event_ongoing_beyond_horizon", False))
    end_dt = now_utc + timedelta(minutes=end_minutes)
    return local_fmt(end_dt, tz), day_offset(now_utc, end_dt, tz), ongoing


def _resolve_metric_id(field: str, direction: str) -> str:
    """summary_field → catalog metric_id, disambiguiert per Richtung.

    `decrease` bevorzugt die cmp='unter'-Metrik (Kältealarm → temperature_cold),
    `increase` die cmp='über'-Metrik (Tageshoch → temperature). Unbekanntes Feld
    → KeyError (kein stiller Fallback).
    """
    candidates = [m for m in _METRICS if field in m.summary_fields.values()]
    if not candidates:
        raise KeyError(f"Unbekanntes summary_field für Alert-Projektion: {field!r}")
    if len(candidates) == 1:
        return candidates[0].id
    want = "unter" if direction == "decrease" else "über"
    for m in candidates:
        if m.cmp == want:
            return m.id
    # Mehrdeutig, aber keine cmp-Übereinstimmung → definierter Fehler.
    raise ValueError(
        f"Mehrdeutiges Feld {field!r} (direction={direction!r}) ohne passende cmp"
    )


def _trip_segment(entry):
    """`SegmentWeatherData` ODER blankes `TripSegment` -> `TripSegment`
    (Issue #2036). Beide Bauformen kommen an: der Aenderungspfad reicht
    Wetterdaten herein, der Korridor-Pfad kann auch die nackten Segmente
    liefern. Ohne diese Normalisierung endet die zweite Bauform im
    `except`-Zweig und der Treffer verschwindet stumm."""
    return getattr(entry, "segment", entry)


def _find_segment(segments, segment_id: str):
    """Referenziertes Segment. Bei nicht auflösbarer/leerer segment_id Fallback
    auf das erste Segment (kein Crash im Versandpfad — der Detector liefert
    nicht immer eine exakte segment_id)."""
    match = next(
        (s for s in segments
         if str(_trip_segment(s).segment_id) == str(segment_id)),
        segments[0] if segments else None,
    )
    if match is None:
        raise KeyError(f"Kein Segment für segment_id={segment_id!r}")
    return match


def _fmt_occurred_at(value, tz) -> str | None:
    """Peak-Zeitpunkt (UTC-`datetime`, s. `WeatherChange.occurred_at`) → "HH:MM"
    in ORTSZEIT (Issue #1386). Guard: naiv hereingereichte Zeitstempel gelten
    als UTC — sonst deutet `astimezone()` sie als System-Lokalzeit."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return local_fmt(value, tz)


# --- Issue #1468: Beginn-Verschiebung (eigener Formatierpfad) ---------------

def _is_onset_change(ch) -> bool:
    """Traegt diese `WeatherChange` eine Beginn-Verschiebung?

    Entschieden ueber den KATALOG (Auswertung des Summary-Felds), nicht ueber
    eine zweite Feldliste im Renderer -- sonst waere eine dritte Beginn-Groesse
    genau die Danebenpflege, die #1435 abgeschafft hat.
    """
    paar = metric_and_aggregation_for_field(ch.metric)
    return bool(paar) and paar[1] == ONSET_AGGREGATION


def _fmt_onset_at(epoch_seconds: float, tz) -> str:
    """Beginn-Zeitpunkt (Epochensekunden, s. `_onset_change()`) -> "HH:MM" in
    ORTSZEIT. Vorbild `_fmt_occurred_at()` -- bewusst NICHT ueber
    `format_metric_value()`, das aus einer Uhrzeit "15 h" machte."""
    return local_fmt(datetime.fromtimestamp(epoch_seconds, timezone.utc), tz)


def _onset_shift_text(delta_seconds: float) -> str:
    """Verschiebung als WORT, nicht als Vorzeichen: "2 h früher"/"2 h später".

    Positives Delta heisst spaeter (der Beginn wandert nach hinten). Der
    Betrag steht ohne Vorzeichen -- die Richtung traegt das Wort.
    """
    stunden = abs(delta_seconds) / 3600.0
    betrag = (f"{stunden:.0f}" if abs(stunden - round(stunden)) < 0.05
              else f"{stunden:.1f}".replace(".", ","))
    return f"{betrag} h {'später' if delta_seconds > 0 else 'früher'}"


def _to_onset_shift_event(
    ch, *, tz, km_from: float, km_to: float,
    segment_id: str | None = None, location_label: str | None = None,
    km_measured: bool = False,   # Issue #2036
    now_utc=None,                # Issue #2020 Scheibe 2
) -> OnsetShiftEvent:
    to_utc = datetime.fromtimestamp(ch.new_value, timezone.utc)
    to_offset, to_past, _weekday = _when_fields(to_utc, now_utc, tz)
    metric_id, _aggregation = metric_and_aggregation_for_field(ch.metric)
    return OnsetShiftEvent(
        metric_id=metric_id,
        from_time=_fmt_onset_at(ch.old_value, tz),
        to_time=_fmt_onset_at(ch.new_value, tz),
        shift_text=_onset_shift_text(ch.delta),
        km_from=km_from, km_to=km_to,
        segment_id=segment_id, location_label=location_label,
        km_measured=km_measured,  # Issue #2036
        to_day_offset=to_offset, to_is_past=to_past,
    )


# --- Issue #2020 Scheibe 2: Tagesbezug + Blickrichtung ----------------------

def _when_fields(target_utc, now_utc, tz) -> tuple[int, bool, str | None]:
    """(Tagesversatz, vergangen?, DE-Wochentagskuerzel) einer Zeitangabe.

    EINE Stelle fuer alle drei Groessen, damit Kalendertag und
    Vergangenheits-Kennzeichen nie aus verschiedenen Zonen stammen. Ohne
    Referenzzeit (Aufrufer ohne `now_utc`) bleibt alles auf dem neutralen
    Bestandswert -- der Renderer schreibt dann wie bisher die nackte Uhrzeit.
    """
    if target_utc is None or now_utc is None:
        return 0, False, None
    target_utc = _as_utc(target_utc)
    now_utc = _as_utc(now_utc)
    offset = day_offset(now_utc, target_utc, tz)
    weekday = _de_weekday_short(local_dt(target_utc, tz)) if offset else None
    return offset, target_utc < now_utc, weekday


def _remaining_fields(eintrag, ch, now_utc, tz) -> dict:
    """Restmenge/Ende/Fensterende EINES Niederschlags-Summen-Ereignisses.

    `eintrag` ist der ROHE Eintrag aus `_find_segment()` -- also die
    `SegmentWeatherData` mit ihrer Stundenreihe, NICHT das ueber
    `_trip_segment()` normalisierte `TripSegment` (Issue #2036). Ein blanker
    Segment-Eintrag (Korridor-Pfad) traegt keine Reihe und faellt unten
    still auf "nicht bestimmbar" zurueck -- richtig, weil dort nichts zu
    rechnen ist.

    Gerechnet wird in `weather_change_detection._precip_remaining()` -- also
    an derselben Stelle und mit demselben Segmentfenster wie die "staerkste
    Stunde" (`_peak_occurred_at()`), bindende Invariante der Spec. HIER
    passiert nur die Umrechnung in Ortszeit und der Tagesbezug.

    Leeres dict = das Ereignis behaelt seinen "staerkste Stunde"-Kopf und
    sagt ueber die Restmenge nichts. Das gilt fuer alle drei Faelle, in denen
    es nichts zu sagen GIBT: andere Metrik, keine Referenzzeit -- und
    `remaining_mm is None`, also "nicht bestimmbar" (keine Stundenreihe,
    Provider-Fehler; z. B. der Vorschau-Stub des Validators). Der Mangelfall
    wird bewusst NUR in `_precip_remaining()` entschieden, nicht hier noch
    einmal parallel: zwei Stellen wuerden auseinanderlaufen, und ein
    unbestimmbares Ergebnis darf unter keinen Umstaenden als `0.0` (=
    "es kommt nachweislich nichts mehr") beim Renderer ankommen.
    """
    if ch.metric != "precip_sum_mm" or now_utc is None:
        return {}
    from services.weather_change_detection import _precip_remaining

    remaining_mm, ends_at = _precip_remaining(eintrag, now_utc)
    if remaining_mm is None:
        return {}
    ende_offset, _ende_past, ende_weekday = _when_fields(ends_at, now_utc, tz)
    fenster_offset, _f_past, _f_weekday = _when_fields(
        eintrag.segment.end_time, now_utc, tz,
    )
    return {
        "remaining_mm": remaining_mm,
        "remaining_until_time": _fmt_occurred_at(ends_at, tz),
        "remaining_until_day_offset": ende_offset,
        "remaining_until_weekday": ende_weekday,
        "window_end_time": local_fmt(_as_utc(eintrag.segment.end_time), tz),
        "window_end_day_offset": fenster_offset,
    }


def to_alert_message(
    changes, segments, trip_name, *, tz, stand_at, corridor_hits=None,
    reference_at=None, now_utc=None,
) -> AlertMessage:
    """WeatherChange-Events → kanonische AlertMessage. source bei Deviation = None.

    Issue #1386: die Ereigniszeit („Wo & wann … · HH:MM", SMS `@HH`) wird HIER
    in ORTSZEIT formatiert — je Event aus den Koordinaten SEINER Etappe
    (`TripSegment.start_point`), `tz` ist Fallback ohne Koordinaten.

    Issue #1444 S1: `corridor_hits` (optional, `list[CorridorHit]`) buendelt
    Schwellen-Treffer desselben Laufs in DIESELBE Nachricht (Muster #1088) --
    `changes` kann dabei leer sein (Korridor als einzige Alarmquelle, AC-5).

    Issue #2020 Scheibe 2: `now_utc` ist die REFERENZZEIT des Versands --
    ohne sie kann niemand entscheiden, welche Stunde noch bevorsteht. Aus ihr
    entstehen Tagesversatz und Vergangenheits-Kennzeichen jeder Zeitangabe
    sowie die Restmenge des Niederschlags-Summen-Ereignisses. Sie wird
    UEBERGEBEN, nie hier von der Systemuhr gelesen (AC-13); `None` laesst die
    Ausgabe byte-identisch zum Bestand.
    """
    events: list[AlertEvent] = []
    onset_events: list[OnsetShiftEvent] = []
    for ch in changes:
        # Issue #2036 normalisiert auf das `TripSegment` (km, Kennung, Zone);
        # Issue #2020 Scheibe 2 braucht daneben den ROHEINTRAG, weil Restmenge
        # und Fensterende aus der Stundenreihe der `SegmentWeatherData`
        # entstehen -- die das normalisierte Segment nicht mehr traegt.
        eintrag = _find_segment(segments, ch.segment_id)
        match = _trip_segment(eintrag)
        km_from = match.start_point.distance_from_start_km
        km_to = match.end_point.distance_from_start_km
        # Issue #2036: Herkunft der Spanne (gemessen vs. Luftlinie) reist mit.
        km_measured = bool(getattr(match, "distance_measured", False))
        # Issue #1468: Beginn-Verschiebungen tragen einen ZEITPUNKT und gehen
        # deshalb NICHT durch den Zahlen-Formatierer (s. `OnsetShiftEvent`).
        if _is_onset_change(ch):
            onset_events.append(_to_onset_shift_event(
                ch, tz=_tz_for_location(match.start_point, tz),
                km_from=km_from, km_to=km_to,
                segment_id=normalize_segment_id(match.segment_id),
                km_measured=km_measured,
                now_utc=now_utc,
            ))
            continue
        metric_id = _resolve_metric_id(ch.metric, ch.direction)
        cmp = get_cmp(metric_id)
        if not cmp:
            raise ValueError(f"Leeres cmp für metric_id={metric_id!r}")
        ev_tz = _tz_for_location(match.start_point, tz)
        occ_offset, occ_past, occ_weekday = _when_fields(
            ch.occurred_at, now_utc, ev_tz,
        )
        events.append(AlertEvent(
            metric_id=metric_id, value_from=ch.old_value, value_to=ch.new_value,
            threshold=ch.threshold, cmp=cmp,
            occurred_at=_fmt_occurred_at(ch.occurred_at, ev_tz),
            km_from=km_from, km_to=km_to,
            occurred_day_offset=occ_offset, occurred_is_past=occ_past,
            occurred_weekday=occ_weekday,
            **_remaining_fields(eintrag, ch, now_utc, ev_tz),
            # Issue #1744 A1: die Kennung der TATSAECHLICH aufgeloesten Etappe
            # (nicht `ch.segment_id` — `_find_segment` faellt bei nicht
            # aufloesbarer Kennung auf das erste Segment zurueck, und der Alarm
            # muss den Ort nennen, den er auch km-seitig meint).
            segment_id=normalize_segment_id(match.segment_id),
            km_measured=km_measured,  # Issue #2036
        ))
    corridor_events = (
        to_corridor_events(corridor_hits, segments, tz=tz) if corridor_hits else ()
    )
    return AlertMessage(
        trip_short=trip_name, stand_at=stand_at, events=tuple(events), source=None,
        corridor_events=corridor_events,
        onset_shift_events=tuple(onset_events), reference_at=reference_at,
    )


def _resolve_corridor_metric_id(alert_metric: str, direction: str) -> str:
    """Korridor-Metrik (BEIDE Namensraeume) → Katalog metric_id fuer
    Beschriftung/Einheit/Kuerzel (Issue #1444 S1, F001-Fix; S2a Namensraum).

    Die Aufloesung des Summary-Felds kommt aus
    `services.corridor_threshold.resolve_corridor_summary_field()` -- DIESELBE
    Funktion, die der Waechter benutzt. Zwei Kopien wuerden bedeuten, dass ein
    im Waechter erkannter Treffer bei der Projektion erneut verschluckt wird.

    Loest ueber das SUMMARY-FIELD auf (wie `_resolve_metric_id()` fuer den
    Delta-Pfad) statt ueber `_ALERT_METRIC_TO_CATALOG_ID` -- das Feld ist die
    praezisere Quelle: `SNOW_LINE` mappt dort auf ZWEI Katalog-IDs
    (`snowfall_limit`/`freezing_level`, Issue #961 OR-Policy fuer die
    Wetter-Tab-Aktivierung, BEIDE mit cmp='unter'), obwohl die
    Korridor-Auswertung ausschliesslich `freezing_level_m` liest (Issue #959).
    Ueber das Feld ist das unzweideutig EIN Treffer -- der alte Weg ueber die
    AlertMetric-Enum-Mehrdeutigkeit warf hier `ValueError` (F001, GEFUNDEN
    von der Adversary-Pruefung: stiller Total-Ausfall der Tour in JEDEM Lauf).

    Bleibt ein Feld dennoch mehrdeutig (nur `temp_min_c` ->
    temperature/temperature_cold), bevorzugt eine cmp-Uebereinstimmung die
    Beschriftung -- NUR ein Label-Tie-Break, NIE eine Fehlerquelle: ohne
    Treffer faellt die Funktion auf den ERSTEN Kandidaten zurueck statt zu
    werfen. Die tatsaechliche Richtung der Meldung kommt beim Rendern aus
    `CorridorHit.direction`, NICHT aus dieser Katalog-cmp (die beschreibt die
    STANDARDRICHTUNG DER METRIK, nicht die Richtung EINES EINZELNEN Treffers).
    """
    from services.corridor_threshold import resolve_corridor_summary_field

    field = resolve_corridor_summary_field(alert_metric)
    if not field:
        raise KeyError(f"Unbekannte Korridor-Metrik: {alert_metric!r}")
    candidates = [m for m in _METRICS if field in m.summary_fields.values()]
    if not candidates:
        raise KeyError(f"Unbekanntes summary_field für Korridor-Projektion: {field!r}")
    if len(candidates) == 1:
        return candidates[0].id
    want = "über" if direction == "above" else "unter"
    for m in candidates:
        if m.cmp == want:
            return m.id
    return candidates[0].id


def to_corridor_events(hits, segments, *, tz) -> tuple[CorridorEvent, ...]:
    """`CorridorHit`-Liste (`services.corridor_threshold`) → `CorridorEvent`-Tupel
    (Issue #1444 S1). Eigener Render-Vertrag, kein `WeatherChange`-Umweg.

    F001-Haertung: ein einzelner nicht projizierbarer Treffer darf die ganze
    Nachricht nicht verschlucken (ADR-0018: ausweichen ja, kaschieren nein --
    sichtbar protokolliert, aber der Rest der Nachricht inkl. eines
    gleichzeitig vorliegenden Aenderungs-Alarms wird trotzdem zugestellt).
    """
    events: list[CorridorEvent] = []
    for hit in hits:
        try:
            metric_id = _resolve_corridor_metric_id(hit.metric, hit.direction)
            match = _trip_segment(_find_segment(segments, hit.segment_id))
            events.append(CorridorEvent(
                metric_id=metric_id, value=hit.value, bound=hit.bound,
                direction=hit.direction,
                occurred_at=_fmt_occurred_at(
                    hit.occurred_at, _tz_for_location(match.start_point, tz)
                ),
                km_from=match.start_point.distance_from_start_km,
                km_to=match.end_point.distance_from_start_km,
                # Issue #2036: Kennung der TATSAECHLICH aufgeloesten Etappe
                # (Muster `to_alert_message`) und Herkunft der Spanne reisen
                # mit -- ohne beides kann der Renderer nur km zeigen (F001).
                segment_id=normalize_segment_id(match.segment_id),
                km_measured=bool(getattr(match, "distance_measured", False)),
            ))
        except Exception as e:
            logger.warning(
                "Korridor-Treffer nicht projizierbar, uebersprungen: "
                "metric=%r segment_id=%r: %s", hit.metric, hit.segment_id, e,
            )
    return tuple(events)


def to_multi_point_alert_message(groups, *, tz, stand_at, reference_at=None) -> AlertMessage:
    """WeatherChange-Events MEHRERER gleichzeitig betroffener Vergleichs-Orte
    (Issue #1170, AC-7-Bündelung) → EINE kanonische AlertMessage.

    `groups`: `list[(location_name, changes, point)]` — `point` trägt
    `.lat`/`.lon` und liefert damit die ZEITZONE DIESES Ortes für die
    Ereigniszeit („Wo & wann … · HH:MM", SMS `@HH`; Issue #1386, vorher
    ungenutzt und die Zeit stand in Weltzeit). Ohne Koordinaten gilt für
    diesen Ort das Bündel-`tz` (Fallback, `_tz_for_location`) — das ist
    zugleich die einzige Rolle des `tz`-Parameters hier. Bei MEHR ALS EINER
    Gruppe trägt jedes `AlertEvent` das `location_label` SEINER Gruppe, damit
    der Renderer je Datenblock den richtigen Ort zeigt (statt nur den
    kollektiven `AlertMessage.location_label`).

    INVARIANTE: bei GENAU einer Gruppe ist das Ergebnis byte-identisch zu
    `to_point_alert_message()` — `to_point_alert_message()` delegiert
    deshalb direkt hierher (Einzel-Ort-Regressions-Invariante, #1169 AC-7).
    Dazu bleibt das per-Event `location_label` bei genau einer Gruppe None:
    nur das nachrichtenweite `AlertMessage.location_label` (Footer/Where)
    ist gesetzt — sonst zeigt der Mehr-Metrik-Zweig von `render_email` einen
    redundanten Orts-Präfix vor JEDER Metrik-Zeile (Issue #1170 Finding F007).
    """
    events: list[AlertEvent] = []
    onset_events: list[OnsetShiftEvent] = []
    multi = len(groups) > 1
    for location_name, changes, point in groups:
        point_tz = _tz_for_location(point, tz)
        for ch in changes:
            # Issue #1468: derselbe eigene Formatierpfad wie im Trip-Zweig --
            # der Ortsvergleich erbt den Beginn-Alarm ohne Zweitlogik.
            if _is_onset_change(ch):
                onset_events.append(_to_onset_shift_event(
                    ch, tz=point_tz, km_from=0.0, km_to=0.0,
                    location_label=location_name if multi else None,
                ))
                continue
            metric_id = _resolve_metric_id(ch.metric, ch.direction)
            cmp = get_cmp(metric_id)
            if not cmp:
                raise ValueError(f"Leeres cmp für metric_id={metric_id!r}")
            events.append(AlertEvent(
                metric_id=metric_id, value_from=ch.old_value, value_to=ch.new_value,
                threshold=ch.threshold, cmp=cmp,
                occurred_at=_fmt_occurred_at(ch.occurred_at, point_tz),
                km_from=0.0, km_to=0.0,
                location_label=location_name if multi else None,
            ))
    collective_label = ", ".join(name for name, _changes, _point in groups)
    return AlertMessage(
        trip_short=collective_label, stand_at=stand_at, events=tuple(events), source=None,
        location_label=collective_label,
        onset_shift_events=tuple(onset_events), reference_at=reference_at,
    )


def _tz_for_location(loc, fallback_tz):
    """Zeitzone DIESES Ortes (Issue #1385, entdoppelt in #1402).

    Delegiert an den EINEN Aufloeser ``resolve_location_tz()`` (Issue #1378,
    PO-Entscheidung E3) statt einer eigenen Koordinaten-Kopie -- damit
    zieht auch hier ein gesetztes ``SavedLocation.timezone``-Feld VOR den
    Koordinaten (vorher stumm ignoriert). Guard: kein Ortsobjekt, keine
    Koordinaten oder nicht aufloesbar → `fallback_tz` (das Bündel-`tz`),
    niemals ein Absturz im Versandpfad.
    """
    try:
        return resolve_location_tz(loc) or fallback_tz
    except Exception:
        return fallback_tz


def to_multi_location_onset_alert_message(
    groups, *, tz, stand_at, cooldown_display: str | None = None
) -> AlertMessage:
    """Radar-Onset-Ergebnisse MEHRERER gleichzeitig auslösender Vergleichs-Orte
    (Issue #1041 Slice 1a) → EINE kanonische AlertMessage.

    `groups`: `list[(location_name: str, location, NowcastResult)]` — `location`
    trägt `.lat`/`.lon` und damit die ZEITZONE DIESES Ortes. Die kurze Form
    `(location_name, NowcastResult)` bleibt zulässig (Aufrufer ohne Ortsobjekt);
    dann gilt für diesen Ort das übergebene Bündel-`tz`. Je Gruppe ein
    `OnsetEvent` (`km_from=km_to=0.0`, kein Etappen-km, Muster
    `to_multi_point_alert_message:98`). Bei MEHR ALS EINER Gruppe trägt jedes
    Event das `location_label` SEINER Gruppe (Renderer-Multi-Zweig).

    Issue #1385: `onset_time` („ab HH:MM") wird JE ORT in dessen eigener
    Ortszeit formatiert (`resolve_location_tz(loc)`, s. `_tz_for_location`
    oben — entdoppelt in #1402). Vorher galt das
    eine Bündel-`tz` (= Zeitzone des ERSTEN Ortes) für alle Orte — bei Orten in
    verschiedenen Zeitzonen war die Angabe für jeden weiteren Ort schlicht
    falsch. Fehlen Koordinaten (kein Ortsobjekt, `lat`/`lon` `None`), gilt für
    diesen Ort weiterhin das Bündel-`tz` (Guard statt Absturz).

    `tz` bleibt: (a) Zeitzone für `stand_at`, (b) Fallback ohne Koordinaten.
    ABSICHTLICH NICHT je Ort aufgelöst wird `stand_at` — es ist eine Aussage
    über die NACHRICHT („Stand: heute HH:MM", Fußzeile, genau EINMAL pro Mail),
    nicht über einen Ort; es bleibt in der Zeitzone des ersten Ortes. Das ist
    kein Bug (Issue #1385, bewusste Entscheidung).

    INVARIANTE: bei GENAU einer Gruppe bleibt `location_label=None` — fällt
    damit auf den unveränderten Single-Onset-Renderpfad zurück (AC-5).
    `source` trägt den Marker `COMPARE_RADAR_SOURCE`, damit die Renderer
    weiterhin über den Onset-Zweig (`msg.source is not None`) routen — und
    damit `_render_sms_onset` den Ein-Ort-Fall an genau dieser Konstante
    erkennt (Issue #1948 S4, AC-6/AC-7).

    `cooldown_display`: optionaler, bereits formatierter Cooldown-Hinweis-Text
    (Issue Pflicht-Fix, analog `send_radar_alert()`s `cooldown_display`) —
    wird unverändert auf die gebaute `AlertMessage` durchgereicht.

    Härtung (#1041 Fix-Loop, Findings F001/F002): eine leere `groups`-Liste
    ist ein Aufrufer-Fehler → definierter `ValueError` statt `IndexError`.
    Orte ohne Onset (`NowcastResult.onset_minutes is None`) gehören nicht in
    einen Radar-Alarm-Bündel und werden VOR dem `OnsetEvent`/`timedelta`-Bau
    defensiv herausgefiltert; bleibt danach kein Ort übrig, ebenfalls
    `ValueError` (verhindert einen Absturz in Slice 1b).
    """
    if not groups:
        raise ValueError(
            "to_multi_location_onset_alert_message benötigt mindestens einen Ort"
        )
    normalized = [
        (g[0], g[1], g[2]) if len(g) == 3 else (g[0], None, g[1]) for g in groups
    ]
    # Issue #2050 S2b: ein Ort, an dem es GERADE regnet, gehoert in das
    # Buendel -- auch wenn kein kuenftiger Beginn bestimmbar ist. Bis hierher
    # entschied allein `onset_minutes is not None`, und damit fiel genau der
    # laufende Ort still heraus, bevor sein `OnsetEvent` ueberhaupt gebaut
    # wurde (Bruchstelle 4).
    valid_groups = [
        (name, loc, nc) for name, loc, nc in normalized
        if nc.onset_minutes is not None or getattr(nc, "already_running", False)
    ]
    if not valid_groups:
        raise ValueError(
            "to_multi_location_onset_alert_message benötigt mindestens einen Ort "
            "mit gesetztem onset_minutes"
        )
    multi = len(valid_groups) > 1
    now = datetime.now(timezone.utc)
    events: list[OnsetEvent] = []
    for location_name, loc, nc in valid_groups:
        # Issue #2009: Zone JE ORT aufloesen und den Tagesbezug in DERSELBEN
        # Zone bilden — ein Buendel kann Orte in verschiedenen Zonen tragen,
        # eine gemeinsame Zone waere fuer alle bis auf einen still falsch.
        loc_tz = _tz_for_location(loc, tz)
        # Issue #2050 S2b: laeuft das Ereignis bereits und ist kein kuenftiger
        # Beginn bestimmbar, ist der Bezugszeitpunkt JETZT -- `timedelta(
        # minutes=None)` waere ein Absturz (Bruchstelle 3). `onset_minutes`
        # faellt dann auf 0 zurueck; gelesen wird es in diesem Fall nirgends,
        # weil jede Textform auf `already_running` verzweigt.
        _laufend = getattr(nc, "already_running", False)
        onset_dt = now + timedelta(minutes=nc.onset_minutes or 0)
        _end_time, _end_offset, _end_ongoing = event_end_display(now, nc, loc_tz)
        events.append(OnsetEvent(
            already_running=_laufend,
            onset_minutes=nc.onset_minutes or 0,
            onset_time=local_fmt(onset_dt, loc_tz),
            km_from=0.0, km_to=0.0, is_convective=nc.is_convective,
            intensity_label=nc.intensity_label, source_label=nc.source,
            location_label=location_name if multi else None,
            onset_day_offset=day_offset(now, onset_dt, loc_tz),
            # Issue #2046: die Mengenangabe der Kurznachricht kommt im
            # Ortsvergleich-Buendel aus DEMSELBEN NowcastResult wie im
            # Trip-Pfad -- sonst entstuende hier eine stille Luecke, weil
            # dieser Pfad sein OnsetEvent selbst baut (ADR-0021: Trip und
            # Ortsvergleich teilen die Ausgabe).
            onset_precip_mm=nc.onset_precip_mm,
            # Issue #2051 S1: Ende und sein EIGENER Tagesbezug in DERSELBEN
            # Ortszone wie der Beginn (`loc_tz`) -- ein Buendel kann Orte in
            # verschiedenen Zonen tragen. Geteilte Fassung `event_end_display`,
            # dieselbe, die der Trip-Pfad benutzt (ADR-0021).
            event_end_time=_end_time,
            event_end_day_offset=_end_offset,
            # Issue #2051 S1 (Spec v1.1): der R4-Waechter waehlt die TEXTFORM
            # des Endes (Untergrenze vs. bekanntes Ende) und muss den Renderer
            # deshalb erreichen -- er darf nicht mehr stromaufwaerts in einem
            # fehlenden Ende aufgeloest werden (AC-5/AC-20).
            event_ongoing_beyond_horizon=_end_ongoing,
        ))
    trip_short = (
        ", ".join(name for name, _loc, _nc in valid_groups)
        if multi else valid_groups[0][0]
    )
    return AlertMessage(
        trip_short=trip_short, stand_at=stand_at, events=tuple(events),
        source=COMPARE_RADAR_SOURCE, cooldown_display=cooldown_display,
    )


def to_point_alert_message(changes, points, entity_name, *, tz, stand_at) -> AlertMessage:
    """WeatherChange-Events (Punkt-Kontext, Issue #1169) → kanonische
    AlertMessage — OHNE `_find_segment()`-Lookup (ein Vergleichs-Ort ist ein
    Punkt ohne km-Spanne, `km_from=km_to=0.0` als neutraler Platzhalter).
    Setzt zusätzlich `location_label`, damit der geteilte Renderer den
    Ortsnamen statt "km 0–0" zeigt (`render.py`).

    Issue #1170: EINE-Ort-Sonderfall von `to_multi_point_alert_message()` —
    Delegation statt Duplikation garantiert Byte-Identität (siehe dort).
    """
    point = points[0] if points else None
    return to_multi_point_alert_message(
        [(entity_name, changes, point)], tz=tz, stand_at=stand_at,
    )
