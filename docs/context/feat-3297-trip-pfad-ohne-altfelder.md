# Context: feat-3297-trip-pfad-ohne-altfelder

Issue #3297 "Was steht wo B6b-3: Trip-Pfad und Anzeigen ohne Altfelder" (Epic #3122, Voraussetzung #3276 erledigt, Backend #3277 live).

## Request Summary

Das Frontend (nur `frontend/src`) soll im Trip-Pfad die Altfelder `channel_layouts`, `channel_layouts_per_report`, `outlook_metrics`, `outlook_metric_formats`, `show_outlook`, `multi_day_trend_reports` (sowie `channel_active_metrics`, `hourly_metrics`, falls Trip-Bezug) weder lesen noch schreiben. Backend (#3277) liest/serialisiert sie nicht mehr; Python entfernt sie beim Speichern. Regel: Altschlüssel WEGLASSEN, nie leer senden (Go-Merge ersetzt Top-Level-Werte). Home-Anzeige "Layout konfiguriert" (`cockpitHelpers568.ts:47-60`) bekommt Quelle `display_config.placements.rows`; `placements` wird im `display_config`-Typ ergänzt. Tests auf `placements` umstellen, nicht still löschen.

## Related Files (Produktion, ohne Tests)

Legende: L = liest, S = schreibt, T = tot/ohne Wirkung, K = nur Kommentar/Typ.

| Datei:Zeile | Fundstelle | Art |
|---|---|---|
| `lib/types.ts:286,296` | `ReportConfig.multi_day_trend_reports`, `show_outlook` | K (Typ; Anteil #3298 "Typen") |
| `lib/types.ts:329-345` | `DisplayConfig.channel_layouts`, `_per_report`, `outlook_metrics`, `outlook_metric_formats`; **`placements` fehlt** | K, hier `placements` ergänzen (#3297), Altfelder-Typen entfernen = #3298 |
| `lib/utils/cockpitHelpers568.ts:47,52,60,92` | `hasLayout` = `preset_name \|\| channel_layouts \|\| channel_layouts_per_report` | L, Quelle wechselt auf `placements.rows` (Länge>0) |
| `lib/components/shared/WeatherMetricsTab.svelte:494-500` | `trip.display_config.channel_layouts` -> `channelBuckets` | L |
| `…WeatherMetricsTab.svelte:505-511, 581-583` | `outlook_metrics`, `outlook_metric_formats` lesen | L |
| `…WeatherMetricsTab.svelte:326-341, 431-443, 788, 868-871` | Zustand `outlookMetricKeysRoute/FormatsRoute`, Dirty-Snapshot | L/S-Vorstufe |
| `…WeatherMetricsTab.svelte:914-948` | `buildWeatherPayload`: sendet `channel_layouts`, `outlook_metrics`, `outlook_metric_formats` (Trip-Payload) | S |
| `…WeatherMetricsTab.svelte:1839-1860` | Block `weather-metrics-ausblick` mit `OutlookLayoutControls`, nur `!createMode && sections.includes('ausblick')`; Kommentar nennt `show_outlook` | S/T |
| `…WeatherMetricsTab.svelte:1612+` | Abschnitt `layout_kanal` (route): LayoutTab auf `channelBuckets` | S (Kanal-Layout je Reiter) |
| `lib/components/shared/weather-metrics-tab/weatherMetricsSavePayload.ts:36,75-88` | `channel_layouts` im Typ, Bestand je Kanal lesen | L |
| `…/weather-metrics-tab/channelMetricLayouts.ts:37,180,247` | `channelOverridesFromSaved`, `mergeAllChannelLayoutsForSave` (Go ersetzt `channel_layouts` komplett), Ausblick-Liste | L/S (Kern der Trip-Layouts) |
| `…/weather-metrics-tab/weatherMetricsTabSections.ts:48,69` | `ROUTE_TRAILING_SECTIONS=['ausblick']`, `layout_kanal` | Steuerung der Bedienflächen |
| `lib/components/shared/OutlookLayoutControls.svelte` (:69,80,175,204,248) | Trip-Zweig; schreibt `outlook_metrics`/`_formats`; importiert `splitChannelMetricsForDisplay` aus channelMetricLayouts | S, nach #3276 nur noch vom Trip genutzt (Datei evtl. löschbar) |
| `lib/components/shared/MailInhaltCard.svelte:31,56,79,133` | `show_outlook` State, Schreiben in `eigene`; Kommentar: "Altfeld ohne Wirkung, nur durchgereicht" | S (Durchreichen, beide Kontexte) |
| `lib/components/shared/mailInhaltZustand.ts:9,31` | `show_outlook` Zustand, Default true | L |
| `lib/components/shared/mailInhaltKonstanten.ts:19-21` | `show_outlook` -> Katalog-IDs Großwetterlage (Nachweis-Tabelle) | K/Daten |
| `lib/components/shared/versand-tab/reportConfigPayload.ts:54-118` | `ausblickReports()` + `multi_day_trend_reports` ins Payload, `ausblickVorbelegung` | L/S |
| `lib/components/shared/VersandTab.svelte:207-211` | Kommentar zu `show_outlook`, `multi_day_trend_reports` | K |
| `lib/components/shared/zustellung-tab/kanalStilSpeicherung.ts:22-43` | Trip: Trend-Start aus `multi_day_trend_reports` (Default `['evening']`), schreibt `multi_day_trend_morning/_evening/_reports` | L/S (sichtbar: Kanal-Stil "Trend morgens/abends") |
| `lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts:41` | nur Kommentar (`channel_layouts`) | K |
| `lib/components/trip-new/tripNewLogic.ts:393-420` | `ergaenzeVersandStandard`, `ergaenzeStandardwerteReportConfig` belegen `multi_day_trend_reports` vor | S |
| `lib/components/trip-new/tripNewLogic.ts:354` | schreibt bereits `placements` (Vorbild) | Muster |
| `lib/components/shared/pickEigenfelder.ts:55,69,79,82,83` | Whitelists `WETTER_REPORT_KEYS`/`WETTER_DISPLAY_KEYS` enthalten Altschlüssel | S (Filter) |
| `lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts:94-137,171,262` | Vergleich-Pfad liest `channel_active_metrics`, `hourly_metrics`, `outlook_*` | Rest #3276/#3298, nicht Trip |
| `…/compareChannelMetricLayouts.ts`, `compare/subscriptionHelpers.ts:275`, `compare/compareHourlyMetricDefs.ts:126`, `compare/compareEditorSave.ts:24,124-151,458` | Kommentare/Vergleich | Nicht Trip (#3298/#3301) |

Produktionsdateien mit Trip-Bezug (zu ändern): ca. 14 (types.ts, cockpitHelpers568.ts, WeatherMetricsTab.svelte, weatherMetricsSavePayload.ts, channelMetricLayouts.ts, weatherMetricsTabSections.ts, OutlookLayoutControls.svelte, MailInhaltCard.svelte, mailInhaltZustand.ts, mailInhaltKonstanten.ts, reportConfigPayload.ts, kanalStilSpeicherung.ts, tripNewLogic.ts, pickEigenfelder.ts) plus Kommentar-Dateien (VersandTab.svelte, alarmeDeliveryPayload.ts). `hourly_metrics`/`channel_active_metrics` kommen in Trip-Pfaden NICHT vor (nur Vergleich/Kommentare).

## UI-Bedienflächen auf Altfeldern

ADR-0124 Nr. 6 (`docs/adr/0124-was-steht-wo-eine-tabelle.md:35`): Der 3-Tages-Ausblick wird allein über `placements.outlook_reports` (Morgen-/Abend-Briefing unter der Tabelle) gesteuert und "ersetzt `show_outlook`, `multi_day_trend_reports`, `outlook_enabled` und die Bedeutung 'leere Liste = aus'". Format: Nr. 5 (Zeile 82): `display_config.placements` mit `rows` und `outlook_reports`.

Wichtigster Befund: `WetterMetrikenVersandPanel.svelte` (einziger Einbinder von `WeatherMetricsTab`; der Rest sind nur Export in `organisms/index.ts`, `trip-detail/index.ts`) wird laut Textsuche von KEINER Produktions-Svelte-Datei mehr als `<WetterMetrikenVersandPanel>` gemountet. Trip-Detail nutzt `WetterTab`/`ZustellungTab` (`TripTabs.svelte:229-231`), Trip-Anlegen `ZustellungTab` (`TripNewEditor.svelte:949,1202`). Damit ist der gesamte route-Zweig von WeatherMetricsTab (Lesen 494-583, Payload 914-948, Ausblick-Block 1839, `layout_kanal`) vermutlich totes Erbe. Muss der Entwickler vor dem Löschen bestätigen (Grep auf `WetterMetrikenVersandPanel`/`WeatherMetricsTab` inkl. Tests; die Tests bauen den Ladeweg nach).

| Bedienfläche | Basis | Wirkung heute | Abdeckung durch Tabelle |
|---|---|---|---|
| Ausblick-Block (Metrik-Auswahl, Roh/Einfach) im Trip | `outlook_metrics`, `_formats` | keine (Backend liest nicht mehr; Block ohnehin nur ohne createMode und ohne Einbinder) | ja: Stellen/Formate in Tabelle, Ausblick über `outlook_reports` |
| Karte "Layout je Kanal" (`layout_kanal`) im Trip | `channel_layouts` | keine (#3277) | ja: Haken je Stelle in Tabelle |
| Haken "Großwetterlage" in MailInhaltCard | schreibt `show_stability`; `show_outlook` nur durchgereicht | `show_stability` wirkt (#3237), `show_outlook` nicht | `layout.mail_inhalt.grosswetterlage*` über Konstanten |
| Kanal-Stil "Trend Morgen/Abend" (kanalStilSpeicherung, Trip) | `multi_day_trend_reports` | laut ADR Nr. 6 ersetzt durch `outlook_reports`; Wirkung im Backend prüfen (#3277 liest es nicht) | Tabelle `outlook_reports` — sichtbare Änderung möglich (Bedienelement entfällt oder auf `outlook_reports` umstellen; Entscheidung in Spec) |
| Versand-Vorbelegung Trip-Anlage (`multi_day_trend_reports`) | tripNewLogic, reportConfigPayload | keine mehr | ersetzt durch Vorbelegung `outlook_reports` (nur abends), falls Karte sie nicht schon setzt |
| Home "Layout konfiguriert" (Checkliste) | `channel_layouts` | Anzeige liefert nach #3277 nie mehr "erledigt" für neue Trips | Quelle `placements.rows` |

Sichtbare UI-Änderung: Home-Checkliste (Quelle), ggf. Wegfall des Trend-Schalters im Kanal-Stil des Trips; sonst Entfernen toter Flächen (kein sichtbarer Unterschied, falls tatsächlich nirgends gemountet).

## Existing Patterns

- Vorgänger Vergleich: Spec `docs/specs/modules/feat_3276_vergleich_altfelder_entfernen.md`; Umsetzung `compare/compareEditorSave.ts` (Kommentare 124-151, 458: sechs Altschlüssel weglassen, auch nicht leer), Test `compare/feat3276_vergleich_ohne_altfelder.test.ts`, E2E `e2e/feat-3276-vergleich-ohne-altfelder.spec.ts`.
- `placements` schreiben/lesen: `shared/wetter-tab/wasStehtWoStand.ts`, `wasStehtWoSpeicherung.ts`, `wetterTabSpeicherung.ts`, `organisms/wetter-tab/WasStehtWoKarte.svelte`; Trip-Anlage `tripNewLogic.ts:354`.
- Teilfeld-PUT-Muster: `pickEigenfelder.ts` (Whitelist je Reiter); Altschlüssel aus `WETTER_*_KEYS` streichen, Wächtertest `pick_eigenfelder_kernregel.test.ts` anpassen.
- Textscan-Sperre-Vorbild (für #3298): `issue_523_suggested_flag_cleanup.test.ts`, `tests/test_altpfad_import_sperre.py`.

## Dependencies

- Upstream: #3276 (Vergleich), #3277 (Backend live, Altfelder nicht mehr gelesen/serialisiert), #3237 (Großwetterlage über `show_stability`), ADR-0124, `docs/reference/api_contract.md` (placements, `GET /api/briefings/{id}/placements`).
- Downstream: Go-Merge (`config_merge.go`) ersetzt Top-Level-Werte: fehlende Altschlüssel im PUT lassen Bestand stehen, Python entfernt sie beim Speichern. Konsumenten von `hasLayout` (`setupStepTrip`, Home-Karte, Trip-Liste).
- Gate: Trip/Ortsvergleich-Code-Teilung (`shared/`, `context="route"|"vergleich"`); `OutlookLayoutControls`/`MailInhaltCard` sind geteilt, nur der Trip-Zweig entfällt, kein neues Pendant anlegen.

## Betroffene Tests (Altfeld-Bezug, Trip-relevant; Auszug)

Unit (`node --test`): `src/lib/issue_568_home_redesign.test.ts` (Home-Checkliste -> placements), `shared/__tests__/{channelMetricLayouts, channelPayloadAllChannels, mail_inhalt_zustand, mail_inhalt_konstanten, mail_inhalt_card, mail_inhalt_card_hub_einbindung, mail_inhalt_haken_grosswetterlage_3237, ausblick_ein_name_3155, outlook_restore_schreibt_nur_outlook_metrics, outlook_erbt_grundauswahl_structure, pick_eigenfelder_kernregel, reportConfigDirty, weatherMetricsTabSharing, wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte, wetter_metriken_versand_panel_*, versandVergleichPruefstand, goMergeServerPruefstand}`, `shared/weather-metrics-tab/__tests__/{lade_kanal_layouts_aus_trip, speichern_*, wetter_metriken_nutzlast_verliert_keine_daten, feld_erhalt_ohne_ausnahme, neue_metrik_in_allen_listen, _editor_kette, f006_*, wind_chill_kanal_mitnahme_speicherpfad, wetter_metriken_*}`, `shared/versand-tab/__tests__/{merge_report_config_read_modify_write, report_config_serialisierung_golden}`, `shared/zustellung-tab/__tests__/{kanalStilSpeicherung.test.ts, zustellungTabDaten.ts}`, `shared/wetter-tab/__tests__/{wertebereiche_nutzlast_verliert_keine_daten, ac26_einstellung_gleich_ausgabe, ampelSchreiben}`, `shared/layout-tab/__tests__/{layout_korridor_sprache, f8KatalogAnker.ts}`, `trip-new/__tests__/{trip_new_mail_inhalt_karte_genau_eine_instanz, trip_anlegen_zustellung_verdrahtung_3332, trip_anlegen_zustellung_payload_3332, standardwerte_payload_paritaet_trip}`, `trip-detail/__tests__/{trip_retry_fehlerpfade_kein_verlust, trip_reiter_roundtrip_jedes_feld, trip_reiter_nutzlast_nur_eigene_felder, trip_python_skip_next_ohne_412, tripMehrreiterPruefstand.ts}`, `src/lib/__tests__/fakeTripServerGoMerge.test.ts`. (Reine `compare/…`-Tests sind Vergleich, gehören zu #3276/#3298/#3301, nicht hierher.)

E2E (`frontend/e2e`): `trip-anlegen-zustellung-3332.spec.ts`, `trip-outlook-metric-selection.staging.setup.ts`, `editor-gleich-gespeichert.staging.spec.ts`, `hub-versand-speichert-selbst.spec.ts`, `hub-wetter-metriken-speichert-selbst.spec.ts`, `hub-save-chip.spec.ts`, `hub-konfliktschutz-zwei-kontexte.spec.ts`, `hub-anlegen-ablauf.spec.ts`, `standardwerte-und-hilfe.spec.ts`, `issue-723-email-tab-eindampfen.spec.ts`, `issue-619-mail-elements-ui.spec.ts`, `kurzform-gefuehlte-temperatur-kind-mitnahme.spec.ts`, `was-steht-wo-karte.spec.ts`, `s3b2795-zustellung.helpers.ts`. (Trip-Bezug je Datei im Grep prüfen.)

Hinweis: viele dieser Tests prüfen genau die Altfeld-Pfade (Round-Trip, Dirty, Payload); je Test entscheiden: auf `placements` umstellen (Home, Round-Trip) oder mit Begründung ersetzen durch "Altschlüssel nicht im Payload" (Vorbild feat3276-Test). Nicht still löschen.

## Existing Specs

- `docs/specs/modules/feat_3276_vergleich_altfelder_entfernen.md` (Vorlage, Spec-AC-38)
- `docs/adr/0124-was-steht-wo-eine-tabelle.md` (Nr. 5, 6), Epic-Spec #3122
- `docs/specs/modules/feat_3155*` (Ausblick-Vorbelegung `multi_day_trend_reports`), `issue_1361_1368_ausblick_konfigurierbar.md`, `feat_3237*` (Großwetterlage)

## Überschneidungen mit Nachbar-Issues

- **#3298** (Typen entfernen + Textscan-Sperre): Liste "Restliche Altfeld-Stellen: `types.ts`, `pickEigenfelder.ts`, `hourlyFriendlyMap.ts`, `subscriptionHelpers.ts`, `compareHourlyMetricDefs.ts`"; Sperre über alle Produktionsdateien nach `channel_layouts`, `outlook_metrics`, `outlook_metric_formats`, `channel_active_metrics`, `hourly_metrics`, `hourly_metric_formats`, `show_outlook`. Überschneidung: `types.ts` und `pickEigenfelder.ts` stehen in beiden. Abgrenzung: #3297 stellt auf `placements` um und entfernt die Trip-Nutzer; #3298 entfernt danach die Typ-Felder und schaltet den Scan scharf. In #3297 `show_outlook` und `multi_day_trend_reports` im Trip-Pfad erledigen (`multi_day_trend_reports` steht NICHT in der #3298-Sperrliste; `show_outlook` schon, daher MailInhaltCard/mailInhaltZustand/Konstanten hier bereinigen, sonst blockiert die Sperre).
- **#3301** (Ortsvergleich: Karte "Layout je Kanal" ohne Wirkung): betrifft `layout_kanal` im Kontext `vergleich` und löscht `compareHourlyMetricDefs.ts`. Überschneidung bei `WeatherMetricsTab.svelte` (`layout_kanal`-Abschnitt, `weatherMetricsTabSections.ts`, `WetterMetrikenVersandPanel`): die Datei wird von beiden angefasst, Merge-Konflikte wahrscheinlich; Reihenfolge klären (#3301 sagt "Trip bleibt unverändert, Rückbau folgt mit #3297"). Falls WeatherMetricsTab nirgends gemountet ist, entfällt die Datei evtl. komplett (dann beide Issues kleiner).

## Risks & Considerations

1. Go-Merge ersetzt Top-Level-Werte: Altschlüssel NIE leer (`{}`/`[]`/`null`) senden, sondern weglassen; sonst Datenverlust oder neu angelegte Leerfelder.
2. Totcode-Frage: wenn `WeatherMetricsTab` (route) wirklich nirgends mounted ist, ist die Datei samt Hilfsdateien löschbar, aber ~30 Tests bauen ihn nach (`_editor_kette`, Prüfstände); Löschen nur mit ersetzter Abdeckung (kein stilles Löschen).
3. Trend-Schalter im Kanal-Stil (`kanalStilSpeicherung`, `multi_day_trend_morning/_evening`) ist eine sichtbare Bedienfläche; entweder auf `placements.outlook_reports` umhängen oder entfernen. Produktentscheidung prüfen gegen ADR-0124 Nr. 6 und #3155-Spec.
4. `show_outlook` in `MailInhaltCard` wird beidseitig durchgereicht; Entfernen ändert den Mail-Inhalt-Blob für Trip und Vergleich (geteilte Komponente, Gate Code-Teilung). Golden-Tests (`report_config_serialisierung_golden`) anpassen.
5. Home-Checkliste: `placements.rows` ist bei neuen Trips ggf. leer/ungesetzt (Karte schreibt erst nach Nutzergeste, Anlage schreibt `placements` via tripNewLogic:354); Definition "konfiguriert" = `rows.length > 0` oder `preset_name` klären; Bestandsdaten ohne `placements` zeigen "offen" (Verhaltensänderung, bewusst laut Issue).
6. Konflikt mit #3298 (Typen) und #3301 (WeatherMetricsTab): Reihenfolge/Branch-Basis beachten.
7. Echte `user_id`/Zwei-Nutzer-Test nur nötig, falls ein datenbewegender Endpoint geändert wird (hier nur Frontend-Payload).
8. Deploy: Frontend-only, aber Staging-E2E nötig (`/e2e-verify`); Playwright-Specs mit Altfeld-Seeds (Trip-Fixtures) auf `placements` umstellen.

## Analysis

Analyse Phase 2 (Pfade unter `frontend/`, Beleg-Stand Worktree `feat-3297-trip-pfad-ohne-altfelder`).

### Type

Rückbau (Nachfolger von #3276). Für Nutzer kein neues Verhalten, ausser Home-Checkliste "Layout konfiguriert" (neue Quelle). Frontend-only, kein Go-/Python-Eingriff (#3277 liest die Altfelder nicht mehr; `src/app/loader.py:145` `ALTFELDER` verwirft sie beim Speichern).

### Befunde (mit Belegen)

1. **Toter Trip-Zweig, bestätigt.** `<WeatherMetricsTab` wird nur in `shared/WetterMetrikenVersandPanel.svelte:64` gemountet. `<WetterMetrikenVersandPanel` kommt in keiner Produktionsdatei vor (nur Kommentare: `CompareTabs.svelte:45`, `ZustellungTab.svelte:10`, `CompareNewEditor.svelte:89`). Keine dynamischen Importe (nur in Tests), keine Treffer unter `src/routes`. Re-Exports ohne Verbraucher: `organisms/index.ts:18`, `trip-detail/index.ts:7`. Transitiv tot: `BriefingScheduleTab.svelte` (nur Panel `:17,68`), `VersandTab.svelte` (nur Panel `:76` und BriefingScheduleTab `:145`), `MailInhaltCard.svelte` (einzige Montage `WeatherMetricsTab.svelte:1827`), `OutlookLayoutControls.svelte` (nur `WeatherMetricsTab.svelte:123,1848`). Live-Trip-Pfad: `WetterTab`/`ZustellungTab` (`TripTabs.svelte`, `TripNewEditor.svelte`).
2. **Trend-Schalter Morgen/Abend: nicht sichtbar.** `kanalStilSpeicherung.ts:3-8`: Bedienung mit #3154 entfernt; kein Svelte nutzt `trendMorgen`/`trendAbend`. Einziger Produktions-Aufrufer `wasStehtWoSpeicherung.ts:233` (`kanalStilNutzlast`) mit Trend false/false und identischem `vorher` -> Trend-Zweig `tripNutzlast` (`:41-43`) wird nie geschrieben. `kanalStilStart` hat KEINEN Produktions-Aufrufer (nur Tests `ac26_*`, `p12_*`, `kanalStilSpeicherung.test.ts`). Er doppelt `placements.outlook_reports`; ADR-0124 Nr. 6 ersetzt ihn: Entfernen ist PO-entschieden.
3. **`show_outlook` in MailInhaltCard:** reiner Round-Trip. Sichtbarer Haken (testid `report-show-outlook`) liest/schreibt `show_stability`; `show_outlook` nur `MailInhaltCard.svelte:31,56,79` durchgereicht, Kommentar `:133` "Altfeld ohne Wirkung". Karte ist nur im toten Baum montiert -> Entfernen ohne sichtbare Änderung. Echte Live-Schreibstelle: `tripNewLogic.ts:25,416` (`ladeMailZustand` in `ergaenzeStandardwerteReportConfig`, schreibt `show_outlook:true` in den POST).
4. **Live-Schreibstelle `multi_day_trend_reports`:** `tripNewLogic.ts:396-404` (`ergaenzeVersandStandard`, `ausblickVorbelegung:true`) -> `reportConfigPayload.ts:59-66,103,118` (Schedule) -> `mergeReportConfig.ts:63`; Aufruf `TripNewEditor.svelte:580`. Python verwirft den Wert, Wirkung null. Die Erst-Tabelle kommt über `mitKarte` (`tripNewLogic.ts:354`, `placements: karte.placements`) bzw. Backend (Spec #3122 Nachtrag 22.11.).
5. **Home-Checkliste:** `cockpitHelpers568.ts:59-60` `hasLayout = preset_name != null || channel_layouts != null || channel_layouts_per_report != null`; einziger Verbraucher `routes/+page.svelte:25,139`. Neue Trips tragen nach #3277 nie `channel_layouts` -> Haken bliebe aus.
6. **Weitere Live-Altfeld-Stellen:** `pickEigenfelder.ts:53-55,69,79,82-83` (Whitelists); `types.ts:284-286,296,329-345`.

### Tech-Lead-Entscheidungen

1. **Totcode löschen statt umbauen.** Zu löschen: `WeatherMetricsTab.svelte` (2079 Z.), `WetterMetrikenVersandPanel.svelte`, `BriefingScheduleTab.svelte`, `VersandTab.svelte`, `MailInhaltCard.svelte`, `OutlookLayoutControls.svelte`, `weather-metrics-tab/{channelMetricLayouts,weatherMetricsSavePayload,weatherMetricsTabSections}.ts`, samt Barrel-Exports. Vor jeder Löschung Produktions-Grep auf Rest-Referenzen; bleibt etwas Lebendes dran, Datei schlank umschneiden. Zu prüfen: `WeatherV2Reihenfolge.svelte`, `kuerzelLegende.ts`, `kuerzelMarken.ts`, `nurEinBericht.ts`, `compareAggregationGrouping.ts` (nur löschen ohne Rest-Referenz). `outlookFriendlyCapability.ts` bleibt (live via `compare/hourlyFriendlyMap.ts:14`).
2. **Bleibt:** `compareMetricSelection.ts`, `compareMetricOrder.ts`, `compareChannelMetricLayouts.ts`, `weatherMetricsCompareSave.ts`, `SavePresetDialog.svelte` (Vergleich/Vorlagen, Rest = #3298/#3301), `reportConfigPayload.ts` (ohne Trend), `mailInhaltZustand.ts`/`mailInhaltKonstanten.ts` (ohne `show_outlook`), `mergeReportConfig.ts`.
3. **Code-Teilung (Gate):** kein neues Pendant. `MailInhaltCard`/`OutlookLayoutControls` sind auch im Vergleich nirgends montiert; Live-Karte ist die geteilte `WasStehtWoKarte` mit `context`.
4. **Trend-Schalter entfällt ersatzlos:** `KanalStilStand` auf `{ stil }`, `tripNutzlast` schreibt nur `telegram_style`; `wasStehtWoSpeicherung.ts:231-233` ohne Trend-Argumente.
5. **Vorbelegung `multi_day_trend_reports` ersatzlos weglassen** (`ausblickReports`, `ausblickVorbelegung`, Eingabe-Parameter; `ergaenzeVersandStandard` vereinfachen). Frontend schreibt kein Ersatz-`outlook_reports`.
6. **Home-Definition:** `hasLayout = placements.rows.length > 0` (ADR-0124 Nr. 5; `preset_name` ist Vorlagenname, entfällt). `DisplayConfig` in `types.ts` um `placements?: { rows?: …; outlook_reports?: string[] }` ergänzen (Altfeld-Typen entfernen = #3298). Bestand: alle 10 Prod-Abos mit Altfeldern haben `rows` (Angabe #3277) -> keine sichtbare Änderung.
7. **Altschlüssel weglassen, nie leer senden** (`internal/handler/config_merge.go` ersetzt Top-Level-Werte). Nach Löschung der Schreibstellen automatisch erfüllt; Nutzlast-Test beweist es (Vorbild `compare/feat3276_vergleich_ohne_altfelder.test.ts`).
8. **Schnitt:** #3297 = alle Trip-Schreib-/Lesewege, `show_outlook`/`multi_day_trend_*` komplett (steht in #3298-Sperrliste), WMT-Baum löschen, Home-Quelle, `placements`-Typ. #3298 danach: Altfeld-Typen, restliche `pickEigenfelder`-Einträge (`channel_layouts`, `outlook_metrics`, `outlook_metric_formats`), Vergleich-Reste, Textscan-Sperre. #3301: WMT-Anteil (`layout_kanal`) entfällt mit #3297; Reihenfolge #3297 zuerst, #3301 schrumpft.

### Affected Files

| File | MODIFY/DELETE/CREATE | Beschreibung |
|---|---|---|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | DELETE | toter Alt-Editor |
| `frontend/src/lib/components/shared/WetterMetrikenVersandPanel.svelte` | DELETE | einziger Einbinder, unmontiert |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | DELETE | nur aus dem Panel |
| `frontend/src/lib/components/shared/VersandTab.svelte` | DELETE | nur Panel + BriefingScheduleTab |
| `frontend/src/lib/components/shared/MailInhaltCard.svelte` | DELETE | nur aus WMT; `show_outlook`-Round-Trip |
| `frontend/src/lib/components/shared/OutlookLayoutControls.svelte` | DELETE | nur WMT; schreibt `outlook_metrics`/`_formats` |
| `frontend/src/lib/components/shared/weather-metrics-tab/{channelMetricLayouts,weatherMetricsSavePayload,weatherMetricsTabSections}.ts` | DELETE | nur WMT-Kette (Grep-Gate) |
| `…/weather-metrics-tab/{WeatherV2Reihenfolge.svelte,kuerzelLegende.ts,kuerzelMarken.ts,nurEinBericht.ts,compareAggregationGrouping.ts}` | DELETE falls ohne Rest-Referenz | Bau prüft per Grep |
| `frontend/src/lib/components/organisms/index.ts`, `trip-detail/index.ts` | MODIFY | Barrel-Exports entfernen |
| `frontend/src/lib/utils/cockpitHelpers568.ts` | MODIFY | `hasLayout` aus `placements.rows`, Doku-Kommentar `:41-50` |
| `frontend/src/lib/types.ts` | MODIFY | `placements` ergänzen; `show_outlook`, `multi_day_trend_*` aus `ReportConfig` |
| `frontend/src/lib/components/shared/mailInhaltZustand.ts`, `mailInhaltKonstanten.ts` | MODIFY | `show_outlook` raus |
| `frontend/src/lib/components/shared/versand-tab/reportConfigPayload.ts` | MODIFY | `ausblickReports`/`ausblickVorbelegung`/Trend im Schedule raus |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | `ergaenzeVersandStandard`/`ergaenzeStandardwerteReportConfig` ohne Vorbelegung und `show_outlook` |
| `frontend/src/lib/components/shared/zustellung-tab/kanalStilSpeicherung.ts` | MODIFY | Trend-Felder/-Lesung raus |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts` | MODIFY | `kurzstil()` ohne Trend |
| `frontend/src/lib/components/shared/pickEigenfelder.ts` | MODIFY | `multi_day_trend_*`, `show_outlook` aus Whitelists |
| Kommentar-Verweise: `alarme-tab/alarmeDeliveryPayload.ts:41`, `CompareTabs.svelte:45`, `ZustellungTab.svelte:10`, `CompareNewEditor.svelte:89`, `app.css:1016`, `utils/rightColumn.ts`, `utils/vorlageSpeichernKarte.ts`, `VorlageKarte.svelte:50`, `edit/weatherSummary.ts` | MODIFY | nur Kommentare nachziehen |
| `frontend/src/lib/issue_568_home_redesign.test.ts` | MODIFY | Home-Checkliste auf `placements.rows` (erst rot) |
| Tests der toten Kette (ca. 134 Test-/Spec-Dateien referenzieren WMT/Panel/BriefingScheduleTab/OutlookLayoutControls/VersandTab; Gruppen `shared/__tests__/{channelMetricLayouts,channelPayloadAllChannels,mail_inhalt_*,ausblick_ein_name_3155,outlook_*,weatherMetricsTabSharing,wetter_metriken_*,versandVergleichPruefstand,goMergeServerPruefstand,reportConfigDirty}`, `weather-metrics-tab/__tests__/*`, `versand-tab/__tests__/*`, `trip-detail/__tests__/*`) | DELETE bzw. MODIFY | nicht still löschen: testet er nur den toten Baum -> löschen mit Begründung im Commit und Abdeckung über Live-Pfad-Test sichern; testet er Live-Funktion (`reportConfigPayload`, `kanalStilSpeicherung`, `ac26_*`, `p12_*`, `tripNewLogic`, `pick_eigenfelder_kernregel`, `trip_reiter_roundtrip_jedes_feld`, `fakeTripServerGoMerge`) -> anpassen |
| `frontend/src/lib/components/trip-new/__tests__/trip_pfad_ohne_altfelder_3297.test.ts` | CREATE | Nutzlast-Test: Anlage-POST (auch "Mit Standardwerten") und Reiter-PUTs ohne Altschlüssel (auch nicht leer); Bestand bleibt per Go-Merge-Fake |
| `frontend/e2e/*` (u. a. `trip-anlegen-zustellung-3332`, `hub-wetter-metriken-speichert-selbst`, `hub-versand-speichert-selbst`, `editor-gleich-gespeichert.staging.spec`, `trip-outlook-metric-selection.staging.setup`, `was-steht-wo-karte`, `issue-619-mail-elements-ui`, `issue-723-email-tab-eindampfen`) | MODIFY/DELETE | Altfeld-Seeds auf `placements`; reine Alt-Oberfläche begründet ersetzen |
| `frontend/e2e/feat-3297-trip-ohne-altfelder.spec.ts` | CREATE | Request-Body ohne Altschlüssel (Anlegen/Speichern) + Home-Haken "Layout" |
| `docs/specs/modules/feat_3297_trip_pfad_ohne_altfelder.md` | CREATE | Spec (Phase 3) nach Vorbild #3276 |
| `docs/specs/modules/feat_3122_was_steht_wo.md` | MODIFY | Nachtrag AC-38 Trip-Teil erledigt |

### Scope Assessment

- Produktionsdateien: ca. 25 (9-14 gelöscht, ca. 11 geändert, Rest Kommentare). Tests: bis ca. 134 Referenzdateien, realistisch 40-60 zu löschen oder umzustellen; das ist der Hauptaufwand.
- LoC: Produktion netto ca. -4000 bis -5000; neuer Code unter 120 Zeilen; Tests netto ebenfalls negativ plus 2 neue.
- Risk: **mittel**. Technisch gering (totes Erbe), aber (a) Fehleinschätzung "tot" -> Grep-Gate vor jeder Löschung; (b) Test-Lösch-Disziplin, Live-Abdeckung nicht verlieren; (c) Home-Checklisten-Semantik; (d) Merge-Konflikte mit #3298/#3301. Zwei-Nutzer-Test nicht nötig (kein neuer datenbewegender Endpoint), Staging-Request-Body-Prüfung genügt. LoC-Gate für reine Löschzeilen im Spec vermerken.

### Technical Approach

1. Phase 4 (Rot): (a) Home: Trip mit `placements.rows` -> Layout done, Trip nur mit `channel_layouts` -> offen; (b) Nutzlast-Test über alle Live-Trip-Speicherwege (rot wegen `multi_day_trend_reports`/`show_outlook` in `tripNewLogic`/`reportConfigPayload`); (c) Scan-Test nur für die hier erledigten Schlüssel (`show_outlook`, `multi_day_trend_*`); die volle Sperre liefert #3298.
2. Phase 5: erst Live-Schreibstellen (tripNewLogic, reportConfigPayload, kanalStilSpeicherung, mailInhalt*), `hasLayout`, `types.ts`; dann WMT-Baum nach Grep-Gate löschen; Barrels und Kommentare; zuletzt Tests umstellen oder begründet löschen.
3. Altschlüssel nur weglassen. Kein Go-/Python-Eingriff.
4. Deploy frontend-only; Staging-E2E (`/e2e-verify`) mit Request-Body-Prüfung für Trip anlegen/speichern und Home-Haken bei Bestandstrip.

### Dependencies

Upstream: #3276, #3277, #3237, #3154, ADR-0124 Nr. 5/6, Spec #3122 Nachtrag 22.11. Downstream: #3298 (setzt #3297 voraus), #3301 (WMT-Anteil entfällt). Gates: Trip/Ortsvergleich-Code-Teilung (nur Löschung, kein Pendant); kein neues ADR nötig (ADR-0124 Nr. 6 deckt das Entfernen).

### Open Questions

Keine Produktfrage an den PO: Trend-Schalter (unsichtbar, ADR Nr. 6), `show_outlook` (wirkungslos), Home-Quelle (Issue + ADR Nr. 5) sind entschieden. Technische Prüfpunkte für den Bau: (1) Rest-Referenzen von `WeatherV2Reihenfolge`, `kuerzel*`, `nurEinBericht`, `compareAggregationGrouping`; (2) setzt das Backend bei Anlage ohne Karten-Stand (Wetter-Reiter nie geöffnet) eine Erst-`placements`? Falls nein: Home-Haken "offen" bis zur ersten Karten-Speicherung, kein Ausfall, im Test belegen; (3) `preset_name` nicht mehr in `hasLayout` (Empfehlung).

### Paket-Entscheidung (Tech Lead, 25.11.)
#3297 und #3020 (Rückbau WeatherMetricsTab) in EINEM Durchlauf: der tote Baum (WeatherMetricsTab, WetterMetrikenVersandPanel, BriefingScheduleTab, VersandTab, MailInhaltCard, OutlookLayoutControls) wird gelöscht; der #3020-Befund „nicht tot“ ist überholt (kein Produktions-Mount mehr). Spec deckt beide Issues ab; Abschluss schließt #3297 und #3020.
