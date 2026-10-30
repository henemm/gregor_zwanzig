# CLAUDE.md - Gregor Zwanzig

> Wird bei **jeder** Modell-Anfrage mitgeladen: nur Entscheidungen und Fakten, die man sonst nicht wissen kann, je mit Verweis. Detailmechanik steht in `docs/reference/` (Wegweiser `docs/README.md`) und wird bei Bedarf gelesen, **nicht** hier einpflegen. Obergrenze 120 Zeilen / 12 KB (`tests/test_claude_md_budget.py`).

## Projekt-Ueberblick

**Gregor Zwanzig** ist ein Headless-Service zur Normalisierung von Wetterdaten und Ausgabe als kompakte Reports (SMS <=160 Zeichen, E-Mail mit Tabellen). Zielgruppe: Weitwanderer (z.B. GR20) mit eingeschraenkter Konnektivitaet. Stack: Python, uv, pytest.

- **Kanäle (vier):** E-Mail · Telegram · SMS · **Premium-SMS** (Garmin inReach, ADR-0049). Signal ist seit 2026-06-06 app-weit entfernt (#610, `docs/adr/0004-signal-channel-removed.md`); Wiedereinführung müsste neu spezifiziert werden.
- **Alle vier Kanäle sind gleichrangig relevant, kein Kanal ersetzt einen anderen** (PO-Vorgabe). Die Empfangslage unterwegs ist **unvorhersehbar** (PO-Korrektur 2026-09-05: auf der Hütte eher WLAN als Satellit, auf dem Pass normaler Handyempfang). Daher muss **jeder Kanal jede Frage beantworten können**, mit demselben Inhalt (Epic #2133); Alarme erreichen **alle** Kanäle (#1701). Wer „E-Mail/Telegram sind nachrangig" folgert, liegt falsch. Volltext: `docs/adr/0095-kanal-paritaet-jeder-kanal-jede-frage.md`.
- **Premium-SMS-Reichweite:** als **Versandkanal** im **Trip-Briefing** UND im **Ortsvergleich-Briefing** verdrahtet (#2275); als **Alarm-Kanal** in Trip UND Ortsvergleich für **alle** Alarmarten inkl. Regen-/Radar-Alarme, über dieselbe geteilte Kanal-Auflösung (Paritäts-Audit #1533).
- **Multi-User-Produkt:** jeder Nutzer hat eigene Trips, Orte, Orts-Vergleiche, Empfänger, Settings unter `data/users/<user_id>/`. Isolation über `s.WithUser(middleware.UserIDFromContext(r.Context()))` (Go) bzw. `user_id`-Parameter (Python). **PFLICHT:** echte `user_id` aus dem Auth-Kontext, **niemals** Fallback auf `"default"` (Cross-User-Datenleck). Jeder datenbewegende Endpoint wird mit **zwei verschiedenen Nutzern** getestet. „Senden" heißt immer „an die konfigurierten Empfänger dieses Nutzers", es gibt kein systemseitiges „an mich".

## Architektur

```
SvelteKit-Frontend  ->  Go-API (Port 8090)  ->  Python-Core (FastAPI, intern Port 8000)
                        Auth/Store/Scheduler     Provider -> Risk Engine -> Renderer -> Channel
```

Go-API (`internal/`, `cmd/`): Auth, Mandantentrennung, Persistenz, einziger Cron-Taktgeber (ruft `POST /api/scheduler/*`; der Python-Core entscheidet die Fälligkeit und versendet), Proxy. Python-Core (`api/`, `src/`): Wetter-Domäne, alle Kanal-Renderer/-Transporte, Alerts, Inbound. Die Legacy-CLI `python -m src.app.cli` (Priorität CLI > ENV > config.ini) ist Debug-Werkzeug. Details: `docs/features/architecture.md`.

## Wichtige Referenzen

| Dokument | Inhalt |
|---|---|
| `docs/reference/api_contract.md` | SSOT: DTOs & Datenformate |
| `docs/reference/operations_playbook.md` | Liefer-Workflow, Deploy, Rollback, Staging, Token-Budget, Betrieb |
| `docs/reference/gates_und_ratschen.md` | Detailmechanik aller Gates/Ratschen, Test-Politik, Prüfdaten |
| `docs/reference/workflow_und_agenten.md` | Workflow-Befehle, Agenten-Modelle, Workflow-State, Nebenbefund-Triage, Messaging |
| `docs/reference/mail_validators.md` | alle Mail-Validatoren, Marker-Header, Schwellen |
| `docs/reference/sms_format.md` · `telegram_format.md` · `premium_sms_format.md` · `renderer_email_spec.md` | Kanal-Formate |
| `docs/reference/decision_matrix.md` · `design_system.md` | Provider-Ist-Stand · Design |
| `docs/adr/README.md` | Architektur-Entscheidungen |

**ADRs:** vor Änderungen an Entscheidungsflächen (Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma, Test-/Deploy-Strategie) `docs/adr/` lesen. Eine Entscheidung wird nie still rückgängig gemacht: Abweichung ⇒ neues ADR („Abgelöst durch"); `tests/test_adr_index_drift.py` erzwingt Index-Konsistenz.

**Specs:** jedes Modul braucht eine Spec vor der Implementierung (`docs/specs/_template.md`, Ablage `docs/specs/modules/[entity].md`). Specs `created >= 2026-05-11` brauchen `## Acceptance Criteria` mit `**AC-1:** Given.../When.../Then...` (>=30 Zeichen), sonst blockt `workflow_gate` Phase 6.

## Workflow

OpenSpec-Workflow (`/00-intake` auch für Bugs, `/01-feature`, dann `/10-context` bis `/70-deploy`); Befehle, Agenten-Modelle, Workflow-State und PO-Pattern: `docs/reference/workflow_und_agenten.md`.

- **Freigabepflichtig ist allein die Spec** (ACs auf Deutsch, `approved`/`freigabe`). Deploy läuft danach ohne Halt durch (Staging-Poll → `/e2e-verify` → Prod-Deploy → Selftest → Issue-Close); ein „Tech-Lead-Brief" mit Bitte um 'go' ist dieselbe verbotene Prozessfrage. Einzige Unterbrechung: ein Hard Gate scheitert (Staging BROKEN, Selftest-Exit ≠ 0).
- **Rückfragen an den PO IMMER über das `AskUserQuestion`-Tool**, nie als Freitext-Frage (PO-Vorgabe 2026-10-08).
- **Main Context orchestriert und schreibt keinen Code**; Implementierung macht der Developer Agent im Worktree. Workflow-Variable ist `OPENSPEC_ACTIVE_WORKFLOW`, beim Agent-Spawn immer im Prompt übergeben.
- **Adversary + Mutations-Gegenprobe sind PFLICHT:** der `implementation-validator` verfälscht die Implementierung gezielt; eine Verfälschung, die kein Test fängt, ist ein Finding (Leitfrage: ist die Zusicherung dort geprüft, wo sie WIRKT?). Mutationen nur per String-Ersetzung mit externer Sicherungskopie, **nie `git checkout/stash/reset`**. Ablauf: `.claude/agents/implementation-validator.md`.

**Hooks erzwingen diesen Workflow.** Blockiert ein Gate und die Meldung reicht nicht: `docs/reference/gates_und_ratschen.md`.

## Test-Politik: Zwei Schichten

Verboten ist **Mock-Theater** (`Mock()`/`patch()`/`MagicMock`, die nur die eigene Annahme spiegeln) und Dateiinhalt-Checks als Verhaltensnachweis (Ausnahme `# doc-compliance-test`). Die Kern-Schicht (deterministisch, ohne Netz) muss immer 100 % grün sein, die Live-E2E-Schicht läuft nur in `/e2e-verify`/Deploy; ein Bug wird erst aus Nutzersicht rot nachgewiesen. **`uv run pytest` ohne benannte Testdateien ist gesperrt** (#1477); Testdateien nach Verhalten benennen, Prüfling relativ zur Testdatei auflösen. Tabelle und Ausnahmen: `docs/reference/gates_und_ratschen.md`.

## E2E-Verifikation & Deploy

Verifikation läuft **nach** dem Push gegen staging (`https://staging.gregor20.henemm.com`), **nie** durch lokalen Neustart des Live-Servers (= Produktion, #339). Prod-Deploy ist Hard Gate: braucht frischen Nachweis `.claude/e2e_verified/<sha>.json`; Issue-Close nur bei Selftest-Exit 0.

**Liefer-Workflow:** `main` ändert sich nur per Pull Request mit allen 6 CI-Checks grün (`test` · `lint` · `go-test` · `svelte-check` · `frontend-test` · `e2e`), Direkt-Push ist abgeschafft. PR, Merge (`gh pr merge --merge --delete-branch`) und Deploy (`deploy-gregor-prod.sh` + `prod_selftest.py`) macht Claude selbst, nie der PO (überstimmt bewusst die Vorlage von `/60-validate`). Merge-Regel, Schritte, Doku-Ausnahme und Verbote: `docs/reference/operations_playbook.md`.

## Mail-Validatoren & Renderer-Gate

Je Mail-Pfad ein eigener Validator, gegen **echt zugestellte Staging-Mail** im Stalwart-Test-Postfach (kein Mock, kein Gmail). Falscher Validator auf einem Pfad ist strukturell nie bestehbar.

- **Orts-Vergleich** (Vergleichstabelle, ≥3 Orte, `X-GZ-Mail-Type: compare`): `uv run python3 .claude/hooks/email_spec_validator.py`; „E2E bestanden" für den Orts-Vergleich nur bei Exit 0.
- **Trip-Briefing** (`full`/`compact`): eigener `briefing_mail_validator.py`; amtliche Warnung: `official_alert_mail_validator.py`; Radar-/Regen-Alarm: `radar_alert_mail_validator.py`.

Ein Renderer-Commit-Gate blockt Commits an Mail-Inhalts-Dateien bis Modus-Matrix-Test und Validator frisch grün sind. Details: `docs/reference/mail_validators.md`, `docs/reference/gates_und_ratschen.md`.

## Design-Leitprinzip

**Hoher Kontrast = Lesbarkeit** gewinnt gegen weiche Optik (WCAG-AA, PO-bestätigt 2026-05-25); Details: `docs/reference/design_system.md`.

## Trip/Ortsvergleich-Code-Teilung (PO-Vorgabe, mehrfach bekräftigt)

Möglichst viel Code zwischen Trip und Ortsvergleich teilen; der Compare-Editor funktioniert wie der Trip-Editor. Geteilt (EIN Code, Parameter `context="route"|"vergleich"`): Editor-Rahmen, Tab-Organismen Wertebereiche/Layout/Versand (`frontend/src/lib/components/shared/`), Muster Liste → Detail-Hub → Anlegen, Datenmodell (Epic #2345). Anlegen folgt dem Trip-Muster (`/trips/new` = `TripNewEditor`, #622; `/compare/new` gleich gebaut) — **keine offene Designfrage, nicht erneut vorlegen.** Compare-eigen dürfen NUR sein: Orte-Tab, transponierte Übersicht, Compare-Mail-Template. Eine neue Compare-Komponente mit Trip-Pendant (oder umgekehrt) ist ein Verstoß (Anti-Pattern #1170); Pendant-Sperre und Volltext: `docs/reference/gates_und_ratschen.md`.

## Confidence — NICHT wählbar als Metrik (Issue #710, Final)

`confidence_pct` ist KEINE pro-Etappe wählbare Metrik, sondern eine Meta-Aussage über Ensemble-Divergenz: nur als Verlässlichkeits-Hinweis im E-Mail-Textblock oder intern, kein SMS-Token (#2233), **NIEMALS** in Trip-Editor, Wizard, Metrik-Auswahl oder als Etappen-Spalte. Umsetzung: `MetricDefinition.selectable=false`, GET `/api/metrics` filtert; alte Trips mit `confidence` laden still, Render-Pfade ignorieren es.

## Daten-Schema-Reworks (PFLICHT!)

Bestandsdaten bleiben erhalten: **Read-Modify-Write mit Merge** (bestehendes Objekt laden, nur geänderte Felder überschreiben), **niemals Replace** (#102, BUG-DATALOSS-GR221). Edits an Schema-Dateien lösen den Pre-Snapshot-Hook `data_schema_backup.py` aus. Dateiliste, Migration, Anti-Pattern: `docs/reference/operations_playbook.md`.

## Backlog & Nebenbefunde

**GitHub Issues ist die einzige Quelle für offene Arbeit** (`enhancement`/`bug`), nie Markdown-Planung. Nebenbefund-Triage (Sammel-Issue #1199) und Regel-Budget: jede neue Pflicht-Regel ersetzt eine alte oder trägt ein Prüfdatum (+90 Tage), siehe `docs/reference/workflow_und_agenten.md`.

## Betrieb

- **Production:** https://gregor20.henemm.com — Systemd (`gregor-python.service`, `gregor-api`, `gregor-frontend`)
- **Staging:** https://staging.gregor20.henemm.com — Systemd (`gregor-python-staging`, `gregor-api-staging`, `gregor-frontend-staging`)

Monitoring-Pflicht (`last_run`), Pre-Test-Validierung (`python3 .claude/validate.py`), Session-Artefakte nie weltlesbar nach /tmp: `docs/reference/operations_playbook.md`.

## Parallele Sessions & Token-Budget

Ein Projektordner trägt höchstens eine Claude-Session; eine zweite arbeitet per `EnterWorktree` bzw. `.claude/tools/gz-workspace` isoliert und liefert unabhängig über `origin/main` aus. Kontext ist die teuerste Ressource: nach jedem Ticket `/clear`, Bash-Aufrufe bündeln, breit suchen delegieren, gezielt lesen; Details: `docs/reference/operations_playbook.md`.

Diese Instanz heißt `gregor`. **VERBOTEN: MQ-Nachrichten `gregor` → `gregor`**; Sitzungen im selben Projekt nutzen `SendMessage`, MQ nur instanzübergreifend (`docs/reference/workflow_und_agenten.md`).

# Compact instructions

Wird von `/compact` als Zusammenfassungs-Anleitung gelesen; nie einen langen `/compact <Text>` tippen, einfaches `/compact` genügt. Bei aktivem Workflow (`OPENSPEC_ACTIVE_WORKFLOW` gesetzt) IMMER bewahren:

- **Workflow-Identität:** Issue-Nummer, Workflow-Name, aktuelle Phase
- **Spec & Akzeptanz:** freigegebene ACs, Designentscheidungen aus der Analyse
- **TDD-Stand:** rote Tests + warum (Bug-Reproduktion aus Nutzersicht), Source-/Test-Dateipfade, RED-Artefakt-Pfade, LoC-Limit
- **Implementierung & QA:** geänderte Dateien, Adversary-Verdict, offene Fix-Loop-Punkte
- **Deploy-relevant:** Scope (frontend-only vs. full-stack), `verified_commit`-Status, Staging-Verdict

Verwerfen: rohe Tool-Output-Dumps, Hin-und-Her, Implementierungs-Detail-Diskussionen, die schon in `.claude/workflows/<name>.json`, `.claude/e2e_verified/<sha>.json` oder `docs/artifacts/` stehen.
