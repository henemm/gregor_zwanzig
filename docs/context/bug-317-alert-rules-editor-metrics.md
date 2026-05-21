# Context: Bug #317 — AlertRulesEditor zeigt nur 3 von 6 Metriken

## Request Summary

Im `AlertRulesEditor` (Edit-View) fehlen die Metriken `precipitation`, `thunder`, `snowfall_limit`. Das Go-Backend liefert alle 6 Rules zurück, aber nur 3 werden angezeigt.

## Root Cause

Zwei unabhängige Probleme:

**1. Staging-Testdaten mit alten Metrik-Namen**
Datei: `gregor_zwanzig_staging/data/users/validator-issue110/trips/ac206-validator-1779092432.json`
Die drei fehlenden Rules nutzen alte `metric_catalog.py`-IDs:
- `"precipitation"` → korrekt: `"precipitation_sum"`
- `"thunder"` → korrekt: `"thunder_level"`
- `"snowfall_limit"` → korrekt: `"snow_line"`

**2. Stiller F004-Guard im Frontend**
`AlertRuleRow.svelte:131`: `{#if info}` blendet die gesamte Row aus, wenn `ALERT_METRIC_LABELS[rule.metric]` undefined ist. Der Guard verhindert Crashes, ist aber zu aggressiv — er versteckt echte Daten.

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | F004-Guard `:131`, `METRIC_OPTIONS :63` |
| `frontend/src/lib/utils/alertMetricLabels.ts` | `ALERT_METRIC_LABELS` — enthält alle 9 gültigen Metriken |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Lädt `trip.alert_rules` und übergibt sie direkt an `AlertRulesEditor` |
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | Zweite Stelle mit `AlertRulesEditor` |
| `gregor_zwanzig_staging/data/users/validator-issue110/trips/ac206-validator-1779092432.json` | Einzige betroffene Datei in Staging |
| `internal/model/trip.go` | `AlertMetric` als plain `string` (keine Validierung) |
| `internal/store/store.go` | Lese-Pfad ohne Normalisierung |
| `src/app/models.py` | Python `AlertMetric` Enum — korrekte Werte |

## Existing Patterns

- `alertMetricLabels.ts`: SSOT für Labels/Units der 9 `AlertMetric`-Werte
- `alertMetricTable.ts::ALL_ALERT_METRICS`: geordnete Liste der 9 Metriken
- `AlertMetricTable.svelte`: zeigt immer alle 9 Metriken (kein Filtern)
- `AlertRulesEditor.svelte`: listenbasiert, rendert nur gespeicherte Rules

## Dependencies

- `AlertRuleRow.svelte` nutzt `ALERT_METRIC_LABELS` für Label + Unit im View-Mode
- `TripEditView.svelte` übergibt `trip.alert_rules` ohne Normalisierung
- Go-Backend: `AlertMetric` ist `string`, keine Enum-Validierung beim Lesen

## Scope der betroffenen Daten

- **Staging**: 1 Datei betroffen (`ac206-validator-1779092432.json`, User `validator-issue110`)
- **Production**: 0 Dateien betroffen (grep bestätigt)

## Fix-Strategie (empfohlen)

1. **Frontend-Normalisierung** in `TripEditView.svelte` + `Step4Briefings.svelte`:
   Legacy-Alias-Map beim Laden anwenden (`precipitation` → `precipitation_sum`, etc.)
2. **F004-Guard entschärfen** in `AlertRuleRow.svelte`:
   Fallback-Label statt komplettem Ausblenden (`info?.label_de ?? rule.metric`)
3. **Staging-Testdatei patchen**: korrekte Metrik-Namen einsetzen

## Risks & Considerations

- Nur 1 Staging-Datei betroffen, keine Production-Daten → begrenzter Impact
- Normalisierung muss idempotent sein (Standard-Namen bleiben unverändert)
- `snowfall_limit` → `snow_line`: semantisch nicht exakt gleich (SnowfallLimitM vs. FreezingLevelM), aber beste verfügbare Annäherung in AlertMetric-Enum
