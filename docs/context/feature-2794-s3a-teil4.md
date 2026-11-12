# Context: feature-2794-s3a-teil4 (S3a Teil-PR 4, AC-31 bis AC-35)

## Request Summary
Letzter Teil von S3a (#2794, Epic #2791): Altkomponenten entfernen, Übersicht nachziehen (U3/U4), Listen-Sprünge und Hilfe-Texte auf die neuen Reiter, Glossar, Fresh-Eyes-Abgleich gegen Mockup Fassung 3. Maßgeblich: `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` Abschnitt „Teil-PR 4" (AC-31 bis AC-35) und Lieferplan Z.154ff. Am Ende Soll/Ist-Bild an den PO.

## Kernbefund (verändert den Zuschnitt von AC-31)
Viele „Altkomponenten" sind **keine tote Oberfläche**, sondern tragen den **Übergangsreiter Zustellung** (S3b noch offen) oder laufen **unsichtbar in den Anlege-Ketten**:
- `shared/WeatherMetricsTab.svelte` + `weather-metrics-tab/`: einziger Mount `WetterMetrikenVersandPanel.svelte` mit `bereich="zustellung"` (Zustellung-Reiter, TripNewEditor, CompareNewEditor). Liefert Layout je Kanal, Stundenverlauf, Ausblick, report_config, Nacht-Block, SMS-Schwellen. **Bleibt.**
- `shared/AlarmeTab.svelte` + `alarme-tab/`: Alarm-Baustein im Reiter Zustellung (Trip via `trip-detail/AlarmeScheduleTab.svelte`, Vergleich via `CompareTabs.svelte` Snippet `hubAlarme`), Anlege-Ketten. **Bleibt** bis S3b.
- `shared/layout-tab/`: Abschnitt Layout je Kanal in Zustellung. **Bleibt.**
- `alerts-tab/` (unter `components/`, nicht `shared/`): bleibt laut AC-31 ausdrücklich.
- `shared/corridor-editor/`: **Kein sichtbarer Mount mehr**, aber
  - `TripNewEditor.svelte:29/922/1188` und `CompareNewEditor.svelte:68-73/592/668` mounten ihn versteckt (`display:none`) für die Vorbelegung `corridors` (`handleVorbelegungFertig`) → Vorbelegung muss ohne UI-Komponente laufen (reine Logik).
  - `compareMetricCatalogLoader.ts` wird vom neuen Reiter gebraucht (`organisms/wetter-tab/WetterTabInhalt.svelte:20`) → umziehen.
  - `wertebereicheVergleichSpeicherung.ts` (`sichereSelbstSpeichererVorReiterwechsel`) in `CompareTabs.svelte:90/183`.
  - Typ `IdealRange` aus `corridorEditorState.ts` in `compareEditorSave.ts:11`, `compareHubHydration.ts:20`, `corridorPropsAus.ts:32`.
- **Sofort löschbar (nur Re-Exports, kein Mount):** `trip-detail/MetricCheckbox.svelte`, `trip-detail/MetricGroup.svelte`, `ui/horizon-chip/HorizonChip.svelte`, `molecules/HorizonChips.svelte`, `organisms/MetricsEditorContextBar.svelte` (Barrels `organisms/index.ts:19-20,33`, `trip-detail/index.ts:8-9`, `molecules/index.ts:39`).
- Vom neuen Reiter gebraucht aus `weather-metrics-tab/`: `SavePresetDialog.svelte` (`VorlageKarte.svelte:10`), Typ `compareMetricSelection` (`WetterTabInhalt.svelte:21`). `DayWindowCard.svelte` hängt nur noch an `WeatherMetricsTab.svelte:122`.

## Related Files
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/subscriptionTabs.ts:43-66,120-135` | `REITER_DEFINITION` (4 Reiter), `LEGACY`-Umleitungen — bleiben |
| `shared/hub-uebersicht/hubUebersichtModell.ts:99,133,253-260` | Versand-Ziel, `tripWetterAlarmAktiv()` (ohne `alarm_ab`), `wertebereicheKarte()` → `tab:'wetter'` aber Eyebrow `aktionen.reiter.wertebereiche` |
| `shared/hub-uebersicht/HubUebersicht.svelte:140,163` | Rendert Übersichtskarten |
| `trip-detail/HubOverview.svelte:121,143,150` | „Wetter-Metriken", „bei Δ" (`trip.uebersicht.bei_delta`) → U4 „Alarm ab" |
| `shared/subscriptionActions.ts:40-41` | Listen-Aktionen `alarms`/`weather` |
| `routes/trips/+page.svelte:109-110`, `routes/compare/+page.svelte:125-126`, `routes/+page.svelte:293-471` | Listen-/Startseiten-Sprünge (zeigen bereits auf neue Kennungen) |
| `i18n/messages/{de,en}/{aktionen,hilfe,layout,alarme,bausteine,vergleich,trip,home,wertebereiche}.json` | Alte Reiternamen in Texten (Details siehe Analyse) |
| `routes/hilfe/+page.svelte:43-45` | Hilfe-Seite |
| `shared/infoboxKeys.ts:11-31`, `lib/utils/cockpitHelpers568.ts:120` | Info-Abschnitte und Startklar-Checkliste mit alten Namen |
| `docs/reference/i18n_glossar.md:24,185-195` | Glossar: neue Begriffe stehen schon, „Wertebereiche" Z.24 soll weg |
| `frontend/src/lib/i18n/__tests__/*` | Wächter: hartkodierte Texte, Parität, Glossar, Schlüssel ohne Verwender, `deutsch_unveraendert` |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` | Mockup Fassung 3 (AC-35) |
| `docs/reference/gates_und_ratschen.md:113ff` | Pendant-Gate (`pendant_gate.py`) |

## Existing Patterns
- Reiter-Kennungen und Umleitung zentral in `subscriptionTabs.ts`; Alt-Kennungen werden umgeleitet (E2E `hub-reiter-alt-kennungen-umleitung` bleibt).
- Trip/Vergleich-Teilung: je Funktion eine Komponente unter `organisms/wetter-tab/` bzw. `shared/` mit `context`. Echte Pendants für die sieben AC-35-Funktionen wurden nicht gefunden; Compare-seitige Reste sind Prop-Bündel (`compare/*PropsAus.ts`).
- Texte nur über Katalog; Wächter-Tests erzwingen Parität und Verwendung.

## Dependencies
- Upstream: neuer Reiter Wetter (Teil 3, live), `alerts-tab/alarmAbAnzeige.ts`, `shared/wetter-tab/wetterTabSpeicherung.ts` → `tripSpeicherung.ts`.
- Downstream: Anlege-Ketten (TripNewEditor, CompareNewEditor), Reiter Zustellung (S3b), Übersicht, Listen.

## Existing Specs
- `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` (Gesamt-Spec, freigegeben in den Teilen)
- `feat_2794_s3a_teil2_leiste.md`, `feat_2794_s3a_teil3_wetter.md`
- Parallel: `feat_2913_scheibe_c_wetter_rest.md` (#2913, andere Sitzung, Phase 6)

## Risks & Considerations
- **Zuschnitt AC-31:** Wörtlich „keine Oberfläche mehr für … Zeithorizont-Chips und die Metrik-Checkbox" ist erfüllbar; „Corridor-Editor" heißt Komponente weg, Logik (Vorbelegung, Katalog-Loader, Typ `IdealRange`, Selbstspeicherer) muss umziehen. „Reiter Alarme" ist als Reiter schon weg; `AlarmeTab` als Baustein des Reiters Zustellung bleibt (wie `alerts-tab/`) — das ist mit AC-31 vereinbar, muss in der Detail-Spec explizit stehen.
- **Kollision mit #2913 (parallele Sitzung):** gemeinsame Dateien `molecules/index.ts`, E2E `speicherung-ueberlebt-neuladen`, `daywindow-*`, `s3a2794-teil3.helpers.ts`. Nur `organisms/wetter-tab/*` von #2913 nicht anfassen; Rebase nach deren Merge.
- **Testumzug:** ~239 Frontend-Unit-, 63 E2E-, 53 Python-Dateien referenzieren Alt-Namen; nur Tests rein entfallener Oberflächen löschen, Rest umstellen. Viele betreffen Komponenten, die bleiben → kein Umzug nötig.
- **Golden-HTML** (`tests/golden/f5_wertebereiche`, `f8_layout_korridor`, …) evtl. betroffen.
- Mandantentrennung: kein neuer Datenweg; Vorbelegung beim Anlegen muss weiter mit echtem Nutzer laufen.
- Der in Issue-Kommentar genannte Worktree `imperative-discovering-dragon` existiert nicht mehr (Fix-Loop 6 ist über PR #2920 live).

## Analysis

### Type
Feature (Abschluss S3a, Teil-PR 4: AC-31 bis AC-35)

### Stand vor Beginn
- #2913 ist gemergt (Fix-Loop 1 in `origin/main`, `HEAD..origin/main` leer). Kollisionswarnung oben ist erledigt; `organisms/wetter-tab/` wird nur bei Importpfaden angefasst (`WetterTabInhalt.svelte:20/21`, `VorlageKarte.svelte:10`).

### Entscheidung Zuschnitt (Tech Lead): zwei Lieferschritte
- **4a Entfernen/Umzug** (keine sichtbare Änderung, hohes Funktionsrisiko beim Anlegen) → eigener PR, abgenommen per Zwei-Nutzer-Anlege-E2E auf Staging.
- **4b Übersicht/Texte/Glossar/Fresh-Eyes** (sichtbar, Text- und Mockup-Abnahme) → zweiter PR.
- Gründe: Rollback der Vorbelegung nicht an Texte koppeln; Rename-Diff (~5000 Zeilen) verdeckt sonst Übersicht/Texte; jeder Schritt einzeln lauffähig. Spec bekommt die Zuordnung AC-31 → 4a, AC-32..AC-35 → 4b (AC-34 Querschnitt in beiden).

### Affected Files (with changes)
| Datei | Change | Beschreibung |
|---|---|---|
| `trip-detail/MetricCheckbox.svelte`, `trip-detail/MetricGroup.svelte`, `ui/horizon-chip/HorizonChip.svelte` (+`HorizonChip.test.ts`, `index.ts`), `molecules/HorizonChips.svelte`, `organisms/MetricsEditorContextBar.svelte` | DELETE (4a) | Reine Barrel-Re-Exporte, kein Mount |
| `organisms/index.ts:19-20,33`, `trip-detail/index.ts:8-9`, `molecules/index.ts:39` | MODIFY (4a) | Barrel-Zeilen raus |
| `molecules/issue_578_molecules_organisms.test.ts:242-244`, `lib/__tests__/bausteine_waechter_regeln.ts:617,618,664,743,760`, `context_herkunft_baseline_ausserhalb_shared.test.ts`, `trip-detail/__tests__/f9Pruefstand.ts`, `e2e/issue-343-horizon-chips.spec.ts` | MODIFY/DELETE (4a) | Tests/Wächter der entfallenen Komponenten |
| `shared/corridor-editor/corridorEditorState.ts` (872), `compareMetricCatalogLoader.ts` (309), `wertebereicheVergleichSpeicherung.ts` (274), `__tests__/wertebereicheVergleichPruefstand.ts`, `corridorEditorState.test.ts` | MOVE (4a) | nach `shared/wetter-tab/` (dort liegt schon `wetterTabSpeicherung.ts`); Namen bleiben (reiner Umzug, keine Logikänderung) |
| `shared/corridor-editor/corridorMatch.ts` (+Test) | DELETE (4a) | einziger Verwender `CorridorEditorMobile.svelte:40` |
| ~90 Importzeilen (u. a. `compareEditorSave.ts:11`, `compareHubHydration.ts:20`, `corridorPropsAus.ts:32`, `alarmeVergleichSpeicherung.ts:16`, `versandVergleichSpeicherung.ts:16`, `compareMetricOrder.ts:16`, `weatherMetricsCompareSave.ts:27`, `wertebereicheAnzeige.ts:11`, `WeatherMetricsTab.svelte:136`, `CompareTabs.svelte:62/90`, Wächter-Allowlists `keine_hartkodierten_nutzertexte.test.ts:416-471`, `reaktivitaet_waechter.test.ts:55`, `harte_farben_waechter`, `ink4_waechter`, Flush-Wächter) | MODIFY (4a) | Pfad `corridor-editor/` → `wetter-tab/` |
| `shared/wetter-tab/anlegeVorbelegung.ts` + `__tests__/anlege_vorbelegung.test.ts` | CREATE (4a) | Reine Funktionen für Vorbelegung `corridors` (Trip: aus `buildRoutePrefillRows`; Vergleich: aus `belegeWertebereicheVor`/`buildComparePrefillRows`) |
| `trip-new/TripNewEditor.svelte:29,154,204-217,502,536,922,1188` | MODIFY (4a) | Versteckte Mounts raus; Vorbelegung als einmaliger `$effect` nach Katalog + Metriken; Fertig-Signal auf jedem Ausgang |
| `compare-new/CompareNewEditor.svelte:42,68-69,84,427-437,588-592,668` | MODIFY (4a) | Versteckte Mounts raus; `isFreshCompareCreate`- und `syncToWizard`-Verhalten als Logik erhalten |
| `shared/corridor-editor/CorridorEditor.svelte` (645), `CorridorEditorMobile.svelte` (580), `__tests__/*` (Komponententests, 6 Dateien), `corridorEditorMobile.test.ts` | DELETE (4a) | Oberfläche Wertebereiche |
| `compare/corridorPropsAus.ts` | MODIFY/DELETE (4a) | schrumpft oder entfällt |
| E2E: `hub-wertebereiche-speichert-selbst`, `hub-wertebereiche-wertprops`, `issue-718-idealwert-validation`, `compare-editor-slice3`, `compare-hub-inline-edit`, `begriff-erklaerung`, `design-system-trip-vergleich`, `epic-138-block-b`, `issue-616-trip-one-surface`, `speicherung-ueberlebt-neuladen` u. a. | MODIFY/DELETE (4a) | Je Datei: entfallene Oberfläche → löschen; Verhalten das bleibt → auf Reiter Wetter umstellen |
| `shared/hub-uebersicht/hubUebersichtModell.ts:133,253-260` | MODIFY (4b) | U3: Eyebrow `aktionen.reiter.wertebereiche` → Wetter-Begriff (Ziel ist schon `wetter`); `tripWetterAlarmAktiv()` berücksichtigt `alarm_ab` |
| `trip-detail/HubOverview.svelte:121,124,143,150` | MODIFY (4b) | U4: „bei Δ" → Text über „Alarm ab" (aus `alerts-tab/alarmAbAnzeige.ts`); Eyebrow/Link-Texte „Wetter-Metriken" → Wetter |
| `i18n/messages/{de,en}/{hilfe,layout,alarme,aktionen,home,trip,vergleich,wertebereiche,bausteine}.json` | MODIFY (4b) | Alte Reiternamen raus (Inventar: `hilfe.alarme.*`, `layout.korridor.einleitung_route`, `alarme.metriken.keine_gewaehlt`, `alarme.tabelle.leer`, `alarme.vorschau.*`, `alarme.alarm_ab.umbau_hinweis`, `alarme.kanaele.kein_empfaenger` („Versand"), `aktionen.weather/alarms` (nur Text, Schlüssel bleibt – `s3a2794_reiter_definition.test.ts:111`), `aktionen.reiter.wertebereiche`, `aktionen.uebersicht.uhrzeiten_festlegen`, `home.aktion.metriken(_ziel)`, `trip.uebersicht.*`, `trip.anlegen.alle_gpx`, `vergleich.neu.profil_hinweis/wetter_metriken`, `wertebereiche.vergleich.titel`, `bausteine.checkliste.layout/wertebereiche`, `tip.aria.wertebereiche`, `info.*`); Schlüssel ohne Verwender nach 4a löschen |
| `shared/infoboxKeys.ts:11-43`, `utils/cockpitHelpers568.ts:73,120-121`, `routes/hilfe/+page.svelte:43-45`, `routes/+page.svelte:297-298` | MODIFY (4b) | Info-Abschnitte, Startklar-Checkliste, Hilfe, Startseite |
| `docs/reference/i18n_glossar.md:24` | MODIFY (4b) | „Wertebereiche" raus; neue Begriffe stehen schon Z.185-195 |
| `i18n/__tests__/keine_alten_reiternamen.test.ts` | CREATE (4b) | AC-33: kein Nutzertext DE/EN nennt Wertebereiche/Alarme/Layout/Wetter-Metriken/Versand als Reiter |
| Golden `tests/golden/f5_wertebereiche`, `f8_layout_korridor`, `f9_trip_flaechen`, `f10_vergleich_flaechen`, `f3_home_listen/cockpit_planung` | MODIFY (4a/4b) | Neu schreiben (`GZ_GOLDEN_SCHREIBEN`), Prüfstände anpassen; `f7_alarme_tab` bleibt |
| `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` §7 + Lieferplan | MODIFY (Spec) | `AlarmeTab`/`alarme-tab/`/`AlarmeScheduleTab` und `WeatherMetricsTab`/`layout-tab/` bleiben bis S3b (tragen Zustellung); Teilung 4a/4b |

### Scope Assessment
- 4a: ~15 Dateien gelöscht, 5 umgezogen, ~90 Importzeilen, ~150 LoC neu, 2 Editoren angepasst; netto ca. −1500 bis −2000 LoC.
- 4b: ~20 Dateien, unter ±300 LoC, plus Golden-Neuschrieb und Fresh-Eyes.
- Risk Level: **MEDIUM** (4a HIGH an einer Stelle: Vorbelegung beim Anlegen; Rest mechanisch).

### Technical Approach
Reihenfolge 4a: (1) Re-Exporte löschen → (2) Logikmodule nach `shared/wetter-tab/` umziehen (mechanisch, `svelte-check`) → (3) Vorbelegung als reine Funktion, TDD mit `node --test`, Fixtures aus `corridorEditorState.test.ts`; Orchestrierung als einmaliger `$effect` in beiden Anlege-Editoren (Katalog `/api/metrics` und `catalogLoaded` gibt es dort schon: `TripNewEditor.svelte:204-207`, `CompareNewEditor.svelte:438ff`) → (4) erst dann `CorridorEditor`/`CorridorEditorMobile` samt vier versteckten Mounts löschen.
Zu erhalten (Pflicht-Invarianten, gehören als ACs in die 4a-Spec):
- Trip: `corridors` landet im POST; „Mit Standardwerten speichern" (`defaultsBereit`) wird freigegeben, auch bei `weatherMetrics.length === 0`; Fertig-Signal genau einmal, auch ohne Vorbelegung.
- Vergleich: Vorbelegung nur bei leeren `wiz.corridors` (heute `isFreshCompareCreate`), keine Überschreibung von Nutzereingaben beim Reiterwechsel; `idealRanges`/`activeMetricKeys`/`metricAlertLevels` wie heute im Wizard-Zustand.
- Mobil/Desktop-Wechsel belegt nicht doppelt vor (heute Mount-XOR; künftig ein Effekt).
- Mandantentrennung: kein neuer Datenweg; Anlege-E2E mit zwei Nutzern.
4b: Pendant-Gate (`pendant_gate.py`) zuerst laufen lassen (AC-35), dann U3/U4, Texte, Glossar, Wächter-Test AC-33, Golden neu, Fresh-Eyes Desktop+Mobil gegen `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`, Soll/Ist-Bild an PO.

### Dependencies
- Upstream: Reiter Wetter (Teil 3 + #2913, live), `alerts-tab/alarmAbAnzeige.ts`, `shared/wetter-tab/wetterTabSpeicherung.ts`.
- Downstream: Anlege-Ketten Trip/Vergleich, Reiter Zustellung (S3b, bleibt unberührt), Übersicht, Listen, Startseite, Hilfe.

### Befunde gegen den Plan
- Spec §7 nennt `AlarmeTab`/`alarme-tab/`/`AlarmeScheduleTab` als zu entfernen — widerspricht dem Zustellung-Reiter, der sie mountet. Spec wird nachgeführt (AC-31 spricht nur vom Reiter Alarme, der schon weg ist), nicht der Code.
- Python-Testdateien mit Namens-Treffern (`tests/tdd/test_corridor_*`, `test_compare_metric_catalog_endpoint.py` u. a.) betreffen Backend, nicht die Oberfläche → kein Umzug erwartet; in 4a einzeln bestätigen.

### Open Questions
- [x] Zuschnitt 4a/4b → Tech-Lead-Entscheidung, siehe oben.
- [ ] Wortlaut der Menü-Einträge `aktionen.alarms` („Alarme") / `aktionen.weather` („Wetter-Metriken") in Listen: Vorschlag „Alarme" bleibt als Funktionsname (zeigt auf Zustellung), „Wetter-Metriken" → „Wetter". Wird mit der 4b-Spec zur Freigabe vorgelegt (kein Extra-Halt).

## TDD RED (Phase 5, 2026-11-12) — Übergabe an /50-implement (nur Schritt 4a)
- RED-Tests: `frontend/src/lib/components/shared/wetter-tab/__tests__/anlege_vorbelegung.test.ts` (AC-43–45) und `.../s3a2794_teil4a_umzug_waechter.test.ts` (AC-31, AC-45 AST, AC-46, AC-47). 22 rot, 9 grün (Bleibe-Bausteine und Fallback-Wächter als Regressionsschutz).
- Vertrag `shared/wetter-tab/anlegeVorbelegung.ts`: `tripVorbelegung({metrics, extraDefs, vorhandeneCorridors}) → Corridor[]|null`; `erstelleTripVorbelegungsLauf({onCorridors, onFertig})` mit `.versuchen({extraDefs, metrics, vorhandeneCorridors})` und `.fertig` (wartet auf extraDefs≠null und nicht-leere metrics, dann genau einmal: erst Korridore, dann Fertig, auch ohne Vorbelegung); `vergleichVorbelegung(wiz, defs) → {corridors, idealRanges, activeMetricKeys, metricAlertLevels}|null` (null bei isEditMode, nicht-leeren corridors, leerer Prefill). Referenz = alter Editor: `buildCorridorSavePayload(buildRoutePrefillRows(...), {}, [])` bzw. `belegeWertebereicheVor` in CompareNewEditor.
- Je Editor genau EIN `$effect` nennt die importierten Vorbelegungs-Namen (bzw. die daraus gebaute Lauf-Variable); `belegeWertebereicheVor` im Standardwerte-Handler soll auf `vergleichVorbelegung` umgestellt werden (Funktion, kein Effekt).
- Im Implement mit umzustellen (heute an CorridorEditor-Einbettungen gemessen): `trip-new/__tests__/standardwerte_wartet_auf_wertebereiche_vorbelegung.test.ts`, `trip_new_editor_weather_metrics_wiring.test.ts`, `shared/__tests__/compare_new_editor_postet_einmal.test.ts`, `corridor_editor_create_mode_route.test.ts` (entfällt mit dem Editor; Gegenstück jetzt anlege_vorbelegung).
- Umzug-Wächter verlangt: kein Import mit `corridor-editor/` in `frontend/src` und `frontend/e2e`, Ordner `shared/corridor-editor/` weg, Barrels ohne entfernte Komponenten.
