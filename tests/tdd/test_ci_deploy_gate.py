"""CI-Auslieferung (#2047 Scheibe 2b) — verbliebene Zusicherungen.

# doc-compliance-test — Die CI-Schritte aus S2b (Deploy per SSH, Selbsttest,
Idempotenz-Erkennung, Telegram, ``concurrency: prod-deploy``) sind seit #3394
(henemm-infra#522) entfernt: Produktion liefert allein der Pull-Deploy auf dem
Server aus. Was der Job ``deploy`` jetzt noch tun darf, bewacht
``tests/test_ci_deploy_ohne_ssh.py``. Hier bleiben die Zusicherungen, die
unabhaengig vom CI-Pfad gelten: Warte-Skript entfaellt, ADR-0085, Doku.

Spec: docs/specs/modules/fix_2047_s2_ci_prod_gate.md (Fassung 2.0)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"


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


def _adr_0085() -> Path:
    files = sorted((REPO_ROOT / "docs" / "adr").glob("0085-*.md"))
    assert len(files) == 1, f"erwartet genau eine docs/adr/0085-*.md, gefunden {files}"
    return files[0]


def test_adr_0085_ergaenzt_adr_0006_und_steht_im_index():
    """AC-10: ADR-0085 existiert, ergaenzt ADR-0006 und ist im Index gelistet."""
    adr = _adr_0085()
    text = adr.read_text(encoding="utf-8")
    assert "0006" in text, "ADR-0085 muss ADR-0006 referenzieren"
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
def test_adr_0085_haelt_die_entscheidung_fest(begriff, muster):
    """AC-10: das ADR haelt fest: kein Nachweis-Schreiber, idempotente Auslieferung, Selbsttest."""
    text = _adr_0085().read_text(encoding="utf-8")
    assert re.search(muster, text, re.IGNORECASE), f"ADR-0085 nennt '{begriff}' nicht"


# --- AC-11: Doku ------------------------------------------------------------------


def test_e2e_verify_nennt_den_commit_getaggten_nachweis_pfad():
    """AC-11: e2e-verify.md nennt .claude/e2e_verified/<sha>.json statt e2e_verified.json."""
    text = (REPO_ROOT / ".claude" / "commands" / "e2e-verify.md").read_text(encoding="utf-8")
    assert not re.search(r"(?<![/\w])e2e_verified\.json", text), "veralteter Dateiname e2e_verified.json"


def test_playbook_beschreibt_pull_deploy_idempotenz_und_keinen_ci_ssh_deploy():
    """AC-11 (Stand #3394): Playbook nennt Idempotenz und den Pull-Deploy als einzigen
    Prod-Weg aus der Automatik; der CI-SSH-Deploy ist als entfernt beschrieben."""
    text = (REPO_ROOT / "docs" / "reference" / "operations_playbook.md").read_text(encoding="utf-8")
    assert "bereits ausgeliefert" in text, "Playbook: Idempotenz-Kurzschluss nicht beschrieben"
    assert "pull-deploy-gregor-prod.sh" in text, "Playbook: Pull-Deploy nicht beschrieben"
    assert "#3394" in text, "Playbook: Entfernen des CI-SSH-Deploys (#3394) nicht beschrieben"


def test_gate_referenz_nennt_notausgang():
    """AC-11: gates_und_ratschen.md nennt den Notausgang GZ_FORCE_REDEPLOY=1."""
    text = (REPO_ROOT / "docs" / "reference" / "gates_und_ratschen.md").read_text(encoding="utf-8")
    assert "GZ_FORCE_REDEPLOY=1" in text, "Gate-Referenz: Notausgang GZ_FORCE_REDEPLOY=1 fehlt"
