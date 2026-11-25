# Context: Rework #3020 R1/R2 + #3366 + #3374 (Prüfungen wiederherstellen, Waisen löschen, tote Browser-Prüfungen)

Stand: origin/main a0a801a0b (25.11.2026, nach #3357 = c8329fea4, #3298, #3301, #3359). Reine Bestandsaufnahme, keine Änderung an Code, Tests oder Daten.
Messskripte (nicht im Repo): `/tmp/claude-1000/-home-hem-gregor-zwanzig/f54b53b5-b98a-45c6-9fc2-f81d68bd3405/scratchpad/` (`waisen.py` Import-Analyse, `verweis.py` Katalog-Verweisprüfung, `faelle.py` Fallzählung, `refs*.py`, `keys.py`).

## Request Summary

Ein Paket aus drei Issues (Sitzung gregor-zwanzig-d3, Epic #3122):

- **#3020 (wieder geöffnet, R1/R2):** R1 = mit #3357 entfallene Prüfungen am lebenden Code wiederherstellen und die 26 falsch-grünen `D-*-frontend`-Katalogfälle samt Verweisprüfung korrigieren; R2 = Restbestand an Alt-Dateien ohne Produktionsaufrufer löschen. Nicht zusammen mit anderen Issues schließen. Eine Spec `rework_3020_altbausteine_entfernen.md` (2.0) und der S1-Zwischenstand (Commit 8b9749601, Testtabelle 161 Zeilen) existieren in diesem Baum nicht (nur im Issue-Kommentar beschrieben); neuer Durchlauf.
- **#3366:** über 40 Frontend-Module ohne Produktionsaufrufer löschen, samt Tests, die nur sie prüfen; Nachweis per transitiver Import-Prüfung ab `frontend/src/routes/`; Lösch-Nachweis-Test. Kein Altfeld-Bezug (der liegt in #3298), keine sichtbare Änderung. Laut Abstimmung (25.11. 20:37/20:38) wird #3366 gemeinsam mit #3020 R2 und #3374 erledigt.
- **#3374:** tote Browser-Prüfungen des Alt-Editors außerhalb der CI-Positivliste neu schreiben oder streichen; `compare-hourly-metric-order` AC-4 zuerst als möglichen echten Fehler prüfen.
- Sperre: `frontend/src/lib/components/molecules/EinstellTabelle.svelte` (hat aktive Aufrufer, wird von anderer Sitzung geändert) nicht anfassen, nicht auf die Löschliste. Bestätigt: Aufrufer `organisms/wetter-tab/WasStehtWoKarte.svelte`, `shared/wetter-tab/wasStehtWoAnsicht.ts`, `molecules/index.ts`, `routes/_design-system/einstelltabelle/+page.svelte`. Sie taucht in der Waisenliste nicht auf.

## Related Files

- Zuordnung gelöschter Tests: `docs/artifacts/feat-3297-trip-pfad-ohne-altfelder/geloeschte-tests.md` (im Baum; zählt 64 Dateien = 60 `.test.ts` + 4 Hilfsdateien), Spec `docs/specs/modules/feat_3297_trip_pfad_ohne_altfelder.md`, Kontext `docs/context/feat-3297-trip-pfad-ohne-altfelder.md`.
- Katalog „Einstellung = Mail“: `tests/fixtures/einstellung_gleich_mail/fallliste_{editor,orte,trip,sms,telegram,premium_sms,validatoren}.json`, Prüftest `tests/tdd/test_einstellung_gleich_mail_fallliste.py` (898 Zeilen).
- Ratschen/Wächter, die Waisen-Pfade führen (alle sind Test-/Daten-Dateien, KEINE Hook-Dateien):
  - `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` (BESTAND, `BESTAND_OBERGRENZE = 188` Zeile 726)
  - `frontend/src/lib/__tests__/ink4_waechter.test.ts`
  - `tests/unit/ein_katalog_ausnahmen.json` + `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py`
  - i18n-Scanner: `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts`, `reaktivitaet_waechter.test.ts`, `katalog_schluessel_haben_verwender.test.ts`
  - Prüfstände/Anker: `shared/versand-tab/__tests__/{f6VersandSsr.ts,f6KatalogAnker.ts}`, `shared/layout-tab/__tests__/{f8Pruefstand.ts,f8KatalogAnker.ts,LayoutTabPruefstand.svelte}`, `trip-detail/__tests__/f9Pruefstand.ts`, `compare/__tests__/{f10Pruefstand.ts,f10KatalogAnker.ts}`, `shared/weather-metrics-tab/__tests__/f5KatalogAnker.ts`; Goldens `tests/golden/{f6_versand_tab,f8_layout_korridor,f9_trip_flaechen,f10_vergleich_flaechen}`
  - Python-Tests mit Waisen-Pfad: `tests/tdd/test_issue_316_docs_cleanup.py` (LocationPreviewMap, WaypointPin), `tests/integration/test_trip_alert_stage_name.py:210` (EditRouteSection), `tests/tdd/test_issue_692_telegram_disabled_unconfigured.py` (WeatherV2Kanaele), `tests/tdd/test_sms_snow_symbols.py` (ThresholdMetricRow), `tests/unit/test_2243_playwright_loeschscheibe.py` (naturalSort)
- NICHT betroffen (geprüft): `.claude/hooks/pendant_gate.py` `BEKANNTE_PAARE` (Zeile 74-85) enthält nur fünf Python-Paare `src/services/*`, kein Frontend-Pfad; `frontend/src/lib/altfeld_namen_sperre.test.ts` hat `ERLAUBT = {}` (Zeile 48), führt keinen Waisen-Pfad (einzige Pfadangabe: `lib/components/compare/hourlyFriendlyMap.ts`, bereits gelöscht, Zeile 219). Keine Hook-Änderung nötig.
- #3374-Specs: `frontend/e2e/*.spec.ts`; CI-Positivliste `.github/ci_e2e_specs.txt` (86 Einträge, `E2E_MIN_SPECS: 86` in `ci.yml:328`).

## Existing Patterns

- Löschen im selben Umbau samt Tests (Regel #3207, Inventur `docs/specs/modules/tote_tests_inventur.md`), Muster aus #3297 (Zuordnungsliste `geloeschte-tests.md` + Lösch-Nachweis-Test `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts`).
- BESTAND-Ratsche (ADR-0112) darf nur sinken: `pruefeBestandsliste` meldet jede in BESTAND eingetragene, nicht mehr vorhandene Datei als Fehler (`bausteine_waechter_regeln.ts` Zeile ~437: „steht in BESTAND, existiert nicht mehr“). Beim Löschen von .svelte also Eintrag streichen und Obergrenze senken.
- `ein_katalog_ausnahmen.json`: abgebaute Stelle ohne verkleinerte Liste macht rot (`test_abgebaute_stelle_ohne_verkleinerte_liste_macht_rot`, Zeile 248).
- Katalog-Verweis `datei.test.ts::Titel` bzw. nur Titel; Prüfer `_pruefe_vitest_verweis` (Zeile 209).

## Dependencies

- #3298 (Altfeld-Typen/Sperre, gemergt) behält Typen und `altfeld_namen_sperre.test.ts`. #3301 (gemergt, `compareHourlyMetricDefs.ts`/`hourlyFriendlyMap.ts` gelöscht, nicht mehr im Baum). #3359 (E2E ohne Altfelder, gemergt, hat `compare-hourly-metric-order` AC-4 bereits umgeschrieben). #3351 (Datenlauf Altfelder, gemergt).
- #3122 (Karte „Was steht wo“) ist der Ersatz-Ort; Ersatzprüfungen liegen in `organisms/__tests__/was_steht_wo_karte*.test.ts`, `rework_3036_*`, `shared/wetter-tab/__tests__/*`, `shared/zustellung-tab/__tests__/*`, E2E `was-steht-wo-karte.spec.ts` (Positivliste).
- Offene Produktfrage #3358 (Vorlage folgt beim Trip-Anlegen nicht der Fortbewegung).

## Existing Specs

- `docs/specs/modules/feat_3297_trip_pfad_ohne_altfelder.md` (Test-Zuordnung), `feat_3298_altfeld_typen_sperre.md`, `feat_3276_vergleich_altfelder_entfernen.md`, `feat_3333_zustellung_anlegen_orte.md`, `feat_3154_karte_abgleich.md`, `feat_3122_was_steht_wo.md`, `tote_tests_inventur.md`.
- Nicht vorhanden: `rework_3020_altbausteine_entfernen.md`; Spec ist neu zu schreiben (Abschnitt Risks: Zahlen bleiben nicht stabil).

## Risks & Considerations

1. **Größtes Risiko: Waisen-Löschung reißt Prüfstände, Goldens, Wächter und i18n-Schlüssel mit.** `f6VersandSsr.ts` rendert nur VT*-Waisen (Goldens `f6_versand_tab` komplett tot), `f8Pruefstand.ts` rendert LayoutTab/LT*, `f9Pruefstand.ts`/`f10Pruefstand.ts` rendern gemischt (leben weiter, Waisen-Teile müssen heraus, ca. 12 Test-Dateien hängen daran). Geschätzt 128 Katalogschlüssel verlieren ihren einzigen Verwender (`katalog_schluessel_haben_verwender.test.ts` wird rot) und müssen aus de/en entfernt werden (Liste unten). 26 von 27 .svelte-Waisen stehen in BESTAND (Obergrenze 188 senken). Löschen ohne diese Nacharbeit = rote CI.
2. **Falsch-Grün im Katalog ist ein Wächter-Fehler, nicht nur ein Datenfehler** (R1b): jede künftige Löschung kann dasselbe wieder verdecken, solange `_template_muster('${key}')` alles akzeptiert.
3. **Beleglücke bei lebendem Verhalten** (R1): Trip-Schreibpfad (`skip_next` darf nicht still zurückgeschrieben werden, If-Match/keepalive-Flush, `show_night_block`-Standard bei Alt-Trips, Feld-Erhalt `display_config.metrics`, Premium-SMS-Schaltbarkeit im Vergleich, „Defaults = Auslieferung“) hatte Tests nur über die gelöschten Komponenten; Ersatz ist teils vorhanden, teils nicht gemessen.
4. **Produktfragen statt Testfragen:** Funktionen, die der Alt-Editor hatte und die in der lebenden Oberfläche keinen Code mehr haben: Telegram-Schnittlinie „max 7“ (`LTCutLine` Waise, Schlüssel `layout.kappung.schnittlinie_*`), SMS-Umschalter Roh/Einfach nur für `sms_format_capable` (kein Treffer im Frontend-Code), „Nur-ein-Bericht“-Kennzeichnung (`nurEinBericht.ts` Waise; Katalogfälle `D-trip_tabellen-nur_ein_bericht_*` stehen auf grün), Kürzel-Legende. Hier nicht still löschen: PO-Entscheidung, ob die Funktion bewusst entfällt (ADR) oder neu gebaut wird.
5. **Tote Exporte in lebenden Dateien:** Datei-Analyse sieht sie nicht. `trip-detail/metricsEditor.ts` und `shared/layout-tab/ltChannels.ts` sind erreichbar, haben aber Exporte ohne Produktionsaufrufer (z. B. `autoAssign`, `bucketsToColumns`, `deriveMissingChildMetrics`, `computeInitialBuckets`, `ltKanalAbwahlHinweisText`, `LT_CH_BY_ID`). Nicht Teil von #3366 (Dateiebene); als Nebenbefund melden.
6. LoC-Limit des Commit-Gates: Löschung von rund 4 000 Quell- plus Testzeilen; in Scheiben schneiden (z. B. nach Familie: layout-tab, versand-tab, weather-metrics-tab, Rest).
7. Sperre EinstellTabelle: nicht berühren; `molecules/index.ts` und `GrundauswahlLeerHinweis.svelte` (Waise, nur in `molecules`, nicht in BESTAND) nur mit Rücksicht auf die andere Sitzung anfassen (kein Konflikt in `index.ts` nötig: die Waise wird dort nicht exportiert).

## Analysis

### R1: Was PR #3357 (c8329fea4) gelöscht hat

Messung: `git diff --diff-filter=D --name-only c8329fea4^1 c8329fea4` = 90 gelöschte Dateien (17 629 Zeilen):

- 12 Produktionsdateien (WeatherMetricsTab, WetterMetrikenVersandPanel, BriefingScheduleTab, VersandTab, MailInhaltCard, OutlookLayoutControls, WeatherV2Reihenfolge, channelMetricLayouts, weatherMetricsSavePayload, weatherMetricsTabSections, kuerzelLegende, kuerzelMarken)
- 60 Testdateien `*.test.ts` mit zusammen **337 Testfällen** (Titelzählung `test(`/`it(`; Template-Titel zählen je einmal)
- 4 Hilfsdateien (`_editor_kette.ts`, `erzeuge_nach_dateien.ts`, `f5Pruefstand.ts`, `f5VarianteHook.mjs`)
- 14 Golden-Dateien `tests/golden/f5_wertebereiche/*`
- Zuordnungsliste `geloeschte-tests.md` nennt 64 Dateien (60 + 4 Hilfsdateien) und eine gelöschte Python-Funktion `tests/tdd/test_issue_934_wizard_schedule.py::TestBug1KeineDoppelteUI::test_bundle_metriken_tab_hat_keine_zeitplan_render_calls`.

**Nachprüfung der Kommentar-Zahlen (13:55-Kommentar):**

| Aussage | Messung |
|---|---|
| 60 Testdateien | stimmt (60 `.test.ts`; plus 4 Hilfsdateien) |
| 145 Fälle | gemessen **143** per Titelvergleich in **50** weiterlaufenden Testdateien (Multimengen-Differenz Vorher/Nachher, enthält Umbenennungen und gestrichene Alt-Quelltext-Prüfungen); Abweichung 2 durch Titel-Template/Regex-Grenzen, Größenordnung bestätigt. Die 337 Fälle der 60 gelöschten Dateien sind darin NICHT enthalten. |
| 15 Katalogfälle | stimmt: `fallliste_editor.json` −197 Zeilen = 15 Fälle `E-*` (u. a. `E-R8-F3-*`, `E-R8-T1-SMS-LADEN-A/B`, `E-P12-TL3-ORTE-KURZSTIL`, `E-R8-F3N-*`), alle `gruen` |
| 2 weitere Katalogfälle | stimmt: `O-VT-H-NEU-IN-LISTEN` (fallliste_orte.json) und `trip-ac10--neu_in_bearbeitetem_layout--html` (fallliste_trip.json); beide hatten Status `gruen`, `_hinweis`-Feld erklärt die Streichung |
| Weitere Änderung | Prüftest `test_template_literal_titel_alle_gefunden` wurde in #3357 angepasst: die Zusicherung „Muster gefunden“ wird jetzt nur noch an verwiesenen Dateien geprüft (weil `editor_standard_gleich_mail`/`neue_metrik_in_allen_listen*` weg sind) |

Weiterlaufende Dateien mit den meisten entfallenen Fällen (Top): `trip_reiter_roundtrip_jedes_feld` 13, `officialAlertLegend` 11, `kanal_abwahl_hinweis` 9, `mail_inhalt_zustand` 9, `merge_report_config_read_modify_write` 8, `trip_night_block_schalter_nutzlast` 6, `standardwerte_payload_paritaet_trip` 6, `daywindowcard_rueckbau_waechter` 5, `trip_reiter_nutzlast_nur_eigene_felder` 4, `naechstes_briefing_verdrahtung` 4. Volle Liste: Scratchpad `faelle.json`.

**Klassifizierung der 60 gelöschten Testdateien** (Heuristik: welche lebenden Produktionsmodule importierte der Test; was existiert heute; gibt es Ersatz). Nicht jede Datei wurde zeilenweise gelesen; Gruppe C ist die Messliste für R1.

*Gruppe A: prüfte nur gelöschten Quelltext (Struktur/Verdrahtung/SSR der entfernten Komponenten), kein lebender Code, kein Ersatz nötig (ca. 33 Dateien):*
`weatherMetricsTabSharing`, `weatherMetricsTabSections`, `s3a2794_bereich_filter`, `s3a2794_speicher_owner_waechter`, `speicher_anzeige_zwischenstand_wetter_und_briefing`, `versand_tab_meldet_aenderungen_reaktiv`, `versand_tab_laedt_keine_compare_klebeschicht`, `wetter_metriken_laedt_keine_compare_klebeschicht`, `wetter_metriken_versand_panel_{fuehrt_sprung_nach,paritaet,speicherung}`, `compare_wetter_metriken_wertprops`, `compare_versand_wertprops`, `compare_outlook_metric_selection_structure`, `outlook_{email_only_hint_per_context,erbt_grundauswahl_structure,restore_schreibt_nur_outlook_metrics}`, `mail_inhalt_card`, `mail_inhalt_card_hub_einbindung`, `multiSymbolMetricRowWiring`, `thunderThresholdCatalogGuard`, `weather_metrics_tab_{compare_catalog_fetch,create_mode_callback,vergleich_uebersicht_kanal_tabs}`, `weather_metric_{name_forms_visible,kuerzel_marken}`, `metricKuerzelLegende`, `ausblick_ein_name_3155`, `wertebereiche_sprache` (Golden f5), `weather_metrics_official_alerts_section`, `altfelder_gesperrt_s1c3`, plus Hilfsdateien. Hinweis: `mail_inhalt_card_hub_einbindung` importierte die jetzt verwaisten `reportConfigDirty.ts`/`weatherSaveGate.ts`.

*Gruppe B: Altfeld-Logik (`channel_layouts`/`outlook_*`/`hourly_*`) in gelöschten Modulen; Altfelder sind per #3276/#3298/#3351 bewusst entfallen, kein lebender Code (ca. 11 Dateien):*
`channelMetricLayouts`, `channelOffGroupListBuilding`, `channelPayloadAllChannels`, `bug_2454_channel_ableitung_und_toggle`, `lade_kanal_layouts_aus_trip`, `neue_metrik_in_allen_listen`, `neue_metrik_in_allen_listen_orte`, `speichern_sendet_alle_kanaele`, `speichern_waehlt_richtigen_bestand`, `wind_chill_kanal_mitnahme_speicherpfad`, `vorlage_anwenden_uebernimmt_ampel` (Teil). Die Kindmetrik-Ableitung lebt in `trip-detail/metricsEditor.ts` und hat noch `kindmetriken_ableitung_und_mitnahme.test.ts`, `bug_2454_wirkort_verdrahtung.test.ts`.

*Gruppe C: Verhalten, das im lebenden Code weiterexistiert (Schreibpfad/Anzeige), Ersatz teils vorhanden, teils zu messen (ca. 16 Dateien):*

| Gelöschter Test (Fälle) | Was heute nicht mehr (so) geprüft wird | Lebender Ort / Ersatz |
|---|---|---|
| `trip_python_skip_next_ohne_412` (7) | von Telegram/SMS gesetztes `report_config.skip_next` darf durch einen offenen Reiter nicht still überschrieben werden (Versandzeit, Kanal, Tagesfenster, Mail-Anzeige, Metrik-Auswahl; frischer und veralteter ETag) | Im Frontend gibt es keinen `skip_next`-Code mehr; Schutz liegt im Schreibpfad (`tripSpeicherung.ts`, `pickEigenfelder.ts`, `wasStehtWoSpeicherung.ts`). Teil-Ersatz: `pick_eigenfelder_kernregel`, `trip_reiter_nutzlast_nur_eigene_felder`, `fakeTripServerGoMerge`. **Messen** |
| `trip_versand_reiter_ohne_dauer_keepalive` (6) | Versand-PUT trägt If-Match, kein keepalive, Flush mit `keepalive:true`, Antwort-Stempel | Ersatz plausibel: `trip_speicherung_reicht_keepalive_durch`, `wetter_metriken_nutzlast_reicht_keepalive_durch`; Zustellung-Reiter selbst **messen** |
| `trip_night_block_schalter_verdrahtung` (8) | Schalter nur Trip/bestehend, Alt-Trip ohne Feld = an, Wert wird dann nicht gesendet, Verwerfen setzt Sende-Merker zurück | Lebt in `WasStehtWoKarte.svelte`/`wasStehtWoSpeicherung.ts`; Ersatz: `rework_3036_bloecke_schalter`, `was_steht_wo_karte*`. Fall „Alt-Trip ohne Feld sendet nichts“ **messen** |
| `feld_erhalt_ohne_ausnahme` (3), `editor_speichern_ohne_aenderung`, `editor_aenderung_gleich_erwartung`, `editor_anzeige_gleich_erwartung`, `editor_standard_gleich_mail` (19) | Speichern ohne Änderung erhält `display_config.metrics.morning_enabled/evening_enabled/format_mode`; Editor-Anzeige = Mail-Standard (26 Katalogfälle `D-*-frontend`, siehe R1b) | Ersatz teilweise: `ac26_einstellung_gleich_ausgabe`, `p5c_ableitung_hub_orte_ausgabe`, `p12_zustellung_gleich_ausgabe`; für die 26 D-Fälle **kein** Test |
| `premium_sms_context_gating_render` (2), `compare_versand_zeigt_schaltbare_premium_sms` (1), `versand_tab_defaults_gleich_auslieferung` (1) | Premium-SMS-Kästchen folgt Handler-Präsenz; Vergleich zeigt schaltbaren Premium-SMS-Block; Versand-Standardwerte = Auslieferung | `zustellungModell.ts` und `zustellung-tab/__tests__/{zustellungModell,zustellungSpeicherung,feat3202_kanalzeile_mockup}.test.ts` erwähnen Premium; Gegenprobe „Defaults = Auslieferung“ (`standardwerte_payload_paritaet_trip` verlor 6 Fälle) **messen** |
| `mail_inhalt_haken_grosswetterlage_3237` (3) | Haken Großwetterlage folgt `show_stability`, nicht `show_outlook` | Lebt in `WasStehtWoKarte.svelte`/`mailInhaltKonstanten.ts`; Ersatz `mail_inhalt_konstanten`, `rework_3036_bloecke_schalter` plausibel |
| `vorlage_anwenden_uebernimmt_ampel` (4), `wetter_metriken_vorlage_anwenden_sendet_ampel` (4), `wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte` (1) | Vorlage anwenden übernimmt Ampel samt `alarm_ab` als Kopie | Ersatz: `fix_3193_vorlage_abweichung_minimal`, `ampelSchreiben`, `feat_3190_vorlage_dialog_inline`; plausibel |
| `telegram_kanalgrenze_je_kontext` (4), `telegram_schnittlinie_wahr` (4), `sms_reiter_roh_einfach_nur_fuer_sms_format_capable` (3), `nur_ein_bericht_kennzeichnung` (4) | Telegram-Trennlinie/Badge 7, SMS-Roh/Einfach-Umschalter, Nur-ein-Bericht-Kennzeichnung | **Funktion hat keinen lebenden Code** (Waisen `LTCutLine`, `nurEinBericht.ts`): PO-Entscheidung, siehe Risiko 4 |
| `trip_night_block…`, siehe oben; `thunderThresholdCatalogGuard` (6) | Gewitter-Schwellenliste aus Katalog, Ladezustand/Fehlerzweig | `ThresholdMetricRow` ist Waise; lebende Schwelle in Karte: `thunderThresholdLevels.test.ts` bleibt |

Modul-Gegenprobe (überlebende Test-Importeure der von den gelöschten Tests genutzten lebenden Module): `api.ts`/`etagRegistry.ts` 81, `compareHubPersistenz.ts` 46, `versandVergleichSpeicherung.ts` 21, `weatherMetricsCompareSave.ts` 21, `compareMetricSelection.ts` 19, `metricsEditor.ts` 15, `compareMetricOrder.ts` 7, `ltChannels.ts` 4, `compareChannelMetricLayouts.ts` 3, `pickEigenfelder.ts` 2, `mailInhaltKonstanten.ts` 2. Diese Module sind nicht ungeprüft; die Lücken liegen auf Fallebene, nicht Modulebene.

Die Zahl „33 von 57 mit Beleglücke“ aus der S1-Testtabelle konnte nicht nachgeprüft werden (Tabelle nur lokal in 8b9749601, nicht im Baum).

### R1b: Katalog „Einstellung = Mail“

**26 falsch-grüne Fälle bestätigt.** Alle in `fallliste_editor.json`, ID `D-*-frontend`, Status `gruen`, Feld `test` ohne Dateiangabe:

- 22 Fälle mit Titel `frontend_seite_*` (Trip: `tabellen_standard/altbestand/gespeichert`, `ausblick_standard/gespeichert/bewusst_leer_alle_aus/grundauswahl_ohne_ausblick`, `vorlage_reihenfolge`, `kanal_totalschnitt_aus_wirkt`, `hinweis_grundauswahl_leer_trip`; Orte: `orte_vergleichstabelle_standard/gespeichert/grundauswahl_bewusst_leer/kanal_totalschnitt_aus_wirkt`, `hinweis_grundauswahl_leer_orte`)
- 4 Fälle `n3_semantik_wie_mail`, `n3_editor_kennzeichnet_je_zeile`, `n3_kennzeichnung_folgt_dem_editorstand`, `n3_speichern_bewahrt_bericht_flags`

Die Titel stammten aus den in #3357 gelöschten `editor_standard_gleich_mail.test.ts` bzw. `nur_ein_bericht_kennzeichnung.test.ts`. Gemessen mit `verweis.py`: kein Titel kommt noch wortgleich in einer der 694 Vitest-Dateien vor (`frontend/src/**/__tests__/*.test.ts`), alle 26 gelten trotzdem als gefunden. `pruefe_testverweise` meldet 0 Fehler.

**Fehlermechanismus (Datei und Zeile):**

1. `frontend/src/lib/i18n/__tests__/standardwerte_hilfe_textkatalog.test.ts:88` enthält ``test(`${key}`, () => …)`` (Titel besteht nur aus dem Platzhalter).
2. `tests/tdd/test_einstellung_gleich_mail_fallliste.py:177`: `_VITEST_TEMPLATE_GANZ` erfasst diesen Titel `${key}`. Zeile 181-184 `_template_muster` splittet an `${…}` und baut `".+".join(...)`; bei `'${key}'` bleiben zwei leere Teile, das Muster ist `.+`.
3. Zeile 187-206 `_vitest_titel_gefunden` (Zeile 199-201): `any(_template_muster(v).fullmatch(titel.strip()) …)` liefert für jeden nicht-leeren Titel True.
4. Zeile 209-216 `_pruefe_vitest_verweis`: hat der Verweis kein `datei.test.ts::`-Präfix (alle 26), sind alle 694 Vitest-Dateien Kandidaten, also reicht die eine Datei mit `${key}`. Bei Verweisen MIT Dateiname wirkt der Fehler nur innerhalb dieser Datei (deshalb fielen die ,,datei.test.ts::…“-Fälle der gelöschten Dateien auf).
5. Zeile 264-: `pruefe_testverweise` prüft nur Fälle mit Status aus `STATUS_MIT_TEST` und ruft diesen Pfad auf.

Folge: Wer eine Testdatei löscht, deren Fälle ohne Dateiangabe verwiesen werden, sieht nie rot. Korrekturansatz (nur Befund, nicht umgesetzt): Ganz-Platzhalter-Titel (`'${…}'` ohne festen Text) nicht als Treffer zählen oder Verweise ohne Dateiangabe verbieten; die 26 Fälle auf `offen`/Ausnahme setzen oder auf Karten-Tests (`ac26_…`, `p5c_…`) umverweisen. Die übrigen Frontend-Fälle mit Dateiangabe (R7-*, E-P12-*, O-P10-*, E-R8-F3N-VERSAND-*) zeigen auf existierende Dateien.

Verwandt: `fallliste_editor.json` hat nach #3357 keine Entsprechung mehr für `hinweis_grundauswahl_leer` (Waise `molecules/GrundauswahlLeerHinweis.svelte`, 37 Zeilen, nirgends eingebunden und in keinem BESTAND).

### R2 / #3366: Dateien ohne Produktionsaufrufer

Methode: `waisen.py` (Scratchpad): Wurzeln = alle Nicht-Test-Dateien unter `frontend/src/routes/` plus `src/*.ts` (hooks, service-worker); Kanten = statische `import … from`, `export … from`, `import('…')`, `import.meta.glob`, `new URL(…, import.meta.url)`, Auflösung von `$lib/…`, relativen Pfaden, `.js`-Endung → `.ts`, `index.ts`; Test-Dateien (`__tests__/`, `*.test.ts`, `*.spec.ts`) zählen weder als Wurzel noch als Aufrufer. Ergebnis: 85 Wurzeln, 479 erreichbare, 450 Nicht-Test-Dateien unter `frontend/src/lib`, **56 ohne Aufrufer** (4 033 Zeilen). Keine `import.meta.glob`-Fundstellen im erreichbaren Baum. Gegenprobe per Wortsuche: alle verbleibenden Treffer der Namen in lebendem Code sind Kommentare (z. B. `ltChannels.ts`, `AlarmeTab.svelte`, `TripNewEditor.svelte`).

Abweichung zu „42 Dateien / 4 454 Zeilen“ im Kommentar von 12:38: dort zählten `compareHourlyMetricDefs.ts` und `hourlyFriendlyMap.ts` mit (inzwischen durch #3301 gelöscht), und der Stichtag war c8329fea4. Heute: 46 Kern-Waisen (4 010 Zeilen) plus 10 Barrel-Dateien (`index.ts`, 23 Zeilen).

**Löschkandidaten (Kern, 46 Dateien, 4 010 Zeilen); Zeilenzahl in Klammern:**

- `components/shared/layout-tab/` (405): LTCapNote (71), LTChannelPicker (109), LTCutLine (46), LayoutTab (95), channelLayoutsDirty (51), ltIdealRange (33)
- `components/shared/versand-tab/` (934): VTBriefingChannels (298), VTLaufzeitRoute (74), VTLaufzeitVergleich (128), VTNextBriefing (60), VTSchedulePlan (287), channelContactLabel (32), vtBriefingChannelsText (55)
- `components/shared/weather-metrics-tab/` (811): AggregationMetricRow (99), MultiSymbolMetricRow (52), ThresholdMetricRow (138), WeatherV2Grundauswahl (167), WeatherV2PresetBar (136), compareAggregationGrouping (76), nurEinBericht (47), outlookFriendlyCapability (34), wertebereicheAnzeige (62)
- `components/shared/reportConfigDirty.ts` (72)
- `components/trip-detail/` (409): AboutOutputLayout (118), WeatherV2Kanaele (194), waypoints/WaypointPin (54), weatherSaveGate (43)
- `components/compare/` (475): AddReportCard (51), CreateGroupDialog (159), LocationPreviewMap (43), layoutPreviewRows (10), versandPropsAus (120), wetterMetrikenPropsAus (92)
- `components/edit/` (435): EditRouteSection (235), EditWeatherSection (11), WeatherSummaryCard (106), weatherSummary (83)
- `components/mobile/` (120): DrawerGroup (30), DrawerItem (53), NavIcon (37)
- `components/molecules/GrundauswahlLeerHinweis.svelte` (37)
- `utils/` (312): alertMetricCatalogIds (45), horizonHelpers (79), naturalSort (61), rightColumn (81), weatherEmoji (46)

Zusammensetzung: 27 `.svelte` (davon 26 in BESTAND, Ausnahme `GrundauswahlLeerHinweis`), 29 `.ts` inkl. Barrels. Nicht Alt-Editor-Familie, aber ohne Aufrufer (Entscheidung nötig, ob im Paket): `mobile/Drawer*`/`NavIcon`, `compare/AddReportCard|CreateGroupDialog|LocationPreviewMap`, `edit/*`, `trip-detail/waypoints/WaypointPin`, `utils/*` (die letzten sind durch `test_issue_316_docs_cleanup.py`, `test_2243_playwright_loeschscheibe.py` o. ä. namentlich gepinnt). Die genannte Aufzählung des Issues (layout-tab, WeatherV2*, VT*, reportConfigDirty, weatherSaveGate, nurEinBericht) ist vollständig enthalten.

**Barrels ohne Aufrufer (10 Dateien, 23 Zeilen), getrennt behandeln:** `components/email-preview/index.ts` (7), `lib/index.ts` (1, SvelteKit-Standard, behalten), `components/ui/{dot,elev-sparkline,eyebrow,input,pill,segmented,topo,wicon}/index.ts` (zusammen 15). Nicht Alt-Editor; Vorschlag: nicht im Paket.

**Tests, die ausschließlich Waisen prüfen (Löschen mit):**

- *Import-eindeutig (12):* `utils/horizonHelpers.test.ts`, `utils/naturalSort.test.ts`, `edit/weatherSummary.test.ts`, `compare/layoutPreviewRows.test.ts`, `shared/layout-tab/ltIdealRange.test.ts`, `shared/versand-tab/__tests__/{channelContactLabel,channel_checkbox_dedupe_render,vtBriefingChannelsTextNoJudgement,vtBriefingChannelsText}.test.ts`, `shared/weather-metrics-tab/__tests__/{compareAggregationGrouping,outlookFriendlyCapabilityDrift}.test.ts`, `trip-detail/__tests__/weatherSaveGate.test.ts`.
- *Namens-/Pfadbezug, Mehrheit rein Waise (je Datei prüfen, ca. 30):* `shared/layout-tab/__tests__/{channelLayoutsDirty,channelLimitModel,channelHintTextNoJudgement}.test.ts`, `shared/versand-tab/__tests__/{naechstes_briefing_baustein_render,naechstes_briefing_lader_laufzeit,naechstes_briefing_text,naechstes_briefing_verdrahtung,shared_schedule_quickpick,sms_unbestaetigt_kanalstatus,telegram_unterzeile_render,versand_tab_sprache,versand_telegram_je_kontext,versand_texte_ohne_wertung_en,vt_schedule_plan_hour_step}.test.ts`, `shared/__tests__/{reportConfigDirty,compare_alarme_wertprops,versand_enddatum_ohne_ereignis_bleibt_wirksam,s3b2795_zustellung_struktur,alarme_tab_premium_sms_channel_row_render,telegram_kurzstil_shared_toggle}.test.ts`, `shared/weather-metrics-tab/__tests__/{aggregation_row_multi_select,thunderThresholdLevels,vorlage_speichern_karte_3190}.test.ts`, `compare/__tests__/{compare_send_time_minutes,compare_wizard_save_new_preset_channels,compare_wizard_state_entfernt,compare_versand_hydration_unter_wetter_metriken,compare_feldsatz_roundtrip_datenerhalt,issue_683_wizard_remove,locationHelpers}.test.ts`, `compare/issue_462.test.ts`, `edit/__tests__/report_config_uses_shared_schedule.test.ts`, `edit/issue_503_etappen_waypoints.test.ts`, `utils/{rightColumn,alertMetricCatalogIds}.test.ts`, `trip-detail/PresetRow.test.ts`, `issue_523_suggested_flag_cleanup.test.ts`. Hinweis: `locationHelpers.test.ts` und `compare_hourly_vocabulary_single_source.test.ts` führen die Waise nur als Kommentar-/Textbezug; `locationHelpers.ts` selbst lebt.
- *Gemischt, nur Teil herausschneiden (nicht löschen):* `issue_390_compare_atomic_migration`, `utils/__tests__/{hilfstexte_sprache,report_slot_aktiv}`, `shared/__tests__/{infobox_nur_beim_anlegen,hub_reiter_gemeinsame_aufloesung,hub_geteilte_felder_cooldown_quiet_konsistent,versand_vergleich_premium_sms,context_herkunft_zweige_eingefroren,reiter_sprunglinks_nur_neue_kennungen,ac2_endbilanz_deckt_alle_47_ab}`, `stores/__tests__/saveStatus`, `trip-detail/__tests__/tempo_fixloop4_3196`, `shared/wetter-tab/__tests__/vorlageName_render`, `i18n/__tests__/{keine_hartkodierten_nutzertexte,reaktivitaet_waechter,deutsch_unveraendert}`, `trip_pfad_altfeld_loeschnachweis_3297` (nennt `outlookFriendlyCapability` als Nachweis), `ink4_waechter`, `karten_dark` (LocationPreviewMap).
- *Prüfstände/Goldens, die nur Waisen rendern (mit löschen oder umbauen):* `f6VersandSsr.ts` + `f6KatalogAnker.ts` + `tests/golden/f6_versand_tab/*` (16 Dateien), `f8Pruefstand.ts` + `f8KatalogAnker.ts` + `f8VarianteHook.mjs` + `LayoutTabPruefstand.svelte` + `tests/golden/f8_layout_korridor/*`; `f9Pruefstand.ts`/`f10Pruefstand.ts` und Goldens `f9_trip_flaechen`, `f10_vergleich_flaechen` sind gemischt (Waisen-Anteile `bausteine.*`, `funktionen.*` prüfen).
- *Playwright-Specs mit Bezug auf Waisen-Testids:* `layout-tab-route`, `layout-tab-vergleich`, `epic-138-metriken-editor`, `hub-versand-briefing-zeiten`, `hub-versand-inline-bearbeiten`, `versandzeit-stundenwahl`, `trip-new-loads-without-effect-loop`, `waypoints-editor`, `issue-1093-unit`, `fix-1350-compare-metric-select.staging`, `wetter-metriken-vorschau-entfernt.staging`, `dark-mode-alle-routen.staging` (nur `LocationPreviewMap`); Überschneidung mit #3374 beachten.

**Ratschen und Gate-Dateien mit Waisen-Pfaden (beim Löschen mitpflegen):**

| Datei | Bezug | Pflege |
|---|---|---|
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | 26 der 27 .svelte-Waisen in BESTAND, Obergrenze 188 (Zeile 726) | Einträge streichen, Obergrenze auf 188 − 26 = 162 senken |
| `tests/unit/ein_katalog_ausnahmen.json` | `WeatherV2Grundauswahl.svelte`, `outlookFriendlyCapability.ts`, `wertebereicheAnzeige.ts`, `utils/alertMetricCatalogIds.ts`, `weatherEmoji.ts` (je FRONTEND_LISTE) | Einträge und Höchststand verkleinern, sonst rot (Test Zeile 248) |
| `frontend/src/lib/__tests__/ink4_waechter.test.ts` | DrawerGroup, LT*, LayoutTab, VTSchedulePlan, WeatherV2* | Listen kürzen |
| i18n-Scanner (3 Tests) | Dateilisten und Schlüsselverwender | Listen kürzen, 128 Schlüssel entfernen |
| `.claude/hooks/pendant_gate.py` `BEKANNTE_PAARE` | keine Frontend-Pfade | keine Änderung |
| `frontend/src/lib/altfeld_namen_sperre.test.ts` | `ERLAUBT = {}`, nur gelöschter Pfad `hourlyFriendlyMap.ts` als Fixture | keine Änderung |

**Katalogschlüssel, die nach der Löschung ohne Verwender sind (Simulation nach Logik von `katalog_schluessel_haben_verwender.test.ts`): 128 Schlüssel** (de; en spiegelt, `paritaet_de_en`). Gruppen: `trip.about.*` (19), `trip.kanaele.*` (13), `trip.route.*` (13), `trip.wetter.*` (6), `versand.zeitplan.*` (12), `versand.laufzeit.*` (7), `versand.kanal.*` (8), `versand.briefing.*` (7), `versand.naechstes.titel`, `versand.kanaele.titel`, `wertebereiche.grundauswahl.*` (7), `wertebereiche.preset.*` (3), `wertebereiche.schwelle.stufe.*` (3), `wertebereiche.symbolzeile.*` (8), `wertebereiche.reihenfolge.aus`, `vergleich.gruppe.*` (5), `vergleich.neu.auto_report`, `vergleich.ort.kartenvorschau`, `layout.kappung.schnittlinie_*` (2), `layout.tab.eyebrow`, `bausteine.horizont.*` (5), `bausteine.profil.*` (4). Bestätigt: heute 0 Schlüssel ohne Verwender.

**Sperren/Gates-Fazit:** keine Hook-Datei (`.claude/hooks/*`) führt einen Waisen-Pfad; alle zu pflegenden Stellen sind Tests, Testdaten oder Wächter-Konfiguration im Frontend/`tests/`.

### #3374: tote Browser-Prüfungen

Positivliste `.github/ci_e2e_specs.txt`: 86 Einträge; **keine** der genannten Specs steht darauf (Treffer 0 je Name). Sie laufen weder im CI-Hauptlauf noch gelten sie für `E2E_MIN_SPECS`; Streichen oder Umschreiben ändert die CI-Ratsche nicht.

| Spec | Existiert? | Prüft heute | Befund | Empfehlung |
|---|---|---|---|---|
| `epic-138-metriken-editor.spec.ts` (237 Z., AC-1/2/3/4/5b/6/7/10) | ja | Reiter Wetter mit `weather-metrics-tab`, `wm2-grundauswahl`, `weather-preset-pill-*`, `preset-confirm-ok` | Testids nur noch in Waisen (`WeatherV2Grundauswahl`, `WeatherV2PresetBar`); `weather-metrics-tab` existiert nirgends mehr | **Streichen komplett.** Ersatz bereits auf Positivliste: `was-steht-wo-karte.spec.ts` (WS-1..16), `hub-wetter-metriken-speichert-selbst`. AC-5b (Ausblick „Einfach“) ist Altfeld |
| `weather-metrics-tab-autosave.spec.ts` (330 Z.) | ja | AC-1/2/6 (Reiter öffnen ohne Klick: kein PUT), AC-3 (Katalogfehler + Wiederholen), AC-4 (alle abwählen), AC-5 (Metrik + Schwelle); F003/F004 sind schon auf die Karte umgestellt | `weather-metrics-load-error/-retry`, `threshold-level-*`, `wm2-grundauswahl` gibt es nicht mehr | **Neu schreiben auf die Karte:** AC-1/2/6 (Hydrations-Gate: Reiter öffnen = kein PUT) und AC-4 (bewusst leere Auswahl bleibt nach Reload leer) mit `was-steht-wo-*`-Schaltern; AC-3 auf den Ladefehler von `wetterTabLaden.ts` abbilden oder streichen; AC-5 Schwelle **streichen** (ThresholdMetricRow Waise) |
| `compare-hourly-metric-order.spec.ts` | ja (+ `.staging.setup.ts`) | AC-3 (Karte: Stundenverlauf „nur in der E-Mail“, keine Schnittlinie), AC-4 | AC-4 ist seit #3276/#3359 **bereits** eine Negativ-Zusicherung (`weather-metrics-stundenverlauf` = 0); „21 statt 9“ stammt aus der alten `weather-metrics-stundenverlauf`-Liste, die es nicht mehr gibt | siehe unten (kein echter Fehler); AC-4 als Duplikat von `feat-3276-vergleich-ohne-altfelder.spec.ts` und `hub-anlegen-ablauf` AN-12 **streichen**, AC-3 behalten (Testids `compare-editor-tab-*` sind dynamisch, stimmen) |
| `compare-neu-kanal-anlegen.staging.spec.ts` | **nein**, gelöscht in 600cb31b0 (#3333) | – | Issue-Text veraltet | nichts zu tun |
| `layout-tab-vergleich.spec.ts` (128 Z., AC-7, AC-11, AC-4, AC-8) | ja | nur Negativ-Zusicherungen (kein Stundenverlauf-Schalter, kein Channel-Tab/Layout-Preview/SMS-Budget), AC-4 „Zustellung gesperrt ohne Orte“, AC-8 mobil kein Querscroll | `LayoutTab` ist Waise; Inhalt durch #3276 gegenstandslos | **Streichen**; vorher AC-4 (Sperre ohne Orte) und AC-8 gegen `hub-anlegen-ablauf` bzw. `mobile-ux-messung` abgleichen, bei Lücke dort ergänzen |
| `fix-2069-alert-preview-echte-segmente.spec.ts` (92 Z., 2 Fälle) | ja | Beispiel-Warnung im Reiter Zustellung: Trip ohne Etappe → `alert-preview-no-stages`, geplanter Trip → Beispiel-Warnung | `AlertPreviewCard` lebt (`alerts-tab/AlertPreviewCard.svelte`, eingebunden über `organisms/zustellung-tab/BeispielAlarm.svelte` und `AlarmeTab.svelte`); Fachaussage (kein Abruf ohne Etappe) gilt weiter | **Neu schreiben:** Einstieg auf `BeispielAlarm` im Zustellung-Reiter anpassen (nicht streichen; Fachregel #2069 AC-8 hat sonst keinen Browser-Test) |
| `feat-1395-s3-etag-ifmatch.staging.spec.ts` (592 Z., 5 Fälle + Aufräumen) | ja (+ `.staging.setup.ts`, Config) | Fall 1 Wetter-Reiter mit `wm2-grundauswahl`; Fälle 2-4 Alarme-Reiter (412, Pause, Archiv), Fall 5 Etappen | Fall 1 tot; Fälle 2-5 nutzen `alarme-tab`, `alerts-tab-official-alert-triggers-toggle`, `subscription-action-*`, `edit-stages-panel` (alle im Quelltext vorhanden) | Fall 1 **neu schreiben auf Karte** (zwei Schaltergesten, zweiter PUT trägt neuen Stempel); Fälle 2-5 **behalten**, auf Gültigkeit gegen Staging prüfen |
| `save-status-indicator-honesty.spec.ts` (203 Z.) | ja | AC-3 Reiter Wetter öffnen ohne Eingabe bleibt „gespeichert“; AC-4 Versand-Tab öffnen = kein PUT; AC-1/2 Vergleich Layout/Versand | `weather-metrics-tab`, `versand-abschnitt`, `versand-tab` nicht mehr im Code | **Neu schreiben:** Kernaussage „bloßes Öffnen von Wetter/Zustellung schreibt nicht und zeigt kein ‚ungespeichert‘“ auf Karte und Zustellung-Reiter, Trip und Vergleich |
| `weather-metrics-editor-day-range-kuerzel.spec.ts` (206 Z., AC-1..9) | ja | Kürzel-Zeilen `sms-multi-symbol-row-*`, „05 — Auswertungen“ entfällt, Vergleich `AggregationMetricRow` | alle Testids nur in Waisen | **Streichen**; Aufgabe „fünf neue Kürzel in der lebenden Oberfläche“ gehört zur Karte (`was-steht-wo-karte`) |
| `issue-932` | **nein**, gelöscht in e089d39a2 (#3196, `issue-932-activity-type-route-tab.spec.ts`) | – | Issue-Text veraltet | nichts zu tun |
| `issue-88` | **nein**, gelöscht in 89d093a6a (#3207, `issue-88-report-config-dialog.spec.ts`) | – | Issue-Text veraltet | nichts zu tun |

Zusammenfassung #3374: 3 der 11 genannten Specs gibt es nicht mehr (Issue-Text veraltet); 3 streichen (`epic-138-metriken-editor`, `layout-tab-vergleich`, `weather-metrics-editor-day-range-kuerzel`); 4 neu schreiben (`weather-metrics-tab-autosave`, `fix-2069-alert-preview-echte-segmente`, `save-status-indicator-honesty`, Fall 1 von `feat-1395-s3-etag-ifmatch.staging`); `compare-hourly-metric-order` nur AC-4 streichen. Neu geschriebene Specs gehören auf die Positivliste (Ratsche `E2E_MIN_SPECS`, `ci.yml:328`, exakt) oder bleiben bewusst außerhalb.

**`compare-hourly-metric-order` AC-4 „21 statt 9“: kein echter Fehler im lebenden Code.**
Der alte Test (Stand vor 63a2161c0) zählte auf `/compare/new` im Schritt Zustellung die Zeilen `wm2-reihenfolge-row` im Container `weather-metrics-stundenverlauf` und erwartete 9 (`DEFAULT_HOURLY_METRIC_KEYS` ohne `wind_dir_deg`). Der Container und die Liste (`hourly_metrics`-Auswahl, `compareHourlyMetricDefs.ts`, `hourlyFriendlyMap.ts`) sind mit #3276/#3298/#3301 entfernt; `DEFAULT_HOURLY…` kommt im Produktionscode nicht mehr vor. Der Test ist seit #3276 eine Negativ-Zusicherung (Zeilen 132-155 der Datei). Die „21“ waren die ungefilterten Kandidaten der Alt-Liste, kein Datenfehler im Speicherpfad. Restfrage (nicht aus dieser Messung beantwortbar, am Staging nachzuziehen): ob die Karte „Was steht wo“ auf `/compare/new` in der Spalte Stundenverlauf dieselbe Vorbelegung zeigt wie im Hub (Fallzahl der `places.hourly: true`-Zeilen); `feat-3276-vergleich-ohne-altfelder.spec.ts` prüft den POST (Zeile 103-105), nicht die Vorbelegung.

## Nachtrag 25.11.: Messung „Nur ein Bericht“ auf Prod

Die Messung lief lesend als Dienstnutzer über alle `users/*/briefings/*.json`. Gezählt wurden Metriken in `display_config.metrics`, bei denen das wirksame Morgen-Flag vom wirksamen Abend-Flag abweicht. Die Regel dafür steht in `nurEinBericht.ts` und folgt `models.py::_filter_metrics_by_report_type`: Fehlt ein Bericht-Flag, gilt `enabled`, und fehlt auch das, gilt `true`.

Ergebnis: 21 Dateien geprüft, 0 Metriken nur in einem Bericht, 0 Nutzer betroffen.

Beleg für den Übergangscharakter: Der Dateikopf von `frontend/src/lib/components/shared/weather-metrics-tab/nurEinBericht.ts` sagt „kennzeichnet bis Phase 2 (#3065)“. #3065 ist auf GitHub geschlossen.

Telegram „nur Tageswert ab der 8. Metrik“ (ADR-0124 Nr. 3) ist in der Karte gebaut. Belegt ist das bisher nur durch Render- und Unit-Tests; der Browser-Fall folgt mit #3375. Entfallen ist nur die alte Schnittlinie des Alt-Editors (`LTCutLine`).
