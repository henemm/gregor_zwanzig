---
entity_id: issue_718_compare_editor_slice4_validierung
type: module
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [frontend, compare, editor, validation, epic-677]
---

# Compare-Editor Slice 4 — Validierungsmeldungen für Idealwerte (Issue #718)

## Approval

- [ ] Approved

## Purpose

Fügt Inline-Validierung in den Tab „Idealwerte" des Compare-Editors ein, damit defekte
Konfigurationen (min > max) sichtbar gemacht werden und den Wizard-Fortschritt blockieren.
Das Tab-System markiert „Idealwerte" derzeit als „done" sobald es besucht wurde — auch bei
strukturell ungültigen Ranges, die ausschließlich über den Edit-Modus per API-Load eingeschleust
werden können (da `RangeSlider.svelte` per Clamping min < max UI-seitig erzwingt).

> **Architektur-Hinweis:** Gelbe Warnstufen (unplausible Werte) entfallen vollständig — sie sind
> per Slider-UI unerreichbar. Einzige Fehlerklasse: `min > max` aus historischen Fehlkonfigurationen
> im Edit-Modus. Die neue `validateIdealRanges()`-Funktion ist rein prüfend; kein Auto-Fix.

## Source

- **Datei A (geändert):** `frontend/src/lib/components/compare/compareMetricDefs.ts`
- **Datei B (geändert):** `frontend/src/lib/components/compare/compareEditorLogic.ts`
- **Datei C (geändert):** `frontend/src/lib/components/compare/compareWizardState.svelte.ts`
- **Datei D (geändert):** `frontend/src/lib/components/compare/CompareEditor.svelte`
- **Datei E (geändert):** `frontend/src/lib/components/compare/steps/Step3Idealwerte.svelte`

> Schicht: **Frontend / User-UI** → `frontend/src/...` (SvelteKit, gregor20.henemm.com).
> Backend (Go-API, Python) ist nicht betroffen — die Validierung ist rein clientseitig.

## Estimated Scope

- **LoC:** ~60–90
- **Files:** 5 (alle geändert, keine neuen)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `compareMetricDefs.ts` | geändert | Neue `validateIdealRanges()` pure Funktion (einzige Logik-Quelle) |
| `compareEditorLogic.ts` | geändert | `idealsValid?: boolean` in `CompareEditorProgress`; `doneTabs()` Bedingung |
| `compareWizardState.svelte.ts` | geändert | Neuer Getter `canAdvanceStep3`; Einbindung in `canAdvanceCurrent` |
| `CompareEditor.svelte` | geändert | `$derived idealsValid`; Übergabe an `doneTabs()` |
| `Step3Idealwerte.svelte` | geändert | Inline-Fehlermeldung pro betroffener Metrik-Zeile |
| `RangeSlider.svelte` | reuse | Bestehende Slider-Komponente (unverändert) |
| `ALL_METRICS` / `MetricDef` | reuse | Metrik-Katalog, `kind`-Feld zur Unterscheidung range/enum |
| `IDEAL_DEFAULTS` | reuse | Typ-Struktur für `idealRanges`-Shape |

---

## Acceptance Criteria

**AC-1:** Inline-Fehlermeldung bei Min > Max
Given: Im Edit-Modus wurden API-geladene `idealRanges` mit `min > max` geladen (z.B. `temp_max_c: { min: 35, max: 15 }`) / When: Der Nutzer den Idealwerte-Tab öffnet / Then: Direkt unterhalb des Sliders der betroffenen Metrik erscheint eine rote Fehlermeldung mit `data-testid="compare-step3-error-{key}"`. Für nicht betroffene Metriken ist kein Fehler-Element im DOM vorhanden.

- Test: Playwright navigiert im Edit-Modus zu Idealwerte-Tab mit vorbereiteten defekten Ranges; `getByTestId('compare-step3-error-temp_max_c')` ist sichtbar, `getByTestId('compare-step3-error-snow_depth_cm')` existiert nicht.

**AC-2:** Weiter-Button im Wizard-Footer deaktiviert bei Fehlern
Given: Step 3 ist aktiv und mindestens ein aktiver `idealRange`-Eintrag hat `min > max` / When: Der Nutzer den Wizard-Footer betrachtet / Then: Der Weiter-Button (`data-testid="compare-wizard-next"` o.ä.) ist `disabled` (`canAdvanceStep3 === false`). Ein Klick löst keine Navigation aus.

- Test: Playwright versucht Klick auf Weiter-Button im Fehlerzustand; aktiver Tab bleibt Step 3 (keine Navigation zu Step 4).

**AC-3:** Tab „Idealwerte" gilt NICHT als done bei Fehlern
Given: `doneTabs()` wird mit `idealsVisited: true` und `idealsValid: false` aufgerufen / When: Die done-Menge berechnet wird / Then: `'idealwerte'` ist **nicht** in der zurückgegebenen Menge enthalten.

- Test: Unit-Test auf `doneTabs()` direkt: `{ idealsVisited: true, idealsValid: false }` → done enthält nicht `'idealwerte'`.

**AC-4:** Valide Konfiguration — kein Fehler, Tab done, Weiter möglich
Given: Alle aktiven Metriken haben `min <= max` (oder nur enum-Metriken, die keine min/max-Prüfung benötigen) / When: Der Nutzer den Idealwerte-Tab öffnet und die done-Berechnung läuft / Then: Kein `compare-step3-error-*`-Element ist im DOM sichtbar. `'idealwerte'` ist in der done-Menge enthalten. Der Weiter-Button ist nicht disabled.

- Test: Playwright öffnet Idealwerte-Tab mit valider Konfiguration; `$$('[data-testid^="compare-step3-error-"]')` gibt leeres Array zurück; Weiter-Klick navigiert zu Step 4.

**AC-5:** Rückwärtskompatibilität — `idealsValid: undefined` zählt als valid
Given: `doneTabs()` wird mit `idealsVisited: true` und `idealsValid` nicht übergeben (`undefined`) / When: Die done-Menge berechnet wird / Then: `'idealwerte'` ist in der Menge enthalten, da `undefined !== false`.

- Test: Unit-Test auf `doneTabs()`: `{ idealsVisited: true }` (kein `idealsValid`) → done enthält `'idealwerte'`.

---

## Implementation Details

### validateIdealRanges() in compareMetricDefs.ts (neu)

Pure Funktion ohne Seiteneffekte.

```typescript
export function validateIdealRanges(
  ranges: Record<string, { min?: number; max?: number; [k: string]: unknown }>,
  activeKeys: string[]
): { valid: boolean; invalidKeys: string[] } {
  const invalidKeys = activeKeys.filter(key => {
    const r = ranges[key];
    if (!r) return false;
    const min = typeof r.min === 'number' ? r.min : undefined;
    const max = typeof r.max === 'number' ? r.max : undefined;
    return min !== undefined && max !== undefined && min > max;
  });
  return { valid: invalidKeys.length === 0, invalidKeys };
}
```

Enum-Metriken (kein `min`/`max` im Range-Objekt) werden automatisch übersprungen —
die Bedingung `min !== undefined && max !== undefined` greift nicht.

### compareEditorLogic.ts — Interface + doneTabs()

```typescript
export interface CompareEditorProgress {
  // ... bestehende Felder ...
  idealsVisited?: boolean;
  idealsValid?: boolean;   // NEU: optional, undefined = rückwärtskompatibel
}

// doneTabs() — Bedingung für 'idealwerte':
// ALT: p.idealsVisited
// NEU: p.idealsVisited && (p.idealsValid !== false)
function doneTabs(p: CompareEditorProgress): Set<string> {
  const done = new Set<string>();
  // ... andere Tabs ...
  if (p.idealsVisited && p.idealsValid !== false) done.add('idealwerte');
  return done;
}
```

### compareWizardState.svelte.ts — canAdvanceStep3

```typescript
// Neuer Getter, aufgerufen von canAdvanceCurrent für case 3
get canAdvanceStep3(): boolean {
  return validateIdealRanges(this.idealRanges, this.activeMetricKeys).valid;
}

// canAdvanceCurrent erweitern:
canAdvanceCurrent(step: number): boolean {
  switch (step) {
    // ... bestehende cases ...
    case 3: return this.canAdvanceStep3;
    default: return true;
  }
}
```

### CompareEditor.svelte — $derived idealsValid

```typescript
// Abgeleitete Validation — reaktiv, kein manueller Aufruf nötig
const idealsValid = $derived(
  validateIdealRanges(wiz.idealRanges, wiz.activeMetricKeys).valid
);

// An doneTabs() übergeben (ergibt das neue dritte Argument):
$: done = doneTabs({ ..., idealsVisited: wiz.idealsVisited, idealsValid });
```

### Step3Idealwerte.svelte — Inline-Fehlermeldung

Für jede Metrik-Zeile mit `kind === 'range'` nach dem Slider-Block einfügen:

```svelte
{#if !validateIdealRanges(wiz.idealRanges, [metric.key]).valid}
  <p
    data-testid="compare-step3-error-{metric.key}"
    style="color: var(--g-danger); font-size: 11px; margin: 2px 0 0 0;"
  >
    Ungültig: Minimalwert ist größer als Maximalwert
  </p>
{/if}
```

Die Fehlermeldung erscheint direkt unterhalb des Sliders der betroffenen Metrik-Zeile.
Für enum-Metriken wird kein Fehler-Element gerendert (strukturell ausgeschlossen).

### Testid-Vertrag (additiv — bestehende Testids bleiben unverändert)

Neue Testids:
- `compare-step3-error-{key}` — Fehlermeldung unterhalb des Sliders für Metrik `key`

Alle bestehenden Testids aus `issue_452_step2_smart_import.test.ts` und
`issue_441_step3_idealwerte.test.ts` bleiben unverändert erhalten.

---

## Expected Behavior

- **Input:** `idealRanges: Record<string, {min?: number; max?: number}>`, `activeMetricKeys: string[]`
- **Output:** `{ valid: boolean; invalidKeys: string[] }` von `validateIdealRanges()`; visuell rote Fehlermeldung pro `invalidKey` in Step3Idealwerte; `'idealwerte'` fehlt in `doneTabs()` wenn `idealsValid === false`; `canAdvanceStep3 === false` blockiert Weiter-Button
- **Side effects:** keine — reine Validierungslogik ohne Schreibzugriff auf Store oder API

## Known Limitations

- **Kein Auto-Fix:** Defekte Ranges (min > max) werden angezeigt aber nicht automatisch korrigiert. Der Nutzer muss die Konfiguration über das Backend bereinigen (Edit-Modus, API-Aufruf) — direkte Korrektur per Slider ist per Design unmöglich (Slider clampt).
- **Edit-Modus ist einziger Eintrittspunkt:** Per UI kann kein defekter Zustand entstehen; die Fehlermeldung ist ausschließlich für historische Fehlkonfigurationen aus dem API-Load relevant.
- **Keine Warnstufe:** Werte außerhalb der MetricDef-Grenzen (aber valid min <= max) erzeugen keine Meldung — per Slider unerreichbar und kein Produktrisiko.

---

## Out-of-Scope / Folge-Issues

| Funktion | Status |
|---|---|
| Auto-Korrektur defekter Ranges | Out-of-Scope — kein API-Endpoint in Scope |
| Gelbe Warnstufe für Grenzwert-Überschreitung | Out-of-Scope — per Slider unerreichbar |
| Backend-Validierung (Go-API reject) | Out-of-Scope (Folge-Issue, defensiv) |

---

## Changelog

- 2026-06-10: Initiale Spec (Issue #718, Epic #677). Validierungsmeldungen für min > max in Tab „Idealwerte"; pure `validateIdealRanges()`-Funktion; `idealsValid`-Feld in `CompareEditorProgress`; rückwärtskompatibel via `undefined !== false`.
