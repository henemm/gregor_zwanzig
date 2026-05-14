---
issue: 223
title: "Edit-Pfad für alert_rules: TripEditView umbauen"
created: 2026-05-14
phase: phase1_context
---

# Context: Issue #223 — Edit-Pfad für `alert_rules`

## Request Summary

`/trips/[id]/edit` schreibt heute nur `report_config`, nicht `alert_rules`.
Bestandstrips können ihre Alarmregeln nicht editieren. Der Edit-Pfad nutzt
einen eigenen Component-Stack (Accordion-View) — kein 4-Step-Wizard.

## ⚠️ Wichtiger Befund: UI-Drift Edit vs. Wizard

Die zwei Threshold-UIs sind **konzeptuell unterschiedlich**:

| | Edit-Pfad `WizardStep4ReportConfig` | Wizard-Save `Step4Briefings` |
|---|---|---|
| **Konzept** | Δ-Alarmierung (bei Änderungen) | Absolut-Alarmierung (bei schlechtem Wetter) |
| **Felder** | `change_threshold_temp_c`<br>`change_threshold_wind_kmh`<br>`change_threshold_precip_mm` | `gust_kmh`<br>`precip_mm`<br>`thunder_level`<br>`snow_line_m` |
| **Maps zu AlertRule** | `kind=delta` (3 Metric-Felder pro Rule expandiert) | `kind=absolute` (1 Metric pro Rule) |

Das Issue-Body von #223 hat das übersehen — die im Issue genannten Felder
(`gust_kmh, precip_mm, thunder_level, snow_line_m`) **gibt es im Edit-Pfad
gar nicht**.

## Related Files

| Datei | Relevanz |
|------|----------|
| `frontend/src/lib/components/edit/TripEditView.svelte` | Accordion-Container, Save-Handler (Z.39-60), Payload-Konstruktion (Z.44-50). **Erweitern** um `alertRules`-State. |
| `frontend/src/lib/components/wizard/WizardStep4ReportConfig.svelte` | Edit-Pfad Step 4. Hat heute Δ-Felder. **Klären:** UI ergänzen um Wizard-Felder ODER nur `alert_rules` aus bestehenden Δ-Feldern schreiben? |
| `frontend/src/lib/utils/alertMapping.ts` | W2 pure function `mapBriefingsToAlertRules`. **Erweitern** um Reverse-Mapping `alertRulesToThresholds`. |
| `frontend/src/lib/utils/alertMetricLabels.ts` | Bleibt. |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | Edit-Link **wieder ergänzen** (heute Z.8 Kommentar "Edit-Link entfernt"). |
| `frontend/src/routes/trips/[id]/edit/+page.server.ts` | Loader fetcht Trip mit `alert_rules`. Read-only. |
| `frontend/e2e/trip-edit.spec.ts` | Vorlage für E2E. Hat Data-Integrity-Pattern (Z.171-195). |

## Existing Patterns

### 1. TripEditView Save-Pipeline
```typescript
// TripEditView.svelte:44-50
const updated: Trip = {
    ...trip,
    name: tripName,
    stages,
    display_config: displayConfig,
    report_config: reportConfig,
    // alert_rules: NICHT GESETZT — Lücke
};
await fetch(`/api/trips/${trip.id}`, { method: 'PUT', body: JSON.stringify(updated) });
```

### 2. WizardStep4ReportConfig Bidirektion
Lokale `$state`-Vars, beim Mount aus `reportConfig` lesen, in `$effect`
zurückschreiben. Pattern bleibt erhalten — Erweiterung für alert_rules
braucht eigenen Prop `bind:alertRules`.

### 3. Wizard-Mapper aus W2
- `mapBriefingsToAlertRules({gust_kmh, precip_mm, thunder_level, snow_line_m}): AlertRule[]`
- `kind=absolute`, alle severity=warning, enabled=true

### 4. Migration aus Issue #205 (Backend)
`src/app/loader.py:53-83` migriert `report_config.change_threshold_*`
→ AlertRule mit `kind=delta`, severity=warning, enabled=(alert_on_changes).
Mapping:
- `change_threshold_temp_c` → `temperature_change` (Δ-Metric)
- `change_threshold_wind_kmh` → `wind_change`
- `change_threshold_precip_mm` → `precipitation_change`

## Scope-Entscheidung (offen, für Phase 2)

Drei Optionen:

**A. UI-Vereinheitlichung (großer Scope, ~300+ LoC):**
`WizardStep4ReportConfig` bekommt die 4 Absolut-Felder wie der Wizard.
Δ-Felder bleiben (sind etwas anderes) oder verschwinden unter "Erweitert".

**B. Edit-Pfad schreibt nur Δ-AlertRules (kleinster Scope, ~120 LoC):**
Die 3 bestehenden Δ-Threshold-Felder werden zu `alert_rules`-Rules mit
`kind=delta` gemappt (genau wie die Migration in Issue #205). Reverse-Mapping
liest sie zurück in die UI. **Keine UI-Änderung** — nur Save/Load-Logik
plus Edit-Link in der Card. Drei AC abdeckbar.

**C. Hybrid (mittlerer Scope):**
Δ-Felder bleiben, zusätzlich neuer Block "Absolute Alarmierung" mit den
4 Wizard-Feldern. Beide schreiben in `alert_rules` (mixed kind=delta+absolute).

## Dependencies

**Upstream:**
- Issue #222 W1 (Backend `from_alert_rules` + Service-Priorität) — live
- Issue #222 W2 (Wizard-Save + Card) — live
- Issue #205 (Datenmodell, Migration) — live

**Downstream:**
- Bestehende E2E-Tests in `trip-edit.spec.ts` (sechs AC, AC-4 = Save mit
  PUT) — können bei UI-Änderung brechen, müssen ggf. angepasst werden

## Risks & Considerations

1. **Scope-Frage A/B/C** ist User-Entscheidung. Kein klares "richtig".
2. **Δ-Rules vs. Absolut-Rules sind unterschiedlich:** Backend feuert sie
   anders (`|new - old| > threshold` vs. `new > threshold`). UI muss das
   transparent machen, sonst missversteht der User die Schwelle.
3. **Reverse-Mapping ist verlustbehaftet:** Wenn jemand viele Rules pro
   Metric hat (z.B. zwei wind_gust-Rules mit unterschiedlichen Schwellen),
   passt das nicht in ein einzelnes UI-Feld. Pragmatisch: nimm die erste
   enabled Rule pro Metric oder "letzter wins".
4. **`alert_on_changes` Flag:** Heute steuert das den ganzen Alert-Pfad
   für `kind=delta`. Bei `enabled=false` zeigt die Card heute Empty-State.
   Soll bleiben.
5. **W2-Edit-Link wieder einbauen:** AlertsPreviewCard.svelte:8 hat einen
   Kommentar — Hinweis vorhanden, einfach zurück nehmen.

## Scope-Entscheidung (User, 2026-05-14)

**Option D: Liste-basierter `AlertRulesEditor`** — Wiederverwendbare
Svelte-Komponente, die das `alert_rules`-Datenmodell direkt spiegelt.
LoC-Override auf 350 (Workflow-Limit).

### Architektur Entscheidungen

1. **`AlertRulesEditor.svelte`** — Container-Komponente:
   - Prop `bind:rules: AlertRule[]` (2-Way über `$bindable()`)
   - Empty-State + Add-Button + Liste von `AlertRuleRow`

2. **`AlertRuleRow.svelte`** — Eine Zeile pro Rule, zwei Modi:
   - **View-Mode (Default):** Label + Threshold/Vergleich + Severity-Pill + Enabled-Toggle + [Bearbeiten] [Löschen]
   - **Edit-Mode:** Inline-Form mit Metric-Select, Threshold-Input (Number bzw. Enum), Severity-Select, Enabled-Checkbox, [Speichern] [Abbrechen]

3. **Integration:**
   - **TripEditView:** Neuer Accordion-Block "Alarmregeln" zwischen "Wetter" und "Reports", mit `<AlertRulesEditor bind:rules={alertRules} />`. State: `let alertRules = $state(trip.alert_rules ?? [])`. Save schreibt `updated.alert_rules = alertRules`.
   - **AlertsPreviewCard:** Edit-Link wieder ergänzen, zeigt auf `/trips/[id]/edit#alerts`.
   - **Wizard:** **NICHT** umgestellt. `Step4Briefings` + `mapBriefingsToAlertRules` bleiben. Wizard-Umstellung auf den neuen Editor ist Folge-Iteration.
   - **`WizardStep4ReportConfig`** (Edit-Step-4): Δ-Felder (`change_threshold_*`) **bleiben** in `report_config`. Backward-Compat: Wenn nur diese gesetzt sind und keine `alert_rules` existieren, greift Backend-Migration aus Issue #205 weiter (delta-Rules werden bei Load erzeugt). Sobald User über den neuen Editor Rules ändert, hat `alert_rules` Vorrang (W1-Priorität).

4. **Add-Default:** Neue Rule bekommt `kind=absolute`, Metric=`wind_gust` (häufigster Use-Case), threshold=0, severity=`warning`, enabled=true, id via `crypto.randomUUID()`. User editiert sofort.

5. **Vorlagen-Sets:** **NICHT** in dieser Iteration. Folge-Issue.

### Was wird abgelöst (langfristig, nicht hier)

- `mapBriefingsToAlertRules` (W2): bleibt für den Wizard, wird redundant sobald Wizard umgestellt
- `report_config.alert_thresholds` als Source-of-Truth: wird redundant, sobald alle Trips über den neuen Editor liefen
- Δ-Schwellen-UI in `WizardStep4ReportConfig`: wird redundant, sobald User Δ-Rules direkt im Editor managen

## Next

Phase 3 (Spec) — Architektur ist klar, Komponenten-Schnitte sind klar,
Reverse-Mapping entfällt (Liste zeigt Rules direkt).
