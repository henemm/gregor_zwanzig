# Commands Reference

Wegweiser, kein eigener Befehl. Maßgeblich für Ablauf und Freigabepunkte ist `CLAUDE.md`
→ „Workflow"; Ist-Stand der Phasen: `docs/features/openspec_workflow.md`.

## Herkunft der Befehle

| Quelle | Befehle |
|---|---|
| Plugin **agent-os-openspec** (hier nur als generierte Kurzbefehle, siehe unten) | `/00-intake`, `/00-bug`, `/01-feature`, `/10-context`, `/20-analyse`, `/30-write-spec`, `/40-tdd-red`, `/50-implement`, `/60-validate`, Verwaltung `/80-workflow`, `/82-test`, `/90-retro`, `/99-reset` |
| Dieser Ordner (projekteigen) | `/70-deploy` (ersetzt das generische Plugin-Template), `/e2e-verify`, `/next-ticket`, `/radar` |

**Kurzbefehle:** `/00-intake` statt `/agent-os-openspec:00-intake` usw. Dateien mit Marker
`openspec-alias` sind generiert, nie von Hand ändern. Auffrischen nach Plugin-Update:
`python3 <plugin>/setup.py . --refresh-aliases`. Nie global in `~/.claude/commands` anlegen: das
überdeckt das projekteigene `/70-deploy` (#1511).

Hooks und `workflow.py` liefert ebenfalls das Plugin (`/home/hem/agent-os-openspec/core/hooks/`);
`.claude/hooks/` enthält nur projekteigene Gates und Validatoren.

## Phasen in Kurzform

`/10-context` → `/20-analyse` → `/30-write-spec` (**einzige Freigabe: ACs auf Deutsch, per
`AskUserQuestion`**) → `/40-tdd-red` → `/50-implement` (+ Adversary) → `/60-validate` →
`/70-deploy` (PR mergen → `/e2e-verify` → Prod-Deploy → Selftest → Issue-Close, **ohne
Freigabe-Halt**).

## Agenten

Definitionen in `.claude/agents/*.md`; Modellzuordnung siehe `docs/reference/workflow_und_agenten.md` → „Agenten-Modelle".

## Workflow-State

Pro Workflow `.claude/workflows/<name>.json` (laufend) bzw. `_archive/` (abgeschlossen).
Aktiver Workflow ausschließlich über `export GZ_ACTIVE_WORKFLOW=<name>`.

## Neuen Befehl anlegen

`.claude/commands/<name>.md` anlegen — wird automatisch als `/<name>` registriert. Danach
diese Tabelle oben ergänzen.
