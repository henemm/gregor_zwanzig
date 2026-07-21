---
entity_id: issue_441_compare_wizard_step3_idealwerte
type: module
created: 2026-05-29
updated: 2026-05-29
status: implemented
version: "1.0"
issue: 441
tags: [sveltekit, frontend, wizard, step3, idealwerte, compare, epic-438]
---

# Issue #441 — Orts-Vergleich Wizard Step 3 (Idealwerte)

## Approval

- [x] Approved
- [x] Implemented (2026-05-29)

## Purpose

Implementiert Wizard Step 3 des Orts-Vergleichs: Der Nutzer legt pro Metrik fest, was für ihn „gutes Wetter" bedeutet — einen idealen Wertebereich mit Min- und Max-Eingabe, abgestimmt auf das in Step 1 gewählte Aktivitätsprofil. Step 3 ist das zentrale Konfigurationselement von Epic #438 und trennt erstmals die Frage „welche Metriken" (Step 1, Profil) von der Frage „welche Werte sind gut" (Step 3, Idealwerte), sodass der Vergleichs-Algorithmus sinnvoll personalisiert werden kann.

## Source

- **NEU:** `frontend/src/lib/components/compare/compareMetricDefs.ts` — Shared Module: `MetricDef`-Typ + `PROFILE_METRICS_WITH_SCALES` + `IDEAL_DEFAULTS`; CompareMatrix.svelte und Step3 importieren hieraus
- **NEU:** `frontend/src/lib/components/compare/steps/Step3Idealwerte.svelte` — Step-Komponente (~120 LoC)
- **NEU:** `frontend/src/lib/components/compare/__tests__/issue_441_step3_idealwerte.test.ts` — Source-Inspection-Tests (node:test, ~80 LoC)
- **EDIT:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts` — `idealRanges`-Feld + `save()`/`toggleEnabled()` + `canAdvanceCurrent` Step 3
- **EDIT:** `frontend/src/lib/components/compare/CompareWizard.svelte` — Placeholder Zeile 141–145 durch `<Step3Idealwerte>` ersetzen
- **EDIT:** `frontend/src/lib/components/compare/steps/Step1Vergleich.svelte` — Profil-Klick-Confirm wenn `idealRanges` nicht leer
- **EDIT:** `frontend/src/routes/compare/[id]/edit/+page.svelte` — `ideal_ranges` aus `display_config` in State laden

> **Schicht-Zuordnung:** Rein Frontend (`frontend/src/`). Kein Backend-Change — `display_config` ist eine opaque `map[string]interface{}` im Go-Modell; der API-Handler reicht den Wert unverändert durch. `PUT /api/subscriptions/{id}` und `POST /api/subscriptions` nehmen `ideal_ranges` als Teil von `display_config` entgegen ohne Schema-Änderung.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/compare/CompareMatrix.svelte` | component (edit-import) | Wird auf `compareMetricDefs.ts` umgestellt; `PROFILE_METRICS` wird durch `PROFILE_METRICS_WITH_SCALES` ersetzt |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | state class (edit) | Nimmt `idealRanges: Record<string, IdealRange>` als neues `$state`-Feld auf |
| `frontend/src/lib/types.ts` | types | `ActivityProfile`, `toCompareProfile` — Profil-Mapping |
| `$lib/components/ui/select/Select.svelte` | component | Sonderfall `thunder_level_max` (kind=`'enum'`, Werte `NONE`/`MED`/`HIGH`) |
| `internal/model/subscription.go` | Go type (read-only) | `display_config map[string]interface{}` — opaque, kein Schema-Change |
| `GET /api/subscriptions/{id}` | api endpoint | Edit-Loader: liefert `display_config.ideal_ranges` zum Vorladen |
| `PUT /api/subscriptions/{id}` / `POST /api/subscriptions` | api endpoint | Save schreibt `ideal_ranges` in `display_config` |

## Implementation Details

### §1 `compareMetricDefs.ts` — Kerntypen und Konstanten

```typescript
export interface MetricDef {
  label: string;
  key: string;          // keyof CompareMetrics
  unit: string;
  decimals: number;
  higherIsBetter: boolean;
  kind: 'range' | 'enum';
  // nur für kind === 'range':
  rangeMin?: number;
  rangeMax?: number;
  step?: number;
  // nur für kind === 'enum':
  enumValues?: string[];
}

export interface IdealRange {
  min?: number | null;
  max?: number | string | null; // string für enum (NONE/MED/HIGH)
}

export type ProfileKey = 'WINTERSPORT' | 'ALPINE_TOURING' | 'SUMMER_TREKKING' | 'ALLGEMEIN';

export const PROFILE_METRICS_WITH_SCALES: Record<ProfileKey, MetricDef[]>;
export const IDEAL_DEFAULTS: Record<ProfileKey, Record<string, IdealRange>>;
```

**Skalengrenzen pro Metrik:**

| key | rangeMin | rangeMax | step | unit |
|-----|----------|----------|------|------|
| `temp_max_c` | -20 | 45 | 1 | °C |
| `wind_max_kmh` | 0 | 100 | 5 | km/h |
| `precip_sum_mm` | 0 | 30 | 0.5 | mm |
| `snow_depth_cm` | 0 | 200 | 5 | cm |
| `snow_new_sum_cm` | 0 | 50 | 1 | cm |
| `sunny_hours_h` | 0 | 12 | 0.5 | h |
| `cloud_avg_pct` | 0 | 100 | 5 | % |
| `visibility_min_m` | 0 | 10000 | 500 | m |
| `uv_index_max` | 0 | 12 | 1 | — |
| `thunder_level_max` | — | — | — | kind=`'enum'`, enumValues=`['NONE','MED','HIGH']` |

**Default-IdealRanges aus IDEAL_DEFAULTS:**

| Profil | Metrik | min | max |
|--------|--------|-----|-----|
| WINTERSPORT | `snow_depth_cm` | 30 | 200 |
| WINTERSPORT | `snow_new_sum_cm` | 5 | 50 |
| WINTERSPORT | `wind_max_kmh` | 0 | 40 |
| WINTERSPORT | `cloud_avg_pct` | 0 | 60 |
| ALPINE_TOURING | `snow_new_sum_cm` | 0 | 10 |
| ALPINE_TOURING | `visibility_min_m` | 2000 | 10000 |
| ALPINE_TOURING | `wind_max_kmh` | 0 | 50 |
| SUMMER_TREKKING | `precip_sum_mm` | 0 | 3 |
| SUMMER_TREKKING | `thunder_level_max` | — | `'NONE'` |
| SUMMER_TREKKING | `wind_max_kmh` | 0 | 35 |
| SUMMER_TREKKING | `uv_index_max` | 0 | 8 |
| ALLGEMEIN | `temp_max_c` | 15 | 35 |
| ALLGEMEIN | `wind_max_kmh` | 0 | 50 |
| ALLGEMEIN | `precip_sum_mm` | 0 | 5 |

`CompareMatrix.svelte` importiert künftig `PROFILE_METRICS_WITH_SCALES` statt des bisherigen `PROFILE_METRICS`-Literals.

### §2 `compareWizardState.svelte.ts` — Erweiterungen

**Neues Feld:**
```typescript
idealRanges = $state<Record<string, IdealRange>>({});
```

**`canAdvanceCurrent` Step 3:** Gibt `true` zurück — keine Pflicht-Eingabe; der Nutzer kann mit leeren oder teil-befüllten Idealwerten weiter.

**`save()` und `toggleEnabled()`:** `display_config` wird um `ideal_ranges` erweitert:
```typescript
display_config: {
  ...this.existingDisplayConfig,
  ...(this.region ? { region: this.region } : {}),
  ...(Object.keys(this.idealRanges).length > 0
    ? { ideal_ranges: this.idealRanges }
    : {})
}
```
Leeres `idealRanges`-Objekt (`{}`) wird nicht als `ideal_ranges: {}` gespeichert.

### §3 `Step3Idealwerte.svelte` — Layout und Verhalten

**Context:** `getContext('compare-wizard-state')` → `CompareWizardState`

**Fallback-Profil:** Kein Profil gewählt → Fallback auf `ALLGEMEIN` (analog `CompareMatrix` Zeile 57).

**$effect Defaults:** Beim ersten Rendern für ein Profil werden Default-Werte aus `IDEAL_DEFAULTS` gesetzt, **nur wenn** der jeweilige Key noch nicht in `state.idealRanges` belegt ist. Schützt im Edit-Modus bereits geladene Werte vor Überschreiben.

```
data-testid="compare-wizard-step-3"
┌─────────────────────────────────────────────────────────────┐
│ IDEALWERTE (Eyebrow)                                        │
│ Pro Aktivitätsprofil werden passende Metriken gezeigt.      │
├─────────────────────────────────────────────────────────────┤
│ pro Metrik (grid-cols-[12rem_1fr_1fr_auto]):                 │
│  [Label mono]  [Min: input] [Max: input/select]  [unit]     │
│                [rangeMin mono]           [rangeMax mono]     │
└─────────────────────────────────────────────────────────────┘
```

**Sonderfall `thunder_level_max` (kind=`'enum'`):**
- Kein `min`-Input — nur `max`-Select mit Optionen `NONE`, `MED`, `HIGH`
- Bindet an `state.idealRanges['thunder_level_max'].max`

**Sonderfall kind=`'range'`:**
- Min-Input (`type="number"`, `min=rangeMin`, `max=rangeMax`, `step`)
- Max-Input (`type="number"`, `min=rangeMin`, `max=rangeMax`, `step`)
- Darunter Skala-Endpunkte als Mono-Span: `{rangeMin}` links, `{rangeMax}` rechts

**Testids:**
- `compare-wizard-step-3` (root `<div>`)
- `compare-step3-metric-{key}` (pro Metrik-Zeile)
- `compare-step3-min-{key}` (min-Input; nur bei kind=`'range'`)
- `compare-step3-max-{key}` (max-Input oder max-Select bei kind=`'enum'`)
- `compare-step3-scale-min-{key}` (Skala-Min-Label)
- `compare-step3-scale-max-{key}` (Skala-Max-Label)

### §4 `Step1Vergleich.svelte` — Profil-Wechsel-Confirm

Onclick der Profil-Tiles wird durch eine Guard-Funktion ersetzt:

```typescript
function handleProfileSelect(value: ActivityProfile) {
  if (Object.keys(state.idealRanges).length > 0 && value !== state.activityProfile) {
    if (!confirm('Aktivitätsprofil wechseln? Deine Idealwert-Einstellungen werden zurückgesetzt.')) return;
    state.idealRanges = {};
  }
  state.activityProfile = value;
}
```

Kein `confirm()` wenn `idealRanges` leer oder dasselbe Profil gewählt wird.

### §5 Edit-Modus: `+page.svelte`

Nach der `region`-Zuweisung aus `display_config`:
```typescript
state.idealRanges =
  (state.existingDisplayConfig.ideal_ranges as Record<string, IdealRange>) ?? {};
```

`IDEAL_DEFAULTS`-`$effect` greift danach nicht überschreibend, da alle Keys bereits belegt sind.

### §6 LoC-Schätzung

| Datei | Änderung | LoC |
|-------|---------|-----|
| `compareMetricDefs.ts` | Neu | ~60 |
| `Step3Idealwerte.svelte` | Neu | ~120 |
| `compareWizardState.svelte.ts` | Erweiterung | ~25 |
| `CompareWizard.svelte` | Placeholder ersetzen | ~5 |
| `Step1Vergleich.svelte` | Guard-Funktion | ~10 |
| `+page.svelte` (edit) | ideal_ranges laden | ~5 |
| `issue_441_step3_idealwerte.test.ts` | Neu | ~80 |
| **Summe** | | **~305 LoC** |

LoC-Override erforderlich: `workflow.py set-field loc_limit_override 300`

## Expected Behavior

- **Input:** `state.activityProfile` (aus Step 1) bestimmt die angezeigte Metrik-Liste. `state.idealRanges` (initiell `{}` bei Create, vorgeladen bei Edit) enthält Min/Max-Werte pro Metrik-Key. User-Eingaben in number-Inputs und enum-Select aktualisieren `state.idealRanges` reaktiv.
- **Output:**
  - Metrik-Liste entsprechend dem gewählten Aktivitätsprofil (Fallback: ALLGEMEIN).
  - Pro Metrik eine Zeile mit Min-Input + Max-Input (kind=`'range'`) oder nur Max-Select (kind=`'enum'`).
  - Skala-Endpunkte als Mono-Labels unter den Inputs.
  - Weiter-Button immer aktiviert (kein Pflichtfeld in Step 3).
  - Beim Speichern wird `idealRanges` (wenn nicht leer) als `display_config.ideal_ranges` persistiert.
- **Side effects:**
  - `$effect`: Beim ersten Rendern pro Profil werden Default-Werte aus `IDEAL_DEFAULTS` in `state.idealRanges` eingetragen, sofern der Key noch nicht belegt ist.
  - Profil-Wechsel in Step 1 mit nicht-leerem `idealRanges`: `confirm()`-Dialog; bei Bestätigung wird `state.idealRanges = {}` gesetzt.
  - `CompareMatrix.svelte` importiert nach der Änderung aus `compareMetricDefs.ts` — kein Verhaltens-Change für die Matrix selbst.

## Acceptance Criteria

**AC-1:** Given der User hat in Step 1 ein Aktivitätsprofil (z.B. WINTERSPORT) gewählt / When Step 3 gerendert wird / Then werden ausschließlich die für dieses Profil definierten Metriken aus `PROFILE_METRICS_WITH_SCALES[profileKey]` als Zeilen angezeigt.

**AC-2:** Given eine Metrik mit `kind='range'` (z.B. `wind_max_kmh`) / When der Nutzer Step 3 betrachtet / Then sind zwei `<input type="number">`-Felder mit `data-testid="compare-step3-min-wind_max_kmh"` und `data-testid="compare-step3-max-wind_max_kmh"` sichtbar, und Eingaben werden sofort in `state.idealRanges['wind_max_kmh']` reflektiert.

**AC-3:** Given die Metrik `thunder_level_max` mit `kind='enum'` / When der Nutzer Step 3 betrachtet / Then ist kein min-Input sichtbar, stattdessen ein Select mit den Optionen `NONE`, `MED`, `HIGH` unter `data-testid="compare-step3-max-thunder_level_max"`; der gewählte Wert wird als String in `state.idealRanges['thunder_level_max'].max` gespeichert.

**AC-4:** Given Step 3 wird zum ersten Mal geöffnet (Create-Modus, `idealRanges` leer) / When die Komponente montiert wird / Then werden die Default-Werte aus `IDEAL_DEFAULTS[profileKey]` in `state.idealRanges` eingetragen, ohne Keys zu überschreiben die bereits belegt sind.

**AC-5:** Given ein gespeicherter Vergleich mit `display_config.ideal_ranges` wird im Edit-Modus geöffnet / When die `+page.svelte` die State-Initialisierung ausführt / Then enthält `state.idealRanges` die gespeicherten Werte, und der `$effect` in Step 3 überschreibt keinen bereits belegten Key mit IDEAL_DEFAULTS-Werten.

**AC-6:** Given der Nutzer hat in Step 3 mindestens eine Idealwert-Eingabe gemacht (`idealRanges` nicht leer) / When er in Step 1 ein anderes Aktivitätsprofil auswählt / Then erscheint ein `confirm()`-Dialog mit dem Text „Aktivitätsprofil wechseln? Deine Idealwert-Einstellungen werden zurückgesetzt."; bei Bestätigung wird `state.idealRanges = {}` gesetzt und das neue Profil übernommen; bei Abbruch bleibt das bisherige Profil aktiv.

**AC-7:** Given der Nutzer befindet sich in Step 3 (Create-Modus) ohne eine einzige Metrik auszufüllen / When der Weiter-Button gerendert wird / Then ist er aktiviert (`canAdvanceCurrent` für Step 3 = `true`).

**AC-8:** Given der Nutzer hat Idealwerte eingegeben (`idealRanges` nicht leer) / When `save()` oder `toggleEnabled()` aufgerufen wird / Then enthält `display_config` den Key `ideal_ranges` mit den aktuellen `state.idealRanges`-Werten; ein leeres `idealRanges`-Objekt erzeugt keinen `ideal_ranges`-Key in `display_config`.

**AC-9:** Given kein Aktivitätsprofil ist gesetzt (`state.activityProfile` ist null/undefined) / When Step 3 gerendert wird / Then wird die Metrik-Liste für das Profil `ALLGEMEIN` angezeigt (Fallback).

**AC-10:** Given eine Metrik mit `kind='range'` (z.B. `snow_depth_cm`, rangeMin=0, rangeMax=200) / When Step 3 gerendert wird / Then sind die Skala-Endpunkte `0` (unter dem Min-Input, `data-testid="compare-step3-scale-min-snow_depth_cm"`) und `200` (unter dem Max-Input, `data-testid="compare-step3-scale-max-snow_depth_cm"`) als Mono-Text sichtbar.

## Known Limitations

- **Notes-Feld fehlt:** Ein optionales Freitextfeld pro Metrik (z.B. „Erklärung warum dieser Bereich") ist nicht in Scope. Folge-Issue auf Wunsch des PO.
- **Keine Eingabe-Validierung Min ≤ Max:** Wenn der Nutzer `min > max` eingibt, wird kein Fehler angezeigt. Der Algorithmus in `/api/compare/run` verarbeitet solche Werte derzeit undefiniert — Validierung als Folge-Issue.
- **Keine mobilen Optimierungen:** Das Grid-Layout (`grid-cols-[12rem_1fr_1fr_auto]`) ist auf Desktop ausgerichtet. Mobile-Anpassungen sind nicht Scope von #441.
- **Steps 4–5 fehlen:** Wizard-Step 4 (Kanaleinstellungen) und Step 5 (Zusammenfassung) sind eigene Issues (#442, #443) und nicht in diesem Scope.
- **Backend reicht display_config opaque durch:** Keine serverseitige Validierung von `ideal_ranges`-Werten. Ungültige Werte (z.B. falsche Schlüssel) werden ohne Fehler gespeichert.

## Changelog

- 2026-05-29: Initial spec — Issue #441. Wizard Step 3 (Idealwerte): `compareMetricDefs.ts` als Shared Module, `Step3Idealwerte.svelte`, State-Erweiterung `idealRanges`, Profil-Wechsel-Confirm in Step 1, Edit-Modus-Vorladen. 7 Dateien (~305 LoC), rein Frontend, kein Backend-Change. Teil von Epic #438.
