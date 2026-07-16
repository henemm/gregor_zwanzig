---
entity_id: issue_1268_compare_timewindow_removal
type: refactor
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
tags: [compare, layout-tab, cleanup, dispatch]
workflow: fix-1268-compare-dead-timewindow-fields
---

<!-- Issue #1268 -->

# Issue 1268 — Zeitfenster/Horizont-Felder aus Ortsvergleich-Editor entfernen

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich-Editor zeigt im Layout-Tab zwei Einstellfelder — „Zeitfenster"
(Start-/End-Stunde, Default 9–16) und „Horizont" (24/48/72 h) — die der PO als
unnötige Komplexität verworfen hat. Anders als der Issue-Titel unterstellt sind
beide Felder **nicht toter Code**: sie wirken über den live verdrahteten
Dispatch-Pfad (`api/routers/scheduler.py:137` → `run_compare_presets_daily` →
`ComparisonEngine.run`) auf jede automatisch versendete Vergleichs-Mail. Diese
Spec entfernt die Einstellmöglichkeit aus der Oberfläche und dem
Preset-Dispatch-Lesepfad, ohne Bestandsdaten zu löschen, und dokumentiert die
dadurch entstehenden fachlichen Nebenwirkungen (Nachtwerte, Sonnenanteil-Bonus)
als bewusst in Kauf genommene Known Limitations (PO-Entscheid 2026-07-16, s.
`docs/context/fix-1268-compare-dead-timewindow-fields.md`).

## Source

- **File:** `frontend/src/lib/components/compare/CompareInhaltSection.svelte`
- **Identifier:** Zeitfenster-Inputs (Z. 107-136), Horizont-Select (Z. 95-104), zugehörige Info-Kacheln (Z. 76-91), `hasTimeOverlap`-Derived (Z. 26)
- **File:** `src/services/scheduler_dispatch_service.py`
- **Identifier:** `hour_from`/`hour_to`-Lesepfad + `ComparisonEngine.run(time_window=..., forecast_hours=...)` (Z. 289-296)

> **Schicht-Hinweis:** Betrifft Frontend (`frontend/src/...`, SvelteKit) UND
> Python-Core-Backend (`src/services/...`, `src/output/renderers/...`). Kein
> Go-API-Code betroffen — der Go-Handler (`internal/handler/compare_preset.go`)
> und das Go-Model (`internal/model/compare_preset.go`) bleiben unverändert,
> da die deprecateten Felder dort weiterhin bestehen bleiben müssen.

## Estimated Scope

- **LoC:** ~-90/+20 (netto negativ — überwiegend Entfernen von UI-Code und Lesepfaden)
- **Files:** 8 Produktionsdateien (3 Backend, 5 Frontend) + 3 Testdateien
- **Effort:** medium (kleine Diffs, aber verteilt über mehrere Schichten + Scoring-Nebenwirkung, die dokumentiert werden muss)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ComparisonEngine.run()` (`src/services/comparison_engine.py`) | function | Nimmt weiterhin `time_window`/`forecast_hours` als Parameter — Signatur bleibt unverändert, nur der Dispatch-Aufrufer ändert die übergebenen Werte |
| `comparison_scoring.calculate_score()` (`src/services/comparison_scoring.py`) | function | Nutzt `window_hours` für den Sonnenanteil-Bonus (#366) — indirekt betroffen durch die neue Fensterbreite 24h |
| `internal/handler/compare_preset.go` Read-Modify-Write (Z. 349-357) | Go handler | Bestandsschutz für `forecast_hours`/`hour_from`/`hour_to` bleibt unverändert — Frontend schickt die Felder künftig einfach nicht mehr mit |
| `docs/specs/modules/issue_1256_compare_ui_rewire.md` | spec | Ursprüngliche (fehlinterpretierte) PO-Korrektur-Referenz — dieser Spec korrigiert/konkretisiert Constraint 2 |
| `docs/context/fix-1268-compare-dead-timewindow-fields.md` | context | PO-Entscheid vom 2026-07-16, bindend für diese Spec |

## Scope

### Affected Files

| Datei | Änderungstyp | Beschreibung |
|---|---|---|
| `src/services/scheduler_dispatch_service.py` | MODIFY | `hour_from`/`hour_to`/`preset.get("forecast_hours")`-Lesepfad entfernen; `ComparisonEngine.run()` fest mit `time_window=(0, 23)`, `forecast_hours=48` aufrufen |
| `src/output/renderers/email/compare_html.py` | MODIFY | `_render_header()`: `time_str`/`start_h`/`end_h` aus der Datumszeile entfernen (Z. 587-589); `horizont_val = "+48h"` bleibt unverändert (wird durch Fix korrekt statt hartkodiert-falsch) |
| `src/output/renderers/comparison.py` | MODIFY | Textbaustein-Zeile `f"Zeitfenster: {time_window[0]:02d}:00 - {time_window[1]:02d}:00"` entfernen (Z. 74) |
| `frontend/src/lib/components/compare/CompareInhaltSection.svelte` | MODIFY | Zeitfenster-Section (Z. 106-136), Horizont-Section (Z. 94-104), zwei zugehörige Info-Kacheln (Z. 76-91, Grid wird 2-spaltig), `hasTimeOverlap`-Derived (Z. 26) entfernen. Top-N-, Stundenverlauf-Metriken- und Inhalt-Toggle-Sections bleiben unverändert |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | State-Felder `timeWindowStart`/`timeWindowEnd`/`forecastHours` (Z. 41-43) sowie deren Aufnahme in `saveNewPreset()`-Payload (Z. 100-102) entfernen |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `forecastHours`/`hourFrom`/`hourTo` aus `CompareEditorEdits`-Interface (Z. 26, 48-51) sowie der Body-Konstruktion (Z. 136-138, 161-164) entfernen — Round-Trip-Spread aus `original` übernimmt die Bestandswerte automatisch |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY | `forecastHours` aus Dirty-Tracking-Snapshot (Z. 206-208, 238), Save-Snapshot (Z. 413) und beiden `buildComparePresetSavePayload()`-Aufrufen (Z. 456, 490) entfernen; `hourFrom`/`hourTo` aus dem Save-Aufruf (Z. 433-434) entfernen |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | MODIFY | Hydration von `timeWindowStart`/`timeWindowEnd`/`forecastHours` aus dem Preset (Z. 59-61) entfernen |
| `frontend/src/lib/utils/cockpitHelpers568.ts` | MODIFY | **AC-9 (Scope-Erweiterung, PO-go 2026-07-16):** `deriveNextSend()` liest `hour_from` (Z. 182) — den Start des Bewertungs-Fensters — statt der echten Versand-Uhrzeiten. Umstellen auf `morning_time`/`evening_time` (+ `morning_enabled`/`evening_enabled`), die laut `types.ts:304` „die einzige Wahrheit für den Versand" sind. Auflösungs-Semantik inkl. Migrations-Fallback: `src/services/compare_slot_scheduler.py::resolve_preset_slots` ist die Referenz |
| `tests/tdd/test_compare_preset_slot_dispatch.py` | MODIFY | Neuer Testfall: Dispatch ignoriert `hour_from`/`hour_to`/`forecast_hours` aus dem Preset und übergibt immer `(0, 23)`/`48` |
| `tests/tdd/test_compare_html_email.py` | MODIFY | Neuer Testfall: Mail-Kopfzeile enthält keine Uhrzeit-Angabe mehr |
| `frontend/src/lib/components/compare/__tests__/compare_layout_timewindow_removed.test.ts` | CREATE | Bug-Repro: Editor rendert keine Zeitfenster-/Horizont-Testids mehr (rot vor Fix, grün nach Fix) |
| `frontend/src/lib/components/compare/__tests__/compare_save_deprecated_fields_roundtrip.test.ts` | CREATE | AC-3 Invarianten-Test: Bestandswerte überleben den Speicher-Round-Trip |
| `tests/tdd/test_compare_dispatch_fixed_window.py` | CREATE | AC-4: Dispatch übergibt fest `(0, 23)` / `48` statt Preset-Werte |
| `tests/tdd/test_compare_sun_hours_full_day_window.py` | CREATE | AC-8 auf Engine-Ebene (s. AC-8-Verortungs-Korrektur) |

### Nicht Teil dieser Spec

- **Feature-Idee „Zusammenfassung je Ort"** (Trip-Stil-Kurztext unter den Orten) — ausgelagert nach Issue **#1278**.
- **`api/routers/compare.py`** (`GET /api/compare`, Query-Parameter `time_window_start`/`time_window_end`/`forecast_hours`) — eigenständiger Ad-hoc-Endpunkt ohne Frontend-Aufrufer (kein `fetch`-Treffer im gesamten `frontend/src`), unabhängig vom Preset-Dispatch-Pfad. Bleibt unverändert.
- **`api/routers/validator.py:305-324`** (`CompareEmailPreviewBody.time_window`) — reines Rendering-DTO für den Mail-Validator, baut nur ein `ComparisonResult` für die HTML-Vorschau. Da `ComparisonEngine.run()` und `ComparisonResult` das Feld `time_window` strukturell behalten (s. „Was darf sich NICHT ändern"), braucht dieses DTO keine Änderung — die Kopfzeile zeigt die Uhrzeit durch die Renderer-Änderung ohnehin nicht mehr an.
- **`internal/model/compare_preset.go`** / **`internal/handler/compare_preset.go`** — keine Änderung; deprecateter Datenerhalt ist bereits vorhandenes Verhalten (Read-Modify-Write).

## Implementation Details

### 1. Dispatch hardcodet statt liest (Backend)

`scheduler_dispatch_service.py` liest aktuell `preset.get("hour_from", 9)` /
`preset.get("hour_to", 16)` und reicht sie als `time_window` durch; ebenso
`preset.get("forecast_hours") or 48`. Beide Zeilen werden durch feste Literale
ersetzt:

```python
result = ComparisonEngine.run(
    locations=locations,
    time_window=(0, 23),       # Issue #1268: ganzer Tag, kein Editor-Feld mehr
    target_date=target_date,
    forecast_hours=48,          # Issue #1268: fest, kein Editor-Feld mehr
    profile=profile,
    official_alerts_enabled=preset.get("official_alerts_enabled", True),
)
```

`ComparisonEngine.run()` selbst bleibt unverändert (Signatur, `window_hours`-
Berechnung `end_hour - start_hour + 1` in `comparison_engine.py:89` — ergibt
mit `(0, 23)` automatisch `window_hours = 24`).

### 2. Mail-Kopfzeile ohne Uhrzeit

`compare_html.py::_render_header()`: `date_line` wird nur noch aus Wochentag +
Datum gebaut, ohne `time_str`. `horizont_val = "+48h"` bleibt als Zeile
unverändert stehen — durch Schritt 1 ist der Wert jetzt korrekt statt vorher
zufällig-hartkodiert.

`comparison.py` (Text-Renderer, z. B. für Klartext-Teil der Mail): Zeile
`Zeitfenster: HH:00 - HH:00` entfällt ersatzlos.

### 3. Frontend: Felder entfernen, nicht nur verstecken

Die zwei Feld-Gruppen werden aus `CompareInhaltSection.svelte` entfernt
(Markup + zugehörige `state.timeWindowStart`/`timeWindowEnd`/`forecastHours`-
Bindings + `hasTimeOverlap`-Validierung). Die Kacheln-Grid-Reihe schrumpft von
3 auf 2 Spalten (Versand + verbleibende Kachel entfällt ersatzlos — es gibt
keine Ersatz-Kachel für Zeitfenster/Horizont).

`compareWizardState.svelte.ts`: State-Runes `timeWindowStart`/`timeWindowEnd`/
`forecastHours` entfallen. `saveNewPreset()` schickt beim Anlegen eines neuen
Presets künftig **keine** `hour_from`/`hour_to`/`forecast_hours`-Keys mehr —
das Go-Backend setzt beim Create ohnehin eigene Defaults
(`internal/handler/compare_preset.go`, ForecastHours-Fallback 48).

`compareEditorSave.ts` (`buildComparePresetSavePayload`): Die drei
`edits.forecastHours`/`edits.hourFrom`/`edits.hourTo`-Zweige entfallen. Der
Spread `{ ...original, ... }` bleibt bestehen — dadurch werden die
Bestandswerte aus dem geladenen Preset unverändert zurückgeschrieben
(Read-Modify-Write via Spread, kein Löschen).

`CompareEditor.svelte`: Die drei Fundstellen, an denen `forecastHours` ins
Dirty-Tracking, den Save-Snapshot und die beiden
`buildComparePresetSavePayload()`-Aufrufe eingespeist wird, sowie die beiden
`hourFrom`/`hourTo`-Zeilen im Save-Aufruf entfallen. `topN`/`hourlyEnabled`
bleiben an allen vier Stellen unverändert (Muster-Referenz für die
Entfernung).

`+page.svelte` (Edit-Hydration): Die drei Zeilen, die
`state.timeWindowStart`/`timeWindowEnd`/`forecastHours` aus
`data.preset.hour_from`/`hour_to`/`forecast_hours` befüllen, entfallen.

### 4. Sonnenanteil-Bonus — nicht normieren, weil ohne Nutzer-Wirkung

`comparison_scoring.py:69-70` berechnet einen Sonnenanteil-Bonus (#366) als
`sunny_hours / window_hours`. Mit `window_hours = 24` statt bisher `8`
(9–16 Uhr) sinkt dieser Bruch strukturell.

**Verifiziert 2026-07-16: Dieser Bonus fließt ausschließlich in
`LocationResult.score` — und `score` wird nirgends ausgegeben.** Weder
`compare_html.py` noch `comparison.py` rendern ihn (Grep über
`src/output/renderers/`: kein Treffer); das Compare-Frontend zeigt ihn
ebenfalls nicht; die Orte werden alphabetisch sortiert
(`sort_locations_alphabetically`), nicht nach Score. Der Renderer-Docstring
hält „Kein Score/Ranking/Winner-Card" (PO 2026-07-08) fest.

**Entscheidung: nicht normieren.** Nicht weil eine Normierung zu teuer wäre,
sondern weil die Änderung **keine beobachtbare Nutzer-Auswirkung** hat. Der
Score ist heute totes Rechenwerk. Sollte er je wieder sichtbar werden, ist die
Normierung auf Tageslichtstunden Teil *jenes* Vorhabens, nicht dieses
Aufräum-Issues.

### 5. Was der Nutzer an der Mail tatsächlich sehen wird

Die Umstellung auf den ganzen Tag ändert die Werte der Vergleichs-Matrix
sichtbar — das ist die Konsequenz des PO-Entscheids und kein Fehler:

| Spalte | Vorher (9–16 Uhr) | Nachher (0–23 Uhr) |
|---|---|---|
| Tiefsttemperatur | kälteste Stunde der Tagzeit | kälteste Stunde inkl. Nacht — meist Wert vom frühen Morgen |
| Wind / Böen (Maximum) | stärkste Böe tagsüber | stärkste Böe inkl. Nacht |
| Sonne (`sunny_hours`, Spalte „Sonne (h)", `compare_html.py:126`) | Sonnenstunden im Fenster | Sonnenstunden des **ganzen Tages** (nachts DNI = 0, daher keine Scheinwerte — der Wert steigt, weil früher Morgen und später Abend hinzukommen) |
| Höchsttemperatur | wärmste Stunde tagsüber | praktisch unverändert (Maximum liegt ohnehin tagsüber) |

## Expected Behavior

- **Input:** Nutzer öffnet den Ortsvergleich-Editor (Layout-Tab) für ein
  neues oder bestehendes Preset.
- **Output:** Der Layout-Tab zeigt keine Zeitfenster-Eingabefelder und keinen
  Horizont-Select mehr; Top-N, Stundenverlauf-Metriken und die beiden
  Inhalts-Toggles bleiben sichtbar und funktionsfähig. Die tägliche
  automatische Vergleichs-Mail wertet immer den ganzen Tag (0–23 Uhr) und holt
  immer 48 h Vorhersagedaten; die Mail-Kopfzeile zeigt kein Zeitfenster mehr
  und einen korrekten, konsistenten „+48h"-Horizont.
- **Side effects:** Bestehende Presets behalten ihre gespeicherten
  `hour_from`/`hour_to`/`forecast_hours`-Werte unverändert in der Persistenz
  (deprecated, ungenutzt) — kein Datenverlust bei den 158 Bestands-Presets.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet den Ortsvergleich-Editor im Layout-Tab / When die Seite gerendert wird / Then sind weder Zeitfenster-Eingabefelder noch der Horizont-Auswahl-Select sichtbar, auch nicht als Info-Kachel.
  - Test: Component-Test rendert `CompareInhaltSection` und prüft, dass die Testids `compare-step5-time-window-start`, `compare-step5-time-window-end`, `compare-step5-forecast-hours`, `compare-step5-timewindow-tile` und `compare-step5-horizon-tile` nicht im DOM existieren.

- **AC-2:** Given der Ortsvergleich-Editor vor diesem Fix zeigte die Felder und sie hatten echten Einfluss auf die versendete Mail / When derselbe Component-Test vor dem Fix läuft / Then schlägt er fehl (rot), weil die Testids noch vorhanden sind — nach dem Fix ist er grün. Damit ist der Nutzer-Bug „verworfene Felder leben weiter" nachweislich behoben.
  - Test: `frontend/src/lib/components/compare/__tests__/compare_layout_timewindow_removed.test.ts` — identischer Test wie AC-1, wird VOR der Implementierung geschrieben und muss zunächst rot sein.

- **AC-3:** Given ein Nutzer öffnet ein bestehendes Preset mit gespeichertem Zeitfenster 10–14 Uhr und speichert die Seite ohne weitere Änderungen / When der PUT-Request an die API geht / Then enthält der Request-Body weiterhin `hour_from: 10, hour_to: 14` unverändert (Round-Trip aus dem Original-Preset, kein Nullen, kein Löschen).
  - Test: Unit-Test auf `buildComparePresetSavePayload()` mit einem Fixture-Preset (`hour_from: 10, hour_to: 14`) und `edits` ohne `hourFrom`/`hourTo`-Felder — Assertion, dass `body.hour_from === 10` und `body.hour_to === 14`.

- **AC-4:** Given ein automatisch versendetes Vergleichs-Preset mit beliebigem gespeichertem `hour_from`/`hour_to` / When der tägliche Dispatch (`run_compare_presets_daily`) läuft / Then wird `ComparisonEngine.run()` unabhängig vom Preset-Wert mit `time_window=(0, 23)` aufgerufen.
  - Test: `tests/tdd/test_compare_preset_slot_dispatch.py` — Fixture-Preset mit `hour_from=10, hour_to=14`, Assertion auf die tatsächlich übergebenen `time_window`-Argumente des `ComparisonEngine.run()`-Aufrufs.

- **AC-5:** Given eine Vergleichs-Mail wird für ein beliebiges Preset erzeugt / When der Nutzer die Kopfzeile liest / Then enthält weder die Datums-/Zeitzeile noch der Klartext-Textblock eine Uhrzeit-Angabe (z. B. „09:00 – 16:00").
  - Test: `tests/tdd/test_compare_html_email.py` — Assertion, dass das gerenderte HTML kein `Uhrzeit`-Zeitfenster-Muster mehr enthält, und ein analoger Test auf `render_compare_email()` (Text-Renderer) ohne „Zeitfenster:"-Zeile.

- **AC-6:** Given eine Vergleichs-Mail wird erzeugt / When der Nutzer die Kopfzeile-Kachel „Horizont" liest / Then zeigt sie „+48h" — konsistent mit den tatsächlich abgerufenen 48 Vorhersagestunden, unabhängig vom früher im Preset gespeicherten Horizont-Wert.
  - Test: erweitert `tests/tdd/test_compare_html_email.py` — Assertion auf `+48h` im Header unabhängig vom `forecast_hours`-Wert im übergebenen `ComparisonResult`.

- **AC-7:** Given Top-N-Auswahl, Stundenverlauf-Metriken-Checkboxen und die beiden Inhalt-Toggles (amtliche Warnungen, Stundenverlauf) im Layout-Tab / When der Nutzer den Editor nach diesem Fix öffnet / Then sind diese Felder weiterhin sichtbar, editierbar und lösen weiterhin `dirty`/Speichern korrekt aus (unverändertes Verhalten).
  - Test: bestehender Component-/E2E-Test (`compare-step5-topn`, `compare-step5-hourly-metrics`, `compare-step5-official-alerts-toggle`, `compare-step5-hourly-enabled-toggle`) bleibt grün, keine Regression.

- **AC-8:** Given ein Ort, an dem es zwischen 6 und 9 Uhr sowie zwischen 16 und 20 Uhr sonnig ist / When die automatische Vergleichs-Mail nach diesem Fix erzeugt wird / Then zählt die Spalte „Sonne" auch diese Stunden mit und weist damit die Sonnenstunden des ganzen Tages aus, nicht nur die eines Fensters.
  - Test: `tests/tdd/test_compare_sun_hours_full_day_window.py` — aufgezeichnetes Stundenprofil mit Sonne nur 6–8 und 17–19 Uhr; Assertion auf Engine-Ebene (`(9,16)` → 0.0 h, `(0,23)` → 6.0 h) plus ein Test durch den echten Dispatch (der rote).
  - **Verortungs-Korrektur (2026-07-16):** Ursprünglich war dieser AC im Mail-Renderer (`test_compare_html_email.py`) verortet. Dort ist er wertlos — der Renderer formatiert `sunny_hours` nur aus einem fertigen `LocationResult`, ein solcher Test spiegelt die eigene Fixture-Zahl zurück und wäre vor **und** nach dem Fix grün. Er kann den Bug nicht fangen. Getestet wird deshalb, wo der Wert entsteht: Engine-Filter → `calculate_sunny_hours`.

- **AC-9:** Given ein Vergleich, dessen Versand auf 07:00 eingestellt ist / When der Nutzer die Startseite, den Vergleichs-Hub oder die Status-Zeile ansieht / Then zeigt „Nächster Versand" die tatsächliche Versandzeit 07:00 — und nicht mehr den Startwert des früheren Bewertungs-Zeitfensters. Für einen neu angelegten Vergleich zeigt die Anzeige ebenfalls die echte Versandzeit, niemals „00:00".
  - Test: Unit-Test auf `deriveNextSend()` (`frontend/src/lib/utils/cockpitHelpers568.ts`) mit Fixture-Presets: (a) `morning_time: "07:00:00"`, `hour_from: 9` → Ergebnis 07:00, nicht 09:00; (b) Preset ohne `hour_from` (neu angelegt) mit `morning_time: "07:00:00"` → 07:00, nicht 00:00; (c) Abend-Slot; (d) `schedule: "manual"` → weiterhin `null`.
  - Bug-Repro-Charakter: Fall (a) ist vor dem Fix rot (liefert 09:00), Fall (b) ist die verhinderte Regression.

- **AC-10:** Given ein neu angelegter täglicher Vergleich mit Versand um 07:00 / When der Nutzer die Vergleichs-Liste (Kachel) oder die Startseite ansieht / Then zeigen beide Flächen die echte Versandzeit — niemals „tägl. 00" oder „· 00:00".
  - Test: Unit-Test auf `presetTileScheduleLabel()` (`subscriptionHelpers.ts:180`) mit Preset ohne `hour_from`, `morning_time: "07:00:00"` → Label nennt 07, nicht 00. Der Startseiten-Hero (`routes/+page.svelte:485`) nutzt dieselbe Ableitung.
  - Herkunft: Adversary-Fund F002. Gleiche Bug-Klasse wie AC-9, weitere Fundstellen.

- **AC-11:** Given ein Vergleich, für den der Nutzer im Hub die Vorschau öffnet / When die Vorschau gerendert wird / Then zeigt sie denselben Zeitraum, den der echte Versand verwendet (ganzer Tag) — und nicht ein aus `hour_from`/`hour_to` gebautes Fenster, das bei neuen Vergleichen 0–0 Uhr wäre und die Vorschau leer liefe.
  - Test: `tests/tdd/test_compare_preview_service.py` — der Vorschau-Dienst ruft `ComparisonEngine.run()` mit `time_window=(0, 23)` und `forecast_hours=48` auf, unabhängig von den Preset-Werten.
  - **Verortungs-Korrektur (2026-07-16, nach Rebase auf `origin/main`):** Ursprünglich war dieser AC im Frontend verortet (`CompareTabs.svelte:619` schickte `time_window: [preset.hour_from, preset.hour_to]` an den Validator-Stub). Der parallel gemergte **#1270** („Echte Compare-Vorschau") hat diesen Aufruf durch `/api/preview/compare/{id}` ersetzt — die Frontend-Fundstelle existiert nicht mehr, unsere dortige Änderung wurde beim Rebase zugunsten von #1270 verworfen. **Der Bug ist dabei nicht verschwunden, sondern ins Backend gewandert:** `src/services/compare_preview_service.py:143` übernahm den `hour_from`/`hour_to`-Lesepfad **wörtlich aus dem alten Dispatch-Code** (inkl. Defaults 9/16), den diese Spec dort gerade entfernt. AC-11 wird daher am neuen Ort erfüllt. Der Kern des AC ist unberührt: Die Vorschau muss zeigen, was tatsächlich verschickt wird.
  - Herkunft: Vom Orchestrierer beim Gegenlesen des Adversary-Berichts gefunden. **Diese Stelle nennt Issue #1268 wörtlich** („Vorschau-Call füttert weiter `time_window` (`CompareTabs.svelte:606-607`)") — die ursprüngliche Spec hatte sie übersehen, weil sie nur das Validator-DTO (`api/routers/validator.py`) betrachtete und den Frontend-Aufrufer nicht.

## Known Limitations

- **Nachtwert-Verzerrung (PO ausdrücklich akzeptiert):** Da die Bewertung
  jetzt über den ganzen Tag (0–23 Uhr) läuft statt über ein Tageslicht-Fenster
  (z. B. 9–16 Uhr), zeigen die Spalten Tiefsttemperatur und Böen künftig
  Nachtwerte, die für eine Tagesaktivität nicht relevant sind. Konkret: Wer
  zwei Orte für einen Tagesausflug vergleicht, sieht bei „Tiefsttemperatur"
  den Wert vom frühen Morgen und bei „Böen" einen nächtlichen Sturm. Der PO hat
  dies nach Vorlage des Gegenarguments ausdrücklich in Kauf genommen
  (PO-Entscheid 2026-07-16, s. Context-Dokument). **Dies ist die zentrale
  bewusste Verschlechterung dieser Spec** — sie ist gewollt, nicht übersehen.
- **Spalte „Sonne" ändert ihre Bedeutung:** Sie zeigt künftig die
  Sonnenstunden des ganzen Tages statt der des Fensters (Werte steigen). Keine
  Falschwerte — nachts ist DNI = 0 —, aber eine andere Aussage als bisher.
- **Sonnenanteil-Bonus im `score`:** rechnet jetzt gegen 24 statt 8 Stunden.
  **Ohne Nutzer-Auswirkung**, da `score` weder in der Mail noch im Frontend
  ausgegeben wird (verifiziert, s. Implementation Details Punkt 4). Bewusst
  nicht angefasst.
- **Versandzeit-Genauigkeit wird sichtbar unehrlich (→ #1280, PO entschieden):**
  Weil die Anzeige seit AC-9/AC-10 die **echte** Versandzeit zeigt, fällt nun auf,
  dass die Oberfläche Minuten annimmt (`VTSchedulePlan.svelte:86,111` — `<input
  type="time">` ohne `step`), der Versand aber nur volle Stunden auswertet
  (`compare_slot_scheduler.py:96,98` vergleicht `.hour`; Go-Cron tickt stündlich).
  Ein auf 07:30 gestellter Versand geht im 07:00-Lauf raus. **Vorbestehend, nicht
  von dieser Spec verursacht** (`compare_slot_scheduler.py` im Diff unberührt;
  identisches Muster beim Trip: `trip_report_scheduler.py:375,381`) — durch diesen
  Fix aber erstmals sichtbar. Vorher zeigte die Anzeige ohnehin eine falsche Zeit,
  insofern ist der Zustand jetzt besser, aber noch nicht ehrlich. PO-Entscheid
  2026-07-16: Eingabe auf volle Stunden begrenzen — ausgelagert nach **#1280**,
  weil es Trip mitbetrifft (geteilte Komponente), Bestandsdaten mit krummen Zeiten
  eine Umstellung brauchen und die Anzeige dann zwischen geplantem (volle Stunde)
  und tatsächlich erfolgtem Versand (minutengenau) trennen muss.
- **158 Bestands-Presets tragen weiterhin `hour_from`/`hour_to`/
  `forecast_hours`** in ihrer Persistenz — diese Felder werden nicht gelöscht,
  aber im Dispatch-Pfad nicht mehr gelesen. Ein zukünftiges Daten-Cleanup
  müsste sie explizit migrieren; ist nicht Teil dieser Spec.
- **`GET /api/compare`** und die Validator-Preview-DTO
  (`CompareEmailPreviewBody.time_window`) behalten ihre Query-Parameter/Felder
  unverändert — sie sind unabhängig vom Editor/Dispatch-Pfad (s.
  „Nicht Teil dieser Spec").

## Was darf sich NICHT ändern (Invarianten)

1. **Bestandsdaten:** Die 158 gespeicherten Presets mit `hour_from`/`hour_to`/
   `forecast_hours` dürfen beim Speichern über den Editor nicht auf `0`/`null`
   fallen oder verschwinden — Round-Trip via `{ ...original, ... }`-Spread in
   `compareEditorSave.ts` bleibt der einzige Schreibmechanismus.
2. **Trip-Pfad unberührt:** Kein Trip-Editor-, Trip-Dispatch- oder
   Trip-Mail-Code wird durch diese Spec angefasst — das Zeitfenster/der
   Horizont existieren beim Trip als UI-Konzept ohnehin nicht (s. Context,
   „Existing Patterns").
3. **Top-N, Stundenverlauf-Metriken-Auswahl, `official_alerts_enabled`- und
   `hourly_enabled`-Toggle** in `CompareInhaltSection.svelte` bleiben
   unverändert bestehen — die Komponente wird NICHT gelöscht, nur um zwei
   Feld-Gruppen reduziert.
4. **`ComparisonEngine.run()`-Signatur** (`time_window`, `forecast_hours` als
   Parameter) bleibt unverändert — nur `scheduler_dispatch_service.py` als
   einziger Preset-Dispatch-Aufrufer ändert, welche Werte es übergibt.
5. **Go-Modell/-Handler** (`internal/model/compare_preset.go`,
   `internal/handler/compare_preset.go`) bleiben unverändert.
   **KORREKTUR 2026-07-16 (Adversary-Fund F003 — die ursprüngliche Begründung
   war sachlich falsch):** Behauptet war, ein „bestehender Read-Modify-Write-
   Schutz für `ForecastHours`/`HourFrom`/`HourTo`" reiche aus. Tatsächlich
   schützt `compare_preset.go:349-357` **nur `ForecastHours`**; `HourFrom`/
   `HourTo` sind einfache `int` (`compare_preset.go:27-28`), kein Pointer, kein
   RMW-Zweig — ein PUT ohne diese Felder überschreibt sie mit 0. Der
   Bestandsschutz für die 158 Alt-Presets hängt damit **allein** am
   `{ ...original, ... }`-Spread im Frontend; eine Verteidigung in der Tiefe
   gibt es nicht. Das bleibt so (Go-Änderung wäre eigener Scope), wird aber
   durch einen Full-Stack-Test gegen den echten Go-Server abgesichert
   (Adversary-Fund F004) statt nur durch einen Unit-Test auf die reine
   Payload-Funktion. Konsequenz für später: Wer den Spread anfasst, bricht den
   Datenschutz ohne Netz — der Test ist die einzige Warnung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Entfernen von zwei UI-Feldern und deren
  Preset-Dispatch-Lesepfad, keine neue Architektur-Komponente, kein neuer
  Persistenz-Mechanismus. Die einzige nicht-triviale Entscheidung (Sonnenanteil-
  Bonus-Normierung) wird in dieser Spec (Implementation Details Punkt 4)
  begründet getroffen und nicht in ein ADR ausgelagert, da sie kein
  strukturelles Architektur-Muster einführt, sondern eine bewusste
  Nicht-Handlung dokumentiert.

## Changelog

- 2026-07-16: Initial spec erstellt — Issue #1268, PO-Entscheid vom selben Tag
- 2026-07-16: Fakten-Korrektur (Orchestrierer, vor Freigabe): Die Behauptung, der
  Sonnenanteil-Bonus sei eine relevante Known Limitation, hielt der Prüfung nicht
  stand — `score` wird nirgends ausgegeben (Grep über `src/output/renderers/`,
  Compare-Frontend, `sort_locations_alphabetically`), die Auswirkung ist damit
  für den Nutzer null. Die Begründung „Normierung unverhältnismäßig teuer" wurde
  durch die tatsächliche Begründung „ohne beobachtbare Wirkung" ersetzt. Neu
  aufgenommen: Implementation Details Punkt 5 (Tabelle der tatsächlich sichtbaren
  Mail-Änderungen) und AC-8, da die sichtbare Änderung der Spalte „Sonne" zuvor
  in keinem AC stand.
- 2026-07-16: Nach RED-Phase — AC-8-Verortung korrigiert (Befund des Developer
  Agents, nicht der Spec): Renderer-Ebene kann den Bug strukturell nicht fangen,
  Test wandert auf Engine-Ebene. Test-Dateiliste um die vier tatsächlich
  angelegten Dateien ergänzt. AC-Wortlaut unverändert.
- 2026-07-16: Test-Werkzeug-Hinweis: Das Frontend hat **kein vitest/jsdom**
  (`package.json` → `node --experimental-strip-types --test`). Der AC-1/AC-2-Test
  prüft daher den Template-AST über den echten Svelte-5-Compiler statt per
  DOM-Mount — struktureller Nachweis über das Renderbare, ausdrücklich **kein**
  Dateiinhalt-Grep (der wäre nach CLAUDE.md als Verhaltensnachweis unzulässig).
  Das echte DOM deckt die Staging-Validierung ab.
- 2026-07-16: **Scope-Erweiterung um AC-9 — PO ausdrücklich zugestimmt** (Frage
  im Workflow gestellt und mit „In #1268 mitbeheben" beantwortet). Befund des
  Developer Agents in der GREEN-Phase, vom Orchestrierer verifiziert:
  `deriveNextSend()` (`cockpitHelpers568.ts:182`) berechnet die Anzeige
  „Nächster Versand" auf Startseite, Hub und Status-Zeile aus `hour_from` statt
  aus den Versand-Slots. **Zwei Gründe für die Aufnahme:** (1) Bestehender,
  nutzersichtbarer Fehler — die Anzeige weicht schon heute vom tatsächlichen
  Versand ab (zeigt 09:00 statt 07:00), seit die Slot-Felder mit #1232 Scheibe 2a
  die Versand-Wahrheit wurden. (2) **Von dieser Spec verursachte Regression:**
  Da der Wizard `hour_from` künftig nicht mehr mitschickt, legt der Go-Handler
  neue Presets mit `HourFrom = 0` an (kein Default, Zero-Value; validate erlaubt
  0) — die Anzeige behauptete dann „Nächster Versand: 00:00". Ein Fix, der eine
  neue Falschanzeige einführt, ist kein Aufräumen. Beides wird durch die
  Umstellung auf die Slot-Felder gemeinsam behoben.
- 2026-07-16: **Adversary-Verdict BROKEN — Fix-Loop 1.** Befunde und Folgen:
  - **F002 → AC-10 (neu):** AC-9 hat nur `cockpitHelpers568.ts` repariert. Zwei
    weitere *live* Flächen lesen `hour_from` und zeigen bei neuen Presets
    „tägl. 00" (`subscriptionHelpers.ts:182`, gerendert über `CompareTile.svelte:68`
    auf `/compare`) bzw. „· 00:00" (`routes/+page.svelte:485`, Startseite) —
    direkt neben der korrekt reparierten Kachel.
  - **→ AC-11 (neu), Fund des Orchestrierers beim Gegenlesen:** Der Vorschau-Call
    (`CompareTabs.svelte:619`) schickt `time_window: [preset.hour_from, preset.hour_to]`
    → bei neuen Presets `[0, 0]`, die Vorschau liefe leer. **Issue #1268 nennt
    genau diese Stelle wörtlich**; die Erst-Spec hat sie übersehen, weil sie nur
    das Validator-DTO prüfte und den Frontend-Aufrufer nicht verfolgte.
  - **F003 → Invariante 5 korrigiert:** Die Spec behauptete einen Go-seitigen
    RMW-Schutz für `HourFrom`/`HourTo`, den es nicht gibt. Sachlich falsch,
    berichtigt.
  - **F001:** `tests/tdd/test_issue_764_compare_forecast_hours_consume.py:143`
    schreibt das Vor-#1268-Verhalten fest und ist rot — Kern-Suite muss 100 %
    grün sein.
  - **F004:** Der gelöschte E2E-Test war der einzige Beweis, dass der
    Bestandsschutz gegen den **echten** Go-Server hält; der Unit-Ersatz prüft nur
    die reine Funktion. Zusammen mit F003 stand AC-3 damit ohne echten Nachweis.
  - **F005 (kein Fix, → #1199):** `presetScheduleLabel` (`subscriptionHelpers.ts:28`,
    „Täglich 0–0 Uhr") und `frontend/src/lib/components/compare/SavePresetDialog.svelte`
    (eigene hour_from/hour_to-Inputs) lesen die Felder ebenfalls — beide sind
    nachweislich toter Code (nirgends eingebunden, nur von Tests referenziert).
    Kein Nutzer-Effekt, daher hier nicht angefasst.
- 2026-07-16: **Adversary Runde 2 BROKEN → Fix-Loop 2.**
  - **F006:** `tests/tdd/test_metric_format_slice5_comparison.py:32` — Golden-String
    hielt `"Zeitfenster: 08:00 - 16:00"` wörtlich fest, rot durch die AC-5-Entfernung
    in `comparison.py:73`. Der Datei-Header erlaubt Änderungen ausdrücklich bei einer
    „bewussten, PO-freigegebenen Verhaltensaenderung" — AC-5 ist genau das; Golden
    sonst zeichengleich, ankert weiter die #1214-Migration.
  - **F007:** `subscriptionHelpers.ts:45-49` — `formatNextSend()` schrieb die Minuten
    hart als `:00`. Korrekt, solange die Zeit aus `hour_from` kam (immer volle
    Stunde); seit AC-9 kommt sie aus `morning_time`/`evening_time` und kann `07:30`
    sein. Folge wäre ein Widerspruch **innerhalb eines Satzes** gewesen:
    `CompareTabs.svelte:137` hätte „Briefings Morgen 07:30 · nächster Versand 07:00"
    gerendert, da `presetBriefingTimesLabel` bereits echte Minuten ausgibt. Behoben;
    Test mit 07:30-Fixture, weil alle bisherigen AC-9/AC-10-Fixtures nur volle
    Stunden nutzten und die Lücke deshalb durchrutschte.
  - **Nebenbefund, mitbehoben:** Dieselbe `:00`-Verkürzung traf `letzter_versand`
    (`_home/cockpitHelpers.ts:223`) — einen **echten** Versand-Zeitstempel. Ein
    Versand um 06:03 wurde als „06:00" ausgewiesen. Vorbestehend falsch, jetzt
    korrekt; per Test festgehalten.
  - **Methodik-Lehre (Developer, selbst offengelegt):** Die zuvor als „erschöpfend"
    gemeldete Fundstellen-Suche war über den **falschen Suchraum** erschöpfend —
    reiner Identifier-Grep findet strukturell weder einen Golden-String (enthält
    `Zeitfenster:`, aber keinen Identifier) noch eine Format-Annahme (hartes `:00`).
    Die Suche nach **Bug-Klassen** statt Bezeichnern führte direkt zum #1280-Befund.
- 2026-07-16: **Adversary Runde 3: AMBIGUOUS** — keine offenen Defekte. F006/F007
  bestätigt behoben, AC-1…AC-11 gegen den Code stichprobenartig belegt, keine neuen
  Fundstellen. Zwei Beweislücken bleiben und sind **ausdrücklich der Staging-Stufe
  zugewiesen**: (1) der vollständige `pytest tests/tdd`-Lauf bricht in der Sandbox
  ohne Live-Dienste ab, (2) `compare-legacy-fields-survive-save.spec.ts` — der
  einzige echte Nachweis für den AC-3-Round-Trip gegen den Go-Server — braucht ein
  laufendes Backend. Beides gehört ohnehin nach Staging, nicht in den Code-Adversary.
  Die vom Adversary angemahnte Doku-Lücke (Sichtbarkeit des #1280-Befunds) ist mit
  dem obigen Known-Limitations-Eintrag geschlossen.
- 2026-07-16: **Rebase auf `origin/main` (10 Commits) — Scope-Nachzug durch #1270.**
  Der parallel entstandene #1270 („Echte Compare-Vorschau + Telegram/SMS-Versand")
  kollidierte fachlich mit dieser Spec. Zwei Nachzüge, beide innerhalb der bereits
  freigegebenen ACs — keine neue PO-Entscheidung nötig:
  - **AC-11 wandert ins Backend** (s. Verortungs-Korrektur am AC selbst). #1270 hat
    den `hour_from`/`hour_to`-Lesepfad **wörtlich aus dem alten Dispatch** nach
    `compare_preview_service.py:143` kopiert — inklusive der Defaults 9/16 —, während
    diese Spec ihn dort entfernte. Der RED-Beweis bestätigte die Folge: Die Vorschau
    übergab `(0, 0)` und wäre bei neu angelegten Vergleichen leer geblieben. Jetzt
    fest `(0, 23)`/`48`, analog Dispatch.
  - **AC-5 gilt auch für die neuen Kanäle:** #1270 brachte `render_compare_telegram`
    und `render_compare_sms`; beide druckten das Zeitfenster in den Kopf — nach diesem
    Fix „Zeitfenster: 00:00 - 23:00" bzw. „00-23h:", also eine Nicht-Information. Bei
    SMS zusätzlich teuer (harte 160-Zeichen-Grenze; 8 Zeichen für echte Messwerte
    gewonnen). Entfernt. Die #1270-Overflow-Tests mussten **nicht** angepasst werden —
    sie leiten den Kopf dynamisch ab und sichern Überlauf-Ehrlichkeit, nicht das
    Kopf-Format.
  - **Lehre:** Beide Nachzüge entstanden durch **kopierten statt geteilten Code** —
    ein Fix an einer Stelle heilt die Kopie nicht, der Bug wandert mit. Vgl. CLAUDE.md
    „Code-Duplikate konsolidieren: eine Quelle, Rest Thin-Wrapper".
