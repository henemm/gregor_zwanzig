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


def _data(
    segment_id: int | str = 1,
    *,
    segment: TripSegment | None = None,
    **summary_kwargs,
) -> SegmentWeatherData:
    """Mit `segment` (#1656) wird das ECHTE Etappensegment des Schedulers
    uebernommen statt eines an `datetime.now()` haengenden Fixture-Segments —
    Briefing-Fenster und spaeteres Alarm-Fenster sind dann dieselbe Spanne."""
    return SegmentWeatherData(
        segment=segment if segment is not None else _segment(segment_id),
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


def _trip(trip_id: str, *, with_levels: bool = False, stage_date: date | None = None) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=stage_date or date.today(),
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

    @property
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


# ══════════════ Issue #1614 Teil 1 — Doppelversand-Schutz (Tests 1-7) ════════
#
# SPEC: docs/specs/modules/fix_1614_briefing_warnfenster.md (AC-1 .. AC-7)
#
# RED-Ursache (heute, vor der Implementierung):
# - `services.alert_briefing_anchor.record_official_alerts_reported()`
#   existiert noch nicht -> ImportError/AttributeError in den betroffenen
#   Tests (5, 6, 7 direkter Import; 3, 4 Patch-Versuch auf das nicht
#   vorhandene Modul-Attribut).
# - Der Scheduler-Pfad `_send_trip_report_outcome()` schreibt das
#   Melde-Gedaechtnis der amtlichen Warnungen nirgends -> der unabhaengige
#   Alarm-Checker haelt eine bereits im Briefing gezeigte, unveraenderte
#   Warnung weiterhin fuer "neu" (Test 1/2 -> AssertionError).
#
# Testpolitik: keine Mocks. Die E-Mail-Transportgrenze (`EmailOutput.send`)
# wird per `monkeypatch.setattr` durch eine echte, aufzeichnende Funktion
# ersetzt (Muster `tests/tdd/test_starkregen_kurzfristhinweis.py::
# _install_fake_email_send`) -- kein Netz, kein Objekt-Double.

# Muster `tests/helpers/alert_log_fixtures.py::settings_email_only()`: die
# Trip-Fixtures dieser Datei (`_trip()`) haben `send_email=True` per Default
# -- `can_send_email()` muss also True liefern, sonst wirft
# `EmailOutput.__init__` VOR dem gefakten `send()` (Konstruktions-Check laesst
# sich nicht durch das Patchen von `.send` umgehen). Telegram/SMS bleiben
# unkonfiguriert, weil `_trip()` diese Kanaele nicht aktiviert.
_NO_TRANSPORT_FIELDS_1614: dict = {
    "smtp_host": "dummy.invalid", "smtp_user": "dummy", "smtp_pass": "dummy",
    "mail_to": "dummy@example.com",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
}


def _settings_no_transport_1614():
    from app.config import Settings

    return Settings(**_NO_TRANSPORT_FIELDS_1614)


def _fixture_scheduler_class_1614():
    """Echte Unterklasse (kein Mock): liefert das Wetter aus der Fixture statt
    vom Provider -- Muster test_ac23/test_trip_briefing_anchor_unchanged.py."""
    from services.trip_report_scheduler import TripReportSchedulerService

    class _FixtureScheduler(TripReportSchedulerService):
        def _fetch_weather(self, segments, provider=None):
            # #1656: die ECHTEN Segmente durchreichen. Vorher baute die Fixture
            # eigene, an `datetime.now()` haengende Segmente — der spaetere
            # Alarm-Lauf prueft dann ein ANDERES Zeitfenster als das Briefing,
            # und ab 18:00 UTC fiel die Warnung aus dem Briefing-Fenster.
            return [_data(s.segment_id, segment=s, gust_max_kmh=20.0) for s in segments]

    return _FixtureScheduler


def _install_fake_email_send_1614(monkeypatch) -> list:
    """Ersetzt den Transport-Rand `EmailOutput.send` -- echte Funktion, kein
    Netz, kein Objekt-Double. Liefert die Liste der 'gesendeten'
    (subject, body)-Paare."""
    from output.channels.email import EmailOutput

    sent: list = []

    def _fake_send(self, *, subject, body, **kwargs):
        sent.append((subject, body))

    monkeypatch.setattr(EmailOutput, "send", _fake_send)
    return sent


# #1656: Das Abend-Briefing zielt auf die Etappe von MORGEN. Ein Etappentag
# liegt zu JEDER Tageszeit vollstaendig in der Zukunft — anders als "heute",
# dessen Etappenfenster (06:00-17:00 UTC) am Abend vorbei ist.
def _stage_date_1614() -> date:
    return date.today() + timedelta(days=1)


def _official_alert_1614(hazard: str, level: int, *, region: str = "Gailtal",
                         day: date | None = None):
    """`day` gesetzt (#1656): die Warnung gilt fuer den GANZEN Etappentag
    (00:00 UTC bis 00:00 UTC des Folgetags). Sie ueberlappt damit jedes
    Etappenfenster dieses Tages, egal wann der Test laeuft, und ihr
    State-Schluessel (er enthaelt valid_from/valid_to) bleibt ueber mehrere
    Aufrufe hinweg IDENTISCH — nur so prueft die Eskalations-Gegenprobe
    wirklich den Level-Vergleich und nicht bloss einen neuen Schluessel.

    Ohne `day` bleibt das bisherige, an `jetzt` haengende Fenster."""
    from services.official_alerts import OfficialAlert

    if day is not None:
        valid_from = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        valid_to = valid_from + timedelta(days=1)
    else:
        now = datetime.now(timezone.utc)
        valid_from, valid_to = now - timedelta(hours=1), now + timedelta(hours=8)
    return OfficialAlert(
        source="tdd-1614", hazard=hazard, level=level,
        label=f"{hazard}-Warnung (#1614)", region_label=region,
        valid_from=valid_from, valid_to=valid_to,
    )


def test_briefing_meldet_unveraenderte_amtliche_warnung_danach_nicht_erneut(monkeypatch):
    """Test 1 / AC-1.

    GIVEN ein Trip-Briefing wurde erfolgreich mit einer amtlichen Warnung X
          versendet (echter `_send_trip_report_outcome()`-Aufrufpfad)
    WHEN  danach `TripAlertService.check_official_alert_triggers()` fuer
          denselben Trip mit unveraenderter Warnung X (gleiches Level) laeuft
    THEN  liefert der Checker X NICHT als neu/eskaliert zurueck (kein
          Doppelversand -- Mail-Paar `86918bc7`/`7d0bbfd6` aus der Forensik).

    RED (heute): der Briefing-Pfad schreibt das Melde-Gedaechtnis nirgends,
    der Checker haelt X weiterhin fuer neu -> `again` ist nicht leer.

    #1656: Abend-Briefing auf die Etappe von MORGEN. Das Etappenfenster liegt
    damit zu jeder Tageszeit in der Zukunft; die beiden Vorbedingungen unten
    verhindern, dass die leere Erwartung `again == []` still dadurch erfuellt
    wird, dass gar nichts mehr geprueft wurde.
    """
    from services.alert_state import OFFICIAL_ALERT_KEY_PREFIX, AlertStateService
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_id = _fresh_user("t1614-1")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        stage_date = _stage_date_1614()
        trip = _trip("trip-1614-t1", stage_date=stage_date)
        sent = _install_fake_email_send_1614(monkeypatch)
        alert = _official_alert_1614("thunderstorm", 2, day=stage_date)
        source = _FixedOfficialAlertSource(LAT, LON, alert)
        register_official_alert_source(source)

        scheduler = _fixture_scheduler_class_1614()(
            settings=_settings_no_transport_1614(), user_id=user_id,
        )
        outcome = scheduler._send_trip_report_outcome(trip, "evening", on_demand=False)
        assert outcome == "sent", f"Vorbedingung: der Versand muss gelingen ({outcome!r})"
        assert sent, "Vorbedingung: die Briefing-Mail wurde tatsaechlich gerendert"

        # Vorbedingung A: die Warnung lag wirklich IM Briefing und wurde
        # vermerkt. Ohne diese Pruefung waere `again == []` auch dann erfuellt,
        # wenn die Warnung nie im Briefing-Fenster gelandet waere.
        state_after_briefing = AlertStateService(user_id=user_id).load(trip.id)
        assert [k for k in state_after_briefing if k.startswith(OFFICIAL_ALERT_KEY_PREFIX)], (
            "Vorbedingung: das Briefing muss die amtliche Warnung ins "
            f"Melde-Gedaechtnis geschrieben haben, vorhanden: {sorted(state_after_briefing)!r}"
        )

        fetches_before = source.fetch_calls
        again = TripAlertService(user_id=user_id).check_official_alert_triggers(trip)
        # Vorbedingung B: der Alarm-Lauf hat die Quelle ueberhaupt befragt —
        # sonst liefert er trivial [] (kein Wetter im Cache, Etappe vorbei).
        assert source.fetch_calls > fetches_before, (
            "Vorbedingung: der Alarm-Lauf muss die Quelle befragt haben, sonst "
            "ist die leere Erwartung wertlos"
        )
        assert again == [], (
            "Dieselbe amtliche Warnung darf nach einem erfolgreichen Briefing nicht "
            f"erneut als neu gemeldet werden (Doppelversand #1614), erhalten: {again!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_eskalierte_warnung_wird_trotz_bereits_gemeldeter_unveraenderter_warnung_weiterhin_gemeldet(
    monkeypatch,
):
    """Test 2 / AC-2 (Eskalations-Gegenprobe).

    GIVEN dasselbe Vorbriefing wie Test 1 -- ZWEI amtliche Warnungen
          (unveraendert: thunderstorm Stufe 2; spaeter eskalierend: flood)
          wurden erfolgreich im Briefing gemeldet
    WHEN  danach NUR "flood" auf Stufe 3 eskaliert
    THEN  meldet der Checker AUSSCHLIESSLICH die eskalierte Warnung ("flood")
          -- NICHT die unveraenderte ("thunderstorm").

    RED (heute): ohne Doppelversand-Schutz erscheint "thunderstorm" (die
    unveraenderte Warnung) ebenfalls wieder -> die Menge der gemeldeten
    Gefahren ist nicht `{"flood"}`, sondern `{"flood", "thunderstorm"}`.

    #1656: Abend-Briefing auf die Etappe von MORGEN (Etappenfenster liegt zu
    jeder Tageszeit in der Zukunft). Die Erwartung `{"flood"}` ist beidseitig
    scharf: sie faellt, wenn die unveraenderte Warnung erneut auftaucht, UND
    sie faellt, wenn ueberhaupt nichts mehr geprueft wird.
    """
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService

    user_id = _fresh_user("t1614-2")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        stage_date = _stage_date_1614()
        trip = _trip("trip-1614-t2", stage_date=stage_date)
        _install_fake_email_send_1614(monkeypatch)

        unchanged = _official_alert_1614("thunderstorm", 2, day=stage_date)
        register_official_alert_source(_FixedOfficialAlertSource(LAT, LON, unchanged))
        escalating_source = _FixedOfficialAlertSource(
            LAT, LON, _official_alert_1614("flood", 2, day=stage_date),
        )
        register_official_alert_source(escalating_source)

        scheduler = _fixture_scheduler_class_1614()(
            settings=_settings_no_transport_1614(), user_id=user_id,
        )
        outcome = scheduler._send_trip_report_outcome(trip, "evening", on_demand=False)
        assert outcome == "sent", f"Vorbedingung: der Versand muss gelingen ({outcome!r})"

        # Gleicher Zeitraum, hoeherer Level -> gleicher State-Schluessel: der
        # Checker muss den Level-Vergleich anstellen, nicht bloss einen neuen
        # Schluessel sehen.
        escalating_source._alert = _official_alert_1614("flood", 3, day=stage_date)

        triggered = TripAlertService(user_id=user_id).check_official_alert_triggers(trip)
        hazards = {a.hazard for a, _seg in triggered}
        assert hazards == {"flood"}, (
            "Eine echte Verschaerfung ('flood') muss weiterhin gemeldet werden, eine "
            "unveraenderte Warnung ('thunderstorm') darf NICHT erneut auftauchen "
            f"(Doppelversand #1614): {triggered!r}"
        )
        (flood_entry,) = [a for a, _seg in triggered if a.hazard == "flood"]
        assert flood_entry.level == 3
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_ad_hoc_abruf_schreibt_das_melde_gedaechtnis_amtlicher_warnungen_nicht(monkeypatch):
    """Test 3 / AC-3 (Ad-hoc-Ausnahme, #1007).

    GIVEN ein On-Demand-Abruf (`on_demand=True`) liefert dieselbe amtliche
          Warnung
    WHEN  der Abruf abgeschlossen ist
    THEN  bleibt das Melde-Gedaechtnis unveraendert -- die neue
          Record-Funktion wird kein einziges Mal aufgerufen.

    RED (heute): `record_official_alerts_reported` existiert noch nicht auf
    `services.alert_briefing_anchor` -> `monkeypatch.setattr(..., raising=True)`
    wirft AttributeError.

    #1656: Abend-Briefing auf die Etappe von MORGEN, dazu die positive
    Gegenprobe am Ende. Ohne sie war die leere Erwartung ab 18:00 UTC
    wertlos -- die Warnung fiel dann aus dem Briefing-Fenster, und der Test
    bestand auch dann noch, wenn die Ad-hoc-Ausnahme ganz entfernt wurde
    (gemessen: `if result.sent and not on_demand:` -> `if result.sent:` faellt
    um 09:00, um 19:00 nicht).
    """
    import services.alert_briefing_anchor as anchor_mod_1614
    from services.alert_state import AlertStateService
    from services.official_alerts import register_official_alert_source

    user_id = _fresh_user("t1614-3")
    _clean_user(user_id)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        stage_date = _stage_date_1614()
        trip = _trip("trip-1614-t3", stage_date=stage_date)
        _install_fake_email_send_1614(monkeypatch)
        register_official_alert_source(
            _FixedOfficialAlertSource(
                LAT, LON, _official_alert_1614("thunderstorm", 2, day=stage_date),
            )
        )

        calls: list = []

        def _fake_record(*, user_id, entity_id, alerts):
            calls.append((user_id, entity_id, alerts))

        monkeypatch.setattr(anchor_mod_1614, "record_official_alerts_reported", _fake_record)

        before = AlertStateService(user_id=user_id).load(trip.id)

        scheduler = _fixture_scheduler_class_1614()(
            settings=_settings_no_transport_1614(), user_id=user_id,
        )
        outcome = scheduler._send_trip_report_outcome(trip, "evening", on_demand=True)
        assert outcome in ("sent", "no_channels", "channels_unreachable"), (
            f"Der Ad-hoc-Lauf ist vorzeitig abgebrochen: {outcome!r}"
        )

        assert calls == [], (
            f"Der Ad-hoc-Abruf (#1007) darf die neue Record-Funktion nicht aufrufen: {calls!r}"
        )
        after = AlertStateService(user_id=user_id).load(trip.id)
        assert after == before, "Das Melde-Gedaechtnis darf sich durch einen Ad-hoc-Abruf nicht aendern"

        # Positive Gegenprobe (Muster test_ac23): derselbe Lauf OHNE Ad-hoc-
        # Kennzeichen ruft die Record-Funktion sehr wohl. Sonst waere die leere
        # Erwartung oben auch dadurch erfuellt, dass die Warnung gar nicht erst
        # im Briefing landete.
        regular = _fixture_scheduler_class_1614()(
            settings=_settings_no_transport_1614(), user_id=user_id,
        )
        regular_outcome = regular._send_trip_report_outcome(trip, "evening", on_demand=False)
        assert regular_outcome == "sent", (
            f"Gegenprobe: der regulaere Versand muss gelingen ({regular_outcome!r})"
        )
        assert len(calls) == 1, (
            "Gegenprobe: der REGULAERE Briefing-Lauf muss die Warnung genau einmal "
            f"vermerken, erhalten: {calls!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)


def test_fehlgeschlagener_versand_schreibt_das_melde_gedaechtnis_nicht(monkeypatch):
    """Test 4 / AC-4 (fehlgeschlagener Versand, neuer Fall).

    GIVEN `result.sent` ist `False` (Telegram konfiguriert, aber garantiert
          scheiternd -- `is_test_mode`-Guard von `TelegramOutput`, kein
          Live-Netz -- E-Mail bewusst deaktiviert)
    WHEN  `_send_trip_report_outcome()` durchlaeuft
    THEN  wird die neue Record-Funktion NICHT aufgerufen -- eine nie
          zugestellte Warnung darf den Alarm-Checker nicht stumm schalten.

    RED (heute): `record_official_alerts_reported` existiert noch nicht ->
    `monkeypatch.setattr(..., raising=True)` wirft AttributeError.

    #1656: Abend-Briefing auf die Etappe von MORGEN, dazu die positive
    Gegenprobe VOR der eigentlichen Pruefung -- ein GELINGENDER Versand mit
    demselben Aufbau muss vermerken. Ohne sie war die leere Erwartung ab
    18:00 UTC wertlos (gemessen: entfernt man die Zustellpruefung
    `result.sent`, faellt der Test um 09:00, um 19:00 nicht).
    """
    import services.alert_briefing_anchor as anchor_mod_1614
    from services.official_alerts import register_official_alert_source
    from tests.helpers.alert_log_fixtures import settings_email_and_failing_telegram

    user_id = _fresh_user("t1614-4")
    control_user = _fresh_user("t1614-4-kontrolle")
    _clean_user(user_id)
    _clean_user(control_user)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        stage_date = _stage_date_1614()
        trip = _trip("trip-1614-t4", stage_date=stage_date)
        trip.report_config = TripReportConfig(
            trip_id=trip.id, send_email=False, send_telegram=True, send_sms=False,
        )
        register_official_alert_source(
            _FixedOfficialAlertSource(
                LAT, LON, _official_alert_1614("thunderstorm", 2, day=stage_date),
            )
        )

        calls: list = []

        def _fake_record(*, user_id, entity_id, alerts):
            calls.append((user_id, entity_id, alerts))

        monkeypatch.setattr(anchor_mod_1614, "record_official_alerts_reported", _fake_record)

        # Positive Gegenprobe: gleicher Aufbau, gleiche Warnung, aber der
        # Versand GELINGT (eigener Nutzer, E-Mail-Transport gefakt) -- dann
        # wird vermerkt. Erst damit ist die leere Erwartung unten aussagekraeftig.
        _install_fake_email_send_1614(monkeypatch)
        control_trip = _trip("trip-1614-t4-kontrolle", stage_date=stage_date)
        control_outcome = _fixture_scheduler_class_1614()(
            settings=_settings_no_transport_1614(), user_id=control_user,
        )._send_trip_report_outcome(control_trip, "evening", on_demand=False)
        assert control_outcome == "sent", (
            f"Gegenprobe: der gelingende Versand muss 'sent' liefern ({control_outcome!r})"
        )
        assert len(calls) == 1, (
            "Gegenprobe: ein GELUNGENER Versand muss die Warnung vermerken, sonst "
            f"prueft der eigentliche Fall unten nichts: {calls!r}"
        )
        calls.clear()

        scheduler = _fixture_scheduler_class_1614()(
            settings=settings_email_and_failing_telegram(), user_id=user_id,
        )
        outcome = scheduler._send_trip_report_outcome(trip, "evening", on_demand=False)
        assert outcome == "channels_unreachable", (
            f"Vorbedingung: der Versand muss ehrlich als nicht zugestellt gelten ({outcome!r})"
        )
        assert calls == [], (
            f"Ein fehlgeschlagener Versand darf die Warnung nicht als 'gemeldet' vermerken: {calls!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(user_id)
        _clean_user(control_user)


def test_record_official_alert_state_wrapper_liefert_denselben_eintrag_wie_die_neue_funktion():
    """Test 5 / AC-5 (Wrapper-Regression).

    GIVEN identische Eingaben (Alert, Trip-Kennung)
    WHEN  einmal ueber den ALTEN Weg (`TripAlertService._record_official_
          alert_state`, wird nach dem Refactor zum duennen Wrapper) und
          einmal ueber die NEUE geteilte Funktion
          (`record_official_alerts_reported`) geschrieben wird
    THEN  entsteht in beiden Faellen exakt derselbe Schluessel mit demselben
          Level -- der Wrapper darf das Verhalten nicht veraendern.

    RED (heute): `record_official_alerts_reported` existiert noch nicht in
    `services.alert_briefing_anchor` -> ImportError.
    """
    from services.alert_briefing_anchor import record_official_alerts_reported
    from services.alert_state import AlertStateService
    from services.trip_alert import TripAlertService

    user_a = _fresh_user("t1614-5a")
    user_b = _fresh_user("t1614-5b")
    _clean_user(user_a)
    _clean_user(user_b)
    try:
        trip_id = "trip-1614-t5"
        alert = _official_alert_1614("thunderstorm", 2)
        official_notices = [(alert, ["1"])]

        TripAlertService(user_id=user_a)._record_official_alert_state(trip_id, official_notices)
        via_wrapper = AlertStateService(user_id=user_a).load(trip_id)

        record_official_alerts_reported(user_id=user_b, entity_id=trip_id, alerts=[alert])
        via_new_function = AlertStateService(user_id=user_b).load(trip_id)

        assert set(via_wrapper) == set(via_new_function), (
            "Wrapper und neue Funktion muessen dieselben Schluessel erzeugen: "
            f"{sorted(via_wrapper)!r} vs {sorted(via_new_function)!r}"
        )
        for key, value in via_wrapper.items():
            assert value["last_reported_value"] == via_new_function[key]["last_reported_value"], (
                f"Unterschiedlicher Level fuer {key!r}: {value!r} vs {via_new_function[key]!r}"
            )
            assert "reported_at" in via_new_function[key]
    finally:
        _clean_user(user_a)
        _clean_user(user_b)


def test_record_official_alerts_reported_laeuft_bei_kaltstart_fehlerfrei_durch():
    """Test 6 / AC-6 (Kaltstart).

    GIVEN ein Trip ohne jeden vorherigen `official_alert:`-State-Eintrag
    WHEN  `record_official_alerts_reported()` mit einer amtlichen Warnung
          aufgerufen wird
    THEN  laeuft der Aufruf fehlerfrei durch und legt einen gueltigen
          Eintrag an.

    RED (heute): `record_official_alerts_reported` existiert noch nicht ->
    ImportError.
    """
    from services.alert_briefing_anchor import record_official_alerts_reported
    from services.alert_state import AlertStateService

    user_id = _fresh_user("t1614-6")
    _clean_user(user_id)
    try:
        trip_id = "trip-1614-t6"
        assert AlertStateService(user_id=user_id).load(trip_id) == {}, (
            "Vorbedingung: kein vorheriger Eintrag"
        )
        alert = _official_alert_1614("thunderstorm", 2)

        record_official_alerts_reported(user_id=user_id, entity_id=trip_id, alerts=[alert])

        after = AlertStateService(user_id=user_id).load(trip_id)
        assert len(after) == 1, f"Erwartet genau einen neuen Eintrag: {after!r}"
        (entry,) = after.values()
        assert entry["last_reported_value"] == 2.0
        assert "reported_at" in entry
    finally:
        _clean_user(user_id)


def test_record_official_alerts_reported_beruehrt_nur_den_eigenen_nutzer():
    """Test 7 / AC-7 (Mandantentrennung, CLAUDE.md-Pflicht).

    GIVEN zwei verschiedene `user_id`s mit je einem Trip und je einer
          identischen amtlichen Warnung
    WHEN  fuer Nutzer A `record_official_alerts_reported()` aufgerufen wird
    THEN  bleibt das Melde-Gedaechtnis von Nutzer B unveraendert.

    RED (heute): `record_official_alerts_reported` existiert noch nicht ->
    ImportError.
    """
    from services.alert_briefing_anchor import record_official_alerts_reported
    from services.alert_state import AlertStateService

    user_a = _fresh_user("t1614-7a")
    user_b = _fresh_user("t1614-7b")
    _clean_user(user_a)
    _clean_user(user_b)
    try:
        trip_id = "trip-1614-t7"
        alert = _official_alert_1614("thunderstorm", 2)

        record_official_alerts_reported(user_id=user_a, entity_id=trip_id, alerts=[alert])

        assert AlertStateService(user_id=user_a).load(trip_id) != {}
        assert AlertStateService(user_id=user_b).load(trip_id) == {}, (
            "Nutzer B darf durch das Melde-Gedaechtnis von Nutzer A nicht beruehrt werden"
        )
    finally:
        _clean_user(user_a)
        _clean_user(user_b)


def test_record_official_alerts_reported_mit_leerer_liste_ist_ein_no_op():
    """F001 (Adversary-Mutations-Fund, #1614). GIVEN kein vorheriger State,
    WHEN record_official_alerts_reported() mit leerer alerts-Liste aufgerufen
    wird, THEN wird keine State-Datei angelegt/veraendert (No-Op-Vertrag).

    RED-Nachweis (Mutations-Gegenprobe): der Fail-soft-Guard `if not alerts:
    return` in `record_official_alerts_reported()` wurde entfernt -- alle
    bestehenden Tests dieser Datei blieben gruen, weil keiner die Funktion
    mit einer leeren Liste aufruft. Dieser Test prueft nicht nur den
    Rueckgabewert von `load()` (leeres dict), sondern dass die Datei
    ueberhaupt nicht existiert -- das ist der eigentliche No-Op-Vertrag
    laut Docstring, nicht bloss ein zufaellig leerer State.
    """
    from services.alert_briefing_anchor import record_official_alerts_reported
    from services.alert_state import AlertStateService

    user_id = _fresh_user("t1614-f001")
    _clean_user(user_id)
    try:
        trip_id = "trip-1614-f001"
        svc = AlertStateService(user_id=user_id)
        state_path = svc._path(trip_id)
        assert not state_path.exists(), "Vorbedingung: keine State-Datei vorhanden"

        record_official_alerts_reported(user_id=user_id, entity_id=trip_id, alerts=[])

        assert AlertStateService(user_id=user_id).load(trip_id) == {}, (
            "Bei leerer alerts-Liste darf kein State entstehen"
        )
        assert not state_path.exists(), (
            "No-Op-Vertrag verletzt: record_official_alerts_reported() hat trotz leerer "
            f"alerts-Liste eine State-Datei angelegt ({state_path!r})"
        )
    finally:
        _clean_user(user_id)
