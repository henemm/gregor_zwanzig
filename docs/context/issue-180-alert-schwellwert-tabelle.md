# Context: Issue #180 — Alert-Konfigurator: Schwellwert-Tabelle

## Request Summary

Ersetzt den Platzhalter-Text im Alerts-Tab (`/trips/[id]#alerts`) durch eine vollständige
Konfigurations-UI mit 9 AlertMetric-Zeilen (Toggle + Schwellwert-Inputs + Schweregrad),
integriert die bereits vorhandenen AlertCooldownCard und AlertQuietHoursCard und speichert
via `PUT /api/trips/{id}`.

## Related Files

| File | Relevanz |
|------|---------|
| `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` | Vorhanden — wird in AlertsTab eingebunden |
| `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | Vorhanden — wird in AlertsTab eingebunden |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Zu ändern: alerts-Branch auf AlertsTab umleiten |
| `frontend/src/lib/utils/alertMetricLabels.ts` | ALERT_METRIC_LABELS (Label, Unit, Comparison), ALERT_SEVERITY_TONE |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | DELTA_ONLY_METRICS (temperature_change, wind_change, precipitation_change) |
| `frontend/src/lib/types.ts` | AlertRule, AlertMetric, AlertSeverity, Trip |
| `frontend/src/lib/api.ts` | api.put() für PUT /api/trips/{id} |
| `docs/specs/modules/issue_180_alert_metric_table.md` | Fertige Spec (9 ACs, vollständige Komponenten-Definitionen) |

## Existing Patterns

- **PresetRow**: Button mit `class:active`, Testid per Item, CSS-Highlight via Design-System-Variablen
- **MetricCheckbox**: `role="checkbox"`, `aria-checked`, bindable State, Testid per Metrik
- **AlertCooldownCard**: `$bindable()` Props, Number-Input, responsive Hint-Text
- **AlertRuleRow**: View/Edit-Modus, Badge für Abs/Δ

## Dependencies

- **Upstream:** `alert_rules: AlertRule[]` auf Trip-Objekt; `PUT /api/trips/{id}` (vorhanden)
- **Downstream:** AlertRow.svelte (read-only Anzeige), AlertsPreviewCard, Scheduler-Alerts-Engine
- **Bereits vorhanden:** AlertCooldownCard.svelte, AlertQuietHoursCard.svelte — werden nur eingebunden

## Neue Komponenten (laut Spec)

| Komponente | LoC | Aufgabe |
|-----------|-----|---------|
| `AlertsTab.svelte` | ~40 | Container, Save-Logik, Erfolgs-/Fehler-Feedback |
| `AlertMetricTable.svelte` | ~30 | 9 Zeilen rendern, Row-State verwalten |
| `AlertMetricRow.svelte` | ~80 | Toggle + Label + Δ-Input + Abs-Input + Severity-Select |
| `TripTabs.svelte` | +5 | alerts-Branch: AlertsTab statt Platzhalter |

## Data Model (Row State — intern)

```typescript
interface MetricRowState {
  absEnabled: boolean;
  absThreshold: number;
  deltaEnabled: boolean;
  deltaThreshold: number;
  severity: AlertSeverity;  // default: 'warning'
}
```

Delta-only-Metriken: `temperature_change`, `wind_change`, `precipitation_change` — kein Abs-Toggle/Input.

## Risks & Considerations

1. **AlertCooldownCard + AlertQuietHoursCard existieren bereits** (für Issue #181) — nur einbinden, nicht neu schreiben
2. **DELTA_ONLY_METRICS** muss konsistent mit `alertRuleDefaults.ts` genutzt werden — kein eigenes Set anlegen
3. **Reihenfolge der Zeilen** — immer via `Object.keys(ALERT_METRIC_LABELS)`, nie hart kodiert
4. **Spec ist bereits vollständig** (9 ACs, alle Komponenten-Definitionen) — kann direkt zur Approval
