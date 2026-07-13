"""Telegram-Auszeichnung: HTML-Escaping + parse_mode="HTML" — Issue #1252.

SPEC: docs/specs/modules/fix_1252_1253_kanal_text.md (AC-1, AC-2)
KONTEXT: docs/context/fix-1252-1253-kanal-text-v2.md
ADR: docs/adr/0012-telegram-parse-mode-html.md (bindend)

RED-Phase:
- Die Warn-ZEILEN und `source_label` von `render_official_alert_telegram`
  sind heute NICHT escaped (nur die Kopfzeile, official_alerts.py:1361) ->
  ein `&`/`<` im Ortsnamen/Behoerden-Label steht wortwoertlich im HTML-Text.
- `notification_service.py:538` (Standalone-Alert) und `:658`
  (Compare-Alert) senden ohne `parse_mode` -> das Bot-API-Payload traegt es
  nicht.
- `TelegramOutput.send()` kennt keinen 400-Fallback -> eine Warnung mit
  unescaptem Sonderzeichen im Upstream-Feed wird bei `parse_mode="HTML"`
  durch die Bot-API mit 400 abgelehnt und geht als `OutputError` verloren
  (stiller Totalausfall, das eigentliche Sicherheitsrisiko dieses Fixes).

Mock-frei: echte `OfficialAlert`/`OfficialAlertNotice`-DTOs, echte Renderer,
echter Trip/echte Compare-Locations, echter lokaler HTTP-Stub-Server fuer die
Telegram-Bot-API (Vorbild `tests/tdd/test_952_onset_alert_fidelity.py`,
`fake_telegram_bot`-Fixture) mit `monkeypatch.setattr(telegram_mod,
"TELEGRAM_API_BASE", ...)` -- laut Projekt-Konvention KEIN Mock, sondern ein
erlaubtes Boundary-Umlenken auf einen echten lokalen HTTP-Server (#645/#650).
KEIN `Mock()`/`patch()`/`MagicMock`.
"""
from __future__ import annotations

import json
import threading
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.config import Settings
from output.channels import telegram as telegram_mod
from output.channels.telegram import TelegramOutput
from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
FR_FROM = datetime(2026, 7, 10, 6, 0, tzinfo=UTC)
FR_TO = datetime(2026, 7, 10, 20, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Lokaler Fake-Bot-Server (Vorbild #650/#952) — echter HTTP-Roundtrip, kein Mock.
# ---------------------------------------------------------------------------


class _FakeTelegramState:
    def __init__(self) -> None:
        self.last_payload: dict | None = None
        self.requests: list[dict] = []
        # Status-Codes, die der Reihe nach beantwortet werden (von links
        # konsumiert); danach faellt der Handler auf 200 zurueck.
        self.status_sequence: list[int] = []

    def next_status(self) -> int:
        if self.status_sequence:
            return self.status_sequence.pop(0)
        return 200


def _make_fake_bot_handler(state: _FakeTelegramState):
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw or b"{}")
            state.last_payload = payload
            state.requests.append(payload)
            status = state.next_status()
            if status == 400:
                body = json.dumps({
                    "ok": False, "error_code": 400,
                    "description": "Bad Request: can't parse entities",
                }).encode()
                self.send_response(400)
            else:
                body = json.dumps({"ok": True, "result": {"message_id": 1}}).encode()
                self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return _Handler


@pytest.fixture
def fake_telegram_bot(monkeypatch):
    """Lokaler Real-HTTP-Server + `TELEGRAM_API_BASE`-Umlenkung (Vorbild #650/#952)."""
    state = _FakeTelegramState()
    server = HTTPServer(("127.0.0.1", 0), _make_fake_bot_handler(state))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(telegram_mod, "TELEGRAM_API_BASE", f"http://127.0.0.1:{port}")
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()


_TELEGRAM_SETTINGS = Settings(telegram_bot_token="test-token-1252", telegram_chat_id="99999")


def _alert(level, hazard, label, vf=FR_FROM, vt=FR_TO, *, region="Var",
           source="geosphere_warn") -> OfficialAlert:
    return OfficialAlert(
        source=source, hazard=hazard, level=level, label=label,
        valid_from=vf, valid_to=vt, region_label=region,
    )


def _notice(alert, scope_label, sms_scope="x"):
    from output.renderers.alert.official_alerts import OfficialAlertNotice
    return OfficialAlertNotice(
        alert=alert, scope_label=scope_label, sms_scope=sms_scope,
        affected_chips=[scope_label], free_chips=[],
    )


# ---------------------------------------------------------------------------
# AC-2 — Escaping der Warnungszeilen + source_label (heute nur die Kopfzeile)
# ---------------------------------------------------------------------------


def test_telegram_notice_lines_escape_ampersand_and_angle_brackets():
    """AC-2: Given amtliche Warnungen, deren Umfang/Label/Quelle `&` bzw.
    `<`/`>` enthalten / When `render_official_alert_telegram` rendert / Then
    sind diese Zeichen als `&amp;`/`&lt;`/`&gt;` escaped -- nicht nur in der
    (bereits escapten) Kopfzeile, sondern auch in den Warnungszeilen
    (`_display_label`, `scope_label`) UND im `source_label`
    (official_alerts.py:1362-1369)."""
    from output.renderers.alert.official_alerts import render_official_alert_telegram

    # Zwei Notices mit UNGLEICHEM Umfang -> uniform_scope=False -> der Umfang
    # steht in den Zeilen (nicht in der ohnehin schon escapten Kopfzeile).
    n1 = _notice(
        _alert(3, "access_ban", "Zugang eingeschränkt — Zone A & B"),
        scope_label="Zone A & B",
    )
    n2 = _notice(
        _alert(2, "extreme_heat", "Hitze"),
        scope_label="Zone C",
    )
    text = render_official_alert_telegram(
        [n1, n2], prefix="GZ", source_label="Präfektur <Test>", tz=UTC,
    )

    assert "&amp;" in text, f"'&' im Warnungs-Umfang/-Label nicht escaped: {text!r}"
    assert "Zone A & B" not in text, (
        f"Rohes, unescaptes '&' im Telegram-Text (Bot-API-400-Risiko): {text!r}"
    )
    assert "&lt;Test&gt;" in text, f"'<'/'>' im source_label nicht escaped: {text!r}"
    assert "<Test>" not in text, (
        f"Rohes HTML-fremdes Tag im Telegram-Text (Bot-API-400-Risiko): {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-1/AC-2 — notification_service.py:538 (Standalone) nutzt parse_mode="HTML"
# ---------------------------------------------------------------------------


def _trip_with_ampersand():
    from app.trip import Stage, Trip, Waypoint

    stage = Stage(
        id="s1", name="Tag 1", date=date(2026, 7, 10),
        waypoints=[Waypoint(id="w1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    return Trip(id="tdd-1252-trip", name="Zone A & B", stages=[stage])


def test_standalone_alert_sends_with_html_parse_mode(fake_telegram_bot):
    """AC-1/AC-2: Given ein Standalone-Trip-Alert mit `&` im Trip-Namen/Label
    / When `NotificationService.send_official_alert` telegram versendet
    (notification_service.py:538) / Then setzt der TATSAECHLICH gebaute
    Bot-API-Payload `parse_mode='HTML'`, und der Text ist escaped."""
    from services.notification_service import NotificationService

    trip = _trip_with_ampersand()
    notices = [(_alert(3, "access_ban", "Zugang eingeschränkt — Zone A & B"), ["1"])]
    svc = NotificationService(_TELEGRAM_SETTINGS, "tdd-1252-standalone")

    svc.send_official_alert(
        trip=trip, notices=notices, effective_channels={"telegram"},
        mail_sink=lambda **_kw: None, sms_sink=lambda _t: None,
    )

    payload = fake_telegram_bot.last_payload
    assert payload is not None, "Kein sendMessage-Request beim Bot-Stub angekommen"
    assert payload.get("parse_mode") == "HTML", (
        f"Standalone-Alert (notification_service.py:538) setzt kein "
        f"parse_mode='HTML': {payload!r}"
    )
    assert "&amp;" in payload["text"], (
        f"'&' im Trip-Namen/Label nicht escaped im gesendeten Payload: {payload!r}"
    )


def test_compare_alert_sends_with_html_parse_mode(fake_telegram_bot):
    """AC-1/AC-2: Given ein Compare-Alert (Ortsvergleich) mit `&` im
    Ortsnamen/Label / When `NotificationService.send_multi_location_official_
    alert` telegram versendet (notification_service.py:658) / Then setzt der
    TATSAECHLICH gebaute Bot-API-Payload `parse_mode='HTML'`, und der Text
    ist escaped."""
    from services.notification_service import NotificationService

    class _Loc:
        def __init__(self, id_, name, lat, lon):
            self.id, self.name, self.lat, self.lon = id_, name, lat, lon

    locations = [_Loc("a", "Zone A & B", 43.1, 5.9)]
    tagged = [(_alert(3, "access_ban", "Zugang eingeschränkt — Zone A & B"), ["a"])]
    svc = NotificationService(_TELEGRAM_SETTINGS, "tdd-1252-compare")

    svc.send_multi_location_official_alert(
        preset_name="Le Var", locations=locations, tagged_alerts=tagged,
        effective_channels={"telegram"},
        mail_sink=lambda **_kw: None, sms_sink=lambda _t: None,
    )

    payload = fake_telegram_bot.last_payload
    assert payload is not None, "Kein sendMessage-Request beim Bot-Stub angekommen"
    assert payload.get("parse_mode") == "HTML", (
        f"Compare-Alert (notification_service.py:658) setzt kein "
        f"parse_mode='HTML': {payload!r}"
    )
    assert "&amp;" in payload["text"], (
        f"'&' im Ortsnamen/Label nicht escaped im gesendeten Payload: {payload!r}"
    )


# ---------------------------------------------------------------------------
# AC-1 (Kernkriterium) — 400-Fallback rettet die Zustellung
# ---------------------------------------------------------------------------


def test_send_falls_back_without_parse_mode_on_400_and_delivers(fake_telegram_bot):
    """AC-1: Given ein lokaler HTTP-Stub antwortet auf den ERSTEN Sendeversuch
    mit `parse_mode='HTML'` mit Status 400 (z.B. weil der Upstream-Feed ein
    Sonderzeichen enthielt, das die Escaping-Stufe nicht abfaengt) / When
    `TelegramOutput.send()` erneut sendet / Then wird OHNE `parse_mode` und
    mit gestrippten + `html.unescape()`-ten Tags nachgesendet, UND die
    Warnung kommt an (kein `OutputError`, kein stiller Totalausfall) --
    dasselbe kosmetische Problem (`&amp;` statt `&`) darf beim Fallback nicht
    neu entstehen."""
    fake_telegram_bot.status_sequence = [400]
    output = TelegramOutput(_TELEGRAM_SETTINGS)

    message_id = output.send(
        "Betreff", "<b>Zone A &amp; B</b>",
        parse_mode="HTML", suppress_subject_line=True,
    )

    assert message_id is not None, (
        "send() hat die Warnung trotz 400-Fallback nicht zugestellt -- "
        "genau der stille Totalausfall, den AC-1 verhindern soll"
    )
    assert len(fake_telegram_bot.requests) == 2, (
        f"Erwartet genau 2 Versuche (erst HTML, dann Fallback ohne "
        f"parse_mode): {len(fake_telegram_bot.requests)} — "
        f"{fake_telegram_bot.requests!r}"
    )
    first, second = fake_telegram_bot.requests
    assert first.get("parse_mode") == "HTML", f"Erster Versuch ohne parse_mode: {first!r}"
    assert "parse_mode" not in second, (
        f"Fallback-Versuch darf kein parse_mode mehr setzen: {second!r}"
    )
    assert "<b>" not in second["text"], (
        f"Fallback-Text enthaelt noch HTML-Tags (nicht gestrippt): {second!r}"
    )
    assert second["text"] == "Zone A & B", (
        f"Fallback muss Tags strippen UND html.unescape() anwenden (sonst "
        f"'&amp;' statt '&' -- ein kosmetischer Fehler gegen einen anderen "
        f"getauscht): {second!r}"
    )
