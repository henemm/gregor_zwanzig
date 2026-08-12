# Context: Tagesfenster beim Trip-Anlegen einstellbar (#1775)

## Request Summary

Der Trip-Anlege-Editor (`/trips/new`) bietet keine Bedienfläche für das Tagesfenster
(`day_window_start_hour`/`_end_hour`, Default 4/19). Seit #1584 bestimmt dieses Fenster nicht
mehr nur die Stundentabelle/Bewertung, sondern auch die Reichweite der Gefahren-Überwachung des
Zielsegments — wer die Voreinstellung stehen lässt, ist ab 19 Uhr Ortszeit ohne Überwachung, ohne
dass die Anlege-Maske das erkennen lässt. Der Ortsvergleich hat das Gegenstück im Anlege-Weg
bereits (`/compare/new`).

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1325-1347` | Rendert `DayWindowCard` für den bestehenden Trip, **explizit `!createMode`-gegated**. Kommentar 1320-1324 benennt die Lücke selbst als „Known Limitation": im `createMode` hält `TripNewEditor.svelte` eine eigene, separate `reportConfig`-Instanz — der hier lokale `reportConfig`-$state (Zeile 225, befüllt aus `trip.report_config` in einem `$effect`, Zeile 729) wäre dort wirkungslos. |
| `frontend/src/lib/components/shared/weather-metrics-tab/DayWindowCard.svelte` | Die geteilte, bereits fertige Bedienfläche (reiner Präsentations-Baustein, Props `startHour`/`endHour`/`onStartHour`/`onEndHour`, kein interner State, kein Speicherweg). Wird unverändert wiederverwendet. |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte:294-312,780,805,1016,1033` | Rückkanal-Muster für den Anlege-Modus: `handleChannelsChange` (#622) und `handleWeatherMetricsChange` (#1552) — beides separate, lokale `$state`-Variablen (`channels`, `weatherMetrics`), die **nicht** über den `reportConfig`-Umweg laufen, sondern per Callback-Prop direkt von `WeatherMetricsTab` hochgereicht werden. `EditReportConfigSection` (mode="create", Zeile 780/1016) bindet an eine eigene `reportConfig`-Instanz (Zeile 62), die 1:1 in den Payload wandert. |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts:90-101,117-149` | `CreateTripState`/`buildCreateTripPayload` — `state.reportConfig` wird 1:1 nach `trip.report_config` übernommen (Zeile 147-149). Zielort für die neuen Felder. |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts:98-99,138-139` | Vorbild Compare: `dayWindowStartHour`/`dayWindowEndHour` als eigene `$state`, Default 4/19, unbedingt in `saveNewPreset()` durchgereicht. |
| `frontend/src/lib/components/compare/compareEditorSave.ts:263-264,336-337` | Vorbild Compare Payload-Mapping: Felder liegen **top-level** im Create-Payload, nicht optional. |
| `internal/handler/trip.go:131-154` | `CreateTripHandler` — `report_config` wird bereits generisch als Map entgegengenommen und mit `store.ClampReportConfigDayWindow(trip.ReportConfig)` geklemmt (Kommentar: ausdrücklich auch für den Anlege-Wizard gedacht). **Kein Backend-Aufwand.** |
| `internal/store/slot_hour_normalization.go:97-114` | Klemm-Logik für das Trip-`report_config` (map-basiert), läuft im Create- und Update-Pfad gleich. |
| `src/app/day_window.py:16-17,40-50` | Python-seitiger Default 4/19 und `resolve_configured_window()` — liest `report_config`, unabhängig davon, ob der Trip beim Anlegen oder später bekommen hat. Kein Python-Aufwand. |

## Existing Patterns

- **Rückkanal statt Zustands-Sharing:** Ein `createMode`-Callback-Prop pro Feldgruppe
  (`onChannelsChange`, `onWeatherMetricsChange`) ist das etablierte Muster, seit #622/#1552.
  `WeatherMetricsTab` bleibt in beiden Modi read-only gegenüber dem Aufrufer-State; der Aufrufer
  (`TripNewEditor`) hält die Quelle der Wahrheit für den Anlege-Payload.
- **Reassign statt Mutation:** Jede Änderung ersetzt das Objekt (`{ ...reportConfig, feld: v }`),
  nie In-Place-Mutation — Kommentar Zeile 1327-1331 verweist auf einen früheren stillen
  Nicht-Speicher-Bug derselben Klasse (#1360-Falle) und die Adversary-Runde-3-Regression aus S1b
  (`DayWindowCard` lag außerhalb des Touch-Scope-Containers → `userTouched` blieb `false`).
- **Compare-Anlegen als Referenzimplementierung:** exakt dasselbe Problem (Tagesfenster beim
  Anlegen) ist dort bereits gelöst — `dayWindowStartHour`/`dayWindowEndHour` mit Default 4/19,
  unbedingt im Payload, dokumentiert per Test `compare_new_preset_payload.test.ts:91-109`.
- **`DayWindowCard` selbst ist bereits context-neutral** (Docstring: „OHNE Kontext-Gate, damit
  Trip UND Ortsvergleich dieselbe Bedienfläche bekommen") — die Lücke liegt ausschließlich in der
  Verdrahtung von `WeatherMetricsTab`/`TripNewEditor`, nicht im Baustein selbst.

## Dependencies

- **Upstream:** `DayWindowCard.svelte` (unverändert wiederverwendet), `clampDayWindowEndHour`
  (Mitternachts-Klemme, unverändert).
- **Downstream:** `POST /api/trips` (nimmt `report_config` bereits an, klemmt serverseitig) →
  `resolve_configured_window()` (Python) → Stundentabelle, Bewertung, **Zielsegment-Ende** (#1584).

## Existing Specs

- `docs/specs/modules/compare_shared_day_window.md` — geteiltes Tagesfenster, S1b (#1361/#1372).
  AC-4 dort beschreibt die Bedienfläche selbst; **deckt den Trip-Anlege-Pfad nicht ab** (S1b war
  vor #1584 — die Alarm-Kopplung existierte noch nicht, und `/trips/new` folgte damals einem
  anderen Editor-Paradigma).
- `docs/specs/modules/fix_1552_neuanlage_metrikauswahl.md` — direktes Formmuster für den
  Rückkanal (`onWeatherMetricsChange`), auf das sich diese Spec stützen kann.
- `docs/specs/modules/fix_1584_alarm_zeitfenster.md` — Herkunft der fachlichen Dringlichkeit.

## Risks & Considerations

- **Silent-no-save-Klasse:** S1b hatte hier vier Adversary-Runden nötig, zwei davon wegen genau
  dieser Fläche (`DayWindowCard` liegt außerhalb erwarteter Touch-Scopes / Dirty-Checks). Der
  Anlege-Pfad hat kein Dirty-Tracking (nur ein POST am Ende), das Risiko ist strukturell kleiner,
  aber die Grund-Falle (Referenz-Vergleich vs. Mutation) gilt weiter für den neuen Callback.
- **Reihenfolge des Rückkanals:** `handleChannelsChange`/`handleWeatherMetricsChange` schreiben in
  eigene, von `reportConfig` getrennte $state-Variablen. Der neue Handler muss dagegen **in**
  `reportConfig` schreiben (dasselbe Objekt, das `EditReportConfigSection` bindet), sonst würden
  zwei parallele `reportConfig`-Quellen existieren und sich beim Speichern gegenseitig
  überschreiben — die Reihenfolge von State-Updates aus verschiedenen Tabs ist bei `$state`-Reassign
  nicht racy, solange auf genau ein Objekt geschrieben wird.
- **Abgrenzung laut Issue:** #1599 (Rechenregel Obergrenze inklusiv/exklusiv) und das
  Mitternachts-Fenster beim Zielsegment (PO-Entscheidung 2026-08-08, `trip_segments.py:259-264`)
  sind **nicht** Teil dieser Scheibe — `DayWindowCard` erlaubt Mitternachts-Fenster in der UI
  bereits (Anzeige/Bewertung), das ist unverändertes Bestandsverhalten, keine neue Fläche.
- **Kein Backend-/Python-Eingriff nötig** — das Feld läuft bereits durch Create inkl. Klemmung.
  Die gesamte Änderung ist Frontend (`shared/WeatherMetricsTab.svelte`, `trip-new/TripNewEditor.svelte`,
  `trip-new/tripNewLogic.ts`) + Tests.

## Analysis

### Type

Feature (Lücke im Anlege-Pfad — kein fehlerhaftes Verhalten des bestehenden Codes, sondern eine
fehlende Bedienfläche, die im Trip-Editor bereits existiert und im Ortsvergleich-Anlegen bereits
nachgebaut wurde).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | `createMode`-Zweig für den `tagesfenster`-Block ergänzen: `DayWindowCard` auch bei `createMode=true` rendern, gebunden an den bereits vorhandenen lokalen `reportConfig`-$state (Zeile 225/717/729 — im `createMode` befüllt aus `stubTrip.report_config` = `{}`, da `stubTrip` keins trägt). Neuer Callback-Prop `onDayWindowChange?: (w: { day_window_start_hour: number; day_window_end_hour: number }) => void`, analog `onChannelsChange`/`onWeatherMetricsChange`, gefeuert bei jeder Änderung (gleiches Reassign-Muster wie Zeile 1336/1341). |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Neuer Handler `handleDayWindowChange` (analog `handleChannelsChange`, Zeile 294-297) merged die zwei Felder **in** die eigene `reportConfig`-$state (Zeile 62) — dasselbe Objekt, das `EditReportConfigSection` bindet und das 1:1 in den Payload wandert. Neue Prop-Verdrahtung an beiden `WeatherMetricsTab`-Einbindungen (Zeile 805, 1033). |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | KEINE ÄNDERUNG NÖTIG | `CreateTripState.reportConfig` und `buildCreateTripPayload` reichen `report_config` bereits 1:1 durch (Zeile 147-149) — die neuen Felder laufen ohne Anpassung mit. |
| `frontend/src/lib/components/trip-new/__tests__/trip_new_editor_weather_metrics_wiring.test.ts` | MODIFY | Bestehendes Vorbild für den `onWeatherMetricsChange`-Rückkanal — Testfall für `onDayWindowChange` ergänzen (Muster übertragen). |
| `frontend/src/lib/components/shared/__tests__/weather_metrics_tab_create_mode_callback.test.ts` | MODIFY | Prüft die Callback-Verdrahtung im `createMode` — Fall für Tagesfenster ergänzen. |
| `frontend/e2e/daywindow-shared-both-contexts.spec.ts` | MODIFY (ggf.) | Bereits vorhandenes Playwright-Vorbild für „geteiltes Tagesfenster, beide Kontexte" — prüft aktuell wahrscheinlich nur Trip-Detail + Compare; um Trip-Anlegen ergänzen, falls dort eine dritte Kontext-Prüfung sauber reinpasst (sonst neue eigene Datei vermeiden — Pfadregel/Namensregel beachten). |

Kein Backend-Feld, kein Go-Test, kein pytest-Fall nötig — der Server-Vertrag ändert sich nicht.

### Scope Assessment

- Files: 2 Produktivdateien geändert, 0 neu · 2 Testdateien geändert, 0 neu (ggf. 1 E2E-Erweiterung)
- Geschätzt: **+35/-5 LoC** (Card-Block + Callback-Prop + Handler-Funktion + Verdrahtung an 2 Einbindungsstellen)
- Risk Level: **LOW-MEDIUM** — der Baustein selbst (`DayWindowCard`) ist unverändert und bereits
  produktiv erprobt; das Risiko liegt ausschließlich in der Verdrahtung (Rückkanal-Reihenfolge,
  Reassign vs. Mutation), für die es mit `onChannelsChange`/`onWeatherMetricsChange` zwei
  funktionierende Präzedenzfälle in genau dieser Datei gibt. Die in S1b/#1361 aufwendigen
  Adversary-Runden betrafen den **Speicher-Pfad des bestehenden Trips** (Dirty-Check, Touch-Scope,
  Auto-Save-Effekt) — der Anlege-Pfad hat kein Dirty-Tracking, nur einen finalen POST, wodurch
  diese Fehlerklasse strukturell entfällt.

### Technical Approach

Kein neuer Baustein, keine neue Abstraktion — Erweiterung des bestehenden `createMode`-Rückkanal-
Musters um ein drittes Feld-Paar, exakt wie #1552 es für die Metrik-Auswahl bereits getan hat:

1. `WeatherMetricsTab.svelte`: Card-Block bei `createMode` sichtbar machen (Bedingung von
   `!createMode && sections.includes('tagesfenster')` auf `sections.includes('tagesfenster')`
   ändern — der Block existiert dann in beiden Modi, gespeist aus demselben lokalen
   `reportConfig`, der im `createMode` bereits als `{}` initialisiert wird), zusätzlich bei jeder
   Änderung `onDayWindowChange?.({ day_window_start_hour, day_window_end_hour })` aufrufen.
2. `TripNewEditor.svelte`: `handleDayWindowChange` merged die zwei Felder additiv in
   `reportConfig` (Reassign: `reportConfig = { ...reportConfig, ...w }`), Prop an beiden
   `WeatherMetricsTab`-Stellen ergänzen.
3. Kein Payload-, Backend- oder Python-Eingriff.

Alternative verworfen: eine **neue**, eigene Bedienfläche nur für `trip-new` — verstößt gegen die
Teilungs-Invariante (CLAUDE.md „Trip/Ortsvergleich-Code-Teilung") und würde `pendant_gate.py`
auslösen, ohne einen Vorteil zu bieten, da der geteilte Baustein bereits alles Nötige leistet.

### Dependencies

- Keine Reihenfolge-Abhängigkeit zu anderen offenen Issues. #1599 (Rechenregel) und das
  Mitternachts-Fenster beim Zielsegment bleiben unberührt — reine UI-Ergänzung im bereits
  bestehenden Wertebereich.

### Open Questions

- [ ] Soll der neue `createMode`-Block in `WeatherMetricsTab.svelte` genau an derselben Stelle
  (nach dem Stundentabelle/Layout-Block) erscheinen wie beim bestehenden Trip, oder passt er
  besser in die Reihenfolge der `trip-new`-Tabs (Reiter „Wetter-Metriken")? — **Annahme:** gleiche
  Position wie bisher, da `sections`-Reihenfolge bereits kontext-unabhängig zentral definiert ist
  (`weatherMetricsTabSections.ts`) und keine separate Anlege-Reihenfolge existiert.
