"""Herkunftssperre fuer Versandkanaele (Issue #1476).

Klassifiziert, aus welchem Checkout der aufrufende Kanal-Code stammt --
unabhaengig von Settings/.env/is_test_mode/env, von einem aufrufenden Skript
nicht abschaltbar. "test" ist der DEFAULT: jeder Pfad, der nicht exakt einer
der beiden bekannten Checkout-Wurzeln entspricht (jeder Arbeitsordner, jeder
Git-Worktree, jeder Klon).

Ein Git-Worktree liegt physisch INNERHALB von PROD_ROOT
(.claude/worktrees/<name>/...) -- ein Praefix- bzw. `is_relative_to()`-
Vergleich wuerde ihn faelschlich als Produktion einstufen. Deshalb wird die
Checkout-Wurzel ueber die bekannte, feste Tiefe der Kanal-Module
(`<wurzel>/src/output/channels/<datei>.py`) ermittelt und per EXAKTER
Gleichheit verglichen.

Spec: docs/specs/fast/fix-1476-telegram-herkunftssperre.md
"""
from __future__ import annotations

from pathlib import Path

PROD_ROOT = Path("/home/hem/gregor_zwanzig")
STAGING_ROOT = Path("/home/hem/gregor_zwanzig_staging")

# Ebenen von einem Kanal-Modul bis zur Checkout-Wurzel:
# <wurzel>/src/output/channels/<datei>.py -> channels(0)/output(1)/src(2)/wurzel(3)
_DEPTH_FROM_CHANNEL_MODULE = 3


def checkout_root(module_file: Path) -> Path:
    """Wurzel des Checkouts, aus dem `module_file` stammt."""
    return module_file.resolve().parents[_DEPTH_FROM_CHANNEL_MODULE]


def classify_origin(root: Path) -> str:
    """production/staging/test fuer eine Checkout-Wurzel (s. Moduldoku)."""
    if root == PROD_ROOT:
        return "production"
    if root == STAGING_ROOT:
        return "staging"
    return "test"


def running_origin(module_file: Path) -> str:
    """Bequemlichkeit: `classify_origin(checkout_root(module_file))`."""
    return classify_origin(checkout_root(module_file))
