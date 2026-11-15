# Context: fix-2931-daywindowcard-rueckbau

## Request Summary
Issue #2931 (Nebenbefund aus #2913 Scheibe c): alte, nicht mehr sichtbare Tagesfenster-Bedienung
(`DayWindowCard`) löschen, BESTAND-Ratsche senken (ADR-0112: alte Bausteine löschen).

**Zuschnitt beim Intake (2026-11-15):** Die Issue-Annahme „WeatherMetricsTab wird nicht mehr gerendert"
ist falsch. `WeatherMetricsTab` läuft weiter über `WetterMetrikenVersandPanel bereich="zustellung"`
(TripNewEditor ×2, CompareNewEditor ×2, `ZustellungTab` → `UebergangBlock` im Hub für Trip und Vergleich).
Sicher tot ist nur der Abschnitt `tagesfenster` (nicht in `ZUSTELLUNGS_SECTIONS`, kein Mount mit
`bereich` ≠ `zustellung`). Löschen von WeatherMetricsTab selbst: Folge-Issue #3020 (Sub-Issue von #2913).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/weather-metrics-tab/DayWindowCard.svelte` | löschen (157 Z.) |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/day_window_card.test.ts` | löschen |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Import Z.122, Vergleichs-Block Z.~1591–1606, Trip-Block Z.~1787–1835 (`data-testid="weather-metrics-tagesfenster"`), toter `onDayWindowChange`-Prop + `$effect` Z.185/~733 |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts` | `'tagesfenster'` aus der Abschnittsliste streichen |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | BESTAND-Eintrag Z.596 streichen, `BESTAND_OBERGRENZE` 199 → 198 |
| `frontend/src/lib/i18n/messages/{de,en}/wertebereiche.json` | Schlüssel `wertebereiche.tagesfenster.*` nur von DayWindowCard genutzt → streichen (Katalog-Anker `f5KatalogAnker.ts` Z.66–71 mitziehen) |
| Tests, die den Abschnitt/die Karte nennen | `weatherMetricsTabDayWindowSave.test.ts` (prüft toten Trip-Block → löschen), `weather_metrics_tab_create_mode_callback.test.ts` (#1775-Block + Trip-DayWindowCard-Test), `weatherMetricsTabSharing.test.ts`, `compareMetricOrder.test.ts`, `s3a2794_bereich_filter.test.ts`, `s3a2794_zustellung_ziel_und_bereich.test.ts`, `s3a2794_teil3_keine_nativen_controls.test.ts`, `f5Pruefstand.ts` |

## Existing Patterns
- Neue Tagesfenster-Bedienung: `organisms/wetter-tab/AnpassenKarte` + `tagesfensterEingabe.ts` (zwei `UhrzeitFeld`), Scheibe c von #2913, Test `wetter_tab_scheibe_c.test.ts` prüft bereits „kein DayWindowCard".
- E2E `daywindow-schedule-control.spec.ts` / `daywindow-shared-both-contexts.spec.ts` laufen schon gegen die neue Karte — bleiben unverändert.
- BESTAND-Ratsche: verwaiste Einträge sind rot, Obergrenze nur senken.

## Dependencies
- Upstream: DayWindowCard nutzt `ui/select`, i18n `wertebereiche.tagesfenster.*`.
- Downstream: nur WeatherMetricsTab (zwei Blöcke im Abschnitt `tagesfenster`).

## Bleibt (nicht anfassen)
- Wertprops `dayWindowStartHour/EndHour` und Handler `onDayWindowStartHourChange/EndHourChange` in WeatherMetricsTab: speisen den Vergleichs-Speicher-Schnappschuss (`weatherMetricsCompareSave.ts`, Read-Modify-Write, kein Feldverlust) und den Vorlage-Anwenden-Pfad (Z.~1380). Entfernen würde Datenverlust riskieren.
- `reportConfig.day_window_*` im Trip-Speicherpfad (Z.~733 ff. außer dem toten `onDayWindowChange`-Effekt).

## Existing Specs
- `docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md` (Known Limitations → dieses Issue)
- `docs/specs/modules/compare_shared_day_window.md`, `fix_1775_tagesfenster_anlegen.md` (Altbestand der toten Karte)

## Risks & Considerations
- WeatherMetricsTab ist live (Reiter Zustellung): nur den toten Abschnitt entfernen, Speicherpfade unverändert lassen.
- `onDayWindowChange` wird von keinem Aufrufer übergeben (grep) → Effekt + Prop tot; vor dem Löschen in Analyse nochmals gegen TripNewEditor bestätigen.
- i18n-Wächter (`keine_hartkodierten_nutzertexte`, Katalog-Parität DE/EN) müssen nach dem Streichen der Schlüssel grün bleiben.
- Kein Nutzersichtbarer Unterschied erwartet → Nachweis: Ganzseitenbild Zustellungs-Reiter vorher/nachher identisch, Kern-Tests grün.

## Analysis

### Type
Feature (Rückbau/Aufräumen, ADR-0112 „alte Bausteine löschen"), kein Nutzer-sichtbarer Unterschied.

### Verifikation der Intake-Annahmen (2026-11-15, grep gegen Worktree = origin/main a0a14c27a)
- Alle produktiven Mounts von `WetterMetrikenVersandPanel` übergeben `bereich="zustellung"`
  (TripNewEditor Z.937/1200, CompareNewEditor Z.609/676, `UebergangBlock` Z.49). `tagesfenster`
  ist nicht in `ZUSTELLUNGS_SECTIONS` ⇒ beide `DayWindowCard`-Blöcke werden in Produktion nie gerendert.
  Gerendert werden sie nur im Default `bereich='alles'` — das nutzen ausschließlich Tests/Prüfstände.
- `onDayWindowChange`: kein Aufrufer übergibt die Prop; `trip_new_editor_weather_metrics_wiring.test.ts`
  sichert sogar ab, dass kein Panel sie setzt (Trip-Tagesfenster läuft über `WetterTab onAnlegeStand →
  handleDayWindowChange`). Prop + `$effect` (WeatherMetricsTab Z.185/227/726–737) sind tot.
  `handleDayWindowChange` in TripNewEditor BLEIBT (wird von WetterTab gespeist).
- i18n `wertebereiche.tagesfenster.*` (titel, untertitel, von, bis, ueber_mitternacht): einziger
  Code-Nutzer DayWindowCard. Die neue Karte nutzt `wetter.anpassen.*`.

### Neue Befunde (nicht im Intake)
1. **F5-Goldens** `tests/golden/f5_wertebereiche/*.{de,en}.html` (12 Dateien, inkl. `bausteine.*`)
   enthalten das DayWindowCard-Markup (`dwc-*`), weil `f5Pruefstand.ts` den Reiter mit `bereich='alles'`
   rendert und `bausteineRendern()` DayWindowCard einzeln einbettet (Z.91/192). Test
   `wertebereiche_sprache.test.ts` vergleicht DE byte-gleich (AC-5) und prüft in „Messaufbau" die Texte
   `'Tagesfenster'` und `'Geht über Mitternacht — endet am Folgetag.'` (Z.152).
   ⇒ Pruefstand-Import + `bausteineRendern`-Zeile entfernen, beide Strings aus der Messaufbau-Liste
   streichen, Goldens DE+EN neu erzeugen. Der Kommentar „de nie neu schreiben" ist in der Praxis
   mehrfach bei gewollten Markup-Änderungen durchbrochen worden (#2794 8909b8efb, #2400, #2881, #2371,
   #2792, #1721) — Diff muss genau die entfernten `dwc`-Blöcke zeigen, sonst nichts.
2. **Elementliste** `docs/context/einstellungen_neu/elementliste.json`: 4 Einträge (trip/orte ×
   normal/luecken, Abschnitt `anpassen`, Text „Tagesfenster") tragen `i18n_key:
   wertebereiche.tagesfenster.titel`. `elementliste_aktuell.test.ts` Z.232 verlangt, dass jeder
   Schlüssel im EN-Katalog existiert ⇒ beim Streichen des Schlüssels rot. Lösung: auf
   `wetter.anpassen.tagesfenster` umstellen (gleicher DE-/EN-Text „Tagesfenster"/„Day window", genau
   der Schlüssel, den AnpassenKarte tatsächlich rendert; `ermittleEn` liefert ihn nach dem Streichen
   über den Exakt-Index). Zahl der Einträge, IDs und `text_en` bleiben unverändert.
3. Props-Listen in Tests: `compare_wetter_metriken_wertprops.test.ts` (`UNVERAENDERTE_PROPS` +
   Prop-Objekt Z.291), `speicher_anzeige_zwischenstand_wetter_und_briefing.test.ts` Z.74,
   `wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte.test.ts` Z.102 nennen
   `onDayWindowChange` ⇒ Eintrag streichen.
4. `tests/tdd/test_onset_respects_configured_day_window.py` Z.24 und E2E-Kommentare nennen DayWindowCard
   nur im Kommentar ⇒ Kommentar-Pflege optional (Python-Docstring auf AnpassenKarte umstellen).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/weather-metrics-tab/DayWindowCard.svelte` | DELETE | toter Baustein |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/day_window_card.test.ts` | DELETE | Test des toten Bausteins |
| `frontend/src/lib/components/shared/__tests__/weatherMetricsTabDayWindowSave.test.ts` | DELETE | prüft nur den toten Trip-Block |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Import, beide `tagesfenster`-Blöcke, `onDayWindowChange` Prop/Destrukturierung/`$effect` raus; Wertprops `dayWindow*` + Handler bleiben |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts` | MODIFY | `'tagesfenster'` aus der Liste + Kommentar |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | MODIFY | BESTAND-Eintrag raus, `BESTAND_OBERGRENZE` 199→198 |
| `frontend/src/lib/i18n/messages/{de,en}/wertebereiche.json` | MODIFY | 5 Schlüssel `wertebereiche.tagesfenster.*` raus |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/f5KatalogAnker.ts` | MODIFY | 5 Anker raus |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/f5Pruefstand.ts` | MODIFY | DayWindowCard-Import + Zeile in `bausteineRendern` raus |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/wertebereiche_sprache.test.ts` | MODIFY | 2 Strings aus Messaufbau |
| `tests/golden/f5_wertebereiche/*.{de,en}.html` | MODIFY | neu erzeugt, nur `dwc`-Blöcke fallen weg |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | 4× `i18n_key` → `wetter.anpassen.tagesfenster` |
| Tests mit Abschnittslisten: `weatherMetricsTabSharing.test.ts`, `compareMetricOrder.test.ts`, `s3a2794_bereich_filter.test.ts`, `s3a2794_zustellung_ziel_und_bereich.test.ts` | MODIFY | `'tagesfenster'` streichen |
| `s3a2794_teil3_keine_nativen_controls.test.ts` | MODIFY | DayWindowCard aus der Prüfliste |
| `weather_metrics_tab_create_mode_callback.test.ts` | MODIFY | #1775-Block (onDayWindowChange) + Trip-DayWindowCard-Test raus, stattdessen Abwesenheit sichern |
| `compare_wetter_metriken_wertprops.test.ts`, `speicher_anzeige_zwischenstand_wetter_und_briefing.test.ts`, `wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte.test.ts` | MODIFY | `onDayWindowChange` aus Prop-Listen |
| `tests/tdd/test_onset_respects_configured_day_window.py` | MODIFY (Kommentar) | Verweis auf AnpassenKarte |

### Scope Assessment
- Dateien: ~22 (davon 3 DELETE, 12 Goldens generiert)
- Geschätzt LoC (Hand, ohne Goldens): +~30 / −~450 (DayWindowCard 157, zwei Testdateien ~250, WMT-Blöcke ~70)
- Risk Level: LOW — nur in Produktion nie gerenderter Code; Speicherpfade unverändert.

### Technical Approach
1. TDD RED: Wächter-Test „DayWindowCard existiert nicht, WeatherMetricsTab importiert ihn nicht,
   kein `'tagesfenster'` in `weatherMetricsTabSections` für keinen Kontext/Bereich, keine
   `onDayWindowChange`-Prop, Katalog ohne `wertebereiche.tagesfenster.*`, BESTAND ohne Eintrag".
   Verhaltensnachweis: SSR-Render (Pruefstand) von WeatherMetricsTab mit `bereich='alles'` in beiden
   Kontexten enthält kein `weather-metrics-tagesfenster`/`dwc-`.
2. GREEN: Löschen/Anpassen laut Tabelle; Goldens neu (`GZ_GOLDEN_SCHREIBEN=de` und `=en` über den
   Pruefstand-Pfad), Diff-Kontrolle: nur `dwc`-Blöcke weg.
3. Erhaltungsnachweis: bestehende Tests der Speicherpfade (`weatherMetricsCompareSave`, Vorlage-Anwenden,
   `trip_new_editor_weather_metrics_wiring`, `wetter_tab_scheibe_c`) grün; E2E `daywindow-*` unverändert grün.
4. Nachweis Nutzersicht (ADR-0112): Ganzseitenbild Reiter Zustellung + Reiter Wetter (Trip, Vergleich)
   auf Staging vorher/nachher gleich.

### Dependencies
- Upstream von DayWindowCard: `ui/select` (bleibt, weitere Nutzer), i18n.
- Downstream: nur WeatherMetricsTab; Prüfstände/Goldens F5; Elementliste (nur Schlüsselname).
- Folge: #3020 (WeatherMetricsTab ganz abbauen) baut darauf auf.

### Open Questions
- keine (reiner Rückbau ohne Produktentscheidung; Spec-Freigabe durch PO bleibt Pflicht)
