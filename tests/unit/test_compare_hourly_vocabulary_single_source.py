"""RATSCHE — es gibt genau EINE Zuordnung Stundenverlaufs-Schluessel → Groesse.

Issue #1406 Scheibe B, AC-10. Pruefdatum: 2026-10-30 (Regel-Budget, CLAUDE.md).
SPEC: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md

Vor dieser Scheibe wurde dieselbe Zuordnung an VIER Stellen gepflegt
(Frontend-Anzeigeliste, Frontend-Uebersetzung, Backend-Aufloesung,
Renderer-Spaltenliste). Diese Ratsche haelt den Python-Teil des Ergebnisses
fest: im gesamten Server-Baum (``src/``, ``api/``) darf es nur EINE literale
Alias-Tabelle geben, die einen historischen Stundenverlaufs-Kurzschluessel auf
eine Wettergroesse abbildet.

Die Frontend-Haelfte derselben Ratsche liegt in
``frontend/src/lib/components/compare/__tests__/
compare_hourly_vocabulary_single_source.test.ts`` — sie kann nur dort laufen,
wo ein JavaScript-Syntaxbaum verfuegbar ist. Zusammen ergeben beide die
Aussage "genau eine Quelle repo-weit".

Bauart gegen die bekannten Faulheitsfallen:

* **Kein Nichtstun-Gruen.** Die Suchbegriffe stammen aus der kanonischen
  Quelle selbst; findet der Scan sie dort NICHT, faellt der Test durch statt
  durchzulaufen. Alle Zaehlwerte werden ausgesprochen behauptet.
* **Keine handgepflegte Groessen-Liste.** Kurzschluessel und Zielbegriffe
  werden zur Laufzeit aus ``FRONTEND_TO_HOURLY_METRIC_ID`` bzw. dem zentralen
  Register abgeleitet.
* **Syntaxbaum statt Textsuche** (``ast``) — Kommentare und Zeichenketten in
  Dokumentation koennen keinen Treffer erzeugen.
* **Pfadregel #1409:** der Pruefbaum wird relativ zur eigenen Testdatei
  aufgeloest, nie ueber einen festen Hauptrepo-Pfad.
"""
from __future__ import annotations

import ast
from pathlib import Path

from app.metric_catalog import get_all_metrics
from output.renderers.compare_hourly_metric_ids import FRONTEND_TO_HOURLY_METRIC_ID

_REPO = Path(__file__).resolve().parents[2]
SUCHBAEUME = [_REPO / "src", _REPO / "api"]
KANONISCHE_QUELLE = (
    _REPO / "src" / "output" / "renderers" / "compare_hourly_metric_ids.py"
)

# Die historischen Kurzschluessel des Stundenverlaufs — Laufzeit-Ableitung aus
# der Quelle, die sie fuehren DARF. Keine Abschrift.
KURZSCHLUESSEL = frozenset(FRONTEND_TO_HOURLY_METRIC_ID)

# Alles, was als "Wettergroesse" auf der rechten Seite stehen kann: die
# Register-ID oder der Rohwert-Feldname derselben Groesse.
ZIELBEGRIFFE = frozenset(
    {m.id for m in get_all_metrics()} | {m.dp_field for m in get_all_metrics()}
)


def _alias_paare(quelltext: str) -> list[tuple[int, str, str]]:
    """(Zeile, Kurzschluessel, Zielbegriff) je Abbildungs-Paar in einem
    Wortverzeichnis-Literal.

    Identitaets-Paare (``"uv_index": "uv_index"``) zaehlen NICHT: sie tragen
    keine Uebersetzung und kommen auch in Provider-Feldtabellen vor, die mit
    dem Stundenverlauf nichts zu tun haben.
    """
    treffer: list[tuple[int, str, str]] = []
    for knoten in ast.walk(ast.parse(quelltext)):
        if not isinstance(knoten, ast.Dict):
            continue
        for schluessel, wert in zip(knoten.keys, knoten.values):
            if not (isinstance(schluessel, ast.Constant)
                    and isinstance(schluessel.value, str)):
                continue
            if not (isinstance(wert, ast.Constant) and isinstance(wert.value, str)):
                continue
            if (schluessel.value in KURZSCHLUESSEL
                    and wert.value in ZIELBEGRIFFE
                    and schluessel.value != wert.value):
                treffer.append((knoten.lineno, schluessel.value, wert.value))
    return treffer


def _durchsuche_baum() -> tuple[int, dict[Path, list[tuple[int, str, str]]]]:
    geprueft = 0
    fundstellen: dict[Path, list[tuple[int, str, str]]] = {}
    for baum in SUCHBAEUME:
        for pfad in sorted(baum.rglob("*.py")):
            geprueft += 1
            paare = _alias_paare(pfad.read_text(encoding="utf-8"))
            if paare:
                fundstellen[pfad] = paare
    return geprueft, fundstellen


def test_detector_finds_a_planted_second_source():
    """Scharfschaltung: Given ein Quelltext enthaelt eine zweite Alias-Tabelle
    / When der Sucher darueber laeuft / Then findet er sie. Ohne diesen
    Nachweis koennte die Ratsche gruen sein, weil sie gar nichts sucht."""
    ein_schluessel = sorted(KURZSCHLUESSEL)[0]
    ein_ziel = next(
        m.id for m in get_all_metrics()
        if m.id != ein_schluessel and m.dp_field != ein_schluessel
    )
    gestellt = f'ALIAS = {{"{ein_schluessel}": "{ein_ziel}"}}\n'

    paare = _alias_paare(gestellt)

    assert paare == [(1, ein_schluessel, ein_ziel)], (
        f"Der Sucher erkennt eine offensichtliche zweite Alias-Tabelle nicht: "
        f"{paare}"
    )


def test_exactly_one_python_source_maps_hourly_keys_to_weather_metrics():
    """AC-10: Given jemand legt im Server-Baum eine zweite Zuordnung
    Stundenverlaufs-Schluessel → Wettergroesse an / When diese Ratsche laeuft
    / Then schlaegt sie fehl und benennt die zusaetzliche Datei konkret."""
    assert len(KURZSCHLUESSEL) >= 5, (
        f"Nur {len(KURZSCHLUESSEL)} Kurzschluessel abgeleitet — die Suche "
        "haette kaum Angriffsflaeche, der Waechter waere stumpf."
    )
    assert len(ZIELBEGRIFFE) >= 24, (
        f"Nur {len(ZIELBEGRIFFE)} Zielbegriffe aus dem Register abgeleitet."
    )

    geprueft, fundstellen = _durchsuche_baum()

    assert geprueft > 0, (
        f"Kein einziger Python-Quelltext unter {[str(p) for p in SUCHBAEUME]} "
        "geprueft — die Ratsche laeuft ins Leere."
    )
    namen = sorted(str(p.relative_to(_REPO)) for p in fundstellen)
    assert len(fundstellen) == 1, (
        f"{geprueft} Dateien geprueft, {len(fundstellen)} Zuordnungs-Quellen "
        f"gefunden — erwartet genau 1.\nFundstellen: {namen}"
    )
    assert next(iter(fundstellen)) == KANONISCHE_QUELLE, (
        f"Die einzige Zuordnung steht nicht in der kanonischen Quelle "
        f"({KANONISCHE_QUELLE.relative_to(_REPO)}), sondern in: {namen}"
    )


def test_the_single_source_speaks_the_registers_language():
    """AC-10 / Implementation Details 1: Given die eine verbliebene
    Alias-Tabelle / When man ihre rechte Seite liest / Then nennt sie
    Register-IDs (``temperature``), nicht Rohwert-Feldnamen (``t2m_c``) —
    sonst bleibt ein zweites Vokabular als Zwischenschicht bestehen."""
    register_ids = {m.id for m in get_all_metrics()}

    fremd = {
        schluessel: wert
        for schluessel, wert in FRONTEND_TO_HOURLY_METRIC_ID.items()
        if wert not in register_ids
    }

    assert FRONTEND_TO_HOURLY_METRIC_ID, "Alias-Tabelle ist leer — Vakuum."
    assert not fremd, (
        "Die Alias-Tabelle bildet auf Namen ab, die im zentralen Register "
        f"nicht vorkommen: {fremd}"
    )
