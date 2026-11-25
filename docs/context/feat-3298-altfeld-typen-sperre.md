# Context + Analyse: #3298 Altfeld-Typen entfernen und Frontend-Sperre scharf schalten

Stand 25.11.2026, Basis `origin/main` nach #3276/#3277/#3297/#3301. Nur lesend erhoben.

## Request Summary

Epic #3122 (Spec AC-38 zweiter Teil). Die Altfeld-Namen aus dem Produktions-Frontend (`frontend/src`, ohne Tests) entfernen und
per Text-Scan-Test unter `node --test` dauerhaft sperren (ERLAUBT-Tabelle mit Grund + Ablaufdatum, Selbstnachweis).
Ergaenzung Kommentar 25.11.: `outlook_enabled` (ADR-0124 Nr. 6, ersetzt durch `placements.outlook_reports`) wird noch
round-getrippt und kommt mit raus und in die Sperre. Abgrenzung Kommentar 12:38: #3020 R2 loescht `hourlyFriendlyMap.ts`
(`compareHourlyMetricDefs.ts` ist schon weg durch #3301). Datenlauf #3351 folgt danach.

## Related Files (Produktionscode, Fundstellen; Pfade unter `frontend/src/lib/`)

L = lesend, S = schreibend, T = Typ, K = nur Kommentar.

| Datei:Zeile | Name | Art | Wirkung heute |
|---|---|---|---|
| `types.ts:284-285` | `multi_day_trend_morning/evening` | T | tot, kein Leser/Schreiber; NICHT in ALTFELDER |
| `types.ts:326-327` | `channel_layouts`, `channel_layouts_per_report` | T | nur Typ im `DisplayConfig` |
| `types.ts:338,342` | `outlook_metrics`, `outlook_metric_formats` | T | nur Typ, keine Wirkung |
| `types.ts:749-750` | `channel_layouts`, `hourly_metric_formats` | K | Kommentar am `display_config` (Record) |
| `types.ts:755` | `outlook_enabled` | T | Typ am `ComparePreset`; Leser/Schreiber s. u. |
| `components/shared/pickEigenfelder.ts:75,78,79` | `channel_layouts`, `outlook_metrics`, `outlook_metric_formats` | S (Whitelist) | `WETTER_DISPLAY_KEYS`; einziger Aufrufer `compare/compareEditorSave.ts:290/292`; muss raus |
| `components/compare/hourlyFriendlyMap.ts:24` | `hourly_metric_formats` | K | Modul ohne Produktionsaufrufer (nur Test `compare_hourly_metric_formats_persistenz.test.ts`); #3020 R2 loescht es |
| `components/compare/subscriptionHelpers.ts:275` | `channel_layouts` | K | Historienkommentar |
| `components/compare/compareEditorSave.ts:24,124,150-152,458-460` | div. Altnamen | K | Kommentare ueber bereits entfernte Logik |
| `compareEditorSave.ts:52,186-187,322,398,518,565,604` | `outlook_enabled` / `outlookEnabled` | S | Edits-Feld, Body-Spread (187), Teilfeld-Body (398), Wizard-Feldsatz; geht als Top-Level-Key an Go, Python verwirft ihn (ALTFELDER) -> toter Round-Trip |
| `compareEditorSave.ts:499-505,553-556` | `hourlyMetricKeys`, `outlookMetricKeys`, `outlookMetricFormats`, `hourlyMetricFormats` | Zustand | camelCase-Wizardfelder, nie mehr geschrieben (Kommentare 46-47, 359-360), nur Startwert `null` |
| `components/compare/CompareTabs.svelte:574-582` (580 = outlookEnabled), 534 | Zustand | L | Hydration aus `hydrateLayoutFieldsFromPreset` bzw. `hydrateChannelActiveMetricsFromPreset`; Werte werden nie gespeichert |
| `components/compare-new/compareNewVorlage.ts:55,57` | Zustand | L | dieselben Hydrationen beim Anlegen aus Vorlage |
| `components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:94` | `channel_active_metrics` | L | `hydrateChannelActiveMetricsFromPreset` |
| `weatherMetricsCompareSave.ts:133-140` | `hourly_metrics`, `outlook_metrics`, `outlook_metric_formats`, `hourly_metric_formats`, `outlook_enabled` | L | `hydrateLayoutFieldsFromPreset`; Backend liefert sie nach #3277 nicht mehr, Lesen ergibt immer `null`/Default |
| `weatherMetricsCompareSave.ts:104-119,158-172,176-195,206-218,245-250,262-301,333` | camelCase + `outlook_enabled` | S/Zustand | `LayoutSnapshot`, `flushPendingLayoutSave`, `rollbackLayoutSnapshot`, `WETTER_TOP = ['hourly_enabled','outlook_enabled']` (265), 172: `outlook_enabled` wird aktiv geschrieben |
| `components/shared/weather-metrics-tab/compareChannelMetricLayouts.ts:40,61` | `channel_active_metrics` | K + Lese-Naht | `compareChannelActiveMetricsFromStored` |
| `components/shared/alarmeVergleichSpeicherung.ts:171`, `versandVergleichSpeicherung.ts:172`, `wetter-tab/wertebereicheVergleichSpeicherung.ts:77` | `preset.outlook_enabled` | L | reicht den Wert nur in `outlookEnabled` des Wizard-Felds weiter |
| `components/shared/alarme-tab/alarmeDeliveryPayload.ts:41` | `channel_layouts` | K | Kommentar |
| `utils/cockpitHelpers568.ts:93` | `channel_layouts` | K | Kommentar |

Nicht (mehr) in Produktionscode: `show_outlook`, `multi_day_trend_reports`, `compareHourlyMetricDefs.ts` (geloescht #3301).
Test-/Pruefstand-Dateien mit den Namen (Fixtures, nicht Teil der Sperre): `components/shared/__tests__/{goMergeServerPruefstand,versandVergleichPruefstand}.ts`, `weather-metrics-tab/__tests__/wetterMetrikenVergleichPruefstand.ts`, `trip-detail/__tests__/tripMehrreiterPruefstand.ts`, `shared/zustellung-tab/__tests__/zustellungTabDaten.ts`, `layout-tab/__tests__/f8KatalogAnker.ts`.

## Zu 2: `hourly_metrics` und Co. noch fachlich gebraucht?

- `src/app/loader.py:142-147` `ALTFELDER` enthaelt ALLE zehn Namen inkl. `hourly_metrics`, `hourly_metric_formats`, `outlook_enabled`. `altfelder_entfernen` wirft sie in `display_config`, `report_config` und oberster Ebene beim Schreiben weg. Gespeichert wird also keiner mehr, das Frontend-Lesen liefert leer.
- Lebend nur als Renderer-interne Parameter: `src/services/report_config_resolver.py:361-376` (View-Model aus `placements`) und Validator-Vorschau `validator_render_service.py:481-491`; beide stehen in `tests/test_altfeld_namen_sperre.py` ERLAUBT (bis 23.02.2027). Das Frontend greift darauf nicht zu.
- `compareEditorSave` behaelt `hourly_metrics` nur ueber den `...baseDisplayConfig`-Spread (Bestandsdaten, #3301 AC-3); der Name steht im Code nur in Kommentaren.
- Entscheidung: alle zehn Namen in die Sperre, keine Ausnahme fuer `hourly_metrics`. `hourly_enabled` (nicht in ALTFELDER) bleibt unberuehrt.

## Zu 3: Verwaiste Module (transitiver Import-Check ab `src/routes`, Skript im Scratchpad, nur Produktionsdateien)

Ohne Produktionsaufrufer erreichbar: `hourlyFriendlyMap.ts`, `WeatherV2Grundauswahl.svelte`, `WeatherV2PresetBar.svelte`, `nurEinBericht.ts`, `outlookFriendlyCapability.ts`, `AggregationMetricRow/MultiSymbolMetricRow/ThresholdMetricRow.svelte`, `compareAggregationGrouping.ts`, `wertebereicheAnzeige.ts`, `trip-detail/WeatherV2Kanaele.svelte`, `weatherSaveGate.ts`, `AboutOutputLayout.svelte`, in `shared/layout-tab/` LayoutTab/LTCapNote/LTChannelPicker/LTCutLine/`channelLayoutsDirty.ts`/`ltIdealRange.ts` (`ltChannels.ts` bleibt lebend), `shared/reportConfigDirty.ts`, `versand-tab/VT{BriefingChannels,LaufzeitRoute,LaufzeitVergleich,NextBriefing,SchedulePlan}.svelte` samt `channelContactLabel/premiumSmsChannelState/sendTargetLabel/vtBriefingChannelsText.ts`, `compare/{versandPropsAus,wetterMetrikenPropsAus,layoutPreviewRows}.ts`, `edit/Edit*Section.svelte`. Das Skript meldet zusaetzlich `ui/*`, `mobile/*` als unerreichbar (Barrel-/Alias-Rauschen, nicht belastbar). Altfeld-Bezug haben davon nur `hourlyFriendlyMap.ts` (Kommentar) und `channelLayoutsDirty.ts`/`LayoutTab` (Name `channel_layouts` ggf. in Kommentaren; Scan nach Kommentar-Strip ohne Treffer).
Empfehlung: `hourlyFriendlyMap.ts` gehoert zu #3020 R2, hier nicht anfassen. Der uebrige Verwaisten-Block (ueber 40 Dateien, Svelte mit eigenen Tests, kein Altfeld-Bezug) wird ein eigenes Aufraeum-Issue im Epic #3122.

## Existing Patterns (Sperre)

- `tests/test_altfeld_namen_sperre.py` (#3277): ERLAUBT = `{(Datei, Name): (Grund >= 20 Zeichen, Ablaufdatum)}`; abgelaufen oder zu kurzer Grund = rot; Kommentare zaehlen nicht; `ALTFELD_NAMEN` (10); zentrale Liste `ALTFELDER` ausgenommen; Selbstnachweis mit synthetischem Quelltext (Verstoss erkannt, erlaubter Eintrag besteht, Ablauf schlaegt an, zu kurzer Grund abgelehnt). Ablauf dort 23.02.2027.
- `tests/test_altpfad_import_sperre.py`: Importsperre nach gleichem Muster.
- `frontend/src/lib/issue_523_suggested_flag_cleanup.test.ts`: `node:test` + `readFileSync`, `ROOT = fileURLToPath(new URL('../../..', import.meta.url))`; Lauf ueber `package.json` `test`-Skript (`node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test`).
- Empfohlener neuer Test: `frontend/src/lib/altfeld_namen_sperre.test.ts`. Dateimenge rekursiv `frontend/src`, `.ts/.svelte/.js`; ausgeschlossen `__tests__/`, `*.test.ts`, `*Pruefstand.ts`, `*Anker.ts`, `bausteine_waechter_regeln.ts`. Kommentare (`//`, `/* */`, `<!-- -->`) vor dem Scan entfernen (wie Backend), sonst erzwingen die vielen Historienkommentare Ausnahmen; wortgenau (`\bname\b`), snake_case. Selbstnachweis: Verstoss erkannt, Kommentar-Treffer nicht, `hourly_enabled` kein Treffer, ERLAUBT gueltig/abgelaufen/zu kurzer Grund.

## Dependencies

- #3276, #3277, #3297, #3301 live. #3351 (Datenlauf) folgt nach #3298.
- Go reicht `report_config`/`display_config` als Map durch (Echo); Python verwirft Altschluessel beim Schreiben. Bestandsdaten koennen sie vor dem Datenlauf noch enthalten; das Frontend darf sie nur durch Spread/Roh-Weitergabe tragen.

## Existing Specs

`docs/specs/modules/feat_3122_was_steht_wo.md` (AC-38), `feat_3276_vergleich_altfelder_entfernen.md`, `feat_3277_altfelder_entfernen.md`, `feat_3297_trip_pfad_ohne_altfelder.md`; Kontexte `docs/context/feat-3277-altfelder-entfernen.md`, `feat-3297-trip-pfad-ohne-altfelder.md`; ADR-0124 Nr. 5/6.

## Risks & Considerations

1. Signaturen: `hydrateLayoutFieldsFromPreset`, `LayoutSnapshot`, `flushPendingLayoutSave`, `rollbackLayoutSnapshot`, `wetterMetrikenSnapshotAus` haben viele Tests (Pruefstaende); Entfernen der camelCase-Felder zieht Testanpassungen nach.
2. `outlook_enabled` wird aktiv geschrieben (`weatherMetricsCompareSave.ts:172,265`, `compareEditorSave.ts:187,398`): Das PUT-Payload aendert sich, Python verwirft den Schluessel aber ohnehin, also keine Verhaltensaenderung; Erwartungen wie `goMergeServerPruefstand.ts:283` anpassen.
3. Bestandsdaten: nur weglassen, nie `delete`, nie leer senden (Read-Modify-Write, CLAUDE.md Daten-Schema-Reworks).
4. `ChannelLayouts`/`ChannelLayoutsPerReport` (types.ts): pruefen, ob sonst genutzt (Trip-Seite), sonst mit loeschen.
5. Wortgrenzen: `hourly_enabled` darf nicht anschlagen.

## Analysis

### Ansatz
1. Produktionscode bereinigen (nur weglassen):
   - `types.ts`: `multi_day_trend_morning/evening`, `channel_layouts`, `channel_layouts_per_report`, `outlook_metrics`, `outlook_metric_formats` aus den Typen, `outlook_enabled` aus `ComparePreset`; Kommentar 749-750 ohne die Namen.
   - `pickEigenfelder.ts`: `WETTER_DISPLAY_KEYS` auf `metrics, preset_name, telegram_kurzform, show_night_block, ampel`.
   - `weatherMetricsCompareSave.ts`: `hydrateLayoutFieldsFromPreset`/`LayoutSnapshot`/Flush/Rollback/`WETTER_TOP`/`felderListe` nur noch `hourlyEnabled`; `hydrateChannelActiveMetricsFromPreset` samt Lese-Naht `compareChannelActiveMetricsFromStored` entfernen (Aufrufer `CompareTabs.svelte:534`, `compareNewVorlage.ts:55`).
   - `compareEditorSave.ts`: `outlookEnabled` aus Edits/Fields/Feldsatz/Wizard-Abbild, camelCase-Wizardfelder 499-505/553-556 raus; `CompareTabs.svelte:574-582` kuerzen; die drei `*VergleichSpeicherung.ts` ohne `outlookEnabled`.
2. Neuer Test `altfeld_namen_sperre.test.ts` wie oben; zusaetzlich Abgleich seiner Namensmenge gegen `ALTFELDER` in `src/app/loader.py`, damit beide nicht auseinanderlaufen.
3. Bestehende Tests/Pruefstaende nachziehen (Fixtures duerfen Altnamen behalten, nur Erwartungen auf entfernte APIs anpassen).

### Betroffene Dateien
Prod (ca. 11): `types.ts`, `pickEigenfelder.ts`, `weatherMetricsCompareSave.ts`, `compareChannelMetricLayouts.ts`, `compareEditorSave.ts`, `CompareTabs.svelte`, `compareNewVorlage.ts`, `alarmeVergleichSpeicherung.ts`, `versandVergleichSpeicherung.ts`, `wertebereicheVergleichSpeicherung.ts`, ggf. `compareHubHydration.ts`/`wetterMetrikenPropsAus.ts`. Neu: `altfeld_namen_sperre.test.ts`, Spec `feat_3298_altfeld_typen_sperre.md`. Tests: ca. 6-10 bestehende anpassen (Pruefstaende, `compareEditorHourly*.test.ts`, evtl. `compare_hourly_metric_formats_persistenz.test.ts`).

### LoC-Schaetzung
Produktion ca. -250 / +30 (fast nur Loeschungen), neuer Test ca. +150, Testanpassungen ca. +-150, Spec ca. 80.

### Offene Entscheidungen mit Tech-Lead-Empfehlung
1. camelCase-Zustand (`outlookEnabled`, `hourlyMetricKeys` ...): mit entfernen (sonst bleibt toter Round-Trip, `outlook_enabled` wird weiter gesendet).
2. Lese-Naht `channel_active_metrics`: entfernen (Backend verwirft, Lesen liefert immer leer); Sperre kommt ohne ERLAUBT-Eintrag aus.
3. Sperre nur auf die zehn snake_case-Namen aus `ALTFELDER` (wie Backend). `multi_day_trend_morning/evening` (nicht in ALTFELDER) in `types.ts` mit entfernen, aber nicht in die Sperre.
4. Kommentare zaehlen nicht; ERLAUBT-Tabelle leer starten (Ablaufdatum 23.02.2027, falls Eintraege noetig werden).
5. `hourlyFriendlyMap.ts`: Loeschung bei #3020 R2; laeuft #3298 zuerst, dort melden, nicht hier loeschen.
6. Verwaiste Module: eigenes Issue im Epic #3122, nicht in diesen Durchlauf.

### Scoring
Ein Durchlauf reicht: ca. 11 Prod-Dateien, ueberwiegend Loeschungen, ein neuer Test. Ablauf Spec -> RED (Sperre rot auf Ist-Stand) -> GREEN (Bereinigung) -> Adversary-Mutation (Altname in Prod-Datei einfuegen, Sperre muss rot werden). Nicht aufteilen; das Aufraeumen der Verwaisten ausgelagert halten.
