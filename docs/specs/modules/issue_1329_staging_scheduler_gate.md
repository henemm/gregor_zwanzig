---
entity_id: issue_1329_staging_scheduler_gate
type: module
created: 2026-07-20
updated: 2026-07-20
status: draft
version: "1.0"
tags: [scheduler, staging, open-meteo, go-api]
---

<!-- Issue #1329 — Maßnahme A: autonomen Go-Scheduler auf Staging deaktivieren -->

# Issue 1329 (Maßnahme A) — Staging-Scheduler-Gate

## Approval

- [x] Approved (PO „Freigabe" 2026-07-20)

## Purpose

Den autonomen Go-Cron-Scheduler (`internal/scheduler`) auf Staging vom Start
ausnehmen, damit Staging keine automatischen `open-meteo`-Aufrufe mehr
auslöst und das gemeinsame Tageskontingent nicht mehr blind mit Prod teilt.
Der Scheduler bleibt auf Produktion unverändert aktiv; Staging bekommt
weiterhin manuell auslösbare Jobs über den bestehenden Python-Trigger-Pfad
(Port 8001), nur der autonome Ticker feuert dort nicht mehr.

## Source

- **File:** `cmd/server/main.go` — bedingungsloser Aufruf `sched.Start()` (Zeile 79)
- **File:** `internal/scheduler/scheduler.go` — `New()` (Zeile 72, registriert 8 Cron-Einträge via `AddFunc`), `Start()` (Zeile 129, startet das Ticken)
- **File:** `internal/config/config.go` — Config-Struct mit `envconfig`-Tags, Präfix `GZ`

> **Schicht-Hinweis:** Reiner Go-API-Eingriff (`cmd/server/`, `internal/`). Kein Python-Core-, kein Frontend-Code betroffen.

## Estimated Scope

- **LoC:** ~20
- **Files:** 3 (config.go, main.go, scheduler.go) + 1 Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `github.com/kelseyhightower/envconfig` | third-party lib | liest `GZ_ENV` in `config.Config.Env` ein (Präfix `GZ` bereits etabliert) |
| `internal/router/router.go:197` (`os.Getenv("GZ_ENV") == "staging"`) | bestehendes Muster | Referenzimplementierung für dieselbe Env-Kennung, wird hier auf Config-Feld gehoben statt erneut `os.Getenv` zu streuen |
| Staging-`.env` (`/home/hem/gregor_zwanzig_staging/.env`, setzt `GZ_ENV=staging`) | Betriebs-Konfiguration | verifiziert vorhanden, keine Deploy-Änderung nötig |
| Prod-`.env` (setzt kein `GZ_ENV`) | Betriebs-Konfiguration | verifiziert: Feld bleibt leer, Fail-safe greift |
| `/api/scheduler/status` (`internal/scheduler.Status()`) | bestehender Endpoint | muss unverändert antworten, auch wenn `Start()` nicht lief |

## Implementation Details

1. `internal/config/config.go`: neues Feld `Env string` mit `envconfig:"ENV" default:""` (Präfix `GZ` ergibt `GZ_ENV`, analog zu allen anderen Feldern der Struct).

2. `internal/scheduler`: kleine pure Prädikat-Funktion, die testbar ist ohne HTTP/Cron-Setup, z. B.

   ```go
   func SchedulerEnabled(cfg *config.Config) bool {
       return cfg.Env != "staging"
   }
   ```

   Exakter Funktionsname liegt beim Implementierer, muss aber exportiert und pur sein (kein Seiteneffekt, kein Zugriff auf laufenden Scheduler-State).

3. `cmd/server/main.go`: `sched.Start()` nur noch bedingt aufrufen:

   ```go
   if scheduler.SchedulerEnabled(cfg) {
       sched.Start()
   } else {
       log.Printf("[scheduler] disabled for env=%s (staging quota gate, Issue #1329)", cfg.Env)
   }
   defer sched.Stop()
   ```

   `scheduler.New(cfg, s)` bleibt in main.go **unverändert vor** dieser Verzweigung — die Cron-Einträge werden weiterhin registriert (nötig, damit `Status()` Job-Liste und `next_run` liefert), nur `cron.Start()` (das tatsächliche Ticken) unterbleibt. `sched.Stop()` per `defer` bleibt harmlos aufrufbar, auch wenn `Start()` nie lief (robfig/cron `Stop()` auf nicht gestartetem Cron ist ein No-Op, das sofort auf dem bereits geschlossenen Kontext zurückkehrt).

4. Kein Eingriff in `internal/scheduler/scheduler.go` selbst nötig außer der neuen Prädikat-Funktion — `Start()`/`Stop()`/`Status()`/`New()` bleiben unverändert.

## Expected Behavior

- **Input:** Prozessstart von `cmd/server` mit Umgebungsvariable `GZ_ENV` (gesetzt oder ungesetzt).
- **Output:** Bei `GZ_ENV=staging` läuft der Prozess normal hoch (HTTP-Server, alle Routen inkl. `/api/scheduler/status`), aber `cron.Start()` wird nicht aufgerufen — keine Job-Ticks, keine `open-meteo`-Aufrufe durch den Scheduler. Bei jedem anderen Wert (inkl. ungesetzt) startet der Scheduler wie bisher.
- **Side effects:** Ein Log-Eintrag beim Start informiert, ob der Scheduler deaktiviert wurde. `/api/scheduler/status` zeigt weiterhin alle Jobs mit `next_run`, aber ohne `last_run`-Fortschritt (bleibt dauerhaft `null`, da nie ausgeführt).

## Acceptance Criteria

- **AC-1:** Given `GZ_ENV=staging` ist gesetzt / When der Go-Server startet / Then wird `cron.Start()` nicht aufgerufen — keine registrierte Job-Funktion feuert, somit erfolgt kein `open-meteo`-Aufruf durch den Scheduler.
  - Test: Unit-Test ruft `scheduler.SchedulerEnabled(cfg)` mit `cfg.Env = "staging"` auf und erwartet `false`; ergänzend Integrationstest, der `main`-Startpfad mit gesetztem `GZ_ENV=staging` simuliert und prüft, dass kein Cron-Tick innerhalb eines kurzen Zeitfensters erfolgt.

- **AC-2:** Given `GZ_ENV` ist nicht gesetzt (Produktions-Fall) / When der Go-Server startet / Then startet der Scheduler wie bisher und die 8 Cron-Einträge feuern nach ihrem jeweiligen Zeitplan — Prod-Verhalten bleibt unverändert.
  - Test: Unit-Test ruft `scheduler.SchedulerEnabled(cfg)` mit `cfg.Env = ""` auf und erwartet `true`.

- **AC-3:** Given `GZ_ENV` hat einen beliebigen Wert außer `staging` (z. B. leer, `dev`, `prod`, Tippfehler) / When `SchedulerEnabled` ausgewertet wird / Then liefert die Funktion `true` — der Scheduler läuft im Zweifel weiter, statt versehentlich auch anderswo lautlos zu deaktivieren (Fail-safe zugunsten von Produktion).
  - Test: Tabellengetriebener Unit-Test mit mehreren Nicht-`staging`-Werten (`""`, `"prod"`, `"Staging"` Groß-/Kleinschreibung, `"stagin"`), erwartet jeweils `true`.

- **AC-4:** Given der Scheduler wurde wegen `GZ_ENV=staging` nicht gestartet / When `GET /api/scheduler/status` aufgerufen wird / Then antwortet der Endpoint mit HTTP 200, listet alle registrierten Jobs mit `next_run`-Zeitstempel und `last_run: null`, ohne Panic oder Nil-Dereferenz.
  - Test: Integrationstest ruft den Handler mit einem `Scheduler`, dessen `New()` lief aber `Start()` nicht, auf und prüft Statuscode 200 sowie `last_run == nil` für jeden Job-Eintrag.

- **AC-5 (Betrieb, kein Code-Test):** Given der Fix ist auf Staging deployt und `gregor-api-staging` läuft / When man das Staging-Log über einen Beobachtungszeitraum (z. B. 30–60 Min) sichtet / Then erscheinen keine neuen scheduler-ausgelösten `open-meteo`-Requests (kein `[scheduler] ... → 2xx`-Log-Muster für die 8 Cron-Jobs), während `GET /api/health` weiterhin 200 liefert.
  - Nachweis: manuelle Staging-Verifikation nach Deploy, dokumentiert im Issue-Kommentar (Log-Auszug + Health-Check), kein automatisierter Test — Teil des Auslieferungsschritts, nicht der TDD-RED-Phase.

## Known Limitations

- Diese Spec deckt **nur Maßnahme A** ab (Scheduler-Deaktivierung auf Staging). Maßnahme B (E2E-Test-Datenmüll aufräumen), C (Forecast-Cache/TTL zur Kontingent-Schonung) und D (bezahlter open-meteo-Tarif) sind separate, hier nicht spezifizierte Arbeit — siehe Issue #1329 Gesamtanalyse.
- Der Rückbau der aktuell laufenden Sofort-Pause (Auto-Deploy-Cron auf dem Server reaktivieren + `gregor-api-staging`-Service wieder starten, siehe Memory `project_1329_openmeteo_quota_staging_paused`) ist ein reiner Deploy-/Betriebsschritt nach diesem Fix, kein Code-Acceptance-Criterion dieser Spec.
- Der Python-Scheduler-Pfad (Trigger-Endpoints über Port 8001) bleibt unverändert nutzbar für manuelle E2E-Auslösung auf Staging — er ist nicht Teil des hier deaktivierten autonomen Go-Cron-Tickers.
- `/api/scheduler/status` liefert weiterhin `"running": true` unabhängig vom tatsächlichen `Start()`-Aufruf (bestehendes Verhalten, nicht Teil dieses Fixes) — das Feld beschreibt aktuell "Scheduler-Objekt existiert", nicht "Cron tickt". Eine Korrektur dieses Feldes ist explizit Out-of-Scope für Maßnahme A.
- **(Adversary F001)** Im deaktivierten Zustand (Staging) zeigt `/api/scheduler/status` für jeden Job `"next_run": "0001-01-01T00:00:00Z"` (Go-Null-Zeit), da `robfig/cron` `Entry.Next` erst beim Ticken (`Start()`) berechnet. Der Endpoint antwortet weiterhin mit 200 und listet alle Jobs (AC-4 erfüllt), aber der `next_run`-Wert ist ohne Aussagekraft. Kosmetisch, kein Fehlverhalten — bewusst nicht korrigiert, da eine Sonderbehandlung des Status-Outputs über Maßnahme A hinausginge (analog zum `running:true`-Feld). Sammel-Eintrag #1199.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-1329-A
- **Rationale:** Bestehende Umgebungs-Kennung `GZ_ENV` wiederverwenden statt einer neuen Variable — sie wird bereits in `internal/router/router.go:197` für denselben Zweck (Staging-Verhalten unterscheiden) gelesen, ist in der Staging-`.env` verifiziert gesetzt (`GZ_ENV=staging`) und in der Prod-`.env` verifiziert ungesetzt. Exakter Wertevergleich (`== "staging"`, nicht `!= ""`) macht Prod-Schutz strukturell robust: fehlt `GZ_ENV` oder hat es einen unerwarteten Wert, läuft der Scheduler weiter — es gibt kein „auf Prod vergessen, den Scheduler wieder anzuschalten". Alternative (neue dedizierte Variable `GZ_SCHEDULER_DISABLED`) wurde verworfen, da sie eine zusätzliche, leicht zu vergessende Betriebs-Variable eingeführt hätte, ohne einen Vorteil gegenüber der bereits etablierten und verifizierten `GZ_ENV`-Kennung zu bieten.

## Changelog

- 2026-07-20: Initial spec created — Issue #1329, Maßnahme A
