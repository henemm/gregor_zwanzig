"""CI-Auslieferung absichern: Idempotenz, Selbsttest, Serialisierung (#2047 Scheibe 2b).

# doc-compliance-test — ``ci.yml`` ist nicht als Ganzes ausfuehrbar. Struktur-
Zusicherungen (concurrency, Schrittfolge) werden per ``yaml.safe_load`` geprueft.
Wo es geht, wird der ``run``-Text eines Schritts aber ECHT ausgefuehrt (bash
-eo pipefail wie auf dem GitHub-Runner, ``ssh``/``curl`` als protokollierende
Ersatz-Kommandos im PATH), und die ``if``-Bedingungen werden mit einem kleinen,
strengen Auswerter fuer GitHub-Ausdruecke ueber alle Status-Kombinationen
ausgewertet — die Zusicherung wird dort geprueft, wo sie wirkt.

Die Basis aus #2516 (needs auf 6 Ampel-Jobs, kein Nachweis-Schreiber, kein
``git reset``, Gate-Schritt, Notice bei ``closed``) bewacht
``tests/test_ci_prod_gate.py``; diese Datei prueft nur das Delta.

Spec: docs/specs/modules/fix_2047_s2_ci_prod_gate.md (Fassung 2.0)
"""
from __future__ import annotations

import itertools
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# Wortlaut, den deploy-gregor-prod.sh (henemm-infra) im Kurzschluss ausgibt —
# derselbe Text, den henemm-infra/tests/test_deploy_gregor_prod_idempotenz.py
# auf stdout zusichert. Der CI-Runner kann henemm-infra nicht lesen; die Kopplung
# "Skript druckt X <-> ci.yml erkennt X" haengt allein an diesem Literal.
KURZSCHLUSS_AUSGABE = "[deploy-gregor-prod] Stand " + "c" * 40 + " bereits ausgeliefert — nichts zu tun."
NORMALE_AUSGABE = "[deploy-gregor-prod] Deploy abgeschlossen, Smoke-Test OK."


# --- Zugriff auf den Job ------------------------------------------------------


def _deploy_job() -> dict:
    jobs = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))["jobs"]
    assert "deploy" in jobs, "Job 'deploy' fehlt in ci.yml"
    return jobs["deploy"]


def _steps() -> list[dict]:
    return _deploy_job()["steps"]


def _run(step: dict) -> str:
    return step.get("run", "") or ""


def _only(pred, what: str) -> tuple[int, dict]:
    hits = [(i, s) for i, s in enumerate(_steps()) if pred(s)]
    assert len(hits) == 1, f"erwartet genau einen Schritt, der {what}; gefunden {len(hits)}"
    return hits[0]


def _deploy_step() -> tuple[int, dict]:
    return _only(lambda s: "deploy-gregor-prod.sh" in _run(s), "deploy-gregor-prod.sh aufruft")


def _selftest_step() -> tuple[int, dict]:
    return _only(lambda s: "prod_selftest.py" in _run(s), "prod_selftest.py aufruft")


def _telegram_steps() -> list[dict]:
    return [s for s in _steps() if "api.telegram.org" in _run(s)]


def _telegram(marker: str) -> dict:
    hits = [s for s in _telegram_steps() if marker in _run(s)]
    assert len(hits) == 1, f"erwartet genau einen Telegram-Schritt mit Text {marker!r}, gefunden {len(hits)}"
    return hits[0]


# --- Auswerter fuer GitHub-``if``-Ausdruecke ------------------------------------

_TOKEN = re.compile(
    r"\s+|success\(\)|failure\(\)|cancelled\(\)|always\(\)"
    r"|steps\.gate\.outputs\.open|steps\.deploy\.outputs\.already"
    r"|'[^']*'|==|!=|&&|\|\||!|\(|\)"
)
_STATUS_FN = ("success()", "failure()", "cancelled()", "always()")


def _eval_if(expr: str | None, status: str, open_: str, already: str) -> bool:
    """Wertet eine ``if``-Bedingung wie GitHub aus.

    - Ohne Statusfunktion gilt implizit ``success() && (...)``.
    - ``cancelled``: success() und failure() sind beide false.
    - Unbekannte Tokens schlagen HART fehl — eine anders formulierte Bedingung
      darf den Test nicht still vakuum-gruen machen.
    """
    text = str(expr or "").strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    values = {
        "success()": status == "success",
        "failure()": status == "failure",
        "cancelled()": status == "cancelled",
        "always()": True,
        "steps.gate.outputs.open": open_,
        "steps.deploy.outputs.already": already,
    }
    py: list[str] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        assert m, f"if-Ausdruck mit unbekanntem Token ab {text[pos:]!r} (Ausdruck: {text!r})"
        tok = m.group(0)
        pos = m.end()
        if tok.isspace():
            continue
        if tok in values:
            py.append(repr(values[tok]))
        elif tok.startswith("'"):
            py.append(repr(tok[1:-1]))
        else:
            py.append({"&&": " and ", "||": " or ", "!": " not "}.get(tok, tok))
    result = bool(eval("".join(py) or "True", {"__builtins__": {}}, {}))  # noqa: S307 — nur eigene Tokens
    if not any(fn in text for fn in _STATUS_FN):
        result = result and status == "success"
    return result


STATUS = ("success", "failure", "cancelled")
OPEN = ("true", "false", "")  # "" = Gate-Schritt lieferte keinen Output
ALREADY = ("true", "false", "")  # "" = Deploy-Schritt lief nicht


def test_auswerter_selbstprobe():
    """Harness-Gegenprobe: der Auswerter bildet die GitHub-Semantik ab, die die Tests brauchen."""
    assert _eval_if("steps.gate.outputs.open == 'true'", "success", "true", "") is True
    assert _eval_if("steps.gate.outputs.open == 'true'", "failure", "true", "") is False  # implizit success()
    assert _eval_if("failure()", "cancelled", "true", "") is False
    assert _eval_if("success() && steps.deploy.outputs.already != 'true'", "success", "true", "") is True
    assert _eval_if("!cancelled() && failure()", "failure", "", "") is True
    with pytest.raises(AssertionError):
        _eval_if("contains(steps.x.outputs.y, 'z')", "success", "true", "")


# --- Ausfuehrungs-Harness -------------------------------------------------------


def _stub(bindir: Path, name: str, body: str) -> None:
    path = bindir / name
    path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _execute_step(step: dict, tmp_path: Path, env_extra: dict[str, str]) -> tuple[int, str, Path]:
    """Fuehrt den run-Text eines Schritts wie der GitHub-Runner aus (bash -eo pipefail)."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    calls = tmp_path / "calls.log"
    # ssh: protokolliert seinen Aufruf, gibt STUB_SSH_OUT aus, endet mit STUB_SSH_RC.
    _stub(
        bindir,
        "ssh",
        f'echo "ssh $*" >> "{calls}"\n'
        'if [ -n "${STUB_SSH_OUT:-}" ]; then printf "%s\\n" "$STUB_SSH_OUT"; fi\n'
        'exit "${STUB_SSH_RC:-0}"\n',
    )
    _stub(bindir, "scp", f'echo "scp $*" >> "{calls}"\nexit 0\n')
    # curl: haelt den gesendeten Koerper fest (Telegram), sendet nichts.
    _stub(
        bindir,
        "curl",
        f'while [ $# -gt 0 ]; do if [ "$1" = "-d" ]; then shift; '
        f'printf "%s\\n" "$1" >> "{tmp_path}/telegram.log"; fi; shift; done\nexit 0\n',
    )
    text = re.sub(r"\$\{\{[^}]*\}\}", "dummy", _run(step))
    # Schluesseldatei des Runners nicht auf dem echten /tmp ablegen.
    text = text.replace("/tmp/deploy_key", str(tmp_path / "deploy_key"))
    script = tmp_path / "step.sh"
    script.write_text(text, encoding="utf-8")
    gh_out = tmp_path / "github_output"
    gh_out.write_text("", encoding="utf-8")
    summary = tmp_path / "step_summary"
    summary.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(gh_out),
        "GITHUB_STEP_SUMMARY": str(summary),
        "GITHUB_SHA": "a" * 40,
        "COMMIT_MSG": 'feat: Testmeldung mit "Anfuehrungszeichen"',
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


def _output(gh_out: Path, key: str) -> str | None:
    value = None
    for line in gh_out.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            value = line.split("=", 1)[1].strip()
    return value


def _ssh_calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "calls.log"
    return [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.startswith("ssh ")] if log.exists() else []


# --- AC-4: Serialisierung ---------------------------------------------------------


def test_deploys_laufen_nacheinander_und_werden_nie_abgebrochen():
    """AC-4: GIVEN Job deploy WHEN geparst THEN concurrency group prod-deploy, cancel-in-progress false."""
    conc = _deploy_job().get("concurrency")
    assert isinstance(conc, dict), f"Job deploy hat keine concurrency-Sektion (ist: {conc!r})"
    assert conc.get("group") == "prod-deploy", f"concurrency.group = {conc.get('group')!r}"
    assert conc.get("cancel-in-progress") is False, (
        f"cancel-in-progress = {conc.get('cancel-in-progress')!r} — ein laufender Deploy darf nie abgebrochen werden"
    )


# --- AC-5: Selbsttest im CI-Pfad --------------------------------------------------


def test_selbsttest_folgt_auf_den_deploy_und_laeuft_nur_bei_offenem_gate():
    """AC-5/AC-6: Selbsttest steht nach dem Deploy und laeuft genau dann, wenn Gate open und Job gruen."""
    d_idx, _ = _deploy_step()
    s_idx, selftest = _selftest_step()
    assert d_idx < s_idx, "prod_selftest.py muss NACH dem Deploy-Schritt laufen"
    assert not selftest.get("continue-on-error"), "continue-on-error wuerde einen roten Selbsttest verschlucken"
    cond = selftest.get("if")
    assert cond, "der Selbsttest braucht eine if-Bedingung auf das Gate"
    for status, open_ in itertools.product(STATUS, OPEN):
        soll = status == "success" and open_ == "true"
        ist = _eval_if(cond, status, open_, "")
        assert ist is soll, f"Selbsttest if={cond!r}: status={status} open={open_!r} -> {ist}, erwartet {soll}"


def test_selbsttest_genau_ein_ssh_aufruf_im_hauptordner(tmp_path):
    """AC-5: GIVEN Ersatz-ssh Exit 0 WHEN Selbsttest-Schritt laeuft THEN genau ein ssh mit cd + prod_selftest.py."""
    _, selftest = _selftest_step()
    assert not re.search(r"\|\|\s*true", _run(selftest)), "'|| true' verschluckt den Exit des Selbsttests"
    rc, out, _ = _execute_step(selftest, tmp_path, {"STUB_SSH_RC": "0"})
    assert rc == 0, f"Selbsttest-Schritt scheitert trotz Exit 0:\n{out}"
    calls = _ssh_calls(tmp_path)
    assert len(calls) == 1, f"erwartet genau einen ssh-Aufruf, gefunden {len(calls)}: {calls}"
    assert "cd /home/hem/gregor_zwanzig" in calls[0], calls[0]
    assert "python3 .claude/hooks/prod_selftest.py" in calls[0], calls[0]


@pytest.mark.parametrize("ssh_rc", [1, 2, 255])
def test_roter_selbsttest_macht_den_job_rot(tmp_path, ssh_rc):
    """AC-5: GIVEN Selbsttest (bzw. ssh) endet mit Exit != 0 WHEN Schritt laeuft THEN Schritt-Exit != 0."""
    _, selftest = _selftest_step()
    rc, out, _ = _execute_step(selftest, tmp_path, {"STUB_SSH_RC": str(ssh_rc)})
    assert rc != 0, f"Selbsttest-Exit {ssh_rc} wurde verschluckt\n{out}"


# --- AC-7: already-Erkennung im Deploy-Schritt -----------------------------------


def test_deploy_schritt_hat_id_deploy():
    """AC-7: Folge-Schritte lesen steps.deploy.outputs.already — der Schritt braucht id 'deploy'."""
    _, deploy = _deploy_step()
    assert deploy.get("id") == "deploy", f"Deploy-Schritt id = {deploy.get('id')!r}"


@pytest.mark.parametrize(
    "ausgabe, erwartet",
    [(KURZSCHLUSS_AUSGABE, "true"), (NORMALE_AUSGABE, "false")],
    ids=["bereits-ausgeliefert", "normal-ausgeliefert"],
)
def test_deploy_schritt_setzt_already_aus_der_skriptausgabe(tmp_path, ausgabe, erwartet):
    """AC-7: GIVEN Skriptausgabe mit/ohne 'bereits ausgeliefert' WHEN Deploy-Schritt endet THEN already=true/false."""
    _, deploy = _deploy_step()
    rc, out, gh_out = _execute_step(deploy, tmp_path, {"STUB_SSH_RC": "0", "STUB_SSH_OUT": ausgabe})
    assert rc == 0, f"Deploy-Schritt scheitert trotz Skript-Exit 0:\n{out}"
    assert _output(gh_out, "already") == erwartet, (
        f"already = {_output(gh_out, 'already')!r}, erwartet {erwartet!r}\nGITHUB_OUTPUT:\n{gh_out.read_text()}"
    )
    assert ausgabe in out, "die Skriptausgabe muss im Job-Log sichtbar bleiben"


@pytest.mark.parametrize("ausgabe", [KURZSCHLUSS_AUSGABE, NORMALE_AUSGABE])
def test_skript_exitcode_bleibt_massgeblich(tmp_path, ausgabe):
    """AC-7: GIVEN Deploy-Skript endet mit Exit 1 WHEN Deploy-Schritt laeuft THEN Schritt rot (Ausgabe egal)."""
    _, deploy = _deploy_step()
    rc, out, _ = _execute_step(deploy, tmp_path, {"STUB_SSH_RC": "1", "STUB_SSH_OUT": ausgabe})
    assert rc != 0, f"Exit 1 des Deploy-Skripts wurde verschluckt\n{out}"


# --- AC-6 / AC-8: Telegram-Meldungen schliessen sich aus -------------------------


def test_drei_telegram_meldungen():
    """AC-8: genau drei Telegram-Schritte — deployed, bereits ausgeliefert, FEHLGESCHLAGEN."""
    assert len(_telegram_steps()) == 3, f"erwartet 3 Telegram-Schritte, gefunden {len(_telegram_steps())}"
    _telegram("gregor20 deployed")
    _telegram("bereits ausgeliefert")
    _telegram("FEHLGESCHLAGEN")


def test_hoechstens_eine_meldung_je_lauf_ueber_alle_kombinationen():
    """AC-6/AC-8: GIVEN jede Kombination Status x open x already WHEN if ausgewertet THEN passende Meldung."""
    deployed = _telegram("gregor20 deployed")
    bereits = _telegram("bereits ausgeliefert")
    fehl = _telegram("FEHLGESCHLAGEN")
    for status, open_, already in itertools.product(STATUS, OPEN, ALREADY):
        feuert = {
            name: _eval_if(step.get("if"), status, open_, already)
            for name, step in (("deployed", deployed), ("bereits", bereits), ("fehl", fehl))
        }
        lage = f"status={status} open={open_!r} already={already!r}: {feuert}"
        assert sum(feuert.values()) <= 1, f"zwei Meldungen in einem Lauf — {lage}"
        assert feuert["fehl"] is (status == "failure"), f"FEHLGESCHLAGEN nur bei failure() — {lage}"
        if already == "true":
            assert not feuert["deployed"], f"'deployed' trotz bereits ausgeliefertem Stand — {lage}"
        if status == "success" and open_ != "true":
            assert not any(feuert.values()), f"bei geschlossenem Gate keine Meldung — {lage}"
        if status == "success" and open_ == "true" and already == "false":
            assert feuert["deployed"], f"Auslieferung ohne 'deployed'-Meldung — {lage}"
        if status == "success" and open_ == "true" and already == "true":
            assert feuert["bereits"], f"Kurzschluss ohne 'bereits ausgeliefert'-Meldung — {lage}"


def test_telegram_texte_passen_zum_ausgang(tmp_path):
    """AC-8: die drei Schritte senden unterscheidbare Texte; 'bereits ausgeliefert' sagt nie 'deployed'."""
    bodies = {}
    for marker in ("gregor20 deployed", "bereits ausgeliefert", "FEHLGESCHLAGEN"):
        d = tmp_path / re.sub(r"\W+", "_", marker)
        d.mkdir()
        step = _telegram(marker)
        rc, out, _ = _execute_step(step, d, {})
        assert rc == 0, f"Telegram-Schritt {step.get('name')!r} scheitert lokal:\n{out}"
        log = d / "telegram.log"
        bodies[marker] = log.read_text(encoding="utf-8") if log.exists() else ""
        assert marker in bodies[marker], f"{step.get('name')!r} sendet nicht {marker!r}: {bodies[marker]!r}"
        assert "Testmeldung" in bodies[marker], "die erste Commit-Zeile fehlt im Text"
    assert "deployed" not in bodies["bereits ausgeliefert"], "'bereits ausgeliefert' ist kein neuer Deploy"


def test_commit_message_nur_per_env():
    """AC-8: Commit-Message nie per ${{ }} im Shell-Text (Injection, zerrissene Zuweisung)."""
    for step in _telegram_steps():
        assert "head_commit" not in _run(step), f"{step.get('name')!r}: Commit-Message im run-Text interpoliert"


# --- AC-9: Warte-Skript entfaellt ersatzlos ---------------------------------------


@pytest.mark.parametrize(
    "rel", ["scripts/ci_wait_for_verdict.sh", "tests/test_ci_wartet_auf_staging_nachweis.py"]
)
def test_warte_skript_und_sein_test_existieren_nicht_mehr(rel):
    """AC-9: das verworfene Warte-Skript (Fassung 1.0) und sein Test sind entfernt."""
    assert not (REPO_ROOT / rel).exists(), f"{rel} existiert noch"


def test_ci_yml_ruft_kein_warte_skript_auf():
    """AC-9: kein Schritt verweist auf ci_wait_for_verdict."""
    assert "ci_wait_for_verdict" not in CI_YML.read_text(encoding="utf-8")


# --- AC-10: ADR -------------------------------------------------------------------


def _adr_0084() -> Path:
    files = sorted((REPO_ROOT / "docs" / "adr").glob("0084-*.md"))
    assert len(files) == 1, f"erwartet genau eine docs/adr/0084-*.md, gefunden {files}"
    return files[0]


def test_adr_0084_ergaenzt_adr_0006_und_steht_im_index():
    """AC-10: ADR-0084 existiert, ergaenzt ADR-0006 und ist im Index gelistet."""
    adr = _adr_0084()
    text = adr.read_text(encoding="utf-8")
    assert "0006" in text, "ADR-0084 muss ADR-0006 referenzieren"
    index = (REPO_ROOT / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
    assert adr.name in index, f"ADR-Index verlinkt {adr.name} nicht"


@pytest.mark.parametrize(
    "begriff, muster",
    [
        ("schreibt keinen Nachweis", r"(nie|kein\w*)[^\n]{0,60}Nachweis|Nachweis[^\n]{0,60}(nie|nicht)"),
        ("Idempotenz", r"idempot"),
        ("Selbsttest", r"Selbsttest|prod_selftest"),
    ],
)
def test_adr_0084_haelt_die_entscheidung_fest(begriff, muster):
    """AC-10: das ADR haelt fest: kein Nachweis-Schreiber, idempotente Auslieferung, Selbsttest."""
    text = _adr_0084().read_text(encoding="utf-8")
    assert re.search(muster, text, re.IGNORECASE), f"ADR-0084 nennt '{begriff}' nicht"


# --- AC-11: Doku ------------------------------------------------------------------


def test_e2e_verify_nennt_den_commit_getaggten_nachweis_pfad():
    """AC-11: e2e-verify.md nennt .claude/e2e_verified/<sha>.json statt e2e_verified.json."""
    text = (REPO_ROOT / ".claude" / "commands" / "e2e-verify.md").read_text(encoding="utf-8")
    assert not re.search(r"(?<![/\w])e2e_verified\.json", text), "veralteter Dateiname e2e_verified.json"


def test_playbook_beschreibt_selbsttest_idempotenz_und_concurrency():
    """AC-11: operations_playbook.md nennt Selbsttest im CI-Pfad, Idempotenz und concurrency."""
    text = (REPO_ROOT / "docs" / "reference" / "operations_playbook.md").read_text(encoding="utf-8")
    assert re.search(r"CI[^\n]*(Selbsttest|prod_selftest)|(Selbsttest|prod_selftest)[^\n]*CI", text), (
        "Playbook: Selbsttest im CI-Pfad nicht beschrieben"
    )
    assert "bereits ausgeliefert" in text, "Playbook: Idempotenz-Kurzschluss nicht beschrieben"
    assert "concurrency" in text, "Playbook: Serialisierung (concurrency) nicht beschrieben"


def test_gate_referenz_nennt_notausgang():
    """AC-11: gates_und_ratschen.md nennt den Notausgang GZ_FORCE_REDEPLOY=1."""
    text = (REPO_ROOT / "docs" / "reference" / "gates_und_ratschen.md").read_text(encoding="utf-8")
    assert "GZ_FORCE_REDEPLOY=1" in text, "Gate-Referenz: Notausgang GZ_FORCE_REDEPLOY=1 fehlt"
