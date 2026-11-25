---
entity_id: feat_3297_trip_pfad_ohne_altfelder
type: module
created: 2026-11-25
updated: 2026-11-25
status: draft
version: "1.0"
workflow: feat-3297-trip-pfad-ohne-altfelder
tags: [was-steht-wo, placements, rueckbau, frontend, epic-3122]
---

# Was steht wo B6b-3: Trip-Pfad ohne Altfelder und Rückbau WeatherMetricsTab (#3297 + #3020)

## Approval

- [ ] Approved

## Purpose

Das Frontend schreibt und liest im Trip-Pfad noch Altfelder (`channel_layouts`, `channel_layouts_per_report`, `outlook_metrics`, `outlook_metric_formats`, `show_outlook`, `multi_day_trend_reports`), obwohl das Backend sie seit #3277 nicht mehr beachtet und die Tabelle „Was steht wo“ (`placements`) die einzige Quelle ist. Dieses Paket (#3297 und #3020, Epic #3122) löscht den nicht mehr eingebundenen Alt-Editor `WeatherMetricsTab` samt Umfeld, entfernt die letzten Live-Schreibstellen der Altschlüssel im Trip und stellt die Home-Anzeige „Layout konfiguriert“ auf die Tabelle um. Für Nutzer ändert sich nichts Sichtbares: die gelöschten Flächen waren nirgends eingebunden, und alle Bestandstrips tragen bereits Zeilen in der Tabelle.

## Source

- **File:** `frontend/src/lib/components/trip-new/tripNewLogic.ts`, `frontend/src/lib/utils/cockpitHelpers568.ts`, `frontend/src/lib/components/shared/versand-tab/reportConfigPayload.ts`, `frontend/src/lib/components/shared/zustellung-tab/kanalStilSpeicherung.ts`
- **Identifier:** `ergaenzeVersandStandard`, `ergaenzeStandardwerteReportConfig`, `hasLayout`, `kanalStilNutzlast`/`tripNutzlast`, `ausblickReports`

> **Schicht-Hinweis:** Nur Frontend (`frontend/src`, `frontend/e2e`) und Doku. Kein Go-, kein Python-Eingriff, kein Datenlauf (#3351). Das Backend verwirft Altfelder bereits beim Speichern (`src/app/loader.py`, `ALTFELDER`, #3277).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung (Gate):** Es entsteht keine neue Komponente und kein Pendant. Gelöscht werden Flächen, die in keinem Kontext gemountet sind (weder `route` noch `vergleich`); die Live-Karte `WasStehtWoKarte` mit `context` bleibt unberührt. Vergleich-Hilfen mit Produktions-Import bleiben.
> - **Mandantentrennung:** Kein neuer datenbewegender Endpoint; die Nutzlast-Tests laufen mit dem Go-Merge-Fake für zwei Nutzer, `user_id` kommt wie bisher aus dem Auth-Kontext, nie `"default"`.
> - **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS sind nicht berührt (reines Frontend, Ausgabe entsteht im Backend aus `placements`).
> - **Altschlüssel nur weglassen, nie leer senden:** Go ersetzt Top-Level-Werte (`internal/handler/config_merge.go`); ein leeres `{}`/`[]`/`null` würde Bestand überschreiben oder Leerfelder anlegen.

## Estimated Scope

- **LoC:** neuer Produktionscode unter +120, netto ca. -4000 bis -5000 (überwiegend Löschzeilen)
- **Files:** ca. 25 Produktionsdateien (9 bis 14 gelöscht, ca. 11 geändert), 40 bis 60 Testdateien gelöscht oder umgestellt, 3 neu
- **Effort:** groß (ein Durchlauf, überwiegend Rückbau und Test-Umstellung)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_3276_vergleich_altfelder_entfernen` | Spec | Vorbild (Nutzlast-Test, Weglassen statt leer senden) |
| `feat_3277_altfelder_entfernen` | Spec | Backend liest/serialisiert Altfelder nicht mehr |
| `feat_3122_was_steht_wo` | Spec | Epic-Spec, Nachtrag AC-38 (Trip-Teil) |
| ADR-0124 Nr. 5, Nr. 6 | ADR | `placements` mit `rows`/`outlook_reports`; ersetzt `show_outlook`, `multi_day_trend_reports` |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | Modul | Live-Schreibstelle bei Trip-Anlage, schreibt `placements` (Vorbild) |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts` | Modul | Live-Pfad Kanal-Stil, ruft `kanalStilNutzlast` |
| `internal/handler/config_merge.go` | Go | Flaches Merge: Altschlüssel nicht leer senden |
| Issues #3297, #3020, #3298, #3301, #3351 | Issues | Paket / Folgeschritte |

## Scope

### Entscheidung Paket

#3297 und #3020 (Rückbau WeatherMetricsTab) laufen in EINEM Durchlauf. Der frühere Befund in #3020 „nicht tot“ ist überholt: `WetterMetrikenVersandPanel` ist in keiner Produktionsdatei mehr gemountet. Abschluss schließt beide Issues.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | DELETE | toter Alt-Editor (Nachweis: einziger Mount im Panel) |
| `frontend/src/lib/components/shared/WetterMetrikenVersandPanel.svelte` | DELETE | von keiner Produktionsdatei gemountet |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | DELETE | nur aus dem Panel |
| `frontend/src/lib/components/shared/VersandTab.svelte` | DELETE | nur Panel und BriefingScheduleTab |
| `frontend/src/lib/components/shared/MailInhaltCard.svelte` | DELETE | nur aus WeatherMetricsTab; `show_outlook`-Durchreichen |
| `frontend/src/lib/components/shared/OutlookLayoutControls.svelte` | DELETE | nur aus WeatherMetricsTab; schreibt `outlook_metrics`/`_formats` |
| `frontend/src/lib/components/shared/weather-metrics-tab/{channelMetricLayouts,weatherMetricsSavePayload,weatherMetricsTabSections}.ts` | DELETE | nur WeatherMetricsTab-Kette (Grep-Gate) |
| `…/weather-metrics-tab/{WeatherV2Reihenfolge.svelte,kuerzelLegende.ts,kuerzelMarken.ts,nurEinBericht.ts,compareAggregationGrouping.ts}` | DELETE nur ohne Rest-Referenz | Grep je Datei, sonst bleibt sie |
| `frontend/src/lib/components/organisms/index.ts`, `trip-detail/index.ts` | MODIFY | Barrel-Exports gelöschter Dateien entfernen |
| `frontend/src/lib/utils/cockpitHelpers568.ts` | MODIFY | `hasLayout` aus `display_config.placements.rows` (nicht leer); Kommentar nachziehen |
| `frontend/src/lib/types.ts` | MODIFY | `placements?: { rows?: …; outlook_reports?: string[] }` in `DisplayConfig`; `show_outlook`, `multi_day_trend_reports` aus `ReportConfig` |
| `frontend/src/lib/components/shared/mailInhaltZustand.ts`, `mailInhaltKonstanten.ts` | MODIFY | `show_outlook` entfernen |
| `frontend/src/lib/components/shared/versand-tab/reportConfigPayload.ts` | MODIFY | `ausblickReports`, `ausblickVorbelegung`, Trend im Schedule entfernen |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | MODIFY | `ergaenzeVersandStandard`/`ergaenzeStandardwerteReportConfig` ohne Vorbelegung und ohne `show_outlook` |
| `frontend/src/lib/components/shared/zustellung-tab/kanalStilSpeicherung.ts` | MODIFY | `KanalStilStand` auf `{ stil }`; Trend-Felder und -Lesung raus; `kanalStilStart` (ohne Produktions-Aufrufer) entfällt |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts` | MODIFY | Aufruf ohne Trend-Argumente |
| `frontend/src/lib/components/shared/pickEigenfelder.ts` | MODIFY | `multi_day_trend_*`, `show_outlook` aus Whitelists (Rest = #3298) |
| Kommentar-Verweise: `alarme-tab/alarmeDeliveryPayload.ts`, `CompareTabs.svelte`, `ZustellungTab.svelte`, `CompareNewEditor.svelte`, `app.css`, `utils/rightColumn.ts`, `utils/vorlageSpeichernKarte.ts`, `VorlageKarte.svelte`, `edit/weatherSummary.ts` | MODIFY | nur Kommentare nachziehen |
| `frontend/src/lib/issue_568_home_redesign.test.ts` | MODIFY | Home-Checkliste auf `placements.rows` (erst rot) |
| `frontend/src/lib/components/trip-new/__tests__/trip_pfad_ohne_altfelder_3297.test.ts` | CREATE | Nutzlast-Test Trip anlegen/speichern ohne Altschlüssel |
| `frontend/src/lib/__tests__/trip_pfad_altfeld_loeschnachweis_3297.test.ts` | CREATE | Lösch-/Sperrnachweis (`# doc-compliance-test`) |
| `frontend/e2e/feat-3297-trip-ohne-altfelder.spec.ts` | CREATE | Request-Body ohne Altschlüssel (Anlegen/Speichern), Home-Haken „Layout“ |
| Tests der gelöschten Kette (Zuordnung siehe unten) | DELETE/MODIFY | nicht still löschen |
| Playwright-Specs mit Altfeld-Seeds (`trip-anlegen-zustellung-3332`, `hub-wetter-metriken-speichert-selbst`, `hub-versand-speichert-selbst`, `editor-gleich-gespeichert.staging.spec`, `trip-outlook-metric-selection.staging.setup`, `was-steht-wo-karte`, `issue-619-mail-elements-ui`, `issue-723-email-tab-eindampfen`) | MODIFY/DELETE | Seeds auf `placements`; reine Alt-Oberfläche begründet ersetzen |
| `docs/specs/modules/feat_3122_was_steht_wo.md` | MODIFY | Nachtrag AC-38: Trip-Teil erledigt |

### Test-Zuordnung (Löschen nur mit Begründung)

- **Löschen (testet nur den gelöschten Baum):** Tests, die ausschließlich `WeatherMetricsTab`, `WetterMetrikenVersandPanel`, `BriefingScheduleTab`, `VersandTab`, `MailInhaltCard`, `OutlookLayoutControls` oder die gelöschten Hilfsdateien importieren oder nachbauen (u. a. `shared/__tests__/{channelMetricLayouts, channelPayloadAllChannels, mail_inhalt_card*, ausblick_ein_name_3155, outlook_restore_*, outlook_erbt_*, weatherMetricsTabSharing, wetter_metriken_versand_panel_*, versandVergleichPruefstand}`, `weather-metrics-tab/__tests__/{lade_kanal_layouts_aus_trip, speichern_*, _editor_kette, f006_*}`). Je gelöschter Datei steht die zugehörige gelöschte Produktionsdatei im Commit-Text.
- **Umstellen (testet Live-Funktion):** `reportConfigPayload`, `mergeReportConfig`, `kanalStilSpeicherung`, `ac26_*`, `p12_*`, `tripNewLogic`, `pick_eigenfelder_kernregel`, `trip_reiter_roundtrip_jedes_feld`, `fakeTripServerGoMerge`, `standardwerte_payload_paritaet_trip`, `issue_568_home_redesign`, Trip-Anlegen-Tests (`trip_anlegen_zustellung_*_3332`). Altfeld-Erwartung wird durch „Schlüssel fehlt“ bzw. `placements` ersetzt.
- **Grenzfall:** Ein Test mit gemischtem Inhalt (toter Baum und Live-Funktion) wird auf den Live-Teil gekürzt, nicht gelöscht.

### Estimated Changes

- Files: ca. 25 Produktionsdateien (9 bis 14 gelöscht, ca. 11 geändert, Rest Kommentare), 40 bis 60 Testdateien gelöscht oder umgestellt, 3 neu
- LoC: neuer Produktionscode unter +120, netto ca. -4000 bis -5000 (überwiegend reine Löschzeilen; LoC-Gate: Löschzeilen zählen nicht gegen das Limit)

### Nicht in dieser Spec

- Altfeld-Typen in `types.ts` außer der `placements`-Ergänzung und den hier erledigten Schlüsseln, die Restliste in `pickEigenfelder.ts` (`channel_layouts`, `outlook_metrics`, `outlook_metric_formats`) und die Frontend-Textscan-Sperre (#3298).
- Ortsvergleich-Anlege-Karte „Layout je Kanal“ (#3301); der `WeatherMetricsTab`-Anteil von #3301 entfällt mit diesem Paket.
- Datenlauf auf Bestandsdaten (#3351).

## Implementation Details

**Schritt 1, Grep-Gate vor jeder Löschung:** Für jede Datei der Löschliste wird per Grep über `frontend/src` (ohne Tests und ohne Kommentare) belegt, dass kein Produktions-Import und kein dynamischer Import besteht. Bleibt eine Referenz, wird die Datei schlank umgeschnitten statt gelöscht. `outlookFriendlyCapability.ts`, `compareMetricSelection.ts`, `compareMetricOrder.ts`, `compareChannelMetricLayouts.ts`, `weatherMetricsCompareSave.ts` und `SavePresetDialog.svelte` bleiben (Vergleich/Vorlagen, Rest #3298/#3301).

**Schritt 2, Live-Schreibstellen im Trip:** `tripNewLogic.ts` belegt `multi_day_trend_reports` und `show_outlook` nicht mehr vor; `reportConfigPayload.ts` schreibt keinen Trend; `kanalStilSpeicherung.ts` kennt keine Trend-Felder mehr, `tripNutzlast` schreibt nur `telegram_style`. Der Trend-Schalter war seit #3154 unsichtbar und wird ersatzlos entfernt (ADR-0124 Nr. 6). Das Frontend schreibt kein Ersatz-`outlook_reports`; die Erst-Tabelle entsteht über die Karte (`placements: karte.placements`) bzw. das Backend.

**Schritt 3, Home-Anzeige:** `hasLayout = (display_config.placements?.rows?.length ?? 0) > 0`. `preset_name` (Vorlagenname) zählt nicht mehr. Bestandstrips tragen `rows` (Angabe #3277: alle zehn Produktions-Abos mit Altfeldern haben `rows`), die Anzeige bleibt für sie gleich. Ein Trip, der nur Altfelder und keine `rows` trägt, zeigt „offen“.

**Schritt 4, Löschen:** Nach Schritt 2 und 3 wird der tote Baum nach Grep-Gate gelöscht, danach Barrels und Kommentare. Zuletzt Tests nach Zuordnung oben.

**Schritt 5, Nachweis:** Nutzlast-Test über alle Live-Trip-Speicherwege (Anlage normal, Anlage „Mit Standardwerten“, Reiter-PUTs Wetter/Zustellung/Alarme) gegen den Go-Merge-Fake: kein Altschlüssel im Body, auch nicht leer; Bestandswerte bleiben nach Merge stehen (Vorbild `compare/feat3276_vergleich_ohne_altfelder.test.ts`). Offene Prüfung: setzt das Backend bei Anlage ohne Karten-Stand eine Erst-`placements`? Falls nein, bleibt der Home-Haken „offen“ bis zur ersten Karten-Speicherung (kein Ausfall); der Test belegt das Verhalten.

## Expected Behavior

- **Input:** Trip anlegen (normal und mit Standardwerten), Trip-Reiter speichern, Home-Seite mit Trips.
- **Output:** Kein Request-Body enthält die sechs Altschlüssel. Home zeigt „Layout konfiguriert“ genau für Trips mit nicht leeren `placements.rows`.
- **Side effects:** Keine sichtbare Änderung in Editor, Mail oder Kanälen. Der Frontend-Bundle wird kleiner. Gespeicherte Altwerte bleiben bis zum Datenlauf (#3351) wirkungslos auf der Platte.

## Acceptance Criteria

- **AC-1:** Given ein neuer Trip wird im Anlegen-Dialog angelegt / When der Anlege-Aufruf an die API gesendet wird / Then enthält der Request-Body keinen der Schlüssel `channel_layouts`, `channel_layouts_per_report`, `outlook_metrics`, `outlook_metric_formats`, `show_outlook`, `multi_day_trend_reports` (weder gefüllt noch leer).
  - Test: `trip_pfad_ohne_altfelder_3297.test.ts` (node --test) baut den Anlege-Body über die echte Logik (`ergaenzeVersandStandard`, `ergaenzeStandardwerteReportConfig`) und prüft die Abwesenheit rekursiv; E2E `feat-3297-trip-ohne-altfelder.spec.ts` fängt den echten POST-Body ab.

- **AC-2:** Given ein neuer Trip wird mit der Option „Mit Standardwerten“ angelegt / When der Anlege-Aufruf gesendet wird / Then fehlen auch hier alle sechs Altschlüssel, und die Tabelle `placements` wird wie bisher aus der Karte mitgegeben.
  - Test: Nutzlast-Test für den Standardwerte-Pfad (node --test), plus Abgleich mit `standardwerte_payload_paritaet_trip`; E2E prüft den POST-Body.

- **AC-3:** Given ein bestehender Trip mit Altfeldern in der Datei / When der Nutzer im Wetter-, Zustellungs- oder Alarme-Reiter etwas ändert und speichert / Then enthält der Speicher-Request keinen Altschlüssel, und alle bestehenden übrigen Felder bleiben nach dem Go-Merge erhalten.
  - Test: Nutzlast-Test mit `fakeTripServerGoMerge` über alle Reiter-PUTs (Round-Trip: Bestand vorher/nachher ohne Datenverlust); E2E speichert einen Reiter und prüft den PUT-Body.

- **AC-4:** Given der Kanal-Stil eines Trips wird gespeichert / When `kanalStilNutzlast` den Body baut / Then enthält er nur `telegram_style` und keinerlei Trend-Felder (`multi_day_trend_morning`, `multi_day_trend_evening`, `multi_day_trend_reports`).
  - Test: `kanalStilSpeicherung.test.ts` und `wasStehtWoSpeicherung`-Test (node --test) auf den gebauten Body; `kanalStilStart` ist nicht mehr exportiert.

- **AC-5:** Given Trips mit und ohne nicht leere `display_config.placements.rows` auf der Home-Seite / When die Checkliste „Layout konfiguriert“ berechnet wird / Then gilt der Schritt nur bei nicht leeren `rows` als erledigt; ein Trip mit nur `channel_layouts`, nur `preset_name` oder leeren `rows` bleibt offen, und für Bestandstrips mit `rows` ändert sich die Anzeige nicht.
  - Test: `issue_568_home_redesign.test.ts` (node --test) mit vier Konstellationen (erst rot gegen den alten Stand); E2E: Bestandstrip mit Tabelle zeigt auf Home den Haken „Layout“.

- **AC-6:** Given der Typ `DisplayConfig` / When ein Trip mit `placements` (`rows`, `outlook_reports`) typisiert wird / Then ist `placements` ein bekanntes optionales Feld, `ReportConfig` kennt `show_outlook` und `multi_day_trend_reports` nicht mehr, und `svelte-check` meldet keinen Fehler.
  - Test: `svelte-check` grün; node-Test, der ein Trip-Objekt mit `placements` durch `hasLayout` schickt (Typ-Verwendung im Verhaltenstest).

- **AC-7:** Given die Löschliste (`WeatherMetricsTab`, `WetterMetrikenVersandPanel`, `BriefingScheduleTab`, `VersandTab`, `MailInhaltCard`, `OutlookLayoutControls` und nur von ihnen genutzte Helfer) / When der Rückbau abgeschlossen ist / Then existieren diese Dateien nicht mehr, keine Produktionsdatei importiert sie (auch nicht über Barrels), und noch benutzte Vergleich-Hilfen sind erhalten.
  - Test: `trip_pfad_altfeld_loeschnachweis_3297.test.ts` (`# doc-compliance-test`: Lösch-/Sperrnachweis) prüft Nichtexistenz und Import-Freiheit über `frontend/src`; `vite build` und `svelte-check` laufen ohne unaufgelöste Importe.

- **AC-8:** Given der Frontend-Quelltext des Trip-Pfads / When nach den Schlüsseln `show_outlook` und `multi_day_trend_reports` in Produktionsdateien gesucht wird / Then gibt es keinen Treffer mehr (Typen, Zustand, Konstanten, Whitelists, Payload-Bau), und die Whitelists in `pickEigenfelder.ts` führen sie nicht.
  - Test: Scan-Test (`# doc-compliance-test`) im Löschnachweis nur für diese zwei Schlüssel; `pick_eigenfelder_kernregel.test.ts` grün auf der gekürzten Liste. Die Sperre für die übrigen Schlüssel liefert #3298.

- **AC-9:** Given der Nutzer öffnet Trip-Detail (Reiter Wetter, Zustellung, Alarme) und Trip anlegen / When er den Ablauf wie bisher bedient (Karte „Was steht wo“, Haken, Speichern) / Then sieht und bedient er dieselben Flächen wie vor dem Rückbau, und die Werte werden korrekt gespeichert und wieder geladen.
  - Test: Playwright-E2E (`feat-3297-trip-ohne-altfelder.spec.ts` sowie umgestellte `was-steht-wo-karte.spec.ts`, `trip-anlegen-zustellung-3332.spec.ts`) gegen Staging: Trip anlegen, Reiter ändern, speichern, neu laden, Werte stehen.

- **AC-10:** Given Tests, die bisher Altfelder als Fixture oder den gelöschten Baum prüften / When der Rückbau abgeschlossen ist / Then ist jeder Test entweder auf `placements` bzw. „Schlüssel fehlt“ umgestellt oder gelöscht, weil seine getestete Produktionsdatei gelöscht wurde, und die Kern-Schicht (Frontend `node --test`, `svelte-check`, Playwright-Kern) ist grün.
  - Test: Diffstatistik der Validierung ordnet jede gelöschte Testdatei einer gelöschten Produktionsdatei zu; die Zuordnung steht im Abschnitt „Test-Zuordnung“ und im Commit-Text; Läufe der betroffenen Testdateien einzeln benannt grün.

## Definition of Done

- AC-1 bis AC-10 durch Kern-Tests ohne Mock grün (`node --test` benannte Dateien, `svelte-check`, `vite build`).
- Nutzlast-Test beweist: kein Altschlüssel in Anlage-POST (normal und Standardwerte) und Reiter-PUTs, auch nicht leer.
- Grep-Gate je gelöschter Datei dokumentiert (Produktions-Importe: null); Barrels bereinigt.
- Test-Zuordnung eingehalten, keine Löschung ohne gelöschte Produktionsdatei.
- Staging: `/e2e-verify` mit Request-Body-Prüfung (Trip anlegen, Trip speichern) und Home-Haken „Layout“ bei Bestandstrip grün.
- Live auf Produktion, Selftest Exit 0; danach #3297 und #3020 schließen. Epic #3122 nicht schließen. Keine Änderung an Gate-Konfiguration.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Trip-Anlage normal WHEN Anlege-Body gebaut THEN keiner der sechs Altschlüssel, auch nicht leer (AC-1)
- [ ] Test 2: GIVEN Anlage „Mit Standardwerten“ WHEN Body gebaut THEN ohne Altschlüssel, mit `placements` aus der Karte (AC-2)
- [ ] Test 3: GIVEN Bestandstrip mit Altfeldern WHEN Reiter-PUT über Go-Merge-Fake THEN kein Altschlüssel im Body, Bestand sonst erhalten (AC-3)
- [ ] Test 4: GIVEN Kanal-Stil speichern WHEN Nutzlast gebaut THEN nur `telegram_style`, keine Trend-Felder (AC-4)
- [ ] Test 5: GIVEN vier Trip-Konstellationen WHEN `hasLayout` THEN nur nicht leere `placements.rows` zählt (AC-5)
- [ ] Test 6: GIVEN Trip mit `placements` WHEN typisiert und geprüft THEN `svelte-check` grün (AC-6)
- [ ] Test 7: GIVEN Löschliste WHEN Löschnachweis THEN Dateien fehlen, keine Importe (AC-7, `# doc-compliance-test`)
- [ ] Test 8: GIVEN Produktionscode WHEN Scan auf `show_outlook`/`multi_day_trend_reports` THEN null Treffer (AC-8, `# doc-compliance-test`)
- [ ] Test 9: GIVEN Staging WHEN Trip anlegen und Reiter speichern (E2E) THEN gleiche Flächen, Werte bleiben, Body ohne Altschlüssel (AC-9)
- [ ] Test 10: GIVEN umgestellte Tests WHEN benannte Testdateien laufen THEN grün, Zuordnung vollständig (AC-10)

Test-Politik: kein Mock-Theater, Frontend-Unit mit `node --test`, Playwright-E2E wo sichtbar. Dateiinhalt-Checks nur für die Lösch-/Sperrnachweise (`# doc-compliance-test`). Die Live-Schicht läuft in `/e2e-verify`.

## Known Limitations

- Trips, die nur Altfelder und keine `placements.rows` tragen, zeigen auf Home „Layout“ als offen (laut Issue und ADR-0124 Nr. 5 gewollt; in Produktion betrifft das keinen Trip).
- Altfeld-Typen und die übrigen `pickEigenfelder`-Einträge bleiben bis #3298; die volle Frontend-Sperre kommt ebenfalls dort.
- Bestandsdaten mit Altfeldern bleiben bis zum Datenlauf (#3351) auf der Platte, wirkungslos.
- Merge-Konflikte mit #3298/#3301 möglich; Reihenfolge: #3297 zuerst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0124 Nr. 5 und Nr. 6)
- **Rationale:** ADR-0124 hat entschieden, dass `placements` die einzige Quelle ist und `outlook_reports` `show_outlook` und `multi_day_trend_reports` ersetzt. Dieses Paket vollzieht den Frontend-Rückbau ohne Verhaltensänderung und widerspricht keiner früheren Entscheidung; das Löschen des nicht eingebundenen Alt-Editors ist eine Umsetzungsentscheidung, kein Architekturwechsel.

## Changelog

- 2026-11-25: Initial spec created (B6b-3, Issues #3297 und #3020 als Paket, Epic #3122).
