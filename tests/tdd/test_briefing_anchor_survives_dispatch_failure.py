"""TDD RED — Issue #1629: der Briefing-Anker ueberlebt einen Versandfehler.

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


def _trip(trip_id: str, *, with_levels: bool = False) -> Trip:
    """Tour mit einer Etappe HEUTE und scharfem E-Mail-Kanal."""
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
            # Katalog-Kennung fuer Boeen ist "gust" (nicht "wind") — mit der
            # falschen Kennung gilt wind_gust als nicht aktiv und die Stufe
            # wird still verworfen.
            metrics=[MetricConfig(metric_id="gust", enabled=True)],
            metric_alert_levels={"wind_gust": "standard"},
        )
    trip = Trip(id=trip_id, name="Anker-Trip #1629", stages=[stage], **kwargs)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=False, send_sms=False,
        alert_on_changes=with_levels,
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
