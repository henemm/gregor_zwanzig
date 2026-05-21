---
entity_id: bug_317_alert_rules_editor_metrics
type: bugfix
created: 2026-05-21
updated: 2026-05-21
status: draft
version: "1.0"
tags: [bugfix, frontend, alert-rules, metric-normalization, legacy-data, issue-317]
---

<!-- Issue #317 — Bug: AlertRulesEditor zeigt nur 3 von 6 Metriken (precipitation, thunder, snowfall_limit fehlen) -->

# Issue #317 — Bug-Fix: AlertRulesEditor — Legacy-Metrik-IDs normalisieren + F004-Guard absichern

## Approval

- [ ] Approved

## Zweck

Der `AlertRulesEditor` blendet Alert-Regeln mit veralteten Metrik-IDs (`precipitation`, `thunder`, `snowfall_limit`) stillschweigend aus, weil `ALERT_METRIC_LABELS` diese IDs nicht kennt und der Guard `{#if info}` in `AlertRuleRow.svelte` die gesamte Zeile versteckt statt einen Fallback zu rendern. Betroffene Trips zeigen damit nur 3 von 6 Metriken — die drei Legacy-IDs sind schlicht unsichtbar, ohne Fehlermeldung. Der Fix führt eine `normalizeAlertMetric()`-Funktion ein, die beim Laden von Trip-Daten Legacy-IDs auf aktuelle `AlertMetric`-Enum-Werte abbildet, und ersetzt den stillen F004-Guard durch einen sichtbaren Fallback-Block mit Löschen-Button.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/lib/utils/alertMetricLabels.ts` — neue `LEGACY_ALERT_METRIC_MAP`-Konstante + `normalizeAlertMetric()`-Funktion
- `frontend/src/lib/utils/alertMetricLabels.test.ts` — Unit-Tests für `normalizeAlertMetric()`
- `frontend/src/lib/components/edit/TripEditView.svelte` — Normalisierung beim Laden von `trip.alert_rules`
- `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` — Normalisierung beim Laden (Konsistenz)
- `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` — `{:else}`-Fallback-Block statt completem Verstecken bei unbekanntem Metrik-Namen

**Datenpatch (einmalig):**
- `/home/hem/gregor_zwanzig_staging/data/users/validator-issue110/trips/ac206-validator-1779092432.json` — 3 metric-Felder auf aktuelle IDs korrigieren (`precipitation` → `precipitation_sum`, `thunder` → `thunder_level`, `snowfall_limit` → `snow_line`)

> **Schicht-Hinweis:** Alle Code-Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Der Datenpatch betrifft eine Testdaten-JSON-Datei in der Staging-Umgebung. Kein Go-API-Code, kein Python-Backend-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/utils/alertMetricLabels.ts` | TypeScript-Modul | Definiert `ALERT_METRIC_LABELS` und den `AlertMetric`-Typ; wird um `LEGACY_ALERT_METRIC_MAP` + `normalizeAlertMetric()` erweitert |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Svelte-Komponente | Rendert eine einzelne Alert-Regel-Zeile; F004-Guard `{#if info}` versteckt Zeile bei unbekanntem Metrik-Namen |
| `frontend/src/lib/components/edit/TripEditView.svelte` | Svelte-Komponente | Lädt `trip.alert_rules` beim Trip-Öffnen; primärer Einstiegspunkt für Normalisierung |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Svelte-Komponente | Zweiter Ladepfad für Alert-Rules im Alerts-Tab; erhält dieselbe Normalisierung für Konsistenz |
| `frontend/src/lib/utils/alertMetricLabels.test.ts` | TypeScript-Testdatei | Unit-Tests für die neue `normalizeAlertMetric()`-Funktion |

## Implementation Details

### 1. `alertMetricLabels.ts` — Legacy-Map + Normalisierungs-Funktion

Neue Konstante und Export-Funktion ans Ende der bestehenden Datei anfügen:

```typescript
const LEGACY_ALERT_METRIC_MAP: Record<string, AlertMetric> = {
  precipitation: 'precipitation_sum',
  thunder: 'thunder_level',
  snowfall_limit: 'snow_line',
};

export function normalizeAlertMetric(raw: string): AlertMetric | undefined {
  if (raw in ALERT_METRIC_LABELS) return raw as AlertMetric;
  return LEGACY_ALERT_METRIC_MAP[raw];
}
```

`LEGACY_ALERT_METRIC_MAP` ist nicht exportiert — es ist ein internes Implementierungsdetail. `normalizeAlertMetric()` gibt `undefined` zurück, wenn die ID weder aktuell noch Legacy ist.

### 2. `alertMetricLabels.test.ts` — Unit-Tests

Vier Testfälle:

```
test — bekannte aktuelle ID ('precipitation_sum') → gibt 'precipitation_sum' zurück
test — Legacy-ID 'precipitation' → gibt 'precipitation_sum' zurück
test — Legacy-ID 'thunder' → gibt 'thunder_level' zurück
test — Legacy-ID 'snowfall_limit' → gibt 'snow_line' zurück
test — vollständig unbekannte ID ('foobar') → gibt undefined zurück
```

### 3. `TripEditView.svelte` + `AlertsTab.svelte` — Normalisierung beim Laden

Import ergänzen:

```typescript
import { normalizeAlertMetric } from '$lib/utils/alertMetricLabels';
```

An der Stelle, wo `trip.alert_rules` in den lokalen State übernommen wird, jede Rule durch die Normalisierung laufen lassen:

```typescript
alert_rules: (trip.alert_rules ?? []).map(r => ({
  ...r,
  metric: normalizeAlertMetric(r.metric) ?? r.metric,
}))
```

Der `?? r.metric`-Fallback stellt sicher, dass komplett unbekannte IDs erhalten bleiben und im F004-Fallback-Block (Schritt 4) sichtbar werden.

### 4. `AlertRuleRow.svelte` — Fallback statt Verstecken (Zeile 131)

Bestehenden Block:

```svelte
{#if info}
  ... bestehender Zeilen-Inhalt ...
{/if}
```

Erweitern um `{:else}`:

```svelte
{#if info}
  ... bestehender Zeilen-Inhalt ...
{:else}
  <div class="alert-rule-view alert-rule-unknown" data-testid="alert-rule-unknown">
    <span class="label">[{rule.metric}]</span>
    <Btn variant="ghost" size="sm" onclick={onDelete} data-testid="alert-rule-delete">Löschen</Btn>
  </div>
{/if}
```

Der Fallback-Block zeigt die rohe Metrik-ID in eckigen Klammern und einen Löschen-Button — kein stiller Datenverlust mehr.

### 5. Datenpatch Staging-Testdaten

In der Datei `ac206-validator-1779092432.json` drei `metric`-Felder direkt ersetzen:

| Vorher | Nachher |
|--------|---------|
| `"metric": "precipitation"` | `"metric": "precipitation_sum"` |
| `"metric": "thunder"` | `"metric": "thunder_level"` |
| `"metric": "snowfall_limit"` | `"metric": "snow_line"` |

Kein Schema-Change, nur Wert-Korrekturen. Nach dem Patch öffnet der Alerts-Tab dieses Trips alle 6 Regeln ohne Normalisierung.

### 6. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/lib/utils/alertMetricLabels.ts` | +10 | nein (Frontend-Asset) |
| `frontend/src/lib/utils/alertMetricLabels.test.ts` | +25 (neu) | nein (Frontend-Asset) |
| `frontend/src/lib/components/edit/TripEditView.svelte` | +5 | nein (Frontend-Asset) |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | +5 | nein (Frontend-Asset) |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | +6 | nein (Frontend-Asset) |
| Datenpatch JSON | +0 / -0 (3 Wert-Ersetzungen) | nein |
| **Gesamt (zählend)** | **0** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Trip-JSON mit Alert-Rules, deren `metric`-Felder entweder aktuelle `AlertMetric`-Enum-Werte oder Legacy-IDs enthalten
- **Output:** Alle 6 Alert-Regeln werden im `AlertRulesEditor` angezeigt. Legacy-IDs werden beim Laden transparent auf aktuelle Werte normalisiert. Unbekannte IDs werden als `[raw-id]`-Fallback mit Löschen-Button dargestellt
- **Side effects:** Beim nächsten Speichern des Trips werden die normalisierten IDs persistiert — die Legacy-IDs verschwinden dauerhaft aus dem JSON. Trips, die bereits korrekte IDs haben, sind nicht betroffen.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit einer Alert-Rule `"metric": "precipitation"` (Legacy-ID) / When der Alerts-Tab geöffnet wird / Then ist die Regel im Editor sichtbar und zeigt den Label für `precipitation_sum`
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Trip mit einer Alert-Rule `"metric": "thunder"` (Legacy-ID) / When der Alerts-Tab geöffnet wird / Then ist die Regel im Editor sichtbar und zeigt den Label für `thunder_level`
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Trip mit einer Alert-Rule `"metric": "snowfall_limit"` (Legacy-ID) / When der Alerts-Tab geöffnet wird / Then ist die Regel im Editor sichtbar und zeigt den Label für `snow_line`
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein Trip mit einer Alert-Rule mit völlig unbekannter Metrik-ID `"metric": "foobar"` / When der Alerts-Tab geöffnet wird / Then wird die Regel als `[foobar]` mit Löschen-Button angezeigt — keine Row wird ausgeblendet
  - Test: (populated after /tdd-red)

- **AC-5:** Given `normalizeAlertMetric('precipitation_sum')` (aktuelle ID) / When die Funktion aufgerufen wird / Then gibt sie `'precipitation_sum'` zurück — keine Doppelt-Mapping-Schleife
  - Test: `test — bekannte aktuelle ID gibt sich selbst zurück`

- **AC-6:** Given der Validator-Staging-Trip `ac206-validator-1779092432` / When der Alerts-Tab geöffnet wird / Then sind alle 6 Alert-Regeln sichtbar (3 Wetter-Metriken + 3 weitere)
  - Test: (populated after /tdd-red)

## Known Limitations

- **Normalisierung nur im Frontend:** Die Legacy-IDs werden nur beim Laden im Frontend normalisiert. Erst beim nächsten Speichern des Trips werden die korrigierten IDs persistiert. Ein datenbankweites Migration-Script ist nicht Teil dieses Scopes — die Frontend-Normalisierung reicht als Lazy-Migration.
- **`normalizeAlertMetric()` kennt nur 3 Legacy-Mappings:** Sollten weitere veraltete IDs existieren, müssen sie manuell in `LEGACY_ALERT_METRIC_MAP` nachgetragen werden. Der F004-Fallback-Block macht unbekannte IDs künftig sichtbar statt sie zu verlieren, was die Entdeckung weiterer Legacy-IDs erleichtert.

## Out of Scope

- Backend-seitige Migration aller Trip-JSONs auf aktuelle Metrik-IDs
- Automatische Erkennung weiterer Legacy-Mappings
- Änderungen an der `AlertMetric`-Enum-Definition oder `ALERT_METRIC_LABELS`
- Go-API- oder Python-Backend-Änderungen

## Changelog

- 2026-05-21: Initial spec erstellt. Behebt stillen Datenverlust im AlertRulesEditor durch Legacy-Metrik-Normalisierung (3 Mappings) in alertMetricLabels.ts und F004-Guard-Absicherung in AlertRuleRow.svelte. 5 Frontend-Dateien + 1 Datenpatch, ~50 LoC.
