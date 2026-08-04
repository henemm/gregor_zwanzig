"""TDD RED — Issue #1474c (letzter Restpunkt zu Epic #1419), AC-2.

SPEC: docs/specs/modules/feat_1474c_blitzpotenzial_stufen.md

DRY-Pflicht (#1481): Blitzdichte UND Blitzpotenzial muessen ihre
Drei-Schwellen-Uebersetzung ueber DIESELBE geteilte Funktion
`(wert, low_min, med_min, high_min) -> ThunderLevel` laufen lassen -- keine
zweite, kopierte if/elif-Kette in `thunder_level_from_signals()`.

RED-Ursache (heute): `thunder_level_from_signals()` enthaelt die
Blitzdichte-Uebersetzung noch INLINE (kein Aufruf einer benannten Funktion)
und kennt `lightning_potential_jkg` nicht -- der AST-Test findet keine
Funktion, die zweimal aufgerufen wird, und der Verhaltens-Beleg wirft
TypeError/AttributeError.

Testart: struktureller AST-Test (nicht Textsuche) + ein Verhaltens-Beleg.
Kein Netz, keine Mocks.
"""
from __future__ import annotations

import ast
from pathlib import Path

# Pfadregel #1409: relativ zur eigenen Testdatei aufloesen, NIE ueber einen
# festen Hauptrepo-Pfad -- sonst prueft dieser Test aus einem Worktree die
# unveraenderte Hauptrepo-Kopie und meldet falsches Gruen.
_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "output" / "metric_format.py"
)


def _modul_ast() -> ast.Module:
    quelltext = _MODULE_PATH.read_text()
    return ast.parse(quelltext, filename=str(_MODULE_PATH))


def _top_level_funktionen(baum: ast.Module) -> dict:
    return {
        node.name: node
        for node in baum.body
        if isinstance(node, ast.FunctionDef)
    }


def _aufruf_zaehler(funktion_node: ast.FunctionDef, bekannte_namen: set) -> dict:
    """Zaehlt je bekanntem Modul-Funktionsnamen, wie oft er INNERHALB von
    `funktion_node` per einfachem Namen (kein Attribut-Zugriff) aufgerufen
    wird."""
    zaehler: dict = {}
    for node in ast.walk(funktion_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name in bekannte_namen:
                zaehler[name] = zaehler.get(name, 0) + 1
    return zaehler


# ─────────────── AC-2 — genau EINE geteilte Leiter-Funktion ───────────────

def test_ac2_ast_eine_geteilte_leiter_funktion_zwei_aufrufstellen():
    """AC-2: `thunder_level_from_signals()` ruft die Schwellen-Uebersetzung
    fuer Blitzdichte UND Blitzpotenzial ueber DIESELBE benannte Funktion auf
    -- per AST gezaehlt, nicht per Textsuche. Erwartet genau EINE Funktion
    im Modul, die von dort aus GENAU zweimal aufgerufen wird, mit einer
    Vier-Parameter-Signatur (Wert, low_min, med_min, high_min).

    Gegenprobe (Spec): fuegt die Implementierung eine zweite, kopierte
    if/elif-Leiter fuer das Blitzpotenzial direkt in
    `thunder_level_from_signals()` ein statt die geteilte Funktion zu
    nutzen, bleibt die per AST gezaehlte Aufrufzahl der geteilten Funktion
    bei 1 (nur Blitzdichte) -- der `kandidaten`-Check unten faengt das, weil
    dann keine Funktion mit Aufrufzahl 2 existiert.
    """
    baum = _modul_ast()
    top_level = _top_level_funktionen(baum)
    assert "thunder_level_from_signals" in top_level, (
        "thunder_level_from_signals() nicht (mehr) als Top-Level-Funktion "
        f"in {_MODULE_PATH} gefunden"
    )
    fusion_node = top_level["thunder_level_from_signals"]
    bekannte_namen = set(top_level) - {"thunder_level_from_signals"}
    zaehler = _aufruf_zaehler(fusion_node, bekannte_namen)

    kandidaten = {name: n for name, n in zaehler.items() if n == 2}
    assert kandidaten, (
        "Keine Funktion wird aus thunder_level_from_signals() GENAU "
        f"zweimal aufgerufen (gezaehlte Aufrufe: {zaehler}) -- die "
        "geteilte Leiter-Funktion fuer Blitzdichte UND Blitzpotenzial "
        "fehlt, oder es existieren zwei unabhaengige Kopien statt einer "
        "gemeinsamen Funktion"
    )
    assert len(kandidaten) == 1, (
        f"Mehr als eine Funktion wird zweimal aufgerufen: {kandidaten} -- "
        "die geteilte Leiter-Funktion ist nicht eindeutig bestimmbar"
    )
    geteilte_funktion_name = next(iter(kandidaten))
    geteilte_funktion_node = top_level[geteilte_funktion_name]
    parameter = [a.arg for a in geteilte_funktion_node.args.args]
    assert len(parameter) == 4, (
        f"Die geteilte Funktion '{geteilte_funktion_name}' hat "
        f"{len(parameter)} Parameter statt 4 (Wert, low_min, med_min, "
        f"high_min) -- Signatur passt nicht zur in der Spec vorgeschlagenen "
        "Leiter-Funktion"
    )


# ─────── Verhaltens-Beleg: gleicher Vergleichsoperator (>=) fuer beide ─────

def test_ac2_beide_signale_liefern_an_der_unteren_schwelle_uebereinstimmend_low():
    """AC-2 Verhaltens-Beleg: Blitzdichte UND Blitzpotenzial liefern an
    ihrer jeweils UNTEREN Schwelle (Wert exakt gleich `low_min`)
    uebereinstimmend LOW -- Beweis, dass beide ueber denselben
    Vergleichsoperator (`>=`) laufen, nicht nur ueber zwei gleich benannte,
    aber unabhaengig implementierte Ketten."""
    from output import metric_format as mf

    blitzdichte_low = mf.thunder_level_from_signals(
        wettercode_level=None, lightning_density=mf._LIGHTNING_LOW_MIN,
        cape_jkg=None,
    )
    blitzpotenzial_low = mf.thunder_level_from_signals(
        wettercode_level=None, lightning_density=None, cape_jkg=None,
        lightning_potential_jkg=mf._LIGHTNING_POTENTIAL_LOW_MIN,
    )

    assert blitzdichte_low == mf.ThunderLevel.LOW, (
        "Blitzdichte an ihrer unteren Schwelle muss LOW liefern "
        f"(Regressions-Bestandsverhalten), erhalten {blitzdichte_low!r}"
    )
    assert blitzpotenzial_low == blitzdichte_low, (
        f"Blitzpotenzial an SEINER unteren Schwelle "
        f"({mf._LIGHTNING_POTENTIAL_LOW_MIN} J/kg) liefert "
        f"{blitzpotenzial_low!r} statt {blitzdichte_low!r} -- beide Signale "
        "muessen an der jeweils unteren Schwelle uebereinstimmend LOW "
        "liefern, wenn sie ueber denselben Vergleichsoperator (>=) laufen"
    )
