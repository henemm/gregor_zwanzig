---
entity_id: issue_445_metric_entry_cleanup
type: module
created: 2026-05-29
updated: 2026-05-29
status: completed
version: "1.0"
tags: [frontend, typescript, refactoring, types, metric-entry]
---

<!-- Issue #445 — Cleanup: 3 pre-existing MetricEntry-Duplikate auf types.ts konsolidieren -->

# Issue 445 — MetricEntry-Duplikate konsolidieren

## Approval

- [x] Approved

## Purpose

Drei Svelte-Komponenten in `frontend/src/lib/components/trip-detail/` definieren `interface MetricEntry` lokal mit 6 Feldern, obwohl seit Issue #435 eine kanonische 8-Felder-Definition in `frontend/src/lib/types.ts:131` existiert. Die lokalen Definitionen kennen die in #435 ergänzten optionalen Felder `format_modes?` und `default_format_mode?` nicht, was zu stillen Typ-Divergenzen führt. Ziel ist es, die drei lokalen Definitionen zu löschen und stattdessen den kanonischen Typ aus `$lib/types` zu importieren, sodass künftige Erweiterungen des Typs automatisch in allen Komponenten wirksam werden.

## Source

- **File:** `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` — lines 17–24 (lokale `interface MetricEntry` + `type MetricCatalog`)
- **File:** `frontend/src/lib/components/trip-detail/TablePreview.svelte` — lines 12–19 (lokale `interface MetricEntry` + `type MetricCatalog`)
- **File:** `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` — lines 13–20 (lokale `interface MetricEntry`)
- **Reference (unverändert):** `frontend/src/lib/types.ts:131` — kanonische `export interface MetricEntry`-Definition (8 Felder)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MetricEntry` in `frontend/src/lib/types.ts` | Kanonischer Typ | 8-Felder-Definition inkl. `format_modes?` und `default_format_mode?` aus #435; wird nach dem Cleanup die einzige Quelle der Wahrheit |
| `import type { ... } from '$lib/types'` in den 3 Komponenten | Bestehender Import | Bereits vorhanden in allen 3 Dateien; `MetricEntry` wird ergänzt, kein neues `import`-Statement nötig |
| `type MetricCatalog = Record<string, MetricEntry[]>` | Lokaler Alias | Bleibt in `SavePresetDialog.svelte` und `TablePreview.svelte` erhalten; referenziert nach dem Cleanup den importierten `MetricEntry` |
| `scoreToggleHelpers.ts` | Absichtlich ausgenommen | Definiert einen minimalen lokalen Typ mit nur `id` + `default_enabled?` für einen anderen Verwendungszweck; wird nicht angefasst |

## Implementation Details

```
Für jede der 3 betroffenen Komponenten gilt dasselbe Vorgehen:

1. Lösche den lokalen interface-Block:
     interface MetricEntry {
       id: string;
       label: string;
       unit: string;
       default_enabled: boolean;
       description?: string;
       icon?: string;
     }
   (6 Felder, ~6 Zeilen)

2. Füge `MetricEntry` zur bestehenden `import type`-Zeile hinzu:
     Vorher:  import type { SomeOtherType } from '$lib/types';
     Nachher: import type { SomeOtherType, MetricEntry } from '$lib/types';

3. Lokale `type MetricCatalog = Record<string, MetricEntry[]>`-Aliasse
   in SavePresetDialog.svelte und TablePreview.svelte bleiben unverändert —
   sie referenzieren nach dem Cleanup automatisch den importierten MetricEntry.

4. Nach allen 3 Änderungen TypeScript-Check ausführen:
     cd frontend && npm run check
   Erwartet: 0 Fehler, 0 neue Warnungen.
```

Gesamtumfang: ~18 LoC entfernt, 3 Import-Zeilen angepasst. Kein Laufzeit-Verhalten ändert sich.

## Expected Behavior

- **Input:** Keine Laufzeit-Eingaben — reine Typ-Konsolidierung ohne Verhaltensänderung
- **Output:** `npm run check` läuft ohne Fehler; alle 3 Komponenten nutzen denselben `MetricEntry`-Typ inkl. `format_modes?` und `default_format_mode?`
- **Side effects:** Keine — das Frontend-Bundle ändert sich nicht, da TypeScript-Interfaces zur Laufzeit nicht existieren

## Acceptance Criteria

- **AC-1:** Given die 3 Komponenten enthalten nach dem Rework keine lokale `interface MetricEntry`-Definition mehr / When `grep -r "interface MetricEntry" frontend/src/lib/components/trip-detail/` ausgeführt wird / Then liefert der Befehl keine Treffer (leere Ausgabe, Exit-Code 1)

- **AC-2:** Given `MetricEntry` ist aus `$lib/types` importiert / When `npm run check` im `frontend/`-Verzeichnis ausgeführt wird / Then endet der Prozess mit Exit-Code 0 und zeigt 0 TypeScript-Fehler

- **AC-3:** Given die lokale `interface MetricEntry` in den 3 Komponenten hatte nur 6 Felder ohne `format_modes?` / When nach dem Cleanup ein TypeScript-Consumer auf `entry.format_modes` zugreift / Then ist das Feld typkorrekt sichtbar (kein TS2339-Fehler), weil der kanonische Typ 8 Felder hat

- **AC-4:** Given `SavePresetDialog.svelte` und `TablePreview.svelte` verwenden `type MetricCatalog = Record<string, MetricEntry[]>` / When die lokale `interface MetricEntry` gelöscht wird / Then kompilieren beide Dateien weiterhin fehlerfrei, weil `MetricCatalog` nun den importierten `MetricEntry` referenziert

- **AC-5:** Given `scoreToggleHelpers.ts` hat einen absichtlich minimalen lokalen Typ für einen anderen Zweck / When der Cleanup durchgeführt wird / Then bleibt `scoreToggleHelpers.ts` unverändert (keine neue Abhängigkeit von `$lib/types`)

## Known Limitations

- Rein statische Typ-Änderung: Laufzeit-Fehler durch die Typ-Divergenz (fehlende Felder in der 6-Felder-Variante) wurden bisher nicht gemeldet, weil die Felder optional sind und JS-Objekte trotzdem übergeben werden können. Der Cleanup verhindert künftige stille Typ-Abweichungen, behebt aber keinen aktiven Bug.

## Changelog

- 2026-05-29: Initial spec erstellt — Issue #445
- 2026-05-29: Implementierung abgeschlossen — 3 Duplikate konsolidiert, TypeScript-Check grün
