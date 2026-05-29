# Context: Issue #445 — MetricEntry-Duplikate konsolidieren

## Request Summary
3 pre-existing lokale `interface MetricEntry`-Definitionen in trip-detail-Komponenten durch Import aus der kanonischen `$lib/types` ersetzen.

## Befund: Typ-Divergenz

Die kanonische Definition in `types.ts` (seit #435, Zeile 131) hat **8 Felder**:
```typescript
export interface MetricEntry {
  id, label, unit, category, default_enabled, has_friendly_format,
  format_modes?: string[];       // NEU in #435
  default_format_mode?: string;  // NEU in #435
}
```
Alle 3 lokalen Definitionen haben nur **6 Felder** (ohne `format_modes`, `default_format_mode`).

## Related Files
| Datei | Änderung |
|-------|----------|
| `frontend/src/lib/types.ts:131` | Quelle (export interface MetricEntry) — unverändert |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte:17` | Lokale Definition löschen, import ergänzen |
| `frontend/src/lib/components/trip-detail/TablePreview.svelte:12` | Lokale Definition löschen, import ergänzen |
| `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte:13` | Lokale Definition löschen, import ergänzen |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts:11` | exportiert `MetricCatalog` (kein Eingriff nötig) |

## Bestehende Muster
- Alle 3 Dateien importieren bereits aus `$lib/types` (für `Horizons`, `HORIZONS_ALL`, `MetricPreset`)
- `metricsEditor.ts` importiert `MetricEntry` schon aus `$lib/types` und re-exportiert `MetricCatalog`
- `SavePresetDialog` und `TablePreview` definieren lokal `type MetricCatalog = Record<string, MetricEntry[]>` — kann als lokale Type-Alias bleiben

## Dependencies
- Upstream: `frontend/src/lib/types.ts` (kein Änderungsbedarf)
- Downstream: alle Aufrufer der 3 Komponenten (Props-API unverändert)

## Risks & Considerations
- TypeScript-Structural-Typing: Neue optionale Felder (`format_modes?`, `default_format_mode?`) sind rückwärtskompatibel — bestehende Props-Übergaben bleiben gültig
- `MetricCatalog` bleibt in SavePresetDialog und TablePreview als lokale Typaliase (kein Breaking Change)
- Build-Check nach Änderung empfohlen (`npm run check` im frontend/)
