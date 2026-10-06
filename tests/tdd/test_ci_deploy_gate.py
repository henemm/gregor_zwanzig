"""CI-Auslieferungs-Job wartet auf den echten Staging-Nachweis (#2047 Scheibe 2).

# doc-compliance-test — ``ci.yml`` ist nicht als Ganzes ausfuehrbar. Die
Struktur-Zusicherungen (needs, concurrency, Schrittfolge) werden per
``yaml.safe_load`` geprueft. Wo es geht, wird der ``run``-Text eines Schritts
aber ECHT ausgefuehrt (bash -eo pipefail wie auf dem GitHub-Runner, ``ssh``/
``curl`` als protokollierende Ersatz-Kommandos im PATH), damit die Zusicherung
dort geprueft wird, wo sie wirkt: Exit-Code-Abbildung und Telegram-Texte.

Spec: docs/specs/modules/fix_2047_s2_ci_prod_gate.md
"""
from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
WAIT_SCRIPT = REPO_ROOT / "scripts" / "ci_wait_for_verdict.sh"

AMPEL_JOBS = {"test", "lint", "go-test", "frontend-test", "svelte-check", "e2e"}


def _deploy_job() -> dict:
    jobs = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))["jobs"]
    assert "deploy" in jobs, "Job 'deploy' fehlt in ci.yml"
    return jobs["deploy"]


def _steps() -> list[dict]:
    return _deploy_job()["steps"]


def _run(step: dict) -> str:
    return step.get("run", "") or ""


def _index_of(pred, what: str) -> int:
    hits = [i for i, s in enumerate(_steps()) if pred(s)]
    assert hits, f"kein Schritt im Job deploy, der {what}"
    return hits[0]


def _wait_index() -> int:
    return _index_of(lambda s: "ci_wait_for_verdict.sh" in _run(s), "ci_wait_for_verdict.sh aufruft")


def _deploy_index() -> int:
    return _index_of(lambda s: "deploy-gregor-prod.sh" in _run(s), "deploy-gregor-prod.sh aufruft")


def _selftest_index() -> int:
    return _index_of(lambda s: "prod_selftest.py" in _run(s), "prod_selftest.py aufruft")


def _telegram_steps() -> list[dict]:
    return [s for s in _steps() if "api.telegram.org" in _run(s)]


def _neutralise(text: str) -> str:
    """GitHub-Ausdruecke ``${{ ... }}`` durch harmlose Platzhalter ersetzen."""
    return re.sub(r"\$\{\{[^}]*\}\}", "dummy", text)


def _stub(bindir: Path, name: str, body: str) -> None:
    path = bindir / name
    path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _execute_step(step: dict, tmp_path: Path, env_extra: dict[str, str]) -> tuple[int, str, Path]:
    """Fuehrt den run-Text eines Schritts wie der GitHub-Runner aus."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    calls = tmp_path / "calls.log"
    # ssh: protokolliert seinen Aufruf, endet mit dem gesteuerten Exit-Code.
    _stub(bindir, "ssh", f'echo "ssh $*" >> "{calls}"\nexit "${{STUB_SSH_RC:-0}}"\n')
    _stub(bindir, "scp", f'echo "scp $*" >> "{calls}"\nexit 0\n')
    # curl: haelt den gesendeten Koerper fest (Telegram), sendet nichts.
    _stub(
        bindir,
        "curl",
        f'while [ $# -gt 0 ]; do if [ "$1" = "-d" ]; then shift; '
        f'printf "%s\\n" "$1" >> "{tmp_path}/telegram.log"; fi; shift; done\nexit 0\n',
    )
    script = tmp_path / "step.sh"
    script.write_text(_neutralise(_run(step)), encoding="utf-8")
    gh_out = tmp_path / "github_output"
    gh_out.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(gh_out),
        "GITHUB_SHA": "a" * 40,
        "COMMIT_MSG": "feat: Testmeldung",
        "CHAT_ID": "4711",
        "SHA": "b" * 40,
        "RUN_URL": "https://example.invalid/run/1",
        **env_extra,
    }
    proc = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script)],
        env=env,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode, proc.stdout + proc.stderr, gh_out


def _outcome(gh_out: Path) -> str | None:
    for line in gh_out.read_text(encoding="utf-8").splitlines():
        if line.startswith("outcome="):
            return line.split("=", 1)[1].strip()
    return None


# --- AC-1 -----------------------------------------------------------------


def test_deploy_wartet_auf_alle_sechs_ampel_jobs():
    """AC-1: GIVEN ci.yml WHEN Job deploy gelesen THEN needs = alle 6 Ampel-Jobs."""
    needs = _deploy_job().get("needs", [])
    needs = {needs} if isinstance(needs, str) else set(needs)
    fehlend = AMPEL_JOBS - needs
    assert not fehlend, f"deploy.needs fehlen Ampel-Jobs: {sorted(fehlend)} (needs={sorted(needs)})"


# --- AC-2 / AC-3 ------------------------------------------------------------


def test_kein_schritt_schreibt_einen_nachweis():
    """AC-2: Kein Schritt des Jobs deploy ruft ``--write-verdict`` auf."""
    treffer = [s.get("name", "?") for s in _steps() if "--write-verdict" in _run(s)]
    assert not treffer, f"CI stellt sich den Nachweis selbst aus in: {treffer}"


def test_kein_schritt_resettet_den_hauptordner():
    """AC-3: Kein Schritt des Jobs deploy enthaelt ``git reset --hard``."""
    treffer = [s.get("name", "?") for s in _steps() if re.search(r"git\s+reset\s+--hard", _run(s))]
    assert not treffer, f"harter Reset ausserhalb des Deploy-Skripts in: {treffer}"


# --- AC-4 / AC-13 -----------------------------------------------------------


def test_warteschritt_vor_deploy_aus_origin_main_bezogen():
    """AC-4: Warteschritt ruft ci_wait_for_verdict.sh (aus origin/main) vor dem Deploy auf."""
    wait, deploy = _wait_index(), _deploy_index()
    assert wait < deploy, "Warteschritt muss VOR dem Deploy-Schritt stehen"
    run = _run(_steps()[wait])
    assert "origin/main:scripts/ci_wait_for_verdict.sh" in run, (
        "das Warte-Skript muss aus origin/main bezogen werden, nicht aus dem Server-Arbeitsbaum"
    )
    assert "github.sha" in run or "GITHUB_SHA" in run, "der Warteschritt muss github.sha uebergeben"
    assert _steps()[wait].get("id"), "der Warteschritt braucht eine id, damit Folge-Schritte outcome lesen"


def test_warte_skript_defaults_takt_60s_fenster_60min():
    """AC-4: Default-Takt 60 s, Default-Fenster 3600 s, Gate = staging_gate.py --check --expected-commit."""
    assert WAIT_SCRIPT.exists(), f"{WAIT_SCRIPT} fehlt"
    text = WAIT_SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"GZ_WAIT_INTERVAL:-60\b", text), "Default-Takt 60 s fehlt"
    assert re.search(r"GZ_WAIT_WINDOW:-3600\b", text), "Default-Fenster 3600 s fehlt"
    assert "staging_gate.py" in text and "--expected-commit" in text, (
        "das Warte-Skript muss dieselbe Gate-Logik befragen (staging_gate.py --check --expected-commit)"
    )


def test_deploys_laufen_nacheinander_und_werden_nie_abgebrochen():
    """AC-13: concurrency group prod-deploy, cancel-in-progress false."""
    conc = _deploy_job().get("concurrency")
    assert isinstance(conc, dict), f"Job deploy hat keine concurrency-Sektion (ist: {conc!r})"
    assert conc.get("group") == "prod-deploy"
    assert conc.get("cancel-in-progress") is False


# --- AC-8: Exit-Code-Abbildung des Warteschritts (echt ausgefuehrt) ---------


@pytest.mark.parametrize(
    "ssh_rc, step_ok, liefert",
    [
        (0, True, True),  # Nachweis da
        (10, True, False),  # kein Nachweis im Fenster -> gruen, nicht ausliefern
        (11, True, False),  # ueberholt -> gruen, nicht ausliefern
        (1, False, False),  # Fehler im Warte-Skript -> rot
        (255, False, False),  # SSH-Verbindung scheitert -> rot
    ],
)
def test_warteschritt_bildet_exit_codes_ab(tmp_path, ssh_rc, step_ok, liefert):
    """AC-5/6/7/8: Exit 0 -> deliver; 10/11 -> gruen ohne Auslieferung; 1/SSH-Fehler -> rot."""
    step = _steps()[_wait_index()]
    rc, out, gh_out = _execute_step(step, tmp_path, {"STUB_SSH_RC": str(ssh_rc)})
    assert (rc == 0) is step_ok, f"ssh-Exit {ssh_rc}: Schritt-Exit {rc} (erwartet ok={step_ok})\n{out}"
    if step_ok:
        outcome = _outcome(gh_out)
        assert outcome, f"ssh-Exit {ssh_rc}: kein outcome= in GITHUB_OUTPUT\n{out}"
        assert (outcome == "deliver") is liefert, f"ssh-Exit {ssh_rc}: outcome={outcome!r}"
    if ssh_rc == 10:
        assert "/70-deploy" in out, "Meldung bei fehlendem Nachweis muss /70-deploy nennen"
    if ssh_rc == 11:
        assert "überholt" in out or "ueberholt" in out, "Meldung bei Ueberholung muss 'überholt' nennen"


def test_outcome_10_und_11_sind_unterscheidbar(tmp_path):
    """AC-6/AC-7: 'kein Nachweis' und 'überholt' setzen verschiedene outcome-Werte."""
    step = _steps()[_wait_index()]
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _, _, out10 = _execute_step(step, a, {"STUB_SSH_RC": "10"})
    _, _, out11 = _execute_step(step, b, {"STUB_SSH_RC": "11"})
    assert _outcome(out10) != _outcome(out11)


# --- AC-8 / AC-9: Folge-Schritte ---------------------------------------------


def test_selftest_folgt_auf_den_deploy():
    """AC-9: Nach deploy-gregor-prod.sh laeuft prod_selftest.py per SSH."""
    deploy, selftest = _deploy_index(), _selftest_index()
    assert deploy < selftest, "prod_selftest.py muss NACH dem Deploy-Schritt laufen"
    assert "ssh" in _run(_steps()[selftest]), "der Selbsttest laeuft per SSH auf dem Server"


@pytest.mark.parametrize("which", ["deploy", "selftest"])
def test_deploy_und_selftest_nur_bei_deliver_und_ohne_continue_on_error(which):
    """AC-8/AC-9: Deploy + Selftest nur bei outcome == deliver; ein Fehlschlag faerbt den Job rot."""
    step = _steps()[_deploy_index() if which == "deploy" else _selftest_index()]
    cond = str(step.get("if", ""))
    assert "outcome" in cond and "deliver" in cond, f"{which}: if={cond!r} bezieht sich nicht auf outcome == deliver"
    assert not step.get("continue-on-error"), f"{which}: continue-on-error wuerde einen Fehlschlag verschlucken"


@pytest.mark.parametrize("ssh_rc", [1, 255])
def test_selftest_fehlschlag_macht_den_schritt_rot(tmp_path, ssh_rc):
    """AC-9: Exit != 0 des Selbsttests (bzw. SSH) laesst den Schritt rot enden."""
    rc, out, _ = _execute_step(_steps()[_selftest_index()], tmp_path, {"STUB_SSH_RC": str(ssh_rc)})
    assert rc != 0, f"Selbsttest-Exit {ssh_rc} wurde verschluckt\n{out}"


# --- AC-10: Telegram-Texte ----------------------------------------------------


def _telegram_texts(tmp_path: Path) -> list[tuple[dict, str]]:
    result = []
    for i, step in enumerate(_telegram_steps()):
        d = tmp_path / f"tg{i}"
        d.mkdir()
        rc, out, _ = _execute_step(step, d, {})
        assert rc == 0, f"Telegram-Schritt {step.get('name')!r} scheitert lokal:\n{out}"
        log = d / "telegram.log"
        body = log.read_text(encoding="utf-8") if log.exists() else ""
        result.append((step, body))
    return result


def test_telegram_texte_passen_zum_ausgang(tmp_path):
    """AC-10: vier Ausgaenge, vier Texte; 'kein Nachweis' sagt nie 'deployed'."""
    texts = _telegram_texts(tmp_path)
    bodies = [b for _, b in texts]
    assert any("deployed" in b for b in bodies), "Text 'ausgeliefert' (deployed) fehlt"
    assert any("FEHLGESCHLAGEN" in b for b in bodies), "Fehlschlag-Text fehlt"
    assert any("bereits ausgeliefert" in b for b in bodies), "Text 'bereits ausgeliefert' fehlt"
    kein = [b for b in bodies if "/70-deploy" in b]
    assert kein, "Text 'kein Nachweis — Session liefert per /70-deploy' fehlt"
    assert all("deployed" not in b for b in kein), "der Kein-Nachweis-Text darf nie 'deployed' sagen"
    bereits = [b for b in bodies if "bereits ausgeliefert" in b]
    assert all("deployed:" not in b for b in bereits), "'bereits ausgeliefert' ist kein neuer Deploy"


def test_telegram_schritte_haben_paarweise_verschiedene_bedingungen():
    """AC-10: genau eine Meldung je Lauf — jede Telegram-Meldung hat eine eigene if-Bedingung."""
    conds = [str(s.get("if", "")).strip() for s in _telegram_steps()]
    assert len(conds) >= 4, f"erwartet mindestens 4 Telegram-Schritte, gefunden {len(conds)}"
    assert all(conds), "jeder Telegram-Schritt braucht eine explizite if-Bedingung"
    assert len(set(conds)) == len(conds), f"doppelte Bedingungen -> Doppelmeldung moeglich: {conds}"
    deployed = [s for s in _telegram_steps() if "gregor20 deployed" in _run(s)]
    assert deployed and all("deliver" in str(s.get("if", "")) for s in deployed), (
        "der 'deployed'-Text darf nur bei outcome == deliver gesendet werden"
    )


# --- AC-17 / AC-19: ADR und Doku ---------------------------------------------


def test_adr_0084_ergaenzt_adr_0006():
    """AC-17: ADR-0084 existiert, verweist auf ADR-0006 und steht im Index."""
    adr_dir = REPO_ROOT / "docs" / "adr"
    files = sorted(adr_dir.glob("0084-*.md"))
    assert files, "docs/adr/0084-*.md fehlt"
    assert "0006" in files[0].read_text(encoding="utf-8"), "ADR-0084 muss ADR-0006 referenzieren"
    assert "0084" in (adr_dir / "README.md").read_text(encoding="utf-8"), "ADR-Index ohne 0084"


DOKU = [
    "CLAUDE.md",
    ".claude/commands/70-deploy.md",
    ".claude/commands/e2e-verify.md",
    "docs/reference/operations_playbook.md",
    "docs/reference/gates_und_ratschen.md",
]


@pytest.mark.parametrize("rel", DOKU)
def test_doku_nennt_sechs_checks(rel):
    """AC-19: keine Doku-Stelle spricht mehr von 5 Ampel-Checks."""
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    alt = re.findall(r"[^\n]*\b5 Checks\b[^\n]*", text)
    assert not alt, f"{rel}: veraltete '5 Checks'-Stellen: {alt}"


def test_e2e_verify_nennt_keinen_veralteten_nachweis_dateinamen():
    """AC-19: e2e-verify.md nennt nicht mehr den alten Singleton ``e2e_verified.json``."""
    text = (REPO_ROOT / ".claude" / "commands" / "e2e-verify.md").read_text(encoding="utf-8")
    assert not re.search(r"(?<![/\w])e2e_verified\.json", text), "veralteter Dateiname e2e_verified.json"


@pytest.mark.parametrize("rel", [".claude/commands/70-deploy.md", "docs/reference/operations_playbook.md"])
def test_doku_beschreibt_ci_auto_deploy_mit_warten_auf_nachweis(rel):
    """AC-19: der CI-Auto-Deploy mit Warten auf den echten Nachweis ist beschrieben."""
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    assert "ci_wait_for_verdict" in text, f"{rel}: CI-Warten auf den Nachweis nicht beschrieben"
