"""TDD RED -- Issue #1405 Scheibe S4b: "Erfolg heisst Wirkung" ausserhalb der
Befehlsverarbeitung (die letzten 8 Eintraege in ``KNOWN_VIOLATIONS``).

SPEC: docs/specs/modules/fix_1405_s4b_erfolg_heisst_wirkung.md (AC-1 bis AC-27)
CONTEXT: docs/context/fix-1405-s4b-erfolg-heisst-wirkung.md

Gemessen wird dort, wo die Zusicherung WIRKT: an der Antwort der echten
Router-Funktionen (``api/routers/scheduler.py``, direkt aufgerufen -- der
Rumpf IST der Endpunkt), an der Bilanz ``(sent, failed)`` von
``run_briefing_dispatch``, am Zaehler ``last_failed_count`` des echten
``InboundEmailReader.poll_and_process`` und am Draht (zugestellte/abgelehnte
Mails, Telegram-Anfragen). Die Go-Seite (``last_run.status``, AC-6/AC-7 Go,
AC-26) bewacht ``internal/scheduler/scheduler_inbound_status_test.go``.

Fakes NUR an Aussengrenzen:

* IMAP: ``imaplib.IMAP4_SSL`` -> ``_Postfach`` (Login-/Netzfehler, UNSEEN nur
  fuer nicht gelesene Mails).
* SMTP: ``smtplib.SMTP`` -> ``_SmtpDraht`` (554 je Empfaengeradresse); der
  ECHTE ``EmailOutput`` und das ECHTE ``send_command_reply_email`` laufen.
* Telegram/seven.io: ``KanalRig`` (lokale HTTP-Server, Issue #1405 S1) bzw.
  die Haus-Unterklassen ``_RecordingTelegram``/``EmailOutput.send``-Aufzeichner
  aus ``test_briefing_anchor_survives_dispatch_failure.py``.
* Wetterquelle: Unterklasse mit ``_fetch_weather``-Ersatz (Haus-Muster
  ``_fixture_scheduler``) bzw. ``weather_source=`` (Ortsvergleich). Die
  Router bauen ihre Dienste selbst; ersetzt wird dafuer das Modul-Attribut
  durch eine ECHTE Unterklasse, die nur ``settings=``/Wetterquelle setzt --
  Zaehl- und Pruefmethoden (``check_all_*``, ``_check_all_counted``,
  ``_process_pending_markers``, ``_send_trip_report_outcome``) bleiben echt.

Neue Felder (``failed`` bei ``/inbound-commands``, ``notice_failed``,
``last_failed_count`` am Mail-Leser, ``notice_failures``) werden nur zur
Laufzeit gelesen (``.get``/``getattr`` mit Platzhalter) -- jeder Test
scheitert an seinem Verhalten, nicht die Datei an einem Importfehler.

Netz: Kernschicht. Lauf wie CI (``--disable-socket --allow-unix-socket
--allow-hosts=127.0.0.1,::1,localhost``) -- nur die lokalen Draehte der
``KanalRig`` sind erreichbar.

Mandantentrennung: jede Kennung ist ein frischer Nutzer unter der je Test
isolierten Datenwurzel (``tests/conftest.py::_isolate_data_root``), die
``user_id`` wird immer explizit uebergeben, nie ``"default"``.

AC-ZUORDNUNG siehe Bericht der Phase /40; je Test steht der AC im Namen.
Regressionswaechter (in RED erwartet gruen): AC-7 (Python-Teil), AC-13,
AC-15 und die Gegenproben der neutralen Ausgaenge in AC-12; AC-19 bewacht
``tests/test_success_status_guard.py::test_intentional_exception_list_cannot_grow``.
"""
from __future__ import annotations

import fcntl
import imaplib
import json
import re
import smtplib
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.tdd._befehl_e2e_fixtures import (
    BefehlNutzer,
    _mime_plain,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

_FEHLT = "<Feld fehlt>"
_REPO = Path(__file__).resolve().parents[2]


# ═════════════════════════ Aussengrenzen: IMAP + SMTP ═══════════════════════


class _Postfach:
    """IMAP-Gegenstelle (``imaplib.IMAP4_SSL``-Ersatz). ``fehler``: Ausnahme,
    die beim Verbindungsaufbau (``OSError``) bzw. beim Login
    (``imaplib.IMAP4.error``) geworfen wird. ``UNSEEN`` liefert nur Mails ohne
    ``\\Seen`` -- ein zweiter Lauf sieht eine bereits gelesene Mail nicht."""

    def __init__(self, mails: list[bytes] | None = None, *, fehler: Exception | None = None):
        self.mails = {str(i + 1).encode(): raw for i, raw in enumerate(mails or [])}
        self.gelesen: set[bytes] = set()
        self.fehler = fehler
        self.verbindungen = 0

    def neue_mail(self, raw: bytes) -> None:
        self.mails[str(len(self.mails) + 1).encode()] = raw

    def __call__(self, host, port=None, *a, **kw):
        self.verbindungen += 1
        if isinstance(self.fehler, OSError):
            raise self.fehler
        return _Verbindung(self)


class _Verbindung:
    def __init__(self, postfach: _Postfach) -> None:
        self._p = postfach

    def login(self, user, password):
        if self._p.fehler is not None:
            raise self._p.fehler
        return "OK", [b"logged in"]

    def select(self, mailbox="INBOX"):
        return "OK", [str(len(self._p.mails)).encode()]

    def search(self, charset, *kriterien):
        offen = [uid for uid in self._p.mails if uid not in self._p.gelesen]
        return "OK", [b" ".join(offen)]

    def fetch(self, uid, spec):
        raw = self._p.mails[uid]
        return "OK", [(b"1 (RFC822 {%d})" % len(raw), raw)]

    def store(self, uid, flags, value):
        if "Seen" in value:
            self._p.gelesen.add(uid)
        return "OK", [b""]

    def logout(self):
        return "BYE", [b""]


class _SmtpDraht:
    """``smtplib.SMTP``-Ersatz: nimmt an oder lehnt je Empfaengeradresse
    permanent ab (554 -- der echte ``EmailOutput`` wiederholt das nicht und
    weicht nicht aus). Gezaehlt wird jeder Einlieferungsversuch."""

    def __init__(self) -> None:
        self.abgelehnt: set[str] = set()
        self.alle_ablehnen = False
        self.versuche: list[dict] = []
        self.zugestellt: list[dict] = []

    def an(self, adresse: str) -> list[dict]:
        return [m for m in self.zugestellt if adresse in m["an"]]

    def __call__(self, host, port=None, *a, **kw):
        draht = self

        class _Sock:
            def settimeout(self, _t) -> None:
                pass

        class _Verb:
            sock = _Sock()

            def __enter__(self):
                return self

            def __exit__(self, *exc) -> bool:
                return False

            def starttls(self) -> None:
                pass

            def login(self, user, password) -> None:
                pass

            def sendmail(self, from_addr, to_addrs, msg) -> None:
                eintrag = {"host": host, "an": [a.lower() for a in to_addrs], "roh": msg}
                draht.versuche.append(eintrag)
                if draht.alle_ablehnen or any(a in draht.abgelehnt for a in eintrag["an"]):
                    raise smtplib.SMTPResponseException(554, b"5.0.0 tdd-1405-s4b: abgelehnt")
                draht.zugestellt.append(eintrag)

        return _Verb()


def _inbound_umgebung(monkeypatch, postfach: _Postfach) -> _SmtpDraht:
    """Herkunftspins + hermetische Settings (Fundament #2417), dann IMAP- und
    SMTP-Draht dieser Datei."""
    import output.channels.email as email_mod

    install_transport_fakes(monkeypatch)
    draht = _SmtpDraht()
    monkeypatch.setattr(smtplib, "SMTP", draht)
    monkeypatch.setattr(email_mod.time, "sleep", lambda _s: None)
    monkeypatch.setattr(imaplib, "IMAP4_SSL", postfach)
    return draht


def _befehlsmail(nutzer: BefehlNutzer, *, ziel: str | None = None, befehl: str = "status") -> bytes:
    name = ziel if ziel is not None else nutzer.trip.name
    return _mime_plain(nutzer.mail_to, f"Re: [{name}] Etappe", befehl)


def _poll(settings=None):
    """Ein Lauf des ECHTEN Lesers; liefert (processed, last_failed_count)."""
    from services.inbound_email_reader import InboundEmailReader

    reader = InboundEmailReader()
    processed = reader.poll_and_process(settings or basis_settings())
    return processed, getattr(reader, "last_failed_count", _FEHLT)


@contextmanager
def _fremde_poll_sperre():
    """Haelt die Lauf-Sperre des Befehls-Posteingangs (eigene Dateibeschreibung
    -> ``flock`` des Routers bekommt sie nicht)."""
    from app.loader import get_data_root

    ordner = get_data_root() / "diagnostics"
    ordner.mkdir(parents=True, exist_ok=True)
    with open(ordner / "inbound_command_poll.lock", "a+") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


# ═══════════════════ B. Befehls-Posteingang (AC-2 bis AC-8) ══════════════════


@pytest.mark.parametrize("fehler", [
    imaplib.IMAP4.error("AUTHENTICATIONFAILED tdd-1405-s4b"),
    OSError("Network is unreachable (tdd-1405-s4b)"),
], ids=["imap_login", "netz"])
def test_ac2_postfach_nicht_erreichbar_meldet_partial_mit_failed(monkeypatch, fehler):
    """AC-2: GIVEN das Postfach des Befehls-Eingangs ist nicht erreichbar
    (Anmelde- bzw. Netzwerkfehler) / WHEN ``POST /api/scheduler/inbound-commands``
    laeuft / THEN antwortet er mit ``failed >= 1`` und ``status == "partial"``.

    RED heute: die Antwort ist fest ``{"status": "ok", ...}`` ohne ``failed``."""
    from api.routers.scheduler import trigger_inbound

    postfach = _Postfach(fehler=fehler)
    _inbound_umgebung(monkeypatch, postfach)

    body = trigger_inbound()

    assert postfach.verbindungen == 1, f"Messaufbau: der Draht wurde nicht erreicht: {body!r}"
    assert body.get("failed", _FEHLT) != _FEHLT and body["failed"] >= 1, (
        f"AC-2: ein nicht erreichbares Postfach muss als failed zaehlen: {body!r}"
    )
    assert body.get("status") == "partial", f"AC-2: status muss 'partial' sein: {body!r}"


def test_ac2_postfach_erreichbar_bleibt_ok_mit_failed_null(monkeypatch, user_ids):
    """AC-2 (Gegenprobe): erreichbares Postfach, eine regulaere Befehlsmail ->
    ``status == "ok"``, ``failed == 0``, ``processed == 1``."""
    from api.routers.scheduler import trigger_inbound

    postfach = _Postfach()
    draht = _inbound_umgebung(monkeypatch, postfach)
    nutzer = lege_lage_an(user_ids, "L2")
    postfach.neue_mail(_befehlsmail(nutzer))

    body = trigger_inbound()

    assert len(draht.an(nutzer.mail_to)) == 1, f"Messaufbau: keine Antwort zugestellt: {body!r}"
    assert body.get("status") == "ok", body
    assert body.get("processed") == 1, body
    assert body.get("failed", _FEHLT) == 0, f"AC-2: failed muss in der Antwort stehen (0): {body!r}"


def test_ac2_ohne_zugangsdaten_bleibt_skipped(monkeypatch):
    """AC-2: fehlende Zugangsdaten bleiben ``skipped`` (kein Fehler, kein
    Verbindungsversuch)."""
    from api.routers.scheduler import trigger_inbound

    postfach = _Postfach()
    _inbound_umgebung(monkeypatch, postfach)
    for feld in ("GZ_IMAP_USER", "GZ_IMAP_PASS", "GZ_SMTP_USER", "GZ_SMTP_PASS"):
        monkeypatch.setenv(feld, "")

    body = trigger_inbound()

    assert body.get("status") == "skipped", body
    assert postfach.verbindungen == 0, body
    assert not body.get("failed"), f"AC-2: skipped ist kein Fehler: {body!r}"


def test_ac2_laufende_sperre_bleibt_busy(monkeypatch):
    """AC-2: haelt ein anderer Lauf die Sperre, antwortet der Lauf ``busy``
    (kein Fehler, kein Verbindungsversuch)."""
    from api.routers.scheduler import trigger_inbound

    postfach = _Postfach()
    _inbound_umgebung(monkeypatch, postfach)

    with _fremde_poll_sperre():
        body = trigger_inbound()

    assert body.get("status") == "busy", body
    assert postfach.verbindungen == 0, body
    assert not body.get("failed"), f"AC-2: busy ist kein Fehler: {body!r}"


@pytest.mark.parametrize("fehler", [
    imaplib.IMAP4.error("AUTHENTICATIONFAILED tdd-1405-s4b"),
    OSError("Connection refused (tdd-1405-s4b)"),
], ids=["imap_login", "netz"])
def test_ac2_leser_zaehlt_imap_und_netzfehler(monkeypatch, fehler):
    """AC-2/AC-21(c): der Leser selbst zaehlt den IMAP-/Netzwerkfehler als
    Fehler des Laufs (``last_failed_count == 1``), ``processed`` bleibt 0."""
    postfach = _Postfach(fehler=fehler)
    _inbound_umgebung(monkeypatch, postfach)

    processed, failed = _poll()

    assert processed == 0
    assert failed == 1, f"AC-2: IMAP-/Netzfehler muss als Fehler zaehlen, last_failed_count={failed!r}"


def test_ac3_fehler_im_inneren_ablauf_zaehlt_obwohl_gelesen(monkeypatch, user_ids):
    """AC-3: GIVEN zwei Befehlsmails; bei der ersten wirft der Antwortversand
    INNERHALB des von ``_process_single_inner`` selbst abgefangenen Blocks /
    WHEN der Lauf endet / THEN ``last_failed_count == 1``, ``processed == 1``
    (nur die regulaere), und BEIDE Mails sind als gelesen markiert.

    Fehlerquelle: seit S4a faengt ``process()`` jeden Programmfehler zentral,
    und ``send_command_reply_email`` faengt Transportfehler selbst -- der
    innere Handler ist aus echter Eingabe nur ueber einen werfenden
    Antwortversand erreichbar. Er wird ueber eine ECHTE Unterklasse des
    Versanddienstes eingespeist (Modul-Attribut, das der Leser beim Bauen
    liest); fuer die zweite Mail laeuft der echte Versand.

    RED heute: ``last_failed_count`` existiert nicht."""
    import services.inbound_email_reader as reader_mod

    postfach = _Postfach()
    draht = _inbound_umgebung(monkeypatch, postfach)
    kaputt = lege_lage_an(user_ids, "L2")
    regulaer = lege_lage_an(user_ids, "L2")

    class _WerfenderVersand(reader_mod.NotificationService):
        def send_command_reply_email(self, result, settings, lang="de"):
            if (settings.mail_to or "").lower() == kaputt.mail_to.lower():
                raise RuntimeError("Antwortversand gestoert (tdd-1405-s4b AC-3)")
            return super().send_command_reply_email(result, settings)

    monkeypatch.setattr(reader_mod, "NotificationService", _WerfenderVersand)
    postfach.neue_mail(_befehlsmail(kaputt))
    postfach.neue_mail(_befehlsmail(regulaer))

    processed, failed = _poll()

    assert len(draht.an(regulaer.mail_to)) == 1, "Messaufbau: die regulaere Antwort fehlt"
    assert postfach.gelesen == set(postfach.mails), "beide Mails muessen als gelesen markiert sein"
    assert processed == 1, f"AC-3: processed darf nur die regulaere Mail zaehlen: {processed!r}"
    assert failed == 1, f"AC-3: die gescheiterte Mail muss als Fehler zaehlen: {failed!r}"


@pytest.mark.parametrize("fall,erwartet_failed,erwartet_versuche", [
    ("antwort_scheitert", 1, 1),
    ("antwort_zugestellt", 0, 1),
    ("kein_versand_eingerichtet", 0, 0),
])
def test_ac4_trip_nicht_gefunden_zaehlt_nur_bei_gescheiterter_antwort(
        monkeypatch, user_ids, fall, erwartet_failed, erwartet_versuche):
    """AC-4: GIVEN eine Befehlsmail fuer einen unbekannten Trip / WHEN der Lauf
    endet / THEN zaehlt eine nicht zugestellte "Trip nicht gefunden"-Antwort
    als Fehler; zugestellt oder gar kein Versand eingerichtet
    (``can_send_email()`` falsch, kein Versuch) zaehlt NICHT.

    Echter ``send_command_reply_email`` am SMTP-Draht (kein Fake der Funktion
    -- sonst bliebe AC-21(d) "liefert wieder None" unbeobachtbar)."""
    postfach = _Postfach()
    draht = _inbound_umgebung(monkeypatch, postfach)
    nutzer = lege_lage_an(user_ids, "L2")
    if fall == "antwort_scheitert":
        draht.abgelehnt.add(nutzer.mail_to.lower())
    settings = basis_settings(smtp_host="") if fall == "kein_versand_eingerichtet" else None
    postfach.neue_mail(_befehlsmail(nutzer, ziel="Gibt es nicht 1405"))

    processed, failed = _poll(settings)

    assert len(draht.versuche) == erwartet_versuche, (
        f"Messaufbau ({fall}): {len(draht.versuche)} Einlieferungsversuche"
    )
    assert postfach.gelesen == set(postfach.mails)
    assert failed == erwartet_failed, (
        f"AC-4 ({fall}): last_failed_count={failed!r}, erwartet {erwartet_failed}"
    )


def test_ac5_send_command_reply_email_meldet_zustellung(monkeypatch, user_ids):
    """AC-5: ``send_command_reply_email`` liefert ``True`` bei Zustellung und
    ``False``, wenn der echte ``EmailOutput`` am SMTP-Draht scheitert; Betreff
    und Text der Antwort bleiben unveraendert.

    RED heute: Rueckgabe ``None`` in beiden Faellen."""
    from services.notification_service import NotificationService
    from services.trip_command_processor import CommandResult

    postfach = _Postfach()
    draht = _inbound_umgebung(monkeypatch, postfach)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings().with_user_profile(nutzer.user_id)
    antwort = CommandResult(
        success=True, command="status", confirmation_subject="[Solo-Trip] Status 1405",
        confirmation_body="Status-Text 1405", trip_name="Solo-Trip",
    )
    dienst = NotificationService(settings=settings, user_id=nutzer.user_id)

    ok = dienst.send_command_reply_email(antwort, settings)
    draht.abgelehnt.add(nutzer.mail_to.lower())
    gescheitert = dienst.send_command_reply_email(antwort, settings)

    assert len(draht.versuche) == 2, draht.versuche
    roh = draht.zugestellt[0]["roh"]
    assert "Status-Text 1405" in roh and "Status 1405" in roh, "AC-5: Antworttext/Betreff veraendert"
    assert ok is True, f"AC-5: zugestellte Antwort muss True liefern, kam {ok!r}"
    assert gescheitert is False, f"AC-5: abgelehnte Antwort muss False liefern, kam {gescheitert!r}"


def test_ac5_abgelehnte_befehlsantwort_zaehlt_als_fehler_des_laufs(monkeypatch, user_ids):
    """AC-5/AC-21(d): GIVEN eine regulaere Befehlsmail, deren Antwort der
    SMTP-Draht ablehnt / WHEN der Lauf endet / THEN ``last_failed_count == 1``
    -- der Aufrufer wertet das Bool aus. Zugestellt (Gegenprobe) -> 0."""
    postfach = _Postfach()
    draht = _inbound_umgebung(monkeypatch, postfach)
    nutzer = lege_lage_an(user_ids, "L2")
    draht.abgelehnt.add(nutzer.mail_to.lower())
    postfach.neue_mail(_befehlsmail(nutzer))

    _, failed = _poll()
    draht.abgelehnt.clear()
    postfach.neue_mail(_befehlsmail(nutzer))
    _, failed_danach = _poll()

    assert len(draht.versuche) == 2, f"Messaufbau: {len(draht.versuche)} Versuche"
    assert failed == 1, f"AC-5: nicht zugestellte Antwort muss als Fehler zaehlen: {failed!r}"
    assert failed_danach == 0, (
        f"AC-5/AC-21(e2): Folgelauf mit zugestellter Antwort muss 0 melden: {failed_danach!r}"
    )


def test_ac7_fehlerstatus_loest_keinen_zweiten_versand_aus(monkeypatch, user_ids):
    """AC-7 (Python-Teil, Regressionswaechter -- in RED erwartet gruen): GIVEN
    ein Lauf, dessen Antwort scheiterte (Mail ist trotzdem gelesen) / WHEN der
    naechste Lauf kommt / THEN wird die Mail nicht erneut verarbeitet und
    keine Antwort erneut eingeliefert."""
    postfach = _Postfach()
    draht = _inbound_umgebung(monkeypatch, postfach)
    nutzer = lege_lage_an(user_ids, "L2")
    draht.abgelehnt.add(nutzer.mail_to.lower())
    postfach.neue_mail(_befehlsmail(nutzer))

    _poll()
    versuche_nach_lauf1 = len(draht.versuche)
    draht.abgelehnt.clear()
    processed2, _ = _poll()

    assert versuche_nach_lauf1 == 1, draht.versuche
    assert len(draht.versuche) == 1, "AC-7: der Fehlerstatus darf keinen Nachversand ausloesen"
    assert processed2 == 0


def test_ac8_fehler_wird_nur_nutzer_a_angerechnet(monkeypatch, user_ids):
    """AC-8: GIVEN EIN Posteingang-Lauf mit je einer Mail zweier Nutzer (zwei
    Absender -> zwei Nutzer, je eigenes ``data/users/<id>/``); die Antwort an
    A wird abgelehnt, die an B zugestellt / WHEN der Lauf endet / THEN zaehlt
    genau EIN Fehler (der von A), B bekam seine Antwort, A keine.

    Lesart (Codelesen): der Befehls-Posteingang ist EIN globaler Job ueber
    alle Nutzer, ``last_failed_count`` ist eine Laufzahl, keine
    Nutzer-Zuordnung. "Nur A angerechnet" heisst hier: der Fehler von A
    verdoppelt sich nicht und B wird nicht als gescheitert gezaehlt."""
    postfach = _Postfach()
    draht = _inbound_umgebung(monkeypatch, postfach)
    a = lege_lage_an(user_ids, "L2")
    b = lege_lage_an(user_ids, "L2")
    assert a.user_id != b.user_id and "default" not in (a.user_id, b.user_id)
    draht.abgelehnt.add(a.mail_to.lower())
    postfach.neue_mail(_befehlsmail(a))
    postfach.neue_mail(_befehlsmail(b))

    _, failed = _poll()

    assert len(draht.an(b.mail_to)) == 1, "AC-8: B muss seine Antwort bekommen"
    assert draht.an(a.mail_to) == [], "AC-8: die Antwort an A wurde abgelehnt"
    assert failed == 1, f"AC-8: genau der Fehler von A zaehlt, last_failed_count={failed!r}"


# ═══════════════ A./G. Alarmlaeufe: Router-Antwort (AC-1, AC-11, AC-25, AC-27) ══════════════
#
# Bausteine aus ``test_alarm_totalausfall_wird_wiederholt.py`` (#1405 S1):
# Lage zweier Orte, steuerbare Draehte, gestellte Uhr ``_T0``. Nur die Lage
# wird von dort uebernommen -- gelaufen wird hier ueber den ROUTER.


@pytest.fixture
def rig(monkeypatch):
    from tests.helpers.kanal_fake_transporte import KanalRig

    r = KanalRig(monkeypatch)
    yield r
    r.stoppen()


def _alarm_uid(tag: str) -> str:
    return f"tdd-1405s4b-{tag}-{uuid.uuid4().hex[:6]}"


def _preset_beschaedigen(uid: str, preset_id: str) -> None:
    """Echte, beschaedigte Bestandsdatei (AC-1): ``display_config`` ist eine
    Liste statt eines Objekts. Die Pruefung DIESES Ortsvergleichs wirft beim
    Aufbau der Auswertungs-Konfiguration -- eine Ausnahme auf Preset-Ebene
    (``_check_all_counted``), nicht der je Ort abgefangene Wetterabruf.
    Read-Modify-Write, alle anderen Felder bleiben."""
    from tests.helpers.alert_log_fixtures import compare_data_root

    pfad = compare_data_root() / uid / "briefings" / f"{preset_id}.json"
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["display_config"] = ["kaputt-tdd-1405-s4b"]
    pfad.write_text(json.dumps(daten), encoding="utf-8")


def _vergleich_verdrahten(monkeypatch, settings_je_nutzer: dict, quelle) -> None:
    """Die Router bauen ``CompareAlertService(user_id=...)`` selbst. Ersetzt
    wird das Modul-Attribut durch eine ECHTE Unterklasse, die nur
    ``settings=`` (Draehte der Rig) und die Wetterquelle setzt; der amtliche
    Teil bekommt dieselben Settings (keine ``.env``-Zugangsdaten)."""
    import services.compare_alert as ca
    import services.compare_official_alert as coa

    # Mehrfach-Verdrahtung im selben Test: immer auf die PRODUKT-Klasse setzen.
    alarm_basis = getattr(ca.CompareAlertService, "_tdd_produkt", ca.CompareAlertService)
    amtlich_basis = getattr(
        coa.CompareOfficialAlertService, "_tdd_produkt", coa.CompareOfficialAlertService,
    )
    # Bereits verdrahtete Nutzer desselben Tests bleiben lauffaehig.
    settings_je_nutzer = {
        **getattr(ca.CompareAlertService, "_tdd_settings", {}), **settings_je_nutzer,
    }

    class _Alarm(alarm_basis):
        _tdd_produkt = alarm_basis
        _tdd_settings = settings_je_nutzer

        def __init__(self, settings=None, *, user_id, **kw):
            super().__init__(settings_je_nutzer[user_id], user_id=user_id, weather_source=quelle)

    class _Amtlich(amtlich_basis):
        _tdd_produkt = amtlich_basis

        def __init__(self, settings=None, *, user_id, **kw):
            super().__init__(settings_je_nutzer[user_id], user_id=user_id)

    monkeypatch.setattr(ca, "CompareAlertService", _Alarm)
    monkeypatch.setattr(coa, "CompareOfficialAlertService", _Amtlich)


def _compare_router_lauf(uid: str, at: datetime) -> dict:
    """``POST /api/scheduler/compare-alert-checks`` unter gestellter Uhr, ohne
    amtliche Warnung (leere Warnquelle -- kein Netz)."""
    from freezegun import freeze_time

    from api.routers.scheduler import trigger_compare_alert_checks
    from tests.helpers.briefing_imminent_fixtures import nur_diese_warnquelle
    from tests.tdd.test_alarm_totalausfall_wird_wiederholt import (
        _AlleOrteWarnquelle, _caches_leeren,
    )

    _caches_leeren()
    with freeze_time(at), nur_diese_warnquelle(_AlleOrteWarnquelle([])):
        return trigger_compare_alert_checks(user_id=uid)


def _vergleich_lage(rig, uid: str, kanaele: tuple[str, ...]):
    from tests.tdd.test_alarm_totalausfall_wird_wiederholt import _VergleichAenderung

    return _VergleichAenderung(rig, uid, kanaele)


def _beide_orte_boeen():
    """Ereignis "B" der S1-Lage: beide Orte melden Boeen -> Telegram faechert
    in ZWEI Sprechblasen auf (je Ort eine), der Hinweis waere die dritte."""
    from tests.tdd.test_alarm_totalausfall_wird_wiederholt import _OrtsQuelle

    return _OrtsQuelle({"loc-a": 60.0, "loc-b": 60.0})


def test_ac1_ortsvergleich_alarmlauf_mit_fehler_meldet_partial(rig, monkeypatch):
    """AC-1: GIVEN der Ortsvergleich-Alarmlauf eines Nutzers, bei dem die
    Pruefung eines Ortsvergleichs wirft (beschaedigte Bestandsdatei) / WHEN
    der Lauf endet / THEN ``failed >= 1`` UND ``status == "partial"``.

    RED heute: ``failed`` wird gezaehlt, ``status`` steht fest auf "ok"."""
    from tests.tdd.test_alarm_totalausfall_wird_wiederholt import _T0

    uid = _alarm_uid("ac1")
    lage = _vergleich_lage(rig, uid, ("email",))
    _preset_beschaedigen(uid, lage.entity_id)
    _vergleich_verdrahten(monkeypatch, {uid: lage.settings}, _beide_orte_boeen())

    body = _compare_router_lauf(uid, _T0)

    assert body.get("failed", 0) >= 1, f"Messaufbau: der Fehler wurde nicht gezaehlt: {body!r}"
    assert body.get("status") == "partial", f"AC-1: status muss 'partial' sein: {body!r}"


def test_ac1_ortsvergleich_alarmlauf_ohne_fehler_bleibt_ok(rig, monkeypatch):
    """AC-1 (Gegenprobe): laeuft alles durch und geht ein Alarm hinaus, bleibt
    ``status == "ok"`` und ``failed == 0``."""
    from tests.tdd.test_alarm_totalausfall_wird_wiederholt import _T0

    uid = _alarm_uid("ac1-ok")
    lage = _vergleich_lage(rig, uid, ("email",))
    _vergleich_verdrahten(monkeypatch, {uid: lage.settings}, _beide_orte_boeen())

    body = _compare_router_lauf(uid, _T0)

    assert rig.anzahl_angenommen("email") == 1, f"Messaufbau: kein Alarm: {body!r} / {rig!r}"
    assert body.get("status") == "ok", body
    assert body.get("failed") == 0, body


def _alarm_protokoll_kern(uid: str) -> list[dict]:
    """Die backoff-/ausgangsrelevanten Felder des Alarm-Protokolls (ohne
    Zeitstempel/Kennungen) -- Vergleichsgrundlage fuer AC-25."""
    from tests.helpers.alert_log_fixtures import read_log

    log = read_log(uid)
    felder = ("entity_type", "changes_count", "reason", "channels_sent", "channels_not_sent")
    return [
        {k: e.get(k) for k in felder if k in e}
        for e in log["entries"] + log["not_delivered"]
    ]


def _compare_hinweis_lauf(rig, monkeypatch, uid: str, *, hinweis_scheitert: bool) -> dict:
    from tests.tdd.test_alarm_totalausfall_wird_wiederholt import _T0

    lage = _vergleich_lage(rig, uid, ("telegram",))
    _vergleich_verdrahten(monkeypatch, {uid: lage.settings}, _beide_orte_boeen())
    rig.zaehler_leeren()
    # Blase 1 kommt an, Blase 2 scheitert; Anfrage 3 ist der Hinweis.
    rig.telegram_fehler_bei = {2, 3} if hinweis_scheitert else {2}
    return _compare_router_lauf(uid, _T0)


def test_ac25_ortsvergleich_alarm_hinweis_scheitert_meldet_notice_failed(rig, monkeypatch):
    """AC-25 (``/compare-alert-checks``): GIVEN ein Ortsvergleich-Alarm geht
    per Telegram in zwei Sprechblasen, Blase 1 kommt an, Blase 2 scheitert,
    und der Hinweis "Briefing unvollstaendig" scheitert ebenfalls / WHEN der
    Lauf endet / THEN ``notice_failed >= 1``, ``status == "partial"``,
    ``failed == 0``; Protokoll (``failed_channels``/Ausgang) und Backoff sind
    IDENTISCH zum Lauf mit zugestelltem Hinweis, und es entsteht kein
    zusaetzlicher Versand.

    RED heute: ``notice_failed`` fehlt, ``status == "ok"``."""
    from tests.helpers.kanal_fake_transporte import wiederholungs_eintraege

    ok_uid = _alarm_uid("ac25-hinweis-ok")
    kontrolle = _compare_hinweis_lauf(rig, monkeypatch, ok_uid, hinweis_scheitert=False)
    versuche_kontrolle = rig.anzahl_versuche("telegram")
    kaputt_uid = _alarm_uid("ac25-hinweis-kaputt")
    body = _compare_hinweis_lauf(rig, monkeypatch, kaputt_uid, hinweis_scheitert=True)

    assert versuche_kontrolle == 3 and rig.anzahl_versuche("telegram") == 3, (
        f"Messaufbau: zwei Blasen + Hinweis erwartet (Kontrolle {versuche_kontrolle}): {rig!r}"
    )
    assert rig.anzahl_angenommen("telegram") == 1, rig
    assert any(e.get("channels_sent") == ["telegram"] for e in _alarm_protokoll_kern(ok_uid)), (
        f"Messaufbau: kein Alarm-Protokolleintrag: {_alarm_protokoll_kern(ok_uid)!r}"
    )
    assert _alarm_protokoll_kern(kaputt_uid) == _alarm_protokoll_kern(ok_uid), (
        "AC-25/ADR-0086: Protokoll (failed_channels/Ausgang) darf vom Hinweis nicht abhaengen"
    )
    assert wiederholungs_eintraege(kaputt_uid) == wiederholungs_eintraege(ok_uid) == {}, (
        "AC-25: ein gescheiterter Hinweis darf keinen Backoff setzen"
    )
    assert kontrolle.get("notice_failed", _FEHLT) == 0, f"Kontrolle: {kontrolle!r}"
    assert body.get("failed") == 0, f"AC-25: Hinweis-Fehlschlag ist kein failed: {body!r}"
    assert body.get("notice_failed", _FEHLT) != _FEHLT and body["notice_failed"] >= 1, (
        f"AC-25: notice_failed muss den gescheiterten Hinweis zaehlen: {body!r}"
    )
    assert body.get("status") == "partial", f"AC-25: status muss 'partial' sein: {body!r}"


def test_ac27_ortsvergleich_hinweiszaehler_je_nutzer_und_lauf(rig, monkeypatch):
    """AC-27 (Alarm-Router): GIVEN Nutzer A (Hinweis scheitert) und danach
    Nutzer B (Hinweis zugestellt) im selben Prozess / WHEN beide Laeufe enden
    / THEN A ``notice_failed >= 1``, B ``notice_failed == 0``; ein zweiter Lauf
    von A ohne Hinweis-Fehlschlag meldet ``0`` (kein Uebertrag). Kein
    ``"default"``."""
    from tests.tdd.test_alarm_totalausfall_wird_wiederholt import _T0

    a, b = _alarm_uid("ac27-a"), _alarm_uid("ac27-b")
    body_a = _compare_hinweis_lauf(rig, monkeypatch, a, hinweis_scheitert=True)
    body_b = _compare_hinweis_lauf(rig, monkeypatch, b, hinweis_scheitert=False)
    rig.telegram_fehler_bei = None
    body_a2 = _compare_router_lauf(a, _T0 + timedelta(minutes=61))

    assert body_a.get("notice_failed", _FEHLT) != _FEHLT and body_a["notice_failed"] >= 1, body_a
    assert body_b.get("notice_failed", _FEHLT) == 0, f"AC-27: Fehler von A in B gebucht: {body_b!r}"
    assert body_a2.get("notice_failed", _FEHLT) == 0, f"AC-27: Uebertrag in Folgelauf: {body_a2!r}"


# AC-25 gilt nach PO-Spec-Korrektur nur fuer ``/compare-alert-checks``: nur der
# Ortsvergleich-Aenderungsalarm faechert Telegram in mehrere Sprechblasen auf
# und kann einen "unvollstaendig"-Hinweis senden. Trip-Abweichung, Trip-Radar
# und Ortsvergleich-Radar senden genau EINE Telegram-Nachricht -- dort gibt es
# kein ``notice_failed``.


@pytest.mark.parametrize("hinweis_scheitert,erwartet", [(True, ["telegram_incomplete_hint"]), (False, [])])
def test_ac11_notification_result_traegt_hinweis_fehlschlag_getrennt(rig, hinweis_scheitert, erwartet):
    """AC-11/AC-21(f): ``NotificationResult.notice_failures`` haelt den
    gescheiterten Hinweis fest -- GETRENNT von ``failed_channels``
    (ADR-0086: Backoff/Throttle bleiben unberuehrt). Der Alarm ist zugestellt
    (``delivery_outcome == "delivered"``).

    RED heute: das Feld existiert nicht."""
    from tests.tdd.test_alarm_totalausfall_wird_wiederholt import _dienst, _versende

    uid = _alarm_uid("ac11")
    rig.telegram_fehler_bei = {2, 3} if hinweis_scheitert else {2}
    result = _versende("_dispatch_alert_message", _dienst(rig, uid), {"telegram"}, orte=2)

    assert rig.anzahl_versuche("telegram") == 3, f"Messaufbau: {rig!r}"
    assert result.failed_channels == [], f"AC-11: Hinweis darf nicht in failed_channels: {result!r}"
    assert result.delivery_outcome == "delivered", result
    assert getattr(result, "notice_failures", _FEHLT) == erwartet, (
        f"AC-11: notice_failures={getattr(result, 'notice_failures', _FEHLT)!r}, erwartet {erwartet!r}"
    )


# ════════ C. Briefing-Lauf: Hinweise (AC-9/AC-10) und Nachlieferung (AC-12..AC-15, AC-27) ════════
#
# Lage und Transport-Raender aus ``test_briefing_anchor_survives_dispatch_failure.py``
# (#1629/#1662): Trip mit Etappe HEUTE, Briefing-Zeiten ausserhalb des
# Vorlaufs (der regulaere Slot ist JETZT nicht faellig), Nachliefer-Vermerk
# ``dispatch_error`` als Ausloeser -- so laeuft der ECHTE stuendliche Pfad
# (Router -> ``send_due_reports`` -> ``run_briefing_dispatch`` -> ``pre_pass``
# -> ``_process_pending_markers`` -> ``_send_trip_report_outcome``) zu jeder
# Wanduhrzeit, ohne die 2-s-Pause zwischen faelligen Slots.


class _Versand:
    """Transportrand Briefing: E-Mail (``EmailOutput.send``), Telegram und SMS
    (echte Unterklassen der Kanaele, Haus-Muster #1662). ``*_scheitert``
    entscheidet je Aufruf; gezaehlt wird jeder Versuch."""

    def __init__(self, monkeypatch) -> None:
        import services.notification_service as ns
        from output.channels.email import EmailOutput

        self.mails: list[dict] = []
        self.mail_versuche: list[str] = []
        self.telegram_versuche: list[str] = []
        self.sms: list[str] = []
        self.mail_scheitert = lambda subject: False
        self.telegram_scheitert = False
        versand = self

        def _mail(self_out, *, subject, body, **kw):
            versand.mail_versuche.append(subject)
            if versand.mail_scheitert(subject):
                raise RuntimeError("SMTP abgelehnt (tdd-1405-s4b)")
            versand.mails.append({"subject": subject, **kw})

        class _Telegram(ns.TelegramOutput):
            def send(self, subject, body, reply_markup=None, *, parse_mode=None,
                     suppress_subject_line=False):
                versand.telegram_versuche.append(body)
                if versand.telegram_scheitert:
                    raise RuntimeError("Telegram gestoert (tdd-1405-s4b)")
                return 4711

        class _Sms(ns.SMSOutput):
            def send(self, subject: str, body: str) -> None:
                versand.sms.append(body)

        monkeypatch.setattr(EmailOutput, "send", _mail)
        monkeypatch.setattr(ns, "TelegramOutput", _Telegram)
        monkeypatch.setattr(ns, "SMSOutput", _Sms)


def _briefing_settings():
    from app.config import Settings
    from tests.tdd.test_briefing_anchor_survives_dispatch_failure import (
        _DUMMY_EMAIL_FIELDS, _SMS_TELEGRAM_FIELDS,
    )

    settings = Settings(_env_file=None, **{**_DUMMY_EMAIL_FIELDS, **_SMS_TELEGRAM_FIELDS})
    assert settings.can_send_email() and settings.can_send_telegram()
    return settings


def _wetter(segment, *, fehlt: bool):
    from app.models import SegmentWeatherData, SegmentWeatherSummary
    from tests.tdd.test_briefing_anchor_survives_dispatch_failure import _data

    if not fehlt:
        return _data(segment.segment_id, segment=segment, gust_max_kmh=25.0)
    return SegmentWeatherData(
        segment=segment, timeseries=None, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
        has_error=True, error_message="Provider-Ausfall (tdd-1405-s4b)",
    )


def _scheduler_verdrahten(monkeypatch, draht_settings, wetter_je_nutzer: dict) -> None:
    """Der Router baut ``TripReportSchedulerService(user_id=...)``, die
    Strategie ``TripReportSchedulerService(settings=..., user_id=...)`` --
    beide ueber das Modul-Attribut. Ersetzt wird es durch eine ECHTE
    Unterklasse, die nur ``settings=`` und die Wetterquelle setzt
    (``wetter_je_nutzer[uid]``: ``"ok"``, ``"alle_fehlen"``, ``"teil_fehlt"``)."""
    import services.trip_report_scheduler as trs

    basis = getattr(trs.TripReportSchedulerService, "_tdd_produkt", trs.TripReportSchedulerService)
    wetter_je_nutzer = {**getattr(trs.TripReportSchedulerService, "_tdd_wetter", {}),
                        **wetter_je_nutzer}

    class _Verdrahtet(basis):
        _tdd_produkt = basis
        _tdd_wetter = wetter_je_nutzer

        def __init__(self, settings=None, *, user_id):
            super().__init__(draht_settings, user_id=user_id)

        def _fetch_weather(self, segments, provider=None):
            modus = self._tdd_wetter[self._user_id]
            return [
                _wetter(s, fehlt=(modus == "alle_fehlen" or (modus == "teil_fehlt" and i > 0)))
                for i, s in enumerate(segments)
            ]

    monkeypatch.setattr(trs, "TripReportSchedulerService", _Verdrahtet)


def _briefing_lage(tag: str, *, send_email=True, send_sms=False, send_telegram=False,
                   wegpunkte: int = 2):
    """Frischer Nutzer + gespeicherter Trip (Etappe heute) + Profil-Kanaele."""
    from app.loader import save_trip
    from app.trip import Waypoint
    from tests.helpers.arrival_window_fixtures import active_window_offsets
    from tests.helpers.sms_empfaenger import mit_profil_kanaele
    from tests.tdd.test_briefing_anchor_survives_dispatch_failure import LAT, LON, _trip

    uid = _alarm_uid(tag)
    trip = _trip(f"trip-s4b-{tag}-{uuid.uuid4().hex[:6]}", send_email=send_email,
                 send_sms=send_sms, send_telegram=send_telegram)
    if wegpunkte == 3:
        from dataclasses import replace

        ankunft = active_window_offsets(LAT, LON, -60, 30, 120)
        trip.stages[0] = replace(trip.stages[0], waypoints=[
            Waypoint(id=f"W{i}", name=f"P{i}", lat=LAT + 0.05 * i, lon=LON + 0.05 * i,
                     elevation_m=1000.0 + 200 * i, arrival_calculated=ankunft[i])
            for i in range(3)
        ])
    save_trip(trip, user_id=uid)
    uid = mit_profil_kanaele(uid, _briefing_settings())
    return uid, trip


def _vermerk(uid, trip, *, report_type="morning", reason="dispatch_error", segment_ids=None):
    from tests.tdd.test_briefing_anchor_survives_dispatch_failure import _seed_marker

    _seed_marker(uid, trip, reason=reason, report_type=report_type,
                 failed_segment_ids=segment_ids)


def _vermerke(uid) -> list:
    from tests.tdd.test_briefing_anchor_survives_dispatch_failure import _pending_markers

    return _pending_markers(uid)


def _trip_reports(uid: str) -> dict:
    from api.routers.scheduler import trigger_trip_reports

    return trigger_trip_reports(at=None, user_id=uid)


def _bilanz(uid: str) -> tuple:
    from services.dispatch_orchestrator import run_briefing_dispatch

    return run_briefing_dispatch("route", uid, datetime.now(timezone.utc), settings=_briefing_settings())


def test_ac9_telegram_hinweis_scheitert_briefing_zugestellt_meldet_partial(monkeypatch):
    """AC-9: GIVEN ein Briefing an E-Mail + Telegram; die Telegram-Teile UND
    danach der Hinweis "Briefing unvollstaendig" scheitern, die E-Mail ist
    zugestellt / WHEN der Briefing-Lauf (``/api/scheduler/trip-reports``)
    endet / THEN ``status == "partial"``, ``notice_failed >= 1``,
    ``failed == 0``, ``count == 1`` (das Briefing gilt als zugestellt).

    RED heute: der Hinweis-Fehlschlag steht nur im Log, ``status == "ok"``."""
    versand = _Versand(monkeypatch)
    uid, trip = _briefing_lage("ac9", send_email=True, send_telegram=True)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: "ok"})
    _vermerk(uid, trip)
    versand.telegram_scheitert = True

    body = _trip_reports(uid)

    assert len(versand.mails) == 1, f"Messaufbau: das Briefing per E-Mail fehlt: {body!r}"
    assert len(versand.telegram_versuche) >= 2, (
        f"Messaufbau: Teil-Nachricht(en) + Hinweis erwartet: {versand.telegram_versuche!r}"
    )
    assert body.get("count") == 1 and body.get("failed") == 0, (
        f"AC-9: zugestelltes Briefing ist sent, kein failed: {body!r}"
    )
    assert body.get("notice_failed", _FEHLT) != _FEHLT and body["notice_failed"] >= 1, (
        f"AC-9: notice_failed muss den gescheiterten Hinweis zaehlen: {body!r}"
    )
    assert body.get("status") == "partial", f"AC-9: status muss 'partial' sein: {body!r}"


def test_ac9_ohne_fehlschlag_bleibt_ok_mit_notice_failed_null(monkeypatch):
    """AC-9 (Gegenprobe): alle Telegram-Teile kommen an -> kein Hinweis,
    ``status == "ok"``, ``notice_failed == 0``."""
    versand = _Versand(monkeypatch)
    uid, trip = _briefing_lage("ac9-ok", send_email=True, send_telegram=True)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: "ok"})
    _vermerk(uid, trip)

    body = _trip_reports(uid)

    assert len(versand.mails) == 1 and versand.telegram_versuche, f"Messaufbau: {body!r}"
    assert body.get("status") == "ok", body
    assert body.get("notice_failed", _FEHLT) == 0, f"AC-9: notice_failed fehlt/ist falsch: {body!r}"


@pytest.mark.parametrize("fall,sms_only,mail_scheitert,erwartet_status,erwartet_notice", [
    ("sms_only_fehlermail_scheitert", True, True, "partial", 1),
    ("sms_only_fehlermail_zugestellt", True, False, "ok", 0),
    ("email_trip", False, True, "ok", 0),
])
def test_ac10_service_fehlermail_sms_only(monkeypatch, fall, sms_only, mail_scheitert,
                                         erwartet_status, erwartet_notice):
    """AC-10: GIVEN ein SMS-only-Trip mit gescheitertem Wetter-Abschnitt (die
    SMS selbst geht hinaus) / WHEN die Service-Fehlermail nicht zugestellt
    werden kann / THEN ``partial``, ``notice_failed >= 1``, ``failed == 0``.
    Fehlermail zugestellt bzw. E-Mail-Trip (keine Fehlermail) -> ``ok``,
    ``notice_failed == 0``.

    RED heute: ``notice_failed`` fehlt, der Fehlschlag steht nur im Log."""
    versand = _Versand(monkeypatch)
    uid, trip = _briefing_lage(f"ac10-{fall}", send_email=not sms_only, send_sms=sms_only,
                               wegpunkte=3)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: "teil_fehlt"})
    _vermerk(uid, trip)
    if mail_scheitert:
        versand.mail_scheitert = lambda subject: "Wetterdaten nicht verfuegbar" in subject

    body = _trip_reports(uid)

    if sms_only:
        assert len(versand.sms) == 1, f"Messaufbau: die SMS fehlt: {body!r} / {versand.mails!r}"
        assert any("Wetterdaten nicht verfuegbar" in s for s in versand.mail_versuche), (
            f"Messaufbau: keine Service-Fehlermail versucht: {versand.mail_versuche!r}"
        )
    else:
        assert len(versand.mails) == 1, f"Messaufbau: das E-Mail-Briefing fehlt: {body!r}"
    assert body.get("count") == 1 and body.get("failed") == 0, body
    assert body.get("notice_failed", _FEHLT) == erwartet_notice, (
        f"AC-10 ({fall}): notice_failed={body.get('notice_failed', _FEHLT)!r}: {body!r}"
    )
    assert body.get("status") == erwartet_status, f"AC-10 ({fall}): {body!r}"


#: AC-12: Ausgang der Nachlieferung -> (Lage, erwartete Bilanz (sent, failed)).
_NACHLIEFER_AUSGAENGE = {
    "sent": (dict(send_email=True), "ok", "morning", (1, 0)),
    "channels_unreachable": (dict(send_email=False, send_telegram=True), "ok", "morning", (0, 1)),
    "no_weather": (dict(send_email=True), "alle_fehlen", "morning", (0, 1)),
    "no_channels": (dict(send_email=False), "ok", "morning", (0, 0)),
    # Abend-Vermerk mit Etappe nur HEUTE: der Versand loest "morgen" auf -> no_stage.
    "no_stage": (dict(send_email=True), "ok", "evening", (0, 0)),
}


#: Protokollzeile, an der der neutrale Ausgang im Versand ENTSTEHT -- ohne
#: sie bewiese ``(0, 0)`` nur, dass gar kein Versand versucht wurde.
_AUSGANG_LOGZEILE = {
    "no_stage": "No segments for trip",
    "no_channels": "Trip report NOT sent (no channel configured)",
}


@pytest.mark.parametrize("ausgang", list(_NACHLIEFER_AUSGAENGE))
def test_ac12_nachlieferung_zaehlt_in_die_lauf_bilanz(monkeypatch, caplog, ausgang):
    """AC-12: GIVEN ein offener Nachliefer-Vermerk / WHEN der Briefing-Lauf
    (echter ``run_briefing_dispatch``, ``pre_pass``) endet / THEN steht eine
    gescheiterte Nachlieferung (``channels_unreachable``/``no_weather``) in
    ``failed``, eine gelungene in ``sent``; ``no_channels``/``no_stage``
    zaehlen weder noch.

    RED heute: ``channels_unreachable``/``no_weather`` -> ``(0, 0)``.
    Regressionswaechter (in RED gruen): ``sent``, ``no_channels``, ``no_stage``
    (bewachen AC-21(g): neutrale Ausgaenge nicht als failed zaehlen)."""
    lage, wetter, report_type, erwartet = _NACHLIEFER_AUSGAENGE[ausgang]
    versand = _Versand(monkeypatch)
    versand.telegram_scheitert = ausgang == "channels_unreachable"
    uid, trip = _briefing_lage(f"ac12-{ausgang}", **lage)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: wetter})
    _vermerk(uid, trip, report_type=report_type)

    with caplog.at_level("INFO"):
        bilanz = _bilanz(uid)

    if ausgang in _AUSGANG_LOGZEILE:
        zeilen = [r.getMessage() for r in caplog.records]
        assert any(_AUSGANG_LOGZEILE[ausgang] in z and (trip.id in z or trip.name in z)
                   for z in zeilen), (
            f"Messaufbau: der Ausgang {ausgang!r} ist im Versand nicht entstanden"
        )
    if ausgang == "sent":
        assert len(versand.mails) == 1, "Messaufbau: die Nachlieferung fehlt"
    if ausgang in ("no_channels", "no_stage"):
        assert versand.mails == [] and versand.telegram_versuche == [], "Messaufbau: Versand trotz neutralem Ausgang"
    if ausgang == "channels_unreachable":
        assert versand.telegram_versuche and versand.mails == [], "Messaufbau: Telegram nicht betreten"
    assert not any(v.get("reason") == "dispatch_error" and v.get("report_type") == report_type
                   and ausgang != "channels_unreachable" for v in _vermerke(uid)), (
        "AC-15: der Versandfehler-Vermerk muss vor dem Versand entfernt sein"
    )
    assert bilanz == erwartet, f"AC-12 ({ausgang}): Bilanz {bilanz!r}, erwartet {erwartet!r}"


def test_ac13_weiter_fehlender_abschnitt_sendet_nicht_und_zaehlt_nicht(monkeypatch):
    """AC-13 (Regressionswaechter -- in RED erwartet gruen): GIVEN ein
    Wetterfehler-Vermerk, dessen zuvor fehlende Abschnitte weiterhin keine
    Daten liefern / WHEN der Lauf endet / THEN nichts gesendet, Bilanz
    ``(0, 0)``, ``attempts`` erhoeht (Laermschutz #1012)."""
    from services.trip_report_scheduler import TripReportSchedulerService
    from tests.tdd.test_briefing_anchor_survives_dispatch_failure import LAT, LON
    from tests.helpers.ortstag import ortstag

    versand = _Versand(monkeypatch)
    uid, trip = _briefing_lage("ac13")
    ids = [str(s.segment_id) for s in TripReportSchedulerService(
        settings=_briefing_settings(), user_id=uid)._convert_trip_to_segments(trip, ortstag(LAT, LON))]
    assert ids, "Messaufbau: der Trip braucht heute Abschnitte"
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: "alle_fehlen"})
    _vermerk(uid, trip, reason=None, segment_ids=ids)

    bilanz = _bilanz(uid)

    assert versand.mails == [] and versand.telegram_versuche == []
    vermerke = _vermerke(uid)
    assert len(vermerke) == 1 and vermerke[0].get("attempts") == 1, vermerke
    assert bilanz == (0, 0), f"AC-13: kein Fehlalarm bei weiter gestoertem Wetterdienst: {bilanz!r}"


def test_ac14_nachlieferfehler_nur_in_der_bilanz_von_nutzer_a(monkeypatch):
    """AC-14: GIVEN Nutzer A (Nachlieferung scheitert: Telegram-only, Telegram
    gestoert) und Nutzer B (Nachlieferung gelingt per E-Mail), je eigenes
    ``data/users/<id>/`` / WHEN beide Laeufe nacheinander im selben Prozess
    enden / THEN Bilanz A ``(0, 1)``, Bilanz B ``(1, 0)``. Kein ``"default"``.

    RED heute: Bilanz A ``(0, 0)``."""
    versand = _Versand(monkeypatch)
    a, trip_a = _briefing_lage("ac14-a", send_email=False, send_telegram=True)
    b, trip_b = _briefing_lage("ac14-b", send_email=True)
    assert a != b and "default" not in (a, b)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {a: "ok", b: "ok"})
    _vermerk(a, trip_a)
    _vermerk(b, trip_b)

    versand.telegram_scheitert = True
    bilanz_a = _bilanz(a)
    versand.telegram_scheitert = False
    bilanz_b = _bilanz(b)

    assert len(versand.mails) == 1, "Messaufbau: B muss sein Briefing bekommen"
    assert bilanz_b == (1, 0), f"AC-14: Fehler von A in B gebucht: {bilanz_b!r}"
    assert bilanz_a == (0, 1), f"AC-14: gescheiterte Nachlieferung von A: {bilanz_a!r}"


def test_ac15_fehlschlag_loest_keinen_nachversand_aus(monkeypatch):
    """AC-15 (Regressionswaechter -- in RED erwartet gruen): GIVEN ein Lauf mit
    gescheitertem Hinweis (AC-9) / WHEN derselbe Lauf erneut kommt / THEN
    keine zweite E-Mail, kein zweiter Telegram-Versuch -- der Vermerk ist
    vor dem Versand entfernt, der Status loest nichts aus."""
    versand = _Versand(monkeypatch)
    uid, trip = _briefing_lage("ac15", send_email=True, send_telegram=True)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: "ok"})
    _vermerk(uid, trip)
    versand.telegram_scheitert = True

    _trip_reports(uid)
    mails, telegram = len(versand.mails), len(versand.telegram_versuche)
    zweiter = _trip_reports(uid)

    assert mails == 1, versand.mails
    assert len(versand.mails) == mails and len(versand.telegram_versuche) == telegram, (
        f"AC-15: zweiter Lauf hat erneut versendet: {zweiter!r}"
    )
    assert not any(v.get("reason") == "dispatch_error" for v in _vermerke(uid))


def test_ac27_briefing_hinweiszaehler_je_nutzer_und_lauf(monkeypatch):
    """AC-27 (Briefing-Router): GIVEN Nutzer A (Hinweis scheitert) und danach
    Nutzer B (alles zugestellt) / WHEN beide Laeufe enden / THEN A
    ``notice_failed >= 1``, B ``0``; ein zweiter Lauf von A nach behobenem
    Fehler, der WIRKLICH versendet (frischer Vermerk), meldet ``0``."""
    versand = _Versand(monkeypatch)
    a, trip_a = _briefing_lage("ac27-a", send_email=True, send_telegram=True)
    b, trip_b = _briefing_lage("ac27-b", send_email=True, send_telegram=True)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {a: "ok", b: "ok"})
    _vermerk(a, trip_a)
    _vermerk(b, trip_b)

    versand.telegram_scheitert = True
    body_a = _trip_reports(a)
    versand.telegram_scheitert = False
    body_b = _trip_reports(b)
    _vermerk(a, trip_a)
    body_a2 = _trip_reports(a)

    assert len(versand.mails) == 3, f"Messaufbau: drei zugestellte Briefings erwartet: {versand.mails!r}"
    assert body_a2.get("count") == 1, f"Messaufbau: der Folgelauf von A muss versenden: {body_a2!r}"
    assert body_a.get("notice_failed", _FEHLT) != _FEHLT and body_a["notice_failed"] >= 1, body_a
    assert body_b.get("notice_failed", _FEHLT) == 0, f"AC-27: Fehler von A in B gebucht: {body_b!r}"
    assert body_a2.get("notice_failed", _FEHLT) == 0, f"AC-27: Uebertrag in Folgelauf: {body_a2!r}"


# ════════════ Fix-Loop 1 (Adversary BROKEN): F001-F006, Reset-Gegenproben ════════════


class _Sink:
    """Aufrufende Instanz fuer ``run_briefing_dispatch(..., notice_sink=)``."""

    last_notice_failed = _FEHLT


def test_fl1_sms_only_ohne_mailversand_ist_kein_hinweis_fehlschlag(monkeypatch):
    """Fix-Loop 1 (F001, Spec B21 "nicht erforderlich", analog AC-4): GIVEN ein
    SMS-only-Trip mit Segmentausfall, dessen Settings KEINEN Mailversand
    einrichten (``can_send_email()`` falsch) / WHEN der Briefing-Lauf endet /
    THEN wird keine Service-Fehlermail versucht, ``notice_failed == 0`` und die
    Bilanz ist ``(1, 0)`` -- sonst stuende jeder SMS-only-Nutzer ohne SMTP
    dauerhaft auf ``partial``.

    Eingang: echter ``run_briefing_dispatch`` (der Router-Weg bricht ohne SMTP
    schon am ``smtp_guard`` ab); die Lauf-Settings bestehen den Guard, der
    Versanddienst des Nutzers hat keinen SMTP-Host."""
    versand = _Versand(monkeypatch)
    versand.mail_scheitert = lambda subject: True  # ein Versuch scheiterte
    uid, trip = _briefing_lage("fl1-ohne-smtp", send_email=False, send_sms=True, wegpunkte=3)
    ohne_smtp = _briefing_settings().model_copy(update={"smtp_host": ""})
    assert not ohne_smtp.can_send_email() and ohne_smtp.can_send_sms()
    _scheduler_verdrahten(monkeypatch, ohne_smtp, {uid: "teil_fehlt"})
    _vermerk(uid, trip)
    sink = _Sink()

    from services.dispatch_orchestrator import run_briefing_dispatch

    bilanz = run_briefing_dispatch(
        "route", uid, datetime.now(timezone.utc), settings=_briefing_settings(),
        notice_sink=sink,
    )

    assert len(versand.sms) == 1, f"Messaufbau: die SMS fehlt: {bilanz!r}"
    assert not any("Wetterdaten nicht verfuegbar" in s for s in versand.mail_versuche), (
        f"F001: ohne Mailversand darf keine Fehlermail versucht werden: {versand.mail_versuche!r}"
    )
    assert bilanz == (1, 0), bilanz
    assert sink.last_notice_failed == 0, (
        f"F001: kein Versuch = kein Hinweis-Fehlschlag, notice_failed={sink.last_notice_failed!r}"
    )


def test_fl1_f003_briefing_zaehler_reset_auf_derselben_strategie(monkeypatch):
    """F003 (AC-27, Reset ``_collect_due_trips``): GIVEN DIESELBE
    ``TripDispatchStrategy`` (damit derselbe Dienst) fuer zwei Laeufe, erst mit
    gescheitertem Hinweis, dann ohne / WHEN der zweite Lauf ``collect_due`` +
    ``pre_pass`` durchlaeuft (Reihenfolge wie ``run_briefing_dispatch``) /
    THEN ist ``notice_failed`` im zweiten Lauf 0 (kein Uebertrag)."""
    from services.dispatch_orchestrator import TripDispatchStrategy

    versand = _Versand(monkeypatch)
    uid, trip = _briefing_lage("fl1-f003-trip", send_email=True, send_telegram=True)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: "ok"})
    strategie = TripDispatchStrategy(_briefing_settings(), uid)

    def _lauf() -> int:
        jetzt = datetime.now(timezone.utc)
        strategie.pre_pass(jetzt, strategie.collect_due(jetzt))
        return strategie.notice_failed

    _vermerk(uid, trip)
    versand.telegram_scheitert = True
    erster = _lauf()
    versand.telegram_scheitert = False
    _vermerk(uid, trip)
    zweiter = _lauf()

    assert len(versand.mails) == 2, f"Messaufbau: zwei Nachlieferungen erwartet: {versand.mails!r}"
    assert erster >= 1, f"Messaufbau: der erste Lauf muss den Hinweis-Fehlschlag zaehlen: {erster!r}"
    assert zweiter == 0, f"F003: Hinweiszaehler traegt in den naechsten Lauf: {zweiter!r}"


def test_fl1_f003_briefing_last_notice_failed_reset_bei_guard_abbruch(monkeypatch):
    """F003 (Reset ``send_due_reports``): GIVEN DERSELBE Dienst, Lauf 1 mit
    gescheitertem Hinweis (``last_notice_failed >= 1``), danach ist der
    Mailversand des Dienstes nicht mehr eingerichtet / WHEN Lauf 2 am
    ``smtp_guard`` endet (kein Versand, keine Zuweisung durch den Lauf) / THEN
    meldet der Dienst ``last_notice_failed == 0`` -- kein Wert aus Lauf 1."""
    import services.trip_report_scheduler as trs

    versand = _Versand(monkeypatch)
    uid, trip = _briefing_lage("fl1-f003-guard", send_email=True, send_telegram=True)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: "ok"})
    dienst = trs.TripReportSchedulerService(user_id=uid)
    _vermerk(uid, trip)
    versand.telegram_scheitert = True

    dienst.send_due_reports(datetime.now(timezone.utc))
    erster = dienst.last_notice_failed
    # Konfigurationswechsel zwischen den Laeufen: SMTP nicht mehr eingerichtet.
    dienst._settings = dienst._settings.model_copy(update={"smtp_host": ""})
    bilanz = dienst.send_due_reports(datetime.now(timezone.utc))

    assert erster >= 1, f"Messaufbau: Lauf 1 muss den Hinweis-Fehlschlag melden: {erster!r}"
    assert bilanz == (0, 0), f"Messaufbau: Lauf 2 muss am smtp_guard enden: {bilanz!r}"
    assert dienst.last_notice_failed == 0, (
        f"F003: last_notice_failed traegt in den naechsten Lauf: {dienst.last_notice_failed!r}"
    )


def test_fl1_f003_mail_leser_reset_auf_derselben_instanz(monkeypatch):
    """F003 (Reset ``poll_and_process``): GIVEN DERSELBE ``InboundEmailReader``,
    Lauf 1 scheitert am Postfach (``last_failed_count == 1``) / WHEN Lauf 2 ohne
    Zugangsdaten frueh endet / THEN ``last_failed_count == 0``."""
    from services.inbound_email_reader import InboundEmailReader

    postfach = _Postfach(fehler=OSError("Network is unreachable (tdd-1405-s4b F003)"))
    _inbound_umgebung(monkeypatch, postfach)
    leser = InboundEmailReader()

    leser.poll_and_process(basis_settings())
    erster = leser.last_failed_count
    leser.poll_and_process(basis_settings(imap_user="", imap_pass="", smtp_user="", smtp_pass=""))

    assert postfach.verbindungen == 1, "Messaufbau: Lauf 2 darf keine Verbindung aufbauen"
    assert erster == 1, f"Messaufbau: Lauf 1 muss den Netzfehler zaehlen: {erster!r}"
    assert leser.last_failed_count == 0, (
        f"F003: last_failed_count traegt in den naechsten Lauf: {leser.last_failed_count!r}"
    )


def test_fl1_f003_vergleichs_hinweiszaehler_reset_auf_derselben_instanz(rig, monkeypatch):
    """F003 (Reset ``_check_all_counted``): GIVEN DERSELBE ``CompareAlertService``,
    Lauf 1 mit gescheitertem Hinweis / WHEN Lauf 2 (61 min spaeter) ohne
    Telegram-Stoerung laeuft / THEN ``last_notice_failed == 0``."""
    import services.compare_alert as ca
    from freezegun import freeze_time

    from tests.helpers.briefing_imminent_fixtures import nur_diese_warnquelle
    from tests.tdd.test_alarm_totalausfall_wird_wiederholt import (
        _AlleOrteWarnquelle, _T0, _caches_leeren,
    )

    uid = _alarm_uid("fl1-f003-vergleich")
    lage = _vergleich_lage(rig, uid, ("telegram",))
    _vergleich_verdrahten(monkeypatch, {uid: lage.settings}, _beide_orte_boeen())
    dienst = ca.CompareAlertService(user_id=uid)
    rig.zaehler_leeren()
    rig.telegram_fehler_bei = {2, 3}

    _caches_leeren()
    with freeze_time(_T0), nur_diese_warnquelle(_AlleOrteWarnquelle([])):
        dienst.check_all_compare_presets()
    erster = dienst.last_notice_failed
    rig.telegram_fehler_bei = None
    _caches_leeren()
    with freeze_time(_T0 + timedelta(minutes=61)), nur_diese_warnquelle(_AlleOrteWarnquelle([])):
        dienst.check_all_compare_presets()

    assert erster >= 1, f"Messaufbau: Lauf 1 muss den Hinweis-Fehlschlag zaehlen: {erster!r}"
    assert dienst.last_notice_failed == 0, (
        f"F003: last_notice_failed traegt in den naechsten Lauf: {dienst.last_notice_failed!r}"
    )


def test_fl1_f004_daten_nachlieferung_mit_gescheitertem_versand_zaehlt_failed(monkeypatch):
    """F004 (AC-12, zweite Sendestelle): GIVEN ein Wetterfehler-Vermerk (kein
    Versandfehler-Vermerk), dessen zuvor fehlende Abschnitte jetzt Daten
    liefern; der einzige Kanal (Telegram) scheitert / WHEN der Lauf endet /
    THEN Bilanz ``(0, 1)`` -- die gescheiterte Daten-Nachlieferung ist sichtbar."""
    versand = _Versand(monkeypatch)
    versand.telegram_scheitert = True
    uid, trip = _briefing_lage("fl1-f004", send_email=False, send_telegram=True)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: "ok"})
    _vermerk(uid, trip, reason=None, segment_ids=["seg-frueher-ohne-daten"])

    bilanz = _bilanz(uid)

    assert versand.telegram_versuche, "Messaufbau: die Daten-Nachlieferung wurde nicht versucht"
    assert not any(v.get("failed_segment_ids") == ["seg-frueher-ohne-daten"] for v in _vermerke(uid)), (
        "Messaufbau: der Wetterfehler-Vermerk muss vor dem Versand entfernt sein"
    )
    assert bilanz == (0, 1), f"F004: gescheiterte Daten-Nachlieferung: Bilanz {bilanz!r}"


def test_fl1_f005_briefing_nichts_zugestellt_ist_failed_nicht_notice(monkeypatch):
    """F005 (Briefing): GIVEN Telegram ist der einzige Kanal, ALLE Teile und der
    Hinweis scheitern / WHEN ``/api/scheduler/trip-reports`` endet / THEN
    ``failed == 1`` und ``notice_failed == 0`` -- ohne Zustellung ist der
    Hinweis kein eigener Fehlschlag (B21: gilt nur bei zugestelltem Briefing)."""
    versand = _Versand(monkeypatch)
    versand.telegram_scheitert = True
    uid, trip = _briefing_lage("fl1-f005-briefing", send_email=False, send_telegram=True)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: "ok"})
    _vermerk(uid, trip)

    body = _trip_reports(uid)

    assert len(versand.telegram_versuche) >= 2, (
        f"Messaufbau: Teile + Hinweis erwartet: {versand.telegram_versuche!r}"
    )
    assert body.get("count") == 0 and body.get("failed") == 1, body
    assert body.get("notice_failed") == 0, f"F005: nichts zugestellt -> kein notice_failed: {body!r}"
    assert body.get("status") == "partial", body


def test_fl1_f005_ortsvergleich_nichts_zugestellt_ist_kein_notice(rig, monkeypatch):
    """F005 (``/compare-alert-checks``): GIVEN Telegram ist der einzige Kanal,
    BEIDE Sprechblasen und der Hinweis scheitern / WHEN der Lauf endet / THEN
    ``notice_failed == 0`` (nichts zugestellt), ``count == 0``; der
    Transportfehler landet wie bisher im Protokoll/Backoff (ADR-0086).

    Hinweis zum Bericht: ``failed`` zaehlt hier Presets, deren Pruefung
    WARF -- ein Transportfehler ist kein solcher Fall und bleibt ``0``; das
    ist Bestandsverhalten (#2217), nicht Teil dieser Scheibe."""
    from tests.helpers.kanal_fake_transporte import wiederholungs_eintraege

    uid = _alarm_uid("fl1-f005-vergleich")
    lage = _vergleich_lage(rig, uid, ("telegram",))
    _vergleich_verdrahten(monkeypatch, {uid: lage.settings}, _beide_orte_boeen())
    rig.zaehler_leeren()
    rig.telegram_fehler_bei = {1, 2, 3}

    from tests.tdd.test_alarm_totalausfall_wird_wiederholt import _T0

    body = _compare_router_lauf(uid, _T0)

    assert rig.anzahl_versuche("telegram") == 3 and rig.anzahl_angenommen("telegram") == 0, rig
    assert wiederholungs_eintraege(uid), "Messaufbau: der Transportfehler muss Backoff setzen"
    assert body.get("count") == 0, body
    assert body.get("notice_failed") == 0, f"F005: nichts zugestellt -> kein notice_failed: {body!r}"


class _FetchBrichtPostfach(_Postfach):
    """IMAP-Gegenstelle, deren ``FETCH`` fuer EINE Nachricht scheitert
    (Server-Fehler mitten im Lauf) -- trifft den Fehler-Handler der
    Mail-Schleife, nicht den des Verbindungsaufbaus."""

    kaputt_uid = b"1"

    def __call__(self, host, port=None, *a, **kw):
        self.verbindungen += 1
        postfach = self

        class _Verb(_Verbindung):
            def fetch(self, uid, spec):
                if uid == postfach.kaputt_uid:
                    raise imaplib.IMAP4.abort("FETCH abgebrochen (tdd-1405-s4b F006)")
                return super().fetch(uid, spec)

        return _Verb(self)


def test_fl1_f006a_fehler_einer_mail_in_der_schleife_zaehlt(monkeypatch, user_ids):
    """F006a (Fehler-Handler der Mail-Schleife): GIVEN zwei Befehlsmails, das
    Abholen der ersten scheitert am Server / WHEN der Lauf endet / THEN
    ``last_failed_count == 1``, die zweite Mail ist regulaer verarbeitet
    (``processed == 1``, Antwort zugestellt)."""
    postfach = _FetchBrichtPostfach()
    draht = _inbound_umgebung(monkeypatch, postfach)
    a = lege_lage_an(user_ids, "L2")
    b = lege_lage_an(user_ids, "L2")
    postfach.neue_mail(_befehlsmail(a))
    postfach.neue_mail(_befehlsmail(b))

    processed, failed = _poll()

    assert len(draht.an(b.mail_to)) == 1, "Messaufbau: die zweite Mail muss beantwortet sein"
    assert processed == 1, processed
    assert failed == 1, f"F006a: Fehler beim Abholen einer Mail muss zaehlen: {failed!r}"


def test_fl1_f006b_nicht_zugestellte_antwort_bleibt_processed(monkeypatch, user_ids):
    """F006b: GIVEN eine regulaere Befehlsmail, deren Antwort der SMTP-Draht
    ablehnt / WHEN ``POST /api/scheduler/inbound-commands`` laeuft / THEN
    ``processed == 1`` (der Befehl IST verarbeitet -- der Push-Nachversuch
    haengt an ``processed``), ``failed == 1``, ``status == "partial"``."""
    from api.routers.scheduler import trigger_inbound

    postfach = _Postfach()
    draht = _inbound_umgebung(monkeypatch, postfach)
    nutzer = lege_lage_an(user_ids, "L2")
    draht.abgelehnt.add(nutzer.mail_to.lower())
    postfach.neue_mail(_befehlsmail(nutzer))

    body = trigger_inbound()

    assert len(draht.versuche) == 1, f"Messaufbau: {draht.versuche!r}"
    assert body.get("processed") == 1 and body.get("count") == 1, (
        f"F006b: der verarbeitete Befehl muss als processed zaehlen: {body!r}"
    )
    assert body.get("failed") == 1 and body.get("status") == "partial", body


# ═══════════ Fix-Loop 2 (Adversary BROKEN Runde 2): F001-F004 Gegenproben ═══════════


@pytest.mark.parametrize("ausgang", ["no_channels", "no_stage"])
def test_fl2_f001_daten_nachlieferung_neutraler_ausgang_zaehlt_nicht(monkeypatch, caplog, ausgang):
    """F001 (AC-12, ZWEITE Sendestelle in ``_process_pending_markers``): GIVEN
    ein Wetterfehler-Vermerk (kein Versandfehler-Vermerk), dessen zuvor
    fehlende Abschnitte jetzt Daten liefern; der Versand endet ``no_channels``
    (kein Kanal) bzw. ``no_stage`` (Abend-Vermerk, Etappe nur heute) / WHEN
    der Lauf endet / THEN Bilanz ``(0, 0)`` -- neutrale Ausgaenge zaehlen
    weder als sent noch als failed. Die Protokollzeile belegt, dass der
    Ausgang im VERSAND entstand (nicht im frueheren ``if not segments``)."""
    lage, _wetter_modus, report_type, erwartet = _NACHLIEFER_AUSGAENGE[ausgang]
    versand = _Versand(monkeypatch)
    uid, trip = _briefing_lage(f"fl2-f001-{ausgang}", **lage)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: "ok"})
    _vermerk(uid, trip, report_type=report_type, reason=None,
             segment_ids=["seg-frueher-ohne-daten"])

    with caplog.at_level("INFO"):
        bilanz = _bilanz(uid)

    zeilen = [r.getMessage() for r in caplog.records]
    assert any(_AUSGANG_LOGZEILE[ausgang] in z and (trip.id in z or trip.name in z)
               for z in zeilen), f"Messaufbau: der Ausgang {ausgang!r} ist im Versand nicht entstanden"
    assert versand.mails == [] and versand.telegram_versuche == [], "Messaufbau: Versand trotz neutralem Ausgang"
    assert not any(v.get("failed_segment_ids") == ["seg-frueher-ohne-daten"] for v in _vermerke(uid)), (
        "Messaufbau: der Wetterfehler-Vermerk muss vor dem Versand entfernt sein (kein attempts-Zweig)"
    )
    assert erwartet == (0, 0)
    assert bilanz == (0, 0), f"F001 ({ausgang}): neutraler Ausgang der Daten-Nachlieferung: {bilanz!r}"


def test_fl2_f002_erfolgreicher_befehl_ohne_mailversand_zaehlt_nicht(monkeypatch, user_ids):
    """F002 (Normalpfad der Befehlsverarbeitung, analog AC-4
    ``kein_versand_eingerichtet``): GIVEN eine regulaere, ERFOLGREICHE
    Befehlsmail, die Settings richten keinen Mailversand ein
    (``can_send_email()`` falsch) / WHEN der Lauf endet / THEN kein
    Antwortversuch, ``processed == 1``, ``last_failed_count == 0`` -- kein
    Versuch ist kein Fehler."""
    postfach = _Postfach()
    draht = _inbound_umgebung(monkeypatch, postfach)
    nutzer = lege_lage_an(user_ids, "L2")
    postfach.neue_mail(_befehlsmail(nutzer))

    processed, failed = _poll(basis_settings(smtp_host=""))

    assert draht.versuche == [], f"Messaufbau: ohne Mailversand kein Versuch: {draht.versuche!r}"
    assert postfach.gelesen == set(postfach.mails)
    assert processed == 1, f"Messaufbau: der Befehl muss im Normalpfad verarbeitet sein: {processed!r}"
    assert failed == 0, f"F002: kein Versuch = kein Fehler, last_failed_count={failed!r}"


def test_fl2_f002_unterdrueckte_antwort_zaehlt_nicht(monkeypatch, user_ids):
    """F002 (``suppress_email_reply``): GIVEN eine Befehlsmail ``heute``, deren
    Antwort das volle Briefing selbst IST (#1007, keine Doppel-Mail) / WHEN
    der Lauf endet / THEN genau EINE Einlieferung (das Briefing, keine
    Befehlsantwort), ``processed == 1``, ``last_failed_count == 0``."""
    postfach = _Postfach()
    draht = _inbound_umgebung(monkeypatch, postfach)
    nutzer = lege_lage_an(user_ids, "L2")
    postfach.neue_mail(_befehlsmail(nutzer, befehl="heute"))

    processed, failed = _poll()

    assert len(draht.zugestellt) == 1, (
        f"Messaufbau: genau das On-Demand-Briefing erwartet: {[v['an'] for v in draht.versuche]!r}"
    )
    assert not any("Briefing wird gesendet" in v["roh"] for v in draht.versuche), (
        "Messaufbau: die Befehlsantwort darf nicht verschickt werden (suppress_email_reply)"
    )
    assert processed == 1, processed
    assert failed == 0, f"F002: unterdrueckte Antwort ist kein Fehler, last_failed_count={failed!r}"


def test_fl2_f003_frischer_dienst_auf_dem_on_demand_pfad_zaehlt_hinweis(monkeypatch):
    """F003 (Konstruktor-Reset ``notice_failed``): GIVEN ein FRISCH gebauter
    Dienst ohne vorherigen Sammellauf (kein ``_collect_due_trips``-Reset) /
    WHEN er ein On-Demand-Briefing zustellt (E-Mail), dessen Telegram-Teile
    und Hinweis scheitern / THEN ``outcome == "sent"`` und
    ``notice_failed == 1`` -- der Zaehler ist ab Konstruktion definiert."""
    import services.trip_report_scheduler as trs

    versand = _Versand(monkeypatch)
    uid, trip = _briefing_lage("fl2-f003", send_email=True, send_telegram=True)
    _scheduler_verdrahten(monkeypatch, _briefing_settings(), {uid: "ok"})
    versand.telegram_scheitert = True
    dienst = trs.TripReportSchedulerService(user_id=uid)

    ergebnis = dienst.send_on_demand_report(trip, "morning")

    assert ergebnis.outcome == "sent", f"Messaufbau: das Briefing muss zugestellt sein: {ergebnis!r}"
    assert len(versand.mails) == 1 and len(versand.telegram_versuche) >= 2, (
        f"Messaufbau: E-Mail zugestellt, Telegram-Teile + Hinweis versucht: {versand.telegram_versuche!r}"
    )
    assert dienst.notice_failed == 1, f"F003: notice_failed={dienst.notice_failed!r}, erwartet 1"


def test_fl2_f004_ortsvergleich_kanalausfall_und_hinweisfehler_zaehlt_notice(rig, monkeypatch):
    """F004 (``/compare-alert-checks``): GIVEN ein Ortsvergleich-Alarm an
    E-Mail + Telegram; E-Mail faellt aus (``failed_channels`` nicht leer),
    Telegram-Blase 1 kommt an, Blase 2 und der Hinweis scheitern / WHEN der
    Lauf endet / THEN ``notice_failed >= 1`` -- der Hinweis-Fehlschlag zaehlt
    auch neben einem ausgefallenen Kanal, denn zugestellt ist der Alarm."""
    from tests.tdd.test_alarm_totalausfall_wird_wiederholt import _T0

    uid = _alarm_uid("fl2-f004")
    lage = _vergleich_lage(rig, uid, ("email", "telegram"))
    _vergleich_verdrahten(monkeypatch, {uid: lage.settings}, _beide_orte_boeen())
    rig.zaehler_leeren()
    rig.modus["email"] = "fehler"
    rig.telegram_fehler_bei = {2, 3}

    body = _compare_router_lauf(uid, _T0)

    assert rig.anzahl_versuche("email") >= 1 and rig.anzahl_angenommen("email") == 0, rig
    assert rig.anzahl_versuche("telegram") == 3 and rig.anzahl_angenommen("telegram") == 1, rig
    protokoll = _alarm_protokoll_kern(uid)
    assert any({"channel": "email", "reason": "delivery_failed"} in (e.get("channels_not_sent") or [])
               for e in protokoll), (
        f"Messaufbau: der E-Mail-Ausfall muss als nicht gesendet protokolliert sein: {protokoll!r}"
    )
    assert body.get("notice_failed", _FEHLT) != _FEHLT and body["notice_failed"] >= 1, (
        f"F004: Hinweis-Fehlschlag neben Kanalausfall muss zaehlen: {body!r}"
    )


# ═══════════════════════════ D. Toter Code (AC-16) ═══════════════════════════

_SEND_REPORTS = re.compile(r"\bsend_reports\s*\(")


def test_ac16_send_reports_ist_geloescht():
    """AC-16: ``TripReportSchedulerService.send_reports`` (kein
    Produktionsaufrufer) existiert nicht mehr -- geprueft an der geladenen
    Klasse, nicht am Quelltext.

    RED heute: die Methode existiert."""
    from services.trip_report_scheduler import TripReportSchedulerService

    assert not hasattr(TripReportSchedulerService, "send_reports"), (
        "AC-16: send_reports ist toter Code und muss geloescht sein"
    )


def test_ac16_kein_test_und_keine_modulspec_ruft_send_reports():  # doc-compliance-test
    """AC-16: kein Test unter ``tests/`` ruft ``send_reports(`` auf, und die
    Modul-Spec ``docs/specs/modules/trip_report_scheduler.md`` fuehrt die
    Methode nicht mehr (``send_reports_for_hour``/``send_due_reports`` sind
    andere Namen). Gelesen werden nur Test- und Doku-Dateien, kein Produkt-
    Quelltext. Historische Specs (``_archive``, ``bugfix``, Issue-Specs)
    bleiben als Geschichte unberuehrt; Negativ-Pruefungen ("darf
    ``send_reports(`` nicht enthalten") zaehlen nicht als Aufruf.

    RED heute: ``tests/e2e/test_e2e_story3_reports.py`` und die Modul-Spec."""
    eigene = {Path(__file__).resolve(), (_REPO / "tests" / "test_success_status_guard.py").resolve()}
    treffer = []
    for pfad in sorted((_REPO / "tests").rglob("*.py")):
        if pfad.resolve() in eigene:
            continue
        for nr, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), 1):
            if _SEND_REPORTS.search(zeile) and "not in" not in zeile and "darf" not in zeile:
                treffer.append(f"{pfad.relative_to(_REPO)}:{nr}")
    spec = (_REPO / "docs" / "specs" / "modules" / "trip_report_scheduler.md").read_text(encoding="utf-8")
    # Nur der geltende Teil -- das Changelog darf die Loeschung (und fruehere
    # Staende) als Geschichte nennen.
    geltend = spec.split("## Changelog", 1)[0]
    spec_treffer = [nr for nr, z in enumerate(geltend.splitlines(), 1)
                    if re.search(r"\bsend_reports\b(?!_)", z)]

    assert treffer == [], f"AC-16: Tests rufen send_reports( noch auf: {treffer}"
    assert spec_treffer == [], (
        f"AC-16: trip_report_scheduler.md fuehrt send_reports noch (Zeilen {spec_treffer})"
    )


# ═══════════════════════════ F. Doku-Vertrag (AC-24) ═════════════════════════


def _abschnitte_nach(text: str, marke: str, laenge: int = 2500) -> list[str]:
    return [text[m.start():m.start() + laenge] for m in re.finditer(re.escape(marke), text)]


def test_ac24_api_contract_dokumentiert_partial_und_inbound_antwortform():  # doc-compliance-test
    """AC-24: ``docs/reference/api_contract.md`` dokumentiert (1) fuer
    ``compare-alert-checks``, dass ``failed > 0`` zu ``status: "partial"``
    fuehrt (in EINER Zeile: ``compare-alert-checks`` ... ``failed > 0`` ...
    ``partial``), und (2) die Antwortform von ``/inbound-commands`` als
    Beispiel mit den Schluesseln ``"status"``, ``"count"``, ``"processed"``,
    ``"failed"`` (in Anfuehrungszeichen, bis 2500 Zeichen nach einer
    Erwaehnung des Pfads).

    Nur Doku gelesen. RED heute: beides fehlt."""
    text = (_REPO / "docs" / "reference" / "api_contract.md").read_text(encoding="utf-8")

    compare_partial = [
        z for z in text.splitlines()
        if "compare-alert-checks" in z and re.search(r"failed\W{0,3}\s*>\s*0", z) and "partial" in z
    ]
    inbound_form = [
        a for a in _abschnitte_nach(text, "inbound-commands")
        if all(f'"{k}"' in a for k in ("status", "count", "processed", "failed"))
    ]

    assert compare_partial, (
        "AC-24: api_contract.md nennt nicht, dass compare-alert-checks bei failed > 0 "
        "status 'partial' meldet"
    )
    assert inbound_form, (
        'AC-24: api_contract.md dokumentiert die Antwortform von /inbound-commands '
        '("status", "count", "processed", "failed") nicht'
    )


def test_ac24_waechter_changelog_fuehrt_s4b():  # doc-compliance-test
    """AC-24: das Changelog in ``docs/specs/modules/waechter_1405_erfolg_wirkung.md``
    fuehrt Scheibe S4b mit ``KNOWN_VIOLATIONS`` 8 -> 0 (in einem Eintrag).

    Nur Doku gelesen. RED heute: kein S4b-Eintrag."""
    text = (_REPO / "docs" / "specs" / "modules" / "waechter_1405_erfolg_wirkung.md").read_text(
        encoding="utf-8")
    changelog = text.split("## Changelog", 1)[-1]
    eintraege = re.split(r"\n- (?=\d{4}-\d{2}-\d{2})", changelog)

    assert any("S4b" in e and re.search(r"\b8\s*(→|->)\s*0\b", e) for e in eintraege), (
        "AC-24: Changelog ohne S4b-Eintrag mit 8 -> 0"
    )
