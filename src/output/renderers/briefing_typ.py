"""Briefing-Art in Nutzersprache -- eine Quelle fuer Mail und Telegram.

Spec: docs/specs/modules/fix_3048_altbestand_telegram_kopf.md (#3052, #3047 AC-17)
"""
from __future__ import annotations

from i18n import Lang, t


def briefing_typ(report_type: str, lang: Lang) -> str:
    """Briefing-Art („Abend“/„Evening“) in Nutzersprache; unbekannte Typen
    fallen auf ``report_type.title()`` zurueck."""
    if report_type in ("morning", "evening", "alert"):
        # i18n-dynamic: mail.kopf.typ_
        return t(f"mail.kopf.typ_{report_type}", lang)
    return report_type.title()


__all__ = ["briefing_typ"]
