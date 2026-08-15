# CLAUDE.md - Gregor Zwanzig

> Diese Datei wird bei **jeder** Modell-Anfrage mitgeladen. Sie enthält nur Entscheidungen und Fakten,
> die man sonst nicht wissen kann. Detailmechanik von Gates, Ratschen und Betriebsabläufen steht in
> `docs/reference/` und wird bei Bedarf gelesen — **nicht** hier einpflegen.

## Projekt-Ueberblick

**Gregor Zwanzig** ist ein Headless-Service zur Normalisierung von Wetterdaten und Ausgabe als kompakte Reports (SMS <=160 Zeichen, E-Mail mit Tabellen).

- **Zielgruppe:** Weitwanderer (z.B. GR20), eingeschraenkte Konnektivitaet
- **Stack:** Python, uv, pytest
- **Kanäle (vier):** E-Mail · Telegram · SMS · **Premium-SMS** (Garmin inReach, ADR-0049). Signal ist seit 2026-06-06 app-weit entfernt (#610) — kein `SignalOutput`/`signal_text`/`send_signal`, kein `/api/preview/{trip}/signal`; Wiedereinführung müsste neu spezifiziert werden.
- **🔴 Alle vier Kanäle sind gleichrangig relevant — kein Kanal ersetzt einen anderen.** PO-Vorgabe, mehrfach bekräftigt: Auf dem Karnischen Höhenweg gibt es **auf der Hütte nur Satellit** — und das ist genau die Zeit, zu der Briefings verschickt werden, weshalb dort **nur Premium-SMS** ankommt. **Auf dem Pass gibt es normalen Handyempfang, dort sind E-Mail und Telegram relevant** und werden gelesen. Wer daraus „E-Mail/Telegram sind für die Tour nachrangig" folgert, liegt falsch. Alarme müssen **alle** Kanäle erreichen (#1701).
- **Premium-SMS-Reichweite:** als **Versandkanal** nur im **Trip-Briefing** verdrahtet (kein Ortsvergleich-Versand). Als **Alarm-Kanal** in **beiden** Flächen (Trip UND Ortsvergleich), für **alle** Alarmarten inklusive Regen-/Radar-Alarme — alles über dieselbe geteilte Kanal-Auflösung (Paritäts-Audit #1533).
- **Multi-User-Produkt:** mandantenfähig — jeder Nutzer hat eigene Trips, Orte, Orts-Vergleiche, Empfänger und Settings. Persistenz pro Nutzer unter `data/users/<user_id>/`. Isolation **konsequent** über `s.WithUser(middleware.UserIDFromContext(r.Context()))` (Go) bzw. `user_id`-Parameter (Python). **PFLICHT bei jedem nutzerbezogenen Endpoint:** echte `user_id` aus Auth-Kontext durchreichen, **niemals** auf `"default"` zurückfallen — das ist ein Cross-User-Datenleck. Jeder neue datenbewegende Endpoint MUSS mit **zwei verschiedenen Nutzern** getestet werden. Es gibt kein systemseitiges „an mich" — „senden" heißt immer „an die konfigurierten Empfänger dieses Nutzers".

## Architektur

Verteiltes System, drei Prozesse:

```
SvelteKit-Frontend  ->  Go-API (Port 8090)  ->  Python-Core (FastAPI, intern Port 8000)
                        Auth/Store/Scheduler     Provider -> Risk Engine -> Renderer -> Channel
```

- **Go-API** (`internal/`, `cmd/`): Auth/Sessions, Mandantentrennung, Persistenz (`data/users/<user_id>/`), Cron-Scheduler, Proxy zum Python-Core
- **Python-Core** (`api/`, `src/`): Wetter-Domäne (Provider Open-Meteo + Fallbacks, Risk Engine, Aggregation), alle Kanal-Renderer/-Transporte, Alerts, Inbound-Handler
- Die Legacy-CLI (`python -m src.app.cli`, Priorität CLI > ENV > config.ini) ist Debug-Werkzeug, nicht der Produktivpfad

## Wichtige Referenzen

| Dokument | Beschreibung |
|----------|--------------|
| `docs/features/architecture.md` | Systemarchitektur (Backend + Frontend + Editoren) |
| `docs/reference/api_contract.md` | Single Source of Truth: DTOs & Datenformate |
| `docs/reference/operations_playbook.md` | Deploy, Rollback, Staging-Verdicts, Datenmigration |
| `docs/reference/gates_und_ratschen.md` | **Detailmechanik aller Gates/Ratschen** — bei Blockade hier nachsehen |
| `docs/reference/mail_validators.md` | Plausibilitäts-Schwellen, Anti-Stale-Mechanik |
| `docs/reference/decision_matrix.md` | Provider-Ist-Stand (Open-Meteo + Fallback-Kette) |
| `docs/features/epic-134-cockpit-dashboard.md` | Trip-Cockpit-Startseite |
| `docs/adr/README.md` | Index der Architektur-Entscheidungen |
| `docs/README.md` | Wegweiser durch docs/ (Referenz vs. Archiv) |

**ADRs:** `docs/adr/` hält die Grundsatzentscheidungen fest — **vor Änderungen an Entscheidungsflächen** (Kanäle, Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie) dort nachsehen. Eine dokumentierte Entscheidung wird nie still rückgängig gemacht: Abweichung ⇒ neues ADR (Status „Abgelöst durch"). Index↔Datei-Konsistenz erzwingt `tests/test_adr_index_drift.py`.

**Specs:** Alle Module brauchen eine Spec vor der Implementierung. Template `docs/specs/_template.md`, Ablage `docs/specs/modules/[entity].md`. Jede Spec `created >= 2026-05-11` braucht `## Acceptance Criteria` mit `**AC-1:** Given.../When.../Then...` (>=30 Zeichen), sonst blockt `workflow_gate` Phase 6.

## Workflow

OpenSpec-Workflow mit Adversary Verification (Einstiege: `/00-intake`, `/00-bug`, `/01-feature`):

| Command | Purpose | PO-Eingriff |
|---------|---------|-------------|
| `/10-context` | Kontext sammeln | — |
| `/20-analyse` | Request verstehen, Codebase recherchieren | Optional: 3-Satz-Zusammenfassung korrigieren |
| `/30-write-spec` | Spezifikation erstellen | **Pflicht: ACs auf Deutsch freigeben** ('go') |
| `/40-tdd-red` | Fehlschlagende Tests schreiben (RED) | Optional: AC-Test-Mapping lesen |
| `/50-implement` | Implementieren (GREEN) + Adversary | — |
| `/60-validate` | Validieren vor Commit | — |
| `/70-deploy` | Staging-Verifikation + Prod-Deploy | — (läuft autonom, **kein** Freigabe-Halt) |

**Freigabepflichtig ist allein die Spec.** Deploy läuft ohne Halt durch: nach dem Merge zieht die Kette Staging-Poll → `/e2e-verify` → `deploy-gregor-prod.sh` → `prod_selftest.py` → Issue-Close **am Stück**. Der PO liest das Ergebnis danach, nicht vorher als Freigabe. Ein selbst formulierter „Tech-Lead-Brief" mit anschließender Bitte um 'go' ist dieselbe verbotene Prozessfrage in Freitextform. Einzige erlaubte Unterbrechung: ein echtes Hard Gate scheitert (Staging-Verdict BROKEN, Selftest-Exit ≠ 0) — dann eskalieren mit konkretem Befund.

**Adversary Verification:** Nach der Implementation führt ein unabhängiger `implementation-validator` (Sonnet) einen strukturierten Dialog, um die Implementierung aktiv zu brechen. Tri-State Verdict: VERIFIED / BROKEN / AMBIGUOUS. Details: `docs/features/openspec_workflow.md`. Bei Findings ist `Code reference: file:line` Pflicht.

**🔴 Mutations-Gegenprobe ist PFLICHT, keine Kür.** Der Adversary muss die Implementierung gezielt verfälschen und melden, **welche Verfälschung KEIN Test fängt** — wird kein Test rot, ist das ein Finding. Ein grüner Testlauf beweist nur, dass die Tests durchlaufen, nicht dass sie etwas bewachen. Leitfrage: **Ist die Zusicherung an der Stelle geprüft, an der sie WIRKT — oder nur dort, wo der Code steht?** Ablauf und Mutations-Familien: `.claude/agents/implementation-validator.md`, Sektion „Step 3b". **Mutationen nur per String-Ersetzung mit externer Sicherungskopie — nie `git checkout/stash/reset`** (hat einmal die gesamte unkommittete Arbeit gelöscht).

**Fresh Eyes:** Bei UI-Änderungen prüft zusätzlich ein `fresh-eyes-inspector` Screenshots OHNE Bug-Kontext.

**Product Owner Pattern:** Main Context (Opus) ist reiner Orchestrierer und schreibt KEINEN Code. Implementierung geht an den Developer Agent (Opus, Worktree-Isolation). >10 Min ohne grüne Tests → `TaskStop` + Neustart mit präziserem Briefing; max 2 Versuche, danach Eskalation.

**Agenten-Modelle:** `developer` Opus · `bug-intake`/`feature-planner`/`implementation-validator`/`spec-writer`/`fresh-eyes-inspector` Sonnet · `docs-updater`/`spec-validator`/Explore Haiku.

### Workflow-State

| Was | Regel |
|-----|-------|
| **GZ_ACTIVE_WORKFLOW** | `export GZ_ACTIVE_WORKFLOW=<name>` ist die EINZIGE erlaubte Methode. **Symlink-Fallback ist deaktiviert** — `workflow.py` bricht FATAL ab ohne die Variable. Niemals `state['active_workflow']` lesen. Beim Agent-Spawn immer im Prompt übergeben. |
| **Execution-Log vor `finish`** | `python3 .claude/hooks/workflow.py write-log success`, dann `workflow.py finish`. Ohne Log blockt der Hook. |
| **LoC-Limit 250/Workflow** | `workflow.py status` zeigt `LoC-Delta: +N/250`. Überschritten → `workflow.py set-field loc_limit_override 500`. `docs/`/`*.md`/`.gitignore` und generierte Dateien zählen nicht. |
| **Adversary-Verdict Gating** | `AMBIGUOUS` → `workflow.py override-ambiguous "<Grund>"` (TTL 1h); `None`/`BROKEN` → `qa_gate.py`. Commit blockt ohne Verdict. |
| **State-Ablage** | `.claude/workflows/<name>.json` (laufend) / `_archive/<name>.json` (abgeschlossen) |

**Hooks erzwingen diesen Workflow** — Edit/Write auf geschützte Dateien ist blockiert. Blockiert ein Gate und die Meldung reicht nicht: `docs/reference/gates_und_ratschen.md`.

## Test-Politik: Zwei Schichten

Verboten bleibt **Mock-Theater**: `Mock()`/`patch()`/`MagicMock`, die nur die eigene Annahme zurückspiegeln, beweisen nichts. Ebenso verboten sind Dateiinhalt-Checks (`assert 'xyz' in file.read_text()`) als Verhaltensnachweis (Ausnahme: `# doc-compliance-test`).

| Schicht | Was | Wann | Regel bei Rot |
|---|---|---|---|
| **Kern (deterministisch)** | ohne Netz/Live-Dienste/echte Postfächer; echte **aufgezeichnete** API-/Mail-Daten als versionierte Fixtures erwünscht | jeder Testlauf; Commit-Gate | MUSS 100 % grün sein: sofort fixen ODER löschen (wenn er veraltetes Verhalten prüft) — nie als „vorbestehend rot" liegenlassen |
| **Live-E2E** | echte API-Calls, echte Staging-Mails via IMAP, Playwright gegen Staging (Marker `live`/`email`/`staging`) | nur `/e2e-verify` bzw. Deploy | Flake → Retry; erst reproduzierbares Scheitern ist ein Befund (→ #1199 bzw. #1196) |

Bug-Nachweis: mindestens ein Test reproduziert den Bug aus Nutzersicht (rot vor Fix, grün nach Fix) — in der Live-Schicht, wenn er Staging braucht, sonst im Kern.

**Testdateien nach Verhalten benennen** (`test_alert_throttle.py`), NICHT nach Issue-Nummer. **`uv run pytest` ohne benannte Testdateien ist gesperrt** — ein ungemarkerter Test genügt für echten Versand an Produktiv-Empfänger (#1477). Erlaubt: Dateien benennen · `--collect-only` · `--disable-socket` · Einmal-Freigabe, die **nur der User** durch Tippen von `override` erzeugt. Ein Test löst seinen Prüfling **relativ zur eigenen Testdatei** auf, nie über den festen Hauptrepo-Pfad (sonst falsches Grün aus dem Worktree).

Durchsetzung, Ausnahme-Syntax und Grenzen: `docs/reference/gates_und_ratschen.md`.

## E2E-Verifikation & Deploy

Verifikation läuft **nach** dem Push gegen Staging (`https://staging.gregor20.henemm.com`) — **nie** durch lokalen Neustart des Live-Servers (= Produktion). Issue #339.

**Ablauf:** Push → ~5 Min Staging-Auto-Deploy → `/e2e-verify` → `deploy-gregor-prod.sh` → Post-Deploy-Selftest → Issue close. Prod-Deploy ist Hard Gate: blockt ohne bestandenen, frischen Nachweis für den Zielstand (`.claude/e2e_verified/<sha>.json`, eine Datei je Stand).

**VERBOTEN:** lokalen Live-Server stoppen/neustarten · Sammel-Versand über alle Touren (nur Test-Trip) · „E2E bestanden" ohne Staging-Verifikation sagen.

**Issue-Close nur bei Selftest-Exit 0.** Verdict-Ableitung, Rollback: `docs/reference/operations_playbook.md`. Gate-Mechanik (Frontend-Browser-Gate, Notausgänge, Zugangsdaten-Quellen): `docs/reference/gates_und_ratschen.md`.

### Liefer-Workflow (PFLICHT — PR statt Direkt-Push)

**Direkt-Push auf `main` ist abgeschafft.** `main` ändert sich nur per Pull Request mit vollständig grüner CI-Ampel.

| Schritt | Was |
|---|---|
| 1 | Arbeitsbranch pushen: `git push -u origin <branch>` (nie direkt `main`) |
| 1b | PR eröffnen (`gh pr create --fill`), CI-Ampel abwarten — **alle 6 Checks grün** auf dem letzten Stand |
| 1c | Mergen (`gh pr merge --merge`) — erst damit ist `main` aktualisiert |
| 2 | Auto-Deploy auf Staging abwarten (~5 Min, Cron `*/5`) |
| 3 | Staging-Validierung |
| 4 | Prod-Deploy: `bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` |
| 4b | Post-Deploy-Selftest: `python3 .claude/hooks/prod_selftest.py` — nur Exit 0 fährt weiter |
| 5 | `gh issue close <N>` — nur wenn 4b Exit 0 |

Wird ein Push nach `main` abgewiesen, ist das die Branch-Protection, kein Fehler. Ein PR ersetzt NICHT die Staging-Validierung — die Ampel bewacht Code-Gesundheit, Staging bewacht Verhalten.

`systemctl restart` allein **reicht nie** — das Deploy-Script macht flock-Lock → hart auf `origin/main` syncen (Daten unberührt, WIP gesichert) → Go-Binary + Frontend bauen → alle 3 Services restarten → Smoke-Test. Ohne vollen Lauf entsteht Code-Drift (#113). Script ist **parallel-session-sicher** — Schritt 4 jederzeit aus jeder Session.

**„Staging-validiert"** = mindestens HTTP-Smoke (`/` → 200/302, `/api/health` → 200) + geänderte Funktion durchgeklickt; bei Mail-Änderungen Test-Mail + IMAP-Verifikation; bei Scheduler-Änderungen `last_run` geprüft.

**Ausnahme reine Doku-/Tooling-Änderungen** (nur `.md`/`docs/`/`.claude/`/`.gitignore`, kein Code in `src/`/`api/`/`internal/`/`frontend/`/`cmd/`): Schritt 3 entfällt, Schritt 4 entfällt solange der Drift-Monitor ruhig ist.

### CI-Ampel & Merge-Regel

Die 6 GitHub-Actions-Checks (`test` · `lint` · `go-test` · `svelte-check` · `frontend-test` · `e2e`) sind die **CI-Ampel**.

- **Merge-Regel (PFLICHT):** Ein PR wird nur gemerged, wenn alle 6 Checks auf seinem letzten Stand grün sind. Fremde Rote auf der Basis: erst die Basis grün ziehen oder den Befund belegt (Commit-/Log-Nachweis) einer anderen Session zuordnen und in #1196 buchen — nie stillschweigend „auf Rot obendrauf" mergen.
- **Wird `main` trotzdem rot:** Drive-to-green hat Vorrang vor neuer Feature-Arbeit.
- **Branch-Protection ist beschlossen:** der dokumentierte Weg auf `main` ist ausschließlich der PR-Liefer-Workflow. Den mechanischen Schalter setzt der PO; bis dahin gilt die Regel organisatorisch und ein Direkt-Push ist ein Regelverstoß, kein Versehen.

Ratschen-Pflege (`ci_tdd_excludes.txt`, `ci_e2e_specs.txt`, Aufnahmefilter): `docs/reference/gates_und_ratschen.md`.

## Mail-Validatoren (ZWINGEND)

Zwei Mail-Pfade, zwei Gates. Falscher Validator auf einen Pfad → strukturell nie bestehbar → Gate-Erosion.

| Mail-Pfad | Validator (PFLICHT vor „E2E bestanden") | Marker-Header |
|---|---|---|
| **Orts-Vergleich** (Vergleichsmatrix, Winner-Box, ≥3 Orte) | `uv run python3 .claude/hooks/email_spec_validator.py` | `X-GZ-Mail-Type: compare` |
| **Trip-Briefing** (`full`/`compact`, Stundentabellen) | `uv run python3 .claude/hooks/briefing_mail_validator.py` | `X-GZ-Mail-Type: trip-briefing` + `X-GZ-Format: full\|compact` |

**Regeln:** gegen **echt zugestellte Staging-Mail** aus dem Stalwart-Test-Postfach (`gregor-test@henemm.com`, Creds `GZ_IMAP_*`, nie im Klartext) — kein Mock, kein Gmail. Geprüft wird Plausibilität, nicht bloße String-Presence. **Nur bei Exit 0** darf „E2E bestanden" gesagt werden.

Ein **Renderer-Commit-Gate** blockiert Commits an Mail-Inhalts-Dateien, bis Modus-Matrix-Test und Validator frisch grün sind — Details in `docs/reference/gates_und_ratschen.md`.

## Design-Leitprinzipien (PO-bestätigt 2026-05-25)

**Hoher Kontrast = Lesbarkeit.** Bei Konflikt zwischen „weicher Optik" und „klarer Lesbarkeit" gewinnt **Lesbarkeit** — das Produkt ist ein Briefing-Werkzeug für Wetter-/Tourenentscheidungen, Inhalt muss unter Zeitdruck lesbar sein. Steht über ästhetischen Präferenzen.

- Karten = weiß (`--g-card #ffffff`) auf warmer Off-White-Page (`--g-paper #f6f4ee`). Kein beiges Card-on-beige.
- Text-Kontrast mindestens WCAG-AA (4.5:1). `--g-ink-4` strikt nur Placeholder/Disabled, nie Captions/Help-Text/Daten-Labels (nur 2.85:1 auf Weiß).
- Akzent-Farben sparsam, nie alleiniger Lesbarkeits-Träger — Form + Position + Mono-Strecke tragen mit.

Quelle: `docs/design-requests/issue_15_atomic_design/RESPONSE-FROM-CLAUDE-DESIGN.md`. Folge-Arbeit: Surface-Stack-Migration → Token-Rename → Atom-Migration (Epic #368).

## Trip/Ortsvergleich-Code-Teilung (PO-Vorgabe, mehrfach bekräftigt)

**Möglichst viel Code zwischen Trip und Ortsvergleich teilen; der Compare-Editor funktioniert wie der Trip-Editor.** Als prüfbare Invariante:

- **Geteilt (EIN Code, Parameter `context="route"|"vergleich"`):** Editor-Rahmen (Progressive Tabs, Lock-Engine, Speichern/Verwerfen), Tab-Organismen Wertebereiche/Layout/Versand (`frontend/src/lib/components/shared/`), Muster Liste → Detail-Hub → Anlegen, Datenmodell-Konvergenz (Epic #1230).
- **Anlegen folgt dem Trip-Muster:** `/trips/new` = Progressive-Tab-Anlege-Seite aus geteilten Bausteinen (`TripNewEditor`, #622); der alte 5-Schritt-Wizard ist dort abgeschafft. `/compare/new` bekommt dieselbe Bauart; `CompareEditor.svelte` + Compare-Wizard sind Alt-Bestand und fallen ersatzlos. **Es gibt keine offene Designfrage dazu — nicht erneut vorlegen.**
- **Compare-eigen dürfen NUR sein:** Orte-Tab (statt Etappen), transponierte Übersicht (Orte = Spalten), Compare-Mail-Template.
- **Default-Fehler:** Eine neue Compare-Komponente, zu der ein Trip-Pendant existiert (oder umgekehrt), ist ein Verstoß — Ausnahme nur mit dokumentierter Begründung in der Spec. Anti-Pattern: #1170.
- **Prüfung:** Bei jeder Editor-/Detail-Arbeit ist „hätte das ein geteilter Baustein sein müssen?" expliziter Adversary-/Review-Punkt. Eine **Pendant-Sperre am Commit** setzt das für Neuanlagen durch (`docs/reference/gates_und_ratschen.md`).

## Confidence — NICHT wählbar als Metrik (Issue #710, Final)

**`confidence_pct` ist KEINE pro-Etappe wählbare Wetter-Metrik** — eine Meta-Aussage über mehrtägige Ensemble-Divergenz, keine lokale Wettergröße. Darf ausschließlich erscheinen als: (1) Vorhersage-Verlässlichkeits-Hinweis im E-Mail-Textblock, (2) SMS-Token (C+/C~/C? für Sicherheit-Bands), (3) interne Aggregation/Scoring. **NIEMALS** im Trip-Editor, Wizard Step 3, Metrik-Auswahl oder als per-Etappe-Spalte.

**Implementierung:** `MetricDefinition.selectable=false`; GET `/api/metrics` filtert auf `selectable=true`. Alte Trips mit aktiviertem `confidence` laden still, die Metrik wird in Render-Pfaden ignoriert.

## Daten-Schema-Reworks (PFLICHT!)

**Bestandsdaten bei Persistenz-Änderungen MÜSSEN erhalten bleiben.** Regel: **Read-Modify-Write mit Merge** — bestehendes Objekt laden, nur geänderte Felder überschreiben. **Niemals Replace** (Client-unbekannte Felder gehen sonst verloren). Hintergrund: BUG-DATALOSS-GR221 (#102), 3 von 4 Stages verloren.

**Schema-relevante Dateien:** `src/app/models.py`, `src/app/trip.py`, `src/app/loader.py`, `internal/model/*.go`, `internal/store/store.go` — Edits lösen automatisch den Pre-Snapshot-Hook `data_schema_backup.py` aus (tar.gz nach `.backups/`, Retention 20). Migration + Roundtrip-Test, Rollback, Anti-Pattern-Beispiele: `docs/reference/operations_playbook.md`.

## Backlog & Nebenbefunde

**GitHub Issues ist die Single Source of Truth für offene Arbeit.** Neue Features → Label `enhancement`; Bugs → Label `bug`; fertig → Issue schließen. **NICHT in Markdown-Dateien planen.** Root-Cause-Analysen → `docs/project/known_issues.md`; strategische Entscheidungen → `docs/project/strategic-directions.md`.

**Nebenbefund-Triage:** Nebenbefunde werden NICHT automatisch eigene Issues. **Eigenes Issue nur bei:** (a) nutzersichtbarem Fehlverhalten, (b) Datenverlust-/Sicherheitsrisiko, (c) fälschlich blockierendem Gate. **Alles andere** → Checkbox-Zeile im rollierenden Sammel-Issue **#1199**; Test-/Gate-Befunde in #1196/#1197. Einträge ohne PO-Bestätigung verfallen nach 30 Tagen. Adversary-Findings der Stufe LOW/kosmetisch sind per Default Sammel-Einträge.

**Regel-Budget:** Jede neue Pflicht-Regel, jedes neue Gate, jeder neue Pflicht-Validator muss beim Einführen entweder **eine bestehende Regel ersetzen** oder ein **Prüfdatum (+90 Tage)** tragen. Am Prüfdatum: kein nachweisbarer Fang → Rückbau. Prüfdaten-Tabelle: `docs/reference/gates_und_ratschen.md`. Wirkmodell: `docs/analysis/backlog-spirale-2026-07.md`.

## Betrieb

- **Production:** https://gregor20.henemm.com — Systemd (`gregor-python.service`, `gregor-api`, `gregor-frontend`)
- **Staging:** https://staging.gregor20.henemm.com — Systemd (`gregor-python-staging`, `gregor-api-staging`, `gregor-frontend-staging`)
- **Infrastruktur-Repo:** `henemm/henemm-infra`. Server-Infos und Monitoring: `~/.claude/CLAUDE.md`.

**Monitoring:** extern über `henemm-infra/check-gregor20.sh`. Status-Endpoint `/api/scheduler/status` (Port 8090) — pro Job `next_run`/`last_run`. **PFLICHT bei neuen Services/Schedulern:** `last_run`-Tracking im Status-Endpoint — kein Job ohne Observability.

**Pre-Test-Validierung:** Vor jeder Testaufforderung an den User `python3 .claude/validate.py` (Syntax + Import geänderter Python-Dateien + Server-Startup); danach `--clear`. **NIEMALS „teste es" ohne vorherige Validierung.**

**Session-Artefakte mit Tokens NIE weltlesbar nach /tmp** (Security #199): Cookiejars, `storageState`, Auth-Responses enthalten Session-Tokens. Verboten: `curl -c /tmp/xyz.txt` mit Default-Rechten. Stattdessen ins Session-Scratchpad (privat) schreiben ODER vorher `install -m 600 /dev/null <pfad>` bzw. `umask 077`. Playwright-`storageState` gehört nach `frontend/e2e/playwright/.auth/` (gitignored).

## Parallele Sessions & Token-Budget

**Ein Projektordner = höchstens eine Claude-Session gleichzeitig.** Der Session-Wächter erzwingt bei einer zweiten Sitzung `EnterWorktree`:

```bash
bash .claude/tools/gz-workspace new <name>   # isolierter Klon auf Branch ws/<name>
bash .claude/tools/gz-workspace list         # alle Workspaces mit Branch + uncommitted-Zähler
bash .claude/tools/gz-workspace clean <name> # entfernen (nur wenn sauber; --force erzwingt)
```

Jede Session liefert **unabhängig** aus, Integrationspunkt ist `origin/main` — erreicht ausschließlich per PR mit grüner Ampel. **Verboten:** Deploy aufschieben „bis der Ordner sauber ist".

**🔴 Kontext ist die teuerste Ressource (gemessen 2026-08-15).** 67 % des Token-Verbrauchs sind Wieder-Einlesen von Kontext, nicht erzeugter Text; Anfragen jenseits 200k Kontext machten 41 % der Anfragen und **66 % des Verbrauchs** aus. Daraus folgt, **unabhängig von der Auslastung**:

- **Nach jedem abgeschlossenen Ticket `/clear`** — nicht erst, wenn es eng wird. Bei neuem Thema selbst vorschlagen.
- **Bash-Aufrufe bündeln.** Jeder Aufruf ist ein voller Durchlauf mit dem gesamten bisherigen Kontext; drei zusammengehörige Kommandos in einem Aufruf kosten ein Drittel.
- **Breit suchen heißt delegieren.** Fan-out-Suchen an einen Explore-Agenten geben — dessen gelesene Dateien landen nicht im Hauptkontext.
- **Gezielt lesen** (`limit`/`offset`), nicht ganze Dateien „zur Sicherheit". Eine einmal gelesene Datei wird bei **jedem** folgenden Schritt erneut bezahlt.

Detailablauf, WIP-Sicherung beim Deploy: `docs/reference/operations_playbook.md`.

## Messaging

Diese Instanz heißt `gregor`. Siehe `~/.claude/CLAUDE.md` → „Inter-Instance Messaging".

# Compact instructions

Diese Sektion wird von `/compact` automatisch als Zusammenfassungs-Anleitung gelesen — nie einen langen `/compact <Text>` tippen, einfaches `/compact` genügt.

Bei aktivem OpenSpec-Workflow (`GZ_ACTIVE_WORKFLOW` gesetzt) beim Komprimieren IMMER bewahren:

- **Workflow-Identität:** Issue-Nummer, Workflow-Name, aktuelle Phase
- **Spec & Akzeptanz:** freigegebene ACs, Designentscheidungen aus der Analyse-Phase
- **TDD-Stand:** rote Tests + warum (Bug-Reproduktion aus Nutzersicht), Source-/Test-Dateipfade, RED-Artefakt-Pfade, LoC-Limit
- **Implementierung & QA:** geänderte Dateien, Adversary-Verdict, offene Fix-Loop-Punkte
- **Deploy-relevant:** Scope (frontend-only vs. full-stack), `verified_commit`-Status, Staging-Verdict

Verwerfen: rohe Tool-Output-Dumps, allgemeines Hin-und-Her, Implementierungs-Detail-Diskussionen, die bereits in Code/State-Dateien (`.claude/workflows/<name>.json`, `.claude/e2e_verified/<sha>.json`, `docs/artifacts/`) stehen.
