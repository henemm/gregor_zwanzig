# Mini-Spec: #1329 AC-8 — Forecast-Budget-Verbrauchsanzeige im Go-Status-Endpoint

## Kontext

`ForecastBudgetGate.snapshot()` (`src/services/forecast_budget.py:93-119`) liefert bereits
alle Felder für den Kontingent-Verbrauch (`calls_today`, `daily_budget`, `usage_ratio`,
`cache_hits`, `cache_misses`, `status`), ist aber im Python-Kern noch an nichts angebunden.
Der Docstring des Feldes verweist explizit auf „Go-Status-Endpunkt, AC-8". Genau dieses
Muster gibt es bereits für einen anderen Provider: `meteoalarmBudgetSnapshot()`
(`internal/scheduler/warn_service_health.go:201-237`) liest
`data/diagnostics/meteoalarm_budget.json` direkt (kein HTTP-Call zu Python-Core) und hängt
das Ergebnis in `WarnServiceHealth()` unter `"meteoalarm_budget"` ein, was wiederum über
`Scheduler.Status()` (`internal/scheduler/scheduler.go:677`) ausgeliefert wird.

Diese Slice überträgt exakt dieses Muster auf `data/diagnostics/forecast_budget.json`
(`src/services/forecast_budget.py:139-159` — Schreibformat: `{"date", "calls": {"openmeteo": N},
"cache_hits", "cache_misses"}`, `calls` ist hier ein Dict pro Provider statt eines Int, anders
als bei meteoalarm).

## Acceptance Criteria

- **AC-1:** Given eine gültige `data/diagnostics/forecast_budget.json` existiert, When `/api/scheduler/status` aufgerufen wird, Then enthält die Antwort unter `forecast_budget` die Felder `calls_today`, `daily_budget`, `usage_ratio`, `cache_hits`, `cache_misses`, `status: "ok"` mit korrekt berechnetem `usage_ratio`.
- **AC-2:** Given die Datei `data/diagnostics/forecast_budget.json` fehlt oder ist nicht lesbar, When `/api/scheduler/status` aufgerufen wird, Then liefert `forecast_budget.status` `"unavailable"` mit Nullwerten und der Endpoint antwortet weiterhin ohne Fehler (kein 500er, kein Panic).
- **AC-3:** Given die Datei enthält kaputtes/unerwartetes JSON, When gelesen wird, Then verhält sich das System wie bei AC-2 (Fail-soft, `status: "unavailable"`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine — additive Erweiterung eines bestehenden Status-Endpoints nach etabliertem Muster (`meteoalarmBudgetSnapshot`), keine neue Architektur-Entscheidung nötig.

## Was ändert sich

- Neue Funktion `forecastBudgetSnapshot(path string) map[string]any` in
  `internal/scheduler/warn_service_health.go` (oder neue Datei `forecast_budget_health.go`),
  analog `meteoalarmBudgetSnapshot`: liest `data/diagnostics/forecast_budget.json`, liefert
  `calls_today` (Wert unter `calls.openmeteo`), `daily_budget` (Konstante 9000, wie Python
  `ForecastBudgetGate.DAILY_BUDGET`), `usage_ratio`, `cache_hits`, `cache_misses`, `status`
  (`"ok"`/`"unavailable"`)
- Ergebnis wird in `Scheduler.Status()` unter dem Schlüssel `"forecast_budget"` eingehängt
  (Pfad: `filepath.Join(s.store.DataDir, "diagnostics", "forecast_budget.json")`)
- Fail-soft: fehlende/kaputte Datei → `status: "unavailable"`, Nullwerte — Endpoint darf nie
  einen Fehler werfen (Spiegel des Python-`snapshot()`-Fail-open-Verhaltens)

## Was darf sich nicht ändern

- Bestehende Felder von `Scheduler.Status()` (`jobs`, `warn_service_health`, …) bleiben
  unverändert
- `ForecastBudgetGate` (Python-Seite) wird nicht angefasst — sie ist bereits fertig
- Kein neuer HTTP-Call Go→Python-Core (Direktzugriff auf die Diagnose-Datei wie beim
  bestehenden Muster)
- Kein UI-Element auf der Account-Seite — der Verbrauch ist eine Ops-/Monitoring-Größe
  (Konsument: `check-gregor20.sh` bzw. manuelle Prüfung des Endpoints), kein
  Nutzer-sichtbares Feature

## Manuelle Test-Schritte

1. Lokal `data/diagnostics/forecast_budget.json` mit Testwerten anlegen
   (`{"date":"2026-08-05","calls":{"openmeteo":42},"cache_hits":10,"cache_misses":5}`)
2. `curl localhost:8090/api/scheduler/status | jq .forecast_budget` → erwartete Felder mit
   korrekten Werten
3. Datei löschen/umbenennen → erneuter Aufruf → `status: "unavailable"`, keine 500er-Antwort

## Inline-Test (wird während Implementierung geschrieben)

- [x] Test für `forecastBudgetSnapshot()`: gültige Datei → korrekte Felder + `usage_ratio`-Berechnung
- [x] Test: fehlende Datei → `status: "unavailable"`, Nullwerte, kein Panic
- [x] Test: kaputtes JSON → `status: "unavailable"` (Fail-soft)
- [x] Test: `Scheduler.Status()` enthält `"forecast_budget"`-Schlüssel
