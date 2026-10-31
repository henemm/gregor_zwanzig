"""Datums-, Wochentags-, Zeit- und Relativtag-Format (Issue #2662).

Feste Namenstabellen statt ``strftime``: keine Prozess-Locale spielt hinein.
Jede Sprache ausser ``en`` gilt als ``de``.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from i18n.lang import Lang

_WOCHENTAGE = {
    "de": ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
}
_WOCHENTAGE_KURZ = {
    "de": ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}
_MONATE = {
    "de": ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
           "August", "September", "Oktober", "November", "Dezember"),
    "en": ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"),
}
_RELATIV = {
    "de": ("heute", "morgen", "übermorgen"),
    "en": ("today", "tomorrow", "day after tomorrow"),
}


def _sprache(lang: object) -> str:
    return "en" if lang == "en" else "de"


def fmt_weekday(d: date | datetime, lang: Lang, kurz: bool = True) -> str:
    """``Do``/``Donnerstag`` bzw. ``Thu``/``Thursday``."""
    tabelle = _WOCHENTAGE_KURZ if kurz else _WOCHENTAGE
    return tabelle[_sprache(lang)][d.weekday()]


def fmt_date(
    d: date | datetime, lang: Lang, style: Literal["kurz", "lang"] = "kurz"
) -> str:
    """``Do 29.10.`` / ``Thu 29 Oct``; lang: ``Donnerstag, 29. Oktober 2026``."""
    s = _sprache(lang)
    if style == "lang":
        tag, monat = fmt_weekday(d, s, kurz=False), _MONATE[s][d.month - 1]  # type: ignore[arg-type]
        if s == "en":
            return f"{tag}, {d.day} {monat} {d.year}"
        return f"{tag}, {d.day}. {monat} {d.year}"
    tag = fmt_weekday(d, s)  # type: ignore[arg-type]
    if s == "en":
        return f"{tag} {d.day} {_MONATE['en'][d.month - 1][:3]}"
    return f"{tag} {d.day:02d}.{d.month:02d}."


def fmt_time(d: datetime) -> str:
    """``14:30`` in beiden Sprachen."""
    return f"{d.hour:02d}:{d.minute:02d}"


def relative_day(delta_days: int, lang: Lang) -> str:
    """``heute``/``morgen``/``übermorgen`` bzw. englisch; sonst ``ValueError``."""
    if delta_days not in (0, 1, 2):
        raise ValueError(f"relative_day: delta_days {delta_days!r} ausserhalb 0..2")
    return _RELATIV[_sprache(lang)][delta_days]
