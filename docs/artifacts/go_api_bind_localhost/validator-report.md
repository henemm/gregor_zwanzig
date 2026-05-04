---
spec: docs/specs/bugfix/go_api_bind_localhost.md
date: 2026-05-03T16:36:00Z
server_staging: https://staging.gregor20.henemm.com
server_prod: https://gregor20.henemm.com
external_ip: 178.104.143.19
verdict: BROKEN
---

# External Validator Report

**Spec:** `docs/specs/bugfix/go_api_bind_localhost.md`
**Datum:** 2026-05-03 16:36 UTC
**Server (Staging):** https://staging.gregor20.henemm.com
**Server (Prod, in Acceptance Criteria referenziert):** https://gregor20.henemm.com
**Externe IP unter Test:** 178.104.143.19

## Checklist

| # | Acceptance Criterion (aus Spec) | Beweis | Verdict |
|---|---|---|---|
| 1 | Vor Fix: `curl -m 5 http://178.104.143.19:8090/` → HTTP 401 | Historisch — nicht prüfbar (Vor-Zustand) | UNKLAR |
| 2 | Nach Fix: `curl -m 5 http://178.104.143.19:8090/` → Connection refused / Timeout | Antwortet HTTP 401 (Backend reagiert direkt) | **FAIL** |
| 3 | Nach Fix: `curl -m 5 http://178.104.143.19:8091/` → Connection refused / Timeout | `curl: (7) Failed to connect ... port 8091` | **PASS** |
| 4 | Nach Fix: `ss -tulnH \| grep ':8090\|:8091'` zeigt `127.0.0.1:8090` und `127.0.0.1:8091` | `127.0.0.1:8091` ✓ aber `*:8090` (alle Interfaces) | **FAIL** |
| 5 | Nach Fix: `curl https://gregor20.henemm.com/api/health` → HTTP 200 | HTTP 200, Body `{"python_core":"ok","status":"ok","version":"0.1.0"}` | **PASS** |
| 6 | Nach Fix: `curl https://staging.gregor20.henemm.com/api/health` → HTTP 200 | HTTP 200, Body `{"python_core":"ok","status":"ok","version":"0.1.0"}` | **PASS** |
| 7 | Unit-Test `TestLoad_DefaultHost` grün | Code-Tests dürfen vom Validator nicht geprüft werden (kein src/-Read) | UNKLAR |
| 8 | Unit-Test `TestLoad_HostOverride` grün | dito | UNKLAR |

## Findings

### F1 — Production-Port 8090 ist extern weiterhin direkt erreichbar (CRITICAL)

- **Severity:** CRITICAL
- **Acceptance Criteria betroffen:** #2, #4
- **Expected:** Connection refused / Timeout; `ss` zeigt `127.0.0.1:8090`
- **Actual:**
  - `curl -m 5 http://178.104.143.19:8090/` → `HTTP/1.1 401 Unauthorized`, Body `{"error":"unauthorized"}`, Header `X-Content-Type-Options: nosniff` (Go-Backend, nicht Nginx)
  - `curl -m 5 http://178.104.143.19:8090/api/health` → `HTTP/1.1 200 OK`, Body `{"python_core":"ok","status":"ok","version":"0.1.0"}` — Backend liefert komplette Health-Response **direkt** an externe IP, ohne Nginx-Layer
  - `ss -tulnH`:
    ```
    tcp LISTEN 0  4096   127.0.0.1:8091   0.0.0.0:*
    tcp LISTEN 0  4096           *:8090           *:*
    ```
- **Evidence:** Live-Antworten des Servers zum Zeitpunkt 2026-05-03 16:36 UTC (siehe oben).
- **Impact:** Die in der Spec adressierte Security-Lücke (henemm-security#70, CVSS 7.5) besteht für **Production** unverändert fort. Nginx-Security-Layer (HSTS, CSP, Rate-Limits, Auth-Header) wird umgangen. `/api/health` ist sogar ohne Auth direkt vom Internet beantwortbar.

### F2 — Staging-Port 8091 ist korrekt gehärtet (PASS)

- **Severity:** N/A (positives Ergebnis)
- **Expected:** `127.0.0.1:8091`, externer Zugriff abgelehnt
- **Actual:**
  - `ss` zeigt `127.0.0.1:8091`
  - `curl http://178.104.143.19:8091/...` → Connection refused
  - `curl https://staging.gregor20.henemm.com/api/health` → 200 (Nginx-Pfad intakt)
- **Evidence:** Siehe Checklist #3, #6.

### F3 — Funktionale Erreichbarkeit via Nginx unverändert (PASS, beide Umgebungen)

- **Severity:** N/A
- **Beweise:**
  - `https://gregor20.henemm.com/api/health` → 200
  - `https://staging.gregor20.henemm.com/api/health` → 200
  - `https://gregor20.henemm.com/api/scheduler/status` → 200, Jobs liefern `last_run` ok
  - `https://staging.gregor20.henemm.com/api/scheduler/status` → 200
- **Bedeutung:** Nginx-Proxy-Pfad (`proxy_pass http://127.0.0.1:8090/8091`) funktioniert weiterhin. Kein Funktionsregress.

## Verdict: BROKEN

### Begründung

Der Fix ist nur **teilweise deployed**: Staging (Port 8091) bindet wie gefordert auf `127.0.0.1`. Production (Port 8090) bindet jedoch unverändert auf alle Interfaces (`*:8090`) und ist damit direkt aus dem öffentlichen Internet erreichbar. Zwei harte Acceptance-Criteria-Punkte (Spec-Zeilen 135–137) schlagen fehl:

- Externer `curl` auf 8090 antwortet mit HTTP 401 / 200 statt Connection refused
- `ss` zeigt `*:8090` statt `127.0.0.1:8090`

Das ist exakt das in der Spec als „BROKEN" beschriebene Vor-Fix-Verhalten — die HIGH-Security-Lücke (CVSS 7.5) gilt für Production weiterhin offen. Solange Production nicht ebenfalls deployed ist, kann die Spec nicht als erfüllt gelten.

### Was zur VERIFIED-Bewertung fehlt

1. Production-Service neu starten **mit aktivem Bind-Host-Fix** (entweder Code-Deploy auf Prod oder Service-Env-Override). Erwartetes Ergebnis:
   - `ss -tulnH` zeigt `127.0.0.1:8090`
   - `curl -m 5 http://178.104.143.19:8090/api/health` → Connection refused
2. `https://gregor20.henemm.com/api/health` muss weiterhin 200 liefern (Regressionscheck).
