---
entity_id: issue_297_alert_beides_mode
type: module
created: 2026-05-21
updated: 2026-05-22
status: implemented
version: "1.0"
issue: 297
tags: [alert-rules, frontend, mode-both, pair-id, alertrulerow, modecard, expandrules, issue-297]
---

# Issue #297 — Alert-Modus "Beides": Separate Threshold-Felder + Paar-Markierung

## Approval

- [ ] Approved

## Purpose

Wenn der User im `AlertRulesEditor` den Modus "Beides" wählt, zeigt die UI bisher nur **ein** Threshold-Feld — semantisch falsch, weil Absolut-Schwelle und Δ-Schwelle unterschiedliche Einheiten und Bedeutungen haben. Dieses Feature trennt die beiden Felder sauber: mode='both' öffnet zwei separate Eingaben (Absolut-Schwelle + Δ-Schwelle + Zeitfenster-Select), die erzeugten Rules erhalten eine gemeinsame `pair_id`, und der List-View markiert die zweite Paar-Regel visuell — damit der User beide Regeln als zusammengehörend erkennt. Daneben bekommt `ModeCard` ein Feld-Anzahl-Badge, das auf einen Blick zeigt, wie viele Eingaben ein Modus erzeugt.

## Source

- **MODIFY:** `frontend/src/lib/types.ts` — `AlertRule`-Interface um `pair_id?: string` und `delta_window?: string` erweitern
- **MODIFY:** `internal/model/trip.go` — `AlertRule`-Struct um `PairID *string` und `DeltaWindow *string` (omitempty) erweitern
- **MODIFY:** `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` — `expandRules()`-Signatur mit separaten `absThreshold`/`deltaThreshold`/`deltaWindow`-Parametern
- **MODIFY:** `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` — 6 bestehende Aufrufe anpassen + 4 neue Tests
- **MODIFY:** `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` — 3 neue State-Variablen, erweitertes `saveEdit()`, bedingtes Rendering für zwei Threshold-Felder bei mode='both'
- **MODIFY:** `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` — Feld-Anzahl-Badge ('1 Feld' / '2 Felder' / '3 Felder')
- **MODIFY:** `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` — Paar-Markierung im List-View via `pair_id`-Gruppierung, `pairFollower`-Prop an `AlertRuleRow`
- **MODIFY:** `frontend/e2e/alert-rules-editor.spec.ts` — 4 neue E2E-Tests für mode='both'

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertRule` | TS-Interface (`frontend/src/lib/types.ts`) | Datenmodell; wird um `pair_id?: string` und `delta_window?: string` erweitert |
| `AlertRuleKind` | TS-Type (`frontend/src/lib/types.ts`) | `'absolute' \| 'delta'` — bleibt unverändert; kein neuer 'both'-Wert im Datenmodell |
| `AlertRuleMode` | TS-Type (`alertRuleDefaults.ts`) | `'absolute' \| 'delta' \| 'both'` — UI-interner Typ, wird nicht persistiert |
| `DELTA_ONLY_METRICS` | TS-Konstante (`alertRuleDefaults.ts`) | Guard-Liste (`temperature_change`, `wind_change`, `precipitation_change`); bei mode='both' + delta-only → nur delta-Rule |
| `expandRules()` | Funktion (`alertRuleDefaults.ts`) | Wird mit neuer Signatur versehen; erzeugt 1–2 Rules inkl. `pair_id` und `delta_window` |
| `AlertRuleRow.svelte` | Svelte-Komponente | Bekommt neue State-Variablen und `pairFollower`-Prop; rendert zwei Felder bei mode='both' |
| `AlertRulesEditor.svelte` | Svelte-Komponente | Steuert Paar-Markierung via `pair_id`-Vergleich zwischen benachbarten Rules |
| `ModeCard.svelte` | Svelte-Komponente | Erhält `badge`-Prop; zeigt Anzahl der Eingabefelder pro Modus |
| `AlertRule` (Go) | Struct (`internal/model/trip.go`) | Backend-Modell; wird um `PairID *string` und `DeltaWindow *string` erweitert (omitempty) |
| `crypto.randomUUID()` | Browser-API | Erzeugt gemeinsame `pair_id` für beide Rules bei mode='both' |
| Issue #179 (Modus-Toggle) | Upstream-Feature | Etabliert ModeCard, `AlertRuleMode`, `expandRules()` und `onSave`-Signatur — Voraussetzung für dieses Issue |

## Implementation Details

### 1. Datenmodell erweitern

**`frontend/src/lib/types.ts`:**
```typescript
export interface AlertRule {
  id: string;
  kind: AlertRuleKind;
  metric: AlertMetric;
  threshold: number;
  unit: string;
  severity: AlertSeverity;
  enabled: boolean;
  pair_id?: string;      // NEU: gemeinsame ID für Absolut+Delta-Paare aus mode='both'
  delta_window?: string; // NEU: Zeitfenster für delta-Rules ('1h' | '3h' | '6h' | '12h' | '24h')
}
```

**`internal/model/trip.go`:**
```go
type AlertRule struct {
    ID          string   `json:"id"`
    Kind        string   `json:"kind"`
    Metric      string   `json:"metric"`
    Threshold   float64  `json:"threshold"`
    Unit        string   `json:"unit"`
    Severity    string   `json:"severity"`
    Enabled     bool     `json:"enabled"`
    PairID      *string  `json:"pair_id,omitempty"`      // NEU
    DeltaWindow *string  `json:"delta_window,omitempty"` // NEU
}
```

Keine Datenmigration notwendig — optionale Felder mit `omitempty`; bestehende Rules ohne diese Felder bleiben gültig.

### 2. `expandRules()` — neue Signatur

```typescript
// ALT:
expandRules(rule: AlertRule, mode: AlertRuleMode): AlertRule[]

// NEU:
expandRules(
  base: AlertRule,
  mode: AlertRuleMode,
  absThreshold: number,
  deltaThreshold: number,
  deltaWindow: string
): AlertRule[]
```

Verhalten je Modus:

- **mode='absolute':** Eine Rule zurückgeben — `kind='absolute'`, `threshold=absThreshold`. `delta_window` und `pair_id` werden nicht gesetzt.
- **mode='delta':** Eine Rule zurückgeben — `kind='delta'`, `threshold=deltaThreshold`, `delta_window=deltaWindow`. `pair_id` nicht gesetzt.
- **mode='both':**
  - `DELTA_ONLY_METRICS`-Guard zuerst prüfen: wenn `base.metric` in der Liste (`temperature_change`, `wind_change`, `precipitation_change`) → wie mode='delta' behandeln, nur eine delta-Rule zurückgeben.
  - Sonst: `const pairId = crypto.randomUUID()` — zwei Rules zurückgeben:
    - Rule 1: `{ ...base, id: base.id, kind: 'absolute', threshold: absThreshold, pair_id: pairId }` (kein `delta_window`)
    - Rule 2: `{ ...base, id: crypto.randomUUID(), kind: 'delta', threshold: deltaThreshold, delta_window: deltaWindow, pair_id: pairId }`

### 3. `AlertRuleRow.svelte` — neue State-Variablen und Rendering

**Neue State-Variablen:**
```typescript
let draftAbsThreshold   = $state<number>(50);   // für mode='absolute' oder 'both'
let draftDeltaThreshold = $state<number>(20);   // für mode='delta' oder 'both'
let draftDeltaWindow    = $state<string>('6h'); // für mode='delta' oder 'both'
```

**`startEdit()` — Initialisierungslogik:**
```typescript
function startEdit() {
  draft = { ...rule };
  if (rule.pair_id) {
    // Diese Rule gehört zu einem Paar — aus 'both' entstanden
    editMode = 'both';
    if (rule.kind === 'absolute') {
      draftAbsThreshold   = rule.threshold;
      draftDeltaThreshold = 20; // Partner-Wert nicht zugänglich — Default
    } else {
      draftDeltaThreshold = rule.threshold;
      draftDeltaWindow    = rule.delta_window ?? '6h';
      draftAbsThreshold   = 50; // Partner-Wert nicht zugänglich — Default
    }
  } else {
    editMode = rule.kind; // 'absolute' oder 'delta'
    if (rule.kind === 'absolute') {
      draftAbsThreshold = rule.threshold;
    } else {
      draftDeltaThreshold = rule.threshold;
      draftDeltaWindow    = rule.delta_window ?? '6h';
    }
  }
  editing = true;
}
```

**`saveEdit()` — ruft `expandRules()` mit neuer Signatur:**
```typescript
function saveEdit() {
  const rules = expandRules(
    { ...draft, unit: ALERT_METRIC_LABELS[draft.metric]?.unit ?? draft.unit },
    editMode,
    draftAbsThreshold,
    draftDeltaThreshold,
    draftDeltaWindow
  );
  onSave(rules);
  editing = false;
}
```

**Bedingtes Rendering der Threshold-Felder im Edit-Modus:**
```svelte
{#if editMode === 'absolute'}
  <input type="number" bind:value={draftAbsThreshold}
         data-testid="alert-rule-threshold" />

{:else if editMode === 'delta'}
  <input type="number" bind:value={draftDeltaThreshold}
         data-testid="alert-rule-threshold" />
  <select bind:value={draftDeltaWindow}
          data-testid="alert-rule-delta-window">
    <option value="1h">1 Stunde</option>
    <option value="3h">3 Stunden</option>
    <option value="6h">6 Stunden</option>
    <option value="12h">12 Stunden</option>
    <option value="24h">24 Stunden</option>
  </select>

{:else if editMode === 'both'}
  <input type="number" bind:value={draftAbsThreshold}
         data-testid="alert-rule-threshold-abs" />
  <input type="number" bind:value={draftDeltaThreshold}
         data-testid="alert-rule-threshold-delta" />
  <select bind:value={draftDeltaWindow}
          data-testid="alert-rule-delta-window">
    <!-- selbe Optionen wie delta -->
  </select>
{/if}
```

**Speichern-Button-Label:**
```svelte
<button onclick={saveEdit} data-testid="alert-rule-save">
  {editMode === 'both' ? 'Beide Regeln speichern' : 'Speichern'}
</button>
```

**`pairFollower`-Prop (neu):**
```typescript
let { rule, onSave, onDelete, pairFollower = false }:
  { rule: AlertRule; onSave: (rules: AlertRule[]) => void; onDelete: () => void; pairFollower?: boolean }
  = $props();
```

Bei `pairFollower=true`: vertikale Linie links (`border-left: 2px solid var(--g-accent)`) + Caption "paar" unter dem Metriklabel. Element mit `data-testid="pair-indicator"`.

### 4. `ModeCard.svelte` — Feld-Anzahl-Badge

```typescript
const COPY: Record<AlertRuleMode, { eyebrow: string; title: string; desc: string; example: string; badge: string }> = {
  absolute: { ..., badge: '1 Feld' },
  delta:    { ..., badge: '2 Felder' },  // Schwelle + Zeitfenster
  both:     { ..., badge: '3 Felder' }   // AbsSchwelle + ΔSchwelle + Zeitfenster
};
```

Badge wird in der Card als `<span class="field-count-badge">{COPY[mode].badge}</span>` gerendert. `data-testid="mode-card-badge-{mode}"`.

### 5. `AlertRulesEditor.svelte` — Paar-Markierung im List-View

```svelte
{#each rules as rule, i (rule.id)}
  {@const isPairFollower = !!(rule.pair_id && rules[i - 1]?.pair_id === rule.pair_id)}
  <li>
    <AlertRuleRow
      {rule}
      onSave={(updated) => updateRules(i, updated)}
      onDelete={() => deleteRule(i)}
      pairFollower={isPairFollower}
    />
  </li>
{/each}
```

Logik: `isPairFollower` ist `true` wenn die aktuelle Rule eine `pair_id` hat UND die vorherige Rule dieselbe `pair_id` trägt.

### 6. `alertRuleDefaults.test.ts` — Tests anpassen

6 bestehende Testaufrufe auf neue Signatur `expandRules(base, mode, absThreshold, deltaThreshold, deltaWindow)` migrieren. Zusätzlich 4 neue Tests:

1. `expandRules` mit mode='both' + normaler Metrik → 2 Rules mit gleicher `pair_id`, erste `kind='absolute'`/`threshold=absThreshold`, zweite `kind='delta'`/`threshold=deltaThreshold`/`delta_window=deltaWindow`.
2. `expandRules` mit mode='both' + delta-only Metrik → 1 Rule mit `kind='delta'` (DELTA_ONLY_METRICS-Guard).
3. `expandRules` mit mode='absolute' → 1 Rule mit `kind='absolute'`, kein `pair_id`, kein `delta_window`.
4. `expandRules` mit mode='delta' → 1 Rule mit `kind='delta'`, `delta_window` aus Parameter, kein `pair_id`.

### 7. `frontend/e2e/alert-rules-editor.spec.ts` — 4 neue E2E-Tests

1. mode='both' zeigt `alert-rule-threshold-abs` + `alert-rule-threshold-delta` + `alert-rule-delta-window`.
2. Speichern-Button bei mode='both' hat Label "Beide Regeln speichern".
3. Nach Speichern mit mode='both' erscheinen zwei Zeilen im List-View; zweite trägt `data-testid="pair-indicator"`.
4. ModeCard für 'both' zeigt Badge `data-testid="mode-card-badge-both"` mit Text "3 Felder".

## Expected Behavior

- **Input:** User öffnet Edit-Modus einer `AlertRule`, wählt ModeCard "Beides", füllt Absolut-Schwelle, Δ-Schwelle und Zeitfenster aus, klickt "Beide Regeln speichern".
- **Output:**
  - Zwei neue `AlertRule`-Einträge im `rules`-Array: erste mit `kind='absolute'`, zweite mit `kind='delta'` und `delta_window`; beide mit gleicher `pair_id` (UUID).
  - List-View zeigt zweite Paar-Regel mit `pair-indicator` (vertikale Linie + Caption "paar").
  - mode='absolute': ein Threshold-Feld (`data-testid="alert-rule-threshold"`), Speichern-Button "Speichern".
  - mode='delta': Threshold-Feld (`data-testid="alert-rule-threshold"`) + Zeitfenster-Select (`data-testid="alert-rule-delta-window"`), Speichern-Button "Speichern".
  - mode='both': `alert-rule-threshold-abs` + `alert-rule-threshold-delta` + `alert-rule-delta-window`, Speichern-Button "Beide Regeln speichern".
- **Side effects:**
  - Backend speichert `pair_id` und `delta_window` als optionale Felder in `alert_rules` (Go-Handler ist Pass-through).
  - Bestehende Rules ohne `pair_id`/`delta_window` bleiben unverändert dargestellt.
  - ModeCard-Badge zeigt Feldanzahl ('1 Feld' / '2 Felder' / '3 Felder') für alle drei Modi sichtbar.

## Acceptance Criteria

- **AC-1:** Given User öffnet Edit-Modus einer Rule und wählt mode='absolute' / When der Edit-Modus gerendert wird / Then ist genau ein Threshold-Feld mit `data-testid="alert-rule-threshold"` sichtbar; kein `alert-rule-threshold-abs`, kein `alert-rule-threshold-delta`, kein `alert-rule-delta-window`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given User wählt mode='delta' / When der Edit-Modus gerendert wird / Then ist ein Threshold-Feld mit `data-testid="alert-rule-threshold"` und ein Zeitfenster-Select mit `data-testid="alert-rule-delta-window"` sichtbar.
  - Test: (populated after /tdd-red)

- **AC-3:** Given User wählt mode='both' / When der Edit-Modus gerendert wird / Then sind drei Felder sichtbar: `alert-rule-threshold-abs`, `alert-rule-threshold-delta` und `alert-rule-delta-window`; kein `alert-rule-threshold` (ohne Suffix).
  - Test: (populated after /tdd-red)

- **AC-4:** Given User öffnet eine beliebige ModeCard / When die Card gerendert wird / Then trägt sie ein Badge-Element mit `data-testid="mode-card-badge-{mode}"`: 'absolute' → "1 Feld", 'delta' → "2 Felder", 'both' → "3 Felder".
  - Test: (populated after /tdd-red)

- **AC-5:** Given `expandRules(base, 'both', 40, 15, '3h')` mit einer nicht-delta-only Metrik (`wind_gust`) / When die Funktion aufgerufen wird / Then gibt sie genau zwei Rules zurück, beide mit derselben `pair_id`; erste hat `kind='absolute'` und `threshold=40`; zweite hat `kind='delta'`, `threshold=15` und `delta_window='3h'`.
  - Test: (populated after /tdd-red)

- **AC-6:** Given `expandRules(base, 'both', 40, 15, '3h')` mit einer delta-only Metrik (`temperature_change`) / When die Funktion aufgerufen wird / Then gibt sie genau eine Rule zurück mit `kind='delta'` und `threshold=15`; kein `pair_id` gesetzt.
  - Test: (populated after /tdd-red)

- **AC-7:** Given `expandRules(base, 'both', 40, 15, '3h')` mit nicht-delta-only Metrik / When geprüft wird / Then trägt die delta-Rule `delta_window='3h'`; die absolute-Rule hat kein `delta_window`.
  - Test: (populated after /tdd-red)

- **AC-8:** Given DELTA_ONLY_METRICS-Guard greift bei mode='both' (delta-only Metrik) / When `expandRules` aufgerufen wird / Then wird nur eine delta-Rule erzeugt, ohne `pair_id`.
  - Test: (populated after /tdd-red)

- **AC-9:** Given User befindet sich im Edit-Modus mit mode='both' / When der Speichern-Button sichtbar ist / Then trägt er das Label "Beide Regeln speichern"; bei mode='absolute' oder mode='delta' lautet er "Speichern".
  - Test: (populated after /tdd-red)

- **AC-10:** Given User hat mit mode='both' zwei Rules gespeichert (gleiche `pair_id`) / When der List-View der Rules gerendert wird / Then zeigt die zweite Paar-Regel ein Element mit `data-testid="pair-indicator"` (vertikale Linie + Caption "paar"); die erste Paar-Regel und alle anderen Rules haben kein `pair-indicator`-Element.
  - Test: (populated after /tdd-red)

- **AC-11:** Given ein Trip hat eine Rule mit `pair_id` und `delta_window` / When der PUT-Request an `/api/trips/{id}` gesendet wird und der Trip neu geladen wird / Then enthält `alert_rules` die Rule mit unverändertem `pair_id` und `delta_window` (Backend persistiert Pass-through).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Paar-Bearbeitung unvollständig:** Wenn der User die Delta-Rule eines bestehenden Paares einzeln bearbeitet, initialisiert `startEdit()` den `draftAbsThreshold` mit Default-Wert 50 — der tatsächliche Absolut-Schwellwert der Partner-Rule ist ohne Lookup des gesamten `rules`-Arrays nicht zugänglich. Vollständige symmetrische Paar-Bearbeitung (beide Seiten synchron editieren) ist Out of Scope für dieses Issue.
- **Pair-ID nach Trennung:** Wenn der User eine der beiden Paar-Rules löscht, bleibt die verbleibende Rule mit ihrer `pair_id`. Der `pair-indicator` erscheint dann nicht mehr (kein Nachbar mit gleicher `pair_id`), aber das Feld ist technisch noch gesetzt.
- **delta_window im Absolut-Modus:** Das Feld `delta_window` wird nur für `kind='delta'`-Rules gesetzt. Bei mode='absolute' wird kein `delta_window` geschrieben, auch wenn `draftDeltaWindow` intern einen Wert hat.

## Files to Change

| # | Datei | Schicht | Aktion | LoC (netto) |
|---|-------|---------|--------|-------------|
| 1 | `frontend/src/lib/types.ts` | Frontend | MODIFY — `pair_id?` + `delta_window?` in `AlertRule` | ~4 |
| 2 | `internal/model/trip.go` | Go-API | MODIFY — `PairID` + `DeltaWindow` in `AlertRule`-Struct | ~4 |
| 3 | `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | Frontend | MODIFY — `expandRules()` neue Signatur, pair_id-Logik | ~25 |
| 4 | `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` | Frontend/Test | MODIFY — 6 Aufrufe anpassen + 4 neue Tests | ~40 |
| 5 | `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | Frontend | MODIFY — 3 State-Variablen, `startEdit()`, Rendering, `pairFollower`-Prop | ~60 |
| 6 | `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | Frontend | MODIFY — Badge-Feld in COPY, Badge-Element im Template | ~10 |
| 7 | `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | Frontend | MODIFY — `isPairFollower`-Logik, `pairFollower`-Prop an `AlertRuleRow` | ~10 |
| 8 | `frontend/e2e/alert-rules-editor.spec.ts` | Frontend/E2E | MODIFY — 4 neue Tests für mode='both' | ~40 |

**Gesamt:** ~193 LoC netto, 8 Dateien (alle bestehend geändert)

## Changelog

- 2026-05-21: Initial spec für Issue #297 — separate Threshold-Felder bei mode='both', ModeCard-Badge, `expandRules()`-Signaturerweiterung mit `absThreshold`/`deltaThreshold`/`deltaWindow`, `pair_id`-Semantik für Paar-Markierung im List-View, Known Limitation für unvollständige Paar-Bearbeitung dokumentiert, 11 Acceptance Criteria im AC-N Given/When/Then-Format.
- 2026-05-22: Implementiert — Adversary-Fixes durchgeführt: expandRules() strippt pair_id/delta_window korrekt via Destructuring in allen 4 Pfaden (F001/F004/AC-7). thunder_level zu DELTA_ONLY_METRICS hinzugefügt (diskrete Ordinal-Metrik). 16 Unit-Tests für expandRules() Logik.
