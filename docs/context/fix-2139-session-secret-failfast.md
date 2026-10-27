# Context: fix-2139-session-secret-failfast

## Request Summary

`internal/config/config.go:16` gibt `SessionSecret` einen Default (`"dev-secret-change-me"`), und `cmd/server/main.go` bricht nach `config.Load()` nur bei einem envconfig-Parsefehler ab (`log.Fatalf("config error: %v", err)`), nie wenn der Default unverändert übernommen wurde. Fehlt `GZ_SESSION_SECRET` in der Umgebung, signiert der Server Sessions mit einem öffentlich bekannten String — jeder kann sich damit eine gültige Session-Cookie für eine beliebige `user_id` selbst ausstellen (Blocker aus Epic #2138).

## Related Files

| File | Relevance |
|------|-----------|
| `internal/config/config.go:16` | Definiert `SessionSecret` mit Default `"dev-secret-change-me"` — der zu prüfende Wert |
| `cmd/server/main.go:27-31` | `config.Load()`-Aufruf + einziger bestehender `log.Fatalf` danach (nur Parsefehler); hier muss die neue Prüfung ansetzen |
| `cmd/server/main.go:70-77` | Vorhandenes Muster für einen zweiten Fail-Fast-Block nach dem Config-Load (`webauthn.New` → `log.Fatalf`) — Vorlage für Stil/Platzierung |
| `internal/egress/guard.go:59-70` (`Install`) | Bestehendes Muster, um "echten Betrieb" von "Test-/Fixture-Lauf" zu unterscheiden: `cfg.Env != "staging" && cfg.TestFixtureDir == ""` |
| `internal/scheduler/scheduler_gate.go` (`SchedulerEnabled`) | Zweites Beispiel für ein Env-basiertes Gate mit demselben Fail-safe-Prinzip ("nur der exakte Wert schaltet um") |
| `internal/config/config_test.go` | Bestehende `Load()`-Tests räumen die Umgebung leer (`os.Clearenv()`) und erwarten Defaults — der neue Fail-Fast darf NICHT in `Load()` selbst liegen, sonst brechen diese Tests |
| `frontend/e2e/ci-stack.sh:9,56-57` | Einziger Ort im Repo, der den echten Go-Server-Binary bewusst **mit unverändertem** `SessionSecret`-Default startet (Kommentar: „bleibt UNGESETZT, halbseitig gesetzt bricht die Cookie-Signatur"). Setzt dabei aber explizit `GZ_TEST_FIXTURE_DIR="$REPO_ROOT/fixtures/openmeteo"` |
| `.env.e2e` | Git-getrackt, secret-frei, setzt ebenfalls `GZ_TEST_FIXTURE_DIR=fixtures/openmeteo` für den Frontend-Preview-Prozess |
| `frontend/e2e/e2e-env.sh`, `frontend/e2e/start-preview.sh` | Anderer E2E-Pfad (lokaler Preview gegen echten Staging-Server): zieht das **echte** `GZ_SESSION_SECRET` aus der Haupt-`.env` — betrifft nicht den Default-Fall |
| `internal/handler/auth_magic.go:187`, `auth_oauth.go:182`, `internal/router/router.go` (mehrere Stellen) | Nutzen `cfg.SessionSecret` zum Signieren/Verifizieren — bleiben durch den Fix unverändert, sind aber der Grund, warum ein falscher Default kritisch ist |
| `docs/specs/bugfix/go_api_bind_localhost.md` | Vorlage: strukturell sehr ähnlicher Bugfix (Fail-Closed-Startup-Verhalten für einen Security-relevanten Config-Wert, gleiche Datei `cmd/server/main.go`) |
| `frontend/src/hooks.server.ts:16` | `env.GZ_SESSION_SECRET ?? 'dev-secret-change-me'` — identischer stiller Fallback im Frontend |

## Existing Patterns

- **Fail-Fast direkt nach `config.Load()` in `main()`**, nicht in `config.Load()` selbst — es gibt bereits zwei solche Blöcke (Parsefehler, `webauthn.New`-Fehler). Der neue Check reiht sich als dritter ein.
- **Test-/Fixture-Lauf-Erkennung über `cfg.TestFixtureDir != ""`** — das ist im Repo bereits die etablierte, einzige verlässliche Unterscheidung zwischen einem isolierten Test-Stack und einem echten Deploy (Env-Wert allein reicht nicht, siehe unten).
- Bestehende Kommentar-Konvention: Fail-safe-Begründung direkt über der Prüfung, mit Issue-Referenz (siehe `scheduler_gate.go`).

## Dependencies

- **Upstream:** `envconfig.Process` (liefert den Default, wenn `GZ_SESSION_SECRET` fehlt) — unverändert.
- **Downstream:** Alle Signier-/Verifizierstellen (`middleware.SignSession`, `AuthMiddleware`, Login/Magic-Link/OAuth/Passkey-Handler) — nicht betroffen, sie lesen weiterhin `cfg.SessionSecret`, unabhängig davon, ob der Wert gültig ist.

## Existing Specs

- Keine Spec zu `SessionSecret` bisher. `docs/specs/bugfix/go_api_bind_localhost.md` ist die nächstverwandte (gleicher Bugfix-Typ, gleiche Datei, gleiches Muster: Default unsicher → Fail-Closed + `GZ_`-Override bleibt bestehen).

## Betriebs-Rechercheergebnis (belegt, kein Risiko für laufenden Betrieb)

- **Prod-`.env`** (`/home/hem/gregor_zwanzig/.env`): `GZ_SESSION_SECRET` ist real gesetzt (1 Treffer), `GZ_ENV` nicht gesetzt, `GZ_TEST_FIXTURE_DIR` nicht gesetzt.
- **Staging-`.env`** (`/home/hem/gregor_zwanzig_staging/.env`): `GZ_SESSION_SECRET` real gesetzt (1 Treffer), `GZ_ENV=staging` gesetzt, `GZ_TEST_FIXTURE_DIR` NICHT gesetzt.
- **CI-E2E-Stack** (`ci-stack.sh` im `e2e`-Job aus `.github/workflows/ci.yml:326`): startet den gebauten Go-Server **ohne** `GZ_SESSION_SECRET`, aber **mit** `GZ_TEST_FIXTURE_DIR` gesetzt.
- Keine weitere Stelle im Repo startet `cmd/server`-Binary direkt (kein lokales Dev-Script, kein Makefile-Target).

→ Ein Fail-Fast, der ausschließlich an `cfg.SessionSecret == "dev-secret-change-me" && cfg.TestFixtureDir == ""` hängt, träfe **nur** eine tatsächliche Fehlkonfiguration (fehlendes Secret in einer echten Umgebung) und ließe den einzigen bekannten legitimen Default-Nutzer (CI-E2E-Stack) unangetastet. Ein Env=="staging"-Ausnahme (wie bei `SchedulerEnabled`/`egress.Install`) ist hier NICHT nötig und würde die Prüfung in echtem Staging unnötig schwächen.

## Risks & Considerations

- Die Prüfung muss **in `main()`** stehen, nicht in `config.Load()` — sonst brechen `TestLoadDefaults*` in `config_test.go`, die bewusst eine leere Umgebung testen.
- String-Vergleich auf den exakten Default-Literal ist beabsichtigt fragil-eng (wie bei `SchedulerEnabled`: nur der exakte bekannte Wert löst aus) — kein Passwort-Stärke-Check, das ist außerhalb des Issue-Scopes.
- Muss den einzigen bekannten Legitim-Fall (CI-E2E-Stack über `GZ_TEST_FIXTURE_DIR`) exakt treffen, sonst wird die `e2e`-CI-Ampel rot (Merge-Regel: alle 6 Checks grün).
- Kein Scope-Creep auf andere Secrets (`AuthPass`, SMTP-Creds etc.) — Issue #2139 ist ausschließlich `SessionSecret`.
- Frontend (`hooks.server.ts`) braucht eine äquivalente Fail-Fast-Prüfung beim SvelteKit-Serverstart — analoge Test-/E2E-Ausnahme dort noch zu klären (kein `TestFixtureDir`-Äquivalent im Frontend bekannt, muss in der Analyse-Phase geprüft werden).

## Analysis

### Type

Bug (Blocker, Security). Bug-Intake-Agent hat die Root Cause unabhängig bestätigt: fehlende Post-Load-Validierung in `main()`, Lösungsmuster existiert im Repo bereits (`egress.Install`, `scheduler_gate.go`).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/config/session_secret_gate.go` | CREATE | `ValidateSessionSecret(cfg *Config) error` — prüft leer → `== "dev-secret-change-me"` → `len < 32`; Ausnahme `cfg.TestFixtureDir != ""` |
| `internal/config/session_secret_gate_test.go` | CREATE | Tabellen-Test für die vier Fälle + Ausnahme |
| `cmd/server/main.go` | MODIFY | Direkt nach dem bestehenden `config.Load()`-Fehlercheck (vor `egress.Install(cfg)`): `if err := config.ValidateSessionSecret(cfg); err != nil { log.Fatalf(...) }` |
| `frontend/src/lib/sessionSecretGate.ts` | CREATE | `assertSessionSecretConfigured(secret: string \| undefined): void` — wirft bei leer/Default-Literal/`< 32` Zeichen |
| `frontend/src/lib/sessionSecretGate.test.ts` | CREATE | Vitest-Unit-Test für die Funktion |
| `frontend/src/hooks.server.ts` | MODIFY | Aufruf auf Modul-Top-Level (crasht den Serverboot, nicht erst beim ersten Request); `?? 'dev-secret-change-me'`-Fallback in `handle` entfällt |

### Scope Assessment

- Files: 6 (4 neu, 2 geändert)
- Estimated LoC: ~120-160 (Go ~75-85, Frontend ~55-70) — deutlich unter dem 250-LoC-Workflow-Limit
- Risk Level: LOW — kein bekannter legitimer Nutzer des unsicheren Defaults im Frontend (E2E setzt das echte Secret bereits real); einziger Go-Ausnahmefall (`TestFixtureDir`) exakt identifiziert; Prod- UND Staging-Secret bereits verifiziert ≥32 Zeichen (66 Zeichen in beiden `.env`), kein Restrisiko für den nächsten Neustart

### Technical Approach

Go: neue testbare Funktion `config.ValidateSessionSecret(cfg) error`, aufgerufen in `main()` nach dem bestehenden Parsefehler-Check, Stil identisch zum bestehenden `webauthn.New(...)`-Fail-Fast-Block. Frontend: äquivalente Funktion `assertSessionSecretConfigured()`, aufgerufen auf Modul-Top-Level in `hooks.server.ts` (SvelteKit/adapter-node importiert das Modul einmal beim Boot — das ist die Analogie zu Go-`main()`). Beide Seiten: eigene, isoliert testbare Datei statt Logik im Aufrufer, damit kein Unit-Test auf `main()`/Modul-Top-Level nötig ist.

### Dependencies

Kein Blocker zwischen Go- und Frontend-Änderung (unabhängige Dateien/Runtimes). Ein gemeinsamer Workflow mit zwei AC-Blöcken (Go zuerst, Frontend danach) ist sinnvoll, da beide dasselbe Sicherheitsproblem lösen und das LoC-Budget reicht.

### Open Questions

- [ ] Spec muss festlegen, dass lokale Entwicklung ohne `.env` künftig ebenfalls beim Serverstart hart abbricht (Go) bzw. beim Boot crasht (Frontend) — das ist der beabsichtigte Zweck des Issues, aber explizit als AC festzuhalten.
