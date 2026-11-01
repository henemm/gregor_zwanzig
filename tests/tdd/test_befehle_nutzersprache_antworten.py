"""Antwortsprache der Inbound-Befehle je Kanal und Kontosprache (Issue #2673).

SPEC: docs/specs/modules/i18n_p10_inbound_2673.md AC-1, AC-2, AC-7.

Echter Eingang: Telegram ueber ``InboundTelegramReader._process_update``,
E-Mail ueber ``InboundEmailReader._process_single`` (Fake-IMAP nur an der
Transportgrenze). Geprueft wird, was tatsaechlich an den Netzrand geht
(Recorder fuer Telegram-API und SMTP). Feste Uhr 2026-10-29T04:00Z.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from freezegun import freeze_time

from tests.helpers.inbound_sprache_fixture import (
    FEST, email_texte, golden_pfad, nutzer_anlegen, telegram_texte,
    trip_anlegen,
)
from tests.tdd._befehl_e2e_fixtures import basis_settings, install_transport_fakes

REPO = Path(__file__).resolve().parents[2]
TOKENS = json.loads((REPO / "tests" / "fixtures" / "metric_tokens_frozen.json")
                    .read_text(encoding="utf-8"))
DEUTSCH = re.compile(r"[äöüÄÖÜß]|\b(nicht|bitte|keine|Etappe|Befehl|Verfügbar|heute)\b")


@pytest.fixture
def netz(monkeypatch):
    return install_transport_fakes(monkeypatch)


def _golden(fall: str) -> str:
    return golden_pfad(fall, "de").read_text(encoding="utf-8")


def _kuerzel_spalte(hilfe: str) -> list[str]:
    """Kuerzel-Spalte der Wetter-Groessen (``  Temp / T         – ...``)."""
    teil = hilfe.split("\n\n")[-1]
    return [z.split(" – ")[0].strip() for z in teil.splitlines() if " – " in z]


# ------------------------------------------------------------------ AC-1


@freeze_time(FEST)
def test_ac1_en_konto_bekommt_status_und_hilfe_englisch_per_telegram(netz):
    uid = "p10-ac1-en"
    nutzer_anlegen(uid, "en")
    trip_anlegen(uid)
    s = basis_settings()

    (status,) = telegram_texte(netz, s, uid, "STATUS")
    assert "Stage 2: Stubai - Neustift" in status and "Thu 29 Oct" in status, status
    assert "Etappe" not in status and "29.10.2026" not in status

    (hilfe,) = telegram_texte(netz, s, uid, "HILFE")
    for wort in ("RESTDAY [N]", "TODAY", "HELP", "STARTDATE YYYY-MM-DD",
                 "Shift stages by N days", "Humidity", "Wind gusts"):
        assert wort in hilfe, (wort, hilfe)
    assert "RUHETAG" not in hilfe and "Luftfeuchtigkeit" not in hilfe
    # Kuerzel-Spalte unveraendert: identisch zur deutschen Hilfe und je Zeile
    # aus col_label/sms_code des Token-Waechters.
    deutsch = _kuerzel_spalte(_golden("hilfe_trip"))
    assert _kuerzel_spalte(hilfe) == deutsch
    col_labels = {v["col_label"] for v in TOKENS.values()}
    assert all(k.split(" / ")[0] in col_labels for k in deutsch)


@freeze_time(FEST)
def test_ac1_en_konto_knoepfe_englisch_callback_unveraendert(netz):
    """Langform-Telegram: Knopf-Beschriftung englisch, ``callback_data`` gleich."""
    knoepfe = {}
    for lang in ("de", "en"):
        uid = f"p10-ac1-knopf-{lang}"
        nutzer_anlegen(uid, lang)
        trip_anlegen(uid)
        vorher = len(netz.telegram_inhalte())
        telegram_texte(netz, basis_settings(), uid, "/th")
        (markup,) = [e["payload"]["reply_markup"] for e in netz.telegram_inhalte()[vorher:]
                     if e["payload"].get("reply_markup")]
        knoepfe[lang] = [k for reihe in markup["inline_keyboard"] for k in reihe]
    assert [k["text"] for k in knoepfe["de"]][-1] == "⬅️ Zurück"
    assert [k["text"] for k in knoepfe["en"]][-1] == "⬅️ Back"
    assert [k["callback_data"] for k in knoepfe["de"]] == [
        k["callback_data"] for k in knoepfe["en"]]


# ------------------------------------------------------------------ AC-2


_FAELLE_AC2 = (
    ("STATUS", "status"), ("HILFE", "hilfe_trip"), ("KUERZEL", "kuerzel"),
    ("RUHETAG 2", "ruhetag_bestaetigung"), ("STOP", "trip_beendet"),
)


@freeze_time(FEST)
@pytest.mark.parametrize("lang", [None, "de"])
@pytest.mark.parametrize("kanal", ["email", "telegram"])
@pytest.mark.parametrize("befehl,fall", _FAELLE_AC2)
def test_ac2_de_konto_antwortet_byte_gleich_zur_golden_fassung(netz, lang, kanal, befehl, fall):
    uid = f"p10-ac2-{kanal}-{lang or 'ohne'}-{fall}"
    nutzer_anlegen(uid, lang)
    trip_anlegen(uid)
    s = basis_settings()
    if kanal == "email":
        (antwort,) = email_texte(netz, s, uid, befehl)
    else:
        (antwort,) = telegram_texte(netz, s, uid, befehl)
    assert antwort == _golden(fall)


@freeze_time(FEST)
@pytest.mark.parametrize("lang", [None, "de"])
def test_ac2_de_konto_unbekannter_befehl_bleibt_deutsch(netz, lang):
    uid = f"p10-ac2-unbekannt-{lang or 'ohne'}"
    nutzer_anlegen(uid, lang)
    trip_anlegen(uid)
    s = basis_settings()
    (mail,) = email_texte(netz, s, uid, "Hilfen")
    assert mail == _golden("unbekannt_trip")
    (tg,) = telegram_texte(netz, s, uid, "Hilfen")
    reader = golden_pfad("reader", "de").read_text(encoding="utf-8")
    assert f"----- telegram_unbekannt -----\n{tg}\n" in reader


# ------------------------------------------------------------------ AC-7


@freeze_time(FEST)
@pytest.mark.parametrize("kanal", ["email", "telegram"])
def test_ac7_en_konto_fehlerantworten_englisch(netz, kanal):
    uid = f"p10-ac7-{kanal}"
    nutzer_anlegen(uid, "en")
    trip_anlegen(uid)
    s = basis_settings()
    senden = email_texte if kanal == "email" else telegram_texte

    (unbekannt,) = senden(netz, s, uid, "Hilfen")
    assert "Unknown command" in unbekannt and "Available: TODAY" in unbekannt
    # Interner Fehler: RUHETAG mit absurder Zahl sprengt die Datumsrechnung.
    (fehler,) = senden(netz, s, uid, "RUHETAG 99999999999")
    assert fehler.startswith("[Command failed]") and "check with STATUS" in fehler
    for text in (unbekannt, fehler):
        assert not DEUTSCH.search(text), text


@freeze_time(FEST)
def test_ac7_en_konto_trip_nicht_gefunden_englisch_per_email(netz):
    uid = "p10-ac7-notfound"
    nutzer_anlegen(uid, "en")
    trip_anlegen(uid)
    (mail,) = email_texte(netz, basis_settings(), uid, "STATUS", trip_name="Gibtsnicht")
    assert mail.startswith("[[Gibtsnicht] Trip not found]"), mail
    assert "No trip named 'Gibtsnicht' found." in mail and not DEUTSCH.search(mail)
    roh = netz.emails[-1]["raw"]
    assert "X-GZ-Lang: en" in roh


@freeze_time(FEST)
@pytest.mark.parametrize("befehl", ["WEITER", "GEWITTER"])
def test_ac7_ohne_trip_und_vergleich_antwortet_die_zielauswahl_in_kontosprache(netz, befehl):
    """Kein Ziel (weder Trip noch Ortsvergleich): Telegram-Antwort der
    Zielauswahl -- fuer Trip-und-Vergleich-Befehle (WEITER) wie fuer reine
    Trip-Befehle (GEWITTER) in der Kontosprache. Gleich lautende Woerter
    (STATUS, PAUSE) zaehlen am Telegram-Eingang englisch (#2417 AC-5)."""
    texte = {}
    for lang in ("de", "en"):
        uid = f"p10-ac7-leer-{lang}-{befehl.lower()}"
        nutzer_anlegen(uid, lang)
        (texte[lang],) = telegram_texte(netz, basis_settings(), uid, befehl)
    assert "Kein aktiver Trip oder Ortsvergleich gefunden." in texte["de"]
    assert texte["en"] == "[Error]\n\nNo active trip or location comparison found."


@freeze_time(FEST)
def test_ac7_de_konto_antwortmail_traegt_x_gz_lang_de(netz):
    uid = "p10-ac7-header-de"
    nutzer_anlegen(uid, "de")
    trip_anlegen(uid)
    email_texte(netz, basis_settings(), uid, "STATUS")
    assert "X-GZ-Lang: de" in netz.emails[-1]["raw"]


def test_ac7_befehlsblock_englisch_und_deutsch_byte_gleich():
    from output.renderers.email.command_block import render_commands_plain
    from services.trip_command_processor import command_rows

    weitere = golden_pfad("weitere", "de").read_text(encoding="utf-8")
    for kind in ("route", "vergleich"):
        de = "\n".join(f"{c} | {b}" for c, b in command_rows(kind, lang="de"))
        assert f"----- command_rows_{kind} -----\n{de}\n" in weitere
        en = command_rows(kind, lang="en")
        woerter = [c.split()[0] for c, _ in en]
        assert {"TODAY", "TOMORROW", "RESUME", "HELP", "CODES"} <= set(woerter)
        assert not any(DEUTSCH.search(b) for _, b in en), en
    zeilen = dict(command_rows("route", lang="en"))
    assert "STARTDATE YYYY-MM-DD" in zeilen and "STARTDATUM JJJJ-MM-TT" not in zeilen
    block = render_commands_plain("vergleich", lang="en")
    assert "Send the comparison to all channels now" in block and "HEUTE" not in block
