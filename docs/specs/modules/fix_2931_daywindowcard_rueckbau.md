---
entity_id: fix_2931_daywindowcard_rueckbau
type: refactor
created: 2026-11-15
updated: 2026-11-15
status: draft
version: "1.0"
workflow: fix-2931-daywindowcard-rueckbau
tags: [frontend, rueckbau, adr-0112, wetter-metriken]
---

# Rückbau Tagesfenster-Abschnitt und DayWindowCard aus WeatherMetricsTab (#2931)

## Approval

- [ ] Approved

## Purpose

Der alte Baustein `DayWindowCard` und der zugehörige Abschnitt „Tagesfenster" in `WeatherMetricsTab` werden in Produktion nie mehr angezeigt, weil die Tagesfenster-Bedienung seit #2913 Scheibe c über die neue Karte im Wetter-Reiter läuft. Der tote Code wird gelöscht (ADR-0112: alte Bausteine löschen) und die BESTAND-Ratsche gesenkt; für Nutzer ändert sich nichts.

## Source

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
- **Identifier:** Abschnitt `tagesfenster` (zwei Blöcke, Trip und Vergleich), Prop `onDayWindowChange` samt `$effect`; Baustein `weather-metrics-tab/DayWindowCard.svelte`

Schicht: ausschließlich Frontend (`frontend/src/...`) plus Testdaten/Doku unter `tests/` und `docs/`. Keine Go- oder Python-Core-Änderung.

Querschnitts-Prüfpunkte: Trip/Ortsvergleich-Teilung bleibt gewahrt (der Abschnitt fällt in beiden Kontexten gleichermaßen weg, kein neuer Baustein). Es werden keine Nutzerdaten bewegt, die Speicherpfade bleiben unverändert. Briefing- und Alarm-Inhalt sowie die vier Kanäle sind nicht betroffen.

## Estimated Scope

- **LoC:** +~30 / -~450 (ohne neu erzeugte Goldens)
- **Files:** ~22 (3 gelöscht, 12 Goldens neu erzeugt)
- **Effort:** low (Risiko niedrig: nur in Produktion nie gerenderter Code)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherMetricsTab.svelte` | component | Einziger Verbraucher von `DayWindowCard`; bleibt bestehen (lebt über Reiter Zustellung) |
| `organisms/wetter-tab/AnpassenKarte` + `tagesfensterEingabe.ts` | component | Neue, aktive Tagesfenster-Bedienung (zwei Uhrzeitfelder); darf nicht berührt werden |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | module | Vergleichs-Speicherpfad (Read-Modify-Write), nutzt Wertprops `dayWindowStartHour/EndHour`; bleibt |
| `TripNewEditor.svelte` (`handleDayWindowChange`) | component | Trip-Tagesfenster-Speicherung über WetterTab; bleibt |
| `bausteine_waechter_regeln.ts` | test-config | BESTAND-Ratsche, Obergrenze 199 auf 198 |
| i18n-Kataloge `de/en/wertebereiche.json`, `f5KatalogAnker.ts` | data | Schlüssel `wertebereiche.tagesfenster.*` werden gestrichen |
| `docs/context/einstellungen_neu/elementliste.json` | data | 4 Einträge auf `wetter.anpassen.tagesfenster` umstellen |
| F5-Goldens `tests/golden/f5_wertebereiche/*` | test-data | Neu erzeugen, nur `dwc`-Blöcke fallen weg |
| Folge-Issue #3020 | issue | Abbau von `WeatherMetricsTab` selbst (Sub-Issue von #2913) |

## Implementation Details

Ausgangslage (Analyse in `docs/context/fix-2931-daywindowcard-rueckbau.md`): Alle produktiven Einbindungen von `WetterMetrikenVersandPanel` setzen `bereich="zustellung"`; der Abschnitt `tagesfenster` ist dort nicht enthalten. Gerendert wurde er nur im Standardbereich `alles`, den ausschließlich Tests und Prüfstände nutzen.

Vorgehen:

1. TDD RED: Wächter-Test (Existenz DayWindowCard, Import, Abschnittsliste, Prop, Katalog, BESTAND) plus SSR-Render von `WeatherMetricsTab` mit `bereich='alles'` in beiden Kontexten ohne `weather-metrics-tagesfenster` und ohne `dwc-`.
2. `DayWindowCard.svelte`, `day_window_card.test.ts` und `weatherMetricsTabDayWindowSave.test.ts` löschen.
3. `WeatherMetricsTab.svelte`: Import, Vergleichs-Block und Trip-Block des Abschnitts entfernen; Prop `onDayWindowChange`, Destrukturierung und zugehörigen `$effect` entfernen. Wertprops `dayWindowStartHour/EndHour`, Handler `onDayWindowStartHourChange/EndHourChange` und alle `reportConfig.day_window_*`-Speicherpfade bleiben unverändert.
4. `weatherMetricsTabSections.ts`: `'tagesfenster'` samt Kommentar streichen.
5. BESTAND-Eintrag streichen, `BESTAND_OBERGRENZE` auf 198.
6. i18n: 5 Schlüssel `wertebereiche.tagesfenster.*` (titel, untertitel, von, bis, ueber_mitternacht) in DE und EN streichen, `f5KatalogAnker.ts` mitziehen; Elementliste 4 Einträge auf `wetter.anpassen.tagesfenster` (Einträge, IDs, `text_en` unverändert).
7. Prüfstand `f5Pruefstand.ts` und `wertebereiche_sprache.test.ts` anpassen (DayWindowCard-Einbettung und zwei Messaufbau-Strings raus); Goldens DE und EN mit `GZ_GOLDEN_SCHREIBEN=de` bzw. `=en` neu erzeugen und den Diff prüfen: nur wegfallende `dwc`-Blöcke. Das ist die bewusste, in Known Limitations begründete Ausnahme von der Regel „Goldens DE nie neu schreiben“; jede andere Abweichung im Diff bricht ab.
8. Tests mit Abschnitts- oder Prop-Listen nachziehen (siehe Scope), Python-Kommentar in `test_onset_respects_configured_day_window.py` auf AnpassenKarte umstellen.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/weather-metrics-tab/DayWindowCard.svelte` | DELETE | toter Baustein |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/day_window_card.test.ts` | DELETE | Test des toten Bausteins |
| `frontend/src/lib/components/shared/__tests__/weatherMetricsTabDayWindowSave.test.ts` | DELETE | prüft nur den toten Trip-Block |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Import, beide Abschnitts-Blöcke, `onDayWindowChange` samt `$effect` raus |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts` | MODIFY | `'tagesfenster'` streichen |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | MODIFY | BESTAND-Eintrag raus, Obergrenze 199 auf 198 |
| `frontend/src/lib/i18n/messages/de/wertebereiche.json`, `.../en/wertebereiche.json` | MODIFY | 5 Schlüssel raus |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/f5KatalogAnker.ts` | MODIFY | 5 Anker raus |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/f5Pruefstand.ts` | MODIFY | DayWindowCard-Import und Zeile in `bausteineRendern` raus |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts` | MODIFY | 2 Strings aus Messaufbau |
| `tests/golden/f5_wertebereiche/*.{de,en}.html` | MODIFY | neu erzeugt (12 Dateien), nur `dwc`-Blöcke entfallen |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | 4x `i18n_key` auf `wetter.anpassen.tagesfenster` |
| `weatherMetricsTabSharing.test.ts`, `compareMetricOrder.test.ts`, `s3a2794_bereich_filter.test.ts`, `s3a2794_zustellung_ziel_und_bereich.test.ts` | MODIFY | `'tagesfenster'` aus Abschnittslisten |
| `s3a2794_teil3_keine_nativen_controls.test.ts` | MODIFY | DayWindowCard aus Prüfliste |
| `weather_metrics_tab_create_mode_callback.test.ts` | MODIFY | #1775-Block und Trip-DayWindowCard-Test raus, Abwesenheit sichern |
| `compare_wetter_metriken_wertprops.test.ts`, `speicher_anzeige_zwischenstand_wetter_und_briefing.test.ts`, `wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte.test.ts` | MODIFY | `onDayWindowChange` aus Prop-Listen |
| `tests/tdd/test_onset_respects_configured_day_window.py` | MODIFY | nur Kommentar |
| neuer Wächter-Test (Frontend, Kern-Schicht) | CREATE | Abwesenheit von Baustein, Abschnitt, Prop, Schlüsseln, BESTAND-Eintrag |

### Estimated Changes

- Files: ~22
- LoC: +~30 / -~450

## Expected Behavior

- **Input:** Nutzer öffnen die Reiter Zustellung und Wetter in Trip und Ortsvergleich.
- **Output:** Aussehen und Bedienung identisch zu vorher; das Tagesfenster wird weiter über die zwei Uhrzeitfelder im Wetter-Reiter eingestellt.
- **Side effects:** Keine. Keine Datenänderung, kein Feldverlust beim Speichern.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (Rückbau-Wächter, als `# doc-compliance-test` gekennzeichnet; Verhaltensnachweis ist Test 2): GIVEN das Repo WHEN der Wächter läuft THEN existiert `DayWindowCard.svelte` nicht, `WeatherMetricsTab` importiert ihn nicht und `weatherMetricsTabSections` enthält kein `'tagesfenster'`.
- [ ] Test 2: GIVEN `WeatherMetricsTab` wird mit `bereich='alles'` in Kontext Trip und Vergleich gerendert (SSR) WHEN das Markup geprüft wird THEN enthält es weder `weather-metrics-tagesfenster` noch `dwc-`.
- [ ] Test 3 (Rückbau-Wächter, `# doc-compliance-test`; Verhaltensnachweis der Speicherpfade ist Test 6): GIVEN `WeatherMetricsTab` WHEN die Props geprüft werden THEN gibt es keine Prop `onDayWindowChange`, aber weiterhin `dayWindowStartHour/EndHour` samt Handlern.
- [ ] Test 4 (bestehende Katalog-/Elementlisten-Wächter, keine neuen Dateiinhalt-Checks): GIVEN die Kataloge DE und EN WHEN Parität und Anker geprüft werden THEN fehlen `wertebereiche.tagesfenster.*` in beiden, Parität bleibt grün, die Elementliste verweist auf `wetter.anpassen.tagesfenster`.
- [ ] Test 5 (bestehende Ratsche `bausteine_waechter`, keine neuen Dateiinhalt-Checks): GIVEN die BESTAND-Ratsche WHEN sie läuft THEN ist der Eintrag gestrichen und `BESTAND_OBERGRENZE` ist 198.
- [ ] Test 6 (Erhaltung): GIVEN ein Vergleich mit gesetztem Tagesfenster WHEN die Wetter-Metriken gespeichert werden THEN bleiben `day_window_*`-Werte erhalten (bestehende Tests `weatherMetricsCompareSave`, `trip_new_editor_weather_metrics_wiring`, `wetter_tab_scheibe_c` unverändert grün).
- [ ] Test 7: GIVEN die neu erzeugten F5-Goldens DE+EN WHEN `wertebereiche_sprache.test.ts` läuft THEN ist es grün, und der Golden-Diff zeigt ausschließlich entfallene `dwc`-Blöcke.

## Definition of Done

Fertig ist der Rückbau, wenn die alte Tagesfenster-Karte samt Test gelöscht ist, die Wetter-Metriken-Ansicht in keinem Kontext und Bereich mehr einen Tagesfenster-Abschnitt zeigt, die tote Prop `onDayWindowChange` entfernt ist, Tagesfenster-Werte von Trip und Ortsvergleich beim Speichern unverändert erhalten bleiben, Ratsche (Obergrenze 198), Kataloge, Elementliste und F5-Goldens nachgezogen und grün sind und die Reiter Zustellung und Wetter auf Staging für Trip und Ortsvergleich vorher und nachher gleich aussehen (AC-1 bis AC-8). Der Abbau des übrigen `WeatherMetricsTab` bleibt im Folge-Issue #3020.

## Acceptance Criteria

- **AC-1:** Given der alte Baustein „Tagesfenster-Karte" samt eigenem Test existiert im Code / When der Rückbau abgeschlossen ist / Then sind beide Dateien gelöscht und kein anderer Code bindet sie noch ein.
  - Test: Wächter-Test prüft Nicht-Existenz und fehlenden Import; Frontend-Build und Kern-Tests bleiben grün.

- **AC-2:** Given ein Nutzer öffnet die Wetter-Metriken-Ansicht im Trip oder im Ortsvergleich (in jedem Bereich, auch dem Standardbereich „alles") / When die Seite dargestellt wird / Then erscheint dort kein eigener Tagesfenster-Abschnitt mehr (kein `weather-metrics-tagesfenster`, kein `dwc`-Markup) und die Abschnittsliste enthält „tagesfenster" nicht mehr.
  - Test: Render-Test von `WeatherMetricsTab` in beiden Kontexten mit Bereich „alles" findet weder Testkennung noch `dwc-`-Markup.

- **AC-3:** Given die nie von außen befüllte Prop `onDayWindowChange` samt zugehörigem Effekt / When der Rückbau abgeschlossen ist / Then sind beide entfernt, die Wertprops `dayWindowStartHour/EndHour`, ihre Handler und die `reportConfig.day_window_*`-Speicherpfade sind unverändert vorhanden.
  - Test: Prop-Test bestätigt Abwesenheit von `onDayWindowChange` und Anwesenheit der übrigen Tagesfenster-Props; bestehende Wiring-Tests bleiben unverändert grün.

- **AC-4:** Given ein Ortsvergleich mit gesetztem Tagesfenster / When der Nutzer den Vergleich speichert / Then bleibt das Tagesfenster mit denselben Werten erhalten und kein anderes gespeichertes Feld geht verloren (Read-Modify-Write); ebenso speichert das Tagesfenster eines Trips weiter über den Wetter-Reiter.
  - Test: bestehende Speicher-Tests (`weatherMetricsCompareSave`, `wetter_tab_scheibe_c`, Trip-Wiring) laufen unverändert grün; E2E `daywindow-*` unverändert grün auf Staging.

- **AC-5:** Given die Bausteine-Ratsche zählt Altlasten (BESTAND) / When der Rückbau abgeschlossen ist / Then ist der Eintrag für die Tagesfenster-Karte gestrichen und die Obergrenze von 199 auf 198 gesenkt, ohne dass die Ratsche rot wird.
  - Test: Ratschen-Test läuft grün mit Obergrenze 198; ein verwaister Eintrag würde ihn rot färben.

- **AC-6:** Given die Übersetzungskataloge Deutsch und Englisch / When der Rückbau abgeschlossen ist / Then fehlen die 5 Schlüssel `wertebereiche.tagesfenster.*` in beiden Sprachen, Katalog-Parität und Anker bleiben grün, und die 4 Einträge der Elementliste zeigen auf `wetter.anpassen.tagesfenster` mit unverändertem Text („Tagesfenster" / „Day window").
  - Test: Katalog-Paritäts-, Anker- und `elementliste_aktuell`-Test laufen grün.

- **AC-7:** Given die F5-Referenzbilder (Goldens) für Deutsch und Englisch / When sie neu erzeugt werden / Then entfallen darin ausschließlich die `dwc`-Blöcke der Tagesfenster-Karte; jede andere Abweichung gilt als Fehler.
  - Test: `wertebereiche_sprache.test.ts` vergleicht DE byte-gleich gegen die neuen Goldens; Diff-Kontrolle gegen den vorherigen Stand zeigt nur entfernte `dwc`-Blöcke.

- **AC-8:** Given ein Nutzer sieht Reiter Zustellung und Wetter (Trip und Ortsvergleich) vor und nach dem Rückbau auf Staging / When er beide Zustände vergleicht / Then sehen die Reiter gleich aus und das Tagesfenster lässt sich weiter über die zwei Uhrzeitfelder einstellen und speichern.
  - Test: Ganzseitenbilder vorher/nachher auf Staging ohne Abweichung; E2E `daywindow-schedule-control` und `daywindow-shared-both-contexts` unverändert grün.

## Known Limitations

- `WeatherMetricsTab` selbst bleibt bestehen, weil er über den Reiter Zustellung produktiv gerendert wird; sein vollständiger Abbau erfolgt im Folge-Issue #3020.
- Der Kommentar „Goldens DE nie neu schreiben" wird hier bewusst für eine gewollte Markup-Änderung genutzt; der Diff wird auf reine `dwc`-Entfernung geprüft.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0112 (bestehend, keine neue Entscheidung)
- **Rationale:** Setzt die Vorgabe „alte Bausteine löschen" um; es wird keine Entscheidung geändert, daher kein neues ADR.

## Changelog

- 2026-11-15: Initial spec created
