---
entity_id: rework_3389_tote_exporte
type: refactor
created: 2026-11-26
updated: 2026-11-26
status: draft
workflow: rework-3389-tote-exporte
version: "1.1"
tags: [frontend, tote-exporte, loeschen, ratsche, "#3389", "#3122", "#3385", "#3384", "#3383", "#3020"]
---

# Rework #3389: Tote Exporte in versandVergleichSpeicherung.ts und weatherMetricsCompareSave.ts

## Approval

- [ ] Approved

## Purpose

Die beiden Module `versandVergleichSpeicherung.ts` und `weather-metrics-tab/weatherMetricsCompareSave.ts` enthalten die frühere Speicherlogik der Reiter „Versand“ und „Wetter-Metriken“ des Ortsvergleichs. Seit dem Umbau auf den Zustellungs-Speicherer ruft sie kein Produktionscode mehr auf; nur Tests halten sie am Leben. Diese Scheibe entfernt die 21 toten Exporte samt aller Tests, Prüfstand-Teile, Zählstellen und Verweise, die nur an ihnen hängen, und führt einen Lösch-Nachweis auf Exportebene ein, weil der Waisen-Wächter nur ganze Dateien erkennt. Für Nutzer ändert sich nichts Sichtbares; die fünf lebenden Hydrations-Funktionen bleiben unverändert, vier davon behalten ihren Test, `hydrateDayWindowFromPreset` erhält einen neuen.

## Source

- **File:** `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts`, `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` (Löschung von Exporten), `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` (neuer Block `#3389`)
- **Identifier:** die 21 Exportnamen der Tabellen unten; Block `describe('#3389 …')` mit Konstanten `GELOESCHT_3389` und `LEBEND_3389`

Schicht: ausschließlich Frontend (`frontend/src/...`) plus eine Katalogdatei der Tests (`fallliste_editor.json`) und Doku (`gates_und_ratschen.md`, eine Referenz-Spec). Kein Go-, kein Python-Produktionscode, keine Hook-Änderung (`.claude/hooks` bleibt unberührt), keine Browser-Spec. Trip/Vergleich-Teilung: es entsteht kein Baustein. Mandantentrennung: keine Nutzerdaten betroffen. Kanäle: kein Briefing- und kein Alarm-Inhalt betroffen. i18n: beide Module enthalten keinen `t(`-Aufruf und keinen Katalogschlüssel (gemessen), es entfällt kein Schlüssel.

## Analyse-Ergebnis (gemessen auf dem Stand nach Merge #3405)

Beide Module bestehen weiter und bleiben vom Waisen-Wächter erreichbar, weil `CompareTabs.svelte`, `compareHubHydration.ts` und `compare-new/compareNewVorlage.ts` fünf Exporte aufrufen. Alle anderen Exporte haben keinen Produktionsaufrufer (Importscan über `frontend/src` ohne Tests und `e2e`; eine Kommentar-Nennung in `CompareTabs.svelte:851` zählt nicht).

Gegenüber der Grobmessung im Kontext-Dokument ändern sich vier Einstufungen (Begründung je Datei in den Tabellen unten): `versand_vergleich_reiterwechsel_verliert_nichts`, `wetter_metriken_reiterwechsel_verliert_nichts`, `f006_zustellung_schreibt_keine_wetterfelder` und `compare_feldsatz_roundtrip_datenerhalt` sind keine Umbau-, sondern Lösch-Kandidaten (Gruppe a statt b), weil ihr lebender Anteil schon an anderer Stelle geprüft wird. Außerdem sind in `hub_versand_inline` acht (nicht neun) Fälle tot und vier (nicht drei) Banner-Fälle lebend, und in `compare_outlook_metric_formats_persistenz` sind zwei (nicht drei) Fälle tot.

## Zu löschende Exporte (21)

### versandVergleichSpeicherung.ts (9 Namen)

| Nr. | Name | Art |
|---|---|---|
| 1 | `versandSnapshotAus` | Funktion |
| 2 | `baueVersandNutzlast` | Funktion |
| 3 | `flushPendingVersandSave` | Funktion |
| 4 | `rollbackVersandSnapshot` | Funktion |
| 5 | `versandVergleichSpeicherungAktiv` | Funktion |
| 6 | `erstelleVersandVergleichSpeicherung` | Funktion |
| 7 | `versandZustandsBruecke` | Funktion |
| 8 | `VersandHydrationTarget` | Typ (nur intern von Nr. 1, 4, 6, 7 genutzt) |
| 9 | `VersandVergleichSpeicherungOptionen` | Typ (nur intern von Nr. 6 genutzt) |

`VersandSnapshot` zählt nicht dazu (siehe unten). Lebend und unverändert bleibt `hydrateVersandFieldsFromPreset` (Aufrufer `CompareTabs.svelte:88/433`, `compareNewVorlage.ts:24`).

### weatherMetricsCompareSave.ts (12 Namen)

| Nr. | Name | Art |
|---|---|---|
| 10 | `flushPendingLayoutSave` | Funktion |
| 11 | `rollbackLayoutSnapshot` | Funktion |
| 12 | `WetterMetrikenLayoutSnapshot` | Typ |
| 13 | `WetterMetrikenZustand` | Typ |
| 14 | `wetterMetrikenSnapshotAus` | Funktion |
| 15 | `baueWetterMetrikenNutzlast` | Funktion |
| 16 | `flushPendingWetterMetrikenSave` | Funktion |
| 17 | `rollbackWetterMetrikenSnapshot` | Funktion |
| 18 | `WetterMetrikenVergleichSpeicherungOptionen` | Typ |
| 19 | `erstelleWetterMetrikenVergleichSpeicherung` | Funktion |
| 20 | `wetterMetrikenVergleichSpeicherungAktiv` | Funktion |
| 21 | `wetterMetrikenZustandsBruecke` | Funktion |

Mit den 9 Namen aus dem Versand-Modul ergeben sich 9 + 12 = 21 tote Exporte. Mit ihnen entfallen die nicht exportierten Hilfen `felder`, `WETTER_TOP` und `zustellungsStand` sowie die Konstante `VERSAND_TOP`. Lebend und unverändert bleiben `hydrateDayWindowFromPreset`, `hydrateWeatherMetricsFromPreset`, `hydrateLayoutFieldsFromPreset`, `wetterMetrikenHydrationAbgeschlossen`; ebenso `DEFAULT_DAY_WINDOW_START_HOUR` und `DEFAULT_DAY_WINDOW_END_HOUR`.

### Die zwei Typen `VersandSnapshot` und `LayoutSnapshot`

Beide sind nur noch Rückgabetypen der lebenden Hydrations-Funktionen. Entscheidung: der Typ bleibt als Schnittstelle im Modul stehen und verliert das Schlüsselwort `export`. Kein Produktionscode importiert sie (gemessen); die Tests, die sie importierten, entfallen oder werden umgebaut. Der Wächter führt sie deshalb als 22. und 23. Name der Löschliste (der Wächter prüft 23 Namen, „tot“ zählt 21).

### Aufräumen der Importe

Versand-Modul: es bleibt nur `import type { ComparePreset }`; entfallen `ActivityProfile`, `IdealRange`, `SaveFn`, `SaveStatus`, `merkeNutzlast`, `PutClient`, `buildComparePresetSavePayload`, `waehleEigenfelder`, `normalizeStoredActiveMetrics`. Weather-Modul: es bleiben `ComparePreset` (Typ), `rehydrateActiveMetrics`, `registeredCompareMetricCatalog` und `CompareSelectionEntry`; entfallen `ActivityProfile`, `SaveFn`, `SaveStatus`, `merkeNutzlast`, `PutClient`, `buildComparePresetSavePayload`, `waehleEigenfelder`, `CompareChannelActiveMetrics`, `materializeActiveMetricKeys`. Keiner dieser Fremdbausteine wird zur Waise (alle haben weitere Produktionsnutzer; gemessen). Die Kopfkommentare beider Module werden auf den verbleibenden Inhalt gekürzt (Hydrations-Helfer). In `CompareTabs.svelte:851` wird der Kommentar so umformuliert, dass `flushPendingLayoutSave` dort nicht mehr steht.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts` | MODIFY | 9 Namen und Importe entfernt, `VersandSnapshot` ohne `export`, Kopfkommentar gekürzt (360 auf rund 60 Zeilen) |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY | 12 Namen, Hilfen und Importe entfernt, `LayoutSnapshot` ohne `export`, Kopfkommentar gekürzt (400 auf rund 90 Zeilen) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | nur Kommentar Z. 851 |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` | MODIFY | neuer Block `#3389` (Lösch-Nachweis auf Exportebene, siehe Abschnitt Wächter) |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/weather_metrics_hydration_tagesfenster.test.ts` | CREATE | Ersatztest für `hydrateDayWindowFromPreset` (3 Fälle, siehe AC-4) |
| 21 Testdateien aus Tabelle „Löschen“ | DELETE | prüfen nur tote Exporte |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wetterMetrikenVergleichPruefstand.ts` | DELETE | nach allen Löschungen und Umbauten ohne Importeur |
| 15 Testdateien aus Tabelle „Umbauen“ | MODIFY | tote Fälle entfallen, lebende bleiben oder werden auf lebende Speicherer umgestellt |
| `frontend/src/lib/components/shared/__tests__/compareReiterAufbauPruefstand.ts` | MODIFY | Reiter `versand` und `wetterMetriken` entfallen |
| `frontend/src/lib/components/shared/__tests__/versandVergleichPruefstand.ts` | MODIFY | `hydrierterWiz`, `versandBedienung`, `dc` entfallen; `makePreset`, `createController` bleiben |
| `frontend/src/lib/components/shared/__tests__/goMergeServerPruefstand.ts` | MODIFY | `EIGENFELDER.versand` und `EIGENFELDER.wetterMetriken` entfallen |
| `frontend/src/lib/components/compare/__tests__/compare_retry_fehlerpfade_kein_verlust.test.ts` | MODIFY | Tabelle Z. 228-232 und Teil-Erfolg-Fall Z. 261-293 (Tabelle Gruppe c) |
| `frontend/src/lib/components/shared/__tests__/compare_reiter_nutzlast_nur_eigene_felder.test.ts` | MODIFY | drei Fälle für `versand` und `wetterMetriken` entfallen |
| `frontend/src/lib/components/shared/__tests__/context_herkunft_zweige_eingefroren.test.ts` | MODIFY | Zählstelle, siehe Abschnitt Zählstellen |
| `frontend/src/lib/components/shared/__tests__/ac2_endbilanz_deckt_alle_47_ab.test.ts` | MODIFY | Zählstelle, siehe Abschnitt Zählstellen |
| `frontend/src/lib/components/compare/__tests__/totcode_rueckbau_speicherweg.test.ts` | MODIFY | Positivkontrolle, siehe Abschnitt Zählstellen |
| `docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md` | MODIFY | Doku-Spiegel der Ratsche (vom Test oben gelesen) |
| `tests/fixtures/einstellung_gleich_mail/fallliste_editor.json` | MODIFY | Z. 637 umgehängt |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Z. 555-561 (Ratschenpositionen `:221`/`:534`, schon heute veraltet) auf den Stand nach #3389 |

Unverändert und danach grün zu laufen haben `compare_konflikt_nutzlast_am_eintrag.test.ts` (die Schleife über `REITER` zählt danach nur noch `alarme` und `wertebereiche`), `alarme_vergleich_konflikt_nochmal_speichern.test.ts` und `wertebereiche_vergleich_konflikt_nochmal_speichern.test.ts` (nutzen `konfliktMitFremdemNamen` nur mit `alarme` und `wertebereiche`), `compare_versand_hydration_unter_wetter_metriken.test.ts`, `compareActiveMetricsStorageFormat.test.ts`, `compareMetricKeysParity.test.ts`, `compare_hub_bridge_restlos_entfernt.test.ts`, `s3b2795_zustellung_struktur.test.ts` (der Name `versandVergleichSpeicherung` steht dort nur in der Verbotsliste `VERBOTENE_SPEICHER_MODULE`, bleibt gültig), `alarme_vergleich_premium_sms_entkoppelt.test.ts`, `rework_3020_vergleich_parallele_schreiber.test.ts`, `daywindowcard_rueckbau_waechter.test.ts`. Kommentare in lebenden Tests, die gelöschte Testdateien als Geschichte nennen, bleiben stehen.

### Estimated Scope (ehrlich)

- **Files:** 3 Produktionsdateien geändert (2 Module, 1 Kommentar), 22 Dateien gelöscht (21 Tests, 1 Prüfstand), 24 Testdateien geändert (15 umgebaut, 3 Prüfstände, 2 Gruppe c, 4 Zählstellen-Dateien), 1 neue Testdatei, 3 Doku-/Katalogdateien; zusammen rund 53 Dateien.
- **LoC:** Produktion rund -600 (Versand-Modul 360 auf rund 60, Weather-Modul 400 auf rund 90, minus Kommentare); Tests rund -4 500 bis -5 500 Zeilen gelöscht oder gekürzt, rund +400 neu (Wächter-Block, Ersatztest, umgebaute Fälle). Die genaue Zahl wird nach dem Löschen gemessen und im Commit eingetragen.
- **Scope-Grenzen:** die Standardgrenzen (5 Dateien, 250 LoC) werden bewusst und bekannt überschritten. Eine reine Löschscheibe ist nicht teilbar, weil jede Zwischenstufe rote Tests oder einen toten Prüfstand hinterließe; Muster wie #3385. Effort: medium.

## Die Testdateien

Entscheidung je Datei. Pfade relativ zu `frontend/src/lib/components/`.

### Löschen (21)

| Pfad | Begründung |
|---|---|
| shared/__tests__/versand_vergleich_speichert_selbst.test.ts | 5 Fälle, nur `erstelleVersandVergleichSpeicherung`; Wirkort lebend: `alarme_vergleich_speichert_selbst`, `zustellungSpeicherung.test` |
| shared/__tests__/versand_vergleich_konflikt_nochmal_speichern.test.ts | 4 Fälle, nur `konfliktMitFremdemNamen('versand')`; lebend: Alarme- und Wertebereiche-Pendants |
| shared/__tests__/versand_vergleich_flush_vor_pausieren.test.ts | 2 Fälle; lebend: `wertebereiche_vergleich_flush_vor_pausieren`, `compare_hub_pausieren_flusht_vorher` |
| shared/__tests__/versand_nutzlast_verliert_keine_daten.test.ts | 4 Fälle, `baueVersandNutzlast`, `versandSnapshotAus`; lebend: `zustellungSpeicherung.test` (Fälle `ac32_*`, `ac10_*`) |
| shared/__tests__/versand_nutzlast_reicht_keepalive_durch.test.ts | 2 Fälle; lebend: `rework_3020_zustellung_ifmatch_keepalive.test` |
| shared/__tests__/versand_enddatum_ohne_ereignis_bleibt_wirksam.test.ts | 3 Fälle; lebend: `zustellungSpeicherung.test` Fall `ac10_bis_datum_und_zurueck` |
| shared/__tests__/versand_speicherung_nur_im_vergleich_hub.test.ts | 6 Fälle, nur `versandVergleichSpeicherungAktiv` |
| shared/__tests__/versand_vergleich_reiterwechsel_verliert_nichts.test.ts | 3 Fälle: Fall 1 (Reiterliste enthält `zustellung`) steht in `vergleich_flush_guard_neue_kennungen.test.ts` (Liste ist genau `wetter`, `zustellung`); Fälle 2 und 3 messen den Reiterwechsel mit dem toten Speicherer, lebend belegt durch `alarme_vergleich_flush_beim_reiterwechsel.test.ts` und `wertebereiche_und_alarme_teilen_den_speicherplatz.test.ts` (Reiterwechsel `zustellung` und `wetter`) |
| compare/__tests__/compare_hub_layout_save.test.ts | 3 Fälle, nur `flushPendingLayoutSave` |
| compare/__tests__/compare_hub_layout_rollback.test.ts | 2 Fälle, nur `rollbackLayoutSnapshot` |
| compare/__tests__/compare_feldsatz_roundtrip_datenerhalt.test.ts | 3 Fälle über den toten Versand-Speicherer; Ersatz am lebenden Speicherer mit demselben Go-Merge-Server und `vollerVergleich`: `zustellungSpeicherung.test.ts` Fälle `ac32_nur_morgenzeit_ein_put_fremdfelder_unveraendert` (alle übrigen Felder unverändert, Teilfeld-Patch) und `ac26_vergleich_cooldown` (geteilter Cooldown) |
| shared/weather-metrics-tab/__tests__/wetter_metriken_drei_stille_gesten_bleiben_wirksam.test.ts | 1 Fall, nur `erstelleWetterMetrikenVergleichSpeicherung` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_intra_gesture_kollision.test.ts | 2 Fälle, nur `erstelle…` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_nutzlast_reicht_keepalive_durch.test.ts | 2 Fälle, nur `erstelle…` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_nutzlast_verliert_keine_daten.test.ts | 5 Fälle (`baue…`, `erstelle…`, `wetterMetrikenSnapshotAus`); der Fallliste-Verweis wird umgehängt (Zählstellen) |
| shared/weather-metrics-tab/__tests__/wetter_metriken_speicherung_nur_im_vergleich_hub.test.ts | 6 Fälle, nur `wetterMetrikenVergleichSpeicherungAktiv` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_flush_vor_pausieren.test.ts | 1 Fall, nur `erstelle…` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_konflikt_nochmal_speichern.test.ts | 4 Fälle, nur `konfliktMitFremdemNamen('wetterMetriken')` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_speichert_einmal.test.ts | 6 Fälle, nur `erstelle…` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_reiterwechsel_verliert_nichts.test.ts | 4 Fälle: Fall 1 (Liste enthält `wetter`) steht in `vergleich_flush_guard_neue_kennungen.test.ts`; Fälle 2 bis 4 messen Reiterwechsel mit dem toten Speicherer, lebend belegt durch `wertebereiche_und_alarme_teilen_den_speicherplatz.test.ts` |
| shared/weather-metrics-tab/__tests__/f006_zustellung_schreibt_keine_wetterfelder.test.ts | alle 7 Fälle gehen über `baueWetterMetrikenNutzlast`/`erstelle…`; die echte Zusicherung („Zustellung schreibt kein Wetter-Feld“) belegt `zustellungSpeicherung.test.ts` mit der `NIE`-Liste (`display_config`, `ampel`, `official_warnings`, `radar_alert_enabled`) und der Eigenfeld-Whitelist je Teil (`pruefeNurEigenfelder`) |

Zusammensetzung: 17 Dateien der Kontext-Gruppe a (7 Versand, 2 Layout, 8 Wetter-Metriken) plus 4 aus Gruppe b umgestufte (`versand_vergleich_reiterwechsel_verliert_nichts`, `wetter_metriken_reiterwechsel_verliert_nichts`, `f006_zustellung_schreibt_keine_wetterfelder`, `compare_feldsatz_roundtrip_datenerhalt`), zusammen 21.

### Umbauen (15)

| Pfad | Entfällt | Bleibt oder wird umgestellt |
|---|---|---|
| shared/__tests__/versand_vergleich_premium_sms.test.ts | Fälle `versandSnapshotAus fuehrt sendPremiumSms`, `rollbackVersandSnapshot …`, `baueVersandNutzlast sendet send_premium_sms …`, `AC-14 … baueVersandNutzlast sendet NIEMALS alert_channels`; Importe der 4 toten Namen und `type VersandSnapshot` | Fall `hydrateVersandFieldsFromPreset liest preset.send_premium_sms` (1 Fall). Die Wirkung `send_premium_sms` im PUT und „Versand sendet nie `alert_channels`“ belegen `zustellungSpeicherung.test.ts` (`ac33_*briefing_kanal_ist_versand_teil`, `NIE`-Liste) und `rework_3020_premium_sms_schaltbar.test.ts` |
| shared/__tests__/s3a2794_zustellung_vergleich_ein_speicherer.test.ts | Fälle 3 und 4 (`der Versand-Speicherer allein meldet …`, `Versand-Änderung speichert … (Kontrolle)`); Import `erstelleVersandVergleichSpeicherung`; im Aufbau `zustellungReiter()` die Variable `versand` und der Aufruf `versand.aenderungMelden()` | Fälle 1 und 2 (Cooldown und Stille Stunden: genau ein PUT über den Alarme-Speicherer); `Object.assign(wizardState, hydrateVersandFieldsFromPreset(basis))` bleibt (lebende Hydration). Titel des `describe` auf „genau EIN Speichervorgang über den Alarme-Speicherer“ |
| shared/__tests__/alarme_vergleich_kein_zurueckschreiben.test.ts | die vier Blöcke `S2-AC-2`, `S5-AC-2`, `S5-AC-11`, `S5-AC-3` (jeder nutzt den toten Versand-Speicherer als Nachbar); Hilfsfunktion `hubZustand`; Importe `erstelleVersandVergleichSpeicherung`, `hydrateVersandFieldsFromPreset` | Block `S2-AC-3` (Basis wird bei Ausführung in der Queue gelesen; nur Alarme-Speicherer) |
| shared/__tests__/alarme_vergleich_kanalwahl_speicherweg.test.ts | im Fall `AC-57` die Zweige „Versand“ und „Wetter-Metriken“ (`baueVersandNutzlast`, `hydrateVersandFieldsFromPreset`, `baueWetterMetrikenNutzlast`, `wetterMetrikenSnapshotAus`, `hydrierterWs` aus dem Wetter-Metriken-Prüfstand) | Fall `AC-57` nur mit dem Wertebereiche-Zweig, Titel „Wertebereiche-Teil-PUT sendet das Feld gar nicht und lässt den Bestand unverändert“; die übrigen 9 Fälle unberührt |
| shared/__tests__/compare_alarm_versand_nutzlast_trennung.test.ts | Block `AC-10: die Versand-Nutzlast enthaelt NIE alert_channels`; Konstante `VERSAND_SNAPSHOT`; Import `baueVersandNutzlast`, `type VersandSnapshot` | die drei übrigen Blöcke (Alarm-Nutzlast ohne `send_*`, vier Kanal-Booleans, Anlege-Payload); „Versand sendet nie `alert_channels`“ belegt `zustellungSpeicherung.test.ts` |
| compare/__tests__/compare_retry_reiterwechsel_eingabe_bleibt.test.ts | Block `F301a` (Fall `PX2`: gescheiterter Retry und Save aus erstmals geöffnetem Versand-Reiter über den toten Speicherer); Import `erstelleVersandVergleichSpeicherung` | alle übrigen 9 Fälle; die Hilfsfunktion `versandErstmalsOeffnen` bleibt (sie führt den lebenden Hydrations-Effekt `hydrateVersandFieldsFromPreset` des echten `CompareTabs`-Skripts aus). Die Zusicherung „kein Save mit Hub-Altstand nach gescheitertem Retry“ belegt weiterhin `compare_retry_fehlerpfade_kein_verlust` (Block F501, umgebaut siehe Gruppe c) |
| compare/__tests__/hub_nochmal_speichern_ueber_reiterwechsel.test.ts | der Versand-Speicherer (`erstelleVersandVergleichSpeicherung`, `hydrateVersandFieldsFromPreset`, `versandZustand`, `versandAendern`) | alle 3 Fälle bleiben; Reiter B ist jetzt `erstelleWertebereicheVergleichSpeicherung` (Zustand `hydrierterWs` aus `wertebereicheVergleichPruefstand.ts`, Änderung `wertebereicheBedienung(zustand).patch('wind_max_kmh', { max: 55 })`, Aufruf `aenderungMelden()`); Messung am Server statt `morning_time`: `corridors` trägt für `wind_max_kmh` den Höchstwert 55; Titel „B (Wertebereiche)“ |
| compare/__tests__/hub_put_queue.test.ts | Import `erstelleVersandVergleichSpeicherung`, Import `hydrierterWiz` | die 3 Queue-Fälle unberührt; `F002-Integration` und `F003-Regression` laufen mit `erstelleAlarmeVergleichSpeicherung` (Zustand per `hydrateAlarmFieldsFromPreset`): F002 ändert `radarAlertEnabled` auf `true`, danach Toggle-PUT, Messung `radar_alert_enabled === true` im Server-Stand und in `currentPreset`; F003: Edit A `radarAlertEnabled = true` (PUT hängt am Tor und gelingt), Edit B `officialWarningsEnabled` umgeschaltet (PUT scheitert mit 500), Messung: Server trägt `radar_alert_enabled: true`, `zustand.radarAlertEnabled` bleibt `true`, `zustand.officialWarningsEnabled` ist auf den Ausgangswert zurückgerollt, Controller-Zustand `error`; `makePreset` und `createController` kommen weiter aus `versandVergleichPruefstand.ts` |
| compare/__tests__/hub_versand_inline.test.ts | die Blöcke `AC-35/AC-36: flushPendingVersandSave` (5 Fälle) und `S5-AC-3: rollbackVersandSnapshot` (3 Fälle); Importe `flushPendingVersandSave`, `rollbackVersandSnapshot`, `type VersandSnapshot`; Hilfsfunktion `makeSnapshot` | Block `AC-36 (Basis): hydrateVersandFieldsFromPreset` (3 Fälle) und Block `hubActivationBanner` (4 Fälle); 7 Fälle bleiben |
| compare/__tests__/compare_outlook_metric_formats_persistenz.test.ts | Block `#2049 F005 / #3276 / #3298 — Layout-Speicherweg` (2 Fälle); Import `flushPendingLayoutSave`, `type LayoutSnapshot` | Block `#2049 F004` (3 Fälle über `buildComparePresetSavePayload`) |
| compare/__tests__/fix_3061_hub_hydrierer.test.ts | im Fall `AC-4: Altbestand oeffnen und ohne Aenderung speichern` die Speicherer-Anteile (`wetterMetrikenSnapshotAus`, `flushPendingWetterMetrikenSave`, Nutzlast-Prüfung); Importe dieser zwei Namen | alle 8 Fälle bleiben; `AC-4` prüft jetzt nur noch Hydration: nach `wetterHydrierer`, `alarmHydrierer` und `hydrateLayoutFieldsFromPreset(ALTBESTAND())` ist `s.activeMetricKeys === null` und `layout` gleich `{ hourlyEnabled: <hourly_enabled des Altbestands, sonst true> }`; Titel „Altbestand oeffnen laesst activeMetricKeys null“ |
| compare/feat3276_vergleich_ohne_altfelder.test.ts | Fall `Zustellungs-Speicherer sendet keinen Altschluessel` (nutzt `baueWetterMetrikenNutzlast`); im Fall `Versand-, Alarm- und Wertebereiche-Speicherer …` der Versand-Zweig und `baueVersandNutzlast`; Importe `baueWetterMetrikenNutzlast`, `type WetterMetrikenLayoutSnapshot`, `baueVersandNutzlast` | Fall wird `Alarm- und Wertebereiche-Speicherer senden keinen Altschluessel (Bestand mit Altfeldern)`; alle übrigen Fälle bleiben. Der lebende Zustellungs-Speicherer erhält den Altschlüssel-Beleg in `feat3298` (neuer Fall, siehe dort) |
| compare/feat3298_vergleich_ohne_altfelder.test.ts | Fall `flushPendingLayoutSave: Aenderung am Stundenverlauf-Schalter …`; Import `flushPendingLayoutSave` | Schleife `for (const reiter of REITER)` läuft nur noch über `alarme` und `wertebereiche` (aus dem Prüfstand); neuer Fall `zustellung: PUT-Rumpf ohne Altschluessel; Altbestand und Nachbar-Nutzer unveraendert`: gleicher Aufbau (`bestandMitAltfeldern` für zwei Nutzer, Go-Merge-Server, Messung `altFunde(rumpf)`, Bestand `ALT_DC`, `outlook_enabled`, `show_outlook`, `placements`, `user_id`), aber der Speicherer ist `erstelleZustellungSpeicherung({ context: 'vergleich', … })` und die Geste `morgenZeit '06:45'`; der `hydrateLayoutFieldsFromPreset`-Fall bleibt; der Fall `Lese-Naht channel_active_metrics ist entfernt` (dynamischer Import Z. 253) bleibt unverändert, weil er eine Abwesenheit prüft und das Modul bleibt |
| shared/weather-metrics-tab/__tests__/wetter_metriken_hydration_vollstaendig_vor_baseline.test.ts | Block `AC-3 (Mechanismus)` (1 Fall); Importe `erstelleWetterMetrikenVergleichSpeicherung`, `createFakeTripServer`, `api`, `createPutQueue`, `./wetterMetrikenVergleichPruefstand.ts` | Block `AC-3 (Prädikat)` mit 5 Fällen auf dem lebenden `wetterMetrikenHydrationAbgeschlossen` |
| shared/weather-metrics-tab/__tests__/wetter_metriken_und_wertebereiche_teilen_active_metric_keys.test.ts | Fälle 1 und 3 (Wetter-Metriken-Speicherer plant nichts, SaveFn liest bei Ausführung); Importe `erstelleWetterMetrikenVergleichSpeicherung`, `./wetterMetrikenVergleichPruefstand.ts` | Fall 2 („Metrikauswahl geändert, noch nicht gespeichert, Wertebereiche speichert → neue Auswahl wird live mitgenommen“) bleibt mit dem lebenden Wertebereiche-Speicherer; Aufbau aus `wertebereicheVergleichPruefstand.ts` (`makePreset`, `createController`, `hydrierterWs`); die Änderung der Auswahl ist `ws.activeMetricKeys = [...ws.activeMetricKeys, 'gust_max_kmh']`; der Rumpf wird direkt über `display_config.active_metrics` gelesen |

Gruppe b hat damit 15 Dateien (Kontext: 19; 4 davon auf „Löschen“ umgestuft).

### Gruppe c: nur Folgen des Prüfstands

| Pfad | Änderung |
|---|---|
| compare/__tests__/compare_retry_fehlerpfade_kein_verlust.test.ts | Tabelle `faelle` (Z. 228-232) behält nur `wertebereiche` (Zeilen `versand` und `wetterMetriken` entfallen). Fall `Teil-Erfolg` (Z. 261-293) wird umgestellt: der veraltete, nie gespeicherte Reiter `ve` ist ein zweiter `reiterAufbau('alarme', start, api, geteilt)`; Fremdwert statt `morning_time` ist `alert_cooldown_minutes: 15`; die Änderung setzt `ve.zustand.alertCooldownMinutes = 77` und meldet `ve.speicherung.aenderungMelden()`; die Zusicherungen bleiben (alle neuen PUTs mit 412, Server-Wert bleibt 15, Controller `conflict`). Fall `F502` unberührt |
| shared/__tests__/compare_reiter_nutzlast_nur_eigene_felder.test.ts | Fälle `versand: keine alert_cooldown_minutes/…`, `wetterMetriken: Leeren ⇒ KEIN [] im Rumpf …` und `versand: „Bis auf Weiteres“ ⇒ end_date: ""` entfallen; die Schleifen über `REITER` (Test 1 und Test 7) laufen automatisch nur über `alarme` und `wertebereiche`; die lebende Zusicherung `end_date: ""` bleibt am Zustellungs-Speicherer in `zustellungSpeicherung.test.ts` (`ac10_bis_datum_und_zurueck`) |
| compare/__tests__/compare_konflikt_nutzlast_am_eintrag.test.ts | unverändert (Schleife über `REITER` zählt weniger Reiter) |

## Die Prüfstände

### wetterMetrikenVergleichPruefstand.ts: löschen

Begründung: Alle 14 bisherigen Importeure sind nach den Löschungen und Umbauten oben ohne Bezug: 8 Wetter-Metriken-Tests der Gruppe a entfallen, `wetter_metriken_reiterwechsel_verliert_nichts` und `f006_zustellung_schreibt_keine_wetterfelder` entfallen, `wetter_metriken_hydration_vollstaendig_vor_baseline`, `wetter_metriken_und_wertebereiche_teilen_active_metric_keys` und `alarme_vergleich_kanalwahl_speicherweg` nutzen ihn nicht mehr, `compareReiterAufbauPruefstand` entfernt den Reiter. Kein Wächter mahnt einen entbehrlichen Prüfstand an (`altfeld_namen_sperre.test.ts` nimmt `*Pruefstand.ts` aus, der Waisen-Wächter ignoriert `__tests__/`); deshalb steht die Löschung hier und im Wächter-Block (Prüfung „Datei existiert nicht“).

### versandVergleichPruefstand.ts: verkleinern

`hydrierterWiz`, `versandBedienung` und `dc` entfallen (nur die Versand-Tests der Gruppen a und b benutzten sie; gemessen). `makePreset` und `createController` bleiben; `createController` hat über 25 lebende Importeure, `makePreset` importiert nach dem Umbau `hub_put_queue`. Der Kopfkommentar wird auf die zwei verbleibenden Hilfen gekürzt.

### compareReiterAufbauPruefstand.ts: verkleinern auf zwei Reiter

`Reiter` wird `'alarme' | 'wertebereiche'`, `REITER` hat zwei Einträge. Die Zweige `versand` (Z. 94-110) und `wetterMetriken` (Z. 131-150), die Importe `erstelleVersandVergleichSpeicherung`, `hydrateVersandFieldsFromPreset`, `erstelleWetterMetrikenVergleichSpeicherung`, `hydrierterWetterWs`, `wetterMetrikenBedienung` entfallen; `konfliktMitFremdemNamen` bleibt. Die Matrix-Tests verlieren nur Läufe der toten Reiter. Lebende Reiter verlieren keine Abdeckung; der lebende Zustellungs-Speicherer erhält den Altschlüssel-Fall in `feat3298` und besitzt die Eigenfeld- und `end_date`-Zusicherungen in `zustellungSpeicherung.test.ts`. `goMergeServerPruefstand.ts`: `EIGENFELDER.versand` und `EIGENFELDER.wetterMetriken` entfallen, weil kein Test sie mehr liest (`compare_reiter_nutzlast_nur_eigene_felder` ist der einzige Leser).

## Lebende Hydrations-Funktionen: Abdeckung nach der Löschung

| Funktion | Test nach der Löschung |
|---|---|
| `hydrateVersandFieldsFromPreset` | `hub_versand_inline` (3 Fälle), `versand_vergleich_premium_sms` (1 Fall), `compare_versand_hydration_unter_wetter_metriken`, `compare_retry_reiterwechsel_eingabe_bleibt` (über den echten Hub-Effekt) |
| `hydrateWeatherMetricsFromPreset` | `compareActiveMetricsStorageFormat`, `fix_3061_hub_hydrierer` (Hub-Hydrierer, 3 Fälle) |
| `hydrateLayoutFieldsFromPreset` | `feat3298` (Fall `Altwerte aendern das Ergebnis nicht`), `fix_3061_hub_hydrierer` (`AC-4`, neu mit Ergebnis-Assertion) |
| `wetterMetrikenHydrationAbgeschlossen` | `wetter_metriken_hydration_vollstaendig_vor_baseline` (5 Fälle) |
| `hydrateDayWindowFromPreset` | bisher kein direkter Test (nur indirekt über `CompareTabs.svelte`); NEU `weather_metrics_hydration_tagesfenster.test.ts` |

Der neue Ersatztest hat drei Fälle: (1) Preset mit `day_window_start_hour: 6` und `day_window_end_hour: 21` liefert `{ dayWindowStartHour: 6, dayWindowEndHour: 21 }`; (2) Preset ohne beide Felder liefert den Trip-Standard 4 und 19; (3) Preset mit `null` in beiden Feldern liefert 4 und 19. Er ist heute schon grün (Regressionsschutz vor der Löschung der Nachbarn). Mutations-Gegenprobe: Standardwert 19 auf 20 ändern macht Fall 2 und 3 rot.

## Die Zählstellen (alter und neuer Wert)

Die Werte der Spalte „Neu“ sind verbindlich.

| Stelle | Alt | Neu | Änderung |
|---|---|---|---|
| `context_herkunft_zweige_eingefroren.test.ts` `EINGEFROREN_SOLL_ANZAHL` (Z. 318) | 10 | **8** | Einträge `'versandVergleichSpeicherung.ts:236'` (Z. 235) und `'weather-metrics-tab/weatherMetricsCompareSave.ts:364'` (Z. 294) samt ihren Kommentarblöcken entfernen; Bilanzkommentar Z. 301-317 um die Zeile „#3389: `versandVergleichSpeicherung.ts:236` und `weatherMetricsCompareSave.ts:364` (die beiden `…SpeicherungAktiv`-Weichen) mit den toten Exporten gelöscht — 2 ENTFERNTE Verzweigungen. Soll 10 → 8.“ ergänzen; die Geschichts-Kommentare Z. 47-86 und 165-177 bleiben. `wetter-tab/wertebereicheVergleichSpeicherung.ts:203` bleibt |
| `ac2_endbilanz_deckt_alle_47_ab.test.ts` | Positiv-Kontrolle 10; Spec-Kategorien FACHLICH 5, DARSTELLUNG 2, HERKUNFT 3, Summe 10 | **8**; FACHLICH 5, DARSTELLUNG 2, HERKUNFT **1**, Summe **8** | Zahlen und Fehlermeldungstexte (Z. 90-108, Kommentar Z. 94 um #3389 ergänzt) |
| `docs/specs/modules/rework_2276_s6h_ac2_endbilanz.md` | Tabelle HERKUNFT 3 Zeilen; Summenzeile 5/2/3 = 10 | HERKUNFT 1 Zeile; 5/2/1 = **8** | Tabellenzeilen Z. 124 und Z. 126 entfernen, Überschrift „HERKUNFT (1 …)“, Anhang-Überschrift Z. 101 „alle 8 Ratschen-Einträge“ mit Zusatz „seit #3389 ohne `versandVergleichSpeicherung.ts:236` und `weather-metrics-tab/weatherMetricsCompareSave.ts:364`“, Summenzeile Z. 128-132 um „#3389: 5 / 2 / 1 = 8“ ergänzen |
| `fallliste_editor.json:637`, Fall `D-orte_vergleichstabelle-totalschnitt_aus_wirkt-frontend` | `test` verweist auf `wetter_metriken_nutzlast_verliert_keine_daten.test.ts::Kanal-Auswahl geändert → …` (Datei wird gelöscht) | `test`: `frontend/src/lib/components/shared/wetter-tab/__tests__/editor_standard_gleich_ausgabe_3020.test.ts::frontend_seite_orte_vergleichstabelle_gespeichert gespeichert_kanal_totalschnitt` | Derselbe Verweis wie beim Schwester-Fall `D-orte_vergleichstabelle-gespeichert_kanal_totalschnitt-frontend` (Z. 623); Status `ausnahme` bleibt, dem Verweis-Text wird „#3389“ angehängt; Anzahl `ausnahme` bleibt 14. Es ist der einzige Fall der Falllisten mit Verweis auf eine Löschkandidaten-Datei (gemessen) |
| `totcode_rueckbau_speicherweg.test.ts:114-118` Liste `speicherModule`, Positivkontrolle | beide Module: `'buildComparePresetSavePayload'` | `versandVergleichSpeicherung.ts`: `'hydrateVersandFieldsFromPreset'`; `weatherMetricsCompareSave.ts`: `'hydrateWeatherMetricsFromPreset'` | `buildComparePresetSavePayload` steht nach der Löschung in keinem der beiden Module mehr. Der Test behält seinen Zweck (Verbot von `buildHubPutPayload`); die Positivkontrolle ist nun ein lebender Name derselben Datei |
| `feat3298_vergleich_ohne_altfelder.test.ts:253` dynamischer Import des Weather-Moduls | – | unverändert | Der Fall prüft die Abwesenheit von `hydrateChannelActiveMetricsFromPreset`, nicht einen toten Export; das Modul bleibt am selben Pfad |
| `waisen_waechter.test.ts` `BEKANNTE_WAISEN`/`OBERGRENZE_WAISEN` | leer / 0 | leer / 0 | beide Module bleiben erreichbar |
| `bausteine_waechter_regeln.ts` `BESTAND_OBERGRENZE` | 162 | 162 | listet nur `.svelte`-Bausteine, kein Eintrag nennt die Module |
| `ein_katalog_ausnahmen.json` `hoechststand` / `test_ein_katalog_eine_verarbeitung_ratsche.py` `HOECHSTSTAND` | 421 / 421 | 421 / 421 | Scan der beiden Module liefert 0 Funde (gemessen) |
| `.github/workflows/ci.yml` `E2E_MIN_SPECS` und `E2E_MIN_EXECUTED*` | 85 | 85 | keine Browser-Spec importiert die Module oder Prüfstände (nur Kommentar in `hub-versand-speichert-selbst.spec.ts:29`) |
| `rework_3020_umfang.ts:59` `BLEIBT` (`weatherMetricsCompareSave.ts`), `RESTBESTAND_ANZAHL` 19, `SPEC_ANZAHL` 42, `DURCH_WAISEN_ENTFERNT` 23, `LEBENDE_HELFER_NUTZER` | wie heute | unverändert | die Datei bleibt bestehen; `rework_3020_rueckbau_waechter.test.ts:110` prüft nur Existenz und Nicht-Umfang; keine der gelöschten oder umgebauten Testdateien steht in `LEBENDE_HELFER_NUTZER` |
| `rework_3020_rote_liste.ts` (E008, E013/E014, E065/E066) | 60/145/15 | unverändert | nennen die Dateien nur als Vergleichsnamen entfallener Fälle; Liste „nie kürzen“ |
| `trip_pfad_altfeld_loeschnachweis_3297.test.ts:48,191` (`ERHALTEN`, `ERHALTEN_3383` mit `weatherMetricsCompareSave.ts`) | enthalten | unverändert | Datei bleibt; der neue Block `#3389` kommt dazu |
| Elementliste, Katalog-Wächter | – | unverändert | reine Logikdateien, keine Oberfläche, keine Katalogschlüssel |

## Der neue Wächter: Lösch-Nachweis auf Exportebene

**Datei:** `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts`, neuer Block `describe('#3389 …')` direkt nach dem Block `#3385`, im selben Muster (wiederverwendet `scanDateien3385`, `ohneKommentare`, `basisname`, `pfad`).

**Konstanten:** `GELOESCHT_3389` (die 23 Namen: 21 tote Exporte und die zwei Typen `VersandSnapshot`, `LayoutSnapshot`, je mit Modul) und `LEBEND_3389`: `versandVergleichSpeicherung.ts` exportiert genau `hydrateVersandFieldsFromPreset`; `weatherMetricsCompareSave.ts` exportiert genau `hydrateDayWindowFromPreset`, `hydrateWeatherMetricsFromPreset`, `hydrateLayoutFieldsFromPreset`, `wetterMetrikenHydrationAbgeschlossen`. Dazu die Liste der 21 gelöschten Testdateien und die gelöschte Datei `weather-metrics-tab/__tests__/wetterMetrikenVergleichPruefstand.ts`.

**Prüfungen (je ein Test):**

1. Die 21 Testdateien und der Prüfstand `wetterMetrikenVergleichPruefstand.ts` existieren nicht (`existsSync === false`, wie im Block `#3385`).
2. Exportmenge: aus dem Text beider Module ohne Kommentare werden alle `export`-Namen gelesen (`export function|async function|const|let|class|interface|type|enum <Name>` und `export { … }`); die Menge muss gleich `LEBEND_3389` sein. Das ist ein Ratschen-Vertrag: jeder neue Export in einem der beiden Module macht den Test rot und verlangt die Erweiterung von `LEBEND_3389` samt Produktionsaufrufer.
3. Wortscan: über alle `.ts`, `.js`, `.mjs`, `.svelte`-Dateien unter `frontend/src` und `frontend/e2e` (ohne Kommentare, Treffer wortgenau mit `\b…\b`) darf keiner der 23 Namen vorkommen; einzige Ausnahme ist diese Lösch-Nachweis-Datei. Das fängt Importe, Aufrufe, Typverwendungen, Namen in Testtiteln und ein zurückkehrendes `export`, auch in anderen Dateien.
4. Lebende Exporte: die 5 Namen sind weiterhin in Produktionsdateien importiert (`CompareTabs.svelte`, `compareHubHydration.ts`, `compareNewVorlage.ts`); die Aufrufer sind also noch vorhanden (Schutz gegen „aus Versehen mitgelöscht“).
5. Die Pfadzeichenketten-Prüfung des Blocks `#3385` (`funde3385`) bleibt für die Dateien dort bestehen; für #3389 gilt der Wortscan, weil keine Datei, sondern Namen entfallen. Der dynamische `import()` der Module in `feat3298_vergleich_ohne_altfelder.test.ts:253` nennt keinen der 23 Namen und bleibt.

**Selbstnachweis (im selben Block, ohne Plattendateien, mit eingebetteten Mini-Quellen):** (a) eine Mini-Quelle `export function erstelleVersandVergleichSpeicherung() {}` macht die Exportprüfung rot (Fund gemeldet); (b) eine Mini-Quelle mit dem Namen nur in einem `//`- oder `*`-Kommentar meldet keinen Fund; (c) eine Mini-Quelle `export const neuerExport = 1` erscheint als zusätzlicher Export; (d) ein Namensfund in der Mini-Quelle einer anderen Datei (zum Beispiel ein `import { wetterMetrikenSnapshotAus } from …`) wird vom Wortscan gemeldet. Mutations-Gegenprobe des Validators: einen der 23 Namen in einem der Module wieder als `export` anlegen, oder eine Testdatei anlegen, die einen der Namen importiert, macht den jeweiligen Test rot (Kopie mit externer Sicherung, nie `git checkout/stash/reset`).

**Abgrenzung zum Waisen-Wächter:** `waisen_waechter.test.ts` arbeitet auf Dateiebene; beide Module bleiben dort Nicht-Waisen. Tote Exporte in lebenden Dateien erfasst nur dieser neue Block.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/rework-3389-tote-exporte.md` | doc | Analyse und Grobmessung (hier nachgeprüft und in vier Punkten korrigiert) |
| `docs/specs/modules/rework_3385_waisen_s3.md`, `rework_3384_waisen_s4.md`, `rework_3383_waisen_s1.md` | spec | Vorbilder für Aufbau, Lösch-Nachweis, Zählstellen |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` | test | Ort des neuen Wächter-Blocks, Hilfen `scanDateien3385`, `ohneKommentare` |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungSpeicherung.ts` und `__tests__/zustellungSpeicherung.test.ts` | prod/test | lebender Speicherer; Ersatzbeleg für die gelöschten Versand- und Wetter-Metriken-Fälle |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts`, `wetter-tab/wertebereicheVergleichSpeicherung.ts` | prod | lebende Speicherer für die umgestellten Tests (Alarme, Wertebereiche) |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/wertebereicheVergleichPruefstand.ts` | test | Prüfstand für `hub_nochmal_speichern_ueber_reiterwechsel` und `…teilen_active_metric_keys` |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | test | Verweis-Wächter der Fallliste |
| `node --test`, `svelte-check`, Vite-Build | tooling | Nachweis „keine sichtbare Änderung“ |

## Implementation Details

**Reihenfolge.** (1) RED: Wächter-Block `#3389` anlegen; er ist rot, weil 23 Namen existieren, 21 Testdateien bestehen und die Exportmenge zu groß ist. Der Ersatztest für `hydrateDayWindowFromPreset` entsteht ebenfalls vor der Löschung (heute grün). (2) Vor dem Löschen wird die `svelte-check`-Baseline (Fehler und Warnungen) auf dem Branch-Stand gemessen und in `docs/artifacts/rework-3389-tote-exporte/svelte-check.md` festgehalten (Zeilen „vorher“ und „nachher“). (3) Umbauten der 15 Testdateien und der Prüfstände, Löschung der 21 Testdateien und des Wetter-Metriken-Prüfstands, Löschung der Exporte in den Modulen, Importe aufräumen, Kommentare kürzen. (4) Zählstellen, Fallliste, Spiegel-Spec und Referenz-Doku im selben Commit nachziehen. (5) Alle betroffenen Testdateien benannt laufen lassen (nie `uv run pytest` ohne Dateinamen), danach die gesamte Frontend-Suite, Build, `svelte-check`.

**Zählstellen sind verbindlich:** Nach dem Löschen werden die Zahlen der Tabelle „Zählstellen“ gegengemessen. Weicht eine Messung von der Spalte „Neu“ ab, ist das ein Fehler in der Umsetzung (zu viel oder zu wenig gelöscht). Er wird nicht hingenommen und nicht still angepasst; die Spec bekommt stattdessen einen eigenen Nachtrag mit Begründung (neue Version im Changelog, wie bei #3385 v1.3), erst danach ändert sich der Sollwert.

**gates_und_ratschen.md:** der Absatz Z. 548-561 behält die Geschichte; hinter die Aussagen „`versandVergleichSpeicherung.ts:221` blieb unverändert an Position“ und „`weatherMetricsCompareSave.ts:534` blieb …“ kommt der Satz „(beide Einträge mit #3389 entfernt, zusammen mit den toten `…SpeicherungAktiv`-Exporten; die Ratsche führt danach 8 Einträge)“.

## Expected Behavior

- **Input:** Quelltext von `frontend/src` und `frontend/e2e`.
- **Output:** Beide Module exportieren genau die fünf lebenden Hydrations-Funktionen; kein Name der 23 kommt in Code vor; Wächter, Ratschen und Frontend-Suite sind grün; `EINGEFROREN` hat 8 Einträge.
- **Side effects:** keine sichtbare Änderung für Nutzer; Tests, Prüfstand-Hilfen und zwei Produktionsdateien schrumpfen.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Wächter `#3389` rot vor der Löschung (23 Namen vorhanden, 21 Testdateien und Prüfstand vorhanden, Exportmenge zu groß), grün danach; Selbstnachweis-Fälle (a) bis (d) grün; Mutationen siehe Wächter-Abschnitt.
- [ ] Ersatztest `weather_metrics_hydration_tagesfenster.test.ts` vor der Löschung grün (Regressionsschutz), nach der Löschung grün; Mutation Standardwert 19 auf 20 macht ihn rot.
- [ ] `feat3298` Fall `zustellung`: Altschlüssel-freier PUT, Bestand beider Nutzer bleibt; Mutation: `erstelleZustellungSpeicherung` sendet testweise `display_config` mit `outlook_metrics` (Kopie mit externer Sicherung) ⇒ Fall rot.
- [ ] Umgebaute Tests: jede der 15 Dateien behält die in der Tabelle „Umbauen“ genannten Fälle; jeder davon wird bei einer Verfälschung der gemeinten lebenden Funktion rot (Validator-Gegenprobe); insbesondere `hub_put_queue` F002/F003 am Alarme-Speicherer (Mutation: `onCompareUpdate` im Alarme-Speicherer nicht aufrufen ⇒ F002 rot; Rollback ohne Diff-Prüfung ⇒ F003 rot) und `hub_nochmal_speichern_ueber_reiterwechsel` am Wertebereiche-Speicherer.
- [ ] Zählstellen: `context_herkunft_zweige_eingefroren` (Soll 8), `ac2_endbilanz_deckt_alle_47_ab` (8 = 5/2/1), `totcode_rueckbau_speicherweg`, `tests/tdd/test_einstellung_gleich_mail_fallliste.py` benannt grün; Mutation: `EINGEFROREN_SOLL_ANZAHL` um 1 erhöhen macht den Test rot, einen Verweis in der Fallliste auf einen nicht existierenden Titel setzen macht `test_testverweise_auffindbar` rot.
- [ ] Gesamt: Frontend-Suite (`node --test`), Vite-Build und `svelte-check` grün; die `svelte-check`-Zahlen steigen nach dem Löschen nicht.
- [ ] Benannt laufen lassen (zusätzlich zu den oben genannten): `hub_versand_inline`, `versand_vergleich_premium_sms`, `compare_versand_hydration_unter_wetter_metriken`, `compareActiveMetricsStorageFormat`, `fix_3061_hub_hydrierer`, `feat3276`, `feat3298`, `wetter_metriken_hydration_vollstaendig_vor_baseline`, `compare_retry_fehlerpfade_kein_verlust`, `compare_reiter_nutzlast_nur_eigene_felder`, `compare_konflikt_nutzlast_am_eintrag`, `alarme_vergleich_konflikt_nochmal_speichern`, `wertebereiche_vergleich_konflikt_nochmal_speichern`, `zustellungSpeicherung`, `waisen_waechter`, `rework_3020_rueckbau_waechter`, `trip_pfad_altfeld_loeschnachweis_3297`; Python (benannt): `tests/tdd/test_einstellung_gleich_mail_fallliste.py`, `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py`.

## Acceptance Criteria

Einordnung: AC-1, AC-2, AC-3, AC-6, AC-7 und AC-9 sind **Struktur-Wächter** gegen die Rückkehr gelöschter Exporte und gegen Zählstellen-Drift, im selben Sinn wie die Waisen-Wächter in #3383 bis #3385. Sie lesen Quelltext und Zahlen und sind kein Verhaltensnachweis. Das Verhalten belegen AC-4, AC-5, AC-8 und AC-10 (lebende Editor- und Hub-Tests, Hydrations-Tests und der Ersatztest für `hydrateDayWindowFromPreset`).

- **AC-1 (Struktur-Wächter):** Given die beiden Module `versandVergleichSpeicherung.ts` und `weatherMetricsCompareSave.ts` / When der Lösch-Nachweis ihren Quelltext nach `export`-Namen durchsucht / Then ist die Menge der Exporte je Modul exakt die der lebenden Hydrations-Funktionen (Versand: eine, Weather: vier), und keiner der 21 toten Namen samt `VersandSnapshot` und `LayoutSnapshot` ist als Export zurückgekehrt; ein Beleg für Nutzerverhalten ist das nicht, den liefern AC-4, AC-5, AC-8 und AC-10.
  - Test: `trip_pfad_altfeld_loeschnachweis_3297.test.ts`, Block `#3389`, Fall „Exportmenge“. Mutations-Gegenprobe: einen gelöschten Namen wieder als `export` anlegen macht den Test rot.

- **AC-2 (Struktur-Wächter):** Given der gesamte Quelltext unter `frontend/src` und `frontend/e2e` / When der Wortscan ohne Kommentare nach den 23 Namen sucht / Then gibt es keinen Treffer außerhalb der Lösch-Nachweis-Datei, die 21 gelöschten Testdateien und der Prüfstand `wetterMetrikenVergleichPruefstand.ts` existieren nicht mehr, und die fünf lebenden Exporte haben weiterhin ihre Produktionsaufrufer in `CompareTabs.svelte`, `compareHubHydration.ts` und `compareNewVorlage.ts` (Schutz gegen Rückkehr toter Namen, kein Verhaltensnachweis).
  - Test: Block `#3389`, Fälle „Wortscan“, „Dateien gelöscht“, „Aufrufer vorhanden“. Mutations-Gegenprobe: eine Testdatei anlegen, die einen der Namen importiert, macht den Wortscan rot.

- **AC-3 (Struktur-Wächter):** Given der Selbstnachweis des Wächters / When er auf eingebettete Mini-Quellen läuft / Then meldet er ein wieder eingeführtes `export function erstelleVersandVergleichSpeicherung`, meldet einen neuen Export `neuerExport` als Abweichung von der Exportmenge, meldet einen Importfund eines gelöschten Namens in einer anderen Datei und meldet keinen Fund, wenn der Name nur in einem Kommentar steht (der Wächter selbst wird geprüft, damit er nicht still blind ist).
  - Test: Block `#3389`, vier Selbstnachweis-Fälle. Mutations-Gegenprobe: im Scanner die Kommentar-Filterung entfernen macht den Kommentar-Fall rot; die Exportregex auf `export function` einschränken macht den Fall `export const` rot.

- **AC-4:** Given ein Ortsvergleich-Preset mit gesetztem, fehlendem oder `null`-wertigem Tagesfenster / When die lebende Hydration `hydrateDayWindowFromPreset` es liest / Then liefert sie die gespeicherten Stunden (6 und 21) oder den Trip-Standard 4 und 19.
  - Test: neu `weather_metrics_hydration_tagesfenster.test.ts` (3 Fälle). Mutations-Gegenprobe: Standardwert 19 auf 20 ändern macht Fall 2 und 3 rot.

- **AC-5:** Given die 21 gelöschten Testdateien und die 15 umgebauten Dateien / When die Löschung geliefert ist / Then bleiben genau diese Fälle als lebender Prüfling stehen: in `hub_versand_inline` die 3 Fälle des Blocks `AC-36 (Basis): hydrateVersandFieldsFromPreset` und die 4 Fälle des Blocks `hubActivationBanner`; in `versand_vergleich_premium_sms` der Fall `hydrateVersandFieldsFromPreset liest preset.send_premium_sms`; in `s3a2794_zustellung_vergleich_ein_speicherer` die Fälle 1 und 2 (Cooldown, Stille Stunden: ein PUT über den Alarme-Speicherer); in `alarme_vergleich_kein_zurueckschreiben` der Block `S2-AC-3`; in `alarme_vergleich_kanalwahl_speicherweg` 10 Fälle, darunter `AC-57` am Wertebereiche-Teil-PUT; in `compare_alarm_versand_nutzlast_trennung` die 3 Alarm-/Kanal-/Anlege-Blöcke; in `compare_retry_reiterwechsel_eingabe_bleibt` 9 Fälle ohne `F301a`/`PX2`; in `hub_nochmal_speichern_ueber_reiterwechsel` alle 3 Fälle am Wertebereiche-Speicherer; in `hub_put_queue` 5 Fälle, davon `F002-Integration` und `F003-Regression` am Alarme-Speicherer; in `compare_outlook_metric_formats_persistenz` die 3 Fälle des Blocks `#2049 F004`; in `fix_3061_hub_hydrierer` 8 Fälle, darunter `AC-4` mit Hydrations-Ergebnis (`activeMetricKeys` null, Layout); in `feat3276_vergleich_ohne_altfelder` 8 Fälle, darunter `Alarm- und Wertebereiche-Speicherer senden keinen Altschluessel`; in `feat3298_vergleich_ohne_altfelder` die Reiter-Schleife (alarme, wertebereiche), der neue Fall `zustellung`, der `hydrateLayoutFieldsFromPreset`-Fall und `Lese-Naht channel_active_metrics ist entfernt`; in `wetter_metriken_hydration_vollstaendig_vor_baseline` die 5 Fälle des Blocks `AC-3 (Prädikat)`; in `wetter_metriken_und_wertebereiche_teilen_active_metric_keys` Fall 2 am Wertebereiche-Speicherer. Die Zusicherungen der gelöschten Dateien (Pausieren-Flush, Keepalive, `end_date`, Eigenfelder, kein Wetter-Feld in der Zustellung) stehen am lebenden Zustellungs-Speicherer in `zustellungSpeicherung.test.ts` (`ac10_bis_datum_und_zurueck`, `ac32_nur_morgenzeit_ein_put_fremdfelder_unveraendert`, `ac26_vergleich_cooldown`, `NIE`-Liste) und `rework_3020_zustellung_ifmatch_keepalive.test.ts`.
  - Test: die genannten Dateien benannt grün (`node --test`). Mutations-Gegenprobe des Validators am lebenden Speicherer (`onCompareUpdate` entfernen macht `F002-Integration` rot, Rollback ohne Diff-Prüfung macht `F003-Regression` rot, Zustellungs-Nutzlast mit `display_config` macht `zustellungSpeicherung.test.ts` rot).

- **AC-6 (Struktur-Wächter):** Given die Prüfstände / When die Löschung geliefert ist / Then ist `wetterMetrikenVergleichPruefstand.ts` gelöscht, `compareReiterAufbauPruefstand.ts` kennt nur noch die Reiter `alarme` und `wertebereiche`, `versandVergleichPruefstand.ts` enthält nur noch `makePreset` und `createController`, `goMergeServerPruefstand.ts` kennt keine Eigenfelder für `versand` und `wetterMetriken`, und die Matrix-Tests (`compare_konflikt_nutzlast_am_eintrag`, `compare_reiter_nutzlast_nur_eigene_felder`, `feat3298` mit Fall `zustellung`, `compare_retry_fehlerpfade_kein_verlust` mit Alarme-Ersatz im Teil-Erfolg-Fall) laufen grün; die Prüfstand-Struktur wird vom Wächter aus AC-2 gegen Rückkehr gesichert, das Verhalten belegt AC-5.
  - Test: die genannten Dateien benannt grün; Mutation: im Prüfstand den Zweig `versand` mit `erstelleVersandVergleichSpeicherung` wieder einfügen macht den Wortscan des Wächters rot.

- **AC-7 (Struktur-Wächter):** Given die Ratschen und Katalogverweise / When die Zählstellen nach dem Löschen gegengemessen werden / Then ist `EINGEFROREN_SOLL_ANZAHL` von 10 auf 8 gesenkt (Einträge `versandVergleichSpeicherung.ts:236` und `weatherMetricsCompareSave.ts:364` entfernt), die ac2-Endbilanz und ihr Spiegel `rework_2276_s6h_ac2_endbilanz.md` führen 5/2/1 = 8, die Fallliste verweist beim Fall `D-orte_vergleichstabelle-totalschnitt_aus_wirkt-frontend` auf `editor_standard_gleich_ausgabe_3020.test.ts`, die Positivkontrolle in `totcode_rueckbau_speicherweg.test.ts` nennt `hydrateVersandFieldsFromPreset` und `hydrateWeatherMetricsFromPreset`, und `BEKANNTE_WAISEN`, `BESTAND_OBERGRENZE`, `hoechststand`/`HOECHSTSTAND`, `E2E_MIN_*` und die `rework_3020_*`-Zahlen sind unverändert; die Werte sind verbindlich, jede Abweichung ist ein Umsetzungsfehler und führt zu einem Spec-Nachtrag, nicht zu einer stillen Anpassung.
  - Test: `context_herkunft_zweige_eingefroren`, `ac2_endbilanz_deckt_alle_47_ab`, `totcode_rueckbau_speicherweg`, `waisen_waechter`, `rework_3020_rueckbau_waechter` und `tests/tdd/test_einstellung_gleich_mail_fallliste.py` benannt grün. Mutation: `EINGEFROREN_SOLL_ANZAHL` um 1 erhöhen oder einen Fallliste-Verweis auf einen nicht existierenden Titel setzen macht den jeweiligen Test rot.

- **AC-8:** Given der Ortsvergleich-Editor und der Hub (Reiter Alarme, Wetter, Zustellung, Hydration beim Öffnen, Aktivieren und Pausieren, Konfliktbehandlung) / When die gesamte Frontend-Suite, der Produktions-Build und `svelte-check` laufen / Then sind alle grün, die lebenden Editor- und Hub-Tests (`hub_versand_inline`, `compare_versand_hydration_unter_wetter_metriken`, `fix_3061_hub_hydrierer`, `compareActiveMetricsStorageFormat`, `compare_retry_reiterwechsel_eingabe_bleibt`, `compare_hub_pausieren_flusht_vorher`, `rework_3020_vergleich_parallele_schreiber`, `s3a2794_flush_hydration_kette`, `zustellungSpeicherung`) laufen vollständig grün, die `svelte-check`-Zahlen (Fehler und Warnungen) wurden vor dem Löschen gemessen und steigen nachher nicht, und für Nutzer gibt es keine sichtbare Änderung.
  - Test: Frontend-Suite per `node --test`, `npm run build`, `svelte-check` (Zahlen vorher/nachher in `docs/artifacts/rework-3389-tote-exporte/svelte-check.md`). Mutations-Gegenprobe: einen Typfehler in eines der beiden Module schreiben macht `svelte-check` rot.

- **AC-9 (Struktur-Wächter):** Given Browser-Specs, CI-Konfiguration, Hooks und Produktionscode außerhalb der Löschmenge / When die Scheibe geliefert ist / Then sind `frontend/e2e/`, `.github/` (darin `ci_e2e_specs.txt` und `ci.yml` mit `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`) und `.claude/hooks` gegenüber `origin/main` unverändert, und die einzigen geänderten Produktionsdateien sind die zwei Module und `CompareTabs.svelte`.
  - Test: Befehl `git diff --quiet origin/main -- frontend/e2e .github .claude/hooks` mit erwartetem Exit-Code 0; Befehl `git diff --name-only origin/main -- frontend/src ':(exclude)*/__tests__/*' ':(exclude)*.test.ts'` mit erwarteter Ausgabe genau der drei Pfade `frontend/src/lib/components/compare/CompareTabs.svelte`, `frontend/src/lib/components/shared/versandVergleichSpeicherung.ts`, `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts`; dazu `tests/tdd/test_2243_playwright_loeschscheibe.py` und `tests/tdd/test_e2e_positivliste_ratschen_bindung.py` benannt grün. Mutation: eine Datei unter `frontend/e2e` verändern macht den ersten Befehl rot (Exit 1).

- **AC-10:** Given ein gespeicherter Ortsvergleich mit Versand-Einstellung (Premium-SMS, Zustellzeit), Tagesfenster, Wetter-Metrik-Auswahl und Stundenverlauf-Schalter / When der Nutzer ihn im Editor oder Hub öffnet und die Hydrations-Funktionen ihn laden / Then sind die Versand-, Tagesfenster-, Wetter-Metrik- und Layout-Felder des Editors mit den gespeicherten Werten gefüllt, und ein Altbestand ohne diese Felder bleibt mit Standardwerten (Metrikauswahl `null`, Tagesfenster 4 bis 19) unverändert.
  - Test: Versand `hub_versand_inline.test.ts` Block `AC-36 (Basis): hydrateVersandFieldsFromPreset` und `versand_vergleich_premium_sms.test.ts::hydrateVersandFieldsFromPreset liest preset.send_premium_sms`; Tagesfenster `weather_metrics_hydration_tagesfenster.test.ts` (3 Fälle); Wetter-Metriken `compareActiveMetricsStorageFormat.test.ts` und `fix_3061_hub_hydrierer.test.ts` (Hub-Hydrierer, 3 Fälle); Layout `feat3298_vergleich_ohne_altfelder.test.ts::Altwerte aendern das Ergebnis nicht` und `fix_3061_hub_hydrierer.test.ts::AC-4`; Hydrations-Abschluss `wetter_metriken_hydration_vollstaendig_vor_baseline.test.ts` (5 Fälle). Mutations-Gegenprobe: in `hydrateVersandFieldsFromPreset` das Feld `send_premium_sms` nicht mehr übernehmen macht den Premium-SMS-Fall rot.

## Definition of Done

- [ ] Spec freigegeben (`approved`/`freigabe`)
- [ ] RED-Nachweis: Wächter `#3389` rot vor der Löschung, grün danach; Ersatztest `hydrateDayWindowFromPreset` vor der Löschung grün
- [ ] svelte-check-Baseline vor dem Löschen gemessen, Artefakt `docs/artifacts/rework-3389-tote-exporte/svelte-check.md`
- [ ] 21 Exporte gelöscht, `VersandSnapshot` und `LayoutSnapshot` ohne `export`, Importe und Kommentare aufgeräumt
- [ ] 21 Testdateien und `wetterMetrikenVergleichPruefstand.ts` gelöscht, 15 Testdateien umgebaut, Prüfstände und Gruppe c angepasst
- [ ] Zählstellen laut Tabelle im selben Commit gepflegt und nach dem Löschen gegengemessen (EINGEFROREN 8, ac2 5/2/1 = 8, Fallliste, totcode)
- [ ] Zusicherungen der gelöschten Tests am lebenden Speicherer belegt (AC-5), Mutations-Gegenproben durch den Validator
- [ ] Frontend-Suite, Build, `svelte-check` und die benannten Python-Tests grün
- [ ] Adversary und Mutations-Gegenprobe am Wächter
- [ ] CI (6 Checks) grün, Deploy ohne sichtbare Änderung

## Known Limitations

- Der Wortscan arbeitet auf Namen: ein neuer Export mit anderem Namen wird nicht vom Wortscan, sondern von der Exportmengen-Prüfung (Ratsche auf genau fünf Namen) gefangen. Eine Verwendung über berechnete Zeichenketten sähe keiner der beiden Scans; für diese Module gibt es keine.
- Die Zusicherungen der gelöschten Versand- und Wetter-Metriken-Speicherer-Tests gelten ab jetzt am Zustellungs-Speicherer; Fälle, die nur den entfernten Speicherer beschrieben (zum Beispiel „Versand-Speicherer meldet bei Alarm-Zustellungsänderung nichts an“), haben kein Gegenstück mehr, weil das Verhalten nicht mehr existiert.

## Out of Scope

- Browser-Specs und Staging-Browserprüfungen (#3374).
- Weitere tote Exporte in anderen lebenden Dateien (Sammel-Issue #1199).
- `compareMetricOrder.ts`, `compareChannelMetricLayouts.ts`, `compareEditorSave.ts` und die übrigen Fremdbausteine (haben weitere Produktionsnutzer).
- Finding F003 aus #3383.
- Änderungen am Zustellungs-Speicherer selbst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Aufräumarbeit nach bestehender Entscheidung (Rückbau der Alt-Speicherer zugunsten des Zustellungs-Speicherers, #2794/#2795/#3020/#3297) und nach vorhandenem Muster (#3383, #3384, #3385); keine neue Entscheidungsfläche. Die Entscheidung, `VersandSnapshot` und `LayoutSnapshot` ohne `export` zu führen, ist modulintern.

## Changelog

- 2026-11-26: Initial spec created (v1.0)
- 2026-11-26: v1.1 nach Validator-Befund: AC-5 mit fester Fallliste, Zählstellen als verbindlich (Abweichung = Spec-Nachtrag), Struktur-Wächter-Einordnung für AC-1/2/3/6/7/9, neues Verhaltens-AC-10 für die Hydrations-Funktionen, AC-9 mit ausführbaren Befehlen
