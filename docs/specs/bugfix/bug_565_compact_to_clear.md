---
entity_id: bug_565_compact_to_clear
type: bugfix
created: 2026-06-03
updated: 2026-06-03
status: complete
version: "1.0"
tags: [workflow, infra, context-management]
---

# Bug #565: Workflow Kontext-Reset — /compact durch /clear ersetzen

## Approval

- [x] Approved

## Purpose

Ersetzt den fehlplatzierten `/compact`-Aufruf in Phase 6 durch `/clear` und führt denselben Reset-Mechanismus am Anfang von Phase 7 und Phase 8 ein. `/compact` fasst die Kontext-History zusammen und hinterlässt Residual-Tokens; `/clear` löscht sie vollständig. Da alle relevanten Informationen (Spec, Workflow-Status, Test-Artefakte) in Dateien liegen, kann Claude nach einem `/clear` den vollständigen Arbeitskontext durch gezieltes Lesen dieser Dateien wiederherstellen — ohne akkumulierten Gesprächs-Overhead.

## Source

- **Files:**
  - `.claude/commands/5-implement.md` (Z. 24–32 — bestehender `/compact`-Aufruf)
  - `.claude/commands/6-validate.md` (Anfang — fehlender Reset vor 4 parallelen Validation-Agents)
  - `.claude/commands/7-deploy.md` (Anfang — fehlender Reset vor E2E)

## Estimated Scope

- **LoC:** ~30
- **Files:** 3
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `workflow.py status` | CLI-Tool | Liefert nach `/clear` den aktuellen Workflow-Status (Spec-Pfad, Phase, Workflow-Name) |
| Spec-Datei (Pfad aus Workflow-Status) | Artefakt | Wird nach `/clear` explizit neu eingelesen, um Acceptance Criteria wiederherzustellen |

## Implementation Details

In allen drei Command-Files wird am Beginn der Phase ein Reset-Block eingefügt. Der Block besteht aus zwei Teilen:

1. `/clear` — löscht die Kontext-History vollständig
2. Pflicht-Re-Read — Claude liest unmittelbar danach `workflow.py status` aus und öffnet die Spec-Datei, die im Status genannt wird

**5-implement.md:** Der bestehende `/compact`-Aufruf wird durch diesen Reset-Block ersetzt. Der Block steht vor dem Developer-Agent-Spawn.

**6-validate.md:** Der Reset-Block wird an den Anfang der Datei gesetzt, vor dem Start der 4 parallelen Validation-Agents. Zusätzlich zum Workflow-Status wird die Spec-Datei für die AC-Liste eingelesen.

**7-deploy.md:** Der Reset-Block wird an den Anfang der Datei gesetzt, vor dem E2E-Verifikationsschritt.

## Expected Behavior

- **Input:** Claude startet Phase 6, 7 oder 8 über das jeweilige `/`-Command
- **Output:** Kontext-History ist vollständig geleert; Claude liest Workflow-Status und Spec-Datei neu ein, bevor die eigentliche Phasen-Arbeit beginnt
- **Side effects:** Keine — Workflow-Logik, Agent-Spawning und Phasen-Übergänge bleiben unverändert

## Acceptance Criteria

**AC-1:** Given `.claude/commands/5-implement.md` enthält einen `/compact`-Aufruf / When die Datei gelesen wird / Then kommt `/compact` nicht mehr vor und stattdessen ist `/clear` gefolgt von einem expliziten Re-Read-Block (Workflow-Status + Spec-Datei) vorhanden.

**AC-2:** Given `.claude/commands/6-validate.md` startet Phase 7 ohne Kontext-Reset / When die Datei gelesen wird / Then steht am Anfang `/clear` gefolgt von einem expliziten Re-Read-Block (Workflow-Status + Spec-Pfad), vor dem Start der parallelen Validation-Agents.

**AC-3:** Given `.claude/commands/7-deploy.md` startet Phase 8 ohne Kontext-Reset / When die Datei gelesen wird / Then steht am Anfang `/clear` gefolgt von einem expliziten Re-Read-Block (Workflow-Status), vor dem E2E-Verifikationsschritt.

**AC-4:** Given alle drei Command-Files nach der Änderung / When ein automatisierter Test jede Datei auf `/compact` prüft und auf das Vorhandensein von `/clear` plus Re-Read-Block / Then enthält keine der drei Dateien `/compact` und jede enthält mindestens einen `/clear`-Aufruf sowie einen nachfolgenden `workflow.py status`-Aufruf.

## Known Limitations

- Der Re-Read-Block ist eine Anweisung an Claude (Markdown-Instruction), keine maschinenausführbare Garantie. Ein Hook, der `/compact` blockiert, existiert nicht und ist nicht Teil dieses Fixes.

## Changelog

- 2026-06-03: Initial spec created (Issue #565)
- 2026-06-03: Implementation complete — all 3 command files updated, tests pass, docs-updater agent ran
