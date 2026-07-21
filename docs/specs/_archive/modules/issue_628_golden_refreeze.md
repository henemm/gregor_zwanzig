---
entity_id: issue_628_golden_refreeze
type: module
created: 2026-06-06
updated: 2026-06-06
status: draft
version: "1.0"
tags: [tests, golden, reports, cleanup]
---

# #628 Golden-Plain-Tests neu einfrieren (Tages-Summe seit #621)

## Approval

- [ ] Approved

## Purpose

5 Plain-Text-Golden-Tests sind seit #621 rot, weil der Tages-Summe-Block in
`plain.py` ergänzt, die eingefrorenen Vorlagen aber nie aktualisiert wurden.
Das Invarianz-Gate (#96/β3) ist dadurch wirkungslos. Diese Spec friert die
Goldens auf den aktuellen, beabsichtigten Output neu ein — nach voller
Diff-Prüfung, dass jede Differenz einer ausgelieferten Änderung entspricht.

## Source

- **File:** `tests/golden/email/*-plain.txt` (5 Vorlagen) + `tests/golden/email/test_email_plain_golden.py`
- **Identifier:** Golden-Refreeze

## Estimated Scope

- **LoC:** ~0 produktiv (nur Test-Fixtures + ggf. Regen-Helfer im Test)
- **Files:** 5 Golden-Vorlagen + ggf. Test-Datei
- **Effort:** low

## Acceptance Criteria

**AC-1:** Given die 5 roten Goldens, When der aktuelle `format_email().email_plain`
je Profil gegen die alte Vorlage gediffт wird, Then ist JEDE Differenz einer
bereits ausgelieferten, beabsichtigten Änderung zuordenbar (z.B. #621 Tages-Summe);
keine unerklärte/regressionsverdächtige Differenz wird eingefroren.

**AC-2:** Given der geprüfte Output, When die 5 Vorlagen neu eingefroren sind,
Then ist der Bit-Vergleich aller 5 Golden-Tests grün.

**AC-3:** Given die Aufgabe, When sie abgeschlossen ist, Then wurde KEIN
Produktivcode (`src/`) geändert — ausschließlich Test-Fixtures (und optional ein
Regen-Helfer in der Testdatei).

## Out of Scope

- Produktiv-Verhalten ändern (Tages-Summe etc. bleibt wie ausgeliefert).
- Andere Test-Suiten.

## Test-Strategie

Bit-Vergleich der 5 Goldens nach Refreeze grün; manuelle Vollständigkeits-Review
des `git diff tests/golden/email/` durch den Orchestrierer vor Commit.
