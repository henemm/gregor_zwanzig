# Context: Issue #224 — Wizard auf AlertRulesEditor umstellen

## Request Summary

Trip-Wizard Step 4 (`/trips/new`) zeigt heute noch vier feste Threshold-Felder
(gust_kmh, precip_mm, thunder_level, snow_line_m, alle severity=`warning`).
Der Edit-Pfad (`/trips/[id]/edit`) nutzt seit Issue #223 den `AlertRulesEditor`
(freie Metrics, freie Severity, Add/Edit/Delete). Ziel: dieselbe Komponente im
Wizard verwenden — **eine UI für ein Datenmodell**, damit TEMPERATURE_MIN-Kälte­
alarm und `critical`-Severity direkt bei der Trip-Anlage verfügbar sind.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | Sektion 3 (Z. 131–171, „Alert-Schwellwerte") wird ersetzt; ThresholdRow-Imports/Handler entfallen. |
| `frontend/src/lib/components/trip-wizard/steps/ThresholdRow.svelte` | **Löschen** — nur in Step4Briefings verwendet. |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `BriefingConfig.thresholds` und `defaultBriefingConfig.thresholds` entfallen; neuer State `alertRules: AlertRule[]`. `toTripPayload` schreibt `trip.alert_rules = this.alertRules`, kein Mapper-Aufruf. Frage Phase 2: bleibt `report_config.alert_thresholds` als BC-Block? |
| `frontend/src/lib/utils/alertMapping.ts` | **Löschen** — wird durch direktes State-Schreiben überflüssig. |
| `frontend/src/lib/utils/alertMapping.test.ts` | **Löschen** mit Modul. |
| `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` | AC-1/AC-2/AC-3/AC-7 Threshold→AlertRule-Tests (Z. 77–135, 720–762) ersetzen durch direkte `alert_rules`-Tests. AC#18/#18b/#19 (alert_thresholds-Block) abhängig von Phase-2-Entscheidung. |
| `frontend/e2e/trip-wizard-step4.spec.ts` | AC#9/AC#10 (Z. 108–134) testen alte Threshold-TestIDs — auf `alert-rules-editor`/`alert-rule-row` umstellen. |
| `frontend/e2e/helpers.ts` | `Step4Input.thresholds` + `fillStep4`-Threshold-Block (Z. 136–141, 195–218) auf neuen Editor anpassen. |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Wiederzuverwendende Komponente (`bind:rules={alertRules}`). |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | `newDefaultRule()` liefert wind_gust=50 km/h (warning). |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Referenz-Implementierung (Z. 26–28, 56, 116) — Muster für `alertRules: AlertRule[] = $state(...)`. |

## Existing Patterns

- **AlertRulesEditor** ist Container-Component mit `let { rules = $bindable<AlertRule[]>([]) }`. Konsument bindet `bind:rules={alertRules}`.
- **State-Initialisierung im Edit-Pfad:** `let alertRules: AlertRule[] = $state(Array.isArray(trip.alert_rules) ? JSON.parse(JSON.stringify(...)) : [])`. Im Wizard reicht ein leeres Array als Start, oder ein fester Default analog `mapBriefingsToAlertRules(defaultThresholds)` → derzeit liefert das `[]`, weil alle Defaults `null` sind.
- **Save-Pfad:** `alert_rules: alertRules` direkt in den Payload schreiben — `trip.alert_rules` ist bereits typisiert (`AlertRule[]`).
- **Safari-Factory-Pattern** ist hier nicht mehr nötig in der Threshold-Sektion, weil AlertRulesEditor seine eigenen Event-Handler hat. Die anderen Step-4-Sektionen (Channels, Reports) behalten ihr Factory-Pattern.

## Dependencies

- **Upstream:** `AlertRulesEditor.svelte`, `AlertRuleRow.svelte`, `alertRuleDefaults.ts`, Typ `AlertRule` aus `$lib/types`.
- **Downstream:**
  - `WizardState.toTripPayload()` → `POST /api/trips` (Go-Backend liest `trip.alert_rules` priorisiert seit W1).
  - `AlertsPreviewCard` (Trip-Detail) liest `trip.alert_rules`.
  - `mapBriefingsToAlertRules` wird nur von `wizardState.svelte.ts` aufgerufen → kann mit Wizard-Refactor entfallen.

## Existing Specs

- `docs/specs/modules/epic_136_step4_briefings.md` — Sub-Spec #164 (heutiges Step-4-Verhalten, AC#9–#10 für Thresholds, AC#18/#19 für `alert_thresholds`-Block). **Muss in Phase 3 ergänzt/überarbeitet werden** (Schwellwerte-Sektion wird durch AlertRulesEditor ersetzt).
- `docs/specs/modules/issue_223_alert_rules_editor.md` — definiert `AlertRulesEditor`-Komponente.
- `docs/specs/modules/issue_222_w2_frontend_alert_konfigurator.md` — Mapper-Spec (wird zur Folge dieses Issues archiviert).
- `docs/specs/modules/epic_136_trip_wizard.md` (Master) — `BriefingConfig`-Definition in §3.1, Update nötig.

## Phase-2-Erkenntnisse (Recherche-Ergebnis)

**Frage 1 — `report_config.alert_thresholds`-Block kann entfallen?** **JA.**
- Grep über `src/`, `internal/`, `api/`, `cmd/` findet **null Konsumenten**, die `alert_thresholds` lesen. Das Feld ist write-only Bridge aus Issue #222 W2 und wurde nie an einen Reader angeschlossen.
- Die Issue #205-Migration (`src/app/loader.py:53–83 _migrate_legacy_alert_rules()`) konvertiert nicht `alert_thresholds`, sondern `report_config.change_threshold_*` → `alert_rules`. Davon ist Issue #224 nicht betroffen.
- AC-6 vom Issue ist leicht missverständlich formuliert: Backward-Compat betrifft die `change_threshold_*`-Migration, nicht den `alert_thresholds`-Block. Sicher zu streichen.

**Frage 2 — Wizard-Default beim Start?** **Empfehlung: leere Liste `[]`.**
- Heute startet der Wizard mit allen Thresholds `null` ⇒ faktisch leere Regelliste (Mapper liefert `[]`).
- Edit-Pfad (`TripEditView.svelte:26–30`) startet `AlertRulesEditor` ebenfalls mit `[]` wenn keine Regeln vorhanden.
- AC#14 (Spec #164) verlangt: „Schwellwert-Inputs zeigen initial keinen Wert (alle null)."
- Konsistent, ehrlich („keine Regeln") und vermeidet hardcoded Default (z.B. wind_gust=50 km/h), der für Skitour-Trips unpassend wäre.
- Aktivitätsspezifische Vorlagen sind laut Issue ein Folge-Ticket.

**Frage 3 — `trip.alert_rules` Read-Path robust?** **JA.** End-to-End-Severity-Round-Trip durch Frontend → Go-Handler (`internal/handler/trip.go:174–175`) → Store → Python-Loader (`src/app/loader.py:48`) → `TripAlertService` (`src/services/trip_alert.py:160`) → E-Mail-Channel (`src/services/weather_change_detection.py:282–286`) bestätigt. Mapping severity → ChangeSeverity ist gepflegt.

## Strategie

### Architekturansatz

Klare Schneise: `BriefingConfig.thresholds` ersatzlos entfernen. Neuer Top-Level-State `alertRules: AlertRule[]` direkt in `WizardState` (analog `stages`). Wizard und Edit-Pfad teilen sich `AlertRulesEditor`-Komponente — eine UI, ein Datenmodell. `mapBriefingsToAlertRules` wird obsolet, `alert_thresholds`-BC-Schreiben entfällt.

### Implementierungs-Reihenfolge

1. **TDD RED** — Tests anpassen:
   - `wizardState.test.ts`: alte Threshold→AlertRule-Tests (Z. 77–135, 720–762) löschen, neue Tests für direkten `alertRules`-State und `toTripPayload`-Verhalten schreiben (kein `alert_thresholds`-Block mehr).
   - `trip-wizard-step4.spec.ts`: AC#9/#10 ersetzen durch Tests gegen `alert-rules-editor`/`alert-rule-row`; neuer Test: TEMPERATURE_MIN + critical-Severity über Wizard anlegbar.
   - `alertMapping.test.ts`: löschen.
2. **TDD GREEN** — Code anpassen:
   - `wizardState.svelte.ts`: `thresholds` aus `BriefingConfig` entfernen, `alertRules: AlertRule[] = $state([])` hinzufügen, `cloneBriefingConfig` anpassen, `toTripPayload`: `rc.alert_thresholds` + `mapBriefingsToAlertRules`-Block durch direktes `if (this.alertRules.length > 0) trip.alert_rules = [...this.alertRules]` ersetzen.
   - `Step4Briefings.svelte`: Sektion 3 (Threshold-Block) ersetzen durch `<AlertRulesEditor bind:rules={wizard.alertRules} />`; ThresholdRow-Imports + 4 Threshold-Factory-Handler löschen; Eyebrow-Label „Alert-Schwellwerte" → „Alarmregeln".
   - `e2e/helpers.ts::fillStep4`: `Step4Input.thresholds` ersetzen durch `Step4Input.alertRules: AlertRule[]`; Hilfsfunktion klickt Add-Button und füllt Rows.
   - Löschen: `alertMapping.ts`, `ThresholdRow.svelte`.

### Scope-Schätzung

| Kategorie | Anzahl |
|-----------|--------|
| Dateien angefasst | 5 |
| Dateien gelöscht | 3 (`alertMapping.ts`, `alertMapping.test.ts`, `ThresholdRow.svelte`) |
| LoC-Delta (geschätzt) | netto −150 bis −250 (Löschungen + Test-Konsolidierung größer als Editor-Integration) |

LoC-Limit 250 sollte locker eingehalten werden, da der Großteil Löschung ist.

### Risiken

- **`fillStep4` Signatur-Bruch**: Nur eine Aufrufer-Stelle (`helpers.ts` selbst), keine anderen E2E-Specs nutzen `Step4Input.thresholds` → folgenarm.
- **Spec-Drift**: `epic_136_step4_briefings.md` AC#9/#10/#14/#18/#18b/#19 sind nach Umbau falsch. Update in Phase 3 erforderlich.

## Nächster Schritt

Phase 3 (Spec): `docs/specs/modules/issue_224_wizard_alert_rules_editor.md` schreiben + Update an `epic_136_step4_briefings.md` (Sektion-3-Änderungen markieren).
