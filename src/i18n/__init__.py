"""Zweisprachigkeit de/en (Epic #2644, ADR-0104).

S1 (#2646): Nutzersprache. Paket #2662 ergaenzt ``t``/``tn``.
"""
from i18n.lang import Lang, language_from_user_dict, resolve_user_lang

__all__ = ["Lang", "language_from_user_dict", "resolve_user_lang"]
