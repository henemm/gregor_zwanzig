# Gelöschte Tests — #3297 / #3020 (Trip-Pfad ohne Altfelder, Rückbau Alt-Editor)

Jede gelöschte Testdatei prüfte ausschließlich den gelöschten Alt-Editor-Baum (Spec
`docs/specs/modules/feat_3297_trip_pfad_ohne_altfelder.md`, Abschnitt „Test-Zuordnung“).
Spalte 2 nennt die gelöschte Produktionsdatei, die der Test importierte, renderte oder nachbaute
(gemessen am Quelltext des Tests vor dem Löschen; die häufigsten Treffer).

## Gelöschte Produktionsdateien (12)

- `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
- `frontend/src/lib/components/shared/WetterMetrikenVersandPanel.svelte`
- `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte`
- `frontend/src/lib/components/shared/VersandTab.svelte`
- `frontend/src/lib/components/shared/MailInhaltCard.svelte`
- `frontend/src/lib/components/shared/OutlookLayoutControls.svelte`
- `frontend/src/lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts`
- `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsSavePayload.ts`
- `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts`
- `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte`
- `frontend/src/lib/components/shared/weather-metrics-tab/kuerzelLegende.ts`
- `frontend/src/lib/components/shared/weather-metrics-tab/kuerzelMarken.ts`

## Gelöschte Testdateien (64) → getestete (gelöschte) Produktionsdatei

| Testdatei (unter `frontend/src/lib/components/`) | gelöschte Produktionsdatei |
|---|---|
| `compare/__tests__/compare_wetter_metriken_wertprops.test.ts` | shared/WeatherMetricsTab.svelte · shared/WetterMetrikenVersandPanel.svelte |
| `shared/__tests__/ausblick_ein_name_3155.test.ts` | Pruefstand f5Pruefstand.ts (rendert WeatherMetricsTab, mitgeloescht) · shared/MailInhaltCard.svelte |
| `shared/__tests__/channelMetricLayouts.test.ts` | weather-metrics-tab/channelMetricLayouts.ts |
| `shared/__tests__/channelOffGroupListBuilding.test.ts` | weather-metrics-tab/channelMetricLayouts.ts |
| `shared/__tests__/channelPayloadAllChannels.test.ts` | weather-metrics-tab/channelMetricLayouts.ts · shared/WeatherMetricsTab.svelte |
| `shared/__tests__/compare_outlook_metric_selection_structure.test.ts` | weather-metrics-tab/WeatherV2Reihenfolge.svelte · shared/WeatherMetricsTab.svelte |
| `shared/__tests__/compare_versand_wertprops.test.ts` | shared/VersandTab.svelte · shared/WetterMetrikenVersandPanel.svelte |
| `shared/__tests__/mail_inhalt_card.test.ts` | shared/MailInhaltCard.svelte · shared/VersandTab.svelte |
| `shared/__tests__/mail_inhalt_card_hub_einbindung.test.ts` | shared/MailInhaltCard.svelte · shared/WeatherMetricsTab.svelte |
| `shared/__tests__/mail_inhalt_haken_grosswetterlage_3237.test.ts` | shared/MailInhaltCard.svelte · shared/WeatherMetricsTab.svelte |
| `shared/__tests__/metricKuerzelLegende.test.ts` | shared/WeatherMetricsTab.svelte · weather-metrics-tab/WeatherV2Reihenfolge.svelte |
| `shared/__tests__/outlook_email_only_hint_per_context.test.ts` | shared/OutlookLayoutControls.svelte · shared/WeatherMetricsTab.svelte |
| `shared/__tests__/outlook_erbt_grundauswahl_structure.test.ts` | shared/OutlookLayoutControls.svelte · weather-metrics-tab/channelMetricLayouts.ts |
| `shared/__tests__/outlook_restore_schreibt_nur_outlook_metrics.test.ts` | shared/OutlookLayoutControls.svelte · weather-metrics-tab/channelMetricLayouts.ts |
| `shared/__tests__/s3a2794_speicher_owner_waechter.test.ts` | shared/WeatherMetricsTab.svelte · trip-detail/BriefingScheduleTab.svelte |
| `shared/__tests__/speicher_anzeige_zwischenstand_wetter_und_briefing.test.ts` | shared/WeatherMetricsTab.svelte · trip-detail/BriefingScheduleTab.svelte |
| `shared/__tests__/versand_tab_laedt_keine_compare_klebeschicht.test.ts` | shared/VersandTab.svelte |
| `shared/__tests__/versand_tab_meldet_aenderungen_reaktiv.test.ts` | shared/VersandTab.svelte · shared/WeatherMetricsTab.svelte |
| `shared/__tests__/weatherMetricsTabSharing.test.ts` | weather-metrics-tab/weatherMetricsTabSections.ts · shared/WeatherMetricsTab.svelte |
| `shared/__tests__/weather_metric_kuerzel_marken.test.ts` | weather-metrics-tab/WeatherV2Reihenfolge.svelte · shared/WeatherMetricsTab.svelte |
| `shared/__tests__/weather_metric_name_forms_visible.test.ts` | shared/WeatherMetricsTab.svelte · shared/OutlookLayoutControls.svelte |
| `shared/__tests__/weather_metrics_tab_compare_catalog_fetch.test.ts` | shared/WeatherMetricsTab.svelte |
| `shared/__tests__/weather_metrics_tab_create_mode_callback.test.ts` | shared/WeatherMetricsTab.svelte |
| `shared/__tests__/weather_metrics_tab_vergleich_uebersicht_kanal_tabs.test.ts` | weather-metrics-tab/WeatherV2Reihenfolge.svelte · shared/WeatherMetricsTab.svelte |
| `shared/__tests__/wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte.test.ts` | shared/WeatherMetricsTab.svelte |
| `shared/__tests__/wetter_metriken_versand_panel_fuehrt_sprung_nach.test.ts` | shared/WetterMetrikenVersandPanel.svelte |
| `shared/__tests__/wetter_metriken_versand_panel_paritaet.test.ts` | shared/WetterMetrikenVersandPanel.svelte · shared/WeatherMetricsTab.svelte |
| `shared/__tests__/wetter_metriken_versand_panel_speicherung.test.ts` | shared/WeatherMetricsTab.svelte · shared/WetterMetrikenVersandPanel.svelte |
| `shared/__tests__/wetter_metriken_vorlage_anwenden_sendet_ampel.test.ts` | shared/WeatherMetricsTab.svelte |
| `shared/versand-tab/__tests__/compare_versand_zeigt_schaltbare_premium_sms.test.ts` | shared/VersandTab.svelte |
| `shared/versand-tab/__tests__/premium_sms_context_gating_render.test.ts` | shared/VersandTab.svelte |
| `shared/versand-tab/__tests__/versand_tab_defaults_gleich_auslieferung.test.ts` | shared/VersandTab.svelte |
| `shared/weather-metrics-tab/__tests__/_editor_kette.ts` | shared/WeatherMetricsTab.svelte · weather-metrics-tab/channelMetricLayouts.ts |
| `shared/weather-metrics-tab/__tests__/altfelder_gesperrt_s1c3.test.ts` | Pruefstand f5Pruefstand.ts (rendert WeatherMetricsTab, mitgeloescht) · weather-metrics-tab/weatherMetricsSavePayload.ts |
| `shared/weather-metrics-tab/__tests__/bug_2454_channel_ableitung_und_toggle.test.ts` | weather-metrics-tab/channelMetricLayouts.ts · shared/WeatherMetricsTab.svelte |
| `shared/weather-metrics-tab/__tests__/editor_aenderung_gleich_erwartung.test.ts` | Pruefstand _editor_kette.ts (baut die WeatherMetricsTab-Kette nach, mitgeloescht) |
| `shared/weather-metrics-tab/__tests__/editor_anzeige_gleich_erwartung.test.ts` | Pruefstand _editor_kette.ts (baut die WeatherMetricsTab-Kette nach, mitgeloescht) · shared/WeatherMetricsTab.svelte |
| `shared/weather-metrics-tab/__tests__/editor_speichern_ohne_aenderung.test.ts` | Pruefstand _editor_kette.ts (baut die WeatherMetricsTab-Kette nach, mitgeloescht) |
| `shared/weather-metrics-tab/__tests__/editor_standard_gleich_mail.test.ts` | shared/WeatherMetricsTab.svelte · shared/OutlookLayoutControls.svelte |
| `shared/weather-metrics-tab/__tests__/erzeuge_nach_dateien.ts` | Pruefstand _editor_kette.ts (baut die WeatherMetricsTab-Kette nach, mitgeloescht) |
| `shared/weather-metrics-tab/__tests__/f5Pruefstand.ts` | shared/WeatherMetricsTab.svelte · weather-metrics-tab/WeatherV2Reihenfolge.svelte |
| `shared/weather-metrics-tab/__tests__/f5VarianteHook.mjs` | Hilfsdatei von f5Pruefstand.ts (Variantenhook) → shared/WeatherMetricsTab.svelte |
| `shared/weather-metrics-tab/__tests__/feld_erhalt_ohne_ausnahme.test.ts` | Pruefstand _editor_kette.ts (baut die WeatherMetricsTab-Kette nach, mitgeloescht) · shared/WeatherMetricsTab.svelte |
| `shared/weather-metrics-tab/__tests__/lade_kanal_layouts_aus_trip.test.ts` | shared/WeatherMetricsTab.svelte · Pruefstand _editor_kette.ts (baut die WeatherMetricsTab-Kette nach, mitgeloescht) |
| `shared/weather-metrics-tab/__tests__/multiSymbolMetricRowWiring.test.ts` | shared/WeatherMetricsTab.svelte |
| `shared/weather-metrics-tab/__tests__/neue_metrik_in_allen_listen.test.ts` | shared/WeatherMetricsTab.svelte · weather-metrics-tab/channelMetricLayouts.ts |
| `shared/weather-metrics-tab/__tests__/neue_metrik_in_allen_listen_orte.test.ts` | shared/WeatherMetricsTab.svelte · weather-metrics-tab/channelMetricLayouts.ts |
| `shared/weather-metrics-tab/__tests__/nur_ein_bericht_kennzeichnung.test.ts` | shared/WeatherMetricsTab.svelte · weather-metrics-tab/weatherMetricsSavePayload.ts |
| `shared/weather-metrics-tab/__tests__/s3a2794_bereich_filter.test.ts` | weather-metrics-tab/weatherMetricsTabSections.ts |
| `shared/weather-metrics-tab/__tests__/sms_reiter_roh_einfach_nur_fuer_sms_format_capable.test.ts` | weather-metrics-tab/WeatherV2Reihenfolge.svelte · shared/WeatherMetricsTab.svelte |
| `shared/weather-metrics-tab/__tests__/speichern_sendet_alle_kanaele.test.ts` | weather-metrics-tab/channelMetricLayouts.ts |
| `shared/weather-metrics-tab/__tests__/speichern_waehlt_richtigen_bestand.test.ts` | weather-metrics-tab/weatherMetricsSavePayload.ts · shared/WeatherMetricsTab.svelte |
| `shared/weather-metrics-tab/__tests__/telegram_kanalgrenze_je_kontext.test.ts` | shared/WeatherMetricsTab.svelte · Pruefstand f5Pruefstand.ts (rendert WeatherMetricsTab, mitgeloescht) |
| `shared/weather-metrics-tab/__tests__/telegram_schnittlinie_wahr.test.ts` | shared/WeatherMetricsTab.svelte · Pruefstand f5Pruefstand.ts (rendert WeatherMetricsTab, mitgeloescht) |
| `shared/weather-metrics-tab/__tests__/thunderThresholdCatalogGuard.test.ts` | shared/WeatherMetricsTab.svelte |
| `shared/weather-metrics-tab/__tests__/vorlage_anwenden_uebernimmt_ampel.test.ts` | weather-metrics-tab/weatherMetricsSavePayload.ts |
| `shared/weather-metrics-tab/__tests__/weatherMetricsTabSections.test.ts` | weather-metrics-tab/weatherMetricsTabSections.ts · shared/WeatherMetricsTab.svelte |
| `shared/weather-metrics-tab/__tests__/weather_metrics_official_alerts_section.test.ts` | weather-metrics-tab/weatherMetricsTabSections.ts · shared/WeatherMetricsTab.svelte |
| `shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts` | Pruefstand f5Pruefstand.ts (rendert WeatherMetricsTab, mitgeloescht) · weather-metrics-tab/weatherMetricsSavePayload.ts |
| `shared/weather-metrics-tab/__tests__/wetter_metriken_laedt_keine_compare_klebeschicht.test.ts` | shared/WeatherMetricsTab.svelte |
| `shared/weather-metrics-tab/__tests__/wind_chill_kanal_mitnahme_speicherpfad.test.ts` | weather-metrics-tab/channelMetricLayouts.ts · shared/WeatherMetricsTab.svelte |
| `trip-detail/__tests__/trip_night_block_schalter_verdrahtung.test.ts` | shared/WeatherMetricsTab.svelte |
| `trip-detail/__tests__/trip_python_skip_next_ohne_412.test.ts` | trip-detail/BriefingScheduleTab.svelte |
| `trip-detail/__tests__/trip_versand_reiter_ohne_dauer_keepalive.test.ts` | trip-detail/BriefingScheduleTab.svelte |

Zusätzlich gelöscht: die Golden-Dateien `tests/golden/f5_wertebereiche/*` (14 Dateien, Render-Ausgabe
von `f5Pruefstand.ts` = WeatherMetricsTab).

## Gekürzt statt gelöscht (gemischter Inhalt, Live-Teil bleibt)

Fälle gegen die gelöschten Dateien wurden herausgeschnitten und mit einem Kommentar `#3297/#3020`
markiert; die Live-Fälle laufen weiter, u. a. in: `trip-detail/__tests__/*` (Mehrreiter-, Retry-,
412-, Roundtrip-Tests auf die Live-Reiter umgestellt), `shared/__tests__/*` (u. a. kanal_abwahl_hinweis,
officialAlertLegend, infobox_nur_beim_anlegen, reiter_sprunglinks, compareMetricOrder,
context_herkunft_zweige_eingefroren + Endbilanz-Spec), `shared/versand-tab/__tests__/*`,
`shared/wetter-tab/__tests__/*` (ampelSchreiben, f004, fix_3193, fixloop3_c1, ac26),
`shared/layout-tab/__tests__/*` (f8Pruefstand + Golden), `compare/__tests__/*`, `alerts-tab/*`,
`i18n/__tests__/*` (Scanner-Listen; 59 verwaiste Katalogschlüssel `layout.ausblick.*`,
`layout.mail_inhalt.titel/format/…`, `wertebereiche.*` der Alt-Oberfläche, `trip.gespeichert_punkt`,
`trip.zeitplan_speichern` aus de/en entfernt), `trip-new/__tests__/*` (Altschlüssel-Erwartung → „Schlüssel fehlt“),
`issue_568_home_redesign.test.ts` (→ `placements.rows`).
