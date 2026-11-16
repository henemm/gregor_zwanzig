# Context: fix-3061-ausblick-alle-groessen

## Request Summary
Im Orte-Vergleich-Editor wird eine bewusst gespeicherte Grundauswahl, die exakt alle Katalog-Größen
(`COMPARE_METRIC_KEYS`) enthält, im Ausblick-Block wie „nie eingestellt“ (Altbestand) behandelt:
der Editor zeigt nur die sieben festen Vorgabe-Spalten aktiv, die Mail zeigt aber alle darstellbaren
Größen. Editor ≠ Mail (Prüfkatalog #3047, Befund F4). Ziel: „nie eingestellt“ hängt am fehlenden
`active_metrics` im Preset, nicht am Listenvergleich.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/OutlookLayoutControls.svelte:149-195` | `istNieEingestellteOrteGrundauswahl()` — Listenvergleich mit `COMPARE_METRIC_KEYS`, Ursache des Fehlers; `grundauswahlKennungen` → `null` ⇒ Vorgabe-Spalten |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1182,1616-1619` | reicht `grundauswahl={materializedActiveMetricKeys}` (= `materializeActiveMetricKeys(activeMetricKeys ?? null)`) — das `null` geht hier verloren |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:80-85` | `hydrateWeatherMetricsFromPreset` materialisiert fehlendes `active_metrics` zu `[...COMPARE_METRIC_KEYS]` |
| `frontend/src/lib/components/compare/compareHubHydration.ts:60-66,128` | `hydrateHubFieldsFromPreset` behält `null`; Alarm-Hydrierer (:128) materialisiert dagegen über `hydrateWeatherMetricsFromPreset` |
| `frontend/src/lib/components/compare/CompareTabs.svelte:386,527` | Hub setzt `wizardState.activeMetricKeys` aus beiden Hydrierern |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricOrder.ts:16-24` | `materializeActiveMetricKeys(null)` → `COMPARE_METRIC_KEYS` |
| `frontend/src/lib/components/compare/compareEditorSave.ts:153-162,519-523` | Speichern: `active_metrics` nur geschrieben, wenn editiert (`!== undefined`) bzw. `!== null` |
| `src/output/renderers/compare_outlook_metric_ids.py:151-249` | Mail-Seite: `active_metrics` fehlt ⇒ `enabled_metrics=None` ⇒ keine Grundauswahl ⇒ feste Vorgabe-Spalten; `active_metrics` = volle Liste ⇒ alle darstellbaren Größen |
| `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` | Prüfkatalog Orte; Ausblick-Fälle `O-AB-*`, Dimension `auswahl_muster` (teilmenge/alles/bewusst_leer/nie_eingestellt) |
| `tests/tdd/test_einstellung_gleich_mail_orte.py`, `test_einstellung_gleich_mail_fallliste.py` | Mail-Seite des Prüfkatalogs, Fallliste-Konsistenz |
| `frontend/src/lib/components/compare/__tests__/outlookMetricIdSelection.test.ts` | bestehende Editor-Tests zum Ausblick |

## Existing Patterns
- `null` = „nie eingestellt“, `[]` = „bewusst leer“ (#1191-Semantik), durchgängig in Save/Load.
- `hydrateHubFieldsFromPreset` liefert bereits `activeMetricKeys: null` für Altbestand.
- Eine Umsetzung für Trip und Vergleich (`_erbe_grundauswahl`, Teilungs-Invariante #1170).

## Dependencies
- Upstream: Preset `display_config.active_metrics`, Compare-Katalog.
- Downstream: Ausblick-Block (OutlookLayoutControls), Kanal-Reiter-Kopplung (`materializedActiveMetricKeys`), Alarme-Reiter (Empfindlichkeits-Tabelle braucht materialisierte Liste, #1320), Save-Pfad (Dirty-Check).

## Existing Specs
- `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md` (AC-13/AC-21, O4)

## Risks & Considerations
- `activeMetricKeys` im Wizard-State auf `null` zu lassen berührt Dirty-Check und Save (darf `active_metrics` nicht ungewollt schreiben/weglassen) und die Alarm-Hydrierung (#1320). Alternativ: separates Signal „Preset hatte kein `active_metrics`“ bis zum Ausblick durchreichen.
- Nach der ersten Änderung der Grundauswahl wird `active_metrics` geschrieben — ab dann gilt die gespeicherte Liste (auch wenn sie wieder alles enthält), Editor muss dem folgen.
- Trip-Kontext darf sich nicht ändern (Trip reicht nie `null` als Altbestand-Signal so herein).
- Parallelsitzung #3048 (Trip-Altbestand Telegram-Kopf) — anderer Bereich, aber Prüfkatalog-Dateien können sich überschneiden.

## Analysis

### Type
Bug (Editor ≠ Mail, Prüfkatalog #3047 Befund F4)

### Root Cause
Beide Hub-Hydrierer, die `wizardState.activeMetricKeys` setzen (`CompareTabs.svelte:527` `hydrateWetterMetrikenTab` und `compareHubHydration.ts:128` in `hydrateAlarmFieldsFromPreset`), rufen `hydrateWeatherMetricsFromPreset`. Diese Funktion materialisiert ein fehlendes `active_metrics` zu `[...COMPARE_METRIC_KEYS]` (`weatherMetricsCompareSave.ts:78-85`). Damit ist im Editor das `null` („nie eingestellt“) verloren. `OutlookLayoutControls.svelte:149-195` rät es deshalb per Listenvergleich zurück. Eine bewusst gespeicherte Vollauswahl sieht genauso aus und wird fälschlich als Altbestand behandelt: Der Editor zeigt nur die sieben festen Spalten aktiv, die Mail aber alle darstellbaren Größen (`compare_outlook_metric_ids.py:225-249`: `enabled_metrics=None` → feste Spalten, `enabled_metrics=alle` → ganze Grundauswahl).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY | neue Funktion `hydrateWeatherMetricsFromPresetOrNull` (Rückgabe `string[] \| null`). Die alte Funktion bleibt unverändert, weil `compareActiveMetricsStorageFormat.test.ts:455` die Rohform erwartet. |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | `:527` nutzt die null-Variante |
| `frontend/src/lib/components/compare/compareHubHydration.ts` | MODIFY | `:128` nutzt die null-Variante. Der Kommentar zu #1320 wird angepasst (AlarmeTab materialisiert selbst, :255-270). |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | `:1619` `grundauswahl={activeMetricKeys == null ? null : materializedActiveMetricKeys}` (nur Vergleich, Trip `:1946` bleibt) |
| `frontend/src/lib/components/shared/OutlookLayoutControls.svelte` | MODIFY | `istNieEingestellteOrteGrundauswahl` und die Prüfung in `grundauswahlKennungen` entfallen. Nur noch `grundauswahl === null` bedeutet „nie eingestellt“. Kommentare werden nachgezogen. |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/editor_standard_gleich_mail.test.ts` | MODIFY | Der Prüfstand (`:160-190`) wird auf die null-Variante und die neue `grundauswahl`-Verdrahtung umgestellt. Dazu kommt ein Rendertest, der die echte Verdrahtung in `WeatherMetricsTab.svelte:1619` prüft. |
| `frontend/src/lib/components/compare/__tests__/outlookMetricIdSelection.test.ts` | MODIFY | neuer Fall `grundauswahl = COMPARE_METRIC_KEYS` → alle Ausblick-Größen aktiv, keine Sonderbehandlung |
| `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` + `tests/tdd/test_einstellung_gleich_mail_orte.py` (`preset_aus_werten` :243-262) | MODIFY | neuer Prüfkatalog-Fall: `active_metrics` = alle Katalog-Größen, `outlook_metrics` fehlt. Die Fixture-Baulogik kennt diese Kombination heute nicht, deshalb war der Fehler unfangbar. |

### Scope Assessment
- Quelldateien: 5, Tests/Fixtures: 3-4
- Estimated LoC: etwa +20/-20 Quelltext, +40-60 Tests (unter 100)
- Risk Level: MEDIUM. Das Risiko liegt darin, dass `wizardState.activeMetricKeys` im Hub künftig `null` sein darf. Geprüft ist, dass alle Leser null-sicher sind:
  - `toggleCompareMetricKeyFromState` (`compareMetricOrder.ts:68-72`)
  - `materializedActiveMetricKeys`, die Kanal-Reiter, die Checkboxen und Idealwerte
  - AlarmeTab `:255-270` und `CompareTabs:477`
  - die Snapshots `corridorSnapshotAus` und `wetterMetrikenSnapshotAus`, die materialisieren, sodass Dirty-Check und `buildCompareCorridorSavePayload` keine Scheindiff erzeugen

  Eine Suche nach Array-Zugriffen auf `.activeMetricKeys.` traf nur Tests. Beim Speichern schreibt `compareEditorSave.ts:519-523` bei `null` den Schlüssel nicht. `toStoredActiveMetrics(null)` wird nie erreicht (`:153` ist `string[]|undefined`).

### Technical Approach
Wie in Issue #3061 vorgeschlagen: Das bestehende `null`-Signal für „nie eingestellt“ (#1191, `hydrateHubFieldsFromPreset`) wird bis zum Ausblick durchgereicht, statt es per Listenvergleich zu erraten. Ein separates Flag wurde verworfen, weil es ein zweites Signal neben dem etablierten null-Vertrag wäre. Beide Hub-Hydrierer müssen umgestellt werden, sonst kippt das Ergebnis je nach Reihenfolge, in der die Reiter geöffnet werden (der Alarme-Reiter überschreibt den Zustand). Nach dem ersten Speichern mit einer Änderung schreibt der Editor wie heute die materialisierte Liste. Ab dann gilt sie für Editor und Mail gleich. Der Trip-Kontext ist nicht betroffen.

TDD-RED (erst rot, dann grün):
- (a) `outlookMetricIdSelection.test.ts`: Grundauswahl = alle Katalog-Größen, `outlook_metrics` fehlt → alle darstellbaren Ausblick-Größen aktiv. Heute rot.
- (b) Prüfstand `editor_standard_gleich_mail`: Editor gleich Mail für den Alles-Fall. Heute rot.
- (c) Der null-Fall bleibt bei den sieben festen Spalten (Regressionsschutz).
- (d) Der Alarme-Reiter als Erst-Tab ohne `active_metrics` zeigt weiter Metriken (#1320).

### Dependencies
- Upstream: Preset `display_config.active_metrics`, Compare-Katalog (`GET /api/compare/metrics`)
- Downstream: Ausblick-Block, Kanal-Reiter, Alarme-Reiter (#1320), Speicher- und Dirty-Pfad, compare-new (`compareNewVorlage.ts:38-41`, schon null-treu)
- Parallelsitzung #3048 (Trip-Altbestand): anderer Code. Möglicherweise überschneidet sich nur die Prüfkatalog-Datei, deshalb vor dem Merge neu auf `main` aufsetzen.

### Open Questions
- keine (keine Produktentscheidung offen; das Soll „Editor = Mail“ ist durch #3047 AC-13/AC-21 festgelegt)
