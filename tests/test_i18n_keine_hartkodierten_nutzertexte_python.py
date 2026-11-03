# doc-compliance-test
"""Ratsche: keine neuen hartkodierten Nutzertexte im Python-Core (Issue #2674).

SPEC: docs/specs/modules/i18n_p11_api_meldungen_ratsche_2674.md AC-5, AC-6.

Der Scan liest Produkt-Quelltext als DATEN fuer eine AST-Strukturregel (kein
Verhaltensnachweis auf Code-Strings), gleiche Werkzeug-Klasse wie die Ratschen
fuer Frontend (S4) und Go (G5). Der Selbsttest der Ratsche laeuft mit echten
Dateien in ``tmp_path``.

Funde: String-Konstanten (auch Teile von f-Strings) mit Umlaut/ß oder einem
Signalwort. Ausgenommen: Docstrings, Argumente von ``t(...)``/``tn(...)`` und
Literale in Zeilen mit dem Kommentar ``# i18n-log`` (Log-, Assert-, Debug-Ausgabe)
oder ``# i18n-fest: <Grund>`` (begruendet sprachfest: Eigenname, SMS-Kanal,
Bot-Menue nach P7 #2669; Grund >= 10 Zeichen, sonst wirkungslos; #2751).

Allowlist ``tests/fixtures/i18n_python_allowlist.json``: JSON-Objekt
``{"<repo-pfad>": <Baseline-Fundzahl>}``. Je Datei darf die Fundzahl nur
sinken: mehr Funde als die Baseline = rot; weniger Funde, ohne dass die
Baseline mitsinkt (bzw. der Eintrag bei 0 gestrichen wird) = ebenfalls rot,
damit die Zahl nie wieder wachsen kann.

Startstand/Restbefund (Prüfdatum 2027-01-28, Regel-Budget): AC-6 (Allowlist
leer) ist mit P11 NICHT erreicht -- dokumentierte Teilauslieferung. #2751 hat
alles ausserhalb des Renderer-Gates abgebaut; uebrig sind Dateien unter
``src/output/renderers/`` (Renderer-Commit-Gate, brauchen den Validator gegen
echte Staging-Mail) und das Telegram-Befehlsmenue ``BOT_COMMANDS`` (bot-weit,
ohne Nutzerkontext; Sprachwahl braucht eine Spec). ``test_allowlist_ist_leer``
ist bis dahin ``xfail(strict=True)``.

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
#: Begruendet sprachfester Text (Eigenname, SMS-Kanal, Bot-Menue P7 #2669), #2751.
_FEST_RE = re.compile(r"# i18n-fest:\s*(\S.{9,})")
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
        if tok.type != tokenize.COMMENT:
            continue
        if tok.string.startswith(_MARKER) or _FEST_RE.match(tok.string.rstrip()):
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


def _allowlist() -> dict[str, int]:
    """Repo-Pfad -> Baseline-Fundzahl (fehlt die Datei: leer)."""
    if not ALLOWLIST.exists():
        return {}
    return json.loads(ALLOWLIST.read_text(encoding="utf-8"))


def _alle_funde(root: Path = REPO) -> dict[str, list[tuple[int, str]]]:
    out: dict[str, list[tuple[int, str]]] = {}
    for pfad in _scan_dateien(root):
        funde = _finde_nutzertexte(pfad)
        if funde:
            out[str(pfad.relative_to(root))] = funde
    return out


def _verstoesse(funde: dict[str, list[tuple[int, str]]],
                erlaubt: dict[str, int]) -> list[str]:
    """Funde ausserhalb der Allowlist und Wachstum ueber die Baseline."""
    out: list[str] = []
    for datei, liste in sorted(funde.items()):
        baseline = erlaubt.get(datei, 0)
        if len(liste) <= baseline:
            continue
        if baseline:
            out.append(f"{datei}: {len(liste)} Funde > Baseline {baseline}")
        out += [f'{datei}:{zeile}: "{text}"' for zeile, text in liste]
    return out


def _tote_eintraege(funde: dict[str, list[tuple[int, str]]],
                    erlaubt: dict[str, int]) -> list[str]:
    """Eintraege, deren Baseline ueber der Fundzahl liegt (mitsenken/streichen)."""
    return [f"{e}: Baseline {n} > {len(funde.get(e, []))} Funde"
            for e, n in sorted(erlaubt.items()) if n > len(funde.get(e, []))]


def test_keine_neuen_hartkodierten_nutzertexte():
    assert len(_scan_dateien()) >= _MIN_DATEIEN, "Messaufbau leer"
    verstoesse = _verstoesse(_alle_funde(), _allowlist())
    assert not verstoesse, "\n".join([*verstoesse, _HINWEIS])


def test_allowlist_hat_keine_toten_eintraege():
    erlaubt = _allowlist()
    assert list(erlaubt) == sorted(erlaubt), "Allowlist sortiert"
    assert all(isinstance(n, int) and n > 0 for n in erlaubt.values()), erlaubt
    tote = _tote_eintraege(_alle_funde(), erlaubt)
    assert not tote, ("Baseline senken bzw. Eintrag bei 0 streichen (die Allowlist "
                      f"schrumpft nur): {tote}")


@pytest.mark.xfail(strict=True, reason=(
    "AC-6 Endstand noch nicht erreicht: Restbefunde unter src/output/renderers/ "
    "(Renderer-Gate, u. a. fallback_notice.py, trip_report.py, alert/*) und "
    "telegram.py-Befehlsmenue BOT_COMMANDS (#2751); "
    "Rueckmeldung im Epic #2644. strict: sobald die Allowlist leer ist, wird "
    "dieser Test rot und die Markierung muss weg."))
def test_allowlist_ist_leer():
    """Endstand Teil 2 (AC-6): alle Pakete P2-P10 haben migriert."""
    assert _allowlist() == {}


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
    assert _verstoesse(alle, {}) == ['src/output/renderer.py:7: "Größe"',
                                     'src/output/renderer.py:9: "Bitte warten"']
    assert _verstoesse(alle, {"src/output/renderer.py": 2}) == []
    assert _verstoesse(alle, {"src/output/renderer.py": 1}) == [
        "src/output/renderer.py: 2 Funde > Baseline 1",
        'src/output/renderer.py:7: "Größe"', 'src/output/renderer.py:9: "Bitte warten"']
    assert _tote_eintraege(alle, {"src/output/renderer.py": 2, "src/output/sauber.py": 1}) \
        == ["src/output/sauber.py: Baseline 1 > 0 Funde"]
    assert _tote_eintraege(alle, {"src/output/renderer.py": 3}) \
        == ["src/output/renderer.py: Baseline 3 > 2 Funde"]


def test_ratsche_fest_marker_braucht_grund(tmp_path):
    """#2751 AC-4: ``# i18n-fest: <Grund>`` nimmt nur mit Grund (>= 10 Zeichen) aus."""
    datei = _baue_mini_repo(tmp_path, (
        'A = "GeoSphere Österreich"  # i18n-fest: Eigenname des Anbieters\n'
        'B = "Böen"  # i18n-fest\n'
        'C = "Böen"  # i18n-fest: kurz\n'
        'D = "Böen"  # i18n-fest:   \n'
    ))
    assert [z for z, _ in _finde_nutzertexte(datei)] == [2, 3, 4]


def _main(argv: list[str]) -> None:
    funde = _alle_funde()
    pfade = sorted(funde)
    text = json.dumps({p: len(funde[p]) for p in pfade}, indent=2,
                      ensure_ascii=False) + "\n"
    if "--startstand" in argv:
        ALLOWLIST.write_text(text, encoding="utf-8")
    for datei in pfade:
        for zeile, auszug in funde[datei]:
            print(f'{datei}:{zeile}: "{auszug}"')
    print(f"{len(_scan_dateien())} Dateien gescannt, {len(pfade)} mit Fund, "
          f"{sum(len(v) for v in funde.values())} Funde")


if __name__ == "__main__":
    _main(sys.argv[1:])
