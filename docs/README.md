# Dokumentation — Gregor Zwanzig: Wegweiser

> Stand: 2026-07-21 (Doku-Audit #1340/#1341). Regel: **lieber wenig Korrektes
> als viel Halbwahres** — was aus dem Code ablesbar ist (Inventare, Mappings,
> Exporte), wird nicht in Prosa gedoppelt. Offene Arbeit steht ausschließlich
> in GitHub Issues.

## Referenz (gepflegt — hier zuerst suchen)

| Ort | Inhalt |
|---|---|
| `CLAUDE.md` (Repo-Root) | Arbeitsregeln, Workflow, Deploy, Pflicht-Gates |
| `reference/` | Technische Referenz: `api_contract.md` (DTOs, SSOT — driftgesichert via `tests/test_api_contract_drift.py`), `decision_matrix.md` (Provider-Ist-Stand), `operations_playbook.md` (Deploy/E2E/Rollback), `mail_validators.md`, `navigation.md` (URL-Modell), `frontend_components.md` (Konzepte, kein Inventar), `design_system.md`, `critical_lessons.md` (Regeln ohne anderen Wächter) |
| `adr/` | Architektur-Entscheidungen (nummeriert; Status beachten — einzelne sind superseded) |
| `design-system/` | CHARTER, COMPONENTS, TOKENS, SCREENS |
| `features/` | `architecture.md` (Systemarchitektur), `scope.md` (Vision), `openspec_workflow.md` (Workflow-Wegweiser) + aktive Epic-Dokumente |
| `project/` | `known_issues.md` (Root-Cause-Archiv), `strategic-directions.md`, Architektur-Programm 2026-07 |
| `runbooks/` | Betriebsanleitungen (z. B. `telegram-webhook.md`) |

## Arbeits- und Wegwerf-Material

| Ort | Charakter |
|---|---|
| `specs/modules/` u. a. | Specs: thematische Modul-Specs + Specs OFFENER Issues. Template: `specs/_template.md` |
| `specs/_archive/` | Wegwerf-Specs GESCHLOSSENER Issues (2026-07-21 archiviert; durchsuchbar, nicht maßgeblich) |
| `artifacts/` | Workflow-Artefakte laufender Vorgänge — Ordner abgeschlossener Workflows werden gelöscht (Git-Historie bewahrt sie) |
| `analysis/` | Punktuelle Analysen (datiert, nicht gepflegt) |
| `design-requests/`, `claude-design-queue/`, `design/` | Design-Austausch-Artefakte (Momentaufnahmen) |

## Gelöscht (2026-07-21, in Git-Historie abrufbar)

`context/` (Sitzungsnotizen pro Issue), `project/backlog/` (Alt-Planung —
Planung lebt in GitHub Issues), `bugs/`, alte `artifacts/`-Ordner,
`reference/provider_mapping.md` (MET/MOSMIX-Ära), `features/cli_spec.md`,
`features/epic-438-compare-wizard.md`, `features/epic-677-compare-editor.md`
(Wizard-Ära), `project/migration-plan-go-sveltekit.md` (Migration
abgeschlossen). Tote Links auf diese Pfade in alten Specs/Changelogs sind
Historie — im Zweifel `git log --all -- <pfad>`.
