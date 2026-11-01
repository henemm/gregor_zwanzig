"""Kompakt-Goldens der Trip-Briefing-Mail, Deutsch und Englisch (Issue #2665, AC-2).

SPEC: docs/specs/modules/i18n_p3_briefing_compact_plain_2665.md

Die deutschen ``*-compact.txt`` wurden VOR der ersten Codeaenderung aus dem
damaligen Code erzeugt (``regenerate.py --format compact``) -- sie sind der
Beweis, dass Deutsch byte-gleich bleibt, mit und ohne ``lang``. Die
englischen ``*-compact.en.txt`` (``--format compact --lang en``) sind
Regressionsschutz. Szenario-Bauer: ``regenerate._scenarios``; Uhr ueber
``conftest.py`` eingefroren.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).parent
STEMS = [
    "gr20-summer-evening", "gr20-spring-morning", "gr221-mallorca-evening",
    "arlberg-winter-morning", "corsica-vigilance",
]


def _regenerate():
    spec = importlib.util.spec_from_file_location(
        "golden_email_regenerate_compact", GOLDEN_DIR / "regenerate.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _berichte(**kw) -> dict:
    return dict(_regenerate()._scenarios(email_format="compact", **kw))


@pytest.mark.parametrize("stem", STEMS)
def test_deutsch_ohne_lang_byte_gleich(stem):
    soll = (GOLDEN_DIR / f"{stem}-compact.txt").read_text(encoding="utf-8")
    assert _berichte()[stem].email_plain == soll


@pytest.mark.parametrize("stem", STEMS)
def test_deutsch_mit_lang_de_byte_gleich(stem):
    soll = (GOLDEN_DIR / f"{stem}-compact.txt").read_text(encoding="utf-8")
    assert _berichte(lang="de")[stem].email_plain == soll


@pytest.mark.parametrize("stem", STEMS)
def test_englisch_byte_gleich_zur_golden_datei(stem):
    pfad = GOLDEN_DIR / f"{stem}-compact.en.txt"
    assert pfad.exists(), f"Englisches Golden fehlt: {pfad.name} (--format compact --lang en)"
    ist = _berichte(lang="en")[stem].email_plain
    assert ist == pfad.read_text(encoding="utf-8"), f"Kompakt-Drift in {pfad.name}"
    assert ist.isascii()
