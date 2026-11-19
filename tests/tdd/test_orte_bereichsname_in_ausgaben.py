"""#3122 Scheibe B5: der Bereich heisst "Orte", Ein-Ort-Texte (AC-35, AC-36).

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md, Teil B Nr. 16, AC-35, AC-36;
ADR-0124 Nr. 10 und Nachtrag Nr. 1 und 13.

Echter Weg: rohes Preset-JSON im Nutzerordner -> ``load_compare_presets`` ->
``send_one_compare_preset`` -> ``NotificationService`` -> Transport-Mitschrift
(``tests/helpers/transport_mitschrift.py``). Einzige Naehte: Wetter
(``ComparisonEngine.run``, echte Subklasse) und Transport. Die Erwartungen
stehen von Hand im Test (Wortlaut der Spec-Tabelle), nie aus ``t()``.

Die "keine Daten"-Faelle laufen ueber den echten SMS-Renderer: der Versand
schickt bei lauter Fehlerorten bewusst nichts (``no_weather``), die SMS-Form
erscheint nur in Vorschau und Renderer.

#3172 (PO-Entscheidungen 2026-11-19, ADR-0125-Nachtrag): die Orte-SMS (und mit
ihr Premium-SMS und Telegram-Kurzstil) hat keinen Kopf, kein Datum und nennt
keine Ortsnamen -- die Orte heissen ``O1``, ``O2``, ...; der Bereichsname
"Orte" steht damit nur noch in Mail und Telegram (Normalstil), die hier
unveraendert geprueft werden.
"""
from __future__ import annotations

import copy
import html as html_mod
import json
import re
from datetime import datetime

import pytest

from tests.helpers.orte_sms import orte_nummern

from app.loader import get_data_dir, save_location
from app.user import SavedLocation
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._compare_kette_fixtures import (
    TARGET_DATE, _dp, briefing_senden, fixture_dict, nutzer_anlegen,
    preset_ablegen, settings_fuer, transport_einrichten,
)

#: Orts-Kennung -> (Name, lat, lon, Tageshoechstwert). Werte je Ort verschieden.
ORTE = {
    "loc-ibk": ("Innsbruck", 47.27, 11.39, 22.0),
    "loc-bz": ("Bozen", 46.50, 11.35, 27.0),
    "loc-lz": ("Lienz", 46.83, 12.77, 19.0),
    "loc-tb": ("Tecklenburg", 52.22, 7.81, 11.0),
}
DREI = ("loc-ibk", "loc-bz", "loc-lz")
EINER = ("loc-tb",)
#: Orte, deren Wetterabruf scheitert (je Test gesetzt).
FEHLER: dict = {"orte": set()}

#: Verbotene Bereichsnamen (ADR-0124 Nr. 10), in jeder Sprache.
VERBOTEN_DE = re.compile(r"vergleich|orts-briefing", re.IGNORECASE)
VERBOTEN_EN = re.compile(r"vergleich|orts-briefing|comparison", re.IGNORECASE)


def _ergebnis(locations, kwargs):
    from app.user import ComparisonResult, LocationResult

    res = []
    for i, loc in enumerate(list(locations)):
        tmax = ORTE[loc.id][3]
        werte = {"precip_1h": 1.0 + i, "pop": 10 + 10 * i}
        if loc.id in FEHLER["orte"]:
            res.append(LocationResult(location=loc, error="Wetterabruf fehlgeschlagen"))
            continue
        res.append(LocationResult(
            location=loc, score=80, temp_max=tmax, temp_min=tmax - 9, wind_max=11.0 + i,
            gust_max=19.0 + i, cloud_avg=35, sunny_hours=6, official_alerts=[],
            hourly_data=[_dp(9, werte), _dp(12, werte), _dp(15, werte)],
        ))
    return ComparisonResult(locations=res, time_window=kwargs.get("time_window", (9, 16)),
                            target_date=kwargs.get("target_date", TARGET_DATE),
                            created_at=datetime(2026, 7, 8, 4, 0))


@pytest.fixture
def mit(monkeypatch):
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod

    original = ce_mod.ComparisonEngine

    class Engine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations") or (args[0] if args else [])
            return _ergebnis(locations, kwargs)

    transport_einrichten(monkeypatch)
    monkeypatch.setattr(ce_mod, "ComparisonEngine", Engine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)
    FEHLER["orte"] = set()
    return aufzeichner_installieren(monkeypatch)


def _preset(orte: tuple[str, ...]) -> dict:
    p = fixture_dict("basis")
    p["location_ids"] = list(orte)
    p["display_config"]["hourly_metrics"] = ["temperature", "wind"]
    p["send_telegram"] = p["send_sms"] = p["send_premium_sms"] = True
    p["alert_channels"] = {"email": True, "telegram": False, "sms": False, "premium_sms": False}
    return p


def _sichtbar(html: str) -> str:
    """Was der Leser der HTML-Mail sieht: ohne Stil-Block, Kommentare, Tags."""
    ohne = re.sub(r"<style.*?</style>|<!--.*?-->", " ", html, flags=re.S)
    text = html_mod.unescape(re.sub(r"<[^>]+>", " ", ohne))
    return re.sub(r"\s+", " ", text)


def _senden(mit, orte: tuple[str, ...], lang: str) -> dict:
    """Ein frischer Nutzer, ein Briefing ueber den echten Weg; alle Kanaltexte."""
    uid = nutzer_anlegen("premium")
    pf = get_data_dir(uid) / "user.json"
    u = json.loads(pf.read_text())
    u["language"] = lang
    pf.write_text(json.dumps(u))
    # Alle Orte des Nutzers anlegen (die Kette verlangt Innsbruck und Bozen);
    # ins Briefing kommen nur die Orte des Abos.
    for lid, (name, lat, lon, _t) in ORTE.items():
        save_location(SavedLocation(id=lid, name=name, lat=lat, lon=lon, elevation_m=1000),
                      user_id=uid)
    p = _preset(orte)
    preset_ablegen(uid, copy.deepcopy(p))
    mit.leeren()
    briefing_senden(uid, p["id"], settings_fuer(uid))
    for k in ("email", "telegram", "sms", "premium_sms"):
        assert mit.sendungen(k), f"Vorbedingung: keine {k}-Sendung fuer {uid}"
    assert mit.empfaenger("telegram") == [f"chat-{uid}"], "Sendung ging nicht an diesen Nutzer"
    mail = mit.sendungen("email")[-1]
    aus = {
        "uid": uid, "betreff": mail["subject"], "html": _sichtbar(mail["body"]),
        "roh_html": mail["body"],
        "klartext": mail["plain_text_body"],
        "telegram": html_mod.unescape(re.sub(r"<[^>]+>", "", mit.sendungen("telegram")[-1]["body"])),
        "sms": mit.sendungen("sms")[-1]["body"],
        "premium_sms": mit.sendungen("premium_sms")[-1]["body"],
    }
    mit.leeren()
    return aus


def _keine_bereichsnamen(texte: dict, lang: str) -> None:
    muster = VERBOTEN_EN if lang == "en" else VERBOTEN_DE
    for kanal in ("betreff", "html", "klartext", "telegram", "sms", "premium_sms"):
        treffer = muster.findall(texte[kanal])
        assert not treffer, f"{kanal} ({lang}) nennt den Bereich noch {treffer}: {texte[kanal][:400]!r}"


# ---------------------------------------------------------------------------
# AC-35: drei Orte, Deutsch und Englisch
# ---------------------------------------------------------------------------

KOPF = {"de": "ORTE", "en": "LOCATIONS"}
BETREFF = {"de": "Orte: Kette Basis (", "en": "Locations: Kette Basis ("}
KNOPF = {"de": "In der App öffnen →", "en": "Open in app →"}
MARKE = {"de": "GREGOR ZWANZIG · Orte", "en": "GREGOR ZWANZIG · Locations"}
FUSS_DREI = {"de": "3 Orte · Vorlage", "en": "3 locations · Template"}
UEBERSICHT_DREI = {"de": "Alle Orte · gewählte Metriken", "en": "All locations · selected metrics"}
STUNDEN_DREI = {"de": "Stundenverlauf · alle Orte", "en": "Hourly view · all locations"}


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac35_drei_orte_heissen_orte_in_allen_kanaelen(mit, lang):
    """Given ein Orte-Abo mit drei Orten / When Mail, Telegram, SMS und
    Premium-SMS zugestellt werden / Then Kopf ORTE bzw. LOCATIONS, SMS beginnt
    mit "Orte TT.MM.:" (sprachfest) und kein Text nennt "Vergleich",
    "Orts-Vergleich", "Ortsvergleich", "Orts-Briefing" (EN: "comparison").
    Zwei Nutzer, jeder bekommt seine eigene Sendung."""
    uids = []
    for _ in range(2):
        tx = _senden(mit, DREI, lang)
        uids.append(tx["uid"])
        assert tx["betreff"].startswith(BETREFF[lang]), tx["betreff"]
        assert f"{KOPF[lang]} · " in tx["html"], tx["html"][:400]
        assert MARKE[lang] in tx["html"], "Marke im Fuss nennt den Bereich nicht 'Orte'"
        assert KNOPF[lang] in tx["html"]
        assert FUSS_DREI[lang] in tx["html"]
        assert UEBERSICHT_DREI[lang] in tx["html"] and STUNDEN_DREI[lang] in tx["html"]
        assert tx["klartext"].splitlines()[0] == KOPF[lang], tx["klartext"][:200]
        assert tx["telegram"].splitlines()[0] == f"{KOPF[lang]} — Kette Basis", tx["telegram"][:200]
        for kanal in ("sms", "premium_sms"):
            # #3172: drei Orte als O1 O2 O3, ohne Kopf und ohne Namen.
            assert orte_nummern(tx[kanal]) == [1, 2, 3], tx[kanal]
            for name in ("Innsbruck", "Bozen", "Lienz"):
                assert name not in tx[kanal], f"{kanal}: Ortsname {name}: {tx[kanal]}"
        _keine_bereichsnamen(tx, lang)
    assert uids[0] != uids[1]


# ---------------------------------------------------------------------------
# AC-36: genau ein Ort
# ---------------------------------------------------------------------------

FUSS_EINER = {"de": "1 Ort · Vorlage", "en": "1 location · Template"}
UEBERSICHT_EINER = {"de": "Gewählte Metriken", "en": "Selected metrics"}
STUNDEN_EINER = {"de": "Stundenverlauf", "en": "Hourly view"}
SPALTE_METRIK = {"de": "Metrik", "en": "Metric"}
MEHRZAHL = {
    "de": re.compile(r"alle Orte|1 Orte\b", re.IGNORECASE),
    "en": re.compile(r"all locations|1 locations\b", re.IGNORECASE),
}


def _uebersicht_zeilen(roh_html: str, lang: str) -> list[list[str]]:
    """Zeilen der Tabelle "Uebersicht" (Kopfzelle "Metrik"/"Metric")."""
    for tabelle in re.findall(r"<table[^>]*>(.*?)</table>", roh_html, re.S):
        zeilen = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tabelle, re.S):
            zellen = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)
            zeilen.append([html_mod.unescape(re.sub(r"<[^>]+>", "", z)).strip() for z in zellen])
        if zeilen and zeilen[0] and zeilen[0][0] == SPALTE_METRIK[lang]:
            return zeilen
    return []


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac36_ein_ort_uebersicht_und_texte_ohne_mehrzahl(mit, lang):
    """Given ein Orte-Abo mit genau einem Ort / When Mail, Telegram und SMS
    zugestellt werden / Then traegt die Mail die Tabelle "Uebersicht" mit den
    Tageswerten des Orts, kein Text sagt "alle Orte" oder "1 Orte", der Fuss
    sagt "1 Ort", die SMS beginnt mit Ortsname und Datum (Name nicht doppelt)."""
    uids = []
    for _ in range(2):
        tx = _senden(mit, EINER, lang)
        uids.append(tx["uid"])
        zeilen = _uebersicht_zeilen(tx["roh_html"], lang)
        assert zeilen, f"Tabelle 'Übersicht' fehlt bei einem Ort ({lang})"
        assert re.sub(r"^#\d+\s*", "", zeilen[0][1]) == "Tecklenburg" and len(zeilen[0]) == 2, zeilen[0]
        werte = " ".join(z[1] for z in zeilen[1:] if len(z) > 1)
        assert "11" in werte, f"Tageswert 11 °C des Orts fehlt in der Übersicht: {zeilen}"
        assert FUSS_EINER[lang] in tx["html"], tx["html"][-800:]
        assert UEBERSICHT_EINER[lang] in tx["html"]
        assert f"{STUNDEN_EINER[lang]} · " not in tx["html"]
        assert STUNDEN_EINER[lang] in tx["html"]
        for kanal in ("betreff", "html", "klartext", "telegram", "sms", "premium_sms"):
            treffer = MEHRZAHL[lang].findall(tx[kanal])
            assert not treffer, f"{kanal} ({lang}) setzt mehrere Orte voraus: {treffer}"
        assert tx["telegram"].splitlines()[0] == f"{KOPF[lang]} — Kette Basis"
        for kanal in ("sms", "premium_sms"):
            # #3172: Token-Zeile der Trip-SMS, ``O1`` ohne Kopf und Namen.
            assert tx[kanal].startswith("O1 D11"), tx[kanal]
            assert "Tecklenburg" not in tx[kanal], f"{kanal}: Ortsname in der SMS: {tx[kanal]}"
        _keine_bereichsnamen(tx, lang)
    assert uids[0] != uids[1]


# ---------------------------------------------------------------------------
# SMS ohne Daten (Renderer; der Versand schickt dann nichts, no_weather)
# ---------------------------------------------------------------------------


def _sms_aus(location_ids: tuple[str, ...]) -> str:
    from output.renderers.comparison import render_compare_sms

    orte = [SavedLocation(id=lid, name=ORTE[lid][0], lat=ORTE[lid][1], lon=ORTE[lid][2],
                          elevation_m=1000) for lid in location_ids]
    return render_compare_sms(_ergebnis(orte, {}))


def test_sms_keine_daten_mehrere_orte():
    """Kein Ort im Ergebnis -> leere SMS (#3172: kein Sondertext; der Versand
    schickt dann ohnehin nichts)."""
    assert _sms_aus(()) == ""


def test_sms_keine_daten_ein_ort():
    """Genau ein Ort ohne Daten -> ``O1 n/a`` (#3172: kein Sondertext
    "{Ortsname}: keine Daten", kein Name)."""
    FEHLER["orte"] = {"loc-tb"}
    try:
        assert _sms_aus(EINER) == "O1 n/a"
    finally:
        FEHLER["orte"] = set()


def test_sms_mehrere_orte_einer_ohne_daten_bleibt_sichtbar():
    """Gegenprobe: bei mehreren Orten bleibt ein Ort ohne Daten als ``O{n} n/a``
    sichtbar; die anderen behalten ihre Nummer."""
    FEHLER["orte"] = {"loc-bz"}
    try:
        sms = _sms_aus(DREI)
    finally:
        FEHLER["orte"] = set()
    assert sms.startswith("O1 "), sms
    assert "O2 n/a" in sms and orte_nummern(sms) == [1, 2, 3], sms


def test_sms_mehrere_orte_alle_ohne_daten():
    """#3172 (PO 2026-11-19): mehrere Orte, alle ohne Daten -> jeder Ort als
    ``O{n} n/a`` (der Sondertext "Orte: keine Daten" ist abgeloest)."""
    FEHLER["orte"] = set(DREI)
    try:
        assert _sms_aus(DREI) == "O1 n/a O2 n/a O3 n/a"
    finally:
        FEHLER["orte"] = set()


# ---------------------------------------------------------------------------
# SMS-Kopf bei genau einem Ort: Grenzen des Ortsnamens, Ort ohne Wertzelle
# ---------------------------------------------------------------------------

#: #3172 (ADR-0125): ein Wert-Token der Token-Zeile (``D12``, ``W-``, ``TH:-``).
_ZELLE = re.compile(r"(?:^| )[A-Z]{1,3}:?(?:-?\d|-|\?)")


def _sms_ein_ort(name: str, enabled_metrics=None) -> str:
    from app.user import ComparisonResult, LocationResult
    from output.renderers.comparison import render_compare_sms

    werte = {"precip_1h": 1.0, "pop": 10}
    loc = SavedLocation(id="loc-x", name=name, lat=47.0, lon=11.0, elevation_m=1000)
    lr = LocationResult(location=loc, temp_max=12.0, temp_min=3.0, wind_max=11.0, gust_max=19.0,
                        cloud_avg=35, sunny_hours=6, official_alerts=[],
                        hourly_data=[_dp(9, werte), _dp(12, werte), _dp(15, werte)])
    res = ComparisonResult(locations=[lr], time_window=(9, 16), target_date=TARGET_DATE,
                           created_at=datetime(2026, 7, 8, 4, 0))
    return render_compare_sms(res, enabled_metrics=enabled_metrics)


@pytest.mark.parametrize("laenge", [5, 60, 200])
def test_sms_ein_ort_langer_name_grenzen(laenge):
    """#3172 (PO 2026-11-19): der Ortsname steht nicht in der SMS -- auch ein
    sehr langer Name kostet kein Zeichen; die SMS beginnt mit ``O1`` und
    einem Wert und haelt die Grenze (160 wie die Trip-SMS)."""
    from output.renderers.comparison import ORTE_SMS_MAX_ZEICHEN

    name = ("Sankt Wolfgang im Salzkammergut " * 8)[:laenge].strip()
    sms = _sms_ein_ort(name)
    assert len(sms) <= ORTE_SMS_MAX_ZEICHEN, (len(sms), sms)
    assert _ZELLE.search(sms.removeprefix("O1")), f"kein Wert: {sms!r}"
    assert sms.startswith("O1 ") and name not in sms, sms


def test_sms_ein_ort_ohne_wertzelle_ohne_haengenden_trenner():
    """Ein Ort, bewusst leere Auswahl bzw. gewaehlte Groesse ohne Wert: kein
    haengendes Leerzeichen und kein Trenner (#3172: nur ``O1``)."""
    assert _sms_ein_ort("Tecklenburg", enabled_metrics=[]) == "O1"
    # #3172: Wintersport ohne Wert entfaellt wie im Trip (kein ``SD?``).
    assert _sms_ein_ort("Tecklenburg", enabled_metrics=["snow_depth_cm"]) == "O1"


def test_sms_ein_ort_ohne_wertzelle_ungekuerzt_ohne_haengendes_leerzeichen():
    """Kern ohne Laengengrenze (``max_chars=None``, Zweig ohne Einpassung): ein
    Ort ohne Wertzelle endet direkt auf dem Kopf, ohne Leerzeichen (Adversary
    F002). Echter Renderer-Kern, keine Attrappe. #3172: nur ``O1``."""
    from app.user import ComparisonResult, LocationResult
    from app.ampel import resolve_ampel
    from output.renderers.comparison import _render_compare_sms_body

    loc = SavedLocation(id="loc-x", name="Tecklenburg", lat=47.0, lon=11.0, elevation_m=1000)
    werte = {"precip_1h": 1.0, "pop": 10}
    lr = LocationResult(location=loc, temp_max=12.0, temp_min=3.0, wind_max=11.0, gust_max=19.0,
                        cloud_avg=35, sunny_hours=6, official_alerts=[],
                        hourly_data=[_dp(9, werte), _dp(12, werte), _dp(15, werte)])
    res = ComparisonResult(locations=[lr], time_window=(9, 16), target_date=TARGET_DATE,
                           created_at=datetime(2026, 7, 8, 4, 0))
    sms = _render_compare_sms_body(res, enabled_metrics=[], metric_formats=None,
                                   max_chars=None, ampel=resolve_ampel({}))
    assert sms == "O1", repr(sms)


# ---------------------------------------------------------------------------
# T1: Warnmail-Kontext, geloeschte Orte, Abo ohne Namen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang, soll", [("de", "Orte · Amtliche Warnung"),
                                        ("en", "Locations · Official warning")])
def test_warnmail_der_orte_nennt_orte(lang, soll):
    """Amtliche Warnmail eines Orte-Abos (``official_header_texts``):
    Herkunftszeile "Orte · Amtliche Warnung" in HTML und Klartext."""
    from zoneinfo import ZoneInfo

    from services.alert_channel_texts import official_header_texts
    from tests.helpers.amtliche_warnungen_fixture import ORTE as WARN_ORTE
    from tests.helpers.amtliche_warnungen_fixture import _compare_notices, meteoalarm_gewitter

    notices = _compare_notices([(meteoalarm_gewitter(), list(WARN_ORTE))], lang)
    tx = official_header_texts(notices, [], prefix="Münsterland", tz=ZoneInfo("Europe/Vienna"),
                               lang=lang)
    assert soll in _sichtbar(tx.html), _sichtbar(tx.html)[-300:]
    assert soll in tx.plain, tx.plain[-300:]
    muster = VERBOTEN_EN if lang == "en" else VERBOTEN_DE
    assert not muster.findall(_sichtbar(tx.html) + tx.plain)


def _warn_kanaele_orte(orte: tuple[str, ...], betroffen: tuple[str, ...], lang: str,
                       namen: dict[str, str] | None = None) -> dict:
    """Amtliche Warnung eines Orte-Abos ueber die echten Bausteine des
    Versands (``send_multi_location_official_alert``): Builder ->
    ``official_header_texts`` (Betreff, Mail HTML+Klartext, SMS = auch
    Premium-SMS, ``head.sms``) und ``official_telegram_text`` (reich und Kurzform)."""
    from zoneinfo import ZoneInfo

    from output.renderers.alert.official_alerts import build_compare_official_alert_notices
    from services.alert_channel_texts import official_header_texts, official_telegram_text
    from tests.helpers.amtliche_warnungen_fixture import meteoalarm_gewitter

    tz = ZoneInfo("Europe/Vienna")
    if namen is None:
        namen = {lid: ORTE[lid][0] for lid in orte}
    notices = build_compare_official_alert_notices(
        list(orte), namen, [(meteoalarm_gewitter(), list(betroffen))], lang=lang)
    head = official_header_texts(notices, [], prefix="Kette Basis", tz=tz, lang=lang)
    tg = {
        stil: html_mod.unescape(re.sub(r"<[^>]+>", "", official_telegram_text(
            notices, [], style=stil, prefix="Kette Basis", source_label=head.source_label,
            tz=tz, lang=lang)))
        for stil in ("rich", "kurzform")
    }
    return {
        "betreff": head.subject, "html": _sichtbar(head.html), "klartext": head.plain,
        "telegram": tg["rich"], "telegram_kurz": tg["kurzform"],
        "sms": head.sms, "premium_sms": head.sms,
    }


ALLE_ORTE = re.compile(r"alle Orte|all locations|alleOrte|nicht alle|not all", re.IGNORECASE)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac2_warnung_bei_einem_ort_sagt_nicht_alle_orte(lang):
    """Given ein Orte-Abo mit genau einem Ort und eine amtliche Warnung fuer
    diesen Ort / When Mail (HTML, Klartext), Telegram, SMS und Premium-SMS
    gerendert werden / Then sagt kein Text "alle Orte" ("all locations",
    SMS "alleOrte", auch nicht "nicht alle Orte"), und der Ortsname steht als
    Umfang in jedem Kanal (SMS: "Tecklenburg: ...")."""
    tx = _warn_kanaele_orte(EINER, EINER, lang)
    for kanal, text in tx.items():
        treffer = ALLE_ORTE.findall(text)
        assert not treffer, f"{kanal} ({lang}) sagt {treffer} bei einem Ort: {text[:600]!r}"
        assert "Tecklenburg" in text, f"{kanal} ({lang}) nennt den Ort nicht: {text[:600]!r}"
    for kanal in ("sms", "premium_sms", "telegram_kurz"):
        assert tx[kanal].startswith("Tecklenburg: "), f"{kanal}: Umfang ist nicht der Ort: {tx[kanal]!r}"
    assert "nur Tecklenburg" not in tx["html"] + tx["klartext"], "Ein-Ort-Umfang mit 'nur'"


@pytest.mark.parametrize("lang, voll", [("de", "alle Orte"), ("en", "all locations")])
def test_ac2_zwei_gleichnamige_orte_alle_betroffen_bleibt_alle_orte(lang, voll):
    """Given ein Orte-Abo mit zwei verschiedenen Orten (zwei IDs), die denselben
    Anzeigenamen tragen, und eine Warnung fuer beide / When die Kanaele
    gerendert werden / Then heisst der Umfang "alle Orte" ("all locations",
    SMS/Premium-SMS/Telegram-Kurzform "alleOrte: "), nicht der Ortsname --
    die Ein-Ort-Regel zaehlt Orts-IDs, nicht Namen (Adversary F003)."""
    orte = ("loc-gleich-1", "loc-gleich-2")
    namen = {"loc-gleich-1": "Tecklenburg", "loc-gleich-2": "Tecklenburg"}
    tx = _warn_kanaele_orte(orte, orte, lang, namen=namen)
    assert voll in tx["html"] and voll in tx["klartext"], tx["html"][:600]
    for kanal in ("sms", "premium_sms", "telegram_kurz"):
        assert tx[kanal].startswith("alleOrte: "), f"{kanal}: {tx[kanal]!r}"


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac2_ein_ort_mit_leerzeichen_sms_ohne_leerzeichen(lang):
    """Given ein Orte-Abo mit genau einem Ort, dessen Name ein Leerzeichen
    enthaelt ("Bad Ischl"), und eine Warnung fuer ihn / When die Kanaele
    gerendert werden / Then beginnen SMS, Premium-SMS und Telegram-Kurzform
    mit "BadIschl: " (Leerzeichen entfernt), die Mail nennt "Bad Ischl"
    (Adversary F004)."""
    orte = ("loc-bad-ischl",)
    tx = _warn_kanaele_orte(orte, orte, lang, namen={"loc-bad-ischl": "Bad Ischl"})
    for kanal in ("sms", "premium_sms", "telegram_kurz"):
        assert tx[kanal].startswith("BadIschl: "), f"{kanal}: {tx[kanal]!r}"
    assert "Bad Ischl" in tx["html"], tx["html"][:600]
    assert "Bad Ischl" in tx["klartext"], tx["klartext"][:600]
    for kanal, text in tx.items():
        assert not ALLE_ORTE.findall(text), f"{kanal} ({lang}): {text[:600]!r}"


@pytest.mark.parametrize("lang, voll, satz", [
    ("de", "alle Orte", "Die Warnung deckt alle Orte ab."),
    ("en", "all locations", "The warning covers all locations."),
])
def test_ac2_gegenprobe_drei_orte_alle_betroffen_bleibt_alle_orte(lang, voll, satz):
    """Gegenprobe: drei Orte, Warnung fuer alle drei -> der Umfang heisst
    weiter "alle Orte" (SMS "alleOrte"), der Satz ist grammatisch richtig."""
    tx = _warn_kanaele_orte(DREI, DREI, lang)
    assert voll in tx["html"] and voll in tx["klartext"], tx["html"][:600]
    assert satz in tx["html"], tx["html"][:800]
    assert "die alle Orte" not in tx["html"] + tx["klartext"]
    for kanal in ("sms", "premium_sms", "telegram_kurz"):
        assert tx[kanal].startswith("alleOrte: "), tx[kanal]


@pytest.mark.parametrize("lang, soll", [
    ("de", "Das Orte-Abo 'kette-basis' verweist auf gelöschte Orte."),
    ("en", "The locations subscription 'kette-basis' refers to deleted locations."),
])
def test_versand_mit_geloeschten_orten_nennt_orte_abo(mit, lang, soll):
    """Echter Versand eines Orte-Abos, dessen Orte geloescht sind: der Grund
    (``InvalidPresetError.reason_text``) nennt das Orte-Abo."""
    from services.send_outcomes import InvalidPresetError

    uid = nutzer_anlegen("premium")
    for lid, (name, lat, lon, _t) in ORTE.items():
        save_location(SavedLocation(id=lid, name=name, lat=lat, lon=lon, elevation_m=1000),
                      user_id=uid)
    p = _preset(("loc-geloescht",))
    preset_ablegen(uid, p)
    with pytest.raises(InvalidPresetError) as exc:
        briefing_senden(uid, p["id"], settings_fuer(uid))
    assert exc.value.reason_text(lang).startswith(soll), exc.value.reason_text(lang)
    assert not VERBOTEN_EN.findall(exc.value.reason_text(lang))


@pytest.mark.parametrize("lang, soll", [("de", "Dieses Abo Orte "),
                                        ("en", "This subscription Locations ")])
def test_abo_ohne_namen_heisst_orte(lang, soll):
    """Abo ohne Namen: der Fuss nennt "Orte" bzw. "Locations"."""
    from output.renderers.email.compare_html import render_compare_html

    orte = [SavedLocation(id=lid, name=ORTE[lid][0], lat=ORTE[lid][1], lon=ORTE[lid][2],
                          elevation_m=1000) for lid in DREI]
    html = render_compare_html(_ergebnis(orte, {}), preset=_preset(DREI), preset_name=None,
                               lang=lang)
    assert soll in _sichtbar(html), _sichtbar(html)[-600:]
