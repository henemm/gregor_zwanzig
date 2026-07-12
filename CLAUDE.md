# CLAUDE.md - Gregor Zwanzig

## Projekt-Ueberblick

**Gregor Zwanzig** ist ein Headless-Service zur Normalisierung von Wetterdaten und Ausgabe als kompakte Reports (SMS <=160 Zeichen, E-Mail mit Tabellen).

- **Zielgruppe:** Weitwanderer (z.B. GR20), eingeschraenkte Konnektivitaet
- **Stack:** Python, uv, pytest
- **Channels:** E-Mail (MVP), Telegram, SMS. (Signal 2026-06-06 app-weit entfernt, Issue #610 — s.u.)
- **Multi-User-Produkt:** Gregor Zwanzig ist **mandantenfähig** — jeder Nutzer hat eigene Trips, Orte, Orts-Vergleiche, Empfänger und Settings. Persistenz pro Nutzer unter `data/users/<user_id>/`. Isolation **konsequent** über `s.WithUser(middleware.UserIDFromContext(r.Context()))` (Go) bzw. `user_id`-Parameter (Python). **PFLICHT bei jedem nutzerbezogenen Endpoint:** echte `user_id` aus Auth-Kontext durchreichen, **niemals** auf `"default"` zurückfallen — das ist ein Cross-User-Datenleck. Jeder neue datenbewegende Endpoint MUSS mit **zwei verschiedenen Nutzern** getestet werden. Es gibt kein systemseitiges „an mich" — „senden" heißt immer „an die konfigurierten Empfänger dieses Nutzers".

## Workflow

OpenSpec 8-Phasen-Workflow mit Adversary Verification:

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

**Adversary Verification:** Nach Implementation führt ein unabhängiger `implementation-validator` Agent (Sonnet) einen strukturierten Dialog, um die Implementierung aktiv zu brechen. Tri-State Verdict: VERIFIED / BROKEN / AMBIGUOUS. Details: `docs/features/openspec_workflow.md`

**Fresh Eyes:** Bei UI-Änderungen prüft zusätzlich ein `fresh-eyes-inspector` Agent Screenshots OHNE Bug-Kontext (verhindert Confirmation Bias).

**Hooks erzwingen diesen Workflow!** Edit/Write auf geschützte Dateien ist blockiert.

### Workflow-Tools v3 (Epic #191, ab 2026-05-11)

| Was | Befehl / Pflicht |
|-----|------------------|
| **AC-N-Format in Specs** | Jede Spec `created >= 2026-05-11` braucht `## Acceptance Criteria` mit `**AC-1:** Given.../When.../Then...` (>=30 Zeichen). Vorbild: `docs/specs/modules/epic_191_state_migration.md`. Ohne AC-N blockt `workflow_gate` Phase 6. |
| **Execution-Log vor `complete`** | `python3 .claude/hooks/workflow.py write-log success` schreibt YAML (Phasen, Laufzeiten, Token-Verbrauch, Issue #829) nach `.claude/workflows/_log/`, dann `workflow.py complete`. Ohne Log blockt der Hook. |
| **Token-Tracking (#829)** | Stop-Hook `track_token_usage.py` summiert Transcript-Tokens ins Workflow-State, kumulativ über Sessions. Kein `GZ_ACTIVE_WORKFLOW` → fail-safe. |
| **LoC-Limit 250/Workflow** | `workflow.py status` zeigt `LoC-Delta: +N/250`. Überschritten → `workflow.py set-field loc_limit_override 500`. Generierte Dateien + `docs/`/`*.md`/`.gitignore` zählen nicht. |
| **Adversary-Verdict Gating** | Nach phase6b: `AMBIGUOUS` → `workflow.py override-ambiguous "<Grund>"` (TTL 1h); `None`/`BROKEN` → `qa_gate.py` aufrufen. Commit blockt ohne Verdict. |
| **Phasen-Audit-Trail** | Jede Transition landet in `phase_transitions[]` (from/to/at/trigger), inkl. Fix-Loop-Counter. |
| **Trigger-Typen für `phase`** | `workflow.py phase <ziel> --trigger=command\|advance\|user_keyword\|manual` (Default `command`). |
| **State pro Workflow** | `.claude/workflows/<name>.json` (laufend) / `_archive/<name>.json` (abgeschlossen). |
| **GZ_ACTIVE_WORKFLOW PFLICHT** | `export GZ_ACTIVE_WORKFLOW=<name>` ist die EINZIGE erlaubte Methode — `workflow.py start <name>` gibt die Export-Zeile aus. |

**SYMLINK VERBOTEN:** `.active`-Symlink-Fallback ist deaktiviert; `workflow.py` bricht FATAL ab ohne `GZ_ACTIVE_WORKFLOW`. Niemals `state['active_workflow']` lesen — immer `os.environ['GZ_ACTIVE_WORKFLOW']`. Beim Agent-Spawn immer `export GZ_ACTIVE_WORKFLOW=<name>` im Prompt übergeben.

**KEINE Mocks in Tests!** Bei Adversary-Findings ist `Code reference: file:line` Pflicht — siehe `.claude/agents/implementation-validator.md` Sektion „Findings-Format".

**Product Owner Pattern:** Main Context (Opus) ist reiner Orchestrierer und schreibt KEINEN Code. Implementierung geht an den Developer Agent (Opus, Worktree-Isolation).

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

**Developer Agent Timeout:** >10 Min ohne grüne Tests → `TaskStop` + Neustart mit präziserem Briefing. Max 2 Versuche, danach Eskalation an den User.

## Architektur

```
CLI -> Config -> Provider-Adapter -> Normalizer -> Risk Engine -> Formatter -> Channel
```

Details: `docs/features/architecture.md`

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

## Test-Politik: Zwei Schichten (PO-go 2026-07-09)

Ersetzt die alte Absolutform von „KEINE MOCKED TESTS". Unverändert verboten bleibt **Mock-Theater**: `Mock()`/`patch()`/`MagicMock`, die nur die eigene Annahme zurückspiegeln, beweisen nichts. Ebenso verboten bleiben Dateiinhalt-Checks (`assert 'xyz' in file.read_text()`) als Verhaltensnachweis (Ausnahme: `# doc-compliance-test`).

| Schicht | Was | Wann | Regel bei Rot |
|---|---|---|---|
| **Kern (deterministisch)** | ohne Netz/Live-Dienste/echte Postfächer; echte **aufgezeichnete** API-/Mail-Daten als versionierte Fixtures erwünscht | jeder Testlauf; Commit-Gate | MUSS 100 % grün sein: sofort fixen ODER löschen (wenn er veraltetes Verhalten prüft) — nie als „vorbestehend rot" liegenlassen |
| **Live-E2E** | echte API-Calls, echte Staging-Mails via IMAP, Playwright gegen Staging (Marker `live`/`email`/`staging`) | nur `/e2e-verify` bzw. Deploy | Flake → Retry; erst reproduzierbares Scheitern ist ein Befund (→ #1199 bzw. #1196) |

Bug-Nachweis unverändert: mindestens ein Test reproduziert den Bug aus Nutzersicht (rot vor Fix, grün nach Fix) — in der Live-Schicht, wenn er Staging braucht, sonst im Kern.

**Namensregel (neu):** Testdateien nach Verhalten benennen (`test_alert_throttle.py`), NICHT nach Issue-Nummer (`test_issue_1234.py`). Nach dem Fix wird der Repro-Test in die passende Modul-Suite überführt oder gelöscht — der Issue-Nummern-Korpus (Bestand: 262 Dateien) wächst nicht weiter. Bestandssanierung: #1196. **Hart durchgesetzt** via `test_naming_gate.py` (blockt neue issue-nummerierte Testdateien; Prüfdatum 2026-10-09).

## Nebenbefund-Triage (PO-go 2026-07-09, ersetzt „immer Folge-Issue")

Nebenbefunde aus Workflows/Adversary-Läufen werden NICHT mehr automatisch eigene Issues. **Eigenes Issue nur bei:** (a) nutzersichtbarem Fehlverhalten, (b) Datenverlust-/Sicherheitsrisiko, (c) fälschlich blockierendem Gate. **Alles andere** → eine Checkbox-Zeile im rollierenden Sammel-Issue **#1199** (Format dort beschrieben). Test-/Gate-Befunde gehören in #1196/#1197, solange diese offen sind. Einträge ohne PO-Bestätigung verfallen nach 30 Tagen. Adversary-Findings der Stufe LOW/kosmetisch sind per Default Sammel-Einträge, keine Issues.

## Regel-Budget (Ratsche-Gegengewicht, PO-go 2026-07-09)

Jede neue Pflicht-Regel, jedes neue Gate, jeder neue Pflicht-Validator muss beim Einführen entweder **eine bestehende Regel ersetzen** oder ein **Prüfdatum (+90 Tage)** tragen. Am Prüfdatum gilt: kein nachweisbarer Fang (verhinderter echter Fehler) → Rückbau. Gate-Befunde, die keine Arbeit blockieren, sind Sammel-Einträge (#1199), keine Issues. Bestandsaudit aller Gates: #1197. Hintergrund und Wirkmodell: `docs/analysis/backlog-spirale-2026-07.md`.

## E2E-Verifikation (Post-Push auf Staging)

Verifikation läuft **nach** dem Push gegen Staging (`https://staging.gregor20.henemm.com`) — **nie** durch lokalen Neustart des Live-Servers (= Produktion). Issue #339.

**Ablauf:** Push → ~5 Min Staging-Auto-Deploy → `/e2e-verify` → `deploy-gregor-prod.sh` → Post-Deploy-Selftest (#564) → Issue close. Prod-Deploy ist Hard Gate: blockt, wenn `e2e_verified.json[verified_commit]` ≠ HEAD oder `staging_verdict` nicht mit `VERIFIED` beginnt (#521).

**VERBOTEN:** lokalen Live-Server stoppen/neustarten · Sammel-Versand über alle Touren (nur Test-Trip) · „E2E bestanden" ohne Staging-Verifikation sagen.

Detailablauf, Verdict-Ableitung PASS/PARTIAL/FAIL/SKIP, Rollback: **`docs/reference/operations_playbook.md`**. Kern: **Issue-Close nur bei Selftest-Exit 0**.

## Mail-Validatoren & Renderer-Gate (ZWINGEND)

Zwei Mail-Pfade, zwei Gates. Falscher Validator auf einen Pfad → strukturell nie bestehbar → Gate-Erosion. Dispatch:

| Mail-Pfad | Validator (PFLICHT vor „E2E bestanden") | Marker-Header |
|---|---|---|
| **Orts-Vergleich** (Vergleichsmatrix, Winner-Box, ≥3 Orte) | `uv run python3 .claude/hooks/email_spec_validator.py` | `X-GZ-Mail-Type: compare` |
| **Trip-Briefing** (`full`/`compact`, Stundentabellen) | `uv run python3 .claude/hooks/briefing_mail_validator.py` | `X-GZ-Mail-Type: trip-briefing` + `X-GZ-Format: full\|compact` |

**Regeln:** gegen **echt zugestellte Staging-Mail** aus Stalwart-Test-Postfach (`gregor-test@henemm.com`, Creds `GZ_IMAP_*`, nie im Klartext) — kein Mock, kein Gmail. Geprüft wird Plausibilität, nicht bloße String-Presence. **Nur bei Exit 0** darf „E2E bestanden" gesagt werden.

**Renderer-Commit-Gate (#811, un-überspringbar):** `renderer_mail_gate.py` blockiert jeden Commit, der eine Mail-Inhalts-Datei staged (`src/output/renderers/email/*.py`, `src/output/renderers/{trip_report,sms_trip,compact_summary}.py`, `src/output/renderers/alert/*.py`, `src/output/channels/email.py`), bis im aktiven Workflow **beide** frisch vorliegen: (1) `tests/tdd/test_issue_811_mode_matrix.py` grün, (2) erfolgreicher `briefing_mail_validator.py`-Lauf. Abhilfe bei Blockade: `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` ausführen, dann Validator grün bekommen.

Details (Plausibilitäts-Schwellen, Anti-Stale-Mechanik, Historie): **`docs/reference/mail_validators.md`**.

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

**GitHub Issues ist die Single Source of Truth für offene Arbeit:** https://github.com/henemm/gregor_zwanzig/issues

- Neue Features → Issue Label `enhancement`; neue Bugs → Label `bug`; fertig → Issue schließen
- Root-Cause-Analysen → `docs/project/known_issues.md`; strategische Entscheidungen → `docs/project/strategic-directions.md`
- **NICHT MEHR in Markdown-Dateien planen!** Offene Features/Bugs/Sprint-Planung gehören auf GitHub Issues.

## Pre-Test Validierung (PFLICHT!)

**Vor jeder Testaufforderung an den User:** `python3 .claude/validate.py` prüft Syntax + Import geänderter Python-Dateien + Server-Startup. Erst bei allen Checks grün den User zum Testen auffordern; danach `python3 .claude/validate.py --clear`.

**NIEMALS "teste es" ohne vorherige Validierung!**

## Daten-Schema-Reworks (PFLICHT!)

**Bestandsdaten bei Persistenz-Änderungen MÜSSEN erhalten bleiben.** Regel: **Read-Modify-Write mit Merge** — bestehendes Objekt laden, nur geänderte Felder überschreiben. **Niemals Replace** (Client-unbekannte Felder gehen sonst verloren). Hintergrund: BUG-DATALOSS-GR221 (#102), 3 von 4 Stages verloren.

**Schema-relevante Dateien:** `src/app/models.py`, `src/app/trip.py`, `src/app/loader.py`, `internal/model/*.go`, `internal/store/store.go` — Edits lösen automatisch den Pre-Snapshot-Hook `data_schema_backup.py` aus (tar.gz nach `.backups/`, Retention 20).

Migration + Roundtrip-Test, Rollback, Anti-Pattern-Beispiele: **`docs/reference/operations_playbook.md`**.

## Session-Artefakte mit Tokens: NIE weltlesbar nach /tmp (Security #199)

Cookiejars, `storageState`, Auth-Responses u.ä. enthalten Session-Tokens (`gz_session`). **Verboten:** `curl -c /tmp/xyz.txt` o.ä. mit Default-Rechten. **Stattdessen:** ins Session-Scratchpad-Verzeichnis schreiben (ist privat) ODER vorher Datei mit `install -m 600 /dev/null <pfad>` anlegen bzw. `umask 077` setzen. Playwright-`storageState` gehört nach `frontend/e2e/playwright/.auth/` (gitignored), nie nach `/tmp`. Hintergrund: henemm-security #199 — world-readable Tokens in /tmp; infra-Monitor härtet nur kompensierend nach. (Prüfdatum-Regelbudget: Konvention statt neuem Gate; Gate nur bei Wiederauftreten.)

## Parallele Sessions

**Ein Projektordner = höchstens eine Claude-Session gleichzeitig** (kollidierende Dateien/WIP/Workflow-Buchführung). Der Session-Wächter erzwingt bei einer zweiten Sitzung `EnterWorktree`:

```bash
bash .claude/tools/gz-workspace new <name>   # isolierter Klon auf Branch ws/<name>
bash .claude/tools/gz-workspace list         # alle Workspaces mit Branch + uncommitted-Zähler
bash .claude/tools/gz-workspace clean <name> # entfernen (nur wenn sauber; --force erzwingt)
```

**Regel:** jede Session liefert **unabhängig** aus, Integrationspunkt ist `origin/main`. Nur Staging-validiertes Grünes wird gepusht → `main` ist immer auslieferbar → Deploy (`deploy-gregor-prod.sh`, `flock`-serialisiert) darf aus jeder Session jederzeit laufen. **Verboten:** Deploy aufschieben „bis der Ordner sauber ist" — diese Pattsituation existiert nicht mehr.

Detailablauf, WIP-Sicherung beim Deploy: **`docs/reference/operations_playbook.md`**.

## Deployment & Infrastruktur

Globale Server-Infos und Monitoring: `~/.claude/CLAUDE.md`.

- **Production:** https://gregor20.henemm.com — Systemd (`gregor-python.service`, `gregor-api`, `gregor-frontend`)
- **Staging:** https://staging.gregor20.henemm.com — Systemd (`gregor-python-staging`, `gregor-api-staging`, `gregor-frontend-staging`)
- **Infrastruktur-Repo:** `henemm/henemm-infra`

### Post-Push-Workflow (PFLICHT)

| Schritt | Was |
|---|---|
| 1 | `git push origin main` |
| 2 | Auto-Deploy auf Staging abwarten (~5 Min, Cron `*/5`) |
| 3 | Staging-Validierung (s.u.) |
| 4 | Prod-Deploy: `bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` |
| 4b | Post-Deploy-Selftest: `python3 .claude/hooks/prod_selftest.py` — nur Exit 0 fährt weiter |
| 5 | `gh issue close <N>` — nur wenn 4b Exit 0 |

`systemctl restart` allein **reicht nie** — das Deploy-Script macht flock-Lock → hart auf `origin/main` syncen (Daten unberührt, WIP gesichert) → Go-Binary + Frontend bauen → alle 3 Services restarten → Smoke-Test. Ohne vollen Lauf entsteht Code-Drift, den `check-gregor20.sh` meldet (#113). Script ist **parallel-session-sicher** (`flock`) — Schritt 4 jederzeit aus jeder Session.

**„Staging-validiert"** = mindestens: HTTP-Smoke (`/` → 200/302, `/api/health` → 200) + geänderte Funktion manuell/Playwright durchgeklickt; bei Mail-Änderungen Test-Mail + IMAP-Verifikation; bei Scheduler-Änderungen `last_run` geprüft.

**Ausnahme reine Doku-/Tooling-Änderungen** (nur `.md`/`docs/`/`.claude/`/`.gitignore`, kein Code in `src/`/`api/`/`internal/`/`frontend/`/`cmd/`): Schritt 3 entfällt, Schritt 4 entfällt solange Drift-Monitor ruhig ist. Im Zweifel trotzdem deployen. Volle Definitionen: **`docs/reference/operations_playbook.md`**.

## Monitoring

Externes Monitoring über `henemm-infra/check-gregor20.sh`. Interner Heartbeat vom Scheduler an BetterStack ist optional (fail-soft bei leeren `GZ_HEARTBEAT_*`-Vars) — dann geht einmalig eine MQ-Nachricht an `infra`.

**Status-Endpoint:** `/api/scheduler/status` (gregor-api, Port 8090) — pro Job `next_run`/`last_run` (Status, Fehler).

**PFLICHT bei neuen Services/Schedulern:** `last_run`-Tracking im Status-Endpoint — kein Job ohne Observability!

## Design-Leitprinzipien (PO-bestätigt 2026-05-25)

**Hoher Kontrast = Lesbarkeit.** Bei Konflikt zwischen "weicher Optik" und "klarer Lesbarkeit" gewinnt **Lesbarkeit** — das Produkt ist ein Briefing-Werkzeug für Wetter-/Tourenentscheidungen, Inhalt muss unter Zeitdruck lesbar sein. Steht über ästhetischen Präferenzen.

Konsequenzen (Quelle: `docs/design-requests/issue_15_atomic_design/RESPONSE-FROM-CLAUDE-DESIGN.md`):
- Karten = weiß (`--g-card #ffffff`) auf warmer Off-White-Page (`--g-paper #f6f4ee`). Kein beiges Card-on-beige.
- Text-Kontrast mindestens WCAG-AA (4.5:1). `--g-ink-4` strikt nur Placeholder/Disabled, nie Captions/Help-Text/Daten-Labels (nur 2.85:1 auf Weiß).
- Akzent-Farben sparsam, nie alleiniger Lesbarkeits-Träger — Form + Position + Mono-Strecke tragen mit.

Folge-Arbeit: Surface-Stack-Migration (vor Atom-Migration) → Token-Rename → Atom-Migration (Epic #368). Kontrast-Audit (#16) parallel möglich.

## Signal als Channel — ENTFERNT (2026-06-06, Issue #610)

Kanäle sind nur noch **E-Mail · Telegram · SMS**. Frontend + Backend bereinigt: keine Kanal-Auswahl, keine `SignalOutput`, kein `signal_text`/`send_signal`, kein `/api/preview/{trip}/signal`. Callmebot-Infrastruktur existiert weiter serverseitig für andere Dienste, aber nicht mehr für Gregor Zwanzig. Wiedereinführung müsste neu spezifiziert werden.

## Confidence (Vorhersage-Verlässlichkeit) — NICHT wählbar als Metrik (2026-06-10, Issue #710)

**`confidence_pct` ist KEINE pro-Etappe wählbare Wetter-Metrik** — eine Meta-Aussage über mehrtägige Ensemble-Divergenz, keine lokale Wettergröße. Darf ausschließlich erscheinen als: (1) Vorhersage-Verlässlichkeits-Hinweis im E-Mail-Textblock, (2) SMS-Token (C+/C~/C? für Sicherheit-Bands), (3) interne Aggregation/Scoring. **NIEMALS** im Trip-Editor, Wizard Step 3, Metrik-Auswahl oder als per-Etappe-Spalte.

**Implementierung:** `MetricDefinition.selectable=false`; GET `/api/metrics` filtert auf `selectable=true`. Alte Trips mit aktiviertem `confidence` laden still, Metrik wird in Render-Pfaden ignoriert. **PO-Entscheidung, Final** — verhindert Regress wie #710/#473.

## Messaging

Diese Instanz heißt `gregor`. Siehe `~/.claude/CLAUDE.md` → "Inter-Instance Messaging" für Details.

# Compact instructions

Diese Sektion wird von `/compact` automatisch als Zusammenfassungs-Anleitung gelesen. Sie greift bei jedem `/compact` — nie einen langen `/compact <Text>` tippen, einfaches `/compact` genügt.

Bei aktivem OpenSpec-Workflow (`GZ_ACTIVE_WORKFLOW` gesetzt) beim Komprimieren IMMER bewahren:

- **Workflow-Identität:** Issue-Nummer, Workflow-Name, aktuelle Phase
- **Spec & Akzeptanz:** freigegebene ACs, Designentscheidungen aus der Analyse-Phase
- **TDD-Stand:** rote Tests + warum (Bug-Reproduktion aus Nutzersicht), Source-/Test-Dateipfade, RED-Artefakt-Pfade, LoC-Limit
- **Implementierung & QA:** geänderte Dateien, Adversary-Verdict, offene Fix-Loop-Punkte
- **Deploy-relevant:** Scope (frontend-only vs. full-stack), `verified_commit`-Status, Staging-Verdict

Verwerfen: rohe Tool-Output-Dumps, allgemeines Hin-und-Her, Implementierungs-Detail-Diskussionen die bereits in Code/State-Dateien (`.claude/workflows/<name>.json`, `e2e_verified.json`, `docs/artifacts/`) stehen.
