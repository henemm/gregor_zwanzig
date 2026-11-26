---
entity_id: rework_3375_wsw_browserpruefungen
type: module
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: rework-3375-wsw-browserpruefungen
tags: [e2e, playwright, was-steht-wo, telegram, marken]
---

# Browser-Prüfungen der Karte „Was steht wo“ (Telegram-Grenze, Marken nicht abgeschnitten)

## Approval

- [ ] Approved

## Purpose

Zwei Zusicherungen der Karte „Was steht wo“ werden wieder im echten Browser gegen den echten Server geprüft: (a) die Telegram-Spalte zeigt beim Trip ab der 8. Metrik „nur Tageswert“ (ADR-0124 Nr. 3), (b) die Marken der Karte werden bei keiner Fensterbreite von 320 bis 1920 Pixel abgeschnitten. Beide Prüfungen sind mit dem Alt-Editor entfallen (Issue #3375, Epic #3122, aus #3164); es wird kein Produktcode geändert.

## Source

- **File:** `frontend/e2e/kanal-grenzen-und-hinweise.staging.spec.ts` und `frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts`
- **Identifier:** neue Playwright-Fälle (Telegram-Grenze; Marken-Sichtbarkeit über 14 Auflösungen)

> Schicht: reine Frontend-E2E-Tests (`frontend/e2e/`) gegen Karte `WasStehtWoKarte.svelte`; Server-Verhalten (`src/output/renderers/channel_layout.py`, `src/services/placements_view_service.py`) wird nur beobachtet, nicht verändert.
> Trip/Vergleich-Teilung: Die Karte ist geteilt (`context="route"|"vergleich"`); der Marken-Fall prüft beide Seiten. Mandantentrennung: kein neuer datenbewegender Endpoint, Seed und Aufräumen laufen über die vorhandenen Helfer mit dem Prüfkonto. Kanäle: der Telegram-Fall belegt die Kanalgrenze; die anderen drei Kanäle sind nicht berührt.

## Estimated Scope

- **LoC:** ca. +170/-10
- **Files:** 3 (+ diese Spec)
- **Effort:** low

## Scope

Nur Browser-Prüfungen und Doku; kein Produktcode.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/kanal-grenzen-und-hinweise.staging.spec.ts` | MODIFY | Neuer Fall Telegram „nur Tageswert“ (9 Metriken) plus Gegenfall mit 7 Metriken; Kopfkommentar „AC-3 gestrichen“ ersetzen |
| `frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts` | MODIFY | Neue Fälle Marken nicht abgeschnitten (Trip, Vergleich) über 14 Auflösungen; Kopfkommentar „AC-10..13 gestrichen“ ersetzen |
| `docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md` | MODIFY | Z. 74 und Z. 180: „folgt mit #3375“ bzw. „#3375: Browser-Fall …“ als erledigt vermerken |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/e2e/was-steht-wo.helpers.ts` | module | `seedAbo`, `oeffneKarte`, `zeile`, `zelle`, `tabelle`, `aufraeumen` |
| `frontend/src/lib/components/molecules/EinstellTabelle.svelte` | component | Marke `[data-slot="et-marke"]`, Zeile `et-zeile`, Zelle `et-zelle` |
| `frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts` | module | Text `wetter.wsw.marke.nur_tageswert` |
| `src/output/renderers/channel_layout.py` | module | Telegram `max_table_cols: 8` inkl. Zeitspalte (Grenze serverseitig) |
| `src/services/placements_view_service.py` | module | `_trip_nur_tageswert`, liefert `mark` |
| Staging-Playwright-Config und Login-Setup je Datei | tooling | Anmeldung per `POST /api/auth/login`, storageState |
| `git show f62019a64^:frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts` | Vorlage | Messfunktion und 14 Auflösungen der alten Fassung (Z. 54–69, 225–260) |
| ADR-0124 Nr. 3 | Entscheidung | Telegram zeigt ab der 8. Metrik nur den Tageswert |

## Implementation Details

Fall (a), Datei `kanal-grenzen-und-hinweise.staging.spec.ts`: Ein Trip wird mit neun Metriken in dieser Reihenfolge angelegt: temperature, gust, wind, precipitation, rain_probability, cloud_cover, humidity, uv_index, sunshine. Die Karte wird geöffnet; die Telegram-Zelle jeder Metrikzeile wird gelesen. Erwartet wird die Marke „nur Tageswert“ sichtbar genau in den Telegram-Zellen von uv_index und sunshine, in keiner anderen Zelle der Zeilen. Zusätzlich wird die Server-Antwort der Placements-Tabelle gelesen (`mark: nur_tageswert` nur dort), damit ein Fehlschlag eindeutig Server oder Darstellung zugeordnet werden kann. Gegenfall: Trip mit sieben Metriken (die ersten sieben der Liste), keine „nur Tageswert“-Marke irgendwo in der Karte.

Fall (b), Datei `kuerzel-marken-sichtbar.staging.spec.ts`: Je ein Seed (Trip mit neun Metriken; Vergleich mit drei Orten), Breitenwechsel per Viewport-Wechsel ohne Neuseed, nach jedem Wechsel warten bis das Layout steht. Vorab wird per API-Antwort sichergestellt, welche Marken vorliegen. Beim Trip müssen „nur Tageswert“ und „passt nicht mehr“ vorliegen. Beim Vergleich muss „passt nicht mehr“ vorliegen, sofern die Antwort eine liefert; sonst genügt mindestens eine Marke, und der Test hält fest, welcher Zweig galt. Die 14 Auflösungen: 320×568, 375×667, 390×844, 414×896, 600, 768×1024, 899, 901, 960, 1024×768, 1180×820, 1280, 1440, 1920×1080. Je Marke `[data-slot="et-marke"]` gilt: Ausdehnung größer 0; nicht beschnitten (`scrollWidth ≤ clientWidth+1` und `scrollHeight ≤ clientHeight+1`); liegt innerhalb des Rechtecks der eigenen Zeile und horizontal im Sichtfenster; die Seite hat keinen seitlichen Überlauf (`documentElement.scrollWidth ≤ innerWidth`).

Kopfkommentare der beiden Dateien nennen statt „gestrichen“ den neuen Fall und verweisen auf #3375. Befund-Regel: wird ein Fall rot, ist das ein echter Fund und kein Grund, die Prüfung zu lockern.

Lauf lokal: `npx playwright test --project=tests e2e/<datei>.staging.spec.ts` gegen den ci-stack (Preview 4173, API 8091); danach gegen Staging.

## Expected Behavior

- **Input:** Trip mit neun bzw. sieben Metriken; Vergleich mit drei Orten; 14 Fensterbreiten.
- **Output:** Alle Prüfungen grün, solange die Karte wie in ADR-0124 Nr. 3 und feat_3122 festgelegt arbeitet.
- **Side effects:** Seed-Daten des Prüfkontos, nach jedem Fall per `aufraeumen` entfernt.

## Test Plan

### Automated Tests (TDD RED)

- [ ] GIVEN Trip mit 9 Metriken WHEN Karte geöffnet THEN „nur Tageswert“ sichtbar nur in Telegram-Zellen von uv_index und sunshine.
- [ ] GIVEN Trip mit 7 Metriken WHEN Karte geöffnet THEN keine „nur Tageswert“-Marke.
- [ ] GIVEN Trip mit 9 Metriken WHEN Breite über 14 Auflösungen gewechselt THEN jede Marke unbeschnitten, in Zeile und Sichtfenster, Seite ohne seitlichen Überlauf.
- [ ] GIVEN Vergleich mit 3 Orten WHEN dieselben 14 Auflösungen THEN dieselben Kriterien je Marke.

### Mutations-Gegenproben (Pflicht, per String-Ersetzung mit externer Sicherungskopie, nie git checkout/stash/reset)

- Telegram-`max_table_cols` in `src/output/renderers/channel_layout.py` von 8 auf 9: Fall (a) muss rot werden; danach zurücksetzen.
- `.et-marke` in `EinstellTabelle.svelte` mit `white-space: nowrap; overflow: hidden; max-width: 2ch` überschreiben: Fall (b) muss bei mindestens einer Auflösung rot werden; danach zurücksetzen.

Eine Mutation, die der Fall nicht fängt, ist ein Finding.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit neun Metriken (Temperatur, Böen, Wind, Niederschlag, Regenwahrscheinlichkeit, Bewölkung, Luftfeuchte, UV-Index, Sonnenscheindauer) / When die Karte „Was steht wo“ im Browser geöffnet wird / Then zeigt die Telegram-Spalte „nur Tageswert“ sichtbar in den Zeilen UV-Index und Sonnenscheindauer und in keiner anderen Zelle der Karte.
  - Test: Der Nutzer sieht in der Telegram-Spalte genau bei den Metriken 8 und 9 die Marke; die ersten sieben Zeilen tragen keine.

- **AC-2:** Given die Server-Antwort der Karte für denselben Trip mit neun Metriken / When sie mit der Darstellung im Browser verglichen wird / Then trägt die Antwort die Marke „nur Tageswert“ genau für die beiden letzten Metriken und der Browser zeigt genau diese beiden.
  - Test: Server-Entscheidung und sichtbare Darstellung stimmen überein, ein Fehlschlag ist eindeutig zuordenbar.

- **AC-3:** Given ein Trip mit nur sieben Metriken / When die Karte geöffnet wird / Then erscheint nirgends in der Karte die Marke „nur Tageswert“.
  - Test: Gegenprobe: Bis zur siebten Metrik zeigt Telegram stündliche Werte ohne Einschränkung.

- **AC-4:** Given ein Trip mit neun Metriken, in dem „nur Tageswert“ und „passt nicht mehr“ als Marken vorliegen / When die Fensterbreite nacheinander auf alle 14 Auflösungen (320×568 bis 1920×1080) gestellt wird / Then ist jede Marke der Karte sichtbar, hat eine Ausdehnung größer 0 und ist weder in Breite noch in Höhe beschnitten.
  - Test: Auf Handy-, Tablet- und Desktopbreite bleibt jede Marke vollständig lesbar.

- **AC-5:** Given derselbe Trip bei jeder der 14 Auflösungen / When Lage der Marken und der Seite gemessen werden / Then liegt jede Marke innerhalb ihres Zeilenrechtecks und horizontal im Sichtfenster, und die Seite hat keinen seitlichen Überlauf (Seitenbreite höchstens Fensterbreite).
  - Test: Der Nutzer muss nie seitlich scrollen, um eine Marke zu sehen.

- **AC-6:** Given ein Vergleich mit drei Orten, dessen Server-Antwort vorab geprüft wird / When dieselben 14 Auflösungen durchlaufen werden / Then gelten für jede Marke der Vergleichs-Karte dieselben Kriterien (sichtbar, unbeschnitten, in Zeile und Sichtfenster, Seite ohne Überlauf), und der Test schlägt fehl, wenn die Karte gar keine Marke zeigt.
  - Test: Auch im Ortsvergleich ist „passt nicht mehr“ (bzw. mindestens eine vorliegende Marke) bei jeder Breite lesbar.

- **AC-7:** Given die beiden neuen Prüfgruppen / When die Telegram-Grenze auf dem Server um eins verschoben (8 auf 9) bzw. die Marken-Darstellung durch eine Abschneide-Regel (`white-space: nowrap`, `overflow: hidden`, sehr kleine Maximalbreite) verfälscht wird / Then wird die jeweilige Prüfung rot, und nach dem Zurücksetzen wieder grün.
  - Test: Die Prüfungen bewachen die Zusicherung dort, wo sie wirkt (im Browser), nicht nur in einem Render-Test.

- **AC-8:** Given die Kopfkommentare der beiden Spec-Dateien und die Spec „Prüfungen wiederherstellen“ (#3020) / When sie nach der Umsetzung gelesen werden / Then nennen sie die neuen Browser-Fälle statt „gestrichen“ bzw. „folgt mit #3375“, ohne Produktcode zu ändern.
  - Test: Wer die Doku liest, findet für beide Zusicherungen den Browser-Fall und keinen offenen Verweis.

## Definition of Done

- AC-1 bis AC-8 erfüllt, jedes AC mit grünem Browser-Fall bzw. dokumentierter Mutations-Gegenprobe; keine Zusicherung gelockert.
- Pull Request mit allen 6 CI-Checks grün gemergt, `/e2e-verify` gegen Staging bestanden, Prod-Deploy mit Selftest-Exit 0.

## Known Limitations

- Liefert die Vergleichs-Antwort keine Marke „passt nicht mehr“, prüft der Fall nur, dass mindestens eine Marke vorliegt.
- Die Läufe gegen Staging brauchen das Login-Setup je Datei (Rate-Limit #703); lokal läuft alles gegen den ci-stack.
- Wird ein Fall rot, ist es ein Produktbefund und braucht ein eigenes Issue, keine Lockerung des Tests.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird nichts entschieden; ADR-0124 Nr. 3 und feat_3122 werden nur im Browser belegt.

## Changelog

- 2026-11-26: Initial spec created
