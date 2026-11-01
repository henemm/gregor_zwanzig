"""Versand-Schicht zweisprachig (Issue #2671, AC-1, AC-2, AC-5, AC-6, AC-7, Ratsche).

SPEC: docs/specs/modules/i18n_p9a_versand_schicht_2671.md

Erwartungen kommen aus dem Katalog (``t(key, lang)``), nie aus getippten
Literalen; je Schluessel wird zusaetzlich belegt, dass ``en`` wirklich englisch
ist (kein stiller Rueckfall auf ``de``). Gemessen wird am Draht (``KanalRig``:
SMTP-, Telegram-, seven.io-Gegenstelle), die Sprache steht in ``user.json``.

SMS, Premium-SMS und Telegram-Kurzstil bleiben in jeder Sprache byte-gleich
(PO-Korrektur 2026-10-31, ADR-0104 Praezisierung) -- AC-7.

Die Ratsche ist VERHALTEN (kein Quelltext-Lesen, #765): die englische Ausgabe
aller Golden-Faelle enthaelt kein Umlaut-Wort und kein deutsches Bruchstueck
des Katalogs ``versand.*``; ausgenommen sind nur die SMS-Kanaele und Daten des
Aufrufers (Etappen-/Trip-Namen, Grund-Text).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from i18n import t
from output.subject import build_email_subject
from output.tokens.dto import Token, TokenLine
from services.send_outcomes import SEND_OUTCOMES, error_body
from tests.helpers.versand_fixture import (
    alle_texte, ausfall_texte, alarm_sms_hinweis, betreffe, fehlertexte, letzte_mail,
    nutzer_anlegen, rig_starten,
)

KATALOG = Path(__file__).resolve().parents[1] / "src" / "i18n" / "messages"


@pytest.fixture
def rig(monkeypatch):
    r = rig_starten(monkeypatch)
    yield r
    r.stoppen()


def _englisch(key: str, **kw) -> str:
    en, de = t(key, "en", **kw), t(key, "de", **kw)
    assert en != de, f"{key}: en faellt auf de zurueck ({en!r})"
    return en


# ---------------------------------------------------------------- AC-1


def test_ac1_testversand_englisch_mit_kopf(rig):
    from services.channel_test_service import send_test_message

    nutzer_anlegen("versand-en", "en")
    assert send_test_message("email", "versand-en") == {"status": "ok"}
    m = letzte_mail(rig)
    assert m["betreff"] == _englisch("versand.test.betreff")
    assert m["plain"] == _englisch("versand.test.text")
    assert m["lang"] == "en"


def test_ac1_testversand_deutsch_bleibt(rig):
    from services.channel_test_service import send_test_message

    nutzer_anlegen("versand-de", "de")
    send_test_message("email", "versand-de")
    m = letzte_mail(rig)
    assert (m["betreff"], m["plain"], m["lang"]) == (
        t("versand.test.betreff", "de"), t("versand.test.text", "de"), "de")


def test_ac1_unbekannter_kanal_englisch(rig):
    from services.channel_test_service import send_test_message

    nutzer_anlegen("versand-en", "en")
    assert send_test_message("fax", "versand-en") == {
        "error": _englisch("versand.test.kanal_unbekannt", kanal="fax")}


# ---------------------------------------------------------------- AC-2


def _tok(sym: str, val: str) -> Token:
    return Token(symbol=sym, value=val, category="forecast", priority=4)


def _zeile(typ: str, risiko: str | None, etappe: str = "Etappe 3") -> TokenLine:
    return TokenLine(stage_name=etappe, report_type=typ, trip_name="GR20", main_risk=risiko,
                     tokens=(_tok("D", "13"), _tok("W", "30"), _tok("G", "55")))


def test_ac2_betreff_englisch_mit_unveraenderten_token():
    morgen = _englisch("versand.betreff.bericht.morgen")
    gewitter = _englisch("versand.betreff.risiko.gewitter")
    assert build_email_subject(_zeile("morning", "Thunder"), lang="en") == (
        f"[GR20] Etappe 3 — {morgen} — {gewitter} D13 W30 G55")


@pytest.mark.parametrize("typ,schluessel", [
    ("morning", "morgen"), ("evening", "abend"), ("update", "update")])
def test_ac2_berichtsart_je_sprache(typ, schluessel):
    for lang in ("de", "en"):
        assert build_email_subject(_zeile(typ, None), lang=lang).startswith(
            f"[GR20] Etappe 3 — {t(f'versand.betreff.bericht.{schluessel}', lang)} —")


@pytest.mark.parametrize("risiko,schluessel", [
    ("Thunder", "gewitter"), ("Storm", "sturm"), ("Heat", "hitze"), ("Cold", "kaelte"),
    ("Rain", "regen"), ("Snow", "schnee"), ("Wind", "wind")])
def test_ac2_risiko_je_sprache(risiko, schluessel):
    for lang in ("de", "en"):
        wort = t(f"versand.betreff.risiko.{schluessel}", lang)
        assert f"— {wort} D13" in build_email_subject(_zeile("evening", risiko), lang=lang)


def test_ac2_unbekannte_werte_unveraendert_in_en():
    s = build_email_subject(TokenLine(stage_name="E1", report_type="compare",  # type: ignore[arg-type]
                                      tokens=(), trip_name="GR20", main_risk="Fog"), lang="en")
    assert s == "[GR20] E1 — compare — Fog"


@pytest.mark.parametrize("etappe", [
    "Etappe 3: Refuge d'Ortu di u Piobbu",
    "Etappe 3: Refuge d'Ortu di u Piobbu bis Bocca",
    "Etappe 3: Refuge d'Ortu di u Piobbu nach Refuge de Carrozzu"])
def test_ac2_kuerzung_haelt_78_zeichen_in_en(etappe):
    s = build_email_subject(_zeile("morning", "Thunder", etappe), lang="en")
    assert len(s) <= 78 or not s.startswith("[GR20]"), s
    assert t("versand.betreff.bericht.morgen", "en") in s


def test_ac2_deutsch_mit_lang_de_gleich_ohne_lang():
    assert betreffe("de") == betreffe(None)
    assert fehlertexte("de") == fehlertexte(None)
    for lang_kw in ({}, {"lang": "de"}):
        assert build_email_subject(_zeile("morning", "Thunder"), **lang_kw) == (
            "[GR20] Etappe 3 — Morgen — Gewitter D13 W30 G55")


# ---------------------------------------------------------------- AC-5


def test_ac5_no_weather_englisch_status_und_code_stabil():
    status, body = error_body("no_weather", lang="en")
    assert (status, body) == (422, {"detail": _englisch("versand.ergebnis.no_weather"),
                                    "code": "no_weather"})
    assert error_body("no_weather") == (422, {"detail": t("versand.ergebnis.no_weather", "de"),
                                              "code": "no_weather"})


@pytest.mark.parametrize("code", list(SEND_OUTCOMES))
def test_ac5_jeder_code_englisch_mit_platzhaltern(code):
    werte = {"entity_id": "trip-42", "report_type": "morning", "reason": "R"}
    _status, body = error_body(code, lang="en", **werte)
    assert body["detail"] == _englisch(f"versand.ergebnis.{code}", **werte)
    assert "{" not in body["detail"]


def _router_antwort(user_id: str) -> dict:
    from api.routers.briefings_send import send_briefing

    antwort = send_briefing("gibt-es-nicht", "trip-1", user_id, "morning")
    assert antwort.status_code == 400
    return json.loads(antwort.body)


def test_ac5_router_antwortet_in_der_sprache_des_nutzers():
    nutzer_anlegen("router-de", "de")
    nutzer_anlegen("router-en", "en")
    assert _router_antwort("router-en") == {
        "detail": _englisch("versand.ergebnis.kind_required"), "code": "kind_required"}
    assert _router_antwort("router-de") == {
        "detail": t("versand.ergebnis.kind_required", "de"), "code": "kind_required"}


def test_ac5_router_trip_nicht_gefunden_englisch():
    from api.routers.briefings_send import send_briefing

    nutzer_anlegen("router-en", "en")
    antwort = send_briefing("route", "trip-fehlt", "router-en", "morning")
    assert json.loads(antwort.body) == {
        "detail": _englisch("versand.ergebnis.not_found", entity_id="trip-fehlt"),
        "code": "not_found"}


# ---------------------------------------------------------------- AC-6


def test_ac6_unbestaetigt_englischer_sperrtext_ohne_mail(rig):
    from services.channel_test_service import send_test_message

    nutzer_anlegen("offen-en", "en", bestaetigt=False)
    assert send_test_message("email", "offen-en") == {
        "error": _englisch("versand.test.mail_gesperrt")}
    assert rig.anzahl_versuche("email") == 0


@pytest.mark.parametrize("uid", ["", "default"])
def test_ac6_leer_oder_default_bleibt_gesperrt(rig, uid):
    from services.channel_test_service import send_test_message

    nutzer_anlegen("default", "en")  # selbst ein vollstaendiges default-Profil oeffnet nichts
    ergebnis = send_test_message("email", uid)
    assert ergebnis["error"] in (t("versand.test.mail_gesperrt", "de"),
                                 t("versand.test.mail_gesperrt", "en"))
    assert rig.anzahl_versuche("email") == 0


# ---------------------------------------------------------------- AC-7


def _sms_teil(paare) -> dict:
    return {k: v for k, v in paare if k.endswith("sms")}


def test_ac7_sms_in_en_byte_gleich_zu_de(rig):
    nutzer_anlegen("sms-de", "de")
    nutzer_anlegen("sms-en", "en")
    de = _sms_teil(ausfall_texte(rig, "sms-de") + alarm_sms_hinweis(rig, "sms-de"))
    en = _sms_teil(ausfall_texte(rig, "sms-en") + alarm_sms_hinweis(rig, "sms-en"))
    assert len(de) == 4 and de == en
    assert de["alarm.sms"].endswith("+ amtl. Warnung s. E-Mail/Telegram")


def test_ac7_ausfall_mail_und_telegram_englisch(rig):
    nutzer_anlegen("ausfall-en", "en")
    texte = dict(ausfall_texte(rig, "ausfall-en"))
    betreff = _englisch("versand.betreff.wetterdaten_fehlen", trip="GR20")
    hinweis = _englisch("versand.hinweis.wetterdienst_ausfall")
    assert (texte["ausfall.betreff"], texte["ausfall.mail"], texte["ausfall.header"]) == (
        betreff, hinweis, "en")
    assert texte["ausfall.telegram"] == f"[{betreff}]\n\n{hinweis}"


# ---------------------------------------------------------------- Ratsche


_DATEN = ("Etappe 3: Refuge d'Ortu di u Piobbu nach Refuge de Carrozzu",
          "Etappe 3: Refuge d'Ortu di u Piobbu", "Etappe 3", "keine Orte")


def _fragmente() -> set[str]:
    de = json.loads((KATALOG / "de" / "versand.json").read_text(encoding="utf-8"))
    en = json.loads((KATALOG / "en" / "versand.json").read_text(encoding="utf-8"))
    out: set[str] = set()
    for key, wert in de.items():
        for teil in re.split(r"\{[a-z_]+\}", wert):
            teil = teil.strip(" :—.[]()")
            if len(teil) >= 3 and teil not in en.get(key, ""):
                out.add(teil)
    return out


def treffer(text: str) -> list[str]:
    frags = _fragmente()
    bloecke = [b for b in text.split("----- ") if b and not b.split(" ", 1)[0].endswith("sms")]
    out = []
    for block in bloecke:
        for daten in _DATEN:
            block = block.replace(daten, "<daten>")
        if re.search(r"[äöüÄÖÜß]", block) or any(f in block for f in frags):
            out.append(block)
    return out


def test_ratsche_englische_ausgabe_ohne_deutsche_versandtexte(rig):
    assert len(_fragmente()) > 20
    assert treffer(alle_texte(rig, "en")) == []


def test_ratsche_gegenprobe_deutsch_findet_treffer(rig):
    assert len(treffer(alle_texte(rig, "de"))) > 20
