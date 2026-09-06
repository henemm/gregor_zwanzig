"""TDD RED — Issue #2128 (Scheibe 1 zu Epic #2127), AC-2.

SPEC: docs/specs/modules/pwa_installierbar_offline_start.md, AC-2

Geprueft wird der BILDINHALT des maskable Symbols, nicht sein Vorhandensein:
Android schneidet ein `purpose: maskable`-Symbol rund zu und darf dabei nichts
vom Motiv erwischen. Alles ausserhalb der mittleren 80 % der Kantenlaenge liegt
in dieser Schnittzone.

Kein Dateiinhalt-Check im verbotenen Sinn (`'xyz' in read_text()`), sondern
echte Pixelauswertung mit Pillow.

Die Randpruefung traegt ihre eigene Positivkontrolle: dieselbe Funktion wird auf
das BESTEHENDE `favicon-512.png` angewandt, das randfuellend ist. Schlaegt sie
dort nicht an, misst sie nichts — dann ist auch ein gruener Befund auf dem
maskable Symbol wertlos.

Ausfuehrung:
    uv run pytest tests/test_pwa_maskable_icon.py -v
"""
from __future__ import annotations

from pathlib import Path

# Der Prueflings-Pfad wird RELATIV zur Testdatei aufgeloest -- sonst misst ein
# Lauf aus einem Worktree heraus die Dateien des Hauptrepos (falsches Gruen).
STATIC_DIR = Path(__file__).resolve().parents[1] / "frontend" / "static"
MASKABLE_ICON = STATIC_DIR / "icon-maskable-512.png"
RANDFUELLENDES_ICON = STATIC_DIR / "favicon-512.png"

# Hintergrund laut Spec (`background_color`/`theme_color` im Manifest).
BACKGROUND_RGB = (246, 244, 238)

# Android nimmt beim runden Zuschnitt den Rand weg; sicher ist nur die
# mittlere Flaeche. Die Spec beziffert sie mit 80 % der Kantenlaenge.
SAFE_FRACTION = 0.8


def border_pixels_other_than_background(
    path: Path,
    background: tuple[int, int, int] = BACKGROUND_RGB,
    safe_fraction: float = SAFE_FRACTION,
) -> list[tuple[int, int, tuple[int, int, int]]]:
    """Alle Pixel im Randbereich, die NICHT die Hintergrundfarbe tragen.

    Randbereich = alles ausserhalb der mittleren `safe_fraction` der
    Kantenlaenge, also der Streifen, den der runde Zuschnitt wegnimmt.
    Rueckgabe: Liste von (x, y, rgb) -- leer heisst "Motiv liegt vollstaendig
    in der Schutzzone".
    """
    from PIL import Image

    with Image.open(path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size
        margin_x = int(round(width * (1.0 - safe_fraction) / 2.0))
        margin_y = int(round(height * (1.0 - safe_fraction) / 2.0))
        pixels = rgb.load()

        found: list[tuple[int, int, tuple[int, int, int]]] = []
        for y in range(height):
            in_vertical_band = y < margin_y or y >= height - margin_y
            for x in range(width):
                in_horizontal_band = x < margin_x or x >= width - margin_x
                if not (in_vertical_band or in_horizontal_band):
                    continue
                value = pixels[x, y]
                if value != background:
                    found.append((x, y, value))
        return found


class TestAC2MaskableIconSchutzzone:
    """AC-2: das Bergmotiv liegt vollstaendig in der Schutzzone."""

    def test_maskable_icon_existiert(self):
        assert MASKABLE_ICON.is_file(), (
            f"{MASKABLE_ICON} fehlt -- ohne maskable Symbol schneidet Android "
            "das randfuellende favicon-512.png an (AC-2)."
        )

    def test_maskable_icon_ist_512x512(self):
        from PIL import Image

        assert MASKABLE_ICON.is_file(), f"{MASKABLE_ICON} fehlt"
        with Image.open(MASKABLE_ICON) as img:
            assert img.size == (512, 512), (
                f"Manifest kuendigt 512x512 an, Datei ist {img.size} (AC-1/AC-2)."
            )

    def test_rand_traegt_ausschliesslich_die_hintergrundfarbe(self):
        assert MASKABLE_ICON.is_file(), f"{MASKABLE_ICON} fehlt"
        fremde = border_pixels_other_than_background(MASKABLE_ICON)
        assert fremde == [], (
            f"{len(fremde)} Motivpixel liegen im Schnittrand (ausserhalb der "
            f"mittleren {int(SAFE_FRACTION * 100)} %), z.B. {fremde[:5]}. "
            "Android wuerde sie wegschneiden (AC-2)."
        )


class TestRandpruefungMisstUeberhauptEtwas:
    """Positivkontrolle — heute schon gruen.

    Ohne diesen Test waere nicht belegt, dass die Randpruefung ueberhaupt
    anschlaegt: ein Pruefverfahren, das nie 'nicht bestanden' sagen kann,
    beweist auch mit gruenem Ergebnis nichts.
    """

    def test_randfuellendes_favicon_faellt_durch_dieselbe_pruefung(self):
        assert RANDFUELLENDES_ICON.is_file(), (
            f"{RANDFUELLENDES_ICON} fehlt -- ohne Vergleichsbild ist die "
            "Positivkontrolle nicht fuehrbar."
        )
        fremde = border_pixels_other_than_background(RANDFUELLENDES_ICON)
        assert fremde, (
            "Die Randpruefung findet im randfuellenden favicon-512.png KEIN "
            "Motivpixel -- dann misst sie nichts und ihr gruenes Ergebnis auf "
            "dem maskable Symbol ist wertlos."
        )
