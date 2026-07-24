---
entity_id: egress_guard_go
type: module
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [egress, isolation, staging, security, go]
workflow: feat-1337-go-egress-guard
---

<!-- Issue #1337 — Scheibe „Go-Prozess": Wächter im zweiten Prozess + Async-Lücke -->

# Egress Guard Go — Wächter für den Go-Dienst (Scheibe „Go-Prozess" von #1337)

## Approval

- [x] Approved (PO, 2026-07-23: „go 400" — inkl. LoC-Rahmen 400)

## Purpose

Der zentrale Egress-Wächter (Scheibe A, `src/app/egress_guard.py`) schützt heute nur den
**Python**-Prozess. Der zweite Prozess des Systems — der Go-Dienst `gregor-api` — telefoniert
in Staging völlig ungebremst nach draußen: open-meteo (Kontingent, geteilt mit Prod),
Nominatim, Komoot, Höhen-API, Google-OAuth, BetterStack-Heartbeats und SMTP-Versand über
`net/smtp`. Damit ist genau das Muster wieder da, das #1337 abstellen will: eine Tür bewacht,
die zweite offen. Diese Scheibe schließt sie mit **demselben Inventar und derselben
Entscheidungsregel** und schließt zusätzlich die verbliebene Async-Lücke auf der Python-Seite.

## Source

- **File:** `internal/egress/guard.go` (NEU), `internal/egress/inventory.go` (NEU)
- **Identifier:** `egress.Install(cfg) bool`, `egress.Uninstall()`, `egress.SMTPAllowed(host) error`, `egress.Inventory`, `egress.Kind`
- **Ergänzt:** `src/app/egress_guard.py` (Async-Transport)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/config.Config` (`Env`, `TestFixtureDir`) | module | Einzige Quelle der Aktivierungsentscheidung im Go-Dienst |
| `net/http` (`http.DefaultTransport`) | stdlib | Gemeinsamer Ausgang **aller** Go-HTTP-Clients im Repo (alle erzeugen `&http.Client{Timeout: …}` ohne eigenen `Transport`) |
| `net/smtp` | stdlib | Zweiter, HTTP-fremder Ausgang — Mailversand aus dem Go-Dienst |
| `cmd/server/main.go` | module | Einziger Prozess-Einstieg → einzige Bootstrap-Stelle |
| `internal/mail/sender.go` | module | Bestehende Guard-Linien (`recipientBlocked` #1122, `resendBlocked`) — die Egress-Linie tritt **zusätzlich** davor, ersetzt nichts |
| `src/app/egress_guard.py` | module | Inventar-Referenz (Single Source of Truth) + Async-Erweiterung |
| `docs/specs/modules/egress_guard.md` | spec | Scheibe A — Mechanik, Entscheidungsregel, Prüfdatum |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/egress/guard.go` | CREATE | `Install`/`Uninstall`, guarded `http.RoundTripper`, `SMTPAllowed`, Entscheidungsregel |
| `internal/egress/inventory.go` | CREATE | Host-Inventar (`Kind`: `TestAccess`/`Blocked`), deckungsgleich mit Python |
| `internal/egress/guard_test.go` | CREATE | Tripwire, Durchlass, Prod-No-Op, Aufrufstellen-Erbschaft, Idempotenz — netzfrei |
| `cmd/server/main.go` | MODIFY | Ein Aufruf `egress.Install(cfg)` direkt nach `config.Load()` |
| `internal/mail/sender.go` | MODIFY | `egress.SMTPAllowed(cfg.Host)` als erste Prüfung in `dialAndSend` |
| `internal/mail/sender_egress_test.go` | CREATE | SMTP-Host in Staging geblockt, in Prod unverändert, bestehende Guards intakt |
| `src/app/egress_guard.py` | MODIFY | `httpx.AsyncHTTPTransport.handle_async_request` patchen + Restore; Inventar-Ergänzungen |
| `tests/tdd/test_egress_guard_async.py` | CREATE | Async-Pfad: Tripwire, Durchlass, Prod-No-Op |
| `tests/test_egress_inventory_drift.py` | CREATE | Python- und Go-Inventar müssen Host-für-Host deckungsgleich sein |
| `docs/specs/modules/egress_guard.md` | MODIFY | Verweis auf diese Scheibe in „Known Limitations" |

### Estimated Changes

- Files: 6 neu, 4 geändert
- LoC: ~300 (davon ~180 Tests) — **über dem 250er-Rahmen**, PO-Freigabe für 400 wird mit der
  Spec-Abnahme eingeholt. Ohne Anhebung müsste die Scheibe künstlich in zwei Workflows
  zerfallen (Go-HTTP / Go-SMTP+Async), was die Inventar-Kopplung über einen Zwischenstand
  hinweg offen ließe.

## Test Plan

Kern-Schicht, deterministisch, ohne Netz. Beweisführung wie in Scheibe A über einen
**Sentinel-Transport**: Der Transport unter dem Wächter wird durch einen `RoundTripper`
ersetzt, der bei Erreichen einen Marker-Fehler liefert. Blockiert der Wächter, wird der
Sentinel nie erreicht (Beweis „geblockt vor dem Netz"); lässt er durch, feuert der Sentinel
(Beweis „durchgelassen" ohne ein gesendetes Byte). Kein Mock-Theater: geprüft wird
Erreichbarkeit des Transports, nicht eine zurückgespiegelte Annahme.

### Automated Tests (TDD RED)

- [ ] Test 1 — Go-Tripwire: undeklarierter Host in Staging → Fehler, Sentinel nie erreicht.
- [ ] Test 2 — Go-Durchlass: `nominatim.openstreetmap.org` (TEST_ACCESS) → Sentinel feuert.
- [ ] Test 3 — Erbschaft der Aufrufstellen: ein Client, der wie im Produktivcode als
  `&http.Client{Timeout: …}` **ohne** eigenen `Transport` gebaut wird, unterliegt dem Wächter.
- [ ] Test 4 — Prod-No-Op: `Env=""`/`"production"` → `http.DefaultTransport` bleibt
  zeiger-identisch, `Install` meldet „nicht installiert".
- [ ] Test 5 — BetterStack geblockt: `uptime.betterstack.com` in Staging → Fehler.
- [ ] Test 6 — Idempotenz + Restore: doppelter `Install`, danach `Uninstall` → Original-Transport
  zeiger-identisch wiederhergestellt.
- [ ] Test 7 — SMTP-Linie: `mail.Send` an undeklarierten SMTP-Host in Staging → Fehler vor dem
  Verbindungsaufbau; bestehende `resendBlocked`/`recipientBlocked`-Fehler bleiben unverändert.
- [ ] Test 8 — Python-Async-Tripwire: undeklarierter Host über `httpx.AsyncClient` → `EgressBlockedError`.
- [ ] Test 9 — Python-Async-Durchlass + Prod-No-Op.
- [ ] Test 10 — Inventar-Drift: Test schlägt rot, sobald ein Host nur in einer der beiden
  Quelldateien steht oder unterschiedlich eingestuft ist.

## Implementation Details

### Ein Andockpunkt statt zehn

`egress.Install(cfg)` ersetzt `http.DefaultTransport` durch einen `http.RoundTripper`, der vor
dem Weiterreichen `req.URL.Hostname()` gegen das Inventar prüft. **Verifizierter Befund:** Alle
externen Go-Clients (`internal/provider/openmeteo`, `internal/resolver/{googlemaps,elevation,komoot}`,
`internal/handler/auth_oauth`, `internal/scheduler.pingHeartbeat`) erzeugen ihre Clients als
`&http.Client{Timeout: …}` ohne eigenen `Transport` und benutzen damit `http.DefaultTransport`.
Es muss **keine einzige Aufrufstelle** angefasst werden — das Go-Pendant zum Python-Monkeypatch.

### Aktivierungsbedingung (fail-open Richtung Prod)

Installiert wird nur bei `cfg.Env == "staging"` **oder** gesetztem `cfg.TestFixtureDir`. Jeder
andere Zustand — leer, Tippfehler, andere Groß-/Kleinschreibung — ist ein No-Op mit
Prod-Verhalten. Exakt die Richtung von `scheduler.SchedulerEnabled` (#1329): Ein
Konfigurationsfehler darf den Produktivbetrieb **nie** lahmlegen. Beim Installieren geht genau
eine Log-Zeile raus (`[egress] Wächter aktiv — N Hosts deklariert`), in Prod keine.

### Entscheidungsregel (identisch zu Scheibe A)

`TestAccess` → durchlassen · `Blocked` → Fehler · nicht deklariert → Fehler (Tripwire) ·
`localhost`/`127.0.0.1` → generisch frei (Python-Core-Proxy, MQ, Frontend).

### SMTP separat

`net/smtp` läuft nicht über `http.DefaultTransport`. `dialAndSend` in `internal/mail/sender.go`
bekommt `egress.SMTPAllowed(cfg.Host)` als erste Zeile — damit sind alle drei Sendewege
(`Send`, `SendVerificationMail`, `SendWithFallback`) abgedeckt. Ist der Wächter nicht
installiert, gibt `SMTPAllowed` immer `nil` zurück; die bestehenden Linien `recipientBlocked`
und `resendBlocked` bleiben unangetastet.

### Inventar-Ergänzungen (auf beiden Seiten identisch)

| Host | Kind | Begründung |
|---|---|---|
| `nominatim.openstreetmap.org` | TestAccess | kostenlos, nebenwirkungsfrei; Ortsanlage muss auf Staging funktionieren |
| `api.open-elevation.com` | TestAccess | dito (Höhenabfrage) |
| `www.komoot.com` | TestAccess | dito (Tour-Import) |
| `maps.app.goo.gl`, `goo.gl`, `www.google.com`, `maps.google.com` | TestAccess | Auflösung geteilter Google-Maps-Links (`followGoogleMapsRedirect` folgt einer Nutzer-URL) |
| `www.googleapis.com`, `oauth2.googleapis.com`, `accounts.google.com` | TestAccess | Google-Login auf Staging |
| `uptime.betterstack.com` | **Blocked** | Staging darf keine Prod-Heartbeats grün pingen — das wäre Falsch-Grün im Monitoring |
| `api.open-meteo.com`, `air-quality-api.open-meteo.com` | TestAccess (unverändert) | Einstufung gehört fachlich zu #1333 — hier nur die Andockstelle, keine stille Umwidmung |

### Warum Doppel-Liste + Drift-Test statt geteilter Datei

Eine gemeinsame JSON-Datei wäre die reine Lehre, scheitert aber an der Werkzeugkette:
`go:embed` kann keine Datei außerhalb des Paketverzeichnisses einbinden — es bräuchte doch
wieder eine Kopie. Und die live verifizierte Python-Scheibe A müsste von Code- auf
Datei-Inventar umgebaut werden, mit Pfadauflösung je systemd-Unit als neuer stiller
Fehlerquelle. Der Drift-Test (`tests/test_egress_inventory_drift.py`, Vorbild
`tests/test_adr_index_drift.py`) parst beide Quelldateien und erzwingt Deckungsgleichheit —
dieselbe Garantie, kein Laufzeitrisiko.

### Python-Async

`httpx.AsyncHTTPTransport.handle_async_request` wird mit derselben `_is_allowed`-Entscheidung
gepatcht, die wahre Originalreferenz beim Modul-Import eingefangen und in
`uninstall_egress_guard()` mit restauriert. Heute gibt es keinen `httpx.AsyncClient` in
`src/`/`api/` — der Patch ist Vorsorge, damit der erste async-Aufruf nicht still am Wächter
vorbeigeht.

## Expected Behavior

- **Input:** `config.Config` des Go-Dienstes; ausgehende HTTP-Requests und SMTP-Verbindungen aus
  beliebigen Go-Paketen; auf der Python-Seite zusätzlich async-httpx-Requests
- **Output:** In Staging/Test entweder durchgelassener Ruf (deklarierter `TestAccess`-Host) oder
  Fehler vor dem Netz-Touch; in Prod unverändertes Verhalten
- **Side effects:** Austausch von `http.DefaultTransport` innerhalb des Prozesslebenszyklus;
  genau eine Log-Zeile beim Installieren; keine Persistenz

## Acceptance Criteria

- **AC-1:** Given der Go-Dienst läuft mit `GZ_ENV=staging` / When ein HTTP-Ruf an einen Host geht, der im Inventar nicht deklariert ist / Then wird der Ruf mit einem Egress-Fehler abgebrochen und der darunterliegende Transport wird nie erreicht
  - Test: `internal/egress/guard_test.go::TestUndeclaredHostBlockedBeforeTransport`

- **AC-2:** Given der Go-Dienst läuft mit `GZ_ENV=staging` / When ein HTTP-Ruf an einen als `TestAccess` deklarierten Host geht (z.B. `nominatim.openstreetmap.org`) / Then lässt der Wächter durch und der darunterliegende Transport wird erreicht
  - Test: `internal/egress/guard_test.go::TestDeclaredHostPassesThrough`

- **AC-3:** Given ein HTTP-Client wird genau so gebaut wie im Produktivcode — `&http.Client{Timeout: …}` ohne eigenen `Transport` / When er in Staging einen undeklarierten Host ruft / Then greift der Wächter ebenfalls, ohne dass die Aufrufstelle geändert wurde
  - Test: `internal/egress/guard_test.go::TestPlainClientInheritsGuard`

- **AC-4:** Given `GZ_ENV` ist leer oder `production` und `GZ_TEST_FIXTURE_DIR` ist nicht gesetzt / When `egress.Install(cfg)` aufgerufen wird / Then bleibt `http.DefaultTransport` zeiger-identisch zum Original und `Install` meldet, dass nicht installiert wurde
  - Test: `internal/egress/guard_test.go::TestProdIsNoOp`

- **AC-5:** Given der Go-Dienst läuft mit `GZ_ENV=staging` / When der Scheduler-Heartbeat `uptime.betterstack.com` pingen will / Then wird der Ping geblockt, damit Staging keine Produktions-Heartbeats grün meldet
  - Test: `internal/egress/guard_test.go::TestHeartbeatHostBlocked`

- **AC-6:** Given `egress.Install(cfg)` wurde bereits aufgerufen / When ein zweiter Aufruf erfolgt und danach `egress.Uninstall()` / Then ist `http.DefaultTransport` wieder zeiger-identisch zum Original (kein Doppel-Patch, einfache Restore-Kette)
  - Test: `internal/egress/guard_test.go::TestDoubleInstallIsIdempotent`

- **AC-7:** Given der Go-Dienst läuft mit `GZ_ENV=staging` / When `mail.Send` an einen SMTP-Host geht, der nicht als `TestAccess` deklariert ist / Then bricht der Versand vor dem Verbindungsaufbau ab, während die bestehenden Guards `resendBlocked` und `recipientBlocked` unverändert weiter greifen
  - Test: `internal/mail/sender_egress_test.go::TestSMTPHostBlockedInStaging`, `::TestExistingGuardsStillApply`

- **AC-8:** Given der Python-Prozess läuft im Test-/Staging-Modus / When ein Ruf über `httpx.AsyncClient` an einen undeklarierten Host geht / Then wirft der Wächter `EgressBlockedError`, und ein `TestAccess`-Host wird durchgelassen
  - Test: `tests/tdd/test_egress_guard_async.py::test_async_undeclared_host_blocked`, `::test_async_declared_host_passes`

- **AC-9:** Given `env="production"` und `is_test_mode=False` auf der Python-Seite / When `install_egress_guard(settings)` läuft / Then bleibt auch `httpx.AsyncHTTPTransport.handle_async_request` unverändert (beweisbarer No-Op)
  - Test: `tests/tdd/test_egress_guard_async.py::test_async_prod_no_patch`

- **AC-10:** Given das Host-Inventar existiert in einer Python- und einer Go-Quelldatei / When ein Host nur in einer der beiden Dateien steht oder unterschiedlich eingestuft ist / Then schlägt der Drift-Test rot und benennt den abweichenden Host
  - Test: `tests/test_egress_inventory_drift.py::test_inventories_are_identical`

- **AC-11:** Given der Staging-Go-Dienst wurde mit dieser Änderung deployt / When er startet und anschließend eine Ortsanlage über einen Ortsnamen durchgeführt wird / Then steht genau eine `[egress] Wächter aktiv`-Zeile im Staging-Log, die Ortsauflösung funktioniert weiterhin, und im Prod-Log erscheint die Zeile nicht
  - Test: Staging-Verifikation in Phase `/70-deploy` (Log-Beleg + Klickpfad)

## Known Limitations

- Go-Clients, die künftig einen **eigenen** `Transport` setzen, umgehen den Wächter. Heute tut
  das keiner (verifiziert); ein Wächter dagegen (z.B. Lint-Regel) ist bewusst nicht Teil dieser
  Scheibe.
- Der Go-Wächter greift nicht automatisch in `go test`; Go-Tests fremder Pakete bleiben
  unverändert. Bewusst — die Aktivierung hängt allein an der Konfiguration.
- Scheiben B (SMS-Feinschliff #1336), C (Telegram-alle-Methoden + Test-Token) und E
  (Resend-Relay infra#114) sind nicht Teil dieser Spec.
- Die open-meteo-Einstufung bleibt `TestAccess`; die Kontingent-Trennung ist #1333.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Fortschreibung der in Scheibe A getroffenen Interceptor-Entscheidung auf den
  zweiten Prozess — kein neues Entscheidungsfeld. Die einzige eigenständige Entscheidung
  (Doppel-Liste + Drift-Test statt geteilter Inventar-Datei) ist oben mit Begründung und
  verworfener Alternative dokumentiert.

## Regel-Budget

Kein neues Gate, keine neue Pflichtregel — der Drift-Test ist ein normaler Kern-Test und
erweitert den bestehenden Guard. Das Prüfdatum der Scheibe A (**2026-10-19**) gilt mit.

## Changelog

- 2026-07-23: Initial spec — Issue #1337, Scheibe „Go-Prozess" + Python-Async-Lücke
