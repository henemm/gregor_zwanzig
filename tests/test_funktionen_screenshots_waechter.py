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


@pytest.mark.parametrize(
    "gekuerzt",
    [
        "bestätigt · gregor-test+jemand@...",
        "bestätigt · max.mustermann@…",
        "bestätigt · +49 171 ...",
        "bestätigt · +49 171 …",
    ],
)
def test_gegenprobe_gekuerzt_angezeigte_kontaktdaten_werden_erkannt(gekuerzt):
    """Die Oberflaeche kuerzt Adressen und Nummern („name@…“, „+49 171 …“);
    auch die gekuerzte Form verraet Personendaten (Befund bei der Sichtpruefung)."""
    assert personendaten_befunde(gekuerzt, FIKTIV_ERLAUBT), f"{gekuerzt!r} nicht erkannt"


def test_sms_kuerzel_mit_at_ist_keine_mail_adresse():
    assert personendaten_befunde("D9/13 W- CT:BKN@9 SU1", FIKTIV_ERLAUBT) == []


def test_uhrzeiten_datum_und_hoehen_sind_keine_telefonnummern():
    text = "07:00 · 2026-11-24 · 1.234 m · 25.02.–07.03.2027 · 12 mm/h · 3/15/50"
    assert personendaten_befunde(text, FIKTIV_ERLAUBT) == []


def test_pruefe_vor_aufnahme_bricht_bei_befund_ab():
    with pytest.raises(PersonendatenGefunden):
        pruefe_vor_aufnahme("Empfänger: echte.person@web.de", FIKTIV_ERLAUBT)


def test_pruefe_vor_aufnahme_laesst_fiktivtext_durch():
    pruefe_vor_aufnahme("GR221 Mockup · Münsterland-Vergleich", FIKTIV_ERLAUBT)


# ─── F003 (Adversary): der AUFNAHMEWEG selbst durchlaeuft Maskierer und Waechter ──
# ``aufnehmen`` ist der einzige Aufnahmeweg des Skripts (``aufnahme`` ruft ihn mit
# ``ziel_datei``). Geprueft im echten Chromium mit lokal gesetztem Seiteninhalt
# (``set_content``, kein Netz, keine Attrappe): Reihenfolge „maskieren → pruefen →
# erst dann aufnehmen und speichern“. Entfernt man den Aufruf von
# ``maskieren_und_pruefen`` in ``aufnehmen`` (oder ``pruefe_vor_aufnahme`` darin),
# entsteht trotz Kontaktdaten ein Bild bzw. bleibt der Text unmaskiert ⇒ rot.

_HTML = "<html><body><main style='padding:16px;font:16px sans-serif'>{}</main></body></html>"


@pytest.fixture(scope="module")
def browser_seite():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def seite(browser_seite):
    page = browser_seite.new_page(viewport={"width": 800, "height": 600})
    try:
        yield page
    finally:
        page.close()


def test_aufnahmeweg_bricht_ab_und_speichert_nichts_wenn_kontaktdaten_den_maskierer_ueberleben(seite, tmp_path):
    # Adresse ueber zwei Textknoten verteilt (z. B. hervorgehobener Teil): der
    # Maskierer ersetzt je Textknoten und erwischt sie nicht, der sichtbare Text
    # (innerText) enthaelt sie aber vollstaendig ⇒ der Waechter muss abbrechen.
    from scripts.funktionen_screenshots import aufnehmen

    seite.set_content(_HTML.format("Empfänger: <b>max.mustermann@</b><span>gmail.com</span>"))
    datei = tmp_path / "bild.webp"
    with pytest.raises(PersonendatenGefunden):
        aufnehmen(seite, datei)
    assert not datei.exists(), "Bild trotz Personendaten gespeichert"


def test_einstieg_aufnahme_bricht_ab_und_speichert_nichts_bei_personendaten(seite, tmp_path, monkeypatch):
    # F-ADV2: der Einstieg ``aufnahme`` (Bildname + Sprache) muss denselben Waechter
    # durchlaufen. Nur das Zielverzeichnis wird auf tmp_path umgelenkt (echte
    # Funktion ``ziel_datei``, echtes Chromium, kein Mock des Aufnahmewegs).
    import scripts.funktionen_screenshots as fs

    monkeypatch.setattr(fs, "STATIC_DIR", tmp_path)
    seite.set_content(_HTML.format("Empfänger: <b>max.mustermann@</b><span>gmail.com</span>"))
    with pytest.raises(PersonendatenGefunden):
        fs.aufnahme(seite, "de", "waechter-probe")
    assert not (tmp_path / "waechter-probe.webp").exists(), "Bild trotz Personendaten gespeichert"
    assert not any(tmp_path.rglob("*.webp")), "Bild trotz Personendaten gespeichert"


def test_einstieg_aufnahme_speichert_fiktivtext_ins_sprachziel(seite, tmp_path, monkeypatch):
    import scripts.funktionen_screenshots as fs

    monkeypatch.setattr(fs, "STATIC_DIR", tmp_path)
    seite.set_content(_HTML.format("GR221 Mockup · Etappe 3 · Böen 45 km/h"))
    fs.aufnahme(seite, "en", "waechter-probe")
    assert (tmp_path / "en" / "waechter-probe.webp").exists()


def test_aufnahmeweg_maskiert_vor_der_aufnahme_und_speichert_dann(seite, tmp_path):
    from scripts.funktionen_screenshots import MASKE_MAIL, MASKE_TELEFON, aufnehmen

    seite.set_content(_HTML.format("Zustellung an max.mustermann@gmail.com und +49 171 2345678"))
    datei = tmp_path / "bild.webp"
    breite, hoehe = aufnehmen(seite, datei)
    assert datei.exists() and datei.read_bytes()[8:12] == b"WEBP"
    assert breite > 0 and hoehe > 0
    sichtbar = seite.inner_text("main")
    assert "gmail.com" not in sichtbar and "2345678" not in sichtbar, "Aufnahme ohne Maskierung"
    assert MASKE_MAIL in sichtbar and MASKE_TELEFON in sichtbar


def test_aufnahmeweg_laesst_fiktivtext_durch(seite, tmp_path):
    from scripts.funktionen_screenshots import aufnehmen

    seite.set_content(_HTML.format("GR221 Mockup · Etappe 3 · Böen 45 km/h · 18:00 · pruefkonto-2967@gregor-test.invalid"))
    datei = tmp_path / "bild.webp"
    aufnehmen(seite, datei)
    assert datei.exists()
