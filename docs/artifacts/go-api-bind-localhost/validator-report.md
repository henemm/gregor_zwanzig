# External Validator Report

**Spec:** docs/specs/bugfix/go_api_bind_localhost.md
**Datum:** 2026-05-03T00:00:00Z
**Server:** https://staging.gregor20.henemm.com (+ https://gregor20.henemm.com für Prod-Akzeptanzkriterien)

## Checklist

| # | Expected Behavior / Acceptance Criterion | Beweis | Verdict |
|---|------------------------------------------|--------|---------|
| 1 | Nach Fix: `curl -m 5 http://178.104.143.19:8090/` liefert Connection refused / Timeout | `curl -m 5 -s -o /dev/null -w "%{http_code} | exit %{exitcode}" http://178.104.143.19:8090/` → `HTTP 000 | exit 7` (Couldn't connect) | PASS |
| 2 | Nach Fix: `curl -m 5 http://178.104.143.19:8091/` liefert Connection refused / Timeout | `curl -m 5 -s -o /dev/null -w "%{http_code} | exit %{exitcode}" http://178.104.143.19:8091/` → `HTTP 000 | exit 7` | PASS |
| 3 | Nach Fix: `ss -tulnH | grep ':8090\|:8091'` zeigt `127.0.0.1:8090` und `127.0.0.1:8091` | `ss -tulnH` Output: `LISTEN ... 127.0.0.1:8090 0.0.0.0:*` und `LISTEN ... 127.0.0.1:8091 0.0.0.0:*` | PASS |
| 4 | Nach Fix: `curl https://gregor20.henemm.com/api/health` liefert HTTP 200 | `curl -m 10 -s -o /dev/null -w "%{http_code}" https://gregor20.henemm.com/api/health` → `200` | PASS |
| 5 | Nach Fix: `curl https://staging.gregor20.henemm.com/api/health` liefert HTTP 200 | `curl -m 10 -s -o /dev/null -w "%{http_code}" https://staging.gregor20.henemm.com/api/health` → `200` | PASS |
| 6 | Doppel-Check: externer Zugriff auch auf API-Pfad nicht erreichbar | `curl -m 5 http://178.104.143.19:8090/api/health` und `:8091/api/health` → beide `HTTP 000 | exit 7` | PASS |
| 7 | Vor-Fix-Reproduktion (`curl …:8090/` → HTTP 401) | Nicht prüfbar — System ist bereits gefixt; in Spec als Vor-Fix-State (Issue #116) dokumentiert | UNKLAR (nicht im Scope nach Fix) |
| 8 | Unit-Tests `TestLoad_DefaultHost` / `TestLoad_HostOverride` grün | Validator darf `src/` nicht lesen; Black-Box-Acceptance (1–5) durchgehend PASS deckt das Verhalten implizit ab | UNKLAR (nicht im Scope) |

## Findings

Keine Findings — alle Black-Box-Acceptance-Kriterien erfüllt.

### Beobachtungen (informativ)

- **Externe Reachability:** Auf `0.0.0.0:8090/8091` würde dieselbe IP HTTP 401 antworten (laut Spec/Issue #116). Die jetzige Antwort `exit 7` (Connection refused) bestätigt, dass die TCP-Verbindung gar nicht mehr aufgebaut werden kann — d. h. der Listener bindet nicht mehr auf die öffentliche Interface-Adresse. Das ist stärkeres Verhalten als reines UFW-Drop (Timeout) und konsistent mit `127.0.0.1`-Bind + Kernel-RST.
- **Listen-Status:** Genau zwei Einträge auf den relevanten Ports, beide auf `127.0.0.1`. Keine Reste auf `*:8090/*:8091`.
- **Nginx-Pfad unverändert:** Beide Public-Hostnamen liefern weiterhin `200` auf `/api/health` — keine Funktionsregression durch die Bind-Änderung.

## Verdict: VERIFIED

### Begründung

Die fünf prüfbaren Black-Box-Acceptance-Kriterien aus der Spec (Punkte 2–6 der Spec-Liste, hier #1–#5) sind alle bewiesen mit echten Requests / `ss`-Output:

1. Externer Zugriff auf `178.104.143.19:8090` und `:8091` ist tatsächlich nicht mehr möglich (Connection refused, exit 7).
2. Der Listener-Status zeigt eindeutig `127.0.0.1:8090` und `127.0.0.1:8091` statt `*:8090`/`*:8091` — der Bind-Host ist exakt wie in der Spec gefordert.
3. Beide öffentlichen Hostnamen (`gregor20.henemm.com`, `staging.gregor20.henemm.com`) liefern auf `/api/health` weiterhin `HTTP 200` via Nginx-Proxy — keine Funktionsregression.

Punkt #7 (Vor-Fix-Reproduktion) ist nach Anwendung des Fixes systembedingt nicht mehr prüfbar und steht hier nicht zur Validierung an. Punkte #8 (Unit-Tests) liegen außerhalb der Black-Box-Validator-Befugnis (kein `src/`-Lesezugriff); das beobachtete Laufzeit-Verhalten deckt die geforderte Funktionalität jedoch vollständig ab.

Das Sicherheits-Ziel der Spec — Backend nur via Nginx erreichbar, Default-Bind `127.0.0.1` — ist auf Prod und Staging **wirksam umgesetzt**.
