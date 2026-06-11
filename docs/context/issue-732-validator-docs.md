# Context: Issue #732 — email_spec_validator Doku-Klarstellung

## Request Summary
CLAUDE.md stellt `email_spec_validator.py` als universell-zwingend für ALLE E-Mail-Features dar. Tatsächlich prüft der Validator fest die **Orts-Vergleich-Mail** und kann von einer **Trip-Briefing-Mail** strukturell nie bestanden werden. Doku-Klarstellung nötig (Coverage-Lücke selbst ist nach #733 ausgegliedert).

## Related Files
| File | Relevance |
|------|-----------|
| `CLAUDE.md` (Z.175–191) | Sektion „E-MAIL SPEC VALIDATOR (ZWINGEND!)" — suggeriert universelle Pflicht. ZU ÄNDERN. |
| `.claude/hooks/email_spec_validator.py` | Validator-Code — beweist die fest verdrahtete Orts-Vergleich-Struktur (Vergleichstabelle 8 Zeilen Z.179, Winner-Box Z.191, `--min-locations` Default 3 Z.341) |

## Existing Patterns
- CLAUDE.md ist Single Source of Truth für Workflow-Pflichten; andere Gate-Beschreibungen (E2E, Post-Deploy-Selftest) nennen präzise ihren Scope.
- Für Trip-Briefing-Mail ist der etablierte Nachweis (seit #722, #721, #636) ein echter IMAP-MIME-Verhaltenstest: Content-Type/multipart, CTE, isascii, Byte-Größe, Inhaltsblöcke present/absent.

## Dependencies
- Upstream: keine (Doku)
- Downstream: künftige Sessions, die E-Mail-Features ändern, lesen diese Regel und entscheiden danach, welchen Nachweis sie führen.

## Existing Specs
- Keine Modul-Spec betroffen (reine Workflow-Doku in CLAUDE.md).

## Risks & Considerations
- Risk: Künftige Session ändert Trip-Briefing-Mail, folgt der Regel wörtlich → Dauer-Exit-1 → falsche Schlussfolgerung „Feature kaputt" oder Gate-Erosion (Validator wird ignoriert).
- Considerations: Reine Doku-Änderung in CLAUDE.md → laut CLAUDE.md „Ausnahme: Reine Doku-/Tooling-Änderungen" → kein Staging/Prod-Deploy nötig. Compliance-Test (`# doc-compliance-test`) möglich, um die Regel-Präzisierung als Artefakt zu fixieren.
