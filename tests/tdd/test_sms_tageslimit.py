"""TDD RED — SMS-/Premium-SMS-Tageslimit je Nutzer (Issue #2412, Sammel-Issue
#2153, Scheibe S4a, Epic #2138).

SPEC: docs/specs/modules/sms_daily_limit.md (AC-1..AC-10)
Kontext: docs/context/feat-2153-s4-sms-tageslimit.md

RED heute, warum: ``src/services/sms_daily_limit.py`` existiert NICHT.
- AC-5 und AC-9 importieren das Modul direkt in der Testfunktion (nicht am
  Modulkopf) -> ``ImportError`` genau in diesen Tests, keine Sammel-Kollision
  der ganzen Datei.
- AC-1..AC-4, AC-6, AC-7, AC-10 rufen ausschliesslich bestehende
  ``NotificationService``-Sendestellen auf. Da dort heute KEIN Gate existiert,
  gehen alle Sendungen durch den Aufzeichner tatsaechlich hinaus — die
  Verhaltens-Assertions (``blocked_channels``, Aufzeichner-Trefferzahl,
  unveraenderter Zaehlerstand) schlagen fehl, weil das gesperrte Verhalten
  fehlt, nicht weil das Test-Setup falsch waere.

REGRESSIONSWAECHTER (heute schon GRUEN, muessen es nach der Implementierung
bleiben):
- ``test_ac8_bestehendes_alarm_frequenz_limit_bleibt_unveraendert_wirksam``:
  das bestehende Alarm-Frequenz-Limit (``alert_daily_limit.py``) blockt schon
  heute VOR ``NotificationService`` — das neue SMS-Tageslimit darf daran
  nichts aendern, ``sms_daily_count.json`` darf dabei gar nicht erst
  entstehen.

Mock-frei (#1477, keine Mocks als Verhaltensbeweis): alle vier
Transport-Klassen (``EmailOutput``/``SMSOutput``/``PremiumSmsOutput``/
``TelegramOutput``) werden per ``monkeypatch.setattr`` durch echte
Aufzeichner-Klassen ersetzt — sowohl im Modul ``notification_service`` (wo
die meisten Sendestellen ihre Klassen importieren) ALS AUCH in den
Quellmodulen ``output.channels.*`` (``send_compare_report`` importiert
``EmailOutput`` LOKAL bei jedem Aufruf neu -- ein reines
``notification_service``-Patch wuerde diese eine Stelle nicht fangen und
haette dort einen echten Versandversuch ausgeloest). Kein ``Mock()``/
``patch()``/``MagicMock``. Zusaetzlich Dummy-Zugangsdaten per ENV.
"""
from __future__ import annotations

import json
import sys
import threading
import uuid
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.config import Settings  # noqa: E402
from app.loader import get_data_dir  # noqa: E402
from app.models import (  # noqa: E402
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from app.user import SavedLocation  # noqa: E402
from services.notification_service import (  # noqa: E402
    NotificationService, RadarAlertRequest, TripReportRequest,
)
from services.official_alerts.models import OfficialAlert  # noqa: E402
from services.trip_command_processor import CommandResult  # noqa: E402


# ---------------------------------------------------------------------------
# Dummy-ENV (#1477) — unbrauchbare, aber VOLLSTAENDIGE Zugangsdaten, damit
# can_send_sms()/can_send_email()/can_send_telegram() True liefern, ohne dass
# jemals ein echter Versand moeglich waere (Aufzeichner ersetzt zusaetzlich
# JEDE Transport-Klasse, s. Modul-Docstring).
# ---------------------------------------------------------------------------
_TRANSPORT_ENV = {
    "GZ_ENV": "development",
    "GZ_SMTP_HOST": "smtp.invalid",
    "GZ_SMTP_USER": "unbrauchbar",
    "GZ_SMTP_PASS": "unbrauchbar",
    "GZ_MAIL_FROM": "gregor@example.invalid",
    "GZ_MAIL_TO": "unbrauchbar-fallback@example.invalid",
    "GZ_TEST_SMTP_HOST": "smtp.invalid",
    "GZ_TEST_SMTP_USER": "",
    "GZ_TEST_SMTP_PASS": "",
    "GZ_TELEGRAM_BOT_TOKEN": "0000000:unbrauchbar",
    "GZ_TELEGRAM_CHAT_ID": "unbrauchbar-chat",
    "GZ_TELEGRAM_TEST_BOT_TOKEN": "",
    "GZ_TELEGRAM_TEST_CHAT_ID": "",
    "GZ_SMS_GATEWAY_URL": "https://gateway.invalid/api/sms",
    "GZ_SEVEN_API_KEY": "unbrauchbar",
    "GZ_SEVEN_SANDBOX_KEY": "",
    "GZ_SMS_TO": "+490000000000",
}


class Mitschrift:
    """Was die vier Aufzeichner tatsaechlich entgegengenommen haben."""

    def __init__(self) -> None:
        self.je_kanal: dict[str, list] = {
            k: [] for k in ("email", "sms", "premium_sms", "telegram")
        }
        # AC-7: einmalig injizierter Transportfehler je Kanal — wird beim
        # ersten Treffer VERBRAUCHT (danach normales Verhalten).
        self.fehler: dict[str, BaseException] = {}

    def anzahl(self, kanal: str) -> int:
        return len(self.je_kanal[kanal])

    def __repr__(self) -> str:
        return f"Mitschrift({ {k: v for k, v in self.je_kanal.items() if v} })"


def _aufzeichner_installieren(monkeypatch) -> Mitschrift:
    """Ersetzt EmailOutput/SMSOutput/PremiumSmsOutput/TelegramOutput sowohl im
    Modul ``notification_service`` als auch in ihren Quellmodulen — Vorbild
    ``test_kanaltreue_adhoc_antwort.py:136-184``, erweitert um die
    Quellmodul-Patches (s. Modul-Docstring)."""
    from services import notification_service as ns
    import output.channels.email as _email_mod
    import output.channels.premium_sms as _premium_mod
    import output.channels.sms as _sms_mod
    import output.channels.telegram as _telegram_mod

    mit = Mitschrift()

    def _buchen(kanal: str, subject) -> None:
        if kanal in mit.fehler:
            raise mit.fehler.pop(kanal)
        mit.je_kanal[kanal].append(subject)

    class _EmailAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body, html=True, plain_text_body=None, to=None,
                 mail_type=None, mail_format=None, compare_hourly_enabled=None):
            _buchen("email", subject)

    class _SmsAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body) -> None:
            _buchen("sms", subject)

    class _PremiumSmsAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body) -> None:
            _buchen("premium_sms", subject)

    class _TelegramAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body, reply_markup=None, *, parse_mode=None,
                 suppress_subject_line=False) -> int:
            _buchen("telegram", subject)
            return 1

    for modul in (ns, _email_mod):
        monkeypatch.setattr(modul, "EmailOutput", _EmailAufzeichner)
    for modul in (ns, _sms_mod):
        monkeypatch.setattr(modul, "SMSOutput", _SmsAufzeichner)
    for modul in (ns, _premium_mod):
        monkeypatch.setattr(modul, "PremiumSmsOutput", _PremiumSmsAufzeichner)
    for modul in (ns, _telegram_mod):
        monkeypatch.setattr(modul, "TelegramOutput", _TelegramAufzeichner)
    return mit


@pytest.fixture
def mitschrift(monkeypatch) -> Mitschrift:
    for name, wert in _TRANSPORT_ENV.items():
        monkeypatch.setenv(name, wert)
    return _aufzeichner_installieren(monkeypatch)


def _settings() -> Settings:
    """Liest ausschliesslich die Dummy-ENV — KEIN ``with_user_profile()``
    (der wuerde ``user.json`` konsultieren und die ENV-Werte auf ``None``
    ueberschreiben, s. ``app/config.py:435-451``)."""
    return Settings()


# ---------------------------------------------------------------------------
# Nutzer-/Zaehler-Helfer
# ---------------------------------------------------------------------------


def _kennung(praefix: str) -> str:
    """Mandantenkennung OHNE "tdd"/"test" (sonst ``is_test_user_id`` erzwingt
    ``Settings.for_testing()`` und die ENV-Werte werden umgeleitet)."""
    return f"smslimit-{praefix}-{uuid.uuid4().hex[:8]}"


def _nutzer_anlegen(uid: str, tier: str) -> None:
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": uid, "tier": tier}))


def _zaehler_pfad(uid: str) -> Path:
    return get_data_dir(uid) / "sms_daily_count.json"


def _heute_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _zaehler_schreiben(
    uid: str, *, sms: int = 0, premium_sms: int = 0, datum: str | None = None,
) -> None:
    pfad = _zaehler_pfad(uid)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(
        {"date": datum or _heute_utc(), "sms": sms, "premium_sms": premium_sms}
    ))


def _zaehler_lesen(uid: str) -> dict:
    pfad = _zaehler_pfad(uid)
    if not pfad.exists():
        return {}
    return json.loads(pfad.read_text())


# ---------------------------------------------------------------------------
# Trip-/Request-Helfer (Trip-Briefing-Pfad)
# ---------------------------------------------------------------------------


def _segment_weather() -> SegmentWeatherData:
    points = [
        ForecastDataPoint(
            ts=datetime(2026, 5, 1, 9 + h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h, wind10m_kmh=10.0 + h,
        )
        for h in range(3)
    ]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=points)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 1, 13, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    agg = SegmentWeatherSummary(
        temp_min_c=15.0, temp_max_c=20.0, temp_avg_c=17.5,
        wind_max_kmh=16.0, precip_sum_mm=2.4,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _trip(trip_id: str) -> Trip:
    stage = Stage(
        id="S1", name="Etappe 1", date=datetime(2026, 5, 1).date(),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200),
        ],
    )
    cfg = TripReportConfig(trip_id=trip_id)
    return Trip(id=trip_id, name=f"Trip-{trip_id}", stages=[stage], report_config=cfg)


def _report_request(
    trip: Trip, *, send_sms: bool = False, send_premium_sms: bool = False,
    send_email: bool = True, send_telegram: bool = True,
) -> TripReportRequest:
    return TripReportRequest(
        trip=trip, report_type="evening", segment_weather=[_segment_weather()],
        trip_tz=ZoneInfo("Europe/Paris"), report_config=trip.report_config,
        send_email=send_email, send_sms=send_sms, send_telegram=send_telegram,
        send_premium_sms=send_premium_sms,
    )


# ---------------------------------------------------------------------------
# Amtliche-Warnung-Helfer (Trip- und Compare-Alarm-Pfad)
# ---------------------------------------------------------------------------

_VON = datetime(2026, 7, 11, 15, 0, tzinfo=timezone.utc)
_BIS = datetime(2026, 7, 11, 21, 0, tzinfo=timezone.utc)


def _official_alert() -> OfficialAlert:
    return OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=_VON, valid_to=_BIS, region_label="Kärnten",
    )


def _official_trip(trip_id: str) -> Trip:
    stage = Stage(
        id="s1", name="Tag 1", date=_date(2026, 7, 11),
        waypoints=[Waypoint(id="w1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    return Trip(id=trip_id, name=f"Official-{trip_id}", stages=[stage])


# ---------------------------------------------------------------------------
# AC-1 — Briefing-SMS wird bei erreichtem Briefing-Kontingent gesperrt
# ---------------------------------------------------------------------------


def test_ac1_briefing_sms_wird_bei_erreichtem_briefing_kontingent_gesperrt(mitschrift):
    """AC-1. GIVEN Standard-Nutzer mit sms=8 (Briefing-Cap Standard = 8) /
    WHEN ein 9. Trip-Briefing ausgeloest wird / THEN bleibt die SMS aus
    (``blocked_channels["sms"]``, ``reason_code=sms_daily_limit_exceeded``),
    E-Mail/Telegram desselben Laufs gehen UNVERAENDERT raus, Zaehler bleibt
    bei 8.

    Nachbesserung (PO/Tech-Lead 2026-09-24): "unveraendert" wird NICHT ueber
    einen fest verdrahteten Zaehlwert (``== 1``) geprueft -- wie viele
    Telegram-Bubbles ein rich-Briefing produziert, ist eine
    Telegram-Rendering-Frage, keine SMS-Tageslimit-Frage, und war mit der
    festen Erwartung strukturell nie erreichbar (rich-Style sendet fuer
    diesen Fixture-Trip mehrere Bubbles). Stattdessen ein Kontrolllauf:
    DERSELBE Trip wird fuer eine ZWEITE, eindeutige ``user_id`` mit vollem
    (nicht gesperrtem) SMS-Kontingent versendet -- die Zustellzahlen fuer
    E-Mail/Telegram muessen in beiden Laeufen IDENTISCH sein (und > 0). Das
    beweist "die SMS-Sperre aendert nichts an E-Mail/Telegram", ohne eine
    konkrete, hier irrelevante Bubble-Anzahl vorzuschreiben.
    """
    uid = _kennung("ac1")
    _nutzer_anlegen(uid, "standard")
    _zaehler_schreiben(uid, sms=8)
    trip = _trip(f"trip-{uid}")
    svc = NotificationService(settings=_settings(), user_id=uid)

    ergebnis = svc.send_trip_report(_report_request(trip, send_sms=True))

    assert "sms" in ergebnis.blocked_channels, (
        f"AC-1: 9. Briefing-SMS bei sms=8/Standard (Briefing-Cap 8) muss "
        f"gesperrt sein, blocked_channels={ergebnis.blocked_channels!r}"
    )
    assert ergebnis.blocked_reason_codes.get("sms") == "sms_daily_limit_exceeded", (
        f"AC-1: reason_code fehlt/falsch: {ergebnis.blocked_reason_codes!r}"
    )
    assert mitschrift.anzahl("sms") == 0, (
        f"AC-1: SMS-Aufzeichner darf nicht aufgerufen worden sein, aber "
        f"{mitschrift!r}"
    )
    email_gesperrt = mitschrift.anzahl("email")
    telegram_gesperrt = mitschrift.anzahl("telegram")

    # Kontrolllauf: DERSELBE Trip (identischer Inhalt), freies SMS-Kontingent,
    # zweite eindeutige user_id -- misst E-Mail/Telegram-Zustellung OHNE die
    # SMS-Sperre als Vergleichsbasis.
    uid_kontrolle = _kennung("ac1-kontrolle")
    _nutzer_anlegen(uid_kontrolle, "standard")
    svc_kontrolle = NotificationService(settings=_settings(), user_id=uid_kontrolle)
    svc_kontrolle.send_trip_report(_report_request(trip, send_sms=True))

    email_kontrolle = mitschrift.anzahl("email") - email_gesperrt
    telegram_kontrolle = mitschrift.anzahl("telegram") - telegram_gesperrt

    assert email_kontrolle > 0 and email_gesperrt == email_kontrolle, (
        f"AC-1: E-Mail-Zustellung muss durch die SMS-Sperre unveraendert "
        f"bleiben (gesperrter Lauf={email_gesperrt}, Kontrolllauf="
        f"{email_kontrolle})"
    )
    assert telegram_kontrolle > 0 and telegram_gesperrt == telegram_kontrolle, (
        f"AC-1: Telegram-Zustellung muss durch die SMS-Sperre unveraendert "
        f"bleiben (gesperrter Lauf={telegram_gesperrt}, Kontrolllauf="
        f"{telegram_kontrolle})"
    )
    assert _zaehler_lesen(uid).get("sms") == 8, (
        f"AC-1: Zaehlerstand darf sich bei Sperre nicht aendern, gelesen "
        f"{_zaehler_lesen(uid)!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Alarm-Reserve: 9./10. Alarm-SMS gehen raus, 11. wird gesperrt
# ---------------------------------------------------------------------------


def test_ac2_alarm_reserve_erlaubt_9_und_10_sperrt_die_11(mitschrift):
    """AC-2. GIVEN Standard-Nutzer mit sms=8 (Briefing-Kontingent ausgeschoepft,
    Alarm-Reserve noch offen bis Cap 10) / WHEN drei echte
    ``send_official_alert``-Laeufe nacheinander ausgeloest werden / THEN gehen
    der 9. und 10. Alarm noch heraus (Reserve), der 11. wird gesperrt —
    Zaehler ueberschreitet 10 nie.

    RED heute: kein Gate -> alle drei Laeufe gehen durch, der 3. bleibt
    faelschlich unbeschraenkt.
    """
    uid = _kennung("ac2")
    _nutzer_anlegen(uid, "standard")
    _zaehler_schreiben(uid, sms=8)
    trip = _official_trip(f"trip-{uid}")
    svc = NotificationService(settings=_settings(), user_id=uid)

    e9 = svc.send_official_alert(
        trip=trip, notices=[(_official_alert(), ["1"])], effective_channels={"sms"},
    )
    assert mitschrift.anzahl("sms") == 1, "AC-2: 9. Alarm-SMS (Reserve) muss noch rausgehen"
    assert "sms" not in e9.blocked_channels
    assert _zaehler_lesen(uid).get("sms") == 9, (
        f"AC-2: Zaehler muss nach der 9. SMS auf 9 stehen, gelesen "
        f"{_zaehler_lesen(uid)!r}"
    )

    e10 = svc.send_official_alert(
        trip=trip, notices=[(_official_alert(), ["1"])], effective_channels={"sms"},
    )
    assert mitschrift.anzahl("sms") == 2, "AC-2: 10. Alarm-SMS (volles Alarm-Cap) muss noch rausgehen"
    assert _zaehler_lesen(uid).get("sms") == 10

    e11 = svc.send_official_alert(
        trip=trip, notices=[(_official_alert(), ["1"])], effective_channels={"sms"},
    )
    assert mitschrift.anzahl("sms") == 2, (
        f"AC-2: 11. Alarm-SMS muss gesperrt bleiben, Aufzeichner darf nicht "
        f"weiter wachsen, aber {mitschrift!r}"
    )
    assert "sms" in e11.blocked_channels, f"AC-2: {e11.blocked_channels!r}"
    assert "sms" not in e11.delivered_channels, (
        f"AC-2: ein gesperrter Kanal darf nie in delivered_channels stehen, "
        f"gefunden {e11.delivered_channels!r}"
    )
    assert _zaehler_lesen(uid).get("sms") == 10, "AC-2: Zaehler darf das Cap (10) nie ueberschreiten"


# ---------------------------------------------------------------------------
# AC-3 — getrennte Zaehler fuer SMS und Premium-SMS, beide Richtungen
# ---------------------------------------------------------------------------


def test_ac3_sms_und_premium_sms_fuehren_getrennte_kontingente(mitschrift):
    """AC-3. GIVEN Premium-Nutzer mit sms=10 (Cap erreicht), premium_sms=0 /
    WHEN ein Briefing mit BEIDEN Kanaelen ausgeloest wird / THEN bleibt die
    SMS gesperrt, die Premium-SMS geht trotzdem raus (unabhaengige Toepfe).
    Gegenprobe mit vertauschten Werten zeigt das umgekehrte Bild.
    """
    uid = _kennung("ac3")
    _nutzer_anlegen(uid, "premium")
    _zaehler_schreiben(uid, sms=10, premium_sms=0)
    trip = _trip(f"trip-{uid}")
    svc = NotificationService(settings=_settings(), user_id=uid)

    ergebnis = svc.send_trip_report(
        _report_request(trip, send_sms=True, send_premium_sms=True),
    )

    assert "sms" in ergebnis.blocked_channels, (
        f"AC-3: SMS-Kontingent (10/10) muss die SMS sperren: "
        f"{ergebnis.blocked_channels!r}"
    )
    assert mitschrift.anzahl("premium_sms") == 1, (
        "AC-3: Premium-SMS-Kontingent ist unabhaengig und muss trotzdem "
        "versendet werden"
    )

    # Gegenprobe: vertauschte Werte, zweiter Nutzer.
    uid2 = _kennung("ac3b")
    _nutzer_anlegen(uid2, "premium")
    _zaehler_schreiben(uid2, sms=0, premium_sms=15)
    trip2 = _trip(f"trip-{uid2}")
    svc2 = NotificationService(settings=_settings(), user_id=uid2)

    ergebnis2 = svc2.send_trip_report(
        _report_request(trip2, send_sms=True, send_premium_sms=True),
    )

    assert "premium_sms" in ergebnis2.blocked_channels, (
        f"AC-3 Gegenprobe: Premium-SMS-Kontingent (15/15) muss Premium-SMS "
        f"sperren: {ergebnis2.blocked_channels!r}"
    )
    assert mitschrift.anzahl("sms") == 1, (
        "AC-3 Gegenprobe: SMS-Kontingent ist unabhaengig und muss trotzdem "
        "versendet werden"
    )


# ---------------------------------------------------------------------------
# AC-4 — Garmin-Antwort darf die Reply-Reserve (3/Tag) ausschoepfen
# ---------------------------------------------------------------------------


def test_ac4_garmin_antwort_darf_die_reply_reserve_ausschoepfen(mitschrift):
    """AC-4. GIVEN Premium-Nutzer mit premium_sms=15 (Alarm-Cap erreicht,
    Reply-Cap 18) / WHEN vier echte ``send_command_reply_premium_sms``-Aufrufe
    nacheinander erfolgen / THEN gehen die Antworten 16, 17 und 18 noch raus,
    die 19. (4. Aufruf) wird gesperrt — Assert ausschliesslich ueber die
    Aufzeichner-Trefferzahl (3, nicht 4).
    """
    uid = _kennung("ac4")
    _nutzer_anlegen(uid, "premium")
    _zaehler_schreiben(uid, premium_sms=15)
    svc = NotificationService(settings=_settings(), user_id=uid)
    ergebnis = CommandResult(
        success=True, command="report",
        confirmation_subject="Bestaetigung", confirmation_body="OK",
    )

    for _ in range(4):
        svc.send_command_reply_premium_sms(ergebnis, _settings())

    assert mitschrift.anzahl("premium_sms") == 3, (
        f"AC-4: bei premium_sms=15 (Alarm-Cap) duerfen nur 3 der 4 "
        f"Garmin-Antworten die Reply-Reserve (Cap 18) ausschoepfen und "
        f"tatsaechlich versendet werden, aufgezeichnet wurden "
        f"{mitschrift.anzahl('premium_sms')}"
    )


# ---------------------------------------------------------------------------
# AC-5 — UTC-Mitternachtsreset (Modul-Ebene, injizierte Uhr)
# ---------------------------------------------------------------------------


def test_ac5_utc_mitternacht_setzt_das_tageskontingent_zurueck():
    """AC-5. GIVEN sms=10 (Cap Standard/Alarm) am 2026-09-24 / WHEN um
    23:59:00 UTC desselben Tages reserviert wird / THEN sperrt das Kontingent
    weiterhin. WHEN um 00:00:00 UTC des naechsten Tages reserviert wird /
    THEN ist das volle Kontingent wieder da, der neue Tag startet bei 1.

    RED heute: ``services.sms_daily_limit`` existiert nicht -> ImportError.
    """
    from output.channels.base import ChannelBlockedError
    from services import sms_daily_limit

    uid = _kennung("ac5")
    _nutzer_anlegen(uid, "standard")
    _zaehler_schreiben(uid, sms=10, datum="2026-09-24")

    spaet = datetime(2026, 9, 24, 23, 59, 0, tzinfo=timezone.utc)
    with pytest.raises(ChannelBlockedError):
        sms_daily_limit.check_and_reserve(uid, "sms", "alert", spaet)
    assert _zaehler_lesen(uid).get("sms") == 10, "vor Mitternacht bleibt das Kontingent erschoepft"

    frueh = datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    sms_daily_limit.check_and_reserve(uid, "sms", "alert", frueh)
    nach_reset = _zaehler_lesen(uid)
    assert nach_reset.get("date") == "2026-09-25", (
        f"AC-5: nach UTC-Mitternacht muss das Datum auf den neuen Tag "
        f"weiterlaufen, gelesen {nach_reset!r}"
    )
    assert nach_reset.get("sms") == 1, (
        f"AC-5: die erste Reservierung des neuen Tages muss bei 1 starten, "
        f"gelesen {nach_reset!r}"
    )


def test_ac5_release_reservation_am_tageswechsel_ist_ein_no_op():
    """AC-5 Randfall (Spec 'Known Limitations'): eine Reservierung von GESTERN
    darf beim Release NACH dem Tageswechsel den bereits zurueckgesetzten neuen
    Tag nicht anfassen (No-op, kein Rueckbuchen in den falschen Tag).

    RED heute: ``services.sms_daily_limit`` existiert nicht -> ImportError.
    """
    from services import sms_daily_limit

    uid = _kennung("ac5rel")
    _nutzer_anlegen(uid, "standard")
    _zaehler_schreiben(uid, sms=3, datum="2026-09-24")

    naechster_tag = datetime(2026, 9, 25, 0, 0, 1, tzinfo=timezone.utc)
    sms_daily_limit.release_reservation(uid, "sms", naechster_tag)

    stand = _zaehler_lesen(uid)
    assert stand.get("date") == "2026-09-24" and stand.get("sms") == 3, (
        f"AC-5 Randfall: ein Release nach dem Tageswechsel darf den ALTEN Tag "
        f"nicht anfassen (No-op), gelesen {stand!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 — Mandantentrennung zwischen zwei Nutzern
# ---------------------------------------------------------------------------


def test_ac6_mandantentrennung_zwischen_zwei_nutzern(mitschrift):
    """AC-6. GIVEN zwei Nutzer A/B, A hat sein SMS-Kontingent ausgeschoepft
    (sms=10), B nicht / WHEN beide unabhaengig je eine Alarm-SMS versenden /
    THEN bleibt A gesperrt, B bleibt vollstaendig unberuehrt — eigener
    Zaehlerstand, eigene Obergrenze.
    """
    uid_a, uid_b = _kennung("ac6a"), _kennung("ac6b")
    _nutzer_anlegen(uid_a, "standard")
    _nutzer_anlegen(uid_b, "standard")
    _zaehler_schreiben(uid_a, sms=10)

    trip_a = _official_trip(f"trip-{uid_a}")
    trip_b = _official_trip(f"trip-{uid_b}")
    svc_a = NotificationService(settings=_settings(), user_id=uid_a)
    svc_b = NotificationService(settings=_settings(), user_id=uid_b)

    ergebnis_a = svc_a.send_official_alert(
        trip=trip_a, notices=[(_official_alert(), ["1"])], effective_channels={"sms"},
    )
    ergebnis_b = svc_b.send_official_alert(
        trip=trip_b, notices=[(_official_alert(), ["1"])], effective_channels={"sms"},
    )

    assert "sms" in ergebnis_a.blocked_channels, (
        f"AC-6: Nutzer A muss gesperrt sein (eigenes Kontingent ausgeschoepft): "
        f"{ergebnis_a.blocked_channels!r}"
    )
    assert "sms" not in ergebnis_b.blocked_channels, (
        f"AC-6: Nutzer B darf von A's Sperre unberuehrt bleiben: "
        f"{ergebnis_b.blocked_channels!r}"
    )
    assert mitschrift.anzahl("sms") == 1, (
        f"AC-6: nur Nutzer B's SMS darf tatsaechlich versendet worden sein, "
        f"aber {mitschrift!r}"
    )
    assert _zaehler_lesen(uid_b).get("sms") == 1, "AC-6: Nutzer B fuehrt einen eigenen Zaehlerstand"
    assert _zaehler_lesen(uid_a).get("sms") == 10, "AC-6: Nutzer A's Zaehler bleibt unveraendert"


# ---------------------------------------------------------------------------
# AC-7 — Rollback bei Transportfehler, unveraenderter Zaehler bei Sperre
# ---------------------------------------------------------------------------


def test_ac7_rollback_bei_transportfehler_und_unveraendert_bei_sperre(mitschrift):
    """AC-7. GIVEN sms=5 (unter dem Cap), der Transport schlaegt danach echt
    fehl (Aufzeichner wirft ``RuntimeError``) / WHEN das Briefing endet / THEN
    ist der Zaehlerstand identisch zu vorher (Reservierung zurueckgerollt).
    Zweiter Lauf mit ausgeschoepftem Kontingent (gesperrt statt
    fehlgeschlagen) zeigt denselben unveraenderten Zaehlerstand.
    """
    uid = _kennung("ac7")
    _nutzer_anlegen(uid, "standard")
    _zaehler_schreiben(uid, sms=5)
    trip = _trip(f"trip-{uid}")
    svc = NotificationService(settings=_settings(), user_id=uid)

    mitschrift.fehler["sms"] = RuntimeError("Transport kaputt")
    svc.send_trip_report(_report_request(trip, send_sms=True))

    assert "sms" not in mitschrift.fehler, (
        "AC-7 Vorbedingung: der SMS-Transport muss tatsaechlich versucht "
        "worden sein (Fehler ausgeloest, nicht uebersprungen)"
    )
    assert _zaehler_lesen(uid).get("sms") == 5, (
        f"AC-7: ein fehlgeschlagener Transport muss die Reservierung "
        f"zurueckrollen, Zaehlerstand ist {_zaehler_lesen(uid)!r}, erwartet 5"
    )

    _zaehler_schreiben(uid, sms=8)  # Briefing-Cap Standard erreicht
    ergebnis = svc.send_trip_report(_report_request(trip, send_sms=True))
    assert "sms" in ergebnis.blocked_channels, (
        f"AC-7: bei sms=8 (Briefing-Cap) muss der 2. Lauf gesperrt sein: "
        f"{ergebnis.blocked_channels!r}"
    )
    assert _zaehler_lesen(uid).get("sms") == 8, (
        "AC-7: eine Sperre darf den Zaehler ebenfalls nicht veraendern"
    )


# ---------------------------------------------------------------------------
# AC-8 — REGRESSIONSWAECHTER: bestehendes Alarm-Frequenz-Limit bleibt
# unveraendert wirksam und wird VOR NotificationService angewendet.
# ---------------------------------------------------------------------------


def _wet_frames(lat: float, lon: float) -> list:
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=5.0),
        RadarFrame(timestamp=now + timedelta(minutes=15), precip_mm_h=8.0),
    ]


_ALERT_LAT, _ALERT_LON = 42.20, 9.10  # Korsika, Vorbild test_issue_1070_daily_alert_limit.py


def _alert_trip(trip_id: str) -> Trip:
    from tests.helpers.arrival_window_fixtures import active_window_offsets, stage_date

    arr0, arr1 = active_window_offsets(_ALERT_LAT, _ALERT_LON, -60, 120)
    wp0 = Waypoint(id="WP0", name="Start", lat=_ALERT_LAT, lon=_ALERT_LON,
                   elevation_m=500.0, arrival_calculated=arr0)
    wp1 = Waypoint(id="WP1", name="End", lat=_ALERT_LAT + 0.1, lon=_ALERT_LON + 0.1,
                   elevation_m=600.0, arrival_calculated=arr1)
    stage = Stage(id="S1", name="Tag 1", date=stage_date(_ALERT_LAT, _ALERT_LON),
                  waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name="SMS-Limit AC8", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_sms=True, send_telegram=False,
    )
    return trip


def _save_alert_trip(trip: Trip, uid: str) -> None:
    from app.loader import get_briefings_dir

    trips_dir = get_briefings_dir(uid)
    trips_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": trip.id, "name": trip.name,
        "stages": [
            {
                "id": s.id, "name": s.name, "date": s.date.isoformat(),
                "waypoints": [
                    {
                        "id": w.id, "name": w.name, "lat": w.lat, "lon": w.lon,
                        "elevation_m": w.elevation_m,
                        "arrival_calculated": w.arrival_calculated,
                    }
                    for w in s.waypoints
                ],
            }
            for s in trip.stages
        ],
        "report_config": {
            "trip_id": trip.report_config.trip_id,
            "send_email": trip.report_config.send_email,
            "send_sms": trip.report_config.send_sms,
        },
    }
    (trips_dir / f"{trip.id}.json").write_text(json.dumps(data))


def _seed_alert_daily_counter(uid: str, count: int, zone: ZoneInfo) -> None:
    """Seedet das bestehende Alarm-Frequenz-Limit am Cap.

    ``max_urgency_sent`` wird auf die HOECHSTE Stufe der produktiven Skala
    gesetzt (Vorbild ``test_issue_1070_daily_alert_limit.py::test_ac1_...``):
    ein fehlender Eintrag gilt sonst als "LOW", und JEDE echte Dringlichkeit
    des Radar-Alarms wuerde das erschoepfte Budget als Eskalations-Durchbruch
    (#2050 S3b) ueberholen — dann wuerde dieser Test faelschlich einen
    Versand sehen, der nichts mit dem SMS-Tageslimit zu tun hat.
    """
    from services import alert_urgency

    today = datetime.now(timezone.utc).astimezone(zone).date().isoformat()
    path = get_data_dir(uid) / "alert_daily_count.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    hoechste = alert_urgency.highest_urgency("LOW", "MODERATE", "HIGH")
    path.write_text(json.dumps({"zones": {str(zone): {
        "date": today, "count": count, "max_urgency_sent": hoechste,
    }}}))


def test_ac8_bestehendes_alarm_frequenz_limit_bleibt_unveraendert_wirksam(mitschrift):
    """AC-8 — REGRESSIONSWAECHTER, heute bereits GRUEN und muss es bleiben.

    GIVEN ein Free-Nutzer hat das bestehende Alarm-Frequenz-Limit
    (``alert_daily_limit.py``, Free-Cap 2) bereits ausgeschoepft, BEVOR
    ``NotificationService`` ueberhaupt erreicht wird / WHEN ein faelliger
    Radar-Alarm ausgeloest wird / THEN bleibt der Versand unveraendert aus
    (kein E-Mail-/SMS-Aufzeichner-Treffer) UND ``sms_daily_count.json`` bleibt
    unangelegt — das neue SMS-Tageslimit darf an diesem VORGESCHALTETEN Gate
    nichts aendern (Spec 'Reihenfolge gegenueber dem bestehenden
    Alarm-Frequenz-Limit').
    """
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService
    from utils.timezone import tz_for_coords

    uid = _kennung("ac8")
    _nutzer_anlegen(uid, "free")
    zone = tz_for_coords(_ALERT_LAT, _ALERT_LON)
    _seed_alert_daily_counter(uid, 2, zone)  # Free-Limit bereits ausgeschoepft

    trip = _alert_trip(f"trip-{uid}")
    _save_alert_trip(trip, uid)

    svc = TripAlertService(
        settings=_settings(), throttle_hours=0, user_id=uid,
        radar_service=RadarNowcastService(frame_source=_wet_frames),
    )
    result = svc.check_radar_alerts()

    assert result == 0, "Vorbedingung: Alarm-Frequenz-Limit muss den Radar-Alarm unterdruecken"
    assert mitschrift.anzahl("email") == 0 and mitschrift.anzahl("sms") == 0, (
        f"AC-8: bei ausgeschoepftem Alarm-Frequenz-Limit darf "
        f"NotificationService gar nicht erst erreicht werden, aber {mitschrift!r}"
    )
    assert not _zaehler_pfad(uid).exists(), (
        "AC-8: sms_daily_count.json darf nicht entstehen, wenn der Alarm "
        "schon vor NotificationService unterdrueckt wird"
    )


# ---------------------------------------------------------------------------
# AC-9 — Nebenlaeufigkeit: zwei gleichzeitige Reservierungen am Limit
# ---------------------------------------------------------------------------


def test_ac9_zwei_gleichzeitige_reservierungen_am_limit_ueberschreiten_das_cap_nie():
    """AC-9. GIVEN sms=9 (cap-1, Standard/Alarm-Cap 10) / WHEN zwei echte
    Threads gleichzeitig ``check_and_reserve`` aufrufen (reales
    ``fcntl``-Locking ueber die Sidecar-Lockdatei, kein Mock) / THEN reserviert
    genau EINER erfolgreich, der andere bekommt eine ``ChannelBlockedError`` —
    der Endstand ueberschreitet 10 nie.

    RED heute: ``services.sms_daily_limit`` existiert nicht -> ImportError.
    """
    from output.channels.base import ChannelBlockedError
    from services import sms_daily_limit

    uid = _kennung("ac9")
    _nutzer_anlegen(uid, "standard")
    _zaehler_schreiben(uid, sms=9)

    barrier = threading.Barrier(2)
    ergebnisse: list[str] = []
    fehler: list[str] = []
    lock = threading.Lock()

    def _worker() -> None:
        barrier.wait()
        now = datetime.now(timezone.utc)
        try:
            sms_daily_limit.check_and_reserve(uid, "sms", "alert", now)
            with lock:
                ergebnisse.append("ok")
        except ChannelBlockedError:
            with lock:
                fehler.append("blocked")

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert len(ergebnisse) == 1 and len(fehler) == 1, (
        f"AC-9: von zwei gleichzeitigen Reservierungen am Limit muss GENAU "
        f"EINE erfolgreich sein und GENAU EINE eine ChannelBlockedError "
        f"erhalten, erhalten ok={ergebnisse!r} blocked={fehler!r}"
    )
    endstand = _zaehler_lesen(uid).get("sms")
    assert endstand == 10, (
        f"AC-9: der Endstand darf das Cap (10) nie ueberschreiten, gelesen "
        f"{endstand!r}"
    )


# ---------------------------------------------------------------------------
# AC-10 — jede der uebrigen Sendestellen wird bei erreichtem Kontingent
# gesperrt (Radar, Ortsvergleichs-Briefing, Ortsvergleichs-Amtswarnung,
# Keine-Daten-Hinweis)
# ---------------------------------------------------------------------------

_AC10_FAELLE = [
    "radar_sms", "radar_premium_sms",
    "compare_briefing_sms",
    "compare_official_sms", "compare_official_premium_sms",
    "no_data_hint_sms", "no_data_hint_premium_sms",
    # Nachbesserung (Tech-Lead 2026-09-24): der Premium-SMS-Zweig von
    # send_official_alert (notification_service.py ~1155) war bislang durch
    # KEINEN Test aus dieser Datei bewacht -- AC-2 deckt dort nur SMS ab.
    "official_alert_premium_sms",
]


@pytest.mark.parametrize("fall", _AC10_FAELLE)
def test_ac10_jede_uebrige_sendestelle_wird_bei_erreichtem_kontingent_gesperrt(
    fall, mitschrift,
):
    """AC-10. GIVEN ein Nutzer, dessen Tageszaehler fuer den jeweiligen Kanal
    voll ist / WHEN ueber JEDE der uebrigen Sendestellen (Radar,
    Ortsvergleichs-Briefing, Ortsvergleichs-Amtswarnung, Keine-Daten-Hinweis;
    SMS und/oder Premium-SMS) ein Versand ausgeloest wird / THEN geht an
    keiner dieser Stellen eine SMS/Premium-SMS hinaus, der Kanal steht mit
    Sperrgrund im Ergebnis, E-Mail desselben Versands geht trotzdem raus.

    Zusammen mit AC-1/AC-2/AC-4 ist damit jede der 12 Sendestellen aus der
    Spec-Tabelle 'Sendestellen' durch mindestens einen Test bewacht.
    """
    uid = _kennung(f"ac10{abs(hash(fall)) % 100000}")
    kanal = "premium_sms" if fall.endswith("premium_sms") else "sms"
    tier = "premium" if kanal == "premium_sms" else "standard"
    _nutzer_anlegen(uid, tier)
    if kanal == "sms":
        _zaehler_schreiben(uid, sms=10)  # Alarm-Cap Standard/Premium erreicht
    else:
        _zaehler_schreiben(uid, premium_sms=15)  # Alarm-Cap Premium erreicht

    svc = NotificationService(settings=_settings(), user_id=uid)

    if fall in ("radar_sms", "radar_premium_sms"):
        trip = _official_trip(f"trip-{uid}")
        request = RadarAlertRequest(
            onset_minutes=15, onset_time="12:00", km_from=0.0, km_to=3.0,
            is_convective=False, intensity_label="Regen",
            source_label="Radar (DWD)", tz=ZoneInfo("UTC"), segment_id="1",
        )
        ergebnis = svc.send_radar_alert(
            trip=trip, request=request, source="Radar (DWD)",
            cooldown_display="1 Stunde", effective_channels={"email", kanal},
        )
    elif fall == "official_alert_premium_sms":
        trip = _official_trip(f"trip-{uid}")
        ergebnis = svc.send_official_alert(
            trip=trip, notices=[(_official_alert(), ["1"])],
            effective_channels={"email", "premium_sms"},
        )
    elif fall == "compare_briefing_sms":
        ergebnis = svc.send_compare_report(
            subject="Ortsvergleich", html_body="<p>H</p>", text_body="T",
            telegram_text="TG", sms_text="SMS", recipients=["to@example.invalid"],
            effective_channels={"email", "sms"},
        )
    elif fall in ("compare_official_sms", "compare_official_premium_sms"):
        loc = SavedLocation(id=f"loc-{uid}", name="Ort", lat=47.0, lon=11.0, elevation_m=1000)
        ergebnis = svc.send_multi_location_official_alert(
            "AC10 Compare", [loc], [(_official_alert(), [f"loc-{uid}"])],
            {"email", kanal},
        )
    else:  # no_data_hint_sms / no_data_hint_premium_sms
        trip = _trip(f"trip-{uid}")
        ergebnis = svc.send_no_data_hint(
            trip, "morning", send_email=True,
            send_sms=(kanal == "sms"), send_premium_sms=(kanal == "premium_sms"),
        )

    assert mitschrift.anzahl(kanal) == 0, (
        f"AC-10 ({fall}): {kanal} darf bei ausgeschoepftem Kontingent NICHT "
        f"aufgerufen werden, aufgezeichnet wurden {mitschrift.anzahl(kanal)}"
    )
    assert mitschrift.anzahl("email") == 1, (
        f"AC-10 ({fall}): E-Mail desselben Versands muss trotzdem zugestellt "
        f"werden, aber {mitschrift!r}"
    )
    blocked = getattr(ergebnis, "blocked_channels", {})
    failed = getattr(ergebnis, "failed_channels", [])
    assert kanal in blocked or kanal in failed, (
        f"AC-10 ({fall}): der Sperrgrund muss im Ergebnis sichtbar sein "
        f"(blocked_channels ODER failed_channels beim Ortsvergleichs-Helfer), "
        f"blocked={blocked!r} failed={failed!r}"
    )


# ---------------------------------------------------------------------------
# Adversary Fix-Loop 1 (2026-09-24) — F001..F006
# ---------------------------------------------------------------------------


def _fremder_wert_im_zaehlerfeld(uid: str) -> None:
    pfad = _zaehler_pfad(uid)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"date": _heute_utc(), "sms": "abc", "premium_sms": 0}))


def _nicht_json_zaehlerdatei(uid: str) -> None:
    pfad = _zaehler_pfad(uid)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("DAS IST KEIN JSON {{{")


def _unendlicher_zaehlerwert(uid: str) -> None:
    """Adversary F001c: `1e400` wird von Python/JSON als `inf` geparst --
    `int(inf)` wirft `OverflowError`, NICHT `ValueError`."""
    pfad = _zaehler_pfad(uid)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"date": _heute_utc(), "sms": 1e400, "premium_sms": 0}))


def _user_json_als_liste(uid: str) -> None:
    """Adversary F001b: gueltiges JSON, aber KEIN Objekt -- `profile.get(...)`
    auf einer Liste wirft `AttributeError`."""
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps(["standard"]))


def _user_json_als_skalar(uid: str) -> None:
    """Adversary F001b: gueltiges JSON, aber ein Skalar -- `profile.get(...)`
    auf einer Zahl wirft ebenfalls `AttributeError`."""
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps(42))


def _user_json_tier_liste(uid: str) -> None:
    """Adversary F009: ein VALIDES Dict-`user.json`, aber der `tier`-WERT
    selbst ist kein String -- ungeprueft in `_DAILY_SMS_LIMIT.get(...)`
    waere eine Liste `unhashable` (`TypeError`)."""
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"tier": ["hack"]}))


def _user_json_tier_zahl(uid: str) -> None:
    """Adversary F009: `tier` ist eine Zahl statt eines Strings."""
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"tier": 42}))


def _user_json_tier_unbekannt(uid: str) -> None:
    """Adversary F009: `tier` ist ein String, aber kein bekannter Tier-Wert."""
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"tier": "gold"}))


@pytest.mark.parametrize(
    "kaputt_machen, sms_erwartet",
    [
        (_fremder_wert_im_zaehlerfeld, True),
        (_nicht_json_zaehlerdatei, True),
        (_unendlicher_zaehlerwert, True),
        (_user_json_als_liste, False),
        (_user_json_als_skalar, False),
        (_user_json_tier_liste, False),
        (_user_json_tier_zahl, False),
        (_user_json_tier_unbekannt, False),
    ],
    ids=[
        "fremder-wert-im-feld",
        "nicht-json",
        "unendlicher-zaehlerwert-f001c",
        "user-json-als-liste-f001b",
        "user-json-als-skalar-f001b",
        "tier-liste-f009",
        "tier-zahl-f009",
        "tier-unbekannt-f009",
    ],
)
def test_f001_kaputte_zaehlerdatei_ist_fail_open(kaputt_machen, sms_erwartet, mitschrift):
    """Adversary F001/F001b/F001c (CRITICAL/CRITICAL/MEDIUM). GIVEN eine
    kaputte `sms_daily_count.json` (fremder Wertetyp, kein gueltiges JSON,
    oder ein Zaehlerwert, der als `inf` geparst wird -- F001/F001c) ODER
    eine `user.json`, die zwar gueltiges JSON, aber KEIN Objekt ist (Liste
    oder Skalar -- F001b) / WHEN ein echtes Trip-Briefing ausgeloest wird /
    THEN wirft das Gate NICHT (sonst erreicht E-Mail den Nutzer, Telegram
    NIE -- die Ausnahme bricht `send_trip_report` vor dessen Versandbloecken
    ab, der Scheduler haelt den Lauf faelschlich fuer einen Totalausfall und
    liefert doppelt nach).

    Zwei unterschiedliche, beide BEABSICHTIGTE Ergebnisse (kein Widerspruch):
    - F001/F001c (Zaehlerdatei-Korruption): fail-OPEN -- der kaputte
      Zaehlerwert gilt als leerer Tagesstand (0), SMS wird versendet.
    - F001b/F009 (user.json ist kein Objekt ODER `tier` ist kein bekannter
      Tier-String -- Liste, Zahl, unbekannter String wie "gold"): der
      TIER-Lookup faellt bewusst fail-CLOSED auf "free" zurueck (identisch
      zum bestehenden Verhalten bei fehlender/kaputter user.json, NUR die
      neue Wurfquelle ist geschlossen) -- SMS bleibt fuer einen free-Nutzer
      legitim gesperrt (Cap 0), aber OHNE Absturz. E-Mail/Telegram sind in
      JEDEM Fall unberuehrt.
    """
    uid = _kennung("f001")
    _nutzer_anlegen(uid, "standard")
    kaputt_machen(uid)
    trip = _trip(f"trip-{uid}")
    svc = NotificationService(settings=_settings(), user_id=uid)

    ergebnis = svc.send_trip_report(_report_request(trip, send_sms=True))

    assert mitschrift.anzahl("email") == 1, (
        "F001: E-Mail muss trotz kaputter Daten zugestellt werden"
    )
    assert mitschrift.anzahl("telegram") >= 1, (
        "F001: Telegram muss trotz kaputter Daten zugestellt werden"
    )
    if sms_erwartet:
        assert mitschrift.anzahl("sms") == 1, (
            f"F001: SMS muss trotz kaputter Zaehlerdatei versendet werden "
            f"(fail-open), aufgezeichnet: {mitschrift.anzahl('sms')}"
        )
        assert "sms" not in ergebnis.blocked_channels, (
            f"F001: kein Sperrgrund erwartet, {ergebnis.blocked_channels!r}"
        )
    else:
        assert mitschrift.anzahl("sms") == 0, (
            f"F001b: kaputte user.json (kein Objekt) muss fail-CLOSED auf "
            f"Tier 'free' zurueckfallen (SMS-Cap 0) -- legitim gesperrt, "
            f"kein Absturz. Aufgezeichnet: {mitschrift.anzahl('sms')}"
        )
        assert "sms" in ergebnis.blocked_channels, (
            f"F001b: Sperrgrund erwartet, {ergebnis.blocked_channels!r}"
        )


@pytest.mark.parametrize("fall", ["radar_sms", "official_alert_premium_sms"])
def test_f002_rollback_bei_transportfehler_an_weiteren_sendestellen(fall, mitschrift):
    """Adversary F002 (MEDIUM). Erweiterung von AC-7 (die nur den
    Rollback-Zweig von `send_trip_report`/SMS bewachte) auf zwei weitere
    Sendestellen: Radar-SMS (`_dispatch_alert_message`) und den
    Premium-SMS-Zweig von `send_official_alert`. GIVEN ein Zaehlerstand
    unter dem Cap, der Transport schlaegt danach echt fehl / WHEN der
    Versand endet / THEN ist der Zaehlerstand identisch zu vorher
    (Reservierung zurueckgerollt) -- fehlt `release_reservation` an einer
    dieser Stellen, bliebe der Zaehler faelschlich erhoeht.
    """
    uid = _kennung(f"f002{fall}")
    kanal = "premium_sms" if fall == "official_alert_premium_sms" else "sms"
    tier = "premium" if kanal == "premium_sms" else "standard"
    _nutzer_anlegen(uid, tier)
    _zaehler_schreiben(uid, **{kanal: 5})
    trip = _official_trip(f"trip-{uid}")
    svc = NotificationService(settings=_settings(), user_id=uid)
    mitschrift.fehler[kanal] = RuntimeError("Transport kaputt")

    if fall == "radar_sms":
        request = RadarAlertRequest(
            onset_minutes=15, onset_time="12:00", km_from=0.0, km_to=3.0,
            is_convective=False, intensity_label="Regen",
            source_label="Radar (DWD)", tz=ZoneInfo("UTC"), segment_id="1",
        )
        svc.send_radar_alert(
            trip=trip, request=request, source="Radar (DWD)",
            cooldown_display="1 Stunde", effective_channels={kanal},
        )
    else:  # official_alert_premium_sms
        svc.send_official_alert(
            trip=trip, notices=[(_official_alert(), ["1"])],
            effective_channels={kanal},
        )

    assert kanal not in mitschrift.fehler, (
        f"F002 ({fall}) Vorbedingung: der Transport muss tatsaechlich "
        f"versucht worden sein (Fehler ausgeloest, nicht uebersprungen)"
    )
    assert _zaehler_lesen(uid).get(kanal) == 5, (
        f"F002 ({fall}): ein fehlgeschlagener Transport muss die "
        f"Reservierung zurueckrollen, Zaehlerstand ist "
        f"{_zaehler_lesen(uid)!r}, erwartet 5"
    )


def test_f003_premium_sms_alarm_reserve_erlaubt_13_bis_15_sperrt_16(mitschrift):
    """Adversary F003 (MEDIUM). AC-2 bewachte die Alarm-Reserve nur fuer den
    Kanal SMS -- `PREMIUM_SMS_ALARM_RESERVE` (Cap 15, Briefing-Cap 12) blieb
    unbewacht, ein Tippfehler 3->0 waere unbemerkt geblieben.

    Teil A: GIVEN premium_sms=12 (Briefing-Cap erreicht) / WHEN ein
    Trip-Briefing ausgeloest wird / THEN bleibt die Premium-SMS gesperrt.
    Teil B: GIVEN premium_sms=12 (Briefing-Cap erreicht, Alarm-Reserve noch
    offen bis Cap 15) / WHEN drei echte `send_official_alert`-Laeufe
    nacheinander ausgeloest werden / THEN gehen der 13., 14. und 15. Alarm
    noch heraus (Reserve), der 16. wird gesperrt.
    """
    # Teil A — Briefing bei Briefing-Cap (12) gesperrt.
    uid_briefing = _kennung("f003-briefing")
    _nutzer_anlegen(uid_briefing, "premium")
    _zaehler_schreiben(uid_briefing, premium_sms=12)
    trip_briefing = _trip(f"trip-{uid_briefing}")
    svc_briefing = NotificationService(settings=_settings(), user_id=uid_briefing)
    ergebnis_briefing = svc_briefing.send_trip_report(
        _report_request(trip_briefing, send_premium_sms=True),
    )
    assert "premium_sms" in ergebnis_briefing.blocked_channels, (
        f"F003 Teil A: 13. Briefing-Premium-SMS bei premium_sms=12 "
        f"(Briefing-Cap) muss gesperrt sein: "
        f"{ergebnis_briefing.blocked_channels!r}"
    )
    assert mitschrift.anzahl("premium_sms") == 0

    # Teil B — Alarm-Reserve 13..15 geht raus, 16 gesperrt.
    uid = _kennung("f003-alarm")
    _nutzer_anlegen(uid, "premium")
    _zaehler_schreiben(uid, premium_sms=12)
    trip = _official_trip(f"trip-{uid}")
    svc = NotificationService(settings=_settings(), user_id=uid)

    e13 = svc.send_official_alert(
        trip=trip, notices=[(_official_alert(), ["1"])],
        effective_channels={"premium_sms"},
    )
    assert mitschrift.anzahl("premium_sms") == 1, "F003 Teil B: 13. Alarm-Premium-SMS (Reserve) muss rausgehen"
    assert "premium_sms" not in e13.blocked_channels
    assert _zaehler_lesen(uid).get("premium_sms") == 13

    e14 = svc.send_official_alert(
        trip=trip, notices=[(_official_alert(), ["1"])],
        effective_channels={"premium_sms"},
    )
    assert mitschrift.anzahl("premium_sms") == 2, "F003 Teil B: 14. Alarm-Premium-SMS muss rausgehen"
    assert _zaehler_lesen(uid).get("premium_sms") == 14

    e15 = svc.send_official_alert(
        trip=trip, notices=[(_official_alert(), ["1"])],
        effective_channels={"premium_sms"},
    )
    assert mitschrift.anzahl("premium_sms") == 3, "F003 Teil B: 15. Alarm-Premium-SMS (volles Cap) muss rausgehen"
    assert _zaehler_lesen(uid).get("premium_sms") == 15

    e16 = svc.send_official_alert(
        trip=trip, notices=[(_official_alert(), ["1"])],
        effective_channels={"premium_sms"},
    )
    assert mitschrift.anzahl("premium_sms") == 3, (
        f"F003 Teil B: 16. Alarm-Premium-SMS muss gesperrt bleiben, "
        f"aufgezeichnet: {mitschrift.anzahl('premium_sms')}"
    )
    assert "premium_sms" in e16.blocked_channels, f"F003 Teil B: {e16.blocked_channels!r}"
    assert _zaehler_lesen(uid).get("premium_sms") == 15, (
        "F003 Teil B: Zaehler darf das Cap (15) nie ueberschreiten"
    )


_F004_ALERT_STELLEN = [
    "radar_sms", "radar_premium_sms",
    "compare_official_sms", "compare_official_premium_sms",
    "official_alert_sms", "official_alert_premium_sms",
]


@pytest.mark.parametrize("fall", _F004_ALERT_STELLEN)
def test_f004_alert_stellen_zaehlen_mit_alarm_cap_nicht_briefing_cap(fall, mitschrift):
    """Adversary F004 (MEDIUM). Ein Zweck-Flip `purpose="alert"` ->
    `purpose="briefing"` an einer Alarm-Sendestelle bliebe unbemerkt, weil
    AC-2/AC-3/AC-10 exakt auf dem ALARM-Cap seeden. Hier wird stattdessen
    exakt auf dem BRIEFING-Cap geseedet (8 SMS / 12 Premium-SMS) -- ist die
    Stelle korrekt mit `purpose="alert"` verdrahtet, MUSS der Versand trotz
    erreichtem Briefing-Cap noch durchgehen (Alarm-Cap 10/15 ist hoeher).
    Deckt alle sechs Alarm-Sendestellen ab: Radar (SMS/Premium),
    Ortsvergleichs-Amtswarnung (SMS/Premium), `send_official_alert`
    (SMS/Premium).
    """
    uid = _kennung(f"f004{fall}")
    kanal = "premium_sms" if fall.endswith("premium_sms") else "sms"
    tier = "premium" if kanal == "premium_sms" else "standard"
    _nutzer_anlegen(uid, tier)
    briefing_cap = 8 if kanal == "sms" else 12
    _zaehler_schreiben(uid, **{kanal: briefing_cap})

    svc = NotificationService(settings=_settings(), user_id=uid)
    trip = _official_trip(f"trip-{uid}")

    if fall in ("radar_sms", "radar_premium_sms"):
        request = RadarAlertRequest(
            onset_minutes=15, onset_time="12:00", km_from=0.0, km_to=3.0,
            is_convective=False, intensity_label="Regen",
            source_label="Radar (DWD)", tz=ZoneInfo("UTC"), segment_id="1",
        )
        svc.send_radar_alert(
            trip=trip, request=request, source="Radar (DWD)",
            cooldown_display="1 Stunde", effective_channels={kanal},
        )
    elif fall in ("compare_official_sms", "compare_official_premium_sms"):
        loc = SavedLocation(id=f"loc-{uid}", name="Ort", lat=47.0, lon=11.0, elevation_m=1000)
        svc.send_multi_location_official_alert(
            "F004 Compare", [loc], [(_official_alert(), [f"loc-{uid}"])], {kanal},
        )
    else:  # official_alert_sms / official_alert_premium_sms
        svc.send_official_alert(
            trip=trip, notices=[(_official_alert(), ["1"])], effective_channels={kanal},
        )

    assert mitschrift.anzahl(kanal) == 1, (
        f"F004 ({fall}): bei Stand=Briefing-Cap ({briefing_cap}) MUSS der "
        f"Alarm-Versand trotzdem durchgehen (Alarm-Cap ist hoeher) -- "
        f"sonst zaehlt diese Stelle faelschlich mit purpose='briefing'. "
        f"Aufgezeichnet: {mitschrift.anzahl(kanal)}"
    )
    assert _zaehler_lesen(uid).get(kanal) == briefing_cap + 1, (
        f"F004 ({fall}): Zaehler muss auf {briefing_cap + 1} stehen, "
        f"gelesen {_zaehler_lesen(uid)!r}"
    )


def test_f005_vienna_zeit_kurz_nach_mitternacht_zaehlt_noch_zum_utc_vortag():
    """Adversary F005 (LOW). `to_utc()` in `sms_daily_limit._today()` wurde
    bislang nie mit einer NICHT-UTC-aware Zeit ausgefuehrt -- ein stiller
    Rueckfall auf `now.date()` (ohne UTC-Umrechnung) waere unbemerkt
    geblieben. Vienna 00:30 CET (15.1.) liegt noch im UTC-VORTAG (23:30 UTC
    am 14.1., CET = UTC+1 im Winter) -- der Zaehler des UTC-Vortags muss
    weiterhin gelten, kein stiller Reset auf einen "neuen" Tag.
    """
    from output.channels.base import ChannelBlockedError
    from services import sms_daily_limit

    uid = _kennung("f005")
    _nutzer_anlegen(uid, "standard")
    _zaehler_schreiben(uid, sms=10, datum="2026-01-14")

    vienna_kurz_nach_mitternacht = datetime(
        2026, 1, 15, 0, 30, tzinfo=ZoneInfo("Europe/Vienna"),
    )

    with pytest.raises(ChannelBlockedError):
        sms_daily_limit.check_and_reserve(
            uid, "sms", "alert", vienna_kurz_nach_mitternacht,
        )
    stand = _zaehler_lesen(uid)
    assert stand.get("date") == "2026-01-14", (
        f"F005: der UTC-Vortag muss weiterhin als 'heute' gelten (Vienna "
        f"00:30 CET = 23:30 UTC des Vortags), gelesen {stand!r}"
    )
    assert stand.get("sms") == 10, "F005: eine Sperre darf den Zaehler nicht veraendern"


def test_f006_standard_nutzer_bekommt_keine_garmin_antwort_per_premium_sms(mitschrift):
    """Adversary F006 (LOW). Ein Standard-Nutzer hat KEIN Premium-SMS-
    Kontingent (Reply-Cap 0) -- die erste Garmin-Antwort muss bereits
    gesperrt sein, nicht erst nach einer Zusatzmenge."""
    uid = _kennung("f006")
    _nutzer_anlegen(uid, "standard")
    svc = NotificationService(settings=_settings(), user_id=uid)
    ergebnis = CommandResult(
        success=True, command="report",
        confirmation_subject="Bestaetigung", confirmation_body="OK",
    )

    svc.send_command_reply_premium_sms(ergebnis, _settings())

    assert mitschrift.anzahl("premium_sms") == 0, (
        f"F006: Standard-Nutzer darf KEINE Garmin-Antwort per Premium-SMS "
        f"erhalten (Reply-Cap 0), aufgezeichnet: "
        f"{mitschrift.anzahl('premium_sms')}"
    )


# ---------------------------------------------------------------------------
# Adversary Fix-Loop 2 (2026-09-24) — F001b, F001c (oben, Parametrisierung
# von test_f001), F008
# ---------------------------------------------------------------------------


_LOCK_SUFFIX_TESTKONST = ".lock"


def test_f008_dauerhafter_oeffnungs_oder_schreibfehler_ist_fail_open(mitschrift, caplog):
    """Adversary F008 (LOW). Die drei OSError-Fail-Open-Stellen in
    ``sms_daily_limit`` -- Sperrdatei oeffnen, ``_write`` in
    ``check_and_reserve``, ``_write`` in ``release_reservation`` -- waren
    bislang durch KEINEN Test bewacht.

    Bewusste Design-Entscheidung (F007, aus Fix-Loop 1, NICHT zu aendern):
    ein DAUERHAFTER Schreib-/Oeffnungsfehler setzt das Tageslimit bewusst
    ausser Kraft -- Zustellung geht vor Zaehltreue, exakt wie beim
    bestehenden Lock-Timeout-Fail-Open (``throttle_store.py``/
    ``forecast_budget.py``-Muster). Erwartet in allen drei Faellen: kein
    Wurf, der Versand geht durch, eine WARNING wird geloggt.
    """
    import logging

    from services import sms_daily_limit as sdl

    caplog.set_level(logging.WARNING, logger="sms_daily_limit")

    # --- Szenario A: Sperrdatei laesst sich nicht oeffnen -------------------
    uid_a = _kennung("f008a")
    _nutzer_anlegen(uid_a, "standard")
    echtes_open = sdl.os.open

    def _kaputtes_open(pfad, *args, **kwargs):
        if str(pfad).endswith(_LOCK_SUFFIX_TESTKONST):
            raise OSError("Simulierter Oeffnungsfehler (F008 Szenario A)")
        return echtes_open(pfad, *args, **kwargs)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(sdl.os, "open", _kaputtes_open)
        svc_a = NotificationService(settings=_settings(), user_id=uid_a)
        trip_a = _trip(f"trip-{uid_a}")
        caplog.clear()
        svc_a.send_trip_report(_report_request(trip_a, send_sms=True))

    assert mitschrift.anzahl("sms") == 1, (
        "F008 (Sperrdatei-Oeffnungsfehler): SMS muss trotzdem versendet "
        "werden (fail-open)"
    )
    assert "nicht erreichbar" in caplog.text, (
        f"F008 (Sperrdatei-Oeffnungsfehler): WARNING erwartet, geloggt: "
        f"{caplog.text!r}"
    )

    # --- Szenario B: Schreibfehler beim Reservieren (check_and_reserve) ----
    uid_b = _kennung("f008b")
    _nutzer_anlegen(uid_b, "standard")

    def _write_immer_kaputt(pfad, daten):
        raise OSError("Simulierter Schreibfehler (F008 Szenario B)")

    with pytest.MonkeyPatch.context() as m:
        m.setattr(sdl, "_write", _write_immer_kaputt)
        svc_b = NotificationService(settings=_settings(), user_id=uid_b)
        trip_b = _trip(f"trip-{uid_b}")
        caplog.clear()
        svc_b.send_trip_report(_report_request(trip_b, send_sms=True))

    assert mitschrift.anzahl("sms") == 2, (
        "F008 (Reservierungs-Schreibfehler): SMS muss trotzdem versendet "
        "werden (fail-open)"
    )
    assert "Schreiben von" in caplog.text, (
        f"F008 (Reservierungs-Schreibfehler): WARNING erwartet, geloggt: "
        f"{caplog.text!r}"
    )

    # --- Szenario C: Schreibfehler beim Rollback (release_reservation) -----
    # Der eigentliche Transport schlaegt bewusst fehl (Aufzeichner wirft),
    # damit der Rollback-Zweig ueberhaupt erreicht wird. NUR der ZWEITE
    # `_write`-Aufruf (der Rollback) wird kaputt gemacht -- der erste (die
    # Reservierung) bleibt echt, sonst waere Szenario C nicht von B zu
    # unterscheiden.
    uid_c = _kennung("f008c")
    _nutzer_anlegen(uid_c, "standard")
    echtes_write = sdl._write
    aufrufe = {"n": 0}

    def _zweiter_write_kaputt(pfad, daten):
        aufrufe["n"] += 1
        if aufrufe["n"] >= 2:
            raise OSError("Simulierter Rollback-Schreibfehler (F008 Szenario C)")
        return echtes_write(pfad, daten)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(sdl, "_write", _zweiter_write_kaputt)
        svc_c = NotificationService(settings=_settings(), user_id=uid_c)
        trip_c = _trip(f"trip-{uid_c}")
        mitschrift.fehler["sms"] = RuntimeError("Transport kaputt (F008 Szenario C)")
        caplog.clear()
        svc_c.send_trip_report(_report_request(trip_c, send_sms=True))  # darf NICHT werfen

    assert "sms" not in mitschrift.fehler, (
        "F008 (Rollback-Schreibfehler) Vorbedingung: der Transport muss "
        "tatsaechlich versucht worden sein"
    )
    assert "Rollback-Schreiben" in caplog.text, (
        f"F008 (Rollback-Schreibfehler): WARNING erwartet, geloggt: "
        f"{caplog.text!r}"
    )


def test_f009a_tier_validierung_faellt_fail_closed_auf_free_zurueck():
    """Adversary F009 (CRITICAL), Teil (a) -- direkter Nachweis auf
    Modul-Ebene (``user_tier``), NICHT ueber ``send_trip_report``: dort
    wuerde der zusaetzliche Fail-Closed-Fang in
    ``sms_daily_limit.check_and_reserve`` (Teil (b) derselben Finding) den
    unvalidierten Wert OHNEHIN abfangen (cap=0) und das Ergebnis am Ende
    NICHT von einer echten Validierung unterscheidbar machen -- deshalb
    bewacht dieser Test GEZIELT die ``_tier()``-Validierung selbst,
    unabhaengig von der zweiten Fangstelle. GIVEN ``user.json`` enthaelt
    ``{"tier": ["hack"]}`` (gueltiges Dict, aber der Tier-WERT ist kein
    String) / WHEN ``_tier()``/``sms_allowed()``/``premium_sms_allowed()``/
    ``daily_alert_limit()`` aufgerufen werden / THEN faellt jede Funktion
    fail-CLOSED auf die free-Werte zurueck, kein Wurf.
    """
    from services import user_tier

    uid = _kennung("f009a")
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"tier": ["hack"]}))

    assert user_tier._tier(uid) == "free", (
        f"F009a: ein Tier-Wert, der kein bekannter String ist, muss auf "
        f"'free' zurueckfallen, erhalten {user_tier._tier(uid)!r}"
    )
    assert user_tier.sms_allowed(uid) is False, "F009a: sms_allowed muss free-Default liefern"
    assert user_tier.premium_sms_allowed(uid) is False, (
        "F009a: premium_sms_allowed muss free-Default liefern"
    )
    assert user_tier.daily_alert_limit(uid) == 2, (
        "F009a: daily_alert_limit muss das free-Default (2) liefern"
    )


def test_f009b_werfender_tier_lookup_ist_fail_closed(mitschrift):
    """Adversary F009 (CRITICAL), Teil (b). GIVEN der Tier-/Cap-Lookup
    (``sms_daily_limit._cap``) wirft aus einem beliebigen Grund (hier per
    Monkeypatch gezielt simuliert, unabhaengig von einer konkreten
    Dateninkonsistenz) / WHEN ein echtes Trip-Briefing ausgeloest wird /
    THEN wird NICHT fail-open durchgelassen (unbegrenzter SMS-Versand waere
    ein Rechte-Problem, kein Infrastruktur-Problem), sondern fail-CLOSED
    gesperrt (`cap=0` -> `ChannelBlockedError`, wie bei einem echten
    free-Nutzer) -- kein Wurf verlaesst `send_trip_report`.
    """
    from services import sms_daily_limit as sdl

    uid = _kennung("f009b")
    _nutzer_anlegen(uid, "premium")  # eigentlich unbegrenzt -- der Lookup wirft trotzdem
    trip = _trip(f"trip-{uid}")
    svc = NotificationService(settings=_settings(), user_id=uid)

    def _kaputter_cap(user_id, kind, purpose):
        raise RuntimeError("Simulierter Tier-/Cap-Lookup-Fehler (F009b)")

    with pytest.MonkeyPatch.context() as m:
        m.setattr(sdl, "_cap", _kaputter_cap)
        ergebnis = svc.send_trip_report(_report_request(trip, send_sms=True))

    assert mitschrift.anzahl("sms") == 0, (
        f"F009b: bei einem werfenden Tier-/Cap-Lookup muss die SMS "
        f"fail-CLOSED gesperrt bleiben, aufgezeichnet: "
        f"{mitschrift.anzahl('sms')}"
    )
    assert "sms" in ergebnis.blocked_channels, (
        f"F009b: Sperrgrund erwartet, {ergebnis.blocked_channels!r}"
    )
    assert mitschrift.anzahl("email") == 1, (
        "F009b: E-Mail muss trotz werfendem Tier-Lookup zugestellt werden"
    )
    assert mitschrift.anzahl("telegram") >= 1, (
        "F009b: Telegram muss trotz werfendem Tier-Lookup zugestellt werden"
    )


@pytest.mark.parametrize("tier,kind", [("free", "sms"), ("free", "premium_sms"), ("standard", "premium_sms")])
def test_kein_kontingent_sperrt_ohne_dateisystem_eingriff(tier, kind):
    """Fix-Loop #2412 (CI rot, #2226): ein Nutzer OHNE Kontingent (Cap 0) wird
    gesperrt, BEVOR `check_and_reserve` irgendetwas anlegt -- weder
    Zaehlerdatei noch Sperrdatei. Sonst hinterliess jeder Dispatch fuer einen
    Nutzer ohne Tarif eine `.lock`-Datei (im echten `data/users`-Baum, wenn
    die Datenwurzel nicht isoliert ist)."""
    from output.channels.base import ChannelBlockedError
    from services import sms_daily_limit

    uid = _kennung(f"cap0-{tier}")
    _nutzer_anlegen(uid, tier)
    vorher = sorted(p.name for p in get_data_dir(uid).iterdir())
    with pytest.raises(ChannelBlockedError) as exc:
        sms_daily_limit.check_and_reserve(uid, kind, "alert", datetime.now(timezone.utc))
    assert exc.value.reason_code == sms_daily_limit.REASON_CODE
    nachher = sorted(p.name for p in get_data_dir(uid).iterdir())
    assert nachher == vorher == ["user.json"], (
        f"Cap 0 darf keine Datei anlegen, vorher {vorher}, nachher {nachher}"
    )


@pytest.mark.parametrize("kind", ["sms", "premium_sms"])
def test_kein_kontingent_ohne_nutzerordner_legt_keinen_ordner_an(kind):
    """Adversary F010 (#2412): brandneue Kennung OHNE Nutzerordner (kein
    user.json => Tarif free => Cap 0). `check_and_reserve` muss sperren,
    OHNE den Nutzerordner anzulegen -- ein vorgezogenes
    `_path(user_id).parent.mkdir(...)` bliebe sonst unbemerkt, weil der
    Schwester-Test den Ordner vorher selbst anlegt."""
    from output.channels.base import ChannelBlockedError
    from services import sms_daily_limit

    uid = _kennung(f"ohneordner-{kind}")
    assert not get_data_dir(uid).exists(), "Vorbedingung: Nutzerordner fehlt"
    with pytest.raises(ChannelBlockedError) as exc:
        sms_daily_limit.check_and_reserve(uid, kind, "alert", datetime.now(timezone.utc))
    assert exc.value.reason_code == sms_daily_limit.REASON_CODE
    assert not get_data_dir(uid).exists(), (
        f"Cap 0 darf den Nutzerordner nicht anlegen: {get_data_dir(uid)}"
    )
