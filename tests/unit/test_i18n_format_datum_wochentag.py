"""Datums-, Wochentags-, Zeit- und Relativtag-Format (Issue #2662 AC-3).

Der 29.10.2026 ist ein Donnerstag. Gegenprobe mit fremder Prozess-Locale:
die Ausgabe darf nicht von ``LC_ALL``/``locale.setlocale`` abhaengen.
"""
from __future__ import annotations

import locale
from datetime import date, datetime, timedelta

import pytest

from i18n import fmt_date, fmt_time, fmt_weekday, relative_day

TAG = date(2026, 10, 29)
ZEIT = datetime(2026, 10, 29, 14, 30)

ERWARTET = [
    (lambda: fmt_date(TAG, "de", "kurz"), "Do 29.10."),
    (lambda: fmt_date(TAG, "en", "kurz"), "Thu 29 Oct"),
    (lambda: fmt_date(TAG, "de"), "Do 29.10."),
    (lambda: fmt_date(ZEIT, "en"), "Thu 29 Oct"),
    (lambda: fmt_date(TAG, "de", "lang"), "Donnerstag, 29. Oktober 2026"),
    (lambda: fmt_date(TAG, "en", "lang"), "Thursday, 29 October 2026"),
    (lambda: fmt_weekday(TAG, "de"), "Do"),
    (lambda: fmt_weekday(TAG, "en"), "Thu"),
    (lambda: fmt_weekday(TAG, "de", kurz=False), "Donnerstag"),
    (lambda: fmt_weekday(ZEIT, "en", kurz=False), "Thursday"),
    (lambda: fmt_time(ZEIT), "14:30"),
    (lambda: fmt_time(datetime(2026, 3, 1, 7, 5)), "07:05"),
    (lambda: relative_day(0, "de"), "heute"),
    (lambda: relative_day(1, "de"), "morgen"),
    (lambda: relative_day(2, "de"), "übermorgen"),
    (lambda: relative_day(0, "en"), "today"),
    (lambda: relative_day(1, "en"), "tomorrow"),
    (lambda: relative_day(2, "en"), "day after tomorrow"),
]


def _alle_pruefen():
    for aufruf, soll in ERWARTET:
        assert aufruf() == soll


def test_tabellenwerte():
    _alle_pruefen()


def test_unbekannte_sprache_ist_deutsch():
    assert fmt_date(TAG, "fr") == "Do 29.10."  # type: ignore[arg-type]
    assert relative_day(1, "xx") == "morgen"  # type: ignore[arg-type]


def test_alle_wochentage_und_monate_eindeutig():
    tage_de = {fmt_weekday(date(2026, 10, 26) + timedelta(days=i), "de", kurz=False) for i in range(7)}
    tage_en = {fmt_weekday(date(2026, 10, 26) + timedelta(days=i), "en") for i in range(7)}
    assert len(tage_de) == 7 and len(tage_en) == 7
    assert fmt_date(date(2026, 10, 26), "en") == "Mon 26 Oct"
    assert fmt_date(date(2026, 11, 1), "de") == "So 01.11."
    monate = {fmt_date(date(2026, m, 1), "en", "lang").split(" ")[2] for m in range(1, 13)}
    assert len(monate) == 12
    assert fmt_date(date(2026, 3, 1), "de", "lang") == "Sonntag, 1. März 2026"


@pytest.mark.parametrize("delta", [-1, 3, 7])
def test_relative_day_ausserhalb_null_bis_zwei(delta):
    with pytest.raises(ValueError):
        relative_day(delta, "de")


def test_unabhaengig_von_prozess_locale(monkeypatch):
    monkeypatch.setenv("LC_ALL", "fr_FR.UTF-8")
    alt = locale.setlocale(locale.LC_TIME)
    for kandidat in ("fr_FR.UTF-8", "de_DE.UTF-8", "C.UTF-8"):
        try:
            locale.setlocale(locale.LC_TIME, kandidat)
            break
        except locale.Error:
            continue
    try:
        _alle_pruefen()
    finally:
        locale.setlocale(locale.LC_TIME, alt)
