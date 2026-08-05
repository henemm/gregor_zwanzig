"""Der Bildvergleich darf keine Anmeldemaske als bestandenen Nachweis ausgeben.

Hintergrund (#1307 Scheibe B): `design_fidelity_diff.py` verlor die Anmeldung
LAUTLOS — `page.fill`/`page.click` werfen keine Ausnahme, wenn die Anwendung
die Zugangsdaten ablehnt. Das Werkzeug lief weiter, fotografierte das
Anmeldeformular und schrieb einen Bericht mit `passed: true` (23,35 % bei
Schwelle 30 %). Der Design-Waechter haette diesen Bericht als echten Nachweis
akzeptiert.

Zwei Schichten, beide ohne Mock:

1. Die Entscheidung selbst (`unauthenticated_reason`) wird direkt aufgerufen.
2. Die WIRKUNG wird an einem echten Lauf gemessen: das Werkzeug laeuft als
   Subprozess mit echtem Playwright gegen einen echten lokalen HTTP-Server
   (127.0.0.1, kein Netz nach draussen). A/B — dieselbe Konfiguration, nur die
   ausgelieferte Seite unterscheidet sich:
     A) Seite mit Passwortfeld  → KEIN Bericht, Rueckgabewert != 0
     B) Seite ohne Passwortfeld → Bericht entsteht (die Pruefung schlaegt also
        nicht pauschal an, sondern unterscheidet)
   Ohne (B) waere (A) auch dann gruen, wenn das Werkzeug generell scheitert.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Pruefling relativ zu DIESER Testdatei (Pfadregel #1409) — sonst prueft ein
# Worktree-Lauf die unveraenderte Hauptrepo-Kopie und meldet falsches Gruen.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DIFF_TOOL = _REPO_ROOT / ".claude" / "hooks" / "design_fidelity_diff.py"

# Bewusst NICHT in SCREEN_URL_MAP → das Werkzeug ruft "/" auf, also die
# Startseite des lokalen Testservers.
_SCREEN = "test-auth-guard-screen"

_PAGE_WITH_PASSWORD = """<!doctype html><html><body style="background:#fff">
<h1>Anmelden um fortzufahren</h1>
<form><input name="username"><input name="password" type="password">
<button type="submit">Anmelden</button></form>
</body></html>"""

_PAGE_WITHOUT_PASSWORD = """<!doctype html><html><body style="background:#fff">
<h1>Orts-Vergleiche</h1>
<form><input name="username"><button type="submit">Weiter</button></form>
</body></html>"""


def _load_tool():
    spec = importlib.util.spec_from_file_location("design_fidelity_diff", str(DIFF_TOOL))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Schicht 1: die Entscheidung
# ---------------------------------------------------------------------------
class TestUnauthenticatedReason:
    def test_redirect_to_login_is_no_valid_capture(self):
        reason = _load_tool().unauthenticated_reason(
            "https://staging.example.com/login", False
        )
        assert reason is not None and "Anmeldemaske" in reason

    def test_visible_password_field_is_no_valid_capture(self):
        reason = _load_tool().unauthenticated_reason(
            "https://staging.example.com/compare", True
        )
        assert reason is not None and "Passwortfeld" in reason

    def test_authenticated_target_page_is_accepted(self):
        """Gegenprobe: ohne diese Zusicherung wuerde eine Pruefung, die IMMER
        anschlaegt, die beiden Faelle oben ebenfalls bestehen."""
        assert _load_tool().unauthenticated_reason(
            "https://staging.example.com/compare", False
        ) is None


# ---------------------------------------------------------------------------
# Schicht 2: die Wirkung am echten Lauf
# ---------------------------------------------------------------------------
def _serve(directory: Path):
    """Echter lokaler HTTP-Server als Subprozess (kein Socket im Testprozess,
    damit pytest-socket unberuehrt bleibt). Gibt (Popen, base_url) zurueck."""
    # `-u`: ohne ungepufferte Ausgabe bleibt die Startmeldung im Puffer des
    # Kindprozesses haengen und readline() blockiert bis zum Test-Timeout.
    # Die Meldung geht auf STDOUT (http.server nutzt print), nicht auf stderr.
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "http.server", "0", "--bind", "127.0.0.1",
         "--directory", str(directory)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    line = proc.stdout.readline()
    match = re.search(r"port (\d+)", line)
    if match is None:
        proc.kill()
        pytest.fail(f"Lokaler Testserver nicht gestartet: {line!r}")
    return proc, f"http://127.0.0.1:{match.group(1)}"


def _project(tmp_path: Path, page_html: str) -> Path:
    """Arbeitsverzeichnis mit Soll-Bild und ausgelieferter Seite."""
    from PIL import Image

    www = tmp_path / "www"
    www.mkdir()
    (www / "index.html").write_text(page_html)

    soll = tmp_path / "claude-code-handoff" / "current" / "soll"
    soll.mkdir(parents=True)
    Image.new("RGB", (1024, 683), (255, 255, 255)).save(soll / f"{_SCREEN}.png")
    return www


def _run_tool(tmp_path: Path, base: str, workflow: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if k not in ("OPENSPEC_ACTIVE_WORKFLOW", "GZ_ACTIVE_WORKFLOW")}
    env["GZ_VALIDATION_URL"] = base
    # Zugangsdaten sind gesetzt, damit der Anmelde-Zweig wirklich durchlaufen
    # wird — genau dort scheiterte es lautlos. Werte sind bedeutungslos, die
    # Testseite nimmt jede Eingabe an.
    env["GZ_AUTH_USER"] = "irgendwer"
    env["GZ_AUTH_PASS"] = "irgendwas"
    return subprocess.run(
        [sys.executable, str(DIFF_TOOL), "--screen", _SCREEN, "--workflow", workflow],
        capture_output=True, text=True, cwd=str(tmp_path), env=env, timeout=120,
    )


@pytest.mark.timeout(180)
def test_login_page_yields_no_passed_report(tmp_path):
    """A: Bleibt das Passwortfeld stehen, entsteht KEIN Bericht — auch ein
    frueher bestandener wird nicht stehen gelassen — und der Rueckgabewert ist
    von Null verschieden."""
    workflow = "test-auth-guard"
    www = _project(tmp_path, _PAGE_WITH_PASSWORD)

    # Altlast: ein bestandener Bericht aus einem frueheren Lauf. Der Waechter
    # sucht per Glob nach IRGENDEINEM `passed: true` — er darf einen
    # gescheiterten Lauf nicht ueberleben.
    report = tmp_path / "docs" / "artifacts" / workflow / f"design-diff-{_SCREEN}.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"screen": _SCREEN, "passed": True, "diff_pct": 0.0}))

    proc, base = _serve(www)
    try:
        result = _run_tool(tmp_path, base, workflow)
    finally:
        proc.kill()

    assert result.returncode != 0, (
        f"Werkzeug muss mit von Null verschiedenem Rueckgabewert abbrechen, "
        f"lieferte {result.returncode}.\nstdout: {result.stdout[:300]}"
    )
    assert "keine gueltige Aufnahme" in result.stderr, (
        "Der Abbruch muss benennen, was fehlt (Anmeldung), statt an einer "
        f"anderen Stelle zu scheitern.\nstderr: {result.stderr[:400]}"
    )
    assert not report.exists(), (
        "Der bestandene Bericht aus dem frueheren Lauf hat einen gescheiterten "
        "Lauf ueberlebt — der Waechter wuerde ihn als Nachweis akzeptieren."
    )


@pytest.mark.timeout(180)
def test_page_without_password_field_still_produces_report(tmp_path):
    """B: Dieselbe Konfiguration, nur ohne Passwortfeld — hier MUSS ein Bericht
    entstehen. Ohne diesen Fall waere A auch dann gruen, wenn das Werkzeug aus
    ganz anderem Grund immer scheitert."""
    workflow = "test-auth-guard-ok"
    www = _project(tmp_path, _PAGE_WITHOUT_PASSWORD)

    proc, base = _serve(www)
    try:
        result = _run_tool(tmp_path, base, workflow)
    finally:
        proc.kill()

    report = tmp_path / "docs" / "artifacts" / workflow / f"design-diff-{_SCREEN}.json"
    assert report.exists(), (
        "Ohne Passwortfeld muss das Werkzeug aufnehmen und berichten — die "
        "Pruefung darf nicht pauschal anschlagen.\n"
        f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:400]}"
    )
    assert "keine gueltige Aufnahme" not in result.stderr
    assert "diff_pct" in json.loads(report.read_text())
