---
entity_id: fix_1775_tagesfenster_anlegen
type: feature
created: 2026-08-12
updated: 2026-08-12
status: draft
workflow: fix-1775-tagesfenster-anlegen
version: "1.0"
tags: [issue-1775, trip-new, day-window, weather-metrics-tab, adr-0035]
---

# Tagesfenster ist beim Trip-Anlegen nicht einstellbar — bestimmt seit #1584 die Reichweite der Alarmbereitschaft

## Approval

- [ ] Approved

## Purpose

Der Trip-Anlege-Dialog (`/trips/new`) bietet im Reiter „Wetter-Metriken" keine
Bedienfläche für das Tagesfenster (`day_window_start_hour`/`_end_hour`,
Default 4/19 Uhr) — sie existiert dort seit #1361/#1372 S1b nur für den
bestehenden Trip. Seit #1584 bestimmt genau dieses Fenster nicht mehr nur
Stundentabelle/Bewertung, sondern auch das Ende der Gefahren-Überwachung des
Ziel-Segments: wer die Voreinstellung beim Anlegen unangetastet lässt, ist ab
19 Uhr Ortszeit strukturell ohne Alarm-Überwachung, ohne dass die Anlege-Maske
das erkennen lässt. Der geteilte Baustein `DayWindowCard.svelte` existiert
bereits und wird für den bestehenden Trip verwendet — im Ortsvergleich-Anlegen
(`/compare/new`) ist die gleiche Bedienfläche seit #1361/#1372 S1b bereits Teil
des Anlege-Flows. Diese Spec schließt die verbliebene Lücke im Trip-Anlege-Pfad
über das bereits etablierte `createMode`-Rückkanal-Muster (#622, #1552).

## Source

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
  — Tagesfenster-Block Zeile 1325-1347, aktuell `!createMode`-gegated; lokaler
  `reportConfig`-$state Zeile 225-227 (Initialisierung einmalig bei Mount, aus
  `trip?.report_config`)
- **File:** `frontend/src/lib/components/trip-new/TripNewEditor.svelte`
  — eigene, separate `reportConfig`-$state Zeile 62; `stubTrip` ($derived)
  Zeile 86-92 (trägt aktuell `channels`/`metrics`, aber KEIN `report_config`);
  bestehende Rückkanal-Handler `handleChannelsChange` Zeile 295-297,
  `handleWeatherMetricsChange` Zeile 302-312; zwei `WeatherMetricsTab`-Mounts
  Zeile 805 (Desktop, hinter `{#if !isMobileViewport}`) und Zeile 1033 (Mobile,
  hinter `{#if isMobileViewport}`) — seit „Fix-Loop 4" (Kommentar Zeile 792-802
  bzw. 1028-1030) ist jeweils nur EINE Instanz gleichzeitig im DOM
  (Desktop XOR Mobile), nicht mehr beide dauerhaft parallel

> **Schicht-Hinweis:** Ausschließlich Frontend (`frontend/src/lib/components/
> shared/`, `frontend/src/lib/components/trip-new/`). Kein Go-, kein
> Python-Eingriff — `internal/handler/trip.go` (`CreateTripHandler`, Zeile
> 131-154) nimmt `report_config` bereits generisch als Map entgegen und
> klemmt es serverseitig (`store.ClampReportConfigDayWindow`); `src/app/
> day_window.py::resolve_configured_window()` liest `report_config`
> unabhängig davon, ob der Trip beim Anlegen oder später ein Tagesfenster
> bekommen hat.

## Estimated Scope

- **LoC:** ~+35/-5 (Card-Sichtbarkeits-Bedingung, neuer Callback-Prop + Effect
  in `WeatherMetricsTab.svelte`; neuer Handler + `stubTrip`-Erweiterung +
  Prop-Verdrahtung an beiden Mounts in `TripNewEditor.svelte`)
- **Files:** 2 Produktivdateien geändert (`WeatherMetricsTab.svelte`,
  `TripNewEditor.svelte`), 0 neu. Zusätzlich 3 Testdateien erweitert (0 neu)
- **Effort:** low-medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `DayWindowCard.svelte` (#1361/#1372 S1b) | component (unverändert) | Reine Präsentationskomponente (Props `startHour`/`endHour`/`onStartHour`/`onEndHour`, kein interner State, kein eigener Speicherweg) — wird 1:1 wiederverwendet, kein neuer Baustein nötig |
| `clampDayWindowEndHour()` (`versand-tab/dayWindowClamp.ts`) | function (unverändert) | Verhindert `start === end` in der Bedienfläche selbst; erlaubt Mitternachts-Fenster (`end < start`) explizit als gültig (PO-Entscheidung 2026-07-25) |
| `onChannelsChange`/`handleChannelsChange` (#622) | pattern (Vorbild) | Erstes etabliertes `createMode`-Rückkanal-Paar in genau diesen zwei Dateien |
| `onWeatherMetricsChange`/`handleWeatherMetricsChange` (#1552) | pattern (Vorbild) | Zweites etabliertes Rückkanal-Paar — inkl. der „Fix-Loop"-Historie (Doppel-Mount-Race), die zu der aktuellen `isMobileViewport`-XOR-Gate-Lösung führte |
| `tripNewLogic.ts::buildCreateTripPayload()` (Zeile 117-149) | function (unverändert) | `state.reportConfig` wird bereits 1:1 nach `trip.report_config` übernommen (Zeile 147-149) — die neuen Feldwerte laufen ohne Anpassung mit |
| `internal/handler/trip.go::CreateTripHandler` + `store.ClampReportConfigDayWindow` | Go (unverändert) | Nimmt `report_config` generisch entgegen, klemmt serverseitig — bereits für den Anlege-Pfad vorgesehen |
| `compareWizardState.svelte.ts`/`compareEditorSave.ts` (#1361/#1372 S1b) | Vorbild (Compare) | Identisches Problem im Ortsvergleich-Anlegen bereits gelöst — `dayWindowStartHour`/`dayWindowEndHour`, Default 4/19, unbedingt im Payload gesendet (Test-Vorbild `compare_new_preset_payload.test.ts:89-109`) |
| `.claude/hooks/pendant_gate.py` (#1481 B) | Gate | Keine neu angelegte Compare-/Trip-Pendant-Datei — nur Bestandsdateien geändert |
| `.claude/hooks/touched_tests_gate.py` (#1481 A) | Gate | Prüft `tests/unit/`-Nachbarn der geänderten Dateien vor Commit |

## Implementation Details

### A) `WeatherMetricsTab.svelte` — Card auch im `createMode` rendern, Rückkanal ergänzen

Der bestehende Block (Zeile 1325-1347) wird von
`{#if !createMode && sections.includes('tagesfenster')}` auf
`{#if sections.includes('tagesfenster')}` geändert — die Karte bindet
weiterhin an denselben lokalen `reportConfig`-$state, der im `createMode`
bereits (mangels `trip.report_config` auf dem Stub) mit `{}` initialisiert
wird, also Default 4/19 zeigt. Die bestehenden `onStartHour`/`onEndHour`-
Handler bleiben unverändert (die darin enthaltenen `scheduleReportConfigOnlySave()`-
Aufrufe sind bereits `createMode`-sicher: `scheduleReportConfigOnlySave()`
selbst hat als ersten Guard `if (!saveController || createMode) return;`
— im Anlege-Modus ist der Aufruf ein No-op, kein neuer Kontrollfluss nötig).

Neuer optionaler Prop, analog `onChannelsChange`/`onWeatherMetricsChange`:

```
onDayWindowChange?: (w: { day_window_start_hour: number; day_window_end_hour: number }) => void;
```

Neuer `$effect` (kein `catalogLoaded`-Gate nötig — die Tagesfenster-Felder
hängen anders als die Metrik-Auswahl an keinem asynchron geladenen Katalog,
sie sind ab Mount synchron verfügbar):

```
$effect(() => {
	if (createMode && onDayWindowChange) {
		onDayWindowChange({
			day_window_start_hour: reportConfig.day_window_start_hour ?? 4,
			day_window_end_hour: reportConfig.day_window_end_hour ?? 19,
		});
	}
});
```

### B) `TripNewEditor.svelte` — Handler + `stubTrip`-Erweiterung + Prop-Verdrahtung

Neuer Handler, analog `handleChannelsChange` (additiv mergen statt Feld für
Feld separat zu halten — `reportConfig` ist hier bereits das EINE Objekt, das
auch `EditReportConfigSection` per `bind:reportConfig` (Zeile 780/1016) hält
und das unverändert in `buildCreateTripPayload()` (`tripNewLogic.ts:147-149`)
1:1 in den POST-Payload wandert):

```
function handleDayWindowChange(w: { day_window_start_hour: number; day_window_end_hour: number }) {
	reportConfig = { ...(reportConfig ?? {}), ...w };
}
```

Prop an beiden Mount-Stellen ergänzen (Zeile 805, 1033):
`onDayWindowChange={handleDayWindowChange}`.

**Notwendige zusätzliche Änderung, beim Spec-Schreiben gemessen (nicht im
ursprünglichen Analyse-Kontext genannt):** `stubTrip` (Zeile 86-92) trägt
aktuell `channels` und `metrics`, aber kein `report_config`. Seit „Fix-Loop 4"
(#1552) wird beim Wechsel Desktop↔Mobile die jeweils andere `WeatherMetricsTab`-
Instanz per `{#if isMobileViewport}`/`{#if !isMobileViewport}` NEU gemountet
(nicht nur per CSS umgeschaltet) — ihr lokaler `reportConfig`-$state
initialisiert dann erneut aus `trip?.report_config` (Zeile 225-227). Bekäme
`stubTrip` kein `report_config`, würde eine neu gemountete Instanz immer bei
`{}` (→ Default 4/19) starten, ihr erster `$effect`-Lauf würde
`onDayWindowChange({4, 19})` feuern und dabei einen zuvor auf der anderen
Instanz bewusst gesetzten Wert (z. B. 6/16) in `TripNewEditor.reportConfig`
stillschweigend überschreiben — dieselbe Fehlerklasse wie die bereits
dokumentierten Fix-Loops 2-4, nur über einen Remount statt eine
Parallel-Race ausgelöst. Deshalb wird `stubTrip` um `report_config:
reportConfig` ergänzt (analog `channels`/`metrics` bereits heute), sodass
jede frisch gemountete Instanz mit dem aktuell in `TripNewEditor` gehaltenen
Stand initialisiert und der erste Effect-Lauf idempotent bleibt (s. AC-6).

### C) Kein Payload-, Backend- oder Python-Eingriff

`report_config` läuft unverändert durch `buildCreateTripPayload()` und den
Go-Handler — beide sind bereits generisch für beliebige `report_config`-Felder
gebaut.

Alternative verworfen: eine **eigene** Bedienfläche nur für `trip-new` —
verstieße gegen die Teilungs-Invariante (CLAUDE.md „Trip/Ortsvergleich-Code-
Teilung") und würde `pendant_gate.py` ohne Vorteil auslösen, da der geteilte
Baustein bereits alles Nötige leistet.

## Expected Behavior

- **Input:** Anlege-Dialog `/trips/new`, Reiter „Wetter-Metriken" — Nutzer
  bestätigt das voreingestellte Tagesfenster (4-19 Uhr) oder ändert es,
  inklusive eines Mitternachts-Fensters (z. B. 22-2 Uhr).
- **Output:** Der beim Speichern gesendete Trip trägt `report_config.
  day_window_start_hour`/`day_window_end_hour` mit exakt den zuletzt im
  Dialog sichtbaren Werten — auch wenn nie angefasst (dann explizit 4/19,
  nicht fehlend). Diese Werte bestimmen ab sofort (bereits bestehendes
  Verhalten seit #1584, hier nur erstmals beim Anlegen erreichbar) das Ende
  der Alarm-Überwachung des Ziel-Segments.
- **Side effects:** Der bestehende Trip-Editor-Speicherpfad (PUT bei
  bestehendem Trip) bleibt unverändert — die Card war dort bereits sichtbar
  und funktionsfähig, nur die Sichtbarkeits-Bedingung in `WeatherMetricsTab.
  svelte` wird erweitert (nicht ersetzt). Ortsvergleich-Anlegen (`/compare/
  new`) ist bereits vollständig unabhängig verdrahtet (eigener `wiz`-Zweig,
  Zeile 1148-1150) und bleibt unberührt.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet `/trips/new` und wechselt zum Reiter
  „Wetter-Metriken" / When die Seite den Reiter anzeigt / Then ist die
  Tagesfenster-Bedienfläche (Karte „Tagesfenster" mit Von/Bis-Auswahl)
  sichtbar — exakt wie beim Öffnen eines bestehenden Trips im selben Reiter.
  - Test: `/trips/new` im Browser durchlaufen bis zum Reiter „Wetter-
    Metriken", prüfen dass die Karte mit den Von/Bis-Dropdowns sichtbar und
    mit den Default-Werten 04:00/19:00 vorbelegt ist.

- **AC-2:** Given ein Nutzer ändert im Anlege-Dialog das Tagesfenster auf
  6-16 Uhr, bevor er den Trip speichert / When der Trip gespeichert wird /
  Then enthält der beim Server ankommende POST-Rumpf `report_config.
  day_window_start_hour = 6` und `report_config.day_window_end_hour = 16`
  top-level in `report_config` (nicht in `display_config`), und der
  anschließend per GET abgerufene Trip trägt exakt diese Werte.
  - Test: im Anlege-Dialog Von auf 06, Bis auf 16 stellen, restliche
    Pflichtfelder ausfüllen, speichern; den abgefangenen POST-Rumpf UND den
    per GET abgerufenen gespeicherten Trip auf `report_config.
    day_window_start_hour`/`_end_hour` prüfen.

- **AC-3:** Given ein Nutzer legt einen Trip an, ohne die Tagesfenster-Karte
  anzufassen / When der Trip gespeichert wird / Then trägt der gespeicherte
  Trip `report_config.day_window_start_hour = 4` und `_end_hour = 19` explizit
  (nicht `null`/fehlend) — identisch zum bisherigen Renderer-Default.
  - Test: `/trips/new` bis zum Speichern durchlaufen, ohne die
    Tagesfenster-Karte zu berühren; gespeicherten Trip per GET abrufen und
    die beiden Felder auf die expliziten Werte 4 und 19 prüfen.

- **AC-4 (Regressionsschutz Mitternachts-Fenster):** Given ein Nutzer stellt
  im Anlege-Dialog die Startstunde auf 22 / When er anschließend die
  Bis-Auswahl öffnet / Then bietet sie weiterhin alle Stunden außer 22 an
  (inkl. Stunden kleiner als 22, z. B. 2 Uhr), ein gewählter Wert wie „02:00"
  erzeugt den Mitternachts-Hinweis, und der gespeicherte Trip trägt
  `day_window_start_hour = 22`, `day_window_end_hour = 2` unverändert (kein
  serverseitiges Nachkorrigieren auf ein Vorwärts-Fenster) — exakt dasselbe
  Verhalten wie beim Setzen desselben Fensters im Editor eines bestehenden
  Trips, keine neue Einschränkung nur für den Anlege-Pfad.
  - Test: im Anlege-Dialog Startstunde 22 wählen, Bis-Dropdown-Optionen auf
    Vorhandensein von „02:00" prüfen, 02:00 auswählen, Mitternachts-Hinweis-
    Element prüfen, speichern, gespeicherten Trip per GET auf
    `day_window_start_hour=22`/`day_window_end_hour=2` prüfen.

- **AC-5 (Regressionsschutz bestehender Trip-Editor):** Given ein bereits
  gespeicherter Trip / When ein Nutzer ihn im Editor öffnet, den Reiter
  „Wetter-Metriken" ansteuert und dort das Tagesfenster ändert / Then
  speichert der bestehende PUT-Autosave-Pfad die Änderung unverändert wie vor
  dieser Scheibe (mindestens ein PUT auf `/api/trips/{id}`, serverseitig
  persistiert, nach Reload weiterhin sichtbar) — die Erweiterung der
  Sichtbarkeits-Bedingung auf den Anlege-Modus darf den bestehenden Pfad
  nicht verändern.
  - Test: bestehenden Trip im Editor öffnen, Tagesfenster auf einen neuen
    Wert stellen, auf den Autosave-PUT warten, Server-Stand per GET prüfen,
    Seite neu laden und den Wert erneut prüfen (identischer Ablauf wie der
    bestehende Live-E2E-Test für die Trip-Hälfte in
    `daywindow-shared-both-contexts.spec.ts`).

- **AC-6 (Viewport-Wechsel verliert keinen bereits gesetzten Wert —
  Spec-Writer-Befund, kein Teil des ursprünglichen Analyse-Kontexts):**
  Given ein Nutzer stellt im Anlege-Dialog auf Desktop-Breite das Tagesfenster
  auf 6-16 Uhr / When er danach das Browserfenster auf Mobile-Breite
  verkleinert (wodurch die Desktop-`WeatherMetricsTab`-Instanz entfernt und
  die Mobile-Instanz neu gemountet wird) und anschließend speichert / Then
  bleibt das gespeicherte Tagesfenster 6-16 Uhr erhalten — der Remount der
  jeweils anderen Instanz setzt es NICHT stillschweigend auf 4/19 zurück.
  - Test: `/trips/new` im Desktop-Viewport bis zum Wetter-Metriken-Reiter
    durchlaufen, Tagesfenster auf 06/16 stellen, Viewport per
    `page.setViewportSize()` auf Mobile-Breite verkleinern, die dort
    sichtbare Tagesfenster-Karte auf 06/16 prüfen, speichern, gespeicherten
    Trip per GET auf `day_window_start_hour=6`/`day_window_end_hour=16`
    prüfen.

## Nicht in dieser Scheibe

- **#1599 (Rechenregel Obergrenze inklusiv/exklusiv)** — unverändert, diese
  Scheibe ändert nichts an der Auswertung des Fensters, nur an seiner
  Erreichbarkeit beim Anlegen.
- **Mitternachts-Fenster beim Zielsegment (PO-Entscheidung 2026-08-08,
  `trip_segments.py:259-264`)** — das Zielsegment kann ein Mitternachts-Fenster
  strukturell nicht abbilden (Loch-Problem, s. `fix_1584_alarm_zeitfenster.md`
  „Known Limitations"); die UI erlaubt das Setzen eines solchen Fensters
  bereits unverändert seit S1b (AC-4 hier ist ausschließlich ein
  Regressionsschutz gegen eine neue, zusätzliche Einschränkung nur im
  Anlege-Pfad, keine neue Aussage über die Wirkung am Zielsegment).
- **Ortsvergleich-Anlegen (`/compare/new`)** — bereits vollständig gelöst
  (#1361/#1372 S1b), eigener, unabhängiger `wiz`-Zweig in `WeatherMetricsTab.
  svelte` (Zeile 1148-1150), von dieser Scheibe nicht berührt.

## Test Plan

Test-Politik (CLAUDE.md „Zwei Schichten"): Kern-Tests deterministisch ohne
Netz/Live-Dienste sind Pflicht (Source-Inspection nach dem Muster der
bestehenden `createMode`-Rückkanal-Tests, da kein jsdom/happy-dom-Rendering
im Frontend-Test-Setup verfügbar ist — `$effect` ist per SSR nie sichtbar).
Der eigentliche Verhaltensnachweis (AC-1 bis AC-6) läuft über Live-E2E
(Playwright gegen Staging), analog dem bestehenden Muster in
`daywindow-shared-both-contexts.spec.ts`. Keine neue Testdatei mit
Issue-Nummer im Namen.

### Automated Tests (TDD RED)

- [ ] Test 1 (`shared/__tests__/weather_metrics_tab_create_mode_callback.test.ts`,
  erweitert): GIVEN `WeatherMetricsTab.svelte` / WHEN der Quelltext auf eine
  `onDayWindowChange`-Prop vom erwarteten Typ und deren Destrukturierung aus
  `Props` geprüft wird / THEN sind beide vorhanden (Muster identisch zu den
  bestehenden `onWeatherMetricsChange`-Tests in derselben Datei).
- [ ] Test 2 (dieselbe Datei): GIVEN `WeatherMetricsTab.svelte` / WHEN ein
  `$effect`-Block gesucht wird, der bei `createMode && onDayWindowChange`
  `onDayWindowChange({ day_window_start_hour: reportConfig.
  day_window_start_hour ?? 4, day_window_end_hour: reportConfig.
  day_window_end_hour ?? 19 })` aufruft / THEN existiert genau ein solcher
  Block (Guard-Bedingung UND übergebener Ausdruck im selben Match, nicht nur
  String-Presence).
- [ ] Test 3 (dieselbe Datei): GIVEN der Tagesfenster-Block (Zeile
  ~1325-1347) / WHEN die Sichtbarkeits-Bedingung geprüft wird / THEN enthält
  sie `sections.includes('tagesfenster')` OHNE ein vorangestelltes
  `!createMode`-Gate mehr (Regressionsschutz gegen ein versehentliches
  Wieder-Einführen der alten Einschränkung).
- [ ] Test 4 (`trip-new/__tests__/trip_new_editor_weather_metrics_wiring.test.ts`,
  erweitert): GIVEN `TripNewEditor.svelte` / WHEN nach einem
  `handleDayWindowChange`-Handler gesucht wird, der additiv in `reportConfig`
  schreibt (`reportConfig = { ...(reportConfig ?? {}), ...w }` oder
  äquivalent) / THEN existiert er.
- [ ] Test 5 (dieselbe Datei): GIVEN beide `WeatherMetricsTab`-Mounts (Zeile
  805, 1033) / WHEN ihre Props geprüft werden / THEN übergeben beide
  `onDayWindowChange={handleDayWindowChange}`, ohne die bestehenden
  `onChannelsChange`/`onWeatherMetricsChange`-Props zu verlieren (Muster
  identisch zum bestehenden Test „beide WeatherMetricsTab-Mounts übergeben
  onWeatherMetricsChange").
- [ ] Test 6 (dieselbe Datei, AC-6-Vorstufe): GIVEN `stubTrip` (Zeile 86-92)
  / WHEN der Quelltext geprüft wird / THEN enthält die `$derived<Trip>`-
  Konstruktion ein Feld `report_config: reportConfig` (Regressionsschutz
  gegen den in „Implementation Details" B beschriebenen Remount-Verlust).

### Live-E2E (Staging, vor „E2E bestanden")

`daywindow-shared-both-contexts.spec.ts` um einen dritten `test.describe`-
Block für die Trip-Anlegen-Hälfte erweitern (Muster: bestehender
Compare-Hub-Test in derselben Datei — Wert wählen → POST abfangen und
Rumpf prüfen → per GET den gespeicherten Trip lesen → optional Reload):
deckt AC-1 (Sichtbarkeit), AC-2 (Payload-Übernahme geänderter Werte), AC-3
(explizite Defaults ohne Nutzereingriff) und AC-4 (Mitternachts-Fenster) ab.
AC-5 ist der bereits bestehende Trip-Hälfte-Test in derselben Datei — bleibt
unverändert grün, sofern die Implementierung wie in „Implementation Details"
A beschrieben additiv (nicht ersetzend) vorgeht. AC-6 (Viewport-Wechsel)
braucht einen eigenen kurzen Testfall mit `page.setViewportSize()`
Desktop→Mobile innerhalb desselben Anlege-Durchlaufs.

**Mutations-Gegenprobe (Hinweis für den Adversary):**
- Sichtbarkeits-Bedingung zurück auf `!createMode && sections.includes(...)`
  → AC-1 muss rot werden (Karte fehlt im Anlege-Dialog).
- `onDayWindowChange`-Aufruf im `$effect` entfernt/nicht verdrahtet → AC-2
  und AC-3 müssen rot werden (Felder erreichen `TripNewEditor.reportConfig`
  nie, Payload trägt sie nicht).
- `stubTrip`-Erweiterung um `report_config: reportConfig` entfernt → AC-6
  muss rot werden (Viewport-Wechsel setzt einen gesetzten Wert auf 4/19
  zurück).
- `?? 4`/`?? 19`-Fallback im `$effect` entfernt (rohe `undefined`-Werte
  emittiert) → AC-3 muss rot werden (Payload trägt die Felder dann nicht
  explizit, sondern lässt sie fehlen).
- `onStartHour`/`onEndHour` in `DayWindowCard.svelte` selbst verändert (z. B.
  End-Optionen wieder auf `> startHour` gedeckelt) → AC-4 muss rot werden
  (Mitternachts-Wert 02:00 wäre bei Startstunde 22 nicht mehr wählbar) —
  dieser Baustein wird von dieser Scheibe nicht angefasst, ein bestehender
  Test (`day_window_card.test.ts`) bewacht ihn bereits unabhängig.

## Known Limitations

- **Ortsvergleich-Anlegen war bereits vor dieser Scheibe korrekt** — kein
  Bezug, keine Abhängigkeit.
- **AC-6 ist ein während des Spec-Schreibens gemessener, nicht im
  ursprünglichen Analyse-Kontext genannter Zusatzbefund** — ohne die
  `stubTrip`-Erweiterung (Implementation Details B) bliebe ein latenter,
  seltener Datenverlust-Pfad offen (nur auslösbar durch einen
  Viewport-Wechsel zwischen Setzen und Speichern des Tagesfensters im
  Anlege-Dialog).
- **`day_window_start_hour`/`_end_hour` werden beim Anlegen künftig immer
  explizit gesendet** (wie beim Ortsvergleich-Anlegen, s. Vorbild-Test), auch
  wenn der Nutzer sie nie berührt hat — konsistent mit dem übrigen
  `reportConfig`-Verhalten in `TripNewEditor.svelte` (z. B. `morning_enabled`
  über `EditReportConfigSection`), keine neue Ausnahmeregel.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0035 (bestehend, keine Ergänzung nötig)
- **Rationale:** ADR-0035 hat bereits entschieden, dass es EIN Tagesfenster
  gibt (`resolve_configured_window()`) und dass neue Ausgaben ihr Zeitfenster
  aus derselben Quelle beziehen — kein neuer Auflöser. Diese Scheibe führt
  keinen neuen Zeitbegriff und keine neue Bedienfläche ein, sondern macht die
  bereits bestehende, geteilte Bedienfläche (`DayWindowCard.svelte`, seit
  #1361/#1372 S1b bereits ADR-0035-konform) in einem bislang ausgesparten
  Modus derselben Komponente sichtbar — reine Erweiterung eines bereits
  etablierten Rückkanal-Musters (#622, #1552), keine neue Architektur-,
  Kanal- oder Persistenzentscheidung. Ein neues ADR wäre hier Overhead.

## Changelog

- 2026-08-12: Initial spec erstellt — Issue #1775. AC-6 (Viewport-Wechsel-
  Datenverlust über `stubTrip`) beim Spec-Schreiben zusätzlich zum
  ursprünglichen Analyse-Kontext identifiziert und samt Implementierungs-
  Vorgabe (`stubTrip` um `report_config` erweitern) ergänzt.
