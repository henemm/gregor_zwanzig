"""Issue #1847: Der Trip-Briefing-Pfad protokolliert den E-Mail-Empfaenger.

Spec: docs/specs/fast/fix-1847-briefing-empfaenger-log.md
Kontext: docs/context/fix-1847-briefing-versand-ohne-zustellung.md

Anlass: "Versand gemeldet, Postfach leer" kostete rund eine Stunde Diagnose,
weil die Erfolgszeile des Trip-Briefings den Empfaenger nicht nennt. Im
Compare-Pfad steht er wortwoertlich im Protokoll
(`scheduler_dispatch_service.py:571`); dort war dieselbe Falle in einer Minute
aufgeklaert.

PRUEFORT = WIRKORT: der Versand laeuft ueber den ECHTEN Pfad
(`send_test_report_outcome` -> `_send_trip_report_outcome` ->
`NotificationService.send_trip_report` -> `EmailOutput.send`). Ersetzt wird
AUSSCHLIESSLICH der aeusserste Netzrand:

* `EmailOutput._dial_and_send` (SMTP-Steckdose, #1412 S3a: der EINE Ort, an
  dem eine SMTP-Verbindung entsteht) und
* `TelegramOutput._post` (Bot-API-Steckdose, #1370: der EINE Transportweg) --
  ohne dieses zweite Substitut wuerde der Telegram-Testfall echt senden
  (#1477: am 2026-08-03 gingen so Nachrichten an den Produktiv-Chat).

Bewusst NICHT ersetzt werden `NotificationService._send_email`,
`Settings.can_send_email` und `mail_sink` -- genau diese drei haengen die
Stellen aus, an denen der Empfaenger ueberhaupt erst sichtbar wird (siehe
`tests/unit/test_trip_send_endpoint_no_channels.py:160-178` als
Gegenbeispiel). Die Empfaenger-Aufloesung (`Settings.with_user_profile` ->
`mail_to`), alle Empfaenger-Guards (#1219/#1235/#1476) und die Zustellbilanz
(`sent_channels`) laufen unveraendert echt.

Zugangsdaten sind bewusst DUMMY-Werte: selbst wenn ein Netzrand-Substitut
ausfiele, koennte weder eine Mail noch eine Telegram-Nachricht ein echtes Ziel
erreichen.

AC-1: erfolgreicher E-Mail-Versand -> die Erfolgszeile nennt die
      Empfaengeradresse (geprueft am ausgegebenen Log-Datensatz).
AC-2: derselbe Versand -> der briefing_log.json-Eintrag traegt den
      Empfaenger, alle Altfelder bleiben unveraendert vorhanden.
AC-3: Telegram-only-Trip -> weder Logzeile noch Eintrag nennen eine
      E-Mail-Adresse.
AC-4: E-Mail scheitert ohne Ersatzkanal -> keine Erfolgszeile, kein
      briefing_log-Eintrag, bestehender Fehlerpfad unveraendert.
"""
from __future__ import annotations

import json
import logging
import smtplib
from datetime import date
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

EMPFAENGER = "gregor-test@henemm.com"

# Dummy-Zugangsdaten: kein einziger Wert erreicht ein echtes Ziel. Sie sind
# noetig, weil `can_send_email()` und die Test-Modus-Guards (#1288/#1363/#1476)
# BEWUSST nicht ausgehaengt werden -- ohne echte Konfiguration braucht der
# Testlauf trotzdem eine vollstaendige.
DUMMY_ENV = {
    "GZ_SMTP_HOST": "mail.henemm.com",
    "GZ_SMTP_PORT": "587",
    "GZ_SMTP_USER": "tdd-1847",
    "GZ_SMTP_PASS": "tdd-1847-kein-echtes-passwort",
    "GZ_TEST_SMTP_HOST": "mail.henemm.com",
    "GZ_TEST_SMTP_USER": "tdd-1847",
    "GZ_TEST_SMTP_PASS": "tdd-1847-kein-echtes-passwort",
    "GZ_TELEGRAM_BOT_TOKEN": "tdd-1847-kein-echter-token",
    "GZ_TELEGRAM_CHAT_ID": "tdd-1847-chat",
    "GZ_TELEGRAM_TEST_BOT_TOKEN": "tdd-1847-kein-echter-token",
    "GZ_TELEGRAM_TEST_CHAT_ID": "tdd-1847-chat",
}


class _TodayOnlyOpenMeteoDouble:
    """Echte, aufgezeichnete Innsbruck-Fixturdaten fuer 'heute' (Muster #1325)."""

    name = "openmeteo"

    def __init__(self) -> None:
        from providers.fixture import FixtureProvider

        self._fixture = FixtureProvider(str(REPO_ROOT / "fixtures" / "openmeteo"))

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble=True, enrich_snow=True):
        return self._fixture.fetch_forecast(
            location, start=start, end=end,
            enrich_ensemble=enrich_ensemble, enrich_snow=enrich_snow,
        )


class Netzrand:
    """Sammelt, was die beiden Steckdosen tatsaechlich zu sehen bekommen."""

    def __init__(self) -> None:
        self.smtp: list[dict] = []
        self.telegram: list[dict] = []
        self.smtp_fehler: BaseException | None = None


@pytest.fixture
def netzrand(monkeypatch) -> Netzrand:
    for key, value in DUMMY_ENV.items():
        monkeypatch.setenv(key, value)

    from output.channels.telegram import reset_telegram_rate_limit_for_tests

    reset_telegram_rate_limit_for_tests()

    rand = Netzrand()

    def _smtp_steckdose(self, host, port, user, password, recipients, msg,
                        from_addr, deadline_at):
        rand.smtp.append({
            "host": host, "recipients": list(recipients), "from": from_addr,
        })
        if rand.smtp_fehler is not None:
            raise rand.smtp_fehler

    def _telegram_steckdose(self, url, payload, *, chat_id=None):
        rand.telegram.append({"chat_id": chat_id, "payload": payload})
        return httpx.Response(
            200, json={"ok": True, "result": {"message_id": len(rand.telegram)}},
        )

    monkeypatch.setattr(
        "output.channels.email.EmailOutput._dial_and_send", _smtp_steckdose,
    )
    monkeypatch.setattr(
        "output.channels.telegram.TelegramOutput._post", _telegram_steckdose,
    )
    monkeypatch.setattr(
        "providers.base.get_provider", lambda name: _TodayOnlyOpenMeteoDouble(),
    )
    return rand


def _trip_anlegen(user_id: str, trip_id: str, report_config: dict) -> None:
    """Legt Nutzerprofil (mit mail_to) und Trip im isolierten Datenbaum an."""
    from app.loader import get_briefings_dir, get_data_dir

    profil = get_data_dir(user_id) / "user.json"
    profil.parent.mkdir(parents=True, exist_ok=True)
    profil.write_text(json.dumps({"mail_to": EMPFAENGER}))

    briefings_dir = get_briefings_dir(user_id)
    briefings_dir.mkdir(parents=True, exist_ok=True)
    (briefings_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id,
        "name": "TDD-1847 Trip",
        "kind": "route",
        "stages": [{
            "id": "st-heute",
            "name": "Etappe heute",
            "date": date.today().isoformat(),
            "waypoints": [
                {"id": "wp1", "name": "Innsbruck", "lat": 47.2692,
                 "lon": 11.4041, "elevation_m": 574},
                {"id": "wp2", "name": "Hafelekar", "lat": 47.3103,
                 "lon": 11.3844, "elevation_m": 2269},
            ],
        }],
        # Kein MeteoAlarm-Fetch -- der Kern-Test bleibt netzfrei.
        "official_alerts_enabled": False,
        "report_config": report_config,
        "alert_rules": [],
    }))


def _versenden(user_id: str, trip_id: str):
    from app.loader import get_briefings_dir, load_trip
    from services.trip_report_scheduler import TripReportSchedulerService

    trip = load_trip(get_briefings_dir(user_id) / f"{trip_id}.json")
    service = TripReportSchedulerService(user_id=user_id)
    return service.send_test_report_outcome(trip, "morning")


def _erfolgszeilen(caplog) -> list[str]:
    return [
        r.getMessage() for r in caplog.records
        if r.getMessage().startswith("Trip report sent:")
    ]


def _log_eintraege(user_id: str) -> list[dict]:
    from app.loader import get_data_dir

    pfad = get_data_dir(user_id) / "briefing_log.json"
    if not pfad.exists():
        return []
    return json.loads(pfad.read_text())["entries"]


# ---------------------------------------------------------------------------
# AC-1 / AC-2: erfolgreicher E-Mail-Versand
# ---------------------------------------------------------------------------


class TestAC1ErfolgszeileNenntEmpfaenger:
    def test_erfolgszeile_enthaelt_die_empfaengeradresse(self, netzrand, caplog):
        user_id, trip_id = "tdd-1847-mail", "tdd-1847-mail-trip"
        _trip_anlegen(user_id, trip_id, {
            "send_email": True, "send_telegram": False, "send_sms": False,
        })

        with caplog.at_level(logging.INFO):
            outcome = _versenden(user_id, trip_id)

        assert outcome == "sent", f"Erwartet 'sent', bekommen {outcome!r}"
        assert netzrand.smtp, (
            "Die SMTP-Steckdose wurde nie erreicht -- der Test haette den "
            "echten Sendeweg verfehlt und koennte den Empfaenger gar nicht "
            "sehen (Pruefort != Wirkort)."
        )
        assert netzrand.smtp[0]["recipients"] == [EMPFAENGER], (
            f"Unerwarteter Empfaenger am SMTP-Rand: {netzrand.smtp}"
        )

        zeilen = _erfolgszeilen(caplog)
        assert len(zeilen) == 1, f"Erwartet genau eine Erfolgszeile: {zeilen}"
        assert EMPFAENGER in zeilen[0], (
            "BUG #1847: die Erfolgszeile nennt den E-Mail-Empfaenger nicht -- "
            "genau das kostete eine Stunde Diagnose. Zeile: " + zeilen[0]
        )

    def test_erfolgszeile_nennt_die_zugestellten_kanaele(self, netzrand, caplog):
        user_id, trip_id = "tdd-1847-kanal", "tdd-1847-kanal-trip"
        _trip_anlegen(user_id, trip_id, {
            "send_email": True, "send_telegram": True, "send_sms": False,
        })

        with caplog.at_level(logging.INFO):
            outcome = _versenden(user_id, trip_id)

        assert outcome == "sent"
        zeilen = _erfolgszeilen(caplog)
        assert zeilen, "Keine Erfolgszeile protokolliert"
        assert "email" in zeilen[0] and "telegram" in zeilen[0], (
            f"Erfolgszeile soll die zugestellten Kanaele nennen: {zeilen[0]}"
        )


class TestAC2BriefingLogTraegtEmpfaenger:
    def test_eintrag_traegt_empfaenger_und_alle_altfelder(self, netzrand, caplog):
        user_id, trip_id = "tdd-1847-log", "tdd-1847-log-trip"
        _trip_anlegen(user_id, trip_id, {
            "send_email": True, "send_telegram": False, "send_sms": False,
        })

        with caplog.at_level(logging.INFO):
            outcome = _versenden(user_id, trip_id)
        assert outcome == "sent"

        eintraege = _log_eintraege(user_id)
        assert len(eintraege) == 1, f"Erwartet genau einen Eintrag: {eintraege}"
        eintrag = eintraege[0]

        assert eintrag.get("mail_to") == EMPFAENGER, (
            "BUG #1847: der briefing_log-Eintrag traegt den E-Mail-Empfaenger "
            f"nicht -- der Nachweis ist nachtraeglich nicht fuehrbar: {eintrag}"
        )
        # Altfelder unveraendert (Wire-Format fuer Go/briefing_slots,
        # #393/#1007/#1725) -- ergaenzt wird, nicht ersetzt.
        assert eintrag["trip_id"] == trip_id
        assert eintrag["kind"] == "morning"
        assert eintrag["channels"] == ["email"]
        assert eintrag["on_demand"] is True
        assert isinstance(eintrag["sent_at"], str) and eintrag["sent_at"]


# ---------------------------------------------------------------------------
# AC-3: Telegram-only -- keine Adresse behaupten
# ---------------------------------------------------------------------------


class TestAC3TelegramOnlyNenntKeineAdresse:
    def test_keine_email_adresse_in_zeile_und_eintrag(self, netzrand, caplog):
        user_id, trip_id = "tdd-1847-telegram", "tdd-1847-telegram-trip"
        _trip_anlegen(user_id, trip_id, {
            "send_email": False, "send_telegram": True, "send_sms": False,
        })

        with caplog.at_level(logging.INFO):
            outcome = _versenden(user_id, trip_id)

        assert outcome == "sent", f"Erwartet 'sent', bekommen {outcome!r}"
        assert netzrand.smtp == [], (
            f"Ohne E-Mail-Kanal darf die SMTP-Steckdose nicht laufen: {netzrand.smtp}"
        )
        assert netzrand.telegram, "Telegram-Steckdose wurde nie erreicht"

        zeilen = _erfolgszeilen(caplog)
        assert zeilen, "Keine Erfolgszeile protokolliert"
        assert "@" not in zeilen[0], (
            "Eine Zeile, die bei JEDEM Versand eine Adresse nennt, waere keine "
            f"Zustell-Aussage: {zeilen[0]}"
        )

        eintraege = _log_eintraege(user_id)
        assert len(eintraege) == 1, f"Erwartet genau einen Eintrag: {eintraege}"
        eintrag = eintraege[0]
        assert eintrag["channels"] == ["telegram"]
        assert "mail_to" not in eintrag, (
            f"Ohne E-Mail-Versand darf kein Empfaenger behauptet werden: {eintrag}"
        )
        assert not any(
            isinstance(v, str) and "@" in v for v in eintrag.values()
        ), f"Keine Adresse im Eintrag erwartet: {eintrag}"


# ---------------------------------------------------------------------------
# AC-4: E-Mail scheitert, kein Ersatzkanal
# ---------------------------------------------------------------------------


class TestAC4FehlgeschlagenerVersand:
    def test_kein_erfolg_und_kein_log_eintrag(self, netzrand, caplog):
        """Erreichbares Verhalten dieses Falls (Spec-Korrektur 2026-08-15):
        bei leerem `sent_channels` reicht `notification_service.py:527-528`
        den E-Mail-Fehler weiter, `trip_report_scheduler.py:1522-1535` faengt
        ihn, schreibt Fehlervermerk + Anker und reicht ihn durch -- die
        Dreier-Auswertung (:1566-1578) wird nie betreten. Zugesichert bleibt
        die Wirkung: kein stiller Erfolg, kein Log-Eintrag, bestehende
        Fehlerzeile unveraendert. Den Zweig mit der Warnzeile ("Kanal
        konfiguriert, aber unerreichbar") deckt
        `test_trip_send_endpoint_no_channels.py` ab.
        """
        from output.channels.base import OutputError

        user_id, trip_id = "tdd-1847-fehler", "tdd-1847-fehler-trip"
        _trip_anlegen(user_id, trip_id, {
            "send_email": True, "send_telegram": False, "send_sms": False,
        })
        # Dauerhafter Auth-Fehler: `send()` bricht ohne Retry und ohne
        # Ersatzweg ab -- derselbe Fehlerpfad wie ein ablehnender Postausgang,
        # aber ohne Wartezeit im Testlauf.
        netzrand.smtp_fehler = smtplib.SMTPAuthenticationError(
            535, b"5.7.8 Authentication credentials invalid",
        )

        with caplog.at_level(logging.INFO):
            with pytest.raises(OutputError):
                _versenden(user_id, trip_id)

        assert netzrand.smtp, "SMTP-Steckdose wurde nie erreicht"
        assert _erfolgszeilen(caplog) == [], (
            "Ohne Zustellung darf keine Erfolgszeile -- und damit kein "
            "Empfaenger als 'zugestellt' -- im Protokoll stehen."
        )
        fehlerzeilen = [
            r.getMessage() for r in caplog.records
            if "E-Mail send failed" in r.getMessage()
        ]
        assert fehlerzeilen, (
            "Der bestehende Fehlerpfad (notification_service.py:409) muss "
            "unveraendert melden."
        )
        assert _log_eintraege(user_id) == [], (
            "Kein briefing_log-Eintrag ohne Zustellung -- ein Eintrag mit "
            "channels=[] taeuschte der Cockpit-Kachel (#393/#1007) einen "
            "Versand vor."
        )
