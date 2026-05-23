---
entity_id: issue_339_verify_timing
type: infra
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [workflow, hooks, e2e, ci-cd, deployment-pipeline, staging, issue-339, issue-337, issue-86]
---

<!-- Issue #339 — Schwere E2E-Verifikation vom Commit-Gate in die Post-Push-Staging-Phase verschieben -->

# Issue #339 — Verifikation zum richtigen Zeitpunkt (Commit-Stage vs. Acceptance-Stage)

## Approval

- [ ] Approved

## Zweck

Die schwere „funktioniert es wirklich"-Verifikation wird heute **vor dem Commit** verlangt (`e2e_commit_gate.py` → `/e2e-verify`), obwohl die einzige geeignete Umgebung dafür (Staging) den Code erst **nach** commit → push → Auto-Deploy bekommt. Daraus folgt ein Henne-Ei-Deadlock mit nur zwei schlechten Auswegen: (1) Verifikation lokal auf der Live-Maschine erzwingen — killt die Prod-API auf Port 8090 und mailt echte Nutzer (Bug #337); (2) das Gate überspringen, was sich wie ein Bypass anfühlt.

Dieser Umbau folgt dem etablierten **Deployment-Pipeline**-Prinzip (Humble/Farley, *Continuous Delivery*): schnelle, lokale Checks in der **Commit-Stage**; langsame, umgebungsbasierte Checks in der **Acceptance-Stage** *nach* erfolgreichem Commit. Ein Commit wird **nie** auf einen Deployed-Environment-Test gegated.

Konkret: Die deployed-environment-Anforderung wird aus dem Commit-Pfad **entfernt**. Die echte Verifikation wird zu einem **sicheren, staging-basierten** Schritt umgebaut, der nach dem Push und vor dem Prod-Deploy läuft — niemals gegen den Live-Prozess, niemals an echte Nutzer.

## Quelle / Source

**Geänderte Dateien:**
- `.claude/hooks/e2e_commit_gate.py` — entfernt die Deployed-Environment-Anforderung aus dem Commit-Pfad (kein Block mehr auf `server_restarted`/`emails_checked` etc.).
- `.claude/commands/e2e-verify.md` — Neufassung als **staging-basierte** Post-Push-Verifikation (kein `fuser -k 8090`, kein lokaler `go run`, kein Gmail; Versand nur an Test-Trip mit Test-Empfänger, niemals `send_reports()`).
- `.claude/hooks/e2e_browser_test.py` — Basis-URL konfigurierbar (`GZ_SVELTE_BASE`), Default Staging; hartkodiertes `localhost:8080` (toter NiceGUI-Port) entfernt.
- `.claude/hooks/email_spec_validator.py` — IMAP gegen Stalwart-Test-Postfach (`gregor-test@henemm.com` / `mail.henemm.com`) statt `imap.gmail.com`.
- `CLAUDE.md` — Sektionen „ECHTE E2E TESTS" und „E-MAIL SPEC VALIDATOR" auf das Post-Push-Staging-Modell umgeschrieben; „ICH restarte den Server"-Anweisung entfernt.

> **Schicht-Hinweis:** Reine Workflow-/Tooling-Schicht (`.claude/`, `CLAUDE.md`). **Kein** Produktiv-Code in `src/`, `api/`, `internal/`, `frontend/`. Damit ist dies nach der Post-Push-Workflow-Ausnahme eine Doku-/Tooling-Änderung (kein Prod-Deploy nötig, solange der Code-Drift-Monitor ruhig bleibt).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/e2e_commit_gate.py` | Python-Hook | Heute Commit-Blocker; wird auf Commit-Stage-konformes Verhalten reduziert |
| `.claude/hooks/pre_commit_validation.py` | Python-Hook (read-only) | Bleibt die Commit-Stage-Kontrolle (pytest grün) — deckt die schnellen Checks bereits ab |
| `.claude/commands/e2e-verify.md` | Slash-Command | Wird zur staging-basierten Acceptance-Stage-Prozedur |
| `.claude/hooks/e2e_browser_test.py` | Python-Tool | Browser-Check; Ziel-URL wird konfigurierbar |
| `.claude/hooks/email_spec_validator.py` | Python-Tool | Mail-Inhaltsprüfung; IMAP-Quelle wird Stalwart |
| `src/services/trip_report_scheduler.py` | Python-Modul (read-only) | `send_reports()` iteriert über ALLE aktiven Touren → in der Verifikation verboten |
| Issue #337 | GitHub-Issue | Akutes Sicherheitsleck — wird hiermit miterledigt |
| Issue #86 | GitHub-Issue | `detect_scope()` bleibt gültig, wird in die Acceptance-Prozedur übernommen |

## Implementation Details

### 1. Commit-Stage: nur schnelle, lokale Checks

`e2e_commit_gate.py` blockiert Commits nicht länger wegen fehlender Deployed-Environment-Verifikation. Die Commit-Stage besteht ausschließlich aus dem bereits vorhandenen `pre_commit_validation.py` (pytest grün) plus den schnellen Hooks (Syntax/Import via `validate.py`). Es gibt keine Commit-Voraussetzung mehr, die einen laufenden Server, echten Mailversand oder ein Postfach erfordert.

Umsetzung: `e2e_commit_gate.py` gibt für alle Scopes Exit 0 zurück (optional mit Hinweis „Verifikation erfolgt nach dem Push auf Staging"). Alternativ Entfernen aus `settings.json` — die Entscheidung (Stilllegen-mit-Hinweis vs. Entfernen) trifft der Developer-Agent; bevorzugt **Stilllegen-mit-Hinweis**, damit der Pfad dokumentiert bleibt.

### 2. Acceptance-Stage: sichere, staging-basierte Verifikation (`/e2e-verify` neu)

Die Prozedur läuft **nach** `git push origin main`, sobald der Staging-Auto-Deploy (~5 Min) durch ist, und **vor** `deploy-gregor-prod.sh`:

- **Ziel-Umgebung:** `https://staging.gregor20.henemm.com` (konfigurierbar via `GZ_SVELTE_BASE` / `GZ_VALIDATION_URL`).
- **Verboten:** `fuser -k 8090/tcp`, lokaler `go run ./cmd/gregor-api`, jeder Eingriff in einen Prod-/Staging-Systemd-Prozess.
- **Scope-Verzweigung** (Logik aus #86, `detect_scope()`):
  - `frontend-only`: visuelle Prüfung auf Staging (Playwright/Screenshot). **Kein** Mailversand.
  - `backend` / `full-stack`: Test-Trip anlegen, Report **ausschließlich** an diesen Test-Trip mit Test-Empfänger `gregor-test@henemm.com` senden — **niemals** `send_reports()` (alle aktiven Touren). IMAP-Verifikation gegen Stalwart.
- Schreibt `.claude/e2e_verified.json` mit `scope` und den durchgeführten Checks als Nachweis für den Pre-Prod-Schritt.

### 3. `e2e_browser_test.py` — URL konfigurierbar

Hartkodiertes `http://localhost:8080` (NiceGUI, seit Epic #129 A.3 entfernt) wird durch eine konfigurierbare Basis-URL ersetzt (Default `https://staging.gregor20.henemm.com`, override via `GZ_SVELTE_BASE`). Compare-spezifische Selektoren bleiben, sofern noch gültig; ansonsten als veraltet markieren.

### 4. `email_spec_validator.py` — Stalwart statt Gmail

`fetch_latest_email()` nutzt bereits `settings.imap_host`; die Settings müssen auf Stalwart (`mail.henemm.com`, User `gregor-test`) zeigen. Jeder hartkodierte Gmail-Bezug wird entfernt. Validierung läuft nur gegen die Test-Trip-Mail, nicht gegen ein produktives Postfach.

### 5. `CLAUDE.md` — Sektionen neu

- „ECHTE E2E TESTS": ersetzt durch „Post-Push-Verifikation auf Staging". Entfernt „ICH stoppe/starte den Server" (auf dieser Maschine = Prod). Verweist auf den bestehenden Post-Push-Workflow.
- „E-MAIL SPEC VALIDATOR": Bezug auf Stalwart-Test-Postfach; läuft in der Acceptance-Stage gegen Staging-Mail.

### 6. Bewusste Nicht-Änderung (Tech-Lead-Entscheidung)

Es wird **kein** neuer Enforcement-Hook auf `git commit` oder `deploy-gregor-prod.sh` ergänzt. Die wiederkehrende Reibung entstand durch zu starre, fehlzündende Gates; ein weiteres Gate würde dieses Muster wiederholen. Die Acceptance-Stage wird durch den bereits dokumentierten Post-Push-Workflow + den bestehenden External-Validator (läuft gegen Staging) + den Prod-HTTP-Smoke abgesichert — schlanke Prozess-Disziplin statt zusätzlicher Hook-Mechanik.

## Expected Behavior

- **Input:** Eine reine Frontend-Änderung (z. B. font-sizes) wird lokal committet.
- **Output:** Der Commit gelingt, sobald die Tests grün sind — **ohne** Server-Neustart, ohne Mailversand, ohne `e2e_verified.json`. Die visuelle Verifikation erfolgt nach dem Push auf Staging.
- **Side effects:** Kein Eingriff in Port 8090 (Prod), keine Mails an echte Nutzer, keine Gmail-Abfrage.

## Acceptance Criteria

- **AC-1:** Given eine rein in `frontend/` liegende Änderung ist lokal gestaged und `uv run pytest` ist grün / When `git commit` ausgeführt wird / Then wird der Commit **nicht** durch `e2e_commit_gate.py` blockiert (keine Forderung nach `server_restarted`/`emails_checked`/`e2e_verified.json`).
  - Test: (populated after /4-tdd-red)

- **AC-2:** Given die neugefasste `/e2e-verify`-Prozedur (`.claude/commands/e2e-verify.md`) / When ihr Inhalt geprüft wird / Then enthält sie **kein** `fuser -k 8090`, **kein** lokales `go run ./cmd/gregor-api` und **keinen** Aufruf von `send_reports()`, und sie nennt `https://staging.gregor20.henemm.com` als Ziel.
  - Test: (populated after /4-tdd-red)

- **AC-3:** Given die Acceptance-Stage prüft eine Backend-Mail / When sie die Empfänger bestimmt / Then geht die Mail ausschließlich an einen Test-Trip mit Empfänger `gregor-test@henemm.com`, und die IMAP-Prüfung verbindet sich mit dem Stalwart-Host (nicht `imap.gmail.com`).
  - Test: (populated after /4-tdd-red)

- **AC-4:** Given `e2e_browser_test.py` / When der Quellcode geprüft wird / Then existiert **kein** hartkodiertes `http://localhost:8080` mehr; die Basis-URL ist konfigurierbar mit Staging als Default.
  - Test: (populated after /4-tdd-red)

- **AC-5:** Given `email_spec_validator.py` / When der Quellcode geprüft wird / Then erscheint **kein** hartkodiertes `imap.gmail.com`; die IMAP-Quelle stammt ausschließlich aus den Settings (Stalwart).
  - Test: (populated after /4-tdd-red)

- **AC-6:** Given die CLAUDE.md-Sektionen „ECHTE E2E TESTS" und „E-MAIL SPEC VALIDATOR" / When sie nach dem Umbau gelesen werden / Then enthalten sie **keine** Anweisung, den Server zu stoppen/neu zu starten, und verweisen auf die staging-basierte Post-Push-Verifikation.
  - Test: (populated after /4-tdd-red)

- **AC-7:** Given Produktiv-Code in `src/`, `api/`, `internal/`, `frontend/` / When der Umbau abgeschlossen ist / Then ist dieser Code zeichengleich zur Pre-Fix-Version (die Änderung beschränkt sich auf `.claude/` und `CLAUDE.md`).
  - Test: (populated after /4-tdd-red)

## Known Limitations

- **Enforcement wird leichter, nicht strenger:** Nach dem Umbau erzwingt kein Hook mehr eine Deployed-Environment-Verifikation vor dem Prod-Deploy. Die Absicherung liegt bewusst im dokumentierten Post-Push-Workflow + External-Validator. Das ist eine bewusste Trade-off-Entscheidung gegen Hook-Fragilität.
- **Compare-Selektoren in `e2e_browser_test.py`** können gegenüber dem heutigen SvelteKit-Frontend veraltet sein; ihre vollständige Modernisierung ist separat (out of scope), hier zählt nur die URL-Korrektur.

## Out of Scope

- Neuer Enforcement-Hook auf Commit oder Deploy (bewusst nicht, siehe Implementation Details §6).
- Änderungen an `deploy-gregor-prod.sh` / Nginx (liegt im Repo `henemm-infra`; bei Bedarf separate MQ-Nachricht an `infra`).
- Vollständige Modernisierung der Playwright-Selektoren für das aktuelle Frontend.
- Änderungen an der Versand-Logik in `src/services/trip_report_scheduler.py` (read-only Referenz).

## Changelog

- 2026-05-22: Initial spec. Verschiebt die schwere E2E-Verifikation von der Commit-Stage in die staging-basierte Acceptance-Stage (Deployment-Pipeline-Prinzip), entschärft die auf dem Live-Server gefährliche Prozedur (#337) und integriert die Scope-Erkennung aus #86. Reine `.claude/`+`CLAUDE.md`-Schicht, kein Produktiv-Code.
