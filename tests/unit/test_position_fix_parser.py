"""TDD RED -- Koordinaten aus einer Garmin-inReach-Nachricht lesen
(Issue #2327, AC-1/AC-2; ADR-0102).

SPEC: docs/specs/modules/feat_2327_gps_etappenfortschritt.md

VERTRAG fuer /50 (aus der Spec abgeleitet, hier festgeschrieben):

* ``services.inbound_sms_reader.extract_position(text: str)
  -> tuple[float, float] | None`` steht NEBEN ``split_link_code`` (eine
  Zerlegungsstelle, D9 #2154) und liefert ``(lat, lon)`` aus der LETZTEN
  Klammer ``(<Zahl>, <Zahl>)`` mit Dezimalpunkt -- tolerant gegen
  Leerzeichen, negative Werte und andere Nachkommastellenzahl. Ohne Klammer,
  bei Unsinn in der Klammer oder ausserhalb ``|lat| <= 90`` / ``|lon| <= 180``
  liefert sie ``None``.
* ``split_link_code`` bleibt im Ergebnis unveraendert: der Befehlstext VOR
  dem Link-Marker ist mit und ohne Koordinaten identisch.

RED-GRUND: ``extract_position`` existiert nicht (ImportError je Test --
Import bewusst IM Test, damit die Bestandsschutz-Tests unten nicht an einem
Sammelfehler der ganzen Datei haengen).

BESTANDSSCHUTZ (heute schon gruen und so gewollt): die
``split_link_code``-Tests -- sie bewachen, dass die neue Koordinatenlesung
den Befehlstext NICHT veraendert. Der Eingangstest "Befehl mit
Unsinn-Klammer wird normal beantwortet" (AC-2) liegt Ende-zu-Ende in
``tests/tdd/test_position_fix_inbound_e2e.py``.
"""
from __future__ import annotations

import pytest

from services.inbound_sms_reader import split_link_code
from tests.helpers.position_fix_fixtures import (
    ECHT_HEUTE,
    ECHT_HEUTE_KOORD,
    ECHT_SO_MORGEN,
    ECHT_SO_MORGEN_KOORD,
)


def _extract(text: str):
    from services.inbound_sms_reader import extract_position

    return extract_position(text)


def _ohne_klammer(text: str) -> str:
    return text[: text.rindex("(")].rstrip()


# ---------------------------------------------------------------------------
# AC-1: die zwei echten Texte
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, koord", [
    (ECHT_HEUTE, ECHT_HEUTE_KOORD),
    (ECHT_SO_MORGEN, ECHT_SO_MORGEN_KOORD),
], ids=["heute", "so_morgen"])
def test_ac1_echte_texte_liefern_die_koordinaten(text, koord):
    ergebnis = _extract(text)
    assert ergebnis is not None, f"Keine Koordinaten aus dem echten Text {text!r}"
    lat, lon = ergebnis
    assert lat == pytest.approx(koord[0], abs=1e-9)
    assert lon == pytest.approx(koord[1], abs=1e-9)


@pytest.mark.parametrize("text, befehl", [
    (ECHT_HEUTE, "Heute"),
    (ECHT_SO_MORGEN, "so morgen"),
], ids=["heute", "so_morgen"])
def test_ac1_befehlstext_mit_und_ohne_koordinaten_identisch(text, befehl):
    """Bestandsschutz: die Koordinaten aendern den Befehlstext nicht."""
    assert split_link_code(text) == ("", befehl)
    assert split_link_code(text) == split_link_code(_ohne_klammer(text))


def test_ac1_koordinaten_und_befehl_aus_demselben_text():
    """Beides aus EINEM Text: Befehl unveraendert UND Koordinaten gelesen --
    auch mit vorangestelltem Verknuepfungs-Code."""
    text = f"XXCJD224 {ECHT_HEUTE}"
    assert split_link_code(text) == ("XXCJD224", "Heute")
    assert _extract(text) == pytest.approx(ECHT_HEUTE_KOORD)


# ---------------------------------------------------------------------------
# AC-2: Toleranz und Verwerfen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw (46.6370, 12.7678)",
    "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw  (46.6370,12.7678)",
    "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw  ( 46.6370 ,  12.7678 )",
    "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw\t(46.6370,\t12.7678)",
    "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw   (46.637, 12.7678)  ",
], ids=["ein_leerzeichen", "ohne_leerzeichen", "innen_leerzeichen", "tabs", "drei_stellen"])
def test_ac2_leerzeichenvarianten_liefern_dasselbe_paar(text):
    assert _extract(text) == pytest.approx(ECHT_HEUTE_KOORD)


@pytest.mark.parametrize("text, koord", [
    ("Heute inreachlink.com/gAbc  (-33.4489, -70.6693)", (-33.4489, -70.6693)),
    ("Heute inreachlink.com/gAbc  (-0.5, 179.99999)", (-0.5, 179.99999)),
    ("Heute inreachlink.com/gAbc  (46.637012, 12.767845)", (46.637012, 12.767845)),
], ids=["negativ", "grenznah", "sechs_stellen"])
def test_ac2_negative_werte_und_andere_nachkommastellen(text, koord):
    assert _extract(text) == pytest.approx(koord)


@pytest.mark.parametrize("text", [
    "Heute",
    "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw",
    "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw  (abc, def)",
    "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw  (46.6370)",
    "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw  ()",
    "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw  (46.6370; 12.7678)",
    "",
], ids=["nur_befehl", "ohne_klammer", "unsinn", "eine_zahl", "leer_klammer", "semikolon", "leerer_text"])
def test_ac2_ohne_oder_mit_unsinniger_klammer_kein_fix(text):
    assert _extract(text) is None


@pytest.mark.parametrize("text", [
    "Heute inreachlink.com/gAbc  (91.0000, 12.7678)",
    "Heute inreachlink.com/gAbc  (-90.5000, 12.7678)",
    "Heute inreachlink.com/gAbc  (46.6370, 181.0000)",
    "Heute inreachlink.com/gAbc  (46.6370, -180.5000)",
], ids=["lat_91", "lat_minus_90_5", "lon_181", "lon_minus_180_5"])
def test_ac2_ungueltiger_wertebereich_kein_fix(text):
    assert _extract(text) is None


def test_ac2_ungueltige_klammer_aendert_den_befehl_nicht():
    """Bestandsschutz: auch eine Unsinn-Klammer laesst den Befehlstext so,
    wie er ohne sie waere -- der Befehl laeuft normal weiter."""
    text = "Heute inreachlink.com/gS5ySf-2sYCWmJQksXnjeHw  (abc, def)"
    assert split_link_code(text) == ("", "Heute")
