---
entity_id: entity_name
type: module
created: 2025-12-27
updated: 2025-12-27
status: draft
version: "1.0"
tags: []
---

# Entity Name

## Approval

- [ ] Approved

## Purpose

[1-2 sentences: What does this entity do? Why does it exist?]

## Source

- **File:** `path/to/file`
- **Identifier:** `class/function name`

> **PFLICHT — Schicht-Hinweis:** Affected Files MUSS die richtige Schicht treffen:
> - **Frontend / User-UI** → `frontend/src/...` (SvelteKit, produktive Oberfläche auf gregor20.henemm.com)
> - **Go-API** → `api/`, `internal/`, `cmd/` (Production-API auf Port 8090)
> - **Python-Backend** → `src/services/`, `src/app/`, `src/providers/` (FastAPI Core über `api.main:app`)
>
> Im Zweifel vor dem Spec-Schreiben grep auf den betroffenen Symbol-Namen — Server-Code (Go vs. Python) und UI-Code (SvelteKit vs. Server-Templates) sind getrennt. Es gab in der Vergangenheit Doppelarbeit, weil Specs Helper-Funktionen in der falschen Schicht verortet haben (Issue #129).

## Estimated Scope

- **LoC:** [Zahl oder Bereich, z.B. ~50]
- **Files:** [Anzahl betroffener Dateien]
- **Effort:** [low | medium | high]

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| | | |

## Implementation Details

```
[Code or logic description]
```

## Expected Behavior

- **Input:** [description]
- **Output:** [description]
- **Side effects:** [if any]

## Acceptance Criteria

- **AC-1:** Given <precondition> / When <action> / Then <observable outcome>
  - Test: [Konkretes Nutzerverhalten das bewiesen wird — kein Dateiinhalt-Check]

- **AC-2:** Given <precondition> / When <action> / Then <observable outcome>
  - Test: [Konkretes Nutzerverhalten das bewiesen wird — kein Dateiinhalt-Check]

## Known Limitations

- [Any limitations or edge cases]

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** [ADR-NNNN oder "keine"]
- **Rationale:** [kurz: warum diese Entscheidung bzw. warum keine noetig ist]

## Changelog

- 2025-12-27: Initial spec created
