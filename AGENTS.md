# Kimi-Agent Instructions: gregor_zwanzig

## Projekt

**Gregor Zwanzig** – Wetter-Briefing-Plattform für Bergtouren.

- **Frontend**: SvelteKit unter `frontend/src/`, produktive Oberfläche auf `gregor20.henemm.com`.
- **Go-API**: `cmd/server/`, `internal/`, produktive API auf Port `8090`.
- **Python-Core / Domain-Backend**: `api/`, `src/services/`, `src/app/`, `src/providers/`, FastAPI-Core über `api.main:app` (interner Port `8000`).
- **Ausgabe-/Renderer-Schicht**: `src/output/renderers/` (E-Mail, HTML, Telegram).

## Arbeitsverzeichnis — NIE im Haupt-Repo schreiben

**Alle Code-Änderungen gehören in eine isolierte Worktree-Kopie unter
`/home/hem/gz-workspaces/<name>`, NIEMALS direkt in den Haupt-Checkout
`/home/hem/gregor_zwanzig`.** Uncommittete Änderungen im Haupt-Repo werden von Deploys
(`reset --hard origin/main`) ersatzlos gelöscht (Vorfall 2026-07-07: ein ganzes Arbeitspaket
ging so verloren). Schreib-/Edit-Zugriff auf den Haupt-Checkout ist zusätzlich per
Permission-Regel hart gesperrt — dort kommt „denied by permission rule".

Vorgehen zu Beginn jeder Aufgabe:

```bash
cd /home/hem/gregor_zwanzig && bash .claude/tools/gz-workspace new <name>
cd /home/hem/gz-workspaces/<name> && pwd && git branch --show-current   # muss gz-workspaces zeigen
```

Nach **jedem** Issue sofort committen (ein Commit pro Issue) — ein Commit überlebt jeden Deploy.

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

- `src/output/`
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
- **Go-API** → `cmd/server/`, `internal/` (Production-API auf Port 8090)
- **Python-Core / Domain-Backend** → `api/`, `src/services/`, `src/app/`, `src/providers/` (FastAPI Core über `api.main:app`)

Server-Code (Go vs. Python) und UI-Code (SvelteKit vs. Server-Templates) sind getrennt.

## Deployment

### Environments

| Environment | Pfad auf Host | URL |
|-------------|---------------|-----|
| **Production** | `/home/hem/gregor_zwanzig` | `https://gregor20.henemm.com` |
| **Staging** | `/home/hem/gregor_zwanzig_staging` | `https://staging.gregor20.henemm.com` |

### Automatischer Deploy (CI)

Bei Push auf `main` läuft `.github/workflows/ci.yml`:

1. **Test + Lint** (`uv run pytest`, `uv run ruff check`)
2. **Staging-Wait**: CI wartet max. 6 Minuten, bis Staging denselben Commit ausliefert.
3. **Staging Smoke-Test**: `GET /` (200/302) und `GET /api/health` (200).
4. **Staging-Verdict**: `staging_gate.py --write-verdict 'VERIFIED: CI smoke test ...'`
5. **Production-Deploy**: `ssh ... bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh`
6. **Telegram-Benachrichtigung** bei Erfolg oder Fehlschlag.

### Staging-Auto-Deploy (Cron)

Alle 5 Minuten läuft auf dem Host:

```bash
/home/hem/henemm-infra/scripts/auto-deploy-gregor-staging.sh
```

Das Script macht in `/home/hem/gregor_zwanzig_staging`:

1. `git fetch origin` + Diff-Check
2. `git pull origin main`
3. `go build -o gregor-api ./cmd/server`
4. `cd frontend && npm install && npm run build`
5. `sudo systemctl restart gregor-python-staging`
6. `sudo systemctl restart gregor-api-staging`
7. `sudo systemctl restart gregor-frontend-staging`
8. Smoke-Test gegen `https://staging.gregor20.henemm.com/`
9. Heartbeat ping bei Erfolg

### Manueller Production-Deploy

Nur wenn CI nicht greift oder für Notfälle:

```bash
# Auf dem Production-Host (/home/hem/gregor_zwanzig)
bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh
```

Das Script baut das Go-Binary und das Frontend neu und startet die Production-Services:

- `gregor-python`
- `gregor-api`
- `gregor-frontend`

### Lokale Entwicklung

Python-Backend:

```bash
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend && npm run dev
```

Go-API:

```bash
go build -o gregor-api ./cmd/server
./gregor-api
```

### Post-Deploy-Checks

- `https://gregor20.henemm.com/` → HTTP 200/302
- `https://gregor20.henemm.com/api/health` → HTTP 200 (enthält Commit-Hash)
- `systemctl status gregor-api gregor-python gregor-frontend`
- Logs prüfen: `journalctl -u gregor-api -f`

## Wichtige Hinweise

- `.claude/hooks/`, `.claude/commands/`, `.claude/agents/` und `.claude/settings.json` werden von Claude Code / dem OpenSpec-Plugin verwaltet. **Nicht ohne Rücksprache ändern.**
- Diese `AGENTS.md` gilt für Kimi. Sie beschreibt denselben Workflow, den Claude Code über das OpenSpec-Plugin durchsetzt.
