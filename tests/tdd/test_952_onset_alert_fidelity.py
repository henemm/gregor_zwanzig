"""TDD RED — Issue #952 (reopened): Onset-/Radar-Alert-Fidelity.

Bringt den Onset-Zweig (`source is not None`) des kanonischen Alert-Renderers
(`src/output/renderers/alert/render.py`) auf dieselbe Design-Fidelity wie der
Deviation-Zweig (bereits #952/#957-fidelity-konform), behebt km-Float-Rauschen,
das doppelte/verirrte Intensitäts-Label, aktiviert SMS im Radar-Pfad
(`check_radar_alerts`) und macht `TelegramOutput.send()` HTML-bold-fähig.

Modell-Erweiterung, die diese RED-Tests voraussetzen (Spec nennt keinen
Feldnamen, s. "Known Limitations" / Open Questions):
`OnsetEvent.briefing_context: str | None = None` — trägt den kurzen Text für
die vierte Datenblock-Zeile "Briefing" (z.B. "nicht angekündigt" /
"bereits angekündigt"), NUR von der E-Mail gerendert. GREEN-Phase MUSS diesen
Feldnamen übernehmen (oder diesen Test entsprechend anpassen).

Mock-frei: echte Dataclass-Konstruktion, echte Renderer-Aufrufe, echte lokale
HTTP-Stub-Server (Telegram/seven.io, Vorbild #650/#914/#936),
`monkeypatch.setattr` auf die Modul-Konstante `TELEGRAM_API_BASE` ist erlaubt
(kein Mock, etabliertes Muster #645/#650) — echter DI-Seam-Trip-Alert-Service
(`radar_service=`, `mail_sink=`) für die Dispatch-Tests, echter
FastAPI-TestClient für AC-7. KEIN Mock()/patch()/MagicMock.

SPEC: docs/specs/modules/issue_952_onset_alert_fidelity.md
"""
from __future__ import annotations

import json
import re
import threading
from datetime import date as date_type
from datetime import datetime, timedelta
from datetime import time as time_type
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from app.config import Settings
from app.models import TripReportConfig
from app.trip import Stage, TimeWindow, Trip, Waypoint
from utils.timezone import tz_for_coords
from output.renderers.alert.model import AlertEvent, AlertMessage, OnsetEvent
from output.renderers.alert.render import (
    render_email, render_subject, render_sms, render_telegram,
)
from output.channels import telegram as telegram_mod
from output.channels.telegram import TelegramOutput
from services.radar_service import NowcastResult, RadarNowcastService

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

KM_RE = re.compile(r"km\s?\d+[–-]\d+")


# ---------------------------------------------------------------------------
# Helpers (mock-frei)
# ---------------------------------------------------------------------------


_UNSET = object()  # Sentinel: briefing_context standardmässig NICHT übergeben.


def _onset_msg(
    *, onset_minutes: int = 12, onset_time: str = "14:35",
    km_from: float = 9.8, km_to: float = 15.200000000000001,
    is_convective: bool = False, intensity_label: str = "leichter Regen",
    source_label: str = "Radar (DWD)", cooldown_display: str | None = "2 Stunden",
    briefing_context: str | None = _UNSET,
) -> AlertMessage:
    """Konstruiert eine Onset-`AlertMessage` direkt (ohne Service-Pfad).

    `briefing_context` (neues Feld dieser Spec, s. Modulkopf) wird NUR
    übergeben, wenn ein Aufrufer ihn explizit setzt — Default `_UNSET` heisst
    "Feld weglassen", damit Tests, die NICHT vom Briefing-Feld handeln (AC-2/
    AC-4/AC-8/AC-3/AC-6), unabhängig vom Modell-Erweiterungs-Stand grün werden
    können. Nur der dedizierte AC-1-Briefing-Test übergibt es explizit und
    schlägt heute mit TypeError fehl (gewolltes RED).
    """
    kwargs = dict(
        onset_minutes=onset_minutes, onset_time=onset_time,
        km_from=km_from, km_to=km_to, is_convective=is_convective,
        intensity_label=intensity_label, source_label=source_label,
    )
    if briefing_context is not _UNSET:
        kwargs["briefing_context"] = briefing_context
    onset = OnsetEvent(**kwargs)
    return AlertMessage(
        trip_short="GR20", stand_at="14:23", events=(onset,),
        source=source_label, cooldown_display=cooldown_display,
    )


def _deviation_msg() -> AlertMessage:
    event = AlertEvent(
        metric_id="cape", value_from=1230.0, value_to=620.0,
        threshold=800.0, cmp="über", occurred_at="09:00",
        km_from=0.0, km_to=1.8,
    )
    return AlertMessage(trip_short="KHW 403", stand_at="09:30", events=(event,), source=None)


class _GuaranteedWetRadar(RadarNowcastService):
    """Echte `RadarNowcastService`-Subklasse (DI-Seam) — garantiert-nasses
    Ergebnis. Kein Mock: `get_nowcast()` wird real überschrieben, damit der
    Rest von `check_radar_alerts` unverändert real durchläuft."""

    def __init__(
        self, *, onset_minutes: int = 12, intensity_label: str = "leichter Regen",
        is_convective: bool = False, source: str = "radar",
    ) -> None:
        super().__init__()
        self._fixed = NowcastResult(
            onset_minutes=onset_minutes, intensity_label=intensity_label,
            source=source, is_convective=is_convective,
        )

    def get_nowcast(self, lat: float, lon: float) -> NowcastResult:
        return self._fixed


def _active_window(lat: float, lon: float) -> tuple[str, str, time_type]:
    """Lokales Zeitfenster, das jetzt aktiv ist und den UTC-Tag nicht verlässt.

    Issue #1015: `time_window` wird von `convert_trip_to_segments` ignoriert;
    ohne `arrival_override` entstand ein Segment, das zur Testlaufzeit oft nicht
    aktiv war. Ein now()-basiertes Fenster (typisch 02:00–22:00 Ortszeit)
    bleibt bei Korsika/UTC+2 vollständig im selben UTC-Tag.
    """
    tz = tz_for_coords(lat, lon)
    now_local = datetime.now(tz)
    start = now_local - timedelta(hours=1)
    end = now_local + timedelta(hours=3)
    day_start = now_local.replace(hour=2, minute=0, second=0, microsecond=0)
    day_end = now_local.replace(hour=22, minute=0, second=0, microsecond=0)
    if start < day_start:
        start = day_start
    if end > day_end:
        end = day_end
    if start > now_local:
        start = now_local
    if end <= now_local:
        end = now_local + timedelta(hours=1)
    return start.strftime("%H:%M"), end.strftime("%H:%M"), time_type(start.hour, start.minute)


def _trip_with_active_segment(trip_id: str, config: TripReportConfig) -> Trip:
    """Trip mit garantiert aktivem Segment JETZT.

    `convert_trip_to_segments` (Issue #822) braucht MINDESTENS 2 Waypoints pro
    Stage (bei 1 Waypoint: "less than 2 waypoints" → leere Segmentliste, kein
    Alert möglich). `arrival_override` auf erstem/letztem Waypoint plus
    passende `stage.start_time` sorgt dafür, dass das Segment zur
    Testlaufzeit aktiv ist (`seg.start_time <= now_utc <= seg.end_time`).
    """
    lat, lon = 42.20, 9.10
    start_str, end_str, start_time = _active_window(lat, lon)
    wp0 = Waypoint(
        id="G1", name="Start", lat=lat, lon=lon, elevation_m=1000.0,
        time_window=TimeWindow(start=time_type(0, 0), end=time_type(23, 57)),
        arrival_override=start_str,
    )
    wp1 = Waypoint(
        id="G2", name="Ziel", lat=42.25, lon=9.15, elevation_m=1200.0,
        time_window=TimeWindow(start=time_type(23, 58), end=time_type(23, 59)),
        arrival_override=end_str,
    )
    stage = Stage(
        id="T1", name="Tag 1", date=date_type.today(),
        start_time=start_time, waypoints=[wp0, wp1],
    )
    trip = Trip(id=trip_id, name="Onset-Fidelity-Trip", stages=[stage])
    trip.report_config = config
    return trip


def _clean_user(uid: str) -> None:
    import shutil
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d)


class _SevenStub:
    """Echter lokaler HTTP-Server, der den seven.io-Gateway nachbildet
    (Vorbild test_914_slice4_alert_sms_dispatch.py)."""

    def __init__(self, body: str = "100", status: int = 200) -> None:
        self.received: list[bytes] = []
        body_bytes = body.encode()
        received = self.received

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                received.append(self.rfile.read(length))
                self.send_response(status)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(body_bytes)

            def log_message(self, *args):
                pass

        self._httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_port}/api/sms"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self._httpd.shutdown()


class _FakeTelegramState:
    def __init__(self) -> None:
        self.last_payload: dict | None = None


def _make_fake_bot_handler(state: _FakeTelegramState):
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw or b"{}")
            state.last_payload = payload
            body = json.dumps({"ok": True, "result": {"message_id": 1}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return _Handler


@pytest.fixture
def fake_telegram_bot(monkeypatch):
    """Lokaler Real-HTTP-Server + `TELEGRAM_API_BASE`-Umlenkung (Vorbild #650)."""
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


_TELEGRAM_SETTINGS = Settings(telegram_bot_token="test-token-952", telegram_chat_id="99999")


# ===========================================================================
# AC-1: render_email() Onset-Zweig auf Design-Tokens/Vorlagen-Struktur
# ===========================================================================


class TestAC1EmailOnsetDesignFidelity:
    def test_badge_h1_datablock_cooldown_footer_and_absence_of_ad_hoc_html(self):
        from output.renderers.email.design_tokens import G_ACCENT

        msg = _onset_msg(onset_minutes=12, is_convective=False)
        html, plain = render_email(msg)

        # Badge: G_ACCENT-getönt, Text exakt "Radar-Nowcast" (nicht "kein Δ").
        assert "Radar-Nowcast" in html, f"Badge-Text fehlt: {html!r}"
        assert "kein Δ" not in html, f"Design-Doc-Annotation im Produktionstext: {html!r}"
        assert G_ACCENT in html, f"G_ACCENT-Token nicht im HTML: {html!r}"

        # H1
        assert "Regen in 12 Min" in html, f"H1 fehlt/falsch: {html!r}"

        # Datenblock: 3 Pflichtzeilen (4. Briefing-Zeile separat getestet, s.u.).
        # "Wo & wann" wird wie im Deviation-Zweig (#957) HTML-escaped gerendert
        # (Wo &amp; wann im Roh-HTML, Mail-Client zeigt "Wo & wann") — Korrektur
        # nach PO-Review: Anzeige-Text vs. Kodierungs-Ebene nicht verwechseln.
        for label in ("Wo &amp; wann", "Intensität", "Quelle"):
            assert label in html, f"Datenblock-Zeile {label!r} fehlt: {html!r}"

        # Cooldown-Box: border-left + G_ACCENT
        assert "border-left" in html, f"Cooldown-Box ohne border-left: {html!r}"
        cooldown_idx = html.find("Cooldown")
        assert cooldown_idx != -1 or "höchstens einmal in" in html, (
            f"Cooldown-Hinweis fehlt: {html!r}"
        )

        # Fußzeile ohne km (Datenblock-Zeile 1 trägt bereits km)
        footer_match = re.search(r"Stand: heute [^\n<]*", plain)
        assert footer_match, f"Fußzeile fehlt im Plain-Text: {plain!r}"
        assert "km" not in footer_match.group(), (
            f"Fußzeile enthält noch eine km-Angabe: {footer_match.group()!r}"
        )

        # Verboten: altes Ad-hoc-HTML
        assert "font-family:sans-serif" not in html, f"Ad-hoc-Font noch vorhanden: {html!r}"
        assert "color:#555" not in html, f"Ad-hoc-Farbe noch vorhanden: {html!r}"

    def test_cooldown_box_absent_when_not_set(self):
        msg = _onset_msg(cooldown_display=None)
        html, _ = render_email(msg)
        assert "höchstens einmal in" not in html, (
            "Cooldown-Box darf ohne cooldown_display nicht erscheinen"
        )

    def test_fourth_briefing_datablock_line(self):
        """Separater Test (eigener TypeError-Fehlgrund): 4. Datenblock-Zeile
        "Briefing" braucht das neue `OnsetEvent.briefing_context`-Feld."""
        msg = _onset_msg(briefing_context="nicht angekündigt")
        html, _ = render_email(msg)
        assert "Briefing" in html, f"4. Datenblock-Zeile 'Briefing' fehlt: {html!r}"
        assert "nicht angekündigt" in html, f"Briefing-Kontext-Wert fehlt: {html!r}"


# ===========================================================================
# AC-2: km-Rundung konsistent über alle vier Kanäle
# ===========================================================================


class TestAC2KmRoundingConsistentAcrossChannels:
    def test_all_four_channels_show_identical_rounded_km(self):
        msg = _onset_msg(km_from=9.8, km_to=15.200000000000001)
        subject = render_subject(msg)
        html, plain = render_email(msg)
        telegram = render_telegram(msg)
        sms = render_sms(msg)

        subj_m = KM_RE.search(subject)
        plain_m = KM_RE.search(plain)
        tg_m = KM_RE.search(telegram)
        sms_m = re.search(r"km(\d+)-(\d+)", sms)

        assert subj_m, f"km-Format fehlt im Betreff: {subject!r}"
        assert plain_m, f"km-Format fehlt im Plain-Text: {plain!r}"
        assert tg_m, f"km-Format fehlt in Telegram: {telegram!r}"
        assert sms_m, f"km-Format fehlt in SMS: {sms!r}"

        digits = re.compile(r"(\d+)")
        subj_nums = digits.findall(subj_m.group())
        plain_nums = digits.findall(plain_m.group())
        tg_nums = digits.findall(tg_m.group())
        sms_nums = [sms_m.group(1), sms_m.group(2)]

        assert subj_nums == ["10", "15"], f"Betreff-km nicht 10-15: {subject!r}"
        assert plain_nums == ["10", "15"], f"Plain-km nicht 10-15: {plain!r}"
        assert tg_nums == ["10", "15"], f"Telegram-km nicht 10-15: {telegram!r}"
        assert sms_nums == ["10", "15"], f"SMS-km nicht 10-15: {sms!r}"

        for text in (subject, html, plain, telegram, sms):
            assert "15.2" not in text, f"Float-Rauschen im Kanal: {text!r}"
            assert "9.8" not in text, f"Float-Rauschen im Kanal: {text!r}"


# ===========================================================================
# AC-4 (Renderer-Teil): echtes Telegram-Bold statt '**' — beide Zweige
# ===========================================================================


class TestAC4TelegramBoldBothBranches:
    def test_onset_uses_html_bold_tag_not_markdown_asterisks(self):
        msg = _onset_msg()
        tg = render_telegram(msg)
        assert "<b>" in tg and "</b>" in tg, f"Kein <b>-Tag im Onset-Telegram: {tg!r}"
        assert "**" not in tg, f"Noch '**'-Markdown im Onset-Telegram: {tg!r}"

    def test_deviation_uses_html_bold_tag_not_markdown_asterisks(self):
        msg = _deviation_msg()
        tg = render_telegram(msg)
        assert "<b>" in tg and "</b>" in tg, f"Kein <b>-Tag im Deviation-Telegram: {tg!r}"
        assert "**" not in tg, f"Noch '**'-Markdown im Deviation-Telegram: {tg!r}"


# ===========================================================================
# AC-8: Renderer-Parität Deviation (source=None) vs. Onset (source gesetzt)
# ===========================================================================


@pytest.mark.parametrize("source", [None, "Radar (DWD)"])
class TestAC8RendererParity:
    def _msg(self, source: str | None) -> AlertMessage:
        if source is None:
            return _deviation_msg()
        return _onset_msg(source_label=source)

    def test_subject_no_crash_nonempty_km_format(self, source):
        subj = render_subject(self._msg(source))
        assert subj, "Betreff darf nicht leer sein"
        assert KM_RE.search(subj), f"km-Format fehlt im Betreff: {subj!r}"

    def test_email_no_crash_nonempty(self, source):
        html, plain = render_email(self._msg(source))
        assert html, "HTML darf nicht leer sein"
        assert plain, "Plain-Text darf nicht leer sein"

    def test_telegram_no_crash_nonempty(self, source):
        tg = render_telegram(self._msg(source))
        assert tg, "Telegram-Text darf nicht leer sein"

    def test_sms_no_crash_nonempty(self, source):
        sms = render_sms(self._msg(source))
        assert sms, "SMS-Text darf nicht leer sein"


# ===========================================================================
# AC-3 + AC-6: check_radar_alerts() Dispatch (Fake-Radar-Seam, kein Mock)
# ===========================================================================


class TestAC3IntensityLabelNoSentenceDuplicate:
    def test_email_intensity_line_is_exact_short_label(self):
        uid = "tdd-952-ac3"
        trip_id = "trip-952-ac3"
        _clean_user(uid)
        try:
            config = TripReportConfig(
                trip_id=trip_id, send_email=True, send_telegram=False,
                send_sms=False, alert_on_changes=True,
            )
            trip = _trip_with_active_segment(trip_id, config)
            from app.loader import save_trip
            save_trip(trip, user_id=uid)

            settings = Settings().model_copy(update={
                "smtp_host": "smtp.test.invalid", "smtp_user": "alert@test.invalid",
                "smtp_pass": "secret", "mail_to": "gregor-test@henemm.com",
                "smtp_port": 587, "is_test_mode": False,
                "telegram_bot_token": "", "telegram_chat_id": "",
            })
            mail_calls: list[tuple[str, str]] = []
            from services.trip_alert import TripAlertService
            svc = TripAlertService(
                settings=settings, throttle_hours=0, user_id=uid,
                radar_service=_GuaranteedWetRadar(
                    onset_minutes=12, intensity_label="leichter Regen",
                    is_convective=False,
                ),
                mail_sink=lambda subject, body: mail_calls.append((subject, body)),
            )

            result = svc.check_radar_alerts()

            assert result == 1, f"check_radar_alerts() sollte 1 Alert liefern, war {result}"
            assert len(mail_calls) == 1, "mail_sink wurde nicht genau einmal aufgerufen"
            _, plain_body = mail_calls[0]

            intensity_line = next(
                (l for l in plain_body.splitlines() if l.startswith("Intensität")), None,
            )
            assert intensity_line is not None, (
                f"Keine 'Intensität'-Zeile im Mail-Body: {plain_body!r}"
            )
            assert intensity_line == "Intensität: leichter Regen", (
                f"Intensitäts-Zeile nicht exakt 'leichter Regen': {intensity_line!r}"
            )
            assert "ab ca." not in plain_body, f"Alter Satzbau noch vorhanden: {plain_body!r}"
            assert plain_body.count("ab ") <= 1, (
                f"Doppeltes 'ab HH:MM' im Body: {plain_body!r}"
            )
        finally:
            _clean_user(uid)


class TestF002IntensityLabelLowercaseViaRealMapping:
    """F002 (Adversary-Finding): TestAC3 oben übergibt das Label bereits
    kleingeschrieben direkt an den Fake-Seam und umgeht damit
    `intensity_to_text()` (das Title-Case liefert, z.B. "Leichter Regen").
    Dieser Test zieht das Label durch die ECHTE Mapping-Funktion, damit die
    Kleinschreibungs-Korrektur in `check_radar_alerts()` selbst geprüft wird."""

    def test_email_intensity_line_lowercased_from_real_intensity_to_text(self):
        uid = "tdd-952-f002"
        trip_id = "trip-952-f002"
        _clean_user(uid)
        try:
            real_label = RadarNowcastService().intensity_to_text(0.5)
            assert real_label == "Leichter Regen", (
                f"Erwartete Title-Case-Ausgabe von intensity_to_text(): {real_label!r}"
            )

            config = TripReportConfig(
                trip_id=trip_id, send_email=True, send_telegram=False,
                send_sms=False, alert_on_changes=True,
            )
            trip = _trip_with_active_segment(trip_id, config)
            from app.loader import save_trip
            save_trip(trip, user_id=uid)

            settings = Settings().model_copy(update={
                "smtp_host": "smtp.test.invalid", "smtp_user": "alert@test.invalid",
                "smtp_pass": "secret", "mail_to": "gregor-test@henemm.com",
                "smtp_port": 587, "is_test_mode": False,
                "telegram_bot_token": "", "telegram_chat_id": "",
            })
            mail_calls: list[tuple[str, str]] = []
            from services.trip_alert import TripAlertService
            svc = TripAlertService(
                settings=settings, throttle_hours=0, user_id=uid,
                radar_service=_GuaranteedWetRadar(
                    onset_minutes=12, intensity_label=real_label,
                    is_convective=False,
                ),
                mail_sink=lambda subject, body: mail_calls.append((subject, body)),
            )

            result = svc.check_radar_alerts()

            assert result == 1, f"check_radar_alerts() sollte 1 Alert liefern, war {result}"
            assert len(mail_calls) == 1, "mail_sink wurde nicht genau einmal aufgerufen"
            _, plain_body = mail_calls[0]

            intensity_line = next(
                (l for l in plain_body.splitlines() if l.startswith("Intensität")), None,
            )
            assert intensity_line is not None, (
                f"Keine 'Intensität'-Zeile im Mail-Body: {plain_body!r}"
            )
            assert intensity_line == "Intensität: leichter Regen", (
                f"Intensitäts-Zeile nicht kleingeschrieben (F002): {intensity_line!r}"
            )
            assert "Leichter Regen" not in plain_body, (
                f"Title-Case-Label aus intensity_to_text() unverändert durchgereicht: "
                f"{plain_body!r}"
            )
        finally:
            _clean_user(uid)


class TestAC6SmsOnlyRadarDispatch:
    def test_sms_only_trip_is_not_skipped_and_receives_alert(self):
        uid = "tdd-952-ac6"
        trip_id = "trip-952-ac6"
        _clean_user(uid)
        # Issue #1069: SMS-Versand ist an Level standard/premium gebunden
        # (sms_allowed() liefert bei fehlender user.json "free" = False). Dieser
        # Test prueft den SMS-Dispatch-Mechanismus selbst, nicht das Tier-Gating.
        (DATA_ROOT / uid).mkdir(parents=True, exist_ok=True)
        (DATA_ROOT / uid / "user.json").write_text(json.dumps({"id": uid, "tier": "standard"}))
        stub = _SevenStub(body="100")
        try:
            config = TripReportConfig(
                trip_id=trip_id, send_email=False, send_telegram=False,
                send_sms=True, alert_on_changes=True,
            )
            trip = _trip_with_active_segment(trip_id, config)
            from app.loader import save_trip
            save_trip(trip, user_id=uid)

            settings = Settings().model_copy(update={
                "smtp_host": None, "smtp_user": None, "smtp_pass": None, "mail_to": None,
                "telegram_bot_token": "", "telegram_chat_id": "",
                "sms_gateway_url": stub.url, "seven_api_key": "test-key",
                "sms_to": "+49123456789", "sms_from": "Gregor",
            })
            assert settings.can_send_email() is False
            assert settings.can_send_telegram() is False
            assert settings.can_send_sms() is True

            from services.trip_alert import TripAlertService
            svc = TripAlertService(
                settings=settings, throttle_hours=0, user_id=uid,
                radar_service=_GuaranteedWetRadar(
                    onset_minutes=12, intensity_label="leichter Regen",
                    is_convective=False,
                ),
            )

            result = svc.check_radar_alerts()

            assert result == 1, (
                f"AC-6: SMS-only-Trip darf NICHT übersprungen werden (heutiger Gate-Bug "
                f"Z.766-770 kennt nur email/telegram), got {result}"
            )
            assert len(stub.received) == 1, (
                "seven.io-Gateway wurde NICHT aufgerufen — SMS-Block fehlt im Radar-Pfad."
            )
            # payload ist application/x-www-form-urlencoded (httpx data=-POST) --
            # ':'/'!' liegen als %3A/%21 vor; vor dem Regex dekodieren (gleiche
            # Fehlerklasse wie AC-1: Anzeige-Text vs. Kodierungs-Ebene).
            import urllib.parse
            payload = urllib.parse.unquote_plus(stub.received[0].decode())
            match = re.search(r"km\d+-\d+: (R|TH)!\d+", payload)
            assert match, f"SMS-Body-Token-Format falsch: {payload!r}"
        finally:
            stub.close()
            _clean_user(uid)


# ===========================================================================
# AC-4/AC-5 (TelegramOutput-Teil): parse_mode="HTML" + suppress_subject_line
# ===========================================================================


class TestAC4TelegramOutputHtmlParseMode:
    def test_send_with_new_params_has_html_parse_mode_and_no_subject_prefix(
        self, fake_telegram_bot,
    ):
        output = TelegramOutput(_TELEGRAM_SETTINGS)

        # RED vor Fix: send() kennt parse_mode/suppress_subject_line nicht -> TypeError.
        output.send(
            "Betreff 952", "<b>Body</b>",
            parse_mode="HTML", suppress_subject_line=True,
        )

        payload = fake_telegram_bot.last_payload
        assert payload is not None, "Stub hat keinen sendMessage-Request empfangen"
        assert payload.get("parse_mode") == "HTML", f"parse_mode fehlt im Payload: {payload!r}"
        assert "[Betreff 952]" not in payload["text"], (
            f"Betreff-Präfix trotz suppress_subject_line=True: {payload!r}"
        )
        assert payload["text"] == "<b>Body</b>", f"Body wurde verändert: {payload!r}"


class TestAC5TelegramOutputBackwardCompatible:
    def test_send_without_new_params_is_bit_identical_to_legacy_behavior(
        self, fake_telegram_bot,
    ):
        """Muss HEUTE UND nach dem Fix grün sein (Rückwärtskompatibilität)."""
        output = TelegramOutput(_TELEGRAM_SETTINGS)
        output.send("Betreff 952", "Body")

        payload = fake_telegram_bot.last_payload
        assert payload is not None
        assert payload["text"] == "[Betreff 952]\n\nBody", f"Altverhalten gebrochen: {payload!r}"
        assert "parse_mode" not in payload, f"parse_mode darf im Altpfad fehlen: {payload!r}"


# ===========================================================================
# AC-7: Alert-Preview-Endpoint — Onset-Zweig
# ===========================================================================


class TestAC7AlertPreviewOnsetPayload:
    def test_post_alert_preview_with_onset_payload_returns_onset_render(self):
        from fastapi.testclient import TestClient

        from api.main import app
        from app.loader import save_trip

        uid = "tdd-952-ac7"
        trip_id = "trip-952-ac7"
        _clean_user(uid)
        try:
            config = TripReportConfig(trip_id=trip_id)
            trip = _trip_with_active_segment(trip_id, config)
            save_trip(trip, user_id=uid)

            client = TestClient(app)
            body = {
                "onset": {
                    "onset_minutes": 12, "onset_time": "14:35",
                    "km_from": 5.0, "km_to": 18.0, "is_convective": False,
                    "intensity_label": "leichter Regen", "source_label": "Radar (DWD)",
                    "cooldown_display": "2 Stunden",
                },
            }
            resp = client.post(
                f"/api/trips/{trip_id}/alert-preview?user_id={uid}", json=body,
            )

            assert resp.status_code == 200, (
                f"AC-7: Onset-Preview-Payload muss 200 liefern, war "
                f"{resp.status_code}: {resp.text}"
            )
            data = resp.json()
            for key in ("subject", "email_html", "email_plain", "telegram", "sms"):
                assert key in data, f"Response-Feld {key!r} fehlt: {data!r}"
            assert "Radar-Nowcast" in data["email_html"], (
                f"Onset-Badge fehlt im Preview-HTML: {data['email_html']!r}"
            )
            assert re.search(r"!\d+", data["sms"]), (
                f"SMS-Token (R!/TH!) fehlt im Preview-SMS: {data['sms']!r}"
            )
        finally:
            _clean_user(uid)
