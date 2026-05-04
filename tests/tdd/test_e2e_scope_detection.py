"""
TDD RED — E2E Commit Gate: Auto-Scope Detection (#86)

Tests fuer die detect_scope() Funktion in e2e_commit_gate.py.

ALLE Tests muessen FEHLSCHLAGEN, weil:
- detect_scope() existiert noch nicht
"""
import pytest
import sys
import os

# Hook-Verzeichnis in den Pfad aufnehmen
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '.claude', 'hooks'))


# -- Test 1: detect_scope Funktion existiert --

def test_detect_scope_exists():
    """
    GIVEN: e2e_commit_gate Modul
    WHEN: detect_scope importiert wird
    THEN: Die Funktion existiert
    """
    from e2e_commit_gate import detect_scope
    assert callable(detect_scope)


# -- Test 2: Frontend-only Erkennung --

def test_detect_scope_frontend_only(monkeypatch):
    """
    GIVEN: Nur frontend/ Dateien gestaget
    WHEN: detect_scope() aufgerufen wird
    THEN: Scope ist 'frontend-only'
    """
    from e2e_commit_gate import detect_scope
    import subprocess

    def mock_run(*args, **kwargs):
        result = subprocess.CompletedProcess(
            args=args[0], returncode=0,
            stdout="frontend/src/routes/compare/+page.svelte\nfrontend/src/lib/api.ts\n"
        )
        return result

    monkeypatch.setattr(subprocess, "run", mock_run)
    assert detect_scope() == "frontend-only"


# -- Test 3: Backend Erkennung --

def test_detect_scope_backend(monkeypatch):
    """
    GIVEN: Nur src/ und api/ Dateien gestaget
    WHEN: detect_scope() aufgerufen wird
    THEN: Scope ist 'backend'
    """
    from e2e_commit_gate import detect_scope
    import subprocess

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0,
            stdout="src/outputs/signal.py\napi/routers/notify.py\n"
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    assert detect_scope() == "backend"


# -- Test 4: Full-stack Erkennung --

def test_detect_scope_full_stack(monkeypatch):
    """
    GIVEN: Frontend UND Backend Dateien gestaget
    WHEN: detect_scope() aufgerufen wird
    THEN: Scope ist 'full-stack'
    """
    from e2e_commit_gate import detect_scope
    import subprocess

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0,
            stdout="frontend/src/routes/account/+page.svelte\nsrc/outputs/email.py\n"
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    assert detect_scope() == "full-stack"


# -- Test 5: Docs-only Erkennung --

def test_detect_scope_docs_only(monkeypatch):
    """
    GIVEN: Nur docs/ und .md Dateien gestaget
    WHEN: detect_scope() aufgerufen wird
    THEN: Scope ist 'docs-only'
    """
    from e2e_commit_gate import detect_scope
    import subprocess

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0,
            stdout="docs/specs/modules/foo.md\n.claude/hooks/bar.py\nREADME.md\n"
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    assert detect_scope() == "docs-only"


# -- Test 6: Unbekannte Pfade → Backend (konservativ) --

def test_detect_scope_unknown_path_is_backend(monkeypatch):
    """
    GIVEN: Unbekannte Pfade gestaget (z.B. config.ini, .env)
    WHEN: detect_scope() aufgerufen wird
    THEN: Scope ist 'backend' (konservativ)
    """
    from e2e_commit_gate import detect_scope
    import subprocess

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0,
            stdout="config.ini\n.env\n"
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    assert detect_scope() == "backend"


# -- Test 7: Leere Staging Area → docs-only --

def test_detect_scope_empty_staging(monkeypatch):
    """
    GIVEN: Keine Dateien gestaget
    WHEN: detect_scope() aufgerufen wird
    THEN: Scope ist 'docs-only' (Gate ueberspringen)
    """
    from e2e_commit_gate import detect_scope
    import subprocess

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=""
        )

    monkeypatch.setattr(subprocess, "run", mock_run)
    assert detect_scope() == "docs-only"
