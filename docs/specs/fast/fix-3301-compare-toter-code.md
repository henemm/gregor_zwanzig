---
entity_id: fix-3301-compare-toter-code
type: fast
created: 2026-11-25
status: draft
---

# Mini-Spec: Ortsvergleich anlegen ohne Kanal-Layout-Karte, toter Stundenmetrik-Code entfernt (#3301)

## Ausgangslage
- Die Karte „Layout je Kanal“ im Versand-Schritt des Ortsvergleich-Anlegens lag in `WeatherMetricsTab.svelte`. Diese Komponente ist mit #3297/#3020 (live seit 25.11., c8329fea4) gelöscht; die Karte ist damit bereits aus der Oberfläche verschwunden.
- Übrig ist `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts` (156 Zeilen). Kein Produktionscode importiert es mehr, nur `compareEditorHourlyMetrics.test.ts`.

## Was ändert sich
- `compareHourlyMetricDefs.ts` wird gelöscht.
- In `compareEditorHourlyMetrics.test.ts` entfallen die Blöcke, die nur Funktionen dieser Datei prüfen (`applyHourlyMetricToggle`, `applyHourlyMetricToggleFromState`, `orderableHourlyMetricKeys`, `applyHourlyReorder`, Server-Vorgabemenge). Der Block `buildComparePresetSavePayload — hourly_metrics` bleibt, weil er lebenden Code (`compareEditorSave.ts`) prüft.
- Ein Lösch-Nachweis-Test sichert zu: Die Datei existiert nicht mehr, kein Produktionsimport verweist darauf, und die Anlegeseite des Ortsvergleichs (`routes/compare/new`) samt ihrer eingebundenen Komponenten enthält keine Kanal-Layout-Karte (`layout_kanal` bzw. `WeatherMetricsTab`).

## Was darf sich nicht ändern
- Speichern eines Ortsvergleichs (`buildComparePresetSavePayload`) bleibt unverändert, `hourly_metrics` aus dem Bestand bleibt erhalten.
- Trip-Pfad unverändert.
- Keine sichtbare Änderung der Oberfläche (die Karte ist bereits weg).

## Acceptance Criteria
- **AC-1:** Given der Stand nach #3297, When die Frontend-Produktionsquellen durchsucht werden, Then existiert `compareHourlyMetricDefs.ts` nicht mehr und kein Produktionsmodul importiert es.
- **AC-2:** Given die Anlegeseite des Ortsvergleichs, When ihre Komponenten-Importkette geprüft wird, Then bindet sie weder `WeatherMetricsTab` noch einen Abschnitt `layout_kanal` ein.
- **AC-3:** Given ein Ortsvergleich mit gespeichertem `hourly_metrics`, When er über `buildComparePresetSavePayload` gespeichert wird, Then bleibt `hourly_metrics` unverändert erhalten (bestehender Test bleibt grün).

## Manuelle Test-Schritte
1. Staging: Ortsvergleich anlegen, Schritt Versand öffnen: keine Karte „Layout je Kanal“.
2. Ortsvergleich speichern, neu laden: Werte bleiben.

## Inline-Test
- [ ] Lösch-Nachweis AC-1/AC-2 (`frontend/src/lib/__tests__/compare_toter_code_3301.test.ts`, `# doc-compliance-test`)
- [ ] `compareEditorHourlyMetrics.test.ts` (Rest) grün, gesamte Unit-Suite grün, Build grün

## Approval
- [ ] Approved
