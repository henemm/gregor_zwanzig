"""RED — Issue #1701 (#1676 Scheibe S2b): Premium-SMS im Ortsvergleich-
Alarmpfad.

Spec: docs/specs/modules/feat_1701_alarm_premium_sms.md
Abgedeckt: AC-4, AC-5 (Compare-Teil).

TESTPOLITIK (CLAUDE.md "Test-Politik: Zwei Schichten", Kern-Schicht): kein
Mock-Theater. Der Ortsvergleich kennt drei STRUKTURELL getrennte
Alarm-Dispatcher (Aenderung/Radar/amtlich); je einer wird hier ueber seinen
echten Service-Pfad ausgeloest. E-Mail laeuft ueber ``mail_sink`` (DI-Seam,
kein SMTP), Premium-SMS geht ueber einen ECHTEN lokalen HTTP-Stub, weil
weder ``send_multi_location_deviation_alert()`` noch
``send_multi_location_radar_alert()`` einen SMS-Sink kennen (nur
``mail_sink``) -- Telegram/SMS werden deshalb in diesen Presets bewusst NICHT
aktiviert, um den Stub sauber auf Premium-SMS zu beschraenken.

Pfadregel #1409: kein fester Hauptrepo-Pfad -- alle Zugriffe laufen ueber
``get_data_dir()``/``get_data_root()`` (pytest-isolierte Datenwurzel, #1133).
"""
from __future__ import annotations

import http.server
import json
import shutil
import socket
import threading
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings
from app.loader import save_location
from app.user import SavedLocation
from services.official_alerts import OfficialAlert
from utils.timezone import first_resolvable_tz

from tests.helpers.briefing_zeiten import briefing_zeiten_iso
from tests.helpers.compare_briefings import write_compare_briefings

LEARNED_REPLY_TO = "+4915799912345"
PREMIUM_SMS_SENDER = "4916092172595"
LAT, LON = 47.07, 15.44


def _data_root_users() -> Path:
    """Nutzer-Wurzel der Compare-Preset-Ablage -- Funktion statt Konstante
    (#1595), s. ``tests/tdd/test_compare_alert_channel_delivery.py``."""
    from app.loader import get_data_root

    return get_data_root() / "users"


# ---------------------------------------------------------------------------
# Lokaler seven.io-Stub -- bedient SMS UND Premium-SMS (geteilte
# ``sms_gateway_url``, SevenIoChannelBase).
# ---------------------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _SevenIoStub:
    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                data = urllib.parse.parse_qs(body.decode())
                received.append({k: v[0] for k, v in data.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()

    def to(self, number: str) -> list[dict]:
        return [e for e in self.received if e.get("to") == number]


# ---------------------------------------------------------------------------
# Fixture-Bausteine
# ---------------------------------------------------------------------------

def _uid(prefix: str) -> str:
    return f"tdd-1701-cmp-{prefix}-{uuid.uuid4().hex[:6]}"


def _clean_user(user_id: str) -> None:
    d = _data_root_users() / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _write_profile(
    user_id: str, *, tier: str, reply_to: str | None = None,
    reply_age: timedelta = timedelta(minutes=5),
) -> None:
    from app.loader import get_data_dir

    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    profile: dict = {"id": user_id, "tier": tier}
    if reply_to is not None:
        stamp = datetime.now(timezone.utc) - reply_age
        profile["premium_sms_reply_to"] = reply_to
        profile["premium_sms_reply_at"] = stamp.isoformat().replace("+00:00", "Z")
    (path / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def _settings(port: int, user_id: str) -> Settings:
    """JEDES versandrelevante Feld ausdruecklich gesetzt (#1477) -- kein
    stiller Ruecksprung auf die Prod-.env des Worktrees. E-Mail-Felder
    sind dummy, aber gesetzt: NIE tatsaechlich kontaktiert, weil jeder
    Aufrufer hier ``mail_sink`` uebergibt -- ohne ``smtp_host``/``mail_to``
    liefert ``can_send_email()`` lokal (echte ``.env`` im Worktree) etwas
    anderes als auf dem CI-Runner (keine ``.env``)."""
    update = {
        "sms_gateway_url": f"http://127.0.0.1:{port}/api/sms",
        "seven_api_key": "test-stub-key",
        "seven_sandbox_key": "test-stub-key",
        "sms_to": "+49000000111",
        "sms_from": None,
        "smtp_host": "dummy.invalid", "smtp_user": "dummy", "smtp_pass": "dummy",
        "mail_to": "dummy@example.com",
    }
    return Settings().with_user_profile(user_id).model_copy(update=update)


def _compare_preset(preset_id: str, location_ids: list[str], **extra) -> dict:
    """Compare-Preset-Rohdict -- ``**extra`` setzt NUR ausdruecklich
    uebergebene Schluessel (Vorbild
    ``tests/tdd/test_compare_alert_channel_delivery.py::_compare_preset``)."""
    preset = {
        "id": preset_id, "name": preset_id, "user_id": "unused",
        "location_ids": list(location_ids), "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": [], "letzter_versand": None, "top_ort_letzter_versand": None,
        "created_at": "2026-08-11T00:00:00Z",
    }
    preset.update(extra)
    return preset


def _preset_briefing_zeiten() -> tuple[str, str]:
    """Morgen-/Abend-Slot ausserhalb des Vorlauf-Fensters (#1594) -- in GENAU
    der Zone, die der Compare-Faelligkeitspfad selbst auswertet
    (``first_resolvable_tz``, ``compare_alert.py::_build_eval_config`` bzw.
    ``compare_official_alert.py::check_all_compare_presets``), nicht in einer
    angenommenen festen Zone. Ohne explizites ``morning_time`` faellt ein
    Preset auf den Migrations-Fallback 06:00 Ortszeit zurueck
    (``compare_slot_scheduler.py::resolve_preset_slots``) -- das ist
    zwischen ca. 05:00 und 07:00 Ortszeit ein taeglich wiederkehrendes
    Sperrfenster (dieselbe Fehlerklasse wie #1594 auf der Trip-Seite, hier am
    Ortsvergleich). Alle Presets dieser Datei liegen auf LAT/LON, eine
    Probe-Location genuegt fuer die Aufloesung."""
    zone = first_resolvable_tz(
        [SavedLocation(id="probe", name="probe", lat=LAT, lon=LON, elevation_m=0)],
    )
    return briefing_zeiten_iso(zone)


def _write_presets(user_id: str, presets: list[dict]) -> None:
    write_compare_briefings(_data_root_users() / user_id, presets)


def _pwd(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float):
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider="test-scripted",
    )


class _ScriptedWeatherSource:
    """Deterministische ``LocationWeatherSource`` (kein Mock): liefert echte
    ``PointWeatherData`` ohne Netz."""

    def __init__(self, values: dict[str, float]) -> None:
        self._values = dict(values)

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None):
        return _pwd(point_id, point_id, lat, lon, self._values.get(point_id, 0.0))


class _CoordFrameSource:
    """Echter ``frame_source``-Doppelgaenger fuer ``RadarNowcastService`` --
    liefert je Koordinate einen vorab festgelegten, echten ``RadarFrame``-Satz
    (Vorbild ``tests/tdd/test_compare_radar_alert.py::_CoordFrameSource``)."""

    def __init__(self, by_coord: dict[tuple[float, float], list]) -> None:
        self._by_coord = by_coord

    def __call__(self, lat: float, lon: float) -> list:
        return self._by_coord.get((round(lat, 4), round(lon, 4)), [])


def _wet_frame(onset_minutes: int) -> list:
    from providers.brightsky import RadarFrame

    ts = datetime.now(timezone.utc) + timedelta(minutes=onset_minutes)
    return [RadarFrame(timestamp=ts, precip_mm_h=0.6, is_convective=False)]


class _FakeOfficialAlertSource:
    """Echte Quelle (kein Mock): zustaendig fuer einen Punkt, liefert
    steuerbare Alerts (Vorbild ``tests/tdd/test_compare_official_alert.py``)."""

    def __init__(self, lat, lon, alerts):
        self._lat, self._lon, self._alerts = lat, lon, alerts

    @property
    def name(self) -> str:
        return "tdd-1701-source"

    def covers(self, lat, lon) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat, lon):
        return list(self._alerts)


def _official_alert() -> OfficialAlert:
    now = datetime.now(timezone.utc)
    return OfficialAlert(
        source="tdd-1701-source", hazard="thunderstorm", level=3, label="Gewitter",
        valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=23),
        region_label="Testregion",
    )


def _sources_backup():
    import services.official_alerts.base as b

    return b, list(b._REGISTERED_SOURCES)


# ═══════════════════════════════ AC-4 ═════════════════════════════════════

def test_compare_deviation_alert_reaches_premium_sms():
    """AC-4 (Aenderungsalarm): Given ein Ortsvergleich-Preset hat
    ``send_premium_sms=true`` (Nutzer ist Premium-Tier) / When ein
    Aenderungsalarm fuer einen betroffenen Vergleichsort ausgeloest wird /
    Then wird der Ort zusaetzlich per Premium-SMS gemeldet.

    ROT-Grund (gemessen): ``effective_compare_channels()`` hat keinen
    ``premium_sms``-Zweig (``compare_alert_channels.py:28-36``).
    """
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid = _uid("ac4-dev")
    _clean_user(uid)
    try:
        _write_profile(uid, tier="premium", reply_to=LEARNED_REPLY_TO)
        preset_id = f"cp-ac4-dev-{uuid.uuid4().hex[:6]}"
        loc_id = "loc-1"
        save_location(
            SavedLocation(id=loc_id, name="Testort", lat=LAT, lon=LON, elevation_m=353),
            user_id=uid,
        )
        morgen, abend = _preset_briefing_zeiten()
        _write_presets(uid, [_compare_preset(
            preset_id, [loc_id], send_premium_sms=True,
            morning_time=morgen, evening_time=abend,
        )])
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, loc_id, _pwd(loc_id, "Testort", LAT, LON, 2.0),
        )

        stub = _SevenIoStub()
        try:
            mails: list = []
            svc = CompareAlertService(
                settings=_settings(stub.port, uid), user_id=uid,
                weather_source=_ScriptedWeatherSource({loc_id: 30.0}),
                mail_sink=lambda subject, body: mails.append((subject, body)),
            )
            svc.check_all_compare_presets()
        finally:
            stub.stop()

        hits = stub.to(LEARNED_REPLY_TO)
        assert len(hits) == 1, (
            f"AC-4 (Aenderungsalarm): erwartet GENAU EINE Premium-SMS, "
            f"erhalten: {hits!r} (voller Stub: {stub.received!r})"
        )
        assert hits[0].get("from") == PREMIUM_SMS_SENDER
        assert mails, "E-Mail muss weiterhin zugestellt werden (E-Mail immer aktiv)"
    finally:
        _clean_user(uid)


def test_compare_radar_alert_reaches_premium_sms():
    """AC-4 (Regenradar): Given dasselbe Opt-in / When ein Regenradar-Onset
    fuer einen Vergleichsort ausgeloest wird / Then wird auch dafuer per
    Premium-SMS gemeldet -- eigener, strukturell getrennter Dispatcher
    (``compare_radar_alert.py``).

    ROT-Grund (gemessen): derselbe fehlende ``premium_sms``-Zweig in
    ``effective_compare_channels()``, hier ueber den Radar-Pfad erreicht.
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = _uid("ac4-radar")
    _clean_user(uid)
    try:
        _write_profile(uid, tier="premium", reply_to=LEARNED_REPLY_TO)
        preset_id = f"cp-ac4-radar-{uuid.uuid4().hex[:6]}"
        loc_id = "loc-1"
        save_location(
            SavedLocation(id=loc_id, name="Testort", lat=LAT, lon=LON, elevation_m=353),
            user_id=uid,
        )
        _write_presets(uid, [_compare_preset(
            preset_id, [loc_id], send_premium_sms=True, radar_alert_enabled=True,
        )])

        stub = _SevenIoStub()
        try:
            mails: list = []
            frame_source = _CoordFrameSource({(LAT, LON): _wet_frame(8)})
            svc = CompareRadarAlertService(
                settings=_settings(stub.port, uid), user_id=uid,
                radar_service=RadarNowcastService(frame_source=frame_source),
                mail_sink=lambda subject, body: mails.append((subject, body)),
            )
            sent = svc.check_all_compare_presets()
        finally:
            stub.stop()

        assert sent == 1, f"Voraussetzung: Radar-Alarm muss ausgeloest sein, sent={sent}"
        hits = stub.to(LEARNED_REPLY_TO)
        assert len(hits) == 1, (
            f"AC-4 (Radar): erwartet GENAU EINE Premium-SMS, erhalten: {hits!r} "
            f"(voller Stub: {stub.received!r})"
        )
    finally:
        _clean_user(uid)


def test_compare_official_alert_reaches_premium_sms():
    """AC-4 (amtliche Warnung): Given dasselbe Opt-in / When eine amtliche
    Warnung fuer einen Vergleichsort eintrifft / Then wird auch dafuer per
    Premium-SMS gemeldet -- dritter, strukturell getrennter Dispatcher
    (``send_multi_location_official_alert``, in der Spec als
    "send_compare_official_alert" bezeichnet).

    ROT-Grund (gemessen): weder ``effective_compare_channels()`` noch
    ``send_multi_location_official_alert()`` kennen ``premium_sms``.
    """
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source

    uid = _uid("ac4-off")
    _clean_user(uid)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        _write_profile(uid, tier="premium", reply_to=LEARNED_REPLY_TO)
        preset_id = f"cp-ac4-off-{uuid.uuid4().hex[:6]}"
        loc_id = "loc-a"
        save_location(
            SavedLocation(id=loc_id, name="Testort", lat=LAT, lon=LON, elevation_m=353),
            user_id=uid,
        )
        morgen, abend = _preset_briefing_zeiten()
        _write_presets(uid, [_compare_preset(
            preset_id, [loc_id], send_premium_sms=True,
            morning_time=morgen, evening_time=abend,
        )])
        register_official_alert_source(_FakeOfficialAlertSource(LAT, LON, [_official_alert()]))

        stub = _SevenIoStub()
        try:
            mails: list = []
            svc = CompareOfficialAlertService(
                settings=_settings(stub.port, uid), user_id=uid,
                mail_sink=lambda subject, body: mails.append((subject, body)),
            )
            svc.check_all_compare_presets()
        finally:
            stub.stop()

        hits = stub.to(LEARNED_REPLY_TO)
        assert len(hits) == 1, (
            f"AC-4 (Amtlich): erwartet GENAU EINE Premium-SMS, erhalten: {hits!r} "
            f"(voller Stub: {stub.received!r})"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)


# ═══════════════════════════════ AC-5 (Compare) ═══════════════════════════

_CONTROL_REPLY_TO = "+4915799954321"


def _run_three_compare_dispatchers(uid: str, reply_to: str, stub: "_SevenIoStub") -> None:
    """Legt Orte/Presets fuer alle drei Ortsvergleichs-Alarmarten an und
    loest sie aus -- gemeinsamer Baustein fuer die Standard- UND die
    Kontroll-Seite von AC-5, damit beide Seiten identisch konfiguriert sind
    bis auf das Tarif der jeweiligen ``user_id``."""
    from services.compare_alert import CompareAlertService
    from services.compare_official_alert import CompareOfficialAlertService
    from services.compare_radar_alert import CompareRadarAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.official_alerts import register_official_alert_source
    from services.radar_service import RadarNowcastService

    loc_dev, loc_radar, loc_off = f"{uid}-dev", f"{uid}-radar", f"{uid}-off"
    for loc_id in (loc_dev, loc_radar, loc_off):
        save_location(
            SavedLocation(id=loc_id, name=loc_id, lat=LAT, lon=LON, elevation_m=353),
            user_id=uid,
        )
    preset_dev = f"cp-{uid}-dev"
    preset_radar = f"cp-{uid}-radar"
    preset_off = f"cp-{uid}-off"
    _write_presets(uid, [
        _compare_preset(preset_dev, [loc_dev], send_premium_sms=True),
        _compare_preset(preset_radar, [loc_radar], send_premium_sms=True, radar_alert_enabled=True),
        _compare_preset(preset_off, [loc_off], send_premium_sms=True),
    ])
    CompareWeatherSnapshotService(user_id=uid).save(
        preset_dev, loc_dev, _pwd(loc_dev, loc_dev, LAT, LON, 2.0),
    )
    register_official_alert_source(_FakeOfficialAlertSource(LAT, LON, [_official_alert()]))

    settings = _settings(stub.port, uid)

    CompareAlertService(
        settings=settings, user_id=uid,
        weather_source=_ScriptedWeatherSource({loc_dev: 30.0}),
        mail_sink=lambda subject, body: None,
    ).check_all_compare_presets()

    frame_source = _CoordFrameSource({(LAT, LON): _wet_frame(8)})
    CompareRadarAlertService(
        settings=settings, user_id=uid,
        radar_service=RadarNowcastService(frame_source=frame_source),
        mail_sink=lambda subject, body: None,
    ).check_all_compare_presets()

    CompareOfficialAlertService(
        settings=settings, user_id=uid,
        mail_sink=lambda subject, body: None,
    ).check_all_compare_presets()


def test_standard_tier_never_reaches_premium_sms_via_compare_alerts():
    """AC-5 (Compare): Given ZWEI Nutzer mit identisch konfiguriertem
    ``send_premium_sms=true`` in Presets fuer alle drei Alarmarten -- Nutzer
    A hat Tier ``standard``, Nutzer B (Kontrolle) hat Tier ``premium`` /
    When bei BEIDEN dieselben drei Ortsvergleichs-Alarmpfade ausgeloest
    werden / Then bleibt Premium-SMS bei Nutzer A in JEDEM der drei Pfade
    inaktiv, waehrend Nutzer B sie in mindestens einem Pfad bekommt --
    ``premium_sms_allowed()`` (NICHT ``sms_allowed()``) entscheidet.

    Warum beide Seiten in EINEM Test stehen: die stumme Seite (Nutzer A)
    ist bereits HEUTE gruen, weil Premium-SMS im Ortsvergleich noch
    NIRGENDS verdrahtet ist (AC-4-Tests derselben Datei sind rot). Erst die
    Kontroll-Seite (Nutzer B, MUSS mindestens einmal ankommen) macht den
    Test scharf und damit heute ROT.
    """
    from services.user_tier import premium_sms_allowed, sms_allowed

    uid = _uid("ac5")
    uid_control = _uid("ac5-control")
    _clean_user(uid)
    _clean_user(uid_control)
    b, backup = _sources_backup()
    b._REGISTERED_SOURCES.clear()
    try:
        _write_profile(uid, tier="standard", reply_to=LEARNED_REPLY_TO)
        _write_profile(uid_control, tier="premium", reply_to=_CONTROL_REPLY_TO)
        assert sms_allowed(uid) is True and premium_sms_allowed(uid) is False, (
            "Testvoraussetzung: 'standard' darf normale SMS, aber NICHT Premium-SMS"
        )
        assert premium_sms_allowed(uid_control) is True, (
            "Testvoraussetzung Kontrolle: 'premium' darf Premium-SMS"
        )

        stub = _SevenIoStub()
        try:
            _run_three_compare_dispatchers(uid, LEARNED_REPLY_TO, stub)
            _run_three_compare_dispatchers(uid_control, _CONTROL_REPLY_TO, stub)
        finally:
            stub.stop()

        hits_standard = stub.to(LEARNED_REPLY_TO)
        hits_control = stub.to(_CONTROL_REPLY_TO)
        assert hits_standard == [], (
            "AC-5: ein Nutzer mit Tier 'standard' darf in KEINEM der drei "
            f"Ortsvergleichs-Alarmpfade eine Premium-SMS bekommen, erhalten: "
            f"{hits_standard!r}"
        )
        assert len(hits_control) >= 1, (
            "AC-5 (Kontrolle): ein Nutzer mit Tier 'premium' MUSS bei "
            "identischer Konfiguration Premium-SMS bekommen -- sonst beweist "
            "die stumme Seite oben nur, dass Premium-SMS im Ortsvergleich "
            "ueberhaupt nicht verdrahtet ist, nicht dass das Tier-Gate "
            f"entscheidet. Erhalten: {hits_control!r} (voller Stub: "
            f"{stub.received!r})"
        )
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)
        _clean_user(uid_control)
