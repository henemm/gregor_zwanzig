"""TDD RED — Kanaltreue der Ad-hoc-Antwort (Issue #2126, Epic #2133 Scheibe S3).

SPEC: docs/specs/modules/feat_2126_kanaltreue_adhoc_antwort.md (AC-1..AC-8)
Kontext: docs/context/feat-2126-kanaltreue-adhoc-antwort.md

Zielverhalten: Eine ``heute``/``morgen``-Anfrage wird ueber GENAU den Kanal
beantwortet, ueber den sie gestellt wurde — auch wenn dieser Kanal im Trip
abgeschaltet ist (AC-4, Override). Slot-Briefing, Test-Versand und das
``report``-Kommando bleiben unveraendert mehrkanalig (AC-3).

RED heute: ``msg.channel`` faellt in ``trip_command_processor.py`` bei
``_handle_query`` weg und erreicht die Kanal-Aufloesung nie;
``_resolve_channel_flags`` existiert nicht. Der Versand geht an ALLE im Trip
aktivierten Kanaele.

Messpunkt: der TATSAECHLICHE Versand, abgegriffen an den vier Kanal-Ausgaengen
des ``NotificationService``, plus ``briefing_log.channels``. Der Nachweis
beginnt bei ``TripCommandProcessor.process(InboundMessage(channel=...))` —
``msg.channel`` ist die Bildungsstelle der Zusicherung, ein direkter
``send_on_demand_report``-Aufruf bewachte die Verdrahtung nicht.

Mock-frei: echte Trips/Profile auf der isolierten Datenwurzel (autouse-Fixture
aus tests/conftest.py, #1133), echter Prozessor, echter Scheduler, echter
Renderer. Offline sind nur die beiden NAEHTE nach aussen — der Wetterabruf
ueber die etablierte ``GZ_TEST_FIXTURE_DIR``-Substitution
(``# fake-provider-seam``, #346; AC-6 lenkt sie auf ein LEERES Verzeichnis und
erzeugt so einen echten Provider-Ausfall) und die vier Kanal-Ausgaenge,
ersetzt durch echte Aufzeichner-Klassen (kein ``Mock()``/``patch()``). Die
Aufzeichner sind zugleich die Sicherung, dass aus diesem Lauf nichts
hinausgeht (#1477) — zusaetzlich zu durchweg unbrauchbaren Zugangsdaten.

Nutzerkennungen tragen bewusst KEIN "tdd"/"test": ``is_test_user_id`` erzwaenge
sonst ``Settings.for_testing()``, und das ueberschreibt die
``telegram_chat_id`` des Profils (``config.py``: ``if
profile.get("telegram_chat_id") and not force_test``). AC-7/AC-8 maessen dann
die Test-Umleitung statt der Profil-Aufloesung.

RED-Charakter: AC-1/AC-2/AC-4/AC-6/AC-8 sind Fehlernachweise (ROT), AC-5 ist
rot mangels ``_resolve_channel_flags``. AC-3 und AC-7 sind REGRESSIONSWAECHTER
und starten GRUEN. AC-3 ist zugleich die Positivkontrolle fuer AC-1/AC-2/AC-4:
gleiche Fixture, gleiche Aufzeichner, alle vier Kanaele tatsaechlich bedient —
ohne diesen Gegenpol koennte ein leeres Ergebnis auch schlicht "Zustellung
fehlgeschlagen" heissen.
"""
from __future__ import annotations

import inspect
import json
import sys
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_data_dir, load_all_trips, save_trip  # noqa: E402
from app.models import TripReportConfig  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage,
    TripCommandProcessor,
)
from services.trip_report_scheduler import TripReportSchedulerService  # noqa: E402
from utils.timezone import tz_for_coords  # noqa: E402

#: Exakter Standort aus ``providers/fixture.py::_FIXTURE_LOCATIONS`` — so
#: trifft der Nearest-Neighbour-Zuordner garantiert ``innsbruck.json``.
INNSBRUCK = (47.2692, 11.4041)

#: Versand-Reihenfolge in ``NotificationService.send_trip_report`` — dieselbe
#: Reihenfolge steht in ``briefing_log.channels``.
ALLE_KANAELE = ("email", "sms", "premium_sms", "telegram")

VIER_KANAELE_AN = {
    "send_email": True, "send_sms": True,
    "send_premium_sms": True, "send_telegram": True,
}

#: Jedes Transport-Feld ausdruecklich belegt (#1477) — ein weggelassenes Feld
#: faellt bei pydantic still auf die Prod-``.env`` zurueck. Unbrauchbar, aber
#: VOLLSTAENDIG: ``can_send_sms()``/``can_send_telegram()`` muessen True
#: liefern, sonst waere "Kanal nicht bedient" nur fehlende Zugangsdaten.
_TRANSPORT_ENV = {
    "GZ_ENV": "development",
    "GZ_SMTP_HOST": "smtp.invalid",
    "GZ_SMTP_USER": "unbrauchbar",
    "GZ_SMTP_PASS": "unbrauchbar",
    "GZ_MAIL_FROM": "gregor@example.invalid",
    # Globaler Rueckfall — er DARF in AC-7/AC-8 nie auftauchen.
    "GZ_MAIL_TO": "globaler-rueckfall@example.invalid",
    "GZ_TEST_SMTP_HOST": "smtp.invalid",
    "GZ_TEST_SMTP_USER": "",
    "GZ_TEST_SMTP_PASS": "",
    "GZ_TELEGRAM_BOT_TOKEN": "0000000:unbrauchbar",
    "GZ_TELEGRAM_CHAT_ID": "globaler-rueckfall-chat",
    "GZ_TELEGRAM_TEST_BOT_TOKEN": "",
    "GZ_TELEGRAM_TEST_CHAT_ID": "",
    "GZ_SMS_GATEWAY_URL": "https://gateway.invalid/api/sms",
    "GZ_SEVEN_API_KEY": "unbrauchbar",
    "GZ_SEVEN_SANDBOX_KEY": "",
    "GZ_SMS_TO": "+490000000000",
}


# ---------------------------------------------------------------------------
# Aufzeichner an den vier Kanal-Ausgaengen
# ---------------------------------------------------------------------------


class Kanalmitschrift:
    """Was tatsaechlich hinausging — je Kanal Empfaenger und Betreff."""

    def __init__(self) -> None:
        self.je_kanal: dict[str, list[dict]] = {k: [] for k in ALLE_KANAELE}

    @property
    def kanaele(self) -> list[str]:
        """Bediente Kanaele in der Versand-Reihenfolge des Produktivcodes."""
        return [k for k in ALLE_KANAELE if self.je_kanal[k]]

    def empfaenger(self, kanal: str) -> list[str]:
        return [e["empfaenger"] for e in self.je_kanal[kanal]]

    def leeren(self) -> None:
        self.je_kanal = {k: [] for k in ALLE_KANAELE}

    def __repr__(self) -> str:  # erscheint in jeder Fehlermeldung
        return f"Kanalmitschrift({({k: v for k, v in self.je_kanal.items() if v})})"


def _aufzeichner_installieren(monkeypatch) -> Kanalmitschrift:
    """Echte Klassen mit den echten ``send()``-Signaturen ersetzen die vier
    Ausgaenge. Sie ersetzen die Naht zum Netz, NICHT die Entscheidung darueber,
    wer bedient wird — die faellt weiter im Produktivcode."""
    from services import notification_service as ns

    mit = Kanalmitschrift()

    def _buchen(kanal: str, empfaenger, subject: str) -> None:
        mit.je_kanal[kanal].append({"empfaenger": empfaenger, "subject": subject})

    class _EmailAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body, html=True, plain_text_body=None, to=None,
                 mail_type=None, mail_format=None, compare_hourly_enabled=None):
            # Ohne `to=` faellt `EmailOutput` auf `settings.mail_to` zurueck
            # (email.py:647-650) — genau die Aufloesung, die AC-7 prueft.
            ziel = to if to else self._s.mail_to
            _buchen("email", ziel if isinstance(ziel, str) else list(ziel)[0], subject)

    class _SmsAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body) -> None:
            _buchen("sms", self._s.sms_to, subject)

    class _PremiumSmsAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body) -> None:
            _buchen("premium_sms", self._s.premium_sms_reply_to, subject)

    class _TelegramAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body, reply_markup=None, *, parse_mode=None,
                 suppress_subject_line=False) -> int:
            _buchen("telegram", self._s.telegram_chat_id, subject)
            return 1

    monkeypatch.setattr(ns, "EmailOutput", _EmailAufzeichner)
    monkeypatch.setattr(ns, "SMSOutput", _SmsAufzeichner)
    monkeypatch.setattr(ns, "PremiumSmsOutput", _PremiumSmsAufzeichner)
    monkeypatch.setattr(ns, "TelegramOutput", _TelegramAufzeichner)
    return mit


@pytest.fixture
def mitschrift(monkeypatch) -> Kanalmitschrift:
    for name, wert in _TRANSPORT_ENV.items():
        monkeypatch.setenv(name, wert)
    return _aufzeichner_installieren(monkeypatch)


# ---------------------------------------------------------------------------
# Aufbau-Helfer (echte Dateien auf der isolierten Datenwurzel)
# ---------------------------------------------------------------------------


def _kennung(praefix: str) -> str:
    """Mandantenkennung OHNE "tdd"/"test" — Begruendung im Modul-Docstring."""
    return f"kanaltreue-{praefix}-{uuid.uuid4().hex[:6]}"


def _nutzer_anlegen(user_id: str, *, mail: str, chat_id: str,
                    tier: str = "premium") -> None:
    """Echtes ``user.json`` — Tier UND Empfaengeradressen von der Platte."""
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": user_id,
        "tier": tier,
        "mail_to": mail,
        "telegram_chat_id": chat_id,
        "sms_to": "+490000000001",
        "premium_sms_reply_to": "+490000000002",
        "premium_sms_reply_at": datetime.now(timezone.utc).isoformat(),
    }))


def _trip_anlegen(user_id: str, *, name: str, kanaele: dict | None = None) -> Trip:
    """Drei Etappen (gestern/heute/morgen, Ortstag) am Fixture-Standort.

    "heute" fuehrt auf ``report_type="morning"`` (Zieltag = Ortstag), "morgen"
    auf ``"evening"`` (Folgetag) — beide brauchen eine Etappe, sonst endet der
    Abruf in ``no_stage`` statt in einem Versand. ``official_alerts_enabled=
    False``: amtliche Warnungen kennen keine Fixture-Naht und haengten diesen
    Kern-Test sonst ans Netz.
    """
    zone = tz_for_coords(*INNSBRUCK)
    heute = datetime.now(timezone.utc).astimezone(zone).date()
    trip_id = f"kanaltreue-{uuid.uuid4().hex[:8]}"
    stages = [
        Stage(
            id=f"T{i}", name=f"Etappe {i}", date=heute + timedelta(days=i - 1),
            waypoints=[
                Waypoint(id=f"G{i}a", name="Start",
                         lat=INNSBRUCK[0], lon=INNSBRUCK[1], elevation_m=600),
                Waypoint(id=f"G{i}b", name="Ziel",
                         lat=INNSBRUCK[0] + 0.02, lon=INNSBRUCK[1] + 0.02,
                         elevation_m=900),
            ],
        )
        for i in range(3)
    ]
    trip = Trip(
        id=trip_id, name=name, stages=stages, official_alerts_enabled=False,
        report_config=TripReportConfig(trip_id=trip_id, **(kanaele or VIER_KANAELE_AN)),
    )
    save_trip(trip, user_id)
    # Zurueck von der Platte: ``save_trip`` rechnet Ankunftszeiten neu.
    return next(t for t in load_all_trips(user_id) if t.id == trip_id)


def _ueber_den_draht(trip: Trip, wort: str, *, kanal: str, user_id: str,
                     absender: str):
    """Getippte Anfrage -> ECHTER ``TripCommandProcessor.process``."""
    return TripCommandProcessor().process(InboundMessage(
        trip_name=trip.name, body=f"### query: {wort}", sender=absender,
        channel=kanal, received_at=datetime.now(timezone.utc), user_id=user_id,
    ))


def _log_kanaele(user_id: str, trip_id: str) -> list[str]:
    pfad = get_data_dir(user_id) / "briefing_log.json"
    roh = json.loads(pfad.read_text()).get("entries", []) if pfad.exists() else []
    eintraege = [e for e in roh if e.get("trip_id") == trip_id]
    assert len(eintraege) == 1, (
        f"Erwartet GENAU EINEN briefing_log-Eintrag fuer {trip_id!r}, gefunden "
        f"{len(eintraege)}: {eintraege} — ein fehlender Eintrag heisst "
        f"'Zustellung fehlgeschlagen', nicht 'Kanal unterdrueckt'."
    )
    return list(eintraege[0].get("channels", []))


# ═══════════════════════════ AC-1 ════════════════════════════════════════════


def test_ac1_email_anfrage_wird_nur_per_email_beantwortet(mitschrift):
    """AC-1.

    GIVEN ein Trip mit allen vier aktivierten Kanaelen und ein Premium-Nutzer.
    WHEN  der Nutzer per E-MAIL ``heute`` sendet und die Nachricht durch
          ``TripCommandProcessor.process`` laeuft.
    THEN  geht das Briefing ausschliesslich per E-Mail hinaus und
          ``briefing_log.channels == ["email"]``.

    RED heute: der Ad-hoc-Abruf loest den Fan-out ueber alle vier Kanaele aus.
    Positivkontrolle gegen "Versand schlicht gescheitert": ``test_ac3_*``.
    """
    uid = _kennung("ac1")
    _nutzer_anlegen(uid, mail="ac1@example.invalid", chat_id="chat-ac1")
    trip = _trip_anlegen(uid, name="Kanaltreue AC1")

    ergebnis = _ueber_den_draht(
        trip, "heute", kanal="email", user_id=uid, absender="ac1@example.invalid",
    )

    assert ergebnis.success, f"Vorbedingung: der Abruf muss durchlaufen: {ergebnis}"
    assert mitschrift.kanaele == ["email"], (
        f"AC-1: eine per E-Mail gestellte Anfrage darf NUR per E-Mail "
        f"beantwortet werden, bedient wurden {mitschrift.kanaele} ({mitschrift!r})"
    )
    assert _log_kanaele(uid, trip.id) == ["email"], (
        f"AC-1: briefing_log.channels muss ['email'] sein, ist "
        f"{_log_kanaele(uid, trip.id)}"
    )


# ═══════════════════════════ AC-2 ════════════════════════════════════════════


def test_ac2_telegram_anfrage_wird_nur_per_telegram_beantwortet(mitschrift):
    """AC-2.

    GIVEN derselbe Trip mit allen vier aktivierten Kanaelen.
    WHEN  derselbe Nutzer per TELEGRAM ``morgen`` sendet.
    THEN  geht das Briefing ausschliesslich per Telegram hinaus und
          ``briefing_log.channels == ["telegram"]``.

    RED heute: wie AC-1 — der Fan-out kennt den Anfrageweg nicht.
    """
    uid = _kennung("ac2")
    _nutzer_anlegen(uid, mail="ac2@example.invalid", chat_id="chat-ac2")
    trip = _trip_anlegen(uid, name="Kanaltreue AC2")

    ergebnis = _ueber_den_draht(
        trip, "morgen", kanal="telegram", user_id=uid, absender="chat-ac2",
    )

    assert ergebnis.success, f"Vorbedingung: der Abruf muss durchlaufen: {ergebnis}"
    assert mitschrift.kanaele == ["telegram"], (
        f"AC-2: eine per Telegram gestellte Anfrage darf NUR per Telegram "
        f"beantwortet werden, bedient wurden {mitschrift.kanaele} ({mitschrift!r})"
    )
    assert _log_kanaele(uid, trip.id) == ["telegram"], (
        f"AC-2: briefing_log.channels muss ['telegram'] sein, ist "
        f"{_log_kanaele(uid, trip.id)}"
    )


# ═══════════════════════════ AC-3 ════════════════════════════════════════════
# Regressionswaechter UND Positivkontrolle: gleiche Fixture, gleiche
# Aufzeichner — hier MUESSEN alle vier Kanaele bedient werden.


@pytest.mark.parametrize("slot_stunde", [9, 18])
def test_ac3_planmaessiges_slot_briefing_bedient_weiter_alle_kanaele(
    mitschrift, slot_stunde,
):
    """AC-3 (Slot-Ausloesung) — Regressionswaechter, heute GRUEN.

    GIVEN ein Trip mit vier aktiven Kanaelen, dessen Morgen-Slot zur
          BEZUGSStunde des Laufs faellig ist.
    WHEN  ``send_due_reports(now_utc)`` mit genau dieser Bezugszeit laeuft —
          ohne jede Kanalangabe.
    THEN  wird GENAU EIN Briefing versendet und dabei alle vier Kanaele
          bedient.

    Wert nach dem Fix: faengt eine Einschraenkung, die den Anlass nicht
    unterscheidet und das planmaessige Briefing mit beschneidet (Spec-Risiko 1
    — der Fehler waere unsichtbar, weil ein fehlender Kanal beim Slot-Briefing
    niemandem sofort auffaellt).

    Die Bezugszeit ist FEST und parametrisiert, nicht ``datetime.now()``: mit
    der Systemuhr als Slot-Stunde kollidierte der Morgen-Slot mit dem
    Abend-Default 18:00 (``models.py``: ``evening_time``), und weil
    Faelligkeit ein Fenster von ``NACHHOL_FENSTER_STUNDEN = 3`` ist
    (``trip_report_scheduler.py``), waren BEIDE Slots zwischen 18 und 20 Uhr
    Ortszeit faellig — der Lauf versendete zwei Briefings und der Test war
    jeden Abend drei Stunden lang rot, ohne dass etwas kaputt war. Der Abend-
    Slot wird deshalb aus dem Fenster herausgesetzt, und ``slot_stunde=18``
    haelt genau die Konstellation fest, die vorher stolperte. Die Zusicherung
    (alle vier Kanaele) bleibt unangetastet.
    """
    uid = _kennung("ac3slot")
    _nutzer_anlegen(uid, mail="ac3slot@example.invalid", chat_id="chat-ac3slot")
    trip = _trip_anlegen(uid, name=f"Kanaltreue AC3 Slot {slot_stunde}")

    # Ortstag der Etappen, aber feste Stunde — der Ausgang darf nicht davon
    # abhaengen, zu welcher Tageszeit der Testlauf stattfindet.
    jetzt = datetime.now(timezone.utc).astimezone(
        tz_for_coords(*INNSBRUCK)
    ).replace(hour=slot_stunde, minute=0, second=0, microsecond=0).astimezone(
        timezone.utc
    )
    trip.report_config.morning_time = time(slot_stunde, 0)
    # Eine Stunde SPAETER heisst: ausserhalb des Nachhol-Fensters, denn das
    # oeffnet erst ab der konfigurierten Stunde.
    trip.report_config.evening_time = time(slot_stunde + 1, 0)
    save_trip(trip, uid)

    gesendet, fehlgeschlagen = TripReportSchedulerService(
        user_id=uid
    ).send_due_reports(jetzt)

    assert (gesendet, fehlgeschlagen) == (1, 0), (
        f"Vorbedingung: der faellige Slot muss genau ein Briefing versenden, "
        f"erhalten sent={gesendet}, failed={fehlgeschlagen}"
    )
    assert mitschrift.kanaele == list(ALLE_KANAELE), (
        f"AC-3: das planmaessige Slot-Briefing muss weiterhin ALLE aktivierten "
        f"Kanaele bedienen, bedient wurden {mitschrift.kanaele} ({mitschrift!r})"
    )
    assert _log_kanaele(uid, trip.id) == list(ALLE_KANAELE), (
        f"AC-3: briefing_log.channels des Slot-Briefings ist "
        f"{_log_kanaele(uid, trip.id)}"
    )


def test_ac3_testversand_bedient_weiter_alle_kanaele(mitschrift):
    """AC-3 (Test-Versand-Knopf) — Regressionswaechter, heute GRUEN.

    GIVEN derselbe Trip mit allen vier aktivierten Kanaelen.
    WHEN  ``send_test_report_outcome(trip, "evening")`` laeuft — der Pfad des
          Test-Versand-Knopfs, ohne Kanalangabe.
    THEN  werden weiterhin alle vier Kanaele bedient.
    """
    uid = _kennung("ac3test")
    _nutzer_anlegen(uid, mail="ac3test@example.invalid", chat_id="chat-ac3test")
    trip = _trip_anlegen(uid, name="Kanaltreue AC3 Testversand")

    ausgang = TripReportSchedulerService(user_id=uid).send_test_report_outcome(
        trip, "evening",
    )

    assert ausgang == "sent", f"Vorbedingung: Testversand-Ausgang war {ausgang!r}"
    assert mitschrift.kanaele == list(ALLE_KANAELE), (
        f"AC-3: der Test-Versand muss weiterhin ALLE aktivierten Kanaele "
        f"bedienen, bedient wurden {mitschrift.kanaele} ({mitschrift!r})"
    )


def test_ac3_report_kommando_bedient_weiter_alle_kanaele(mitschrift):
    """AC-3 (``report``-Kommando am Draht) — Regressionswaechter, heute GRUEN.

    GIVEN derselbe Trip mit allen vier aktivierten Kanaelen.
    WHEN  der Nutzer per Telegram ``### report: morning`` sendet.
    THEN  werden weiterhin alle vier Kanaele bedient.

    Der schaerfste der drei AC-3-Faelle: er laeuft ueber DENSELBEN Draht wie
    AC-1/AC-2 und traegt dieselbe Herkunftskennung. Wer die Einschraenkung
    pauschal an ``msg.channel`` haengt statt am Anfragewort, wird hier rot.
    """
    uid = _kennung("ac3report")
    _nutzer_anlegen(uid, mail="ac3report@example.invalid", chat_id="chat-ac3report")
    trip = _trip_anlegen(uid, name="Kanaltreue AC3 Report")

    ergebnis = TripCommandProcessor().process(InboundMessage(
        trip_name=trip.name, body="### report: morning", sender="chat-ac3report",
        channel="telegram", received_at=datetime.now(timezone.utc), user_id=uid,
    ))

    assert ergebnis.success, f"Vorbedingung: das report-Kommando lief nicht: {ergebnis}"
    assert mitschrift.kanaele == list(ALLE_KANAELE), (
        f"AC-3: das 'report'-Kommando muss weiterhin ALLE aktivierten Kanaele "
        f"bedienen, bedient wurden {mitschrift.kanaele} ({mitschrift!r})"
    )


# ═══════════════════════════ AC-4 ════════════════════════════════════════════


def test_ac4_deaktivierter_anfragekanal_wird_dennoch_bedient(mitschrift):
    """AC-4 (PO-Entscheid: antworten statt ablehnen).

    GIVEN ein Trip, in dem Telegram AUSDRUECKLICH abgeschaltet ist
          (``send_telegram=False``), E-Mail/SMS/Premium-SMS aber aktiv sind.
    WHEN  der Nutzer trotzdem per Telegram ``heute`` anfragt.
    THEN  wird geantwortet, und zwar GENAU ueber Telegram — die
          Trip-Einstellung wird fuer den Anfrageweg ueberschrieben, die drei
          anderen Kanaele bleiben stumm.

    RED heute: das System leitet still auf E-Mail/SMS/Premium-SMS um und meldet
    Erfolg; auf dem Draht, ueber den gefragt wurde, kommt nichts an.

    Diese Fixture ist die EINZIGE, die Mutation 2 der Spec faengt (Override zu
    ``restrict_to_channel == "telegram" and config.send_telegram`` verdreht):
    mit vier aktiven Kanaelen (AC-1/AC-2) bliebe die Verdrehung unsichtbar.
    """
    uid = _kennung("ac4")
    _nutzer_anlegen(uid, mail="ac4@example.invalid", chat_id="chat-ac4")
    trip = _trip_anlegen(uid, name="Kanaltreue AC4", kanaele={
        "send_email": True, "send_sms": True,
        "send_premium_sms": True, "send_telegram": False,
    })
    assert trip.report_config.send_telegram is False, (
        "Testaufbau: Telegram muss im Trip abgeschaltet sein, sonst faengt "
        "dieser Test Mutation 2 nicht"
    )

    ergebnis = _ueber_den_draht(
        trip, "heute", kanal="telegram", user_id=uid, absender="chat-ac4",
    )

    assert ergebnis.success, f"Vorbedingung: der Abruf muss durchlaufen: {ergebnis}"
    assert mitschrift.kanaele == ["telegram"], (
        f"AC-4: die Anfrage kam ueber den im Trip DEAKTIVIERTEN Telegram-Draht "
        f"— genau dieser muss die Antwort tragen, alle anderen nicht. Bedient "
        f"wurden {mitschrift.kanaele} ({mitschrift!r})"
    )
    assert _log_kanaele(uid, trip.id) == ["telegram"], (
        f"AC-4: briefing_log.channels muss ['telegram'] sein, ist "
        f"{_log_kanaele(uid, trip.id)}"
    )


# ═══════════════════════════ AC-5 ════════════════════════════════════════════


def _kanal_flags(trip, user_id: str, *, restrict_to_channel):
    """``_resolve_channel_flags`` aufrufen — mit sprechendem RED-Grund.

    Direktaufruf ist hier laut Spec zulaessig und noetig: SMS ist heute kein
    Eingangsweg, der Fall kann den Draht gar nicht erreichen.
    """
    fn = getattr(TripReportSchedulerService, "_resolve_channel_flags", None)
    assert fn is not None, (
        "src/services/trip_report_scheduler.py hat keine Methode "
        "`_resolve_channel_flags()` — die Kanal-Aufloesung steht weiterhin "
        "zweimal wortgleich im Fliesstext (:1743-1752 und :1371-1379) und "
        "kennt keine Kanal-Einschraenkung (Spec-Sektion 'Wirkort')."
    )
    scheduler = TripReportSchedulerService(user_id=user_id)
    return fn(scheduler, trip.report_config, user_id,
              restrict_to_channel=restrict_to_channel)


def test_ac5_sms_override_ueberspringt_das_tier_gate_nicht(mitschrift):
    """AC-5.

    GIVEN zwei ECHTE Nutzerprofile auf der Platte — eines ohne SMS-Tier
          (``free``), eines mit (``standard``) —, beide mit einem Trip, in dem
          ``send_sms`` AUSGESCHALTET ist.
    WHEN  fuer beide ``_resolve_channel_flags(config, user_id,
          restrict_to_channel="sms")`` aufgeloest wird.
    THEN  bleibt ``send_sms`` ohne Tier ``False`` und wird mit Tier ``True``:
          das Override ueberschreibt die TRIP-Einstellung, nicht die
          BERECHTIGUNG.

    Kein Stub von ``sms_allowed`` — die fail-closed-Auflosung aus ``user.json``
    ist Teil der Zusicherung. RED heute: ``_resolve_channel_flags`` fehlt.
    """
    ohne, mit_tier = _kennung("ac5-ohne"), _kennung("ac5-mit")
    _nutzer_anlegen(ohne, mail="ac5a@example.invalid", chat_id="chat-ac5a", tier="free")
    _nutzer_anlegen(mit_tier, mail="ac5b@example.invalid", chat_id="chat-ac5b",
                    tier="standard")
    ohne_sms = {"send_email": True, "send_sms": False,
                "send_premium_sms": False, "send_telegram": False}
    trip_ohne = _trip_anlegen(ohne, name="Kanaltreue AC5 ohne Tier", kanaele=ohne_sms)
    trip_mit = _trip_anlegen(mit_tier, name="Kanaltreue AC5 mit Tier", kanaele=ohne_sms)

    # Vorbedingung am ECHTEN Tier-Gate, nicht an der Annahme ueber die Datei.
    from services.user_tier import sms_allowed
    assert sms_allowed(ohne) is False and sms_allowed(mit_tier) is True, (
        f"Testaufbau: sms_allowed muss die beiden Profile unterscheiden, "
        f"erhalten ohne={sms_allowed(ohne)}, mit={sms_allowed(mit_tier)}"
    )

    flags_ohne = _kanal_flags(trip_ohne, ohne, restrict_to_channel="sms")
    flags_mit = _kanal_flags(trip_mit, mit_tier, restrict_to_channel="sms")

    assert flags_ohne[1] is False, (
        f"AC-5: ohne SMS-Tier muss send_sms auch im Override-Fall False "
        f"bleiben, erhalten {flags_ohne!r}"
    )
    assert flags_mit[1] is True, (
        f"AC-5: mit SMS-Tier muss das Override die abgeschaltete "
        f"Trip-Einstellung ueberschreiben, erhalten {flags_mit!r}"
    )
    assert flags_mit[0] is False and flags_mit[3] is False, (
        f"AC-5: die Einschraenkung auf 'sms' muss E-Mail und Telegram "
        f"abschalten, erhalten {flags_mit!r}"
    )


def test_ac5_ohne_einschraenkung_bleibt_die_alte_formel(mitschrift):
    """AC-5 (Gegenprobe): ``restrict_to_channel=None`` ist das NEUTRALE Element.

    GIVEN ein Premium-Nutzer und ein Trip mit allen vier Kanaelen.
    WHEN  ``_resolve_channel_flags(..., restrict_to_channel=None)`` aufgeloest
          wird.
    THEN  kommen exakt die vier Trip-Einstellungen zurueck.

    Ohne diese Gegenprobe waere AC-5 auch von einer Auflosung erfuellt, die
    IMMER einschraenkt.
    """
    uid = _kennung("ac5-neutral")
    _nutzer_anlegen(uid, mail="ac5c@example.invalid", chat_id="chat-ac5c")
    trip = _trip_anlegen(uid, name="Kanaltreue AC5 neutral")

    assert _kanal_flags(trip, uid, restrict_to_channel=None) == (True, True, True, True), (
        f"AC-5: ohne Einschraenkung muessen die vier Trip-Einstellungen "
        f"unveraendert durchkommen, erhalten "
        f"{_kanal_flags(trip, uid, restrict_to_channel=None)!r}"
    )


# --- AC-5, gemessen am AUSGELIEFERTEN Kanal (Adversary F001) ----------------
# Die beiden AC-5-Tests darueber pruefen die Unterscheidung am Rueckgabewert
# von `_resolve_channel_flags`, und nur im Override-Zweig. Damit blieb der
# Weg VOM Rueckgabe-Tupel BIS zum Transport unbewacht: das Unpacking in
# `_build_trip_report_request` und die vier Keyword-Argumente an
# `send_no_data_hint`. Alle anderen Tests dieser Datei fahren `tier="premium"`
# — dort sind `sms_allowed` und `premium_sms_allowed` beide True und die
# beiden Kanaele nicht auseinanderzuhalten.

#: `sms_allowed` laesst `standard` durch, `premium_sms_allowed` nicht
#: (`user_tier.py`, #1676 S2a). Genau EIN Tier trennt die beiden Gates — mit
#: `free` waeren beide zu, mit `premium` beide offen.
TRENNENDES_TIER = "standard"

#: Beide SMS-artigen Kanaele im Trip AN — die Trip-Einstellung darf den
#: Unterschied nicht schon vorwegnehmen, sonst misst der Test das Gate nicht.
BEIDE_SMS_AN = {
    "send_email": False, "send_sms": True,
    "send_premium_sms": True, "send_telegram": False,
}


def _nutzer_mit_trennendem_tier(praefix: str):
    uid = _kennung(praefix)
    _nutzer_anlegen(uid, mail=f"{praefix}@example.invalid",
                    chat_id=f"chat-{praefix}", tier=TRENNENDES_TIER)
    from services.user_tier import premium_sms_allowed, sms_allowed
    assert sms_allowed(uid) is True and premium_sms_allowed(uid) is False, (
        f"Testaufbau: Tier {TRENNENDES_TIER!r} muss die beiden Gates TRENNEN, "
        f"erhalten sms={sms_allowed(uid)}, premium={premium_sms_allowed(uid)} "
        f"— sonst kann dieser Test eine Vertauschung nicht sehen."
    )
    return uid


def test_ac5_briefing_bedient_sms_und_nicht_premium_sms(mitschrift):
    """AC-5 am Auslieferungspfad (Erfolgsfall).

    GIVEN ein Nutzer, dessen Tier die beiden SMS-Gates TRENNT (``standard``:
          SMS erlaubt, Premium-SMS nicht), und ein Trip, in dem BEIDE
          SMS-artigen Kanaele eingeschaltet sind.
    WHEN  ein Briefing ohne jede Kanaleinschraenkung ausgeliefert wird.
    THEN  geht es ueber SMS hinaus und NICHT ueber Premium-SMS.

    Misst am tatsaechlich bedienten Ausgang, nicht am Rueckgabewert der
    Auflosung: faengt eine Vertauschung der beiden Gates in der neutralen
    Formel EBENSO wie eine Vertauschung beim Unpacking der vier Flags in
    `_build_trip_report_request`. Kein Stub — die Gates lesen das echte
    ``user.json``.
    """
    uid = _nutzer_mit_trennendem_tier("ac5liefer")
    trip = _trip_anlegen(uid, name="Kanaltreue AC5 Auslieferung",
                         kanaele=BEIDE_SMS_AN)

    ausgang = TripReportSchedulerService(user_id=uid).send_test_report_outcome(
        trip, "evening",
    )

    assert ausgang == "sent", f"Vorbedingung: Ausgang war {ausgang!r}"
    assert mitschrift.kanaele == ["sms"], (
        f"AC-5: mit Tier {TRENNENDES_TIER!r} darf NUR der SMS-Kanal bedient "
        f"werden — Premium-SMS ist ein Premium-Merkmal (#1676 S2a). Bedient "
        f"wurden {mitschrift.kanaele} ({mitschrift!r}). ['premium_sms'] heisst: "
        f"die beiden Tier-Gates sind irgendwo auf dem Weg von "
        f"`_resolve_channel_flags` bis zum Transport vertauscht."
    )


def test_ac5_ausfallhinweis_bedient_sms_und_nicht_premium_sms(
    mitschrift, monkeypatch, tmp_path,
):
    """AC-5 am Auslieferungspfad (Ausfallfall).

    GIVEN derselbe Aufbau und ein VOLLSTAENDIGER Wetterausfall.
    WHEN  der No-Data-Hint-Zweig den Hinweistext ohne Kanaleinschraenkung
          versendet.
    THEN  geht auch er ueber SMS hinaus und NICHT ueber Premium-SMS.

    Eigener Test, weil der Hinweis-Zweig die vier Flags als vier EINZELNE
    Keyword-Argumente an ``send_no_data_hint`` weiterreicht — eine dort
    vertauschte Zuordnung faengt der Erfolgsfall darueber nicht.

    ``_leeres_fixture_verzeichnis`` steht weiter unten im AC-6-Block.
    """
    _leeres_fixture_verzeichnis(monkeypatch, tmp_path)
    uid = _nutzer_mit_trennendem_tier("ac5ausfall")
    trip = _trip_anlegen(uid, name="Kanaltreue AC5 Ausfall",
                         kanaele=BEIDE_SMS_AN)

    ausgang = TripReportSchedulerService(user_id=uid)._send_trip_report_outcome(
        trip, "morning",
    )

    assert ausgang == "no_weather", (
        f"Vorbedingung: der leere Fixture-Ordner muss einen Totalausfall "
        f"erzeugen, Ausgang war {ausgang!r}"
    )
    assert mitschrift.kanaele == ["sms"], (
        f"AC-5: der Ausfall-Hinweis darf mit Tier {TRENNENDES_TIER!r} nur ueber "
        f"SMS gehen, bedient wurden {mitschrift.kanaele} ({mitschrift!r}) — "
        f"['premium_sms'] heisst: die vier Keyword-Argumente an "
        f"`send_no_data_hint` sind vertauscht."
    )


# ═══════════════════════════ AC-6 ════════════════════════════════════════════


def _leeres_fixture_verzeichnis(monkeypatch, tmp_path) -> None:
    """``# fake-provider-seam``: Fixture-Ordner OHNE Dateien -> JEDER
    Wetterabruf scheitert real (``ProviderError``), also Totalausfall."""
    leer = tmp_path / "fixtures_leer"
    leer.mkdir()
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(leer))


def test_ac6_positivkontrolle_ausfallhinweis_geht_ohne_einschraenkung_an_alle(
    mitschrift, monkeypatch, tmp_path,
):
    """AC-6 Positivkontrolle — heute GRUEN, Vorbedingung fuer den Test darunter.

    GIVEN ein Trip mit vier Kanaelen und ein VOLLSTAENDIGER Wetterausfall.
    WHEN  ein planmaessiger Briefing-Lauf ohne Kanalangabe laeuft.
    THEN  liefert er ``no_weather`` UND der Ausfall-Hinweis geht an alle vier
          Kanaele.

    Belegt, ohne das der Test darunter nichts messen wuerde: der
    No-Data-Hint-Zweig (``trip_report_scheduler.py:1371-1379``) wird von diesem
    Aufbau WIRKLICH erreicht und ist ohne Einschraenkung mehrkanalig.
    """
    _leeres_fixture_verzeichnis(monkeypatch, tmp_path)
    uid = _kennung("ac6pos")
    _nutzer_anlegen(uid, mail="ac6pos@example.invalid", chat_id="chat-ac6pos")
    trip = _trip_anlegen(uid, name="Kanaltreue AC6 Positivkontrolle")

    ausgang = TripReportSchedulerService(user_id=uid)._send_trip_report_outcome(
        trip, "morning",
    )

    assert ausgang == "no_weather", (
        f"Vorbedingung: der leere Fixture-Ordner muss einen Totalausfall "
        f"erzeugen, Ausgang war {ausgang!r}"
    )
    assert mitschrift.kanaele == list(ALLE_KANAELE), (
        f"Vorbedingung: der Ausfall-Hinweis muss ohne Einschraenkung an alle "
        f"vier Kanaele gehen, bedient wurden {mitschrift.kanaele} ({mitschrift!r})"
    )


def test_ac6_ausfallhinweis_folgt_dem_anfragekanal(mitschrift, monkeypatch, tmp_path):
    """AC-6.

    GIVEN derselbe vollstaendige Wetterausfall, derselbe Trip mit vier Kanaelen.
    WHEN  derselbe Lauf MIT gesetzter Kanal-Einschraenkung (``telegram``) laeuft.
    THEN  geht auch der Hinweistext ausschliesslich an Telegram — der
          No-Data-Hint-Zweig folgt derselben Auflosung wie der Haupt-Request.

    Dies ist der Test gegen Mutation 1 der Spec (halber Fix, der nur
    ``:1743-1752`` anfasst und ``:1371-1379`` vergisst): AC-1/AC-2/AC-4
    beruehren den Ausfallzweig nie und blieben bei diesem halben Fix gruen.

    Warum hier direkt am Scheduler statt am Draht: ``send_on_demand_report``
    setzt ``on_demand=True``, und der Ausfallzweig laeuft ausdruecklich nur bei
    ``not on_demand`` (``:1363``) — ueber den Ad-hoc-Draht ist er strukturell
    unerreichbar (der Prozessor antwortet stattdessen selbst, siehe Test
    darunter). Gemessen wird an der naechstgelegenen erreichbaren Stelle.

    RED heute: ``_send_trip_report_outcome`` kennt keinen
    ``restrict_to_channel``-Parameter.
    """
    _leeres_fixture_verzeichnis(monkeypatch, tmp_path)
    uid = _kennung("ac6")
    _nutzer_anlegen(uid, mail="ac6@example.invalid", chat_id="chat-ac6")
    trip = _trip_anlegen(uid, name="Kanaltreue AC6")

    scheduler = TripReportSchedulerService(user_id=uid)
    assert "restrict_to_channel" in inspect.signature(
        scheduler._send_trip_report_outcome
    ).parameters, (
        "`_send_trip_report_outcome` nimmt keinen `restrict_to_channel` "
        "entgegen — die Kanalangabe erreicht weder den Haupt-Request noch den "
        "No-Data-Hint-Zweig (Spec-Sektion 'Transportweg')."
    )
    ausgang = scheduler._send_trip_report_outcome(
        trip, "morning", restrict_to_channel="telegram",
    )

    assert ausgang == "no_weather", (
        f"Vorbedingung: es muss weiterhin ein Totalausfall sein, Ausgang war "
        f"{ausgang!r}"
    )
    assert mitschrift.kanaele == ["telegram"], (
        f"AC-6: der Ausfall-Hinweis muss dem Anfragekanal folgen, bedient "
        f"wurden {mitschrift.kanaele} ({mitschrift!r}) — ein halber Fix, der "
        f"nur die Haupt-Formel anfasst, faellt genau hier auf."
    )


def test_ac6_adhoc_ausfall_antwortet_auf_dem_anfrageweg(mitschrift, monkeypatch,
                                                        tmp_path):
    """AC-6b (Waechter gegen die falsche Reparatur) — Regressionswaechter, heute GRUEN.

    GIVEN derselbe Totalausfall.
    WHEN  der Nutzer per Telegram ``heute`` anfragt.
    THEN  geht KEIN Briefing und KEIN Ausfall-Hinweis ueber irgendeinen Kanal
          hinaus; der Prozessor beantwortet die Anfrage selbst
          (``confirmation_body``), also auf dem Anfrageweg.

    Haelt fest, warum AC-6 oben nicht am Draht messbar ist. Wuerde eine
    Umsetzung den Hinweis-Zweig fuer On-Demand oeffnen, bekaeme der Nutzer die
    Ausfallmeldung doppelt — das faengt dieser Waechter.
    """
    _leeres_fixture_verzeichnis(monkeypatch, tmp_path)
    uid = _kennung("ac6draht")
    _nutzer_anlegen(uid, mail="ac6draht@example.invalid", chat_id="chat-ac6draht")
    trip = _trip_anlegen(uid, name="Kanaltreue AC6 Draht")

    ergebnis = _ueber_den_draht(
        trip, "heute", kanal="telegram", user_id=uid, absender="chat-ac6draht",
    )

    assert mitschrift.kanaele == [], (
        f"AC-6: der Ad-hoc-Ausfall darf keinen zusaetzlichen Hinweis-Versand "
        f"ausloesen, bedient wurden {mitschrift.kanaele} ({mitschrift!r})"
    )
    assert "nicht verfügbar" in (ergebnis.confirmation_body or ""), (
        f"AC-6: der Prozessor muss die Ausfallmeldung selbst auf dem Anfrageweg "
        f"beantworten, erhalten {ergebnis.confirmation_body!r}"
    )


# ═══════════════════════════ AC-7 ════════════════════════════════════════════


def test_ac7_email_antwort_geht_an_die_profiladresse(mitschrift):
    """AC-7 (E-Mail) — Regressionswaechter, heute GRUEN.

    GIVEN ein per E-Mail erkannter Nutzer, dessen Profil ``mail_to`` traegt.
    WHEN  er ``heute`` anfragt.
    THEN  traegt die versendete Antwort als Empfaenger genau diese Adresse —
          nicht den globalen ``GZ_MAIL_TO``-Rueckfall.

    Die Auflosung (``Settings.with_user_profile``) ist bereits korrekt und wird
    von dieser Scheibe nicht veraendert; bewacht war sie bisher nicht.
    """
    uid = _kennung("ac7mail")
    _nutzer_anlegen(uid, mail="ac7-eigene@example.invalid", chat_id="chat-ac7")
    trip = _trip_anlegen(uid, name="Kanaltreue AC7 Mail")

    _ueber_den_draht(trip, "heute", kanal="email", user_id=uid,
                     absender="ac7-eigene@example.invalid")

    assert mitschrift.empfaenger("email") == ["ac7-eigene@example.invalid"], (
        f"AC-7: die E-Mail-Antwort muss an die Profiladresse gehen, zugestellt "
        f"an {mitschrift.empfaenger('email')} — der globale Rueckfall "
        f"{_TRANSPORT_ENV['GZ_MAIL_TO']!r} waere ein Fremdempfaenger."
    )


def test_ac7_telegram_antwort_geht_an_die_profil_chat_id(mitschrift):
    """AC-7 (Telegram) — Regressionswaechter, heute GRUEN.

    GIVEN ein per Telegram erkannter Nutzer mit ``telegram_chat_id`` im Profil.
    WHEN  er ``heute`` anfragt.
    THEN  traegt die Telegram-Antwort genau diese ``chat_id`` — nicht den
          globalen ``GZ_TELEGRAM_CHAT_ID``-Rueckfall.
    """
    uid = _kennung("ac7tg")
    _nutzer_anlegen(uid, mail="ac7tg@example.invalid", chat_id="chat-ac7-eigen")
    trip = _trip_anlegen(uid, name="Kanaltreue AC7 Telegram")

    _ueber_den_draht(trip, "heute", kanal="telegram", user_id=uid,
                     absender="chat-ac7-eigen")

    assert set(mitschrift.empfaenger("telegram")) == {"chat-ac7-eigen"}, (
        f"AC-7: die Telegram-Antwort muss an die chat_id des Profils gehen, "
        f"zugestellt an {mitschrift.empfaenger('telegram')} — der globale "
        f"Rueckfall {_TRANSPORT_ENV['GZ_TELEGRAM_CHAT_ID']!r} waere ein "
        f"fremder Chat."
    )


# ═══════════════════════════ AC-8 ════════════════════════════════════════════


def test_ac8_zwei_nutzer_bekommen_ihre_antwort_je_auf_ihrem_weg(mitschrift):
    """AC-8 (Mandantentrennung).

    GIVEN zwei verschiedene Nutzer mit je eigenem Trip, eigener E-Mail-Adresse
          und eigener ``chat_id``.
    WHEN  Nutzer A per E-Mail und Nutzer B per Telegram unabhaengig voneinander
          ``heute`` anfragt.
    THEN  bekommt A seine Antwort ausschliesslich per E-Mail an SEINE Adresse
          und B ausschliesslich per Telegram an SEINE ``chat_id`` — keine
          Kreuzung zwischen beiden.

    RED heute: beide Anfragen loesen den vollen Vier-Kanal-Fan-out aus. Der
    Kreuzungsteil ist heute schon erfuellt und bleibt der Waechter gegen eine
    Umsetzung, die die Einschraenkung an einem prozessweiten Zustand statt am
    Aufruf festmacht.
    """
    uid_a, uid_b = _kennung("ac8-a"), _kennung("ac8-b")
    _nutzer_anlegen(uid_a, mail="ac8-a@example.invalid", chat_id="chat-ac8-a")
    _nutzer_anlegen(uid_b, mail="ac8-b@example.invalid", chat_id="chat-ac8-b")
    trip_a = _trip_anlegen(uid_a, name="Kanaltreue AC8 Nutzer A")
    trip_b = _trip_anlegen(uid_b, name="Kanaltreue AC8 Nutzer B")

    _ueber_den_draht(trip_a, "heute", kanal="email", user_id=uid_a,
                     absender="ac8-a@example.invalid")
    kanaele_a = mitschrift.kanaele
    adressen_a = {k: list(mitschrift.empfaenger(k)) for k in ALLE_KANAELE}

    mitschrift.leeren()
    _ueber_den_draht(trip_b, "heute", kanal="telegram", user_id=uid_b,
                     absender="chat-ac8-b")
    kanaele_b = mitschrift.kanaele
    adressen_b = {k: list(mitschrift.empfaenger(k)) for k in ALLE_KANAELE}

    # Keine Kreuzung (heute schon erfuellt — Waechter).
    assert "ac8-b@example.invalid" not in adressen_a["email"], (
        f"AC-8: Nutzer A hat an die Adresse von Nutzer B gesendet: {adressen_a}"
    )
    assert "chat-ac8-a" not in adressen_b["telegram"], (
        f"AC-8: Nutzer B hat an den Chat von Nutzer A gesendet: {adressen_b}"
    )

    # Kanaltreue je Nutzer (heute ROT).
    assert kanaele_a == ["email"], (
        f"AC-8: Nutzer A fragte per E-Mail und darf nur per E-Mail bedient "
        f"werden, bedient wurden {kanaele_a} ({adressen_a})"
    )
    assert kanaele_b == ["telegram"], (
        f"AC-8: Nutzer B fragte per Telegram und darf nur per Telegram bedient "
        f"werden, bedient wurden {kanaele_b} ({adressen_b})"
    )
    assert adressen_a["email"] == ["ac8-a@example.invalid"], (
        f"AC-8: A muss seine eigene Adresse bekommen: {adressen_a}"
    )
    assert set(adressen_b["telegram"]) == {"chat-ac8-b"}, (
        f"AC-8: B muss seinen eigenen Chat bekommen: {adressen_b}"
    )
    assert _log_kanaele(uid_a, trip_a.id) == ["email"], (
        f"AC-8: briefing_log von A ist {_log_kanaele(uid_a, trip_a.id)}"
    )
    assert _log_kanaele(uid_b, trip_b.id) == ["telegram"], (
        f"AC-8: briefing_log von B ist {_log_kanaele(uid_b, trip_b.id)}"
    )
