"""#3047 Runde 7, Paket p2 (Orte-Mail): Befunde B-OM-1 und B-OM-2 (AC-28).

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md,
"Nachtrag Runde 7", AC-28: Given amtliche Warnungen sind aus bzw. der
Warndienst ist nicht erreichbar / When die Orts-Mail erzeugt wird / Then zeigt
das HTML keine leere Warnzeile, und der Klartext traegt denselben Hinweis
"nicht abrufbar" wie das HTML.

Echter Weg: rohes Preset-JSON -> echter Loader -> ``send_one_compare_preset``
(``mail_sink`` mit HTML und Klartext derselben Mail), Helfer
``tests/helpers/einstellung_gleich_mail_orte.py``. Die Wetter-Naht
(``build_result``) meldet fuer den ersten Ort "Warndienst nicht erreichbar"
(``official_alerts_unavailable``). Je Fall zwei Nutzer, DE und EN; die
erwarteten Texte stehen von Hand im Test.
"""
from __future__ import annotations

import re

import pytest

from tests.helpers.einstellung_gleich_mail_orte import _tabellen, preset_dict, sende_orte_mail

#: von Hand: Hinweistext "nicht abrufbar" (Katalog mail.hinweis.warnungen_nicht_abrufbar.text)
HINWEIS = {
    "de": "Amtliche Warnungen aktuell nicht abrufbar — bitte selbst pruefen.",
    "en": "Official warnings are currently unavailable — please check yourself.",
}
#: von Hand: HTML-Kasten-Titel desselben Hinweises
HTML_TITEL = {
    "de": "Amtliche Warnungen aktuell nicht abrufbar",
    "en": "Official warnings currently unavailable",
}
#: von Hand: feste erste Zeile der Vergleichstabelle
WARNZEILE = {"de": "Amtliche Warnungen", "en": "Official warnings"}


def _uebersicht_zeilenkoepfe(html: str) -> list[str]:
    for _pos, zeilen in _tabellen(html):
        if zeilen and zeilen[0] and zeilen[0][0] in ("Metrik", "Metric"):
            return [z[0] for z in zeilen[1:] if z]
    raise AssertionError("Vergleichstabelle nicht im HTML gefunden")


def _preset(**top) -> dict:
    p = preset_dict("basis")
    p["id"] = "om-r7"
    p["name"] = "OM Runde 7"
    p.update(top)
    return p


@pytest.mark.parametrize("lang", ["de", "en"])
def test_om1_klartext_traegt_hinweis_nicht_abrufbar_wie_html(lang):
    """B-OM-1: Warndienst eines Ortes nicht erreichbar -> HTML zeigt den Kasten,
    der Klartext DERSELBEN Mail traegt denselben Hinweis (genau einmal)."""
    uids = set()
    for _ in range(2):
        m = sende_orte_mail(_preset(), language=lang)
        uids.add(m.uid)
        assert HTML_TITEL[lang] in m.html, f"Vorbedingung: HTML-Hinweis fehlt ({lang})"
        assert m.plain.count(HINWEIS[lang]) == 1, (
            f"B-OM-1 ({lang}): Klartext ohne Hinweis 'nicht abrufbar':\n{m.plain[:900]}")
        kopf_ende = m.plain.index("-" * 50)
        assert m.plain.index(HINWEIS[lang]) < kopf_ende, "Hinweis steht vor den Ortsbloecken"
    assert len(uids) == 2


@pytest.mark.parametrize("lang", ["de", "en"])
def test_om2_warnungen_aus_keine_leere_warnzeile(lang):
    """B-OM-2: Schalter "Amtliche Warnungen" aus -> die Vergleichstabelle hat
    keine Zeile "Amtliche Warnungen" (wie der Klartext); an -> erste Zeile."""
    for _ in range(2):
        aus = sende_orte_mail(_preset(official_alerts_enabled=False), language=lang)
        koepfe = _uebersicht_zeilenkoepfe(aus.html)
        assert koepfe, "Vorbedingung: Uebersicht hat Zeilen"
        assert WARNZEILE[lang] not in koepfe, f"B-OM-2 ({lang}): leere Warnzeile: {koepfe}"
        assert not re.search(r"^   ⚠️ ", aus.plain, re.M), "Klartext ohne Warnzeile je Ort"
        an = sende_orte_mail(_preset(official_alerts_enabled=True), language=lang)
        assert _uebersicht_zeilenkoepfe(an.html)[0] == WARNZEILE[lang]
        nie = sende_orte_mail(_preset(), language=lang)
        assert _uebersicht_zeilenkoepfe(nie.html)[0] == WARNZEILE[lang], "nie eingestellt = an"
        assert aus.uid != an.uid != nie.uid
