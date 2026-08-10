"""TDD RED — Issue #1629: der Briefing-Anker ueberlebt einen Versandfehler.

Seit Issue #1662 (zweiter Abschnitt am Dateiende, SPEC:
`docs/specs/modules/fix_1662_versandfehler_nachliefern.md`, AC-1..AC-13) deckt
diese Datei zusaetzlich die NACHLIEFERUNG eines gescheiterten Versands ab —
gleicher Fehlerpfad, gleiche mockfreien Helfer, deshalb dieselbe Datei.

SPEC: docs/specs/modules/fix_1629_briefing_anker_versandfehler.md (AC-1, AC-3
bis AC-7, AC-9, AC-10). AC-2 liegt im Compare-Pendant
`test_compare_briefing_anchor_survives_dispatch_failure.py`, AC-8 ist ein
Go-Test (Spec-Abschnitt "Hinweis fuer die TDD-RED-Phase").

Gemessener Defekt (Prod, 2026-08-08): `trip_report_scheduler.py:958`
(`send_trip_report`) hat kein `try/except`. Wirft der E-Mail-Kanal — im echten
Fall der Resend-Allowlist-Guard, `output/channels/email.py:678-731` —, fliegt
die Ausnahme bis `dispatch_orchestrator.py:66-79` hoch und ueberspringt dabei
`write_anchor_and_reset_memory(...)` bei `:1046`. Folge: kein datierter und
kein undatierter Wetter-Snapshot, kein Melde-Reset. Der Abweichungs-Alarm des
Tages faellt ganztaegig aus (AC-9).

Test-Politik (kein Mock-Theater):

* Der Versandfehler wird **nicht** durch ein werfendes Double erzeugt, sondern
  durch eine echte, unzulaessige Kanal-Konfiguration: E-Mail ist fuer die Tour
  eingeschaltet, die SMTP-Zugangsdaten sind aber unvollstaendig. Es laeuft der
  ECHTE Guard im echten `EmailOutput` und wirft den ECHTEN `OutputConfigError`
  — dieselbe Ausnahmeklasse, aus demselben Modul, auf demselben Weg wie am
  08.08. in Prod. Kein Netz: der Guard schlaegt vor jedem Verbindungsaufbau zu.

  Warum nicht der Resend-Allowlist-Guard selbst (der Prod-Ausloeser)? Er ist im
  deterministischen Kern-Testlauf **strukturell unerreichbar**, und zwar
  doppelt: `Settings._resend_default_deny()` (#1122) lenkt jeden
  Resend-Host in einem pytest-Prozess auf `mail.henemm.com` um, und die
  Herkunftssperre `EmailOutput.send()` (#1476) ersetzt bei Testlauf-Herkunft
  jeden Empfaenger durch `gregor-test@henemm.com` — der ist lokal zustellbar
  und passiert beide Empfaenger-Guards. Gemessen: der Versuch endete in einem
  ECHTEN Verbindungsaufbau zu `mail.henemm.com` (535 Auth). Ein Kern-Test darf
  das nicht ausloesen. Fuer den Pruefgegenstand ist der Unterschied folgenlos:
  entscheidend ist, dass `send_trip_report()` mit einer Ausnahme abbricht.
* Ersetzt werden nur teure Upstream-Abhaengigkeiten (Provider-Abruf) durch
  echte Unterklassen bzw. gleichwertige Implementierungen — Haus-Muster aus
  `test_trip_briefing_anchor_unchanged.py` und
  `test_compare_briefing_anchor_and_memory_reset.py`.
* Geprueft wird der echte Dateizustand ueber die echten Services, nie ein
  Dateiinhalt-String.

Versand-Sicherheit (#1477): `Settings(...)` faellt bei fehlenden Feldern still
auf die Prod-`.env` im Worktree zurueck. Jede hier gebaute `Settings`-Instanz
setzt deshalb ALLE Transport-Felder ausdruecklich; Telegram/SMS sind
ausdruecklich leer und werden vor dem Lauf gegengeprueft.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
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

# Pfadregel #1409: Pruefling relativ zur Testdatei aufloesen, nie ueber einen
# festen Hauptrepo-Pfad — sonst pruefte dieser Test aus dem Worktree die
# unveraenderte Hauptrepo-Kopie und meldete falsches Gruen.
REPO_ROOT = Path(__file__).resolve().parents[2]

LAT, LON = 47.0, 11.0

# Alle Transport-Felder ausdruecklich unbrauchbar: `Settings()` faellt bei
# fehlenden Feldern still auf die Prod-`.env` im Worktree zurueck (#1477).
_BROKEN_EMAIL_FIELDS: dict = {
    # Unvollstaendige SMTP-Konfiguration -> `EmailOutput.__init__()` wirft
    # `OutputConfigError`, ohne je eine Verbindung aufzubauen.
    "smtp_host": "", "smtp_user": "", "smtp_pass": "", "mail_to": "",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
}

# Vollstaendig konfigurierter, aber nie gewaehlter Postausgang: der
# Alarm-Pfad (AC-9) prueft `can_send_email()`, bevor er ueberhaupt etwas tut —
# der tatsaechliche Versand laeuft dort ueber die `mail_sink`-Naht.
_DUMMY_EMAIL_FIELDS: dict = {
    **_BROKEN_EMAIL_FIELDS,
    "smtp_host": "dummy.invalid", "smtp_user": "dummy", "smtp_pass": "dummy",
    "mail_to": "dummy@example.com",
}


def _settings_email_broken() -> Settings:
    """Echte Settings, deren E-Mail-Versand am echten Konfigurations-Guard
    scheitert — der Versandaufruf wird erreicht und wirft dort."""
    settings = Settings(**_BROKEN_EMAIL_FIELDS)
    assert settings.can_send_email() is False, (
        "Vorbedingung: der E-Mail-Kanal darf NICHT sendefaehig sein, sonst "
        "wuerde dieser Test einen echten Verbindungsaufbau ausloesen."
    )
    _assert_no_live_channel(settings)
    return settings


def _settings_mail_sink() -> Settings:
    """Echte Settings fuer den Alarm-Pfad: sendefaehig konfiguriert, aber ohne
    erreichbaren Host — der Versand laeuft ueber `mail_sink`, nie ueber SMTP."""
    settings = Settings(**_DUMMY_EMAIL_FIELDS)
    assert settings.can_send_email() is True, (
        "Vorbedingung: der Alarm-Pfad steigt ohne sendefaehigen Kanal sofort "
        "aus und wuerde nichts pruefen."
    )
    _assert_no_live_channel(settings)
    return settings


def _assert_no_live_channel(settings: Settings) -> None:
    assert settings.can_send_telegram() is False, (
        "Sicherung (#1477): Telegram darf hier nicht sendefaehig sein — sonst "
        "ginge eine echte Nachricht an den Prod-Chat."
    )
    assert settings.can_send_sms() is False, (
        "Sicherung (#1477): SMS darf hier nicht sendefaehig sein."
    )


def _segment(segment_id: int | str = 1, *, day_offset: int = 0) -> TripSegment:
    """Etappe im aktiven Fenster (`day_offset=0`) bzw. abgelaufen (`-1`)."""
    now = datetime.now(timezone.utc) + timedelta(days=day_offset)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500,
                           distance_from_start_km=8.0),
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=3),
        duration_hours=4.0, distance_km=8.0, ascent_m=500, descent_m=0,
    )


def _data(segment_id: int | str = 1, *, segment: TripSegment | None = None,
          **summary_kwargs) -> SegmentWeatherData:
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


def _trip(trip_id: str, *, with_levels: bool = False,
          stage_offsets: tuple[int, ...] = (0,), send_email: bool = True,
          send_sms: bool = False, send_telegram: bool = False) -> Trip:
    """Tour mit einer Etappe HEUTE und scharfem E-Mail-Kanal.

    `stage_offsets` (#1662 AC-4): zusaetzliche Etappentage relativ zu heute —
    `(-1, 0)` ergibt eine Tour, die GESTERN schon lief. Nur damit laesst sich
    ein Vermerk mit gestrigem Zieltag pruefen, ohne dass er schon an der
    bestehenden "keine Segmente"-Regel (`:392-395`) verfaellt.
    """
    stages = [
        Stage(
            id=f"T{i + 1}", name=f"Tag {i + 1}", date=date.today() + timedelta(days=off),
            waypoints=[
                Waypoint(id=f"G{i}1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0),
                Waypoint(id=f"G{i}2", name="Ziel", lat=LAT + 0.1, lon=LON + 0.1,
                         elevation_m=1500.0),
            ],
        )
        for i, off in enumerate(stage_offsets)
    ]
    kwargs: dict = {"official_warnings": None}
    if with_levels:
        kwargs["display_config"] = UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            # Katalog-Kennung fuer Boeen ist "gust" (nicht "wind") — mit der
            # falschen Kennung gilt wind_gust als nicht aktiv und die Stufe
            # wird still verworfen.
            metrics=[MetricConfig(metric_id="gust", enabled=True)],
            metric_alert_levels={"wind_gust": "standard"},
        )
    trip = Trip(id=trip_id, name="Anker-Trip #1629", stages=stages, **kwargs)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=send_email, send_telegram=send_telegram,
        send_sms=send_sms, alert_on_changes=with_levels,
    )
    trip.alert_cooldown_minutes = 0
    trip.official_alerts_enabled = False
    trip.official_alert_triggers_enabled = False
    return trip


def _fixture_scheduler(gust: float):
    """Echte Unterklasse des Schedulers (kein Mock): liefert das Wetter aus der
    Fixture statt vom Provider und reicht die ECHTEN Segmente durch — sonst
    prueft der spaetere Alarm-Lauf ein anderes Zeitfenster (#1656)."""
    from services.trip_report_scheduler import TripReportSchedulerService

    class _FixtureScheduler(TripReportSchedulerService):
        def _fetch_weather(self, segments, provider=None):
            return [_data(s.segment_id, segment=s, gust_max_kmh=gust) for s in segments]

    return _FixtureScheduler


def _fresh_user(prefix: str) -> str:
    return f"tdd-1629-{prefix}-{uuid.uuid4().hex[:6]}"


def _snapshots(user_id: str):
    from services.weather_snapshot import WeatherSnapshotService

    return WeatherSnapshotService(user_id=user_id)


def _memory(user_id: str, entity_id: str) -> dict:
    from services.alert_state import AlertStateService

    return AlertStateService(user_id=user_id).load(entity_id)


def _run_failing_briefing(user_id: str, trip: Trip, *, gust: float = 25.0,
                          report_type: str = "morning", on_demand: bool = False):
    """Fuehrt das Briefing aus und gibt die durchgereichte Ausnahme zurueck.

    Faellt der Lauf NICHT mit einer Ausnahme aus dem Versand, ist die
    Vorbedingung des ganzen Issues nicht mehr gegeben — dann muss der Test
    laut scheitern statt still etwas anderes zu messen.
    """
    from output.channels.base import OutputConfigError

    scheduler = _fixture_scheduler(gust)(
        settings=_settings_email_broken(), user_id=user_id,
    )
    with pytest.raises(OutputConfigError) as excinfo:
        scheduler._send_trip_report_outcome(
            trip, report_type, on_demand=on_demand,
        )
    assert "Incomplete SMTP configuration" in str(excinfo.value), (
        "Vorbedingung: die durchgereichte Ausnahme muss die des ECHTEN "
        "E-Mail-Kanals sein (und nicht etwa ein Folgefehler aus dem neuen "
        f"except-Zweig), erhalten: {excinfo.value!r}"
    )
    return excinfo.value


# ═══════════════════════════════ AC-1 (RED) ══════════════════════════════════


def test_ac1_versandfehler_schreibt_datierten_und_undatierten_snapshot_trotzdem():
    """AC-1.

    GIVEN ein Trip-Briefing, dessen Versand mit einer Ausnahme scheitert
          (echter Resend-Allowlist-Fehler).
    WHEN  der Versandlauf abgeschlossen ist.
    THEN  liegt fuer diesen Trip trotzdem der Wetter-Snapshot des Tages vor —
          sowohl der datierte als auch der undatierte, beide mit dem
          Briefing-Stand.

    RED heute: `write_anchor_and_reset_memory()` wird von der Ausnahme
    uebersprungen, beide Snapshots fehlen.
    """
    uid = _fresh_user("ac1")
    trip = _trip(f"trip-1629-ac1-{uuid.uuid4().hex[:6]}")

    _run_failing_briefing(uid, trip, gust=25.0)

    svc = _snapshots(uid)
    dated = svc.load_dated(trip.id, date.today())
    undated = svc.load(trip.id)

    assert dated is not None, (
        "Nach einem gescheiterten Versand fehlt der DATIERTE Wetter-Snapshot "
        "des Tages — genau die Luecke, die am 08.08. den Abweichungs-Alarm "
        "einen ganzen Tag lahmgelegt hat (AC-1)"
    )
    assert undated is not None, (
        "Nach einem gescheiterten Versand fehlt der UNDATIERTE Wetter-Snapshot "
        "(AC-1)"
    )
    assert dated[0].aggregated.gust_max_kmh == pytest.approx(25.0), (
        f"Der datierte Snapshot traegt nicht den Briefing-Stand: "
        f"{dated[0].aggregated.gust_max_kmh!r}"
    )
    assert undated[0].aggregated.gust_max_kmh == pytest.approx(25.0), (
        f"Der undatierte Snapshot traegt nicht den Briefing-Stand: "
        f"{undated[0].aggregated.gust_max_kmh!r}"
    )


# ══════════════════════ AC-3 (Regressionsschutz, Bestand) ════════════════════


def test_ac3_versandfehler_zaehlt_weiterhin_als_fehlschlag_und_wird_protokolliert(caplog):
    """AC-3 (Regressionsschutz gegen den Bestand — heute bereits gruen).

    GIVEN derselbe Versandfehler wie in AC-1.
    WHEN  der Aufrufer `TripDispatchStrategy.dispatch_one()` den Lauf
          verarbeitet.
    THEN  zaehlt der Lauf weiterhin als fehlgeschlagen (0 gesendet, 1
          fehlgeschlagen) und die bisherige Fehlerzeile steht unveraendert im
          Protokoll — die Ausnahme wird also tatsaechlich weitergereicht und
          nicht vom neuen `except`-Zweig verschluckt.

    Kein Mock: die Strategie bekommt ihren eigenen, echten Scheduler
    (`_service` ist ihre Kompositionsnaht) in der Fixture-Variante.
    """
    from services.dispatch_orchestrator import TripDispatchStrategy

    uid = _fresh_user("ac3")
    trip = _trip(f"trip-1629-ac3-{uuid.uuid4().hex[:6]}")
    settings = _settings_email_broken()

    strategy = TripDispatchStrategy(settings=settings, user_id=uid)
    strategy._service = _fixture_scheduler(25.0)(settings=settings, user_id=uid)

    with caplog.at_level(logging.ERROR, logger="dispatch_orchestrator"):
        strategy.dispatch_one((trip, "morning"))

    assert strategy.result() == (0, 1), (
        "Ein Versandfehler muss weiterhin als fehlgeschlagener Lauf zaehlen "
        f"(0 gesendet / 1 fehlgeschlagen), erhalten: {strategy.result()!r} (AC-3)"
    )
    assert f"Failed morning report for {trip.id}" in caplog.text, (
        "Die bestehende Fehlerzeile des Orchestrators muss unveraendert "
        f"geschrieben werden, Protokoll: {caplog.text!r} (AC-3)"
    )


# ═══════════════════════════════ AC-4 (RED) ══════════════════════════════════


def test_ac4_versandfehler_setzt_melde_gedaechtnis_wie_ein_unerreichbarer_kanal_zurueck():
    """AC-4 (Vergleichsmessung).

    GIVEN zwei Nutzer mit identisch vorbelegtem Melde-Gedaechtnis (ein
          Aenderungs- UND ein amtlicher Eintrag).
    WHEN  bei Nutzer A der Versand mit einer Ausnahme scheitert und bei
          Nutzer B derselbe Lauf mit `result.sent == False` endet (Kanal
          konfiguriert, aber unerreichbar — heutiges Bestandsverhalten).
    THEN  steht danach in BEIDEN Faellen exakt derselbe Zustand: der
          Aenderungs-Eintrag ist weg, der amtliche Eintrag ueberlebt. Kein
          Sonderweg fuer den Ausnahmefall.

    RED heute: bei A bleibt der Aenderungs-Eintrag stehen (der Reset wird von
    der Ausnahme uebersprungen), bei B ist er weg — die beiden Zustaende sind
    verschieden.
    """
    from services.alert_state import AlertStateService
    from tests.helpers.alert_log_fixtures import settings_email_and_failing_telegram

    official_key = "official_alert:region:Gailtal:thunderstorm:none:none"
    vorher = {
        "gust_max_kmh:1": {"last_reported_value": 42.0, "reported_at": "x"},
        official_key: {"last_reported_value": 3.0, "reported_at": "x"},
    }

    # Nutzer A — Versand wirft eine Ausnahme.
    uid_a = _fresh_user("ac4-ausnahme")
    trip_a = _trip(f"trip-1629-ac4a-{uuid.uuid4().hex[:6]}")
    AlertStateService(user_id=uid_a).save(trip_a.id, dict(vorher))
    _run_failing_briefing(uid_a, trip_a, gust=25.0)

    # Nutzer B — Kanal konfiguriert, aber unerreichbar (result.sent == False).
    # `settings_email_and_failing_telegram()` laesst den echten
    # `TelegramOutput`-Guard (#1363) VOR jedem Netzaufruf scheitern.
    uid_b = _fresh_user("ac4-unerreichbar")
    trip_b = _trip(f"trip-1629-ac4b-{uuid.uuid4().hex[:6]}")
    trip_b.report_config = TripReportConfig(
        trip_id=trip_b.id, send_email=False, send_telegram=True, send_sms=False,
    )
    AlertStateService(user_id=uid_b).save(trip_b.id, dict(vorher))
    outcome_b = _fixture_scheduler(25.0)(
        settings=settings_email_and_failing_telegram(), user_id=uid_b,
    )._send_trip_report_outcome(trip_b, "morning", on_demand=False)
    assert outcome_b == "channels_unreachable", (
        "Vorbedingung: der Vergleichslauf muss ehrlich als nicht zugestellt "
        f"gelten, erhalten: {outcome_b!r}"
    )

    nach_b = _memory(uid_b, trip_b.id)
    assert nach_b == {official_key: vorher[official_key]}, (
        "Vorbedingung: der heutige 'Kanal unerreichbar'-Pfad muss den "
        f"Aenderungs-Eintrag leeren und den amtlichen schonen: {nach_b!r}"
    )

    nach_a = _memory(uid_a, trip_a.id)
    assert nach_a == nach_b, (
        "Ein Versandfehler mit Ausnahme muss das Melde-Gedaechtnis GENAUSO "
        "behandeln wie ein konfigurierter, aber unerreichbarer Kanal — kein "
        f"Sonderweg.\nAusnahme-Fall:   {nach_a!r}\n"
        f"Unerreichbar-Fall: {nach_b!r} (AC-4)"
    )


# ══════════════════ AC-5 (Grenz-Wache, heute bereits gruen) ══════════════════


def test_ac5_ad_hoc_versandfehler_laesst_anker_und_gedaechtnis_unberuehrt():
    """AC-5 (Grenz-Wache).

    GIVEN ein Ad-hoc-Abruf (`on_demand=True`) mit bestehendem Δ-Anker (20 km/h)
          und vorbelegtem Melde-Gedaechtnis.
    WHEN  der Versand dieses Ad-hoc-Abrufs mit einer Ausnahme scheitert.
    THEN  bleiben Anker UND Melde-Gedaechtnis unveraendert — ein Ad-hoc-Abruf
          ist auch im Fehlerfall gegenueber beiden Zustaenden read-only
          (#1007).

    Diese Zusicherung faellt, sobald der neue `except`-Zweig den Anker
    schreibt, ohne `on_demand` zu beachten.
    """
    from services.alert_state import AlertStateService

    uid = _fresh_user("ac5")
    trip = _trip(f"trip-1629-ac5-{uuid.uuid4().hex[:6]}")

    _snapshots(uid).save_dated(trip.id, date.today(), [_data(1, gust_max_kmh=20.0)])
    vorher = {
        "gust_max_kmh:1": {"last_reported_value": 42.0, "reported_at": "x"},
        "official_alert:region:Gailtal:thunderstorm:none:none": {
            "last_reported_value": 3.0, "reported_at": "x",
        },
    }
    AlertStateService(user_id=uid).save(trip.id, dict(vorher))

    _run_failing_briefing(uid, trip, gust=48.0, on_demand=True)

    dated = _snapshots(uid).load_dated(trip.id, date.today())
    assert dated is not None and dated[0].aggregated.gust_max_kmh == pytest.approx(20.0), (
        "Der Ad-hoc-Abruf darf den Δ-Anker auch im Fehlerfall nicht "
        f"ueberschreiben, gefunden: {dated and dated[0].aggregated.gust_max_kmh!r} "
        "km/h statt 20.0 km/h (AC-5)"
    )
    assert _snapshots(uid).load(trip.id) is None, (
        "Der Ad-hoc-Abruf darf im Fehlerfall keinen undatierten Anker anlegen "
        "(AC-5)"
    )
    assert _memory(uid, trip.id) == vorher, (
        f"Das Melde-Gedaechtnis muss unveraendert bleiben: "
        f"{_memory(uid, trip.id)!r} (AC-5)"
    )


# ══════════════════ AC-6 (Grenz-Wache, zweites Gedaechtnis) ══════════════════


class _FixedOfficialAlertSource:
    """Echte Quelle (kein Mock): zustaendig fuer einen Punkt (0.05-Toleranz),
    liefert stets dieselbe, unveraenderte Warnung."""

    def __init__(self, lat: float, lon: float, alert) -> None:
        self._lat, self._lon, self._alert = lat, lon, alert
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "tdd-1629-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        self.fetch_calls += 1
        return [self._alert]


def _official_alert_today():
    from services.official_alerts import OfficialAlert

    day = date.today()
    valid_from = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return OfficialAlert(
        source="tdd-1629", hazard="thunderstorm", level=2,
        label="Gewitterwarnung (#1629)", region_label="Gailtal",
        valid_from=valid_from, valid_to=valid_from + timedelta(days=1),
    )


def test_ac6_versandfehler_vermerkt_amtliche_warnung_nicht_als_gemeldet(monkeypatch):
    """AC-6 (Grenz-Wache — ZWEITES Gedaechtnis, nicht mit AC-4 verwechseln).

    GIVEN ein Trip-Briefing mit amtlicher Warnung, dessen Versand mit einer
          Ausnahme scheitert.
    WHEN  der Lauf abgeschlossen ist.
    THEN  wurde die Warnung NICHT als "im Briefing bereits gemeldet" vermerkt
          (`record_official_alerts_reported` bleibt ungerufen) — der Vermerk
          haengt weiterhin an der tatsaechlichen Zustellung, damit eine nie
          zugestellte Warnung den unabhaengigen Alarm-Checker nicht
          stummschaltet.

    Die positive Gegenprobe (gelingender Versand vermerkt sehr wohl) steht
    VOR der eigentlichen Pruefung — ohne sie waere die leere Erwartung auch
    dann erfuellt, wenn die Warnung gar nicht erst im Briefing gelandet waere.
    """
    import services.alert_briefing_anchor as anchor_mod
    import services.official_alerts.base as official_mod
    from output.channels.email import EmailOutput
    from services.official_alerts import register_official_alert_source

    backup = list(official_mod._REGISTERED_SOURCES)
    official_mod._REGISTERED_SOURCES.clear()
    try:
        register_official_alert_source(
            _FixedOfficialAlertSource(LAT, LON, _official_alert_today())
        )

        calls: list = []

        def _recording_record(*, user_id, entity_id, alerts):
            calls.append((user_id, entity_id, list(alerts)))

        monkeypatch.setattr(
            anchor_mod, "record_official_alerts_reported", _recording_record,
        )

        # Gegenprobe: derselbe Aufbau, aber der Versand GELINGT (Transportrand
        # durch eine echte, aufzeichnende Funktion ersetzt — kein Netz).
        gesendet: list = []

        def _fake_send(self, *, subject, body, **kwargs):
            gesendet.append(subject)

        monkeypatch.setattr(EmailOutput, "send", _fake_send)
        uid_ok = _fresh_user("ac6-kontrolle")
        trip_ok = _trip(f"trip-1629-ac6ok-{uuid.uuid4().hex[:6]}")
        trip_ok.official_alerts_enabled = True
        outcome_ok = _fixture_scheduler(25.0)(
            settings=Settings(
                smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
                mail_to="dummy@example.com",
                telegram_bot_token="", telegram_chat_id="",
                telegram_test_bot_token="", telegram_test_chat_id="",
                sms_gateway_url="", seven_api_key="", sms_to="",
            ),
            user_id=uid_ok,
        )._send_trip_report_outcome(trip_ok, "morning", on_demand=False)
        assert outcome_ok == "sent", (
            f"Gegenprobe: der gelingende Versand muss 'sent' liefern ({outcome_ok!r})"
        )
        assert len(calls) == 1, (
            "Gegenprobe: ein GELUNGENER Versand muss die amtliche Warnung genau "
            f"einmal vermerken, sonst prueft der Fall unten nichts: {calls!r}"
        )
        calls.clear()
        monkeypatch.undo()

        # Erneut registrieren + beobachten (monkeypatch.undo hat beides geloest).
        official_mod._REGISTERED_SOURCES.clear()
        register_official_alert_source(
            _FixedOfficialAlertSource(LAT, LON, _official_alert_today())
        )
        monkeypatch.setattr(
            anchor_mod, "record_official_alerts_reported", _recording_record,
        )

        uid = _fresh_user("ac6")
        trip = _trip(f"trip-1629-ac6-{uuid.uuid4().hex[:6]}")
        trip.official_alerts_enabled = True
        _run_failing_briefing(uid, trip, gust=25.0)

        assert calls == [], (
            "Ein mit einer Ausnahme gescheiterter Versand darf die amtliche "
            "Warnung NICHT als 'im Briefing gemeldet' vermerken — sonst "
            "schweigt der unabhaengige Alarm-Checker zu einer nie zugestellten "
            f"Warnung: {calls!r} (AC-6)"
        )
    finally:
        official_mod._REGISTERED_SOURCES.clear()
        official_mod._REGISTERED_SOURCES.extend(backup)


# ═══════════════════════════ AC-7 / AC-8-Naht (RED) ══════════════════════════


def _dispatch_failure_journal(user_id: str) -> Path:
    """Die Ablage, die der Go-Leser aus AC-8 per Glob erwartet
    (`.../diagnostics/briefing_dispatch_failures.jsonl`, Spec-Abschnitt
    "Diagnose-Schreiber" + "Sichtbarkeit")."""
    from app.loader import get_data_dir

    return get_data_dir(user_id) / "diagnostics" / "briefing_dispatch_failures.jsonl"


def test_versandfehler_hinterlaesst_diagnose_spur_an_der_vereinbarten_stelle():
    """AC-7/AC-8-Naht (RED).

    GIVEN ein Trip-Briefing, dessen Versand mit einer Ausnahme scheitert.
    WHEN  der Lauf abgeschlossen ist.
    THEN  liegt unter `users/<uid>/diagnostics/briefing_dispatch_failures.jsonl`
          mindestens eine Zeile — genau die Datei, die
          `analyzeBriefingDispatchErrors()` (AC-8) spaeter per Glob einliest.
          Ohne diese Spur haette das Ausfall-Signal am Status-Endpunkt keine
          Quelle.

    RED heute: die Datei existiert nicht — es gibt keinen Diagnose-Schreiber.
    """
    import json

    uid = _fresh_user("diag")
    trip = _trip(f"trip-1629-diag-{uuid.uuid4().hex[:6]}")

    _run_failing_briefing(uid, trip, gust=25.0)

    journal = _dispatch_failure_journal(uid)
    assert journal.exists(), (
        f"Ein Versandfehler muss eine Diagnose-Spur unter {journal.name!r} "
        "hinterlassen — sonst kann der Status-Endpunkt keinen mit der "
        "Ausfalldauer wachsenden Alarm bilden (ADR-0018, AC-7/AC-8)"
    )
    zeilen = [z for z in journal.read_text(encoding="utf-8").splitlines() if z.strip()]
    assert len(zeilen) >= 1, f"Die Diagnose-Datei ist leer: {journal}"
    eintrag = json.loads(zeilen[-1])
    assert eintrag.get("entity_id") == trip.id, (
        f"Der Diagnose-Eintrag muss die betroffene Kennung tragen: {eintrag!r}"
    )


def test_ac7_defekter_diagnose_schreiber_verdeckt_die_versandausnahme_nicht():
    """AC-7.

    GIVEN das Zielverzeichnis des Diagnose-Schreibers ist nicht beschreibbar
          (`diagnostics` existiert als DATEI statt als Verzeichnis — jeder
          Schreibversuch darunter wirft `NotADirectoryError`).
    WHEN  gleichzeitig ein Versandfehler auftritt.
    THEN  kommt beim Aufrufer weiterhin GENAU die urspruengliche
          Versand-Ausnahme an (nicht der Datei-Fehler), und der Anker wird
          trotzdem geschrieben — ein defekter Diagnose-Schreiber darf den
          Briefing-Lauf nicht zusaetzlich brechen.

    RED heute: der Anker fehlt (kein `except`-Zweig). Nach der Umsetzung
    faellt dieser Test, sobald der Diagnose-Schreiber nicht fail-soft ist.
    """
    from app.loader import get_data_dir

    uid = _fresh_user("ac7")
    trip = _trip(f"trip-1629-ac7-{uuid.uuid4().hex[:6]}")

    user_dir = get_data_dir(uid)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "diagnostics").write_text("kein Verzeichnis (AC-7)", encoding="utf-8")

    # `_run_failing_briefing` prueft bereits, dass die durchgereichte Ausnahme
    # der ECHTE Allowlist-Fehler ist — ein NotADirectoryError wuerde hier
    # sofort auffallen.
    _run_failing_briefing(uid, trip, gust=25.0)

    assert _snapshots(uid).load_dated(trip.id, date.today()) is not None, (
        "Auch bei defektem Diagnose-Schreiber muss der Wetter-Snapshot des "
        "Tages entstehen — der Diagnose-Eintrag ist fail-soft, der Anker nicht "
        "(AC-7)"
    )


# ═════════════════════════ AC-9 (Wirkungs-AC, RED) ═══════════════════════════


class _FixedSegmentWeatherService:
    """Echte, netzfreie Implementierung der Abruf-Naht, die
    `TripAlertService._fetch_fresh_weather()` benutzt.

    Ersetzt wird NUR der Provider-Abruf. Der eigentliche Pruefgegenstand von
    AC-9 — der Zeitfilter in `_fetch_fresh_weather()` (`end_time < now`,
    `start_time.date() > heute`), der am 08.08. alles wegfilterte — laeuft
    unveraendert echt weiter.
    """

    def __init__(self, provider=None) -> None:
        self._provider = provider

    def fetch_segment_weather(self, segment, **kwargs):
        return _data(segment.segment_id, segment=segment, gust_max_kmh=80.0)


def test_ac9_alarm_lauf_desselben_tages_prueft_nach_gescheitertem_briefing_regulaer(
    monkeypatch, caplog,
):
    """AC-9 (Wirkungs-AC, zwingend).

    GIVEN ein Morgen-Briefing, dessen Versand mit einer Ausnahme scheitert,
          und — wie in Prod am 08.08. — ein undatierter Alt-Anker vom VORTAG,
          dessen Etappenzeiten bereits abgelaufen sind.
    WHEN  am selben Tag der regulaere Abweichungs-Alarm-Lauf
          (`check_all_trips()`) fuer denselben Trip laeuft.
    THEN  findet er einen gueltigen, heute datierten Wetter-Snapshot, fuehrt
          die normale Abweichungspruefung durch und stellt die Meldung zu —
          er endet NICHT in der Warnung "No fresh weather data".

    RED heute (exakte Prod-Kette): kein datierter Snapshot → Rueckfall auf den
    undatierten Alt-Anker vom Vortag → dessen Segmente fallen im Zeitfilter
    von `_fetch_fresh_weather()` komplett weg → `[]` →
    `logger.warning("No fresh weather data for trip …")` → kein Alarm.

    Dieser Test misst die WIRKUNG am Alarm-Pfad, nicht die Existenz einer
    Datei.
    """
    import services.segment_weather as sw_mod
    from app.loader import save_trip
    from services.trip_alert import TripAlertService

    uid = _fresh_user("ac9")
    trip = _trip(f"trip-1629-ac9-{uuid.uuid4().hex[:6]}", with_levels=True)
    save_trip(trip, user_id=uid)

    # Alt-Anker vom Vortag (undatiert) — dieselbe Ausgangslage wie in Prod:
    # die Datei existiert, ihre Etappenzeiten sind aber abgelaufen.
    _snapshots(uid).save(
        trip.id,
        [_data(1, segment=_segment(1, day_offset=-1), gust_max_kmh=25.0)],
        date.today() - timedelta(days=1),
    )

    _run_failing_briefing(uid, trip, gust=25.0)

    monkeypatch.setattr(sw_mod, "SegmentWeatherService", _FixedSegmentWeatherService)
    meldungen: list = []
    alert_svc = TripAlertService(
        settings=_settings_mail_sink(), user_id=uid,
        mail_sink=lambda subject, body: meldungen.append(subject),
    )

    with caplog.at_level(logging.WARNING, logger="trip_alert"):
        result = alert_svc.check_all_trips()

    assert "No fresh weather data" not in caplog.text, (
        "Der Alarm-Lauf desselben Tages ist in der Warnung 'No fresh weather "
        "data' geendet — genau der ganztaegige Alarm-Ausfall vom 08.08.: das "
        "gescheiterte Briefing hat keinen heute datierten Anker hinterlassen "
        f"(AC-9).\nProtokoll: {caplog.text!r}"
    )
    assert result.alerts_sent == 1, (
        "Der Alarm-Lauf muss die regulaere Abweichungspruefung durchfuehren "
        "und die Boeen-Aenderung 25 → 80 km/h melden, erhalten: "
        f"alerts_sent={result.alerts_sent} (AC-9)"
    )
    assert meldungen, (
        "Es muss tatsaechlich eine Meldung rausgehen — sonst ist die "
        "Abweichungspruefung nur formal gelaufen (AC-9)"
    )


# ══════════════════ AC-10 (Grenz-Wache gegen zu weite Absicherung) ═══════════


def test_ac10_fehler_vor_dem_versand_schreibt_keinen_anker():
    """AC-10 (Grenz-Wache, Mutations-Gegenprobe der Spec).

    GIVEN der Fehler entsteht VOR dem Versand — der Wetterabruf scheitert, es
          liegen gar keine vollstaendigen Segmentdaten vor.
    WHEN  der Lauf mit einer Ausnahme endet.
    THEN  entsteht WEDER ein datierter NOCH ein undatierter Wetter-Snapshot,
          und das Melde-Gedaechtnis bleibt unangetastet.

    Der Absicherungs-Block darf ausschliesslich den Versandaufruf umschliessen.
    Zieht ihn jemand ueber die gesamte Methode, entstuende ein Anker aus
    unvollstaendigen Daten — der Alarm vergliche dann gegen eine Referenz, die
    nie ein Briefing war. Dieser Test MUSS bei einer solchen Mutation rot
    werden.
    """
    from services.alert_state import AlertStateService
    from services.trip_report_scheduler import TripReportSchedulerService

    uid = _fresh_user("ac10")
    trip = _trip(f"trip-1629-ac10-{uuid.uuid4().hex[:6]}")
    vorher = {"gust_max_kmh:1": {"last_reported_value": 42.0, "reported_at": "x"}}
    AlertStateService(user_id=uid).save(trip.id, dict(vorher))

    class _BrokenWeatherScheduler(TripReportSchedulerService):
        """Echte Unterklasse: der Wetterabruf scheitert, bevor der Versand
        ueberhaupt erreicht wird (Provider-Totalausfall mit Ausnahme)."""

        def _fetch_weather(self, segments, provider=None):
            raise RuntimeError("Wetterabruf gescheitert (#1629 AC-10)")

    scheduler = _BrokenWeatherScheduler(
        settings=_settings_email_broken(), user_id=uid,
    )
    with pytest.raises(RuntimeError):
        scheduler._send_trip_report_outcome(trip, "morning", on_demand=False)

    assert _snapshots(uid).load_dated(trip.id, date.today()) is None, (
        "Ein Fehler VOR dem Versand darf keinen datierten Anker erzeugen — "
        "sonst vergleicht der Alarm gegen eine Referenz, die nie ein Briefing "
        "war (AC-10)"
    )
    assert _snapshots(uid).load(trip.id) is None, (
        "Ein Fehler VOR dem Versand darf keinen undatierten Anker erzeugen "
        "(AC-10)"
    )
    assert _memory(uid, trip.id) == vorher, (
        "Ein Fehler VOR dem Versand darf das Melde-Gedaechtnis nicht "
        f"zuruecksetzen: {_memory(uid, trip.id)!r} (AC-10)"
    )


# ═════════════════════════════════════════════════════════════════════════════
# Issue #1662 — ein Versandfehler wird NACHGELIEFERT
#
# SPEC: docs/specs/modules/fix_1662_versandfehler_nachliefern.md (AC-1..AC-13).
# Fortsetzung von #1629: der Anker ueberlebt seither einen Versandfehler, das
# Briefing selbst aber nicht — es wird nirgends vorgemerkt und nie nachgeholt
# (07./08.08.2026: zwei verlorene Briefings derselben Tour).
#
# Test-Politik wie oben: kein Mock-Theater. Der Fehlschlag entsteht am ECHTEN
# Konfigurations-Guard des echten E-Mail-Kanals (`_settings_email_broken`),
# gelingende Zustellungen laufen ueber den Transportrand — eine aufzeichnende
# Funktion bzw. eine ECHTE Unterklasse des jeweiligen Kanals. Geprueft wird die
# WIRKUNG (existiert der Vermerk? kam eine Zustellung an? welchen Text traegt
# sie?), nie ein Dateiinhalt-String eines Prueflings.
# ═════════════════════════════════════════════════════════════════════════════

# Vollstaendig konfiguriert, damit `can_send_sms()`/`can_send_telegram()` den
# Kanal ueberhaupt betreten — der Transport selbst wird an der Modul-Naht durch
# eine echte Unterklasse ersetzt, es entsteht KEIN Netz.
_TELEGRAM_FIELDS: dict = {
    "telegram_bot_token": "tdd-1662-kein-echter-token",
    "telegram_chat_id": "4711",
    "telegram_test_bot_token": "tdd-1662-kein-echter-token",
    "telegram_test_chat_id": "4711",
}
# Der Gateway zeigt auf den Discard-Port des eigenen Rechners: der Kanal wird
# ECHT betreten und scheitert ECHT (Verbindung abgelehnt) — ohne Netz und ohne
# je einen fremden Dienst zu erreichen. Wo eine gelingende SMS gebraucht wird,
# ersetzt `_recording_sms_and_telegram()` den Transportrand.
_SMS_FIELDS: dict = {
    "sms_gateway_url": "http://127.0.0.1:9/tdd-1662",
    "seven_api_key": "tdd-1662-kein-echter-key",
    "sms_to": "+490000000000",
}
_SMS_TELEGRAM_FIELDS: dict = {**_TELEGRAM_FIELDS, **_SMS_FIELDS}


def _fresh_user_1662(prefix: str) -> str:
    return f"tdd-1662-{prefix}-{uuid.uuid4().hex[:6]}"


def _pending_markers(user_id: str) -> list:
    """Die Nachliefer-Vermerke dieses Nutzers.

    Testkontrakt der Ablage (`test_issue_1012_no_data_guard.py:23-26`):
    `data/users/<uid>/pending_briefings.json` == `{"entries": [...]}`.
    """
    import json

    from app.loader import get_data_dir

    path = get_data_dir(user_id) / "pending_briefings.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("entries", []) if isinstance(data, dict) else data


def _seed_marker(user_id: str, trip: Trip, *, reason: str | None,
                 target_date: date | None = None, report_type: str = "morning",
                 failed_segment_ids: list | None = None, slot_hour: int = 7) -> None:
    """Legt einen Vermerk als AUSGANGSLAGE an (Setup, keine Zusicherung).

    Geprueft wird jeweils, was der stuendliche Vorlauf mit ihm TUT — nicht,
    dass die Datei diesen Inhalt hat.
    """
    import json

    from app.loader import get_data_dir

    entry: dict = {
        "trip_id": trip.id,
        "report_type": report_type,
        "date": (target_date or date.today()).isoformat(),
        "slot_hour": slot_hour,
        "failed_segment_ids": list(failed_segment_ids or []),
        "attempts": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if reason is not None:
        entry["reason"] = reason
    user_dir = get_data_dir(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "pending_briefings.json").write_text(
        json.dumps({"entries": [entry]}, indent=2), encoding="utf-8",
    )


def _briefing_log_channels(user_id: str) -> list:
    """Die Zustellbilanz, wie sie das Cockpit sieht (`briefing_log.json`,
    #393) — je Eintrag die Liste der tatsaechlich bedienten Kanaele."""
    import json

    from app.loader import get_data_dir

    path = get_data_dir(user_id) / "briefing_log.json"
    if not path.exists():
        return []
    return [e.get("channels") for e in json.loads(path.read_text()).get("entries", [])]


def _settings_email_ok() -> Settings:
    """E-Mail vollstaendig konfiguriert (Host unerreichbar), Telegram/SMS aus.
    Der Transport wird ueber `_recording_email()` ersetzt — kein Netz."""
    settings = Settings(**_DUMMY_EMAIL_FIELDS)
    assert settings.can_send_email() is True
    _assert_no_live_channel(settings)
    return settings


def _recording_email(monkeypatch) -> list:
    """Ersetzt den Transportrand `EmailOutput.send` durch eine echte,
    aufzeichnende Funktion (Haus-Muster, s. AC-6 oben) — kein Netz, kein
    Mock-Objekt. Liefert die Liste der zugestellten Nachrichten."""
    from output.channels.email import EmailOutput

    zugestellt: list = []

    def _record(self, *, subject, body, **kwargs):
        zugestellt.append({"subject": subject, "body": body, **kwargs})

    monkeypatch.setattr(EmailOutput, "send", _record)
    return zugestellt


def _recording_sms_and_telegram(monkeypatch, *, telegram_error=None):
    """Ersetzt SMS- und Telegram-Transportrand durch ECHTE Unterklassen des
    jeweiligen Kanals (Haus-Muster `_FixtureScheduler`).

    Kein Mock: ueberschrieben wird ausschliesslich die Transport-Methode; die
    Klassen bleiben die echten, inklusive Konstruktor-Guards. `telegram_error`
    laesst Telegram mit einer Stoerung scheitern, mit der der Versandpfad
    heute nicht rechnet (AC-9).
    """
    import services.notification_service as ns

    sms_out: list = []
    telegram_out: list = []

    class _RecordingSMS(ns.SMSOutput):
        def send(self, subject: str, body: str) -> None:
            sms_out.append(body)

    class _RecordingTelegram(ns.TelegramOutput):
        def send(self, subject, body, reply_markup=None, *, parse_mode=None,
                 suppress_subject_line=False):
            if telegram_error is not None:
                raise telegram_error
            telegram_out.append(body)
            return 4711

    monkeypatch.setattr(ns, "SMSOutput", _RecordingSMS)
    monkeypatch.setattr(ns, "TelegramOutput", _RecordingTelegram)
    return sms_out, telegram_out


def _settings_email_broken_sms_telegram_scharf() -> Settings:
    """E-Mail scheitert am echten Guard, SMS und Telegram sind scharf.

    Sicherung (#1477): scharf heisst hier NUR, dass der Kanal betreten wird —
    der Transport MUSS vorher ueber `_recording_sms_and_telegram()` ersetzt
    sein, sonst ginge ein echter Aufruf hinaus.
    """
    settings = Settings(**{**_BROKEN_EMAIL_FIELDS, **_SMS_TELEGRAM_FIELDS})
    assert settings.can_send_email() is False
    assert settings.can_send_sms() is True
    assert settings.can_send_telegram() is True
    return settings


def _allow_sms_tier(user_id: str) -> None:
    """SMS haengt am Nutzerlevel (`services/user_tier.py:6`) — ohne
    `tier` >= standard bleibt der Kanal aus, und AC-8/AC-13 pruefen nichts."""
    import json

    from app.loader import get_data_dir

    user_dir = get_data_dir(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "user.json").write_text(
        json.dumps({"id": user_id, "tier": "premium"}), encoding="utf-8",
    )


def _strategy(user_id: str, settings: Settings, *, gust: float = 25.0):
    """Der ECHTE stuendliche Trip-Pfad (`TripDispatchStrategy`) mit dem
    Fixture-Scheduler als Wetterquelle — `_service` ist seine
    Kompositionsnaht (Haus-Muster, s. AC-3 oben)."""
    from services.dispatch_orchestrator import TripDispatchStrategy

    strategy = TripDispatchStrategy(settings=settings, user_id=user_id)
    strategy._service = _fixture_scheduler(gust)(settings=settings, user_id=user_id)
    return strategy


def _dispatch_marker(user_id: str):
    """Der eine Versandfehler-Vermerk dieses Nutzers, sonst None."""
    for entry in _pending_markers(user_id):
        if entry.get("reason") == "dispatch_error":
            return entry
    return None


# ═══════════════════════════════ #1662 AC-1 ══════════════════════════════════


def test_versandfehler_ohne_zweitkanal_wird_zur_nachlieferung_vorgemerkt():
    """#1662 AC-1.

    GIVEN der Versand eines Trip-Briefings scheitert vollstaendig — kein
          einziger konfigurierter Kanal hat zugestellt (E-Mail-Fehler, kein
          weiterer aktiver Kanal).
    WHEN  der Versandlauf beendet ist.
    THEN  liegt fuer diesen Trip unter der ECHTEN Nutzerkennung ein Vermerk mit
          dem Grund "Versandfehler" und ohne betroffene Wetterabschnitte vor.

    RED heute: der `except`-Zweig (`trip_report_scheduler.py:1035-1042`)
    schreibt Diagnose und Anker, aber keinen Vermerk — das Briefing ist
    verloren, genau wie am 07./08.08. in Prod.
    """
    uid = _fresh_user_1662("ac1")
    trip = _trip(f"trip-1662-ac1-{uuid.uuid4().hex[:6]}")

    _run_failing_briefing(uid, trip, gust=25.0)

    marker = _dispatch_marker(uid)
    assert marker is not None, (
        "Nach einem vollstaendig gescheiterten Versand fehlt der "
        "Nachliefer-Vermerk — das Briefing ist ersatzlos verloren "
        f"(#1662 AC-1). Vorhanden: {_pending_markers(uid)!r}"
    )
    assert marker.get("trip_id") == trip.id, f"Falsche Tour im Vermerk: {marker!r}"
    assert marker.get("failed_segment_ids") == [], (
        "Ein Versandfehler betrifft keinen Wetterabschnitt — die Liste muss "
        f"leer sein, sonst zieht der Vorlauf die Wetterdaten-Logik: {marker!r}"
    )


# ═══════════════════════════════ #1662 AC-2 ══════════════════════════════════


def test_vorgemerkter_versandfehler_wird_im_naechsten_vorlauf_zugestellt(monkeypatch):
    """#1662 AC-2.

    GIVEN ein Versandfehler-Vermerk aus einem echten, gescheiterten Lauf.
    WHEN  der stuendliche Vorlauf des Schedulers das naechste Mal laeuft und
          der Kanal wieder funktioniert.
    THEN  wird das Briefing an den Nutzer zugestellt.

    Bewusst als Kette ab dem echten Fehlschlag (nicht ab einem gesetzten
    Vermerk): geprueft wird der ganze Weg vom Ausfall bis zur Zustellung.
    RED heute: es entsteht kein Vermerk, also holt der Vorlauf nichts nach.
    """
    from app.loader import save_trip

    uid = _fresh_user_1662("ac2")
    trip = _trip(f"trip-1662-ac2-{uuid.uuid4().hex[:6]}")
    save_trip(trip, user_id=uid)

    _run_failing_briefing(uid, trip, gust=25.0)

    zugestellt = _recording_email(monkeypatch)
    _strategy(uid, _settings_email_ok()).pre_pass(hour=9, due=[])

    assert len(zugestellt) == 1, (
        "Der stuendliche Vorlauf muss das nach einem Versandfehler "
        "ausgefallene Briefing nachliefern — zugestellt wurde: "
        f"{[m['subject'] for m in zugestellt]!r} (#1662 AC-2)"
    )


# ═══════════════════════════════ #1662 AC-3 ══════════════════════════════════


def test_nachgeliefertes_briefing_nennt_den_gescheiterten_versand_als_grund(monkeypatch):
    """#1662 AC-3.

    GIVEN ein nach Versandfehler nachgeliefertes Briefing.
    WHEN  der Nutzer es liest.
    THEN  nennt der Text einen fehlgeschlagenen Zustellversuch als Grund —
          ausdruecklich NICHT den Bestandstext "jetzt mit vollstaendigen
          Daten" und ohne Technikjargon.

    RED heute doppelt: es wird gar nichts nachgeliefert; und selbst wenn (leere
    `failed_segment_ids` -> leere Schnittmenge, `:422`), traege der Text die
    sachlich falsche Wetterdaten-Begruendung.
    """
    from app.loader import save_trip

    uid = _fresh_user_1662("ac3")
    trip = _trip(f"trip-1662-ac3-{uuid.uuid4().hex[:6]}")
    save_trip(trip, user_id=uid)

    _run_failing_briefing(uid, trip, gust=25.0)

    zugestellt = _recording_email(monkeypatch)
    _strategy(uid, _settings_email_ok()).pre_pass(hour=9, due=[])

    assert zugestellt, (
        "Ohne Nachlieferung gibt es keinen Text zu pruefen (#1662 AC-3)"
    )
    text = " ".join(str(v) for m in zugestellt for v in m.values())
    assert "jetzt mit vollständigen Daten" not in text, (
        "Der Nachliefer-Text behauptet 'jetzt mit vollstaendigen Daten' — bei "
        "einem Versandfehler waren die Daten nie das Problem, und der Nutzer "
        "hat kein 'Vorher', das aktualisiert wuerde (#1662 AC-3)"
    )
    lower = text.lower()
    assert "nachgeliefert" in lower, (
        "Der Text weist den Nutzer nicht auf eine Nachlieferung hin (#1662 AC-3)"
    )
    assert any(w in lower for w in ("zustellung", "zugestellt", "versand", "versendet")), (
        "Der Text nennt den gescheiterten Zustellversuch nicht als Grund "
        "(#1662 AC-3)"
    )
    assert any(w in lower for w in ("fehlgeschlagen", "gescheitert", "nicht möglich")), (
        "Der Text sagt nicht, dass der Zustellversuch gescheitert ist "
        "(#1662 AC-3)"
    )
    assert "OutputConfigError" not in text and "SMTP" not in text, (
        "Kein Technikjargon im Nutzertext (Spec, Implementation Details 5) — "
        "der Text steht direkt im Briefing (#1662 AC-3)"
    )


# ═══════════════════════════════ #1662 AC-4 ══════════════════════════════════


def test_vermerk_mit_vergangenem_zieltag_verfaellt_ohne_zustellversuch(monkeypatch):
    """#1662 AC-4.

    GIVEN ein Versandfehler-Vermerk, dessen Zieltag GESTERN liegt (die Tour
          lief gestern schon, es gaebe also sehr wohl Etappen-Daten).
    WHEN  der stuendliche Vorlauf laeuft.
    THEN  verfaellt der Vermerk ohne weiteren Zustellversuch — ein
          Morgen-Briefing von gestern ist heute wertlos.

    RED heute: die Bestandslogik kennt keinen Verfall ueber den Zieltag; sie
    holt Wetterdaten, findet eine leere Schnittmenge und liefert das
    Briefing verspaetet aus.
    """
    from app.loader import save_trip

    uid = _fresh_user_1662("ac4")
    trip = _trip(f"trip-1662-ac4-{uuid.uuid4().hex[:6]}", stage_offsets=(-1, 0))
    save_trip(trip, user_id=uid)
    _seed_marker(uid, trip, reason="dispatch_error",
                 target_date=date.today() - timedelta(days=1))

    zugestellt = _recording_email(monkeypatch)
    _strategy(uid, _settings_email_ok()).pre_pass(hour=9, due=[])

    assert zugestellt == [], (
        "Ein Vermerk mit gestrigem Zieltag darf keinen Zustellversuch mehr "
        f"ausloesen, zugestellt wurde: {zugestellt!r} (#1662 AC-4)"
    )
    assert _pending_markers(uid) == [], (
        "Der abgelaufene Vermerk muss verfallen, sonst wird er stuendlich "
        f"weitergeschleppt: {_pending_markers(uid)!r} (#1662 AC-4)"
    )


# ═══════════════════════════════ #1662 AC-5 ══════════════════════════════════


def test_gelingender_regulaerer_versand_macht_den_vermerk_gegenstandslos(monkeypatch):
    """#1662 AC-5.

    GIVEN ein Versandfehler-Vermerk und dieselbe Tour ist zur aktuellen Stunde
          regulaer faellig; der regulaere Versand gelingt.
    WHEN  der stuendliche Lauf (Vorlauf + regulaerer Slot) durch ist.
    THEN  erhielt der Nutzer GENAU EINE Nachricht, und der Vermerk ist weg.

    Mitgeprueft wird die tragende Zwischenstufe (Spec, Punkt 6): der Vorlauf
    darf den Vermerk NICHT mehr blind loeschen, sondern erst der gelungene
    regulaere Versand macht ihn gegenstandslos. Ohne diese Zwischenpruefung
    waere der Test auch vom Bestand erfuellt — der loescht bei Faelligkeit
    ersatzlos (`:386-388`) und verliert das Briefing, sobald der regulaere
    Versand dann doch scheitert.
    """
    from app.loader import save_trip

    uid = _fresh_user_1662("ac5")
    trip = _trip(f"trip-1662-ac5-{uuid.uuid4().hex[:6]}")
    save_trip(trip, user_id=uid)
    _seed_marker(uid, trip, reason="dispatch_error")

    zugestellt = _recording_email(monkeypatch)
    strategy = _strategy(uid, _settings_email_ok())
    due = [(trip, "morning")]

    strategy.pre_pass(hour=7, due=due)
    assert _dispatch_marker(uid) is not None, (
        "Der Vorlauf hat den Vermerk bei Faelligkeit blind geloescht — dann "
        "gibt es keinen 'letzten Versuch' mehr, wenn der regulaere Versand "
        f"gleich ebenfalls scheitert: {_pending_markers(uid)!r} (#1662 AC-5)"
    )
    assert zugestellt == [], (
        "Der Vorlauf darf in der Faelligkeitsstunde nicht zusaetzlich "
        f"zustellen (Doppel-Nachricht): {zugestellt!r} (#1662 AC-5)"
    )

    strategy.dispatch_one((trip, "morning"))

    assert len(zugestellt) == 1, (
        f"Der Nutzer muss genau EINE Nachricht bekommen, erhalten: "
        f"{len(zugestellt)} (#1662 AC-5)"
    )
    assert _pending_markers(uid) == [], (
        "Nach gelungenem regulaerem Versand ist der Vermerk gegenstandslos "
        f"und muss verschwinden: {_pending_markers(uid)!r} (#1662 AC-5)"
    )


# ═══════════════════════════════ #1662 AC-6 ══════════════════════════════════


def test_erneut_gescheiterter_regulaerer_versand_haelt_den_vermerk_am_leben():
    """#1662 AC-6.

    GIVEN ein Versandfehler-Vermerk, die Tour ist zur aktuellen Stunde regulaer
          faellig, und der regulaere Versand scheitert erneut.
    WHEN  der Lauf beendet ist.
    THEN  bleibt ein Versandfehler-Vermerk bestehen, sodass die naechste Stunde
          erneut nachholt.

    RED heute: der Vorlauf loescht den Vermerk bei Faelligkeit ersatzlos, der
    gescheiterte regulaere Versand schreibt keinen neuen — genau so gingen am
    07./08.08. ZWEI Briefings hintereinander verloren.
    """
    from app.loader import save_trip

    uid = _fresh_user_1662("ac6")
    trip = _trip(f"trip-1662-ac6-{uuid.uuid4().hex[:6]}")
    save_trip(trip, user_id=uid)
    _seed_marker(uid, trip, reason="dispatch_error")

    strategy = _strategy(uid, _settings_email_broken())
    due = [(trip, "morning")]
    strategy.pre_pass(hour=7, due=due)
    strategy.dispatch_one((trip, "morning"))

    assert strategy.result() == (0, 1), (
        f"Vorbedingung: der Lauf muss als gescheitert zaehlen, erhalten: "
        f"{strategy.result()!r}"
    )
    assert _dispatch_marker(uid) is not None, (
        "Nach dem zweiten Fehlschlag steht kein Vermerk mehr — das Briefing "
        "wird nie wieder versucht und ist endgueltig verloren: "
        f"{_pending_markers(uid)!r} (#1662 AC-6)"
    )


# ═══════════════════════════════ #1662 AC-7 ══════════════════════════════════


def test_ad_hoc_versandfehler_merkt_nichts_zur_nachlieferung_vor():
    """#1662 AC-7 (Grenz-Wache).

    GIVEN ein Ad-hoc-Abruf (nicht der regulaere Zeitplan) scheitert beim
          Versand.
    WHEN  der Aufruf beendet ist.
    THEN  entsteht KEIN Vermerk — ein Ad-hoc-Abruf bleibt gegenueber
          gespeichertem Zustand wirkungslos (#1007).

    Diese Zusicherung faellt, sobald der neue `except`-Zweig den Vermerk
    schreibt, ohne `on_demand` zu beachten.
    """
    uid = _fresh_user_1662("ac7")
    trip = _trip(f"trip-1662-ac7-{uuid.uuid4().hex[:6]}")

    _run_failing_briefing(uid, trip, gust=25.0, on_demand=True)

    assert _pending_markers(uid) == [], (
        "Ein Ad-hoc-Abruf darf keine Nachlieferung vormerken — sonst bekaeme "
        "der Nutzer ein Briefing, das er nie geplant hatte: "
        f"{_pending_markers(uid)!r} (#1662 AC-7)"
    )


# ═══════════════════════════════ #1662 AC-8 ══════════════════════════════════


def test_email_fehler_reisst_sms_und_telegram_nicht_mehr_mit(monkeypatch):
    """#1662 AC-8.

    GIVEN E-Mail scheitert, SMS und Telegram sind konfiguriert und
          funktionieren.
    WHEN  der Versandlauf beendet ist.
    THEN  gehen SMS und Telegram trotzdem hinaus, E-Mail fehlt in der
          Zustellbilanz, und es entsteht KEIN Vermerk — der Nutzer hat sein
          Briefing bereits ueber die funktionierenden Kanaele bekommen.

    RED heute: E-Mail laeuft zuerst und ist der einzige Kanal ohne `try` — die
    Ausnahme verlaesst `send_trip_report()` sofort, SMS und Telegram werden
    nie versucht. Konkreter Anlass: Garmin-inReach-Weg ab 20.08. (#1533).
    """
    uid = _fresh_user_1662("ac8")
    _allow_sms_tier(uid)
    trip = _trip(f"trip-1662-ac8-{uuid.uuid4().hex[:6]}",
                 send_sms=True, send_telegram=True)

    sms_out, telegram_out = _recording_sms_and_telegram(monkeypatch)
    scheduler = _fixture_scheduler(25.0)(
        settings=_settings_email_broken_sms_telegram_scharf(), user_id=uid,
    )
    outcome = scheduler._send_trip_report_outcome(trip, "morning", on_demand=False)

    assert outcome == "sent", (
        f"Der Lauf muss als zugestellt gelten, erhalten: {outcome!r} (#1662 AC-8)"
    )
    assert sms_out, "SMS wurde nicht versucht — der E-Mail-Fehler hat sie mitgerissen (AC-8)"
    assert telegram_out, (
        "Telegram wurde nicht versucht — der E-Mail-Fehler hat es mitgerissen (AC-8)"
    )
    kanaele = _briefing_log_channels(uid)
    assert kanaele and "email" not in kanaele[-1], (
        f"E-Mail darf nicht in der Zustellbilanz stehen: {kanaele!r} (#1662 AC-8)"
    )
    assert _pending_markers(uid) == [], (
        "Es darf KEIN Vermerk entstehen, wenn mindestens ein Kanal zugestellt "
        f"hat — sonst doppelt die Nachlieferung: {_pending_markers(uid)!r} (AC-8)"
    )


# ═══════════════════════════════ #1662 AC-9 ══════════════════════════════════


def test_unerwartete_telegram_stoerung_bricht_den_versandlauf_nicht_ab(monkeypatch):
    """#1662 AC-9.

    GIVEN beim Telegram-Versand tritt eine Stoerung auf, mit der der Pfad heute
          nicht rechnet (etwas anderes als `OutputError`), waehrend E-Mail
          erfolgreich zustellt.
    WHEN  der Versandlauf beendet ist.
    THEN  laeuft er normal zu Ende und gilt als erfolgreich — der
          Telegram-Fehlschlag zaehlt wie jeder andere Kanalfehler in die
          Zustellbilanz.

    RED heute: beide Telegram-Stellen fangen nur `OutputError`; alles andere
    fliegt bis in den `except`-Zweig des Schedulers — NACHDEM die E-Mail
    bereits raus ist. Genau der Randfall, an dem eine Nachlieferung doppeln
    wuerde.
    """
    uid = _fresh_user_1662("ac9")
    trip = _trip(f"trip-1662-ac9-{uuid.uuid4().hex[:6]}", send_telegram=True)

    zugestellt = _recording_email(monkeypatch)
    _recording_sms_and_telegram(
        monkeypatch, telegram_error=RuntimeError("Telegram-Transport gestoert (#1662)"),
    )
    settings = Settings(**{**_DUMMY_EMAIL_FIELDS, **_TELEGRAM_FIELDS})
    assert settings.can_send_email() and settings.can_send_telegram()
    scheduler = _fixture_scheduler(25.0)(settings=settings, user_id=uid)

    outcome = scheduler._send_trip_report_outcome(trip, "morning", on_demand=False)

    assert outcome == "sent", (
        "Eine unerwartete Telegram-Stoerung darf den Lauf nicht scheitern "
        f"lassen, solange E-Mail zugestellt hat, erhalten: {outcome!r} (AC-9)"
    )
    assert len(zugestellt) == 1, (
        f"Die E-Mail muss zugestellt worden sein: {zugestellt!r} (#1662 AC-9)"
    )
    assert _pending_markers(uid) == [], (
        "Mindestens ein Kanal hat zugestellt — es darf kein Vermerk entstehen, "
        f"sonst doppelt die Nachlieferung: {_pending_markers(uid)!r} (AC-9)"
    )


# ══════════════════════════════ #1662 AC-10 ══════════════════════════════════


def test_wetterfehler_vermerk_behaelt_die_segment_schnittmengen_regel(monkeypatch):
    """#1662 AC-10 (Regressionsschutz #1012).

    GIVEN ein WETTERfehler-Vermerk (ohne Grund-Feld) mit zuvor fehlgeschlagenen
          Abschnitten, die weiterhin keine Daten liefern.
    WHEN  der stuendliche Vorlauf laeuft.
    THEN  bleibt alles wie bisher: kein erneuter Versand, der Vermerk bleibt
          stehen und sein Zaehler waechst — die neuen Versandfehler-Zweige
          duerfen hier nicht greifen.
    """
    from app.loader import save_trip

    from app.models import SegmentWeatherData as _SWD
    from app.models import SegmentWeatherSummary as _SWS
    from services.trip_report_scheduler import TripReportSchedulerService

    uid = _fresh_user_1662("ac10")
    trip = _trip(f"trip-1662-ac10-{uuid.uuid4().hex[:6]}")
    save_trip(trip, user_id=uid)

    class _AllSegmentsFailing(TripReportSchedulerService):
        """Echte Unterklasse: jeder Abschnitt kommt als Fehler-Platzhalter
        zurueck — genau das, was `_fetch_weather()` bei Provider-Ausfall tut."""

        def _fetch_weather(self, segments, provider=None):
            return [
                _SWD(segment=s, timeseries=None, aggregated=_SWS(),
                     fetched_at=datetime.now(timezone.utc), provider="openmeteo",
                     has_error=True, error_message="Provider-Ausfall (#1662 AC-10)")
                for s in segments
            ]

    settings = _settings_email_ok()
    scheduler = _AllSegmentsFailing(settings=settings, user_id=uid)
    segment_ids = [
        str(s.segment_id) for s in scheduler._convert_trip_to_segments(trip, date.today())
    ]
    assert segment_ids, "Vorbedingung: die Tour muss heute Abschnitte haben"
    _seed_marker(uid, trip, reason=None, failed_segment_ids=segment_ids)

    zugestellt = _recording_email(monkeypatch)
    scheduler._process_pending_markers(9, set())

    assert zugestellt == [], (
        "Ein weiterhin fehlender Wetterabschnitt darf keinen Versand ausloesen "
        f"(#1012-Laermschutz): {zugestellt!r} (#1662 AC-10)"
    )
    entries = _pending_markers(uid)
    assert len(entries) == 1 and entries[0].get("attempts") == 1, (
        "Der Wetterfehler-Vermerk muss unveraendert bestehen bleiben und sein "
        f"Zaehler wachsen: {entries!r} (#1662 AC-10)"
    )
    assert entries[0].get("reason") is None, (
        f"Ein Wetterfehler-Vermerk darf keinen Versandfehler-Grund bekommen: "
        f"{entries[0]!r} (#1662 AC-10)"
    )


# ══════════════════════════════ #1662 AC-11 ══════════════════════════════════


def test_versandfehler_schreibt_anker_diagnose_UND_vermerk():
    """#1662 AC-11 (Regressionsschutz #1629).

    GIVEN ein Versandfehler.
    WHEN  der Fehlerpfad laeuft.
    THEN  liegen Wetter-Anker UND Diagnose-Zeile weiterhin vor (#1629) — der
          neue Vermerk kommt ZUSAETZLICH hinzu, nichts Bestehendes faellt weg.

    Die Reihenfolge im Test ist Absicht: zuerst die beiden Bestandszusagen,
    dann die neue. Faellt eine der ersten beiden, ist das eine Regression und
    keine offene Neuerung.
    """
    uid = _fresh_user_1662("ac11")
    trip = _trip(f"trip-1662-ac11-{uuid.uuid4().hex[:6]}")

    _run_failing_briefing(uid, trip, gust=25.0)

    assert _snapshots(uid).load_dated(trip.id, date.today()) is not None, (
        "REGRESSION #1629: der datierte Wetter-Anker fehlt (#1662 AC-11)"
    )
    journal = _dispatch_failure_journal(uid)
    assert journal.exists() and journal.read_text(encoding="utf-8").strip(), (
        "REGRESSION #1629: die Diagnose-Spur fehlt (#1662 AC-11)"
    )
    assert _dispatch_marker(uid) is not None, (
        "Der Nachliefer-Vermerk fehlt — Anker und Diagnose allein holen das "
        f"verlorene Briefing nicht nach: {_pending_markers(uid)!r} (AC-11)"
    )


# ══════════════════════════════ #1662 AC-12 ══════════════════════════════════


def test_vermerke_zweier_nutzer_bleiben_getrennt():
    """#1662 AC-12 (Mandantentrennung).

    GIVEN zwei verschiedene, echte Nutzer haben je einen fehlgeschlagenen
          Versand (nie die Sammelkennung "default").
    WHEN  beide Vermerke geschrieben sind.
    THEN  enthaelt die Ablage jedes Nutzers ausschliesslich den eigenen
          Eintrag — kein Nutzer sieht den Vermerk des anderen.
    """
    uid_a = _fresh_user_1662("ac12-a")
    uid_b = _fresh_user_1662("ac12-b")
    assert uid_a != uid_b and "default" not in (uid_a, uid_b)

    trip_a = _trip(f"trip-1662-ac12a-{uuid.uuid4().hex[:6]}")
    trip_b = _trip(f"trip-1662-ac12b-{uuid.uuid4().hex[:6]}")
    _run_failing_briefing(uid_a, trip_a, gust=25.0)
    _run_failing_briefing(uid_b, trip_b, gust=25.0)

    ids_a = [e.get("trip_id") for e in _pending_markers(uid_a)]
    ids_b = [e.get("trip_id") for e in _pending_markers(uid_b)]
    assert ids_a == [trip_a.id], (
        f"Nutzer A sieht nicht genau seinen eigenen Vermerk: {ids_a!r} (AC-12)"
    )
    assert ids_b == [trip_b.id], (
        f"Nutzer B sieht nicht genau seinen eigenen Vermerk: {ids_b!r} (AC-12)"
    )


# ══════════════════════════════ #1662 AC-13 ══════════════════════════════════


def test_gescheiterte_email_neben_gelungener_sms_bleibt_in_der_diagnose(monkeypatch):
    """#1662 AC-13.

    GIVEN E-Mail scheitert, SMS wird zugestellt.
    WHEN  der Lauf beendet ist.
    THEN  entsteht KEIN Vermerk (der Nutzer hat sein Briefing), der
          gescheiterte E-Mail-Versand ist aber in der Diagnose-Spur
          festgehalten — der Ausfall bleibt sichtbar, ohne dass ein
          funktionierender Kanal dafuer geopfert wird.

    RED heute: der E-Mail-Fehler reisst SMS mit, es kommt gar nichts an.
    """
    uid = _fresh_user_1662("ac13")
    _allow_sms_tier(uid)
    trip = _trip(f"trip-1662-ac13-{uuid.uuid4().hex[:6]}", send_sms=True)

    sms_out, _ = _recording_sms_and_telegram(monkeypatch)
    scheduler = _fixture_scheduler(25.0)(
        settings=_settings_email_broken_sms_telegram_scharf(), user_id=uid,
    )
    outcome = scheduler._send_trip_report_outcome(trip, "morning", on_demand=False)

    assert outcome == "sent" and sms_out, (
        f"Die SMS muss trotz E-Mail-Fehler zugestellt werden: outcome={outcome!r}, "
        f"sms={sms_out!r} (#1662 AC-13)"
    )
    assert _pending_markers(uid) == [], (
        "Mit zugestellter SMS darf keine Nachlieferung vorgemerkt werden: "
        f"{_pending_markers(uid)!r} (#1662 AC-13)"
    )
    journal = _dispatch_failure_journal(uid)
    assert journal.exists(), (
        "Der gescheiterte E-Mail-Versand muss trotzdem in der Diagnose-Spur "
        f"stehen — sonst ist der Ausfall unsichtbar ({journal.name}, AC-13)"
    )
    zeilen = [z for z in journal.read_text(encoding="utf-8").splitlines() if z.strip()]
    import json as _json
    assert any(_json.loads(z).get("entity_id") == trip.id for z in zeilen), (
        f"Kein Diagnose-Eintrag fuer diese Tour: {zeilen!r} (#1662 AC-13)"
    )


# ═════════════ #1662 AC-1, Zweitkanal-Luecke (Adversary-Befund F001) ══════════
#
# AC-1 sagt "kein einziger konfigurierter Kanal hat zugestellt" und nennt
# E-Mail ausdruecklich nur als Beispiel ("z.B."). Ist E-Mail fuer eine Tour gar
# nicht eingeschaltet und der EINZIGE konfigurierte Kanal scheitert, verlaesst
# den Versand keine Ausnahme (SMS und Telegram sind fail-soft) — der Vermerk
# haengt aber bis hierher allein am `except`-Zweig. Ergebnis: `sent_channels`
# leer, Rueckgabe "channels_unreachable", kein Vermerk, Briefing still
# verloren. Genau dieser Zuschnitt (Premium-SMS auf ein Garmin inReach) ist
# fuer den Karnischen Hoehenweg ab 20.08. vorgesehen (#1533).
#
# Die tragende Invariante der Spec lautet: ein Vermerk entsteht genau dann,
# wenn NICHTS zugestellt wurde. Sie darf nicht an der Frage haengen, WELCHER
# Kanal ausgefallen ist.
# ═════════════════════════════════════════════════════════════════════════════


def _settings_nur_sms_scharf() -> Settings:
    """SMS ist der einzige sendefaehige Kanal — und scheitert echt.

    Sicherung (#1477): E-Mail und Telegram sind ausdruecklich unbrauchbar
    konfiguriert und werden gegengeprueft; die SMS laeuft gegen den
    Discard-Port des eigenen Rechners, es geht nichts hinaus.
    """
    settings = Settings(**{**_BROKEN_EMAIL_FIELDS, **_SMS_FIELDS})
    assert settings.can_send_sms() is True, (
        "Vorbedingung: der SMS-Kanal muss betreten werden, sonst prueft "
        "dieser Test den Fall 'gar kein Kanal aktiv' statt AC-1."
    )
    assert settings.can_send_email() is False
    assert settings.can_send_telegram() is False
    return settings


def test_sms_only_ohne_zustellung_wird_zur_nachlieferung_vorgemerkt():
    """#1662 AC-1 (Adversary F001) — SMS ist der einzige Kanal und scheitert.

    GIVEN eine Tour ohne E-Mail-Versand, deren einziger konfigurierter Kanal
          SMS ist, und der SMS-Gateway ist nicht erreichbar.
    WHEN  der Versandlauf beendet ist (er wirft dabei KEINE Ausnahme — SMS ist
          fail-soft, die Zustellbilanz bleibt leer).
    THEN  liegt fuer diesen Trip trotzdem ein Vermerk mit dem Grund
          "Versandfehler" und ohne betroffene Wetterabschnitte vor.

    RED vor dem Fix: der Vermerk haengt ausschliesslich am `except`-Zweig, der
    hier nie laeuft — es entsteht kein Vermerk, das Briefing ist verloren.
    """
    uid = _fresh_user_1662("f001-sms")
    _allow_sms_tier(uid)
    trip = _trip(f"trip-1662-f001sms-{uuid.uuid4().hex[:6]}",
                 send_email=False, send_sms=True)

    scheduler = _fixture_scheduler(25.0)(
        settings=_settings_nur_sms_scharf(), user_id=uid,
    )
    outcome = scheduler._send_trip_report_outcome(trip, "morning", on_demand=False)

    assert outcome == "channels_unreachable", (
        "Vorbedingung: der einzige Kanal war konfiguriert, hat aber nicht "
        f"zugestellt — erhalten: {outcome!r} (#1662 AC-1)"
    )
    marker = _dispatch_marker(uid)
    assert marker is not None, (
        "Kein Kanal hat zugestellt, es fliegt aber keine Ausnahme — der "
        "Nachliefer-Vermerk fehlt und das Briefing ist ersatzlos verloren "
        f"(#1662 AC-1). Vorhanden: {_pending_markers(uid)!r}"
    )
    assert marker.get("trip_id") == trip.id, f"Falsche Tour im Vermerk: {marker!r}"
    assert marker.get("failed_segment_ids") == [], (
        "Ein Versandfehler betrifft keinen Wetterabschnitt — die Liste muss "
        f"leer sein, sonst zieht der Vorlauf die Wetterdaten-Logik: {marker!r}"
    )


def test_telegram_only_ohne_zustellung_wird_vorgemerkt_und_bleibt_unerreichbar(
    monkeypatch,
):
    """#1662 AC-1 (Adversary F001) — Telegram ist der einzige Kanal.

    GIVEN eine Tour ohne E-Mail- und ohne SMS-Versand, deren einziger
          konfigurierter Kanal Telegram ist, und der Telegram-Transport
          scheitert bei jeder Nachricht.
    WHEN  der Versandlauf beendet ist.
    THEN  liegt ein Vermerk mit dem Grund "Versandfehler" vor, UND der Lauf
          meldet weiterhin "channels_unreachable" statt zu werfen.

    Der zweite Teil ist Regressionsschutz: "Kanal konfiguriert, aber nicht
    erreichbar" ist ein bewusstes ERGEBNIS (#1403 AC-4, oben gesichert bei
    `test_erneut_gescheiterter_regulaerer_versand_haelt_den_vermerk_am_leben`),
    kein Abbruch. Der Vermerk darf nicht dadurch entstehen, dass hier neu eine
    Ausnahme geworfen wird.
    """
    uid = _fresh_user_1662("f001-tg")
    trip = _trip(f"trip-1662-f001tg-{uuid.uuid4().hex[:6]}",
                 send_email=False, send_telegram=True)

    _, telegram_out = _recording_sms_and_telegram(
        monkeypatch, telegram_error=RuntimeError("Telegram-Transport gestoert (F001)"),
    )
    settings = Settings(**{**_BROKEN_EMAIL_FIELDS, **_TELEGRAM_FIELDS})
    assert settings.can_send_telegram() is True
    assert settings.can_send_email() is False and settings.can_send_sms() is False
    scheduler = _fixture_scheduler(25.0)(settings=settings, user_id=uid)

    outcome = scheduler._send_trip_report_outcome(trip, "morning", on_demand=False)

    assert telegram_out == [], (
        f"Vorbedingung: es darf nichts zugestellt worden sein: {telegram_out!r}"
    )
    assert outcome == "channels_unreachable", (
        "REGRESSION: 'konfiguriert, aber unerreichbar' bleibt ein Ergebnis "
        f"(#1403 AC-4) — erhalten: {outcome!r}"
    )
    marker = _dispatch_marker(uid)
    assert marker is not None, (
        "Telegram war der einzige Kanal und hat nichts zugestellt — ohne "
        "Vermerk wird das Briefing nie nachgeholt "
        f"(#1662 AC-1). Vorhanden: {_pending_markers(uid)!r}"
    )
    assert marker.get("trip_id") == trip.id, f"Falsche Tour im Vermerk: {marker!r}"


def test_tour_ganz_ohne_kanal_wird_nicht_zur_nachlieferung_vorgemerkt():
    """#1662 AC-1, Gegenprobe zur Abgrenzung (Mutations-Fund M3).

    GIVEN eine Tour, fuer die GAR KEIN Kanal eingeschaltet ist.
    WHEN  der Versandlauf beendet ist.
    THEN  entsteht KEIN Vermerk — hier ist nichts ausgefallen, es war nichts
          vorgesehen; eine Nachlieferung haette kein Ziel und liesse den
          Monitor-Zaehler `open_pending_briefings` dauerhaft klettern.

    Aufgedeckt bei der Mutations-Gegenprobe zu F001: ein Vermerk im Zweig
    `no_channel_configured` blieb von jedem Test unbemerkt. Die Abgrenzung
    "nichts zugestellt" vs. "nichts vorgesehen" ist damit gesichert, nicht
    bloss kommentiert.
    """
    uid = _fresh_user_1662("kein-kanal")
    trip = _trip(f"trip-1662-nochan-{uuid.uuid4().hex[:6]}", send_email=False)
    assert not any((trip.report_config.send_email, trip.report_config.send_sms,
                    trip.report_config.send_telegram)), "Vorbedingung: kein Kanal"

    scheduler = _fixture_scheduler(25.0)(
        settings=_settings_email_broken(), user_id=uid,
    )
    outcome = scheduler._send_trip_report_outcome(trip, "morning", on_demand=False)

    assert outcome == "no_channels", (
        f"Vorbedingung: der Lauf muss 'kein Kanal aktiv' melden: {outcome!r}"
    )
    assert _pending_markers(uid) == [], (
        "Ohne konfigurierten Kanal ist nichts ausgefallen — ein Vermerk waere "
        f"eine Nachlieferung ins Leere: {_pending_markers(uid)!r} (#1662)"
    )
