"""TDD RED — Kommando "report" meldet das echte Ergebnis (Issue #1405 S1, B15/B16/B1).

SPEC: docs/specs/modules/fix_1405_s1_alarm_zustellung.md (Abschnitt G, AC-22..AC-25)
Kontext: docs/context/fix-1405-s1-alarm-zustellung.md

Defekt (B15): ``TripCommandProcessor._trigger_report`` verwirft das Ergebnis von
``send_test_report`` und antwortet IMMER "Report gesendet" — auch wenn keine
Etappe, kein Wetter oder kein Kanal da war. Eine Ausnahme beim Ausloesen wird
nicht gefangen. B16/B1: ``_trigger_on_demand`` bzw. der Endpunkt
``send_test_trip_report`` schreiben ihr Erfolgskennzeichen als festen Wert.

Kontrollierter Ausloeser (keine Mock-Spiegel): die Methoden
``TripReportSchedulerService.send_test_report_outcome`` UND
``send_test_report`` (heutiger Aufrufer, sonst liefe der volle Versandpfad)
werden per ``monkeypatch.setattr`` durch ECHTE Funktionen ersetzt, die je
Nutzer ein festgelegtes Ergebnis liefern bzw. werfen und jeden Aufruf
(user_id, trip_id) mitschreiben. Fuer AC-25 ebenso
``send_on_demand_report`` (liefert ein echtes ``OnDemandErgebnis``).

AC-24 laeuft durch die DREI echten Eingaenge (``InboundEmailReader._process_single``,
``InboundTelegramReader._process_update``, ``InboundSmsReader.poll_and_process``)
ueber das Fundament ``tests/tdd/_befehl_e2e_fixtures.py`` — die Antworten
werden am Netzrand (httpx/smtplib-Recorder) abgegriffen, nicht am Rueckgabewert.
"""
from __future__ import annotations

import email as email_lib
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.trip_command_processor import (  # noqa: E402
    InboundMessage,
    TripCommandProcessor,
    _on_demand_failure_body,
)
from services.trip_report_scheduler import (  # noqa: E402
    OnDemandErgebnis,
    TripReportSchedulerService,
)
from tests.tdd._befehl_e2e_fixtures import (  # noqa: E402
    _trip,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    sende_email,
    sende_premium_sms,
    sende_telegram_text,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

ALLE_ERGEBNISSE = (
    "sent", "no_stage", "no_weather", "no_channels",
    "channels_unreachable", "already_in_progress",
)


# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------

def _ausloeser_installieren(monkeypatch, ergebnis_je_nutzer: dict[str, object]) -> list[tuple[str, str]]:
    """Ersetzt beide Ausloese-Methoden des Schedulers durch echte Funktionen.

    ``ergebnis_je_nutzer[user_id]`` ist ein Ergebnis-String oder eine
    Exception-Instanz (dann wird sie geworfen). Rueckgabe: Aufrufprotokoll
    ``[(user_id, trip_id), ...]``."""
    aufrufe: list[tuple[str, str]] = []

    def _ergebnis(self, trip):
        aufrufe.append((self._user_id, trip.id))
        wert = ergebnis_je_nutzer[self._user_id]
        if isinstance(wert, BaseException):
            raise wert
        return wert

    def _outcome(self, trip, report_type):
        return _ergebnis(self, trip)

    def _bool(self, trip, report_type):
        return _ergebnis(self, trip) == "sent"

    monkeypatch.setattr(TripReportSchedulerService, "send_test_report_outcome", _outcome)
    monkeypatch.setattr(TripReportSchedulerService, "send_test_report", _bool)
    return aufrufe


_ERFOLG_DE = re.compile(r"(?<!nicht )(?<!kein )\bgesendet\b", re.IGNORECASE)
_ERFOLG_EN = re.compile(r"(?<!not )(?<!never )\bsent\b", re.IGNORECASE)


def _meldet_versand(text: str) -> bool:
    """Behauptet der Text einen erfolgten Versand ("Report gesendet",
    "wird jetzt gesendet", "Report sent")? Verneinte Formen ("nicht gesendet",
    "not sent") gelten NICHT als Erfolgsmeldung."""
    return bool(_ERFOLG_DE.search(text) or _ERFOLG_EN.search(text))


def _ohne(text: str, *namen: str) -> str:
    for n in namen:
        text = text.replace(n, "<NAME>")
    return text


def _process_report(trip, user_id: str) -> object:
    return TripCommandProcessor().process(InboundMessage(
        trip_name=trip.name, body="### report: morning", sender=f"{user_id}@henemm.com",
        channel="email", received_at=datetime.now(tz=timezone.utc), user_id=user_id,
    ))


def _mailtext(raw: str) -> str:
    msg = email_lib.message_from_string(raw)
    teile = [msg.get("Subject", "")]
    for p in msg.walk():
        if p.get_content_type() in ("text/plain", "text/html"):
            nutz = p.get_payload(decode=True)
            if nutz is not None:
                teile.append(nutz.decode(p.get_content_charset() or "utf-8", errors="replace"))
    return "\n".join(teile)


# ═══════════════════════════ AC-22 ═══════════════════════════════════════════


def test_ac22_report_antwort_folgt_dem_echten_ergebnis(monkeypatch, user_ids):
    """AC-22.

    GIVEN ein Nutzer mit Trip, der das Kommando "report" sendet
    WHEN  das Ergebnis des Test-Reports nacheinander ``sent``, ``no_stage``,
          ``no_weather``, ``no_channels``, ``channels_unreachable``,
          ``already_in_progress`` ist
    THEN  sind die sechs Antworttexte paarweise verschieden, nur ``sent``
          meldet einen Versand ("gesendet") und gilt als erfolgreich; alle
          anderen nennen einen Grund und haben ``success is False``.

    RED heute: Antwort ist immer "Report gesendet", ``success=True``.
    """
    install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    antworten: dict[str, tuple[bool, str]] = {}
    for ergebnis in ALLE_ERGEBNISSE:
        _ausloeser_installieren(monkeypatch, {nutzer.user_id: ergebnis})
        res = _process_report(nutzer.trip, nutzer.user_id)
        assert res.command == "report", f"Vorbedingung: Kommando nicht erkannt: {res!r}"
        text = f"{res.confirmation_subject}\n{res.confirmation_body}"
        antworten[ergebnis] = (res.success, _ohne(text, nutzer.trip.name))

    erfolg_sent, text_sent = antworten["sent"]
    assert erfolg_sent is True, f"AC-22: 'sent' muss als Erfolg gelten: {antworten['sent']!r}"
    assert _meldet_versand(text_sent), f"AC-22: 'sent' muss den Versand melden: {text_sent!r}"

    for ergebnis in ALLE_ERGEBNISSE[1:]:
        erfolg, text = antworten[ergebnis]
        assert erfolg is False, (
            f"AC-22: Ergebnis {ergebnis!r} darf nicht als Erfolg gelten (success={erfolg!r}), "
            f"Antwort: {text!r}"
        )
        assert not _meldet_versand(text), (
            f"AC-22: Ergebnis {ergebnis!r} darf keinen Versand melden, Antwort: {text!r}"
        )

    texte = [t for _, t in antworten.values()]
    doppelt = {e: t for e, (_, t) in antworten.items() if texte.count(t) > 1}
    assert not doppelt, (
        f"AC-22: die Antworttexte muessen je Ergebnis verschieden sein; gleich sind: {doppelt!r}"
    )


# ═══════════════════════════ AC-23 ═══════════════════════════════════════════


def test_ac23_ausloeser_wirft_ergibt_fehlermeldung_ohne_absturz(monkeypatch, user_ids):
    """AC-23.

    GIVEN ein Nutzer mit Trip; das Ausloesen des Test-Reports wirft eine Ausnahme
    WHEN  das Kommando "report" verarbeitet wird
    THEN  stuerzt der Befehlsablauf nicht ab, die Antwort ist eine Fehlermeldung
          ohne Versandmeldung, und ``success is False``.

    RED heute: ``_trigger_report`` faengt die Ausnahme nicht — sie propagiert.
    """
    install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    _ausloeser_installieren(monkeypatch, {nutzer.user_id: RuntimeError("SMTP kaputt")})

    try:
        res = _process_report(nutzer.trip, nutzer.user_id)
    except Exception as exc:  # noqa: BLE001 — genau das ist der Befund
        pytest.fail(f"AC-23: der Befehlsablauf stuerzt ab statt zu antworten: {exc!r}")

    text = f"{res.confirmation_subject}\n{res.confirmation_body}"
    assert res.success is False, f"AC-23: Ausnahme darf nicht als Erfolg gelten: {res!r}"
    assert not _meldet_versand(text), f"AC-23: keine Versandmeldung bei Ausnahme: {text!r}"
    assert text.strip(), "AC-23: der Nutzer muss eine Fehlermeldung bekommen"


def test_ac23_ausloeser_wirft_durch_echten_telegram_eingang(monkeypatch, user_ids):
    """AC-23 (am echten Eingang).

    GIVEN ein Nutzer mit Trip; das Ausloesen wirft eine Ausnahme
    WHEN  er "report" per Telegram sendet
    THEN  bekommt er auf seinem Chat eine Antwort, die keinen Versand meldet.

    RED heute: die Ausnahme verlaesst ``_trigger_report``; entweder bekommt der
    Nutzer gar keine Antwort oder eine generische ohne Bezug.
    """
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    _ausloeser_installieren(monkeypatch, {nutzer.user_id: RuntimeError("SMTP kaputt")})

    try:
        sende_telegram_text(basis_settings(), nutzer, "report")
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"AC-23: der Telegram-Eingang stuerzt ab: {exc!r}")

    inhalte = recorder.telegram_inhalte(nutzer.telegram_chat_id)
    assert inhalte, f"AC-23: keine Antwort an den Fragenden: {recorder.telegram!r}"
    text = inhalte[-1]["payload"].get("text", "")
    assert not _meldet_versand(text), f"AC-23: Versandmeldung trotz Ausnahme: {text!r}"


# ═══════════════════════════ AC-24 ═══════════════════════════════════════════


def _zwei_nutzer(user_ids):
    a = lege_lage_an(user_ids, "L1")
    a.trip = _trip(a.user_id, "Anna Hochweg")
    b = lege_lage_an(user_ids, "L1")
    b.trip = _trip(b.user_id, "Bert Talpfad")
    assert a.user_id != "default" and b.user_id != "default"
    return a, b


def _antwort_email(recorder, nutzer) -> list[str]:
    return [_mailtext(e["raw"]) for e in recorder.emails if nutzer.mail_to in e["to"]]


def _antwort_telegram(recorder, nutzer) -> list[str]:
    return [e["payload"].get("text", "") for e in recorder.telegram_inhalte(nutzer.telegram_chat_id)]


def _antwort_sms(recorder, nutzer) -> list[str]:
    return [e["text"] for e in recorder.premium_sms_out if e["to"] == nutzer.premium_sms_reply_to]


_EINGAENGE = {
    "email": (
        lambda s, r, n: sende_email(s, n, "### report: morning"),
        _antwort_email,
    ),
    "telegram": (
        lambda s, r, n: sende_telegram_text(s, n, "report"),
        _antwort_telegram,
    ),
    "premium_sms": (
        # Premium-SMS kennt "report" nicht als nacktes Wort (nur Telegram hat
        # den _VALID_COMMANDS-Rueckfall) -- daher die ###-Form wie bei E-Mail.
        lambda s, r, n: sende_premium_sms(s, r, n, "### report: morning"),
        _antwort_sms,
    ),
}


@pytest.mark.parametrize("eingang", list(_EINGAENGE))
def test_ac24_zwei_nutzer_bekommen_je_ihr_eigenes_ergebnis_ueber_ihren_eingang(
    monkeypatch, user_ids, eingang,
):
    """AC-24.

    GIVEN zwei Nutzer mit je eigenem Trip; der Test-Report liefert fuer
          Nutzer A ``sent`` und fuer Nutzer B ``no_channels``
    WHEN  beide das Kommando "report" ueber denselben echten Eingang
          (E-Mail / Telegram / Premium-SMS) senden
    THEN  bekommt jeder genau auf seiner eigenen Adresse eine Antwort: A meldet
          den Versand, B meldet ihn NICHT und unterscheidet sich von A; jede
          Antwort nennt nur den eigenen Trip, und der Ausloeser wurde je Nutzer
          nur mit dessen eigenem Trip aufgerufen.

    RED heute: B bekommt ebenfalls "Report gesendet".
    """
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    a, b = _zwei_nutzer(user_ids)
    aufrufe = _ausloeser_installieren(monkeypatch, {a.user_id: "sent", b.user_id: "no_channels"})
    senden, antworten_von = _EINGAENGE[eingang]

    senden(settings, recorder, a)
    senden(settings, recorder, b)

    recorder.pruefe_keine_unbekannten_aufrufe()
    assert sorted(aufrufe) == sorted([(a.user_id, a.trip.id), (b.user_id, b.trip.id)]), (
        f"AC-24: der Ausloeser muss je Nutzer genau einmal mit dessen eigenem Trip "
        f"laufen (Vorbedingung: Kommando erreicht den Report-Pfad): {aufrufe!r}"
    )

    antworten_a = antworten_von(recorder, a)
    antworten_b = antworten_von(recorder, b)
    assert antworten_a, f"AC-24 [{eingang}]: Nutzer A bekam keine Antwort auf seinem Kanal"
    assert antworten_b, f"AC-24 [{eingang}]: Nutzer B bekam keine Antwort auf seinem Kanal"
    text_a, text_b = antworten_a[-1], antworten_b[-1]

    assert _meldet_versand(text_a), f"AC-24 [{eingang}]: A ('sent') muss den Versand melden: {text_a!r}"
    assert not _meldet_versand(text_b), (
        f"AC-24 [{eingang}]: B ('no_channels') darf keinen Versand melden: {text_b!r}"
    )
    assert _ohne(text_a, a.trip.name) != _ohne(text_b, b.trip.name), (
        f"AC-24 [{eingang}]: A und B muessen unterschiedliche Antworten bekommen: "
        f"{text_a!r} / {text_b!r}"
    )

    # Keine Datenvermischung.
    for text_eigen, eigen, fremd in ((text_a, a, b), (text_b, b, a)):
        assert fremd.trip.name not in text_eigen, (
            f"AC-24 [{eingang}]: Antwort an {eigen.user_id} nennt den fremden Trip: {text_eigen!r}"
        )
        assert fremd.user_id not in text_eigen
    for e in recorder.emails:
        assert not (a.mail_to in e["to"] and b.mail_to in e["to"]), "AC-24: Mail an beide Nutzer"


# ═══════════════════════════ AC-25 ═══════════════════════════════════════════


@pytest.mark.parametrize("outcome, erwartet", [("sent", True), ("no_channels", False), ("no_stage", False)])
def test_ac25_on_demand_success_folgt_dem_outcome(monkeypatch, user_ids, outcome, erwartet):
    """AC-25 (B16, ``_trigger_on_demand``).

    GIVEN ein Nutzer mit Trip; das On-Demand-Briefing liefert ``outcome``
    WHEN  er "heute" sendet
    THEN  ist ``success`` genau dann True, wenn ``outcome == "sent"``; der
          Antworttext fuer Nicht-``sent`` bleibt der bisherige Fehlertext.

    RED heute: ``success=True`` in beiden Zweigen.
    """
    install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    zieltag = date(2026, 10, 9)

    def _on_demand(self, trip, report_type, *, restrict_to_channel=None, **kw):
        assert self._user_id == nutzer.user_id and trip.id == nutzer.trip.id
        return OnDemandErgebnis(outcome=outcome, zieltag=zieltag)

    monkeypatch.setattr(TripReportSchedulerService, "send_on_demand_report", _on_demand)

    res = TripCommandProcessor().process(InboundMessage(
        trip_name=nutzer.trip.name, body="### query: heute", sender=nutzer.mail_to,
        channel="email", received_at=datetime.now(tz=timezone.utc), user_id=nutzer.user_id,
    ))

    assert res.command == "heute", f"Vorbedingung: On-Demand-Pfad nicht erreicht: {res!r}"
    if outcome != "sent":
        assert res.confirmation_body == _on_demand_failure_body(outcome, "Heute", zieltag, en=False), (
            "AC-25: der Antworttext darf sich nicht aendern"
        )
    assert res.success is erwartet, (
        f"AC-25: success muss aus dem Outcome {outcome!r} folgen (erwartet {erwartet}), "
        f"ist {res.success!r}"
    )


def _endpunkt(monkeypatch, user_ids, outcome: str):
    from fastapi.testclient import TestClient
    from api.main import app

    nutzer = lege_lage_an(user_ids, "L2")
    monkeypatch.setattr("app.config.Settings.can_send_email", lambda self: True)
    monkeypatch.setattr(
        TripReportSchedulerService, "send_test_report_outcome",
        lambda self, trip, report_type: outcome,
    )
    return TestClient(app).post(
        f"/api/scheduler/trips/{nutzer.trip.id}/send",
        params={"user_id": nutzer.user_id, "report_type": "evening"},
    )


def test_ac25_endpunkt_sent_bleibt_200_mit_sent_true(monkeypatch, user_ids):
    """AC-25 (B1, Regression).

    GIVEN der Endpunkt ``send_test_trip_report`` und Outcome ``sent``
    WHEN  er aufgerufen wird
    THEN  200 und ``"sent": True`` (unveraendert).
    """
    resp = _endpunkt(monkeypatch, user_ids, "sent")
    assert resp.status_code == 200, resp.text
    assert resp.json()["sent"] is True


def test_ac25_endpunkt_no_channels_bleibt_422(monkeypatch, user_ids):
    """AC-25 (B1, Regression Statuscode).

    GIVEN Outcome ``no_channels``
    WHEN  der Endpunkt aufgerufen wird
    THEN  bleibt der Statuscode 422 (unveraendert) — kein Erfolgskennzeichen.
    """
    resp = _endpunkt(monkeypatch, user_ids, "no_channels")
    assert resp.status_code == 422, resp.text
    assert "sent" not in resp.json()


def test_ac25_endpunkt_sent_kennzeichen_ist_aus_outcome_abgeleitet(monkeypatch, user_ids):
    """AC-25 (B1, Ableitung beobachtbar).

    Alle sechs bekannten Nicht-``sent``-Outcomes enden heute VOR dem
    ``return`` in 422/409 — dort ist ein festes ``True`` vom abgeleiteten
    Wert per Verhalten nicht unterscheidbar. Beobachtbar wird die Ableitung
    nur mit einem Outcome, das in keinen Fehlerzweig faellt.

    GIVEN ein Outcome, das kein bekannter Fehlerzweig ist (``"zugestellt_teilweise"``)
    WHEN  der Endpunkt antwortet (200, Statuscode unveraendert)
    THEN  ist ``"sent"`` False, weil ``outcome != "sent"``.

    RED heute: ``"sent": True`` ist als fester Wert geschrieben.
    """
    resp = _endpunkt(monkeypatch, user_ids, "zugestellt_teilweise")
    assert resp.status_code == 200, resp.text
    assert resp.json()["sent"] is False, (
        f"AC-25: 'sent' muss aus dem Outcome abgeleitet sein, nicht fest True: {resp.json()!r}"
    )
