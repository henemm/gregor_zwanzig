"""Zwei Nutzer, zwei Sprachen, ein Prozess (Issue #2671, AC-4).

SPEC: docs/specs/modules/i18n_p9a_versand_schicht_2671.md

``golden-de`` (``language: de``) und ``golden-en`` (``language: en``) senden im
selben Lauf, je mit eigenem ``NotificationService``, ein Briefing, eine
Ausfall-Meldung und einen amtlichen Ortsvergleich-Alarm. Reihenfolge
``de, en, de`` -- die Sprache haengt am Dienstobjekt, nicht an Modul- oder
Klassenzustand. Gemessen am Draht (``KanalRig``: Betreff, Hinweis, Kopf
``X-GZ-Lang``); die Sprache steht nur in den echten ``user.json``-Dateien,
kein Spiegel-Mock. Ausserdem: ``lang=`` am Konstruktor hat Vorrang (P9b).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from i18n import t
from services.notification_service import NotificationService
from tests.helpers.versand_fixture import anfrage, letzte_mail, nutzer_anlegen, rig_starten, trip


@pytest.fixture
def rig(monkeypatch):
    r = rig_starten(monkeypatch)
    yield r
    r.stoppen()


def _briefing(rig, dienst, uid) -> dict:
    rig.zaehler_leeren()
    dienst.send_trip_report(anfrage(uid, test_prefix=True))
    m = letzte_mail(rig)
    return {"betreff": m["betreff"], "hinweis": m["plain"].split("\n\n", 1)[0], "lang": m["lang"]}


def _ausfall(rig, dienst, uid) -> dict:
    rig.zaehler_leeren()
    dienst.send_no_data_hint(trip(uid), "morning")
    m = letzte_mail(rig)
    return {"betreff": m["betreff"], "hinweis": m["plain"], "lang": m["lang"]}


def _vergleich(rig, dienst) -> dict:
    from services.official_alerts.models import OfficialAlert

    rig.zaehler_leeren()
    ort = SimpleNamespace(id="loc-1", name="Hyeres", lat=43.12, lon=6.13, timezone="Europe/Paris")
    warnung = OfficialAlert(source="geosphere_warn", hazard="wind_gust", level=3, label="Sturm")
    dienst.send_multi_location_official_alert(
        "Cote", [ort], [(warnung, ["loc-1"])], {"email"})
    eintrag = rig.angenommen["email"][-1]["roh"]
    m = letzte_mail(rig)
    return {"lang": m["lang"], "roh": eintrag}


def _erwartung(lang: str) -> dict:
    datum = {"de": "29.10.2026", "en": "29 Oct 2026"}[lang]
    morgen = t("versand.betreff.bericht.morgen", lang)
    return {
        "briefing": {
            "betreff": f"[TEST] [GR20] Etappe 3 — {morgen}",
            "hinweis": t("versand.hinweis.test_vorschau", lang, etappe="Etappe 3", datum=datum),
            "lang": lang,
        },
        "ausfall": {
            "betreff": t("versand.betreff.wetterdaten_fehlen", lang, trip="GR20"),
            "hinweis": t("versand.hinweis.wetterdienst_ausfall", lang), "lang": lang,
        },
    }


def test_ac4_zwei_nutzer_je_eigene_sprache_reihenfolge_egal(rig):
    nutzer_anlegen("golden-de", "de")
    nutzer_anlegen("golden-en", "en")
    dienste = {lang: NotificationService(rig.settings(), f"golden-{lang}") for lang in ("de", "en")}
    assert t("versand.betreff.bericht.morgen", "en") != t("versand.betreff.bericht.morgen", "de")

    for lang in ("de", "en", "de"):
        uid, dienst = f"golden-{lang}", dienste[lang]
        soll = _erwartung(lang)
        assert _briefing(rig, dienst, uid) == soll["briefing"], lang
        assert _ausfall(rig, dienst, uid) == soll["ausfall"], lang
        v = _vergleich(rig, dienst)
        assert v["lang"] == lang
        anderer = "en" if lang == "de" else "de"
        kontext = t("versand.kontext.ortsvergleich", lang)
        assert kontext in _klartext(v["roh"]), lang
        assert t("versand.kontext.ortsvergleich", anderer) not in _klartext(v["roh"]), lang


def _klartext(roh: str) -> str:
    import email

    msg = email.message_from_string(roh)
    teile = [p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8")
             for p in msg.walk() if p.get_content_maintype() == "text"]
    return "\n".join(teile)


def test_ac4_lang_am_konstruktor_hat_vorrang(rig):
    nutzer_anlegen("golden-de", "de")
    dienst = NotificationService(rig.settings(), "golden-de", lang="en")
    assert _ausfall(rig, dienst, "golden-de")["lang"] == "en"

