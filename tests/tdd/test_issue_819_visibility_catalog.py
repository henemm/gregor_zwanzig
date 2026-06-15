"""Issue #819 — Katalog-Ehrlichkeit visibility (numerisch-only seit #814).

RED vor Fix: Der Katalog trägt für `visibility` noch Friendly-Format-Metadaten
(`friendly_label`, `format_modes=("raw","simplified")`, `default_format_mode=
"simplified"`), obwohl die Metrik seit #814 ausschließlich als km-Zahl gerendert wird.
`has_friendly_format` lügt mit `True`.

GREEN nach Fix: friendly_label entfernt → has_friendly_format == False,
format_modes == ("raw",), default_format_mode == "raw"; der Loader löst Legacy-
use_friendly_format für visibility auf "raw" auf.

AC-4 (Render-Inertness — Sicht zeigt in jedem Modus km, kein englisches Wort) ist
mock-frei durch tests/tdd/test_issue_811_mode_matrix.py::
test_visibility_numeric_km_no_english_word abgedeckt (bleibt grün vor UND nach dem
Fix → beweist, dass diese Aufräumung verhaltens-inert ist).

KEINE Mocks — direkter Katalog-/Loader-Zugriff.
"""
from __future__ import annotations

from app.metric_catalog import get_metric


def test_ac1_visibility_has_no_friendly_format():
    """AC-1: visibility.has_friendly_format ist False (friendly_label leer)."""
    m = get_metric("visibility")
    assert m.has_friendly_format is False, (
        f"AC-1 RED: visibility soll keinen Einfach-Modus vortäuschen, "
        f"has_friendly_format war {m.has_friendly_format!r} (friendly_label="
        f"{m.friendly_label!r})"
    )


def test_ac2_visibility_only_raw_mode():
    """AC-2: visibility kennt nur den Roh-Modus."""
    m = get_metric("visibility")
    assert tuple(m.format_modes) == ("raw",), (
        f"AC-2 RED: format_modes soll ('raw',) sein, war {tuple(m.format_modes)!r}"
    )
    assert m.default_format_mode == "raw", (
        f"AC-2 RED: default_format_mode soll 'raw' sein, war {m.default_format_mode!r}"
    )


def test_ac3_loader_resolves_legacy_friendly_to_raw():
    """AC-3: Bestands-Config use_friendly_format=True → Render-Modus 'raw'."""
    from app import loader

    mode = loader._resolve_format_mode(
        {"metric_id": "visibility", "use_friendly_format": True},
        "visibility",
    )
    assert mode == "raw", (
        f"AC-3 RED: Legacy use_friendly_format=True für visibility soll auf 'raw' "
        f"auflösen (Katalog-Default), war '{mode}'"
    )
