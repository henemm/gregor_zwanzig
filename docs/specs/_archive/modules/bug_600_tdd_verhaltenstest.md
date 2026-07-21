---
entity_id: bug_600_tdd_verhaltenstest
type: module
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [workflow, tdd, testing]
---

# Bug #600: TDD-Tests müssen Verhalten beweisen, nicht Dateiinhalt prüfen

## Approval

- [ ] Approved

## Purpose

Ergänzt drei Workflow-Dokumente um ein explizites Verbot von Dateiinhalt-Checks als TDD-Nachweis. Ein Test der prüft ob ein String im Quellcode vorkommt (`assert 'xyz' in file.read_text()`) ist kein Beweis dafür dass das Feature korrekt funktioniert — er ist Code-Analyse, kein Verhaltenstest.

## Source

- **Files:** `CLAUDE.md`, `.claude/commands/4-tdd-red.md`, `docs/specs/_template.md`

## Estimated Scope

- **LoC:** ~25
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Bug #590 | Referenz | Konkreter Auslöser: 3 Iterationen alle mit Dateiinhalt-Checks |

## Implementation Details

### CLAUDE.md — Abschnitt „KEINE MOCKED TESTS"

Nach der Zeile `**NIEMALS \`Mock()\`, \`patch()\`, oder \`MagicMock\` fuer E-Mail/API Tests verwenden!**` ergänzen:

```
**Dateiinhalt-Checks sind ebenfalls VERBOTEN:**
`assert 'xyz' in file.read_text()` — das ist Code-Analyse, kein Verhaltensnachweis.
TDD-Tests MÜSSEN das tatsächliche Verhalten beweisen:
- Frontend-Bug: Playwright-E2E gegen Staging als eingeloggter Nutzer
- Backend-Bug: echter HTTP-Call, echter DB-Zustand prüfen
- Mindestens ein Test muss den Bug aus Nutzerperspektive reproduzieren (rot vor Fix, grün nach Fix)
```

### `.claude/commands/4-tdd-red.md` — nach „MUST BE RED"

Nach `**Expected:** Tests FAIL with clear error messages.` ergänzen:

```
**Verhaltenstest-Pflicht:** Mindestens ein Test muss den Fehler aus Nutzerperspektive beweisen.
- Frontend-Bug: Playwright-E2E gegen Staging
- Backend-Bug: echter HTTP-Call
- VERBOTEN: `assert 'xyz' in file.read_text()` (Code-Analyse ≠ Verhaltensnachweis)
```

### `docs/specs/_template.md` — Acceptance Criteria

Im AC-Block nach `Then <observable outcome>` die Test-Zeile ergänzen:

```
  - Test: [Konkretes Nutzerverhalten das bewiesen wird — kein Dateiinhalt-Check]
```

## Acceptance Criteria

**AC-1:** Given der Abschnitt „KEINE MOCKED TESTS" in CLAUDE.md / When ein Entwickler-Agent die Regeln liest / Then sieht er ein explizites Verbot von `file.read_text()`-Checks mit Begründung und konkreten Alternativen (Playwright, HTTP-Call).
  - Test: CLAUDE.md enthält `file.read_text()` und `Verhaltensnachweis` und `Playwright` nach dem Mock-Verbot-Block.

**AC-2:** Given der `/4-tdd-red` Skill / When der Agent Phase 5 durchläuft / Then wird direkt nach dem „MUST BE RED"-Block auf die Verhaltenstest-Pflicht hingewiesen, inkl. Verbot von Dateiinhalt-Checks.
  - Test: `.claude/commands/4-tdd-red.md` enthält `Verhaltenstest-Pflicht` und `file.read_text()` nach dem Expected-Block.

**AC-3:** Given das Spec-Template `docs/specs/_template.md` / When ein Spec-Writer ein AC formuliert / Then sieht er in der Test-Zeile den expliziten Hinweis, dass Dateiinhalt-Checks kein gültiger Nachweis sind.
  - Test: `_template.md` enthält `kein Dateiinhalt-Check` in der Test-Zeile der ACs.

## Known Limitations

- Diese Änderungen gelten für neue Workflows — laufende Workflows mit bereits geschriebenen Dateiinhalt-Tests werden nicht rückwirkend invalidiert.

## Changelog

- 2026-06-04: Spec erstellt basierend auf Issue #600
