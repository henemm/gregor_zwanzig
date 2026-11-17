"""#3047 Runde 7, Paket p2 (Orte-Kanaele): Befunde B-K3, B-K5, B-K6, B-K7, B-K8.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md,
"Nachtrag Runde 7" (AC-22, AC-23, AC-24) und PO-Entscheidungen 2026-11-16.

Echter Weg: rohes Preset-JSON im Nutzerordner -> ``load_compare_presets`` ->
``send_one_compare_preset`` -> ``NotificationService`` -> Transport-Mitschrift
(``tests/helpers/transport_mitschrift.py``). Einzige Naehte: Wetter
(``ComparisonEngine.run``, echte Subklasse) und Transport. Jeder Fall mit zwei
frischen Nutzern. Erwartungen stehen von Hand im Test bzw. kommen aus dem rohen
JSON, nie aus ``resolve_*``.

B-K7 (3-Tages-Ausblick im Orte-Telegram): seit Paket p2b reicht der
Versandaufruf (``scheduler_dispatch_service.py``) die Ausblick-Einstellungen an
``render_compare_telegram``; der Kettentest laeuft ohne ``xfail``.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.loader import get_data_dir
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._compare_kette_fixtures import (
    TARGET_DATE, _WERTE, _dp, briefing_senden, fixture_dict, nutzer_anlegen,
    orte_anlegen, preset_ablegen, preset_laden, settings_fuer, transport_einrichten,
)

WIEN = ZoneInfo("Europe/Vienna")
#: Orts-Kennung -> amtliche Warnung an? (je Test gesetzt)
WARN: dict = {"orte": set()}


def _ausblick(i: int) -> list:
    """Drei Tage Ausblick-Stunden je Ort (geteilte Erzeugungsregel der Mail-Kette)."""
    from tests.helpers.einstellung_gleich_mail_orte import _ausblick_fuer

    return _ausblick_fuer(i)


def _warnung():
    from services.official_alerts.models import OfficialAlert

    return OfficialAlert(
        source="meteoalarm", hazard="thunderstorm", level=3, label="Gewitter",
        region_label="Tirol", valid_from=datetime(2026, 7, 8, 10, 0, tzinfo=WIEN),
        valid_to=datetime(2026, 7, 8, 20, 0, tzinfo=WIEN))


def _ergebnis(locations, kwargs):
    from app.models import ThunderLevel
    from app.user import ComparisonResult, LocationResult

    res = []
    for i, loc in enumerate(list(locations)):
        w = _WERTE[loc.id]
        res.append(LocationResult(
            location=loc, score=90 - 7 * i, temp_max=w["temp_max"], temp_min=w["temp_min"],
            wind_max=w["wind_max"], gust_max=w["gust_max"], cloud_avg=w["cloud_avg"],
            sunny_hours=w["sunny_hours"], snow_depth_cm=w["snow_depth_cm"],
            snow_new_cm=w["snow_new_cm"], wind_direction_avg=250 + 20 * i,
            precip_sum_mm=3.5 + i, pop_max_pct=40 + 10 * i, uv_index_max=6.0,
            thunder_level_max=ThunderLevel.MED, visibility_min_m=8000,
            official_alerts=[_warnung()] if loc.id in WARN["orte"] else [],
            hourly_data=[_dp(9, w), _dp(12, w), _dp(15, w)],
            outlook_hourly_data=_ausblick(0 if loc.id == "loc-ibk" else 1),
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
    WARN["orte"] = set()
    return aufzeichner_installieren(monkeypatch)


#: Grundauswahl, Folge bewusst != Katalogfolge (zehn Zeilen).
GRUND = [("gust", "max"), ("temperature", "max"), ("wind_direction", "avg"), ("wind", "max"),
         ("precipitation", "sum"), ("rain_probability", "max"), ("cloud_total", "avg"),
         ("sunshine", "sum"), ("thunder", "max"), ("uv_index", "max")]


def preset(layouts=None, **top) -> dict:
    p = fixture_dict("basis")
    p["display_config"]["active_metrics"] = [{"metric_id": m, "aggregation": a} for m, a in GRUND]
    if layouts is not None:
        p["display_config"]["channel_layouts"] = layouts
    p["send_telegram"] = p["send_sms"] = p["send_premium_sms"] = True
    p["alert_channels"] = {"email": True, "telegram": False, "sms": False, "premium_sms": False}
    p.update(top)
    return p


def _sprache(uid: str, lang: str) -> None:
    pf = get_data_dir(uid) / "user.json"
    u = json.loads(pf.read_text())
    u["language"] = lang
    pf.write_text(json.dumps(u))


def zwei_nutzer(mit, p, *, lang: str = "de") -> list:
    """Zwei frische Nutzer, je ein Briefing ueber den echten Weg; je Nutzer die
    Mitschrift. Vorbedingung: Telegram, SMS und Premium-SMS gingen an DIESEN Nutzer."""
    laeufe = []
    for _ in range(2):
        uid = nutzer_anlegen("premium")
        _sprache(uid, lang)
        orte_anlegen(uid)
        preset_ablegen(uid, copy.deepcopy(p))
        mit.leeren()
        briefing_senden(uid, p["id"], settings_fuer(uid))
        snap = copy.deepcopy(mit)
        mit.leeren()
        for k in ("telegram", "sms", "premium_sms"):
            assert snap.sendungen(k), f"Vorbedingung: keine {k}-Sendung fuer {uid}"
        assert snap.empfaenger("telegram") == [f"chat-{uid}"]
        laeufe.append((uid, snap))
    assert laeufe[0][0] != laeufe[1][0]
    return laeufe


def text(snap, kanal: str) -> str:
    return snap.sendungen(kanal)[-1]["body"]


def ortsbloecke(tg: str) -> dict[str, list[str]]:
    """Telegram-Text -> {Ortsname: eingerueckte Zeilen des Ortsblocks}."""
    bloecke: dict[str, list[str]] = {}
    aktuell = None
    for zeile in tg.splitlines():
        if zeile in ("Innsbruck", "Bozen"):
            aktuell = bloecke.setdefault(zeile, [])
        elif aktuell is not None and zeile.startswith("   "):
            aktuell.append(zeile.strip())
    return bloecke


def wertezeilen(block: list[str]) -> list[list[str]]:
    """Zellen der Werte-Zeilen eines Ortsblocks (Zeilen mit ' · '), nur der
    Telegram-Liste: der 3-Tages-Ausblick (ab Kopf "Ausblick"/"Outlook", B-K7)
    gehoert nicht dazu."""
    for kopf in ("Ausblick", "Outlook"):
        if kopf in block:
            block = block[:block.index(kopf)]
    return [z.split(" · ") for z in block if " · " in z]


# ---------------------------------------------------------------------------
# B-K3 / AC-23: amtliche Warnung eines weiteren Ortes faellt zuletzt weg
# ---------------------------------------------------------------------------

#: SMS-Kuerzel je Grundauswahl-Zeile (von Hand, sms_format.md).
KUERZEL = {"gust": "G", "temperature": "D", "wind_direction": "WD", "wind": "W",
           "precipitation": "R", "rain_probability": "PR", "cloud_total": "CT",
           "sunshine": "SU", "thunder": "TH", "uv_index": "UV"}


def _sms_ort(sms: str, name: str) -> str:
    teile = sms.split(": ", 1)[1].split("; ")
    treffer = [t for t in teile if t.startswith(name + " ")]
    assert treffer, f"Ort {name} fehlt in der SMS: {sms}"
    return treffer[0]


def _kuerzel_folge(ortsteil: str) -> list[str]:
    alle = "|".join(sorted(KUERZEL.values(), key=len, reverse=True))
    return re.findall(rf"(?<= )({alle}) (?=[-\w])", ortsteil)


@pytest.mark.parametrize("folge", ["grund", "eigene_sms_liste"])
def test_ac23_warnung_zweiter_ort_faellt_zuletzt_weg(mit, folge):
    """Nur Bozen (zweiter Ort) hat eine Gewitterwarnung. SMS und Premium-SMS
    tragen sie (``!TS``), die Wetterzellen fallen vom Listenende weg."""
    WARN["orte"] = {"loc-bz"}
    liste = [m for m, _ in GRUND]
    layouts = None
    if folge == "eigene_sms_liste":
        liste = ["uv_index", "thunder", "precipitation", "gust", "temperature",
                 "sunshine", "cloud_total", "wind", "rain_probability", "wind_direction"]
        layouts = {"sms": [{"metric_id": m, "enabled": True} for m in liste]}
    soll = [KUERZEL[m] for m in liste]
    for uid, snap in zwei_nutzer(mit, preset(layouts)):
        for kanal in ("sms", "premium_sms"):
            sms = text(snap, kanal)
            assert len(sms) <= 160, sms
            bozen = _sms_ort(sms, "Bozen")
            assert "!TS" in bozen, f"{kanal} ({uid}): Warnung von Bozen fehlt: {sms}"
            for name in ("Innsbruck", "Bozen"):
                ist = _kuerzel_folge(_sms_ort(sms, name))
                assert len(ist) >= 3, f"{kanal}: {name} unnoetig leer gekuerzt: {sms}"
                assert ist == soll[:len(ist)], (
                    f"{kanal}: {name} kuerzt nicht vom Listenende: {ist} vs {soll}")
            # #3122 B5: der Kopf heisst "Orte TT.MM.:" -- gemeint ist der Ueberlauf " +k Orte".
            assert not re.search(r"\+\d+ Orte", sms), f"kein Ort darf ganz wegfallen: {sms}"


def test_ac23_ohne_warnung_bleibt_kuerzung_wie_bisher(mit):
    """Gegenprobe ohne Warnung. #3047 Runde 7 p8 (Tech-Lead-Entscheidung zu
    AC-23, ADR-0095 -- ein Vergleich braucht mehrere Orte) loest die fruehere
    Erwartung "erster Ort voll, weitere als ``+k Orte``" ab: auch ohne Warnung
    werden zuerst die Zellen aller Orte vom Listenende gekuerzt, beide Orte
    bleiben sichtbar."""
    soll = [KUERZEL[m] for m, _ in GRUND]
    for uid, snap in zwei_nutzer(mit, preset()):
        sms = text(snap, "sms")
        assert not re.search(r"\+\d+ Orte", sms), sms
        for name in ("Innsbruck", "Bozen"):
            ist = _kuerzel_folge(_sms_ort(sms, name))
            assert ist and ist == soll[:len(ist)], (name, ist, sms)
        assert text(snap, "premium_sms") == sms


# ---------------------------------------------------------------------------
# B-K5 / AC-24: Orte-Telegram, Zeilen ab Platz 8 in einer zweiten Zeile
# ---------------------------------------------------------------------------

#: Telegram-Zellbeschriftung je Zeile (von Hand, DE/EN).
TG_DE = {"gust": "Böen", "temperature": "Temp", "wind_direction": "Windrichtung", "wind": "Wind",
         "precipitation": "Regen", "rain_probability": "Regenwahrscheinlichkeit",
         "cloud_total": "Wolken", "sunshine": "Sonne", "thunder": "Gewitter", "uv_index": "UV"}
TG_EN = {"gust": "Gusts", "temperature": "Temp", "wind_direction": "Wind direction",
         "wind": "Wind", "precipitation": "Rain", "rain_probability": "Rain probability",
         "cloud_total": "Clouds", "sunshine": "Sun", "thunder": "Thunderstorm", "uv_index": "UV"}


def _beschriftung(zelle: str, namen: dict) -> str:
    treffer = [m for m, n in namen.items() if zelle.startswith(n + " ")]
    return max(treffer, key=lambda m: len(namen[m]))


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac24_telegram_zeilen_ab_8_in_zweiter_zeile(mit, lang):
    """Zehn Zeilen in eigener Folge: Zeile 1 traegt die ersten sieben, Zeile 2
    die Plaetze 8 bis 10; kein Kappungshinweis, nichts faellt weg."""
    liste = ["thunder", "sunshine", "gust", "wind_direction", "uv_index", "cloud_total",
             "temperature", "rain_probability", "wind", "precipitation"]
    p = preset({"telegram": [{"metric_id": m, "enabled": True} for m in liste]})
    namen = TG_DE if lang == "de" else TG_EN
    for uid, snap in zwei_nutzer(mit, p, lang=lang):
        tg = text(snap, "telegram")
        assert "Telegram" not in tg, f"Kappungshinweis darf nicht mehr erscheinen:\n{tg}"
        bloecke = ortsbloecke(tg)
        assert set(bloecke) == {"Innsbruck", "Bozen"}, tg
        for name, block in bloecke.items():
            zeilen = wertezeilen(block)
            assert [len(z) for z in zeilen] == [7, 3], f"{name}:\n{tg}"
            ist = [_beschriftung(c, namen) for z in zeilen for c in z]
            assert ist == liste, f"{name}: Folge {ist} != {liste}"


# ---------------------------------------------------------------------------
# B-K6: ausdruecklich leere Kanal-Liste bleibt leer
# ---------------------------------------------------------------------------


def test_k6_leere_kanal_liste_bleibt_leer(mit):
    """``channel_layouts.sms = []`` und ``.telegram = []`` (bewusst leer) ->
    keine Wetterzelle in SMS, Premium-SMS und Telegram (Trip-Semantik)."""
    p = preset({"sms": [], "telegram": []})
    for uid, snap in zwei_nutzer(mit, p):
        for kanal in ("sms", "premium_sms"):
            sms = text(snap, kanal)
            assert not re.search(r"\b[A-Z]{1,2} \d", sms), f"{kanal}: leer bleibt leer: {sms}"
        tg = text(snap, "telegram")
        for block in ortsbloecke(tg).values():
            assert not wertezeilen(block), f"Telegram: leer bleibt leer:\n{tg}"
            assert not any(re.match(r"(Böen|Temp|Wind|Regen|Wolken|Sonne) ", z) for z in block), tg


def test_k6_gegenprobe_ohne_liste_volle_grundauswahl(mit):
    """Gegenprobe: ohne ``channel_layouts`` gilt die Grundauswahl (nie eingestellt)."""
    for uid, snap in zwei_nutzer(mit, preset()):
        assert "G 19 km/h" in text(snap, "sms")
        assert "Böen 19 km/h" in text(snap, "telegram")


# ---------------------------------------------------------------------------
# B-K8: Roh/Einfach der Orte-Telegram-Liste (Kettentest)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("einfach", [True, False])
def test_k8_telegram_roh_einfach_je_zeile(mit, einfach):
    """Bewoelkung und Windrichtung in ``channel_layouts.telegram`` auf Einfach
    bzw. Roh; Windstaerke bleibt in beiden Faellen Roh (Zahl)."""
    p = preset({"telegram": [
        {"metric_id": "cloud_total", "enabled": True, "use_friendly_format": einfach},
        {"metric_id": "wind_direction", "enabled": True, "use_friendly_format": einfach},
        {"metric_id": "wind", "enabled": True},
    ]})
    for uid, snap in zwei_nutzer(mit, p):
        tg = text(snap, "telegram")
        zellen = wertezeilen(ortsbloecke(tg)["Innsbruck"])[0]
        wolken, richtung, wind = zellen[:3]
        assert wind == "Wind 11 km/h", tg
        if einfach:
            assert not re.search(r"\d", wolken), f"Wolken Einfach zeigt Zahl: {wolken}"
            assert richtung == "Windrichtung W", f"Windrichtung Einfach: {richtung}"
        else:
            assert wolken == "Wolken 35%", f"Wolken Roh: {wolken}"
            assert richtung == "Windrichtung 250°", f"Windrichtung Roh: {richtung}"


# ---------------------------------------------------------------------------
# B-K7 / AC-24: 3-Tages-Ausblick im Orte-Telegram
# ---------------------------------------------------------------------------

AUSBLICK = ["gust", "temperature", "wind"]


def _ausblick_preset(**top) -> dict:
    p = preset(**top)
    p["display_config"]["outlook_metrics"] = list(AUSBLICK)
    p["display_config"]["outlook_metric_formats"] = {"gust": True, "temperature": False,
                                                     "wind": False}
    return p


def _ausblick_zeilen(block: list[str], lang: str) -> list[str]:
    kopf = {"de": "Ausblick", "en": "Outlook"}[lang]
    assert kopf in block, f"Ausblick-Kopf fehlt im Ortsblock: {block}"
    return block[block.index(kopf) + 1:]


def _pruefe_ausblick(tg: str, lang: str) -> None:
    namen = ("Gust", "Temp", "Wind")  # von Hand: Spaltenkoepfe des Registers (wie Trip)
    for name, block in ortsbloecke(tg).items():
        tage = [z for z in _ausblick_zeilen(block, lang) if ":" in z]
        assert len(tage) == 3, f"{name}: drei Ausblick-Tage erwartet:\n{tg}"
        for tag in tage:
            felder = re.findall(r"(\S+(?: \S+)?): (\S+(?: \S+)?)(?:  |$)", tag.split("  ", 1)[1])
            assert [f[0] for f in felder] == list(namen), f"{name}: Folge {felder}"
            werte = dict(zip(AUSBLICK, (f[1] for f in felder)))
            assert not re.search(r"\d", werte["gust"]), f"Boeen Einfach: {tag}"
            assert re.search(r"\d", werte["wind"]), f"Wind Roh: {tag}"


@pytest.mark.parametrize("lang", ["de", "en"])
def test_k7_ausblick_im_orte_telegram_renderer(mit, lang):
    """Optionen aus dem gespeicherten JSON (echter Loader + Resolver) -> Orte-
    Telegram traegt je Ort den 3-Tages-Ausblick in Trip-Telegram-Form; Folge
    und Roh/Einfach wie gespeichert. Bewusst leere Liste bzw. Schalter aus ->
    kein Ausblick."""
    from output.renderers.comparison import render_compare_telegram
    from services.report_config_resolver import resolve_compare_render_options

    from app.loader import load_all_locations

    leer = _ausblick_preset()
    leer["display_config"]["outlook_metrics"] = []
    faelle = ((_ausblick_preset(), True), (_ausblick_preset(outlook_enabled=False), False),
              (leer, False))
    for p, soll in faelle:
        for _ in range(2):
            uid = nutzer_anlegen("premium")
            orte_anlegen(uid)
            preset_ablegen(uid, copy.deepcopy(p))
            gespeichert = preset_laden(uid, p["id"])
            opts = resolve_compare_render_options(gespeichert)
            orte = [o for o in load_all_locations(user_id=uid) if o.id in gespeichert["location_ids"]]
            tg = render_compare_telegram(
                _ergebnis(orte, {}), enabled_metrics=opts.enabled_metrics_by_channel["telegram"],
                preset_name=gespeichert["name"], lang=lang,
                metric_formats=opts.metric_formats("telegram"),
                outlook_enabled=opts.outlook_enabled, outlook_metrics=opts.outlook_metrics,
                outlook_metric_formats=opts.outlook_metric_formats, preset=gespeichert,
            )
            if soll:
                _pruefe_ausblick(tg, lang)
            else:
                assert not any("Ausblick" in z or "Outlook" in z for z in tg.splitlines()), tg


def _ausblick_faelle() -> tuple:
    leer = _ausblick_preset()
    leer["display_config"]["outlook_metrics"] = []
    return ((_ausblick_preset(), True), (_ausblick_preset(outlook_enabled=False), False),
            (leer, False))


@pytest.mark.parametrize("lang", ["de", "en"])
def test_k7_ausblick_im_orte_telegram_kette(mit, lang):
    """B-K7 (AC-24) ueber den echten Versandweg bis zur Transport-Mitschrift:
    Ausblick an -> je Ort drei Tage in gespeicherter Folge und Roh/Einfach;
    Schalter aus bzw. bewusst leere Ausblick-Liste -> kein Ausblick. Zwei Nutzer."""
    for p, soll in _ausblick_faelle():
        for uid, snap in zwei_nutzer(mit, p, lang=lang):
            tg = text(snap, "telegram")
            if soll:
                _pruefe_ausblick(tg, lang)
            else:
                assert not any(z.strip() in ("Ausblick", "Outlook") for z in tg.splitlines()), tg


@pytest.mark.parametrize("lang", ["de", "en"])
def test_k7_ausblick_in_orte_telegram_vorschau(mit, lang):
    """B-K7 (AC-24): die Telegram-Vorschau des Editors zeigt denselben Ausblick
    wie der Versand (an -> drei Tage je Ort; aus/leere Liste -> keiner). Echter
    Lade- und Renderweg ``ComparePreviewService``, zwei Nutzer."""
    from services.compare_preview_service import ComparePreviewService

    for p, soll in _ausblick_faelle():
        uids = []
        for _ in range(2):
            uid = nutzer_anlegen("premium")
            _sprache(uid, lang)
            orte_anlegen(uid)
            preset_ablegen(uid, copy.deepcopy(p))
            tg = ComparePreviewService().render_all_channels(
                p["id"], user_id=uid, target_date=TARGET_DATE)["telegram"]
            if soll:
                _pruefe_ausblick(tg, lang)
            else:
                assert not any(z.strip() in ("Ausblick", "Outlook") for z in tg.splitlines()), tg
            uids.append(uid)
        assert uids[0] != uids[1]


def test_om1_gegenprobe_ohne_ausfall_kein_hinweis(mit):
    """B-OM-1 Gegenprobe (Mail-Klartext derselben Kette): Warndienst erreichbar
    -> kein Hinweis "nicht abrufbar" im Klartext."""
    for uid, snap in zwei_nutzer(mit, preset()):
        plain = snap.sendungen("email")[-1]["plain_text_body"]
        assert "Kette Basis" in plain or "ORTE" in plain, "Vorbedingung: Klartext"
        assert "Amtliche Warnungen aktuell nicht abrufbar" not in plain, plain[:600]


# ---------------------------------------------------------------------------
# Nebenbefund p2b: Orte-Telegram mit Warnung -- keine Roh-Tags beim Nutzer
# ---------------------------------------------------------------------------

#: Ortsnamen mit HTML-Sonderzeichen (Nutzerdaten, muessen wortgetreu ankommen).
SONDERNAMEN = {"loc-ibk": "Inns<b>ruck & Hall", "loc-bz": "Bozen <Süd> & Co"}


def _wie_telegram_anzeigt(sendung: dict) -> str:
    """Was der Nutzer in Telegram sieht (Bot-API-Regeln): ohne ``parse_mode``
    der Text wortgetreu; mit ``HTML`` werden Tags zu Formatierung und Entities
    aufgeloest -- ein rohes ``<``/``&`` ausserhalb von Tag/Entity lehnt die API
    ab (HTTP 400), hier als Fehler."""
    import html as _html

    body = sendung["body"]
    if sendung["parse_mode"] is None:
        return body
    assert sendung["parse_mode"] == "HTML", sendung["parse_mode"]
    ohne_tags = re.sub(r"</?(b|i|u|s|code|pre|a)(\s[^>]*)?>", "", body)
    assert "<" not in ohne_tags and not re.search(r"&(?!(amp|lt|gt|quot|#\d+);)", ohne_tags), (
        f"ungueltiges Telegram-HTML (API: 400):\n{body}")
    return _html.unescape(ohne_tags)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_orte_telegram_warnung_ohne_rohe_tags(mit, lang):
    """Ein Ort mit amtlicher Warnung, Ortsnamen mit ``<`` und ``&``: der Nutzer
    sieht im Orte-Telegram die Warnung und beide Namen wortgetreu, aber nie
    ein rohes ``<b>``/``</b>`` oder ``&amp;``. Zwei Nutzer, echter Versandweg
    bis zur Transport-Mitschrift (Text + parse_mode)."""
    from app.loader import save_location
    from app.user import SavedLocation
    from tests.tdd._compare_kette_fixtures import ORTE

    WARN["orte"] = {"loc-bz"}
    p = preset()
    nutzer = []
    for _ in range(2):
        uid = nutzer_anlegen("premium")
        _sprache(uid, lang)
        for lid, (_, lat, lon) in ORTE.items():
            save_location(SavedLocation(id=lid, name=SONDERNAMEN[lid], lat=lat, lon=lon,
                                        elevation_m=1000), user_id=uid)
        preset_ablegen(uid, copy.deepcopy(p))
        mit.leeren()
        briefing_senden(uid, p["id"], settings_fuer(uid))
        assert mit.empfaenger("telegram") == [f"chat-{uid}"]
        sicht = _wie_telegram_anzeigt(mit.sendungen("telegram")[-1])
        for name in SONDERNAMEN.values():
            assert name in sicht.splitlines(), f"Ortsname nicht wortgetreu:\n{sicht}"
        warnkopf = [z for z in sicht.splitlines() if z.strip().startswith("Bozen <Süd> & Co · ")]
        assert warnkopf, f"Warnkopf des Ortes fehlt:\n{sicht}"
        assert "<b>" not in sicht.replace("Inns<b>ruck", ""), f"rohe Tags beim Nutzer:\n{sicht}"
        assert "</b>" not in sicht, f"rohe Tags beim Nutzer:\n{sicht}"
        assert "&amp;" not in sicht and "&lt;" not in sicht, f"rohe Entities:\n{sicht}"
        nutzer.append(uid)
    assert nutzer[0] != nutzer[1]
