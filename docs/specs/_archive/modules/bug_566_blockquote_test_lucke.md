# Spec: Bug #566 — Test-Lücke Blockquote-Regression (5-implement / 7-deploy)

**Status:** Draft  
**Issue:** #566  
**Typ:** Bug (Test-Ergänzung)

## Problem

Der Test `test_bug_548_workflow_output_readability.py` hat zwei Stellen nie abgedeckt:
- `7-deploy.md`: Abschluss-Ausgabe „Fertig und live." (Z.101–102)
- `5-implement.md`: Adversary-Verdict-Ausgabe „Validator-Ergebnis:" (Z.197–198) und Abschluss-Zeile (Z.243)

Der Fix (Commit `97a4807c`) ist bereits deployed. Die Tests fehlen, sodass eine Regression unbemerkt bliebe.

## Scope

Nur `tests/tdd/test_bug_548_workflow_output_readability.py` wird erweitert. Kein Produktionscode.

## Acceptance Criteria

**AC-1:** Given `7-deploy.md` enthält die Abschluss-Ausgabe „Fertig und live." / When der Test `test_deploy_no_blockquote_in_fertig_und_live` läuft / Then schlägt er fehl, wenn diese Ausgabe als `>` Blockquote formatiert ist, und besteht, wenn sie plain text ist.

**AC-2:** Given `5-implement.md` enthält die Validator-Ergebnis-Ausgabe / When der Test `test_implement_no_blockquote_in_validator_result` läuft / Then schlägt er fehl, wenn „Validator-Ergebnis:", „VERIFIED/BROKEN/AMBIGUOUS" oder „Implementation complete. Adversary verified." als `>` Blockquote formatiert sind, und besteht, wenn sie plain text sind.

**AC-3:** Given der Fix `97a4807c` ist bereits deployed / When die gesamte Test-Suite `uv run pytest tests/tdd/test_bug_548_workflow_output_readability.py` läuft / Then sind alle Tests (inkl. der zwei neuen) grün.

## Out of Scope

- Änderungen an `5-implement.md` oder `7-deploy.md`
- Weitere Command-Dateien
