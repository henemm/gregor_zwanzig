"""TDD RED — Issue #1460 Teil 1, Paket P2: das Melde-Gedaechtnis ueberlebt den
Briefing-Versand (nur der Aenderungs-Raum wird zurueckgesetzt).

SPEC: docs/specs/modules/rework_1460_t1_relevanzfilter.md (AC-20 .. AC-23)

Das Melde-Gedaechtnis kennt zwei Schluesselraeume:

    "<feld>:<etappe>"                       -> Aenderungs-Raum (Briefing = neuer Anker)
    "official_alert:<ident>:<gefahr>:..."   -> amtliche Warnungen (eigene Entprellung)

`AlertStateService.reset()` loescht heute die GANZE Datei und damit auch die
Entprellung der amtlichen Warnungen — dieselbe Warnung wird deshalb nach jedem
Briefing erneut gemeldet (B1). Ab dieser Scheibe bleibt der amtliche Raum
erhalten.

RED-Ursache (heute, vor der Implementierung):
- `alert_state.py:68-75` (`reset()`) macht `path.unlink()` — der amtliche
  Eintrag ist danach weg (AC-20 rot).
- Dieselbe amtliche Warnung gilt nach dem Briefing-Reset wieder als "neu" und
  wird erneut gemeldet (AC-22 rot).

Keine Mocks: echte Zustands-Dateien auf Platte, echte Services, echte Quelle
ueber `register_official_alert_source()` (strukturelles Subtyping), kein Netz,
kein Versand.
"""
from __future__ import annotations

import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.models import (
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint

# Pfadregel #1409: Pruefling relativ zur Testdatei, nicht ueber den Hauptrepo-Pfad.
DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

LAT, LON = 47.0, 11.0


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _fresh_user(prefix: str) -> str:
    return f"tdd-1460-p2-{prefix}-{uuid.uuid4().hex[:6]}"


def _segment(segment_id: int | str = 1) -> TripSegment:
    now = datetime.now(timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500,
                           distance_from_start_km=8.0),
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        duration_hours=4.0,
        distance_km=8.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(segment_id: int | str = 1, **summary_kwargs) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(segment_id),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _save_cached(user_id: str, trip_id: str, cached: list[SegmentWeatherData]) -> None:
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(user_id=user_id).save_dated(trip_id, date.today(), cached)


def _trip(trip_id: str, *, with_levels: bool = False) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0),
            Waypoint(id="G2", name="Ziel", lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500.0),
        ],
    )
    kwargs: dict = {"official_warnings": None}
    if with_levels:
        kwargs["display_config"] = UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            # Katalog-Kennung fuer Boeen ist "gust" (nicht "wind"), sonst gilt
            # wind_gust als nicht aktiv und die Stufe wird still verworfen.
            metrics=[MetricConfig(metric_id="gust", enabled=True)],
            metric_alert_levels={"wind_gust": "standard"},
        )
    trip = Trip(id=trip_id, name="Gedaechtnis-Trip", stages=[stage], **kwargs)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=with_levels,
    )
    trip.alert_cooldown_minutes = 0
    return trip


class _FixedOfficialAlertSource:
    """Echte Quelle (kein Mock): zustaendig fuer einen Punkt (0.05-Toleranz),
    liefert stets dieselbe, unveraenderte Warnung."""

    def __init__(self, lat: float, lon: float, alert) -> None:
        self._lat, self._lon, self._alert = lat, lon, alert
        self.fetch_calls = 0

    property
    def name(self) -> str:
        return "tdd-1460-p2-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        self.fetch_calls += 1
        return [self._alert]


def _sources_backup():
    import services.official_alerts.base as b

    return b, list(b._REGISTERED_SOURCES)


# ────────────── AC-20 — reset() schneidet nur den Aenderungs-Raum ────────────

def test_ac20_reset_behaelt_die_amtlichen_eintraege():
    """AC-20.

    GIVEN ein Melde-Gedaechtnis mit einem Aenderungs-Eintrag
          ("gust_max_kmh:seg1") UND einem amtlichen Eintrag
          ("official_alert:region:X:thunderstorm:...")
    WHEN  das Gedaechtnis der Tour zurueckgesetzt wird
    THEN  bleibt der amtliche Eintrag unveraendert erhalten und nur der
          Aenderungs-Eintrag verschwindet.
    """
    from services.alert_state import AlertStateService

    user_id = _fresh_user("ac20")
    _clean_user(user_id)
    try:
        trip_id = "trip-1460-ac20"
        official_key = (
            "official_alert:region:Gailtal:thunderstorm:"
            "2026-08-02T06:00:00+00:00:2026-08-02T18:00:00+00:00"
        )
        official_value = {"last_reported_value": 3.0, "reported_at": "2026-08-02T07:00:00+00:00"}
        change_value = {"last_reported_value": 42.0, "reported_at": "2026-08-02T07:00:00+00:00"}

        svc = AlertStateService(user_id=user_id)
        svc.save(trip_id, {"gust_max_kmh:seg1": change_value, official_key: official_value})

        svc.reset(trip_id)

        after = AlertStateService(user_id=user_id).load(trip_id)
        assert official_key in after, (
            "Der amtliche Eintrag muss den Briefing-Reset ueberleben, "
            f"vorhanden: {sorted(after)!r}"
        )
        assert after[official_key] == official_value, (
            f"Der amtliche Eintrag darf sich nicht veraendern: {after[official_key]!r}"
        )
        assert "gust_max_kmh:seg1" not in after, (
            f"Der Aenderungs-Eintrag muss geloescht werden: {sorted(after)!r}"
        )
    finally:
        _clean_user(user_id)


def test_ac20b_reset_bleibt_ohne_amtliche_eintraege_ein_vollstaendiges_loeschen():
    """AC-20 (Gegenprobe).

    GIVEN ein Melde-Gedaechtnis, das ausschliesslich Aenderungs-Eintraege
          enthaelt
    WHEN  das Gedaechtnis zurueckgesetzt wird
    THEN  ist es danach leer — das bisherige Verhalten bleibt fuer diesen Fall
          unveraendert.
    """
    from services.alert_state import AlertStateService

    user_id = _fresh_user("ac20b")
    _clean_user(user_id)
    try:
        trip_id = "trip-1460-ac20b"
        svc = AlertStateService(user_id=user_id)
        svc.save(trip_id, {
            "gust_max_kmh:seg1": {"last_reported_value": 42.0, "reported_at": "x"},
            "precip_sum_mm:seg2": {"last_reported_value": 18.0, "reported_at": "x"},
        })

        svc.reset(trip_id)

        assert AlertStateService(user_id=user_id).load(trip_id) == {}, (
            "Ohne amtliche Eintraege muss das Gedaechtnis vollstaendig leer sein"
        )
    finally:
        _clean_user(user_id)


# ───────── AC-21 — nach dem Briefing meldet derselbe Wert nicht erneut ───────

def test_ac21_nach_dem_briefing_meldet_der_unveraenderte_wert_nicht_erneut():
    """AC-21 (nutzersichtbar).

    GIVEN eine Tour mit einer bereits gemeldeten Wetter-Aenderung im
          Melde-Gedaechtnis
    WHEN  danach das regulaere Briefing versendet wird (Gedaechtnis-Reset) und
          derselbe, unveraenderte Wert erneut geprueft wird
    THEN  geht KEINE erneute Meldung raus — der Briefing-Stand ist der neue
          Vergleichsanker.
    """
    from app.config import Settings
    from services.alert_state import AlertStateService
    from services.trip_alert import TripAlertService
    from services.trip_report_scheduler import TripReportSchedulerService

    user_id = _fresh_user("ac21")
    _clean_user(user_id)
    try:
        trip = _trip("trip-1460-ac21", with_levels=True)
        briefing_stand = [_data(1, gust_max_kmh=35.0)]
        _save_cached(user_id, trip.id, briefing_stand)

        AlertStateService(user_id=user_id).save(trip.id, {
            "gust_max_kmh:1": {
                "last_reported_value": 35.0,
                "reported_at": datetime.now(timezone.utc).isoformat(),
            }
        })

        # Der echte Briefing-Reset-Pfad des Schedulers (kein Nachbau).
        TripReportSchedulerService(
            settings=Settings(), user_id=user_id,
        )._reset_alert_state_after_briefing(trip.id)

        mail_calls: list = []
        svc = TripAlertService(
            user_id=user_id,
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        sent = svc.check_and_send_alerts(
            trip, briefing_stand, fresh_weather=[_data(1, gust_max_kmh=35.0)],
        )

        assert sent is False, "Der unveraenderte Wert darf nach dem Briefing nicht erneut melden"
        assert mail_calls == [], f"Erwartet keine Meldung, erhalten: {len(mail_calls)}"
    finally:
        _clean_user(user_id)


# ─────────── AC-22 — die amtliche Entprellung ueberlebt das Briefing ─────────

def test_ac22_amtliche_warnung_wird_nach_dem_briefing_nicht_erneut_gemeldet():
    """AC-22 (die eigentliche B1-Reparatur).

    GIVEN eine amtliche Warnung wurde bereits gemeldet (Eintrag im
          Melde-Gedaechtnis)
    WHEN  danach das regulaere Briefing versendet wird und dieselbe,
          nicht verschaerfte Warnung erneut abgerufen wird
    THEN  wird sie NICHT erneut gemeldet — die Entprellung bleibt ueber den
          Briefing-Reset hinweg wirksam.
    """
    from app.config import Settings
    from services.official_alerts import OfficialAlert, register_official_alert_source
    from services.trip_alert import TripAlertService
    from services.trip_report_scheduler import TripReportSchedulerService

    user_id = _fresh_user("ac22")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        trip = _trip("trip-1460-ac22")
        _save_cached(user_id, trip.id, [_data(1, gust_max_kmh=20.0)])

        now = datetime.now(timezone.utc)
        alert = OfficialAlert(
            source="tdd-1460-p2", hazard="thunderstorm", level=3,
            label="Gewitterwarnung (#1460 AC-22)", region_label="Gailtal",
            valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=8),
        )
        register_official_alert_source(_FixedOfficialAlertSource(LAT, LON, alert))

        svc = TripAlertService(user_id=user_id)

        first = svc.check_official_alert_triggers(trip)
        assert len(first) == 1, f"Vorbedingung: die Warnung ist zunaechst neu ({first!r})"
        svc._record_official_alert_state(trip.id, first)

        # Regulaeres Briefing dazwischen — echter Scheduler-Reset-Pfad.
        TripReportSchedulerService(
            settings=Settings(), user_id=user_id,
        )._reset_alert_state_after_briefing(trip.id)

        second = svc.check_official_alert_triggers(trip)
        assert second == [], (
            "Dieselbe, nicht verschaerfte amtliche Warnung darf nach dem "
            f"Briefing nicht erneut gemeldet werden, erhalten: {second!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_ac22b_verschaerfte_amtliche_warnung_meldet_auch_nach_dem_briefing():
    """AC-22 (Gegenprobe — kein Stummschalten echter Verschaerfungen).

    GIVEN eine bereits gemeldete amtliche Warnung und ein Briefing dazwischen
    WHEN  dieselbe Region/Gefahr mit HOEHERER Stufe erneut abgerufen wird
    THEN  WIRD sie gemeldet — die erhaltene Entprellung darf keine echte
          Verschaerfung verschlucken.
    """
    from app.config import Settings
    from services.official_alerts import OfficialAlert, register_official_alert_source
    from services.trip_alert import TripAlertService
    from services.trip_report_scheduler import TripReportSchedulerService

    user_id = _fresh_user("ac22b")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        trip = _trip("trip-1460-ac22b")
        _save_cached(user_id, trip.id, [_data(1, gust_max_kmh=20.0)])

        now = datetime.now(timezone.utc)
        vf, vt = now - timedelta(hours=1), now + timedelta(hours=8)

        def _alert(level: int) -> OfficialAlert:
            return OfficialAlert(
                source="tdd-1460-p2", hazard="thunderstorm", level=level,
                label="Gewitterwarnung (#1460 AC-22b)", region_label="Gailtal",
                valid_from=vf, valid_to=vt,
            )

        source = _FixedOfficialAlertSource(LAT, LON, _alert(2))
        register_official_alert_source(source)

        svc = TripAlertService(user_id=user_id)
        first = svc.check_official_alert_triggers(trip)
        assert len(first) == 1, f"Vorbedingung: Stufe 2 ist neu ({first!r})"
        svc._record_official_alert_state(trip.id, first)

        TripReportSchedulerService(
            settings=Settings(), user_id=user_id,
        )._reset_alert_state_after_briefing(trip.id)

        source._alert = _alert(3)
        escalated = svc.check_official_alert_triggers(trip)
        assert len(escalated) == 1, (
            f"Eine echte Verschaerfung muss weiterhin melden, erhalten: {escalated!r}"
        )
        assert escalated[0][0].level == 3
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


# ───────────── AC-23 — der Ad-hoc-Abruf setzt nichts zurueck (#1007) ─────────

def test_ac23_ad_hoc_abruf_setzt_das_melde_gedaechtnis_nicht_zurueck():
    """AC-23.

    GIVEN ein Melde-Gedaechtnis mit einem Aenderungs- UND einem amtlichen
          Eintrag
    WHEN  ein Ad-hoc-Abruf laeuft (kein regulaeres Briefing)
    THEN  bleibt das Gedaechtnis VOLLSTAENDIG unangetastet — unveraendertes
          Bestandsverhalten (Issue #1007).
    """
    from app.config import Settings
    from services.alert_state import AlertStateService
    from services.trip_report_scheduler import TripReportSchedulerService

    user_id = _fresh_user("ac23")
    _clean_user(user_id)
    try:
        trip = _trip("trip-1460-ac23")
        # Kein Kanal scharf: der Lauf soll den vollen Briefing-Pfad nehmen,
        # aber keinen echten Versand versuchen (Outcome "no_channels" —
        # der Reset-Block liegt davor).
        trip.report_config = TripReportConfig(
            trip_id=trip.id, send_email=False, send_telegram=False, send_sms=False,
        )
        before = {
            "gust_max_kmh:1": {"last_reported_value": 42.0, "reported_at": "x"},
            "official_alert:region:Gailtal:thunderstorm:none:none": {
                "last_reported_value": 3.0, "reported_at": "x",
            },
        }
        AlertStateService(user_id=user_id).save(trip.id, dict(before))

        class _RecordingScheduler(TripReportSchedulerService):
            """Echte Unterklasse (kein Mock): merkt sich, ob der Briefing-Reset
            aufgerufen wurde, und liefert das Wetter aus der Fixture."""

            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.reset_calls: list[str] = []

            def _reset_alert_state_after_briefing(self, trip_id: str) -> None:
                self.reset_calls.append(trip_id)
                super()._reset_alert_state_after_briefing(trip_id)

            def _fetch_weather(self, segments, provider=None):
                return [_data(s.segment_id, gust_max_kmh=20.0) for s in segments]

        scheduler = _RecordingScheduler(settings=Settings(), user_id=user_id)
        outcome = scheduler._send_trip_report_outcome(trip, "morning", on_demand=True)

        # Beweis, dass der Ad-hoc-Pfad wirklich bis zum Ende lief (und der Test
        # nicht schon an "keine Etappe"/"kein Wetter" abgebrochen ist).
        assert outcome in ("sent", "no_channels"), (
            f"Der Ad-hoc-Lauf ist vorzeitig abgebrochen: {outcome!r}"
        )
        assert scheduler.reset_calls == [], (
            "Der Ad-hoc-Abruf darf den Briefing-Reset nicht ausloesen (Issue #1007), "
            f"aufgerufen fuer: {scheduler.reset_calls!r}"
        )
        after = AlertStateService(user_id=user_id).load(trip.id)
        assert after == before, (
            f"Das Melde-Gedaechtnis muss unveraendert bleiben.\n"
            f"vorher: {before!r}\nnachher: {after!r}"
        )

        # Gegenprobe: derselbe Lauf OHNE Ad-hoc-Kennzeichen ruft den Reset sehr
        # wohl auf — sonst waere die Aussage oben durch einen toten Pfad erkauft.
        regular = _RecordingScheduler(settings=Settings(), user_id=user_id)
        regular._send_trip_report_outcome(trip, "morning", on_demand=False)
        assert regular.reset_calls == [trip.id], (
            "Der regulaere Briefing-Pfad muss den Reset weiterhin ausloesen, "
            f"aufgerufen fuer: {regular.reset_calls!r}"
        )
    finally:
        _clean_user(user_id)


# ────── Praefix-Kopplung — Schluesselbildung und Reset-Filter laufen nie ─────
# ────── auseinander (#1460 Nebenbefund beim Gate-Fix) ────────────────────────

def test_official_alert_state_key_praefix_stimmt_mit_dem_reset_filter_ueberein():
    """AC-20/AC-22 (Regressionsschutz gegen Auseinanderlaufen der Praefixe).

    GIVEN ein echter `OfficialAlert` und der echte Schluessel, den
          `official_alert_state_key()` (Renderer, official_alerts.py) daraus
          bildet
    WHEN  dieser Schluessel im Melde-Gedaechtnis gespeichert und danach ueber
          den echten `_reset_alert_state_after_briefing()`-Pfad des Schedulers
          zurueckgesetzt wird
    THEN  beginnt der Schluessel mit `OFFICIAL_ALERT_KEY_PREFIX` UND der
          Eintrag ueberlebt den Reset unveraendert. Bricht, wenn Schluessel-
          bildung (hier) und Praefix-Filter (`alert_state.reset()`)
          auseinanderlaufen — egal auf welcher Seite.
    """
    from app.config import Settings
    from output.renderers.alert.official_alerts import official_alert_state_key
    from services.alert_state import OFFICIAL_ALERT_KEY_PREFIX, AlertStateService
    from services.official_alerts import OfficialAlert
    from services.trip_report_scheduler import TripReportSchedulerService

    user_id = _fresh_user("keyprefix")
    _clean_user(user_id)
    try:
        trip_id = "trip-1460-keyprefix"
        now = datetime.now(timezone.utc)
        alert = OfficialAlert(
            source="tdd-1460-keyprefix", hazard="thunderstorm", level=3,
            label="Gewitterwarnung (#1460 Praefix-Kopplung)",
            region_label="Gailtal",
            valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=8),
        )
        key = official_alert_state_key(alert)
        assert key.startswith(OFFICIAL_ALERT_KEY_PREFIX), (
            f"Schluessel von official_alert_state_key() muss mit "
            f"OFFICIAL_ALERT_KEY_PREFIX beginnen, erhalten: {key!r}"
        )

        value = {"last_reported_value": 3.0, "reported_at": now.isoformat()}
        AlertStateService(user_id=user_id).save(trip_id, {key: value})

        TripReportSchedulerService(
            settings=Settings(), user_id=user_id,
        )._reset_alert_state_after_briefing(trip_id)

        after = AlertStateService(user_id=user_id).load(trip_id)
        assert after == {key: value}, (
            "Der ueber official_alert_state_key() gebildete Eintrag muss den "
            f"echten Briefing-Reset unveraendert ueberleben: {after!r}"
        )
    finally:
        _clean_user(user_id)
