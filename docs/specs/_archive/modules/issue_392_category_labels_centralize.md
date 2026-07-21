---
entity_id: issue_392_category_labels_centralize
type: module
created: 2026-05-27
updated: 2026-05-27
status: approved
version: "1.0"
tags: [refactoring, frontend, metricsEditor, WeatherMetricsTab, WeatherConfigDialog, deduplication, issue-392]
---

<!-- Issue #392 — Phase 2 (Folge): organisms.jsx ↔ #331/#364-Editor abgleichen, dann /metrics-editor migrieren -->

# Issue #392 — Refactoring: CATEGORY_LABELS/CATEGORY_ORDER in metricsEditor.ts zentralisieren

## Approval

- [x] Approved

## Zweck

`CATEGORY_LABELS` und `CATEGORY_ORDER` sind aktuell dreifach im Frontend definiert: einmal in `WeatherMetricsTab.svelte`, einmal in `WeatherConfigDialog.svelte` — und letztere weicht beim `winter`-Label ab (`'Winter/Schnee'` ohne Leerzeichen statt `'Winter / Schnee'`). Das Refactoring verschiebt beide Konstanten sowie `INDICATOR_MAP` und `indicatorCapable` als `export const` bzw. `export function` in `metricsEditor.ts`, wo `CATEGORY_ORDER` bereits definiert ist, und entfernt alle Inline-Definitionen aus den Komponenten. Es gibt keine Logik-Änderung — ausschliesslich Quell-Konsolidierung und Behebung der Label-Divergenz.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/lib/components/trip-detail/metricsEditor.ts` — `CATEGORY_LABELS` als `export const` nach `CATEGORY_ORDER` (Zeile 53) einfügen
- `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` — Inline-Definitionen von `CATEGORY_LABELS`, `CATEGORY_ORDER`, `INDICATOR_MAP`, `indicatorCapable` entfernen; Import aus `metricsEditor.ts` um diese vier Namen erweitern
- `frontend/src/lib/components/WeatherConfigDialog.svelte` — Inline-Definitionen von `CATEGORY_LABELS`, `CATEGORY_ORDER` entfernen; neuen Import aus `$lib/components/trip-detail/metricsEditor.ts` hinzufügen

> **Schicht-Hinweis:** Ausschliesslich Frontend-Schicht (`frontend/src/`). Kein Go-API-, kein Python-Backend-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | TypeScript-Modul | Single Source of Truth für Metriken-Logik; enthält bereits `CATEGORY_ORDER`, `INDICATOR_MAP`, `indicatorCapable`, `autoAssign`, `move`, `reorder`, `buildWeatherConfigMetrics` |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Svelte-Komponente | Haupteditor für Wetter-Metriken im Trip-Detail; importiert aus `metricsEditor.ts`; gibt `CATEGORY_LABELS` als Prop `categoryLabels` an `BucketSectionOff` weiter |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Svelte-Komponente | Dialog zur Wetter-Konfiguration; verwendete bisher eigene Inline-`CATEGORY_LABELS` mit abweichendem `winter`-Label |
| `frontend/src/lib/components/trip-detail/BucketSectionOff.svelte` | Svelte-Komponente (read-only) | Empfängt `categoryLabels` als Prop — kein Änderungsbedarf |
| `frontend/src/lib/components/trip-detail/TablePreview.svelte` | Svelte-Komponente (read-only) | Empfängt `categoryOrder` und `indicatorCapable` als Props — kein Änderungsbedarf |
| `frontend/src/lib/components/trip-detail/BucketSection.svelte` | Svelte-Komponente (read-only) | Empfängt `indicatorCapable` als Prop — kein Änderungsbedarf |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | Svelte-Komponente (read-only) | Empfängt `indicatorCapable` als Prop — kein Änderungsbedarf |

## Implementation Details

### Schritt 1 — `metricsEditor.ts`: CATEGORY_LABELS exportieren

Direkt nach der bestehenden `CATEGORY_ORDER`-Definition (Zeile 53) einfügen:

```typescript
export const CATEGORY_LABELS: Record<string, string> = {
  temperature: 'Temperatur',
  wind: 'Wind',
  precipitation: 'Niederschlag',
  atmosphere: 'Atmosphäre',
  winter: 'Winter / Schnee',
};
```

`CATEGORY_ORDER`, `INDICATOR_MAP` und `indicatorCapable` sind bereits in dieser Datei definiert — prüfen ob sie bereits als `export` markiert sind; falls nicht, `export` voranstellen.

### Schritt 2 — `WeatherMetricsTab.svelte`: Inline-Definitionen entfernen

Folgende Blöcke aus dem `<script>`-Bereich entfernen (aktuell Zeilen 35–61):

- `const CATEGORY_LABELS: Record<string, string> = { ... }` (7 Zeilen)
- `const CATEGORY_ORDER = [...]` (1 Zeile, falls inline)
- `const INDICATOR_MAP: Record<string, string> = { ... }` (14 Zeilen)
- `function indicatorCapable(id: string): boolean { ... }` (3 Zeilen)

Bestehenden Import aus `metricsEditor.ts` (aktuell Zeile 20–23) um die vier entfernten Namen erweitern:

```typescript
import {
  autoAssign, move, reorder, buildWeatherConfigMetrics,
  CATEGORY_LABELS, CATEGORY_ORDER, INDICATOR_MAP, indicatorCapable,
  type Buckets, type MetricEntry, type MetricCatalog,
} from './metricsEditor.ts';
```

### Schritt 3 — `WeatherConfigDialog.svelte`: Inline-Definitionen entfernen

Folgende Blöcke aus dem `<script>`-Bereich entfernen (aktuell Zeilen 32–40):

- `const CATEGORY_LABELS: Record<string, string> = { ... }` (7 Zeilen, mit `winter: 'Winter/Schnee'` ohne Leerzeichen — bewusst entfernen, da abweichend)
- `const CATEGORY_ORDER = [...]` (1 Zeile)

Neuen Import nach den bestehenden Imports (nach Zeile 8) hinzufügen:

```typescript
import { CATEGORY_LABELS, CATEGORY_ORDER } from '$lib/components/trip-detail/metricsEditor.ts';
```

**Nebeneffekt:** `winter`-Label vereinheitlicht sich auf `'Winter / Schnee'` (mit Leerzeichen um den Slash) — war vorher `'Winter/Schnee'` in `WeatherConfigDialog.svelte`.

### LoC-Budget

| Datei | Δ LoC |
|-------|--------|
| `metricsEditor.ts` | +6 (CATEGORY_LABELS-Block) |
| `WeatherMetricsTab.svelte` | −25 (Inline-Defs) + 4 (Import-Erweiterung) = −21 |
| `WeatherConfigDialog.svelte` | −8 (Inline-Defs) + 1 (Import) = −7 |
| **Netto** | **−22 LoC (innerhalb 250-LoC-Limit)** |

## Expected Behavior

- **Input:** Keine Verhaltensänderung für den Nutzer. WeatherMetricsTab und WeatherConfigDialog rendern identisch wie zuvor, mit dem einzigen Unterschied dass `WeatherConfigDialog` den `winter`-Kategorienamen jetzt als `'Winter / Schnee'` (statt `'Winter/Schnee'`) anzeigt.
- **Output:** `svelte-check` läuft ohne Typfehler durch; alle bestehenden Frontend-Tests bleiben grün.
- **Side effects:** `CATEGORY_LABELS` ist nun aus `metricsEditor.ts` importierbar für zukünftige Komponenten — kein neues Verhalten, nur neue Exportierbarkeit.

## Acceptance Criteria

- **AC-1:** Given `metricsEditor.ts` wird importiert / When `import { CATEGORY_LABELS } from './metricsEditor'` ausgeführt / Then wird ein Objekt mit genau 5 Schlüsseln (`temperature`, `wind`, `precipitation`, `atmosphere`, `winter`) zurückgegeben, wobei `CATEGORY_LABELS['winter'] === 'Winter / Schnee'` (mit Leerzeichen um den Slash)
  - Test: (populated after /4-tdd-red)

- **AC-2:** Given `WeatherMetricsTab.svelte` / When die Datei analysiert wird / Then sind keine lokalen Definitionen `const CATEGORY_LABELS`, `const CATEGORY_ORDER`, `const INDICATOR_MAP`, `function indicatorCapable` in der Datei vorhanden; alle vier Namen kommen ausschliesslich aus dem `metricsEditor.ts`-Import
  - Test: (populated after /4-tdd-red)

- **AC-3:** Given `WeatherConfigDialog.svelte` / When die Datei analysiert wird / Then sind keine lokalen Definitionen `const CATEGORY_LABELS`, `const CATEGORY_ORDER` in der Datei vorhanden; beide Namen kommen ausschliesslich aus dem `metricsEditor.ts`-Import
  - Test: (populated after /4-tdd-red)

- **AC-4:** Given beide Komponenten verwenden `CATEGORY_LABELS` aus `metricsEditor.ts` / When `CATEGORY_LABELS['winter']` ausgelesen wird / Then ist der Wert in beiden Kontexten identisch `'Winter / Schnee'` (Leerzeichen um den Slash, kein Drift mehr zwischen den Komponenten)
  - Test: (populated after /4-tdd-red)

- **AC-5:** Given `WeatherMetricsTab` rendert `BucketSectionOff` mit `categoryLabels={CATEGORY_LABELS}` / When die Komponente gerendert wird / Then zeigt `BucketSectionOff` die korrekten deutschsprachigen Kategorienamen an und wirft keinen Regressions-Crash
  - Test: (populated after /4-tdd-red)

## Known Limitations

- Keine Tests für `WeatherMetricsTab` oder `WeatherConfigDialog` vorhanden — AC-2 und AC-3 werden als Source-Inspection-Tests (statische Analyse der Datei-Inhalte) implementiert, nicht als Render-Tests.
- `BucketSectionOff`, `TablePreview`, `BucketSection`, `SavePresetDialog` werden nicht geändert; ihr Verhalten wird durch AC-5 als Regressions-Check abgedeckt.

## Out of Scope

- Migration weiterer Komponenten in `metricsEditor.ts` (z.B. `organisms.jsx` ↔ #331/#364 — separater Scope von Issue #392)
- Umbenennung von `INDICATOR_MAP` oder `indicatorCapable` (andere Namen, keine Scope-Änderung)
- Einführung von Unit-Tests für die Render-Logik von `WeatherMetricsTab` oder `WeatherConfigDialog`
- Änderungen am Go-API- oder Python-Backend

## Changelog

- 2026-05-27: Initial spec erstellt. Refactoring: `CATEGORY_LABELS`/`CATEGORY_ORDER`/`INDICATOR_MAP`/`indicatorCapable` aus `WeatherMetricsTab.svelte` und `WeatherConfigDialog.svelte` in `metricsEditor.ts` zentralisiert. Behebt Label-Divergenz `winter: 'Winter/Schnee'` vs `'Winter / Schnee'`. 3 Dateien, netto −22 LoC, keine Logik-Änderung.
