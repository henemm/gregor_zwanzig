# doc-compliance-test
"""AC-14 (Issue #1412 S5): Spec-Verweise in Go-Testkoepfen muessen leben.

Werkzeug-Klasse `# doc-compliance-test`: liest die Kommentarkoepfe von fuenf
Go-Testdateien als DATEN und verlangt, dass jeder dort genannte
`docs/specs/...md`-Pfad als Datei existiert. Ein toter Verweis (z. B. auf
`docs/specs/_archive/modules/...`) macht den Test rot.

Pfade werden relativ zu dieser Testdatei auf den Repo-Root aufgeloest, nie
ueber den festen Hauptrepo-Pfad.

SPEC: docs/specs/modules/fix_1412_s5_go_empfaengerschutz.md (AC-14)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIL_DIR = REPO_ROOT / "internal" / "mail"

TESTDATEIEN = [
    "sender_allowlist_test.go",
    "recipient_guard_test.go",
    "resend_guard_test.go",
    "sender_verified_allowlist_test.go",
    "verify_send_test.go",
]

SPEC_PFAD = re.compile(r"docs/specs/[\w./-]+?\.md")


@pytest.mark.parametrize("name", TESTDATEIEN)
def test_spec_verweise_im_testkopf_existieren(name):
    datei = MAIL_DIR / name
    assert datei.is_file(), f"{name} fehlt unter {MAIL_DIR}"
    kopf = [z for z in datei.read_text(encoding="utf-8").splitlines() if z.strip().startswith("//")]
    pfade = sorted(set(SPEC_PFAD.findall("\n".join(kopf))))
    assert pfade, f"{name}: Kommentar nennt keinen docs/specs/...md-Pfad (Verweis verloren)"
    tot = [p for p in pfade if not (REPO_ROOT / p).is_file()]
    assert not tot, f"{name}: tote Spec-Verweise (Datei existiert nicht): {tot}"
