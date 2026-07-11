"""TDD tests for Issue #810 — "Roh"-Format ignoriert Ampelpunkt-Override.

Bug: In fmt_val geben wind/gust (Z.446-448), precip (Z.460-461) und pop
(Z.500-501) im HTML-Pfad UNBEDINGT ampel_dot(...) zurueck — VOR jeder Pruefung
von use_friendly/mode. Dadurch ignoriert das "raw"-Format (format_modes={key:"raw"})
den Nutzerwunsch und zeigt trotzdem die Ampel-Emojis.

RED phase: AC-1..AC-3 schlagen fehl (Ampel-Emoji statt Zahl), AC-4/AC-5 sind
bereits gruen (Regress-Sicherung gegen #759).

SPEC: docs/specs/modules/issue_810_raw_format_ampel.md AC-1..AC-6 (AC-6 = E2E,
hier ausgelassen).
IMPORTANT: NO mocks, NO patch, NO MagicMock. Real fmt_val calls only.
"""
from __future__ import annotations

from src.output.renderers.email.helpers import fmt_val

# Issue #1222: Ampelpunkte sind jetzt gestylte CSS-Dots (kein Kreis-Emoji mehr).
_CIRCLE_EMOJIS = ("🟢", "🟡", "🟠", "🔴")


def _has_ampel(s: str) -> bool:
    """True wenn s einen CSS-Ampel-Dot ODER (Regress) ein Kreis-Emoji enthaelt."""
    return "border-radius:50%" in s or any(e in s for e in _CIRCLE_EMOJIS)


# ---------------------------------------------------------------------------
# AC-1: Wind/Boen im "raw"-Format zeigen die Zahl, KEIN Ampel-Emoji
# ---------------------------------------------------------------------------

class TestWindGustRawFormat:
    """AC-1: format_modes={key:'raw'} liefert numerischen Wert ohne Ampelpunkt."""

    def test_issue810_wind_raw_shows_number_no_ampel(self):
        result = fmt_val("wind", 33, html=True, format_modes={"wind": "raw"})
        assert "33" in result, f"Wind raw should contain '33': {result!r}"
        assert not _has_ampel(result), (
            f"Wind raw must NOT contain ampel emoji: {result!r}"
        )

    def test_issue810_gust_raw_shows_number_no_ampel(self):
        result = fmt_val("gust", 55, html=True, format_modes={"gust": "raw"})
        assert "55" in result, f"Gust raw should contain '55': {result!r}"
        assert not _has_ampel(result), (
            f"Gust raw must NOT contain ampel emoji: {result!r}"
        )


# ---------------------------------------------------------------------------
# AC-2: Regen im "raw"-Format zeigt die Zahl, KEIN Ampel-Emoji
# ---------------------------------------------------------------------------

class TestPrecipRawFormat:
    """AC-2: format_modes={'precip':'raw'} liefert numerischen Wert ohne Ampelpunkt."""

    def test_issue810_precip_raw_shows_number_no_ampel(self):
        result = fmt_val("precip", 2.4, html=True, format_modes={"precip": "raw"})
        assert "2.4" in result, f"Precip raw should contain '2.4': {result!r}"
        assert not _has_ampel(result), (
            f"Precip raw must NOT contain ampel emoji: {result!r}"
        )


# ---------------------------------------------------------------------------
# AC-3: Regenwahrscheinlichkeit im "raw"-Format zeigt die Zahl, KEIN Ampel-Emoji
# ---------------------------------------------------------------------------

class TestPopRawFormat:
    """AC-3: format_modes={'pop':'raw'} liefert numerischen Wert ohne Ampelpunkt."""

    def test_issue810_pop_raw_shows_number_no_ampel(self):
        result = fmt_val("pop", 60, html=True, format_modes={"pop": "raw"})
        assert "60" in result, f"Pop raw should contain '60': {result!r}"
        assert not _has_ampel(result), (
            f"Pop raw must NOT contain ampel emoji: {result!r}"
        )


# ---------------------------------------------------------------------------
# AC-4: Regress-Sicherung — Ampel bleibt bei echtem Produktions-Modus "simplified"
# ---------------------------------------------------------------------------

class TestSimplifiedFormatStillAmpel:
    """AC-4 (massgeblich): format_modes={key:'simplified'} liefert Ampelpunkt im HTML.

    "simplified" ist der echte Katalog-Modus fuer wind/gust/precip/pop (UI "Einfach").
    Der Ampelpunkt muss fuer diesen Pfad unveraendert erhalten bleiben (#759-Regress).
    """

    def test_issue810_wind_simplified_still_ampel(self):
        result = fmt_val("wind", 33, html=True, format_modes={"wind": "simplified"})
        assert _has_ampel(result), (
            f"Wind simplified/html must BE one ampel emoji: {result!r}"
        )

    def test_issue810_gust_simplified_still_ampel(self):
        result = fmt_val("gust", 55, html=True, format_modes={"gust": "simplified"})
        assert _has_ampel(result), (
            f"Gust simplified/html must BE one ampel emoji: {result!r}"
        )

    def test_issue810_precip_simplified_still_ampel(self):
        result = fmt_val("precip", 2.4, html=True, format_modes={"precip": "simplified"})
        assert _has_ampel(result), (
            f"Precip simplified/html must BE one ampel emoji: {result!r}"
        )

    def test_issue810_pop_simplified_still_ampel(self):
        result = fmt_val("pop", 60, html=True, format_modes={"pop": "simplified"})
        assert _has_ampel(result), (
            f"Pop simplified/html must BE one ampel emoji: {result!r}"
        )


class TestIndicatorFormatStillAmpel:
    """AC-4 (zusaetzlich): format_modes={key:'indicator'} liefert ebenfalls Ampelpunkt.

    'indicator' ist kein Katalog-Modus, aber da mode != 'raw' greift die Ampel.
    Diese Tests sichern das Verhalten fuer beliebige Nicht-'raw'-Werte ab.
    """

    def test_issue810_wind_indicator_still_ampel(self):
        result = fmt_val("wind", 33, html=True, format_modes={"wind": "indicator"})
        assert _has_ampel(result), (
            f"Wind indicator must BE one ampel emoji: {result!r}"
        )

    def test_issue810_precip_indicator_still_ampel(self):
        result = fmt_val("precip", 2.4, html=True, format_modes={"precip": "indicator"})
        assert _has_ampel(result), (
            f"Precip indicator must BE one ampel emoji: {result!r}"
        )

    def test_issue810_pop_indicator_still_ampel(self):
        result = fmt_val("pop", 60, html=True, format_modes={"pop": "indicator"})
        assert _has_ampel(result), (
            f"Pop indicator must BE one ampel emoji: {result!r}"
        )


# ---------------------------------------------------------------------------
# AC-5: Plain-Text bleibt numerisch, kein Ampel-Emoji (auch bei 'indicator')
# ---------------------------------------------------------------------------

class TestPlainTextNoAmpel:
    """AC-5: html=False liefert nie ein Ampel-Emoji."""

    def test_issue810_wind_plain_indicator_no_ampel(self):
        result = fmt_val("wind", 33, html=False, format_modes={"wind": "indicator"})
        assert not _has_ampel(result), (
            f"Wind plain must NOT contain ampel emoji: {result!r}"
        )
