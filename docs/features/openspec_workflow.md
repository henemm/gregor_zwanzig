# OpenSpec-Workflow (Ist-Stand)

> Stand: 2026-07-21 (Doku-Audit #1341). Ersetzt die 8-Phasen-Fassung mit
> einstelligen Commands und `workflow_state.json` (Git-Historie). Maßgeblich
> sind die installierten Plugin-Skills und die Hooks — dieses Dokument ist nur
> der Wegweiser.

## Phasen und Commands

Die Commands sind zweistellig; Deploy ist eine **eigene** Phase:

| Command | Phase | PO-Eingriff |
|---|---|---|
| `/00-intake`, `/00-bug`, `/01-feature` | Einstieg/Klassifikation | — |
| `/10-context` | Kontext sammeln | — |
| `/20-analyse` | Request verstehen, Codebase recherchieren | optional |
| `/30-write-spec` | Spezifikation mit AC-N-Format | **Pflicht: ACs freigeben („go")** |
| `/40-tdd-red` | Fehlschlagende Tests (RED) | optional |
| `/50-implement` | Implementieren (GREEN) + Adversary | — |
| `/60-validate` | Validieren vor Commit | — |
| `/70-deploy` | Staging-Verifikation + Prod-Deploy | **Pflicht: Tech-Lead-Brief + „go"** |
| `/80-workflow`, `/82-test`, `/90-retro`, `/99-reset` | Verwaltung/Hilfsphasen | — |

## State & Enforcement

- **State pro Workflow:** `.claude/workflows/<name>.json` (laufend) bzw.
  `_archive/` (abgeschlossen). Aktiver Workflow AUSSCHLIESSLICH über die
  Umgebungsvariable `GZ_ACTIVE_WORKFLOW` (Symlink-Fallback deaktiviert).
- **Hooks erzwingen den Ablauf** (Auswahl): `workflow_gate` (Phasen-Sequenz,
  AC-N-Pflicht), `qa_gate`/Adversary-Verdict-Gating, `renderer_mail_gate`
  (#811), `e2e_commit_gate`, `nebenbefund_gate`, `test_naming_gate`.
  Gate-/Hook-Bugs gehören ins Plugin-Repo (agent-os-openspec).
- Die verbindliche Kurzreferenz der Regeln (LoC-Limit, Execution-Log,
  Token-Tracking, Trigger-Typen) steht in **CLAUDE.md → „Workflow-Tools v3"**.

## Adversary Verification

Nach der Implementierung führt ein unabhängiger `implementation-validator`
(Sonnet) einen strukturierten Dialog, um die Implementierung aktiv zu brechen —
ohne Zugriff auf das Reasoning des Implementierers. Tri-State-Verdict:
`VERIFIED` / `BROKEN` / `AMBIGUOUS` (AMBIGUOUS → `override-ambiguous` mit
Begründung, BROKEN → Fix-Loop). Findings brauchen `Code reference: file:line`.
Bei UI-Änderungen ergänzt der `fresh-eyes-inspector` (Screenshots OHNE
Bug-Kontext, gegen Confirmation Bias).

## Rollen

Main Context (Opus) ist reiner Orchestrierer und schreibt keinen Code;
Implementierung macht der `developer`-Agent. Agentenliste mit Modellen:
CLAUDE.md → „Agenten-Rollen und Modelle"; Definitionen: `.claude/agents/*.md`.
