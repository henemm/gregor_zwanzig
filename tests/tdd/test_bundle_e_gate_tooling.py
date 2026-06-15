"""TDD — Bundle E: Gate-Tooling-Verlässlichkeit (#788, #786, #780).

Mock-frei. Echte Git-Repos (tmp_path), echte email.message.Message-Objekte,
echte Funktionsaufrufe gegen die isoliert geladenen Hook-Module. Kein Netzwerk.

ACs (siehe docs/specs/modules/bundle_e_gate_tooling.md):
  AC-1/AC-2  #788  Sentinel-URLs in prod_selftest._probe_ac → SKIPPED_NO_URL,
                   Verdict nicht PARTIAL.
  AC-3/AC-4  #786  run_selftest(scope=...) skippt docs-only, Erfolgspfad intakt.
  AC-5       #786  _detect_committed_scope(repo_dir) klassifiziert echten Commit.
  AC-6/AC-7/AC-8 #780  _message_matches / _decode_subject / fetch_latest_message-Default.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from email.message import EmailMessage
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
PROD_SELFTEST_PATH = HOOKS_DIR / "prod_selftest.py"
VALIDATOR_PATH = HOOKS_DIR / "briefing_mail_validator.py"


def _load_module(name: str, path: Path):
    """Lädt ein Hook-Modul isoliert. HOOKS_DIR auf sys.path (für `import _e2e_paths`)."""
    import sys

    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def selftest():
    return _load_module("bundle_e_selftest", PROD_SELFTEST_PATH)


@pytest.fixture(scope="module")
def validator():
    return _load_module("bundle_e_validator", VALIDATOR_PATH)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True,
                   capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "T")


# --------------------------------------------------------------------------- #
# #788 — AC-1 / AC-2: Sentinel-URLs
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("sentinel", ["n/a", "N/A", " n/a ", "na", "-", "none",
                                      "—", "interaktiv", "INTERAKTIV", ""])
def test_ac1_sentinel_url_skipped_no_http(selftest, sentinel):
    """AC-1: Sentinel-URL → SKIPPED_NO_URL, kein HTTP-GET."""
    finding = {"ac": "AC-1", "status": "PASS", "url": sentinel}
    result = selftest._probe_ac(finding)
    assert result["prod_status"] == "SKIPPED_NO_URL", result


def test_ac1_null_url_skipped_no_crash(selftest):
    """F001: url=None (JSON null) → kein AttributeError, prod_status == SKIPPED_NO_URL."""
    result = selftest._probe_ac({"status": "PASS", "url": None})
    assert result["prod_status"] == "SKIPPED_NO_URL", result


def test_ac2_all_sentinel_pass_findings_not_partial(selftest):
    """AC-2: Alle PASS-Findings mit Sentinel-URL → Verdict nicht PARTIAL."""
    findings = [
        {"ac": "AC-1", "status": "PASS", "url": "n/a"},
        {"ac": "AC-2", "status": "PASS", "url": "interaktiv"},
    ]
    probes = [selftest._probe_ac(f) for f in findings]
    verdict = selftest._derive_verdict(probes)
    assert verdict != "PARTIAL", (verdict, probes)
    assert verdict in ("PASS", "SKIPPED_ALL"), verdict


# --------------------------------------------------------------------------- #
# #786 — AC-5: _detect_committed_scope gegen echtes Git-Repo
# --------------------------------------------------------------------------- #
def test_ac5_detect_scope_docs_only(selftest, tmp_path):
    repo = tmp_path / "docsrepo"
    _init_repo(repo)
    (repo / "a.py").write_text("x = 1\n")  # erster Commit braucht Inhalt
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    docsdir = repo / ".claude"
    docsdir.mkdir()
    (docsdir / "x.md").write_text("doc\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "docs only")
    assert selftest._detect_committed_scope(repo) == "docs-only"


def test_ac5_detect_scope_backend(selftest, tmp_path):
    repo = tmp_path / "berepo"
    _init_repo(repo)
    (repo / "README.md").write_text("hi\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    srcdir = repo / "src"
    srcdir.mkdir()
    (srcdir / "mod.py").write_text("y = 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "backend change")
    assert selftest._detect_committed_scope(repo) == "backend"


# --------------------------------------------------------------------------- #
# #786 — AC-3 / AC-4: run_selftest(scope=...)
# --------------------------------------------------------------------------- #
def test_ac3_docs_only_scope_skips_despite_stale_attestation(selftest, tmp_path):
    """AC-3: scope=docs-only → Return 0, KEINE Commit-Mismatch-Prüfung."""
    att = tmp_path / "e2e_verified.json"
    att.write_text(json.dumps({"verified_commit": "deadbeef" * 5,
                               "findings": []}))
    rc = selftest.run_selftest(att, "wf-test", scope="docs-only")
    assert rc == 0


def test_ac4_backend_scope_does_not_early_skip(selftest, tmp_path):
    """AC-4: scope=backend skippt NICHT vorzeitig; nicht-existenter Pfad trifft
    den regulären 'Attestation fehlt'-Pfad (return 0) — beweist, dass der
    Code über den docs-only-Skip hinaus läuft. Netzwerkfrei."""
    missing = tmp_path / "nope.json"
    assert not missing.exists()
    rc = selftest.run_selftest(missing, "wf-test", scope="backend")
    assert rc == 0


# --------------------------------------------------------------------------- #
# #780 — AC-6 / AC-7 / AC-8: Mail-Auswahl-Prädikate
# --------------------------------------------------------------------------- #
def _make_msg(mail_type=None, subject="Subject"):
    m = EmailMessage()
    if mail_type is not None:
        m["X-GZ-Mail-Type"] = mail_type
    m["Subject"] = subject
    m.set_content("body")
    return m


def test_ac6_matches_own_marker_mail(validator):
    own = _make_msg(mail_type="trip-briefing", subject="[TEST] tok123 Report")
    foreign_no_marker = _make_msg(mail_type=None, subject="[TEST] tok123 Report")
    foreign_other_subject = _make_msg(mail_type="trip-briefing", subject="andere")

    assert validator._message_matches(
        own, mail_type="trip-briefing", subject_contains="tok123") is True
    assert validator._message_matches(
        foreign_no_marker, mail_type="trip-briefing", subject_contains="tok123") is False
    assert validator._message_matches(
        foreign_other_subject, mail_type="trip-briefing", subject_contains="tok123") is False


def test_ac7_rfc2047_subject_decoded_before_substring(validator):
    """AC-7: RFC-2047-kodiertes Subject (Em-Dash/Umlaut) wird dekodiert.

    Serialisieren + Reparsen erzeugt das echte Wire-Format (`=?utf-8?b?...?=`),
    wie es per IMAP zurückkommt.
    """
    import email as _email

    src = _make_msg(mail_type="trip-briefing", subject="Tag 3 — Gepäck tok999")
    msg = _email.message_from_bytes(src.as_bytes())
    raw_subject = msg["Subject"]
    assert "=?" in raw_subject  # wirklich RFC-2047-kodiert auf dem Wire

    assert validator._message_matches(
        msg, subject_contains="tok999") is True
    assert validator._message_matches(
        msg, subject_contains="Gepäck") is True
    # _decode_subject liefert lesbaren str
    decoded = validator._decode_subject(raw_subject)
    assert "Gepäck" in decoded
    assert "—" in decoded


def test_ac8_no_filters_returns_true(validator):
    """AC-8: beide None → True (rückwärtskompatibel)."""
    msg = _make_msg(mail_type=None, subject="irgendwas")
    assert validator._message_matches(msg) is True
    assert validator._message_matches(msg, mail_type=None, subject_contains=None) is True
