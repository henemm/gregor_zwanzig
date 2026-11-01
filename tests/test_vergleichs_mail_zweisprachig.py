"""Ortsvergleich zweisprachig: Mail, Klartext, Telegram (Issue #2666, AC-1/2/4/6).

SPEC: docs/specs/modules/i18n_p4_vergleichs_mail_2666.md

Kern-Schicht: echte Renderer, deterministische Fixture
(``tests/helpers/vergleichs_mail_fixture.py``), kein Mock. Erwartete Texte
kommen aus dem Katalog (``t(key, lang)``) bzw. dem Metrik-Register, nie aus
Literalen. Die Ratsche ist VERHALTEN: die englische Ausgabe enthaelt keinen
deutschen Katalogtext und kein Umlaut-Wort (Ausnahmen unten, je mit Paket).
SMS bleibt in jeder Sprache byte-gleich (PO-Korrektur 2026-10-31).
"""
from __future__ import annotations

import html as _html
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from i18n import t
from tests.helpers.vergleichs_mail_fixture import (
    ORTSNAMEN, PRESET_NAME, TRENNER, build_result, golden_pfad, render_kanaele, render_mail,
)

KATALOG = Path(__file__).resolve().parents[1] / "src" / "i18n" / "messages"
# Daten des Aufrufers (keine Renderertexte): Orts-/Preset-Namen, Fehlertext, Warnung.
_DATEN = (*ORTSNAMEN, "Brenner", PRESET_NAME, "Zeitueberschreitung beim Abruf",
          "Ort Brenner nicht erreichbar")


def sichtbar(html: str) -> list[str]:
    s = re.sub(r"<head>.*?</head>", "", html, flags=re.S)
    s = re.sub(r"<[^>]+>", "\n", s)
    return [z.strip() for z in _html.unescape(s).split("\n") if z.strip()]


def _de_fragmente() -> set[str]:
    """Deutsche Bruchstuecke aller Katalogtexte, die dieses Paket verwendet."""
    out: set[str] = set()
    for bereich, praefix in (("vergleich", "vergleich."), ("allgemein", "allgemein."),
                             ("mail", "mail.legende.")):
        de = json.loads((KATALOG / "de" / f"{bereich}.json").read_text(encoding="utf-8"))
        en = json.loads((KATALOG / "en" / f"{bereich}.json").read_text(encoding="utf-8"))
        for key, wert in de.items():
            if not key.startswith(praefix):
                continue
            for teil in re.split(r"\{[a-z_]+\}", wert):
                teil = teil.strip(" :—…·.,+→←\n")
                if len(teil) >= 4 and teil not in en.get(key, ""):
                    out.add(teil)
    return out


def _ohne_ausnahmen(zeilen: list[str]) -> list[str]:
    """Entfernt Daten und Texte anderer Pakete: Eyebrow ``ORT`` vor dem
    Ortsnamen, Erkennungsmarke des Pflicht-Validators ``email_spec_validator.py``
    (``>ORT</span>``), Aenderung dort = Blocker. Die Befehlszeilen sind seit
    P10 (#2673) englisch und keine Ausnahme mehr."""
    out = []
    for z in zeilen:
        if z == "ORT":
            continue
        for d in _DATEN:
            z = z.replace(d, "")
        out.append(z)
    return out


def treffer(zeilen: list[str]) -> list[str]:
    frags = _de_fragmente()
    return [z for z in _ohne_ausnahmen(zeilen)
            if re.search(r"[äöüÄÖÜß]", z) or any(f in z for f in frags)]


def _englisch_alles() -> list[str]:
    html, text = render_mail("en")
    zeilen = sichtbar(html) + text.splitlines()
    for kanal in render_kanaele("en")[:-1]:  # ohne SMS (bleibt deutsch)
        zeilen += kanal.splitlines()
    return zeilen


# --------------------------------------------------------------------------- AC-1


def test_ac1_ueberschriften_englisch_aus_dem_katalog():
    html, text = render_mail("en")
    vis = "\n".join(sichtbar(html))
    for key in ("vergleich.kopf.titel", "vergleich.zeile.amtliche_warnungen",
                "vergleich.ausblick.titel", "vergleich.fuss.naechster_versand",
                "vergleich.abschnitt.uebersicht", "vergleich.uebersicht.titel",
                "vergleich.abschnitt.stunden", "vergleich.stunden.titel",
                "vergleich.fuss.dieses_abo", "vergleich.fuss.app_oeffnen",
                "vergleich.ausblick.eyebrow", "vergleich.uebersicht.spalte_metrik"):
        assert t(key, "en") in vis, key
        assert t(key, "en") != t(key, "de"), key
    for key in ("vergleich.kopf.titel", "vergleich.ausblick.titel",
                "vergleich.stunden.klartext_titel"):
        assert t(key, "en") in text, key
    assert '<html lang="en">' in html
    assert f"<title>{t('vergleich.kopf.titel_kurz', 'en')}</title>" in html


def test_ac1_kein_deutscher_katalogtext_in_der_englischen_ausgabe():
    assert treffer(_englisch_alles()) == []


def test_ac1_ratsche_greift_auf_deutsche_ausgabe():
    """Gegenprobe der Ratsche: dieselbe Pruefung findet in Deutsch Treffer."""
    html, text = render_mail("de")
    assert len(treffer(sichtbar(html) + text.splitlines())) > 20


def test_ac1_kopf_datum_und_fuss_englisch():
    from i18n.format import fmt_date_numeric, fmt_weekday

    result = build_result()
    html, text = render_mail("en")
    d = result.target_date
    assert f"{fmt_weekday(d, 'en')}, {fmt_date_numeric(d, 'en')}" in sichtbar(html)
    assert fmt_date_numeric(d, "en") == "29 Oct 2026"
    assert t("vergleich.kopf.datum", "en", datum=f"{fmt_weekday(d, 'en', kurz=False)}, "
             f"{fmt_date_numeric(d, 'en')}") in text.splitlines()
    zeile = t("vergleich.fuss.abo_zeile", "en", n=4, profil=t("mail.profil.wandern", "en"))
    assert zeile in sichtbar(html)
    assert any(z.startswith(fmt_date_numeric(d, "en")) for z in sichtbar(html)), "Naechster Versand"


def test_ac1_zellwoerter_gewitter_und_niederschlagsart_englisch():
    from app.thunder_scale import format_hail_note, thunder_label, thunder_signal_label
    from app.models import ThunderLevel

    html, text = render_mail("en")
    gewitter = " · ".join([thunder_label(ThunderLevel.MED, lang="en"),
                           ", ".join(thunder_signal_label(s, lang="en") for s in ("cape", "blitzdichte")),
                           format_hail_note(True, lang="en")])
    assert gewitter in sichtbar(html)
    assert f"Thdr {gewitter}" in text
    for key in ("rain", "snow", "mixed"):
        wort = t(f"vergleich.niederschlagsart.{key}", "en")
        assert wort != t(f"vergleich.niederschlagsart.{key}", "de")
        assert f"PType {wort}" in text, key
    telegram = render_kanaele("en")[0]
    assert f"{t('vergleich.zeile.thunder_max', 'en')} {gewitter}" in telegram
    assert f"{t('vergleich.zeile.precip_type', 'en')} {t('vergleich.niederschlagsart.mixed', 'en')}" in telegram


# --------------------------------------------------------------------------- AC-2


def _erwartete_uebersicht(lang: str) -> list[str]:
    from app.metric_catalog import aggregation_label, get_metric
    from output.renderers.email.compare_html import CV2_METRICS

    zeilen = [m for m in CV2_METRICS if m.get("metric_id")]
    namen = [get_metric(m["metric_id"]).label(lang) for m in zeilen]
    doppelt = {n for n in namen if namen.count(n) > 1}
    return [t("vergleich.zeile.amtliche_warnungen", lang)] + [
        f"{n} {aggregation_label(m['aggregation'], lang)}" if n in doppelt else n
        for m, n in zip(zeilen, namen)
    ]


def _tabellen(html: str) -> list[list[list[str]]]:
    out = []
    for tab in re.findall(r"<table[^>]*>(.*?)</table>", html, re.S):
        zeilen = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S):
            zellen = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)
            zeilen.append([_html.unescape(re.sub(r"<[^>]+>", "", z)).strip() for z in zellen])
        out.append(zeilen)
    return out


def _stundenkoepfe(html: str, zeit: str) -> list[list[str]]:
    return [tab[0] for tab in _tabellen(html) if tab and tab[0] and tab[0][0] == zeit]


def test_ac2_stundenkoepfe_bleiben_kurzform_erste_spalte_time():
    html_de, _ = render_mail("de")
    html_en, _ = render_mail("en")
    de = _stundenkoepfe(html_de, t("vergleich.stunden.zeit", "de"))
    en = _stundenkoepfe(html_en, t("vergleich.stunden.zeit", "en"))
    assert len(en) == 3 and len(de) == 3
    assert t("vergleich.stunden.zeit", "en") == "Time"
    assert [k[1:] for k in de] == [k[1:] for k in en]
    assert 'text-align:left;padding:6px 4px' in html_en.split(">Time</th>")[0][-400:]


def test_ac2_uebersichtszeilen_tragen_den_englischen_registernamen():
    html_en, text_en = render_mail("en")
    uebersicht = next(tab for tab in _tabellen(html_en)
                      if len(tab) > 1 and tab[1][0] == t("vergleich.zeile.amtliche_warnungen", "en"))
    assert [z[0] for z in uebersicht[1:]] == _erwartete_uebersicht("en")
    assert uebersicht[0][0] == t("vergleich.uebersicht.spalte_metrik", "en")
    for name in _erwartete_uebersicht("en")[1:]:
        assert f"   {name}: " in text_en, name


def test_ac2_englische_zeilennamen_beispiele():
    namen = _erwartete_uebersicht("en")
    assert "Precipitation" in namen and "Wind gusts" in namen


# --------------------------------------------------------------------------- AC-4


def _zwoelf_orte():
    result = build_result(mit_fehlerort=False)
    vorlage = result.locations
    orte = []
    for i in range(12):
        lr = vorlage[i % 3]
        # lange Namen, damit zwoelf Ortsbloecke die 4096 Zeichen sprengen
        name = f"{lr.location.name} Huette Nummer {i:02d} " + "Hochgebirgsstation " * 10
        ort = replace(lr.location, id=f"ort-{i}", name=name.strip())
        orte.append(replace(lr, location=ort))
    return replace(result, locations=orte)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac4_telegram_grenze_und_ueberlaufhinweis_am_ende(lang):
    from output.renderers.comparison import render_compare_telegram
    from tests.helpers.vergleichs_mail_fixture import KANAL_METRIKEN

    text = render_compare_telegram(_zwoelf_orte(), enabled_metrics=KANAL_METRIKEN,
                                   preset_name=PRESET_NAME, unresolved_count=1, lang=lang)
    assert len(text) <= 4096
    hinweise = [t("vergleich.telegram.uebersprungen", lang, n=n) for n in range(1, 12)]
    assert any(text.endswith("\n" + h) for h in hinweise), text[-200:]


def test_ac4_sms_in_jeder_sprache_byte_gleich_und_in_der_grenze():
    from output.renderers.channel_layout import CHANNEL_LIMITS
    from output.renderers.comparison import render_compare_sms

    sms = render_compare_sms(_zwoelf_orte())
    assert len(sms) <= CHANNEL_LIMITS["sms"]["max_chars"]
    soll = golden_pfad("telegram_sms.de.txt").read_text(encoding="utf-8").split(TRENNER)[-1]
    assert render_kanaele("en")[-1] == soll == render_kanaele("de")[-1]
    with pytest.raises(TypeError):
        render_compare_sms(build_result(), lang="en")  # kein Sprachparameter (PO 2026-10-31)


def test_ac4_telegram_hinweise_englisch():
    from output.renderers.channel_layout import selection_gap_notice, telegram_metric_notice

    voll, leer, keine = render_kanaele("en")[:3]
    assert "   " + telegram_metric_notice(3, context="vergleich", lang="en") in voll.splitlines()
    assert "   " + selection_gap_notice(1, scope="ort", lang="en") in voll.splitlines()
    assert telegram_metric_notice(3, context="vergleich", lang="en") != telegram_metric_notice(
        3, context="vergleich")
    assert "   " + t("vergleich.ort.fehler", "en", fehler="Zeitueberschreitung beim Abruf") in voll
    assert voll.splitlines()[0] == f"{t('vergleich.kopf.titel', 'en')} — {PRESET_NAME}"
    assert voll.splitlines()[1] == t("vergleich.kopf.datum", "en", datum="29 Oct 2026")
    assert "   " + t("vergleich.telegram.keine_werte", "en") in leer.splitlines()
    assert leer.splitlines()[0] == t("vergleich.kopf.titel", "en")
    assert keine == t("vergleich.allgemein.keine_daten", "en")


def test_ac4_notice_bausteine_englisch_und_deutsch_unveraendert():
    from output.renderers.channel_layout import selection_gap_notice, telegram_metric_notice

    assert selection_gap_notice(2, scope="vergleich") == (
        "… +2 gewählte Wettergrößen ohne Wert in diesem Vergleich")
    assert selection_gap_notice(2, scope="ort") == "… +2 gewählte Wettergrößen ohne Wert an diesem Ort"
    assert telegram_metric_notice(2, context="route") == (
        "… +2 weitere Wettergrößen nur als Tageswert (Telegram-Limit)")
    for lang in ("de", "en"):
        assert selection_gap_notice(0, scope="ort", lang=lang) == ""
        assert telegram_metric_notice(0, context="route", lang=lang) == ""
    en = [selection_gap_notice(2, scope="vergleich", lang="en"),
          selection_gap_notice(2, scope="ort", lang="en"),
          telegram_metric_notice(2, context="route", lang="en"),
          telegram_metric_notice(2, context="vergleich", lang="en")]
    assert len(set(en)) == 4 and treffer(en) == []


def test_klartext_und_telegram_ohne_orte_englisch():
    from app.user import ComparisonResult
    from output.renderers.comparison import render_comparison_text

    leer = ComparisonResult(locations=[], time_window=(9, 16), target_date=build_result().target_date)
    assert render_comparison_text(leer, lang="en") == t("vergleich.allgemein.keine_daten", "en")
    assert render_comparison_text(leer) == "Keine Vergleichsdaten verfügbar."


# --------------------------------------------------------------------------- AC-6


def test_ac6_reihenfolge_en_de_en_ohne_zustand():
    gold_de = (golden_pfad("ortsvergleich_3orte.de.html").read_text(encoding="utf-8"),
               golden_pfad("ortsvergleich_3orte.de.txt").read_text(encoding="utf-8"))
    gold_en = (golden_pfad("ortsvergleich_3orte.en.html").read_text(encoding="utf-8"),
               golden_pfad("ortsvergleich_3orte.en.txt").read_text(encoding="utf-8"))
    erst = render_mail("en")
    zweit = render_mail("de")
    dritt = render_mail("en")
    assert zweit == gold_de
    assert erst == gold_en == dritt
    assert treffer(sichtbar(erst[0]) + erst[1].splitlines()) == []


def test_zwei_nutzer_zwei_sprachen(tmp_path):
    """Sprachaufloesung je Nutzer -> Renderer: Nutzer A (en), Nutzer B (kein Feld)."""
    from i18n import resolve_user_lang

    for uid, daten in (("p4-anna", {"language": "en"}), ("p4-bernd", {})):
        pfad = tmp_path / "users" / uid / "user.json"
        pfad.parent.mkdir(parents=True)
        pfad.write_text(json.dumps(daten), encoding="utf-8")
    ergebnisse = {}
    for uid in ("p4-anna", "p4-bernd", "p4-anna"):
        lang = resolve_user_lang(uid, data_dir=tmp_path)
        ergebnisse.setdefault(uid, []).append((render_mail(lang), render_kanaele(lang)))
    anna, bernd = ergebnisse["p4-anna"], ergebnisse["p4-bernd"]
    assert anna[0] == anna[1]
    assert anna[0][0][0] == golden_pfad("ortsvergleich_3orte.en.html").read_text(encoding="utf-8")
    assert bernd[0][0][0] == golden_pfad("ortsvergleich_3orte.de.html").read_text(encoding="utf-8")
    assert anna[0][1][-1] == bernd[0][1][-1], "SMS bleibt fuer beide Nutzer gleich"
    assert anna[0][1][0] != bernd[0][1][0], "Telegram folgt der Nutzersprache"


# ------------------------------------------------- amtliche Warnungen: P4-Rahmen


def _mit_warnungen(*alerts_je_ort):
    from services.official_alerts.models import OfficialAlert

    result = build_result(mit_fehlerort=False)
    orte = []
    for lr, alerts in zip(result.locations, alerts_je_ort):
        orte.append(replace(lr, official_alerts=[
            OfficialAlert(source="geosphere", hazard=h, level=lvl, label=f"Label {h}",
                          native_level=nat, scale="eaws" if nat else "awareness")
            for h, lvl, nat in alerts
        ]))
    return replace(result, locations=orte)


@pytest.mark.parametrize("hazard,level,native,key,params", [
    ("extreme_heat", 3, None, "vergleich.warnchip.hitze", {}),
    ("wildfire_risk", 3, None, "vergleich.warnchip.brand", {"stufe": 3}),
    ("access_ban", 2, None, "vergleich.warnchip.zugang", {}),
    ("flood", 3, None, "vergleich.warnchip.hochwasser", {}),
    ("avalanche", 3, None, "vergleich.warnchip.lawine", {}),
    ("avalanche_bulletin", 3, 3, "vergleich.warnchip.lawine_stufe", {"stufe": 3}),
])
def test_warnchips_der_uebersicht_englisch(hazard, level, native, key, params):
    from output.renderers.email.compare_html import render_compare_html

    result = _mit_warnungen([(hazard, level, native)], [], [])
    html_en = render_compare_html(result, lang="en")
    html_de = render_compare_html(result)
    chip_en, chip_de = t(key, "en", **params), t(key, "de", **params)
    assert chip_en != chip_de
    assert f">{_html.escape(chip_en)}</div>" in html_en
    assert f">{_html.escape(chip_de)}</div>" in html_de


def test_warnbanner_rahmen_englisch():
    from output.renderers.email.compare_html import render_compare_html

    result = _mit_warnungen([("extreme_heat", 3, None)], [("extreme_heat", 2, None)], [])
    html_en = render_compare_html(result, lang="en")
    assert t("vergleich.warn.n_von_m_orten", "en", n=2, gesamt=3) in html_en
    assert "von 3 Orten" not in html_en
    from output.renderers.alert.official_alerts import _LEVEL_WORDS

    stufe = _LEVEL_WORDS[3][1]  # Stufenwort selbst: P6 (#2668)
    assert t("vergleich.warn.hoechste_stufe", "en", stufe=stufe, ort="Innsbruck") in html_en
    assert f"höchste Stufe {stufe} · Innsbruck" in render_compare_html(result)
    lawine = _mit_warnungen([("avalanche_bulletin", 4, 5)], [], [])
    assert t("vergleich.warn.lawinenstufe", "en", stufe=5, ort="Innsbruck") in render_compare_html(
        lawine, lang="en")
    assert "Lawinenstufe 5 · Innsbruck" in render_compare_html(lawine)


def test_legende_warnkuerzel_englisch():
    html_en, _ = render_mail("en")
    assert t("vergleich.legende.warn_kuerzel", "en") in sichtbar(html_en)
    for key in ("mail.legende.risk_gruen", "mail.legende.risk_gelb",
                "mail.legende.risk_orange", "mail.legende.risk_rot"):
        assert t(key, "en") in sichtbar(html_en), key


# ------------------------------------- weitere Render-Wege (Mutations-Gegenprobe)


def test_gewaehlte_metriken_uebersicht_englisch():
    """Pfad mit gesetzter Auswahl (``enabled_metrics`` als Liste)."""
    from app.metric_catalog import get_metric
    from output.renderers.email.compare_html import render_compare_html

    auswahl = ["precip_sum", "gust_max"]
    html_en = render_compare_html(build_result(), enabled_metrics=auswahl, lang="en")
    uebersicht = next(tab for tab in _tabellen(html_en)
                      if len(tab) > 1 and tab[1][0] == t("vergleich.zeile.amtliche_warnungen", "en"))
    assert [z[0] for z in uebersicht[2:]] == [
        get_metric("precipitation").label("en"), get_metric("gust").label("en")]


def test_ausblick_leere_auswahl_zeigt_zustand_englisch():
    """Ausblick eingeschaltet, Auswahl bewusst leer -> benannter Zustand."""
    from output.renderers.email.compare_html import render_compare_html
    from output.renderers.email.outlook_state_hint import OutlookState, outlook_state_text

    html_en = render_compare_html(build_result(mit_fehlerort=False), outlook_enabled=True,
                                  outlook_metrics=[], lang="en")
    vis = sichtbar(html_en)
    assert outlook_state_text(OutlookState.UNAVAILABLE, lang="en") in vis
    assert t("vergleich.ausblick.eyebrow", "en") in vis
    assert t("vergleich.ausblick.titel", "en") in vis
    assert t("vergleich.ausblick.eyebrow", "de") not in vis


def test_spaltenlegende_des_ausblicks_englisch():
    """Ohne Stundenspalten traegt die Spalten-Legende nur die Ausblick-Kuerzel."""
    from output.renderers.email.compare_html import render_compare_html
    from output.renderers.email.helpers import format_column_legend, outlook_legend_pairs

    html_en = render_compare_html(build_result(mit_fehlerort=False), hourly_metrics=[],
                                  outlook_enabled=True, lang="en")
    erwartet = format_column_legend(outlook_legend_pairs(None, lang="en"), lang="en")
    assert erwartet and erwartet in sichtbar(html_en)
    assert erwartet != format_column_legend(outlook_legend_pairs(None))


def test_kollisionszusatz_der_langform_englisch():
    """``derive_row_labels`` (oeffentlich): gleicher Name, verschiedene Auswertung.
    Im gerenderten Ortsvergleich kollidieren heute nur min/max (in beiden
    Sprachen gleich), deshalb hier direkt am oeffentlichen Baustein."""
    from app.metric_catalog import aggregation_label, get_metric
    from output.renderers.email.compare_html import derive_row_labels

    zeilen = [{"key": "a", "metric_id": "cloud_total", "aggregation": "avg"},
              {"key": "b", "metric_id": "cloud_total", "aggregation": "sum"}]
    name = get_metric("cloud_total").label("en")
    assert [z["label"] for z in derive_row_labels(zeilen, form="long", lang="en")] == [
        f"{name} {aggregation_label('avg', 'en')}", f"{name} {aggregation_label('sum', 'en')}"]
    assert aggregation_label("avg", "en") != aggregation_label("avg", "de")


def test_telegram_ueberlauf_degeneriert_englisch():
    """Schon der erste Ortsblock sprengt 4096 Zeichen: Hinweis trotzdem englisch."""
    from output.renderers.comparison import render_compare_telegram

    result = build_result(mit_fehlerort=False)
    riese = replace(result.locations[0], location=replace(
        result.locations[0].location, name="Riesenname " * 500))
    text = render_compare_telegram(replace(result, locations=[riese, result.locations[1]]),
                                   lang="en")
    assert len(text) <= 4096
    assert text.endswith("\n" + t("vergleich.telegram.uebersprungen", "en", n=1))


def _telegram_orte(namen: list[str]):
    result = build_result(mit_fehlerort=False)
    vorlage = result.locations
    orte = [replace(vorlage[i % 3], location=replace(vorlage[i % 3].location, id=f"o-{i}", name=n))
            for i, n in enumerate(namen)]
    return replace(result, locations=orte)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_telegram_einpassen_genau_am_limit_zaehlt_neun_nicht_zehn(lang):
    """F001: zwoelf Orte, der dritte Block passt mit dem Hinweis "+9" GENAU auf
    4096 Zeichen. Mit falsch gezaehltem Hinweis ("+10", ein Zeichen laenger)
    fiele er heraus und die Nachricht nennte "+10"."""
    from output.renderers.comparison import render_compare_telegram

    namen = [f"Ort {i:02d} " + "Hochgebirgsstation " * 50 for i in range(12)]
    drei = render_compare_telegram(_telegram_orte(namen[:3]), lang=lang)
    hinweis9 = "\n" + t("vergleich.telegram.uebersprungen", lang, n=9)
    luecke = 4096 - len(drei) - len(hinweis9)
    assert luecke > 0, "Testaufbau: drei Bloecke muessen unter das Limit passen"
    namen[2] = namen[2].rstrip() + "x" * (luecke + 1)  # +1: rstrip entfernte ein Leerzeichen
    text = render_compare_telegram(_telegram_orte(namen), lang=lang)
    assert len(text) == 4096
    assert text.endswith(hinweis9), text[-120:]


@pytest.mark.parametrize("n", [1, 2])
def test_telegram_hinweise_singular_plural(n):
    """F002: englisch Singular bei 1, Plural bei 2; deutsch wortgleich wie vorher."""
    from output.renderers.comparison import render_compare_telegram
    from tests.helpers.vergleichs_mail_fixture import KANAL_METRIKEN

    result = build_result(mit_fehlerort=False)
    en = render_compare_telegram(result, enabled_metrics=KANAL_METRIKEN[:8],
                                 unresolved_count=n, lang="en").splitlines()
    de = render_compare_telegram(result, enabled_metrics=KANAL_METRIKEN[:8],
                                 unresolved_count=n).splitlines()
    wert = "value" if n == 1 else "values"
    assert f"   … +{n} selected weather {wert} without data at this location" in en
    # 8 Groessen, 7 Plaetze: immer genau eine verdraengt -> Singular
    assert "   … +1 more weather value per location (Telegram limit) — full version by email" in en
    assert f"   … +{n} gewählte Wettergrößen ohne Wert an diesem Ort" in de
    assert "   … +1 weitere Wettergrößen je Ort (Telegram-Limit) — vollständig per E-Mail" in de


def test_vortag_unbekannte_kennung_faellt_auf_neutrales_wort():
    """Schutz fuer kuenftige Kennungen ohne eigenes Richtungswort."""
    from services.day_comparison import _direction_word

    assert _direction_word("unbekannt", True, "en") == t("vergleich.vortag.anders", "en")
    assert _direction_word("unbekannt", False, "de") == "anders"
