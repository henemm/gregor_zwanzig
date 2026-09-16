"""TDD RED — Issue #2341, AC-7 und AC-8.

SPEC: docs/specs/modules/brand_icon_silhouette.md

Zwei doc-compliance-Pruefungen (CLAUDE.md-Ausnahme von der
"kein Dateiinhalt-Check"-Regel, weil beide Ziele KEINE eigene
Laufzeitumgebung haben):

- AC-7: `brand-kit.jsx` ist die kanonische Referenzquelle fuer den
  Marken-Glyphen, wird aber nirgends importiert/ausgefuehrt -- ein
  Verhaltensnachweis ist strukturell unmoeglich, der Textabgleich mit
  den Svelte-Portierungen IST die einzig moegliche Pruefung.
- AC-8: `favicon-einrichten.md` ist eine Markdown-Spec ohne Laufzeit --
  der Status-Vermerk "Abgeloest durch" ist reine Dokumentkonsistenz.

Ausfuehrung:
    uv run pytest tests/test_brand_icon_silhouette.py -v
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BRAND_KIT = REPO_ROOT / "docs/design-requests/issue_15_atomic_design/spec/brand-kit.jsx"
FAVICON_SPEC = REPO_ROOT / "docs/specs/modules/favicon-einrichten.md"

# Bergkamm-Pfad ist geometrisch unveraendert -- nur fill statt stroke.
BERGKAMM_D = "M3 54 L18 22 L29 38 L38 26 L52 50 L61 54 Z"
BLITZ_D = "M48 11 L41 23 L45 23 L43 29 L50 17 L46 17 Z"
NEBENKANTE_D = "M3 54 L18 22 L25 32"


def _function_body(source: str, function_name: str) -> str:
    """Schneidet den Quelltext-Block einer `function <name>(` bis zur
    naechsten `function `-Deklaration heraus -- vermeidet einen
    Volltext-Suchtreffer, der auch in einer anderen Funktion liegen
    koennte (analog zum bestehenden Muster in
    issue_481_mobile_header_icons.test.ts)."""
    start = source.index(f"function {function_name}(")
    rest = source[start + len(f"function {function_name}(") :]
    next_fn = rest.find("\nfunction ")
    end = len(rest) if next_fn == -1 else next_fn
    return rest[:end]


class TestAC7BrandKitReferenzKonsistenz:
    """AC-7: brand-kit.jsx enthaelt dieselbe Fill-Silhouette + 1,35x-Blitz
    wie die Svelte-Portierungen. # doc-compliance-test"""

    def test_brand_kit_existiert(self):
        assert BRAND_KIT.is_file(), f"{BRAND_KIT} fehlt"

    def test_brand_icon_bergkamm_ist_fill_statt_stroke(self):
        src = BRAND_KIT.read_text(encoding="utf-8")
        body = _function_body(src, "BrandIcon")
        assert f'd="{BERGKAMM_D}"' in body, "Bergkamm-Pfad in BrandIcon fehlt/geaendert"
        # Der Bergkamm-Pfad selbst muss ein fill tragen und darf keinen
        # eigenen stroke mehr haben (Silhouette statt Kontur).
        path_start = body.index(f'd="{BERGKAMM_D}"')
        path_tag = body[max(0, path_start - 10) : path_start + 200]
        assert "fill=" in path_tag and "#1a1a18" in path_tag or "inkPrimary" in path_tag, (
            "BrandIcon-Bergkamm traegt in brand-kit.jsx noch keine Fill-Farbe "
            "(AC-7: Silhouette statt Kontur)."
        )
        assert "stroke=" not in path_tag, (
            "BrandIcon-Bergkamm traegt in brand-kit.jsx noch ein stroke-Attribut "
            "-- das ist die ALTE Kontur-Optik, AC-7 verlangt reinen Fill."
        )

    def test_brand_icon_blitz_ist_vergroessert(self):
        src = BRAND_KIT.read_text(encoding="utf-8")
        body = _function_body(src, "BrandIcon")
        assert "scale(1.35)" in body, (
            "BrandIcon in brand-kit.jsx enthaelt keine scale(1.35)-Transformation "
            "um den Blitz-Schwerpunkt (45.5, 20) -- AC-7 verlangt den "
            "proportional groesseren Blitz aus der PO-Entscheidung."
        )

    def test_brand_icon_square_hat_keine_nebenkante_mehr(self):
        src = BRAND_KIT.read_text(encoding="utf-8")
        body = _function_body(src, "BrandIconSquare")
        assert f'd="{NEBENKANTE_D}"' not in body, (
            "BrandIconSquare in brand-kit.jsx enthaelt noch die Nebenkante -- "
            "AC-7/AC-2 verlangen, dass sie ersatzlos entfaellt."
        )
        assert "y1=\"58\"" not in body and "y1='58'" not in body, (
            "BrandIconSquare in brand-kit.jsx enthaelt noch die separate "
            "Horizontlinie -- AC-7/AC-2 verlangen, dass sie ersatzlos entfaellt."
        )


class TestAC8FaviconSpecAbgeloest:
    """AC-8: favicon-einrichten.md traegt einen Status-Vermerk auf die
    neue Spec. # doc-compliance-test"""

    def test_favicon_spec_existiert(self):
        assert FAVICON_SPEC.is_file(), f"{FAVICON_SPEC} fehlt"

    def test_favicon_spec_ist_als_abgeloest_markiert(self):
        text = FAVICON_SPEC.read_text(encoding="utf-8")
        assert "Abgel" in text and "brand_icon_silhouette" in text, (
            "favicon-einrichten.md fehlt der Vermerk 'Abgeloest durch "
            "docs/specs/modules/brand_icon_silhouette.md' (AC-8) -- die "
            "widerspruechliche AC-2 ('kein abgeschnittenes Icon') steht "
            "sonst kommentarlos neben dem Ticket-Befund #2341."
        )
