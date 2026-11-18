"""Befehlsantworten der Orte nennen den Bereich "Orte" (ADR-0124 Nr. 10).

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md, Teil B Nr. 16 (B5),
AC-35; ADR-0124 Nr. 10: "Vergleich", "Orts-Vergleich" und "Orts-Briefing"
entfallen als Name in Oberflaeche, Mail, Telegram und SMS. Antworten auf
Befehle sind Ausgaben an den Nutzer. Ein einzelnes Abo des Bereichs heisst
"Orte-Abo" (EN "locations subscription"), wie in der Spec (AC-1, AC-15, AC-35).

Echter Weg: ``TripCommandProcessor.process`` (Langform E-Mail/Telegram,
Kurzform Premium-SMS) und ``resolve_command_target`` (Zielauswahl), jeweils
mit dem echten Nutzerordner. Kein Mock. Der Name des Abos ist bewusst
neutral ("Münsterland"), damit Nutzerdaten keinen Treffer erzeugen.
"""
from __future__ import annotations

import json
import re
from datetime import date

import pytest
from freezegun import freeze_time

from tests.helpers.inbound_sprache_fixture import (
    FEST, JETZT, antwort, nutzer_anlegen, trip_anlegen, vergleich_anlegen,
)

ALT = re.compile(r"vergleich|comparison|orts-briefing", re.IGNORECASE)
NAME = "Münsterland"


def _ohne_alten_namen(texte: dict[str, str]) -> None:
    for fall, text in texte.items():
        treffer = ALT.findall(text)
        assert not treffer, f"{fall}: alter Bereichsname {treffer}: {text!r}"


def _orte_antworten(uid: str, lang: str | None, channel: str = "email") -> dict[str, str]:
    preset = vergleich_anlegen(uid, NAME)
    a = lambda body: antwort(uid, body, channel=channel, preset=preset)  # noqa: E731
    return {
        "hilfe": a("HILFE"), "status": a("STATUS"), "gewitter": a("GEWITTER"),
        "pause": a("PAUSE 2d"), "weiter": a("WEITER"),
        "weiter_nicht_pausiert": a("WEITER"), "report": a("REPORT"),
    }


@freeze_time(FEST)
@pytest.mark.parametrize("lang", ["de", "en"])
def test_orte_befehlsantworten_langform_ohne_alten_namen(lang):
    """Given ein Orte-Abo / When Befehle per E-Mail beantwortet werden /
    Then nennt keine Antwort den Bereich "Vergleich"/"comparison"; Pause und
    Fortsetzen nennen das Orte-Abo. Zwei Nutzer, jeder bekommt seine Antwort."""
    abo = {"de": "Orte-Abo", "en": "Locations subscription"}[lang]
    for nr in (1, 2):
        uid = f"orte-befehl-{lang}-{nr}"
        nutzer_anlegen(uid, lang)
        texte = _orte_antworten(uid, lang)
        _ohne_alten_namen(texte)
        assert f"{abo} '{NAME}'" in texte["pause"], texte["pause"]
        assert f"{abo} '{NAME}'" in texte["weiter"], texte["weiter"]
        assert f"{abo} '{NAME}'" in texte["weiter_nicht_pausiert"]


@freeze_time(FEST)
def test_orte_befehlsantworten_kurzform_ohne_alten_namen():
    """Kurzform (Premium-SMS, englisch fuer jede Kontosprache) ebenso."""
    uid = "orte-befehl-kurz"
    nutzer_anlegen(uid, "de")
    texte = _orte_antworten(uid, None, channel="premium_sms")
    _ohne_alten_namen(texte)
    assert "locations subscription" in texte["status"].lower(), texte["status"]


@pytest.mark.parametrize("lang", ["de", "en"])
def test_orte_zielauswahl_ohne_alten_namen(lang):
    """Zielauswahl ohne Ziel, nur Orte-Abo bei Trip-Befehl, Mehrdeutigkeit."""
    from app.loader import load_all_trips
    from services.trip_selection import resolve_command_target

    uid = f"orte-ziel-{lang}"
    nutzer_anlegen(uid, lang)
    trip_anlegen(uid)
    eins, zwei = vergleich_anlegen(uid, NAME), vergleich_anlegen(uid, "Emsland", nr=2)
    trips = load_all_trips(uid)
    texte = {}
    for kanal in ("telegram", "email", "premium_sms"):
        texte[f"kein_kandidat_{kanal}"] = resolve_command_target(
            "status", [], [], JETZT, channel=kanal, lang=lang).text
        texte[f"kein_aktives_{kanal}"] = resolve_command_target(
            "status", [], [eins], JETZT, channel=kanal, lang=lang).text
        texte[f"mehrdeutig_{kanal}"] = resolve_command_target(
            "pause", trips, [eins, zwei], JETZT, channel=kanal, lang=lang).text
    _ohne_alten_namen(texte)
    marke = {"de": "(Orte)", "en": "(locations)"}[lang]
    assert marke in texte["mehrdeutig_telegram"], texte["mehrdeutig_telegram"]


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("en_kurz", [False, True])
@pytest.mark.parametrize("ergebnis", ["no_weather", "no_channels", "channels_unreachable",
                                      "already_in_progress", "invalid_preset", "no_stage"])
def test_orte_versand_fehlerantwort_ohne_alten_namen(lang, en_kurz, ergebnis):
    """Fehlerantwort eines Versands auf Befehl (echte Funktion), Orte-Abo."""
    from services.trip_command_processor import _on_demand_failure_body

    text = _on_demand_failure_body(ergebnis, "Heute", date(2026, 10, 29), en=en_kurz,
                                   objekt="vergleich", lang=lang)
    assert not ALT.findall(text), text
    if ergebnis == "no_channels" and lang == "de" and not en_kurz:
        assert text.startswith("Keine Versandkanäle für dieses Orte-Abo aktiv"), text


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("ergebnis", ["no_channels", "channels_unreachable"])
def test_trip_versand_fehlerantwort_unveraendert(lang, ergebnis):
    """Gegenprobe: Trip-Antworten bleiben byte-gleich zum Stand vor B5."""
    from services.trip_command_processor import _on_demand_failure_body

    text = _on_demand_failure_body(ergebnis, "Heute", date(2026, 10, 29), lang=lang)
    soll = {
        ("de", "no_channels"): "Keine Versandkanäle für diesen Trip aktiv — Briefing nicht "
                               "gesendet. Kanäle im Trip-Editor aktivieren.",
        ("de", "channels_unreachable"): "Versandweg für diesen Trip konfiguriert, aber nicht "
                                        "erreichbar — Briefing nicht gesendet. Verbindung prüfen.",
        ("en", "no_channels"): "No delivery channels enabled for this trip — briefing not sent. "
                               "Turn channels on in the trip editor.",
        ("en", "channels_unreachable"): "Delivery channel for this trip configured but not "
                                        "reachable — briefing not sent. Check the connection.",
    }
    assert text == soll[(lang, ergebnis)]


def test_orte_vorschau_fehlertexte_ohne_alten_namen():
    """Fehler der Orte-Vorschau (echter ``ComparePreviewService``): unbekanntes
    Abo, Abo ohne Orte, Abo mit geloeschten Orten. Die API zeigt den Text in der
    Kontosprache aus ``code``/``params`` (DE = Ausnahmetext, EN ueber denselben
    Code)."""
    from app.loader import get_briefings_dir
    from i18n import t
    from services.compare_preview_service import ComparePreviewService

    uid = "orte-vorschau-fehler"
    nutzer_anlegen(uid, "de")
    leer = {**vergleich_anlegen(uid, NAME), "location_ids": []}
    (get_briefings_dir(uid) / f"{leer['id']}.json").write_text(
        json.dumps(leer), encoding="utf-8")
    weg = vergleich_anlegen(uid, "Emsland", nr=2)  # loc-a..c gibt es nicht
    svc = ComparePreviewService()
    texte = {}
    for fall, pid in (("unbekannt", "gibt-es-nicht"), ("ohne_orte", leer["id"]),
                      ("orte_geloescht", weg["id"])):
        with pytest.raises((LookupError, ValueError)) as exc:
            svc.render_all_channels(pid, user_id=uid)
        assert exc.value.code.startswith("vergleich_"), exc.value
        texte[f"{fall}_de"] = str(exc.value)
        texte[f"{fall}_en"] = t(f"api.fehler.{exc.value.code}", "en", **exc.value.params)
    _ohne_alten_namen(texte)
    assert texte["unbekannt_de"].startswith("Orte-Abo 'gibt-es-nicht'"), texte
    assert texte["unbekannt_en"].startswith("Locations subscription 'gibt-es-nicht'"), texte
