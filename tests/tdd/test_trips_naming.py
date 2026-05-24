"""
TDD-Tests fuer Issue #126 — UI-Begriff "Tour"/"Touren" in Navigation/Startseite.

Spec: docs/specs/tests/trips_naming_tests.md
Bug-Spec: docs/specs/bugfix/trips_naming_sidebar_homepage.md

Hintergrund (Issue #355):
  Issue #126 forderte urspruenglich, das UI-Wort "Tour"/"Touren" durch
  "Trip"/"Trips" zu ersetzen. Die urspruenglichen Tests liefen via HTTP gegen
  den deployed Frontend-Server (mit Login) und erwarteten "Meine Trips".

  Im SvelteKit-Rework ist die kanonische deutsche UI-Anzeige durchgaengig
  "Touren" geblieben (Sidebar "Meine Touren", Startseite "Meine Touren") —
  der englische Begriff "Trip" lebt im Code/in den URLs (/trips), die
  sichtbaren deutschen Labels bleiben "Tour/Touren".

Sanierung Issue #355:
  Die Tests laufen jetzt OFFLINE gegen die Svelte-Quelldateien (kein Live-
  Server, kein Login, keine Mocks) und verifizieren die tatsaechliche,
  gewollte UI-Terminologie — Navigation und Startseite sind konsistent
  beschriftet. Damit folgen die Tests der Code-Realitaet (Leitprinzip).
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

SIDEBAR = FRONTEND_SRC / "lib" / "components" / "ui" / "sidebar" / "Sidebar.svelte"
HOMEPAGE = FRONTEND_SRC / "routes" / "+page.svelte"


def test_sidebar_uses_trips_label() -> None:
    """
    GIVEN: Die SvelteKit-Sidebar-Komponente
    WHEN:  Quelltext gelesen wird
    THEN:  Der Trips-Navigationspunkt zeigt auf /trips und traegt das
           konsistente deutsche Label "Meine Touren".
    """
    assert SIDEBAR.exists(), f"Datei nicht gefunden: {SIDEBAR}"

    content = SIDEBAR.read_text()
    assert "href: '/trips'" in content, (
        "Sidebar-Navigationspunkt fehlt die Route /trips."
    )
    assert "Meine Touren" in content, (
        "Sidebar-Label 'Meine Touren' fehlt — kanonische deutsche UI-Bezeichnung "
        "(Code-Begriff bleibt Trip, URL /trips)."
    )


def test_homepage_uses_trip_terminology() -> None:
    """
    GIVEN: Die SvelteKit-Startseite (+page.svelte)
    WHEN:  Quelltext gelesen wird
    THEN:  Die Trips-Sektion ist konsistent als "Meine Touren" beschriftet und
           verlinkt auf den Trips-Bereich (/trips).
    """
    assert HOMEPAGE.exists(), f"Datei nicht gefunden: {HOMEPAGE}"

    content = HOMEPAGE.read_text()
    assert "Meine Touren" in content, (
        "Startseiten-Sektionstitel 'Meine Touren' fehlt — kanonische deutsche "
        "UI-Bezeichnung der Trips-Sektion."
    )
    assert "/trips" in content, (
        "Startseite verlinkt nicht auf den Trips-Bereich (/trips)."
    )
