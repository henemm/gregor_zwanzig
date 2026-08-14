"""TDD RED/Regressionsschutz — Issue #1460 Teil 1: Mandantentrennung ueber alle
vier Pakete (P1a/P1b/P2/P4).

SPEC: docs/specs/modules/rework_1460_t1_relevanzfilter.md (AC-34)

Zwei Nutzer (`alice`, `bob`) mit strukturell identischen Touren/Vergleichen:
gleiche Wertebereiche, gleiche Empfindlichkeitsstufen, gleiche amtliche Warnung
an denselben Koordinaten. Jeder Melde-Gedaechtnis- und Protokoll-Effekt muss
ausschliesslich im Verzeichnis des jeweiligen Nutzers landen.

Dieser Test ist ein REGRESSIONSSCHUTZ: er darf heute schon gruen sein (die
Mandantentrennung haelt bereits). Er sichert ab, dass keine der vier Aenderungen
dieser Scheibe sie aufbricht — insbesondere der neue, teilweise Reset in
`alert_state.reset()` (P2) und der erweiterte Dedup-Schluessel in
`check_official_alert_triggers()` (P4).

Keine Mocks: echte Nutzerverzeichnisse, echte Persistenz, echte Quelle ueber
`register_official_alert_source()`, `mail_sink`-DI-Naht statt SMTP. Kein Netz.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.models import (
    Corridor,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripReportConfig,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint
from services.official_alerts.models import OfficialAlert

from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip

# Pfadregel #1409: Pruefling relativ zur Testdatei, nicht ueber den Hauptrepo-Pfad.
DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

LAT, LON = 47.0, 11.0
TRIP_ID = "trip-1460-tenancy"


def _clean_user(uid: str) -> None:
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _user_pair() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:6]
    return f"tdd-1460-alice-{suffix}", f"tdd-1460-bob-{suffix}"


def _segment(segment_id: str = "1") -> TripSegment:
    now = datetime.now(timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=LAT + 0.01, lon=LON + 0.01, elevation_m=1500,
                           distance_from_start_km=8.0),
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        duration_hours=4.0,
        distance_km=8.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(**summary_kwargs) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _identical_trip() -> Trip:
    """Strukturell identische Tour fuer beide Nutzer: gleicher Wertebereich
    (P1a), gleiche Empfindlichkeitsstufen fuer Boeen und Gewitter (P1b),
    amtliche Warnungen aktiv (P4)."""
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(
        id=TRIP_ID, name="Mandanten-Trip", stages=[stage], official_warnings=None,
        corridors=[Corridor(metric="wind_gust", range=[None, 20.0], notify=True)],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=TRIP_ID,
            metrics=[
                # "gust" ist die Katalog-Kennung fuer Boeen ("wind" waere der
                # mittlere Wind -- damit bliebe der Boeen-Anteil wirkungslos).
                MetricConfig(metric_id="gust", enabled=True),
                MetricConfig(metric_id="thunder", enabled=True),
            ],
            metric_alert_levels={"wind_gust": "standard", "thunder_level": "sensibel"},
        ),
    )
    # Issue #1594: Briefing-Zeiten ausserhalb des Vorlaufs — sonst schweigt der
    # Alarm wegen der Sperre und die Mandantentrennung bleibt ungemessen.
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=TRIP_ID, send_email=True, alert_on_changes=True,
        morning_time=morgen, evening_time=abend,
    )
    trip.alert_cooldown_minutes = 0
    return trip


def _save_cached(user_id: str, cached: list[SegmentWeatherData]) -> None:
    from services.weather_snapshot import WeatherSnapshotService

    WeatherSnapshotService(user_id=user_id).save_dated(TRIP_ID, date.today(), cached)


def _state_dir(user_id: str) -> Path:
    from app.loader import get_data_dir

    return get_data_dir(user_id) / "alert_state"


def _alert_log(user_id: str) -> list:
    from app.loader import get_data_dir

    path = get_data_dir(user_id) / "alert_log.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    if isinstance(raw, dict):
        return list(raw.get("entries") or []) + list(raw.get("not_delivered") or [])
    return list(raw or [])


class _FixedSource:
    """Echte Quelle (kein Mock), zustaendig fuer einen Punkt (0.05-Toleranz)."""

    def __init__(self, alert: OfficialAlert) -> None:
        self._alert = alert

    property
    def name(self) -> str:
        return "tdd-1460-tenancy-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - LAT) < 0.05 and abs(lon - LON) < 0.05

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        return [self._alert]


def _sources_backup():
    import services.official_alerts.base as b

    return b, list(b._REGISTERED_SOURCES)


def test_ac34_melde_gedaechtnis_und_protokoll_bleiben_nutzergetrennt():
    """AC-34.

    GIVEN zwei Nutzer (alice, bob) mit strukturell identischen Touren — gleiche
          Wertebereiche, gleiche Empfindlichkeitsstufen, dieselbe amtliche
          Warnung an denselben Koordinaten
    WHEN  die Auswertung (Wertebereich, Empfindlichkeitsstufe, amtliche Warnung,
          Briefing-Reset) nacheinander fuer beide Nutzer laeuft
    THEN  landet jeder Melde-Gedaechtnis- und Protokoll-Effekt ausschliesslich
          im Verzeichnis des jeweiligen Nutzers — nie im des anderen.
    """
    from services.alert_state import AlertStateService
    from services.official_alerts import register_official_alert_source
    from services.trip_alert import TripAlertService
    from services.trip_report_scheduler import TripReportSchedulerService
    from app.config import Settings

    alice, bob = _user_pair()
    _clean_user(alice)
    _clean_user(bob)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        now = datetime.now(timezone.utc)
        alert = OfficialAlert(
            source="tdd-1460-tenancy", hazard="thunderstorm", level=3,
            label="Gewitterwarnung (#1460 AC-34)", region_label="Testregion",
            valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=2),
        )
        register_official_alert_source(_FixedSource(alert))

        trip_alice, trip_bob = _identical_trip(), _identical_trip()
        cached = [_data(gust_max_kmh=10.0, thunder_level_max=ThunderLevel.NONE)]
        fresh = [_data(gust_max_kmh=35.0, thunder_level_max=ThunderLevel.HIGH)]
        _save_cached(alice, cached)
        _save_cached(bob, cached)

        # ── Schritt 1: nur alice laeuft ──────────────────────────────────────
        mail_alice: list = []
        svc_alice = TripAlertService(
            user_id=alice, mail_sink=lambda subject, body: mail_alice.append((subject, body)),
        )
        notices_alice = svc_alice.check_official_alert_triggers(trip_alice)
        assert len(notices_alice) == 1, (
            f"Vorbedingung: alice sieht die amtliche Warnung ({notices_alice!r})"
        )
        assert svc_alice.check_and_send_alerts(
            trip_alice, cached, fresh_weather=fresh, official_notices=notices_alice,
        ) is True, "Vorbedingung: alice bekommt einen Alarm"

        assert _state_dir(alice).exists() and any(_state_dir(alice).iterdir()), (
            "Vorbedingung: alice hat ein Melde-Gedaechtnis"
        )
        assert _alert_log(alice), "Vorbedingung: alice hat einen Protokoll-Eintrag"

        assert not (_state_dir(bob).exists() and any(_state_dir(bob).iterdir())), (
            "Kreuz-Kontamination: bobs Melde-Gedaechtnis wurde von alices Lauf "
            f"geschrieben: {sorted(p.name for p in _state_dir(bob).iterdir())!r}"
        )
        assert _alert_log(bob) == [], (
            f"Kreuz-Kontamination: bobs Protokoll wurde beschrieben: {_alert_log(bob)!r}"
        )

        # ── Schritt 2: bob laeuft mit identischer Lage ───────────────────────
        # Die Entprellung von alice darf bob NICHT stumm schalten.
        mail_bob: list = []
        svc_bob = TripAlertService(
            user_id=bob, mail_sink=lambda subject, body: mail_bob.append((subject, body)),
        )
        notices_bob = svc_bob.check_official_alert_triggers(trip_bob)
        assert len(notices_bob) == 1, (
            "bob muss dieselbe amtliche Warnung eigenstaendig als neu sehen, "
            f"erhalten: {notices_bob!r}"
        )
        assert svc_bob.check_and_send_alerts(
            trip_bob, cached, fresh_weather=fresh, official_notices=notices_bob,
        ) is True, "bob muss seinen eigenen Alarm bekommen"
        assert len(mail_bob) == 1, f"Erwartet genau 1 Meldung fuer bob: {len(mail_bob)}"
        assert len(mail_alice) == 1, (
            f"alices Meldungszahl darf sich durch bobs Lauf nicht aendern: {len(mail_alice)}"
        )

        # ── Schritt 3: Briefing-Reset nur fuer alice ─────────────────────────
        state_bob_before = AlertStateService(user_id=bob).load(TRIP_ID)
        assert state_bob_before, "Vorbedingung: bob hat ein Melde-Gedaechtnis"

        TripReportSchedulerService(
            settings=Settings(), user_id=alice,
        )._reset_alert_state_after_briefing(TRIP_ID)

        state_bob_after = AlertStateService(user_id=bob).load(TRIP_ID)
        assert state_bob_after == state_bob_before, (
            "Kreuz-Kontamination: alices Briefing-Reset hat bobs Melde-Gedaechtnis "
            f"veraendert.\nvorher: {state_bob_before!r}\nnachher: {state_bob_after!r}"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(alice)
        _clean_user(bob)


def test_ac34b_wertebereich_wirkt_bei_beiden_nutzern_gleich_nicht():
    """AC-34 (P1a-Anteil).

    GIVEN zwei Nutzer mit identischer Tour, deren EINZIGE eingestellte
          Alarmquelle ein gerissener Wertebereich ist
    WHEN  der Alarm-Lauf fuer beide Nutzer nacheinander laeuft
    THEN  bleibt es bei BEIDEN still und in KEINEM der beiden Verzeichnisse
          entsteht ein Melde-Gedaechtnis oder ein Protokoll-Eintrag.
    """
    from services.trip_alert import TripAlertService

    alice, bob = _user_pair()
    _clean_user(alice)
    _clean_user(bob)
    try:
        stage = Stage(
            id="T1", name="Tag 1", date=date.today(),
            waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
        )
        cached = [_data(gust_max_kmh=25.0)]

        for user_id in (alice, bob):
            trip = Trip(
                id=TRIP_ID, name="Nur-Wertebereich", stages=[stage],
                official_warnings=None,
                corridors=[Corridor(metric="wind_gust", range=[None, 20.0], notify=True)],
            )
            trip.report_config = TripReportConfig(
                trip_id=TRIP_ID, send_email=True, alert_on_changes=False,
            )
            trip.alert_cooldown_minutes = 0
            trip.official_alert_triggers_enabled = False
            _save_cached(user_id, cached)

            mails: list = []
            svc = TripAlertService(
                user_id=user_id, mail_sink=lambda subject, body: mails.append((subject, body)),
            )
            sent = svc.check_and_send_alerts(trip, cached, fresh_weather=cached)

            assert sent is False, f"{user_id}: der Wertebereich darf nicht mehr ausloesen"
            assert mails == [], f"{user_id}: es darf keine Meldung rausgehen ({len(mails)})"
            assert _alert_log(user_id) == [], (
                f"{user_id}: es darf kein Protokoll-Eintrag entstehen ({_alert_log(user_id)!r})"
            )
    finally:
        _clean_user(alice)
        _clean_user(bob)
