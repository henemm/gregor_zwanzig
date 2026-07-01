"""
TDD — Issue #936: SMS-Format-Verifikation via lokalem HTTP-Stub

SPEC: docs/specs/tests/issue_936_sms_stub_server.md

Testet die vollständige Send-Kette render_sms() → SMSOutput.send() gegen einen
lokalen HTTP-Stub-Server. Der Stub empfängt den echten HTTP-POST von SMSOutput.send()
und gibt die gesendeten Daten zurück — ohne externe API-Abhängigkeit.

Kein Mock, kein patch() — echter HTTP-Roundtrip über localhost.
"""
from __future__ import annotations

import http.server
import threading
import urllib.parse

import pytest

from app.config import Settings
from output.renderers.sms import render_sms
from output.tokens.builder import build_token_line
from output.tokens.dto import DailyForecast, HourlyValue, NormalizedForecast
from outputs.sms import SMSOutput


class _SMSStub:
    """Lokaler HTTP-Stub für seven.io SMS API."""

    def __init__(self):
        self.received: list[dict] = []
        self._server: http.server.HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port: int = 0

    def start(self) -> "_SMSStub":
        import socket
        s = socket.socket()
        s.bind(("", 0))
        self.port = s.getsockname()[1]
        s.close()

        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                data = urllib.parse.parse_qs(body.decode())
                received.append({k: v[0] for k, v in data.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):
                pass

        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        if self._server:
            self._server.shutdown()

    def last_text(self) -> str | None:
        if self.received:
            return self.received[-1].get("text")
        return None

    def last_text_matching(self, contains: str) -> str | None:
        """Letzter empfangener text der `contains` enthält (Parallel-Isolation)."""
        for entry in reversed(self.received):
            text = entry.get("text")
            if text is not None and contains in text:
                return text
        return None


def _stub_settings(port: int) -> Settings:
    return Settings().model_copy(update={
        "sms_gateway_url": f"http://127.0.0.1:{port}/api/sms",
        "seven_api_key": "test-stub-key",
        "sms_to": "+49000000000",
        "sms_from": None,
    })


def _token_line_with_km_stage():
    """Synthetischer NormalizedForecast mit Stage-Name der km enthält."""
    today = DailyForecast(
        temp_min_c=8.0, temp_max_c=15.0,
        wind_hourly=(HourlyValue(11, 55.0),),
        gust_hourly=(HourlyValue(11, 70.0),),
        rain_hourly=(HourlyValue(10, 8.0),),
        pop_hourly=(HourlyValue(10, 60.0),),
    )
    return build_token_line(
        NormalizedForecast(days=(today,)),
        None,
        report_type="evening",
        stage_name="GR221 Mallorca km0-11",
    )


# ---------------------------------------------------------------------------
# AC-1 + AC-2: Echter HTTP-Roundtrip — SMS landet im Stub
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_sms_send_appears_in_stub():
    """
    AC-1: Given lokaler Stub-Server läuft
    When SMSOutput(settings).send() aufgerufen wird
    Then empfängt der Stub einen POST mit dem erwarteten text-Feld

    AC-2: Given Stub-Eintrag gefunden
    When text ausgelesen wird
    Then ist er nicht leer und identisch mit dem render_sms()-Rückgabewert
    """
    stub = _SMSStub().start()
    try:
        token_line = _token_line_with_km_stage()
        expected = render_sms(token_line)

        SMSOutput(_stub_settings(stub.port)).send("", expected)

        text = stub.last_text()
        assert text is not None, (
            f"Stub hat keinen POST empfangen — SMSOutput.send() hat möglicherweise "
            f"einen Fehler geworfen. Erwartet: {expected!r}"
        )
        assert text == expected, (
            f"Stub-Text weicht von render_sms()-Output ab: {text!r} != {expected!r}"
        )
    finally:
        stub.stop()


# ---------------------------------------------------------------------------
# AC-3: text-Feld <= 140 Zeichen
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_sms_text_length():
    """
    AC-3: Given render_sms() produziert String
    When Länge gemessen wird
    Then ist len(text) <= 140 für den Testdatensatz
    """
    stub = _SMSStub().start()
    try:
        token_line = _token_line_with_km_stage()
        expected = render_sms(token_line)

        SMSOutput(_stub_settings(stub.port)).send("", expected)

        text = stub.last_text()
        assert text is not None, "Stub hat keinen POST empfangen"
        assert len(text) <= 140, (
            f"SMS-Text zu lang: {len(text)} Zeichen (max 140). Text: {text!r}"
        )
    finally:
        stub.stop()


# ---------------------------------------------------------------------------
# AC-4: Kein ( im Stage-Name-Anteil vor km
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_sms_stage_name_no_parens():
    """
    AC-4: Given Stub-text mit stage_name 'GR221 Mallorca km0-11'
    When Anteil vor erstem km isoliert wird
    Then enthält er kein (-Zeichen
    """
    stub = _SMSStub().start()
    try:
        token_line = _token_line_with_km_stage()
        expected = render_sms(token_line)

        SMSOutput(_stub_settings(stub.port)).send("", expected)

        text = stub.last_text()
        assert text is not None, "Stub hat keinen POST empfangen"

        before_km = text.split("km")[0].rstrip()
        assert "(" not in before_km, (
            f"Unerwartete öffnende Klammer im Stage-Name-Anteil vor 'km': {before_km!r}"
        )
    finally:
        stub.stop()


# ---------------------------------------------------------------------------
# AC-5: km-Format korrekt (km0-11: nicht km 0 oder km-11:)
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_sms_km_format():
    """
    AC-5: Given Stub-text mit stage_name 'GR221 Mallorca km0-11'
    When nach km-Bereichsformat gesucht wird
    Then enthält text 'km0-11:' (Bindestrich, kein Leerzeichen, Doppelpunkt direkt)
    """
    stub = _SMSStub().start()
    try:
        token_line = _token_line_with_km_stage()
        expected = render_sms(token_line)

        SMSOutput(_stub_settings(stub.port)).send("", expected)

        text = stub.last_text()
        assert text is not None, "Stub hat keinen POST empfangen"
        assert "km0-11:" in text, (
            f"km-Format falsch — erwartet 'km0-11:' (Bindestrich+Doppelpunkt direkt). "
            f"Tatsächlicher Text: {text!r}"
        )
    finally:
        stub.stop()


# ---------------------------------------------------------------------------
# AC-6: SMSOutput.send() verändert den Text nicht
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_sms_send_does_not_transform_text():
    """
    AC-6: Given render_sms() erzeugt String S
    When SMSOutput.send() S an Stub schickt
    Then ist Stub-text byte-identisch mit S
    """
    stub = _SMSStub().start()
    try:
        token_line = _token_line_with_km_stage()
        expected = render_sms(token_line)

        SMSOutput(_stub_settings(stub.port)).send("", expected)

        text = stub.last_text()
        assert text is not None, "Stub hat keinen POST empfangen"
        assert text == expected, (
            f"SMSOutput.send() hat den Text verändert!\n"
            f"  render_sms(): {expected!r}\n"
            f"  Stub:         {text!r}"
        )
    finally:
        stub.stop()


# ---------------------------------------------------------------------------
# Issue #945: Extremwetter — Render-Länge bleibt <= 140 Zeichen
# ---------------------------------------------------------------------------

def _token_line_extreme_weather():
    """NormalizedForecast mit Wetterwerten an den Extremen (Sturm, Starkregen,
    Schnee, Temperaturextreme) — Stresstest für die 140-Zeichen-Grenze."""
    today = DailyForecast(
        temp_min_c=-38.0, temp_max_c=47.0,
        rain_hourly=(HourlyValue(6, 88.5), HourlyValue(16, 120.9)),
        pop_hourly=(HourlyValue(11, 100.0), HourlyValue(17, 100.0)),
        wind_hourly=(HourlyValue(11, 99.0), HourlyValue(15, 110.0)),
        gust_hourly=(HourlyValue(11, 130.0), HourlyValue(15, 165.0)),
        thunder_hourly=(HourlyValue(16, 3),),
        snow_depth_cm=420.0,
        snow_new_24h_cm=95.0,
        snowfall_limit_m=0.0,
        avalanche_level=5,
        wind_chill_c=-55.0,
    )
    tomorrow = DailyForecast(thunder_hourly=(HourlyValue(14, 3),))
    return build_token_line(
        NormalizedForecast(days=(today, tomorrow)),
        None,
        report_type="evening",
        stage_name="Extremwetter km0-42",
    )


@pytest.mark.live
def test_sms_text_length_extreme_weather():
    """
    Issue #945: Given Extremwetter (max Regen/Böen/Temperatur/Schnee)
    When render_sms() den TokenLine rendert
    Then bleibt der Text <= 140 Zeichen (SMS-Grenze).
    """
    token_line = _token_line_extreme_weather()
    text = render_sms(token_line, max_length=140)
    assert len(text) <= 140, (
        f"Extremwetter-SMS zu lang: {len(text)} Zeichen (max 140). Text: {text!r}"
    )


# ---------------------------------------------------------------------------
# Issue #945: Morning-Report — km-Format wie beim Abend-Report
# ---------------------------------------------------------------------------

def _token_line_with_km_stage_morning():
    """Wie _token_line_with_km_stage(), aber report_type='morning'."""
    today = DailyForecast(
        temp_min_c=8.0, temp_max_c=15.0,
        wind_hourly=(HourlyValue(11, 55.0),),
        gust_hourly=(HourlyValue(11, 70.0),),
        rain_hourly=(HourlyValue(10, 8.0),),
        pop_hourly=(HourlyValue(10, 60.0),),
    )
    return build_token_line(
        NormalizedForecast(days=(today,)),
        None,
        report_type="morning",
        stage_name="GR221 Mallorca km0-11",
    )


@pytest.mark.live
def test_sms_morning_report_km_format():
    """
    Issue #945: Given morning-Report mit stage_name 'GR221 Mallorca km0-11'
    When SMS gesendet wird
    Then enthält der Stub-Text 'km0-11:' (identisches km-Format wie evening).
    """
    stub = _SMSStub().start()
    try:
        token_line = _token_line_with_km_stage_morning()
        expected = render_sms(token_line)

        SMSOutput(_stub_settings(stub.port)).send("", expected)

        text = stub.last_text_matching("km0-11:")
        assert text is not None, (
            f"Stub hat keinen POST mit 'km0-11:' empfangen. Erwartet: {expected!r}"
        )
        assert "km0-11:" in text, (
            f"km-Format im morning-Report falsch — erwartet 'km0-11:'. Text: {text!r}"
        )
    finally:
        stub.stop()
