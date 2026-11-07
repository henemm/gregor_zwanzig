"""Issue #2792 S1c-4b -- letzte Testluecken aus der vierten Gegenpruefung
(Protokoll: docs/artifacts/feat-2792-s1c4b-umschalten/adversary-dialog.md).

1. Fester Ausblick-Zweig (keine Ausblick-Auswahl): Gewitter je Stufe in der
   Farbe der zentralen Abbildung ``app.ampel.thunder_color`` -- leicht gelb.
2. SMS-Kuerzel ``UV`` und ``PR`` folgen der Abo-Ampel: unter Gelb Null-Form
   ``-``, ab Gelb ``Wert@Stunde``; Vorlagen mit anderer Gelbgrenze
   unterscheiden sich.
3. Grenzwerte exakt auf der Schwelle: oben ``>=`` (die Grenze gehoert zur
   schlechteren Stufe), unten ``<`` (die Grenze gehoert zur besseren Stufe),
   wie ``output.metric_format.severity_from_thresholds``.
4. Klammer bei rundungsgleichen Werten: steht nur, wenn sich der ANGEZEIGTE
   Wert unterscheidet (``docs/reference/sms_format.md``, Abschnitt Klammer).

Gemessen am gerenderten Ausblick (``render_outlook_table``) bzw. an der echten
Tokenzeile (``build_token_line``). Kern-Schicht, keine Mocks, kein Netz.
"""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from tests.tdd.test_s1c4b_fixloop1_findings import _ampel, _hv, _sms_token

_KOEPFE = ("Tag", "Temp Minimum", "Temp Maximum", "Rain", "Rain%", "Wind", "Gust", "Thdr", "ACC")


def _bg(stufe: str | None) -> str:
    """Erwarteter Zell-Hintergrund (``""`` = keine Toenung)."""
    from output.renderers.email.design_tokens import tone_css
    return "" if stufe in (None, "green") else f"background:{tone_css(stufe)[0]};"


def _hat_bg(style: str, bg: str) -> bool:
    return style.startswith(bg) if bg else not style.startswith("background:")


def _ausblick(vorlage: str, **felder) -> dict[str, str]:
    """Spaltenkopf -> style der Zelle; fester Zweig (keine Ausblick-Auswahl)."""
    from output.renderers.email.outlook import render_outlook_table
    zeile = dict(weekday="Mo", name="E", temp_lo=10, temp_hi=18, precip_mm=0.0,
                 wind_dir="W", wind_kmh=12, gust_kmh=15, thunder="NONE", note=None,
                 hourly_precip=(), hourly_wind=(), hourly_gust=(), hourly_thunder=(),
                 rain_probability_pct=10)
    zeile.update(felder)
    html = render_outlook_table([zeile], show_acc=True, ampel=_ampel(vorlage))
    tr = BeautifulSoup(html, "html.parser").find("tbody").find("tr")
    return {k: td.get("style", "") for k, td in zip(_KOEPFE, tr.find_all("td"))}


# ---------------------------------------------------------------------------
# 1. Gewitter im festen Ausblick-Zweig, je Stufe
# ---------------------------------------------------------------------------

#: Erwartung aus der Vorlage (app/ampel_templates.py): keins gruen, leicht
#: fest gelb (P2), mittel/hoch nach ``thunder`` der Vorlage.
_GEWITTER = {
    "allgemein": {"NONE": "green", "LOW": "yellow", "MED": "orange", "HIGH": "red"},
    "wassersport": {"NONE": "green", "LOW": "yellow", "MED": "red", "HIGH": "red"},
}


@pytest.mark.parametrize("vorlage", list(_GEWITTER))
@pytest.mark.parametrize("stufe", ["NONE", "LOW", "MED", "HIGH"])
def test_fester_ausblick_gewitter_je_stufe_nach_zentraler_abbildung(vorlage, stufe):
    """Die Gewitter-Zelle traegt die Farbe der zentralen Abbildung; „leicht"
    ist gelb und wird gefaerbt (nicht wie gruen behandelt)."""
    from app.ampel import thunder_color
    erwartet = _GEWITTER[vorlage][stufe]
    assert thunder_color(stufe, _ampel(vorlage)) == erwartet, "Vorbedingung: zentrale Abbildung"
    stil = _ausblick(vorlage, thunder=stufe)["Thdr"]
    assert _hat_bg(stil, _bg(erwartet)), (vorlage, stufe, stil[:60])


# ---------------------------------------------------------------------------
# 2. SMS-Kuerzel UV und PR nach der Abo-Ampel
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("vorlage, werte, erwartet", [
    # Allgemein UV gelb ab 3, Wandern gelb ab 5
    ("allgemein", ((9, 2.0), (12, 2.0)), "-"),
    ("wandern", ((9, 2.0), (12, 2.0)), "-"),
    ("allgemein", ((9, 2.0), (12, 4.0)), "4@12"),
    ("wandern", ((9, 2.0), (12, 4.0)), "-"),
    ("wandern", ((9, 2.0), (12, 6.0)), "6@12"),
])
def test_uv_kuerzel_folgt_der_abo_ampel(vorlage, werte, erwartet):
    """UV 2 ist bei Allgemein grün ⇒ Null-Form; UV 4 ist bei Allgemein gelb
    (``4@12``), bei Wandern grün (``-``). (Skitouren hat dieselben UV-Grenzen
    wie Allgemein, 3/6/8; deshalb Wandern als Gegenstück.)"""
    assert _sms_token("UV", "uv_hourly", _hv(*werte), _ampel(vorlage)) == erwartet


@pytest.mark.parametrize("werte, erwartet", [
    (((9, 20.0), (12, 25.0)), "-"),            # unter Gelb 30
    (((9, 20.0), (12, 35.0)), "35%@12"),       # ab Gelb
    (((9, 35.0), (12, 65.0)), "35%@9(65%@12)"),  # Klammer: orange schlimmer
])
def test_pr_kuerzel_folgt_der_abo_ampel(werte, erwartet):
    """Regenwahrscheinlichkeit bei Allgemein (gelb ab 30 %, orange ab 60 %)."""
    assert _sms_token("PR", "pop_hourly", _hv(*werte), _ampel("allgemein")) == erwartet


# ---------------------------------------------------------------------------
# 3. Grenzwerte exakt auf der Schwelle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("vorlage, felder, spalte, stufe", [
    # Wassersport Wind unten: orange unter 4, gelb unter 8 (``<``)
    ("wassersport", {"wind_kmh": 4}, "Wind", "yellow"),
    ("wassersport", {"wind_kmh": 8}, "Wind", "green"),
    ("wassersport", {"wind_kmh": 3}, "Wind", "orange"),
    # Skitouren Temperatur unten: rot unter -30, orange unter -20, gelb unter -15
    ("skitouren", {"temp_lo": -30}, "Temp Minimum", "orange"),
    ("skitouren", {"temp_lo": -31}, "Temp Minimum", "red"),
    ("skitouren", {"temp_lo": -15}, "Temp Minimum", "green"),
    ("skitouren", {"temp_lo": -16}, "Temp Minimum", "yellow"),
    # Skitouren Temperatur oben: gelb ab 3, rot ab 15 (``>=``)
    ("skitouren", {"temp_lo": 0, "temp_hi": 3}, "Temp Maximum", "yellow"),
    ("skitouren", {"temp_lo": 0, "temp_hi": 2}, "Temp Maximum", "green"),
    ("skitouren", {"temp_lo": 0, "temp_hi": 15}, "Temp Maximum", "red"),
])
def test_grenzwert_auf_der_schwelle(vorlage, felder, spalte, stufe):
    """Oben gehoert die Grenze zur schlechteren Stufe (``>=``), unten zur
    besseren (``<``): Wassersport-Wind 4 ist gelb, 8 gruen; Skitouren −30 °C
    orange, −15 °C gruen, +3 °C gelb, +15 °C rot."""
    from app.ampel import ampel_stufe
    wert = next(iter(v for k, v in felder.items() if {"Wind": "wind_kmh", "Temp Minimum": "temp_lo",
                                                     "Temp Maximum": "temp_hi"}[spalte] == k))
    metrik = "wind" if spalte == "Wind" else "temperature"
    assert ampel_stufe(_ampel(vorlage), metrik, wert) == stufe, (vorlage, spalte, wert)
    stil = _ausblick(vorlage, **felder)[spalte]
    assert _hat_bg(stil, _bg(stufe)), (vorlage, spalte, wert, stil[:60])


@pytest.mark.parametrize("werte, erwartet", [
    (((9, 4.0), (12, 12.0)), "4@9"),   # 4 = gelb (nicht orange), 12 gruen
    (((9, 8.0), (12, 12.0)), "-"),     # 8 = gruen
])
def test_grenzwert_wind_unten_in_der_sms(werte, erwartet):
    """Dieselbe Grenz-Semantik im Kurzkanal (Wassersport-Wind)."""
    assert _sms_token("W", "wind_hourly", _hv(*werte), _ampel("wassersport")) == erwartet


# ---------------------------------------------------------------------------
# 4. Klammer bei rundungsgleichen Werten
# ---------------------------------------------------------------------------

def test_klammer_entfaellt_bei_rundungsgleichem_angezeigtem_wert():
    """Boeen 35.1 um 8 und 35.4 um 10 Uhr (Allgemein, gelb ab 30): der
    schlimmere Wert 35.4 zeigt gerundet dasselbe ⇒ ``35@8`` ohne Klammer."""
    assert _sms_token("G", "gust_hourly", _hv((8, 35.1), (10, 35.4)), _ampel("allgemein")) == "35@8"


def test_klammer_steht_bei_verschiedenem_angezeigtem_wert():
    """Gegenprobe: 35.1 und 36.0 unterscheiden sich gerundet ⇒ Klammer."""
    assert _sms_token("G", "gust_hourly", _hv((8, 35.1), (10, 36.0)), _ampel("allgemein")) == "35@8(36@10)"
