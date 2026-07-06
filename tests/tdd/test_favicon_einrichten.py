"""
RED-Tests: Favicon-Setup für gregor.zwanzig

Prüft ob alle Favicon-Artefakte vorhanden sind und die korrekte
Brand-Geometrie (Bergkamm + Blitz) enthalten.
"""
import json
from pathlib import Path

FRONTEND = Path(__file__).parents[2] / "frontend"
STATIC = FRONTEND / "static"
ASSETS = FRONTEND / "src" / "lib" / "assets"
APP_HTML = FRONTEND / "src" / "app.html"

BRAND_PATHS = [
    "M48 11",   # Blitz-Start
    "M3 54",    # Hauptkamm-Start
]
ACCENT_COLOR = "#c45a2a"
INK_COLOR = "#1a1a18"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestFaviconSvg:
    def test_favicon_svg_exists(self):
        assert (ASSETS / "favicon.svg").exists(), "favicon.svg fehlt in src/lib/assets/"

    def test_favicon_svg_contains_brand_geometry(self):
        content = read(ASSETS / "favicon.svg")
        for path in BRAND_PATHS:
            assert path in content, f"Brand-Pfad '{path}' fehlt in favicon.svg"

    def test_favicon_svg_uses_accent_color(self):
        content = read(ASSETS / "favicon.svg")
        assert ACCENT_COLOR in content, f"Accent-Farbe {ACCENT_COLOR} fehlt in favicon.svg"

    def test_favicon_svg_uses_ink_color(self):
        content = read(ASSETS / "favicon.svg")
        assert INK_COLOR in content, f"Ink-Farbe {INK_COLOR} fehlt in favicon.svg"

    def test_favicon_svg_is_valid_xml(self):
        import xml.etree.ElementTree as ET
        content = read(ASSETS / "favicon.svg")
        root = ET.fromstring(content)
        assert root.tag.endswith("svg"), "favicon.svg ist kein gültiges SVG"


class TestStaticFavicons:
    def test_favicon_ico_exists(self):
        assert (STATIC / "favicon.ico").exists(), "favicon.ico fehlt in static/"

    def test_favicon_ico_not_empty(self):
        size = (STATIC / "favicon.ico").stat().st_size
        assert size > 100, f"favicon.ico ist zu klein ({size} Bytes) — vermutlich leer"

    def test_apple_touch_icon_exists(self):
        assert (STATIC / "apple-touch-icon.png").exists(), "apple-touch-icon.png fehlt in static/"

    def test_apple_touch_icon_is_png(self):
        data = (STATIC / "apple-touch-icon.png").read_bytes()
        assert data[:4] == b"\x89PNG", "apple-touch-icon.png ist kein valides PNG"

    def test_favicon_192_exists(self):
        assert (STATIC / "favicon-192.png").exists(), "favicon-192.png fehlt in static/"

    def test_favicon_512_exists(self):
        assert (STATIC / "favicon-512.png").exists(), "favicon-512.png fehlt in static/"

    def test_favicon_192_is_png(self):
        data = (STATIC / "favicon-192.png").read_bytes()
        assert data[:4] == b"\x89PNG", "favicon-192.png ist kein valides PNG"

    def test_favicon_512_is_png(self):
        data = (STATIC / "favicon-512.png").read_bytes()
        assert data[:4] == b"\x89PNG", "favicon-512.png ist kein valides PNG"


class TestWebManifest:
    def test_site_webmanifest_exists(self):
        assert (STATIC / "site.webmanifest").exists(), "site.webmanifest fehlt in static/"

    def test_site_webmanifest_is_valid_json(self):
        content = read(STATIC / "site.webmanifest")
        data = json.loads(content)
        assert isinstance(data, dict), "site.webmanifest ist kein JSON-Objekt"

    def test_site_webmanifest_has_required_fields(self):
        data = json.loads(read(STATIC / "site.webmanifest"))
        assert "name" in data, "site.webmanifest: 'name' fehlt"
        assert "icons" in data, "site.webmanifest: 'icons' fehlt"
        assert "theme_color" in data, "site.webmanifest: 'theme_color' fehlt"

    def test_site_webmanifest_has_two_icon_sizes(self):
        data = json.loads(read(STATIC / "site.webmanifest"))
        icons = data.get("icons", [])
        sizes = {icon.get("sizes") for icon in icons}
        assert "192x192" in sizes, "site.webmanifest: 192×192-Icon fehlt"
        assert "512x512" in sizes, "site.webmanifest: 512×512-Icon fehlt"

    def test_site_webmanifest_theme_color(self):
        data = json.loads(read(STATIC / "site.webmanifest"))
        assert data.get("theme_color") == "#f6f4ee", "theme_color sollte #f6f4ee (--g-paper) sein"


class TestAppHtml:
    def test_app_html_has_ico_link(self):
        content = read(APP_HTML)
        assert 'href="/favicon.ico"' in content, "<link> auf favicon.ico fehlt in app.html"

    def test_app_html_has_svg_link(self):
        content = read(APP_HTML)
        assert 'type="image/svg+xml"' in content, "<link> auf favicon.svg (type=svg+xml) fehlt in app.html"

    def test_app_html_has_apple_touch_icon(self):
        content = read(APP_HTML)
        assert "apple-touch-icon" in content, "<link rel=apple-touch-icon> fehlt in app.html"

    def test_app_html_has_manifest_link(self):
        content = read(APP_HTML)
        assert 'rel="manifest"' in content, "<link rel=manifest> fehlt in app.html"
