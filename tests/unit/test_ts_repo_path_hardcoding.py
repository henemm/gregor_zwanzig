"""Wächter (#2243 AC-6): kein TypeScript unter `frontend/e2e/` verdrahtet den
Hauptrepo-Pfad im Code.

TS-Pendant zu `tests/tdd/test_repo_path_hardcoding_ratchet.py` (#1409). Wer im
E2E-Code `/home/hem/gregor_zwanzig/...` fest einträgt, prüft aus einem Worktree
die unveränderte Hauptrepo-Kopie (falsches Grün) und auf dem CI-Runner gar
nichts (ENOENT).

Regel: Jeder Treffer des Hauptrepo-Präfixes im CODE einer `frontend/e2e/**/*.ts`
ist ein Fund. Zeilen-, Block- und JSDoc-Kommentare zählen nicht. Ausnahme:
`// gz-main-path: <Grund>` auf der Fundzeile oder der Zeile davor; der Grund
braucht mindestens `_MIN_BEGRUENDUNG` sinnvolle Zeichen (Credential-Orte wie
`staging_admin.env` oder die Staging-`.env`).

Regel-Budget: Prüfdatum `EXPIRY` (+90 Tage), danach Weiterführung oder Streichung.

Spec: docs/specs/modules/rework_2243_playwright_loeschscheibe.md
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_ROOT = REPO_ROOT / "frontend" / "e2e"

EXPIRY = date(2027, 2, 10)  # 2027-02-10

# Verzeichnis-Präfix, kein Dateipfad (für den Python-Wächter nie ein Fund).
_MAIN = "/home/hem/gregor_zwanzig"
_MARKER = re.compile(r"//\s*gz-main-path:\s*(.*)$")
_MIN_BEGRUENDUNG = 10


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    text: str


def _strip_comments(src: str) -> str:
    """Kommentare durch Leerzeichen ersetzen (Zeilenumbrüche bleiben), Strings
    und Template-Literale bleiben unangetastet."""
    out = []
    i, n = 0, len(src)
    state = None  # None | "'" | '"' | '`' | "line" | "block"
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if state is None:
            if c == "/" and nxt == "/":
                state = "line"
                out.append("  ")
                i += 2
                continue
            if c == "/" and nxt == "*":
                state = "block"
                out.append("  ")
                i += 2
                continue
            if c in "'\"`":
                state = c
            out.append(c)
        elif state == "line":
            if c == "\n":
                state = None
                out.append(c)
            else:
                out.append(" ")
        elif state == "block":
            if c == "*" and nxt == "/":
                state = None
                out.append("  ")
                i += 2
                continue
            out.append("\n" if c == "\n" else " ")
        else:  # in String
            if c == "\\":
                out.append(src[i:i + 2])
                i += 2
                continue
            if c == state:
                state = None
            elif c == "\n" and state != "`":
                state = None  # unterminierter String: nicht weiterschleppen
            out.append(c)
        i += 1
    return "".join(out)


def _marker_gueltig(zeile: str) -> bool:
    m = _MARKER.search(zeile)
    if not m:
        return False
    grund = re.sub(r"[^\wäöüÄÖÜß]", "", m.group(1))
    return len(grund) >= _MIN_BEGRUENDUNG


def scan_ts_for_hardcoded_repo_paths(root: Path) -> list[Finding]:
    funde: list[Finding] = []
    for f in sorted(root.rglob("*.ts")):
        if "node_modules" in f.parts:
            continue
        roh = f.read_text("utf-8").splitlines()
        code = _strip_comments(f.read_text("utf-8")).splitlines()
        for idx, zeile in enumerate(code):
            if _MAIN not in zeile:
                continue
            davor = roh[idx - 1] if idx > 0 else ""
            if _marker_gueltig(roh[idx]) or _marker_gueltig(davor):
                continue
            funde.append(Finding(f, idx + 1, roh[idx].strip()))
    return funde


# ── Synthetische Fälle (echte Dateien in tmp_path, keine Mocks) ──────────────

def _ts(tmp_path: Path, inhalt: str) -> Path:
    d = tmp_path / "e2e"
    d.mkdir(exist_ok=True)
    (d / "probe.spec.ts").write_text(inhalt, "utf-8")
    return d


def test_code_fund_schlaegt_an(tmp_path):
    d = _ts(tmp_path, "import { readFileSync } from 'fs';\n"
                      f"const c = readFileSync('{_MAIN}/frontend/gibt-es-nicht.svelte', 'utf-8');\n")
    funde = scan_ts_for_hardcoded_repo_paths(d)
    assert [x.line for x in funde] == [2]


def test_template_literal_fund_schlaegt_an(tmp_path):
    d = _ts(tmp_path, "const f = 'x';\nconst c = await readFile(`" + _MAIN + "/${f}`, 'utf-8');\n")
    assert [x.line for x in scan_ts_for_hardcoded_repo_paths(d)] == [2]


def test_zeilenkommentar_zaehlt_nicht(tmp_path):
    d = _ts(tmp_path, f"// liegt unter {_MAIN}/frontend\nconst a = 1; // {_MAIN}\n")
    assert scan_ts_for_hardcoded_repo_paths(d) == []


def test_block_und_jsdoc_kommentar_zaehlen_nicht(tmp_path):
    d = _ts(tmp_path, f"/**\n * Pfad {_MAIN}/x\n */\n/* {_MAIN} */ const a = 1;\n")
    assert scan_ts_for_hardcoded_repo_paths(d) == []


def test_url_im_string_ist_kein_kommentar(tmp_path):
    d = _ts(tmp_path, f"const u = 'https://x.y'; const p = '{_MAIN}/a.env';\n")
    assert [x.line for x in scan_ts_for_hardcoded_repo_paths(d)] == [1]


def test_marker_auf_fundzeile_oder_davor_erlaubt(tmp_path):
    d = _ts(tmp_path,
            f"// gz-main-path: Credential-Ort staging_admin.env liegt nur im Hauptrepo\n"
            f"const a = '{_MAIN}/.claude/staging_admin.env';\n"
            f"const b = '{_MAIN}_staging/.env'; // gz-main-path: Staging-Umgebung liegt außerhalb des Repos\n")
    assert scan_ts_for_hardcoded_repo_paths(d) == []


def test_marker_ohne_sinnvollen_grund_zaehlt_nicht(tmp_path):
    d = _ts(tmp_path, f"const a = '{_MAIN}/x.env'; // gz-main-path: ok\n")
    assert [x.line for x in scan_ts_for_hardcoded_repo_paths(d)] == [1]


def test_marker_zwei_zeilen_davor_zaehlt_nicht(tmp_path):
    d = _ts(tmp_path, "// gz-main-path: Credential-Ort staging_admin.env im Hauptrepo\n\n"
                      f"const a = '{_MAIN}/x.env';\n")
    assert [x.line for x in scan_ts_for_hardcoded_repo_paths(d)] == [3]


# ── Echter Bestand ────────────────────────────────────────────────────────────

def test_echter_bestand_ohne_fund():
    funde = scan_ts_for_hardcoded_repo_paths(E2E_ROOT)
    assert funde == [], "Fest verdrahteter Hauptrepo-Pfad im E2E-Code:\n" + "\n".join(
        f"  {x.path.relative_to(REPO_ROOT)}:{x.line}: {x.text}" for x in funde
    )


def test_pruefdatum_steht_im_regel_budget():
    assert EXPIRY == date(2027, 2, 10)
