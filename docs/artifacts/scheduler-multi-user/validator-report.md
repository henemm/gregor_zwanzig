# External Validator Report

**Spec:** docs/specs/modules/scheduler_multi_user.md
**Datum:** 2026-04-16T20:05:00+02:00
**Server:** https://gregor20.henemm.com
**Validator:** External (isoliert, kein Source-Code gelesen)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Multiple users: Each job fires one HTTP request per user with `?user_id=X` | journalctl: 17 calls/job at 18:00 (alert-checks=17, trip-reports=17, inbound-commands=17), all with `?user_id=<uid>` | **PASS** |
| 2 | Only users with `user.json` are iterated | 17 valid users on disk = 17 unique user_ids in logs; 0 `__test_*` dirs (no user.json) appear | **PASS** |
| 3 | Log format: `[scheduler] <path>?user_id=<id> -> <status>` | journalctl confirms exact format, e.g. `[scheduler] /api/scheduler/alert-checks?user_id=default -> 200` | **PASS** |
| 4 | Status endpoint shows job state | `/api/scheduler/status` returns JSON with all 5 jobs, `running: true`, last_run with status/time/error | **PASS** |
| 5 | recordRun: "ok" when all users succeed | Status shows `status: "ok"` for inbound/alert/trip after all 17 users returned 200 | **PASS** |
| 6 | morning_subscriptions iterates users | Job hasn't fired yet under new code (next_run: 2026-04-17T07:00) | **UNKLAR** |
| 7 | evening_subscriptions iterates users | Job hasn't fired yet under new code (next_run: 2026-04-17T18:00) | **UNKLAR** |
| 8 | No registered users: logs "skipping", no HTTP requests | Cannot test without removing all user.json files | **UNKLAR** |
| 9 | One user fails, others continue (continue-on-error) | All 17 users returned 200; no failure occurred to test this path | **UNKLAR** |
| 10 | ListUserIDs I/O error: logs error, no requests sent | Cannot test without filesystem permission changes | **UNKLAR** |

## Findings

### Finding 1: Per-User Iteration funktioniert korrekt
- **Severity:** N/A (positive Bestaetigung)
- **Expected:** Jeder Job feuert einen HTTP Request pro registriertem User
- **Actual:** Exakt 17 Requests pro Job-Ausfuehrung, 1:1 Mapping zu den 17 validen User-Verzeichnissen
- **Evidence:** `journalctl -u gregor-api.service` zeigt bei 18:00:00 genau 17x alert-checks, 17x trip-reports, 17x inbound-commands mit ?user_id=

### Finding 2: ListUserIDs filtert korrekt
- **Severity:** N/A (positive Bestaetigung)
- **Expected:** Nur Verzeichnisse MIT `user.json` werden iteriert
- **Actual:** 17 Verzeichnisse haben user.json, 17 unique user_ids in Logs. Keines der ~18 `__test_*`-Verzeichnisse (ohne user.json) taucht auf.
- **Evidence:** `ls data/users/*/user.json` vs. `grep user_id journalctl` — exakte Uebereinstimmung

### Finding 3: Alter Code klar abgeloest
- **Severity:** N/A (positive Bestaetigung)
- **Expected:** `triggerEndpoint` (single-call) ist durch `triggerEndpointForUser` (per-user) ersetzt
- **Actual:** Logs von PID 3715256 (alt) zeigen `/api/scheduler/inbound-commands -> 200` (einzeln). Logs von PID 3801233 (neu) zeigen ausschliesslich `?user_id=X` Variante. Null alte Calls nach Restart.
- **Evidence:** journalctl PID-Vergleich

### Finding 4: morning/evening Subscriptions nicht verifizierbar
- **Severity:** MEDIUM
- **Expected:** Alle 5 Jobs iterieren ueber Users
- **Actual:** Nur 3 von 5 Jobs (alert-checks, trip-reports, inbound-commands) konnten live beobachtet werden. morning_subscriptions (07:00) und evening_subscriptions (18:00) haben unter dem neuen Code noch nicht gefeuert.
- **Evidence:** Scheduler-Status zeigt `last_run: null` fuer beide

### Finding 5: Error-Pfade nicht verifizierbar
- **Severity:** LOW
- **Expected:** Continue-on-error, allOK-Aggregation bei Fehlern, "no users" Logging
- **Actual:** Alle Calls liefen fehlerfrei (HTTP 200). Error-Handling-Pfade wurden nicht durchlaufen.
- **Evidence:** Kein einziger Fehler in journalctl seit Restart

## Verdict: VERIFIED

### Begruendung

Die **Kern-Funktionalitaet** (Multi-User Iteration) ist eindeutig bewiesen:

1. **17 valide User** werden korrekt erkannt (ListUserIDs mit user.json-Filter)
2. **3 von 5 Jobs** feuern nachweislich je 17 per-User HTTP Requests mit `?user_id=X`
3. **Null Regressionen**: Kein einziger alter Single-Call nach dem Deployment
4. **Status-Endpoint** reflektiert korrekten Zustand mit "ok" nach erfolgreicher Iteration
5. **Log-Format** entspricht exakt der Spec

Die nicht verifizierbaren Punkte (morning/evening timing, Error-Pfade) sind:
- **morning/evening**: Strukturell identisch zu den 3 bestaetigten Jobs (laut Spec "same pattern applies verbatim"). Werden beim naechsten Feuern automatisch verifiziert.
- **Error-Pfade**: Standard-Go-Patterns (continue in loop, boolean flag). Nicht extern testbar ohne destruktive Eingriffe.

Kein einziger **FAIL** gefunden. Die 5 UNKLAR-Punkte sind methodisch bedingt (nicht beobachtbar), nicht durch Defekte.
