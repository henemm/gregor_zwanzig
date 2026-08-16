"""TDD RED — Issue #1914: Radar-Alarm folgt dem konfigurierten Telegram-Stil
(Ortsvergleich-Pfad).

Deckt AC-3/AC-4 der Spec `docs/specs/modules/fix_1914_radar_telegram_style.md`
ab: `CompareRadarAlertService.check_all_compare_presets()` ->
`send_multi_location_radar_alert()` reicht heute `telegram_style` NICHT
durch — die Telegram-Nachricht eines Multi-Location-Radar-Alarms kommt
deshalb immer im reichen HTML-Format an, auch wenn
`preset["display_config"]["telegram_style"] == "kurzform"` gesetzt ist.

Pflicht (Lehre #1467): der Test laeuft ueber die tatsaechliche Aufrufstelle
(`CompareRadarAlertService.check_all_compare_presets()`), NICHT nur direkt
gegen `NotificationService.send_multi_location_radar_alert(telegram_style=
...)` — sonst beweist er nur den Baustein, nicht die Verdrahtung ueber
`compare_radar_alert.py`.

RED-Ursache: der `send_multi_location_radar_alert()`-Aufruf in
`compare_radar_alert.py::_check_one_preset()` kennt `telegram_style` noch
nicht (AC-3 schlaegt fehl: die Telegram-Nachricht kommt trotz `"kurzform"`
als reiche HTML-Bubble an). AC-4 ist der Regressionsschutz fuer den
unveraenderten Bestandsfall (rich/Default) und darf bereits heute gruen sein.

Fixtures/Helfer (Vorbild `test_compare_radar_alert.py`): echte Preset-/
Locations-Dateien unter `data/users/<user_id>/` (eindeutige tdd-1914-*-IDs,
Cleanup per try/finally), echter `frame_source`-DI-Seam von
`RadarNowcastService` (`radar_service.py:84-89`, kein Mock der
Provider-Kette). Telegram wird ueber einen echten lokalen HTTP-Stub
beobachtet (Vorbild `test_telegram_kurzstil_trip_alert.py::_TelegramStub`,
`monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE", ...)`) — kein
`Mock()`/`patch()` des Verhaltens selbst.

SPEC: docs/specs/modules/fix_1914_radar_telegram_style.md
"""
from __future__ import annotations

import http.server
import json
import shutil
import socket
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings
from app.loader import save_location
from app.user import SavedLocation

import output.channels.telegram as tg_module

from tests.helpers.compare_briefings import write_compare_briefings


def _data_root_users() -> Path:
    """Funktion statt Konstante (#1595) — Vorbild
    `test_compare_radar_alert.py::_data_root_users`."""
    from app.loader import get_data_root

    return get_data_root() / "users"


def _clean_user(user_id: str) -> None:
    d = _data_root_users() / user_id
    if d.exists():
        shutil.rmtree(d)


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _radar_preset(
    preset_id: str, location_ids: list[str], empfaenger: list[str], *,
    telegram_style: str,
) -> dict:
    """Direktes Compare-Preset-Dict (Vorbild
    `test_compare_radar_alert.py::_radar_preset`), zusaetzlich mit
    `send_telegram=True` + `display_config.telegram_style` — genau die zwei
    Felder, die `effective_compare_channels()`/`effective_compare_telegram_
    style()` fuer diesen Test auswerten."""
    return {
        "id": preset_id,
        "name": preset_id,
        "user_id": "default",
        "location_ids": location_ids,
        # Issue #1467 S2 AG6: aktiver Zeitplan noetig, sonst gilt das Preset
        # als pausiert und schweigt in allen Alarm-Pfaden.
        "schedule": "daily",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": empfaenger,
        "letzter_versand": None,
        "top_ort_letzter_versand": None,
        "created_at": "2026-07-10T00:00:00Z",
        "radar_alert_enabled": True,
        "send_telegram": True,
        "display_config": {"telegram_style": telegram_style},
    }


def _write_preset_file(user_id: str, presets: list[dict]) -> Path:
    return write_compare_briefings(_data_root_users() / user_id, presets)


def _wet_frame(onset_minutes: int, *, is_convective: bool = False, rate: float = 0.6) -> list:
    """Ein einzelner nasser `RadarFrame` `onset_minutes` in der Zukunft —
    echtes DTO (kein Mock), Vorbild `test_compare_radar_alert.py::_wet_frame`."""
    from providers.brightsky import RadarFrame

    ts = datetime.now(timezone.utc) + timedelta(minutes=onset_minutes)
    return [RadarFrame(timestamp=ts, precip_mm_h=rate, is_convective=is_convective)]


class _CoordFrameSource:
    """Echter (kein `Mock()`/`patch()`), aufrufbarer `frame_source`-
    Doppelgaenger fuer `RadarNowcastService(frame_source=...)` — liefert je
    nach (lat, lon) einen vorab festgelegten `RadarFrame`-Satz."""

    def __init__(self, by_coord: dict[tuple[float, float], list]) -> None:
        self._by_coord = by_coord

    def __call__(self, lat: float, lon: float) -> list:
        return self._by_coord.get((round(lat, 4), round(lon, 4)), [])


# ---------------------------------------------------------------------------
# Echter lokaler Telegram-Bot-API-Stub (kein Mock) — Vorbild
# test_telegram_kurzstil_trip_alert.py::_TelegramStub.
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
        counter = {"mid": 4000}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body.decode())
                except ValueError:
                    payload = {}
                sent.append(payload)
                counter["mid"] += 1
                resp = json.dumps(
                    {"ok": True, "result": {"message_id": counter["mid"]}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        self._server.shutdown()


def _telegram_only_settings() -> Settings:
    """Nur Telegram sendebereit — `effective_compare_channels()` nimmt zwar
    immer `"email"` auf, aber ohne SMTP-Konfiguration schlaegt der E-Mail-
    Versuch lediglich fehl (Best-Effort, `_log_error`) und beeinflusst die
    Telegram-Assertions nicht.

    `telegram_test_chat_id` ist BEWUSST identisch zu `telegram_chat_id`
    gesetzt: die Herkunftssperre (`TelegramOutput._guard_code_origin()`,
    Issue #1476, `src/app/origin_guard.py`) verlangt aus jedem
    Nicht-Prod-/Staging-Checkout eine konfigurierte Test-Chat-ID, sonst
    `OutputConfigError` VOR jedem HTTP-Request. Ohne dieses Feld lief der
    Test nur lokal (per zufaelligem `.env`-Wert), nicht auf dem
    GitHub-Actions-Runner (kein `.env`) -- die Guard-Ausnahme verschwand
    silent im breiten `except Exception` von `_dispatch_alert_message()`."""
    return Settings().model_copy(update={
        "smtp_host": None, "smtp_user": None, "smtp_pass": None, "mail_to": None,
        "telegram_bot_token": "test-token-1914-cmp", "telegram_chat_id": "99999",
        "telegram_test_chat_id": "99999",
        "sms_gateway_url": None, "seven_api_key": None, "sms_to": None,
    })


# ===========================================================================
# AC-3: display_config.telegram_style="kurzform" -> Kurzstil-Telegram
# ===========================================================================


class TestAC3CompareRadarAlertTelegramKurzstil:
    def test_kurzform_compare_radar_path_sends_plaintext_no_parse_mode(self, monkeypatch) -> None:
        """RED: `check_all_compare_presets()` reicht `telegram_style` noch
        nicht bis zu `send_multi_location_radar_alert()`/
        `_dispatch_alert_message()` durch — die Telegram-Nachricht kommt
        trotz `"kurzform"` als reiche HTML-Bubble (parse_mode="HTML") an."""
        from services.compare_radar_alert import CompareRadarAlertService
        from services.radar_service import RadarNowcastService

        uid = "tdd-1914-cmp-ac3"
        _clean_user(uid)
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)

            loc = _location("loc-a", "Zermatt-Kurzstil", 46.0207, 7.7491)
            save_location(loc, user_id=uid)
            preset_id = "cp-1914-ac3"
            _write_preset_file(uid, [
                _radar_preset(
                    preset_id, ["loc-a"], ["gregor-test@henemm.com"],
                    telegram_style="kurzform",
                ),
            ])

            frame_source = _CoordFrameSource({(46.0207, 7.7491): _wet_frame(8)})
            radar_service = RadarNowcastService(frame_source=frame_source)

            service = CompareRadarAlertService(
                settings=_telegram_only_settings(), user_id=uid,
                radar_service=radar_service,
            )
            sent = service.check_all_compare_presets()

            assert sent == 1, f"Erwartete genau 1 Alarm-Lauf, erhalten: {sent}"
            assert len(tg_stub.sent) == 1, (
                f"Erwartete genau 1 Telegram-Nachricht, erhalten: {len(tg_stub.sent)}"
            )
            payload = tg_stub.sent[0]
            assert "parse_mode" not in payload, (
                "RED: Kurzstil-Redirect muss parse_mode=None nutzen (kein "
                f"Schluessel im Payload); gefunden parse_mode="
                f"{payload.get('parse_mode')!r} — die Verdrahtung von "
                "telegram_style durch check_all_compare_presets() -> "
                "send_multi_location_radar_alert() -> _dispatch_alert_message() "
                "fehlt noch."
            )
            assert "reply_markup" not in payload, (
                "RED: Kurzstil darf keine Inline-Knoepfe (reply_markup) senden."
            )
            assert "<b>" not in (payload.get("text") or ""), (
                "RED: Kurzstil-Body enthaelt HTML-Tags — es ist noch die reiche "
                f"Telegram-Radar-Warnung: {payload.get('text')!r}"
            )
        finally:
            tg_stub.stop()
            _clean_user(uid)


# ===========================================================================
# AC-4: display_config.telegram_style="rich"/Default -> Regressionsschutz
# ===========================================================================


class TestAC4CompareRadarAlertTelegramRichRegression:
    def test_rich_compare_radar_path_still_sends_html(self, monkeypatch) -> None:
        """Regressionsschutz — darf bereits vor der Implementierung gruen
        sein: der heutige (fehlerhafte) Default-Pfad rendert IMMER rich."""
        from services.compare_radar_alert import CompareRadarAlertService
        from services.radar_service import RadarNowcastService

        uid = "tdd-1914-cmp-ac4"
        _clean_user(uid)
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)

            loc = _location("loc-b", "Zermatt-Rich", 46.0207, 7.7491)
            save_location(loc, user_id=uid)
            preset_id = "cp-1914-ac4"
            _write_preset_file(uid, [
                _radar_preset(
                    preset_id, ["loc-b"], ["gregor-test@henemm.com"],
                    telegram_style="rich",
                ),
            ])

            frame_source = _CoordFrameSource({(46.0207, 7.7491): _wet_frame(8)})
            radar_service = RadarNowcastService(frame_source=frame_source)

            service = CompareRadarAlertService(
                settings=_telegram_only_settings(), user_id=uid,
                radar_service=radar_service,
            )
            sent = service.check_all_compare_presets()

            assert sent == 1, f"Erwartete genau 1 Alarm-Lauf, erhalten: {sent}"
            assert len(tg_stub.sent) == 1
            assert tg_stub.sent[0].get("parse_mode") == "HTML", (
                "Regression: rich/Default muss den reichen HTML-Compare-Radar-"
                f"Alarm unveraendert senden; gefunden parse_mode="
                f"{tg_stub.sent[0].get('parse_mode')!r}."
            )
        finally:
            tg_stub.stop()
            _clean_user(uid)
