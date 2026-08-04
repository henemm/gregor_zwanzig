# doc-compliance-test
"""PARITAETS-WAECHTER — die Tour-Mail darf sich durch #1406 Scheibe B nicht
aendern.

SPEC: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md — AC-7.
Vorbild: ``tests/tdd/test_trip_outlook_parity.py`` (Scheibe A).

Scheibe B stellt den Ortsvergleich-Stundenverlauf auf den zentralen Katalog um
und ersetzt dabei die Compare-eigenen ``_fmt_*``-Funktionen durch die BEREITS
GETEILTEN ``format_value()``/``severity_for()`` aus ``output/metric_format.py``.
Genau diese beiden Funktionen benutzt auch die Tour-Mail. Wer sie "passend fuer
Compare" nachjustiert, aendert stillschweigend jede Tour-Mail mit.

Drei Waechter, alle HEUTE BEREITS GRUEN — sie muessen es BLEIBEN:

1. Die geteilte Formel-Schicht liefert Zeichen fuer Zeichen dasselbe wie vor
   der Umstellung (aufgezeichnete Wertetabelle, `tests/fixtures/
   shared_metric_format_parity/`). Referenz ist eine Datei mit dem Stand VOR
   dem Umbau, kein zweiter Aufruf desselben Codes im selben Lauf.
2. Der Vergleichs-Renderer importiert die Tour-ORCHESTRIERUNG nicht
   (``dp_to_row``/``extract_hourly_rows``/``visible_cols`` aus
   ``email/helpers.py``) — geteilt ist die Formel, nicht die Aufrufsignatur
   (Spec Known Limitations). Geprueft am Syntaxbaum, nicht per Textsuche.
3. Die aufgezeichneten Tour-Mail-Goldens (``tests/golden/email/``) bleiben
   unangetastet. AC-7 verlangt ausdruecklich "bleibt gruen, OHNE dass das
   Golden angepasst wird" — wer sie neu einfriert, um einen roten
   Golden-Lauf loszuwerden, faellt hier auf.

Kern-Schicht, deterministisch: kein Netz, keine Mocks/``patch()``.

HYGIENE (#765, Adversary-Befund F001): Waechter 2 liest Produkt-Quelltext als
DATEN fuer eine AST-Strukturregel (welche Namen importiert werden), NICHT als
String-Verhaltensnachweis. Das ist dieselbe Werkzeug-Klasse wie
``test_report_config_scheduler_structure.py`` und ``test_dispatch_orchestrator.py``
— daher wie dort: ``# doc-compliance-test`` in Zeile 1 UND Eintrag in
``test_765_backend_hygiene_compliance.py::_SELF_EXEMPT``. Die Pruefung selbst
bleibt unveraendert scharf.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
from pathlib import Path

from app.metric_catalog import get_all_metrics
from output.metric_format import format_value, severity_for

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen, nie ueber
# einen festen Hauptrepo-Pfad — sonst prueft ein Worktree-Lauf die unveraenderte
# Hauptrepo-Kopie und meldet falsches Gruen.
_TESTS = Path(__file__).resolve().parents[1]
_REPO = Path(__file__).resolve().parents[2]

_GRID_FIXTURE = (
    _TESTS / "fixtures" / "shared_metric_format_parity"
    / "format_value_severity_grid.tsv"
)
_GOLDEN_DIR = _TESTS / "golden" / "email"

# Wertegitter der Aufzeichnung — identisch zum Erzeugungslauf.
GRID = [None, -12.5, 0, 0.4, 7.5, 42, 137.0, 1013.0, 20000]

# sha256 der Tour-Mail-Goldens, aufgezeichnet vor Scheibe B (HEAD 1863e6c1).
# Neu eingefroren 2026-08-04 (Issue #1491, PO-freigegeben): die
# Gewitter-Spalte wurde von einem Text-/Emoji-Sonderfall zu einer regulaeren
# 4-stufigen Ampel-Spalte (Kreis + Zell-Toenung wie Wind/Boeen/Regen). Ein
# Diff gegen den Vorstand (c31f777c) zeigt: NUR die "Thdr"-Spalte weicht ab
# (HTML-Zellen + Klartext-Label "kein"/"leicht"/"mittel"/"hoch" statt
# "–"/"⚡ mögl."/"⚡⚡"), alles andere ist zeichengleich.
GOLDEN_HASHES = {
    "arlberg-winter-morning-html.txt": "f5190879c865d905ef15c87437871bc6d95eb86d95abb47f3b61e7fd6fa9c9c8",
    "arlberg-winter-morning-plain.txt": "46b27784d1fbe579c0c6db7fd3b40fdb173159a941a5a44dfd063137c2793900",
    "corsica-vigilance-html.txt": "65d4fe8145b24d778b42c63ec7cbaddf67ede7d3b0b5b78ef5b9e81b12af7555",
    "corsica-vigilance-plain.txt": "5c5c13ee3186c6ff305eada602dfe01a0d9228710d28761ae8aee09e5a2e4e3a",
    "gr20-spring-morning-html.txt": "63521106b5615deacc9f3f57f3fa1946349f97db0eda77bfc83f4d12c213b3b3",
    "gr20-spring-morning-plain.txt": "59a5597273e07bcbaa97b29fe0608ca838d1b975459247efb123bd8166be3752",
    "gr20-summer-evening-html.txt": "2ee2f16223152ba11113b3128e0d091200fb47af9b772c0604d7b581a292d43e",
    "gr20-summer-evening-plain.txt": "41c513accb3a541a62efd0574cd345a4496da5229ca80853fac1b92ecd5f7c45",
    "gr221-mallorca-evening-html.txt": "fb5cbd8428e96b4af5b3e9ed70246360bd3a200bb70b931b8811bc17a301cc43",
    "gr221-mallorca-evening-plain.txt": "08fb942aa9c164713c415eef5378e3c35a49643249227185dbee2398de006b2f",
}

# Tour-Orchestrierung, die der Vergleich NICHT importieren darf (Spec Known
# Limitations: sie erwartet ein volles UnifiedWeatherDisplayConfig).
TRIP_ORCHESTRATION = {"dp_to_row", "extract_hourly_rows", "visible_cols",
                      "aggregate_night_block"}

COMPARE_RENDERER_FILES = [
    _REPO / "src" / "output" / "renderers" / "email" / "compare_html.py",
    _REPO / "src" / "output" / "renderers" / "comparison.py",
    _REPO / "src" / "output" / "renderers" / "compare_hourly_metric_ids.py",
]


def _current_grid() -> str:
    zeilen = []
    for metric in sorted(get_all_metrics(), key=lambda m: m.id):
        for value in GRID:
            parts = []
            for style in ("plain", "bare"):
                try:
                    parts.append(format_value(metric.id, value, style=style))
                except Exception as exc:  # noqa: BLE001 - Verhalten aufzeichnen
                    parts.append(f"<{type(exc).__name__}>")
            try:
                sev = severity_for(metric.id, value)
            except Exception as exc:  # noqa: BLE001
                sev = f"<{type(exc).__name__}>"
            zeilen.append(f"{metric.id}\t{value!r}\t{parts[0]}\t{parts[1]}\t{sev}")
    return "\n".join(zeilen) + "\n"


def test_shared_metric_format_layer_is_unchanged():
    """AC-7 (1): Given die Tour-Mail formatiert und ampelt ueber
    ``format_value``/``severity_for`` / When Scheibe B dieselben Funktionen
    fuer den Vergleichs-Stundenverlauf einspannt / Then liefern sie
    zeichengleich dasselbe wie vorher — sonst aendert sich jede Tour-Mail mit.
    """
    erwartet = _GRID_FIXTURE.read_text(encoding="utf-8")
    assert erwartet.count("\n") > 0, (
        f"Aufzeichnung {_GRID_FIXTURE} ist leer — der Waechter kann nichts "
        "vergleichen."
    )
    aktuell = _current_grid()

    assert aktuell == erwartet, "Die geteilte Formel-Schicht hat sich geaendert:\n" + "\n".join(
        difflib.unified_diff(
            erwartet.splitlines(), aktuell.splitlines(),
            fromfile="aufgezeichnet (vor Scheibe B)", tofile="jetzt", lineterm="",
        )
    )


def test_compare_renderer_does_not_import_the_trip_orchestration():
    """AC-7 (2): Given die Tour-Orchestrierung erwartet ein Datenmodell, das
    der Vergleich gar nicht hat / When man den Vergleichs-Renderer am
    Syntaxbaum untersucht / Then importiert er keine ihrer Funktionen —
    geteilt ist die Formel, nicht die Aufrufsignatur."""
    geprueft = 0
    treffer: list[str] = []
    for pfad in COMPARE_RENDERER_FILES:
        assert pfad.exists(), f"Pruefling fehlt: {pfad}"
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        geprueft += 1
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.ImportFrom) and knoten.module:
                if not knoten.module.endswith("email.helpers"):
                    continue
                for alias in knoten.names:
                    if alias.name in TRIP_ORCHESTRATION:
                        treffer.append(
                            f"{pfad.relative_to(_REPO)}:{knoten.lineno} "
                            f"importiert {alias.name}"
                        )

    assert geprueft == len(COMPARE_RENDERER_FILES) and geprueft > 0, (
        f"{geprueft} von {len(COMPARE_RENDERER_FILES)} Vergleichs-Renderern "
        "geprueft — Waechter greift ins Leere."
    )
    assert not treffer, (
        "Der Vergleichs-Renderer haengt sich an die Tour-Orchestrierung:\n"
        + "\n".join(treffer)
    )


def test_trip_mail_goldens_are_not_re_recorded():
    """AC-7 (3): Given die aufgezeichneten Tour-Mails sind der Beweis / When
    diese Scheibe geliefert wird / Then ist keine einzige Golden-Datei neu
    eingefroren worden."""
    abweichend = []
    for name, erwartet in sorted(GOLDEN_HASHES.items()):
        pfad = _GOLDEN_DIR / name
        assert pfad.exists(), f"Tour-Golden fehlt: {pfad}"
        ist = hashlib.sha256(pfad.read_bytes()).hexdigest()
        if ist != erwartet:
            abweichend.append(f"{name}: {ist} statt {erwartet}")

    assert len(GOLDEN_HASHES) == 10, "Aufzeichnung unvollstaendig."
    assert not abweichend, (
        "Tour-Mail-Golden wurde neu eingefroren statt gruen zu bleiben "
        "(AC-7):\n" + "\n".join(abweichend)
    )
