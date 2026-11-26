# Context: rework-3389-tote-exporte

## Request Summary
Issue #3389 (Teil von Epic #3122, aus #3385 abgespalten, Refs #3020): In `versandVergleichSpeicherung.ts` und `weatherMetricsCompareSave.ts` stehen 21 Exporte, die nur noch Tests nutzen. Sie werden entfernt, Tests nur auf diese Exporte entfallen, Tests mit lebendem Anteil werden umgebaut. Keine sichtbare Änderung. Vorgehen wie #3383/#3384/#3385: Zahlen nach dem Löschen messen, Lösch-Nachweis führen.

Pfade (unter `frontend/src/lib/components/shared/`):
- `versandVergleichSpeicherung.ts` (360 Zeilen, 11 Exporte)
- `weather-metrics-tab/weatherMetricsCompareSave.ts` (400 Zeilen, 17 Exporte)

Stand der Messung: Worktree `jiggly-tickling-biscuit`, Branch `rework-3389-tote-exporte`, nach Merge #3405.

## Befund in einem Absatz
28 Exporte insgesamt: 5 lebend (je mit Aufrufer in `CompareTabs.svelte`, `compareHubHydration.ts`, `compareNewVorlage.ts`), 2 reine Typen, die nur modulintern von lebenden Exporten gebraucht werden (`VersandSnapshot`, `LayoutSnapshot`), 21 tot. Das passt zur Zahl 9 + 12 im Issue. Beide Module bleiben nach dem Löschen bestehen (nicht leer, keine Waisen); `weatherMetricsCompareSave.ts` steht ausdrücklich auf der BLEIBT-Liste und der ERHALTEN-Liste.

## Exporte
Produktionsaufrufer = Import aus Nicht-Test-Code unter `frontend/src` (ohne `__tests__`, `*.test.ts`, `e2e`). Per grep gemessen; Kommentar-Nennungen zählen nicht.

### versandVergleichSpeicherung.ts

| Name (Zeile) | Prod-Aufrufer | Beleg | Testdateien (Import) |
|---|---|---|---|
| `hydrateVersandFieldsFromPreset` (81) | JA, lebend | `compare/CompareTabs.svelte:88` (Import), `:433` (Aufruf); `compare-new/compareNewVorlage.ts:24` | hub_versand_inline, compare_feldsatz_roundtrip_datenerhalt, hub_nochmal_speichern_ueber_reiterwechsel, compare_versand_hydration_unter_wetter_metriken, s3a2794_zustellung_vergleich_ein_speicherer, alarme_vergleich_kein_zurueckschreiben, alarme_vergleich_kanalwahl_speicherweg, versand_vergleich_premium_sms, compareReiterAufbauPruefstand |
| `VersandSnapshot` (34, Typ) | nein extern; modulintern vom lebenden `hydrateVersandFieldsFromPreset` (Rückgabetyp, Z. 82) | kein Import außerhalb des Moduls | hub_versand_inline, alarme_vergleich_*, versand_vergleich_premium_sms, compare_alarm_versand_nutzlast_trennung |
| `VersandHydrationTarget` (56, Typ) | nein | nur modulintern von `versandSnapshotAus`, `versandZustandsBruecke` | keine |
| `versandSnapshotAus` (104) | nein | kein Import in Prod | versand_enddatum…, versand_nutzlast_verliert…, versand_vergleich_premium_sms |
| `baueVersandNutzlast` (147) | nein | kein Import in Prod | feat3276, versand_nutzlast_verliert…, versand_vergleich_premium_sms, compare_alarm_versand_nutzlast_trennung, alarme_vergleich_kanalwahl_speicherweg |
| `flushPendingVersandSave` (185) | nein | kein Import in Prod | hub_versand_inline |
| `rollbackVersandSnapshot` (205) | nein | kein Import in Prod | hub_versand_inline, versand_vergleich_premium_sms |
| `versandVergleichSpeicherungAktiv` (230) | nein | kein Import in Prod | versand_speicherung_nur_im_vergleich_hub |
| `VersandVergleichSpeicherungOptionen` (239, Typ) | nein | nur modulintern | keine |
| `erstelleVersandVergleichSpeicherung` (267) | nein | kein Import in Prod | 13 Testdateien + `compareReiterAufbauPruefstand.ts` (siehe Tabelle Testdateien) |
| `versandZustandsBruecke` (349) | nein | kein Import in Prod | keine (nirgends importiert, auch nicht in Tests) |

Tot: 9 (ohne `VersandSnapshot`, das als Typ des lebenden Exports bleibt). `VersandSnapshot` kann bleiben, ob mit oder ohne `export`, entscheidet die Spec (extern importieren ihn nur Tests, die entfallen oder umgebaut werden).

### weatherMetricsCompareSave.ts

| Name (Zeile) | Prod-Aufrufer | Beleg | Testdateien (Import) |
|---|---|---|---|
| `hydrateDayWindowFromPreset` (39) | JA, lebend | `compare/CompareTabs.svelte:48,539`; `compare-new/compareNewVorlage.ts:27,55` | keine |
| `hydrateWeatherMetricsFromPreset` (66) | JA, lebend | `CompareTabs.svelte:47,528`; `compare/compareHubHydration.ts:28,132` | compareActiveMetricsStorageFormat, compareMetricKeysParity (Name im Text), wetterMetrikenVergleichPruefstand (Name im Kommentar) |
| `LayoutSnapshot` (84, Typ) | nein extern; modulintern vom lebenden `hydrateLayoutFieldsFromPreset` (Z. 93) | kein Import außerhalb | compare_hub_layout_save, compare_hub_layout_rollback, compare_outlook_metric_formats_persistenz |
| `hydrateLayoutFieldsFromPreset` (93) | JA, lebend | `CompareTabs.svelte:49,573`; `compareNewVorlage.ts:28,56` | feat3298, fix_3061_hub_hydrierer |
| `flushPendingLayoutSave` (104) | nein | in `CompareTabs.svelte:851` nur Kommentar | compare_hub_layout_save, compare_outlook_metric_formats_persistenz, feat3298 |
| `rollbackLayoutSnapshot` (129) | nein | kein Import in Prod | compare_hub_layout_rollback |
| `WetterMetrikenLayoutSnapshot` (143, Typ) | nein | nur modulintern | feat3276, wetter_metriken_nutzlast_verliert… |
| `WetterMetrikenZustand` (154, Typ) | nein | nur modulintern | keine |
| `wetterMetrikenSnapshotAus` (165) | nein | kein Import in Prod | fix_3061, alarme_vergleich_kanalwahl_speicherweg, f006, wetter_metriken_nutzlast_verliert… |
| `baueWetterMetrikenNutzlast` (201) | nein | kein Import in Prod | feat3276, alarme_vergleich_kanalwahl_speicherweg, f006, wetter_metriken_nutzlast_verliert… |
| `flushPendingWetterMetrikenSave` (234) | nein | kein Import in Prod | fix_3061_hub_hydrierer |
| `rollbackWetterMetrikenSnapshot` (249) | nein | kein Import in Prod | keine |
| `WetterMetrikenVergleichSpeicherungOptionen` (266, Typ) | nein | nur modulintern | keine |
| `erstelleWetterMetrikenVergleichSpeicherung` (293) | nein | kein Import in Prod | 11 Testdateien + `compareReiterAufbauPruefstand.ts` |
| `wetterMetrikenHydrationAbgeschlossen` (346) | JA, lebend | `CompareTabs.svelte:50,517` | wetter_metriken_hydration_vollstaendig_vor_baseline, s3a2794_flush_hydration_kette (Name im Text) |
| `wetterMetrikenVergleichSpeicherungAktiv` (358) | nein | kein Import in Prod | wetter_metriken_speicherung_nur_im_vergleich_hub; Name auch im Kommentar von context_herkunft_zweige_eingefroren |
| `wetterMetrikenZustandsBruecke` (389) | nein | kein Import in Prod | keine |

Tot: 12 (ohne `LayoutSnapshot`). Lebend: 4. Zusammen mit Versand 9 = 21. Nicht exportierte Hilfen, die mitfallen: `felder` (156), `WETTER_TOP` (192), `zustellungsStand` (224). `DEFAULT_DAY_WINDOW_*` (33/34) bleiben (von `hydrateDayWindowFromPreset` gebraucht).

Dynamische/String-Importe: nur `feat3298_vergleich_ohne_altfelder.test.ts:253` (`await import('…/weatherMetricsCompareSave.ts')`, prüft laut Titel „Lese-Naht channel_active_metrics ist entfernt“, also eine Abwesenheit, kein Aufruf toter Exporte; Detail in der Analyse prüfen). In Prod gibt es keinen dynamischen Import und kein `import.meta.glob` auf die beiden Module. `totcode_rueckbau_speicherweg.test.ts:116-118` und `trip_pfad_altfeld_loeschnachweis_3297.test.ts:48,191` nennen die Dateinamen als Pfadstrings (siehe Risks).

Importe der beiden Module, die nach dem Löschen unbenutzt werden (Aufräumen, svelte-check/lint): Versand: `IdealRange`, `SaveFn`, `SaveStatus`, `merkeNutzlast`, `PutClient`, `buildComparePresetSavePayload`, `waehleEigenfelder`, `normalizeStoredActiveMetrics`, `ActivityProfile`. Weather: `ActivityProfile`, `SaveFn`, `SaveStatus`, `merkeNutzlast`, `PutClient`, `buildComparePresetSavePayload`, `waehleEigenfelder`, `CompareChannelActiveMetrics`, `materializeActiveMetricKeys`. Keiner dieser Fremdbausteine wird dadurch zur Waise: alle haben weitere Prod-Nutzer (`merkeNutzlast`: tripSpeicherung, CompareTabs u. a.; `waehleEigenfelder`: alarme-/wertebereicheVergleichSpeicherung; `materializeActiveMetricKeys`: AlarmeTab, CompareTabs, anlegeVorbelegung; `compareChannelMetricLayouts.ts`: compareEditorSave.ts). Bleiben im Weather-Modul: `rehydrateActiveMetrics`, `registeredCompareMetricCatalog`, `CompareSelectionEntry`, `ComparePreset`. Im Versand-Modul bleibt nur `ComparePreset`.

## Testdateien
Gruppe a = prüft nur tote Exporte (entfällt). Gruppe b = hat lebenden Anteil oder anderes Thema (umbauen). Gruppe c = nur Prüfstand-Folgen, ohne Import toter Exporte. Fallzahlen aus grober Blockmessung (`test(`-Blöcke, die tote Namen nennen); genaue Aufteilung gehört in die Analyse, weil mehrere Tests die toten Exporte über lokale Hilfsfunktionen aufrufen.

Pfade relativ zu `frontend/src/lib/components/`.

| Pfad | Gruppe | Begründung |
|---|---|---|
| shared/__tests__/versand_vergleich_speichert_selbst.test.ts | a | 5 Fälle, nur `erstelleVersandVergleichSpeicherung` |
| shared/__tests__/versand_vergleich_konflikt_nochmal_speichern.test.ts | a | 4 Fälle, nur `erstelleVersandVergleichSpeicherung`; nutzt `konfliktMitFremdemNamen` (Prüfstand) |
| shared/__tests__/versand_vergleich_flush_vor_pausieren.test.ts | a | 2 Fälle, nur `erstelle…` |
| shared/__tests__/versand_nutzlast_verliert_keine_daten.test.ts | a | 4 Fälle, `baueVersandNutzlast`, `versandSnapshotAus` |
| shared/__tests__/versand_nutzlast_reicht_keepalive_durch.test.ts | a | 2 Fälle, nur `erstelle…` |
| shared/__tests__/versand_enddatum_ohne_ereignis_bleibt_wirksam.test.ts | a | 3 Fälle, `erstelle…`, `versandSnapshotAus` |
| shared/__tests__/versand_speicherung_nur_im_vergleich_hub.test.ts | a | 6 Fälle, nur `versandVergleichSpeicherungAktiv` |
| compare/__tests__/compare_hub_layout_save.test.ts | a | 3 Fälle, `flushPendingLayoutSave`, `flushPendingVersandSave`(Name im Text) |
| compare/__tests__/compare_hub_layout_rollback.test.ts | a | 2 Fälle, `rollbackLayoutSnapshot` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_drei_stille_gesten_bleiben_wirksam.test.ts | a | 1 Fall, nur `erstelleWetterMetriken…` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_intra_gesture_kollision.test.ts | a | 2 Fälle, nur `erstelle…` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_nutzlast_reicht_keepalive_durch.test.ts | a | 2 Fälle, nur `erstelle…` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_nutzlast_verliert_keine_daten.test.ts | a | 5 Fälle, `baue…`, `erstelle…`, `wetterMetrikenSnapshotAus`; Fall „Kanal-Auswahl geändert…“ steht in der Fallliste (siehe Zählstellen) |
| shared/weather-metrics-tab/__tests__/wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts | a | 6 Fälle, nur `wetterMetrikenVergleichSpeicherungAktiv` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_flush_vor_pausieren.test.ts | a | 1 Fall, `erstelle…` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_konflikt_nochmal_speichern.test.ts | a | 4 Fälle, `erstelle…` + `konfliktMitFremdemNamen('wetterMetriken')` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_speichert_einmal.test.ts | a | 6 Fälle, `erstelle…` |
| shared/__tests__/versand_vergleich_premium_sms.test.ts | b (fast a) | 5 Fälle; 4 prüfen tote Funktionen, 1 (`hydrateVersandFieldsFromPreset liest send_premium_sms`) lebt. Rote-Liste E065/E066 nennen die Datei nur als Namensvergleich entfallener Fälle, keine Prüfung der Datei selbst |
| shared/__tests__/versand_vergleich_reiterwechsel_verliert_nichts.test.ts | b | 3 Fälle; Reiterwechsel mit Alarme-Speicherer (lebend) und Konstante `SELBST_SPEICHERNDE_VERGLEICH_REITER`; Versandseite tot |
| shared/__tests__/s3a2794_zustellung_vergleich_ein_speicherer.test.ts | b | Alarme-Owner (lebend) ist Thema, Versand-Speicherer nur als Kontrolle (Fall 3 und 4) |
| shared/__tests__/alarme_vergleich_kein_zurueckschreiben.test.ts | b | 5 Fälle, Alarme-Speicherer lebt; 4 Fälle nutzen den Versand-Speicherer als Nachbar |
| shared/__tests__/alarme_vergleich_kanalwahl_speicherweg.test.ts | b | 10 Fälle, nur Fall „AC-57 Versand-, Wertebereiche-, Wetter-Metriken-Teil-PUT“ nutzt tote `baue…`/`…SnapshotAus` |
| shared/__tests__/compare_alarm_versand_nutzlast_trennung.test.ts | b | 4 Fälle, 1 Fall `baueVersandNutzlast` (Versand-Nutzlast ohne alert_channels) |
| compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts | b | 3 Fälle, Roundtrip über Versand-Speicherer als Wirkort; Ersatz durch lebenden Speicherer prüfen |
| compare/__tests__/compare_retry_reiterwechsel_eingabe_bleibt.test.ts | b | 10 Fälle, nur der erste braucht `erstelleVersand…` |
| compare/__tests__/hub_nochmal_speichern_ueber_reiterwechsel.test.ts | b | 3 Fälle, Alarme + Versand-Speicherer; Versandteil tot |
| compare/__tests__/hub_put_queue.test.ts | b | 5 Fälle, Schlange (lebend); Integration F002 nutzt `erstelleVersand…` |
| compare/__tests__/hub_versand_inline.test.ts | b | 15 Fälle: 3 lebende Hydration, 9 tote (flush/rollback), 3 weitere (`hubActivationBanner`) |
| compare/__tests__/compare_outlook_metric_formats_persistenz.test.ts | b | 5 Fälle, 3 mit `flushPendingLayoutSave` tot, 2 lebend (Round-Trip) |
| compare/__tests__/fix_3061_hub_hydrierer.test.ts | b | 8 Fälle, 1 nutzt `flushPendingWetterMetrikenSave`/`wetterMetrikenSnapshotAus` |
| compare/feat3276_vergleich_ohne_altfelder.test.ts | b | 9 Fälle, 2 nutzen `baue…Nutzlast`; Rote-Liste E013/E014 nennen die Datei nur historisch |
| compare/feat3298_vergleich_ohne_altfelder.test.ts | b | 12 Fälle, 1 `flushPendingLayoutSave` tot, 1 `hydrateLayoutFieldsFromPreset` lebend; `:253` dynamischer Import |
| shared/weather-metrics-tab/__tests__/f006_zustellung_schreibt_keine_wetterfelder.test.ts | b | Zustellungs-Speicherer (lebend) ist Thema; Wetter-Seite nutzt tote Exporte |
| shared/weather-metrics-tab/__tests__/wetter_metriken_hydration_vollstaendig_vor_baseline.test.ts | b | 5 Prädikat-Fälle auf lebendem `wetterMetrikenHydrationAbgeschlossen`, 1 Mechanismus-Fall mit `erstelle…` tot |
| shared/weather-metrics-tab/__tests__/wetter_metriken_reiterwechsel_verliert_nichts.test.ts | b | 4 Fälle, Mix mit Alarme-Speicherer und Konstante `SELBST_SPEICHERNDE_VERGLEICH_REITER` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_und_wertebereiche_teilen_active_metric_keys.test.ts | b | 3 Fälle; Wertebereiche-Speicherer (lebend) liest Live-Auswahl, Wetter-Metriken-Speicherer tot |
| shared/__tests__/compareReiterAufbauPruefstand.ts | Prüfstand 1 (b) | importiert `erstelleVersand…`, `hydrateVersand…`, `erstelleWetterMetriken…`; Reiter-Matrix `REITER = alarme, versand, wertebereiche, wetterMetriken` (Z. 43); Zweige `versand` (Z. 94-) und `wetterMetriken` (Z. 131-) müssen raus |
| shared/__tests__/versandVergleichPruefstand.ts | Prüfstand 2 (b) | importiert die beiden Module nicht (nur Kommentar). `createController` wird von ca. 27 lebenden Tests genutzt, bleibt. `makePreset`, `hydrierterWiz`, `versandBedienung`, `dc` dienen nur den Versand-Tests der Gruppe a/b (11 Importeure), danach tot |
| shared/weather-metrics-tab/__tests__/wetterMetrikenVergleichPruefstand.ts | Prüfstand 3 (b) | importiert die Module nicht. Importeure: nur Wetter-Metriken-Tests (13), `alarme_vergleich_kanalwahl_speicherweg` (`hydrierterWs`), `compareReiterAufbauPruefstand`; nach den Löschungen wohl ganz entbehrlich (außer Importeure aus Gruppe b, die Alternativen brauchen) |
| compare/__tests__/compare_konflikt_nutzlast_am_eintrag.test.ts | c | iteriert `REITER` des Prüfstands (zählt weniger Reiter) |
| compare/__tests__/compare_retry_fehlerpfade_kein_verlust.test.ts | c | `reiterAufbau('versand'…)`, Tabelle `['versand','Versand'], ['wetterMetriken','Wetter-Metriken']` (Z. 229-231, 267) |
| shared/__tests__/compare_reiter_nutzlast_nur_eigene_felder.test.ts | c | ruft `speichereEinmal('versand'|'wetterMetriken', …)` (Z. 121-155) |
| shared/__tests__/alarme_vergleich_konflikt_nochmal_speichern.test.ts, shared/wetter-tab/__tests__/wertebereiche_vergleich_konflikt_nochmal_speichern.test.ts | c | `konfliktMitFremdemNamen` (Prüfstand), prüfen ob nur Reiter alarme/wertebereiche verwendet werden |
| compare/__tests__/compare_versand_hydration_unter_wetter_metriken.test.ts, compare/__tests__/compareActiveMetricsStorageFormat.test.ts, shared/wetter-tab/__tests__/compareMetricKeysParity.test.ts | unberührt | importieren nur lebende Exporte |
| compare/__tests__/compare_hub_bridge_restlos_entfernt.test.ts, shared/__tests__/s3b2795_zustellung_struktur.test.ts, shared/__tests__/alarme_vergleich_premium_sms_entkoppelt.test.ts, shared/__tests__/rework_3020_vergleich_parallele_schreiber.test.ts, shared/weather-metrics-tab/__tests__/daywindowcard_rueckbau_waechter.test.ts | unberührt | nennen Modulnamen nur im Kommentar bzw. in einer Verbotsliste (`VERBOTENE_SPEICHER_MODULE`, s3b2795:67) |

Summe (nach Importen toter Exporte): Gruppe a = 17 Testdateien, Gruppe b = 19 Testdateien plus 3 Prüfstände, Gruppe c (nur Prüfstand-Folgen) = 6. Das ist mit den Prüfstandsnutzern rund 40 wie im Issue.

Prüfstände und Nutzer:
- `versandVergleichPruefstand.ts`: Importeure 32 (davon `createController` allein 27 lebende Tests: compare_*, hub_reiter_gemeinsame_aufloesung, rework_3020_vergleich_parallele_schreiber, s3a2794_flush_hydration_kette, vergleich_flush_guard_neue_kennungen, nutzlastStand.test, saveStatusStoreBesitzer, f003/fixloop3_c1/c2/p14_ac6/vergleich_412_aufloesung_2988 …). Nur `hydrierterWiz`/`makePreset`/`versandBedienung` gehören den Versand-Tests.
- `wetterMetrikenVergleichPruefstand.ts`: 14 Importeure (siehe oben), alle Wetter-Metriken-Tests.
- `compareReiterAufbauPruefstand.ts`: 8 Importeure (`reiterAufbau`/`REITER`: 4, `konfliktMitFremdemNamen`: 4, davon `versand_vergleich_konflikt…` und `wetter_metriken_vergleich_konflikt…` in Gruppe a).
- Der Altfeld-Wächter `altfeld_namen_sperre.test.ts:8` nimmt `*Pruefstand.ts` aus dem Scan aus, Waisen-Wächter ignoriert `__tests__/` (waisen_waechter.test.ts:14, 67): ein entbehrlich gewordener Prüfstand wird also von keinem Wächter angemahnt, muss von Hand mit gelöscht werden.

## Related Files
| Datei | Rolle |
|---|---|
| frontend/src/lib/components/shared/versandVergleichSpeicherung.ts | Löschziel (9 tote Exporte) |
| frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts | Löschziel (12 tote Exporte) |
| frontend/src/lib/components/compare/CompareTabs.svelte | lebender Aufrufer (5 Exporte); Kommentare Z. 423, 506, 851 nennen tote Namen |
| frontend/src/lib/components/compare/compareHubHydration.ts | lebender Aufrufer (`hydrateWeatherMetricsFromPreset`); Kommentar Z. 75, 114 |
| frontend/src/lib/components/compare-new/compareNewVorlage.ts | lebender Aufrufer (3 Exporte) |
| frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts:75, wetter-tab/corridorEditorState.ts:498, weather-metrics-tab/compareMetricOrder.ts:20 | nur Kommentare mit Dateinamen |
| frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts | Ratsche, Einträge `:236`, `:364` (siehe Zählstellen) |
| frontend/src/lib/components/compare/__tests__/totcode_rueckbau_speicherweg.test.ts | Positivkontrolle Z. 116-118 (siehe Risks) |
| frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts | Lösch-Nachweis (Muster), ERHALTEN Z. 48 und ERHALTEN_3383 Z. 191 nennen `weatherMetricsCompareSave.ts` |
| frontend/src/lib/__tests__/rework_3020_umfang.ts:59 | `BLEIBT` enthält `weatherMetricsCompareSave.ts` |
| tests/fixtures/einstellung_gleich_mail/fallliste_editor.json:637 | Fall verweist auf toten Test |
| docs/reference/gates_und_ratschen.md:555-561 | beschreibt die Ratschenpositionen `versandVergleichSpeicherung.ts:221`, `weatherMetricsCompareSave.ts:534` (schon heute veraltet; nachziehen) |

## Existing Patterns
- Vorbilder: `docs/specs/modules/rework_3383_waisen_s1.md`, `rework_3384_waisen_s4.md`, `rework_3385_waisen_s3.md`, `docs/context/rework-3385-waisen-s3.md`. Muster: Spec mit Löschliste, Tabellen „Datei, Änderung, Beschreibung“, RED-Schritt vor der Löschung, Zahlen nach dem Löschen messen, Lösch-Nachweis als neuer Block in `trip_pfad_altfeld_loeschnachweis_3297.test.ts` (Pfad existiert nicht mehr plus Importscan über `frontend/src` und `frontend/e2e`, Basisnamen-Wortscan F004), Tests mit lebendem Anteil umbauen, Mutations-Gegenprobe durch den Validator.
- Unterschied zu den Vorbildern: Die Vorbilder löschten ganze Dateien (Waisen-Wächter erkennt sie auf Dateiebene). #3383/#3384 vermerken ausdrücklich: „Tote Exporte in lebenden Dateien erfasst der Wächter nicht (Dateiebene)“ (rework_3384 Z. 237, rework_3383 Z. 180). Hier muss der Lösch-Nachweis auf Name und Datei zielen (Export-Namen, die in Prod-Code nicht mehr vorkommen, plus Fehlen als `export`-Zeile). Ein Namensscan über `frontend/src` und `frontend/e2e` mit Kommentare-Ausnahme ist das übertragbare Muster (F004, `altfeld_namen_sperre.test.ts` erlaubt als Vorlage: Kommentare zählen nicht, Treffer wortgenau).
- Zählstellen nach dem Löschen messen, nicht schätzen; Goldens/Elementliste per Projektwerkzeug, svelte-check-Baseline vorher.
- Die Katalogfälle der Mail-Fallliste dürfen nur auf existierende Tests verweisen (`tests/tdd/test_einstellung_gleich_mail_fallliste.py`, `_vitest_titel_gefunden`).

## Dependencies
- Rückwärts (wer braucht die lebenden Exporte): CompareTabs.svelte, compareHubHydration.ts, compareNewVorlage.ts. Die fünf lebenden Funktionen (`hydrateVersandFieldsFromPreset`, `hydrateDayWindowFromPreset`, `hydrateWeatherMetricsFromPreset`, `hydrateLayoutFieldsFromPreset`, `wetterMetrikenHydrationAbgeschlossen`) werden nicht angefasst.
- Vorwärts (was die toten Exporte brauchen): siehe Liste der Importe oben; alle haben andere Prod-Nutzer, keine neue Waise (geprüft per grep für `materializeActiveMetricKeys`, `merkeNutzlast`, `waehleEigenfelder`, `buildComparePresetSavePayload`, `rehydrateActiveMetrics`, `normalizeStoredActiveMetrics`, `compareChannelMetricLayouts.ts`).
- i18n: Beide Module enthalten keinen `t(`-Aufruf und keine Katalogschlüssel (grep leer). Es entfallen keine Katalogschlüssel; kein Katalog-Wächter (Paritäts- oder Ungenutzt-Prüfung) wird berührt.

## Existing Specs
- Vorbilder: rework_3383_waisen_s1.md, rework_3384_waisen_s4.md, rework_3385_waisen_s3.md (nennt #3389 im Tag-Feld).
- Herkunft der Module: rework_2276_s4_wetter_metriken.md, rework_2276_s5_versand.md, rework_2276_s6a_totcode_und_ratsche.md, rework_2276_s6e_versand.md (Ratschenzeilen :221/:534 historisch), rework_3366_waisen_waechter_layout_tab.md (Z. 149: „Tote Exporte in lebenden Dateien (`versandVergleichSpeicherung.ts`, `weatherMetricsCompareSave.ts`, …)“).
- Rework 3020: rework_3020_altbausteine_entfernen.md, rework_3020_testtabelle.md (referenziert keinen der Löschkandidaten; Gegenprobe per grep).

## Zählstellen (Datei, Zeile, aktueller Wert, betroffen?)
| Stelle | Wert heute | Betroffen? |
|---|---|---|
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts:318` `EINGEFROREN_SOLL_ANZAHL` | 10 | JA: sinkt auf 8. Die beiden Weichen `context === 'vergleich'` liegen in den toten Exporten `versandVergleichSpeicherungAktiv` (Eintrag `'versandVergleichSpeicherung.ts:236'`, Z. 235) und `wetterMetrikenVergleichSpeicherungAktiv` (Eintrag `'weather-metrics-tab/weatherMetricsCompareSave.ts:364'`, Z. 294). Beide Einträge raus, Anzahl senken, Bilanzkommentar (Z. 307-317, Muster „#3385: … Soll 13 → 10“) um Zeile „#3389 … Soll 10 → 8“ ergänzen, Titel des Falls Z. 435 („46 Einträge“, schon alt) lassen. Kein `BLEIBT_MIT_INHALT`-Eintrag betrifft die beiden Dateien. Kopfkommentare Z. 62, 84-86, 165, 177 nennen die alten Zeilen als Geschichte |
| `frontend/src/lib/__tests__/waisen_waechter.test.ts:55,65` `BEKANNTE_WAISEN` / `OBERGRENZE_WAISEN` | leer / 0 | nein (Datei-Ebene, beide Module bleiben erreichbar) |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts:707` `BESTAND_OBERGRENZE` | 162 | nein (listet `.svelte`-Bausteine; kein Eintrag nennt die beiden Module oder Gruppe-a/b-Tests) |
| `tests/unit/ein_katalog_ausnahmen.json:234` `hoechststand` und `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py:39` `HOECHSTSTAND` | 421 / 421 (im #3385-Kontext stand noch 422, seither gesunken) | nein: `scanne_frontend` über beide Module liefert 0 Funde (gemessen), kein Ausnahmen-Eintrag nennt sie; Tests und `__tests__` sind vom Scan ausgenommen |
| `.github/workflows/ci.yml:328` `E2E_MIN_SPECS` (und `E2E_MIN_EXECUTED*`) | 85 | nein: `frontend/e2e/hub-versand-speichert-selbst.spec.ts:29` nennt die Datei nur im Kommentar, keine E2E-Spec importiert die Module oder Prüfstände |
| `frontend/src/lib/__tests__/rework_3020_umfang.ts:59` `BLEIBT` (`weatherMetricsCompareSave.ts`) | enthalten; `RESTBESTAND_ANZAHL` 19, `SPEC_ANZAHL` 42, `DURCH_WAISEN_ENTFERNT` 23 | nein, solange die Datei bestehen bleibt (`rework_3020_rueckbau_waechter.test.ts:110` prüft, dass sie existiert und nicht im Umfang steht) |
| `rework_3020_probe_loeschung.test.ts` (`LEBENDE_HELFER_NUTZER` in `rework_3020_umfang.ts`) | 30er-Liste lebender Trip-/hub-kopf-Tests | nein: keiner der Gruppe-a/b-Tests steht darin |
| `rework_3020_rote_liste.ts` (G01-G60, E001-E145, 15 Katalog) | 60/145/15 | nein: E008 (fix_3061), E013/E014 (feat3276), E065/E066 (versand_vergleich_premium_sms) nennen die Dateien nur als Vergleichsnamen entfallener Fälle; der Wächter prüft dafür nur Mengen und Entscheide, nicht die Datei. Liste „nie kürzen“, nicht ändern |
| `docs/specs/modules/rework_3020_testtabelle.md` | – | nein (kein Beleg verweist auf Löschkandidaten; per grep geprüft) |
| `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json:637` | Fall `D-orte_vergleichstabelle-totalschnitt_aus_wirkt-frontend`, Status `ausnahme`, `test` = `…/wetter_metriken_nutzlast_verliert_keine_daten.test.ts::Kanal-Auswahl geändert → der Rumpf trägt nur Eigenfelder, keinen Altschluessel (#3276)` | JA: die Testdatei (Gruppe a) entfällt, der Verweis muss auf einen lebenden Test umgehängt werden (Prüfung `test_einstellung_gleich_mail_fallliste.py` „(b) jeder Fall nennt eine existierende Testfunktion“). Es ist der einzige Fall der Fallliste (`fallliste_editor.json`, `fallliste_sms.json` gegenprüfen) mit Verweis auf die Löschkandidaten. Anzahl `ausnahme` = 14 ändert sich nicht, wenn der Fall umgehängt statt gestrichen wird |
| Elementliste | – | nein: reine Logikdateien, keine Oberfläche; Projektwerkzeug trotzdem laufen lassen |
| Python-Tests mit TS-Pfaden | – | nur der Fall oben; sonst keine Python-Datei nennt die beiden Module, die Löschkandidaten oder die drei Prüfstände (grep über `tests/`, `.github/`, `scripts/`, `.claude/hooks`) |
| `frontend/src/lib/components/compare/__tests__/totcode_rueckbau_speicherweg.test.ts:114-118` | Liste `speicherModule` mit Positivkontrolle `'buildComparePresetSavePayload'` für beide Module | JA, siehe Risks 1 |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts:48,191` | `ERHALTEN`/`ERHALTEN_3383` enthalten `weatherMetricsCompareSave.ts` | nein (Datei bleibt); neuer Block `#3389` kommt dazu |

## Risks & Considerations
1. **Positivkontrolle in `totcode_rueckbau_speicherweg.test.ts` (Z. 114-132)** verlangt, dass `buildComparePresetSavePayload` im Text beider Module steht. Dieser Name kommt nur in toten Funktionen vor (versand Z. 152, weather Z. 113, 206 und Kommentare), nach dem Löschen wird der Test rot. Der Test prüft eigentlich nur, dass `buildHubPutPayload` nicht mehr vorkommt. Umbau: die beiden Einträge streichen oder Positivkontrolle auf einen lebenden Namen (`hydrateVersandFieldsFromPreset`, `hydrateDayWindowFromPreset`) setzen.
2. **Ratsche `context_herkunft_zweige_eingefroren`:** zwei der zehn eingefrorenen Weichen sind tote Exporte. Wird das übersehen, ist der Test in beide Richtungen rot (Ist < Soll, Soll-Anzahl). Das Muster aus #3385 (Soll 13 → 10) trägt; hier 10 → 8.
3. **Prüfstand `compareReiterAufbauPruefstand.ts` gleicht eine Reiter-Matrix ab** (`REITER` mit 4 Einträgen). Fällt die Hälfte weg, verlieren `compare_konflikt_nutzlast_am_eintrag`, `compare_reiter_nutzlast_nur_eigene_felder`, `compare_retry_fehlerpfade_kein_verlust`, `feat3298` Abdeckung für die „Zustellung“- und „Wetter“-Konsolidierung. Der gleichwertige Schutz liegt heute teils in `zustellungSpeicherung.ts` (lebend, Zustellungs-Speicherer) und `wertebereicheVergleichSpeicherung.ts`; Spec muss festlegen, was als Ersatz für die weggefallenen Reiter-Fälle gilt (nicht still Abdeckung verlieren, Leitfrage Adversary: ist die Zusicherung dort geprüft, wo sie wirkt?). Ein Wegfall von Testfällen, deren Zusicherung nur der tote Speicherer erfüllte, ist fachlich keine Abdeckungslücke, weil der Speicherer selbst nicht mehr existiert; Zusicherungen am lebenden Speicherer (Alarme, Wertebereiche, Zustellung) müssen aber erhalten bleiben.
4. **Der „Zustellungs“-Speicherer trägt die Versand- und Wetterfelder bereits.** Tote Speicherer sind durch `zustellungSpeicherung.ts` ersetzt (siehe Kommentare im Versand-Modul Z. 7ff und rework_2794 S3a). Wichtig für die Analyse: Es gibt kein Produkt-Verhalten, das an den toten Exporten hängt; die Gruppe-a-Tests prüfen also nichts Lebendes. Trotzdem prüfen, ob eine der Gruppe-a-Zusicherungen (z. B. „Pausieren direkt nach Änderung verliert nichts“, keepalive-Durchreichung, Datenerhalt-Teilfeld-Nutzlast) für den lebenden Speicherer noch einen Wirkort-Test hat; sonst eine Lücke nennen.
5. **Dynamischer Import:** `feat3298_vergleich_ohne_altfelder.test.ts:253` importiert das Weather-Modul dynamisch (Namensscan über `import(` reicht für die Wächter nicht, ein einfaches `grep "from '…weatherMetricsCompareSave"` übersieht ihn). Der Lösch-Nachweis muss auch `import(`-Formen und Pfadstrings (`trip_pfad…:48,191`, `totcode_…:116-118`, `rework_3020_umfang.ts:59`) prüfen. Sonst: keine String-Importe in Prod.
6. **Prüfstand-Reste:** `versandVergleichPruefstand.ts` bleibt wegen `createController` (≈27 lebende Nutzer) bestehen; `makePreset`, `hydrierterWiz`, `versandBedienung`, `dc` werden dort tot, in `wetterMetrikenVergleichPruefstand.ts` wird fast alles tot. Beide Dateien sind durch `__tests__/` bzw. `*Pruefstand.ts` von den Wächtern ausgenommen, also kein automatischer Hinweis: von Hand mit der Löschliste führen oder per Messung belegen.
7. **Kommentar-Nennungen:** Dutzende Kommentare und Specs nennen die toten Namen (z. B. `CompareTabs.svelte:851` „flushPendingLayoutSave“, `gates_und_ratschen.md:555-561`). Sie stören die Importscans nicht, aber ein Wortscan nach Basisnamen (wie F004 in #3385) schlägt auf Kommentare an, wenn er Kommentare nicht ausnimmt. Nur Kommentare in Prod-Dateien, die einen toten Namen als Funktion beschreiben, anpassen (`CompareTabs.svelte:851`).
8. **Aufräumen nach dem Löschen:** ungenutzte Importe in beiden Modulen (siehe Liste) entfernen; svelte-check-Baseline vorher messen. `lint` (CI) kann ungenutzte Importe anmahnen.
9. **Zählung im Issue:** 9 + 12 = 21 stimmt nur, wenn die Typen `VersandSnapshot` und `LayoutSnapshot` als „modulintern gebraucht“ nicht mitzählen. Beschluss nötig, ob sie ohne `export` bleiben oder weiter exportiert werden (extern nutzt sie keiner außer den Tests der Gruppe b).
10. **Gegenprobe-Aufgaben für den Adversary:** (a) Verfälschung `hydrateVersandFieldsFromPreset` (z. B. `morning_enabled`-Default kippen) muss rot werden — heute fängt sie `hub_versand_inline` (Gruppe b, bleibt) und `compare_versand_hydration_unter_wetter_metriken` (unberührt); (b) `hydrateLayoutFieldsFromPreset` wird nur von feat3298 und fix_3061 bewacht (beide Gruppe b); (c) `hydrateDayWindowFromPreset` hat gar keinen direkten Testimport, nur Aufrufer über CompareTabs — Lücke prüfen, vor dem Löschen der Nachbarn belegen.
