"""#3047 Runde 9 (Abnahme 8, LOW): Orte-Altbestand ohne ``active_metrics`` und
ohne ``outlook_metrics`` -- der 3-Tages-Ausblick stellt sich im HTML anders dar
als im Klartext derselben Mail ("Temp Minimum"/"Temp Maximum" als zwei Spalten
gegen "Temp 6/11") und anders als die gleichwertige explizite Konfiguration.

Massstab (Konzept einstellungen_neu.md §5 P6/P8, Spec AC-5/AC-13/AC-21,
ADR-0097 ein Code): der Altbestand zeigt genau das, was der Editor fuer ihn als
aktiv anzeigt (``editor_standard.json`` Zustand ``nie_eingestellt``: Temperatur,
Niederschlag, Regenwahrscheinlichkeit, Wind, Boeen, Gewitter). Dieselbe Liste
ausdruecklich gespeichert ist die Referenz -- der Altbestand darf sich davon
nicht unterscheiden, HTML und Klartext tragen dieselben Zeilen in derselben Form.

Echter Weg: rohes Preset-JSON -> Loader -> ``send_one_compare_preset`` mit
``mail_sink`` (HTML und Klartext aus DERSELBEN Mail), zwei Nutzer, DE und EN.
Kein Mock, kein patch; Naht nur an Transport und Wetter-Engine
(``tests/helpers/einstellung_gleich_mail_orte.py``).
"""
from __future__ import annotations

import copy

import pytest

from tests.helpers.einstellung_gleich_mail_orte import (
    html_ausblick,
    klartext_ausblick,
    preset_dict,
    sende_orte_mail,
)

# Von Hand aus editor_standard.json (Orte-Ausblick, Zustand "nie_eingestellt")
# abgeschrieben -- bewusst NICHT aus dem Produktcode gelesen.
EDITOR_ANZEIGE = ["temperature", "precipitation", "rain_probability", "wind", "gust", "thunder"]
NUTZER = ("r9-altbestand-anna", "r9-altbestand-bert")


def _altbestand() -> dict:
    roh = preset_dict("altbestand_ohne_grundauswahl")
    assert roh["display_config"] == {}, "Vorbedingung: Altbestand ohne jede Liste"
    return roh


def _explizit() -> dict:
    roh = copy.deepcopy(_altbestand())
    roh["display_config"]["outlook_metrics"] = list(EDITOR_ANZEIGE)
    return roh


def _koepfe(zellen):
    return [k for k, _ in zellen]


@pytest.mark.parametrize("lang", ["de", "en"])
def test_r9_orte_altbestand_ausblick_wie_explizite_liste(lang):
    """Altbestand == gleichwertige explizite Liste, je Nutzer, im HTML UND im
    Klartext (Koepfe und Zellwerte der ersten Tageszeile)."""
    for uid in NUTZER:
        alt = sende_orte_mail(_altbestand(), uid=f"{uid}-{lang}-alt", language=lang)
        ref = sende_orte_mail(_explizit(), uid=f"{uid}-{lang}-ref", language=lang)
        h_alt, h_ref = html_ausblick(alt.html, lang), html_ausblick(ref.html, lang)
        k_alt, k_ref = klartext_ausblick(alt.plain, lang), klartext_ausblick(ref.plain, lang)
        assert h_ref and k_ref, "Vorbedingung: Referenz-Mail traegt einen Ausblick"
        assert h_alt == h_ref, (uid, lang, "HTML", h_alt, h_ref)
        assert k_alt == k_ref, (uid, lang, "Klartext", k_alt, k_ref)


@pytest.mark.parametrize("lang", ["de", "en"])
def test_r9_orte_altbestand_ausblick_html_gleich_klartext(lang):
    """HTML und Klartext derselben Altbestand-Mail: dieselben Spaltenkoepfe in
    derselben Folge, Temperatur als EINE Spanne (wie im Trip-Ausblick)."""
    for uid in NUTZER:
        mail = sende_orte_mail(_altbestand(), uid=f"{uid}-{lang}-form", language=lang)
        h, k = html_ausblick(mail.html, lang), klartext_ausblick(mail.plain, lang)
        assert h and list(h) == list(k), (h, k)
        for ort in h:
            assert _koepfe(h[ort]) == _koepfe(k[ort]), (uid, lang, ort, h[ort], k[ort])
            temp = [v for kopf, v in h[ort] if kopf == "Temp"]
            assert len(temp) == 1 and "/" in temp[0], (uid, lang, ort, h[ort])
