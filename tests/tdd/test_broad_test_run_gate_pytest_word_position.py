"""TDD RED -- Issue #1478 Teil 1: `broad_test_run_gate.py` haelt jedes Token
mit dem Wortlaut "pytest" fuer einen Aufrufbeginn, unabhaengig von seiner
Position im Kommando. Das blockiert reine Lesebefehle, die "pytest" nur als
Argumentwert eines ANDEREN Kommandos enthalten (`grep -n "pytest" datei`,
`pgrep -af "pytest"`), faelschlich.

SPEC: docs/specs/modules/fix_1478_teil1_gate_fehlalarme.md (AC-1 bis AC-12)

Kein Mock-Theater: `_pytest_invocations()` wird direkt mit echten Token-Listen
geprueft (Unit-Ebene), der volle Gate-Pfad ueber einen echten Subprozess mit
JSON-Payload auf stdin (End-to-End-Ebene, identisches Muster wie
tests/tdd/test_fix_853_842_837_tooling_gates.py).
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))

import broad_test_run_gate as gate  # noqa: E402


def _run_gate(command: str) -> subprocess.CompletedProcess:
    """Fuehrt den echten Hook als Subprozess aus (kein In-Process-Aufruf --
    main() ruft sys.exit(), das wuerde den Testprozess beenden)."""
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(ROOT / ".claude" / "hooks" / "broad_test_run_gate.py")],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


class TestPytestInvocationsUnit:
    """Direkte Pruefung von `_pytest_invocations()` gegen bereits
    tokenisierte Kommandos (kein Subprozess noetig)."""

    def test_ac1_uv_run_pytest_recognized(self):
        tokens = ["uv", "run", "pytest", "tests/tdd/x.py"]
        assert gate._pytest_invocations(tokens) == [2]

    def test_ac2_pytest_as_grep_pattern_not_recognized(self):
        tokens = ["grep", "-n", "pytest", ".github/workflows/ci.yml"]
        assert gate._pytest_invocations(tokens) == []

    def test_ac3_pytest_as_pgrep_pattern_not_recognized(self):
        tokens = ["pgrep", "-af", "pytest"]
        assert gate._pytest_invocations(tokens) == []

    def test_ac4_pytest_after_separator_recognized(self):
        tokens = ["echo", "x", "&&", "pytest", "tests/tdd/x.py"]
        assert gate._pytest_invocations(tokens) == [3]

    def test_bare_pytest_at_segment_start_still_recognized(self):
        tokens = ["pytest", "tests/"]
        assert gate._pytest_invocations(tokens) == [0]

    def test_python_dash_m_pytest_still_recognized(self):
        tokens = ["python3", "-m", "pytest", "tests/tdd/x.py"]
        assert gate._pytest_invocations(tokens) == [2]

    def test_semicolon_separator_recognized(self):
        tokens = ["cmd1", ";", "pytest", "tests/tdd/x.py"]
        assert gate._pytest_invocations(tokens) == [2]

    def test_pipe_separator_recognized(self):
        tokens = ["echo", "x", "|", "pytest", "tests/tdd/x.py"]
        assert gate._pytest_invocations(tokens) == [3]


class TestGateEndToEnd:
    """Voller Hook-Pfad ueber Subprozess -- belegt die tatsaechliche
    Blockier-/Freigabe-Wirkung, nicht nur die Hilfsfunktion."""

    def test_ac2_grep_for_pytest_not_blocked(self):
        result = _run_gate('grep -n "pytest" .github/workflows/ci.yml')
        assert result.returncode == 0, result.stderr

    def test_ac3_pgrep_for_pytest_not_blocked(self):
        result = _run_gate('pgrep -af "pytest"')
        assert result.returncode == 0, result.stderr

    def test_ac5_bare_broad_pytest_still_blocked(self):
        result = _run_gate("pytest tests/")
        assert result.returncode == 2, (
            f"Echter breiter Testlauf MUSS weiterhin blockiert werden, "
            f"war returncode={result.returncode}, stderr={result.stderr!r}"
        )
        assert "BLOCKED" in result.stderr

    def test_uv_run_pytest_broad_still_blocked(self):
        result = _run_gate("uv run pytest tests/")
        assert result.returncode == 2
        assert "BLOCKED" in result.stderr

    def test_uv_run_pytest_named_file_still_allowed(self):
        result = _run_gate("uv run pytest tests/tdd/test_x.py")
        assert result.returncode == 0, result.stderr


class TestAC6LauncherPrefixesStillBlocked:
    """Adversary-Fund F001 (Runde 1, BROKEN): die erste Fix-Fassung nutzte
    eine Positions-Allowlist (Segmentanfang / nach 'run'), die reale
    Launcher-Praefixe NICHT als Kommando-Position erkannte -- ein breiter
    Lauf dahinter wurde faelschlich NICHT blockiert (Regression gegenueber
    dem Alt-Code, der jedes 'pytest'-Token positionsunabhaengig matchte).
    Diese Tests belegen je einen der von der Adversary-Session real
    reproduzierten Faelle (exit=0 statt exit=2 mit der ersten Fix-Fassung)."""

    def test_env_prefix_still_blocked(self):
        result = _run_gate("env pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_nice_prefix_still_blocked(self):
        result = _run_gate("nice pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_timeout_prefix_still_blocked(self):
        result = _run_gate("timeout 60 pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_sudo_prefix_still_blocked(self):
        result = _run_gate("sudo pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_xargs_prefix_still_blocked(self):
        result = _run_gate("xargs pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr


class TestAC7AmpersandSeparatorRecognized:
    """Adversary-Fund F002: '&' (einfacher Hintergrund-Trenner, nicht '&&')
    fehlte in _SEGMENT_SEPARATORS -- ein pytest-Aufruf im Hintergrund-Segment
    wurde nicht als eigenes Segment erkannt und lief unblockiert durch."""

    def test_background_ampersand_segment_still_blocked(self):
        result = _run_gate("sleep 1 & pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr


class TestF003F004BoundaryHardening:
    """Adversary-Runde 2 (VERIFIED, 2 MEDIUM-Findings aus der Mutationsprobe):
    der ausgelieferte Code ist in beiden Faellen bereits korrekt -- diese
    Tests sichern die Boundary-Bedingungen gegen kuenftige Regression ab.

    F003: `_nearest_non_flag_predecessor` bricht bei einem Trenner-Token
    (hier '&&') sofort ab und liefert None -- ein Suchkommando OHNE
    Argumente direkt vor dem Trenner darf 'pytest' im NAECHSTEN Segment
    nicht als sein Suchmuster vereinnahmen.

    F004: der Vorgaenger-Suchradius ist bewusst genau 1 Token -- ein
    Suchkommando MIT einem Wortargument direkt vor 'pytest' (kein Trenner
    dazwischen) darf 'pytest' ebenfalls nicht vereinnahmen, weil der
    unmittelbare Vorgaenger ('foo') kein bekanntes Suchkommando ist.
    """

    def test_f003_grep_before_separator_does_not_swallow_next_segment(self):
        tokens = ["grep", "&&", "pytest", "tests/"]
        assert gate._pytest_invocations(tokens) == [2]

        result = _run_gate("grep && pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_f004_grep_with_word_arg_before_pytest_does_not_swallow(self):
        tokens = ["grep", "foo", "pytest", "tests/"]
        assert gate._pytest_invocations(tokens) == [2]

        result = _run_gate("grep foo pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr


class TestAC8F005FlagValueNotInvocation:
    """Adversary-Fund F005 (Runde 2, BROKEN): der unconditionelle '-m'-Zweig
    registrierte JEDES '<kommando> -m pytest' als Aufruf, unabhaengig davon,
    ob <kommando> ueberhaupt Python ist. Live am unmutierten Code
    reproduziert: git commit -m pytest / git log --grep pytest /
    grep -m pytest datei wurden faelschlich blockiert -- 'pytest' ist in
    allen drei Faellen erkennbar der Freitext-Wert eines Flags, kein
    eigener Aufruf. Gerade 'git commit -m' ist im PR-Liefer-Workflow dieses
    Projekts allgegenwaertig."""

    def test_git_commit_dash_m_pytest_message_not_blocked(self):
        result = _run_gate('git commit -m "pytest"')
        assert result.returncode == 0, result.stdout + result.stderr

    def test_git_log_grep_pytest_not_blocked(self):
        result = _run_gate("git log --grep pytest")
        assert result.returncode == 0, result.stdout + result.stderr

    def test_grep_dash_m_pytest_not_blocked(self):
        result = _run_gate("grep -m pytest datei.txt")
        assert result.returncode == 0, result.stdout + result.stderr

    def test_unit_git_commit_dash_m_pytest_not_recognized(self):
        tokens = ["git", "commit", "-m", "pytest"]
        assert gate._pytest_invocations(tokens) == []

    def test_unit_grep_dash_m_pytest_not_recognized(self):
        tokens = ["grep", "-m", "pytest", "datei.txt"]
        assert gate._pytest_invocations(tokens) == []


class TestAC9PythonDashMStillRecognized:
    """Regressionswaechter zu AC-8: die Flag-Wert-Ausnahme darf den
    einzigen legitimen '-m'-Fall (python -m pytest) nicht mit ausschliessen."""

    def test_python3_dash_m_pytest_still_recognized(self):
        tokens = ["python3", "-m", "pytest", "tests/tdd/x.py"]
        assert gate._pytest_invocations(tokens) == [2]

        result = _run_gate("python3 -m pytest tests/tdd/x.py")
        assert result.returncode == 0, result.stdout + result.stderr

    def test_bare_python_dash_m_pytest_broad_still_blocked(self):
        result = _run_gate("python3 -m pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr


class TestAC10F006LauncherWithFlagStillBlocked:
    """Adversary-Fund F006 (Runde 3, BROKEN): 'jedes Flag vor pytest schliesst
    aus, ausser -m+Python' war selbst zu pauschal -- ein einzelnes Flag
    zwischen einem echten Launcher und 'pytest' hebelte die AC-6-Erkennung
    wieder aus. Live am unmutierten Runde-3-Code reproduziert (RC=0 statt 2
    fuer alle fuenf Beispiele)."""

    def test_sudo_with_flag_still_blocked(self):
        result = _run_gate("sudo -E pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_nice_with_flag_still_blocked(self):
        result = _run_gate("nice -n10 pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_xargs_with_braces_flag_still_blocked(self):
        result = _run_gate("xargs -I{} pytest {} tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_xargs_with_n_flag_still_blocked(self):
        result = _run_gate("xargs -n1 pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_env_with_flag_still_blocked(self):
        result = _run_gate("env -S pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_unit_sudo_with_flag_recognized(self):
        tokens = ["sudo", "-E", "pytest", "tests/"]
        assert gate._pytest_invocations(tokens) == [2]


class TestAC11F007PathQualifiedPythonRecognized:
    """Adversary-Fund F007 (Runde 3): _PYTHON_LAUNCHER_RE matchte nur den
    nackten Interpreter-Namen, nicht pfad-qualifizierte Formen -- realistisch
    haeufig (Skripte/Cron/systemd/venv-relative Pfade)."""

    def test_absolute_path_python3_dash_m_pytest_still_blocked(self):
        result = _run_gate("/usr/bin/python3 -m pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_venv_relative_python3_dash_m_pytest_still_blocked(self):
        result = _run_gate(".venv/bin/python3 -m pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_absolute_path_versioned_python_still_blocked(self):
        result = _run_gate("/usr/bin/python3.12 -m pytest tests/")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_unit_absolute_path_python_recognized(self):
        tokens = ["/usr/bin/python3", "-m", "pytest", "tests/"]
        assert gate._pytest_invocations(tokens) == [2]


class TestAC12FAdv1ArgsAfterAmpersandBoundary:
    """Adversary-Fund F-ADV1 (Runde 4, BROKEN, CRITICAL): _args_after() hatte
    ein eigenes, nie mit _SEGMENT_SEPARATORS synchronisiertes Trenner-Set
    ohne '&'. _pytest_invocations() erkannte einen breiten Aufruf VOR einem
    '&'-Hintergrund-Trenner zwar korrekt, aber _args_after() sammelte
    Tokens ueber die Grenze hinweg ein und hielt ein '.py'-Token aus dem
    NAECHSTEN, unabhaengigen Segment faelschlich fuer eine benannte
    Testdatei des ERSTEN Aufrufs -- genau der 2026-08-03-Vorfall (voller,
    ungemarkerter Testlauf laeuft durch)."""

    def test_broad_pytest_before_ampersand_with_py_token_after_still_blocked(self):
        result = _run_gate("pytest tests/ & x.py")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_broad_pytest_before_ampersand_with_echo_py_after_still_blocked(self):
        result = _run_gate("pytest tests/ & echo x.py")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_control_double_ampersand_still_blocked(self):
        # Kontrollprobe: mit '&&' (bereits vor Runde 5 im stop-Set) war es
        # schon immer korrekt -- isoliert den Fund eindeutig auf '&'.
        result = _run_gate("pytest tests/ && echo x.py")
        assert result.returncode == 2, result.stdout + result.stderr
        assert "BLOCKED" in result.stderr

    def test_unit_args_after_stops_at_ampersand(self):
        tokens = ["pytest", "tests/", "&", "x.py"]
        assert gate._args_after(tokens, 0) == ["tests/"]
