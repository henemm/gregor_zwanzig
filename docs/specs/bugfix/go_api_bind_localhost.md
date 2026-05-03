---
entity_id: go_api_bind_localhost
type: bugfix
created: 2026-05-03
updated: 2026-05-03
status: draft
version: "1.0"
tags: [security, bugfix, go-api, networking, nginx, issue-116]
---

# Go-API Bind auf Localhost

## Approval

- [ ] Approved

## Purpose

Behebt eine Security-Lücke (HIGH, CVSS 7.5), bei der der Go-API-Server (Port 8090 Prod, 8091 Staging) auf alle Netzwerk-Interfaces bindet und damit das Backend direkt aus dem Internet erreichbar ist. Nginx als Gateway (HSTS, CSP, Rate-Limits, Auth-Header) wird so umgangen — das Backend muss zwingend nur via Nginx-Proxy ansprechbar sein. Der Fix bindet die API standardmäßig auf `127.0.0.1` und macht den Bind-Host über `GZ_HOST` konfigurierbar (z. B. für Container-Setups, in denen explizit `0.0.0.0` gewünscht ist).

## Source

- **File:** `cmd/server/main.go`
- **Identifier:** `main()` — `http.ListenAndServe(":"+cfg.Port, r)` in Zeile 115
- **Secondary File:** `internal/config/config.go` — `Config`-Struct, derzeit ohne `Host`-Feld

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Config` (`internal/config/config.go`) | Struct | Lädt Server-Konfiguration via `envconfig` mit Prefix `GZ` |
| `envconfig.Process("GZ", &cfg)` | External Library | Mappt ENV-Variablen mit Prefix `GZ_` auf Struct-Felder |
| `http.ListenAndServe` | Stdlib | Startet HTTP-Server an `host:port` (leeres `host` → bind auf alle Interfaces) |
| `nginx/gregor20.henemm.com.conf` | Nginx Config | Proxyt `https://gregor20.henemm.com/api/*` → `http://127.0.0.1:8090` |
| `nginx/staging.gregor20.henemm.com.conf` | Nginx Config | Proxyt Staging-Pfad → `http://127.0.0.1:8091` |
| `gregor-api.service` / `gregor-api-staging.service` | Systemd | Setzt aktuell **kein** `GZ_HOST` → Default greift |

## Root Cause Analysis

### Aktueller Zustand (BROKEN)

`cmd/server/main.go:115`:

```go
http.ListenAndServe(":"+cfg.Port, r)
```

Leeres Host-Prefix in Go bedeutet bind auf alle Interfaces (`0.0.0.0` und IPv6 `::`). Damit ist der Backend-Port von außen direkt erreichbar:

```
ss -tulnH | grep ':8090\|:8091'
  *:8091   *:*
  *:8090   *:*

curl -m 5 http://178.104.143.19:8090/   → HTTP 401 (Backend reachable)
curl -m 5 http://178.104.143.19:8091/   → HTTP 401
```

`internal/config/config.go` enthält Felder wie `Port`, `LogLevel`, `DataDir` etc., aber kein `Host`-Feld — der Bind-Host ist also weder konfigurierbar noch dokumentiert.

### Sicherheits-Implikation

- HSTS-Header, CSP, Rate-Limits, Basic-Auth aus Nginx werden umgangen
- Direkter Zugriff auf API-Endpoints inkl. ggf. weniger restriktiver CORS-Defaults
- Klassifiziert als HIGH / CVSS 7.5 (henemm-security#70), medium-Variante in henemm-security#72

## Implementation Strategy

### 1. `internal/config/config.go` — Neues `Host`-Feld

```go
type Config struct {
    Host string `envconfig:"HOST" default:"127.0.0.1"`
    Port string `envconfig:"PORT" default:"8090"`
    // ... bestehende Felder unverändert ...
}
```

Default `127.0.0.1` ist sicher: Backend wird ausschließlich via Nginx erreichbar. Override via `GZ_HOST=0.0.0.0` bleibt für Container/Sonderfälle möglich.

### 2. `cmd/server/main.go:115` — Host beim Bind verwenden

Vorher:

```go
http.ListenAndServe(":"+cfg.Port, r)
```

Nachher:

```go
http.ListenAndServe(cfg.Host+":"+cfg.Port, r)
```

> Hinweis: Der bestehende Code wrappt `http.ListenAndServe` nicht in `log.Fatal(...)` — ein Bind-Fehler würde aktuell still beendet. Das ist ein eigenständiger Schwachpunkt, der hier bewusst nicht im Scope ist (separater Bug, falls gewünscht). Dieser Fix ändert nur das Bind-Argument.

### 3. `internal/config/config_test.go` — Tests

```go
func TestLoad_DefaultHost(t *testing.T) {
    // Kein GZ_HOST gesetzt → Default 127.0.0.1
    cfg, err := Load()
    require.NoError(t, err)
    assert.Equal(t, "127.0.0.1", cfg.Host)
}

func TestLoad_HostOverride(t *testing.T) {
    t.Setenv("GZ_HOST", "0.0.0.0")
    cfg, err := Load()
    require.NoError(t, err)
    assert.Equal(t, "0.0.0.0", cfg.Host)
}
```

## Expected Behavior

### Vor Fix (BROKEN)

- **Input:** `curl -m 5 http://178.104.143.19:8090/`
- **Output:** HTTP 401 (Backend antwortet, weil bind auf `0.0.0.0`)
- **Side effects:** Nginx-Security-Layer wird umgangen

### Nach Fix (GREEN)

- **Input (extern):** `curl -m 5 http://178.104.143.19:8090/`
- **Output:** Connection refused / Timeout (Port von außen nicht erreichbar)
- **Input (via Nginx):** `curl https://gregor20.henemm.com/api/health`
- **Output:** HTTP 200 (Nginx-Proxy-Pfad funktioniert unverändert)
- **Listen-Status:** `ss -tulnH | grep ':8090\|:8091'` zeigt `127.0.0.1:8090` und `127.0.0.1:8091` (statt `*:8090` / `*:8091`)
- **Side effects:** Keine — Nginx proxyt bereits auf `127.0.0.1`, Service-Files setzen kein `GZ_HOST`

## Acceptance Criteria

- [ ] Vor Fix: `curl -m 5 http://178.104.143.19:8090/` antwortet mit HTTP 401 (Reproduktion bestätigt)
- [ ] Nach Fix: `curl -m 5 http://178.104.143.19:8090/` liefert Connection refused / Timeout
- [ ] Nach Fix: `curl -m 5 http://178.104.143.19:8091/` liefert Connection refused / Timeout
- [ ] Nach Fix: `ss -tulnH | grep ':8090\|:8091'` zeigt `127.0.0.1:8090` und `127.0.0.1:8091`
- [ ] Nach Fix: `curl https://gregor20.henemm.com/api/health` liefert HTTP 200
- [ ] Nach Fix: `curl https://staging.gregor20.henemm.com/api/health` liefert HTTP 200
- [ ] Unit-Test `TestLoad_DefaultHost` grün
- [ ] Unit-Test `TestLoad_HostOverride` grün

## Files to Modify

| Datei | Änderung | LoC |
|---|---|---|
| `internal/config/config.go` | Neues Feld `Host string envconfig:"HOST" default:"127.0.0.1"` | ~1 |
| `cmd/server/main.go` (Zeile 115) | `cfg.Host+":"+cfg.Port` statt `":"+cfg.Port` | ~1 |
| `internal/config/config_test.go` | `TestLoad_DefaultHost` + `TestLoad_HostOverride` | ~12 |

Gesamt: 3 Dateien, ~15 LoC.

## Known Limitations

- Fix adressiert ausschließlich den Go-API-Anteil. Frontend-Ports 3000 (Prod) / 3001 (Staging) haben denselben Root-Cause und werden parallel im Repo `henemm-infra` über MQ-Nachricht #14426 gefixt.
- IPv6: `127.0.0.1` ist explizit IPv4-loopback. Falls künftig IPv6-Loopback gewünscht ist, müsste der Default auf `localhost` (resolved beide) wechseln — aktuell nicht nötig, da Nginx via `127.0.0.1` proxyt.
- Service-Files (`gregor-api.service`, `gregor-api-staging.service`) bleiben unverändert — Default-Verhalten greift. Falls jemand explizit `0.0.0.0` möchte, muss `GZ_HOST=0.0.0.0` im Service-File gesetzt werden.

## Bezug

- GitHub Issue: [henemm/gregor_zwanzig#116](https://github.com/henemm/gregor_zwanzig/issues/116)
- Security Findings: henemm-security#70 (HIGH, CVSS 7.5), henemm-security#72 (medium, gleicher Root-Cause)
- Verwandter Frontend-Fix: henemm-infra via MQ #14426

## Changelog

- 2026-05-03: Initial spec created based on Issue #116 analysis
