"""Amtliche Warnungen zweisprachig: Titel, Lagebericht, Ratsche
(Issue #2668, AC-4, AC-7).

SPEC: docs/specs/modules/i18n_p6_amtliche_warnungen_2668.md

Erwartungen kommen aus dem Katalog (``t(key, lang)``), nie aus getippten
Literalen. Die Ratsche ist VERHALTEN: die englische Ausgabe aller Golden-Faelle
enthaelt keinen deutschen Katalogtext des Bereichs ``warnung`` und kein
deutsches Umlaut-Wort ausser Eigennamen (Orte, Behoerden). Die SMS bleibt in
jeder Sprache byte-gleich (PO-Korrektur 2026-10-31) und ist von der Ratsche
ausgenommen.
"""
from __future__ import annotations

import html as _html
import json
import re
from pathlib import Path

import pytest

from i18n import t
from output.renderers.alert import official_alerts as oa
from tests.helpers.amtliche_warnungen_fixture import (
    FAELLE, ORTE, PREFIX, STAND, TRENNER, TZ, lagebericht, notices_fuer, render_fall,
    sms_aus_txt,
)

KATALOG = Path(__file__).resolve().parents[1] / "src" / "i18n" / "messages"
# Daten des Aufrufers / Eigennamen (keine Renderertexte).
_EIGENNAMEN = (*ORTE.values(), "Météo-France", "WSL-Institut für Schnee- und Lawinenforschung SLF",
               "Innsbruck-Land", "Golden-Vergleich", "Zeitueberschreitung beim Abruf",
               "Ort Brenner nicht erreichbar")
# Fremde Pakete im Ortsvergleich-Fall: Antwort-Kommandos (P10, #2673).
_FREMDE_ZEILEN = ("Vergleich für", "Briefings für", "Kürzel-Bedeutungen", "alle Kanäle senden")


def sichtbar(html: str) -> list[str]:
    s = re.sub(r"<head>.*?</head>", "", html, flags=re.S)
    s = re.sub(r"<[^>]+>", "\n", s)
    return [z.strip() for z in _html.unescape(s).split("\n") if z.strip()]


def _ohne_sms(fall: str, txt: str) -> list[str]:
    sms = set(sms_aus_txt(fall, txt))
    return [teil for teil in txt.split(TRENNER) if teil not in sms]


def englische_zeilen(fall: str) -> list[str]:
    html, txt = render_fall(fall, "en")
    return sichtbar(html) + [z for teil in _ohne_sms(fall, txt) for z in teil.splitlines()]


def _de_fragmente() -> set[str]:
    """Deutsche Bruchstuecke der warnung.*-Texte, die sich vom Englischen unterscheiden."""
    de = json.loads((KATALOG / "de" / "warnung.json").read_text(encoding="utf-8"))
    en = json.loads((KATALOG / "en" / "warnung.json").read_text(encoding="utf-8"))
    out: set[str] = set()
    for key, wert in de.items():
        if wert == en.get(key):
            continue
        for stueck in re.split(r"\{[a-z_]+\}", wert):
            stueck = stueck.strip(" ().:,·—→")
            if len(stueck) >= 4 and stueck not in en.get(key, ""):
                out.add(stueck)
    return out


def treffer(zeilen: list[str]) -> list[str]:
    fragmente = _de_fragmente()
    funde = []
    for zeile in zeilen:
        if any(f in zeile for f in _FREMDE_ZEILEN):
            continue
        rest = zeile
        for name in _EIGENNAMEN:
            rest = rest.replace(name, "")
        funde += [f"{f!r} in {zeile!r}" for f in fragmente if re.search(rf"(?<!\w){re.escape(f)}(?!\w)", rest)]
        funde += [f"Umlaut-Wort {w!r} in {zeile!r}" for w in re.findall(r"\w*[äöüÄÖÜß]\w*", rest)]
    return funde


@pytest.mark.parametrize("fall", FAELLE)
def test_ratsche_englische_ausgabe_ohne_deutsche_rahmentexte(fall):
    assert treffer(englische_zeilen(fall)) == []


def test_ratsche_gegenprobe_deutsch_findet_treffer():
    html, txt = render_fall("gemischte_stufen", "de")
    assert len(treffer(sichtbar(html) + txt.splitlines())) > 15


def _texte(fall: str, lang: str) -> dict[str, str]:
    notices = notices_fuer(fall, lang)
    quelle = oa.official_alert_source_label(notices[0].alert.source, lang=lang)
    kw = dict(source_label=quelle, stand_at=STAND, tz=TZ, context_label=PREFIX, lang=lang)
    return {
        "html": "\n".join(sichtbar(oa.render_warn_block(notices, variant="standalone", **kw))),
        "embedded": "\n".join(sichtbar(oa.render_warn_block(
            notices, variant="embedded", source_label=quelle, tz=TZ, lang=lang))),
        "plain": oa.render_official_alert_mail_plain(notices, **kw),
        "telegram": oa.render_official_alert_telegram(
            notices, prefix=PREFIX, source_label=quelle, tz=TZ, lang=lang),
        "subject": oa.render_official_alert_subject(notices, prefix=PREFIX, tz=TZ, lang=lang),
        "sms": oa.render_official_alert_sms(notices, tz=TZ),
    }


def test_ac4_waldbrand_und_zugangssperre_englisch():
    k = _texte("gemischte_stufen", "en")
    waldbrand = t("warnung.gefahr.wildfire_risk", "en")
    sperre = f"{t('warnung.gefahr.access_ban', 'en')} — Monts Toulonnais"
    assert (waldbrand, sperre) == ("Wildfire risk", "Access closed — Monts Toulonnais")
    for kanal in ("html", "embedded", "plain", "telegram", "subject"):
        assert waldbrand in k[kanal] and sperre in k[kanal], kanal
        assert "Stufe 3" not in k[kanal] and "Waldbrand" not in k[kanal], kanal
        assert t("warnung.gefahr.access_ban", "de") not in k[kanal], kanal
    assert "Haute-Corse" in k["html"] and "Haute-Corse" in k["plain"]
    assert k["sms"] == _texte("gemischte_stufen", "de")["sms"]


def test_ac4_quellenname_mit_englischem_zusatz_behoerde_bleibt():
    assert oa.official_alert_source_label("meteo_forets", lang="en") == "Météo-France (wildfire)"
    assert oa.official_alert_source_label("massif_closure", lang="en") == "Prefecture (access closure)"
    for quelle in ("dwd", "meteoalarm", "geosphere_warn", "slf_bulletin:CH-1", "avalanche_report:at-07"):
        assert oa.official_alert_source_label(quelle, lang="en") == oa.official_alert_source_label(quelle)
    assert oa.official_alert_source_label("meteo_forets") == oa.official_alert_source_label("meteo_forets", lang="de")


def test_ac7_lagebericht_englisch_slf_bleibt_sms_gleich():
    k = _texte("lawinen_lagebericht", "en")
    stufe = t("warnung.lawine.stufe", "en", n="3+", wort=t("warnung.eaws.3", "en"))
    assert stufe == "Avalanche level 3+ (considerable)"
    for kanal in ("html", "plain", "telegram", "embedded"):
        assert stufe in k[kanal], kanal
        assert "WSL-Institut für Schnee- und Lawinenforschung SLF" in k[kanal], kanal
    for key in ("warnung.hoehe.above", "warnung.hoehe.waldgrenze", "warnung.tageszeit.earlier",
                "warnung.problem.wind_slab", "warnung.problem.persistent_weak_layers",
                "warnung.hinweis.massgeblich_slf"):
        assert t(key, "en") in k["plain"], key
    assert k["sms"] == _texte("lawinen_lagebericht", "de")["sms"]
    assert oa.avalanche_bulletin_text(lagebericht()) == oa.avalanche_bulletin_text(lagebericht(), lang="de")


def test_lagebericht_ohne_bekanntes_eaws_wort_nennt_nur_die_stufe():
    from dataclasses import replace

    alert = replace(lagebericht(), native_level=7, problems=("unknown_code",), level_modifier=None,
                    elevation_value=None, time_of_day=None)
    assert oa.avalanche_bulletin_text(alert, lang="en") == f"{t('warnung.gefahr.avalanche_bulletin', 'en')} 7 · unknown_code"


def test_entwarnung_englisch_alle_kanaele():
    html, txt = render_fall("entwarnung", "en")
    zeilen = sichtbar(html) + txt.splitlines()
    wort = t("warnung.entwarnung.wort", "en")
    uebergang = t("warnung.entwarnung.uebergang", "en", alt=3, neu=t("warnung.entwarnung.beendet", "en"))
    assert f"{wort} {t('warnung.gefahr.thunderstorm', 'en')} 3→1 +1 more" in zeilen
    assert f"<b>{PREFIX} · {wort}</b>" in zeilen
    assert any(z.endswith(f": {uebergang}") and z.startswith(t("warnung.gefahr.extreme_heat", "en"))
               for z in zeilen)
    assert sms_aus_txt("entwarnung", txt) == sms_aus_txt("entwarnung", render_fall("entwarnung", "de")[1])


def test_umfang_und_saetze_englisch():
    k = _texte("ortsvergleich_nur", "en")
    assert t("warnung.satz.nur_orte", "en", ort="Hyères") in k["plain"]
    assert t("warnung.umfang.nur", "en", ort="Hyères") in k["subject"]
    voll = _texte("einzelne_warnung", "en")
    assert t("warnung.satz.deckt_route.one", "en") in voll["plain"]
    assert f"{t('warnung.zeile.route', 'en')}: {t('warnung.umfang.gesamte_route', 'en')}" in voll["plain"]
    gemischt = _texte("gemischte_stufen", "en")
    assert t("warnung.satz.unterschiedlich", "en") in gemischt["plain"]
    assert t("warnung.umfang.mehrere_orte", "en") in gemischt["subject"]
    assert t("warnung.umfang.alle_orte", "en") in gemischt["telegram"]


def _vergleich(lang):
    html, txt = render_fall("vergleich_mit_warnungen", lang)
    return "\n".join(sichtbar(html)), txt


def test_ortsvergleich_mail_und_telegram_reichen_die_sprache_durch():
    """Direkte Aufrufer (compare_html, comparison): Warn-Block, Warn-Zeile und
    Warn-Telegram folgen der Mail-Sprache; die SMS bleibt."""
    html, txt = _vergleich("en")
    zeile = f"{t('mail.herkunft.amtliche_warnung', 'en')}: {t('warnung.gefahr.wildfire_risk', 'en')}"
    assert zeile in txt
    assert t("warnung.gefahr.wildfire_risk", "en") in html.splitlines()
    assert "Moderate thunderstorm warning" in html.splitlines()
    assert oa.official_alert_source_label("meteo_forets", lang="en") in txt
    assert f"{t('warnung.kopf.warnstufe', 'en')} {t('warnung.stufe.orange', 'en')} (2/3)" in txt
    assert t("mail.herkunft.amtliche_warnung", "en") in html.splitlines()
    assert "Moderate thunderstorm warning" in txt
    assert sms_aus_txt("vergleich_mit_warnungen", txt) == sms_aus_txt(
        "vergleich_mit_warnungen", render_fall("vergleich_mit_warnungen", None)[1])


def test_embedded_block_zaehlzeile_englisch():
    k = _texte("ortsvergleich_nur", "en")
    assert t("warnung.block.aktiv_stufe", "en", count=2, wort=t("warnung.stufe.orange", "en"),
             position=2) in k["embedded"]
    assert t("mail.herkunft.amtliche_warnung", "en") in k["embedded"]


# ------------------------------- Randfaelle (Mutations-Gegenprobe, #2668)

def _alarm(hazard="wind_gust", level=3, label="Sturm", source="geosphere_warn", **kw):
    from services.official_alerts.models import OfficialAlert

    return OfficialAlert(source=source, hazard=hazard, level=level, label=label, **kw)


def _orte(n: int) -> dict[str, str]:
    return {f"o{i}": f"Ort{i}" for i in range(n)}


def _plain(notices, lang="en", **kw):
    return oa.render_official_alert_mail_plain(
        notices, source_label="GeoSphere Austria", stand_at=STAND, tz=TZ, lang=lang, **kw)


_STUFE_KEY = {2: "gelb", 3: "orange", 4: "rot"}


@pytest.mark.parametrize("level, position", [(2, "niedrigste"), (3, "mittlere"), (4, "hoechste")])
def test_einheitliche_stufe_leiter_und_betreff_englisch(level, position):
    notices = oa.build_official_alert_notices(None, [(_alarm(level=level), ["1"])], lang="en")
    wort = t(f"warnung.stufe.{_STUFE_KEY[level]}", "en")
    hinweis = t("warnung.stufe.von_drei", "en", position=t(f"warnung.stufe.position.{position}", "en"))
    assert f"{t('warnung.kopf.warnstufe', 'en')}: {wort} ({hinweis})" in _plain(notices)
    html = "\n".join(sichtbar(oa.render_official_alert_html(
        notices, source_label="GeoSphere Austria", stand_at=STAND, tz=TZ, lang="en")))
    assert hinweis in html
    assert oa.render_official_alert_subject(notices, prefix=PREFIX, lang="en").startswith(
        f"[{PREFIX}] Segment 1 · {wort} ")


def test_stufe_eins_und_unbekannter_umfang_englisch():
    notices = oa.build_official_alert_notices(None, [(_alarm(level=1), [])], lang="en")
    unbekannt = t("warnung.zeit.unbekannt", "en")
    assert notices[0].scope_label == unbekannt
    assert notices[0].sms_scope == t("warnung.zeit.unbekannt", "de")
    zeilen = oa.render_official_alert_notice_plain([(notices[0].alert, [])], TZ, lang="en")
    assert zeilen[0].startswith(f"{t('warnung.stufe.gruen', 'en')} — ")
    assert zeilen[1] == f"{t('warnung.zeile.region', 'en')}: {unbekannt}"
    assert oa._format_validity(notices[0].alert, lang="en") == unbekannt


def test_ortsvergleich_ohne_orte_und_voller_umfang_englisch():
    leer = oa.build_compare_official_alert_notices(list(_orte(3)), _orte(3), [(_alarm(), [])], lang="en")
    assert leer[0].scope_label == t("warnung.zeit.unbekannt", "en")
    assert leer[0].sms_scope == t("warnung.zeit.unbekannt", "de")
    voll = oa.build_compare_official_alert_notices(
        list(_orte(3)), _orte(3),
        [(_alarm(), list(_orte(3))), (_alarm("rain", 3, "Starkregen"), list(_orte(3)))], lang="en")
    assert oa.render_official_alert_subject(voll, prefix=PREFIX, lang="en").startswith(
        f"[{PREFIX}] {t('warnung.umfang.alle_orte', 'en')} · ")
    assert t("warnung.satz.deckt_orte.other", "en") in _plain(voll)
    assert voll[0].sms_scope == "alleOrte"


@pytest.mark.parametrize("gesamt", [True, False])
def test_viele_orte_als_mengenangabe_englisch(gesamt):
    from dataclasses import replace

    orte = _orte(4)
    notices = oa.build_compare_official_alert_notices(list(orte), orte, [(_alarm(), ["o0", "o1", "o2"])],
                                                      lang="en")
    if not gesamt:
        notices = [replace(n, scope_total=None) for n in notices]
    menge = (t("vergleich.warn.n_von_m_orten", "en", n=3, gesamt=4) if gesamt
             else t("warnung.umfang.anzahl_orte", "en", count=3))
    assert f"[{PREFIX}] {menge} · " in oa.render_official_alert_subject(notices, prefix=PREFIX, lang="en")
    typen = t("warnung.gefahr.wind_gust", "en")
    assert t("warnung.kopf.gemeldet_fuer", "en", typen=typen, umfang=menge) in _plain(notices)


def test_kritischere_warnung_bei_einheitlichem_umfang_englisch():
    notices = oa.build_compare_official_alert_notices(
        list(_orte(3)), _orte(3), [(_alarm(level=4), ["o1"]), (_alarm("rain", 2, "Starkregen"), ["o1"])],
        lang="en")
    satz = t("warnung.satz.kritischer", "en",
             typ=f"{t('warnung.gefahr.wind_gust', 'en')} ({t('warnung.stufe.rot', 'en')})")
    assert satz in _plain(notices)


def test_teilstrecke_mit_km_angabe_und_freier_rest_englisch():
    from dataclasses import replace

    notices = oa.build_official_alert_notices(None, [(_alarm(), ["2"])], segment_km={"2": (3.0, 8.0)},
                                              lang="en")
    assert t("warnung.satz.nur_route", "en", ort=notices[0].scope_label) in _plain(notices)
    frei = [replace(notices[0], free_chips=["Segment 1", "Segment 3"])]
    abschnitte = t("warnung.liste.und", "en", liste="Segment 1", letztes="Segment 3")
    notiz = t("warnung.zeile.route_frei", "en", abschnitte=abschnitte)
    assert notiz in _plain(frei)
    html = oa.render_official_alert_html(frei, source_label="GeoSphere Austria", stand_at=STAND, tz=TZ,
                                         lang="en")
    assert notiz in sichtbar(html)


def test_quellen_ohne_kennung_und_lawinendienste_englisch():
    assert oa.official_alert_source_label(None, lang="en") == t("warnung.quelle.amtlich", "en")
    assert oa.official_alert_source_label(None) == t("warnung.quelle.amtlich", "de")
    assert oa.official_alert_source_label("avalanche_report", lang="en") == t("warnung.quelle.lawinendienste", "en")
    assert oa.official_alert_source_label("avalanche_report") == t("warnung.quelle.lawinendienste", "de")


def test_deutsche_gefahrenwoerter_fuer_bestandsimporteure():
    """`_HAZARD_LABELS` speist den Gefahren-Katalog der API (`/api/sms-symbols`)."""
    from api.routers.config import get_sms_symbols

    labels = {h["hazard"]: h["label"] for h in get_sms_symbols()["hazards"]}
    assert labels["thunderstorm"] == t("warnung.gefahr.thunderstorm", "de")
    assert labels["wildfire_risk"] == t("warnung.gefahr.wildfire_risk", "de")


def test_entwarnung_aus_deutschem_builder_englisch_gerendert():
    """Notice in Builder-Sprache de, Darstellung en: die Gefahr folgt der Darstellung."""
    from tests.helpers.amtliche_warnungen_fixture import allclears

    de_ac = list(reversed(allclears(None)))  # "beendet" zuerst
    assert de_ac[0].hazard_label == t("warnung.gefahr.extreme_heat", "de")
    assert allclears("en")[0].hazard_label == t("warnung.gefahr.thunderstorm", "en")
    hitze_en = t("warnung.gefahr.extreme_heat", "en")
    betreff = oa.render_official_allclear_subject_part(de_ac, lang="en")
    assert betreff == t("warnung.entwarnung.betreff", "en", gefahr=hitze_en,
                        uebergang=t("warnung.entwarnung.beendet", "en")) + " " + t(
        "warnung.kopf.weitere", "en", count=1)
    assert oa.official_allclear_lines(de_ac, lang="en")[0].startswith(f"{hitze_en} · ")


def test_entwarnung_im_ortsvergleich_ohne_orte():
    from types import SimpleNamespace

    ac = SimpleNamespace(kind="ended", alert=_alarm(), scope_ids=[], old_rank=3, new_rank=0,
                         old_level=3, new_level=0)
    n = oa.build_official_allclear_notices([ac], {}, lang="en")[0]
    assert n.scope_label == t("warnung.umfang.ort", "en")
    assert n.sms_scope == t("warnung.umfang.ort", "de")


def test_ortsvergleich_banner_stufe_und_quelle_englisch():
    from dataclasses import replace

    from output.renderers.email.compare_html import render_compare_html
    from tests.helpers.vergleichs_mail_fixture import build_result

    result = build_result()
    brand = _alarm("wildfire_risk", 4, "Waldbrand-Gefahr — Stufe 4", source="meteo_forets")
    orte = [replace(loc, official_alerts=[brand]) if i == 0 else loc for i, loc in enumerate(result.locations)]
    html = "\n".join(sichtbar(render_compare_html(replace(result, locations=orte), lang="en")))
    stufe = t("warnung.stufe.rot", "en")
    assert t("vergleich.warn.hoechste_stufe", "en", stufe=stufe, ort=orte[0].location.name) in html
    assert oa.official_alert_source_label("meteo_forets", lang="en") in html


def test_briefing_mail_warnblock_quelle_englisch():
    from dataclasses import replace

    from output.renderers.trip_report import TripReportFormatter
    from tests.helpers.briefing_html_sprache_fixture import TZ as BTZ, _segment

    brand = _alarm("wildfire_risk", 3, "Waldbrand-Gefahr — Stufe 3", source="meteo_forets")
    seg = replace(_segment(), official_alerts=[brand])
    report = TripReportFormatter().format_email([seg], "Corsica North", "morning", tz=BTZ, lang="en")
    html = "\n".join(sichtbar(report.email_html))
    assert oa.official_alert_source_label("meteo_forets", lang="en") in html
    assert t("warnung.gefahr.wildfire_risk", "en") in html


def test_briefing_telegram_warnung_voller_umfang_und_quelle_englisch():
    from types import SimpleNamespace

    from output.renderers.narrow import _official_alert_bubble
    from tests.helpers.telegram_briefing_fixture import TZ as TTZ, _segment

    brand = _alarm("wildfire_risk", 3, "Waldbrand-Gefahr — Stufe 3", source="meteo_forets")
    segs = [_segment(1, (0.0, 8.4), (7, 12), [brand]), _segment("Ziel", (8.4, 14.2), (12, 16), [brand])]
    trip = SimpleNamespace(all_waypoints=[0, 1], alert_channel_thresholds={})
    text = _official_alert_bubble(segs, TTZ, trip, lang="en").text
    assert f" · {t('warnung.umfang.gesamte_route', 'en')} · " in text
    assert oa.official_alert_source_label("meteo_forets", lang="en") in text
