# Kimi-Agent Instructions: gregor_zwanzig

## Projekt

**Gregor Zwanzig** – Wetter-Briefing-Plattform für Bergtouren.

- **Frontend**: SvelteKit unter `frontend/src/`, produktive Oberfläche auf `gregor20.henemm.com`.
- **Go-API**: `api/`, `internal/`, `cmd/`, produktive API auf Port `8090`.
- **Python-Backend**: `src/services/`, `src/app/`, `src/providers/`, FastAPI-Core über `api.main:app`.
- **Ausgabe-/Renderer-Schicht**: `src/output/renderers/` (E-Mail, HTML, Telegram).

## Wichtige Dateien

- `openspec.yaml` – OpenSpec-Framework-Konfiguration (Phasen, Gates, Scope).
- `docs/specs/_template.md` – Template für neue Specs.
- `docs/adr/` – Architektur-Entscheidungs-Records (ADRs).
- `.claude/workflow_state.json` + `.claude/workflows/.active` – aktiver Workflow.
- `.claude/hooks/workflow.py` – CLI zum Workflow-Status lesen/steuern.

## Entwicklungsworkflow (OpenSpec 8-Phasen)

Kimi führt den Workflow **manuell** aus, weil Kimi die Claude-Code-Hooks nicht triggert. Vor jeder Code-Änderung:

```bash
python3 .claude/hooks/workflow.py status
```

Das zeigt die aktuelle Phase. Code-Änderungen sind nur in diesen Phasen erlaubt:

- `phase6_implement`
- `phase6b_adversary`
- `phase7_validate`
- `phase8_complete`
- **Bug-Fix-Fast-Track**: `workflow_type=bug` oder `feature-fast` (max. 5 Dateien, TDD optional).

Ist das Projekt **nicht** in einer Code-Modify-Phase, frag den Nutzer um Erlaubnis bevor du Dateien außerhalb von `docs/`, `tests/` oder `.claude/` editierst.

## Phasen-Zuordnung für Kimi

| Phase | Was Kimi tut |
|-------|--------------|
| `phase0_idle` | Anforderung aufnehmen, vorhandene Specs/ADRs suchen. |
| `phase1_context` | Kontext sammeln (`grep`, README, `docs/context/`). |
| `phase2_analyse` | Analyse, Risiken, Schicht-Zuordnung (Frontend / Go-API / Python-Backend). |
| `phase3_spec` | Spec nach `docs/specs/_template.md` in `docs/specs/modules/` oder `docs/specs/bugfix/` schreiben. |
| `phase4_approved` | Auf Freigabe warten; Freigabe-Keywords: `approved`, `freigabe`, `spec ok`, `lgtm`, `genehmigt`, `abgenommen`, `passt`, `sieht gut aus`. |
| `phase5_tdd_red` | Failing Tests schreiben; Test-Artifact erzeugen. |
| `phase6_implement` | Implementieren; LoC-Delta ≤ 250 beachten. |
| `phase6b_adversary` | Gegenprüfung, Edge-Cases, Test-Verstärkung. |
| `phase7_validate` | Tests laufen lassen, Validierung, Artifacts aktualisieren. |
| `phase8_complete` | Log schreiben, abschließen. |

## Spec-Format

Specs verwenden `docs/specs/_template.md` und müssen enthalten:

- `entity_id`, `type`, `status`, `version`, `tags`
- `## Affected Files` mit korrekter Schicht-Zuordnung
- `## Estimated Scope` (LoC, Files, Effort)
- `## Acceptance Criteria` im Given/When/Then-Format mit konkretem Nutzerverhalten
- `## Architektur-Entscheidung (ADR)`

## TDD-Enforcement

- Red-Green-Refactor: erst failing Test, dann Implementierung.
- Pro Iteration mindestens ein Test-Artifact (Screenshot, API-Response, Log, Test-Output, etc.).
- Artifact-Dateien müssen > 0 Bytes sein.
- Frontend-Änderungen brauchen Screenshots oder UI-Test-Output.

## Scope Guard

- Max. `max_loc_delta: 250` Zeilen Änderung pro Iteration.
- Ausgenommen: Lockfiles (`uv.lock`, `package-lock.json`, …), `_archive/`, `_log/`, `.claude/workflows/`.
- Bei Überschreitung: Scope reduzieren oder neuen Spec/ADR anlegen.

## ADR Guard (Architektur-Entscheidungen)

Folgende Änderungen erfordern einen ADR unter `docs/adr/NNNN-*.md` ODER den Marker `[no-adr]` in der Commit-Message:

- `src/outputs/`
- `src/output/renderers/`
- `docs/reference/decision_matrix.md`
- `src/providers/`
- `src/.*metric.*`
- Neue/veränderte Guard-Hooks unter `.claude/hooks/*_(gate|guard).py`

Wenn du an einer dieser Stellen arbeitest, prüfe zuerst, ob bereits ein passender ADR existiert.

## Commit-Regeln

- Klare, präfixfreie Commit-Messages mit Issue-/Spec-Referenz.
- `[no-adr]` erlaubt bei bewusster Verzicht auf ADR.
- Keine Secrets in Commits (`.env`, `credentials.json`, `*.pem`, `*.key`).

## Tests ausführen

Python:

```bash
uv run pytest tests/<pfad>
```

Frontend:

```bash
cd frontend && npm run test
```

E2E (Playwright):

```bash
cd frontend && npx playwright test
```

Golden-Tests:

```bash
# falls vorhanden
uv run pytest tests/golden
```

## Schicht-Zuordnung vor Code-Änderung

Im Zweifel `grep` auf das betroffene Symbol ausführen:

- **Frontend / User-UI** → `frontend/src/...` (SvelteKit)
- **Go-API** → `api/`, `internal/`, `cmd/`
- **Python-Backend** → `src/services/`, `src/app/`, `src/providers/`

Server-Code (Go vs. Python) und UI-Code (SvelteKit vs. Server-Templates) sind getrennt.

## Wichtige Hinweise

- `.claude/hooks/`, `.claude/commands/`, `.claude/agents/` und `.claude/settings.json` werden von Claude Code / dem OpenSpec-Plugin verwaltet. **Nicht ohne Rücksprache ändern.**
- Diese `AGENTS.md` gilt für Kimi. Sie beschreibt denselben Workflow, den Claude Code über das OpenSpec-Plugin durchsetzt.
