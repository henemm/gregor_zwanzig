"""``lang`` reist vom ``NotificationService`` zu jedem Langform-Renderer (Issue #2671).

SPEC: docs/specs/modules/i18n_p9a_versand_schicht_2671.md (Kanaele, Mandantentrennung)

Ein ``en``-Nutzer und ein ``de``-Nutzer senden ueber den ECHTEN Versandweg
(``KanalRig`` am Drahtende): Briefing voll und kompakt, Telegram-Sprechblasen
samt Unvollstaendig-Hinweis, amtliche Warnung (Trip und Ortsvergleich),
Abweichungs-Alarm mit eingebettetem amtlichem Block, Ortsvergleich-Briefing.
Geprueft wird die Ausgabe am Draht: die ``en``-Fassung traegt keinen deutschen
Katalogtext (Umlaut oder deutsches Bruchstueck eines Katalogwerts, das in der
englischen Fassung desselben Schluessels fehlt), die ``de``-Fassung sehr wohl
(Gegenprobe), und jede Mail traegt ``X-GZ-Lang`` ihres Nutzers. Faellt irgendwo
die Weitergabe weg, steht Deutsch in der englischen Ausgabe.

SMS, Premium-SMS und Telegram-Kurzstil bleiben ausgenommen: sie sind in jeder
Sprache byte-gleich (PO-Korrektur 2026-10-31) -- belegt in
``tests/test_versand_zweisprachig.py`` (AC-7) und hier fuer die amtliche Warnung.
"""
from __future__ import annotations

import email
import html as _html
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.notification_service import NotificationService
from tests.helpers.versand_fixture import TZ, anfrage, nutzer_anlegen, rig_starten

KATALOG = Path(__file__).resolve().parents[1] / "src" / "i18n" / "messages"
# Daten des Aufrufers / Eigennamen (keine Renderertexte).
_DATEN = ("Etappe 3", "GR20", "Hyeres", "Toulon", "Cote", "Orages", "Calenzana", "Ortu")
# Fremdes Paket: Antwort-Kommando-Block im Briefing (Inbound, P10 #2673).
_FREMDE_ZEILEN = ("Wetter der heutigen Etappe", "Wetter der morgigen Etappe",
                  "Nowcast Regen/Gewitter", "Gewittergefahr heutige Etappe",
                  "Regen-Ereignisfl", "Etappen um N Tage", "Briefings für Dauer",
                  "Nächstes Briefing", "Kürzel-Bedeutungen", "Briefing jetzt senden")
_BEFEHLE = {"HEUTE", "MORGEN", "JETZT", "GEWITTER", "STRECKE", "RUHETAG", "PAUSE", "SKIP",
            "KUERZEL", "REPORT"}  # Befehlswoerter (P10), z. B. als Telegram-Knopf


@pytest.fixture
def rig(monkeypatch):
    r = rig_starten(monkeypatch)
    yield r
    r.stoppen()


def _fragmente() -> set[str]:
    """Deutsche Katalog-Bruchstuecke, die in KEINEM englischen Wert vorkommen."""
    de: dict[str, str] = {}
    en_alle = ""
    for pfad in sorted((KATALOG / "de").glob("*.json")):
        de.update(json.loads(pfad.read_text(encoding="utf-8")))
        en_alle += "\n".join(json.loads((KATALOG / "en" / pfad.name).read_text(encoding="utf-8")).values())
    out: set[str] = set()
    for wert in de.values():
        for teil in re.split(r"\{[a-z_]+\}", wert):
            teil = teil.strip(" :—–·.,;!?()[]+-/|%°⚠️")
            if len(teil) >= 4 and teil not in en_alle:
                out.add(teil)
    return out


_FRAGMENTE = _fragmente()


def deutsch(text: str) -> list[str]:
    for d in _DATEN:
        text = text.replace(d, "<daten>")
    zeilen = [z for z in text.splitlines()
              if z.strip() and not any(f in z for f in _FREMDE_ZEILEN)
              and z.split()[0] not in _BEFEHLE]
    return [z for z in zeilen if re.search(r"[äöüÄÖÜß]|\bOrt\b", z)
            or any(re.search(rf"(?<![A-Za-z]){re.escape(f)}(?![a-z])", z) for f in _FRAGMENTE)]


def _sichtbar(roh: str) -> tuple[str, str, str]:
    msg = email.message_from_string(roh)
    texte = []
    for teil in msg.walk():
        if teil.get_content_maintype() == "text":
            t = teil.get_payload(decode=True).decode(teil.get_content_charset() or "utf-8")
            if teil.get_content_subtype() == "html":
                t = re.sub(r"<head>.*?</head>|<style.*?</style>", "", t, flags=re.S)
                t = _html.unescape(re.sub(r"<[^>]+>", "\n", t))
            texte.append(t)
    betreff = str(email.header.make_header(email.header.decode_header(msg["Subject"])))
    return betreff, "\n".join(texte), msg["X-GZ-Lang"]


def _mails(rig) -> list[tuple[str, str, str]]:
    return [_sichtbar(e["roh"]) for e in rig.angenommen["email"]]


def _telegramme(rig) -> str:
    return "\n".join(_html.unescape(re.sub(r"<[^>]+>", "", p.get("text", "")))
                     for p in rig.angenommen["telegram"])


def _warnung(level: int = 2, source: str = "meteo_forets"):
    """Quelle mit sprachabhaengigem Anzeigenamen (``Météo-France (Waldbrand)``)."""
    from services.official_alerts.models import OfficialAlert

    return OfficialAlert(source=source, hazard="thunderstorm", level=level, label="Orages")


def _entwarnungen(*ziele: list[str]) -> list:
    """Je Ziel eine Entwarnung 3 -> 1 (Quelle mit sprachabhaengigem Namen)."""
    return [SimpleNamespace(kind="lowered", alert=_warnung(1, "massif_closure"), scope_ids=z,
                            old_rank=3, new_rank=1, old_level=3, new_level=1) for z in ziele]


# ------------------------------------------------------------ Versandfaelle


def _briefing_voll(rig, dienst, uid, lang):
    rig.telegram_fehler_bei = {2}  # eine Sprechblase scheitert -> Unvollstaendig-Hinweis
    dienst.send_trip_report(anfrage(uid, on_demand_prefix=True))


def _briefing_kompakt(rig, dienst, uid, lang):
    from app.models import TripReportConfig

    dienst.send_trip_report(anfrage(uid, send_telegram=False, report_config=TripReportConfig(
        trip_id=f"trip-{uid}", email_format="compact")))


def _amtlich_trip(rig, dienst, uid, lang):
    from tests.helpers.versand_fixture import trip

    dienst.send_official_alert(trip(uid), [(_warnung(), ["1", "Ziel"])], {"email", "telegram"},
                               allclears=_entwarnungen(["Ziel"]))


def _entwarnung_trip(rig, dienst, uid, lang):
    from tests.helpers.versand_fixture import trip

    dienst.send_official_alert(trip(uid), [], {"email", "telegram"},
                               allclears=_entwarnungen(["1"], []))


def _amtlich_vergleich(rig, dienst, uid, lang):
    ort = SimpleNamespace(id="loc-1", name="Hyeres", lat=43.12, lon=6.13, timezone="Europe/Paris")
    dienst.send_multi_location_official_alert(
        "Cote", [ort], [(_warnung(3), ["loc-1"])], {"email", "telegram"})  # nur Warnung


def _entwarnung_vergleich(rig, dienst, uid, lang):
    orte = [SimpleNamespace(id=f"loc-{i}", name=n, lat=43.12, lon=6.13, timezone="Europe/Paris")
            for i, n in ((1, "Hyeres"), (2, "Toulon"))]
    dienst.send_multi_location_official_alert(
        "Cote", orte, [], {"email", "telegram"}, allclears=_entwarnungen(["loc-1"], ["loc-2"]))


def _entwarnung_vergleich_ohne_ort(rig, dienst, uid, lang):
    ort = SimpleNamespace(id="loc-1", name="Hyeres", lat=43.12, lon=6.13, timezone="Europe/Paris")
    dienst.send_multi_location_official_alert(
        "Cote", [ort], [(_warnung(3), ["loc-1"])], {"email"}, allclears=_entwarnungen([]))


def _abweichung(rig, dienst, uid, lang):
    from tests.helpers.alarm_fixture import nachricht

    dienst._dispatch_alert_message(
        alert_msg=nachricht("abweichung_wind", lang),  # Referenzzeit kommt vom Aufrufer (P9b)
        effective_channels={"email", "telegram"},
        official_notices=[(_warnung(), ["3", "Ziel"])], alert_tz=TZ)


def _abweichung_vergleich(rig, dienst, uid, lang):
    """Ortsvergleich-Abweichung: eine Telegram-Sprechblase je Ort."""
    from datetime import datetime, timezone

    from app.models import ChangeSeverity, SegmentWeatherSummary, WeatherChange
    from services.point_weather import PointWeatherData

    zeit = datetime(2026, 10, 29, 13, 0, tzinfo=timezone.utc)
    entities = []
    for name in ("Hyeres", "Toulon"):
        punkt = PointWeatherData(id=name.lower(), name=name, lat=43.12, lon=6.13, timeseries=None,
                                 aggregated=SegmentWeatherSummary(), fetched_at=zeit,
                                 provider="openmeteo")
        wechsel = WeatherChange(metric="gust_max_kmh", old_value=40.0, new_value=75.0, delta=35.0,
                                threshold=20.0, severity=ChangeSeverity.MAJOR,
                                direction="increase", occurred_at=zeit)
        entities.append((name, [punkt], [wechsel]))
    dienst.send_multi_location_deviation_alert(entities, {"email", "telegram"})


def _vergleich_briefing(rig, dienst, uid, lang):
    dienst.send_compare_report(
        subject="Cote", html_body="<html><body>Cote</body></html>", text_body="Cote",
        telegram_text="Cote", sms_text="Cote", recipients=["gregor-test@henemm.com"],
        effective_channels={"email"})


FAELLE = {
    "briefing_voll": _briefing_voll, "briefing_kompakt": _briefing_kompakt,
    "amtlich_trip": _amtlich_trip, "amtlich_vergleich": _amtlich_vergleich,
    "entwarnung_trip": _entwarnung_trip, "entwarnung_vergleich": _entwarnung_vergleich,
    "entwarnung_vergleich_ohne_ort": _entwarnung_vergleich_ohne_ort,
    "abweichung": _abweichung, "abweichung_vergleich": _abweichung_vergleich,
}


def _lauf(rig, fall: str, lang: str) -> tuple[list, str]:
    uid = f"durch-{lang}"
    nutzer_anlegen(uid, lang)
    rig.zaehler_leeren()
    rig.telegram_fehler_bei = None
    FAELLE[fall](rig, NotificationService(rig.settings(), uid), uid, lang)
    return _mails(rig), _telegramme(rig)


@pytest.mark.parametrize("fall", list(FAELLE))
def test_englische_ausgabe_ohne_deutsch_und_mit_kopf(rig, fall):
    mails, telegramme = _lauf(rig, fall, "en")
    assert mails, fall
    assert [m[2] for m in mails] == ["en"] * len(mails)
    reste = [z for b, text, _ in mails for z in deutsch(f"{b}\n{text}")] + deutsch(telegramme)
    assert reste == [], (fall, reste)


@pytest.mark.parametrize("fall", list(FAELLE))
def test_gegenprobe_deutsche_ausgabe_findet_deutsch(rig, fall):
    mails, telegramme = _lauf(rig, fall, "de")
    assert [m[2] for m in mails] == ["de"] * len(mails)
    assert deutsch("\n".join(f"{b}\n{t}" for b, t, _ in mails)), fall
    if rig.angenommen["telegram"]:
        assert deutsch(telegramme), fall


def test_amtliche_warnung_sms_und_kurzstil_in_en_wie_de(rig):
    from tests.helpers.versand_fixture import trip

    texte = {}
    for lang in ("de", "en"):
        uid = f"kurz-{lang}"
        nutzer_anlegen(uid, lang)
        rig.zaehler_leeren()
        NotificationService(rig.settings(), uid).send_official_alert(
            trip(uid), [(_warnung(), ["1"])], {"sms", "premium_sms", "telegram"},
            telegram_style="kurzform")
        texte[lang] = ([d["text"] for d in rig.angenommen["sms"] + rig.angenommen["premium_sms"]],
                       [p["text"] for p in rig.angenommen["telegram"]])
    assert len(texte["de"][0]) == 2 and len(texte["de"][1]) == 1
    assert texte["en"] == texte["de"]


def test_briefing_sms_premium_und_kurzstil_in_en_wie_de(rig):
    """Briefing-Kurzform (SMS, Premium-SMS, Telegram-Kurzstil) sprachunabhaengig."""
    from app.models import TripReportConfig

    texte = {}
    for lang in ("de", "en"):
        uid = f"kurzb-{lang}"
        nutzer_anlegen(uid, lang)
        rig.zaehler_leeren()
        NotificationService(rig.settings(), uid).send_trip_report(anfrage(
            uid, send_email=False, send_sms=True, send_premium_sms=True,
            report_config=TripReportConfig(trip_id=f"trip-{uid}", telegram_style="kurzform")))
        texte[lang] = ([d["text"] for d in rig.angenommen["sms"] + rig.angenommen["premium_sms"]],
                       [p["text"] for p in rig.angenommen["telegram"]])
    assert len(texte["de"][0]) == 2 and len(texte["de"][1]) == 1
    assert texte["en"] == texte["de"]


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ortsvergleich_briefing_kopf_ist_sprache_des_inhalts(rig, lang):
    """Bis P9b (#2672) rendert scheduler_dispatch_service den Ortsvergleich deutsch:
    der Kopf sagt deshalb fuer jeden Nutzer ``de`` (kein Fehlalarm, keine Mischmail)."""
    uid = f"vgl-{lang}"
    nutzer_anlegen(uid, lang)
    rig.zaehler_leeren()
    _vergleich_briefing(rig, NotificationService(rig.settings(), uid), uid, lang)
    assert [m[2] for m in _mails(rig)] == ["de"]


def test_servicefehler_mail_betreff_und_kopf_wie_rumpf_deutsch(rig):
    """Rumpf der Service-Fehler-Mail ist noch deutsch: Betreff + Kopf ebenso."""
    from tests.helpers.versand_fixture import service_fehler_betreff

    nutzer_anlegen("svc-en", "en")
    werte = dict(service_fehler_betreff(rig, "svc-en"))
    assert werte == {"servicefehler.betreff": "[GR20] Wetterdaten nicht verfuegbar",
                     "servicefehler.header": "de"}
    _betreff, text, _ = _mails(rig)[-1]
    assert "Wetterdaten konnten nicht abgerufen werden" in text
