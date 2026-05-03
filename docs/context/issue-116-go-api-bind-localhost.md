# Issue #116 — Go-API bindet auf 0.0.0.0 statt 127.0.0.1

## Symptom

Backend-Ports 8090 (Prod) und 8091 (Staging) sind direkt aus dem Internet erreichbar. Nginx als Gateway (mit HSTS, CSP, Rate-Limits, Security-Headern) wird umgangen.

Verifikation:
```
ss -tulnH | grep ':8090\|:8091'
  *:8091   *:*
  *:8090   *:*

curl -m 5 http://178.104.143.19:8090/   → 401 (Backend antwortet)
curl -m 5 http://178.104.143.19:8091/   → 401
```

## Root Cause

`cmd/server/main.go:115`:
```go
http.ListenAndServe(":"+cfg.Port, r)
```

Leeres Host-Prefix bedeutet in Go: bind auf alle Interfaces (`0.0.0.0` und IPv6 `::`).

`internal/config/config.go` hat aktuell kein `Host`-Feld.

## Affected Files

| Datei | Änderung |
|---|---|
| `internal/config/config.go` | Neues Feld `Host string envconfig:"HOST" default:"127.0.0.1"` |
| `cmd/server/main.go` (Zeile 115) | `cfg.Host+":"+cfg.Port` statt `":"+cfg.Port` |
| `internal/config/config_test.go` | Default-Test + Override-Test für `Host` |

ENV-Variable heißt effektiv `GZ_HOST` (Prefix `GZ` aus `envconfig.Process("GZ", &cfg)`).

## Risiko-Analyse

- Nginx Prod: `proxy_pass http://127.0.0.1:8090` (Datei `nginx/gregor20.henemm.com.conf`) → funktioniert weiter
- Nginx Staging: `proxy_pass http://127.0.0.1:8091` (Datei `nginx/staging.gregor20.henemm.com.conf`) → funktioniert weiter
- Service-Files setzen kein `GZ_HOST` → Default greift, kein Service-File-Update nötig

## Test-Strategie

Pre-Fix Verifikation (extern):
```
curl -m 5 http://178.104.143.19:8090/   → 401
```

Post-Fix Verifikation:
```
ss -tulnH | grep ':8090\|:8091'
  → 127.0.0.1:8090 (statt *:8090)
  → 127.0.0.1:8091 (statt *:8091)

curl -m 5 http://178.104.143.19:8090/   → Connection refused / Timeout
curl https://gregor20.henemm.com/api/health   → 200 (Nginx-Pfad weiter ok)
```

Unit-Tests:
- `TestLoad_DefaultHost` — Default ist `127.0.0.1`
- `TestLoad_HostOverride` — `GZ_HOST=0.0.0.0` wird übernommen

## Scope

3 Dateien, ~15 LoC inkl. Tests. Effort: Klein.

## Bezug

- GitHub Issue: henemm/gregor_zwanzig#116
- Security Findings: henemm-security#70 (HIGH, CVSS 7.5), #72 (medium)
- Frontend-Anteil (Port 3000/3001): henemm-infra (MQ #14426)
