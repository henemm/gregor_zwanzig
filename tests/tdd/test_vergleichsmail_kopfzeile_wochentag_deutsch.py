"""#2210 AC-1/AC-2: Datumszeile der Klartext-Vergleichs-Mail ist locale-unabhaengig."""
from __future__ import annotations

import locale
from dataclasses import replace
from datetime import date

import pytest

from tests.helpers.vergleichs_mail_fixture import build_result


@pytest.fixture
def englische_systemsprache():
    alt = locale.setlocale(locale.LC_TIME)
    try:
        locale.setlocale(locale.LC_TIME, "C")
    except locale.Error:
        pytest.skip("Locale C nicht verfuegbar")
    yield
    locale.setlocale(locale.LC_TIME, alt)


def _datumszeile(lang: str) -> str:
    from output.renderers.comparison import render_comparison_text

    result = replace(build_result(), target_date=date(2026, 11, 2))
    text = render_comparison_text(result, lang=lang)
    zeilen = [z for z in text.splitlines() if "2026" in z and ("02.11" in z or "Nov" in z)]
    assert zeilen, f"Keine Datumszeile im Klartext gefunden:\n{text[:400]}"
    return zeilen[0]


def test_ac1_deutscher_wochentag_trotz_englischer_systemsprache(englische_systemsprache):
    zeile = _datumszeile("de")
    assert "Montag, 02.11.2026" in zeile
    assert "Monday" not in zeile


def test_ac2_englische_mail_bleibt_englisch(englische_systemsprache):
    assert "Monday, 2 Nov 2026" in _datumszeile("en")
