# Context: issue-367-compare-unify

## Request Summary
Go-Compare-Engine (`POST /api/compare/run`) liefert Sonnenschein als `dni_avg_wm2` (W/m²), während
Python-Compare-Engine und alle anderen Ausgaben `sunny_hours` (h) zeigen. Frontend-Label lautet
bereits "Sonnenstunden", aber Einheit ist noch W/m² — beides inkonsistent. Ziel: Go-Engine auf
WMO-konforme Sonnenstunden-Berechnung umstellen (identisch zur Python-Logik), Frontend-Matrix
korrigieren.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `internal/compare/engine.go:238-241` | Berechnet `DniAvgWm2` als Durchschnitt aller DNI-Stunden — hier muss die Interpolation rein |
| `internal/model/segment.go:24` | `DniAvgWm2 *float64` — neues Feld `SunnyHoursH *float64` ergänzen |
| `internal/compare/scoring.go:17,48,233` | Scoring-Schlüssel `metricDniAvg`, 20% Gewicht bei WINTERSPORT — auf `metricSunnyHours` umstellen |
| `internal/compare/types.go:37-56` | `CompareRow` / `CompareResult` — API-Response-Shape |
| `internal/handler/compare_run.go:22-60` | HTTP-Handler, delegiert an `engine.Run()` |
| `internal/handler/compare_run_test.go` | 2 Go-Tests (Ranking + Partial-Result) — müssen erweitert werden |
| `src/services/weather_metrics.py:245-326` | `dni_to_sunny_fraction()` + `calculate_sunny_hours()` — **Referenz-Implementierung** (DNI-Band 60–180 W/m²) |
| `src/services/comparison_engine.py:146-148` | Python verwendet `calculate_sunny_hours()` für `metrics["sunny_hours"]` |
| `src/services/comparison_scoring.py:67-83` | Python-Scoring für `sunny_hours` (Fenster-Bonus, Issue #366) |
| `frontend/src/lib/types.ts:276` | `CompareMetrics.dni_avg_wm2` — `sunny_hours?: number \| null` ergänzen |
| `frontend/src/lib/components/compare/CompareMatrix.svelte:31` | WINTERSPORT zeigt `dni_avg_wm2` mit Label "Sonnenstunden" + Unit "W/m²" — auf `sunny_hours` + "h" umstellen |
| `frontend/src/routes/compare/+page.svelte` | Importiert `CompareMatrix` |
| `tests/tdd/test_compare_html_email.py` | Python-Compare-Tests — nicht betroffen (Python-Pfad bleibt unverändert) |

## Existing Patterns

- **Python-Interpolation:** `dni_to_sunny_fraction(dni_wm2, min=60, max=180)` → lineares Band,
  dann `calculate_sunny_hours()` summiert über stündliche Werte. Ergebnis: Float auf 1 Dezimalstelle.
- **Go-Aggregation:** `engine.go` iteriert über stündliche Forecast-Werte und akkumuliert Summen
  pro Metrik. Gleiches Muster für DNI — Interpolation kann 1:1 dort eingebaut werden.
- **Scoring-Schlüssel:** `scoring.go` nutzt String-Konstanten (`metricDniAvg`); Rename auf
  `metricSunnyHours` + neues Feld im Scoring-Gewicht reicht.
- **Frontend-Matrix:** `PROFILE_METRICS` Map in `CompareMatrix.svelte` pro Aktivitätsprofil —
  einfaches Feld-Swap (Key + Unit + Formatter).

## Dependencies

- **Upstream (Go-Engine):** Open-Meteo liefert stündliche DNI-Werte (`direct_radiation` oder
  `direct_normal_irradiance`) — gleiche Rohdaten, die Python ebenfalls verwendet.
- **Upstream (Python-Engine):** `calculate_sunny_hours()` in `weather_metrics.py` — bleibt
  unverändert, ist die Referenz.
- **Downstream:** Frontend `CompareMatrix.svelte` konsumiert Go-Response; nach Umstellung
  erwartet es `sunny_hours` statt `dni_avg_wm2`.

## Existing Specs

- `docs/specs/modules/issue_250_compare_engine.md` — ursprüngliche Compare-Engine-Spec (Go,
  Issue #250, implementiert); beschreibt `DniAvgWm2` als damalig geplantes Feld.
- `docs/specs/modules/compare_247_location_model.md` — Location-Model-Erweiterungen.

## Risks & Considerations

- **Scoring-Kalibrierung:** Python-Scoring (Issue #366) nutzt `window_hours` + Share-basierte
  Bonus-Logik. Go-Scoring ist einfacher (20% Gewicht auf Rohwert). Nach Umstellung auf
  `sunny_hours` muss der Go-Schwellenwert (ab wie vielen Stunden = gut?) festgelegt werden —
  vernünftiger Default: ≥ 6 h = voller Bonus (analog Python-Legacy-Pfad).
- **Backward-Compat API:** `dni_avg_wm2` verschwindet aus der Go-Response. Falls ein externer
  Client das Feld nutzt — unwahrscheinlich (interner Endpunkt), aber `omitempty` wird es ohnehin
  nur zeigen, wenn gesetzt.
- **Go-Fixture-Tests:** `compare_run_test.go` nutzt Fixture-Provider (#263). Die Fixture-Daten
  müssen `direct_radiation` enthalten, damit die neue Berechnung prüfbar ist.
- **Float vs. Int:** Python liefert `sunny_hours` als Float (1 Dezimalstelle). Go-Modell kann
  `*float64` verwenden; Frontend-Type ist `number | null` — kompatibel.
