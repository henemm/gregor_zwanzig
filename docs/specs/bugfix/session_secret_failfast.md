---
entity_id: session_secret_failfast
type: bugfix
created: 2026-09-06
updated: 2026-09-06
status: draft
version: "1.0"
tags: [security, bugfix, auth, go-api, frontend, issue-2139]
---

# Session-Secret Fail-Fast

## Approval

- [ ] Approved

## Purpose

Behebt eine Auth-Bypass-Lücke (Issue #2139): Sowohl Go-API (`internal/config/config.go:16`) als auch Frontend (`frontend/src/hooks.server.ts:16`) fallen still auf das öffentlich im Repo stehende Default-Secret `"dev-secret-change-me"` zurück, wenn `GZ_SESSION_SECRET` fehlt. Mit diesem bekannten Secret kann jede Person für eine beliebige `user_id` ein gültiges Session-Cookie selbst signieren (`internal/middleware.SignSession` = `{userId}.{unix}.{hmac_sha256(userId:ts)}`) und sich damit als jeder Nutzer ausgeben. Der Fix führt in beiden Prozessen eine Fail-Fast-Prüfung direkt nach dem Konfigurations-Laden ein: leeres, unverändertes oder zu kurzes Secret beendet den Prozess beim Start statt einen unsicheren Betrieb zuzulassen.

## Source

- **File:** `internal/config/config.go`
- **Identifier:** `Config.SessionSecret` (Zeile 16, `default:"dev-secret-change-me"`)
- **Secondary File:** `frontend/src/hooks.server.ts`
- **Identifier:** `env.GZ_SESSION_SECRET ?? 'dev-secret-change-me'` (Zeile 16)

> **Schicht-Hinweis:** Zwei getrennte Prozesse, zwei getrennte Fixes — Go-API (`cmd/server/`, `internal/`) und Frontend-Server (`frontend/src/`, SvelteKit `hooks.server.ts`, läuft node-seitig unter `adapter-node`). Beide lesen `GZ_SESSION_SECRET` unabhängig voneinander aus der Umgebung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `envconfig.Process` (`internal/config/config.go`) | External Library | Liefert `SessionSecret`-Wert inkl. Default, wenn ENV fehlt — unverändert |
| `internal/middleware.SignSession`, `SignSessionWithID`, `AuthMiddleware` (`internal/middleware/auth.go`) | Consumer | Nutzen `cfg.SessionSecret` zum Signieren/Verifizieren von Session-Cookies — unverändert, aber Grund für die Kritikalität |
| `frontend/src/lib/auth.ts` (`verifySession`) | Consumer | Verifiziert `gz_session`-Cookie im Frontend-Server mit demselben Secret-Konzept |
| `internal/egress/guard.go` (`Install`) | Reference Pattern | Bestehendes Vorbild für ein Env-basiertes Fail-safe-Gate nach Config-Load |
| `internal/scheduler/scheduler_gate.go` (`SchedulerEnabled`) | Reference Pattern | Bestehendes Vorbild für eine reine, testbare Gate-Funktion über `*config.Config` |
| `frontend/e2e/ci-stack.sh`, `.github/workflows/ci.yml` (`e2e`-Job) | Test Infrastructure | Startet den Go-Stack via `GZ_TEST_FIXTURE_DIR` ohne gesetztes `GZ_SESSION_SECRET` — einziger legitimer Nutzer des Fallback-Pfads, muss von der neuen Go-Prüfung ausgenommen bleiben |
| `frontend/e2e/e2e-env.sh`, `frontend/e2e/start-preview.sh` | Test Infrastructure | Setzen für Frontend-E2E bereits immer ein echtes `GZ_SESSION_SECRET` — keine Ausnahme im Frontend-Gate nötig |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/config/session_secret_gate.go` | CREATE | `ValidateSessionSecret(cfg *Config) error` — prüft leer/Default-Literal/Mindestlänge, mit `TestFixtureDir`-Ausnahme |
| `internal/config/session_secret_gate_test.go` | CREATE | Tabellen-Test für alle Fälle (leer, Default, zu kurz, gültig, TestFixtureDir-Ausnahme) |
| `cmd/server/main.go` | MODIFY | Aufruf von `config.ValidateSessionSecret(cfg)` direkt nach dem bestehenden `config.Load()`-Fehlercheck, vor `egress.Install(cfg)` |
| `frontend/src/lib/sessionSecretGate.ts` | CREATE | `assertSessionSecretConfigured(secret: string \| undefined): void` |
| `frontend/src/lib/sessionSecretGate.test.ts` | CREATE | Vitest-Test für alle Fälle (leer, undefined, Default, zu kurz, gültig) |
| `frontend/src/hooks.server.ts` | MODIFY | Modul-Top-Level-Aufruf von `assertSessionSecretConfigured(env.GZ_SESSION_SECRET)` statt des `?? 'dev-secret-change-me'`-Fallbacks in Zeile 16 |

### Estimated Changes

- Files: 6 (4 CREATE, 2 MODIFY)
- LoC: +120/-2 (deutlich unter dem 250-LoC-Workflow-Limit)

## Implementation Details

**Go — `internal/config/session_secret_gate.go`:** Neue, reine Funktion `func ValidateSessionSecret(cfg *Config) error`, analog im Stil zu `scheduler.SchedulerEnabled` (Reference Pattern). Prüfreihenfolge, jeweils mit `error`-Rückgabe bei Verstoß:

1. `cfg.TestFixtureDir != ""` → sofort `nil` zurückgeben (deckt den CI-E2E-Stack ab, der bewusst ohne `GZ_SESSION_SECRET` startet).
2. `cfg.SessionSecret == ""` → Fehler.
3. `cfg.SessionSecret == "dev-secret-change-me"` → Fehler.
4. `len(cfg.SessionSecret) < 32` → Fehler.
5. Sonst `nil`.

Aufruf in `cmd/server/main.go` direkt nach dem bestehenden `config.Load()`-Fehlercheck (aktuell Zeile 29-31), vor `egress.Install(cfg)` (aktuell Zeile 35):

```go
if err := config.ValidateSessionSecret(cfg); err != nil {
    log.Fatalf("session secret invalid: %v", err)
}
```

Stilistisch identisch zum bestehenden `webauthn.New(...)`-Fail-Fast-Block weiter unten in `main.go` (`if err != nil { log.Fatalf(...) }`). Bewusst NICHT in `config.Load()` selbst platziert, da sonst `TestLoadDefaults*` in `internal/config/config_test.go` bricht — diese Tests nutzen `os.Clearenv()` und erwarten ein fehlerfreies `Load()` mit reinen Defaults.

**Frontend — `frontend/src/lib/sessionSecretGate.ts`:** `export function assertSessionSecretConfigured(secret: string | undefined): void` wirft ein `Error`-Objekt, wenn `secret` `undefined`/leer ist, exakt `'dev-secret-change-me'` entspricht, oder kürzer als 32 Zeichen ist. Aufruf auf Modul-Top-Level in `frontend/src/hooks.server.ts`, außerhalb der `handle`-Funktion, direkt nach dem `env`-Import:

```ts
import { env } from '$env/dynamic/private';
import { assertSessionSecretConfigured } from '$lib/sessionSecretGate.js';

assertSessionSecretConfigured(env.GZ_SESSION_SECRET);
```

SvelteKit/`adapter-node` importiert `hooks.server.ts` einmal beim Prozessstart — ein Top-Level-Throw beendet den Serverstart dort, statt erst beim ersten eingehenden Request sichtbar zu werden. Die bisherige Zeile `const secret = env.GZ_SESSION_SECRET ?? 'dev-secret-change-me';` entfällt und wird durch `const secret = env.GZ_SESSION_SECRET as string;` ersetzt — das Gate hat die Anwesenheit und Mindestqualität des Secrets bereits vor Erreichen dieser Zeile sichergestellt.

## Expected Behavior

- **Input (Go, fehlendes/Default-/zu kurzes Secret):** `GZ_SESSION_SECRET` unset, `=dev-secret-change-me`, oder `<32` Zeichen beim Prozessstart.
- **Output (Go):** Prozess beendet sich sofort mit `log.Fatalf("session secret invalid: %v", err)`, Exit-Code ≠ 0. Kein HTTP-Server startet.
- **Input (Go, TestFixtureDir gesetzt):** `GZ_TEST_FIXTURE_DIR` gesetzt, `GZ_SESSION_SECRET` unset.
- **Output (Go):** Startet unverändert wie bisher (CI-E2E-Pfad bleibt funktionsfähig).
- **Input (Frontend, fehlendes/Default-/zu kurzes Secret):** `GZ_SESSION_SECRET` unset, `=dev-secret-change-me`, oder `<32` Zeichen beim Prozessstart.
- **Output (Frontend):** Der Node-Prozess wirft beim Modul-Import von `hooks.server.ts` und beendet sich, bevor er Requests annimmt.
- **Side effects:** Bei gültigem, langem, individuellem Secret (wie bereits in Prod-/Staging-`.env` hinterlegt) ändert sich das Laufzeitverhalten nicht — beide Prozesse starten wie bisher.

## Test Plan

### Automated Tests (TDD RED)

#### Go Tests

- [ ] Test 1: GIVEN eine `Config` mit `SessionSecret: "dev-secret-change-me"` und leerem `TestFixtureDir` WHEN `ValidateSessionSecret(cfg)` aufgerufen wird THEN liefert die Funktion einen Fehler ungleich `nil` zurück.
- [ ] Test 2: GIVEN eine `Config` mit gesetztem `TestFixtureDir` und leerem `SessionSecret` WHEN `ValidateSessionSecret(cfg)` aufgerufen wird THEN liefert die Funktion `nil` zurück (CI-E2E-Ausnahme greift).
- [ ] Test 3: GIVEN eine `Config` mit `SessionSecret` kürzer als 32 Zeichen (z. B. `"kurz"`) WHEN `ValidateSessionSecret(cfg)` aufgerufen wird THEN liefert die Funktion einen Fehler ungleich `nil` zurück.
- [ ] Test 4: GIVEN eine `Config` mit einem individuellen 40-Zeichen-Secret ohne Default-Literal WHEN `ValidateSessionSecret(cfg)` aufgerufen wird THEN liefert die Funktion `nil` zurück.

#### Frontend Tests

- [ ] Test 5: GIVEN `secret` ist `undefined` WHEN `assertSessionSecretConfigured(secret)` aufgerufen wird THEN wirft die Funktion einen `Error`.
- [ ] Test 6: GIVEN `secret` ist exakt `'dev-secret-change-me'` WHEN `assertSessionSecretConfigured(secret)` aufgerufen wird THEN wirft die Funktion einen `Error`.
- [ ] Test 7: GIVEN `secret` ist kürzer als 32 Zeichen WHEN `assertSessionSecretConfigured(secret)` aufgerufen wird THEN wirft die Funktion einen `Error`.
- [ ] Test 8: GIVEN `secret` ist ein individuelles 40-Zeichen-Secret ohne Default-Literal WHEN `assertSessionSecretConfigured(secret)` aufgerufen wird THEN wirft die Funktion KEINEN `Error`.

## Acceptance Criteria

- **AC-1:** Given die Go-API wird ohne `GZ_SESSION_SECRET` und ohne `GZ_TEST_FIXTURE_DIR` gestartet / When `config.Load()` erfolgreich zurückkehrt und anschließend `config.ValidateSessionSecret(cfg)` aufgerufen wird / Then liefert die Funktion einen Fehler ungleich `nil` zurück und der Prozess terminiert über `log.Fatalf` statt den HTTP-Server zu starten.
  - Test: `internal/config/session_secret_gate_test.go` ruft `ValidateSessionSecret` mit einer `Config` auf, deren `SessionSecret` das Default-Literal `"dev-secret-change-me"` trägt, und prüft `err != nil`.

- **AC-2:** Given die Go-API wird mit `GZ_TEST_FIXTURE_DIR` gesetzt und ohne `GZ_SESSION_SECRET` gestartet (CI-E2E-Konfiguration) / When `ValidateSessionSecret(cfg)` aufgerufen wird / Then liefert die Funktion `nil` zurück, sodass der CI-E2E-Stack (`frontend/e2e/ci-stack.sh`) unverändert startfähig bleibt.
  - Test: `internal/config/session_secret_gate_test.go` ruft `ValidateSessionSecret` mit einer `Config` auf, deren `TestFixtureDir` gesetzt und `SessionSecret` leer ist, und prüft `err == nil`.

- **AC-3:** Given der Frontend-Server wird ohne `GZ_SESSION_SECRET` gestartet / When das Modul `frontend/src/hooks.server.ts` beim Prozessstart importiert wird / Then wirft `assertSessionSecretConfigured` einen `Error` und der Serverstart schlägt fehl, statt mit dem unsicheren Default-Secret weiterzulaufen.
  - Test: `frontend/src/lib/sessionSecretGate.test.ts` ruft `assertSessionSecretConfigured(undefined)` sowie `assertSessionSecretConfigured('dev-secret-change-me')` auf und prüft jeweils, dass ein `Error` geworfen wird.

- **AC-4:** Given ein gültiges, individuelles Secret mit mindestens 32 Zeichen ist gesetzt (wie in Prod-/Staging-`.env` bereits hinterlegt) / When sowohl `config.ValidateSessionSecret` (Go) als auch `assertSessionSecretConfigured` (Frontend) mit diesem Secret aufgerufen werden / Then liefern beide Prüfungen keinen Fehler und der jeweilige Prozess startet regulär weiter.
  - Test: `internal/config/session_secret_gate_test.go` und `frontend/src/lib/sessionSecretGate.test.ts` enthalten je einen Fall mit einem 40-Zeichen-Zufallssecret ohne Default-Literal und prüfen `err == nil` bzw. dass kein `Error` geworfen wird.

## Known Limitations

- Der Fix ändert nichts an bereits laufenden Prozessen mit bereits geladenem Default-Secret — er wirkt ausschließlich beim nächsten Prozessstart (Neustart/Deploy). Für Prod und Staging ist das kein Restrisiko, da beide `.env`-Dateien bereits ein 66 Zeichen langes `GZ_SESSION_SECRET` gesetzt haben (in der Analyse-Phase verifiziert).
- Die Mindestlänge von 32 Zeichen ist eine Heuristik gegen offensichtlich schwache/geratene Secrets, kein Ersatz für eine echte Entropie-Prüfung. Ausreichend, um das bekannte Default-Literal und triviale Kurz-Secrets abzufangen.
- Bereits ausgestellte Session-Cookies, die mit dem alten Default-Secret signiert wurden, werden durch diesen Fix nicht invalidiert — sie verlieren ihre Gültigkeit erst, sobald der Prozess mit einem neuen Secret neu startet (Signaturprüfung schlägt dann fehl). Ein aktives Invalidieren bestehender Cookies ist nicht Teil dieses Fixes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Fail-Fast-Absicherung eines bestehenden Konfigurationswerts nach etabliertem Repo-Muster (`egress.Install`, `SchedulerEnabled`) — keine neue Architekturentscheidung, kein neuer Kanal, kein neues Datenmodell.

## Changelog

- 2026-09-06: Initial spec created based on Issue #2139 analysis
- 2026-09-06: Test Plan Sektion ergänzt (Spec-Validator-Finding: fehlende Pflichtsektion)
