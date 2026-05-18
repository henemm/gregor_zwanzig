"""Profil-Signaturen fuer Mail-Renderer.

Python-Port von frontend/src/lib/utils/profileSignature.ts (Issue #238).
Liefert pro ActivityProfile Akzentfarbe (Inline-Hex), Icon (Plain-Text-Emoji),
Eyebrow-Label (CAPS-Format) und icon_html (inline SVG fuer HTML-Mails).

Outlook ignoriert CSS-Variablen -- daher direkte Hex-Werte, kein var(--g-profile-...).

Bei None oder unbekanntem Wert wird die Signatur von ALLGEMEIN zurueckgegeben.

SPEC: docs/specs/modules/issue_255_email_profil_signaturen.md (CAPS-Eyebrows + SVG)
SPEC: docs/specs/modules/issue_241_email_profile_pipeline.md (Pipeline)
VORBILD: frontend/src/lib/utils/profileSignature.ts
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.profile import ActivityProfile


@dataclass(frozen=True)
class ProfileSignature:
    accent_hex: str   # Inline-Hex fuer Outlook-kompatibles Inline-CSS
    icon: str         # Unicode-Glyph (Plain-Text-Fallback)
    eyebrow: str      # Sichtbares CAPS-Label
    icon_html: str    # Inline SVG fuer HTML-Mails (Gmail/Apple Mail)


_SVG_WINTERSPORT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
    'style="display:inline;vertical-align:middle" viewBox="0 0 14 14">'
    '<line stroke="#4a7fb5" stroke-width="1.5" stroke-linecap="round" x1="7" y1="1" x2="7" y2="13"/>'
    '<line stroke="#4a7fb5" stroke-width="1.5" stroke-linecap="round" x1="1" y1="7" x2="13" y2="7"/>'
    '<line stroke="#4a7fb5" stroke-width="1.5" stroke-linecap="round" x1="2.76" y1="2.76" x2="11.24" y2="11.24"/>'
    '<line stroke="#4a7fb5" stroke-width="1.5" stroke-linecap="round" x1="11.24" y1="2.76" x2="2.76" y2="11.24"/>'
    '</svg>'
)

_SVG_WANDERN = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
    'style="display:inline;vertical-align:middle" viewBox="0 0 14 14">'
    '<path fill="#3a7d44" d="M7 1 L13 13 H1 Z"/>'
    '</svg>'
)

_SVG_SUMMER_TREKKING = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
    'style="display:inline;vertical-align:middle" viewBox="0 0 14 14">'
    '<path fill="#c45a2a" d="M5 8 L9 1 L13 8 H5 Z"/>'
    '<path fill="#c45a2a" d="M1 13 L5 7 L9 13 H1 Z"/>'
    '</svg>'
)

_SVG_ALLGEMEIN = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
    'style="display:inline;vertical-align:middle" viewBox="0 0 14 14">'
    '<circle cx="7" cy="7" r="5.5" stroke="#6b675c" stroke-width="1.5" fill="none"/>'
    '<polygon fill="#6b675c" points="7,2.5 8.5,7 7,8.5 5.5,7"/>'
    '</svg>'
)


_SIGNATURES: dict[ActivityProfile, ProfileSignature] = {
    ActivityProfile.WINTERSPORT: ProfileSignature(
        accent_hex='#4a7fb5',
        icon='❄',           # Schneeflocke
        eyebrow='WINTERSPORT · PISTE',
        icon_html=_SVG_WINTERSPORT,
    ),
    ActivityProfile.WANDERN: ProfileSignature(
        accent_hex='#3a7d44',
        icon='\U0001F97E',       # Wanderschuh
        eyebrow='WANDERN',
        icon_html=_SVG_WANDERN,
    ),
    ActivityProfile.SUMMER_TREKKING: ProfileSignature(
        accent_hex='#c45a2a',
        icon='\U0001F3D4',       # Berg-Symbol
        eyebrow='ALPINE TOUR',
        icon_html=_SVG_SUMMER_TREKKING,
    ),
    ActivityProfile.ALLGEMEIN: ProfileSignature(
        accent_hex='#6b675c',
        icon='◯',           # Kreis (large circle)
        eyebrow='WETTER-BRIEFING',
        icon_html=_SVG_ALLGEMEIN,
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
