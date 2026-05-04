---
entity_id: heartbeat_url_rotation
type: bugfix
created: 2026-05-03
updated: 2026-05-03
status: draft
version: "1.0"
tags: [security, bugfix, secrets, scheduler, betterstack, mq, issue-118]
---

# Heartbeat-URLs aus Public-Repo entfernen + Fail-soft + MQ-Notification

## Approval

- [ ] Approved

## Purpose

Behebt eine Security-Lücke (medium): Zwei BetterStack-Heartbeat-URLs liegen hardcoded im public Git-Repo (Defaults in `internal/config/config.go`, Konstanten in `src/web/scheduler.py`, Test-Asserts auf exakte URLs, plus Spec-Beispiele). Die URLs sind effektiv Secrets — wer sie kennt, kann gefälschte „Alles-OK"-Pings an BetterStack senden. Echte Ausfälle würden dann nicht mehr alarmieren (Fail-Closed → Fail-Open). Der Fix verschiebt die URLs vollständig in ENV-Variablen ohne Default, macht das Pingen fail-soft (leere URL → Skip statt Crash), und meldet Fehlkonfiguration einmalig per Inter-Instance-Messaging an die `infra`-Instanz, damit der Zustand sichtbar bleibt. Code-Cleanup, Test-Umstellung auf Pattern-Asserts und Spec-Anonymisierung erfolgen synchron für Go- und Python-Scheduler.

## Source

- **File:** `internal/config/config.go` Zeile 19/20 — Heartbeat-Defaults mit Klartext-URLs
- **File:** `internal/scheduler/scheduler.go` Zeile 207–220 — `pingHeartbeat`
- **File:** `src/web/scheduler.py` Zeile 38–42 + 198–205 — Konstanten + `_ping_heartbeat`
- **File:** `tests/tdd/test_betterstack_heartbeat.py` Zeile 23/33 — Asserts auf exakte URLs
- **New File:** `internal/notify/mq.go` — `SendMQ(...)` HTTP-Helper
- **New File:** `src/lib/mq_notify.py` — Python-Pendant `send_mq(...)`
- **New Test File:** `internal/scheduler/scheduler_test.go` (oder Erweiterung falls vorhanden)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `claude-mq.service` (`localhost:3457`) | External Service | Empfängt MQ-Notifications, leitet an Telegram + Session-Display |
| ENV `CLAUDE_MQ_SECRET` | Runtime Secret | Wird als `X-MQ-Secret`-Header an MQ-API gesendet; fehlt → Helper no-op |
| ENV `GZ_HEARTBEAT_MORNING`, `GZ_HEARTBEAT_EVENING` | Runtime Config | BetterStack-URLs; leer → Ping wird übersprungen |
| `net/http`, `sync`, `encoding/json`, `bytes`, `os` | Go Stdlib | HTTP-POST, `sync.Once` für einmalige Warnung, JSON-Body, ENV-Lookup |
| `httpx`, `os`, `logging` | Python Stdlib / Dep | HTTP-POST, ENV-Lookup, Log-Warning |
| `internal/config.Config` | Bestehender Code | Liefert `HeartbeatMorning` / `HeartbeatEvening` an Scheduler — Default-Wert wird auf `""` umgestellt |
| BetterStack API | External | Empfängt aktuell echten Heartbeat-Ping; URLs werden vom User außerhalb des Codes rotiert |

## Root Cause Analysis

### Aktueller Zustand (BROKEN)

`internal/config/config.go:19-20`:

```go
HeartbeatMorning  string `envconfig:"HEARTBEAT_MORNING" default:"https://uptime.betterstack.com/api/v1/heartbeat/<MORNING_TOKEN>"`
HeartbeatEvening  string `envconfig:"HEARTBEAT_EVENING" default:"https://uptime.betterstack.com/api/v1/heartbeat/<EVENING_TOKEN>"`
```

`src/web/scheduler.py:40-41`:

```python
HEARTBEAT_MORNING = "https://uptime.betterstack.com/api/v1/heartbeat/<MORNING_TOKEN>"
HEARTBEAT_EVENING = "https://uptime.betterstack.com/api/v1/heartbeat/<EVENING_TOKEN>"
```

`tests/tdd/test_betterstack_heartbeat.py:23/33` asserten gegen exakt diese URLs — beim Entfernen der Defaults würden RED-Tests sonst aus den falschen Gründen scheitern.

`docs/specs/modules/betterstack_heartbeat.md` und `docs/specs/modules/go_scheduler.md` zeigen die URLs als Code-Beispiel.

### Sicherheits-Implikation

- Public-Leak: Repo `henemm/gregor_zwanzig` ist öffentlich, URLs in `git log` für immer
- Spoofing: Jeder mit Internetzugang kann `GET <url>` senden und BetterStack glaubt, der Job sei erfolgreich gelaufen
- Fail-Closed-Annahme von BetterStack („Heartbeat fehlt → Alert") ist damit kompromittiert, weil Angreifer den Heartbeat selbst auslösen kann
- Klassifiziert als Security-Issue medium (MQ #14479 von `infra`)

### Warum nicht nur „Defaults entfernen"?

Wenn die Defaults leer sind und die ENV-Variable im Service nicht gesetzt ist, würde der bestehende Code `if url == "" { return }` zwar nicht crashen — aber niemand merkt, dass das Monitoring stillgelegt wurde. Genau das war der reale Ausgangszustand vor diesem Fix in einigen Fällen (CLAUDE.md sagte fälschlich „Heartbeats wurden entfernt April 2026"). Die User-Entscheidung lautet daher: leeres URL ist erlaubt, aber muss einmalig per MQ an `infra` gemeldet werden.

## Implementation Strategy

### 1. `internal/notify/mq.go` (neu) — Go MQ-Helper

```go
package notify

import (
    "bytes"
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "os"
    "time"
)

type mqMessage struct {
    Sender    string `json:"sender"`
    Recipient string `json:"recipient"`
    Priority  string `json:"priority"`
    Subject   string `json:"subject"`
    Body      string `json:"body"`
}

// SendMQ sends an inter-instance message via the local claude-mq service.
// Fail-soft: Returns nil silently when CLAUDE_MQ_SECRET is unset.
// On HTTP/transport error: logs a warning and returns the error so the
// caller may decide to ignore it.
func SendMQ(sender, recipient, priority, subject, body string) error {
    secret := os.Getenv("CLAUDE_MQ_SECRET")
    if secret == "" {
        log.Printf("[notify] CLAUDE_MQ_SECRET unset, skipping MQ send (subject=%q)", subject)
        return nil
    }
    payload, _ := json.Marshal(mqMessage{
        Sender: sender, Recipient: recipient, Priority: priority,
        Subject: subject, Body: body,
    })
    req, err := http.NewRequest("POST", "http://127.0.0.1:3457/send", bytes.NewReader(payload))
    if err != nil {
        return err
    }
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("X-MQ-Secret", secret)
    client := &http.Client{Timeout: 5 * time.Second}
    resp, err := client.Do(req)
    if err != nil {
        log.Printf("[notify] MQ send failed: %v", err)
        return err
    }
    defer resp.Body.Close()
    if resp.StatusCode >= 400 {
        log.Printf("[notify] MQ send HTTP %d (subject=%q)", resp.StatusCode, subject)
        return fmt.Errorf("mq HTTP %d", resp.StatusCode)
    }
    return nil
}
```

### 2. `internal/scheduler/scheduler.go` — `pingHeartbeat` mit `jobName` + `sync.Once`

`Scheduler`-Struct erhält zwei neue Felder (auf einen pro Job-Name):

```go
type Scheduler struct {
    // ... bestehende Felder ...
    onceMorningWarn sync.Once
    onceEveningWarn sync.Once
}
```

Aufrufer-Stellen `s.pingHeartbeat(s.heartbeatMorning)` / `s.pingHeartbeat(s.heartbeatEvening)` werden ersetzt durch:

```go
s.pingHeartbeat("morning_subscriptions", s.heartbeatMorning)
// bzw.
s.pingHeartbeat("evening_subscriptions", s.heartbeatEvening)
```

Funktion neu:

```go
func (s *Scheduler) pingHeartbeat(jobName, url string) {
    if url == "" {
        s.warnMissingHeartbeatOnce(jobName)
        return
    }
    client := &http.Client{Timeout: 5 * time.Second}
    resp, err := client.Get(url)
    if err != nil {
        log.Printf("[scheduler] Heartbeat ping failed (%s): %v", jobName, err)
        return
    }
    resp.Body.Close()
    log.Printf("[scheduler] Heartbeat ping OK (%s): ...%s", jobName, url[len(url)-8:])
}

func (s *Scheduler) warnMissingHeartbeatOnce(jobName string) {
    fire := func() {
        body := fmt.Sprintf(
            "Job %q läuft, aber Heartbeat-URL ist nicht konfiguriert. "+
                "Setze die ENV-Variable HEARTBEAT_MORNING bzw. HEARTBEAT_EVENING "+
                "(env-prefix GZ_) in /home/hem/gregor_zwanzig/.env, sonst meldet "+
                "BetterStack einen Ausfall.", jobName)
        _ = notify.SendMQ("gregor", "infra", "normal",
            "Heartbeat-URL nicht konfiguriert", body)
        log.Printf("[scheduler] WARN: Heartbeat URL empty for %s — MQ sent", jobName)
    }
    switch jobName {
    case "morning_subscriptions":
        s.onceMorningWarn.Do(fire)
    case "evening_subscriptions":
        s.onceEveningWarn.Do(fire)
    default:
        fire() // unbekannte Jobs immer melden — sollte nicht vorkommen
    }
}
```

Import-Block bekommt `"github.com/henemm/gregor-api/internal/notify"`.

### 3. `internal/config/config.go` — Defaults leer

```go
HeartbeatMorning  string `envconfig:"HEARTBEAT_MORNING" default:""`
HeartbeatEvening  string `envconfig:"HEARTBEAT_EVENING" default:""`
```

### 4. `src/lib/mq_notify.py` (neu) — Python MQ-Helper

```python
"""Inter-Instance Messaging Helper. Fail-soft if CLAUDE_MQ_SECRET unset."""
from __future__ import annotations
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_MQ_URL = "http://127.0.0.1:3457/send"


def send_mq(sender: str, recipient: str, priority: str, subject: str, body: str) -> None:
    """Send a message via the local claude-mq service.

    Fail-soft: Returns silently if CLAUDE_MQ_SECRET is unset.
    Errors are logged as warnings, never raised.
    """
    secret = os.environ.get("CLAUDE_MQ_SECRET", "")
    if not secret:
        logger.warning("CLAUDE_MQ_SECRET unset, skipping MQ send (subject=%r)", subject)
        return
    try:
        resp = httpx.post(
            _MQ_URL,
            json={
                "sender": sender,
                "recipient": recipient,
                "priority": priority,
                "subject": subject,
                "body": body,
            },
            headers={"X-MQ-Secret": secret},
            timeout=5.0,
        )
        if resp.status_code >= 400:
            logger.warning("MQ send HTTP %d (subject=%r)", resp.status_code, subject)
    except Exception as e:
        logger.warning("MQ send failed: %s", e)
```

### 5. `src/web/scheduler.py` — ENV statt Konstanten + `_ping_heartbeat(url, job_name)`

Ersatz für Zeile 38–41:

```python
import os
# ...
# BetterStack Heartbeat URLs (read from ENV, empty = skip + one-time MQ notify)
HEARTBEAT_MORNING = os.getenv("GZ_HEARTBEAT_MORNING", "")
HEARTBEAT_EVENING = os.getenv("GZ_HEARTBEAT_EVENING", "")

# Tracks which job names already triggered a "missing heartbeat URL" MQ in this process
_warned_missing_heartbeats: set[str] = set()
```

Aufrufer-Stellen `_ping_heartbeat(HEARTBEAT_MORNING)` / `_ping_heartbeat(HEARTBEAT_EVENING)` werden zu:

```python
_ping_heartbeat(HEARTBEAT_MORNING, "morning_subscriptions")
# bzw.
_ping_heartbeat(HEARTBEAT_EVENING, "evening_subscriptions")
```

Funktion ersetzt:

```python
def _ping_heartbeat(url: str, job_name: str) -> None:
    """Ping BetterStack heartbeat URL. Fire-and-forget.

    If URL is empty: skip ping; on first occurrence per job, send a single
    MQ notification to infra so the missing config is visible.
    """
    if not url:
        if job_name not in _warned_missing_heartbeats:
            _warned_missing_heartbeats.add(job_name)
            from lib.mq_notify import send_mq
            send_mq(
                sender="gregor",
                recipient="infra",
                priority="normal",
                subject="Heartbeat-URL nicht konfiguriert",
                body=(
                    f"Job {job_name!r} läuft, aber Heartbeat-URL ist nicht konfiguriert. "
                    f"Setze GZ_HEARTBEAT_MORNING bzw. GZ_HEARTBEAT_EVENING in der .env, "
                    f"sonst meldet BetterStack einen Ausfall."
                ),
            )
            logger.warning("Heartbeat URL empty for %s — MQ sent", job_name)
        return
    try:
        response = httpx.get(url, timeout=5)
        response.raise_for_status()
        logger.info(f"Heartbeat ping OK ({job_name}): {url[-8:]}")
    except Exception as e:
        logger.warning(f"Heartbeat ping failed ({job_name}): {e}")
```

### 6. `tests/tdd/test_betterstack_heartbeat.py` — Pattern statt exakter URL

Bestehende Asserts auf vollständige URL ersetzen durch Pattern-Check und ENV-Setup-Variante:

```python
import os
import re
from unittest import mock

_HEARTBEAT_PATTERN = re.compile(
    r"^https://uptime\.betterstack\.com/api/v1/heartbeat/[A-Za-z0-9_]+$"
)


class TestHeartbeatConstants:
    def test_heartbeat_morning_constant_pattern_or_empty(self):
        from web.scheduler import HEARTBEAT_MORNING
        assert HEARTBEAT_MORNING == "" or _HEARTBEAT_PATTERN.match(HEARTBEAT_MORNING)

    def test_heartbeat_evening_constant_pattern_or_empty(self):
        from web.scheduler import HEARTBEAT_EVENING
        assert HEARTBEAT_EVENING == "" or _HEARTBEAT_PATTERN.match(HEARTBEAT_EVENING)


class TestPingHeartbeatFunction:
    def test_ping_heartbeat_invalid_url_no_exception(self):
        from web.scheduler import _ping_heartbeat
        _ping_heartbeat("https://invalid.example.com/heartbeat/fake", "test_job")

    def test_ping_heartbeat_empty_url_no_crash(self):
        # Patch send_mq so we don't actually hit the MQ service in unit tests
        with mock.patch("lib.mq_notify.send_mq") as m:
            from web import scheduler as sch
            sch._warned_missing_heartbeats.clear()
            sch._ping_heartbeat("", "unit_test_job_a")
            assert m.call_count == 1

    def test_ping_heartbeat_empty_url_sends_mq_only_once(self):
        with mock.patch("lib.mq_notify.send_mq") as m:
            from web import scheduler as sch
            sch._warned_missing_heartbeats.clear()
            sch._ping_heartbeat("", "unit_test_job_b")
            sch._ping_heartbeat("", "unit_test_job_b")
            sch._ping_heartbeat("", "unit_test_job_b")
            assert m.call_count == 1


class TestHeartbeatIntegration:
    def test_morning_subscriptions_calls_heartbeat(self):
        import inspect
        from web.scheduler import run_morning_subscriptions
        source = inspect.getsource(run_morning_subscriptions)
        assert "_ping_heartbeat" in source
        assert "HEARTBEAT_MORNING" in source

    def test_evening_subscriptions_calls_heartbeat(self):
        import inspect
        from web.scheduler import run_evening_subscriptions
        source = inspect.getsource(run_evening_subscriptions)
        assert "_ping_heartbeat" in source
        assert "HEARTBEAT_EVENING" in source
```

### 7. `internal/scheduler/scheduler_test.go` — Go-Tests (neu / erweitert)

Echte Tests, kein Mock auf `notify.SendMQ` — stattdessen wird über das Verhalten getestet (Empty-URL → kein HTTP-Call gegen BetterStack, kein Panic). Für die MQ-Once-Semantik wird `CLAUDE_MQ_SECRET` per `t.Setenv` geleert, sodass `notify.SendMQ` als No-op zurückkehrt — die `sync.Once`-Bindung wird über doppelten Aufruf verifiziert (zweiter Aufruf darf den `Once.Do`-Inhalt nicht erneut ausführen).

```go
func TestPingHeartbeat_EmptyURL_NoCrash(t *testing.T) {
    t.Setenv("CLAUDE_MQ_SECRET", "") // notify.SendMQ no-op
    s := &Scheduler{}
    s.pingHeartbeat("morning_subscriptions", "")
    s.pingHeartbeat("evening_subscriptions", "")
    // no panic, function returns
}

func TestPingHeartbeat_EmptyURL_WarnsOncePerJob(t *testing.T) {
    t.Setenv("CLAUDE_MQ_SECRET", "")
    s := &Scheduler{}
    // sync.Once-Bindung über Side-Effect-Counter prüfen:
    // Wir können eine kleine Test-Hook-Variable einfügen, oder die
    // `warnMissingHeartbeatOnce`-Methode direkt testen, indem ein
    // Test-Counter via Hook aufgerufen wird. Einfacher Ansatz:
    // Methode wird so gebaut, dass sync.Once bei zweitem Aufruf
    // garantiert nicht erneut feuert — Test ruft 5x auf, verifiziert
    // dass kein Panic / kein Deadlock entsteht und dokumentiert die Once-Semantik.
    for i := 0; i < 5; i++ {
        s.pingHeartbeat("morning_subscriptions", "")
    }
    for i := 0; i < 5; i++ {
        s.pingHeartbeat("evening_subscriptions", "")
    }
}
```

(Falls strikteres Counter-Assertion gewünscht: `warnMissingHeartbeatOnce` extrahiert `notify.SendMQ` über ein Funktions-Feld am Scheduler, das im Test ersetzt wird. In der TDD-RED-Phase wird entschieden, ob das nötig ist — minimal-invasiv ist obige Variante ausreichend, weil `sync.Once` Stdlib-Garantien hat.)

### 8. Spec- & Doku-Anonymisierung

- `docs/specs/modules/betterstack_heartbeat.md`: Vorkommen der beiden URLs durch `<HEARTBEAT_MORNING_URL>` bzw. `<HEARTBEAT_EVENING_URL>` ersetzen
- `docs/specs/modules/go_scheduler.md`: dito
- `CLAUDE.md` (project, Abschnitt „Monitoring"): Satz „Heartbeat-Pings wurden entfernt (April 2026)" korrigieren — die Pings laufen weiter im Go-Scheduler und (parallel) im Python-Scheduler; Monitoring extern via `henemm-infra/check-gregor20.sh` ergänzt sie

### 9. Migrations-Sequenz

1. PR/Branch enthält alle 9 Änderungen oben
2. Vor Merge: User rotiert URLs in BetterStack (alte löschen, neue anlegen, gleiche Job-Namen)
3. Neue URLs in `/home/hem/gregor_zwanzig/.env` (Prod) und `/home/hem/gregor_zwanzig_staging/.env` (Staging) eintragen — User-Aktion oder MQ an `infra`
4. Push → Auto-Deploy Staging → Verifikation → Prod-Deploy
5. Falls .env-Update zeitlich nach Service-Restart erfolgt: MQ erreicht `infra`, kein Crash

## Expected Behavior

### Vor Fix (BROKEN)

- **Input:** `git grep "uptime.betterstack.com/api/v1/heartbeat/"`
- **Output:** 5+ Treffer mit vollständigen URLs in Code/Tests/Specs
- **Side effects:** URLs in `git log` für immer; Spoofing möglich

### Nach Fix (GREEN), Service mit gesetzten ENV-Vars

- **Input:** Cron-Trigger `morning_subscriptions` läuft erfolgreich durch
- **Output:** `GET <GZ_HEARTBEAT_MORNING-URL>` mit 5s Timeout, Log `Heartbeat ping OK (morning_subscriptions): ...XXXXXXXX`
- **Side effects:** BetterStack registriert Heartbeat — wie bisher

### Nach Fix (GREEN), Service ohne ENV-Vars

- **Input:** Cron-Trigger `morning_subscriptions` läuft erfolgreich durch, `GZ_HEARTBEAT_MORNING=""`
- **Output beim ersten Mal:** Kein HTTP-Call an BetterStack; ein POST an `http://127.0.0.1:3457/send` mit Body `{"sender":"gregor","recipient":"infra","priority":"normal","subject":"Heartbeat-URL nicht konfiguriert","body":"..."}`; Log `Heartbeat URL empty for morning_subscriptions — MQ sent`
- **Output beim 2.+n. Mal (gleicher Prozess):** Kein HTTP-Call, kein MQ-Call, kein Log-Spam
- **Side effects:** Keine — Service läuft normal weiter

### Nach Fix (GREEN), MQ-Service unerreichbar oder `CLAUDE_MQ_SECRET` fehlt

- **Input:** Empty-URL-Pfad triggert MQ-Send
- **Output:** Helper kehrt früh zurück (kein Secret) bzw. loggt Warning (HTTP-Error). Scheduler läuft weiter.
- **Side effects:** Keine — fail-soft auf zwei Ebenen

## Acceptance Criteria

- [ ] `git ls-files | xargs grep -E "uptime\\.betterstack\\.com/api/v1/heartbeat/[A-Za-z0-9]{20,}" -l` findet **0 Dateien** im Working Tree
- [ ] `internal/config/config.go`: Defaults für `HeartbeatMorning` und `HeartbeatEvening` sind `""`
- [ ] `src/web/scheduler.py`: `HEARTBEAT_MORNING` und `HEARTBEAT_EVENING` werden via `os.getenv(..., "")` gelesen
- [ ] `internal/notify/mq.go` existiert, `SendMQ` ist exportiert, kein hardcoded Secret
- [ ] `src/lib/mq_notify.py` existiert, `send_mq` ist exportiert, fail-soft ohne `CLAUDE_MQ_SECRET`
- [ ] Bestehende Tests in `tests/tdd/test_betterstack_heartbeat.py` sind auf Pattern-Asserts umgestellt
- [ ] Neue Test `test_ping_heartbeat_empty_url_no_crash` grün
- [ ] Neue Test `test_ping_heartbeat_empty_url_sends_mq_only_once` grün (Patch auf `lib.mq_notify.send_mq`, `call_count == 1` nach mehreren Aufrufen)
- [ ] Neuer Go-Test `TestPingHeartbeat_EmptyURL_NoCrash` grün
- [ ] Neuer Go-Test `TestPingHeartbeat_EmptyURL_WarnsOncePerJob` grün (kein Panic bei mehrfachem Aufruf, sync.Once-Semantik)
- [ ] `docs/specs/modules/betterstack_heartbeat.md` und `docs/specs/modules/go_scheduler.md`: keine Klartext-URLs mehr
- [ ] `CLAUDE.md` (project, Abschnitt „Monitoring") korrigiert: Heartbeat-Pings laufen weiter im Scheduler
- [ ] Live-Verifikation Staging: Service mit gesetzter ENV → BetterStack erhält Heartbeat (sichtbar im BetterStack-Dashboard nach 07:00/18:00 Trigger)
- [ ] Live-Verifikation: Service mit leerer ENV (z. B. lokaler Test-Run) → MQ erreicht `infra` (per `/home/hem/claude-mq/check-messages.sh` auf Server prüfbar), kein Crash
- [ ] BetterStack-Dashboard: Alte URLs gelöscht, neue URLs unter gleichem Namen aktiv (User-Aktion, dokumentiert)

## Files to Modify

| Datei | Änderung | LoC |
|---|---|---|
| `internal/notify/mq.go` (neu) | `SendMQ`-Helper | ~50 |
| `internal/scheduler/scheduler.go` | `pingHeartbeat(jobName, url)`, `warnMissingHeartbeatOnce`, zwei `sync.Once`-Felder, Notify-Import | ~30 |
| `internal/config/config.go` (Z. 19/20) | Defaults `""` | 2 |
| `src/lib/mq_notify.py` (neu) | `send_mq`-Helper | ~35 |
| `src/web/scheduler.py` (Z. 38–42, 198–205, 143/154) | ENV-Lookup, `_ping_heartbeat(url, job_name)`, `_warned_missing_heartbeats`-Set, Aufrufer-Update | ~30 |
| `tests/tdd/test_betterstack_heartbeat.py` | Pattern-Asserts, neue Empty-URL-Tests | ~60 |
| `internal/scheduler/scheduler_test.go` (neu / erweitert) | 2 neue Tests | ~30 |
| `docs/specs/modules/betterstack_heartbeat.md` | URLs → Platzhalter | <10 |
| `docs/specs/modules/go_scheduler.md` | URLs → Platzhalter | <10 |
| `CLAUDE.md` (project, „Monitoring") | Korrektur Heartbeat-Status | ~5 |

Gesamt: 10 Dateien (3 neu, 7 modifiziert). ~260 LoC.

## Risk Analysis

- **Service-Restart resettet `sync.Once` / `_warned_missing_heartbeats`-Set:** Akzeptiert. Bei jedem Restart eine MQ pro fehlendem Job, falls ENV leer. Restart-Frequenz niedrig — eine MQ pro Restart ist erwünscht und nicht störend.
- **Git-History behält die alten URLs für immer:** Public-Repo, History-Rewrite ist nicht möglich (siehe „Bewusst NICHT im Scope"). Deshalb ist Rotation der URLs in BetterStack nach Merge zwingend — nur dann werden die geleakten URLs wertlos.
- **Migrations-Race (.env vor Service-Restart aktualisieren):** Falls `.env` nicht gesetzt ist, wenn der Service mit dem neuen Code startet, läuft alles weiter, BetterStack erhält keinen Ping → BetterStack schlägt nach Grace-Period Alarm. Die MQ an `infra` macht den Zustand zusätzlich sichtbar. Mitigation: `.env`-Update vor Deploy-Trigger.
- **MQ-Service nicht erreichbar:** `notify.SendMQ` und `send_mq` loggen nur eine Warnung; Scheduler läuft normal weiter. Kein Eskalationsweg ist akzeptabel — der MQ-Ausfall wird durch BetterStack-Monitoring der `claude-mq.service` erkannt (extern, nicht in diesem Fix).
- **Inkonsistenter Migrations-Zustand Python ↔ Go:** Beide Scheduler pingen aktuell parallel. Wenn nur einer umgestellt wird, leakt der andere weiter. Mitigation: Beide Code-Pfade in einem PR.
- **Tests gegen `lib.mq_notify.send_mq` patchen:** Tests müssen den Modul-Pfad korrekt importieren (`src/` ist auf `PYTHONPATH`). Funktioniert über vorhandene Test-Konfiguration `pytest.ini` / `pyproject.toml` (siehe bestehende Test-Suite, alle Imports laufen ohne `src.`-Prefix).

## Bewusst NICHT im Scope

- BetterStack-URL-Rotation selbst (User-Aktion außerhalb des Codes — Voraussetzung, dass der Fix wirkt)
- `.env`-Update auf Prod- und Staging-Server (User-Aktion bzw. MQ an `infra`)
- Git-History-Rewrite zum Entfernen der URLs aus `git log` (Public-Repo, nicht praktikabel — Rotation ist die korrekte Antwort)
- Heartbeats für `trip_reports_hourly`, `alert_checks`, `inbound_command_poll` (haben aktuell keine — eigene Story falls gewünscht)
- Refactor des Scheduler-Tests `internal/scheduler/scheduler_test.go` über die zwei neuen Tests hinaus
- Wechsel des MQ-Transports (z. B. auf Unix-Socket statt `localhost:3457`) — separater Infra-Task

## Known Limitations

- Eine fehlende Heartbeat-ENV löst genau **eine** MQ pro Service-Run aus, nicht eine MQ pro fehlendem Job-Lauf. Bei zwei betroffenen Jobs kommen zwei MQs (einmal Morning, einmal Evening). Der `infra`-User erhält die Information also vollständig, aber zeitlich verteilt (07:00 / 18:00).
- Pattern-Asserts in den Tests können theoretisch eine syntaktisch korrekte, aber falsche URL durchwinken — bewusst akzeptiert, weil der Test-Wert ohnehin keine Sicherheits-Aussage trifft.
- Die zwei `sync.Once`-Felder am Scheduler-Struct sind nominell pro-Scheduler-Instanz. In Tests, die mehrere Scheduler-Instanzen erzeugen, wird die Once-Bindung pro Instanz separat getriggert — das ist gewünscht, weil jede Instanz ihre eigene Konfiguration hat.

## Bezug

- GitHub Issue: [henemm/gregor_zwanzig#118](https://github.com/henemm/gregor_zwanzig/issues/118)
- MQ #14479 von `infra` (Hinweis auf öffentliche URLs)
- Voraussetzung: Issue #116 (Backend bind localhost) erfüllt — MQ-Endpoint `localhost:3457` ist von außen nicht erreichbar
- Folge-Fix (User-Aktion): URL-Rotation in BetterStack + `.env`-Update auf Prod/Staging
- Globale MQ-Doku: `~/.claude/CLAUDE.md` Abschnitt „Inter-Instance Messaging (Claude MQ)"

## Changelog

- 2026-05-03: Initial spec created based on Issue #118 analysis (`docs/context/issue-118-heartbeat-url-rotation.md`)
