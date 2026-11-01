---
entity_id: fix-2560-lawinenmail-name-typwort
type: bugfix
created: 2026-11-01
updated: 2026-11-01
status: draft
version: "1.0"
tags: [validator, official-alert, lawine, fast-track]
---

# Mini-Spec: Lawinenmail-Erkennung ignoriert Trip-/Ortsnamen (#2560)

## Was ändert sich
- `.claude/hooks/official_alert_mail_validator.py`: Vor der Prüfung `_OTHER_HAZARD_RE` (Variable `avalanche_only`) wird der Trip-/Ortsname aus dem durchsuchten Text entfernt. Der Name wird aus dem Betreff-Präfix `[Name]` gelesen und nur dort entfernt, wo er als Kopf-/Fußzeilen-Name steht (direkt gefolgt von ` · `). Er wird nicht überall entfernt, damit ein echtes Typwort in der Warnkarte erhalten bleibt.
- `tests/tdd/test_official_alert_mail_validator.py`: Zwei neue Tests (siehe unten).
- Die Regex `_OTHER_HAZARD_RE` selbst bleibt unverändert (bewusst ohne Wortgrenze, MeteoAlarm-Labels).

## Was darf sich nicht ändern
- Eine Gewittermail ohne Leiter, an die ein Lawinentext angehängt ist, fällt weiter an S-2 durch (bestehender Test F012).
- Gemischte Mails (Gewitter + Lawine) verhalten sich wie bisher.
- Der Validator blockiert weiterhin nur sich selbst bzw. das Renderer-Commit-Gate, nie den Versand.

## Acceptance Criteria

**AC-1:** Given eine echt gerenderte reine Lawinenmail eines Trips mit dem Namen „PROBE Sturmtrip", When der Validator sie prüft, Then besteht sie (Exit-Status ok, keine S-2-Meldung).

**AC-2:** Given eine echt gerenderte reine Lawinenmail eines Trips mit dem Namen „Hitzeck", When der Validator sie prüft, Then besteht sie ebenfalls.

**AC-3:** Given eine Gewittermail ohne Leiter und ohne Farbwörter, an die ein Lawinentext angehängt ist, und der Trip heißt „PROBE Sturmtrip", When der Validator sie prüft, Then fällt sie weiterhin mit S-2 durch.

## Manuelle Test-Schritte
1. `uv run pytest tests/tdd/test_official_alert_mail_validator.py` – alle Tests grün.
2. Mutation: Entfernung des Namens auskommentieren – AC-1/AC-2 müssen rot werden.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Test für AC-1/AC-2 (parametrisiert über Trip-Namen) und AC-3
