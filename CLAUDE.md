# CLAUDE.md - Gregor Zwanzig

## Projekt-Ueberblick

**Gregor Zwanzig** ist ein Headless-Service zur Normalisierung von Wetterdaten und Ausgabe als kompakte Reports (SMS <=160 Zeichen, E-Mail mit Tabellen).

- **Zielgruppe:** Weitwanderer (z.B. GR20), eingeschraenkte Konnektivitaet
- **Stack:** Python, uv, pytest
- **Channels:** E-Mail (MVP), spaeter SMS/Push, Signal (verfügbar via Callmebot)

## Workflow

Dieses Projekt nutzt den **OpenSpec 8-Phasen-Workflow** mit Adversary Verification:

| Phase | Command | Purpose |
|-------|---------|---------|
| 1 | `/1-context` | Kontext sammeln |
| 2 | `/2-analyse` | Request verstehen, Codebase recherchieren |
| 3 | `/3-write-spec` | Spezifikation erstellen |
| 4 | User: "approved" | Spec freigeben |
| 5 | `/4-tdd-red` | Fehlschlagende Tests schreiben (RED) |
| 6 | `/5-implement` | Implementieren (GREEN) + User sagt "go" |
| 6b | Adversary Dialog | QA-Agent versucht Implementierung zu brechen |
| 7 | `/6-validate` | Validieren vor Commit |
| 8 | `/7-deploy` | Deployment |

**Adversary Verification:** Nach Implementation fuehrt ein unabhaengiger `implementation-validator` Agent (Sonnet) einen strukturierten Dialog, um die Implementierung aktiv zu brechen. Tri-State Verdict: VERIFIED / BROKEN / AMBIGUOUS. Details: `docs/features/openspec_workflow.md`

**Fresh Eyes:** Bei UI-Aenderungen prueft zusaetzlich ein `fresh-eyes-inspector` Agent Screenshots OHNE Bug-Kontext (verhindert Confirmation Bias).

**Hooks erzwingen diesen Workflow!** Edit/Write auf geschuetzte Dateien ist blockiert.

### Workflow-Tools v3 (Epic #191, ab 2026-05-11)

| Was | Wann | Befehl / Pflicht |
|-----|------|------------------|
| **AC-N-Format in Specs** | Jede neue Spec (`created >= 2026-05-11`) | `## Acceptance Criteria` mit `**AC-1:** Given... / When... / Then...` (>=30 Zeichen). Vorbild: `docs/specs/modules/epic_191_state_migration.md`. Ohne AC-N blockt `workflow_gate` Code-Edits in Phase 6. |
| **Execution-Log vor `complete`** | Workflow-Abschluss | `python3 .claude/hooks/workflow.py write-log success` schreibt YAML in `.claude/workflows/_log/`. Danach `workflow.py complete`. Ohne Log blockt der Hook. |
| **LoC-Limit 250 pro Workflow** | Bei jedem Code-Edit | `workflow.py status` zeigt `LoC-Delta: +N/250`. Bei Überschreitung: `workflow.py set-field loc_limit_override 500` (oder höher) — gilt nur für aktiven Workflow. Generierte Dateien (`.po`, `uv.lock`, `package-lock.json` etc.) zählen nicht mit, ebenso `docs/`, `*.md`, `.gitignore`. |
| **Adversary-Verdict Gating** | Nach phase6b muss Verdict gesetzt sein | `AMBIGUOUS` → Override mit `workflow.py override-ambiguous "<Grund>"` (TTL 1h). `None`/`BROKEN` → `qa_gate.py` aufrufen (setzt Verdict aus Test-Output). Commits blockt pre_commit_gate bis Verdict vorhanden ist. |
| **Phasen-Audit-Trail** | Automatisch | Jede Phasen-Transition landet in `phase_transitions[]` mit `from/to/at/trigger`. Fix-Loop-Counter (phase6b→phase6) wird automatisch gezählt. `workflow.py status` zeigt beide. |
| **Trigger-Typen für `phase`** | Optional | `workflow.py phase <ziel> --trigger=command\|advance\|user_keyword\|manual`. Default `command`. UserPromptSubmit-Hook setzt automatisch `user_keyword`. |
| **State pro Workflow** | Persistent | `.claude/workflows/<name>.json` (laufende) + `_archive/<name>.json` (abgeschlossen). Worktree-Routing bleibt intakt. |
| **GZ_ACTIVE_WORKFLOW PFLICHT** | Jederzeit | `export GZ_ACTIVE_WORKFLOW=<name>` ist die EINZIGE erlaubte Methode. `workflow.py start <name>` gibt die korrekte Export-Zeile aus. |

**SYMLINK VERBOTEN:** Der `.active`-Symlink ist als Fallback DEAKTIVIERT. `workflow.py` bricht mit FATAL-Fehler ab wenn `GZ_ACTIVE_WORKFLOW` nicht gesetzt ist. Niemals `state['active_workflow']` aus `load_state()` lesen — immer `os.environ['GZ_ACTIVE_WORKFLOW']` direkt. Beim Agent-Spawn immer `export GZ_ACTIVE_WORKFLOW=<name>` im Prompt übergeben.

**Memory-Regel: KEINE Mocks in Tests!** Bei Adversary-Findings ist `Code reference: file:line` Pflicht — siehe `.claude/agents/implementation-validator.md` Sektion "Findings-Format".

**Product Owner Pattern:** Main Context (Opus) ist reiner Orchestrierer und schreibt KEINEN Code. Implementierung wird an den Developer Agent (Opus, Worktree-Isolation) delegiert. Agent Teams ist aktiviert fuer direkte Inter-Agent-Kommunikation.

**Agenten-Rollen und Modelle:**

| Agent | Modell | Rolle |
|-------|--------|-------|
| `developer` | Opus | Implementiert Code in Worktree-Isolation |
| `bug-intake` | Sonnet | Bug-Analyse mit User-Perspektive |
| `feature-planner` | Sonnet | Use-Case-Denken, Feature-Planung |
| `implementation-validator` | Sonnet | Adversary QA Testing |
| `spec-writer` | Sonnet | Spezifikationen schreiben |
| `fresh-eyes-inspector` | Sonnet | UI-Screenshots neutral bewerten |
| `docs-updater` | Haiku | Dokumentation aktualisieren |
| `spec-validator` | Haiku | Spec-Checklisten pruefen |
| Explore-Agents | Haiku | Codebase durchsuchen |

## Developer Agent Timeout

Wenn ein Developer Agent >10 Minuten ohne gruene Tests laeuft: Abbrechen (`TaskStop`) und neu starten mit praeziserem Briefing. Max 2 Versuche pro Feature, danach Eskalation an den User.

## Architektur

```
CLI -> Config -> Provider-Adapter -> Normalizer -> Risk Engine -> Formatter -> Channel
```

Siehe: `docs/features/architecture.md`

## Wichtige Referenzen

| Dokument | Beschreibung |
|----------|--------------|
| `docs/features/epic-438-compare-wizard.md` | Orts-Vergleich Wizard (5 Steps, Step 3 ✓) |
| `docs/features/epic-134-cockpit-dashboard.md` | Trip-Cockpit-Startseite |
| `docs/features/architecture.md` | Systemarchitektur (Backend + Frontend + Wizards) |
| `docs/reference/api_contract.md` | Single Source of Truth: DTOs & Datenformate |
| `docs/reference/decision_matrix.md` | Provider-Auswahl (MET vs MOSMIX) |
| `docs/features/scope.md` | Projektvision & Ziele |

## CLI

```bash
python -m src.app.cli --report evening --channel email
python -m src.app.cli --report morning --channel none --dry-run
python -m src.app.cli --debug verbose
```

Konfigurations-Prioritaet: CLI > ENV > config.ini

## Tests

```bash
uv run pytest
```

## KEINE MOCKED TESTS! (KRITISCH!)

**Mocked Tests sind VERBOTEN in diesem Projekt!**

- Mocked Tests beweisen NICHTS - sie testen nicht das echte Verhalten
- **E-Mail-Tests:** Echte E-Mail via Gmail SMTP senden, via IMAP abrufen, Inhalt pruefen
- **API-Tests:** Echte API-Calls machen (Geosphere, etc.)
- Siehe `tests/tdd/test_html_email.py::TestRealGmailE2E` als Referenz

**NIEMALS `Mock()`, `patch()`, oder `MagicMock` fuer E-Mail/API Tests verwenden!**

## E2E-Verifikation (Post-Push auf Staging)

Die echte "funktioniert es wirklich"-Verifikation laeuft **nach** dem Push gegen
die Staging-Umgebung (`https://staging.gregor20.henemm.com`) — **nie** durch einen
lokalen Neustart des Live-Servers (auf dieser Maschine = Produktion). Siehe Issue #339.

**Ablauf:** `git push origin main` → ~5 Min Staging-Auto-Deploy abwarten →
`/e2e-verify` (gegen Staging) → `deploy-gregor-prod.sh`.

**E2E-Verifikation (`/e2e-verify`):**

1. Smoke gegen Staging (`/` + `/api/health`)
2. Scope bestimmen (frontend-only vs. backend/full-stack)
3. frontend-only → `staging-validator` Agent prüft alle ACs aus der Spec via Playwright; schreibt `e2e_verified.json` mit `verified_commit` + `staging_verdict`
4. backend/full-stack → Test-Trip auf Staging, Mail nur an `gregor-test@henemm.com`, IMAP-Pruefung
5. Nachweis in `.claude/e2e_verified.json` mit `verified_commit` (HEAD-SHA), `staging_verdict` und strukturierten Findings pro AC

Basis-URL fuer Browser-Checks via `GZ_SVELTE_BASE` (Default Staging):
```bash
GZ_SVELTE_BASE=https://staging.gregor20.henemm.com \
  uv run python3 .claude/hooks/e2e_browser_test.py browser --check "Feature" --url "/"
```

`deploy-gregor-prod.sh` liest `e2e_verified.json` und blockiert den Prod-Deploy als Hard Gate wenn `verified_commit` nicht dem aktuellem HEAD entspricht oder `staging_verdict` nicht mit `VERIFIED` beginnt (Issue #521).

**VERBOTEN:**
- Den lokalen Live-Server stoppen oder neu starten
- Sammel-Versand ueber alle Touren — nur der Test-Trip darf eine Mail bekommen
- "E2E Test erfolgreich" sagen ohne Verifikation gegen Staging

## E-MAIL SPEC VALIDATOR (ZWINGEND!)

**PFLICHT vor "E2E Test bestanden" bei E-Mail-Features:**

```bash
uv run python3 .claude/hooks/email_spec_validator.py
```

Prueft: Struktur, Location-Anzahl, Plausibilitaet, Format, Vollstaendigkeit.

Laeuft in der Acceptance-Stage gegen die Staging-Mail: Test-Trip mit Empfaenger
`gregor-test@henemm.com`, IMAP-Quelle ist das Stalwart-Test-Postfach (`mail.henemm.com`).
Credentials kommen aus den Settings (`GZ_IMAP_*`) — niemals im Klartext hier. Kein Gmail.

**NUR bei Exit 0 darfst du "E2E Test bestanden" sagen!**

Einfache String-Checks beweisen NICHTS - sie pruefen nicht ob Daten SINNVOLL sind!

## Specs

Alle Module benoetigen Specs vor Implementierung:
- Template: `docs/specs/_template.md`
- Location: `docs/specs/modules/[entity].md`
- Implementierte Module: siehe geschlossene GitHub Issues + `docs/specs/modules/`

## Dokumentation

- `docs/specs/` - Entity-Spezifikationen
- `docs/features/` - Feature-Dokumentation
- `docs/reference/` - Technische Referenz
- `docs/project/` - Projekt-Management (Archiv)

## Backlog & Issue-Tracking

**GitHub Issues ist die Single Source of Truth fuer offene Arbeit:**
https://github.com/henemm/gregor_zwanzig/issues

- **Neue Features** → GitHub Issue mit Label `enhancement` erstellen
- **Neue Bugs** → GitHub Issue mit Label `bug` erstellen
- **Fortschritt** → Issue schliessen wenn fertig
- **Erledigte Features** → GitHub Issues/PRs (closed). Historisches Archiv (vor 2026-05-02): `docs/project/backlog/completed-features-archive.md` (stillgelegt)
- **Root-Cause-Analysen** → `docs/project/known_issues.md`
- **Strategische Entscheidungen** → `docs/project/strategic-directions.md`

**NICHT MEHR in Markdown-Dateien planen!** Offene Features, Bugs und Sprint-Planung gehoeren auf GitHub Issues.

## Pre-Test Validierung (PFLICHT!)

**BEVOR du den User zum Testen aufforderst, MUSST du validieren!**

```bash
python3 .claude/validate.py
```

### Was wird geprueft:
1. **Syntax-Check** auf alle geaenderten Python-Dateien
2. **Import-Check** - Module lassen sich importieren
3. **Server-Startup** - Web-UI startet fehlerfrei

### Workflow:
1. Code schreiben/aendern
2. `python3 .claude/validate.py` ausfuehren
3. Alle Checks gruen? -> User zum Testen auffordern
4. Checks rot? -> Fehler beheben, erneut validieren

### Nach erfolgreichem User-Test:
```bash
python3 .claude/validate.py --clear
```

**NIEMALS "teste es" oder "pruefe" sagen ohne vorherige Validierung!**

## Daten-Schema-Reworks (PFLICHT!)

**Bei Aenderungen an Persistenz-Strukturen MUESSEN Bestandsdaten erhalten bleiben.**

Hintergrund: BUG-DATALOSS-GR221 (Issue #102). Bei einem frueheren Refactor gingen 3 von 4 Stages des GR221-Trips verloren — das Recovery war nur moeglich, weil GPX-Dateien zufaellig in einem Stash ueberlebt haben.

### Schema-relevante Dateien

`src/app/models.py`, `src/app/trip.py`, `src/app/loader.py`, `internal/model/*.go`, `internal/store/store.go`

### Pflicht-Workflow

1. **Pre-Snapshot:** Hook `data_schema_backup.py` erstellt automatisch ein tar.gz von `data/users/` nach `.backups/data-pre-rework-<ts>.tar.gz` bevor eine Schema-Datei editiert wird (Retention: 20 Stueck).
2. **Migration mit Test:** Bei Feldumbenennung/-removal: Migration-Skript schreiben + Roundtrip-Test (load alt → migrate → load neu → assert keine Daten-Diff)
3. **Post-Verifikation:** Nach Deploy alle Trips/Locations/Subscriptions im Frontend laden, Stage-/Waypoint-Counts gegen Pre-Snapshot vergleichen
4. **Bei Datenverlust:** Sofortiges Rollback aus `.backups/`, Root-Cause in `docs/project/known_issues.md` dokumentieren

### Anti-Pattern (verboten)

```python
# Edit-Handler baut neues Objekt aus UI-State und ueberschreibt Persistenz
updated = Trip(id=tid, name=name_input.value, stages=ui_stages)
save_trip(updated)  # Felder die UI nicht kennt sind weg!
```

```go
// Backend Replace statt Merge
var trip model.Trip
json.Decode(r.Body, &trip)
store.SaveTrip(trip)  // existing.aggregation, .display_config etc. weg!
```

**Korrekt:** Read-Modify-Write mit Merge — bestehendes Objekt laden, nur explizit veraenderte Felder ueberschreiben, Rest erhalten.

## Parallele Sessions

**Ein Projektordner = hoechstens eine Claude-Session gleichzeitig.** Mehrere Sessions im selben Working-Tree kollidieren: gemeinsame Dateien (uncommittete Fremd-Arbeit verschmutzt die Sicht, `git add -A` wuerde sie mit-committen) und gemeinsame Workflow-Buchfuehrung (Session-Verwechslung).

Fuer Parallelarbeit eine isolierte Arbeitskopie anlegen:

```bash
bash .claude/tools/gz-workspace new <name>   # isolierter Klon unter $GZ_WS_ROOT (Default /home/hem/gz-workspaces) auf Branch ws/<name>
bash .claude/tools/gz-workspace list         # alle Workspaces mit Branch + uncommitted-Zaehler
bash .claude/tools/gz-workspace clean <name> # entfernen (nur wenn sauber; --force erzwingt)
```

Danach `cd` in den Workspace und dort eine NEUE Claude-Session starten. Fuer Frontend-Arbeit dort `cd frontend && npm ci`. Jeder Workspace ist voll isoliert (eigenes `.git`/Index, eigene Dateien, eigener Workflow-State); die Klon-Objekte sind gehardlinkt (platzsparend). Hauptrepo und andere Workspaces bleiben unberuehrt.

**Selbst-Isolierung (automatisch):** Erkennt der Session-Wächter eine zweite Sitzung im selben Ordner, ruft Claude unaufgefordert `EnterWorktree` auf und arbeitet in der isolierten Kopie weiter — kein Beenden oder Neustart nötig, der Nutzer muss nichts tun.

### Abschluss einer parallelen Session — NIE „ich warte auf die andere Session"

Jede Session liefert **unabhängig** aus. Kein Warten aufeinander, keine Koordination über den geteilten Baum. Der Integrationspunkt ist `origin/main`, nicht der lokale Ordner:

1. **Isoliert arbeiten** (Workspace/Worktree) — erzwingt der Session-Wächter ohnehin.
2. **Grün?** Im eigenen Branch committen, dann `git fetch origin && git rebase origin/main`, dann nach `main` pushen. Git serialisiert gleichzeitige Pushes selbst; bei Ablehnung erneut rebasen und pushen.
3. **Staging** aktualisiert sich automatisch (~5 Min, eigener Klon) → gegen Staging validieren.
4. **Production ausliefern:** `bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` — **aus jeder Session jederzeit gefahrlos.** Ein `flock` serialisiert gleichzeitige Deploys (zweiter Aufruf wartet kurz und liefert dann den aktuellen `origin/main`-Stand). Das Script hängt **nicht mehr** am Zustand des geteilten Arbeitsbaums.

**Die eine Regel, die das sicher macht:** Nach `main` wird nur Grünes (staging-validiert) gepusht — `main` ist immer auslieferbar. Dann darf ein Deploy auch frisch gepushte Arbeit einer anderen Session mitnehmen.

**Verboten:** Ein Deploy aufschieben, „bis der gemeinsame Ordner sauber ist" oder „bis die andere Session fertig ist". Diese Pattsituation existiert nicht mehr — der Deploy bringt den Code hart auf `origin/main` (untracked Live-Daten unberührt, echte uncommittete WIP wird vorher als stash-Commit + `deploy-safety/*`-Tag gesichert).

## Deployment & Infrastruktur

Globale Server-Infos und Monitoring-Anleitung stehen in `~/.claude/CLAUDE.md`.

- **Production:** https://gregor20.henemm.com — Systemd (`gregor-python.service`, `gregor-api`, `gregor-frontend`)
- **Staging:** https://staging.gregor20.henemm.com — Systemd (`gregor-python-staging`, `gregor-api-staging`, `gregor-frontend-staging`)
- **Infrastruktur-Repo:** `henemm/henemm-infra` (Nginx-Config, Systemd-Service, Deploy-Scripts)

### Post-Push-Workflow (PFLICHT)

**Nach jedem `git push origin main`** in dieser Reihenfolge:

| Schritt | Was | Wie |
|---|---|---|
| 1 | Push | `git push origin main` |
| 2 | Auto-Deploy auf Staging abwarten (~5 Min) | Cron `*/5` ruft `auto-deploy-gregor-staging.sh` |
| 3 | Staging-Validierung | siehe Definition unten |
| 4 | Prod-Deploy | `bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` |

`systemctl restart` allein **reicht nie** — `deploy-gregor-prod.sh` macht `flock-Lock → hart auf origin/main syncen (Daten unberührt, WIP gesichert) → Go-Binary bauen → Frontend bauen → alle 3 Services restarten → Smoke-Test`. Ohne diesen vollen Lauf entsteht Code-Drift, den `check-gregor20.sh` als BetterStack-Alert meldet (siehe Issue #113). Das Script ist **parallel-session-sicher**: es blockiert nicht mehr bei „dirty" Arbeitsbaum und serialisiert gleichzeitige Deploys über `flock`. Schritt 4 darf daher aus jeder Session jederzeit laufen.

### Was zaehlt als „Staging-validiert"?

Mindestens diese Checks gegen `https://staging.gregor20.henemm.com`:
- HTTP-Smoke: `/` antwortet `200` oder `302`, `/api/health` antwortet `200`
- Eine geaenderte Funktion manuell durchgeklickt (oder via Playwright fuer UI-Features)
- Bei Mail-Aenderungen: Test-Mail aus dem Scheduler triggern und IMAP-Verifikation
- Bei Scheduler-Aenderungen: `last_run`-Status im Endpoint geprueft

### Ausnahme: Reine Doku-/Tooling-Aenderungen

Wenn der Push **ausschliesslich** `.md`-Dateien, `docs/`, `.claude/`-Inhalte (Hooks/Agents/Commands), `.gitignore` o. ae. veraendert hat — **keinen Code in `src/`, `api/`, `internal/`, `frontend/`, `cmd/`** — dann:
- Schritt 3 (Staging-Validierung) entfaellt
- Schritt 4 (Prod-Deploy) entfaellt, **wenn** der Code-Drift-Monitor (`check-gregor20.sh`) noch keinen Alert ausloest (Drift-Schwelle > 1h gegenueber `mtime(gregor-api)`)

Im Zweifel: trotzdem deployen, dann ist der Drift-Monitor auf jeden Fall ruhig.

## Monitoring

Externes Monitoring laeuft ueber `henemm-infra/check-gregor20.sh`. Der interne Heartbeat-Ping vom Scheduler an BetterStack ist optional — wenn `GZ_HEARTBEAT_MORNING`/`GZ_HEARTBEAT_EVENING` ENV-Variablen leer sind, wird kein Heartbeat gesendet (fail-soft). In dem Fall geht beim ersten Job-Lauf einmalig pro Prozess eine MQ-Nachricht an `infra` raus.

**Status-Endpoint:** `/api/scheduler/status` (gregor-api, Port 8090) — liefert pro Job: `next_run` + `last_run` (time, status ok/error, error message). Der externe Health-Check kann damit erkennen ob Jobs tatsaechlich erfolgreich laufen.

**PFLICHT bei neuen Services/Schedulern:** Jeder neue Hintergrund-Job oder Service MUSS `last_run`-Tracking im Status-Endpoint haben, damit das externe Monitoring Fehler erkennen kann. Kein Job ohne Observability!

## Design-Leitprinzipien (PO-bestätigt 2026-05-25)

**Hoher Kontrast = Lesbarkeit.** Bei jedem Konflikt zwischen "weicher Optik"/"warmer Atmosphäre" und "klarer Lesbarkeit von Inhalt" gewinnt **Lesbarkeit**. Begründung: Das Produkt ist ein Briefing-Werkzeug für Wetter-/Tourenentscheidungen — Inhalt muss unter Zeitdruck und in jeder Lichtsituation verlässlich lesbar sein. Dieses Prinzip steht über ästhetischen Präferenzen.

Konkrete Konsequenzen (Quelle: `docs/design-requests/issue_15_atomic_design/RESPONSE-FROM-CLAUDE-DESIGN.md`):
- **Karten = weiß** (`--g-card #ffffff`) auf warmer Off-White-Page (`--g-paper #f6f4ee`). Kein beiges Card-on-beige.
- **Text-Kontrast:** echter Text mindestens WCAG-AA (4.5:1). `--g-ink-4` ist strikt für Placeholder/Disabled — nicht für Captions/Help-Text/Daten-Labels (nur 2.85:1 auf Weiß).
- **Akzent-Farben sparsam** und nie als alleiniger Lesbarkeits-Träger — Form + Position + Mono-Strecke tragen mit.

Folge-Arbeit (Reihenfolge laut Claude Design): Surface-Stack-Migration (app.css-Werte auf weiße Karten, **vor** Atom-Migration) → Token-Rename (Code-Namen gewinnen, Mapping in RESPONSE-FROM-CLAUDE-DESIGN.md) → Atom-Migration (Epic #368). Kontrast-Audit (#16) parallel möglich.

## Signal als Channel (Feature-Idee)

Signal-Benachrichtigungen sind als zusätzlicher Channel neben E-Mail und SMS verfügbar. Infrastruktur steht bereit:
- Callmebot API: `https://signal.callmebot.com/signal/send.php?phone=PHONE&apikey=KEY&text=MSG`
- Credentials in `/home/hem/henemm-infra/.env` (CALLMEBOT_PHONE, CALLMEBOT_APIKEY)
- Referenz-Implementierung: `oebb-nightjet-monitor/notify.go` (Go) oder `henemm-infra/scripts/notify-signal.sh` (Bash)

## Messaging

Diese Instanz heißt `gregor`. Siehe `~/.claude/CLAUDE.md` → "Inter-Instance Messaging" für Details.
