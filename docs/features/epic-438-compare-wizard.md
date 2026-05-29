# Epic 438: Orts-Vergleich Wizard (Compare Subscription System)

**Status:** In Progress  
**Completion Target:** 2026-06-30  
**Related Specs:**
- `docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md` (Shell + Steps 1–2)
- `docs/specs/modules/issue_441_compare_wizard_step3_idealwerte.md` (Step 3 — Idealwerte)
- `docs/specs/modules/issue_442_...` (Step 4 — Layout, TBD)
- `docs/specs/modules/issue_443_...` (Step 5 — Versand, TBD)
- `docs/specs/modules/issue_455_compare_main_stage.md` (Compare-Hauptbühne Frontend)

**Child Issues:** #440, #441, #442, #443, #455 (planned)

---

## Overview

Epic #438 implementiert ein **5-Schritt-Wizard-System** zur Konfiguration von **Orts-Vergleichen** (Compare Subscriptions). Ein Orts-Vergleich ist eine automatisierte Briefing-Serie, die täglich mehrere geografische Standorte anhand personalisierter Idealwerte bewertet und einen Ranking-Report (E-Mail/SMS) versendet.

**Nutzerfall:** Ein Weitwanderer entscheidet sich VOR dem Urlaub für 3–5 Hütten/Skiorte und konfiguriert im Frontend, welche Wetterbedingungen "ideal" sind. Der Scheduler versendet dann täglich einen Report: "Hütte A: ☀ 18°C, perfekt | Hütte B: ☁ 8°C, zu kalt | …"

---

## Wizard Architecture

### 5-Step Flow

```
┌──────────────────────────────────────────┐
│ Step 1: Vergleich                        │  Name + Aktivitätsprofil
│ "Name & Profil"                          │  Profil bestimmt verfügbare Metriken
├──────────────────────────────────────────┤
│ Step 2: Orte                             │  2–5 Standorte auswählen
│ "Standorte auswählen"                    │  Aus bestehender Locations-Bibliothek
├──────────────────────────────────────────┤
│ Step 3: Idealwerte ✓                     │  Min/Max pro Metrik (profil-spezifisch)
│ "Metriken konfigurieren" (DONE #441)     │  Default-Vorschläge aus IDEAL_DEFAULTS
├──────────────────────────────────────────┤
│ Step 4: Layout                           │  Spalten-Reihenfolge, Formatierung
│ "Ausgabe gestalten" (TBD #442)           │  Schwellwert-Anzeige, Farbcodierung
├──────────────────────────────────────────┤
│ Step 5: Versand                          │  E-Mail/SMS, Zeitpunkt, Empfänger
│ "Briefings aktivieren" (TBD #443)        │  Cron-Ausdruck oder vordefinierte Zeit
└──────────────────────────────────────────┘
```

### State Management

**File:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts`

**State Felder (Runes-basiert):**

```typescript
// Identität
name: string = '';
description: string = '';
isEditMode: boolean = false;
subscriptionId: string | null = null;

// Step-Validierung
currentStep: number = 1;
completedSteps: Set<number> = new Set();

// Inhalte (aus Steps)
activityProfile: ActivityProfile | null = null;        // Step 1
selectedLocations: Location[] = [];                     // Step 2
idealRanges: Record<string, IdealRange> = {};           // Step 3 (DONE #441)
outputLayout: OutputLayout = { /* TBD #442 */ };        // Step 4
scheduleConfig: ScheduleConfig = { /* TBD #443 */ };    // Step 5

// Server-Inhalte
existingDisplayConfig: Record<string, any> = {};        // Nur im Edit-Mode
```

**Methoden:**

- `canAdvanceCurrent()` — Prüft Validierung für aktuellen Step
- `advance()` — Wechsel zum nächsten Step
- `goToStep(n)` — Sprung zu Step n (mit Validierungschain)
- `save()` — POST/PUT gegen `/api/subscriptions` mit allen Feldern
- `toggleEnabled()` — Enable/Disable der Subscription

### Component Tree

```
frontend/src/routes/compare/
├── +page.svelte (Create-Modus)
├── +page.server.ts (Server-Daten)
├── [id]/
│   └── edit/
│       ├── +page.svelte (Edit-Modus)
│       └── +page.server.ts (Subscription laden)
│
frontend/src/lib/components/compare/
├── CompareWizard.svelte (Shell mit Stepper)
├── compareWizardState.svelte.ts (State, Kontext)
├── compareMetricDefs.ts (DONE #441 — Metrik-Definitions + Idealwerte-Defaults)
├── CompareMatrix.svelte (Read-Only Matrix für Vergleich-Ausgabe)
├── steps/
│   ├── Step1Vergleich.svelte (DONE #440 — Name, Profil)
│   ├── Step2Orte.svelte (DONE #440 — Ort-Auswahl)
│   ├── Step3Idealwerte.svelte (DONE #441 — Min/Max-Eingaben)
│   ├── Step4Layout.svelte (TBD #442)
│   └── Step5Versand.svelte (TBD #443)
└── __tests__/
    ├── issue_440_*.test.ts
    ├── issue_441_step3_idealwerte.test.ts
    └── …
```

---

## Step 3: Idealwerte (Issue #441, COMPLETED)

**Status:** ✓ Implemented  
**Completion Date:** 2026-05-29

### Purpose

Der Nutzer definiert pro Metrik (abhängig vom Aktivitätsprofil in Step 1), welche Wertebereiche als "ideal" gelten. Diese Idealwerte werden vom Backend-Vergleichsalgorithmus verwendet, um Standorte zu bewerten.

### Architecture

**Metric Definition Module** (`compareMetricDefs.ts`)

```typescript
interface MetricDef {
  label: string;           // "Temperatur max"
  key: string;             // "temp_max_c"
  unit: string;            // "°C"
  decimals: number;        // 0
  higherIsBetter: boolean; // true/false
  kind: 'range' | 'enum';  // Input-Typ
  rangeMin?: number;       // 0 (für kind='range')
  rangeMax?: number;       // 45 (für kind='range')
  step?: number;           // 1 (für kind='range')
  enumValues?: string[];   // ['NONE', 'MED', 'HIGH'] (für kind='enum')
}

interface IdealRange {
  min?: number | null;
  max?: number | string | null; // string für Enum (z.B. 'NONE')
}

// Profil-spezifische Metrik-Listen
const PROFILE_METRICS_WITH_SCALES: Record<ProfileKey, MetricDef[]> = {
  WINTERSPORT: [temp, snow_depth, snow_new, wind_max, cloud_avg, ...],
  ALPINE_TOURING: [snow_new, visibility, wind_max],
  SUMMER_TREKKING: [precip_sum, thunder, wind_max, uv_index, visibility],
  ALLGEMEIN: [temp_max, wind_max, precip_sum, visibility]
};

// Default-Idealwerte pro Profil
const IDEAL_DEFAULTS: Record<ProfileKey, Record<string, IdealRange>> = {
  WINTERSPORT: {
    snow_depth_cm: { min: 30, max: 200 },
    snow_new_sum_cm: { min: 5, max: 50 },
    wind_max_kmh: { min: 0, max: 40 },
    cloud_avg_pct: { min: 0, max: 60 }
  },
  // … weitere Profile
};
```

**UI Layout** (`Step3Idealwerte.svelte`)

```
┌─────────────────────────────────────────┐
│ IDEALWERTE                              │  Eyebrow
│ Pro Aktivitätsprofil werden passende    │  Beschreibung
│ Metriken gezeigt.                       │
├─────────────────────────────────────────┤
│ [Label]  [Min Input]  [Max Input]  [Einheit]
│          [rangeMin]   [rangeMax]        │  For kind='range'
├─────────────────────────────────────────┤
│ [Label]           [Max Select]  [Einheit]
│                   [NONE MED HIGH]        │  For kind='enum' (e.g., thunder)
└─────────────────────────────────────────┘
```

**Sonderfall: Enum-Metriken** (z.B. `thunder_level_max`)

- Kein Min-Input, nur Max-Select mit vordefinierten Optionen
- Wert wird als String gespeichert (`"NONE"`, `"MED"`, `"HIGH"`)

**Profil-Wechsel** (in Step 1)

- Wenn der Nutzer das Aktivitätsprofil wechselt und bereits Idealwerte eingegeben hat, wird ein Confirm-Dialog angezeigt
- Bei Bestätigung: `state.idealRanges = {}` (Idealwerte werden zurückgesetzt, neue Defaults aus dem neuen Profil werden geladen)

**Edit-Modus**

- Beim Laden eines bestehenden Vergleichs werden gespeicherte `ideal_ranges` aus `display_config` in `state.idealRanges` vorgeladen
- Der `$effect` in Step 3 überschreibt vorgeladene Werte nicht

**Persistierung**

- Gespeichert in `display_config.ideal_ranges` (opaque `map[string]interface{}` im Go-Backend)
- API Endpoints: `GET /api/subscriptions/{id}`, `PUT /api/subscriptions/{id}`, `POST /api/subscriptions`
- Kein Backend-Schema-Change nötig

**Implementation Details:**

| Datei | Änderung | LoC |
|-------|----------|-----|
| `compareMetricDefs.ts` | Neu: MetricDef, IdealRange, PROFILE_METRICS_WITH_SCALES, IDEAL_DEFAULTS | ~60 |
| `Step3Idealwerte.svelte` | Neu: UI mit Range-Inputs + Enum-Select | ~120 |
| `compareWizardState.svelte.ts` | Erweiterung: idealRanges-Feld, save()-Update | ~25 |
| `CompareWizard.svelte` | Step 3 einbinden | ~5 |
| `Step1Vergleich.svelte` | Profil-Wechsel-Guard hinzufügen | ~10 |
| `+page.svelte` (edit) | ideal_ranges laden | ~5 |
| `issue_441_step3_idealwerte.test.ts` | Neu: 80 mock-freie Tests | ~80 |
| **Summe** | | **~305 LoC** |

**Acceptance Criteria (10 AC, alle erfüllt):**

- AC-1: Metriken pro Profil angezeigt
- AC-2: Range-Inputs für numerische Metriken
- AC-3: Enum-Select für `thunder_level_max`
- AC-4: Defaults aus IDEAL_DEFAULTS beim ersten Öffnen (Create)
- AC-5: Vorgeladene Werte im Edit-Modus nicht überschrieben
- AC-6: Profil-Wechsel-Confirm Dialog
- AC-7: Weiter-Button immer aktiviert (keine Pflicht-Eingabe)
- AC-8: Idealwerte in display_config.ideal_ranges persistiert
- AC-9: Fallback auf ALLGEMEIN wenn kein Profil
- AC-10: Skala-Endpunkte unter Inputs angezeigt

---

## Planned Steps (Future Issues)

### Step 4: Layout (Issue #442)

**Placeholder:** Spalten-Konfiguration, Anzeigeformat für Zahlenwerte, Farbschwellen

### Step 5: Versand (Issue #443)

**Placeholder:** Zeitplan (Cron oder vordefinierte Zeiten), Kanal-Auswahl (E-Mail/SMS), Empfänger

---

## Data Model

### Subscription (Backend)

```go
type Subscription struct {
  ID             string                 `json:"id"`
  UserID         string                 `json:"user_id"`
  Name           string                 `json:"name"`
  Description    string                 `json:"description"`
  Type           string                 `json:"type"` // "compare"
  Enabled        bool                   `json:"enabled"`
  
  Config         SubscriptionConfig     `json:"config"`
  DisplayConfig  map[string]interface{} `json:"display_config"` // ideal_ranges, layout, schedule
  
  CreatedAt      time.Time              `json:"created_at"`
  UpdatedAt      time.Time              `json:"updated_at"`
}

type SubscriptionConfig struct {
  ActivityProfile  string     `json:"activity_profile"`  // WINTERSPORT, ALPINE_TOURING, SUMMER_TREKKING, ALLGEMEIN
  LocationIDs      []string   `json:"location_ids"`       // 2–5 Ort-IDs
}

// display_config keys (from Step 3 onwards):
// {
//   "ideal_ranges": { "temp_max_c": { "min": 15, "max": 35 }, ... },
//   "output_layout": { /* Step 4 */ },
//   "schedule": { /* Step 5 */ }
// }
```

### Frontend Types

```typescript
interface CompareMetrics {
  temp_max_c: number;
  temp_min_c: number;
  wind_max_kmh: number;
  gust_max_kmh: number;
  precip_sum_mm: number;
  cloud_avg_pct: number;
  visibility_min_m: number;
  sunny_hours_h: number;
  uv_index_max: number;
  thunder_level_max: 'NONE' | 'MED' | 'HIGH';
  snow_depth_cm?: number;
  snow_new_sum_cm?: number;
}

type ActivityProfile = 'WINTERSPORT' | 'ALPINE_TOURING' | 'SUMMER_TREKKING' | 'ALLGEMEIN';

interface IdealRange {
  min?: number | null;
  max?: number | string | null;
}

interface CompareSubscription {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  
  activityProfile: ActivityProfile;
  selectedLocations: Location[];
  
  display_config: {
    ideal_ranges?: Record<string, IdealRange>;
    output_layout?: OutputLayout;
    schedule?: ScheduleConfig;
  };
  
  createdAt: Date;
  updatedAt: Date;
}
```

---

## Backend Integration

**API Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/subscriptions` | GET | List all compare subscriptions (filtered by user) |
| `POST /api/subscriptions` | POST | Create new subscription (Create-Wizard) |
| `GET /api/subscriptions/{id}` | GET | Load for edit |
| `PUT /api/subscriptions/{id}` | PUT | Save (all steps) |
| `DELETE /api/subscriptions/{id}` | DELETE | Delete subscription |
| `PATCH /api/subscriptions/{id}/enabled` | PATCH | Toggle enabled state |
| `POST /api/subscriptions/{id}/preview` | POST | Preview compare-Report (for validation) |

**Compare Algorithm** (Backend, TBD)

```
Input: [Location A, Location B, Location C], Idealwerte, today's forecast

For each location:
  1. Fetch forecast (24h)
  2. Aggregate metrics (temp_max, wind_max, etc.)
  3. Score gegen Idealwerte: -1 (zu schlecht), 0 (ok), +1 (ideal)
  4. Gewichte nach Profil anpassen

Output: CompareReport {
  [LocationA] → Score: +3/10, Metriken, Begründung
  [LocationB] → Score: +8/10, Metriken, Begründung
  [LocationC] → Score: +5/10, Metriken, Begründung
}
```

---

## Known Limitations

1. **Min ≤ Max Validierung:** Ungültige Eingaben (min > max) werden nicht im Frontend validiert. Folge-Issue für Validierung.

2. **Notes-Felder:** Kein optionales Freitextfeld pro Metrik zur Erklärung der Idealwerte. Folge-Issue auf Wunsch.

3. **Keine mobilen Optimierungen:** Das Grid-Layout in Step 3 ist auf Desktop ausgerichtet. Mobile Anpassungen in separater Epic.

4. **Backend opaque:** Der Go-Service reicht `display_config` unverändert durch — keine serverseitige Validierung von `ideal_ranges`. Ungültige Werte werden kommentarlos gespeichert.

5. **5-Step Linear:** Es gibt derzeit keine Möglichkeit, Steps zu überspringen. Folge-Issue für Non-Linear-Wizards.

---

## Testing

### Unit Tests

**File:** `frontend/src/lib/components/compare/__tests__/`

- `issue_440_compare_wizard_shell_step1_step2.test.ts` (~150 LoC) — Step 1–2 Validierung, State-Transitions
- `issue_441_step3_idealwerte.test.ts` (~80 LoC) — Metric-Rendering, Input-Events, Defaults, Profil-Wechsel

### E2E Tests (Planned)

- Complete wizard flow: Create → Steps 1–5 → Save
- Edit mode: Load existing → Modify → Save
- Cancel/Back navigation
- Validation errors

### Manual Testing (Staging)

Before promotion to production:

1. Create new comparison with all 5 steps
2. Edit existing comparison
3. Test Step 3 (Idealwerte) with all profile variants
4. Verify field defaults load correctly
5. Test profile switch with unsaved idealRanges

---

## Deployment Notes

### Post-Push Validation

After `git push origin main`:

1. Wait for auto-deploy to staging (~5 min)
2. Verify on staging:
   - `/compare` route loads
   - Wizard Steps 1–3 render correctly
   - Metric defaults load per profile
   - API calls to `/api/subscriptions` work
3. Run production deploy: `deploy-gregor-prod.sh`

### Known Drift Scenarios

None—pure frontend changes for Steps 1–3. Backend endpoints are opaque (no schema changes), so old data continues to work.

---

## Design System Dependencies

**Components used in Wizard:**

- `Btn` — Navigation buttons (Next, Back, Save, Cancel)
- `Select` / `input[type=number]` — Form inputs
- `Eyebrow` — Section labels
- `Stepper` — Multi-step navigation
- `GCard` / `Surface` — Card containers
- `Checkbox` — For toggles (enable/disable)

**Design Tokens:**

- `--g-ink`, `--g-ink-muted`, `--g-ink-faint` — Text colors
- `--g-paper`, `--g-card` — Backgrounds
- `--g-accent` — Interactive states

---

## Future Enhancements

1. **Step 4–5 Completion** — Layout customization, schedule configuration
2. **Compare Algorithm Backend** — Score calculation and ranking
3. **Preview Endpoint** — Sample comparison output before saving
4. **Non-Linear Wizard** — Skip steps conditionally
5. **Mobile Optimization** — Responsive grid for small screens
6. **Batch Editing** — Modify multiple subscriptions at once
7. **Template Library** — Save/reuse wizard profiles as templates
8. **Metric Sorting** — Drag-to-reorder metrics in output

---

## Changelog

| Date | Change |
|------|--------|
| 2026-05-29 | Compare-Hauptbühne Frontend implemented: `/compare` route rebuilt from 49-line subscription list to full 3-column interactive layout (LocationsRail \| CompareMatrix/Banner/HourlyMatrix \| AutoReportsOverview), 156 net LoC. Issue #455 ✓ |
| 2026-05-29 | Step 3 (Idealwerte) implemented: compareMetricDefs.ts, Step3Idealwerte.svelte, ~305 LoC, 10 AC fulfilled. Issue #441 ✓ |
| 2026-05-27 | Wizard shell + Steps 1–2 implemented: CompareWizard.svelte, Step1Vergleich.svelte, Step2Orte.svelte, State management. Issue #440 ✓ |
| 2026-05-?? | Steps 4–5 planned (Issues #442, #443) |
