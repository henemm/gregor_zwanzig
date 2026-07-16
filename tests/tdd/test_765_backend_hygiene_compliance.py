# doc-compliance-test
"""
Backend-Test-Hygiene-Compliance-Gate (Issue #765).

Dieser Test prüft die TEST-ARTEFAKTE selbst — nicht Produkt-Verhalten. Er ist
nach der dokumentierten CLAUDE.md-Ausnahme als `# doc-compliance-test` markiert
und verhindert Regress des Backend-Datei-Inhalt-Anti-Patterns: Backend-Tests,
die echten Produkt-Quelltext (`.py`/`.go` unter `src/`/`api/`/`internal/`/`cmd/`)
via `read_text()` oder grep/rg-Subprozess lesen und auf Code-Strings asserten
statt auf tatsächliches Verhalten.

RED (vor Sweep): die 14 #765-Offender lesen Produkt-`.py`/`.go`-Quelltext.
GREEN (nach Sweep): kein Produkt-Quelltext-Read mehr (Source-Asserts entfernt,
auf echtes Verhalten umgestellt, oder Datei gelöscht).

CLAUDE.md: "Dateiinhalt-Checks sind VERBOTEN" + Ausnahme für Workflow-/Test-
Artefakt-Compliance-Tests (`# doc-compliance-test`).

Bypass-Schutz (AC-4): Die Markierung `# doc-compliance-test` rechtfertigt nur
Reads von Doku/Tooling/Workflow-/Runtime-Daten — NIEMALS von Produkt-`.py`/`.go`.
Auch ein als Compliance markierter Test wird geflaggt, wenn er Produkt-Quelltext
liest. Deshalb nimmt das Gate NUR sich selbst und das #754-Vorbild aus.

Erkennung via echter Pfad-Auflösung (nicht naiver Datei-Namen-Substring):
String-Literale, relative Pfade und `pathlib`-Joins werden gegen die Repo-Root
aufgelöst und gegen `.exists()` + Produkt-Root + `.py`/`.go`-Endung geprüft.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TESTS = _REPO / "tests"

# Produkt-Quelltext-Wurzeln (relativ zur Repo-Root). Nur Reads von Dateien
# UNTER diesen Pfaden mit Endung .py/.go gelten als Verstoß.
_PRODUCT_ROOTS = ("src", "api", "internal", "cmd")
_PRODUCT_SUFFIXES = (".py", ".go")

# Diese Dateien sind selbst Compliance-Gates (lesen Test-Artefakte / Pfade als
# Daten, nicht Produkt-Quelltext) und werden vom Scan ausgenommen.
_SELF_EXEMPT = {
    "test_765_backend_hygiene_compliance.py",
    "test_754_755_test_hygiene_compliance.py",
    # #1208 AC-3 (PO-Freigabe 2026-07-11): Struktur-Gate liest Produkt-Quelltext
    # als DATEN fuer eine AST-Strukturregel (kein Verhaltensnachweis) — gleiche
    # Werkzeug-Klasse wie die beiden Gates oben. Spec:
    # docs/specs/modules/report_config_resolver.md
    "test_report_config_scheduler_structure.py",
    # #1207 AC-2: AST-Strukturregel auf dispatch_orchestrator.py (Produkt-Quelltext
    # als DATEN, kein Verhaltensnachweis; # doc-compliance-test) — gleiche
    # Werkzeug-Klasse wie test_report_config_scheduler_structure.py.
    # Spec: docs/specs/modules/dispatch_orchestrator.md
    "test_dispatch_orchestrator.py",
}


def _iter_test_files() -> list[Path]:
    return sorted(
        p
        for p in _TESTS.rglob("*.py")
        if p.is_file() and p.name not in _SELF_EXEMPT
    )


def _resolve_product_path(raw: str) -> Path | None:
    """Löst einen rohen Pfad-String gegen die Repo-Root auf.

    Erkennt absolute, repo-relative und `../..`-relative Pfade. Gibt den
    aufgelösten Pfad zurück, wenn er ein existierender Produkt-`.py`/`.go`
    unter einer Produkt-Wurzel ist — sonst None.
    """
    raw = raw.strip().strip("/")
    if not raw:
        return None
    if not raw.endswith(_PRODUCT_SUFFIXES):
        return None
    # Normalisiere `./` und `../` weg — wir prüfen ohnehin gegen Root.
    parts = [
        seg
        for seg in raw.replace("\\", "/").split("/")
        if seg not in ("", ".", "..")
    ]
    if not parts:
        return None
    # Pfad muss unter einer Produkt-Wurzel beginnen ODER eine Produkt-Wurzel
    # als Teilsegment enthalten (z.B. aus parents[2] / "src" / ...).
    if parts[0] not in _PRODUCT_ROOTS:
        idx = next(
            (i for i, seg in enumerate(parts) if seg in _PRODUCT_ROOTS), None
        )
        if idx is None:
            return None
        parts = parts[idx:]
    candidate = _REPO.joinpath(*parts)
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


# --- AST-basierte Sammlung von Pfad-Strings je Modul -----------------------

def _collect_string_constants(tree: ast.AST) -> list[str]:
    """Alle String-Konstanten im Modul (für Join-Rekonstruktion)."""
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
    return out


def _flatten_path_expr(node: ast.AST) -> list[str] | None:
    """Löst einen `a / "b" / "c"`-BinOp- oder `Path("src/...")`-Ausdruck auf.

    Gibt die String-Segment-Liste zurück (Variablen-/Attribut-Wurzeln werden
    ignoriert, nur String-Segmente zählen) oder None, wenn keine Segmente.
    """
    segments: list[str] = []

    def walk(n: ast.AST) -> None:
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
            walk(n.left)
            walk(n.right)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            for piece in n.value.replace("\\", "/").split("/"):
                if piece:
                    segments.append(piece)
        elif isinstance(n, ast.Call):
            # z.B. Path("src/...") — String-Argumente einsammeln.
            for arg in getattr(n, "args", []):
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    for piece in arg.value.replace("\\", "/").split("/"):
                        if piece:
                            segments.append(piece)
        # Name-/Attribute-Wurzeln (REPO, Path(__file__).parents[2]...) ignoriert.

    walk(node)
    return segments or None


def _module_path_assignments(tree: ast.AST) -> dict:
    """Map: Variablenname -> aufgelöster Pfad-Segment-String.

    Erfasst `FOO = REPO / "src" / "..."`-Zuweisungen, damit ein späterer
    `FOO.read_text()` auf den Pfad zurückgeführt werden kann.
    """
    assignments: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            segs = _flatten_path_expr(node.value)
            if segs:
                joined = "/".join(segs)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments[target.id] = joined
    return assignments


def _collect_listed_product_paths(tree: ast.AST) -> set[str]:
    """Produkt-Pfade aus List-/Tuple-Literalen (z.B. `FILES = [REPO/"src/...", ...]`).

    Deckt das `for f in FILES: f.read_text()`-Muster ab, bei dem das
    read_text-Ziel eine Schleifenvariable ist und nicht direkt auflösbar.
    """
    listed: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)):
            for elt in node.elts:
                segs = _flatten_path_expr(elt)
                if segs:
                    resolved = _resolve_product_path("/".join(segs))
                    if resolved:
                        listed.add(str(resolved.relative_to(_REPO)))
    return listed


def _read_text_targets(tree: ast.AST, assignments: dict) -> tuple[set[str], bool]:
    """Produkt-Pfade aus `<expr>.read_text(...)` + Flag für nicht-auflösbare Ziele.

    Rückgabe: (aufgelöste Produkt-Pfade, hat_unaufgelöstes_read_text_ziel).
    Letzteres signalisiert ein `for f in FILES: f.read_text()`-Muster, dessen
    Pfade aus den List-Literalen rekonstruiert werden müssen.
    """
    hits: set[str] = set()
    unresolved = False
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "read_text"
        ):
            continue
        target = node.func.value
        # 1) target ist eine Modul-Variable mit aufgelöstem Pfad.
        if isinstance(target, ast.Name) and target.id in assignments:
            resolved = _resolve_product_path(assignments[target.id])
            if resolved:
                hits.add(str(resolved.relative_to(_REPO)))
                continue
        # 2) target ist ein inline Path-Join / Path("...")-Ausdruck.
        segs = _flatten_path_expr(target)
        if segs:
            resolved = _resolve_product_path("/".join(segs))
            if resolved:
                hits.add(str(resolved.relative_to(_REPO)))
                continue
        # 3) target ist eine Schleifenvariable / nicht direkt auflösbar.
        unresolved = True
    return hits, unresolved


def _find_product_reads(path: Path) -> list[str]:
    """Findet alle Produkt-`.py`/`.go`-Quelltext-Reads in einer Test-Datei.

    Deckt ab:
      1) `<expr>.read_text(...)` — Ziel-Expr wird zu Pfad aufgelöst
         (Path-Join, String-Literal, oder Modul-Variable).
      2) grep/rg `--include=*.py|*.go` / `--glob=*.py|*.go` Subprozesse, die
         einen Produkt-Pfad-String als Argument tragen.

    Gibt die Liste der gelesenen Produkt-Pfade (relativ zur Repo-Root) zurück.
    """
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    assignments = _module_path_assignments(tree)
    hits, has_unresolved_read = _read_text_targets(tree, assignments)

    # `for f in FILES: f.read_text()` — Pfade aus List-/Tuple-Literalen, wenn
    # mind. ein read_text-Ziel eine nicht-auflösbare Schleifenvariable war.
    if has_unresolved_read:
        hits |= _collect_listed_product_paths(tree)

    # grep/rg-Subprozesse auf Produkt-Quelltext: nur, wenn der Scan einen
    # Produkt-`.py`/`.go`-Glob auf eine konkrete Produkt-Datei richtet.
    has_source_glob = bool(
        re.search(
            r"""--include=['"*]?\*\.(py|go)\b|--glob=['"*]?\*\.(py|go)\b""",
            src,
        )
    )
    if has_source_glob:
        for literal in _collect_string_constants(tree):
            resolved = _resolve_product_path(literal)
            if resolved:
                hits.add(str(resolved.relative_to(_REPO)))

    return sorted(hits)


# Vorab-Scan, damit die Parametrisierung jede Test-Datei einzeln prüft.
_ALL_TEST_FILES = [str(p.relative_to(_REPO)) for p in _iter_test_files()]


@pytest.mark.parametrize("rel_path", _ALL_TEST_FILES)
def test_765_no_product_source_read(rel_path: str) -> None:
    """Jede Test-Datei: kein read_text()/grep auf Produkt-`.py`/`.go`-Quelltext."""
    path = _REPO / rel_path
    if not path.exists():
        return  # Datei gelöscht → konform.
    reads = _find_product_reads(path)
    assert not reads, (
        f"{rel_path} liest Produkt-Quelltext {reads!r} via read_text()/grep "
        f"und assertet auf Code-Strings statt Verhalten "
        f"(CLAUDE.md: Dateiinhalt-Checks sind VERBOTEN). Source-Asserts "
        f"entfernen (behaviorale behalten), auf echten Verhaltenstest "
        f"umstellen, oder Datei löschen (wenn anderswo gedeckt)."
    )
