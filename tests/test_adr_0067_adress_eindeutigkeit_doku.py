# doc-compliance-test
"""Doku-Wächter Issue #2147 Scheibe C, AC-19 (Spec google_login_adress_verknuepfung.md).

Given die Spec und ADR 0067 sind angelegt / When ADR-Index und
docs/specs/modules/google_oauth_login.md geprüft werden / Then ist ADR 0067 im
Index verzeichnet und JEDE Stelle von google_oauth_login.md, die „kein
Account-Linking in v1" zusagt, ist ausdrücklich als durch ADR 0067 abgelöst
markiert.

Warum ein Dateiinhalt-Test: das Prüfobjekt IST die Dokumentation — eine
veraltete Zusage „separate Konten bei gleicher Adresse" widerspräche nach
Scheibe C dem Code und würde die nächste Sitzung auf den falschen Stand setzen.
Index-/Status-Konsistenz aller ADRs bewacht zusätzlich tests/test_adr_index_drift.py.

Pfade relativ zu dieser Datei (Pfadregel #1409).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ADR_DIR = REPO / "docs" / "adr"
README = ADR_DIR / "README.md"
GOOGLE_SPEC = REPO / "docs" / "specs" / "modules" / "google_oauth_login.md"

_ADR_0067 = re.compile(r"ADR[- ]?0067|\(0067-[^)]*\.md\)|\b0067\b")
_ABGELOEST = re.compile(r"abgelöst|abgeloest|superseded", re.IGNORECASE)
_LINKING_V1 = re.compile(r"account-linking", re.IGNORECASE)


def _adr_0067_dateien() -> list[Path]:
    return sorted(ADR_DIR.glob("0067-*.md"))


def test_ac19_adr_0067_datei_existiert():
    dateien = _adr_0067_dateien()
    assert len(dateien) == 1, (
        f"AC-19: genau eine Datei docs/adr/0067-*.md erwartet, gefunden: {[p.name for p in dateien]}"
    )
    text = dateien[0].read_text(encoding="utf-8")
    assert re.search(r"\*\*Status:\*\*", text), "AC-19: ADR 0067 braucht eine **Status:**-Zeile"


def test_ac19_adr_0067_steht_im_index():
    dateien = _adr_0067_dateien()
    assert dateien, "AC-19: ADR 0067 fehlt — kann nicht im Index stehen"
    index = README.read_text(encoding="utf-8")
    assert f"({dateien[0].name})" in index, (
        f"AC-19: docs/adr/README.md verlinkt {dateien[0].name} nicht"
    )


def test_ac19_google_spec_markiert_kein_linking_als_abgeloest():
    zeilen = GOOGLE_SPEC.read_text(encoding="utf-8").splitlines()
    fundstellen = [i for i, z in enumerate(zeilen) if _LINKING_V1.search(z) and "v1" in z]
    assert fundstellen, (
        "AC-19: in google_oauth_login.md keine Stelle zu „Account-Linking … v1“ gefunden — "
        "Messpunkt verloren (Zeilen umformuliert?), Test nachziehen statt still grün"
    )
    unmarkiert = []
    for i in fundstellen:
        # Markierung in derselben Zeile oder der unmittelbar folgenden nicht-leeren Zeile.
        umfeld = zeilen[i]
        for folgend in zeilen[i + 1:]:
            if folgend.strip():
                umfeld += "\n" + folgend
                break
        if not (_ADR_0067.search(umfeld) and _ABGELOEST.search(umfeld)):
            unmarkiert.append(f"Z. {i + 1}: {zeilen[i].strip()[:100]}")
    assert not unmarkiert, (
        "AC-19: diese Aussagen zu „kein Account-Linking in v1“ sind nicht als durch ADR 0067 "
        "abgelöst markiert:\n  " + "\n  ".join(unmarkiert)
    )
