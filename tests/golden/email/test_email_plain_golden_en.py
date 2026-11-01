"""Englische Klartext-Goldens der Trip-Briefing-Mail (Issue #2665, AC-2).

SPEC: docs/specs/modules/i18n_p3_briefing_compact_plain_2665.md

Dieselben fuenf Referenz-Szenarien wie ``test_email_plain_golden.py`` (die
deutschen ``*-plain.txt`` bleiben dort unveraendert der Deutsch-Beweis),
gerendert mit ``lang="en"``; dazu der Nachweis, dass ``lang="de"``
byte-gleich zur deutschen Datei ist. Erzeugt mit ``regenerate.py --lang en``.
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
        "golden_email_regenerate_plain_en", GOLDEN_DIR / "regenerate.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("stem", STEMS)
def test_englisch_byte_gleich_zur_golden_datei(stem):
    reports = dict(_regenerate()._scenarios(lang="en"))
    pfad = GOLDEN_DIR / f"{stem}-plain.en.txt"
    assert pfad.exists(), f"Englisches Golden fehlt: {pfad.name} (regenerate.py --lang en)"
    assert reports[stem].email_plain == pfad.read_text(encoding="utf-8"), (
        f"Klartext-Drift in {pfad.name}"
    )


@pytest.mark.parametrize("stem", STEMS)
def test_deutsch_mit_lang_de_byte_gleich_zur_deutschen_datei(stem):
    reports = dict(_regenerate()._scenarios(lang="de"))
    soll = (GOLDEN_DIR / f"{stem}-plain.txt").read_text(encoding="utf-8")
    assert reports[stem].email_plain == soll
