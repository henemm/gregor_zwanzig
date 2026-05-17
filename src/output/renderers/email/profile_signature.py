"""Profil-Signaturen fuer Mail-Renderer.

Python-Port von frontend/src/lib/utils/profileSignature.ts (Issue #238).
Liefert pro ActivityProfile Akzentfarbe (Inline-Hex), Icon und Eyebrow-Label.
Outlook ignoriert CSS-Variablen -- daher direkte Hex-Werte, kein var(--g-profile-...).

Bei None oder unbekanntem Wert wird die Signatur von ALLGEMEIN zurueckgegeben.

SPEC: docs/specs/modules/issue_241_email_profile_pipeline.md
VORBILD: frontend/src/lib/utils/profileSignature.ts
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.profile import ActivityProfile


@dataclass(frozen=True)
class ProfileSignature:
    accent_hex: str   # Inline-Hex fuer Outlook-kompatibles Inline-CSS
    icon: str         # Unicode-Glyph
    eyebrow: str      # Sichtbares Label


_SIGNATURES: dict[ActivityProfile, ProfileSignature] = {
    ActivityProfile.WINTERSPORT: ProfileSignature(
        accent_hex='#4a7fb5',
        icon='❄',           # Schneeflocke
        eyebrow='Wintersport',
    ),
    ActivityProfile.WANDERN: ProfileSignature(
        accent_hex='#3a7d44',
        icon='\U0001F97E',       # Wanderschuh
        eyebrow='Wandern',
    ),
    ActivityProfile.SUMMER_TREKKING: ProfileSignature(
        accent_hex='#c45a2a',
        icon='\U0001F3D4',       # Berg-Symbol
        eyebrow='Sommer-Trekking',
    ),
    ActivityProfile.ALLGEMEIN: ProfileSignature(
        accent_hex='#6b675c',
        icon='◯',           # Kreis (large circle)
        eyebrow='Allgemein',
    ),
}

_FALLBACK = _SIGNATURES[ActivityProfile.ALLGEMEIN]


def profile_signature(profile: Optional[ActivityProfile]) -> ProfileSignature:
    """Liefert die ProfileSignature fuer ein ActivityProfile.

    Bei ``None`` oder unbekanntem Wert wird die ALLGEMEIN-Signatur zurueckgegeben
    (Fallback, kein Throw).
    """
    if profile is None:
        return _FALLBACK
    return _SIGNATURES.get(profile, _FALLBACK)


__all__ = ["ProfileSignature", "profile_signature"]
