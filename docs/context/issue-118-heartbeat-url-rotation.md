# Issue #118 — BetterStack-Heartbeat-URLs aus Public-Repo entfernen

## Symptom

Zwei Heartbeat-URLs liegen hardcoded im public Git-Repo (5 Dateien, 4+ Commits in der History). Angreifer kann gefälschte "Alles-OK"-Pings senden → echte Ausfälle würden nicht alarmieren (Fail-Closed → Fail-Open).

Aktive Heartbeat-Pings laufen sowohl im Go-Scheduler (`internal/scheduler/scheduler.go:135/148`) als auch im Python-Scheduler (`src/web/scheduler.py:143/154`).

## Root Cause

Defaults in `internal/config/config.go:19/20` und Konstanten in `src/web/scheduler.py:40/41` enthalten die URLs als Klartext. Tests asserten gegen exakte URLs. Specs zeigen sie als Code-Beispiel.

## Affected Files

| Datei | Änderung |
|---|---|
| `internal/config/config.go` | Defaults auf `""` (leer); ENV-Variable optional |
| `internal/scheduler/scheduler.go` | `pingHeartbeat`: bei leerem URL einmalige MQ-Notification (sync.Once) statt nur Skip |
| `internal/notify/mq.go` (neu) | Helper `SendMQ(...)` für POST an `localhost:3457/send` |
| `src/web/scheduler.py` | Konstanten via `os.getenv("GZ_HEARTBEAT_MORNING", "")`; `_ping_heartbeat` bei leerem URL skip + einmalige MQ |
| `src/lib/mq_notify.py` (neu) | Python-Pendant zu `notify/mq.go` |
| `tests/tdd/test_betterstack_heartbeat.py` | Asserts auf Pattern (`startswith("https://uptime.betterstack.com/api/v1/heartbeat/")`) statt exakte URL; neue Tests für Empty-URL-Behavior |
| `internal/scheduler/scheduler_test.go` | Test für MQ-Notification bei leerem Heartbeat-URL |
| `docs/specs/modules/betterstack_heartbeat.md` | URLs durch `<HEARTBEAT_MORNING_URL>` / `<HEARTBEAT_EVENING_URL>` ersetzen |
| `docs/specs/modules/go_scheduler.md` | dito |
| `CLAUDE.md` (project) | Hinweis "Heartbeats wurden entfernt (April 2026)" korrigieren — Go-Scheduler pingt weiter |

## Architektur-Entscheidung

**Fail-soft + MQ-Notification** (User-Entscheidung):
- ENV-Variable leer → kein Ping
- ENV-Variable leer UND noch nicht gemeldet → MQ-Send an `infra` (priority `normal`)
- MQ-Send fehlt (kein `CLAUDE_MQ_SECRET`, kein Service) → Log-Warn, Service läuft trotzdem

Dadurch:
- Service crasht nie an fehlender Heartbeat-Konfiguration
- Fehlkonfiguration wird sichtbar (MQ erreicht infra)
- Deployment kann ohne ENV-Variable laufen → URL-Rotation hat kein Race

## MQ-API Vertrag

```
POST http://127.0.0.1:3457/send
Headers: Content-Type: application/json
         X-MQ-Secret: $CLAUDE_MQ_SECRET
Body: {"sender":"gregor","recipient":"infra","priority":"normal","subject":"...","body":"..."}
```

Falls `CLAUDE_MQ_SECRET` ENV nicht gesetzt → Helper gibt sofort zurück (kein POST, kein Crash).

## Risiko-Analyse

- **Service-Restart resettet `sync.Once`** → bei jedem Restart eine MQ wenn ENV fehlt. Kein Problem (Restart-Frequenz niedrig, eine MQ pro Restart akzeptabel)
- **Git-History hat URLs für immer** — deshalb müssen die URLs in BetterStack rotiert werden, NICHT nur Code-Cleanup
- **Test-Datei testet aktuell mit echten URLs** — muss umgestellt werden, sonst RED-Tests laufen mit alten Werten
- **Migrations-Phase Python+Go beide pingen** — beide Stellen müssen synchron umgestellt werden, sonst inkonsistenter Zustand

## Test-Strategie

Go-Tests:
- `TestPingHeartbeat_EmptyURL_NoCrash` — kein Panic, kein HTTP-Call
- `TestPingHeartbeat_EmptyURL_SendsMQOnce` — sync.Once: erste leere URL triggert MQ, zweite tut nichts mehr

Python-Tests (umgestellt):
- `test_heartbeat_morning_url_pattern` — assert URL startswith BetterStack-Domain ODER ist leer
- `test_ping_heartbeat_empty_url_no_crash`
- `test_ping_heartbeat_empty_url_sends_mq_once`

Live-Verifikation:
- Service ohne ENV starten → MQ an infra
- Service mit ENV starten → BetterStack erhält Heartbeat (alte URL → 404 nach Rotation, neue → 200)

## User-Aktion (außerhalb des Codes)

1. BetterStack-Dashboard: alte Morning + Evening Heartbeats löschen
2. Zwei neue erstellen mit gleichen Namen
3. Neue URLs in `/home/hem/gregor_zwanzig/.env` (Prod) und `/home/hem/gregor_zwanzig_staging/.env` (Staging) eintragen → ggf. via MQ an infra delegieren

## Scope

- Code: 6 Dateien (4 modifiziert, 2 neu) ~120 LoC
- Specs: 3 Dateien (Anonymisierung)
- Doku: CLAUDE.md
- Tests: 2 Dateien (umgestellt + erweitert) ~50 LoC

Insgesamt mittel — größer als die letzten zwei Stories.

## Bezug

- MQ #14479 von infra
- Voraussetzung: Issue #116 (Backend bind localhost) ✅, Issue #117 (Register Rate-Limit) ✅
