# Zuordnung der mit #3357 entfallenen Prüfungen (Rework #3020 R1/R1b)

Workflow `rework-3020-pruefungen-und-waisen`, Stand 25.11.2026.
Spec: `docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md` (AC-16 Zuordnungsliste, Definition of Done).
Quelle: `git diff --name-only --diff-filter=D c8329fea4^1 c8329fea4` (90 gelöschte Dateien, davon 60 `*.test.ts`),
Kontext `docs/context/rework-3020-pruefungen-und-waisen.md` (Abschnitt Analysis R1), Vorlage
`docs/artifacts/feat-3297-trip-pfad-ohne-altfelder/geloeschte-tests.md`.

Dokument für Menschen, kein Test darauf (Spec, Known Limitations).

Pfade unten relativ zu `frontend/src/lib/components/`, sofern nicht anders angegeben.

## Zählung

| Gruppe | Bedeutung | Dateien |
|---|---|---|
| A | prüfte nur gelöschten Quelltext (Aufbau, Verdrahtung, Darstellung der Alt-Komponenten) | 29 |
| B | prüfte Altfeld-Logik (`channel_layouts`, `outlook_*`, `hourly_*`), bewusst entfallen (ADR-0124 Nr. 6) | 10 |
| C | prüfte Verhalten, das im lebenden Code weiterbesteht | 21 |
| | **Summe** | **60** |

Abweichung zur Spec („ca. 33“ / „ca. 11“ / 20): `thunderThresholdCatalogGuard` stand im Kontext unter A, die Spec führt ihn in C (Verweis auf `thunderThresholdLevels.test.ts`); `vorlage_anwenden_uebernimmt_ampel` stand im Kontext unter B („Teil“), die Spec führt ihn in C. Nach der Adversary-Prüfung (F001) wechselt `wetter_metriken_versand_panel_speicherung` von A nach C (Spec: „Ergibt sich, dass eine Datei aus A oder B doch lebenden Code geprüft hat, wechselt sie nach C“). Die exakte Zählung ist daher 29 / 10 / 21.

## Gruppe A: nur gelöschter Quelltext (29)

Begründung für jede Zeile: **nur gelöschter Quelltext** – der geprüfte Code (WeatherMetricsTab, WetterMetrikenVersandPanel, VersandTab, MailInhaltCard, OutlookLayoutControls, WeatherV2Reihenfolge, weatherMetricsTabSections, kuerzelLegende/kuerzelMarken u. a.) existiert nicht mehr; es gibt nichts wiederherzustellen. Ersatz-Ort ist die Karte „Was steht wo“ (#3122) mit eigenen Tests unter `organisms/__tests__/was_steht_wo_karte*.test.ts`.

| Gelöschte Datei | Gruppe | Begründung |
|---|---|---|
| `compare/__tests__/compare_wetter_metriken_wertprops.test.ts` | A | nur gelöschter Quelltext (Wert-Props des Alt-Reiters im Vergleich) |
| `shared/__tests__/ausblick_ein_name_3155.test.ts` | A | nur gelöschter Quelltext (Ausblick-Benennung im Alt-Editor; Ausblick heute nur in der Karte) |
| `shared/__tests__/compare_outlook_metric_selection_structure.test.ts` | A | nur gelöschter Quelltext (Aufbau der Alt-Ausblick-Auswahl) |
| `shared/__tests__/compare_versand_wertprops.test.ts` | A | nur gelöschter Quelltext (Wert-Props VersandTab) |
| `shared/__tests__/mail_inhalt_card.test.ts` | A | nur gelöschter Quelltext (MailInhaltCard) |
| `shared/__tests__/mail_inhalt_card_hub_einbindung.test.ts` | A | nur gelöschter Quelltext (Einbindung MailInhaltCard; importierte die heute verwaisten `reportConfigDirty.ts`/`weatherSaveGate.ts`, deren Löschung folgt mit #3366) |
| `shared/__tests__/metricKuerzelLegende.test.ts` | A | nur gelöschter Quelltext (`kuerzelLegende`; Kürzel-Legende heute in der Karte, `was_steht_wo_karte.test.ts` „Kürzel erklärt“) |
| `shared/__tests__/outlook_email_only_hint_per_context.test.ts` | A | nur gelöschter Quelltext (Hinweis der OutlookLayoutControls) |
| `shared/__tests__/outlook_erbt_grundauswahl_structure.test.ts` | A | nur gelöschter Quelltext (Aufbau OutlookLayoutControls) |
| `shared/__tests__/outlook_restore_schreibt_nur_outlook_metrics.test.ts` | A | nur gelöschter Quelltext (Restore-Pfad des Alt-Ausblicks) |
| `shared/__tests__/s3a2794_speicher_owner_waechter.test.ts` | A | nur gelöschter Quelltext (Speicher-Owner des Alt-Reiters) |
| `shared/__tests__/speicher_anzeige_zwischenstand_wetter_und_briefing.test.ts` | A | nur gelöschter Quelltext (Speicheranzeige des Alt-Reiters) |
| `shared/__tests__/versand_tab_laedt_keine_compare_klebeschicht.test.ts` | A | nur gelöschter Quelltext (VersandTab) |
| `shared/__tests__/versand_tab_meldet_aenderungen_reaktiv.test.ts` | A | nur gelöschter Quelltext (VersandTab) |
| `shared/__tests__/weatherMetricsTabSharing.test.ts` | A | nur gelöschter Quelltext (WeatherMetricsTab-Teilung) |
| `shared/__tests__/weather_metric_kuerzel_marken.test.ts` | A | nur gelöschter Quelltext (`kuerzelMarken`) |
| `shared/__tests__/weather_metric_name_forms_visible.test.ts` | A | nur gelöschter Quelltext (Namensformen im Alt-Reiter) |
| `shared/__tests__/weather_metrics_tab_compare_catalog_fetch.test.ts` | A | nur gelöschter Quelltext (Katalog-Abruf des Alt-Reiters) |
| `shared/__tests__/weather_metrics_tab_create_mode_callback.test.ts` | A | nur gelöschter Quelltext (Anlege-Rückruf des Alt-Reiters; Anlegen heute #3305/#3306) |
| `shared/__tests__/weather_metrics_tab_vergleich_uebersicht_kanal_tabs.test.ts` | A | nur gelöschter Quelltext (Kanal-Reiter des Alt-Editors) |
| `shared/__tests__/wetter_metriken_versand_panel_fuehrt_sprung_nach.test.ts` | A | nur gelöschter Quelltext (WetterMetrikenVersandPanel) |
| `shared/__tests__/wetter_metriken_versand_panel_paritaet.test.ts` | A | nur gelöschter Quelltext (WetterMetrikenVersandPanel) |
| `shared/weather-metrics-tab/__tests__/altfelder_gesperrt_s1c3.test.ts` | A | nur gelöschter Quelltext (Sperr-Anzeige der Altfelder im Alt-Reiter; Altfeld-Sperre heute `altfeld_namen_sperre.test.ts`) |
| `shared/weather-metrics-tab/__tests__/multiSymbolMetricRowWiring.test.ts` | A | nur gelöschter Quelltext (Verdrahtung MultiSymbolMetricRow, Waise #3366) |
| `shared/weather-metrics-tab/__tests__/s3a2794_bereich_filter.test.ts` | A | nur gelöschter Quelltext (Bereichsfilter des Alt-Reiters) |
| `shared/weather-metrics-tab/__tests__/weatherMetricsTabSections.test.ts` | A | nur gelöschter Quelltext (`weatherMetricsTabSections.ts`) |
| `shared/weather-metrics-tab/__tests__/weather_metrics_official_alerts_section.test.ts` | A | nur gelöschter Quelltext (Abschnitt Amtliche Warnungen im Alt-Reiter; feste Zeile heute `was_steht_wo_karte.test.ts` „Feste Zeile Amtliche Warnungen“) |
| `shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts` | A | nur gelöschter Quelltext (Sprachprüfung samt Golden `tests/golden/f5_wertebereiche/*`, mit gelöscht) |
| `shared/weather-metrics-tab/__tests__/wetter_metriken_laedt_keine_compare_klebeschicht.test.ts` | A | nur gelöschter Quelltext (Lader des Alt-Reiters) |

## Gruppe B: Altfeld-Logik (10)

Begründung für jede Zeile: **Altfeld bewusst entfallen** – `channel_layouts`, `channel_active_metrics`, `outlook_*`, `hourly_*` sind mit #3276/#3297/#3298/#3351 entfernt (ADR-0124 Nr. 3 eine Reihenfolge für alle Stellen, Nr. 4 keine eigene Ausblick-/Stundenverlaufsliste, Nr. 6 Altfelder). Die Kindmetrik-Ableitung lebt weiter in `trip-detail/metricsEditor.ts` und ist belegt durch `kindmetriken_ableitung_und_mitnahme.test.ts` und `bug_2454_wirkort_verdrahtung.test.ts`.

| Gelöschte Datei | Gruppe | Begründung |
|---|---|---|
| `shared/__tests__/channelMetricLayouts.test.ts` | B | Altfeld `channel_layouts` (Modul `channelMetricLayouts.ts` gelöscht) |
| `shared/__tests__/channelOffGroupListBuilding.test.ts` | B | Altfeld `channel_layouts` (Aus-Gruppe je Kanal) |
| `shared/__tests__/channelPayloadAllChannels.test.ts` | B | Altfeld `channel_layouts` (Nutzlast je Kanal) |
| `shared/weather-metrics-tab/__tests__/bug_2454_channel_ableitung_und_toggle.test.ts` | B | Altfeld `channel_layouts`; Ableitung lebt, belegt durch `bug_2454_wirkort_verdrahtung.test.ts` |
| `shared/weather-metrics-tab/__tests__/lade_kanal_layouts_aus_trip.test.ts` | B | Altfeld `channel_layouts` (Laden je Kanal) |
| `shared/weather-metrics-tab/__tests__/neue_metrik_in_allen_listen.test.ts` | B | Altfeld `channel_layouts` (Einwahl in jede Kanal-Liste; heute gibt es nur eine Liste) |
| `shared/weather-metrics-tab/__tests__/neue_metrik_in_allen_listen_orte.test.ts` | B | Altfelder `channel_active_metrics`/`outlook_metrics`/`hourly_metrics` |
| `shared/weather-metrics-tab/__tests__/speichern_sendet_alle_kanaele.test.ts` | B | Altfeld `channel_layouts` (Speichern aller Kanal-Listen) |
| `shared/weather-metrics-tab/__tests__/speichern_waehlt_richtigen_bestand.test.ts` | B | Altfeld `channel_layouts` (Bestandswahl je Kanal) |
| `shared/weather-metrics-tab/__tests__/wind_chill_kanal_mitnahme_speicherpfad.test.ts` | B | Altfeld `channel_layouts` (Mitnahme je Kanal); Kind-Mitnahme belegt durch `kindmetriken_ableitung_und_mitnahme.test.ts` |

## Gruppe C: lebendes Verhalten (21)

Jede Datei hat genau eine Zeile. Neue Tests dieses Workflows: Frontend `node --test`, Server echter Go-Store mit zwei Nutzern.

| Gelöschte Datei | Entscheidung | Neuer Test bzw. Verweis |
|---|---|---|
| `trip-detail/__tests__/trip_python_skip_next_ohne_412.test.ts` | neuer Test | AC-5 `internal/store/trip_skip_next_erhalt_test.go::TestRework3020_SkipNextBleibtBeimSpeichernOhneFeld_ZweiNutzer`; AC-6 `shared/__tests__/rework_3020_trip_nutzlast_ohne_skip_next.test.ts` |
| `trip-detail/__tests__/trip_versand_reiter_ohne_dauer_keepalive.test.ts` | neuer Test | AC-7 `shared/zustellung-tab/__tests__/rework_3020_zustellung_ifmatch_keepalive.test.ts`; Teilersatz Trip-Speichertakt `trip_speicherung_reicht_keepalive_durch.test.ts::Gegenprobe: regulärer Flush (Feld verlassen) → PUT OHNE keepalive, MIT dem bekannten If-Match` |
| `trip-detail/__tests__/trip_night_block_schalter_verdrahtung.test.ts` | neuer Test | AC-8 bis AC-10 `shared/wetter-tab/__tests__/rework_3020_nachtblock_schalter.test.ts`, Server-Teil AC-9 `internal/store/trip_night_block_altstandard_test.go::TestRework3020_AltTripOhneNightBlockBleibtOhneFeld_ZweiNutzer`; AC-11 abgelöst durch #3305: `organisms/__tests__/was_steht_wo_karte_anlegen_3305.test.ts::Schalter (Nacht-Block): gemeldet mit felder und felderStart, kein Teilfeld-PUT`, Anzeige im Anlegen `organisms/__tests__/rework_3020_karte_schalter.test.ts` |
| `shared/weather-metrics-tab/__tests__/feld_erhalt_ohne_ausnahme.test.ts` | neuer Test | AC-12 `internal/store/trip_display_config_felderhalt_test.go::TestRework3020_SpeichernOhneAenderungErhaeltMetrikFlags_ZweiNutzer` |
| `shared/weather-metrics-tab/__tests__/editor_speichern_ohne_aenderung.test.ts` | neuer Test | AC-12 (derselbe Go-Test, Speichern ohne Änderung im Server) |
| `shared/weather-metrics-tab/__tests__/editor_aenderung_gleich_erwartung.test.ts` | Verweis | `shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts::minus_dann_plus_haengt_hinten_an` |
| `shared/weather-metrics-tab/__tests__/editor_anzeige_gleich_erwartung.test.ts` | Verweis | `shared/wetter-tab/__tests__/p5c_ableitung_hub_orte_ausgabe.test.ts::vorlage_uebernehmen_mail_wie_vor_p5a_und_anzeige_gleich_mail` |
| `shared/weather-metrics-tab/__tests__/editor_standard_gleich_mail.test.ts` | Verweis | `ac26_einstellung_gleich_ausgabe.test.ts::trip_nie_eingestellt_zeigt_register_standard` und `ac26_einstellung_gleich_ausgabe.test.ts::orte_nie_eingestellt_zeigt_alle_zeilen_und_gesperrtes`; die 22 Katalogfälle `frontend_seite_*` siehe unten (R1b) |
| `shared/versand-tab/__tests__/premium_sms_context_gating_render.test.ts` | neuer Test | AC-13 `shared/zustellung-tab/__tests__/rework_3020_premium_sms_schaltbar.test.ts` (route) |
| `shared/versand-tab/__tests__/compare_versand_zeigt_schaltbare_premium_sms.test.ts` | neuer Test | AC-13 dieselbe Datei (Kontext `vergleich`) |
| `shared/versand-tab/__tests__/versand_tab_defaults_gleich_auslieferung.test.ts` | neuer Test | AC-14 `shared/zustellung-tab/__tests__/rework_3020_defaults_gleich_auslieferung.test.ts` (route und vergleich) |
| `shared/__tests__/mail_inhalt_haken_grosswetterlage_3237.test.ts` | neuer Test | AC-15 `organisms/__tests__/rework_3020_karte_schalter.test.ts` |
| `shared/weather-metrics-tab/__tests__/vorlage_anwenden_uebernimmt_ampel.test.ts` | Verweis | `fix_3193_vorlage_abweichung_minimal.test.ts::trip_uebernehmen_wandern_aboampel_mit_abgeleiteten_kindern` |
| `shared/__tests__/wetter_metriken_vorlage_anwenden_sendet_ampel.test.ts` | Verweis | `fix_3193_vorlage_abweichung_minimal.test.ts::trip_uebernehmen_wandern_aboampel_mit_abgeleiteten_kindern` und `fix_3193_vorlage_abweichung_minimal.test.ts::vergleich_uebernehmen_wandern_aboampel_temperature_night_neutral` |
| `shared/__tests__/wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte.test.ts` | neuer Test | AC-17 `shared/wetter-tab/__tests__/rework_3020_ausblick_warnungswerte_nutzlast.test.ts`; Server `internal/store/trip_metric_alert_levels_test.go::TestRework3020_WarnungswerteUndAusblickJeNutzerGetrennt` und `trip_display_config_felderhalt_test.go::TestRework3020_TeilUpdateAusblickUndWarnungswerteErhaeltUebrigeFelder_ZweiNutzer` |
| `shared/weather-metrics-tab/__tests__/telegram_kanalgrenze_je_kontext.test.ts` | Verweis | `organisms/__tests__/was_steht_wo_karte.test.ts::Trip: „nur Tageswert“, „passt nicht mehr“, Zeile mit max_length und Hinweissatz für Trip` (ADR-0124 Nr. 3, Trip); Katalogfall `E-3020-TRIP-TG-NUR-TAGESWERT`; Browser-Fall #3375 |
| `shared/weather-metrics-tab/__tests__/telegram_schnittlinie_wahr.test.ts` | Verweis | derselbe Test wie oben; `LTCutLine` entfallen |
| `shared/weather-metrics-tab/__tests__/sms_reiter_roh_einfach_nur_fuer_sms_format_capable.test.ts` | begründeter Status | `ausnahme`, ADR-0124 Nr. 5 (SMS ohne Roh/Einfach-Wahl). Die Karte prüft das Gegenstück: `was_steht_wo_karte.test.ts::Knopf nur bei Haken und zwei Formen, nie in der SMS-Spalte`. Im Katalog gibt es keinen eigenen Editor-Fall dazu |
| `shared/weather-metrics-tab/__tests__/nur_ein_bericht_kennzeichnung.test.ts` | begründeter Status | `ausnahme`, #3065 (geschlossen) und Prod-Messung 25.11.2026 (0 Metriken nur in einem Bericht); die vier Katalogfälle `n3_*` siehe unten |
| `shared/__tests__/wetter_metriken_versand_panel_speicherung.test.ts` | neuer Test (F001) | Der Vergleichs-Block prüfte zwei parallele Schreiber an einem Controller, einer Hub-Schlange (`createPutQueue`, `compareHubPersistenz.ts`) und einer Basis, damals über die Fabriken aus `versandVergleichSpeicherung.ts`/`weatherMetricsCompareSave.ts` (heute ohne Produktionsaufrufer). Heute dieselbe Lage mit den lebenden Schreibern aus CompareTabs (Reiter Wetter `SPEICHERER.vergleich`, Reiter Zustellung `erstelleZustellungSpeicherung`): `shared/__tests__/rework_3020_vergleich_parallele_schreiber.test.ts` (beide Reihenfolgen, kein 412, höchstens ein PUT unterwegs, Warten hinter einem fremden Hub-Schreiber). Der Trip-Block (`route`) prüfte nur gelöschten Quelltext (WeatherMetricsTab/BriefingScheduleTab) |
| `shared/weather-metrics-tab/__tests__/thunderThresholdCatalogGuard.test.ts` | Verweis | `shared/weather-metrics-tab/__tests__/thunderThresholdLevels.test.ts::leerer Katalog -> leere Liste, kein Wurf` und `thunderThresholdLevels.test.ts::undefined (Katalog noch nicht geladen) -> leere Liste, kein Wurf` (`deriveThunderThresholdLevels` lebt in `compareMetricCatalogLoader.ts`; #3366 darf diesen Test nicht mitlöschen) |

## Die 26 bisher falsch-grünen Katalogfälle `D-*-frontend` (R1b)

`tests/fixtures/einstellung_gleich_mail/fallliste_editor.json`. Bis #3020 verwiesen sie ohne Dateiangabe auf Titel der gelöschten `editor_standard_gleich_mail.test.ts`/`nur_ein_bericht_kennzeichnung.test.ts` und galten nur wegen der reinen Platzhalter-Vorlage `${key}` als gefunden. Kürzel: `ac26` = `shared/wetter-tab/__tests__/ac26_einstellung_gleich_ausgabe.test.ts`, `p5c` = `shared/wetter-tab/__tests__/p5c_ableitung_hub_orte_ausgabe.test.ts`, `karte` = `organisms/__tests__/was_steht_wo_karte.test.ts`, `3297` = `trip-new/__tests__/trip_pfad_ohne_altfelder_3297.test.ts::Reiter Wetter: beide PUTs ohne Altschluessel, Bestand sonst erhalten`, `nutzlast` = `shared/weather-metrics-tab/__tests__/wetter_metriken_nutzlast_verliert_keine_daten.test.ts::Kanal-Auswahl geändert → der Rumpf trägt nur Eigenfelder, keinen Altschluessel (#3276)`, `go-flags` = `internal/store/trip_display_config_felderhalt_test.go::TestRework3020_SpeichernOhneAenderungErhaeltMetrikFlags_ZweiNutzer`.

| Fall | Status | Verweis |
|---|---|---|
| `D-trip_tabellen-nie_eingestellt-frontend` | gruen | `ac26::trip_nie_eingestellt_zeigt_register_standard` |
| `D-trip_tabellen-altbestand_ohne_metrics-frontend` | gruen | `ac26::anzeige_gleich_ausgabe_a_nie_eingestellt_ohne_metrics` |
| `D-trip_tabellen-gespeichert_folge-frontend` | gruen | `karte::Zeilen in der Folge der Antwort mit Namen aus der Antwort` |
| `D-trip_tabellen-gespeichert_folge_array_ungleich_order-frontend` | ausnahme | ADR-0124 Nr. 3, Altfeld `channel_layouts`; Test `3297` |
| `D-trip_tabellen-gespeichert_ausserhalb_grundauswahl-frontend` | ausnahme | ADR-0124 Nr. 1/Nr. 3, Altfeld `channel_layouts`; Test `3297` |
| `D-trip_tabellen-gespeichert_totalschnitt-frontend` | ausnahme | ADR-0124 Nr. 3, Altfeld `channel_layouts`; Test `3297` |
| `D-trip_tabellen-totalschnitt_aus_wirkt-frontend` | ausnahme | ADR-0124 Nr. 3, Altfeld `channel_layouts`; Test `3297` |
| `D-trip_tabellen-hinweis_grundauswahl_leer-frontend` | gruen | `karte::leere Grundauswahl: sachlicher Leertext statt Tabelle` (geteilter, kontextfreier Zweig; Test rendert `vergleich`) |
| `D-trip_ausblick-nie_eingestellt-frontend` | gruen | `ac26::anzeige_gleich_ausgabe_a_trend_nie_eingestellt` |
| `D-trip_ausblick-gespeichert_folge-frontend` | ausnahme | ADR-0124 Nr. 4, Altfeld `outlook_metrics`; Test `3297` |
| `D-trip_ausblick-gespeichert_ausserhalb_grundauswahl-frontend` | ausnahme | ADR-0124 Nr. 4, Altfeld `outlook_metrics`; Test `3297` |
| `D-trip_ausblick-gespeichert_totalschnitt-frontend` | ausnahme | ADR-0124 Nr. 4, Altfeld `outlook_metrics`; Test `3297` |
| `D-trip_ausblick-bewusst_leer_alle_aus-frontend` | gruen | `ac26::anzeige_gleich_ausgabe_a_bewusst_leer` |
| `D-trip_ausblick-grundauswahl_ohne_ausblick-frontend` | gruen | `karte::gesperrt mit Grundtext je reason, nicht in der E-Mail, ab` |
| `D-trip_vorlage-reihenfolge-frontend` | gruen | `p5c::anlegen_alpen-trekking_anzeige_gleich_mail` (Server-Seite `TestF3047_NeuerTripAusVorlageBehaeltVorlagenFolge`) |
| `D-orte_vergleichstabelle-nie_eingestellt-frontend` | gruen | `ac26::orte_nie_eingestellt_zeigt_alle_zeilen_und_gesperrtes` |
| `D-orte_vergleichstabelle-gespeichert_folge-frontend` | gruen | `karte::Zeilen in der Folge der Antwort mit Namen aus der Antwort` (geteilter Zweig; Test rendert `route`) |
| `D-orte_vergleichstabelle-gespeichert_kanal_liste-frontend` | ausnahme | ADR-0124 Nr. 3, Altfeld `channel_active_metrics`; Test `nutzlast` |
| `D-orte_vergleichstabelle-gespeichert_kanal_totalschnitt-frontend` | ausnahme | ADR-0124 Nr. 3, Altfeld `channel_active_metrics`; Test `nutzlast` |
| `D-orte_vergleichstabelle-totalschnitt_aus_wirkt-frontend` | ausnahme | ADR-0124 Nr. 3, Altfeld `channel_active_metrics`; Test `nutzlast` |
| `D-orte_vergleichstabelle-grundauswahl_bewusst_leer-frontend` | gruen | `ac26::anzeige_gleich_ausgabe_a_bewusst_leer` (Orte, `active_metrics: []`) |
| `D-orte_vergleichstabelle-hinweis_grundauswahl_leer-frontend` | gruen | `karte::leere Grundauswahl: sachlicher Leertext statt Tabelle` |
| `D-trip_tabellen-nur_ein_bericht_semantik-frontend` | ausnahme | #3065, Prod-Messung; Test `go-flags` (`seite: go`) |
| `D-trip_tabellen-nur_ein_bericht_kennzeichnung-frontend` | ausnahme | #3065, Prod-Messung; Test `go-flags` (`seite: go`) |
| `D-trip_tabellen-nur_ein_bericht_editorstand-frontend` | ausnahme | #3065, Prod-Messung; Test `go-flags` (`seite: go`) |
| `D-trip_tabellen-bericht_flags_bewahrt-frontend` | ausnahme | #3065, Prod-Messung; Test `go-flags` (`seite: go`) |

Neu angelegt (AC-4): `E-3020-TRIP-TG-NUR-TAGESWERT`, Status `gruen`, Test `karte::Trip: „nur Tageswert“, „passt nicht mehr“, Zeile mit max_length und Hinweissatz für Trip` (ADR-0124 Nr. 3; Browser-Fall #3375).

## Die 17 mit #3357 gestrichenen Katalogfälle

Alle standen auf `gruen`; ihre Testdateien prüften nur den gelöschten Alt-Editor.

| Fall (Datei) | Gelöschter Test | Verweis bzw. Status heute |
|---|---|---|
| `E-P12-TL3-ORTE-KURZSTIL` (editor) | `p12_zustellung_gleich_ausgabe.test.ts::tl3_kurzstil_gleich_telegram_a_kurzstil` (Fall aus der Datei entfernt; las `kanalStilStart`) | entfallen; Kurzstil heute in der Karte: `was_steht_wo_karte.test.ts::Kurzstil: Telegram-Spalte „Kurzstil: wie SMS“, Haken nicht bedienbar, keine Marke` |
| `E-R8-F3-ORTE-TG-DE` (editor) | `telegram_schnittlinie_wahr.test.ts::vergleich/de: …` | entfallen: ADR-0124 Nr. 3 kennt die Telegram-Grenze nur beim Trip; `LTCutLine` gelöscht |
| `E-R8-F3-ORTE-TG-EN` (editor) | `telegram_schnittlinie_wahr.test.ts::vergleich/en: …` | entfallen wie oben |
| `E-R8-F3-TRIP-TG-DE` (editor) | `telegram_schnittlinie_wahr.test.ts::route/de: …` | ersetzt durch `E-3020-TRIP-TG-NUR-TAGESWERT` (gruen, Kartentest „nur Tageswert“) |
| `E-R8-F3-TRIP-TG-EN` (editor) | `telegram_schnittlinie_wahr.test.ts::route/en: …` | ersetzt durch `E-3020-TRIP-TG-NUR-TAGESWERT`; Englisch der Karte: `was_steht_wo_karte.test.ts::alle Texte englisch, Namen und Kürzel aus der Antwort unverändert` |
| `E-R8-F3-TRIP-REITER` (editor) | `telegram_schnittlinie_wahr.test.ts::WeatherMetricsTab Trip, Telegram-Reiter (9 Metriken) …` | ersetzt durch `E-3020-TRIP-TG-NUR-TAGESWERT` |
| `E-R8-F3-ORTE-REITER` (editor) | `telegram_schnittlinie_wahr.test.ts::WeatherMetricsTab Orts-Vergleich, Telegram-Reiter (9 Zeilen) …` | entfallen: Alt-Reiter je Kanal (ADR-0124 Nr. 2/Nr. 3) |
| `E-R8-T1-SMS-LADEN-A` (editor) | `lade_kanal_layouts_aus_trip.test.ts::Nutzer A: …` | entfallen: Altfeld `channel_layouts` (ADR-0124 Nr. 3), Gruppe B |
| `E-R8-T1-SMS-LADEN-B` (editor) | `lade_kanal_layouts_aus_trip.test.ts::Nutzer B: …` | entfallen wie oben |
| `E-R8-F3N-ORTE-HINWEIS-DE` (editor) | `telegram_kanalgrenze_je_kontext.test.ts::de: 9 Zeilen …` | entfallen: Orte ohne Telegram-Grenze (ADR-0124 Nr. 3 nur Trip) |
| `E-R8-F3N-ORTE-HINWEIS-EN` (editor) | `telegram_kanalgrenze_je_kontext.test.ts::en: 9 Zeilen …` | entfallen wie oben |
| `E-R8-F3N-ORTE-EINE-DE` (editor) | `telegram_kanalgrenze_je_kontext.test.ts::de: 5 Zeilen …` | entfallen wie oben |
| `E-R8-F3N-ORTE-EINE-EN` (editor) | `telegram_kanalgrenze_je_kontext.test.ts::en: 5 Zeilen …` | entfallen wie oben |
| `E-R8-F3N-ORTE-EMAILREITER` (editor) | `telegram_kanalgrenze_je_kontext.test.ts::E-Mail-Reiter des Vergleichs …` | entfallen: Alt-Reiter je Kanal |
| `E-R8-F3N-TRIP-STUNDENTABELLE` (editor) | `telegram_kanalgrenze_je_kontext.test.ts::9 Metriken, Telegram-Reiter: Badge 7, Chip −2, Hinweis zu breit` | ersetzt durch `E-3020-TRIP-TG-NUR-TAGESWERT` |
| `O-VT-H-NEU-IN-LISTEN` (orte) | `neue_metrik_in_allen_listen_orte.test.ts::Einwahl haengt die Metrik an jede gespeicherte Kanal-Liste hinten an, Folge bleibt` | entfallen: Altfelder `channel_active_metrics`/`outlook_metrics`/`hourly_metrics` (ADR-0124 Nr. 3/Nr. 4), Gruppe B; „wieder hinzugefügt steht hinten“ belegt `ac26::minus_dann_plus_haengt_hinten_an` |
| `trip-ac10--neu_in_bearbeitetem_layout--html` (trip) | `neue_metrik_in_allen_listen.test.ts::Einwahl haengt die Metrik in jeder bearbeiteten Kanal-Liste hinten an, Folge bleibt` | entfallen: Altfeld `channel_layouts` (ADR-0124 Nr. 3), Gruppe B; Ersatz wie oben `ac26::minus_dann_plus_haengt_hinten_an` |
