# Mini-Spec: Trip-Wertebereiche — Min/Max-Unterscheidung bei geteiltem Katalog-Label

Issue: #1429

## Acceptance Criteria

- **AC-1:** Given ein Katalog-Eintrag mit `aggregation_label` (z.B. `wind_chill_min_c`), When `buildRouteMetricDefsFromCatalog()` ihn mappt, Then trägt das resultierende `RouteMetricDef` ein `aggregationLabel`-Feld mit demselben Wert.

- **AC-2:** Given ein Katalog-Eintrag ohne `aggregation_label`, When `buildRouteMetricDefsFromCatalog()` ihn mappt, Then bleibt `aggregationLabel` im resultierenden `RouteMetricDef` `undefined` (kein erfundener Key, keine Rendering-Änderung für die übrigen Metriken).

- **AC-3:** Given eine bereits gespeicherte Korridor-Zeile für eine Def mit `aggregationLabel` (z.B. `wind_chill_max_c`), When `buildRoutePool()` die Zeile aufbaut, Then trägt die resultierende `CorridorRowState` dasselbe `aggregationLabel`.

- **AC-4:** Given eine Def mit `aggregationLabel` im `poolLeft`, When `addRow()` sie hinzufügt, Then trägt die neu erzeugte `CorridorRowState` dasselbe `aggregationLabel`.

## Problem

Im Trip-Editor, Reiter "Wertebereiche", zeigen `wind_chill_min_c` und
`wind_chill_max_c` beide nur "Gefühlte Temperatur" — nicht unterscheidbar,
ob Min oder Max. Ursache: `buildRouteMetricDefsFromCatalog()`
(`compareMetricCatalogLoader.ts`) mappt `entry.aggregation_label` bisher
nicht in `RouteMetricDef`, obwohl der Katalog-Eintrag ihn liefert. Der
Ortsvergleich-Pfad (`buildCompareMetricDefs`/`addCompareRow`) hat dasselbe
Rohmaterial und löst es bereits über `aggregationLabel`.

Die Anzeige selbst (`CorridorEditor.svelte`/`CorridorEditorMobile.svelte`,
Pool-Button UND Zeilen-Darstellung) rendert `row.aggregationLabel` /
`m.aggregationLabel` bereits kontextunabhängig für `route` und `vergleich`
— dort ist NICHTS zu ändern. Es fehlt nur die Datendurchreichung auf der
Route-Seite (Trip/Compare-Code-Teilung: Rendering ist bereits geteilt,
nur die Datenquelle route hinkt hinterher).

## Was ändert sich

- `RouteMetricDef` (`corridorEditorState.ts`): optionales Feld
  `aggregationLabel?: string` ergänzen.
- `buildRouteMetricDefsFromCatalog()` (`compareMetricCatalogLoader.ts`):
  `entry.aggregation_label` nach `aggregationLabel` mappen — exakt wie
  `buildCompareMetricDefs()` es bereits tut (nur wenn im Eintrag
  vorhanden, kein erfundener `undefined`-Schlüssel).
- `buildRoutePool()` (`corridorEditorState.ts`): beim Zusammenbau einer
  bereits gespeicherten Zeile (`rows.push(...)`) `aggregationLabel:
  def.aggregationLabel` mitgeben.
- `addRow()` (`corridorEditorState.ts`): beim Hinzufügen einer neuen
  Zeile aus dem Pool ebenso `aggregationLabel: def.aggregationLabel`
  mitgeben — exakt wie `addCompareRow()` es bereits tut.

## Was darf sich nicht ändern

- Kein Eingriff in `CorridorEditor.svelte`/`CorridorEditorMobile.svelte`
  (Rendering ist bereits geteilt und korrekt).
- Die alten 6 fest verdrahteten `ROUTE_METRIC_DEFS` haben kein
  `aggregation_label` im Katalog-Sinn (eigene Route-Labels wie
  "Temperatur Min"/"Temperatur Max") — für sie bleibt `aggregationLabel`
  `undefined`, unverändertes Verhalten.
- Kein Rendering-Unterschied für Metriken ohne Kollision (die anderen 16
  der 17 neuen Katalog-Metriken behalten ihr einfaches Label).

## Manuelle Test-Schritte

1. Trip-Editor öffnen, Reiter "Wertebereiche", "+ Metrik hinzufügen".
2. Prüfen: die beiden "Gefühlte Temperatur"-Chips zeigen zusätzlich
   "Minimum"/"Maximum" (analog zum Ortsvergleich-Pool).
3. Eine der beiden Zeilen hinzufügen — die Zeilen-Darstellung zeigt
   ebenfalls die Unterscheidung.
4. Eine bereits gespeicherte `wind_chill_min_c`/`wind_chill_max_c`-Zeile
   laden (Trip mit bestehendem Korridor) — auch dort unterscheidbar.
5. Stichprobe bei einer Nicht-Kollisions-Metrik (z.B. "Böen"): unverändert
   ohne Zusatz-Label.

## Inline-Test (wird während Implementierung geschrieben)

- [ ] `buildRouteMetricDefsFromCatalog`: Katalog-Eintrag mit
      `aggregation_label` liefert `aggregationLabel` im `RouteMetricDef`;
      Eintrag ohne das Feld liefert `undefined` (kein erfundener Key).
- [ ] `buildRoutePool`: eine gespeicherte Zeile für eine Def mit
      `aggregationLabel` trägt es in der resultierenden `CorridorRowState`.
- [ ] `addRow`: eine aus dem Pool hinzugefügte Zeile trägt
      `aggregationLabel`, wenn die Def es hat.
