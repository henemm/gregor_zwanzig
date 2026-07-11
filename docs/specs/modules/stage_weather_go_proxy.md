---
entity_id: stage_weather_go_proxy
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [risk, weather, cockpit, adr-0015, issue-1212, go, dead-code]
---

# Stage-Weather Go-Proxy + Risk-Löschung (Slice R2, #1212)

## Approval

- [x] Approved — PO „go" 2026-07-11

## Purpose

Den Go-Handler `StagesWeatherHandler` durch einen dünnen Proxy auf den (in R1 gebauten, live)
Python-Endpoint `/api/_internal/trips/{id}/stages-weather` ersetzen und die dadurch tote,
duplizierte Go-Risk-Logik löschen (`internal/risk/` + Aggregation + verwaiste Models, ~1167 LoC).
Damit gibt es genau EINE Risk-Implementierung (Python, ADR-0015). Reine Backend-Konsolidierung —
**keine nutzersichtbare Änderung** (die Cockpit-Anzeige ist toter Code, separat via #1223).

## Source

- **File:** `internal/handler/proxy.go` (CREATE Handler) · `internal/router/router.go` (MODIFY) ·
  DELETE `internal/risk/*`, `internal/handler/stage_weather.go` (+ `_test.go`), `internal/model/stage_weather.go`, `internal/model/risk.go`
- **Identifier:** `StagesWeatherProxyHandler(pythonURL string)` · Route `GET /api/trips/{id}/stages/weather`

## Estimated Scope

- **LoC:** neuer Produktivcode ~26; Löschung ~−1167 (netto stark negativ)
- **Files:** 2 geändert (proxy.go, router.go) + 1 Testdatei; ~8 gelöscht
- **Effort:** medium (Go-Build-Integrität + Konsumenten-Sicherheit ist das Risiko)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `LoadedTripProxyHandler` (`internal/handler/proxy.go:165`) | pattern | Vorbild: Path-Param + user_id-Query-Proxy |
| `appendUserID` (`internal/handler/proxy.go:147`) | reuse | Anti-Spoofing: authentifizierte user_id injizieren |
| `deps.Config.PythonCoreURL` (`internal/config`) | reuse | Ziel-Host (`GZ_PYTHON_CORE_URL`, default localhost:8000) |
| Python `/api/_internal/trips/{id}/stages-weather` (R1) | upstream | Liefert die eigentliche Antwort |
| `ForecastHandler` (`internal/handler/forecast.go`) | invariant | Nutzt `deps.WeatherProvider` WEITER — bleibt unangetastet |

## Implementation Details

### Neuer Proxy-Handler
```
func StagesWeatherProxyHandler(pythonURL string) http.HandlerFunc:
  id    := chi.URLParam(r, "id")
  query := appendUserID("", middleware.UserIDFromContext(r.Context()))  // client-user_id wird verworfen
  url   := pythonURL + "/api/_internal/trips/" + id + "/stages-weather?" + query
  client := &http.Client{Timeout: 60 * time.Second}   // Wetter-Fetch teuer
  resp, err := client.Get(url)
  err → 502 {"error":"upstream unreachable"}, Content-Type application/json
  sonst: Content-Type + StatusCode durchreichen, io.Copy(w, resp.Body)   // 200/404/500 transparent
```

### Router
`internal/router/router.go:140`:
`r.Get("/api/trips/{id}/stages/weather", handler.StagesWeatherProxyHandler(deps.Config.PythonCoreURL))`
(Pfad unverändert; `deps.WeatherProvider`-Argument entfällt hier.)

### Löschung (verifiziert konsumentenfrei)
`internal/risk/{engine,exposition,thresholds}.go` + Tests · `internal/handler/stage_weather.go` + `_test.go` ·
`internal/model/stage_weather.go` · `internal/model/risk.go` (nach den anderen Löschungen verwaist — Grep bestätigt: kein weiterer Konsument).

## Expected Behavior

- **Input:** `GET /api/trips/{id}/stages/weather` (Cookie-Auth via `authmw.AuthMiddleware`).
- **Output:** identische JSON-Struktur wie der Python-Endpoint (`{"results": {...}}`), transparent durchgereicht.
- **Side effects:** keine (read-only Proxy).

## Acceptance Criteria

- **AC-1 (Route-Parität):** Given ein authentifizierter Nutzer mit einem bekannten Trip / When er `GET /api/trips/{id}/stages/weather` aufruft / Then erhält er dieselbe JSON-Struktur (`results` mit `weather_summary`/`risk` je Etappe) wie der Python-Endpoint direkt liefert — der Proxy reicht Status und Body transparent durch.
  - Test: Staging-HTTP-Vergleich — die geproxyte Go-Route und der direkte Python-Endpoint liefern für denselben Trip strukturell dieselbe Antwort.

- **AC-2 (Anti-Spoofing / Isolation):** Given ein authentifizierter Nutzer A, der in der Query ein fremdes `user_id=B` mitschickt / When der Proxy die Anfrage weiterleitet / Then wird B verworfen und die authentifizierte user_id A injiziert — A sieht nie B's Daten.
  - Test: Go-Handler-Test mit gesetztem Auth-Kontext A und `?user_id=B` prüft, dass die an Python gehende URL `user_id=A` trägt.

- **AC-3 (Upstream-Fehler):** Given der Python-Core ist nicht erreichbar / When der Proxy aufgerufen wird / Then antwortet er mit HTTP 502 Body `{"error":"upstream unreachable"}`, Content-Type application/json — kein Absturz, kein 5xx-Leck von Go-internem Zustand.
  - Test: Go-Handler-Test mit unerreichbarer pythonURL → 502 + exakter Body.

- **AC-4 (Durchgereichte Fehler):** Given der Python-Endpoint antwortet 404 (unbekannter Trip) bzw. 200 / When der Proxy aufgerufen wird / Then reicht der Proxy Status und Body unverändert durch (404 bleibt 404, 200 bleibt 200).
  - Test: Go-Handler-Test mit Fake-Upstream (404/200) prüft transparente Weiterleitung.

- **AC-5 (Löschung + Build-Integrität):** Given die Löschung von `internal/risk/` und der Aggregations-Logik / When `go build ./...` und `go vet ./...` laufen / Then kompilieren sie fehlerfrei, und kein anderer Go-Konsument (insb. `ForecastHandler`, `internal/compare/*`) bricht.
  - Test: `go build ./...` + `go vet ./...` + bestehende Go-Test-Suite grün; `grep` bestätigt: kein Import von `internal/risk` mehr.

- **AC-6 (Provider-Invariante):** Given `ForecastHandler` nutzt weiterhin `deps.WeatherProvider` / When R2 deployt ist / Then funktioniert `GET /api/forecast` unverändert (die Provider-Verdrahtung bleibt bestehen).
  - Test: bestehender Forecast-Handler-Test grün nach dem Umbau.

## Known Limitations

- **Keine sichtbare Cockpit-Änderung.** Der Endpoint hat aktuell keinen lebenden Frontend-Konsumenten
  (`StageList.svelte` ist nicht gemountet; live liest `TripStageRow` das nie-gefüllte `stage.risk`).
  Der im Issue geforderte Playwright-Vorher/Nachher-Farbvergleich ist daher gegenstandslos und wird
  durch einen **dokumentierten No-Op-Nachweis** + HTTP-Contract-Parität der Route ersetzt. Die sichtbare
  Anzeige liefert **#1223** (separates Frontend-Issue, PO-Entscheidung 2026-07-10).
- **Auth-Kontext-Verschärfung (Verbesserung):** In Produktion ruft nur die authentifizierte Go-API den
  internen Python-Endpoint (via appendUserID) — die user_id ist nicht mehr client-kontrollierbar wie beim
  R1-Direktzugriff.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0015 (bestehend). Kein neuer ADR — R2 vollendet die Konsolidierung.
- **Rationale:** Entfernt die letzte doppelte Risk-Implementierung; folgt der getroffenen Owner-Entscheidung.

## Changelog

- 2026-07-10: Initial spec created (Slice R2 von #1212)
