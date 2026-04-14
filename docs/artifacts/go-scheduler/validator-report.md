# External Validator Report

**Spec:** docs/specs/modules/go_scheduler.md
**Datum:** 2026-04-14T18:03:00+02:00
**Server:** https://gregor20.henemm.com
**Validator-Run:** 3 (nach Fix von Run-2-Issues: Auth-401 gefixt, Format angepasst)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | 5 Cron-Jobs laufen im Hintergrund | Go-Log: `[scheduler] Started: 5 jobs, timezone Europe/Vienna` | **PASS** |
| 2 | Timezone Europe/Vienna | Status: `"timezone": "Europe/Vienna"` | **PASS** |
| 3 | `GET /api/scheduler/status` erreichbar | HTTP 200, JSON mit 5 Jobs (Run-2 Fix: Auth-401 behoben) | **PASS** |
| 4 | Status: `running`, `timezone`, `jobs` Felder | Alle vorhanden | **PASS** |
| 5 | Status: `last_run` Tracking | Korrekt nach Ausfuehrung: `{"time":"...","status":"ok","error":""}` | **PASS** |
| 6 | Inbound Commands alle 5 Min (Ausfuehrung) | Go-Log: `/api/scheduler/inbound-commands → 200` um 15:55, 16:00 UTC | **PASS** |
| 7 | Alert Checks alle 30 Min (Ausfuehrung) | Go-Log: `/api/scheduler/alert-checks → 200` um 16:00 UTC | **PASS** |
| 8 | Trip Reports stuendlich (Ausfuehrung) | Go-Log: `/api/scheduler/trip-reports → 200` um 16:00 UTC | **PASS** |
| 9 | Evening Subscriptions um 18:00 (Ausfuehrung) | Go-Log: `Running evening subscriptions...` + Heartbeat um 16:00 UTC = 18:00 Vienna | **PASS** |
| 10 | Heartbeat nach Evening Subscriptions | Go-Log: `Heartbeat ping OK: ...Ba2k2av4` direkt nach Evening | **PASS** |
| 11 | Morning Subscriptions um 07:00 | Nicht testbar (naechster Lauf morgen 07:00) | **UNKLAR** |
| 12 | Heartbeat nach Morning Subscriptions | Nicht testbar (naechster Lauf morgen 07:00) | **UNKLAR** |
| 13 | Jobs blockieren sich nicht | 4 Jobs feuerten gleichzeitig um 18:00, alle erfolgreich (200) | **PASS** |
| 14 | POST /api/scheduler/morning-subscriptions → 200 | `{"status":"ok","count":1}` via localhost:8000 | **PASS** |
| 15 | POST /api/scheduler/evening-subscriptions → 200 | `{"status":"ok","count":0}` via localhost:8000 | **PASS** |
| 16 | POST /api/scheduler/trip-reports → 200 | `{"status":"ok","count":0}` via localhost:8000 | **PASS** |
| 17 | POST /api/scheduler/alert-checks → 200 | `{"status":"ok","count":0}` via localhost:8000 | **PASS** |
| 18 | POST /api/scheduler/inbound-commands → 200 | `{"status":"ok","count":0}` via localhost:8000 | **PASS** |
| 19 | POST trip-reports?hour=7 → 200 | `{"status":"ok","count":1}` via localhost:8000 | **PASS** |
| 20 | Response Format `{"status":"ok","count":N}` | Alle 5+1 Trigger-Endpoints bestaetigt | **PASS** |
| 21 | Status: `next_run` korrekt pro Job | next_run-Werte sind den FALSCHEN Job-IDs zugeordnet (4/5 falsch) | **FAIL** |
| 22 | Python-nicht-erreichbar Fehlerbehandlung | Nicht testbar ohne destruktive Aktion | **UNKLAR** |

**Score: 18/22 PASS, 1 FAIL, 3 UNKLAR**

## Findings

### F1: next_run im Status-Endpoint den falschen Jobs zugeordnet (CRITICAL)

- **Severity:** CRITICAL
- **Expected:** Jeder Job zeigt seinen eigenen naechsten Cron-Zeitpunkt als `next_run`
- **Actual:** Die `next_run`-Werte sind zyklisch zwischen den Jobs vertauscht. 4 von 5 Jobs zeigen die `next_run` eines ANDEREN Jobs.
- **Evidence:** Status-Response abgerufen um 18:03 Vienna (nach dem 18:00-Lauf):

| Job ID | Angezeigtes next_run | Impliziertes Cron-Pattern | Spec-Cron | Erwartetes next_run |
|--------|---------------------|--------------------------|-----------|-------------------|
| morning_subscriptions | **18:05** | `*/5 * * * *` | `0 7 * * *` | 2026-04-15 07:00 |
| evening_subscriptions | **18:30** | `0,30 * * * *` | `0 18 * * *` | 2026-04-15 18:00 |
| trip_reports_hourly | **19:00** ✓ | `0 * * * *` | `0 * * * *` | 19:00 ✓ |
| alert_checks | **2026-04-15 07:00** | `0 7 * * *` | `0,30 * * * *` | 18:30 |
| inbound_command_poll | **2026-04-15 18:00** | `0 18 * * *` | `*/5 * * * *` | 18:05 |

- **Verifikationsmethode:** Zwei Zeitpunkte verglichen (17:53 und 18:03). Das Fortschreiten der next_run-Werte bestaetigt die falschen Zuordnungen:
  - `morning_subscriptions` schritt von 17:55 → 18:05 fort (5-Min-Takt, nicht taeglich)
  - `inbound_command_poll` blieb bei morgen 07:00 (taeglich, nicht 5-Min-Takt)
- **WICHTIG:** Die **tatsaechliche Job-Ausfuehrung ist KORREKT** — die Go-Logs beweisen, dass die richtigen Endpoints zu den richtigen Zeiten aufgerufen werden. Nur die Status-Anzeige ist falsch.
- **Impact:** Externes Monitoring (`henemm-infra/check-gregor20.sh`) nutzt `next_run` um festzustellen ob Jobs laufen. Falsche `next_run`-Werte fuehren zu:
  1. Falschen Alarmen (z.B. "morning_subscriptions laeuft alle 5 Min statt taeglich")
  2. Verpassten echten Ausfaellen (z.B. inbound-poll Ausfall wird nicht erkannt weil next_run auf morgen zeigt)
- **Root Cause (Hypothese):** Die `Status()`-Methode iteriert ueber `s.cron.Entries()` und mapped die Entry-IDs auf die Job-Identifier-Liste in falscher Reihenfolge. `robfig/cron` vergibt Entry-IDs in Registrierungsreihenfolge, aber die Status-Map ordnet sie mit einem Offset zu.

### F2: Trigger-Endpoints hinter Go-Auth-Middleware (LOW)

- **Severity:** LOW
- **Expected:** Spec zeigt manuellen Trigger gegen `localhost:8000` (Python direkt)
- **Actual:** Trigger via Go-Proxy (`https://gregor20.henemm.com/api/scheduler/*`) gibt 401 zurueck. Via Python direkt (`localhost:8000`) funktioniert einwandfrei.
- **Evidence:** `POST https://gregor20.henemm.com/api/scheduler/morning-subscriptions` → `{"error":"unauthorized"} HTTP 401`
- **Impact:** Minimal. Go-Scheduler ruft Python intern auf localhost:8000 auf (korrekt). Auth schuetzt vor externem Missbrauch (sinnvoll). Spec-Beispiel nutzt localhost:8000.

### F3: Run-2-Issues behoben (INFO)

- **Severity:** INFO (positiv)
- **Evidence:**
  - `GET /api/scheduler/status` gibt jetzt 200 zurueck (war 401 in Run 2)
  - `timezone`-Feld ist jetzt vorhanden
  - `id` ist jetzt string mit sprechenden Namen (sinnvolle Verbesserung gegenueber Spec-int)
  - `name` und `last_run`-Felder sind zusaetzlich vorhanden (Erweiterung)

## Verdict: BROKEN

### Begruendung

**Kern-Scheduling: VOLLSTAENDIG KORREKT**

Die zentrale Aufgabe — "Go-Scheduler triggert Python-Endpoints via HTTP POST" — funktioniert einwandfrei:
- Alle 5 Jobs feuern zu den korrekten Zeiten (Log-Beweis)
- Alle 5 Jobs rufen die korrekten Python-Endpoints auf (Log-Beweis)
- Heartbeat nach Evening Subscriptions funktioniert (Log-Beweis)
- Alle Python Trigger-Endpoints antworten korrekt mit `{"status":"ok","count":N}`
- `last_run`-Tracking funktioniert korrekt
- Optional-Parameter `?hour=N` funktioniert

**Status-Endpoint: BROKEN**

Der `GET /api/scheduler/status` Endpoint — obwohl jetzt erreichbar (Run-2-Fix) — zeigt fuer **4 von 5 Jobs falsche `next_run`-Werte** an. Die Werte sind zyklisch zwischen den Jobs vertauscht. Da das externe Monitoring diesen Endpoint nutzt um Ausfaelle zu erkennen, ist dies ein CRITICAL Bug der die Zuverlaessigkeit des gesamten Monitoring untergräbt.

**Warum BROKEN statt AMBIGUOUS:** Der Status-Endpoint ist nicht optional — er ist explizit in der Spec definiert und wird vom externen Monitoring-System als primaere Datenquelle genutzt. Falsche `next_run`-Werte machen Monitoring-Entscheidungen unzuverlaessig.

### Fix-Empfehlung

Die `Status()`-Methode muss die cron.Entry-IDs korrekt auf die Job-Identifier mappen. Vermutlich reicht es, die Zuordnung in der Entries-Iteration zu korrigieren (z.B. durch Speichern der Entry-ID bei `AddFunc()` und Zuordnung in einer Map).
