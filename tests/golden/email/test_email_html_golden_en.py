"""Englische HTML-Goldens der Trip-Briefing-Mail (Issue #2664, AC-2).

SPEC: docs/specs/modules/i18n_p2_briefing_mail_html_2664.md

Dieselben fuenf Referenz-Szenarien wie ``test_email_html_golden.py`` (die
deutschen Dateien bleiben dort unveraendert der Deutsch-Beweis), gerendert
mit ``lang="en"``. Szenario-Bauer: ``regenerate._scenarios`` -- dieselbe
Quelle, die die ``*-html.en.txt`` schreibt (``regenerate.py --lang en``).
Uhr eingefroren ueber ``conftest.py``.
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
        "golden_email_regenerate_en", GOLDEN_DIR / "regenerate.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("stem", STEMS)
def test_englisch_byte_gleich_zur_golden_datei(stem):
    reports = dict(_regenerate()._scenarios(lang="en"))
    pfad = GOLDEN_DIR / f"{stem}-html.en.txt"
    assert pfad.exists(), f"Englisches Golden fehlt: {pfad.name} (regenerate.py --lang en)"
    assert reports[stem].email_html == pfad.read_text(encoding="utf-8"), (
        f"HTML-Drift in {pfad.name}"
    )


@pytest.mark.parametrize("stem", STEMS)
def test_deutsch_mit_lang_de_byte_gleich_zur_deutschen_datei(stem):
    reports = dict(_regenerate()._scenarios(lang="de"))
    soll = (GOLDEN_DIR / f"{stem}-html.txt").read_text(encoding="utf-8")
    assert reports[stem].email_html == soll
