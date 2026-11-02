# doc-compliance-test
"""Ratsche: keine neuen hartkodierten Nutzertexte im Python-Core (Issue #2674).

SPEC: docs/specs/modules/i18n_p11_api_meldungen_ratsche_2674.md AC-5, AC-6.

Der Scan liest Produkt-Quelltext als DATEN fuer eine AST-Strukturregel (kein
Verhaltensnachweis auf Code-Strings), gleiche Werkzeug-Klasse wie die Ratschen
fuer Frontend (S4) und Go (G5). Der Selbsttest der Ratsche laeuft mit echten
Dateien in ``tmp_path``.

Funde: String-Konstanten (auch Teile von f-Strings) mit Umlaut/ß oder einem
Signalwort. Ausgenommen: Docstrings, Argumente von ``t(...)``/``tn(...)`` und
Literale in Zeilen mit dem Kommentar ``# i18n-log``.

Startstand/Messen: ``python tests/test_i18n_keine_hartkodierten_nutzertexte_python.py
--startstand`` schreibt die Allowlist; ``--messen`` gibt nur auf stdout aus.
"""
from __future__ import annotations

import ast
import io
import json
import re
import sys
import tokenize
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ALLOWLIST = REPO / "tests" / "fixtures" / "i18n_python_allowlist.json"
_SERVICE_WOERTER = ("report", "alert", "notification", "command", "inbound",
                    "preview", "comparison")
#: Dateien mit Nutzertexten ausserhalb der Namensmuster (Spec Annahme 2).
EXTRA_DATEIEN = ("src/services/weather_metrics.py", "src/services/trip_selection.py")
_SIGNAL_RE = re.compile(r"[äöüÄÖÜß]|\b(nicht|bitte|keine|fehlgeschlagen|hinweis)\b",
                        re.IGNORECASE)
#: Katalogschluessel (``bereich.gruppe.element``) sind keine Nutzertexte.
_SCHLUESSEL_RE = re.compile(r"[a-z0-9_]+(\.[a-z0-9_]+){1,3}")
_MARKER = "# i18n-log"
_HINWEIS = ("Text in den Katalog `src/i18n/messages/{de,en}/<bereich>.json`, "
            "oder Log-Zeile mit `# i18n-log` markieren")
_MIN_DATEIEN = 100


def _scan_dateien(root: Path = REPO) -> list[Path]:
    """Scanflaeche + EXTRA_DATEIEN, sortiert."""
    dateien = set((root / "src" / "output").rglob("*.py"))
    dateien |= set((root / "api" / "routers").rglob("*.py"))
    dateien |= {p for p in (root / "src" / "services").glob("*.py")
                if any(w in p.name for w in _SERVICE_WOERTER)}
    dateien |= {root / rel for rel in EXTRA_DATEIEN if (root / rel).is_file()}
    return sorted(p for p in dateien if "__pycache__" not in p.parts)


def _docstring_ids(baum: ast.AST) -> set[int]:
    ids: set[int] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef)) and knoten.body:
            erstes = knoten.body[0]
            if isinstance(erstes, ast.Expr) and isinstance(erstes.value, ast.Constant):
                ids.add(id(erstes.value))
    return ids


def _katalog_argument_ids(baum: ast.AST) -> set[int]:
    ids: set[int] = set()
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        name = getattr(knoten.func, "id", None) or getattr(knoten.func, "attr", None)
        if name in ("t", "tn"):
            for arg in [*knoten.args, *(k.value for k in knoten.keywords)]:
                ids |= {id(n) for n in ast.walk(arg)}
    return ids


def _marker_zeilen(quelltext: str) -> set[int]:
    zeilen: set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(quelltext).readline):
        if tok.type == tokenize.COMMENT and tok.string.startswith(_MARKER):
            zeilen.add(tok.start[0])
    return zeilen


def _finde_nutzertexte(pfad: Path) -> list[tuple[int, str]]:
    """(Zeile, Textauszug <= 60 Zeichen) je Fund."""
    quelltext = pfad.read_text(encoding="utf-8")
    baum = ast.parse(quelltext)
    ausgenommen = _docstring_ids(baum) | _katalog_argument_ids(baum)
    marker = _marker_zeilen(quelltext)
    funde: list[tuple[int, str]] = []
    for knoten in ast.walk(baum):
        if not (isinstance(knoten, ast.Constant) and isinstance(knoten.value, str)):
            continue
        if id(knoten) in ausgenommen or not _SIGNAL_RE.search(knoten.value):
            continue
        if _SCHLUESSEL_RE.fullmatch(knoten.value):
            continue
        if marker & set(range(knoten.lineno, (knoten.end_lineno or knoten.lineno) + 1)):
            continue
        funde.append((knoten.lineno, knoten.value.strip()[:60]))
    return sorted(funde)


def _allowlist() -> list[str]:
    """JSON-Liste von Repo-Pfaden (fehlt die Datei: leer)."""
    if not ALLOWLIST.exists():
        return []
    return json.loads(ALLOWLIST.read_text(encoding="utf-8"))


def _alle_funde(root: Path = REPO) -> dict[str, list[tuple[int, str]]]:
    out: dict[str, list[tuple[int, str]]] = {}
    for pfad in _scan_dateien(root):
        funde = _finde_nutzertexte(pfad)
        if funde:
            out[str(pfad.relative_to(root))] = funde
    return out


def _verstoesse(funde: dict[str, list[tuple[int, str]]], erlaubt: list[str]) -> list[str]:
    return [f'{datei}:{zeile}: "{text}"'
            for datei, liste in sorted(funde.items()) if datei not in erlaubt
            for zeile, text in liste]


def _tote_eintraege(funde: dict[str, list[tuple[int, str]]], erlaubt: list[str]) -> list[str]:
    return [e for e in erlaubt if e not in funde]


def test_keine_neuen_hartkodierten_nutzertexte():
    assert len(_scan_dateien()) >= _MIN_DATEIEN, "Messaufbau leer"
    verstoesse = _verstoesse(_alle_funde(), _allowlist())
    assert not verstoesse, "\n".join([*verstoesse, _HINWEIS])


def test_allowlist_hat_keine_toten_eintraege():
    erlaubt = _allowlist()
    assert erlaubt == sorted(set(erlaubt)), "Allowlist sortiert und ohne Dubletten"
    tote = _tote_eintraege(_alle_funde(), erlaubt)
    assert not tote, f"Allowlist-Eintraege ohne Fund (streichen, sie schrumpft nur): {tote}"


@pytest.mark.xfail(strict=True, reason=(
    "AC-6 Endstand noch nicht erreicht: Restbefunde der Pakete P2-P10 (u. a. "
    "telegram.py-Befehlsmenue, fallback_notice.py, tokens/builder.py, "
    "trip_command_processor.py-Aktionsknoepfe) und unmarkierte Log-Zeilen; "
    "Rueckmeldung im Epic #2644. strict: sobald die Allowlist leer ist, wird "
    "dieser Test rot und die Markierung muss weg."))
def test_allowlist_ist_leer():
    """Endstand Teil 2 (AC-6): alle Pakete P2-P10 haben migriert."""
    assert _allowlist() == []


def _baue_mini_repo(root: Path, inhalt: str) -> Path:
    for ordner in ("src/output", "api/routers", "src/services"):
        (root / ordner).mkdir(parents=True, exist_ok=True)
    datei = root / "src" / "output" / "renderer.py"
    datei.write_text(inhalt, encoding="utf-8")
    (root / "src" / "output" / "sauber.py").write_text('X = "ok"\n', encoding="utf-8")
    return datei


def test_ratsche_erkennt_bekannte_faelle(tmp_path):
    datei = _baue_mini_repo(tmp_path, (
        '"""Modul-Docstring mit Umlaut: Größe."""\n'
        'from i18n import t\n'
        'def f(x):\n'
        '    """Funktions-Docstring: nicht melden."""\n'
        '    a = t("api.fehler.x", "de", grund="für")\n'
        '    log.info("Lauf fehlgeschlagen")  # i18n-log\n'
        '    b = f"Größe {x}"\n'
        '    c = _m("vergleich.pause.hinweis")\n'
        '    return "Bitte warten"\n'
    ))
    funde = _finde_nutzertexte(datei)
    assert [z for z, _ in funde] == [7, 9], funde
    alle = _alle_funde(tmp_path)
    assert list(alle) == ["src/output/renderer.py"]
    assert _verstoesse(alle, []) == ['src/output/renderer.py:7: "Größe"',
                                     'src/output/renderer.py:9: "Bitte warten"']
    assert _verstoesse(alle, ["src/output/renderer.py"]) == []
    assert _tote_eintraege(alle, ["src/output/renderer.py", "src/output/sauber.py"]) \
        == ["src/output/sauber.py"]


def _main(argv: list[str]) -> None:
    funde = _alle_funde()
    pfade = sorted(funde)
    text = json.dumps(pfade, indent=2, ensure_ascii=False) + "\n"
    if "--startstand" in argv:
        ALLOWLIST.write_text(text, encoding="utf-8")
    for datei in pfade:
        for zeile, auszug in funde[datei]:
            print(f'{datei}:{zeile}: "{auszug}"')
    print(f"{len(_scan_dateien())} Dateien gescannt, {len(pfade)} mit Fund, "
          f"{sum(len(v) for v in funde.values())} Funde")


if __name__ == "__main__":
    _main(sys.argv[1:])
