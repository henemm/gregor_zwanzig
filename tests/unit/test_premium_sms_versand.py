"""Premium-SMS (Garmin inReach) als vierter Versandkanal — Nachweis am POST.

Spec: docs/specs/modules/feat_1676_s2a_premium_sms_versand.md
Abgedeckt: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-8, AC-10.

Naht ist ein ECHTER lokaler HTTP-Server auf 127.0.0.1, der die POSTs an das
seven.io-Gateway entgegennimmt (Vorbild ``tests/tdd/test_issue_936_sms_stub.py``
und ``tests/tdd/test_issue_1069_tier_channel_gating.py``) — kein Mock, kein
``patch()``. Gemessen wird die tatsaechlich abgesendete Nutzlast (``from``,
``to``, ``text`` aus dem eingegangenen Request), nicht das Settings-Objekt:
die Zusicherungen wirken am ausgehenden POST, nicht am Konstruktor.

Der Weg ist der produktive:

    gelernte Rueckadresse in ``user.json`` (S1 schreibt sie dort)
      -> ``Settings.with_user_profile()``
      -> ``TripReportSchedulerService._build_trip_report_request()``  (Tier-Gate
         + Kanalwunsch)
      -> ``NotificationService.send_trip_report()``
      -> Kanal -> POST an das Gateway

Das Kanal-Flag ``send_premium_sms`` wird bewusst NICHT am Modell-Konstruktor
vorbeigeschoben, sondern als freier Schluessel in ``report_config`` der
gespeicherten Briefing-Datei abgelegt — genau dort, wo der Go-Handler es
ablegt (Spec D8) — und ueber ``load_trip()`` zurueckgelesen. So messen diese
Tests die ganze Kette inklusive Persistenz-Uebernahme, und ein fehlgeschlagener
Test benennt den ausgebliebenen Versand statt eines fehlenden Schlagworts.
"""
from __future__ import annotations

import http.server
import json
import re
import socket
import threading
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from app.loader import get_data_dir, load_trip, save_trip
from output.renderers.trip_report import TripReportFormatter

# Unsere feste seven.io-Dienstnummer (Spec AC-1) — der Premium-Absender.
PREMIUM_SMS_SENDER = "4916092172595"
# Von Garmin je Gespraech neu vergebene Rueckadresse, die S1 gelernt hat.
LEARNED_REPLY_TO = "+4915799912345"
# Settings.sms_to / Settings.sms_from — duerfen den Premium-Kanal nie erreichen.
CONFIG_SMS_TO = "+49000000111"
CONFIG_SMS_FROM = "+49000000222"
# Spec D6: 30 Tage. Absichtlich hier ausgeschrieben statt aus dem Produktivmodul
# gelesen — ein aus dem Code importierter Wert wuerde jede Fristverschiebung
# stillschweigend mitziehen und die Kantentests (AC-4/AC-5) entwerten.
REPLY_TTL = timedelta(days=30)
# Kurzschluessel der zwei Sperrfaelle — aus demselben Grund ausgeschrieben:
# ein importierter Wert wuerde ein Vertauschen der beiden Kennungen
# stillschweigend mitziehen, und genau dieses Vertauschen wuerde der Alarmpfad
# (#1701) als falschen Grund ins Protokoll buchen.
EXPECTED_CODE_NO_REPLY = "premium_sms_no_reply_address"
EXPECTED_CODE_STALE = "premium_sms_reply_address_stale"

_KEEP = object()  # Sentinel: Settings-Feld absichtlich NICHT ueberschreiben


# ---------------------------------------------------------------------------
# Lokaler seven.io-Stub (echter HTTP-Server, kein Mock)
# ---------------------------------------------------------------------------

class _SevenIoStub:
    """Nimmt die echten POSTs von SMSOutput/PremiumSmsOutput entgegen."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                data = urllib.parse.parse_qs(body.decode())
                entry = {k: v[0] for k, v in data.items()}
                entry["_api_key"] = self.headers.get("X-Api-Key")
                received.append(entry)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):
                pass

        probe = socket.socket()
        probe.bind(("", 0))
        self.port = probe.getsockname()[1]
        probe.close()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()

    def recipients(self) -> list[str | None]:
        return [entry.get("to") for entry in self.received]

    def to(self, number: str) -> list[dict]:
        return [entry for entry in self.received if entry.get("to") == number]


@pytest.fixture()
def stub():
    s = _SevenIoStub()
    yield s
    s.stop()


class _CapturingFormatter(TripReportFormatter):
    """Echter Renderer, der die erzeugten Reports zusaetzlich festhaelt.

    Kein Fake: ``format_email`` laeuft unveraendert durch die Produktivlogik,
    der Rueckgabewert wird nur mitgeschrieben. So kann AC-6 den abgesendeten
    Text gegen den TATSAECHLICH gerenderten ``report.sms_text`` derselben
    Fixture vergleichen, statt gegen eine Konstante im Test (die einen
    gemeinsamen Kopierfehler in Renderer und Test nicht aufdecken wuerde).
    """

    def __init__(self) -> None:
        super().__init__()
        self.reports: list = []

    def format_email(self, *args, **kwargs):
        report = super().format_email(*args, **kwargs)
        self.reports.append(report)
        return report


# ---------------------------------------------------------------------------
# Fixture-Daten
# ---------------------------------------------------------------------------

def _write_profile(
    user_id: str,
    *,
    tier: str,
    reply_to: str | None = None,
    reply_age: timedelta = timedelta(minutes=5),
) -> None:
    """Schreibt ``user.json`` in die (per conftest isolierte) Datenwurzel.

    Feldnamen exakt wie der einzige Schreiber sie ablegt
    (``internal/handler/premium_sms_connect.go`` -> ``internal/model/user.go``:
    ``premium_sms_reply_to`` / ``premium_sms_reply_at`` als RFC3339-UTC).
    """
    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    profile: dict = {"id": user_id, "tier": tier}
    if reply_to is not None:
        stamp = datetime.now(timezone.utc) - reply_age
        profile["premium_sms_reply_to"] = reply_to
        profile["premium_sms_reply_at"] = stamp.isoformat().replace("+00:00", "Z")
    (path / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def _stub_settings(port: int, user_id: str, *, sms_from=None, sms_to=CONFIG_SMS_TO) -> Settings:
    update = {
        "sms_gateway_url": f"http://127.0.0.1:{port}/api/sms",
        "seven_api_key": "test-stub-key",
        "seven_sandbox_key": "test-stub-key",
        "sms_from": sms_from,
    }
    if sms_to is not _KEEP:
        update["sms_to"] = sms_to
    return Settings().with_user_profile(user_id).model_copy(update=update)


def _make_segment_data(*, extreme: bool = False):
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    if extreme:
        points = [
            ForecastDataPoint(
                ts=datetime(2026, 5, 1, 9 + h, 0, tzinfo=timezone.utc),
                t2m_c=-38.0 + h * 15, wind10m_kmh=99.0 + h, gust_kmh=165.0 + h,
                pop_pct=100, precip_1h_mm=120.9, wind_chill_c=-55.0,
                cloud_total_pct=100, visibility_m=50, snow_depth_cm=420.0,
                snow_new_24h_cm=95.0, thunder_level=ThunderLevel.HIGH,
            )
            for h in range(6)
        ]
        agg = SegmentWeatherSummary(
            temp_min_c=-38.0, temp_max_c=47.0, temp_avg_c=4.5,
            wind_max_kmh=104.0, gust_max_kmh=170.0, precip_sum_mm=725.4,
            cloud_avg_pct=100,
        )
    else:
        points = [
            ForecastDataPoint(
                ts=datetime(2026, 5, 1, 9 + h, 0, tzinfo=timezone.utc),
                t2m_c=15.0 + h, wind10m_kmh=10.0 + h, gust_kmh=22.0 + h,
                pop_pct=40, precip_1h_mm=0.4, wind_chill_c=12.0 + h,
                cloud_total_pct=55,
            )
            for h in range(6)
        ]
        agg = SegmentWeatherSummary(
            temp_min_c=15.0, temp_max_c=20.0, temp_avg_c=17.5,
            wind_max_kmh=16.0, gust_max_kmh=28.0, precip_sum_mm=2.4,
            cloud_avg_pct=55,
        )

    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0, interp="point_grid",
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 1, 13, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=points),
        aggregated=agg, fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _persisted_trip(user_id: str, *, send_sms: bool, send_premium_sms: bool):
    """Speichert einen Trip und liest ihn zurueck — inklusive Kanal-Flag.

    ``send_premium_sms`` wird als freier Schluessel in die gespeicherte
    ``report_config`` geschrieben (Spec D8: genau so legt der Go-Handler es ab)
    und muss von ``load_trip()`` uebernommen werden.
    """
    from app.models import TripReportConfig
    from app.trip import Stage, Trip, Waypoint

    trip_id = f"trip-{user_id}"
    # #1709: feste Ankunftszeiten statt Naismith-Self-Heal
    # (trip_segments.py:125-127) — die Zeiten selbst tragen keine
    # Pruefaussage dieser Datei, sie muessen nur ueberhaupt gesetzt sein.
    stage = Stage(
        id="S1", name="Etappe 1", date=date.today() + timedelta(days=1),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400,
                     arrival_calculated="08:00"),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200,
                     arrival_calculated="12:00"),
        ],
    )
    trip = Trip(
        id=trip_id, name=f"Premium-SMS {user_id}", stages=[stage],
        report_config=TripReportConfig(
            trip_id=trip_id, send_email=False, send_sms=send_sms, send_telegram=False,
        ),
    )
    path = save_trip(trip, user_id=user_id)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["report_config"]["send_premium_sms"] = send_premium_sms
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = load_trip(path, user_id=user_id)
    assert loaded is not None, "Trip liess sich nicht zurueckladen"
    return loaded


def _dispatch(
    user_id: str,
    stub: _SevenIoStub,
    *,
    send_sms: bool,
    send_premium_sms: bool,
    extreme: bool = False,
    settings: Settings | None = None,
):
    """Faehrt den echten Briefing-Versandweg und gibt (request, result, reports)."""
    from services.notification_service import NotificationService
    from services.trip_report_scheduler import TripReportSchedulerService

    settings = settings if settings is not None else _stub_settings(stub.port, user_id)
    trip = _persisted_trip(user_id, send_sms=send_sms, send_premium_sms=send_premium_sms)
    scheduler = TripReportSchedulerService(settings=settings, user_id=user_id)
    request = scheduler._build_trip_report_request(
        trip=trip,
        report_type="evening",
        segment_weather=[_make_segment_data(extreme=extreme)],
        trip_tz=ZoneInfo("Europe/Vienna"),
        stage_name=None,
        stage_stats=None,
        night_weather=None,
        thunder_forecast=None,
        multi_day_trend=None,
        stability_result=None,
        day_comparison=None,
        exposed_sections=[],
        allow_test_fallback=False,
        on_demand=False,
        catchup_prefix=None,
    )
    notifier = NotificationService(settings=settings, user_id=user_id)
    formatter = _CapturingFormatter()
    notifier._formatter = formatter
    result = notifier.send_trip_report(request)
    return request, result, formatter.reports


def _blocked_reason(result, *, expected_code: str) -> str:
    """``blocked_channels``/``blocked_reason_codes`` sind Spec D4/D10 —
    Ergebnisfelder, keine Logzeilen.

    ``expected_code`` ist PFLICHT (keyword-only, ohne Vorgabewert): vorher
    genuegte hier irgendein nicht-leerer Text, und damit war eine BEWUSSTE
    Sperre von einem unfreiwilligen Absturz nicht mehr zu unterscheiden — ein
    ``AttributeError`` aus einer verfaelschten Fail-Closed-Pruefung landet ueber
    denselben ``except``-Zweig in ``blocked_channels`` und liest sich dort wie
    eine Sperrmeldung. Die Kennung entsteht ausschliesslich dort, wo der Kanal
    bewusst abbricht (``ChannelBlockedError``), und trennt beides.
    """
    blocked = getattr(result, "blocked_channels", None)
    assert blocked is not None, (
        "NotificationResult hat kein Feld `blocked_channels` — der ausgebliebene "
        "Premium-SMS-Versand ist damit nur in einer Logzeile sichtbar, und eine "
        "Logzeile ist kein Nachweis (Spec D4)."
    )
    assert "premium_sms" in blocked, (
        f"Kein Grund unter dem Kanalnamen 'premium_sms' hinterlegt: {blocked!r}"
    )
    reason = blocked["premium_sms"]
    assert isinstance(reason, str) and reason.strip(), (
        f"Grund ist kein auswertbarer Text: {reason!r}"
    )
    codes = getattr(result, "blocked_reason_codes", None)
    assert codes is not None, (
        "NotificationResult hat kein Feld `blocked_reason_codes` — dann ist der "
        "deutsche Prosatext die einzige Quelle des Sperrgrunds, und ein "
        "Absturztext ist darin von einer bewussten Sperre nicht zu "
        "unterscheiden (Spec D10)."
    )
    assert codes.get("premium_sms") == expected_code, (
        f"Sperrgrund traegt die Kennung {codes.get('premium_sms')!r}, erwartet "
        f"{expected_code!r}. Hinterlegter Prosatext: {reason!r} — der allein "
        "beweist nichts: ein unfreiwilliger Absturz in der Fail-Closed-Pruefung "
        "kommt ueber denselben except-Zweig hier an und sieht genauso aus."
    )
    return reason


# ---------------------------------------------------------------------------
# AC-1: Absender ist ausnahmslos die feste Dienstnummer
# ---------------------------------------------------------------------------

def test_sender_is_fixed_number_regardless_of_sms_from(stub) -> None:
    """AC-1: Given Premium-Nutzer mit frischer Rueckadresse UND abweichend
    gesetztem ``sms_from`` / When das Briefing per Premium-SMS geht / Then
    traegt der abgesendete POST als ``from`` die feste Nummer 4916092172595."""
    user_id = "tdd-1676-sender"
    _write_profile(user_id, tier="premium", reply_to=LEARNED_REPLY_TO)
    settings = _stub_settings(stub.port, user_id, sms_from=CONFIG_SMS_FROM)
    assert settings.sms_from == CONFIG_SMS_FROM, "Widerspruch nicht wirksam gesetzt"

    _, result, _ = _dispatch(
        user_id, stub, send_sms=False, send_premium_sms=True, settings=settings,
    )

    assert len(stub.received) == 1, (
        f"Erwartet genau EIN Premium-SMS-POST, bekommen: {stub.received!r} — "
        "der Premium-Kanal erreicht den seven.io-Transport nicht."
    )
    # Dieser Trip hat NUR den Premium-Kanal — er ist damit konfiguriert.
    # Faellt das Flag aus der `no_channel_configured`-Rechnung heraus, geht die
    # SMS weiter hinaus, aber der Scheduler bucht den Lauf als `no_channels`,
    # schreibt keinen briefing_log-Eintrag und die Cockpit-Kachel zeigt keinen
    # Versand (trip_report_scheduler.py:1188/1238-1241). Deshalb hier
    # mitgemessen: die Wirkung ist unsichtbar am POST allein.
    assert result.no_channel_configured is False, (
        "Ein Trip, der ausschliesslich Premium-SMS bekommt, gilt als 'kein "
        "Kanal konfiguriert' — der nachweislich abgesendete Versand wuerde im "
        "Protokoll und im Cockpit als 'nicht vorgesehen' erscheinen."
    )
    assert stub.received[0].get("from") == PREMIUM_SMS_SENDER, (
        f"Absender falsch: {stub.received[0].get('from')!r} — erwartet die feste "
        f"Dienstnummer {PREMIUM_SMS_SENDER!r}; sms_from ({CONFIG_SMS_FROM}) darf "
        "auf den Premium-Kanal keinerlei Wirkung haben."
    )


# ---------------------------------------------------------------------------
# AC-2: Empfaenger ist die gelernte Rueckadresse, nie sms_to
# ---------------------------------------------------------------------------

def test_recipient_comes_from_learned_reply_to_not_sms_to(stub, monkeypatch) -> None:
    """AC-2: Given ``GZ_SMS_TO`` steht bewusst widersprüchlich im Prozess-
    Environment / When das Briefing per Premium-SMS geht / Then geht der POST
    ausschliesslich an die gelernte Rueckadresse."""
    user_id = "tdd-1676-recipient"
    contradicting = "+49111111111"
    monkeypatch.setenv("GZ_SMS_TO", contradicting)
    _write_profile(user_id, tier="premium", reply_to=LEARNED_REPLY_TO)
    settings = _stub_settings(stub.port, user_id, sms_to=_KEEP)
    assert settings.sms_to == contradicting, (
        f"GZ_SMS_TO wurde nicht wirksam ({settings.sms_to!r}) — der Widerspruch, "
        "den dieser Test braucht, liegt nicht vor."
    )

    _dispatch(user_id, stub, send_sms=False, send_premium_sms=True, settings=settings)

    assert len(stub.received) == 1, (
        f"Erwartet genau EIN Premium-SMS-POST, bekommen: {stub.received!r}"
    )
    assert stub.received[0].get("to") == LEARNED_REPLY_TO, (
        f"Empfaenger falsch: {stub.received[0].get('to')!r} — erwartet die gelernte "
        f"Rueckadresse {LEARNED_REPLY_TO!r} aus user.json, nie sms_to."
    )
    assert contradicting not in stub.recipients(), (
        "sms_to wurde fuer den Premium-Kanal gelesen — verboten (AC-2)."
    )


# ---------------------------------------------------------------------------
# AC-3: keine gelernte Rueckadresse -> kein Versand, sichtbarer Grund
# ---------------------------------------------------------------------------

def test_empty_reply_to_blocks_send_with_visible_reason(stub) -> None:
    """AC-3: Given Premium-Nutzer ohne gelernte Rueckadresse / When das
    Briefing versendet wird / Then kein HTTP-Aufruf UND ein auswertbarer Grund
    unter ``blocked_channels['premium_sms']``."""
    user_id = "tdd-1676-noreply"
    _write_profile(user_id, tier="premium", reply_to=None)

    _, result, _ = _dispatch(user_id, stub, send_sms=False, send_premium_sms=True)

    assert stub.received == [], (
        f"Ohne gelernte Rueckadresse darf KEIN POST hinausgehen, bekommen: "
        f"{stub.received!r}"
    )
    _blocked_reason(result, expected_code=EXPECTED_CODE_NO_REPLY)
    assert "premium_sms" not in result.sent_channels, (
        f"Kanal als gesendet vermerkt, obwohl nichts hinausging: {result.sent_channels!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 / AC-5: die 30-Tage-Frist, beidseitig auf die Sekunde
# ---------------------------------------------------------------------------

def test_reply_to_older_than_ttl_blocks_send(stub) -> None:
    """AC-4: Given Zeitstempel exakt eine Sekunde UEBER der 30-Tage-Frist /
    When das Briefing versendet wird / Then kein Versand, Grund benennt die
    veraltete Rueckadresse."""
    user_id = "tdd-1676-stale"
    _write_profile(
        user_id, tier="premium", reply_to=LEARNED_REPLY_TO,
        reply_age=REPLY_TTL + timedelta(seconds=1),
    )

    _, result, _ = _dispatch(user_id, stub, send_sms=False, send_premium_sms=True)

    assert stub.received == [], (
        "Rueckadresse ist 30 Tage + 1 Sekunde alt — es darf KEIN POST hinausgehen "
        f"(die Nummer sieht syntaktisch gueltig aus), bekommen: {stub.received!r}"
    )
    reason = _blocked_reason(result, expected_code=EXPECTED_CODE_STALE).lower()
    assert any(word in reason for word in ("veralt", "alt", "abgelaufen", "30")), (
        f"Grund benennt die veraltete Rueckadresse nicht: {reason!r}"
    )


def test_reply_to_just_within_ttl_still_sends(stub) -> None:
    """AC-5: Given Zeitstempel exakt eine Sekunde UNTER der 30-Tage-Frist /
    When das Briefing versendet wird / Then geht die Premium-SMS regulaer
    hinaus — die Frist blockiert nicht vorsorglich frueher."""
    user_id = "tdd-1676-fresh-edge"
    _write_profile(
        user_id, tier="premium", reply_to=LEARNED_REPLY_TO,
        reply_age=REPLY_TTL - timedelta(seconds=1),
    )

    _, result, _ = _dispatch(user_id, stub, send_sms=False, send_premium_sms=True)

    assert len(stub.received) == 1, (
        "Rueckadresse ist 30 Tage - 1 Sekunde alt und damit noch gueltig — genau "
        f"EIN POST erwartet, bekommen: {stub.received!r} "
        f"(blocked: {getattr(result, 'blocked_channels', None)!r})"
    )
    assert stub.received[0].get("to") == LEARNED_REPLY_TO


# ---------------------------------------------------------------------------
# AC-6: Text bitidentisch mit report.sms_text, <= 160 Zeichen
# ---------------------------------------------------------------------------

def test_text_matches_sms_text_verbatim_under_extreme_weather(stub) -> None:
    """AC-6: Given Extremwetter-Fixture / When per Premium-SMS versendet wird /
    Then ist der abgesendete Text bitidentisch mit dem tatsaechlich gerenderten
    ``report.sms_text`` und nicht laenger als 160 Zeichen."""
    user_id = "tdd-1676-text"
    _write_profile(user_id, tier="premium", reply_to=LEARNED_REPLY_TO)

    _, _, reports = _dispatch(
        user_id, stub, send_sms=False, send_premium_sms=True, extreme=True,
    )

    assert len(reports) == 1, f"Erwartet genau EINEN gerenderten Report, bekommen {len(reports)}"
    report = reports[0]
    assert len(stub.received) == 1, (
        f"Erwartet genau EIN Premium-SMS-POST, bekommen: {stub.received!r}"
    )
    sent_text = stub.received[0].get("text")
    assert report.sms_text, "Renderer hat keinen SMS-Text erzeugt"
    assert report.sms_text != report.email_plain, (
        "Fixture unbrauchbar: sms_text und email_plain sind identisch — dann "
        "koennte dieser Test einen Griff zum falschen Feld nicht unterscheiden."
    )
    assert sent_text == report.sms_text, (
        "Abgesendeter Text weicht vom gerenderten report.sms_text ab.\n"
        f"  gesendet: {sent_text!r}\n  gerendert: {report.sms_text!r}"
    )
    assert len(sent_text) <= 160, f"SMS-Text zu lang: {len(sent_text)} Zeichen"


# ---------------------------------------------------------------------------
# AC-8: standard-Tier loest nie einen Premium-SMS-Versand aus
# ---------------------------------------------------------------------------

def test_standard_tier_never_triggers_premium_sms_send(stub) -> None:
    """AC-8: Given Tier ``standard`` mit aktiviertem ``send_premium_sms`` UND
    gueltiger Rueckadresse / When das Versandfenster prueft / Then keine
    Premium-SMS — obwohl derselbe Nutzer fuer den normalen SMS-Kanal
    berechtigt ist."""
    from services.user_tier import sms_allowed

    user_id = "tdd-1676-standard"
    _write_profile(user_id, tier="standard", reply_to=LEARNED_REPLY_TO)
    assert sms_allowed(user_id) is True, (
        "Voraussetzung des Tests: standard darf normale SMS — sonst prueft er "
        "nur eine Generalsperre."
    )

    request, _, _ = _dispatch(user_id, stub, send_sms=True, send_premium_sms=True)

    assert getattr(request, "send_premium_sms", None) is False, (
        "Das Versandfenster hat Premium-SMS fuer einen standard-Nutzer "
        f"freigegeben: {getattr(request, 'send_premium_sms', '<Feld fehlt>')!r}"
    )
    assert stub.to(LEARNED_REPLY_TO) == [], (
        f"Premium-SMS an die gelernte Rueckadresse trotz Tier 'standard': "
        f"{stub.to(LEARNED_REPLY_TO)!r}"
    )
    assert stub.to(CONFIG_SMS_TO), (
        "Der normale SMS-Kanal muss weiter funktionieren (keine Generalsperre) — "
        f"empfangen: {stub.received!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 am ZWEITEN Wirkort: der Wetterausfall-Hinweis
# (Adversary-Fund F001, 2026-08-10)
# ---------------------------------------------------------------------------

def _outage_scheduler_class():
    """Echter Scheduler, dessen Wetterquelle einen Totalausfall zurueckgibt.

    Kein Mock: der Rueckgabewert ist bitgleich der Platzhalter, den
    ``_fetch_weather()`` bei Provider-Fehlern selbst erzeugt (WEATHER-04,
    ``trip_report_scheduler.py`` „Error-Placeholder statt auslassen") — nur ihr
    ANTEIL (>75 %, ``OUTAGE_WITHHOLD_RATIO``) entscheidet ueber den
    Ausfall-Pfad. Der zu pruefende Code, die Kanalentscheidung in diesem Pfad,
    laeuft unveraendert; ein echter Provider-Ausfall waere hier nur langsamer
    und wetterabhaengig, nicht aussagekraeftiger.
    """
    from app.models import SegmentWeatherData, SegmentWeatherSummary
    from services.trip_report_scheduler import TripReportSchedulerService

    class _OutageScheduler(TripReportSchedulerService):
        def _fetch_weather(self, segments, provider=None):
            return [
                SegmentWeatherData(
                    segment=segment,
                    timeseries=None,
                    aggregated=SegmentWeatherSummary(),
                    fetched_at=datetime.now(timezone.utc),
                    provider="unknown",
                    has_error=True,
                    error_message="Wetterdienst nicht erreichbar (aufgezeichneter Ausfall)",
                )
                for segment in segments
            ]

    return _OutageScheduler


def test_standard_tier_gets_no_premium_sms_when_weather_data_fails(stub) -> None:
    """AC-8 am zweiten Wirkort: Given Tier ``standard`` mit aktiviertem
    ``send_premium_sms`` und gueltiger Rueckadresse UND der Wetterdienst faellt
    komplett aus / When der Scheduler den Wetterausfall-Hinweis verschickt /
    Then geht KEINE Premium-SMS hinaus, obwohl derselbe Lauf den normalen
    SMS-Hinweis zustellt.

    Das Tarif-Gate steht im Scheduler an ZWEI Kanal-Entscheidungsstellen —
    Briefing und Ausfall-Hinweis. Entfernt man es an dieser zweiten, bleiben
    alle uebrigen Tests dieser Datei gruen, weil sie nur die erste fahren
    (nachgemessen, Adversary-Fund F001). Geprueft wird deshalb die WIRKUNG im
    Ausfall-Pfad: was am Gateway ankommt.
    """
    from services.user_tier import sms_allowed

    user_id = "tdd-1676-outage-standard"
    _write_profile(user_id, tier="standard", reply_to=LEARNED_REPLY_TO)
    assert sms_allowed(user_id) is True, (
        "Voraussetzung des Tests: standard darf normale SMS — sonst prueft er "
        "nur eine Generalsperre."
    )
    settings = _stub_settings(stub.port, user_id)
    trip = _persisted_trip(user_id, send_sms=True, send_premium_sms=True)

    scheduler = _outage_scheduler_class()(settings=settings, user_id=user_id)
    outcome = scheduler._send_trip_report_outcome(trip, "evening")

    assert outcome == "no_weather", (
        f"Der Lauf hat den Wetterausfall-Pfad nicht genommen (outcome={outcome!r}) "
        "— dann sagt dieser Test ueber die zweite Kanal-Entscheidungsstelle "
        "nichts aus."
    )
    assert stub.to(CONFIG_SMS_TO), (
        "Der Ausfall-Hinweis ist ueberhaupt nicht verschickt worden (kein "
        f"SMS-POST): {stub.received!r}. Ohne ihn ist das Ausbleiben der "
        "Premium-SMS kein Nachweis, sondern nur ein stiller Pfad."
    )
    assert stub.to(LEARNED_REPLY_TO) == [], (
        "Premium-SMS an die gelernte Rueckadresse trotz Tier 'standard': "
        f"{stub.to(LEARNED_REPLY_TO)!r} — am Wetterausfall-Hinweis fehlt das "
        "Tarif-Gate; die SMS ist kostenpflichtig und geht an ein Geraet, fuer "
        "das der Nutzer nicht bezahlt hat."
    )


def test_outage_hint_names_the_reason_when_premium_sms_is_blocked(stub) -> None:
    """AC-3/D4 am zweiten Wirkort: Given ein Premium-Nutzer ohne gelernte
    Rueckadresse / When der Wetterausfall-Hinweis verschickt wird / Then geht
    keine Premium-SMS hinaus und der Grund steht im Ergebnis DIESES Versands.

    ``blocked_channels`` wird an zwei Stellen gefuellt (Briefing und
    Ausfall-Hinweis); bewacht war nur die erste. Ohne diesen Test koennte der
    Ausfall-Hinweis den Grund verschlucken, ohne dass etwas rot wird.
    """
    from services.notification_service import NotificationService

    user_id = "tdd-1676-outage-noreply"
    _write_profile(user_id, tier="premium", reply_to=None)
    settings = _stub_settings(stub.port, user_id)
    trip = _persisted_trip(user_id, send_sms=False, send_premium_sms=True)

    result = NotificationService(settings=settings, user_id=user_id).send_no_data_hint(
        trip, "evening",
        send_email=False, send_sms=False, send_telegram=False, send_premium_sms=True,
    )

    assert stub.received == [], (
        f"Ohne gelernte Rueckadresse darf auch der Ausfall-Hinweis KEINEN POST "
        f"absetzen, bekommen: {stub.received!r}"
    )
    _blocked_reason(result, expected_code=EXPECTED_CODE_NO_REPLY)
    assert "premium_sms" not in result.sent_channels, (
        f"Kanal als gesendet vermerkt, obwohl nichts hinausging: "
        f"{result.sent_channels!r}"
    )


# ---------------------------------------------------------------------------
# Persistenz: ein Speichervorgang ohne das Flag darf es nicht zuruecksetzen
# ---------------------------------------------------------------------------

def test_saving_a_trip_without_the_flag_keeps_a_stored_true() -> None:
    """Given ein Trip mit gespeichertem ``send_premium_sms: true`` / When ein
    Schreibvorgang laeuft, der das Flag NICHT mitsendet (der Weg der
    Inbound-Kommandos ``/skip``/``/pause``: ``dataclasses.replace`` +
    ``save_trip``) / Then steht das Flag danach unveraendert in der Datei.

    Hintergrund: beim Kanal-Set ``alert_channels`` wird das GANZE Objekt
    ersetzt (``internal/handler/trip.go`` — „gesetzt = ersetzt", all-or-nothing);
    ein neues Feld, das die Oberflaeche nicht mitsendet, faellt dort still auf
    ``false``. Fuer ``send_premium_sms`` traegt der Python-Schreibweg das Risiko,
    weil er ein VOLLSTAENDIGES ``report_config``-Objekt aus dem Modell
    serialisiert: liest der Ladeweg das Flag nicht, ueberschreibt der
    Vorgabewert ``False`` den gespeicherten Wert — stiller Kanal-Abschalter
    ohne Zutun des Nutzers.
    """
    import dataclasses

    from app.loader import get_briefings_dir, load_trip, save_trip

    user_id = "tdd-1676-persist"
    trip = _persisted_trip(user_id, send_sms=False, send_premium_sms=True)
    # Vorbedingung ist die DATEI, nicht das Modell: dass der Ladeweg den Wert
    # uebernimmt, ist Teil des Prueflings — waere es die Vorbedingung, wuerde
    # ausgerechnet der Verlustfall als "Vorbedingung nicht hergestellt"
    # gemeldet und der eigentliche Befund verdeckt.
    path = get_briefings_dir(user_id) / f"{trip.id}.json"
    stored_before = json.loads(path.read_text(encoding="utf-8"))["report_config"]
    assert stored_before.get("send_premium_sms") is True, (
        "Vorbedingung nicht hergestellt — in der Datei steht gar nicht true: "
        f"{stored_before.get('send_premium_sms')!r}"
    )

    # Ein Schreibvorgang, der NUR ein anderes Feld anfasst.
    changed = dataclasses.replace(
        trip,
        report_config=dataclasses.replace(trip.report_config, skip_next=True),
    )
    written = save_trip(changed, user_id=user_id)
    assert written == path, f"Unerwarteter Schreibpfad: {written} != {path}"

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["report_config"].get("send_premium_sms") is True, (
        "Das Flag ist beim Speichern verloren gegangen bzw. auf false "
        f"zurueckgedreht: {raw['report_config'].get('send_premium_sms')!r} — der "
        "Nutzer hat den Kanal gewaehlt und bekommt ihn ohne Vorwarnung nicht mehr."
    )
    reloaded = load_trip(path, user_id=user_id)
    assert reloaded is not None and reloaded.report_config.send_premium_sms is True, (
        "Nach dem Zuruecklesen ist der Kanal aus: "
        f"{getattr(reloaded and reloaded.report_config, 'send_premium_sms', None)!r}"
    )


# ---------------------------------------------------------------------------
# AC-10: Premium-SMS und SMS sind unabhaengig schaltbar
# ---------------------------------------------------------------------------

@pytest.mark.timeout(120)
def test_premium_sms_and_sms_are_independently_switchable(stub) -> None:
    """AC-10: Given alle vier Kombinationen aus ``send_sms``/
    ``send_premium_sms`` / When das Briefing versendet wird / Then wird genau
    der jeweils aktivierte Kanal angesprochen — unterschieden am ``to``-Wert."""
    combos = [(False, False), (True, False), (False, True), (True, True)]
    for index, (send_sms, send_premium_sms) in enumerate(combos):
        user_id = f"tdd-1676-combo{index}"
        _write_profile(user_id, tier="premium", reply_to=LEARNED_REPLY_TO)
        before_sms = len(stub.to(CONFIG_SMS_TO))
        before_premium = len(stub.to(LEARNED_REPLY_TO))

        _dispatch(user_id, stub, send_sms=send_sms, send_premium_sms=send_premium_sms)

        got_sms = len(stub.to(CONFIG_SMS_TO)) - before_sms
        got_premium = len(stub.to(LEARNED_REPLY_TO)) - before_premium
        assert (got_sms, got_premium) == (int(send_sms), int(send_premium_sms)), (
            f"Kombination send_sms={send_sms}, send_premium_sms={send_premium_sms}: "
            f"erwartet ({int(send_sms)} SMS, {int(send_premium_sms)} Premium-SMS), "
            f"bekommen ({got_sms}, {got_premium}) — die Kanaele sind nicht "
            "unabhaengig schaltbar."
        )


# ---------------------------------------------------------------------------
# Die zwei Sperrfaelle sind OHNE Textvergleich unterscheidbar
# (Nachziehung 2026-08-10, Vorarbeit fuer den Alarmpfad #1701)
# ---------------------------------------------------------------------------

def _block_case(user_id: str, stub: _SevenIoStub, *, reply_to, reply_age) -> tuple:
    """Faehrt den Kanal bis zur Sperre; gibt (Kurzschluessel, Prosatext).

    Prüfort ist der Kanal selbst, weil GENAU DORT der Alarmpfad (#1701) den
    Grund abgreift: er sieht die Ausnahme des Kanals, kein Ergebnisfeld des
    Briefing-Aufrufers. Gefragt wird per ``getattr`` — genauso, wie ein
    Aufrufer fragen muss, der auch Ausnahmen ohne Kurzschluessel faengt.
    """
    from output.channels.base import OutputConfigError
    from output.channels.premium_sms import PremiumSmsOutput

    _write_profile(user_id, tier="premium", reply_to=reply_to, reply_age=reply_age)
    settings = _stub_settings(stub.port, user_id)
    with pytest.raises(OutputConfigError) as caught:
        PremiumSmsOutput(settings).send(subject="egal", body="egal")
    code = getattr(caught.value, "reason_code", None)
    assert isinstance(code, str) and code.strip(), (
        f"Die Sperre traegt keinen maschinenlesbaren Grund (reason_code={code!r}) "
        "— dann bleibt dem Alarmpfad nur der deutsche Prosatext, und ein "
        "Vergleich darauf bricht beim ersten Umformulieren still."
    )
    return code, str(caught.value)


def test_channel_name_premium_sms_resolves_to_the_premium_channel(stub) -> None:
    """Given der Kanalname ``premium_sms`` wird ueber die zentrale Kanal-Fabrik
    aufgeloest (der Weg der CLI, ``get_channel``) / When ohne gelernte
    Rueckadresse gesendet wird / Then blockt derselbe Fail-Closed-Grund wie beim
    direkt gebauten Kanal, und es geht KEIN POST hinaus.

    Gemessen wird das Verhalten, nicht der Typ: waere der Name dort auf den
    normalen SMS-Kanal verdrahtet, ginge hier eine kostenpflichtige SMS an
    ``sms_to`` ab — mit falschem Absender und falschem Empfaenger — statt zu
    blocken. Die Registrierung war bis hierhin von keinem Test beruehrt.
    """
    from output.channels.base import OutputConfigError, get_channel

    user_id = "tdd-1676-factory"
    _write_profile(user_id, tier="premium", reply_to=None)
    settings = _stub_settings(stub.port, user_id)

    with pytest.raises(OutputConfigError) as caught:
        get_channel("premium_sms", settings).send(subject="egal", body="egal")

    assert getattr(caught.value, "reason_code", None) == EXPECTED_CODE_NO_REPLY, (
        f"Kanalname 'premium_sms' fuehrt nicht auf den Premium-Kanal: der "
        f"Abbruch traegt {getattr(caught.value, 'reason_code', None)!r} statt "
        f"{EXPECTED_CODE_NO_REPLY!r}."
    )
    assert stub.received == [], (
        f"Trotz fehlender Rueckadresse ging ein POST hinaus: {stub.received!r}"
    )


def test_the_two_block_cases_carry_distinct_machine_codes(stub) -> None:
    """Given die beiden Sperrfaelle (keine Rueckadresse / Rueckadresse aelter
    als die Frist) / When der Premium-Kanal jeweils blockt / Then tragen die
    Ausnahmen VERSCHIEDENE, stabile Kurzschluessel — ein Aufrufer unterscheidet
    die Faelle, ohne deutschen Prosatext zu vergleichen — und der Prosatext
    bleibt daneben erhalten."""
    no_reply_code, no_reply_text = _block_case(
        "tdd-1676-code-empty", stub, reply_to=None, reply_age=timedelta(minutes=5),
    )
    stale_code, stale_text = _block_case(
        "tdd-1676-code-stale", stub, reply_to=LEARNED_REPLY_TO,
        reply_age=REPLY_TTL + timedelta(seconds=1),
    )

    assert stub.received == [], (
        f"Beide Faelle muessen VOR dem POST blocken, bekommen: {stub.received!r}"
    )
    assert no_reply_code != stale_code, (
        f"Beide Sperrfaelle tragen denselben Kurzschluessel ({no_reply_code!r}) "
        "— dann ist der deutsche Prosatext das einzige Unterscheidungsmerkmal, "
        "und genau das soll er nicht sein."
    )
    # Zuordnung Fall -> Kennung, gegen ausgeschriebene Werte: ein Vertauschen
    # der beiden Kennungen wuerde den Alarmpfad den falschen Grund buchen
    # lassen, und ein Vergleich gegen die importierten Konstanten wuerde das
    # Vertauschen mitziehen.
    assert no_reply_code == EXPECTED_CODE_NO_REPLY, (
        f"Fall 'keine gelernte Rueckadresse' meldet {no_reply_code!r}, erwartet "
        f"{EXPECTED_CODE_NO_REPLY!r}."
    )
    assert stale_code == EXPECTED_CODE_STALE, (
        f"Fall 'Rueckadresse veraltet' meldet {stale_code!r}, erwartet "
        f"{EXPECTED_CODE_STALE!r}."
    )
    for code in (no_reply_code, stale_code):
        assert re.fullmatch(r"[a-z][a-z0-9_]*", code), (
            f"Kurzschluessel {code!r} ist kein stabiler Schluessel im Stil von "
            "`alert_log.py` (channel_disabled, delivery_failed), sondern sieht "
            "wie Prosatext aus — er wandert dann bei jeder Umformulierung mit."
        )
    for label, text in (("keine Rueckadresse", no_reply_text), ("veraltet", stale_text)):
        assert len(text) > 60, (
            f"Fall {label}: der menschenlesbare Grund ist auf {text!r} "
            "geschrumpft — die Kennung kommt ZUSAETZLICH, sie ersetzt den "
            "Prosatext nicht (Spec D4)."
        )
