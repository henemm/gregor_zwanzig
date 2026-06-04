# Spec: Issue #576 — tokens.css → app.css Sync (Fundament)

## Status
- Phase: Specification
- Issue: #576
- Typ: Rework / Design-Fidelity

## Problem
`--g-paper-deep` in `frontend/src/app.css` hat den Wert `#ede9df`. Die kanonische Quelle
`claude-code-handoff/current/jsx/tokens.css` schreibt `#ecead9` vor. Die Korrektur wurde
in Issue #378 bewusst aufgeschoben (Guard-Kommentar: "nicht im #378-Scope, C1").

## Lösung
Einen Token-Wert in `app.css` korrigieren und den zugehörigen Guard-Test aktualisieren.

## Dateien
- `frontend/src/app.css` (1 Zeile)
- `frontend/src/lib/tokens-bridge.test.ts` (1 Test-Assertion)

## Acceptance Criteria

**AC-1:** Given `frontend/src/app.css` wird nach `:root` gesucht /
When `grep 'g-paper-deep' frontend/src/app.css` ausgeführt wird /
Then enthält der Treffer den Wert `#ecead9` (nicht `#ede9df`).

**AC-2:** Given `tokens-bridge.test.ts` wird ausgeführt /
When `cd frontend && node --experimental-strip-types --test src/lib/tokens-bridge.test.ts` /
Then Exit-Code 0 und alle 16 Tests grün (kein Fail, keine neuen Skips).

**AC-3:** Given der kanonische Wert aus `tokens.css` /
When `grep 'paper-deep' frontend/src/app.css` und `grep 'paper-deep' claude-code-handoff/current/jsx/tokens.css` /
Then beide liefern `#ecead9`.

## Nicht im Scope
- `--g-info` bleibt `#2a6cb3` (intentionelle Divergenz, durch Test bewacht)
- `--g-good`/`--g-warn`/`--g-bad` bleiben nicht in app.css (absichtlich entfernt in #541)
- Font-Stacks und Radien-Aliase bleiben unverändert
