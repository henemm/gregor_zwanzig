---
entity_id: issue_732_email_validator_scope_docs
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [docs, workflow, email, validator]
---

# Issue #732 — email_spec_validator Scope-Klarstellung (CLAUDE.md)

## Approval

- [ ] Approved

## Purpose

Die CLAUDE.md-Sektion „E-MAIL SPEC VALIDATOR (ZWINGEND!)" präzisieren, sodass klar ist: `email_spec_validator.py` prüft **ausschließlich** den **Orts-Vergleich-Mail**-Pfad. Für **Trip-Briefing-Mail**-Änderungen ist der Nachweis ein echter IMAP-MIME-Verhaltenstest. Verhindert Gate-Erosion durch Dauer-Exit-1 (Issue #732).

## Source

- **File:** `CLAUDE.md` (Sektion ab Z.175 „## E-MAIL SPEC VALIDATOR (ZWINGEND!)")
- **Identifier:** Workflow-Dokumentation (keine Code-Schicht — reine Doku-Änderung)
- **Belegquelle (read-only):** `.claude/hooks/email_spec_validator.py` (Vergleichstabelle 8 Zeilen Z.179, Winner-Box Z.191, `--min-locations` Default 3 Z.341) — beweist die fest verdrahtete Orts-Vergleich-Struktur.

## Estimated Scope

- **LoC:** ~15 (CLAUDE.md) + ~25 (Compliance-Test)
- **Files:** 2 (CLAUDE.md, neuer Compliance-Test)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `email_spec_validator.py` | Code (read-only) | Belegt den tatsächlichen Validator-Scope, der dokumentiert wird |
| Issue #733 | Follow-up | Echter eigener Validator für Trip-Briefing-Mails (ausgegliedert, NICHT Teil dieses Issues) |

## Implementation Details

```
CLAUDE.md-Sektion „## E-MAIL SPEC VALIDATOR (ZWINGEND!)" so umformulieren, dass:

1. Der Validator explizit als Prüfer des ORTS-VERGLEICH-MAIL-Pfads benannt wird
   (2 Tabellen, Vergleichstabelle, Winner-Box, --min-locations).
2. Die „NUR bei Exit 0 ..."-Pflicht auf Orts-Vergleich-Mail-Features eingegrenzt wird.
3. Für TRIP-BRIEFING-MAIL-Änderungen der etablierte Nachweis benannt wird:
   echter IMAP-MIME-Verhaltenstest (Content-Type/multipart, CTE, isascii,
   Byte-Größe, Inhaltsblöcke present/absent).
4. Auf #733 als ausgegliederte Coverage-Lücke verwiesen wird.
```

## Expected Behavior

- **Input:** Künftige Session liest CLAUDE.md, um zu entscheiden, welcher E-Mail-Nachweis vor „E2E Test bestanden" zu führen ist.
- **Output:** Eindeutige Scope-Trennung — Orts-Vergleich-Mail → `email_spec_validator.py`; Trip-Briefing-Mail → IMAP-MIME-Verhaltenstest.
- **Side effects:** Keine. Reine Doku. Kein Code-Pfad, kein Deploy.

## Acceptance Criteria

- **AC-1:** Given die CLAUDE.md-Sektion „E-MAIL SPEC VALIDATOR" / When ein Leser den Validator-Scope nachschlägt / Then nennt der Text explizit den **Orts-Vergleich-Mail**-Pfad (Vergleichstabelle/Winner-Box/`--min-locations`) als das, was der Validator prüft — nicht „alle E-Mail-Features" undifferenziert.
  - Test: `# doc-compliance-test` — liest die Sektion aus CLAUDE.md und prüft, dass der Orts-Vergleich-Scope benannt ist (Schlüsselbegriffe „Orts-Vergleich" UND eines von Winner-Box/Vergleichstabelle/min-locations).

- **AC-2:** Given dieselbe Sektion / When ein Leser nach dem Nachweis für eine **Trip-Briefing-Mail**-Änderung sucht / Then verweist der Text auf den echten IMAP-MIME-Verhaltenstest (Content-Type/multipart, CTE/Encoding, isascii, Byte-Größe, Inhaltsblöcke) als korrekten Nachweis — statt auf `email_spec_validator.py`.
  - Test: `# doc-compliance-test` — prüft, dass die Sektion „Trip-Briefing" zusammen mit IMAP/MIME-Nachweisbegriffen nennt.

- **AC-3:** Given die geänderte Sektion / When sie maschinell gelesen wird / Then ist die universell-absolute Formulierung „NUR bei Exit 0 darfst du 'E2E Test bestanden' sagen" entweder entfernt oder explizit auf Orts-Vergleich-Mail-Features eingegrenzt, sodass sie nicht mehr fälschlich für Trip-Briefing-Mails gilt.
  - Test: `# doc-compliance-test` — prüft, dass eine etwaige Exit-0-Pflicht im selben Kontext den Orts-Vergleich-Scope trägt (kein kontextfreies Absolut-Gebot mehr).

## Known Limitations

- Reine Doku-Klarstellung. Die eigentliche Coverage-Lücke (eigener Struktur-Validator für Trip-Briefing-Mails) bleibt offen und ist nach **#733** ausgegliedert.
- Compliance-Test ist ein Dokumentations-Artefakt-Check (`# doc-compliance-test`, laut CLAUDE.md erlaubte Ausnahme von „kein Dateiinhalt-Check") — er prüft die Workflow-Datei selbst, nicht Laufzeitverhalten.

## Changelog

- 2026-06-11: Initial spec created (Nebenbefund aus #722, Folge #733)
