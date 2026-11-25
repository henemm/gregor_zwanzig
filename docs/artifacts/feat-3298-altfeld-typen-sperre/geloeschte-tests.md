# #3298 — Zuordnung gelöschter und gekürzter Tests

Jede gelöschte Testdatei bzw. jeder gelöschte Testfall ist einer entfernten Produktionsfunktion
oder einem entfernten Feld zugeordnet (Spec `feat_3298_altfeld_typen_sperre.md`, AC-10).

## Gelöschte Testdateien

| Testdatei | Entfernte Produktionsstelle |
|---|---|
| `frontend/src/lib/components/compare/__tests__/compare_hourly_metric_formats_persistenz.test.ts` | `frontend/src/lib/components/compare/hourlyFriendlyMap.ts` (gelöscht, AC-8) |
| `frontend/src/lib/components/compare/__tests__/compare_hourly_metric_formats_wirkorte.test.ts` | `hourlyMetricFormats` in `LayoutSnapshot`/`WetterMetrikenLayoutSnapshot` und Lesen von `hourly_metric_formats` in `hydrateLayoutFieldsFromPreset` (`weatherMetricsCompareSave.ts`) |

## Gelöschte Testfälle in weiterbestehenden Dateien

| Datei | Testfall | Entfernte Produktionsstelle |
|---|---|---|
| `shared/__tests__/compareChannelMetricLayouts.test.ts` | Block „Hydration: gespeicherter Stand -> Kanal-Overrides" (3 Fälle) | `compareChannelActiveMetricsFromStored` (Lese-Naht `channel_active_metrics`) |
| `compare-new/__tests__/compareNewVorlage.test.ts` | „AC-9 bewusst leeres hourly_metrics [] bleibt []", „AC-9 fehlendes hourly_metrics bleibt null", „AC-9 bewusst leere outlook_metrics …", „AC-9 outlook_metric_formats: fehlend bleibt null …" | Layout-Altfelder in `hydrateLayoutFieldsFromPreset` / `feldsatzAusVorlage` |
| `compare/__tests__/compare_hub_layout_save.test.ts` | „#3276: geänderte hourlyMetricKeys …", „#3276: umsortierter Snapshot …", Block „C2 AC-5 / #3276: leere hourlyMetricKeys …" | `hourlyMetricKeys` in `LayoutSnapshot` |
| `compare/__tests__/compare_outlook_metric_formats_persistenz.test.ts` | „NUR outlookMetricFormats geaendert -> kein PUT", „Zuruecknehmen auf Roh …", „der Ausblick-Schalter (eigenes Feld) wird weiter gesendet" | `outlookMetricFormats`/`outlookEnabled` in `LayoutSnapshot`, `outlook_enabled` im Layout-PUT |
| `shared/weather-metrics-tab/__tests__/wetter_metriken_intra_gesture_kollision.test.ts` | „umgekehrte Reihenfolge (Ausblick zuerst, dann Stundenverlauf)" | `outlookEnabled` (zweites eigenes Feld des Zustellungs-Speicherers) |
| `shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_konflikt_nochmal_speichern.test.ts` | „Konflikt beim Ausblick-Schalter verhält sich identisch" | `outlookEnabled` / `outlook_enabled` im Zustellungs-PUT |
| `shared/weather-metrics-tab/__tests__/wetter_metriken_nutzlast_verliert_keine_daten.test.ts` | Schleife „AC-12 (Rueckfall, #3276): {hourlyMetricKeys,outlookMetricKeys,outlookMetricFormats} == null" (3 Fälle, ersetzt durch einen Fall „Bestand mit Altfeldern") | camelCase-Altfelder in `WetterMetrikenLayoutSnapshot` |

## Umgestellte Tests (Altfeld-Erwartung → „Schlüssel fehlt")

- `compare/__tests__/compareOutlookMetricSelection.test.ts` (AC-13: Editor-Wert `outlookEnabled` wird nie gesendet)
- `compare/__tests__/outlookMetricIdSelection.test.ts` (Lesepfad direkt an `normalizeStoredOutlookMetrics` statt über die entfernte Hub-Hydration)
- `compare/__tests__/compare_feldsatz_standard_startwerte.test.ts` (camelCase-Altfelder in der Liste toter Felder)
- `compare/__tests__/compare_hub_layout_rollback.test.ts`, `compare/__tests__/fix_3061_hub_hydrierer.test.ts`
- `compare-new/__tests__/compareNewVorlage.test.ts` (Altfelder der Vorlage landen nicht im Feldsatz; Kanal-Metriken werden nicht gelesen)
- `shared/__tests__/compare_reiter_nutzlast_nur_eigene_felder.test.ts` (wetterMetriken: kein `outlook_enabled`)
- `shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` (drei Zeilennummern nachgeführt, Bedingungen unverändert)
- `shared/weather-metrics-tab/__tests__/*` (Gesten auf den Stundenverlauf-Schalter umgestellt)
- Prüfstände `goMergeServerPruefstand.ts` (`EIGENFELDER.wetterMetriken.top`), `compareReiterAufbauPruefstand.ts` (`leeren`), `wetterMetrikenVergleichPruefstand.ts` (`outlookEnabledToggle`, `outlookSelect`, `outlookFormatToggle`, `hourlyDragEnd` entfernt)
- Fixtures `compare-new/__tests__/fixtures/vergleich_anlegen_ohne_zustellung_3333.json` und `tests/fixtures/einstellung_gleich_mail/neuanlage_p11_payload.json`: `outlook_enabled` aus dem Referenz-POST entfernt (der Anlege-Rumpf sendet es nicht mehr)
- `feat3276_vergleich_ohne_altfelder.test.ts` (`wizMitAltwerten` und Snapshot schieben die Altfelder per Cast unter), `shared/__tests__/reportConfigDirty.test.ts` (`multi_day_trend_morning/evening` aus dem typisierten Objekt)
