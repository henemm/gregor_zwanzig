# Spec: bug-567 — Stale /7-deploy & "approved" Referenzen

- **Status:** Draft
- **Created:** 2026-06-05
- **Issue:** #567
- **Typ:** Doku-Bereinigung (Follow-up F002 aus #563)

## Problem

In `.claude/commands/README.md` und `.claude/commands/5-implement.md` stehen noch veraltete Verweise auf den entfernten Befehl `/7-deploy` und das alte Spec-Approval-Keyword `"approved"`. Beides wurde in #563 (commit-stand `main`) durch `/6-validate` Step 5 bzw. `"go"` ersetzt. Wer die Doku liest, tippt einen nicht existierenden Befehl oder ein vom Gate ignoriertes Keyword.

## Scope

Reine Textkorrekturen in zwei Dateien. Keine Code-Änderung, keine Verhaltensänderung.

## Acceptance Criteria

**AC-1:** Given die Phasen-Tabelle in `.claude/commands/README.md` Zeile 22, When der Leser sie sieht, Then steht in Phase 8 kein `/7-deploy` mehr (durch `—` ersetzt, da Deploy inline in `/6-validate` Step 5 erfolgt).

**AC-2:** Given die Phasen-Tabelle in `.claude/commands/README.md` Zeile 17, When der Leser sie sieht, Then heißt das Approval-Keyword `"go"` statt `"approved"`.

**AC-3:** Given die Beispiel-Workflows in `.claude/commands/README.md` (Zeilen 67, 91), When der Leser sie kopiert, Then erscheint dort `# User: "go"` statt `# User: "approved"`.

**AC-4:** Given die State-Übersicht in `.claude/commands/README.md` Zeile 192, When der Leser sie liest, Then heißt das Keyword `"go"` statt `"approved"` (der State-Name `phase4_approved` bleibt unverändert).

**AC-5:** Given der Abschluss-Brief-Hinweis in `.claude/commands/5-implement.md` Zeile 237, When der Leser ihn liest, Then verweist er auf `/6-validate` Step 5 statt auf `/7-deploy`.

**AC-6:** Given die fertige Änderung, When `grep -rn "/7-deploy" .claude/commands/` läuft, Then liefert es keine Treffer.

## Out of Scope

- `phase4_approved` (State-Name, kein User-Keyword) — bleibt
- „Read the approved spec" (Bedeutung „freigegebene Spec", kein Keyword) — bleibt
- Andere Doku-Dateien (CLAUDE.md ist bereits in #563 korrigiert)

## Test-Strategie

Doku-Compliance via `grep`-Check (AC-6) reicht — keine Verhaltenstests, da keine Logik-Änderung. Manuelle Sichtprüfung der 2 Dateien.

## Deploy

Doku-Only → Post-Push-Workflow-Ausnahme, kein Prod-Deploy nötig (Drift-Monitor bleibt ruhig).
