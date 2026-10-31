"""Zweisprachigkeit de/en (Epic #2644, ADR-0104).

S1 (#2646): Nutzersprache. #2662: Katalog ``t``/``tn`` und Formatfunktionen.
Kein globaler Sprachzustand: ``lang`` wird immer ausdruecklich uebergeben.
"""
from __future__ import annotations

from i18n import catalog as _catalog
from i18n.format import fmt_date, fmt_time, fmt_weekday, relative_day
from i18n.lang import Lang, language_from_user_dict, resolve_user_lang

__all__ = [
    "Lang", "fmt_date", "fmt_time", "fmt_weekday", "language_from_user_dict",
    "relative_day", "resolve_user_lang", "t", "tn",
]


def _ersetze(key: str, text: str, params: dict[str, object]) -> str:
    kat = _catalog.get_catalog()

    def _wert(treffer) -> str:
        name = treffer.group(1)
        if name in params:
            return str(params[name])
        kat.melde_einmal("placeholder", f"{key} {{{name}}}")
        return treffer.group(0)

    return _catalog.PLATZHALTER_RE.sub(_wert, text)


def t(key: str, lang: Lang = "de", /, **params: object) -> str:
    """Text zu ``key`` in ``lang`` (Fallback de, dann der Schluessel selbst)."""
    text = _catalog.get_catalog().nachschlagen(key, lang)
    return _ersetze(key, text, params)


def tn(key: str, count: int, lang: Lang = "de", /, **params: object) -> str:
    """Pluralform: ``key.one`` genau bei ``count == 1``, sonst ``key.other``."""
    form = f"{key}.one" if count == 1 else f"{key}.other"
    return t(form, lang, **{"count": count, **params})
