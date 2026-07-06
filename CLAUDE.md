# CLAUDE.md - Gregor Zwanzig

## Projekt-Ueberblick

**Gregor Zwanzig** ist ein Headless-Service zur Normalisierung von Wetterdaten und Ausgabe als kompakte Reports (SMS <=160 Zeichen, E-Mail mit Tabellen).

- **Zielgruppe:** Weitwanderer (z.B. GR20), eingeschraenkte Konnektivitaet
- **Stack:** Python, uv, pytest
- **Channels:** E-Mail (MVP), Telegram, SMS. (Signal wurde 2026-06-06 app-weit als Kanal entfernt — PO-Entscheidung, Issue #610.)
- **Multi-User-Produkt:** Gregor Zwanzig ist **mandantenfähig** — jeder Nutzer hat eigene Trips, Orte, Orts-Vergleiche, Empfänger und Settings. Persistenz pro Nutzer unter `data/users/<user_id>/`. Das Backend isoliert **konsequent** über `s.WithUser(middleware.UserIDFromContext(r.Context()))` (Go) bzw. den `user_id`-Parameter (Python-Scheduler/-Router). **PFLICHT bei jedem nutzerbezogenen Endpoint:** echte `user_id` aus dem Auth-Kontext durchreichen, **niemals** auf `"default"` zurückfallen — ein `"default"`-Fallback in einem authentifizierten Pfad ist ein Cross-User-Datenleck. Jeder neue Endpoint, der Daten lädt/schreibt/versendet, MUSS mandantengetrennt arbeiten und mit **zwei verschiedenen Nutzern** getestet werden. Konsequenz fürs Produkt-Denken: Es gibt kein systemseitiges „an mich" — der eingeloggte Nutzer sieht nur seine eigenen Daten; „senden" heißt immer „an die von diesem Nutzer konfigurierten Empfänger". (Single-User-Annahmen wie „Test an mich vs. an die Empfänger" sind gegenstandslos.)

## Workflow

Dieses Projekt nutzt den **OpenSpec 8-Phasen-Workflow** mit Adversary Verification:

| Phase | Command | Purpose | PO-Eingriff |
|-------|---------|---------|-------------|
| 1 | `/1-context` | Kontext sammeln | — |
| 2 | `/2-analyse` | Request verstehen, Codebase recherchieren | Optional: 3-Satz-Zusammenfassung korrigieren |
| 3 | `/3-write-spec` | Spezifikation erstellen | **Pflicht: ACs auf Deutsch freigeben** ('go') |
| 4 | — | Spec freigegeben | — |
| 5 | `/4-tdd-red` | Fehlschlagende Tests schreiben (RED) | Optional: AC-Test-Mapping lesen |
| 6 | `/5-implement` | Implementieren (GREEN) + Adversary | — (läuft automatisch durch) |
| 7 | `/6-validate` | Validieren vor Commit | — |
| 8 | — | Deployment (inline in `/6-validate` Step 5) | **Pflicht: Tech-Lead-Brief lesen + 'go' sagen** |

**Adversary Verification:** Nach Implementation fuehrt ein unabhaengiger `implementation-validator` Agent (Sonnet) einen strukturierten Dialog, um die Implementierung aktiv zu brechen. Tri-State Verdict: VERIFIED / BROKEN / AMBIGUOUS. Details: `docs/features/openspec_workflow.md`

**Fresh Eyes:** Bei UI-Aenderungen prueft zusaetzlich ein `fresh-eyes-inspector` Agent Screenshots OHNE Bug-Kontext (verhindert Confirmation Bias).

**Hooks erzwingen diesen Workflow!** Edit/Write auf geschuetzte Dateien ist blockiert.

### Workflow-Tools v3 (Epic #191, ab 2026-05-11)

| Was | Wann | Befehl / Pflicht |
|-----|------|------------------|
| **AC-N-Format in Specs** | Jede neue Spec (`created >= 2026-05-11`) | `## Acceptance Criteria` mit `**AC-1:** Given... / When... / Then...` (>=30 Zeichen). Vorbild: `docs/specs/modules/epic_191_state_migration.md`. Ohne AC-N blockt `workflow_gate` Code-Edits in Phase 6. |
| **Execution-Log vor `complete`** | Workflow-Abschluss | `python3 .claude/hooks/workflow.py write-log success` schreibt YAML in `.claude/workflows/_log/`. Das Log enthält Workflow-Metadaten: Phasen-Transitions, Laufzeiten, **Token-Verbrauch (input/output/cache)** akkumuliert über alle Sessions (Issue #829). Danach `workflow.py complete`. Ohne Log blockt der Hook. |
| **Token-Tracking (Issue #829)** | Automatisch bei Session-Ende | Stop-Hook `track_token_usage.py` liest Session-Transcript und summiert Token-Felder in Workflow-State. Kumulativ über mehrere Sessions. Wird in `write-log` ins YAML geschrieben. Kein GZ_ACTIVE_WORKFLOW → fail-safe (exit 0). |
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

**Dateiinhalt-Checks sind ebenfalls VERBOTEN:**
`assert 'xyz' in file.read_text()` — das ist Code-Analyse, kein Verhaltensnachweis.
TDD-Tests MÜSSEN das tatsächliche Verhalten beweisen:
- Frontend-Bug: Playwright-E2E gegen Staging als eingeloggter Nutzer
- Backend-Bug: echter HTTP-Call, echter DB-Zustand prüfen
- Mindestens ein Test muss den Bug aus Nutzerperspektive reproduzieren (rot vor Fix, grün nach Fix)
- **Ausnahme:** Dokumentations-Compliance-Tests die Workflow-Dateien selbst als Artefakt prüfen (z.B. "enthält CLAUDE.md die Regel X?"). Diese müssen mit `# doc-compliance-test` markiert sein.

## E2E-Verifikation (Post-Push auf Staging)

Die echte "funktioniert es wirklich"-Verifikation laeuft **nach** dem Push gegen die
Staging-Umgebung (`https://staging.gregor20.henemm.com`) — **nie** durch einen lokalen Neustart
des Live-Servers (auf dieser Maschine = Produktion). Siehe Issue #339.

**Ablauf:** `git push origin main` → ~5 Min Staging-Auto-Deploy → `/e2e-verify` (gegen Staging)
→ `deploy-gregor-prod.sh` → Post-Deploy-Selftest (Issue #564) → Issue close. Der Prod-Deploy ist
ein Hard Gate: er blockt, wenn `e2e_verified.json[verified_commit]` nicht dem HEAD entspricht
oder `staging_verdict` nicht mit `VERIFIED` beginnt (Issue #521).

**VERBOTEN:**
- Den lokalen Live-Server stoppen oder neu starten
- Sammel-Versand ueber alle Touren — nur der Test-Trip darf eine Mail bekommen
- "E2E Test erfolgreich" sagen ohne Verifikation gegen Staging

**Detailablauf** (E2E-Schritte, `GZ_SVELTE_BASE`-Aufruf, Post-Deploy-Selftest inkl.
Verdict-Ableitung PASS/PARTIAL/FAIL/SKIP): **`docs/reference/operations_playbook.md`**.
Kern-Schutzwirkung: **Issue-Close nur bei Selftest-Exit 0** — bei PARTIAL/FAIL erst Bericht
prüfen, ggf. Rollback (Issue #564).

## Mail-Validatoren & Renderer-Gate (ZWINGEND)

Drei Mail-Pfade, drei Gates. **Den falschen Validator auf einen Pfad anzuwenden ist ein Fehler** (er kann strukturell nie bestehen → Dauer-Exit-1 → falsches „Feature kaputt"/Gate-Erosion). Dispatch:

| Mail-Pfad | Validator (PFLICHT vor „E2E bestanden") | Marker-Header |
|---|---|---|
| **Orts-Vergleich** (Vergleichsmatrix, Winner-Box, ≥3 Orte) | `uv run python3 .claude/hooks/email_spec_validator.py` | `X-GZ-Mail-Type: compare` |
| **Trip-Briefing** (`full`/`compact`, Stundentabellen, keine Winner-Box) | `uv run python3 .claude/hooks/briefing_mail_validator.py` | `X-GZ-Mail-Type: trip-briefing` + `X-GZ-Format: full\|compact` |

**Regeln (beide Validatoren):**
- Lauf gegen die **echt zugestellte Staging-Mail** aus dem Stalwart-Test-Postfach (`gregor-test@henemm.com`, Creds `GZ_IMAP_*` — nie im Klartext). **Kein Mock, kein Gmail.** Geprüft wird **Plausibilität**, nicht bloß String-Presence (einfache String-Checks beweisen NICHTS).
- **Nur bei Exit 0** darfst du „E2E Test bestanden" sagen. Falscher Validator für den Pfad → sauberes No-Op (Exit 0); fehlender Marker-Header → Exit 1.

**Renderer-Commit-Gate (seit #811 — un-überspringbar, kein Bypass):** `renderer_mail_gate.py`
blockiert jeden `git commit`, der eine Mail-Inhalts-Datei staged (`src/output/renderers/email/*.py`,
`src/formatters/*.py`, `src/outputs/email.py`), bis im aktiven Workflow **beide** Nachweise
**frisch** vorliegen: (1) Modus-Matrix-Vertragstest `tests/tdd/test_issue_811_mode_matrix.py` grün,
(2) erfolgreicher `briefing_mail_validator.py`-Lauf. **Abhilfe bei Blockade** (kein Override):
`uv run pytest tests/tdd/test_issue_811_mode_matrix.py` schreibt den Matrix-Nachweis automatisch,
dann den Validator gegen die Staging-Mail grün bekommen.

Vollständige Details (Plausibilitäts-Schwellen pro Format, Dispatch-Verhalten, Anti-Stale-Mechanik, Historie): **`docs/reference/mail_validators.md`**.

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

**BEVOR du den User zum Testen aufforderst, MUSST du validieren!** `python3 .claude/validate.py`
prüft Syntax + Import geänderter Python-Dateien und Server-Startup. Erst wenn **alle Checks grün**
sind, den User zum Testen auffordern; nach erfolgreichem Test `python3 .claude/validate.py --clear`.

**NIEMALS "teste es" oder "pruefe" sagen ohne vorherige Validierung!**

## Daten-Schema-Reworks (PFLICHT!)

**Bei Aenderungen an Persistenz-Strukturen MUESSEN Bestandsdaten erhalten bleiben.** Grundregel:
**Read-Modify-Write mit Merge** — bestehendes Objekt laden, nur explizit veränderte Felder
überschreiben, Rest erhalten. **Niemals Replace** (neues Objekt aus UI-/Request-State bauen und
speichern → Felder, die der Client nicht kennt, sind weg). Hintergrund: BUG-DATALOSS-GR221
(Issue #102), 3 von 4 Stages verloren.

**Schema-relevante Dateien:** `src/app/models.py`, `src/app/trip.py`, `src/app/loader.py`,
`internal/model/*.go`, `internal/store/store.go`. Ein Edit daran löst automatisch den
Pre-Snapshot-Hook `data_schema_backup.py` aus (tar.gz nach `.backups/`, Retention 20).

Pflicht-Workflow im Detail (Migration + Roundtrip-Test, Post-Verifikation der Stage-/Waypoint-
Counts, Rollback) und die Anti-Pattern-Codebeispiele (Python/Go): **`docs/reference/operations_playbook.md`**.

## Parallele Sessions

**Ein Projektordner = hoechstens eine Claude-Session gleichzeitig.** Mehrere Sessions im selben
Working-Tree kollidieren (gemeinsame Dateien, `git add -A` zieht Fremd-WIP mit, gemeinsame
Workflow-Buchführung). Für Parallelarbeit eine isolierte Arbeitskopie anlegen — der
Session-Wächter erzwingt das ohnehin und ruft bei einer zweiten Sitzung unaufgefordert
`EnterWorktree` auf:

```bash
bash .claude/tools/gz-workspace new <name>   # isolierter Klon auf Branch ws/<name>
bash .claude/tools/gz-workspace list         # alle Workspaces mit Branch + uncommitted-Zähler
bash .claude/tools/gz-workspace clean <name> # entfernen (nur wenn sauber; --force erzwingt)
```

**Die eine Regel, die das sicher macht:** Jede Session liefert **unabhängig** aus — kein Warten
aufeinander. Integrationspunkt ist `origin/main`, nicht der lokale Ordner. Nach `main` wird nur
Grünes (staging-validiert) gepusht → `main` ist immer auslieferbar → ein Deploy
(`deploy-gregor-prod.sh`, per `flock` serialisiert) darf aus jeder Session jederzeit laufen.
**Verboten:** einen Deploy aufschieben, „bis der Ordner sauber ist" oder „die andere Session
fertig ist" — diese Pattsituation existiert nicht mehr.

Detailablauf (isoliert arbeiten → committen/rebasen/pushen → Staging → Deploy) und die
WIP-Sicherung beim Deploy: **`docs/reference/operations_playbook.md`**.

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
| 4b | Post-Deploy-Selftest | `python3 .claude/hooks/prod_selftest.py` (Commit/Health/AC-Attestation) — nur Exit 0 fährt weiter |
| 5 | Issue schließen | `gh issue close <N>` — nur wenn 4b Exit 0 |

`systemctl restart` allein **reicht nie** — `deploy-gregor-prod.sh` macht `flock-Lock → hart auf
origin/main syncen (Daten unberührt, WIP gesichert) → Go-Binary bauen → Frontend bauen → alle 3
Services restarten → Smoke-Test`. Ohne diesen vollen Lauf entsteht Code-Drift, den
`check-gregor20.sh` als BetterStack-Alert meldet (Issue #113). Das Script ist
**parallel-session-sicher** (`flock`, kein „dirty"-Block) — Schritt 4 darf aus jeder Session
jederzeit laufen.

**„Staging-validiert"** heißt mindestens: HTTP-Smoke (`/` → 200/302, `/api/health` → 200) +
eine geänderte Funktion manuell/Playwright durchgeklickt; bei Mail-Änderungen Test-Mail +
IMAP-Verifikation; bei Scheduler-Änderungen `last_run` geprüft.

**Ausnahme — reine Doku-/Tooling-Änderungen:** Verändert der Push **ausschließlich** `.md`,
`docs/`, `.claude/`, `.gitignore` o. ä. (**keinen Code in `src/`, `api/`, `internal/`,
`frontend/`, `cmd/`**), entfallen Schritt 3 und — solange der Drift-Monitor ruhig ist — Schritt 4.
Im Zweifel trotzdem deployen. Volle Definitionen: **`docs/reference/operations_playbook.md`**.

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

## Signal als Channel — ENTFERNT (2026-06-06, Issue #610)

**Signal ist app-weit als Kanal entfernt** (PO-Entscheidung, Issue #610). Kanäle sind nur noch **E-Mail · Telegram · SMS**. Frontend (Schritt 1/2) und Backend (Schritt 2/2) wurden bereinigt: keine Kanal-Auswahl, keine `SignalOutput`, kein `signal_text`/`send_signal`, kein `/api/preview/{trip}/signal`.

Die Callmebot-Infrastruktur existiert weiterhin auf Server-Ebene (`/home/hem/henemm-infra/.env`, `notify-signal.sh`) und wird von anderen Diensten genutzt — aber **nicht** mehr von Gregor Zwanzig als Briefing-Kanal. Eine etwaige Wiedereinführung müsste neu spezifiziert werden.

## Confidence (Vorhersage-Verlässlichkeit) — NICHT wählbar als Metrik (2026-06-10, Issue #710)

**Confidence (`confidence_pct`, Vorhersage-Verlässlichkeit aus Open-Meteo Ensemble API) ist KEINE pro-Etappe wählbare Wetter-Metrik.** Sie ist eine Meta-Aussage über die mehrtägige Ensemble-Divergenz (NICHT eine lokale Wettergröße wie Temperatur/Wind) und darf ausschließlich als:

1. **Vorhersage-Verlässlichkeits-Hinweis** (E-Mail-Textblock: "Ab Mittwoch nimmt die Unsicherheit zu...")
2. **SMS-Token** (C+/C~/C? für Sicherheit-Bands)
3. **Interne Aggregation/Scoring** (Berechnungen, Persistenz)

…erscheinen — **NIEMALS** wieder im Trip-Editor, Wizard Step 3, Metrik-Auswahl oder als per-Etappe-Spalte.

**Implementierung (seit 2026-06-10):** `MetricDefinition.selectable=false` für `confidence`; GET `/api/metrics` filtert auf `selectable=true`. **Backward Compatibility:** Alte Trips mit aktiviertem `confidence` in `display_config` laden still, aber die Metrik wird in Render-Pfaden ignoriert (keine Spalte, keine Vorschau-Werte). **PO-Entscheidung, Final** — diese Regel verhindert Regress wie Issue #710 (confidence re-aktiviert nach Bug #424-Fix) und Issue #473 (unvollständiger Entfernung).

## Messaging

Diese Instanz heißt `gregor`. Siehe `~/.claude/CLAUDE.md` → "Inter-Instance Messaging" für Details.

# Compact instructions

Diese Sektion wird von `/compact` automatisch als Zusammenfassungs-Anleitung gelesen (dokumentiertes Claude-Code-Feature). Sie greift bei jedem `/compact` — du musst also **nie** einen langen `/compact <Text>` tippen, einfaches `/compact` genügt.

Wenn gerade ein OpenSpec-Workflow läuft (`GZ_ACTIVE_WORKFLOW` gesetzt), bewahre beim Komprimieren IMMER:

- **Workflow-Identität:** Issue-Nummer, Workflow-Name (`GZ_ACTIVE_WORKFLOW`), aktuelle Phase.
- **Spec & Akzeptanz:** die freigegebenen ACs (AC-N) und alle Designentscheidungen aus der Analyse-Phase.
- **TDD-Stand:** welche Tests rot sind und **warum** (Bug-Reproduktion aus Nutzersicht), die betroffenen Source-/Test-Dateipfade, RED-Artefakt-Pfade, das LoC-Limit.
- **Implementierung & QA:** welche Dateien geändert wurden, das Adversary-Verdict, offene Fix-Loop-Punkte.
- **Deploy-relevant:** den Scope (frontend-only vs. full-stack — entscheidet den E2E-Pfad), `verified_commit`-Status, Staging-Verdict.

Verwirf dagegen: rohe Tool-Output-Dumps, allgemeines Hin-und-Her und Implementierungs-Detail-Diskussionen, die bereits im Code oder in den State-Dateien (`.claude/workflows/<name>.json`, `e2e_verified.json`, `docs/artifacts/`) stehen — diese überleben den Compact ohnehin auf der Platte.
