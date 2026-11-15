"""Zeitspalten-Kopf der Telegram-Segmenttabelle folgt der Kontosprache
(Issue #3014, Epic #2644, ADR-0104).

SPEC: docs/specs/modules/i18n_zt_kopf_sprache_3014.md

Echte Renderer (``render_telegram_bubbles`` ueber die Golden-Fixture und das
Startseiten-Beispiel ``telegram_html()``), netzfrei, kein Mock.
Deutsch bleibt byte-gleich ("Zt"), Englisch zeigt "Hr", die Metrik-Kuerzel
(Protokoll-Token) bleiben in beiden Sprachen unveraendert.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from i18n import t
from output.renderers.narrow import _TG_TABLE_WIDTH
from tests.helpers.telegram_briefing_fixture import (
    BUBBLE_SEP, build_texts, golden_path,
)

_ROOT = Path(__file__).resolve().parents[2]
_METRIK_KOPF = ["T", "W", "G", "R", "TH", "VS", "FZ"]


def _tabellen(texts: list[str]) -> list[str]:
    tabs = [b for b in texts if "<pre>" in b]
    assert len(tabs) == 2, "Vorbedingung: Segment- und Ziel-Tabelle"
    return tabs


def _tabellenzeilen(tab: str) -> list[str]:
    innen = tab.split("<pre>", 1)[1].split("</pre>", 1)[0]
    return [z for z in innen.splitlines() if z.strip()]


def test_ac1_en_tabellenkopf_beginnt_mit_hr_und_kein_zt_in_der_nachricht():
    """AC-1: Englisches Briefing, jede Segmenttabelle beginnt mit "Hr";
    "Zt" kommt in keiner Blase vor."""
    texts = build_texts(lang="en")
    for tab in _tabellen(texts):
        kopf = _tabellenzeilen(tab)[0]
        assert kopf.split()[0] == "Hr", f"EN-Kopf nicht 'Hr':\n{tab}"
    for b in texts:
        assert not re.search(r"\bZt\b", b), f"deutsches 'Zt' im en-Briefing:\n{b}"


@pytest.mark.parametrize("kw", [{}, {"lang": "de"}])
def test_ac2_de_tabellenkopf_bleibt_zt_und_byte_gleich_zur_golden(kw):
    """AC-2: Deutsch (mit und ohne ``lang``) beginnt mit "Zt" und ist
    byte-gleich zur bestehenden DE-Golden-Datei."""
    texts = build_texts(**kw)
    for tab in _tabellen(texts):
        assert _tabellenzeilen(tab)[0].split()[0] == "Zt", tab
    golden = golden_path("de").read_text(encoding="utf-8")[:-1].split(BUBBLE_SEP)
    assert texts == golden


def test_ac3_en_keine_tabellenzeile_breiter_als_telegram_grenze():
    """AC-3: Englische Tabelle mit allen Spalten belegt, keine Zeile ueber
    ``_TG_TABLE_WIDTH`` und kein Umbruch mitten in einer Datenzeile
    (jede Datenzeile beginnt mit einer 2-stelligen Stunde und hat volle Spaltenzahl)."""
    assert _TG_TABLE_WIDTH == 32
    for tab in _tabellen(build_texts(lang="en")):
        zeilen = _tabellenzeilen(tab)
        for z in zeilen:
            assert len(z) <= _TG_TABLE_WIDTH, f"Zeile zu breit ({len(z)}): {z!r}"
        kopf, daten = zeilen[0], zeilen[1:]
        assert len(kopf.split()) == 1 + len(_METRIK_KOPF), kopf
        for z in daten:
            assert re.match(r"^\d{2} ", z), f"Umbruch mitten in Datenzeile: {z!r}"
            assert len(z.split()) == 1 + len(_METRIK_KOPF), z


def _landing_modul():
    pfad = _ROOT / "scripts" / "landing_screenshots.py"
    spec = importlib.util.spec_from_file_location("landing_screenshots_3014", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ac4_startseiten_beispiel_en_zeigt_hr_statt_zt():
    """AC-4: Die Telegram-Beispielnachricht des englischen Startseiten-Bilds
    zeigt im Tabellenkopf "Hr" statt "Zt"."""
    html = _landing_modul().telegram_html()
    pres = re.findall(r"<pre>(.*?)</pre>", html, flags=re.S)
    assert pres, "Vorbedingung: Beispielnachricht enthaelt eine Segmenttabelle"
    for pre in pres:
        kopf = next(z for z in pre.splitlines() if z.strip())
        assert kopf.split()[0] == "Hr", f"Startseiten-Kopf nicht 'Hr':\n{pre}"
    assert not re.search(r"\bZt\b", html), "deutsches 'Zt' im EN-Startseiten-Beispiel"


def test_ac5_metrik_kuerzel_in_beiden_sprachen_identisch():
    """AC-5: Nach dem Zeitspalten-Kopf bleiben die Metrik-Kuerzel
    (Protokoll-Token) in de und en unuebersetzt und identisch."""
    koepfe = {}
    for lang in ("de", "en"):
        koepfe[lang] = [
            _tabellenzeilen(tab)[0].split() for tab in _tabellen(build_texts(lang=lang))
        ]
    for de_kopf, en_kopf in zip(koepfe["de"], koepfe["en"]):
        assert de_kopf[1:] == en_kopf[1:] == _METRIK_KOPF
        assert (de_kopf[0], en_kopf[0]) == ("Zt", "Hr")


def test_katalog_paritaet_zeitspalten_kopf_in_beiden_sprachen():
    """Katalog: ``telegram.tabelle.zeit`` existiert in de und en
    (``t`` faellt sonst auf de bzw. den Schluessel selbst zurueck)."""
    assert t("telegram.tabelle.zeit", "de") == "Zt"
    assert t("telegram.tabelle.zeit", "en") == "Hr"
