"""Issue #2050 Scheibe S6 — Alarm-Protokoll haelt Vorwarnzeit, Ereigniszeit,
Messpunkt, Vergleichsbasis und Quelle fest (Anforderung E-1).

SPEC: docs/specs/modules/alarm_protokoll_vorwarnzeit.md (AC-1..AC-8)

Alle Laeufe gehen ueber die ECHTE Ausloeseentscheidung: `AlarmPruefstrecke`
(S1, Radar-/Abweichungs-/amtlicher Zweig) fuer den Trip-Pfad,
`CompareRadarAlertService.check_all_compare_presets()` direkt fuer den
Ortsvergleich-Nowcast (kein Trip-Pendant in der Pruefstrecke). Kein
Mock()/patch()/MagicMock — echte DI-Naehte (`frame_source`, `radar_service`,
`mail_sink`), echte `alert_log.json`-Dateien unter `get_data_dir(user_id)`.

RED-Grund: keine der fuenf E-1-Groessen existiert heute im Protokoll-Eintrag
(`services/alert_log.py`) — jede Praesenz-Zusicherung schlaegt fehl, weil der
Schluessel schlicht fehlt.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from app.loader import get_data_dir, load_all_trips, save_location
from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary,
)
from output.renderers.alert.segments import normalize_segment_id
from services.official_alerts.models import OfficialAlert
from services.radar_service import NowcastResult, RadarNowcastService
from services.trip_alert import TripAlertService
from services.trip_day import trip_local_today

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _AT, _radar_trip, _settings_all_channels, _write_premium_profile,
)
from tests.tdd.test_issue_1070_daily_alert_limit import (
    _deviation_trip, _segment,
)
from tests.tdd.test_compare_radar_alert import (
    _CoordFrameSource, _clean_user as _clean_user_compare, _location,
    _radar_preset, _settings_email_capable_dummy, _write_preset_file,
)

_ANGELEGT: list[str] = []


def _uid(tag: str) -> str:
    uid = f"tdd-2050-s6-{tag}-{uuid.uuid4().hex[:6]}"
    _ANGELEGT.append(uid)
    return uid


def _entry_for(uid: str, entity_id: str) -> dict:
    """Liest den JUENGSTEN `entries`-Eintrag fuer `entity_id` zurueck."""
    path = get_data_dir(uid) / "alert_log.json"
    data = json.loads(path.read_text())
    treffer = [e for e in data.get("entries", []) if e.get("entity_id") == entity_id]
    assert treffer, f"kein entries-Eintrag fuer {entity_id!r} in {path}: {data!r}"
    return treffer[-1]


class _FixedRadar(RadarNowcastService):
    """Echte `RadarNowcastService`-Unterklasse (DI-Seam, Vorbild
    `_GuaranteedWetRadar`) mit frei waehlbarem `NowcastResult` — im
    Unterschied zum Vorbild auch mit `event_end_minutes` steuerbar (AC-2)."""

    def __init__(self, **kwargs) -> None:
        super().__init__()
        kwargs.setdefault("intensity_label", "leichter Regen")
        kwargs.setdefault("source", "radar")
        self._fixed = NowcastResult(**kwargs)

    def get_nowcast(self, lat, lon, elevation_m=None, priority="user_briefing"):
        return self._fixed


def _weather_data_mit_peak(segment_id, precip_sum_mm: float, peak_at: datetime) -> SegmentWeatherData:
    """`SegmentWeatherData` mit EINEM Zeitreihenpunkt -- macht den
    Spitzenwert-Zeitpunkt (`occurred_at`) fuer den Abweichungszweig
    bestimmbar (Vorbild `_weather_data()`, aber mit befuellter Zeitreihe
    statt `data=[]`)."""
    return SegmentWeatherData(
        segment=_segment(segment_id),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[ForecastDataPoint(ts=peak_at, precip_1h_mm=5.0)],
        ),
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=_AT - timedelta(hours=1),
        provider="openmeteo",
    )


def _active_segment_snapshot(uid: str, trip_id: str, at: datetime):
    """Ermittelt das aktive Segment GENAU wie `check_radar_alerts()` es waehlt
    -- ueber dieselbe Ableitung (`TripAlertService._resolve_alert_segment`),
    NICHT ueber geratene Literale. Aufruf NACH dem echten Pruefstrecken-Lauf
    und ueber `load_all_trips()` (statt des lokalen `trip`-Objekts), damit
    dieselbe -- ggf. von `_resolve_alert_segment` nachgeruestete -- Trip-Datei
    gelesen wird wie im echten Lauf (Vorbild: km-Nachruestung Issue #2036
    AC-7)."""
    with freeze_time(at):
        now = datetime.now(timezone.utc)
        svc = TripAlertService(user_id=uid)
        trip = next(t for t in load_all_trips(user_id=uid) if t.id == trip_id)
        today = trip_local_today(trip, now)
        resolved = svc._resolve_alert_segment(trip, now, today)
    assert resolved is not None, f"kein aktives Segment fuer {trip_id!r} ableitbar"
    active, _segment_date = resolved
    return active


def _aufraeumen() -> None:
    for uid in _ANGELEGT:
        _clean_user(uid)
        _clean_user_compare(uid)
    _ANGELEGT.clear()


# ---------------------------------------------------------------------------
# AC-1/AC-2: Radar-Zweig (Trip)
# ---------------------------------------------------------------------------

def test_ac1_radar_alarm_traegt_vorwarnzeit_ereigniszeit_messpunkt_und_quelle():
    uid = _uid("ac1")
    try:
        _write_premium_profile(uid, _AT)
        trip = _radar_trip(uid, "trip-2050-s6-ac1", send_email=True)
        # EINE Variable fuer die Vorwarnzeit -- speist sowohl den Nowcast-Stub
        # als auch die Erwartung unten, damit die Bildungsstelle (`_onset_dt =
        # now_utc + timedelta(minutes=result.onset_minutes)`) tatsaechlich
        # bewacht ist statt nur die ISO-Parsebarkeit der Ausgabe.
        vorwarnzeit_min = 12
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_FixedRadar(onset_minutes=vorwarnzeit_min),
        )
        assert lauf.triggered_count == 1, (
            f"AC-1 Vorbedingung: der Radar-Alarm muss ausloesen (war {lauf.triggered_count})."
        )
        entry = _entry_for(uid, trip.id)

        assert entry.get("lead_time_minutes") == vorwarnzeit_min, (
            f"AC-1: lead_time_minutes fehlt oder stimmt nicht mit onset_minutes ueberein: {entry!r}"
        )
        assert "event_at" in entry, f"AC-1: event_at fehlt: {entry!r}"
        tatsaechlicher_event_at = datetime.fromisoformat(entry["event_at"])
        if tatsaechlicher_event_at.tzinfo is None:
            tatsaechlicher_event_at = tatsaechlicher_event_at.replace(tzinfo=timezone.utc)
        erwarteter_event_at = _AT + timedelta(minutes=vorwarnzeit_min)
        assert tatsaechlicher_event_at == erwarteter_event_at, (
            f"AC-1: event_at muss der Ereignisbeginn sein (Laufzeitpunkt {_AT.isoformat()} "
            f"+ Vorwarnzeit {vorwarnzeit_min} min = {erwarteter_event_at.isoformat()}), "
            f"nicht bloss irgendein ISO-parsebarer Zeitstempel: war {tatsaechlicher_event_at.isoformat()}"
        )

        mp = entry.get("measurement_point")
        assert mp is not None, f"AC-1: measurement_point fehlt: {entry!r}"
        assert {"segment_id", "km_from", "km_to"} <= set(mp), (
            f"AC-1: measurement_point unvollstaendig (erwarte segment_id/km_from/km_to): {mp!r}"
        )
        aktives_segment = _active_segment_snapshot(uid, trip.id, _AT)
        assert mp["segment_id"] == normalize_segment_id(aktives_segment.segment_id), (
            f"AC-1: measurement_point.segment_id muss die Segment-Kennung des "
            f"aktiven Segments sein: {mp!r} vs. Segment {aktives_segment.segment_id!r}"
        )
        assert mp["km_from"] == aktives_segment.start_point.distance_from_start_km, (
            f"AC-1: measurement_point.km_from muss die Start-km des aktiven "
            f"Segments sein (nicht vertauscht mit km_to): {mp!r} vs. Segment "
            f"start={aktives_segment.start_point.distance_from_start_km!r}/"
            f"end={aktives_segment.end_point.distance_from_start_km!r}"
        )
        assert mp["km_to"] == aktives_segment.end_point.distance_from_start_km, (
            f"AC-1: measurement_point.km_to muss die End-km des aktiven "
            f"Segments sein (nicht vertauscht mit km_from): {mp!r} vs. Segment "
            f"start={aktives_segment.start_point.distance_from_start_km!r}/"
            f"end={aktives_segment.end_point.distance_from_start_km!r}"
        )

        assert entry.get("source") == "radar", (
            f"AC-1: source muss der ROHE Quellen-Schluessel sein (`result.source`), "
            f"nicht die Beschriftung aus `source_label()` -- sonst stuenden zwei "
            f"Vokabulare in EINEM Feld (Spec-Abschnitt \"Korrektur: `source` ist "
            f"immer der rohe Schluessel\", Regel O1): {entry!r}"
        )
    finally:
        _aufraeumen()


def test_ac2_laufendes_ereignis_mit_bestimmbarem_ende_traegt_event_end_at():
    uid = _uid("ac2")
    try:
        _write_premium_profile(uid, _AT)
        trip = _radar_trip(uid, "trip-2050-s6-ac2", send_email=True)
        # Dieselben Variablen speisen den Nowcast-Stub UND die Erwartung --
        # sonst prueft `ende > beginn` nur die Reihenfolge, nie den WERT.
        vorwarnzeit_min = 12
        ereignisende_min = 45
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_FixedRadar(
                onset_minutes=vorwarnzeit_min, event_end_minutes=ereignisende_min,
            ),
        )
        assert lauf.triggered_count == 1, (
            f"AC-2 Vorbedingung: der Radar-Alarm muss ausloesen (war {lauf.triggered_count})."
        )
        entry = _entry_for(uid, trip.id)

        assert "event_at" in entry, f"AC-2 Vorbedingung: event_at fehlt: {entry!r}"
        assert "event_end_at" in entry, f"AC-2: event_end_at fehlt: {entry!r}"
        beginn = datetime.fromisoformat(entry["event_at"])
        ende = datetime.fromisoformat(entry["event_end_at"])
        if beginn.tzinfo is None:
            beginn = beginn.replace(tzinfo=timezone.utc)
        if ende.tzinfo is None:
            ende = ende.replace(tzinfo=timezone.utc)
        assert ende > beginn, (
            f"AC-2: event_end_at ({ende}) muss NACH event_at ({beginn}) liegen -- "
            f"sonst ist es kein Ende des GEMELDETEN Ereignisses."
        )

        erwarteter_beginn = _AT + timedelta(minutes=vorwarnzeit_min)
        erwartetes_ende = _AT + timedelta(minutes=ereignisende_min)
        assert beginn == erwarteter_beginn, (
            f"AC-2: event_at muss der Laufzeitpunkt {_AT.isoformat()} + Vorwarnzeit "
            f"{vorwarnzeit_min} min sein: erwartet {erwarteter_beginn.isoformat()}, war {beginn.isoformat()}"
        )
        assert ende == erwartetes_ende, (
            f"AC-2: event_end_at muss der Laufzeitpunkt {_AT.isoformat()} + Ereignisende "
            f"{ereignisende_min} min sein: erwartet {erwartetes_ende.isoformat()}, war {ende.isoformat()}"
        )
    finally:
        _aufraeumen()


# ---------------------------------------------------------------------------
# AC-3/AC-4/AC-6: Abweichungszweig (Trip)
# ---------------------------------------------------------------------------

def test_ac3_vorhersageaenderung_ueber_ein_segment_traegt_messpunkt_und_vergleichsbasis():
    uid = _uid("ac3")
    try:
        trip = _deviation_trip("trip-2050-s6-ac3")
        anker_zeit = _AT - timedelta(hours=1)
        cached = [_weather_data_mit_peak(1, 2.0, _AT - timedelta(hours=2))]
        fresh = [_weather_data_mit_peak(1, 18.0, _AT - timedelta(minutes=30))]
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="deviation", trip=trip, cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 1, (
            f"AC-3 Vorbedingung: die Aenderung muss ausloesen (war {lauf.triggered_count})."
        )
        entry = _entry_for(uid, trip.id)

        mp = entry.get("measurement_point")
        assert mp == {"segment_id": "1"}, (
            f"AC-3: measurement_point muss GENAU das eine betroffene Segment tragen: {mp!r}"
        )
        assert "reference_at" in entry, f"AC-3: reference_at fehlt: {entry!r}"
        assert datetime.fromisoformat(entry["reference_at"]) == anker_zeit, (
            f"AC-3: reference_at muss der Anker-Fetchzeitpunkt sein: {entry.get('reference_at')!r}"
        )
    finally:
        _aufraeumen()


def test_ac4_vorhersageaenderung_ueber_zwei_segmente_hat_keinen_messpunkt():
    """AC-4, Positivkontrolle zu AC-3: zwei VERSCHIEDENE Segmente in einem
    Eintrag -> `measurement_point` fehlt komplett. Gegenprobe im selben Test:
    derselbe Aufbau mit nur EINEM der beiden Segmente traegt den Schluessel
    sehr wohl -- der Unterschied beweist, dass die Mehrdeutigkeit selbst der
    Grund fuer die Absenz ist, nicht ein durchgehend leerer Pfad."""
    uid_zwei, uid_eins = _uid("ac4-zwei"), _uid("ac4-eins")
    try:
        trip_zwei = _deviation_trip("trip-2050-s6-ac4-zwei")
        cached_zwei = [
            _weather_data_mit_peak(1, 2.0, _AT - timedelta(hours=2)),
            _weather_data_mit_peak(2, 2.0, _AT - timedelta(hours=2)),
        ]
        fresh_zwei = [
            _weather_data_mit_peak(1, 18.0, _AT - timedelta(minutes=30)),
            _weather_data_mit_peak(2, 18.0, _AT - timedelta(minutes=45)),
        ]
        strecke_zwei = AlarmPruefstrecke(user_id=uid_zwei, settings=_settings_all_channels())
        lauf_zwei = strecke_zwei.lauf(
            at=_AT, zweig="deviation", trip=trip_zwei,
            cached_weather=cached_zwei, fresh_weather=fresh_zwei,
        )
        assert lauf_zwei.triggered_count == 1, (
            f"AC-4 Vorbedingung: BEIDE Segmente muessen ausloesen (war {lauf_zwei.triggered_count})."
        )
        entry_zwei = _entry_for(uid_zwei, trip_zwei.id)
        assert entry_zwei.get("changes_count") == 2, (
            f"AC-4 Vorbedingung: der Eintrag muss ZWEI Aenderungen buendeln, "
            f"sonst prueft der Test keine Mehrdeutigkeit: {entry_zwei!r}"
        )
        assert "measurement_point" not in entry_zwei, (
            f"AC-4: bei zwei verschiedenen Segmenten darf KEIN willkuerlich "
            f"gewaehltes Segment als Messpunkt erscheinen: {entry_zwei!r}"
        )

        # Gegenprobe: dieselbe Konstruktion mit nur EINEM Segment.
        trip_eins = _deviation_trip("trip-2050-s6-ac4-eins")
        cached_eins = [_weather_data_mit_peak(1, 2.0, _AT - timedelta(hours=2))]
        fresh_eins = [_weather_data_mit_peak(1, 18.0, _AT - timedelta(minutes=30))]
        strecke_eins = AlarmPruefstrecke(user_id=uid_eins, settings=_settings_all_channels())
        lauf_eins = strecke_eins.lauf(
            at=_AT, zweig="deviation", trip=trip_eins,
            cached_weather=cached_eins, fresh_weather=fresh_eins,
        )
        assert lauf_eins.triggered_count == 1
        entry_eins = _entry_for(uid_eins, trip_eins.id)
        assert entry_eins.get("measurement_point") == {"segment_id": "1"}, (
            f"AC-4 Gegenprobe: mit nur EINEM Segment muss measurement_point "
            f"vorhanden sein -- sonst ist die Absenz oben nicht durch die "
            f"Mehrdeutigkeit erklaert, sondern ein durchgehend leerer Pfad: {entry_eins!r}"
        )
    finally:
        _aufraeumen()


def test_ac6_vorhersageaenderung_kennt_weder_vorwarnzeit_noch_ereignisende():
    """AC-6, Positivkontrolle zu AC-5: derselbe Abweichungs-Eintrag traegt
    NIE `lead_time_minutes`/`event_end_at` (strukturell), waehrend `event_at`
    sehr wohl vorkommen KANN (AC-3) -- der Unterschied ist am Schema selbst
    ablesbar."""
    uid = _uid("ac6")
    try:
        trip = _deviation_trip("trip-2050-s6-ac6")
        cached = [_weather_data_mit_peak(1, 2.0, _AT - timedelta(hours=2))]
        fresh = [_weather_data_mit_peak(1, 18.0, _AT - timedelta(minutes=30))]
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="deviation", trip=trip, cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf.triggered_count == 1
        entry = _entry_for(uid, trip.id)

        assert "lead_time_minutes" not in entry, (
            f"AC-6: der Abweichungszweig kennt keine Vorwarnzeit im Nowcast-Sinn: {entry!r}"
        )
        assert "event_end_at" not in entry, (
            f"AC-6: der Abweichungszweig kennt kein Ereignisende: {entry!r}"
        )
        assert "event_at" in entry, (
            f"AC-6: event_at MUSS bei eindeutigem Segment vorkommen (AC-3) -- "
            f"sonst waere die Absenz oben nur ein durchgehend leerer Pfad: {entry!r}"
        )
    finally:
        _aufraeumen()


# ---------------------------------------------------------------------------
# AC-5: amtlicher Zweig (Trip)
# ---------------------------------------------------------------------------

def test_ac5_amtliche_warnung_traegt_ereigniszeit_und_quelle_ohne_vorwarnzeit_und_vergleichsbasis():
    uid = _uid("ac5")
    try:
        trip = _deviation_trip("trip-2050-s6-ac5")
        alert = OfficialAlert(
            source="tdd-2050-s6-ac5-quelle", hazard="thunderstorm", level=3,
            label="Gewitterwarnung",
            valid_from=_AT + timedelta(hours=1), valid_to=_AT + timedelta(hours=6),
        )
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(at=_AT, zweig="official", trip=trip, official_notices=[(alert, ["1"])])
        assert lauf.triggered_count == 1, (
            f"AC-5 Vorbedingung: die amtliche Warnung muss ausloesen (war {lauf.triggered_count})."
        )
        entry = _entry_for(uid, trip.id)

        assert entry.get("source") == "tdd-2050-s6-ac5-quelle", (
            f"AC-5: source muss OfficialAlert.source sein: {entry!r}"
        )
        assert "event_at" in entry and "event_end_at" in entry, (
            f"AC-5: event_at/event_end_at fehlen: {entry!r}"
        )
        assert datetime.fromisoformat(entry["event_at"]) == alert.valid_from, (
            f"AC-5: event_at muss valid_from sein: {entry.get('event_at')!r}"
        )
        assert datetime.fromisoformat(entry["event_end_at"]) == alert.valid_to, (
            f"AC-5: event_end_at muss valid_to sein: {entry.get('event_end_at')!r}"
        )
        assert "lead_time_minutes" not in entry, (
            f"AC-5: amtliche Warnungen haben KEINE Vorwarnzeit -- auch nicht als null: {entry!r}"
        )
        assert "reference_at" not in entry, (
            f"AC-5: amtliche Warnungen haben KEINE Vergleichsbasis -- auch nicht als null: {entry!r}"
        )
    finally:
        _aufraeumen()


# ---------------------------------------------------------------------------
# AC-7: Ortsvergleich, Nowcast
# ---------------------------------------------------------------------------

def _compare_entry_for(uid: str, preset_id: str) -> dict:
    path = get_data_dir(uid) / "alert_log.json"
    data = json.loads(path.read_text())
    treffer = [e for e in data.get("entries", []) if e.get("entity_id") == preset_id]
    assert treffer, f"kein entries-Eintrag fuer {preset_id!r} in {path}: {data!r}"
    return treffer[-1]


def _wet_frame(onset_minutes: int) -> list:
    from providers.brightsky import RadarFrame
    ts = datetime.now(timezone.utc) + timedelta(minutes=onset_minutes)
    return [RadarFrame(timestamp=ts, precip_mm_h=2.0)]


def test_ac7_ortsvergleich_nowcast_ein_ort_traegt_messpunkt_zwei_orte_nicht():
    from services.compare_radar_alert import CompareRadarAlertService

    uid_eins, uid_zwei = _uid("ac7-eins"), _uid("ac7-zwei")
    try:
        loc = _location("loc-ac7", "Zermatt-2050-S6", 46.0207, 7.7491)
        save_location(loc, user_id=uid_eins)
        preset_id_eins = "cp-2050-s6-ac7-eins"
        _write_preset_file(
            uid_eins, [_radar_preset(preset_id_eins, ["loc-ac7"], ["gregor-test@henemm.com"])],
        )
        frame_source_eins = _CoordFrameSource({(46.0207, 7.7491): _wet_frame(8)})
        service_eins = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid_eins,
            radar_service=RadarNowcastService(frame_source=frame_source_eins),
            mail_sink=lambda subject, body: None,
        )
        sent_eins = service_eins.check_all_compare_presets()
        assert sent_eins == 1, (
            f"AC-7 Vorbedingung: EIN ausloesender Ort muss senden (war {sent_eins})."
        )
        entry_eins = _compare_entry_for(uid_eins, preset_id_eins)
        assert entry_eins.get("measurement_point") == {"location_id": "loc-ac7"}, (
            f"AC-7: EIN getriggerter Ort MUSS als measurement_point erscheinen: {entry_eins!r}"
        )

        loc_a = _location("loc-a", "Zermatt-2050-S6-a", 46.0207, 7.7491)
        loc_b = _location("loc-b", "Chamonix-2050-S6-b", 45.9237, 6.8694)
        save_location(loc_a, user_id=uid_zwei)
        save_location(loc_b, user_id=uid_zwei)
        preset_id_zwei = "cp-2050-s6-ac7-zwei"
        _write_preset_file(
            uid_zwei,
            [_radar_preset(preset_id_zwei, ["loc-a", "loc-b"], ["gregor-test@henemm.com"])],
        )
        frame_source_zwei = _CoordFrameSource({
            (46.0207, 7.7491): _wet_frame(5),
            (45.9237, 6.8694): _wet_frame(18),
        })
        service_zwei = CompareRadarAlertService(
            settings=_settings_email_capable_dummy(), user_id=uid_zwei,
            radar_service=RadarNowcastService(frame_source=frame_source_zwei),
            mail_sink=lambda subject, body: None,
        )
        sent_zwei = service_zwei.check_all_compare_presets()
        assert sent_zwei == 1, (
            f"AC-7 Vorbedingung: ZWEI gleichzeitig ausloesende Orte muessen "
            f"EINE gebuendelte Mail ergeben (war {sent_zwei})."
        )
        entry_zwei = _compare_entry_for(uid_zwei, preset_id_zwei)
        assert "measurement_point" not in entry_zwei, (
            f"AC-7: bei ZWEI gleichzeitig ausloesenden Orten darf KEIN "
            f"willkuerlich gewaehlter Ort als Messpunkt erscheinen: {entry_zwei!r}"
        )
    finally:
        _aufraeumen()


# ---------------------------------------------------------------------------
# AC-8: Fail-soft
# ---------------------------------------------------------------------------

def test_ac8_direktaufruf_ohne_bestimmbare_werte_erzeugt_absenz_statt_null():
    """Absenz-Regel (Baustein von AC-8, aber NICHT dessen Fail-soft-
    Zusicherung): ruft man `append_entry()` direkt mit allen sechs kwargs
    auf `None`, entsteht KEINER der sechs Schluessel im Eintrag -- Absenz
    statt eines erfundenen `null`. Das ist ein reiner Verhaltenstest der
    Schreibfunktion selbst (Team-Lead-Review 2026-08-22: der urspruengliche
    Test hier bewies NUR seine eigene Eingabe zurueck -- `sent_channels`/
    `changes_count` wurden selbst uebergeben und identisch wieder ausgelesen,
    das ist keine Zusicherung ueber Zustellung. Die eigentliche Fail-soft-
    Zusicherung "der Alarm geht trotzdem raus" wirkt im Versandpfad, nicht
    in `append_entry()`, und wird deshalb unten als echter Pruefstrecken-Lauf
    gefuehrt, s. `test_ac8_radar_alarm_mit_unbestimmbaren_groessen_...`)."""
    from services import alert_log

    uid = _uid("ac8-absenz")
    try:
        alert_log.append_entry(
            uid, entity_id="trip-2050-s6-ac8-absenz", entity_type="trip",
            changes_count=2, severity="MODERATE",
            reason=alert_log.REASON_FORECAST_CHANGE,
            effective_channels={"email"}, sent_channels=["email"],
            # Die sechs neuen Groessen: alle explizit unbelegt.
            lead_time_minutes=None, event_at=None, event_end_at=None,
            measurement_point=None, reference_at=None, source=None,
        )
        entry = _entry_for(uid, "trip-2050-s6-ac8-absenz")
        for schluessel in (
            "lead_time_minutes", "event_at", "event_end_at",
            "measurement_point", "reference_at", "source",
        ):
            assert schluessel not in entry, (
                f"Absenz-Regel: {schluessel!r} darf bei `None`-Eingabe NICHT im "
                f"Eintrag stehen (Absenz statt null): {entry!r}"
            )
    finally:
        _aufraeumen()


def test_ac8_radar_alarm_mit_unbestimmbaren_groessen_wird_trotzdem_zugestellt_und_protokolliert():
    """AC-8 (Fail-soft, PFLICHT): echter Lauf ueber `AlarmPruefstrecke`
    (`zweig="radar"`), NICHT nur ein Direktaufruf -- die Zusicherung "der
    Alarm geht trotzdem raus" wirkt im Versandpfad, nicht in
    `append_entry()`, und muss deshalb dort geprueft werden, wo sie WIRKT
    (Team-Lead-Review 2026-08-22).

    Konstruktion, ehrlich auf das begrenzt, was am Radar-Nowcast-Zweig
    tatsaechlich unbestimmbar herstellbar ist:

    - **laufendes Ereignis ohne kuenftigen Beginn** (S2b-Fall,
      `onset_minutes=None`, `already_running=True`) -> `lead_time_minutes`
      bleibt `None` (= `result.onset_minutes`, direkt uebernommen).
    - **kein Ende bestimmbar** (`event_end_minutes=None`) -> `event_end_at`
      bleibt `None`.
    - **kein Briefing-Snapshot fuer den Tag** (keiner geschrieben) ->
      `_briefing_precip_for_onset()` liefert sofort `None` -> `reference_at`
      bleibt `None` ("None falls kein Snapshot fuer den Tag existiert",
      Spec-Tabelle Radar-Zeile).

    Das sind damit DREI der sechs Groessen -- NICHT alle sechs: `event_at`
    ist am Radar-Zweig laut Spec-Tabelle "immer gesetzt"
    (`_onset_dt = now_utc + timedelta(minutes=result.onset_minutes or 0)`,
    `trip_alert.py`, Kommentar "Bezugszeitpunkt ist dann JETZT" -- S2b-
    Bruchstelle 3), `measurement_point` (`active.segment_id`/`km_from`/
    `km_to`) und `source` (der rohe `result.source`) sind am
    Radar-Zweig strukturell IMMER aus dem laufenden Trip/Request ableitbar.
    Diese drei koennen an dieser Aufrufstelle nicht auf unbestimmbar gebracht
    werden -- das ist keine Testschwaeche, sondern folgt aus der
    Aufrufstellen-Tabelle der Spec selbst.

    BEWUSST von Anfang an GRUEN (gemessen 2026-08-22): `triggered_count==1`
    und `channels_sent` sind bereits VOR dieser Scheibe unveraendertes
    Verhalten (Zustellung haengt nicht von den sechs neuen Feldern ab), und
    die drei Absenz-Zusicherungen sind vor GREEN trivial erfuellt, weil noch
    KEIN Aufrufer irgendeinen der sechs kwargs uebergibt -- nicht nur fuer
    diese drei. Die Positivkontrolle, dass die Absenz-Pruefung ueberhaupt
    etwas MISST (statt eines durchgehend leeren Pfads), liefern die drei
    Nachbar-Tests in DERSELBEN Datei: `test_ac1_...` zeigt `lead_time_minutes`
    PRAESENT bei bestimmbarem Onset, `test_ac2_...` zeigt `event_end_at`
    PRAESENT bei bestimmbarem Ende, `test_ac3_...` zeigt `reference_at`
    PRAESENT bei vorhandenem Anker -- exakt dieselbe Codefamilie
    (Radar-/Abweichungszweig), nur mit den jeweils bestimmbaren statt
    unbestimmbaren Eingaben."""
    uid = _uid("ac8-radar")
    try:
        trip = _radar_trip(uid, "trip-2050-s6-ac8-radar", send_email=True)
        # Kein Briefing-Snapshot fuer den Tag geschrieben (bewusst) ->
        # reference_at bleibt unbestimmbar.
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=_AT, zweig="radar", trip=trip,
            radar_service=_FixedRadar(onset_minutes=None, already_running=True, event_end_minutes=None),
        )
        assert lauf.triggered_count == 1, (
            f"AC-8 Vorbedingung: das laufende Ereignis (already_running=True) "
            f"muss trotz unbestimmbarem Beginn ausloesen (war {lauf.triggered_count})."
        )
        entry = _entry_for(uid, trip.id)

        assert entry.get("changes_count") == 1 and entry.get("channels_sent"), (
            f"AC-8: der Alarm muss trotzdem VOLLSTAENDIG protokolliert und "
            f"zugestellt werden (mind. ein Kanal in channels_sent): {entry!r}"
        )
        for schluessel in ("lead_time_minutes", "event_end_at", "reference_at"):
            assert schluessel not in entry, (
                f"AC-8: {schluessel!r} ist an dieser Aufrufstelle unbestimmbar "
                f"und darf NICHT im Eintrag stehen: {entry!r}"
            )
    finally:
        _aufraeumen()
