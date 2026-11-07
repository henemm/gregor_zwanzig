"""Issue #2792 S1c-4b — 3-Tages-Ausblick färbt die Temperatur beidseitig.

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md v1.5, §5 „3-Tages-
Ausblick" (Temperatur wird beidseitig gefärbt), AC-4 (beide Seiten derselben
Metrik in Stundentabelle, Kachel und 3-Tages-Ausblick), AC-19 (b).

Prüfling ist der feste Zweig von ``render_outlook_table`` (Trip und
Vergleich ohne konfigurierte Ausblick-Auswahl): die Tief-Zelle (N) folgt der
unteren, die Hoch-Zelle (D) der oberen Seite der übergebenen Ampel; grün
färbt nicht. Kern-Schicht: echte Renderer-Ausgabe, keine Mocks.
"""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from app.ampel import resolve_ampel


def _ampel(vorlage: str) -> dict:
    return resolve_ampel({"display_config": {"preset_name": vorlage}})


def _bg(level: str) -> str:
    from output.renderers.email.design_tokens import tone_css
    return f"background:{tone_css(level)[0]};"


def _zelle(html: str, text: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for td in soup.find_all("td"):
        if td.get_text(strip=True) == text:
            return td.get("style") or ""
    raise AssertionError(f"Vorbedingung: Zelle {text!r} fehlt\n{html}")


def _tabelle(vorlage: str, tief: int, hoch: int) -> str:
    from output.renderers.email.outlook import render_outlook_table
    zeile = {"weekday": "Mo", "temp_lo": tief, "temp_hi": hoch, "precip_mm": 0.0,
             "wind_kmh": 5, "thunder": "NONE"}
    return render_outlook_table([zeile], ampel=_ampel(vorlage))


@pytest.mark.parametrize("vorlage,tief,hoch,tief_farbe,hoch_farbe", [
    # Skitouren: oben gelb 3 / orange 8 / rot 15, unten gelb -15 / orange -20 / rot -30
    ("skitouren", -17, 9, "yellow", "orange"),
    ("skitouren", -31, 16, "red", "red"),
    # Allgemein: oben gelb 28, unten gelb 0 -- +9/+2 bleiben ungefärbt
    ("allgemein", 2, 9, None, None),
    ("allgemein", -6, 31, "orange", "orange"),
])
def test_ausblick_faerbt_tief_und_hoch_nach_der_abo_ampel(vorlage, tief, hoch, tief_farbe, hoch_farbe):
    html = _tabelle(vorlage, tief, hoch)
    for wert, farbe in ((tief, tief_farbe), (hoch, hoch_farbe)):
        stil = _zelle(html, f"{wert}°")
        if farbe is None:
            assert "background:" not in stil, (vorlage, wert, stil)
        else:
            assert stil.startswith(_bg(farbe)), (vorlage, wert, stil)


def test_ausblick_temperatur_unterscheidet_skitouren_und_allgemein():
    """Dieselbe Zeile, zwei Abos: +9 °C ist nur bei Skitouren gefärbt."""
    ski, allg = _tabelle("skitouren", 2, 9), _tabelle("allgemein", 2, 9)
    assert _zelle(ski, "9°").startswith(_bg("orange"))
    assert "background:" not in _zelle(allg, "9°")
