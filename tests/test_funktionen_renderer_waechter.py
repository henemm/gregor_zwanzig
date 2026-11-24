"""Personendaten-Waechter im Renderer-Bildpfad der Funktionsseiten (Issue #3324).

Spec: docs/specs/modules/pruefregeln_funktionsseiten_3324.md (AC-3, AC-4, AC-5)

``scripts/landing_screenshots.py --funktionen`` erzeugt die Renderer-Bilder der
oeffentlichen Funktionsseiten aus festen Testdaten. Der Aufnahmeweg dafuer ist der
modulweite Helfer ``renderer_aufnahme(page, html, ziel, width, *, height=None,
body_css="", clip=None) -> (breite, hoehe)``. Vor dem Bildschirmfoto prueft er den
GESAMTEN sichtbaren Seitentext (``body``), auch wenn nur ein Ausschnitt (``clip``)
fotografiert wird, mit ``pruefe_vor_aufnahme`` gegen ``FIKTIV_ERLAUBT``; es wird
nichts maskiert. Ein Befund bricht mit ``PersonendatenGefunden`` ab, es entsteht
keine Datei, die Meldung nennt nur die Anzahl.

Echtes Chromium mit lokal gesetztem Seiteninhalt (kein Netz, kein Mock des Waechters).

    uv run pytest tests/test_funktionen_renderer_waechter.py --disable-socket --allow-unix-socket -v -rA
"""

from __future__ import annotations

import pytest

import scripts.landing_screenshots as ls

NUMMER = "+49 171 2345678"
_HTML = "<html><body style='margin:0;font:16px sans-serif'>{}</body></html>"


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        try:
            yield b
        finally:
            b.close()


@pytest.fixture
def page(browser):
    p = browser.new_page(viewport={"width": 800, "height": 600})
    try:
        yield p
    finally:
        p.close()


def test_ac4_echt_aussehende_nummer_bricht_ab_ohne_datei_und_ohne_wert_in_meldung(page, tmp_path):
    ziel = tmp_path / "briefing-sms.webp"
    assert not ziel.exists()
    html = _HTML.format(f"<p>Briefing 07:00 · Böen 45 km/h</p><p>Empfänger: {NUMMER}</p>")
    with pytest.raises(ls.PersonendatenGefunden) as fehler:
        ls.renderer_aufnahme(page, html, ziel, 420)
    assert not ziel.exists(), "Bild trotz Personendaten gespeichert"
    assert not any(tmp_path.rglob("*.webp")), "Bild trotz Personendaten gespeichert"
    meldung = str(fehler.value)
    assert "2345678" not in meldung and "171" not in meldung, "Meldung verraet den Wert"
    assert meldung.startswith("1 "), f"Meldung nennt die Anzahl der Befunde nicht: {meldung!r}"


def test_ac3_ausschnitt_aufnahme_prueft_den_ganzen_sichtbaren_text(page, tmp_path):
    # Die Nummer steht weit unterhalb des fotografierten Ausschnitts: trotzdem Abbruch.
    ziel = tmp_path / "befehle-mail.webp"
    html = _HTML.format(
        "<div style='height:120px'>HEUTE · MORGEN · STATUS</div>"
        f"<div style='margin-top:1500px'>Kontakt {NUMMER}</div>"
    )
    with pytest.raises(ls.PersonendatenGefunden):
        ls.renderer_aufnahme(page, html, ziel, 800, clip={"x": 0, "y": 0, "width": 800, "height": 120})
    assert not ziel.exists(), "Ausschnitt trotz Personendaten ausserhalb des Ausschnitts gespeichert"


def test_ac3_mail_adresse_ueber_zwei_textknoten_wird_erkannt(page, tmp_path):
    ziel = tmp_path / "alarm-mail.webp"
    html = _HTML.format("Empfänger: <b>max.mustermann@</b><span>gmail.com</span>")
    with pytest.raises(ls.PersonendatenGefunden):
        ls.renderer_aufnahme(page, html, ziel, 600)
    assert not ziel.exists()


def test_ac3_es_wird_nichts_maskiert(page, tmp_path):
    ziel = tmp_path / "briefing-mail.webp"
    html = _HTML.format(f"<p>Briefing</p><p>{NUMMER}</p>")
    with pytest.raises(ls.PersonendatenGefunden):
        ls.renderer_aufnahme(page, html, ziel, 800)
    assert NUMMER in page.inner_text("body"), "Renderer-Pfad hat maskiert statt abzubrechen"


def test_ac5_fiktiver_inhalt_ergibt_webp(page, tmp_path):
    ziel = tmp_path / "premium-sms.webp"
    html = _HTML.format("GR221 Mockup · Etappe 3 · Böen 45 km/h · 18:00 · pruefkonto-2967@gregor-test.invalid")
    breite, hoehe = ls.renderer_aufnahme(page, html, ziel, 420)
    assert ziel.exists() and ziel.read_bytes()[8:12] == b"WEBP"
    assert breite > 0 and hoehe > 0


def test_ac5_fiktiver_ausschnitt_ergibt_webp(page, tmp_path):
    ziel = tmp_path / "briefing-quelle.webp"
    html = _HTML.format("<div style='height:100px'>Quelle: arome_france</div><div>Fusszeile</div>")
    ls.renderer_aufnahme(page, html, ziel, 800, clip={"x": 0, "y": 0, "width": 800, "height": 100})
    assert ziel.exists() and ziel.read_bytes()[8:12] == b"WEBP"


def _bildstand(ordner):
    """Pfad -> (Groesse, mtime) aller echten Bildausgaben; Tests duerfen sie nie schreiben."""
    return {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in ordner.rglob("*") if p.is_file()}


def test_ac5_funktionen_bilder_erzeugt_alle_bilder_beider_sprachen(page, tmp_path):
    # Echte Auftragsquelle (alle Renderer-Fixtures inkl. Ausschnitte), Ziel nur in tmp_path.
    vorher = _bildstand(ls.FUNKTIONEN_DIR)
    masse = ls.funktionen_bilder(page, ziel=lambda name, lang: tmp_path / lang / f"{name}.webp")
    for lang in ls.FUNKTIONEN_SPRACHEN:
        erwartet = {name for name, *_ in ls.renderer_auftraege(lang)}
        assert len(erwartet) >= 7, f"{lang}: Auftragsquelle unvollstaendig: {sorted(erwartet)}"
        erzeugt = {p.stem for p in (tmp_path / lang).glob("*.webp")}
        assert erzeugt == erwartet, f"{lang}: Bilder {sorted(erzeugt)} statt {sorted(erwartet)}"
        for name in erwartet:
            assert (tmp_path / lang / f"{name}.webp").read_bytes()[8:12] == b"WEBP"
            assert masse[name][lang][0] > 0 and masse[name][lang][1] > 0
    assert _bildstand(ls.FUNKTIONEN_DIR) == vorher, "Test hat echte Bildausgaben veraendert"


def test_ac4_funktionen_bilder_bricht_bei_personendaten_ohne_datei_ab(page, tmp_path):
    # Der Bildlauf selbst (nicht nur der Helfer) muss den Waechter durchlaufen.
    def auftraege(lang):
        return [("briefing-sms", _HTML.format(f"<p>Briefing 07:00</p><p>{NUMMER}</p>"), 420, {})]

    with pytest.raises(ls.PersonendatenGefunden):
        ls.funktionen_bilder(page, ziel=lambda name, lang: tmp_path / lang / f"{name}.webp",
                             auftraege=auftraege)
    assert not any(tmp_path.rglob("*")), "Bild trotz Personendaten gespeichert"
