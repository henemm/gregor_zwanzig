# Mini-Spec: Playwright-Selektoren des Trip-Ausblick-Klickpfads richtigstellen

<!-- Nacharbeit zu #1720 Scheibe 1. Herkunft: Staging-Validator F001/F002 (beide LOW,
     ausdrücklich als Testautoren-Befunde eingestuft, kein Produktfehler). -->

## Warum

`frontend/e2e/trip-outlook-metric-selection.staging.spec.ts` entstand in der RED-Phase und
konnte dort strukturell nicht gegen Staging laufen — der Stand war noch nicht deployt. Beim
ersten echten Lauf zeigten sich zwei falsche Annahmen über die Oberfläche. Die
Staging-Verifikation lief deshalb mit korrigierten Selektoren; die Datei im Repo trägt die
Korrektur noch nicht und schlägt fehl, wenn jemand sie ausführt.

Ein Test, der aus falschen Gründen rot ist, kostet den Nächsten eine Fehlersuche am Produkt.

## Was ändert sich

- **Speichern:** Der Helfer klickt `data-testid=weather-metrics-tab-save`. Diesen Knopf gibt es
  im Trip-Kontext nicht — `WeatherMetricsTab.svelte:1451` rendert ihn nur
  `{#if isDirty && !saveController && !createMode}`, und der Trip übergibt einen
  `saveController` (Autosave, 700 ms Debounce). Stattdessen auf den PUT warten
  (`page.waitForResponse`), so wie es der Validator im bestätigten Nachlauf getan hat.
- **Gegenprobe zu AC-13:** Sie wechselt zu `data-testid=trip-detail-tab-briefings` und sucht
  dort `report-show-outlook`. Der Schalter lebt im **selben** Wetter-Reiter
  (`WeatherMetricsTab.svelte:1780-1787` bindet `EditReportConfigSection` inline);
  `BriefingScheduleTab.svelte:117-119` hält ausdrücklich fest: „Mail-Inhalt bleibt unangetastet
  im Inhalt-Tab". Gegenprobe ohne Tab-Wechsel prüfen.

## Was darf sich nicht ändern

- Die geprüften Zusicherungen selbst — AC-6, AC-7, AC-11 und AC-13 bleiben inhaltlich gleich.
  Geändert wird nur, **wie** der Test die Oberfläche anspricht, nicht **was** er behauptet.
- Kein Produktivcode. Kein Eintrag in `.github/ci_e2e_specs.txt` (Positivliste wächst nur nach
  dem Vermessungsverfahren aus ADR-0054).

## Manuelle Test-Schritte

1. Aus `frontend/`: `npx playwright test --config=playwright.trip-outlook.staging.config.ts`
2. Alle Prüfungen grün, ohne Selektor-Anpassung von Hand.
3. Gegenprobe, dass der Test etwas bewacht: Abwahl im Testablauf entfernen ⇒ der AC-6-Fall
   muss rot werden.

## Acceptance Criteria

- **AC-1:** Given die Datei `trip-outlook-metric-selection.staging.spec.ts` im Repo-Zustand,
  When sie unverändert gegen Staging läuft, Then bestehen alle enthaltenen Prüfungen — ohne
  dass jemand vorher Selektoren von Hand anpassen muss.
- **AC-2:** Given der Trip-Editor speichert per Autosave statt per Knopf, When der Test eine
  Auswahl ändert, Then wartet er auf die tatsächliche Speicher-Antwort des Servers und nicht
  auf ein Element, das im Trip-Kontext gar nicht gerendert wird.
- **AC-3:** Given der bestehende Ein/Aus-Schalter für den Ausblick liegt im selben
  Wetter-Reiter, When die Gegenprobe zu AC-13 ihn sucht, Then findet sie ihn dort — ohne
  Wechsel in den Versand-Reiter.
