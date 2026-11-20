"""#3137 E2E-Haupt-Suite immer seriell — AC-1, AC-2, AC-3, AC-5.

Spec: docs/specs/modules/e2e_seriell_haupt_suite.md

Verhaltensnachweis ist der Playwright-Runner selbst:
- AC-1/AC-3: die Haupt-Config wird so ausgewertet, wie Playwright sie lädt
  (Import im Node-Prozess, mit bzw. ohne `CI`), und das echte Setup-Projekt
  läuft ohne Worker-Override, ohne dass der Wächter anschlägt.
- AC-2: das echte `e2e/global.setup.ts` läuft mit `--workers=2` und muss mit
  einer Meldung zu Grund und Abhilfe abbrechen, BEVOR es eine Verbindung
  aufbaut.

Damit kein Stack nötig ist und nie ein echter Server (Staging 8091, Vorschau
4173) Daten abbekommt, läuft der Runner über eine Hilfs-Config im
Temp-Verzeichnis: sie übernimmt die Haupt-Config unverändert (also auch ihren
`workers`-Wert), lässt nur den Vorschauserver weg und zeigt Base-URL und
API-Ziel auf einen geschlossenen Port.

AC-4 (DS-2 plus Sprach-Umschalter, lokal ohne `CI`) ist ein E2E-Lauf auf dem
isolierten Stack und wird in /50-implement bzw. /60-validate real belegt.
"""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
MAIN_CONFIG = FRONTEND / "playwright.config.ts"
PLAYWRIGHT_BIN = FRONTEND / "node_modules" / ".bin" / "playwright"
GATES_DOC = REPO_ROOT / "docs" / "reference" / "gates_und_ratschen.md"

# Geschlossener Port: jede Verbindung scheitert sofort, nichts wird angelegt.
CLOSED = "http://127.0.0.1:9"

needs_playwright = pytest.mark.skipif(
    not PLAYWRIGHT_BIN.exists(),
    reason="frontend/node_modules fehlt (npm ci) — Runner-Nachweis nur mit Playwright",
)

GUARD_MARKERS = ("Admin-Konto", "Datenwurzel", "--workers=1")


def _env(ci: bool) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "CI"}
    if ci:
        env["CI"] = "1"
    env["GZ_API_BASE"] = CLOSED
    env["GZ_E2E_API_PROXY_TARGET"] = CLOSED
    env["E2E_USER"] = "e2e-3137-nicht-vorhanden"
    env["E2E_PASS"] = "e2e-3137-nicht-vorhanden"
    env["FORCE_COLOR"] = "0"
    return env


def _resolved_workers(ci: bool):
    """Wert von `workers`, so wie die Haupt-Config ihn beim Laden liefert."""
    script = (
        f"const m = await import({json.dumps(MAIN_CONFIG.as_uri())});"
        "process.stdout.write(JSON.stringify(m.default.workers ?? null));"
    )
    out = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings",
         "--input-type=module", "-e", script],
        cwd=FRONTEND, env=_env(ci), capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _helper_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "playwright.3137.config.ts"
    cfg.write_text(
        f"import base from {json.dumps(str(MAIN_CONFIG))};\n"
        "const setup = base.projects.find((p) => p.name === 'setup');\n"
        "export default {\n"
        "  ...base,\n"
        f"  testDir: {json.dumps(str(FRONTEND / 'e2e'))},\n"
        f"  outputDir: {json.dumps(str(tmp_path / 'results'))},\n"
        "  globalTeardown: undefined,\n"
        "  webServer: undefined,\n"
        "  timeout: 20_000,\n"
        f"  use: {{ ...base.use, baseURL: {json.dumps(CLOSED)} }},\n"
        "  projects: [setup],\n"
        "};\n",
        encoding="utf-8",
    )
    return cfg


def _run_setup(tmp_path: Path, *extra: str, ci: bool = False):
    cfg = _helper_config(tmp_path)
    return subprocess.run(
        [str(PLAYWRIGHT_BIN), "test", "--config", str(cfg),
         "--project=setup", "--reporter=line", *extra],
        cwd=FRONTEND, env=_env(ci), capture_output=True, text=True, timeout=180,
    )


def _guard_fired(output: str) -> bool:
    return all(m in output for m in GUARD_MARKERS)


@needs_playwright
def test_ac1_haupt_config_ohne_ci_genau_ein_worker():
    """GIVEN kein CI / WHEN Playwright die Haupt-Config lädt / THEN workers == 1."""
    assert _resolved_workers(ci=False) == 1


@needs_playwright
def test_ac1_setup_ohne_override_ohne_ci_wird_nicht_vom_waechter_gestoppt(tmp_path):
    """GIVEN kein CI, kein --workers / WHEN das echte Setup läuft / THEN kein Wächter-Abbruch."""
    res = _run_setup(tmp_path, ci=False)
    out = res.stdout + res.stderr
    assert "Running 1 test using 1 worker" in out, out
    assert not _guard_fired(out), out


@needs_playwright
def test_ac2_setup_mit_zwei_workern_bricht_mit_grund_und_abhilfe_ab(tmp_path):
    """GIVEN --workers=2 / WHEN das echte Setup läuft / THEN rot, Meldung nennt Grund + Abhilfe."""
    res = _run_setup(tmp_path, "--workers=2", ci=False)
    out = res.stdout + res.stderr
    assert res.returncode != 0, out
    for marker in GUARD_MARKERS:
        assert marker in out, f"Meldung ohne {marker!r}:\n{out}"
    assert re.search(r"Sprache", out), out
    # Abbruch VOR jedem Netzzugriff: weder Seitenaufruf noch API-Anfrage erreicht.
    assert "ECONNREFUSED" not in out and "net::ERR" not in out, out


@needs_playwright
def test_ac2_setup_mit_workers_4_bricht_ebenfalls_ab(tmp_path):
    """Grenze: jede Zahl > 1, nicht nur genau 2."""
    res = _run_setup(tmp_path, "--workers=4", ci=False)
    out = res.stdout + res.stderr
    assert res.returncode != 0, out
    assert _guard_fired(out), out


@needs_playwright
def test_ac3_mit_ci_unveraendert_ein_worker():
    """GIVEN CI=1 / WHEN die Haupt-Config geladen wird / THEN workers == 1 (wie bisher)."""
    assert _resolved_workers(ci=True) == 1


@needs_playwright
def test_ac3_setup_mit_ci_kein_waechter_abbruch(tmp_path):
    res = _run_setup(tmp_path, ci=True)
    out = res.stdout + res.stderr
    assert not _guard_fired(out), out


@needs_playwright
def test_ac3_fallzahl_setup_projekt_unveraendert_ein_fall(tmp_path):
    """Der Wächter ist kein eigener Testfall: das Setup-Projekt listet genau 1 Fall."""
    cfg = _helper_config(tmp_path)
    res = subprocess.run(
        [str(PLAYWRIGHT_BIN), "test", "--config", str(cfg), "--project=setup", "--list"],
        cwd=FRONTEND, env=_env(False), capture_output=True, text=True, timeout=120,
    )
    out = res.stdout + res.stderr
    assert res.returncode == 0, out
    assert "Total: 1 test in 1 file" in out, out


def test_ac5_doku_haupt_suite_laeuft_immer_seriell():
    # doc-compliance-test: reine Doku-Zusicherung (AC-5), kein Verhaltensnachweis.
    text = GATES_DOC.read_text(encoding="utf-8")
    zeilen = [z for z in text.splitlines() if "#3137" in z]
    assert zeilen, "kein Verweis auf #3137 in gates_und_ratschen.md"
    joined = " ".join(zeilen)
    assert "seriell" in joined
    assert "Konto" in joined
