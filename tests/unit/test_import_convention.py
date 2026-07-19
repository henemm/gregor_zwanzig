"""
Collection-Guard: bare-Importkonvention in api/ und src/ (Issue #1308).

GIVEN der gesamte Produkt-Code unter api/ und src/
WHEN dieser Guard-Test läuft (Kern, deterministisch, kein Netz)
THEN existiert dort keine einzige `from src.`/`import src.`-Zeile mehr.

Warum: `app.X` und `src.app.X` werden von Python als zwei getrennte
Modulobjekte geladen (Editable-Install legt `src/` auf sys.path,
uvicorn-cwd legt zusätzlich den Repo-Root auf sys.path, wo `src` als
Top-Level-Paket erscheint). Die #1133-Test-Datenisolation
(tests/conftest.py patcht ausschließlich `app.loader._DATA_ROOT`) wirkt
deshalb nur auf den bare-Importpfad — jeder verbleibende `src.`-Import
liest weiterhin unisoliert echte Nutzerdaten, sowohl in Tests als auch
in Prod/Staging-Laufzeit. Dieser Guard erzwingt die bare-Form als
strukturelle Konvention, statt sie durch ein Alias-Netz zu emulieren.

Spec: docs/specs/modules/fix_1308_dual_module_isolation.md (AC-1)
"""
import re
from pathlib import Path

# Erfasst sowohl "from src.foo import bar" als auch "import src.foo" als
# eigene Anweisungszeile (führender Whitespace für eingerückte Importe
# innerhalb von Funktionen/try-Blöcken erlaubt).
_SRC_IMPORT_RE = re.compile(r"^\s*(from|import)\s+src\.", re.MULTILINE)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCAN_DIRS = ("api", "src")


def _find_src_prefixed_import_lines():
    """Durchsucht alle *.py unter api/ und src/ nach `src.`-präfixierten
    Importzeilen. Liefert eine Liste von "relativer/pfad.py:zeilennummer"
    Strings, sortiert nach Pfad und Zeilennummer.
    """
    hits = []
    for scan_dir in _SCAN_DIRS:
        base = _REPO_ROOT / scan_dir
        if not base.is_dir():
            continue
        for py_file in sorted(base.rglob("*.py")):
            text = py_file.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _SRC_IMPORT_RE.match(line):
                    rel_path = py_file.relative_to(_REPO_ROOT)
                    hits.append(f"{rel_path}:{lineno}")
    return hits


def test_no_src_prefixed_imports_in_api_and_src():
    hits = _find_src_prefixed_import_lines()
    assert hits == [], (
        f"{len(hits)} verbotene 'src.'-präfixierte Importzeile(n) gefunden "
        f"(Konvention: bare — s. fix_1308_dual_module_isolation.md ADR-1):\n"
        + "\n".join(hits)
    )
