"""TDD RED — Premium-SMS erreicht den Kommandoverarbeiter (Issue #2184, S4).

SPEC: docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md
      (AC-1..AC-7, AC-9, AC-10 — AC-8 liegt in
      ``test_gewitter_herkunft_kanalabhaengig.py``)

Zielverhalten: Eine Garmin-inReach-Nachricht (Kennzeichen ``inreachlink.com``)
loest nicht mehr nur das Lernen der Rueckadresse aus — der Text VOR dem
Kennzeichen wird als Befehl verarbeitet und die Antwort geht per Premium-SMS
an die gelernte Nummer zurueck.

RED heute (gemessen an ``inbound_sms_reader.py:160-212``): der Nachrichtentext
wird verworfen (``payload = {"from": sender}``), ``TripCommandProcessor`` wird
nie gerufen, ``send_command_reply_premium_sms`` existiert nicht. Es geht
nichts hinaus — deshalb messen die roten Tests am TATSAECHLICHEN Versand.

Messpunkt = Wirkort, ohne Ausnahme: gezaehlt wird, was die vier Kanal-Ausgaenge
des ``NotificationService`` absetzen, plus ``briefing_log.channels``. Ein Test
auf ``learned == 0`` oder auf einen Zwischenwert bewachte die Zusicherung
nicht (Spec-Mutationen 1, 5, 6).

Kein Mock-Theater: echte Trips/Profile auf der isolierten Datenwurzel
(autouse-Fixture aus tests/conftest.py, #1133), echter Reader, echter
Prozessor, echter Scheduler, echter Renderer. Ersetzt sind ausschliesslich die
drei AUSSENGRENZEN durch echte Aufzeichner-Klassen (kein ``Mock()``, kein
``patch()``):

  1. ``httpx.get`` des seven.io-Journals   — nur IM Reader-Modul ersetzt
  2. ``httpx.post`` auf ``LEARN_ENDPOINT`` — dito, antwortet wie der Go-Endpunkt
  3. die vier Kanal-Ausgaenge (E-Mail/SMS/Premium-SMS/Telegram)

Die Aufzeichner sind zugleich die Sicherung, dass aus diesem Lauf nichts
hinausgeht (#1477) — zusaetzlich zu durchweg unbrauchbaren Zugangsdaten.

🔴 Der Premium-SMS-Messpunkt haengt an der KLASSE
``output.channels.premium_sms.PremiumSmsOutput.send``, nicht am Modulsymbol in
``notification_service``. Sonst waere eine Implementierung unsichtbar, die
``PremiumSmsOutput`` direkt im Reader importiert und am
``NotificationService`` vorbei sendet — und genau daran haengt AC-5: bei einem
Versand am Modulsymbol vorbei bliebe "im Trockenlauf ging nichts hinaus" gruen,
waehrend real ins Satellitennetz gesendet wird (Spec-Mutation 6). Dass der
Messpunkt genau EINMAL je Versand zaehlt und nicht doppelt, prueft
``test_messwerkzeug_zaehlt_einen_premium_sms_versand_genau_einmal`` an einem
echten Briefing-Versand nach.

Nutzerkennungen tragen bewusst KEIN "tdd"/"test": ``is_test_user_id``
erzwaenge sonst ``Settings.for_testing()`` und ueberschriebe die
Profil-Aufloesung, die AC-7 gerade misst.

Heute GRUEN und bewusst so (Regressionswaechter fuer die Spec-Mutationen 2, 4,
6): ``test_ac4_*``, ``test_ac5_*``, ``test_ac9_*`` sagen "es geht nichts
hinaus" zu — was heute schon stimmt, weil noch gar nichts verarbeitet wird.
Ihr Wert entsteht NACH der Implementierung.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import services.inbound_sms_reader as reader_mod  # noqa: E402
from app.config import Settings  # noqa: E402
from app.loader import get_data_dir, load_all_trips, save_trip  # noqa: E402
from app.models import TripReportConfig  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from output.channels.premium_sms import PremiumSmsOutput  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage,
    TripCommandProcessor,
)
from services.trip_report_scheduler import (  # noqa: E402
    TripReportSchedulerService,
)
from utils.timezone import tz_for_coords  # noqa: E402

#: Exakter Standort aus ``providers/fixture.py::_FIXTURE_LOCATIONS`` — so
#: trifft der Nearest-Neighbour-Zuordner garantiert ``innsbruck.json`` und der
#: Wetterabruf bleibt offline (``# fake-provider-seam``, #346).
INNSBRUCK = (47.2692, 11.4041)

#: Versand-Reihenfolge in ``NotificationService.send_trip_report`` — dieselbe
#: Reihenfolge steht in ``briefing_log.channels``.
ALLE_KANAELE = ("email", "sms", "premium_sms", "telegram")

VIER_KANAELE_AN = {
    "send_email": True, "send_sms": True,
    "send_premium_sms": True, "send_telegram": True,
}

SERVICE_NUMBER = "4916092172595"   # oeffentliche Dienstnummer aus Issue #1676
NUMMER_A = "4917000000001"
NUMMER_B = "4917000000002"
RUECKADRESSE_A = "+4917000000001"
RUECKADRESSE_B = "+4917000000002"
#: Rueckadresse des Mandanten "default". Sie darf NIE bedient werden, wenn der
#: Lernaufruf keine `user_id` liefert (AC-9, Cross-User-Datenleck-Verbot).
RUECKADRESSE_DEFAULT = "+4917000000099"

#: Jedes Transport-Feld ausdruecklich belegt (#1477) — ein weggelassenes Feld
#: faellt bei pydantic still auf die Prod-``.env`` zurueck. Unbrauchbar, aber
#: VOLLSTAENDIG: sonst waere "Kanal nicht bedient" nur fehlende Zugangsdaten.
_TRANSPORT_ENV = {
    "GZ_ENV": "development",
    "GZ_SMTP_HOST": "smtp.invalid",
    "GZ_SMTP_USER": "unbrauchbar",
    "GZ_SMTP_PASS": "unbrauchbar",
    "GZ_MAIL_FROM": "gregor@example.invalid",
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
# Aussengrenze 1+2: seven.io-Journal und der interne Lern-Endpunkt
# ---------------------------------------------------------------------------


class _Journal:
    """``GET journal/inbound``. ``seiten`` ist eine Liste von Journal-Listen —
    eine je aufeinanderfolgendem Abruf, die letzte wird wiederholt.

    Fix F004 (#1676): die echte API liefert ``id`` als ZEICHENKETTE.
    """

    def __init__(self, seiten: list[list[dict]]) -> None:
        self._seiten = seiten
        self.abrufe = 0

    def __call__(self, url, headers=None, params=None, timeout=None, **kw):
        self.abrufe += 1
        idx = min(self.abrufe - 1, len(self._seiten) - 1)
        return httpx.Response(200, json=self._seiten[idx])


class _LernEndpunkt:
    """``POST /api/internal/premium-sms-learn``, mit der Antwortform des
    echten Go-Endpunkts (``{"status":"ok","user_id":...}``, ``:115``).

    Er bildet die Vertragslogik des Endpunkts NICHT nach und schreibt nichts —
    er sagt nur, welche Nummer welchem Mandanten zugeordnet wurde. Genau diese
    Zuordnung ist der Eingang, den der Reader konsumieren soll.
    """

    def __init__(self, *, nummer_zu_user: dict[str, str] | None = None,
                 status: int = 200, antwort: dict | None = None) -> None:
        self._nummer_zu_user = nummer_zu_user or {}
        self._status = status
        self._antwort = antwort
        self.aufrufe: list[dict] = []

    def __call__(self, url, json=None, timeout=None, **kw):  # noqa: A002
        self.aufrufe.append({"url": url, "json": json})
        assert url.endswith("/api/internal/premium-sms-learn"), url
        if (json or {}).get("dry_run"):
            # Realer Vertrag (`premium_sms_connect.go:76-94`, gegengelesen
            # 2026-09-08): auch der Trockenlauf loest den Nutzer auf und
            # liefert bei eindeutiger Zuordnung `user_id` UND `masked_from`;
            # nur ohne eindeutigen Kandidaten kommt `would_skip`. Ohne die
            # `user_id` liefe AC-5 in den AC-9-Guard (fehlende Kennung) statt
            # ins Dry-Run-Gate und waere zufaellig gruen statt bewachend.
            ziel = self._nummer_zu_user.get((json or {})["from"])
            if ziel is None:
                return httpx.Response(200, json={
                    "status": "dry_run", "outcome": "would_skip",
                    "reason": "no_unique_premium_candidate"})
            return httpx.Response(200, json={
                "status": "dry_run", "outcome": "would_learn",
                "user_id": ziel,
                "masked_from": "*" * (len((json or {})["from"]) - 3)
                               + (json or {})["from"][-3:]})
        if self._status != 200:
            return httpx.Response(
                self._status, json=self._antwort or {
                    "error": "no_unique_premium_candidate"})
        if self._antwort is not None:
            return httpx.Response(200, json=self._antwort)
        return httpx.Response(200, json={
            "status": "ok",
            "user_id": self._nummer_zu_user[(json or {})["from"]],
        })


class _HttpSchicht:
    """Ersetzt ``httpx`` NUR im Reader-Modul — der Rest des Prozesses behaelt
    das echte ``httpx``. Eine globale Ersetzung raubte den uebrigen
    Bausteinen ihren echten Transport und machte den Testlauf unlesbar."""

    def __init__(self, journal: _Journal, lernen: _LernEndpunkt) -> None:
        self.get = journal
        self.post = lernen


def _garmin(msg_id: int, sender: str, befehl: str) -> dict:
    """Eine echte Garmin-Nachricht: Nutzertext, dann Kennzeichen, Link und
    Koordinaten (Beleg #1676 S1, gemessen 2026-08-10)."""
    return {
        "id": str(msg_id),
        "from": sender,
        "to": SERVICE_NUMBER,
        "text": (f"{befehl} inreachlink.com/g-0Ab1Cd2Ef... "
                 f"({INNSBRUCK[0]}, {INNSBRUCK[1]})"),
        "timestamp": "2026-09-08 08:30:14",
        "reply_to_message_id": None,
        "price": 0.0,
    }


# ---------------------------------------------------------------------------
# Aussengrenze 3: die vier Kanal-Ausgaenge
# ---------------------------------------------------------------------------


class Kanalmitschrift:
    """Was tatsaechlich hinausging — je Kanal Empfaenger, Betreff und Text."""

    def __init__(self) -> None:
        self.je_kanal: dict[str, list[dict]] = {k: [] for k in ALLE_KANAELE}

    @property
    def kanaele(self) -> list[str]:
        return [k for k in ALLE_KANAELE if self.je_kanal[k]]

    @property
    def premium(self) -> list[dict]:
        return self.je_kanal["premium_sms"]

    def empfaenger(self, kanal: str) -> list[str]:
        return [e["empfaenger"] for e in self.je_kanal[kanal]]

    def alle_empfaenger(self) -> list:
        return [e["empfaenger"] for k in ALLE_KANAELE for e in self.je_kanal[k]]

    def __repr__(self) -> str:
        return f"Kanalmitschrift({({k: v for k, v in self.je_kanal.items() if v})})"


def _aufzeichner_installieren(monkeypatch) -> Kanalmitschrift:
    """Echte Klassen mit den echten ``send()``-Signaturen ersetzen die vier
    Ausgaenge. Sie ersetzen die Naht zum Netz, NICHT die Entscheidung darueber,
    wer bedient wird — die faellt weiter im Produktivcode.

    E-Mail/SMS/Telegram werden als Modulsymbol in ``notification_service``
    ersetzt (dort liegt ihr einziger Aufrufort). Premium-SMS dagegen an der
    KLASSE — Begruendung im Modul-Docstring.
    """
    from services import notification_service as ns

    mit = Kanalmitschrift()

    def _buchen(kanal: str, empfaenger, subject: str, body: str) -> None:
        mit.je_kanal[kanal].append(
            {"empfaenger": empfaenger, "subject": subject, "body": body})

    class _EmailAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body, html=True, plain_text_body=None, to=None,
                 mail_type=None, mail_format=None, compare_hourly_enabled=None):
            ziel = to if to else self._s.mail_to
            _buchen("email", ziel if isinstance(ziel, str) else list(ziel)[0],
                    subject, body)

    class _SmsAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body) -> None:
            _buchen("sms", self._s.sms_to, subject, body)

    def _premium_sms_send(self, subject, body) -> None:
        """Ersetzt ``PremiumSmsOutput.send`` an der KLASSE — jeder Importweg
        landet hier. ``self._settings`` ist das echte, nutzerbezogene
        Settings-Objekt, das der Produktivcode uebergeben hat; die
        Empfaenger-Aufloesung wird damit an derselben Quelle gemessen, aus der
        auch ``_resolve_recipient()`` liest."""
        _buchen("premium_sms", self._settings.premium_sms_reply_to,
                subject, body)

    class _TelegramAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body, reply_markup=None, *, parse_mode=None,
                 suppress_subject_line=False) -> int:
            _buchen("telegram", self._s.telegram_chat_id, subject, body)
            return 1

    monkeypatch.setattr(ns, "EmailOutput", _EmailAufzeichner)
    monkeypatch.setattr(ns, "SMSOutput", _SmsAufzeichner)
    monkeypatch.setattr(ns, "TelegramOutput", _TelegramAufzeichner)
    # Premium-SMS an der Klasse, NICHT am Modulsymbol (Modul-Docstring).
    monkeypatch.setattr(PremiumSmsOutput, "send", _premium_sms_send)
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
    return f"premsms-{praefix}-{uuid.uuid4().hex[:6]}"


def _nutzer_anlegen(user_id: str, *, rueckadresse: str,
                    tier: str = "premium") -> None:
    """Echtes ``user.json`` mit bereits GELERNTER Premium-SMS-Rueckadresse."""
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": user_id,
        "tier": tier,
        "mail_to": f"{user_id}@example.invalid",
        "telegram_chat_id": f"chat-{user_id}",
        "sms_to": "+490000000001",
        "premium_sms_reply_to": rueckadresse,
        "premium_sms_reply_at": datetime.now(timezone.utc).isoformat(),
    }))


def _trip_anlegen(user_id: str, *, name: str) -> Trip:
    """Drei Etappen (gestern/heute/morgen am Ortstag) am Fixture-Standort.

    ``official_alerts_enabled=False``: amtliche Warnungen kennen keine
    Fixture-Naht und haengten diesen Kern-Test sonst ans Netz.
    """
    zone = tz_for_coords(*INNSBRUCK)
    heute = datetime.now(timezone.utc).astimezone(zone).date()
    trip_id = f"premsms-{uuid.uuid4().hex[:8]}"
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
        report_config=TripReportConfig(trip_id=trip_id, **VIER_KANAELE_AN),
    )
    save_trip(trip, user_id)
    # Zurueck von der Platte: ``save_trip`` rechnet Ankunftszeiten neu.
    return next(t for t in load_all_trips(user_id) if t.id == trip_id)


def _poll(monkeypatch, *, journal: _Journal, lernen: _LernEndpunkt,
          herkunft: str = "production", dry_run_env: bool = False,
          reader: reader_mod.InboundSmsReader | None = None,
          ) -> tuple[reader_mod.InboundSmsReader, int]:
    """Ein echter Poll-Lauf: ``InboundSmsReader.poll_and_process(settings)``.

    ``herkunft`` steuert die Herkunftssperre ausdruecklich, statt sich darauf
    zu verlassen, aus welchem Checkout der Testlauf gerade stammt — im
    Hauptcheckout waere die Herkunft "production" und der Trockenlauf-Test
    (AC-5) liefe still am Prueffall vorbei.
    """
    monkeypatch.setattr(reader_mod, "classify_origin", lambda root: herkunft)
    monkeypatch.setattr(reader_mod, "httpx", _HttpSchicht(journal, lernen))
    if dry_run_env:
        monkeypatch.setenv(reader_mod.DRYRUN_ENV_VAR, "1")
    else:
        monkeypatch.delenv(reader_mod.DRYRUN_ENV_VAR, raising=False)
    r = reader or reader_mod.InboundSmsReader()
    return r, r.poll_and_process(Settings(_env_file=None))


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


def _erwartete_antwort(trip: Trip, *, befehl: str, user_id: str,
                       absender: str):
    """Die Antwort, die der Kommandoverarbeiter auf denselben Befehl gibt —
    Vergleichsmassstab fuer AC-2/AC-3.

    Beide Befehle sind lesend (``status``/unbekannt), der Vergleichslauf
    veraendert also nichts. Der Test prueft damit, dass der Reader die Antwort
    UNVERAENDERT durchreicht, statt eigenen Text zu erfinden.
    """
    return TripCommandProcessor().process(InboundMessage(
        trip_name=trip.name, body=befehl, sender=absender,
        channel="premium_sms", received_at=datetime.now(timezone.utc),
        user_id=user_id,
    ))


def _prozessoraufrufe_aufzeichnen(monkeypatch) -> list[InboundMessage]:
    """Zeichnet jeden ``TripCommandProcessor.process()``-Aufruf auf — an der
    KLASSE, damit jeder Importweg erfasst wird.

    Reiner Durchreicher: die echte Verarbeitung laeuft unveraendert weiter, der
    Beobachter verfaelscht sie nicht. Ein Aufzeichner, der stattdessen wuerfe,
    taugte hier nicht — der Reader faengt Verarbeitungsfehler laut Spec
    (Schritt 8) ab, der Fehlschlag kaeme also nie beim Test an.
    """
    aufrufe: list[InboundMessage] = []
    echt = TripCommandProcessor.process

    def _mitschreiben(self, msg):
        aufrufe.append(msg)
        return echt(self, msg)

    monkeypatch.setattr(TripCommandProcessor, "process", _mitschreiben)
    return aufrufe


# ══════════════ Positivkontrolle fuer das Messinstrument selbst ═════════════


def test_messwerkzeug_zaehlt_einen_premium_sms_versand_genau_einmal(mitschrift):
    """Positivkontrolle — heute GRUEN, prueft die Pruefung.

    GIVEN ein Premium-Nutzer mit gelernter Rueckadresse und ein Trip mit einer
          Etappe am heutigen Ortstag.
    WHEN  GENAU EIN Briefing ueber den produktiven Versandpfad hinausgeht
          (``send_on_demand_report(..., restrict_to_channel="premium_sms")`` —
          derselbe Pfad, den AC-1/AC-10 spaeter ausloesen).
    THEN  steht in der Mitschrift GENAU EIN Premium-SMS-Eintrag mit der
          richtigen Rueckadresse.

    Zweck: Der Premium-SMS-Messpunkt haengt an der Klasse
    ``PremiumSmsOutput.send``. Laege zusaetzlich ein Aufzeichner auf dem
    Modulsymbol in ``notification_service``, zaehlte derselbe Versand zweimal
    — dann waere ``len(...) == 1`` in AC-10 unerfuellbar und ``== 2`` in AC-5
    ein falscher Alarm. Ohne diese Kontrolle bliebe unbelegt, dass der
    Messpunkt den NotificationService-Pfad ueberhaupt sieht: eine leere
    Mitschrift in AC-4/AC-5/AC-9 hiesse dann "gar nicht gemessen" statt
    "nichts gesendet".
    """
    uid = _kennung("messpunkt")
    _nutzer_anlegen(uid, rueckadresse=RUECKADRESSE_A)
    trip = _trip_anlegen(uid, name="Messpunkt Kontrolle")

    ergebnis = TripReportSchedulerService(user_id=uid).send_on_demand_report(
        trip, "morning", restrict_to_channel="premium_sms",
    )

    assert ergebnis.outcome == "sent", (
        f"Vorbedingung: das Briefing muss tatsaechlich versendet worden sein, "
        f"Ergebnis war {ergebnis.outcome!r}")
    assert len(mitschrift.premium) == 1, (
        f"Das Messinstrument muss EINEN Versand GENAU EINMAL buchen — "
        f"gebucht wurden {len(mitschrift.premium)}: {mitschrift.premium!r}")
    assert mitschrift.empfaenger("premium_sms") == [RUECKADRESSE_A], (
        f"Der gebuchte Empfaenger muss die gelernte Rueckadresse sein, "
        f"gebucht wurde {mitschrift.empfaenger('premium_sms')!r}")


# ═══════════════════════════ AC-1 ════════════════════════════════════════════


def test_ac1_heute_loest_briefing_ausschliesslich_per_premium_sms_aus(
    monkeypatch, mitschrift,
):
    """AC-1.

    GIVEN eine Garmin-Nachricht "heute inreachlink.com/g-xxx (lat, lon)" von
          einer Nummer, die der Lernaufruf eindeutig einem Premium-Nutzer
          zuordnet, dessen Trip alle vier Kanaele aktiviert hat.
    WHEN  der Journal-Poll laeuft.
    THEN  wird das Tagesbriefing ausgeloest und AUSSCHLIESSLICH per
          Premium-SMS zugestellt — ``briefing_log.channels == ["premium_sms"]``.

    Der Trip hat bewusst alle vier Kanaele an: nur so ist belegt, dass die
    Beschraenkung vom Anfrageweg kommt und nicht davon, dass ohnehin nur ein
    Kanal konfiguriert waere.

    RED heute: der Nachrichtentext wird verworfen, es geht gar nichts hinaus —
    ``mitschrift.kanaele == []``.
    """
    uid = _kennung("ac1")
    _nutzer_anlegen(uid, rueckadresse=RUECKADRESSE_A)
    trip = _trip_anlegen(uid, name="Premium Kommando AC1")

    _poll(monkeypatch,
          journal=_Journal([[_garmin(1001, NUMMER_A, "heute")]]),
          lernen=_LernEndpunkt(nummer_zu_user={NUMMER_A: uid}))

    assert mitschrift.kanaele == ["premium_sms"], (
        f"AC-1: eine per Premium-SMS gestellte 'heute'-Anfrage muss das "
        f"Briefing ausloesen und AUSSCHLIESSLICH per Premium-SMS beantworten, "
        f"bedient wurden {mitschrift.kanaele} ({mitschrift!r})")
    assert mitschrift.empfaenger("premium_sms") == [RUECKADRESSE_A], (
        f"AC-1: das Briefing muss an die gelernte Rueckadresse gehen, "
        f"gesendet wurde an {mitschrift.empfaenger('premium_sms')}")
    assert _log_kanaele(uid, trip.id) == ["premium_sms"], (
        f"AC-1: briefing_log.channels muss ['premium_sms'] sein, ist "
        f"{_log_kanaele(uid, trip.id)}")


# ═══════════════════════════ AC-2 ════════════════════════════════════════════


def test_ac2_bekanntes_bare_keyword_antwortet_unveraendert_per_premium_sms(
    monkeypatch, mitschrift,
):
    """AC-2.

    GIVEN eine Garmin-Nachricht mit dem bekannten Bare-Keyword "status" vor
          dem Kennzeichen.
    WHEN  der Poll laeuft.
    THEN  geht die ``confirmation_body`` des Kommandoverarbeiters UNVERAENDERT
          per Premium-SMS an die gelernte Rueckadresse zurueck.

    Der Vergleichsmassstab entsteht aus einem echten
    ``TripCommandProcessor.process()``-Lauf mit derselben Nachricht — ein im
    Test getippter Soll-Text pruefte eine Welt, die es nicht gibt.

    RED heute: keine Antwort, ``mitschrift.premium == []``.
    """
    uid = _kennung("ac2")
    _nutzer_anlegen(uid, rueckadresse=RUECKADRESSE_A)
    trip = _trip_anlegen(uid, name="Premium Kommando AC2")

    _poll(monkeypatch,
          journal=_Journal([[_garmin(1002, NUMMER_A, "status")]]),
          lernen=_LernEndpunkt(nummer_zu_user={NUMMER_A: uid}))

    erwartet = _erwartete_antwort(trip, befehl="status", user_id=uid,
                                  absender=NUMMER_A)
    assert erwartet.success, f"Vorbedingung: 'status' muss antworten: {erwartet}"

    assert len(mitschrift.premium) == 1, (
        f"AC-2: genau EINE Premium-SMS-Antwort erwartet, gesehen "
        f"{len(mitschrift.premium)} ({mitschrift!r})")
    gesendet = mitschrift.premium[0]
    assert gesendet["empfaenger"] == RUECKADRESSE_A, (
        f"AC-2: die Antwort muss an die gelernte Rueckadresse gehen, ging an "
        f"{gesendet['empfaenger']!r}")
    assert gesendet["body"] == erwartet.confirmation_body, (
        f"AC-2: der Reader muss die Antwort des Kommandoverarbeiters "
        f"unveraendert durchreichen.\nGesendet: {gesendet['body']!r}\n"
        f"Erwartet: {erwartet.confirmation_body!r}")
    assert gesendet["subject"] == erwartet.confirmation_subject, (
        f"AC-2: auch der Betreff kommt unveraendert aus dem Verarbeiter, "
        f"gesendet wurde {gesendet['subject']!r} statt "
        f"{erwartet.confirmation_subject!r}")


# ═══════════════════════════ AC-3 ════════════════════════════════════════════


def test_ac3_unbekannter_text_erhaelt_die_unbekannt_antwort_per_premium_sms(
    monkeypatch, mitschrift,
):
    """AC-3.

    GIVEN eine Garmin-Nachricht, deren Text vor dem Kennzeichen zu keinem
          bekannten Befehl passt — die reale Erstverbindungsnachricht des
          Geraets ("Test ueber App …", Beleg #1676 S1).
    WHEN  der Poll laeuft.
    THEN  erhaelt der Nutzer dieselbe "Unbekannter Befehl"-Antwort wie ueber
          E-Mail/Telegram, per Premium-SMS — kein stilles Verwerfen.

    RED heute: die Nachricht wird stillschweigend verworfen.
    """
    uid = _kennung("ac3")
    _nutzer_anlegen(uid, rueckadresse=RUECKADRESSE_A)
    trip = _trip_anlegen(uid, name="Premium Kommando AC3")

    _poll(monkeypatch,
          journal=_Journal([[_garmin(1003, NUMMER_A, "Test ueber App")]]),
          lernen=_LernEndpunkt(nummer_zu_user={NUMMER_A: uid}))

    erwartet = _erwartete_antwort(trip, befehl="Test ueber App", user_id=uid,
                                  absender=NUMMER_A)
    assert not erwartet.success and erwartet.command == "unknown", (
        f"Vorbedingung: dieser Text MUSS im Unbekannt-Zweig landen, sonst "
        f"prueft der Test etwas anderes: {erwartet}")

    assert len(mitschrift.premium) == 1, (
        f"AC-3: ein unbekannter Befehl darf nicht still verworfen werden — "
        f"genau EINE Premium-SMS-Antwort erwartet, gesehen "
        f"{len(mitschrift.premium)} ({mitschrift!r})")
    assert mitschrift.premium[0]["body"] == erwartet.confirmation_body, (
        f"AC-3: es muss die unveraenderte 'Unbekannter Befehl'-Antwort sein.\n"
        f"Gesendet: {mitschrift.premium[0]['body']!r}\n"
        f"Erwartet: {erwartet.confirmation_body!r}")


# ═══════════════════════════ AC-4 ════════════════════════════════════════════


def test_ac4_mehrdeutige_absendernummer_loest_keine_verarbeitung_aus(
    monkeypatch, mitschrift,
):
    """AC-4 — Regressionswaechter, heute GRUEN.

    GIVEN eine Garmin-Nachricht, deren Absendernummer der Lernaufruf NICHT
          eindeutig zuordnen kann (HTTP 409, ``no_unique_premium_candidate``).
    WHEN  der Poll laeuft.
    THEN  wird keine Kommandoverarbeitung ausgeloest und ueber KEINEN Kanal
          etwas versendet — es gibt keine bekannte Zieladresse.

    Beobachtet wird der tatsaechliche Versand, nicht ein Zwischenwert: ohne
    Zieladresse darf nichts hinausgehen, egal an welcher Stelle die
    Verarbeitung abbricht.

    Vorbedingung im selben Test: der Lernaufruf ist tatsaechlich erfolgt —
    sonst belegte die leere Mitschrift nur, dass der Poll gar nicht lief.
    """
    uid = _kennung("ac4")
    _nutzer_anlegen(uid, rueckadresse=RUECKADRESSE_A)
    _trip_anlegen(uid, name="Premium Kommando AC4")

    lernen = _LernEndpunkt(status=409)
    _poll(monkeypatch,
          journal=_Journal([[_garmin(1004, NUMMER_A, "heute")]]),
          lernen=lernen)

    assert len(lernen.aufrufe) == 1, (
        f"Vorbedingung: der Poll muss den Lernaufruf abgesetzt haben, "
        f"gesehen: {lernen.aufrufe!r}")
    assert mitschrift.kanaele == [], (
        f"AC-4: ohne eindeutige Zuordnung darf NICHTS versendet werden, "
        f"bedient wurden {mitschrift.kanaele} ({mitschrift!r})")


# ═══════════════════════════ AC-5 ════════════════════════════════════════════


def test_ac5_trockenlauf_setzt_keine_einzige_premium_sms_ab(
    monkeypatch, mitschrift,
):
    """AC-5 — Regressionswaechter, heute GRUEN.

    GIVEN die Herkunft ist nicht "production" und ``GZ_PREMIUM_SMS_POLL_DRYRUN
          =1`` (Trockenlauf).
    WHEN  eine Garmin-Nachricht mit gueltigem Befehlstext ("heute") eintrifft.
    THEN  wird WEDER ``TripCommandProcessor.process`` gerufen NOCH eine
          einzige Premium-SMS abgesetzt — beide Haelften des Spec-Wortlauts.

    Gemessen wird der tatsaechliche Versandaufruf an
    ``PremiumSmsOutput.send`` (Klassen-Messpunkt, s. Modul-Docstring), nicht
    der Zaehler ``learned == 0``: ein Trockenlauf, der ins Satellitennetz
    sendet, bliebe sonst unentdeckt (Spec-Mutation 6, Dry-Run-Gate hinter die
    Verarbeitung geschoben). Der Prozessor-Aufruf wird zusaetzlich beobachtet,
    weil eine Verarbeitung schon vor dem Versand Nebenwirkungen haette
    (Wetterabruf, Schnappschuss, ``briefing_log``).

    Vorbedingung im selben Test: der Lernaufruf traegt ``dry_run: True`` —
    damit ist belegt, dass der Poll wirklich gelaufen ist und die leere
    Mitschrift nicht bloss "Poll uebersprungen" bedeutet.
    """
    uid = _kennung("ac5")
    _nutzer_anlegen(uid, rueckadresse=RUECKADRESSE_A)
    _trip_anlegen(uid, name="Premium Kommando AC5")

    prozessoraufrufe = _prozessoraufrufe_aufzeichnen(monkeypatch)
    lernen = _LernEndpunkt(nummer_zu_user={NUMMER_A: uid})
    _, gelernt = _poll(
        monkeypatch,
        journal=_Journal([[_garmin(1005, NUMMER_A, "heute")]]),
        lernen=lernen, herkunft="test", dry_run_env=True,
    )

    assert len(lernen.aufrufe) == 1 and lernen.aufrufe[0]["json"].get("dry_run"), (
        f"Vorbedingung: der Trockenlauf muss den Lernaufruf mit dry_run=True "
        f"abgesetzt haben, gesehen: {lernen.aufrufe!r}")
    assert gelernt == 0, (
        f"Vorbedingung: im Trockenlauf wird strukturell nichts gelernt, "
        f"gemeldet wurden {gelernt}")
    assert prozessoraufrufe == [], (
        f"AC-5: im Trockenlauf darf TripCommandProcessor.process gar nicht "
        f"gerufen werden, gerufen wurde es mit "
        f"{[m.body for m in prozessoraufrufe]!r}")
    assert mitschrift.premium == [], (
        f"AC-5: im Trockenlauf darf KEINE einzige Premium-SMS abgesetzt "
        f"werden, gesehen: {mitschrift.premium!r}")
    assert mitschrift.kanaele == [], (
        f"AC-5: im Trockenlauf darf ueberhaupt nichts versendet werden, "
        f"bedient wurden {mitschrift.kanaele} ({mitschrift!r})")


# ═══════════════════════════ AC-6 ════════════════════════════════════════════


class _WerfenderProzessor:
    """Ein Kommandoverarbeiter, der bei jedem ``process()`` scheitert.

    Kein Mock, sondern eine echte Klasse mit der echten Signatur: sie erzeugt
    genau den Fehlerfall, den AC-6 beschreibt (Verarbeitungsfehler NACH einem
    erfolgreichen Lernaufruf), und laesst alles andere im Produktivcode.
    """

    def process(self, msg):
        raise RuntimeError(
            "Verarbeitungsfehler (Testfixtur AC-6) — der Lernaufruf war "
            "erfolgreich, erst die Kommandoverarbeitung scheitert.")


def test_ac6_verarbeitungsfehler_laesst_zeiger_wandern_und_zaehler_bei_null(
    monkeypatch, mitschrift,
):
    """AC-6.

    GIVEN eine Exception waehrend der Kommandoverarbeitung, NACH einem
          erfolgreichen Lernaufruf.
    WHEN  der Poll laeuft und danach ein ZWEITER Poll mit einem zusaetzlichen,
          neueren Journal-Eintrag.
    THEN  hat der Dedup-Zeiger die erste Nachricht passiert — der zweite Lauf
          ruft den Lern-Endpunkt nur noch fuer die NEUE Nachricht auf — und
          ``last_failed_count`` bleibt in beiden Laeufen bei 0.

    Zwei Poll-Laeufe sind Pflicht: erst der zweite macht den Zeigerstand
    sichtbar. Ein Test auf ``learned == 0`` faenge weder ein ``break`` statt
    ``continue`` (Spec-Mutation 2) noch ein in den Lernblock hineingezogenes
    ``except`` (Spec-Mutation 5).

    RED heute: ``services.inbound_sms_reader`` kennt kein
    ``TripCommandProcessor`` — die Fehlereinspeisung findet ihren Angriffspunkt
    nicht (AttributeError).
    """
    uid = _kennung("ac6")
    _nutzer_anlegen(uid, rueckadresse=RUECKADRESSE_A)
    _trip_anlegen(uid, name="Premium Kommando AC6")

    lernen = _LernEndpunkt(nummer_zu_user={NUMMER_A: uid, NUMMER_B: uid})
    monkeypatch.setattr(reader_mod, "TripCommandProcessor", _WerfenderProzessor)

    reader, _ = _poll(
        monkeypatch,
        journal=_Journal([[_garmin(1006, NUMMER_A, "status")]]),
        lernen=lernen,
    )

    assert reader.last_failed_count == 0, (
        f"AC-6: ein reiner Verarbeitungsfehler darf NICHT als "
        f"voruebergehender Lernfehler (F001) gezaehlt werden — sonst kippt der "
        f"Go-Scheduler-Status von 'ok' auf 'partial'. "
        f"last_failed_count={reader.last_failed_count}")
    assert len(lernen.aufrufe) == 1, (
        f"Vorbedingung: der Lernaufruf des ersten Laufs muss erfolgt sein, "
        f"gesehen: {lernen.aufrufe!r}")

    # Zweiter Lauf mit dem echten Verarbeiter — das Journal liefert die alte
    # UND eine neue Nachricht (so verhaelt sich seven.io: das Fenster bleibt).
    monkeypatch.setattr(reader_mod, "TripCommandProcessor", TripCommandProcessor)
    vor_lauf_zwei = len(lernen.aufrufe)
    _poll(
        monkeypatch,
        journal=_Journal([[_garmin(1006, NUMMER_A, "status"),
                           _garmin(1007, NUMMER_B, "status")]]),
        lernen=lernen, reader=reader,
    )

    zweiter_lauf = [a["json"]["from"] for a in lernen.aufrufe[vor_lauf_zwei:]]
    assert zweiter_lauf == [NUMMER_B], (
        f"AC-6: der Dedup-Zeiger muss ueber die gescheiterte Nachricht "
        f"hinweggewandert sein — der zweite Lauf darf NUR die neue Nachricht "
        f"melden, gemeldet wurden {zweiter_lauf!r}")
    assert reader.last_failed_count == 0, (
        f"AC-6: auch der zweite Lauf darf keinen Fehlschlag buchen, "
        f"last_failed_count={reader.last_failed_count}")


# ═══════════════════════════ AC-7 ════════════════════════════════════════════


def test_ac7_zwei_nutzer_erhalten_je_ihre_eigene_antwort(monkeypatch, mitschrift):
    """AC-7 — Mandantentrennung.

    GIVEN zwei Premium-Nutzer mit je eigener gelernter Rueckadresse und je
          eigener aktiver Tour.
    WHEN  beide unabhaengig voneinander eine Garmin-Nachricht ("status")
          senden und derselbe Poll beide verarbeitet.
    THEN  erhaelt jeder Nutzer die Antwort auf SEINE Tour an SEINE gelernte
          Nummer — keine Kreuzung, kein Rueckfall auf einen gemeinsamen Wert.

    Zwei Nutzer sind Pflicht: ein Ein-Nutzer-Test bliebe auch dann gruen, wenn
    der Reader statt ``user_id`` einen falschen Schluessel laese und auf die
    Basis-Settings zurueckfiele (Spec-Mutation 4).

    RED heute: es geht nichts hinaus.
    """
    uid_a, uid_b = _kennung("ac7a"), _kennung("ac7b")
    _nutzer_anlegen(uid_a, rueckadresse=RUECKADRESSE_A)
    _nutzer_anlegen(uid_b, rueckadresse=RUECKADRESSE_B)
    trip_a = _trip_anlegen(uid_a, name="Tour Anna AC7")
    trip_b = _trip_anlegen(uid_b, name="Tour Bert AC7")

    _poll(monkeypatch,
          journal=_Journal([[_garmin(1008, NUMMER_A, "status"),
                             _garmin(1009, NUMMER_B, "status")]]),
          lernen=_LernEndpunkt(nummer_zu_user={NUMMER_A: uid_a,
                                               NUMMER_B: uid_b}))

    je_nummer = {e["empfaenger"]: e for e in mitschrift.premium}
    assert sorted(je_nummer) == sorted([RUECKADRESSE_A, RUECKADRESSE_B]), (
        f"AC-7: jeder der beiden Nutzer muss genau eine Antwort an seine "
        f"eigene gelernte Nummer erhalten, bedient wurden "
        f"{sorted(je_nummer)} ({mitschrift!r})")

    assert trip_a.name in je_nummer[RUECKADRESSE_A]["subject"], (
        f"AC-7: die Antwort an {RUECKADRESSE_A} muss sich auf {trip_a.name!r} "
        f"beziehen, Betreff war {je_nummer[RUECKADRESSE_A]['subject']!r}")
    assert trip_b.name in je_nummer[RUECKADRESSE_B]["subject"], (
        f"AC-7: die Antwort an {RUECKADRESSE_B} muss sich auf {trip_b.name!r} "
        f"beziehen, Betreff war {je_nummer[RUECKADRESSE_B]['subject']!r}")
    assert trip_b.name not in je_nummer[RUECKADRESSE_A]["body"], (
        f"AC-7: die Antwort an {RUECKADRESSE_A} darf die fremde Tour nicht "
        f"nennen: {je_nummer[RUECKADRESSE_A]['body']!r}")
    assert trip_a.name not in je_nummer[RUECKADRESSE_B]["body"], (
        f"AC-7: die Antwort an {RUECKADRESSE_B} darf die fremde Tour nicht "
        f"nennen: {je_nummer[RUECKADRESSE_B]['body']!r}")


# ═══════════════════════════ AC-9 ════════════════════════════════════════════


@pytest.mark.parametrize("antwort", [
    {"status": "ok"},                 # Schluessel fehlt ganz
    {"status": "ok", "user_id": ""},  # Schluessel da, aber leer
], ids=["ohne_user_id", "leere_user_id"])
def test_ac9_200er_ohne_user_id_verarbeitet_nichts_und_faellt_nicht_zurueck(
    monkeypatch, mitschrift, antwort,
):
    """AC-9 — Regressionswaechter, heute GRUEN.

    GIVEN der Lernaufruf antwortet mit HTTP 200, aber ohne verwertbaren
          ``user_id``-Schluessel (fehlt oder leer) — der 200er-Vertrag ist
          durch keinen Contract-Test abgesichert.
    WHEN  der Poll laeuft.
    THEN  wird KEINE Kommandoverarbeitung ausgeloest und KEIN Rueckfall auf
          den Mandanten "default" vorgenommen.

    Der Mandant "default" existiert in diesem Test vollstaendig — mit eigener
    Tour, Premium-Tier und eigener gelernter Rueckadresse. Faellt der Reader
    still auf ihn zurueck, ginge eine Antwort an ``RUECKADRESSE_DEFAULT``
    hinaus; genau das misst die Zusicherung.
    """
    _nutzer_anlegen("default", rueckadresse=RUECKADRESSE_DEFAULT)
    _trip_anlegen("default", name="Tour Default AC9")

    lernen = _LernEndpunkt(antwort=antwort)
    _poll(monkeypatch,
          journal=_Journal([[_garmin(1010, NUMMER_A, "heute")]]),
          lernen=lernen)

    assert len(lernen.aufrufe) == 1, (
        f"Vorbedingung: der Lernaufruf muss erfolgt sein, gesehen: "
        f"{lernen.aufrufe!r}")
    assert RUECKADRESSE_DEFAULT not in mitschrift.alle_empfaenger(), (
        f"AC-9: ohne verwertbare user_id darf NICHTS an den Mandanten "
        f"'default' gehen (Cross-User-Datenleck-Verbot), bedient wurden "
        f"{mitschrift.alle_empfaenger()!r}")
    assert mitschrift.kanaele == [], (
        f"AC-9: ohne verwertbare user_id darf ueberhaupt nichts versendet "
        f"werden, bedient wurden {mitschrift.kanaele} ({mitschrift!r})")


# ═══════════════════════════ AC-10 ═══════════════════════════════════════════


def test_ac10_heute_setzt_genau_eine_premium_sms_ab(monkeypatch, mitschrift):
    """AC-10.

    GIVEN eine Garmin-Nachricht mit dem Text "heute" vor dem Kennzeichen.
    WHEN  der Poll laeuft.
    THEN  geht GENAU EINE Premium-SMS heraus — das ausgeloeste Briefing. Es
          gibt KEINE zusaetzliche Kommando-Bestaetigung daneben.

    Bewusst ``== 1`` und nicht ``>= 1``: faellt die Pruefung auf
    ``suppress_email_reply`` weg (Spec-Mutation 1), kaeme neben dem Briefing
    eine zweite, kostenpflichtige Satelliten-SMS heraus — ein Test auf "eine
    SMS ist angekommen" winkte das durch.

    RED heute: es geht keine einzige Premium-SMS heraus (0 statt 1).
    """
    uid = _kennung("ac10")
    _nutzer_anlegen(uid, rueckadresse=RUECKADRESSE_A)
    _trip_anlegen(uid, name="Premium Kommando AC10")

    _poll(monkeypatch,
          journal=_Journal([[_garmin(1011, NUMMER_A, "heute")]]),
          lernen=_LernEndpunkt(nummer_zu_user={NUMMER_A: uid}))

    assert len(mitschrift.premium) == 1, (
        f"AC-10: auf 'heute' darf GENAU EINE Premium-SMS herausgehen (das "
        f"Briefing, ohne zusaetzliche Bestaetigung), gesehen "
        f"{len(mitschrift.premium)}: {mitschrift.premium!r}")
