# Context + Analysis: rework-1212-risk-r2-go-proxy (Slice R2)

## Request Summary
Slice R2 von #1212: Den Go-Handler `StagesWeatherHandler` durch einen **Proxy** auf den in R1
gebauten Python-Endpoint ersetzen und die doppelte/tote Go-Risk-Logik löschen (ADR-0015 —
Python ist alleiniger Owner der Wetter-Risiko-Domäne). Reines Backend-Aufräumen, **keine
nutzersichtbare Änderung** (siehe Schlüsselbefund).

## Schlüsselbefund (PO-bestätigt 2026-07-10) — Endpoint hat KEINEN lebenden Konsumenten
- Die Frontend-Komponente `StageList.svelte` (die `/api/trips/{id}/stages/weather` aufriefe und
  `risk`→Farbe übersetzt) ist **nirgends gemountet** (`grep '<StageList'` → 0). Toter Code.
- Live rendert der Übersicht-Tab `HubOverview` → `TripStageRow` (`TripTabs.svelte:142`);
  `TripStageRow.svelte:13` liest `stage.risk` aus dem Trip-Modell — ein Feld, das das Backend nie
  füllt → Kachel immer „OK"/grün.
- Der Home-Loader darf den Endpoint aus Performance ausdrücklich NICHT rufen (#386/#395).
- **Konsequenz:** R2 verändert die sichtbare UI nicht. Der Playwright-Vorher/Nachher aus dem Issue
  wäre identisch. Das eigentliche Nutzerziel (Cockpit zeigt Farben) ist als eigenes Frontend-Issue
  **#1223** ausgelagert (PO-Entscheidung). R2 liefert die Backend-Konsolidierung + Dead-Code-Löschung.

## Technical Approach
### Neuer Proxy-Handler (Vorbild `LoadedTripProxyHandler`, `internal/handler/proxy.go:165-189`)
- Path-Param `{id}` via `chi.URLParam(r,"id")`; `user_id` via `appendUserID("", middleware.UserIDFromContext(r.Context()))`
  (Anti-Spoofing #199/#200 — der authentifizierte User gewinnt, Client-`user_id` wird verworfen).
- Ziel: `pythonURL + "/api/_internal/trips/" + id + "/stages-weather?" + query`; `pythonURL` = `deps.Config.PythonCoreURL` (`GZ_PYTHON_CORE_URL`, default `http://localhost:8000`).
- Fehler: Python nicht erreichbar → 502 `{"error":"upstream unreachable"}` (konsistent mit Vorbild).
  Timeout **60s** (Wetter-Fetch teuer — vgl. `CompareProxyHandler` 60s; Vorbild nutzt nur 10s, hier zu knapp).
- Response 1:1 durchreichen (Status + Content-Type + Body via `io.Copy`). 404/500 vom Python werden transparent weitergereicht.

### Löschfläche (verifiziert, ~1167 LoC weg)
| Datei | LoC | Aktion |
|------|-----|--------|
| `internal/risk/engine.go` | 139 | DELETE |
| `internal/risk/engine_test.go` | 208 | DELETE |
| `internal/risk/exposition.go` | 62 | DELETE (AssessWithExposition ist bereits toter Code) |
| `internal/risk/exposition_test.go` | 54 | DELETE |
| `internal/risk/thresholds.go` | 27 | DELETE |
| `internal/handler/stage_weather.go` | 275 | DELETE (komplett durch Proxy ersetzt) |
| `internal/handler/stage_weather_test.go` | 377 | DELETE (→ neuer Proxy-Test) |
| `internal/model/stage_weather.go` | 25 | DELETE (nur hier genutzt) |
| `internal/model/risk.go` | ~? | PRÜFEN: nach Löschung von risk/ + stage_weather.go verwaist? Dann DELETE, sonst lassen |

### Verifizierte Sicherheits-Fakten
- **`internal/risk/` hat NUR einen Konsumenten:** `stage_weather.go` (`risk.Assess`/`GetMaxRiskLevel`).
  `AssessWithExposition` hat gar keinen Aufrufer. → Nach Handler-Umbau löschbar.
- **`deps.WeatherProvider` bleibt** — `ForecastHandler` (`router.go:121`) nutzt ihn weiter. Nur das
  2. Argument im `StagesWeatherHandler`-Aufruf (`router.go:140`) entfällt.
- **`model.SegmentWeatherSummary`** (`internal/model/segment.go`) ≠ `model.StageWeatherSummary` —
  ersterer wird von `internal/compare/*` massiv genutzt, bleibt. Nicht verwechseln.

### Router-Änderung
`internal/router/router.go:140`: `StagesWeatherHandler(deps.Store, deps.WeatherProvider)` →
neuer Proxy `StagesWeatherProxyHandler(deps.Config.PythonCoreURL)`. Route-Pfad unverändert (`/api/trips/{id}/stages/weather`).

## Affected Files
| Datei | Change | LoC |
|------|--------|-----|
| `internal/handler/proxy.go` (oder neu `stage_weather_proxy.go`) | CREATE Proxy-Handler | ~25 |
| `internal/router/router.go` | MODIFY Zeile 140 | ~1 |
| `internal/handler/proxy_test.go` (o.ä.) | CREATE Proxy-Test | ~40 (Test) |
| `internal/risk/*`, `internal/handler/stage_weather*.go`, `internal/model/stage_weather.go`, ggf. `model/risk.go` | DELETE | −1167 |

## Scope Assessment
- Netto-LoC: stark negativ (~+65 / −1167). Neuer Produktivcode ~26 LoC. Klar unter Limit.
- Blast Radius: Go-API/Cockpit-Route (aber kein lebender UI-Konsument → geringes Sichtbarkeitsrisiko);
  User-Isolation via appendUserID (besser als R1-Direktzugriff, da Go-Auth die user_id setzt).
- Risk Level: MEDIUM (Go-Build muss grün bleiben, keine anderen risk/-Konsumenten brechen).

## Dependencies / Reihenfolge
- Hängt hart von R1 (Python-Endpoint live) ab — ✅ erfüllt.
- #1223 (Frontend-Anzeige) hängt von R2 (Route liefert dann Python-Risiko).

## Open Questions
- [ ] `internal/model/risk.go` nach Löschungen wirklich verwaist? Vor Löschen per Grep bestätigen; im Zweifel lassen (dead-but-harmless) → #1199.
- [ ] Go-Proxy-Timeout: 60s ausreichend für einen Trip mit vielen Segmenten? (R1-Staging-Antwort war schnell für 1 Etappe; Multi-Etappe messen.)
- [ ] „Playwright-Pflicht" aus dem Issue: durch dokumentierten No-Op-Nachweis erfüllen (kein lebender Konsument), stattdessen HTTP-Contract-Parität der geproxyten Route auf Staging prüfen.

## Acceptance-Skizze (für Spec)
1. Route `/api/trips/{id}/stages/weather` liefert nach Umbau dieselbe JSON-Struktur wie der Python-Endpoint (via Proxy), für bekannten Trip.
2. `user_id` wird aus dem Auth-Kontext injiziert; ein client-gesetztes `user_id` in der Query wird überschrieben (Anti-Spoofing).
3. Python nicht erreichbar → 502 `upstream unreachable`; unbekannter Trip → 404 (durchgereicht).
4. `internal/risk/` existiert nicht mehr; `go build ./...` + `go vet` grün; kein anderer Konsument bricht.
5. `ForecastHandler` (nutzt weiter `WeatherProvider`) unverändert funktionsfähig.
6. Keine sichtbare Cockpit-Änderung (dokumentiert; #1223 liefert die Anzeige).
