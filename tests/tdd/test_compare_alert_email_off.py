"""TDD RED — Issue #2279 Scheibe S1 (AC-2): Ortsvergleich kann E-Mail für
Alarme abschalten (`alert_channels.email=false`), Ende-zu-Ende über alle
drei Compare-Alarmpfade.

SPEC: docs/specs/modules/rework_2279_s1_alert_kanal_aufloesung.md (AC-2,
Mutations-Gegenprobe (a))
KONTEXT: docs/context/rework-2279-alert-kanal-aufloesung.md

IST-STAND (gemessen, vor dieser Scheibe): der damalige Compare-Alarm-Resolver
startet mit `channels = {"email"}` -- E-Mail ist HART an, unabhängig von
jedem Preset-Feld. Ein `alert_channels`-Override wird von KEINEM der drei
Compare-Alarmpfade (`compare_alert.py`, `compare_official_alert.py`,
`compare_radar_alert.py`) heute überhaupt gelesen. Alle drei Tests sind
deshalb ROT: die Mail-Senke bekommt trotz `alert_channels.email=False`
eine Zustellung, obwohl sie leer bleiben müsste.

Mock-frei (CLAUDE.md): echte Compare-Services, echte Preset-/Orts-Dateien,
echte (skriptierte) Wetterquellen-/Radar-/amtliche-Warnung-Seams. E-Mail
wird über den echten `mail_sink`-DI-Seam beobachtet (kein SMTP-Socket),
Telegram über den echten `telegram_sink`-DI-Seam (amtlicher Pfad, kennt
ihn bereits) bzw. einen echten lokalen HTTP-Stub für die Telegram-Bot-API
(Abweichungs-/Radar-Pfad, die keinen `telegram_sink` kennen -- Vorbild
`test_compare_alert_channel_delivery.py`/`test_compare_radar_alert_telegram_style.py`).

Settings sind ABSICHTLICH voll sendebereit (SMTP+Telegram, #1477-konform
JEDES Feld ausdrücklich gesetzt): der Test soll eine AKTIVE Unterdrückung
durch `alert_channels` beweisen, nicht eine zufällig fehlende
Konto-Konfiguration.

Pfadregel #1409: Preset-/Orts-Dateien relativ zur Testdatei über
`app.loader.get_data_root()`, kein fester Hauptrepo-Pfad.
"""
from __future__ import annotations

import http.server
import json
import shutil
import socket
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import output.channels.telegram as tg_module
from app.config import Settings
from app.models import SegmentWeatherSummary
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings


def _data_root_users() -> Path:
    """Funktion statt Konstante (#1595) -- Vorbild
    `test_compare_alert_channel_delivery.py::_data_root_users`: `get_data_root()`
    liefert erst zur Laufzeit die von der #1133-Fixture gesetzte Basis."""
    from app.loader import get_data_root

    return get_data_root() / "users"


def _clean_user(user_id: str) -> None:
    d = _data_root_users() / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _uid(prefix: str) -> str:
    return f"tdd-2279-s1-ac2-{prefix}-{uuid.uuid4().hex[:6]}"


def _write_tier(user_id: str, tier: str) -> None:
    from app.loader import get_data_dir

    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "user.json").write_text(json.dumps({"id": user_id, "tier": tier}))


def _settings_all_channels() -> Settings:
    """ALLE Kanäle technisch erreichbar (#1477: jedes versandrelevante Feld
    ausdrücklich gesetzt) -- so entscheidet ausschließlich `alert_channels`,
    nicht ein zufällig fehlendes Konto-Feld."""
    # `telegram_test_chat_id` MUSS identisch zu `telegram_chat_id` gesetzt
    # sein: die Herkunftssperre (Issue #1476, `_guard_code_origin()`) bricht
    # aus einem Testlauf-Verzeichnis sonst JEDEN Telegram-Versand vor dem
    # HTTP-Request ab (Vorbild `test_compare_radar_alert_telegram_style.py::
    # _telegram_only_settings`).
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
        telegram_bot_token="tdd-2279-stub-token", telegram_chat_id="99999",
        telegram_test_chat_id="99999",
        sms_gateway_url="https://sms.invalid/api/sms",
        seven_api_key="dummy-key", sms_to="+490000000000", sms_from=None,
    )


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


_ALERT_CHANNELS_EMAIL_OFF = {
    "email": False, "telegram": True, "sms": False, "premium_sms": False,
}


def _preset(preset_id: str, location_ids: list[str], **extra) -> dict:
    preset: dict = {
        "id": preset_id, "name": preset_id, "user_id": "unused",
        "location_ids": list(location_ids), "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": [], "created_at": "2026-09-09T00:00:00Z",
        "alert_channels": dict(_ALERT_CHANNELS_EMAIL_OFF),
        "send_telegram": True,
    }
    preset.update(extra)
    return preset


def _pwd(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float):
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider="test-scripted",
    )


class _ScriptedWeatherSource:
    """Deterministische `LocationWeatherSource`-Fassung (kein Mock) --
    liefert für JEDE angeforderte ID denselben vorab festgelegten Messwert."""

    def __init__(self, values: dict[str, float]) -> None:
        self._values = dict(values)

    def fetch(
        self, point_id: str, lat: float, lon: float,
        start_hour: int | None = None, end_hour: int | None = None,
        elevation_m: int | None = None,
    ):
        return _pwd(point_id, point_id, lat, lon, self._values.get(point_id, 0.0))


# ---------------------------------------------------------------------------
# Echter lokaler HTTP-Stub für die Telegram-Bot-API (Abweichungs-/Radar-Pfad,
# die -- anders als der amtliche Pfad -- keinen `telegram_sink`-DI-Seam kennen)
# ---------------------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _TelegramStub:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body.decode())
                except ValueError:
                    payload = {}
                sent.append(payload)
                resp = json.dumps({"ok": True, "result": {"message_id": 1}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, *args):  # noqa: D401 - silence
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def texts(self) -> list[str]:
        return [p.get("text", "") for p in self.sent]

    def stop(self) -> None:
        self._server.shutdown()


# ═══════════════════ AC-2a — Vorhersage-Änderungsalarm (Deviation) ══════════

def test_ac2_deviation_alert_stays_silent_on_email_with_channels_off(monkeypatch):
    """AC-2: Ortsvergleich mit `alert_channels={"email": False, "telegram":
    True, ...}`, ein Ort mit einer Wetteränderung weit über der Δ-Schwelle.

    THEN bleibt die Mail-Senke leer, Telegram bekommt genau eine
    Zustellung.

    ROT-Grund (gemessen): der damalige Compare-Alarm-Resolver setzt E-Mail
    hart auf an -- die Mail-Senke bekommt trotz `email=False` eine
    Zustellung."""
    from app.loader import save_location
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid = _uid("deviation")
    preset_id = f"cp-{uid}"
    loc_id = "loc-1"
    tg_stub = _TelegramStub()
    _clean_user(uid)
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
        _write_tier(uid, "premium")

        save_location(_location(loc_id, "Graz", 47.07, 15.44), user_id=uid)
        write_compare_briefings(
            _data_root_users() / uid, [_preset(preset_id, [loc_id])],
        )
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, loc_id, _pwd(loc_id, "Graz", 47.07, 15.44, 2.0),
        )

        mails: list[tuple[str, str]] = []
        service = CompareAlertService(
            settings=_settings_all_channels(), user_id=uid,
            weather_source=_ScriptedWeatherSource({loc_id: 30.0}),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        sent = service.check_all_compare_presets()

        assert sent == 1, f"Vorbedingung: der Alarm muss ausloesen, gemessen sent={sent}"
        assert mails == [], (
            "AC-2: die Mail-Senke muss bei alert_channels.email=False LEER "
            f"bleiben, gemessen: {mails!r}"
        )
        assert len(tg_stub.texts()) == 1, (
            "AC-2: Telegram muss trotzdem GENAU EINE Zustellung bekommen, "
            f"gemessen: {tg_stub.texts()!r}"
        )
    finally:
        tg_stub.stop()
        _clean_user(uid)


# ══════════════════════════ AC-2b — Radar-Nowcast ═══════════════════════════

def test_ac2_radar_alert_stays_silent_on_email_with_channels_off(monkeypatch):
    """AC-2, Radar-Nowcast-Pfad: derselbe `alert_channels`-Schalter muss den
    Onset-Alarm ohne E-Mail, aber mit Telegram zustellen.

    ROT-Grund (gemessen): identisch zum Deviation-Pfad -- E-Mail ist im
    heutigen Resolver hart verdrahtet, der `alert_channels`-Schalter wird
    ignoriert."""
    from app.loader import save_location
    from providers.brightsky import RadarFrame
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_cache import reset_shared_radar_cache_for_tests
    from services.radar_service import RadarNowcastService

    uid = _uid("radar")
    preset_id = f"cp-{uid}"
    loc_id = "loc-1"
    lat, lon = 48.2082, 16.3738  # Wien -- eigene Koordinate, kein Cache-Konflikt
    tg_stub = _TelegramStub()
    _clean_user(uid)
    reset_shared_radar_cache_for_tests()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
        _write_tier(uid, "premium")

        save_location(_location(loc_id, "Wien", lat, lon), user_id=uid)
        write_compare_briefings(
            _data_root_users() / uid,
            [_preset(preset_id, [loc_id], radar_alert_enabled=True)],
        )

        onset_at = datetime.now(timezone.utc) + timedelta(minutes=8)

        def _frame_source(_lat: float, _lon: float) -> list:
            return [RadarFrame(timestamp=onset_at, precip_mm_h=0.6, is_convective=False)]

        mails: list[tuple[str, str]] = []
        service = CompareRadarAlertService(
            settings=_settings_all_channels(), user_id=uid,
            radar_service=RadarNowcastService(frame_source=_frame_source),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        )
        sent = service.check_all_compare_presets()

        assert sent == 1, f"Vorbedingung: der Nowcast muss ausloesen, gemessen sent={sent}"
        assert mails == [], (
            "AC-2: die Mail-Senke muss bei alert_channels.email=False LEER "
            f"bleiben, gemessen: {mails!r}"
        )
        assert len(tg_stub.texts()) == 1, (
            "AC-2: Telegram muss trotzdem GENAU EINE Zustellung bekommen, "
            f"gemessen: {tg_stub.texts()!r}"
        )
    finally:
        tg_stub.stop()
        _clean_user(uid)
        reset_shared_radar_cache_for_tests()


# ═════════════════════ AC-2c — Amtliche Warnung (Standalone) ════════════════

def test_ac2_official_alert_stays_silent_on_email_with_channels_off():
    """AC-2, amtlicher Warnungs-Pfad: `CompareOfficialAlertService` kennt
    bereits einen `telegram_sink`-DI-Seam (kein HTTP-Stub nötig).

    ROT-Grund (gemessen): identisch -- E-Mail ist im heutigen Resolver hart
    verdrahtet, der `alert_channels`-Schalter wird ignoriert."""
    import services.official_alerts.base as official_base
    from app.loader import save_location
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source
    from services.official_alerts.models import OfficialAlert

    uid = _uid("official")
    preset_id = f"cp-{uid}"
    loc_id = "loc-1"
    lat, lon = 47.07, 15.44  # Graz
    _clean_user(uid)
    backup = list(official_base._REGISTERED_SOURCES)
    official_base._REGISTERED_SOURCES.clear()
    try:
        save_location(_location(loc_id, "Graz", lat, lon), user_id=uid)
        write_compare_briefings(
            _data_root_users() / uid, [_preset(preset_id, [loc_id])],
        )

        now = datetime.now(timezone.utc)

        class _FakeOfficialAlertSource:
            name = "test-2279-s1-source"

            def covers(self, source_lat: float, source_lon: float) -> bool:
                return abs(source_lat - lat) < 0.05 and abs(source_lon - lon) < 0.05

            def fetch(self, source_lat: float, source_lon: float):
                return [OfficialAlert(
                    source="test-2279-s1", hazard="extreme_heat", level=2,
                    label="Hitze", valid_from=now - timedelta(hours=1),
                    valid_to=now + timedelta(hours=23), region_label="Graz",
                )]

        register_official_alert_source(_FakeOfficialAlertSource())

        mails: list = []
        tg_calls: list = []
        service = CompareOfficialAlertService(
            settings=_settings_all_channels(), user_id=uid,
            mail_sink=lambda subject, body: mails.append(body),
            telegram_sink=lambda text: tg_calls.append(text),
        )
        sent = service.check_all_compare_presets()

        assert sent == 1, f"Vorbedingung: die Warnung muss ausloesen, gemessen sent={sent}"
        assert mails == [], (
            "AC-2: die Mail-Senke muss bei alert_channels.email=False LEER "
            f"bleiben, gemessen: {mails!r}"
        )
        assert len(tg_calls) == 1, (
            "AC-2: Telegram muss trotzdem GENAU EINE Zustellung bekommen, "
            f"gemessen: {tg_calls!r}"
        )
    finally:
        official_base._REGISTERED_SOURCES.clear()
        official_base._REGISTERED_SOURCES.extend(backup)
        _clean_user(uid)
