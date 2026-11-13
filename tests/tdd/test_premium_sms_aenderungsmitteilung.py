"""Mitteilung ueber andere Kanaele bei zustandsaendernden Premium-SMS-Befehlen
(Issue #2961 Welle 2, ADR-0116, Spec AC-9..AC-12).

Statt eines PIN je Nachricht: fuehrt eine Premium-SMS einen Befehl aus, der
etwas veraendert (Briefings pausieren/stoppen/fortsetzen, Ruhetag,
Startdatum, Etappe ueberspringen), bekommt der Nutzer zusaetzlich eine kurze
Mitteilung per E-Mail (nur an die bestaetigte Adresse) und Telegram (falls
verbunden). Lesende Befehle loesen nichts aus; hoechstens 10 Mitteilungen je
Nutzer und Tag.

Gemessen durch den echten Eingang (Journal-Poll -> Lern-Antwort -> Prozessor
-> NotificationService) mit dem Aufbau aus ``test_premium_sms_kommandopfad``:
ersetzt sind nur die Aussengrenzen (Journal, Lern-Endpunkt, die vier
Kanal-Ausgaenge) durch Aufzeichner-Klassen.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.loader import get_data_dir
from services import premium_sms_aenderungshinweis as hinweis
from services.trip_command_processor import _BARE_KEYWORD_MAP, _VALID_COMMANDS
from tests.tdd.test_premium_sms_kommandopfad import (
    _TRANSPORT_ENV,
    NUMMER_A,
    NUMMER_B,
    RUECKADRESSE_A,
    RUECKADRESSE_B,
    _aufzeichner_installieren,
    _garmin,
    _Journal,
    _kennung,
    _LernEndpunkt,
    _poll,
    _trip_anlegen,
)


@pytest.fixture
def mitschrift(monkeypatch):
    """Dieselben Aufzeichner wie in ``test_premium_sms_kommandopfad``."""
    for name, wert in _TRANSPORT_ENV.items():
        monkeypatch.setenv(name, wert)
    return _aufzeichner_installieren(monkeypatch)


def _nutzer(user_id: str, *, rueckadresse: str, bestaetigt: bool = True,
            telegram: bool = True) -> None:
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    profil = {
        "id": user_id, "tier": "premium",
        "mail_to": f"{user_id}@example.invalid",
        "premium_sms_reply_to": rueckadresse,
        "premium_sms_reply_at": datetime.now(timezone.utc).isoformat(),
    }
    if bestaetigt:
        profil["email_verified_at"] = "2026-10-01T00:00:00Z"
    if telegram:
        profil["telegram_chat_id"] = f"chat-{user_id}"
    (ordner / "user.json").write_text(json.dumps(profil))


def _befehl(monkeypatch, nummer: str, user_id: str, text: str, msg_id: int = 501):
    journal = _Journal([[_garmin(msg_id, nummer, text)]])
    _poll(monkeypatch, journal=journal,
          lernen=_LernEndpunkt(nummer_zu_user={nummer: user_id}))


def test_pause_meldet_auf_email_und_telegram_nur_dem_eigenen_konto(monkeypatch, mitschrift):
    """AC-9: PAUSE per Premium-SMS -> Antwort per Premium-SMS plus je eine
    Mitteilung an die bestaetigte E-Mail und den Telegram-Chat DIESES Kontos;
    das zweite Konto bekommt nichts."""
    anna, bert = _kennung("anna"), _kennung("bert")
    _nutzer(anna, rueckadresse=RUECKADRESSE_A)
    _nutzer(bert, rueckadresse=RUECKADRESSE_B)
    _trip_anlegen(anna, name="Hochtour Anna")
    _trip_anlegen(bert, name="Hochtour Bert")

    _befehl(monkeypatch, NUMMER_A, anna, "pause 2d")

    assert mitschrift.empfaenger("premium_sms") == [RUECKADRESSE_A], mitschrift
    assert mitschrift.empfaenger("email") == [f"{anna}@example.invalid"], mitschrift
    assert mitschrift.empfaenger("telegram") == [f"chat-{anna}"], mitschrift
    mail = mitschrift.je_kanal["email"][0]
    for teil in ("Premium-SMS", "pause", "WEITER", "UTC"):
        assert teil in mail["subject"] + mail["body"], (teil, mail)
    assert bert not in json.dumps(mitschrift.je_kanal)


def test_lesender_befehl_loest_keine_mitteilung_aus(monkeypatch, mitschrift):
    """AC-10: STATUS veraendert nichts -> nur die Premium-SMS-Antwort."""
    anna = _kennung("anna")
    _nutzer(anna, rueckadresse=RUECKADRESSE_A)
    _trip_anlegen(anna, name="Hochtour Anna")

    _befehl(monkeypatch, NUMMER_A, anna, "status")

    assert mitschrift.kanaele == ["premium_sms"], mitschrift


def test_unbestaetigte_adresse_bekommt_keine_mail(monkeypatch, mitschrift):
    """AC-11: E-Mail nur an eine bestaetigte Adresse; Telegram unabhaengig."""
    anna = _kennung("anna")
    _nutzer(anna, rueckadresse=RUECKADRESSE_A, bestaetigt=False)
    _trip_anlegen(anna, name="Hochtour Anna")

    _befehl(monkeypatch, NUMMER_A, anna, "pause 2d")

    assert mitschrift.je_kanal["email"] == [], mitschrift
    assert mitschrift.empfaenger("telegram") == [f"chat-{anna}"], mitschrift


def test_hoechstens_zehn_mitteilungen_je_tag(monkeypatch, mitschrift):
    """AC-12: nach zehn Mitteilungen an einem Tag kommt keine elfte; die
    Befehle selbst und ihre Antworten laufen weiter. Ein zweites Konto hat
    sein eigenes Kontingent."""
    anna, bert = _kennung("anna"), _kennung("bert")
    _nutzer(anna, rueckadresse=RUECKADRESSE_A, telegram=False)
    _nutzer(bert, rueckadresse=RUECKADRESSE_B, telegram=False)
    _trip_anlegen(anna, name="Hochtour Anna")
    _trip_anlegen(bert, name="Hochtour Bert")

    for i in range(11):
        _befehl(monkeypatch, NUMMER_A, anna, "pause 2d" if i % 2 == 0 else "weiter", msg_id=600 + i)
    assert len(mitschrift.je_kanal["email"]) == hinweis.TAGESGRENZE == 10, mitschrift
    assert len(mitschrift.premium) == 11, "die Befehlsantworten selbst bleiben unbegrenzt durch die Mitteilung"

    _befehl(monkeypatch, NUMMER_B, bert, "pause 2d", msg_id=700)
    assert mitschrift.empfaenger("email")[-1] == f"{bert}@example.invalid"


@pytest.mark.parametrize("schluessel", sorted(set(_VALID_COMMANDS) | set(_BARE_KEYWORD_MAP.values())))
def test_jeder_befehl_ist_als_aendernd_oder_lesend_eingestuft(schluessel):
    """Klassifikationswaechter: jeder Befehlsschluessel des Verarbeiters ist
    genau einer Klasse zugeordnet -- ein neuer Befehl kann nicht still ohne
    Mitteilung bleiben."""
    aendernd = schluessel in hinweis.ZUSTANDSAENDERNDE_BEFEHLE
    lesend = schluessel in hinweis.LESENDE_BEFEHLE
    assert aendernd != lesend, schluessel


# ---------------------------------------------------------------------------
# Gegenpruefung F003
# ---------------------------------------------------------------------------


def _startdatum_text() -> str:
    from datetime import timedelta

    return f"startdatum {(datetime.now(timezone.utc).date() + timedelta(days=10)).isoformat()}"


@pytest.mark.parametrize("text, schluessel", [
    ("pause 2d", "pause"), ("stop", "abbruch"), ("weiter", "weiter"),
    ("ruhetag", "ruhetag"), ("skip", "skip"), (None, "startdatum"),
])
def test_jeder_aendernde_befehl_meldet_ueber_den_echten_weg(monkeypatch, mitschrift, text, schluessel):
    """Jeder als aendernd eingestufte Befehl loest durch den echten Eingang
    eine Mitteilung aus -- nicht nur laut Einstufungs-Waechter."""
    assert schluessel in hinweis.ZUSTANDSAENDERNDE_BEFEHLE
    anna = _kennung("anna")
    _nutzer(anna, rueckadresse=RUECKADRESSE_A, telegram=False)
    _trip_anlegen(anna, name="Hochtour Anna")

    _befehl(monkeypatch, NUMMER_A, anna, text or _startdatum_text())

    assert mitschrift.empfaenger("email") == [f"{anna}@example.invalid"], mitschrift


def test_fehlgeschlagener_aendernder_befehl_meldet_nichts(monkeypatch, mitschrift):
    """"pause" ohne Dauer ist ein fehlgeschlagener aendernder Befehl: nur die
    Premium-SMS-Antwort, keine Mitteilung."""
    anna = _kennung("anna")
    _nutzer(anna, rueckadresse=RUECKADRESSE_A)
    _trip_anlegen(anna, name="Hochtour Anna")

    _befehl(monkeypatch, NUMMER_A, anna, "pause")

    assert mitschrift.kanaele == ["premium_sms"], mitschrift


def test_ohne_zustellbaren_kanal_wird_kein_mitteilungs_zaehler_verbraucht(monkeypatch, mitschrift):
    anna = _kennung("anna")
    _nutzer(anna, rueckadresse=RUECKADRESSE_A, bestaetigt=False, telegram=False)
    _trip_anlegen(anna, name="Hochtour Anna")

    _befehl(monkeypatch, NUMMER_A, anna, "pause 2d")

    assert mitschrift.kanaele == ["premium_sms"], mitschrift
    pfad = get_data_dir(anna) / "sms_daily_count.json"
    stand = json.loads(pfad.read_text()) if pfad.exists() else {}
    assert hinweis.ZAEHLER_SCHLUESSEL not in stand, stand


def test_fehler_beim_mitteilungsversand_bricht_die_verarbeitung_nicht_ab(monkeypatch, mitschrift, caplog):
    """Fail-soft am Wirkort: wirft der Versand der Mitteilung, laeuft die
    Befehlsverarbeitung ohne Fehlermeldung des Readers weiter."""
    import logging

    from services.notification_service import NotificationService

    def _wirft(self, subject, body):
        raise RuntimeError("Mitteilungsversand kaputt")

    monkeypatch.setattr(NotificationService, "send_premium_sms_change_notice", _wirft)
    anna = _kennung("anna")
    _nutzer(anna, rueckadresse=RUECKADRESSE_A)
    _trip_anlegen(anna, name="Hochtour Anna")

    with caplog.at_level(logging.WARNING):
        _befehl(monkeypatch, NUMMER_A, anna, "pause 2d")

    assert mitschrift.empfaenger("premium_sms") == [RUECKADRESSE_A]
    assert not any("Kommandoverarbeitung fehlgeschlagen" in r.getMessage() for r in caplog.records), caplog.text


@pytest.mark.parametrize("lang, ergebnis_label", [("de", "Ergebnis:"), ("en", "Result:")])
def test_mitteilungstext_nennt_das_ergebnis(lang, ergebnis_label):
    from services.trip_command_processor import CommandResult

    result = CommandResult(
        success=True, command="skip", confirmation_subject="x",
        confirmation_body="Etappe 2 uebersprungen", trip_name="Hochtour",
    )
    betreff, text = hinweis.texte(result, "skip", datetime(2026, 11, 13, 8, 30, tzinfo=timezone.utc), lang)
    assert "skip" in betreff
    assert f"{ergebnis_label} Etappe 2 uebersprungen" in text
    assert "Hochtour" in text and "2026-11-13 08:30 UTC" in text
