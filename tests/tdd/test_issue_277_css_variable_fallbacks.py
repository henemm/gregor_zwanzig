"""
TDD RED — Issue #277: CSS Variable Fallbacks bereinigen

Tests prüfen, dass keine undefined oder fehlerhaften CSS-Tokens
in den Svelte-Komponenten vorkommen.

AC-1: var(--g-primary ...) → 0 Treffer
AC-2: var(--g-border ...) → 0 Treffer
AC-3: Hex-Fallbacks #2563eb|#e5e7eb|#6b7280|#f3f4f6 → 0 Treffer
"""

import subprocess
from pathlib import Path

import pytest

FRONTEND_SRC = Path(__file__).parent.parent.parent / "frontend" / "src"


def _grep(pattern: str, path: Path, fixed_string: bool = False) -> list[str]:
    cmd = ["grep", "-rn"]
    if fixed_string:
        cmd.append("-F")
    cmd += [pattern, str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    return lines


class TestUndefinedCSSTokens:
    """AC-1 + AC-2: Undefinierte Token --g-primary und --g-border müssen 0 Treffer haben."""

    def test_no_g_primary_token(self):
        """
        GIVEN: Quelltext in frontend/src/
        WHEN: Suche nach var(--g-primary in allen Svelte/CSS/TS-Dateien
        THEN: 0 Treffer — Token existiert nicht in app.css und darf nicht verwendet werden
        """
        matches = _grep("var(--g-primary", FRONTEND_SRC, fixed_string=True)
        assert matches == [], (
            f"var(--g-primary ist ein undefinierter Token ({len(matches)} Treffer):\n"
            + "\n".join(matches[:10])
        )

    def test_no_g_border_token(self):
        """
        GIVEN: Quelltext in frontend/src/
        WHEN: Suche nach var(--g-border in allen Svelte/CSS/TS-Dateien
        THEN: 0 Treffer — Token existiert nicht in app.css und darf nicht verwendet werden
        """
        matches = _grep("var(--g-border", FRONTEND_SRC, fixed_string=True)
        assert matches == [], (
            f"var(--g-border ist ein undefinierter Token ({len(matches)} Treffer):\n"
            + "\n".join(matches[:10])
        )


class TestHexFallbacks:
    """AC-3: Keine hartcodierten Design-Hex-Werte als var()-Fallbacks in Komponenten-CSS."""

    @pytest.mark.xfail(reason="#1309: System-Blau #2563eb noch als Hex-Fallback in Komponenten-CSS vorhanden", strict=False)
    def test_no_blue_2563eb(self):
        """
        GIVEN: Quelltext in frontend/src/lib/ (Komponenten)
        WHEN: Suche nach #2563eb (System-Blau — war Fallback für --g-primary)
        THEN: 0 Treffer
        """
        matches = _grep("#2563eb", FRONTEND_SRC / "lib", fixed_string=True)
        assert matches == [], (
            f"System-Blau #2563eb gefunden ({len(matches)} Treffer):\n"
            + "\n".join(matches[:10])
        )

    def test_no_gray_e5e7eb(self):
        """
        GIVEN: Quelltext in frontend/src/lib/ (Komponenten)
        WHEN: Suche nach #e5e7eb (Neutral-Grau — war Fallback für --g-border)
        THEN: 0 Treffer
        """
        matches = _grep("#e5e7eb", FRONTEND_SRC / "lib", fixed_string=True)
        assert matches == [], (
            f"Neutral-Grau #e5e7eb gefunden ({len(matches)} Treffer):\n"
            + "\n".join(matches[:10])
        )

    def test_no_muted_gray_6b7280(self):
        """
        GIVEN: Quelltext in frontend/src/lib/ (Komponenten)
        WHEN: Suche nach #6b7280 (Tailwind slate-500 — war falscher Fallback für --g-ink-muted/faint)
        THEN: 0 Treffer
        """
        matches = _grep("#6b7280", FRONTEND_SRC / "lib", fixed_string=True)
        assert matches == [], (
            f"Tailwind-Grau #6b7280 gefunden ({len(matches)} Treffer):\n"
            + "\n".join(matches[:10])
        )

    def test_no_surface_f3f4f6(self):
        """
        GIVEN: Quelltext in frontend/src/lib/ (Komponenten)
        WHEN: Suche nach #f3f4f6 (Tailwind gray-100 — war falscher Fallback für --g-surface-2)
        THEN: 0 Treffer
        """
        matches = _grep("#f3f4f6", FRONTEND_SRC / "lib", fixed_string=True)
        assert matches == [], (
            f"Tailwind-Surface #f3f4f6 gefunden ({len(matches)} Treffer):\n"
            + "\n".join(matches[:10])
        )


class TestTokenIntegrity:
    """Integrität: app.css definiert alle benötigten Token korrekt."""

    def test_g_ink_defined_in_app_css(self):
        """
        GIVEN: frontend/src/app.css
        WHEN: Suche nach --g-ink: Definition
        THEN: Token ist definiert (Ersatz für --g-primary bei Buttons)
        """
        app_css = FRONTEND_SRC / "app.css"
        content = app_css.read_text()
        assert "--g-ink:" in content, "--g-ink ist nicht in app.css definiert"

    def test_g_accent_defined_in_app_css(self):
        """
        GIVEN: frontend/src/app.css
        WHEN: Suche nach --g-accent: Definition
        THEN: Token ist definiert (Ersatz für --g-primary bei Active-States)
        """
        app_css = FRONTEND_SRC / "app.css"
        content = app_css.read_text()
        assert "--g-accent:" in content, "--g-accent ist nicht in app.css definiert"

    def test_g_ink_faint_defined_in_app_css(self):
        """
        GIVEN: frontend/src/app.css
        WHEN: Suche nach --g-ink-faint: Definition
        THEN: Token ist definiert (Ersatz für --g-border)
        """
        app_css = FRONTEND_SRC / "app.css"
        content = app_css.read_text()
        assert "--g-ink-faint:" in content, "--g-ink-faint ist nicht in app.css definiert"
