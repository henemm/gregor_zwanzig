"""TDD RED: briefing_mail_validator.py's No-Op-Zweig darf kein "Pass" sein
(Issue #1282, Fix-Workflow fix-1282-1283-gate-honesty, AC-2).

Mocks sind in diesem Projekt VERBOTEN. Der Seam ist deterministisch OHNE
IMAP erreichbar: ``validate_message()`` nimmt ein bereits geparstes
``email.message.Message``-Objekt entgegen -- wir konstruieren es synthetisch
(Header ``X-GZ-Mail-Type``) statt eine echte Mail abzurufen. Kein Netz, keine
echte Mail-Zustellung.

Getestete AC (docs/specs/modules/gate_honesty_mail_selftest.md):
  AC-2: Given briefing_mail_validator.py laeuft gegen eine Mail mit
        X-GZ-Mail-Type: compare (oder deviation-alert) / When der No-Op-Zweig
        greift / Then liefert validate_message() success=False, und
        _write_validation_log() schreibt passed: false PLUS skipped: true.

Aktuell (rot): der No-Op-Zweig in ``validate_message()``
(briefing_mail_validator.py Zeile ~498-501) liefert ``return True, [...]``
-- success ist also True, und das YAML bekommt (nach Schema-Erweiterung)
weder ``passed: false`` noch das neue ``skipped: true``-Feld.
"""
from __future__ import annotations

import importlib.util
import shutil
from email.message import Message
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SRC = _REPO_ROOT / ".claude" / "hooks"


def _load_briefing_validator(tmp_path: Path, module_name: str):
    """Laedt eine isolierte Kopie von briefing_mail_validator.py.

    Eigene Kopie-Verzeichnis pro Aufruf: ``_write_validation_log`` berechnet
    seinen log_dir relativ zu ``__file__`` -- damit landen Test-Logs in
    tmp_path statt im echten Repo (`.claude/workflows/_log` bleibt unberuehrt).
    """
    hooks_copy = tmp_path / f"hooks_{module_name}"
    hooks_copy.mkdir(parents=True, exist_ok=True)
    shutil.copy(_HOOKS_SRC / "briefing_mail_validator.py",
                hooks_copy / "briefing_mail_validator.py")
    path = hooks_copy / "briefing_mail_validator.py"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_message(mail_type: str) -> Message:
    msg = Message()
    msg["X-GZ-Mail-Type"] = mail_type
    msg["X-GZ-Format"] = "full"
    msg["Subject"] = "Test-Mail"
    msg.set_payload("Test-Body")
    return msg


# ---------------------------------------------------------------------------
# AC-2: validate_message() Rueckgabe-Vertragsebene -- kein echter Mail-Abruf
# ---------------------------------------------------------------------------

def test_compare_mail_type_noop_is_not_a_pass(tmp_path):
    """AC-2: mail_type='compare' -> No-Op-Zweig darf NICHT success=True
    liefern (das Gate wertet ein YAML mit passed:true als ausreichenden
    Nachweis -- ein No-Op ohne echte Pruefung darf das nicht sein)."""
    mod = _load_briefing_validator(tmp_path, "briefing_validator_noop_compare")
    msg = _make_message("compare")

    success, errors = mod.validate_message(msg)

    assert success is False, (
        "AC-2: validate_message() muss fuer mail_type='compare' im "
        "No-Op-Zweig success=False liefern (briefing_mail_validator.py "
        "Zeile ~498-501 gibt aktuell 'return True, [...]' zurueck). "
        f"success={success!r} errors={errors!r}"
    )


def test_deviation_alert_mail_type_noop_is_not_a_pass(tmp_path):
    """AC-2: mail_type='deviation-alert' -> derselbe No-Op-Zweig, dieselbe
    Erwartung wie fuer 'compare'."""
    mod = _load_briefing_validator(tmp_path, "briefing_validator_noop_deviation")
    msg = _make_message("deviation-alert")

    success, errors = mod.validate_message(msg)

    assert success is False, (
        "AC-2: validate_message() muss fuer mail_type='deviation-alert' im "
        "No-Op-Zweig success=False liefern. "
        f"success={success!r} errors={errors!r}"
    )


# ---------------------------------------------------------------------------
# AC-2: _write_validation_log() schreibt passed:false + skipped:true
# ---------------------------------------------------------------------------

def test_noop_validation_log_marks_not_passed_and_skipped(tmp_path):
    """AC-2: Das aus dem No-Op-Ergebnis geschriebene YAML muss sowohl
    'passed: false' als auch ein neues 'skipped: true'-Feld enthalten, damit
    das Gate den No-Op nicht als ausreichenden Nachweis akzeptiert und die
    Diagnose (No-Op vs. echter Fehlschlag) im Log nachvollziehbar bleibt."""
    mod = _load_briefing_validator(tmp_path, "briefing_validator_noop_log")
    msg = _make_message("compare")

    success, errors = mod.validate_message(msg)
    mod._write_validation_log(success, errors)

    # _write_validation_log() schreibt relativ zu seinem eigenen __file__:
    # hooks_dir.parent / "workflows" / "_log" -- hooks_dir ist die Kopie
    # unter tmp_path, also NIEMALS das echte Repo betroffen.
    hooks_copy_dir = tmp_path / "hooks_briefing_validator_noop_log"
    log_dir = hooks_copy_dir.parent / "workflows" / "_log"
    logs = list(log_dir.glob("*_briefing_validation.yaml"))
    assert logs, f"_write_validation_log() muss eine YAML-Datei schreiben (log_dir={log_dir})"

    content = logs[0].read_text()
    assert "passed: false" in content, (
        "AC-2: das No-Op-Validation-YAML muss 'passed: false' enthalten "
        "(aktuell 'passed: true', weil validate_message() fuer "
        "mail_type='compare' derzeit (True, [...]) liefert). "
        f"content={content!r}"
    )
    assert "skipped: true" in content, (
        "AC-2: das No-Op-Validation-YAML muss zusaetzlich ein neues "
        "'skipped: true'-Feld enthalten, um den No-Op von einem echten "
        "Fehlschlag zu unterscheiden -- dieses Feld existiert im aktuellen "
        f"YAML-Schema von _write_validation_log() noch nicht. content={content!r}"
    )
