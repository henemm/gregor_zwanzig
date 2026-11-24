"""Personendaten-Waechter des Bild-Skripts /funktionen (Issue #3319, AC-9).

Spec: docs/specs/modules/oeffentliche_doku_3319.md

``scripts/funktionen_screenshots.py`` nimmt Bilder der echten Staging-Oberflaeche
mit dem Pruefkonto auf. Vor JEDER Aufnahme prueft ``personendaten_befunde`` den
sichtbaren Seitentext: jede Mail-Adresse und jede Telefonnummer, die nicht in der
Fiktiv-Liste des Seeds steht, ist ein Befund; ``pruefe_vor_aufnahme`` bricht dann
mit ``PersonendatenGefunden`` ab. Getestet wird die echte Funktion mit echten
Texten (kein Browser, kein Netz). Gegenprobe: echte-aussehende Daten werden erkannt.

    uv run pytest tests/test_funktionen_screenshots_waechter.py --disable-socket -v -rA
"""

from __future__ import annotations

import pytest

from scripts.funktionen_screenshots import (
    FIKTIV_ERLAUBT,
    PersonendatenGefunden,
    personendaten_befunde,
    pruefe_vor_aufnahme,
)


def test_fiktiv_liste_ist_nicht_leer():
    assert len(FIKTIV_ERLAUBT) > 0


def test_text_ohne_kontaktdaten_hat_keine_befunde():
    text = "GR221 Mockup · Etappe 3 · Sóller → Tossals Verds · Böen 45 km/h · 18:00 Abendbriefing"
    assert personendaten_befunde(text, FIKTIV_ERLAUBT) == []


def test_fiktivwerte_des_seeds_sind_erlaubt():
    text = " · ".join(sorted(FIKTIV_ERLAUBT))
    assert personendaten_befunde(text, FIKTIV_ERLAUBT) == []


@pytest.mark.parametrize(
    "fremd",
    [
        "max.mustermann@gmail.com",
        "Kontakt: jemand@henemm.com",
        "+49 171 2345678",
        "+491712345678",
        "0171 2345678",
        "+43 664 1234567",
    ],
)
def test_gegenprobe_fremde_kontaktdaten_werden_erkannt(fremd):
    befunde = personendaten_befunde(f"Empfänger: {fremd} · Briefing 07:00", FIKTIV_ERLAUBT)
    assert befunde, f"{fremd!r} nicht erkannt"


def test_uhrzeiten_datum_und_hoehen_sind_keine_telefonnummern():
    text = "07:00 · 2026-11-24 · 1.234 m · 25.02.–07.03.2027 · 12 mm/h · 3/15/50"
    assert personendaten_befunde(text, FIKTIV_ERLAUBT) == []


def test_pruefe_vor_aufnahme_bricht_bei_befund_ab():
    with pytest.raises(PersonendatenGefunden):
        pruefe_vor_aufnahme("Empfänger: echte.person@web.de", FIKTIV_ERLAUBT)


def test_pruefe_vor_aufnahme_laesst_fiktivtext_durch():
    pruefe_vor_aufnahme("GR221 Mockup · Münsterland-Vergleich", FIKTIV_ERLAUBT)
