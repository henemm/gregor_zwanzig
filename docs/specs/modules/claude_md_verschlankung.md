---
entity_id: claude_md_verschlankung
type: module
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
workflow: docs-2640-claude-md-verschlanken
tags: [doku, token-budget, claude-md]
---

# CLAUDE.md verschlanken (#2640)

## Approval

- [ ] Approved

## Purpose

Die Projekt-`CLAUDE.md` (273 Zeilen, 27,5 KB) wird bei jeder Modell-Anfrage jeder Sitzung mitgeladen und gehört damit zu den größten Kostenposten (67 % des Verbrauchs sind Wieder-Einlesen von Kontext). Sie soll nur noch dauerhafte Entscheidungen und je einen Verweis auf die Detailmechanik enthalten; die Detailmechanik wandert vollständig nach `docs/reference/`, nichts geht verloren.

## Source

- **File:** `CLAUDE.md` (Ziel: unter 120 Zeilen, unter 12 KB)
- **Identifier:** alle Abschnitte laut Zuordnungstabelle unter „Implementation Details"
- **Neu:** `docs/reference/workflow_und_agenten.md`, `tests/test_claude_md_budget.py`
- **Ergänzt:** `docs/reference/operations_playbook.md`, `docs/reference/gates_und_ratschen.md`, `docs/reference/design_system.md`, `docs/README.md`
- Reine Doku-Änderung: kein Code in `src/`, `api/`, `internal/`, `frontend/`, `cmd/`. Lieferweg: PR mit grüner Ampel, kein Staging-/Prod-Deploy (Doku-Ausnahme). Trip/Ortsvergleich-, Mandanten- und Kanal-Prüfpunkte entfallen (kein Produktverhalten betroffen).

## Estimated Scope

- **LoC:** ~60 Test; ~350 Zeilen Doku (zählen nicht gegen das Limit)
- **Files:** 8 (1 gekürzt, 2 neu, 4 ergänzt, 1 Spec)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/test_issue_732_email_validator_scope_docs.py` | Test | verlangt Abschnitt „Mail-Validatoren & Renderer-Gate" mit Orts-Vergleich, Vergleichstabelle, Trip-Briefing, `briefing_mail_validator` |
| `tests/tdd/test_compare_validator_mail_selection.py` | Test | zählt genau 3 Aufrufe von `email_spec_validator.py` über `CLAUDE.md`, `e2e-verify.md`, `email_formatting.md` |
| `tests/tdd/test_compare_premium_sms_versand.py` | Test | Zeile „Premium-SMS-Reichweite" nennt „Ortsvergleich-Briefing" |
| `tests/tdd/test_issue_339_verify_timing.py` | Test | „staging" kommt vor, die Server-Neustart-Sätze nicht |
| `test_naming_gate.py`, `pendant_gate.py`, `file_claim_gate.py` | Hooks | Meldungstexte nennen die Abschnitte „Test-Politik", „Trip/Ortsvergleich-Code-Teilung", „Parallele Sessions" |

## Implementation Details

Reihenfolge: **erst auslagern, dann kürzen.** Jede Regel steht wörtlich am neuen Ort, bevor sie aus `CLAUDE.md` verschwindet.

### Zuordnung (Quelle → Ziel)

| Block in `CLAUDE.md` | Ziel nach der Änderung |
|---|---|
| Projekt-Überblick, vier Kanäle, Premium-SMS-Reichweite, Multi-User | bleibt (je 1–3 Sätze, PO-Vorgaben wörtlich) |
| Architektur-Diagramm | bleibt, ohne Fließtext-Dopplung |
| Referenz-Tabelle, ADR-/Spec-Hinweis | bleibt, gekürzt |
| Workflow-Befehlstabelle, Agenten-Modelle, Herkunft der Befehle, PO-Pattern, Adversary-Details | `docs/reference/workflow_und_agenten.md` (NEU); in `CLAUDE.md` Kern: Spec-Freigabe, `AskUserQuestion`, Deploy ohne Halt, Mutations-Pflicht |
| Workflow-State-Tabelle (korrigiert: `OPENSPEC_ACTIVE_WORKFLOW` gilt; `GZ_ACTIVE_WORKFLOW` nur noch Fallback dreier Hooks) | `workflow_und_agenten.md` |
| Test-Politik, Tabelle „Zwei Schichten" | Tabelle → `gates_und_ratschen.md`; in `CLAUDE.md` Verbot Mock-Theater + „kein `uv run pytest` ohne Dateien" |
| E2E-Verifikation, Liefer-Workflow-Tabelle | `operations_playbook.md` „Liefer-Workflow"; in `CLAUDE.md` Kernsätze |
| CI-Ampel (6 Checks) und Merge-Regel | `operations_playbook.md` „Liefer-Workflow" (Playbook sagt bisher „5 Checks" → korrigieren); Rollen: PR, Merge, Deploy liegen bei Claude (überstimmt bewusst die Vorlage von `/60-validate`) |
| Mail-Validatoren (Tabelle) | `mail_validators.md` (existiert); in `CLAUDE.md` Abschnitt `## Mail-Validatoren & Renderer-Gate` als Kurztext mit genau einer `email_spec_validator.py`-Zeile |
| Design-Leitprinzipien | `design_system.md` (Prinzip NEU, wörtlich); in `CLAUDE.md` ein Satz |
| Trip/Ortsvergleich-Code-Teilung | bleibt (Dauerentscheidung), gekürzt |
| Confidence-Verbot | bleibt (2 Sätze) |
| Daten-Schema-Reworks | bleibt als Regelsatz (Read-Modify-Write, nie Replace); Details im Playbook |
| Backlog & Nebenbefunde, Regel-Budget | Triage → `workflow_und_agenten.md`; Regel-Budget bleibt als 1 Satz |
| Betrieb (URLs, Monitoring, Pre-Test-Validierung, Session-Artefakte) | URLs bleiben; Rest → `operations_playbook.md` |
| Parallele Sessions, Token-Budget | Playbook „Parallele Sessions" (existiert) + Token-Budget-Regeln NEU dort; in `CLAUDE.md` 2 Sätze, Überschrift „Parallele Sessions" bleibt |
| Messaging (MQ-Verbot `gregor` → `gregor`) | Details → `workflow_und_agenten.md`; Verbot bleibt als 1 Satz |
| Compact instructions | bleibt, gekürzt |

## Expected Behavior

- **Input:** `CLAUDE.md` Ist-Stand (273 Zeilen).
- **Output:** `CLAUDE.md` unter 120 Zeilen/12 KB; jeder entfernte Regelblock existiert an dem in der Tabelle genannten Ort; jeder Verweis in `CLAUDE.md` zeigt auf eine vorhandene Datei.
- **Side effects:** Hook-Meldungen und die vier lesenden Tests bleiben gültig; ein neuer Wächter hält die Datei klein.

## Acceptance Criteria

- **AC-1:** Given die gekürzte `CLAUDE.md` / When ihre Größe gemessen wird / Then hat sie höchstens 120 Zeilen und höchstens 12 288 Byte.
  - Test: `tests/test_claude_md_budget.py` misst die Datei und scheitert bei Überschreitung (Ratsche gegen erneutes Anwachsen); als `# doc-compliance-test` markiert.

- **AC-2:** Given ein Verweis auf eine Datei unter `docs/` oder `.claude/` in `CLAUDE.md` / When der Pfad aufgelöst wird / Then existiert die Datei.
  - Test: derselbe Wächter prüft alle in Backticks genannten Pfade auf Existenz.

- **AC-3:** Given jeder in der Zuordnungstabelle als „NEU" oder „ergänzt" gekennzeichnete Regelblock / When die Zieldatei gelesen wird / Then steht die Regel dort vollständig und nicht nur als Verweis (Workflow-State, Zwei-Schichten-Test-Politik, Merge-Regel mit 6 Checks, Design-Kontrast-Prinzip, Nebenbefund-Triage, MQ-Regel, Token-Budget-Regeln).
  - Test: der Wächter prüft je Block ein Kernmerkmal in der Zieldatei (z. B. „Mock-Theater", „Kern (deterministisch)", „`#1199`", „`/clear`"); als `# doc-compliance-test` markiert.

- **AC-4:** Given die vier lesenden Tests und die drei Hook-Meldungen / When sie nach der Kürzung laufen / Then sind sie grün bzw. nennen Abschnitte, die es weiter gibt („Test-Politik", „Trip/Ortsvergleich-Code-Teilung", „Parallele Sessions", „Mail-Validatoren & Renderer-Gate").
  - Test: die vier Test-Dateien aus „Dependencies" laufen grün; der Wächter prüft die vier Überschriften.

- **AC-5:** Given die PO-Vorgaben „alle vier Kanäle gleichrangig", Premium-SMS-Reichweite, Multi-User-Isolation, Trip/Ortsvergleich-Teilung, Confidence-Verbot, Read-Modify-Write / When `CLAUDE.md` gelesen wird / Then steht jede in `CLAUDE.md` selbst (nicht nur als Verweis).
  - Test: der Wächter sucht je ein Schlüsselwort (`gleichrangig`, `Premium-SMS-Reichweite`, `user_id`, `context="route"|"vergleich"`, `confidence_pct`, `Read-Modify-Write`).

- **AC-6:** Given der Liefer-Workflow / When Playbook und `CLAUDE.md` gelesen werden / Then steht in beiden: PR, Merge und Deploy liegen bei Claude, die Ampel hat 6 Checks, und die Vorlage von `/60-validate` („Merge, PR bleiben beim PO") ist bewusst überstimmt.
  - Test: der Wächter prüft „6 Checks"/„sechs" und die Rollenaussage im Playbook.

- **AC-7:** Given die Zuordnungstabelle dieser Spec / When ein Block entfernt wird, der keinen Zielort hat / Then ist die Änderung unzulässig (nichts löschen ohne Gegenstück).
  - Test: Adversary-Prüfung Zeile für Zeile gegen `git show HEAD:CLAUDE.md`; jede Zeile des Altbestands ist in `CLAUDE.md` oder in einer Zieldatei auffindbar.

## Known Limitations

- Die Plugin-Vorlage von `/60-validate` liegt außerhalb des Repos und bleibt unverändert; sie wird nur in der Projekt-Doku überstimmt.
- Hooks, die noch `GZ_ACTIVE_WORKFLOW` lesen, bleiben unangetastet (eigenes Thema).
- Falls 12 KB die wörtlichen PO-Vorgaben nicht tragen, schlägt die Umsetzung 14 KB mit Begründung vor; das entscheidet der PO, nicht die Umsetzung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Dokumentenorganisation, keine Entscheidungsfläche aus `docs/adr/`.
- **Regel-Budget:** Der neue Wächter ersetzt die bisher ungeprüfte Prosa-Vorgabe „CLAUDE.md nur Entscheidungen"; Prüfdatum 2027-01-28.

## Changelog

- 2026-10-30: Erstfassung (#2640)
