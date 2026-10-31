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
