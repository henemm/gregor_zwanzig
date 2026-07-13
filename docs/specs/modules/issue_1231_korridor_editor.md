---
entity_id: issue_1231_korridor_editor
type: feature
created: 2026-07-12
updated: 2026-07-12
status: draft
version: "1.0"
tags: [corridor-editor, alerts, compare, trip-editor, migration, epic-29]
---

<!-- Issue #1231 — Phase 1 von Epic #29 (Briefing-Abo-Chassis): Korridore.
     AC-Übertrag aus #1232 (Kommentar 2026-07-12) ist eingearbeitet. -->

# Issue 1231 — Wertebereiche-Editor (Korridore): Alerts + Idealwerte vereinen

## Approval

- [x] Approved — PO Henning, getipptes „go" 2026-07-12 (inkl. bewusster Abnahme der zwei Known-Limitations-Punkte: notify nur an/aus statt 4 Stufen; range im route-Kontext ohne Live-Trigger-Wirkung)

## Purpose

Zwei bisher getrennte Konzepte — Trip-Alert-Schwellwerte (Empfindlichkeit je
Metrik, Δ-Wächter seit #817) und Vergleichs-Idealbereiche (Slider je Metrik,
#1191) — bekommen **eine** gemeinsame Datenstruktur (`Corridor`) und **einen**
gemeinsamen Editor-Organism (`CorridorEditor`/`CorridorEditorMobile`). Ein
Wertebereich (`range: [min|null, max|null]`) trägt zwei unabhängig
kombinierbare Wirkungen: `notify` (warnen, wenn ein Wert den Bereich
verlässt) und `mark` (im Briefing markieren, solange ein Wert im Bereich
liegt). User-facing Label ist „Wertebereich(e)"; der Code-/Datenterm bleibt
`corridor`.

## Source

> Schicht-Hinweis (Template-Pflicht): Diese Spec deckt **alle drei Schichten**
> ab — Frontend (`frontend/src/lib/...`, SvelteKit), Go-API (`internal/model/`)
> und Python-Core (`src/app/`, `src/services/`, `src/output/renderers/email/`).
> Aufteilung nach Schicht + Slice steht in der Scope-Tabelle unten.

- **File (Design-Referenz, verbindlich):** `claude-code-handoff/current/jsx/corridor-editor.jsx` (Desktop) und `claude-code-handoff/current/jsx/corridor-editor-mobile.jsx` (Mobile)
- **Identifier:** `CorridorEditor`, `CorridorEditorMobile`, `corridorInside()`, `corridorFmt()`

## Estimated Scope

- **LoC:** ~1300–1450 gesamt, verteilt auf 7 Slices (je ≤250 LoC, eigene Workflows analog #1232)
- **Files:** ~19 (Neuanlagen + Änderungen), s. Scope-Tabelle
- **Effort:** high (cross-layer: Go + Python + Svelte, Migration, Renderer-Gate #811)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/trip.go::AlertRule`, `AlertableMetrics`, `SyncAlertRules` | Go-Modul | bestehender Δ-Wächter-Mechanismus, bleibt unverändert Wirkungsträger für `notify` (PO-A) |
| `frontend/.../alertMetricTable.ts::metric_alert_levels` (`display_config`) | FE-Modul | Empfindlichkeitsstufen je Metrik (off/entspannt/standard/sensibel) — `notify` steuert nur off↔nicht-off |
| `src/services/weather_change_detection.py` | Python-Modul | konsumiert `AlertRule`/`metric_alert_levels`, unverändert |
| `docs/specs/modules/issue_1191_compare_alert_deactivated_metric.md` | Spec | #1191-Erhalt: `active_metrics` mit bewusst leerer Liste `[]` darf die Migration nicht reaktivieren |
| `src/services/comparison_scoring.py::calculate_score()` | Python-Modul | C1-Grenze: `mark` darf hier NICHT andocken (Neutralität, #1229 parallel offen) |
| `src/app/metric_catalog.py::selectable` | Python-Modul | `confidence_pct` (`selectable=False`) darf im Korridor-Metrikpool nie auftauchen (#710) |
| `.claude/hooks/renderer_mail_gate.py` (#811) | Gate | greift auf Slice 7 (`compare_html.py`), Pflicht: `tests/tdd/test_issue_811_mode_matrix.py` grün + `briefing_mail_validator.py`-Lauf vor Commit |
| `scripts/migrate_1191_compare_active_metrics.py`, `scripts/migrate_946_alert_levels.py` | Skripte | strukturelles Vorbild für `migrate_1231_corridors.py` (Dry-Run-Default, `--execute`, tar.gz-Backup, Idempotenz, Read-Modify-Write) |

## Implementation Details

### Datenmodell (Slice 1)

```ts
interface Corridor {
  metric: string;                         // kontextabhängige Metrik-ID, s. „Metrik-Namensräume"
  range: [number | null, number | null];  // [min, max]; C2: einseitig offen erlaubt
  notify: boolean;                        // steuert bestehenden Δ-Wächter (an/aus), KEINE neue Schwelle
  mark: boolean;                          // markiert im Briefing, solange corridorInside(v)===true
  prio?: "hoch" | "mittel" | "niedrig";   // C1: NUR Anzeige-Reihenfolge, kein Rang/Score
}
// Defaults beim Anlegen: context=route → notify=true, mark=false
//                        context=vergleich → notify=false, mark=true
```

Go-Pendant additiv in `internal/model/trip.go` (`Trip.Corridors []Corridor`)
und `internal/model/compare_preset.go` (`ComparePreset.Corridors []Corridor`),
jeweils `json:"corridors"` (OHNE omitempty, analog `alert_rules` — Go bleibt
konsistent zu Python, das `corridors` immer emittiert) — **additiv neben** `AlertRules`/
`DisplayConfig["ideal_ranges"]`, die bis zu einem späteren, hier nicht
enthaltenen Cutover die technische Wahrheit für den Δ-Wächter bleiben (s.
„Sync-Brücke" unten). Python-Pendant als Dataclass in `src/app/models.py`
analog `AlertRule` (Zeile ~807).

### C5 · `corridorInside()` — Single-Source (verbatim aus `corridor-editor.jsx`)

```js
function corridorInside(value, min, max) {
  if (value == null) return null;               // kein Messwert → neutral
  if (min != null && value < min) return false; // unter dem Korridor
  if (max != null && value > max) return false; // über dem Korridor
  return true;                                  // im Korridor
}
```

Diese Funktion (plus `corridorFmt()`) wird **wortgleich** an drei Stellen
gebraucht und darf nur EINMAL implementiert sein:
1. FE-Util `frontend/src/lib/components/shared/corridor-editor/corridorMatch.ts` — ersetzt
   `shared/layout-tab/ltIdealRange.ts::isIdealGood()` (bisheriges
   Fast-Duplikat mit Demo-Fallback; Call-Sites auf `corridorInside` umziehen).
2. Editor-Live-Vorschau (`CorridorPreviewChips`, Slices 3–5).
3. Python-Port `src/services/corridor_match.py` (Slice 1, für den
   Mail-Renderer in Slice 7 — `value == None → None`, `<`/`>` exklusiv, keine
   `<=`/`>=`, identisch zur JS-Fassung).

### Metrik-Namensräume (bleiben in Phase 1 getrennt)

`Corridor.metric` nutzt **kontextabhängig** zwei unterschiedliche,
bestehende Metrik-ID-Räume — keine Vereinheitlichung in Phase 1:

| context | Metrik-IDs | Quelle |
|---|---|---|
| `route` | `wind_gust`, `precipitation_sum`, `temperature_min`, `temperature_max`, `thunder_level`, `snow_line` (6) | `internal/model/trip.go::AlertableMetrics` |
| `vergleich` | `temp_max_c`, `temp_min_c`, `wind_max_kmh`, `gust_max_kmh`, `precip_sum_mm`, `thunder_level_max`, `visibility_min_m`, `snow_new_sum_cm`, `cape_max_jkg`, `freezing_level_m` (10) | `scripts/migrate_1191_compare_active_metrics.py::FULL_METRIC_SET` |

`confidence_pct` ist in KEINEM der beiden Räume enthalten und darf im
CorridorEditor-Metrikpool (`CORRIDOR_SEED`/`CORRIDOR_POOL`) nie auftauchen
(ADR-0005, #710).

### Sync-Brücke `notify` ↔ bestehender Δ-Wächter (PO-A, verbindlich)

`corridor.notify` ist ein reiner an/aus-Schalter, KEINE neue
Trigger-Schwelle. Beim Speichern im CorridorEditor:
- `notify: true` → `display_config.metric_alert_levels[metric]` wird auf die
  zuletzt bekannte Stufe zurückgesetzt (Default `"standard"`, falls nie
  gesetzt).
- `notify: false` → `metric_alert_levels[metric] = "off"`.
- Die Stufen-Feinwahl (`entspannt`/`standard`/`sensibel`) ist im
  CorridorEditor NICHT einzeln wählbar (Known Limitation) — der gespeicherte
  Stufenwert bleibt beim Wieder-Einschalten erhalten (kein Datenverlust).
- Die `range`-Zahlen des `route`-Korridors sind in Phase 1 **reine
  Anzeige-Geometrie** (Vorschau-Band + Referenzwert aus der Migration) und
  verändern NICHT die Δ-Sensitivität — diese bleibt vollständig im
  bestehenden Mechanismus (`weather_change_detection.py`, unverändert).

### Migration (Slice 2) — `scripts/migrate_1231_corridors.py`

Vorbild: `migrate_1191_compare_active_metrics.py` (Dry-Run-Default,
`--execute`, tar.gz-Backup, Idempotenz-Check, Read-Modify-Write-Merge).

- **Trip-Alerts → `corridors[notify]`:** je `AlertRule` (Kind=delta, aktuell
  einzige Kind nach #817) wird ein `Corridor{metric, range:[null,threshold]`
  oder `[threshold,null]` je Metrik-Richtung`, notify: metric_alert_levels[metric] != "off", mark:false}`
  erzeugt. `metric_alert_levels="off"` bleibt als `notify:false` erhalten
  (Korridor bleibt bestehen, inaktiv) — KEIN Verlust der Deaktivierung.
- **Compare-Idealwerte → `corridors[mark]`:** je Eintrag in
  `display_config["ideal_ranges"]` wird `Corridor{metric, range:[min,max], notify:false, mark:true}`
  erzeugt; einseitige Idealwerte behalten die offene Gegenseite (C2).
- **#1191-Erhalt (hart):** `display_config["active_metrics"]` wird von der
  Migration NICHT verändert; eine bewusst leere `[]` bleibt leer. Migrierte
  Metriken, die nicht in `active_metrics` enthalten sind, bekommen dennoch
  einen `Corridor`-Eintrag (Datenerhalt), aber der Editor zeigt nur
  aktivierte Metriken (bestehendes Verhalten aus #1191 unverändert).
- **Report:** Zeile je migrierter Regel/Idealwert (`alt → neu`); nicht
  1:1-abbildbare Fälle brechen den Lauf ab (kein Teil-Commit) — laut C4
  dürfen solche Fälle nicht auftreten.

### CorridorEditor / CorridorEditorMobile (Slices 3–5)

Ein Organism (`context="route"|"vergleich"`), Port aus
`corridor-editor.jsx`/`corridor-editor-mobile.jsx` nach Svelte 5 (Runes,
analog bestehender Shared-Organismen aus #1232). Ersetzt:
- **Trip · Alerts-Tab:** `alerts-tab/AlertsTab.svelte` +
  `AlertMetricLevelTable.svelte` (+`AlertMetricLevelRow.svelte`) — DELETE nach
  Cutover. Zustell-Controls (Kanäle/Cooldown/Stille Stunden/Beispiel) bleiben
  unverändert in `shared/VersandTab.svelte` (bereits durch #1232 dorthin
  umgezogen) — auf Mobile über den `footer`-Slot von `CorridorEditorMobile`.
- **Compare · Idealwerte-Tab (BEIDE Stellen, PO-B):**
  `compare/steps/Step3Idealwerte.svelte` — DELETE. Ersetzt sowohl im
  Compare-**Wizard** Step 3 als auch im **CompareEditor**-Tab
  (`CompareEditor.svelte:690,854`).

**Explizit NICHT gebaut (PO-C, obwohl im selben JSX-File vorhanden):**
`AlertChannelPicker`, `alertChannels[]`-Feld, `ChannelRow`-Wiring für Alerts.
Alert-Kanäle bleiben die bestehende Trip-Kanalwahl; Vergleichs-Briefings
bleiben E-Mail-only ohne Kanal-Auswahl. `CompareEndDateControl(Mobile)` aus
derselben JSX-Datei ist Phase-2-Scope (Epic #29) und wird hier NICHT
verdrahtet.

### Tab-Renames + Testid-Migration (Slice 6)

| Editor | Tab-value | alt | neu |
|---|---|---|---|
| Trip (`TripTabs.svelte`) | `weather` | „Inhalt" | „Wetter-Metriken" |
| Trip (`TripTabs.svelte`) | `alerts` | „Alerts" | „Wertebereiche" |
| Compare (`CompareEditor.svelte` `TAB_DEFS`) | `idealwerte` | „Idealwerte" | „Wertebereiche" |

`value`-Schlüssel und `data-testid`-Suffixe (`trip-detail-tab-alerts`,
`compare-editor-tab-idealwerte` etc., C6) bleiben unverändert — nur die
Label-Strings ändern sich (Präzedenz: Issue #736, s.
`TripTabs.svelte:57-62`). 7 Playwright-E2E-Specs referenzieren die alten
Labels/Testids und müssen mitgezogen werden.

### `mark` im Compare-Mail-Renderer (Slice 7)

`src/output/renderers/email/compare_html.py::_render_overview_row()` bekommt
eine zusätzliche Grün-Markierung, wenn `corridorInside(value, corridor.min, corridor.max) === True`
für die jeweilige Metrik+Ort-Zelle — additiv zur bestehenden
`severity_for()`-Färbung (Slice 7 fügt eine neue Bedingung hinzu, ersetzt
nichts). Kein Einfluss auf `comparison_scoring.py::calculate_score()` (C1,
#1229 bleibt unangetastet). Löst das Renderer-Commit-Gate (#811) aus.

### Scope-Tabelle (Slice → Dateien → ~LoC)

| Slice | Dateien | ~LoC |
|---|---|---|
| 1 · Datenmodell + `corridorInside` | `internal/model/trip.go` (MODIFY), `internal/model/compare_preset.go` (MODIFY), `src/app/models.py` (MODIFY), `frontend/src/lib/components/shared/corridor-editor/corridorMatch.ts` (CREATE), `src/services/corridor_match.py` (CREATE) | 120–180 |
| 2 · Migration | `scripts/migrate_1231_corridors.py` (CREATE) | 200–250 |
| 3 · CorridorEditor Desktop `route` | `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`, `CorridorRow.svelte`, `CorridorBand.svelte`, `CorridorBound.svelte`, `CorridorEffect.svelte`, `CorridorPreviewChips.svelte` (CREATE), `trip-detail/TripTabs.svelte` (MODIFY) | ~230 |
| 4 · CorridorEditor Desktop `vergleich` + Wizard Step 3 | `compare/CompareEditor.svelte` (MODIFY), Compare-Wizard-Step-3-Einbindung (MODIFY) | ~200 |
| 5 · CorridorEditorMobile beide Contexts | `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` + `CM_*`-Subkomponenten (CREATE) | ~230 |
| 6 · Tab-Renames + Testid-Migration | `TripTabs.svelte`, `CompareEditor.svelte` (MODIFY), 7 Playwright-Specs (MODIFY) | ~150 |
| 7 · `mark` im Compare-Mail-Renderer | `src/output/renderers/email/compare_html.py` (MODIFY) | ~180 |

## Expected Behavior

- **Input:** User bearbeitet Wertebereiche im CorridorEditor (Trip- oder
  Compare-Kontext), Desktop oder Mobile.
- **Output:** `corridors[]` persistiert additiv; Δ-Wächter-Enabled-Zustand
  (`metric_alert_levels`) synchron zu `notify`; Compare-Mail-Renderer
  markiert Werte im Bereich grün, wenn `mark=true`.
- **Side effects:** `data_schema_backup.py` Pre-Snapshot-Hook feuert bei
  Edits an `trip.go`/`compare_preset.go`/`models.py`/`loader.py` (Schema-Datei
  Konvention). Migration schreibt `tar.gz`-Backup vor jedem `--execute`-Lauf.

## Test Plan

Zwei Schichten gemäß Test-Politik (CLAUDE.md, PO-go 2026-07-09). Detaillierte
Testfälle stehen als `- Test:`-Unterpunkte direkt bei jedem AC (AC-1…AC-21);
hier die Strategie-Zusammenfassung:

**Kern-Schicht (deterministisch, kein Netz — Commit-Gate):**
- Roundtrip-Test Datenerhalt: Trip/Preset laden→speichern, `alert_rules`/
  `ideal_ranges` byte-identisch, `corridors` additiv (AC-1)
- Parametrisierter Fixture-Vergleich `corridorInside` TS ↔ Python ↔
  Editor-Vorschau: `v=null`, Grenzwert exakt, außerhalb (AC-2)
- Metrikpool-Ausschluss `confidence_pct` in beiden Kontexten (AC-3)
- Migrations-Fixtures: 1:1-Mapping, #1191-Erhalt (leeres `active_metrics`),
  Abbruch bei Nicht-Abbildbarkeit (Exit ≠ 0), Dry-Run-Noop (AC-4–AC-7)
- DOM-/Komponententests: Editor-Struktur je Kontext, notify↔`metric_alert_levels`-
  Sync, notify+mark kombinierbar, Speicher-Block bei beidseitig offenem
  Bereich, Neutralitäts-Hinweis, Mobile-Touch-Targets ≥44px, Logik-Import aus
  Desktop-Modul (AC-8–AC-15)
- Tab-Label-Tests + Testid-Stabilität (AC-16, AC-17)
- Score-Identität mit/ohne Korridore — `calculate_score()` unverändert (AC-20)
- Statischer Grep-Test: kein `AlertChannelPicker`/`alertChannels` (AC-21)

**Live-E2E-Schicht (nur `/e2e-verify` gegen Staging):**
- Playwright: Trip- und Compare-Editor-Durchklick beider Wertebereiche-Tabs
  inkl. Wizard Step 3, echter Klick-Pfad (AC-8–AC-10, AC-16–AC-18)
- Die 7 bestehenden Playwright-Specs mit Tab-Referenzen nach Rename grün (AC-18)
- Echte Vergleichs-Testmail an `gregor-test@henemm.com`, IMAP-Abruf,
  `email_spec_validator.py` (compare-Pfad) für die grüne `mark`-Markierung
  (AC-19) — Slice 7 triggert Renderer-Commit-Gate #811
  (`test_issue_811_mode_matrix.py` + Validator-Lauf vor Commit an
  `compare_html.py`)

## Acceptance Criteria

**Slice 1 — Datenmodell**

- **AC-1:** Given ein Trip ohne `corridors`-Feld / When der Trip geladen und
  gespeichert wird / Then bleibt `alert_rules` unverändert erhalten und
  `corridors` wird additiv ergänzt, kein bestehendes Feld geht verloren
  (Read-Modify-Write, kein Replace).
  - Test: Roundtrip-Test lädt einen Bestands-Trip-JSON, speichert ihn, prüft
    `alert_rules` byte-identisch zum Original.

- **AC-2:** Given ein Messwert `v`, `min`, `max` / When `corridorInside(v, min, max)`
  in FE (TS), Python-Port und der Editor-Live-Vorschau aufgerufen wird / Then
  liefern alle drei identische Ergebnisse für `v=null` (→ `null`), `v` exakt
  auf `min`/`max` (→ `true`, da `<`/`>` exklusiv geprüft wird) und `v`
  außerhalb (→ `false`).
  - Test: Parametrisierter Test mit identischer Fixture-Tabelle
    (value/min/max/expected) gegen TS-Util, Python-Port und
    Editor-Snapshot-Test.

- **AC-3:** Given `confidence_pct` (`selectable=False`) / When der
  CorridorEditor-Metrikpool (`CORRIDOR_SEED`/`CORRIDOR_POOL`) für `route` oder
  `vergleich` aufgebaut wird / Then erscheint `confidence_pct` in keinem der
  beiden Pools.
  - Test: Prüft die Metrik-ID-Liste beider Kontexte gegen die
    `selectable=true`-Katalogliste, `confidence_pct` fehlt in beiden.

**Slice 2 — Migration**

- **AC-4:** Given ein Bestand aus Trip-`alert_rules` und Compare-`ideal_ranges`
  / When `migrate_1231_corridors.py --execute` läuft / Then hat jede
  bestehende `AlertRule` und jeder Idealwert einen korrespondierenden
  `Corridor`-Eintrag, verlustfrei (jeder Wert im Report als `alt → neu`
  nachvollziehbar).
  - Test: Migration auf Fixture-Datensatz laufen lassen, Report-Zeilenzahl ==
    Anzahl Quell-Regeln + Idealwerte, jeder Zielwert numerisch geprüft.

- **AC-5:** Given ein Compare-Preset mit bewusst leerer
  `active_metrics: []` (#1191-Zustand) / When die Migration läuft / Then
  bleibt `active_metrics` unverändert `[]` — die Migration reaktiviert keine
  deaktivierten Metriken.
  - Test: Fixture-Preset mit `active_metrics: []` vor/nach Migration
    vergleichen, Feld bytegleich.

- **AC-6:** Given eine nicht 1:1-abbildbare Alt-Regel (Edge Case, sollte laut
  C4 nicht vorkommen) / When die Migration sie erkennt / Then bricht der Lauf
  vollständig ab (kein Teil-Commit), Exit-Code ≠ 0.
  - Test: Künstliche Fixture mit inkonsistenter Regel, Migration mit
    `--execute` gegen diese Fixture laufen lassen, prüft Abbruch + keine
    Datei verändert.

- **AC-7:** Given `migrate_1231_corridors.py` ohne `--execute` / When das
  Skript läuft / Then werden keine Dateien verändert, aber ein vollständiger
  Report ausgegeben (Dry-Run-Default).
  - Test: Dateizeitstempel/-inhalt vor/nach Dry-Run-Lauf identisch.

**Slice 3+4 — CorridorEditor Desktop (route + vergleich)**

- **AC-8:** Given ein Trip-Editor / When der User den Tab „Wertebereiche"
  öffnet / Then sieht er `CorridorEditor context="route"` (keine
  `AlertsTab`/`AlertMetricLevelTable`-Inhalte mehr).
  - Test: Playwright öffnet Trip-Editor, klickt Tab, prüft Vorhandensein der
    Korridor-Zeilen-Struktur (Band + Bound + Effect-Toggles) und Abwesenheit
    der alten Empfindlichkeits-Tabelle.

- **AC-9:** Given ein Compare-Editor / When der User den Tab „Wertebereiche"
  im Wizard-Step-3 UND im Editor-Tab öffnet / Then zeigt BEIDE Stellen
  denselben `CorridorEditor context="vergleich"` (keine
  `Step3Idealwerte`-Instanz mehr an einer der beiden Stellen).
  - Test: Playwright durchläuft Compare-Wizard bis Step 3, prüft
    CorridorEditor-Markup; öffnet separat den Editor-Tab „Wertebereiche",
    prüft identisches Markup/Verhalten.

- **AC-10:** Given eine Korridor-Zeile mit `notify=true` / When der User sie
  auf `notify=false` umschaltet und speichert / Then wird
  `metric_alert_levels[metric]` auf `"off"` gesetzt, der numerische
  `range`-Wert bleibt im gespeicherten `Corridor`-Eintrag unverändert
  erhalten.
  - Test: E2E — Toggle klicken, Speichern, Trip via API neu laden, prüft
    `metric_alert_levels[metric] == "off"` und `corridors[].range`
    unverändert.

- **AC-11:** Given `notify` und `mark` derselben Korridor-Zeile / When beide
  gleichzeitig aktiviert werden (egal auf welchem `context`) / Then blockt
  der Editor das NICHT — beide Wirkungen sind auf beiden `kind`s frei
  kombinierbar (C1/Edge-Case-Tabelle aus dem Issue).
  - Test: Beide Toggles in einer Zeile aktivieren, Speichern erfolgreich,
    keine Validierungsfehler.

- **AC-12:** Given ein Korridor ohne obere UND ohne untere Grenze / When der
  User versucht zu speichern / Then blockt der Editor das Speichern mit einer
  sichtbaren Fehlermeldung (mind. eine Grenze ist Pflicht).
  - Test: Beide Grenzen auf „offen" setzen, Speichern-Button klicken, prüft
    Fehlermeldung + kein Save-Request.

- **AC-13:** Given `context="vergleich"` / When die Editor-Zusammenfassung
  gerendert wird / Then zeigt sie den Neutralitäts-Hinweis „kein Score · kein
  Rang" und es gibt an keiner Stelle im Editor eine Sortierung oder
  Rang-Anzeige der Orte anhand der Wertebereiche (C1).
  - Test: Snapshot/DOM-Test prüft Neutralitäts-Hinweis-Text und Abwesenheit
    jeglicher Rang-/Score-Elemente im Rendered-Output.

**Slice 5 — Mobile**

- **AC-14:** Given ein Mobile-Viewport (≤480px) / When der User den
  Wertebereiche-Tab öffnet (Trip oder Compare) / Then zeigt
  `CorridorEditorMobile` je Metrik eine Card mit Touch-Targets ≥44px (Stepper,
  Effect-Buttons) statt der Desktop-Tabelle.
  - Test: Playwright im Mobile-Viewport, prüft `getBoundingClientRect()`
    Höhe/Breite der Stepper-/Toggle-Buttons ≥44px.

- **AC-15:** Given `CorridorEditorMobile` / When Daten oder Match-Logik
  benötigt werden / Then importiert sie `corridorInside`/`CORRIDOR_*` aus dem
  Desktop-Modul (`corridorMatch.ts`/`CorridorEditor.svelte`-Exports) — kein
  zweites Datenmodell.
  - Test: Statischer Grep-/Import-Test prüft, dass `CorridorEditorMobile.svelte`
    keine eigene `corridorInside`-Implementierung enthält.

**Slice 6 — Tab-Renames**

- **AC-16:** Given den Trip-Editor / When die Tab-Leiste gerendert wird /
  Then heißt der `weather`-Tab „Wetter-Metriken" und der `alerts`-Tab
  „Wertebereiche"; `value`-Schlüssel und `data-testid`s bleiben unverändert
  (`trip-detail-tab-weather`, `trip-detail-tab-alerts`).
  - Test: DOM-Test liest Tab-Label-Texte und prüft `data-testid`-Attribute
    gegen die alte Testid-Liste.

- **AC-17:** Given den Compare-Editor / When `TAB_DEFS` gerendert wird / Then
  heißt der `idealwerte`-Tab „Wertebereiche"; `data-testid="compare-editor-tab-idealwerte"`
  bleibt unverändert.
  - Test: DOM-Test für den Compare-Editor, analog zu AC-16.

- **AC-18:** Given die 7 identifizierten Playwright-E2E-Specs mit alten
  Tab-Label-Referenzen / When sie nach dem Rename laufen / Then sind alle 7
  grün (Label-Strings aktualisiert, Testid-Selektoren unverändert lauffähig).
  - Test: `uv run playwright test` bzw. Node-Test-Runner über die
    betroffenen 7 Specs, alle grün.

**Slice 7 — Mail-Renderer `mark`**

- **AC-19:** Given ein Compare-Preset mit einem `Corridor{mark:true}` für
  eine sichtbare Metrik / When die Vergleichs-Mail gerendert wird / Then ist
  die Zelle jedes Orts mit `corridorInside(value)===true` grün markiert,
  zusätzlich zur bestehenden Severity-Färbung.
  - Test: `briefing_mail_validator.py`-kompatibler Test — echte
    Staging-Test-Mail an `gregor-test@henemm.com`, IMAP-Abruf, HTML enthält
    die Grün-Markierung für die erwarteten Orte/Metriken.

- **AC-20:** Given ein `Corridor{mark:true}` / When `compare_html.py` die
  Mail rendert / Then hat `mark` KEINEN Einfluss auf
  `comparison_scoring.py::calculate_score()` — der Score bleibt zwischen
  einem Lauf mit und ohne Korridore identisch.
  - Test: Score-Berechnung zweimal mit identischen Metrikdaten aufrufen
    (einmal mit, einmal ohne `corridors`), Ergebnis bytegleich.

**Übergreifend (PO-C, #1232-Übertrag)**

- **AC-21:** Given den fertigen CorridorEditor (beide Kontexte) / When das
  UI durchsucht wird / Then existiert weder ein `AlertChannelPicker`-Element
  noch ein `alertChannels`-Feld im gespeicherten Trip/Preset-JSON — Alert-
  Kanäle bleiben die bestehende Trip-Kanalwahl, Vergleichs-Briefings bleiben
  E-Mail-only.
  - Test: Statischer Grep-Test über `frontend/src/` auf `AlertChannelPicker`/
    `alertChannels` (0 Treffer außerhalb der Design-Referenz-JSX) + API-
    Response-Schema-Test ohne `alert_channels`-Feld.

## Known Limitations

- **Δ-Sensitivitätsstufen verlieren UI-Feinsteuerung:** Der CorridorEditor
  exponiert nur `notify` an/aus, nicht die vier Stufen
  (off/entspannt/standard/sensibel) aus dem bisherigen
  `AlertMetricLevelTable`. Der gespeicherte Stufenwert bleibt erhalten
  (kein Datenverlust), ist aber im Phase-1-Editor nicht mehr einzeln
  wählbar. Bindend akzeptiert per PO-B (Ersetzung von AlertsTab +
  AlertMetricLevelTable); bei Bedarf eigenes Folge-Issue.
- **`range` im `route`-Kontext ist Anzeige-Geometrie, keine Live-Schwelle:**
  Editieren der Zahlen ändert NICHT die tatsächliche Δ-Trigger-Sensitivität
  (PO-A) — nur `notify` (an/aus) wirkt technisch. Das kann für Nutzer
  überraschend sein (die Vorschau-Copy im JSX suggeriert „warnt sobald der
  Wert den Bereich verlässt", technisch bleibt es der Δ-Wächter). Bewusst
  akzeptierte Phase-1-Einschränkung, kein Blocker.
- **`AlertChannelPicker`/`alertChannels[]` explizit nicht gebaut** (PO-C),
  obwohl im Design-JSX vorhanden und exportiert — Design-Referenz enthält
  Phase-2/3-Vorgriffe, die hier ausdrücklich nicht implementiert werden.
- **`CompareEndDateControl(Mobile)`** aus denselben JSX-Dateien ist
  Epic-#29-Phase-2-Scope (Laufzeit/`endDate`) und wird hier NICHT
  verdrahtet, obwohl die Komponente im Design bereits existiert.
- **Metrik-Namensräume bleiben getrennt** zwischen `route` (6
  AlertableMetrics) und `vergleich` (10 Compare-Summary-Keys) — keine
  Vereinheitlichung in Phase 1; ein Korridor ist nicht kontextübergreifend
  portabel.
- **Renderer-Gate #811** greift auf Slice 7 (`compare_html.py`) — Commit ist
  erst möglich, wenn `test_issue_811_mode_matrix.py` grün UND
  `briefing_mail_validator.py` erfolgreich gegen eine echte Staging-Test-Mail
  gelaufen ist.
- **Gemeinsames `BriefingSubscription`-Schema** (Zusammenführung von
  `channels`/Zustellung über Trip UND Compare) ist Phase-3-Scope (Epic #29),
  hier nicht enthalten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** #1231 führt keine neue Alert-Trigger-Architektur ein. Der
  Δ-Wächter-Mechanismus (ADR-0009, ADR-0013) und die Shared-Deviation-Alert-
  Engine (ADR-0021) bleiben laut bindender PO-Entscheidung A vollständig
  unverändert — `corridor.notify` ist nur ein neuer Oberflächen-Schalter auf
  denselben bestehenden Mechanismus (`metric_alert_levels`). `mark` ist eine
  rein additive, aggregations-freie Renderer-Markierung (C1 verbietet
  ausdrücklich jede Score-/Rang-Wirkung, damit keine Berührung mit
  ADR-relevanten Scoring-Entscheidungen). Die einzige neue persistente
  Struktur (`Corridor`) ist eine additive Vereinheitlichung zweier bereits
  etablierter, ADR-gedeckter Konzepte auf UI-/Storage-Ebene, kein neuer
  Architektur-Grundsatzentscheid.

## Changelog

- 2026-07-13: Slice 7 implementiert + Adversary VERIFIED (2 Runden, 1 Fix-Loop
  mit 4 Findings: unsichtbare Markierung/tautologischer Test, gebrochene
  Bestands-Signatur, Aggregat-vs-Stundenwert-Vermischung, Versandpfad-Crash
  bei malformten Corridors). Known Limitations ergänzt: (1) mark-Markierung
  wirkt in Übersichts-Zeilen (via FRONTEND_TO_RENDERER_METRIC_ID) und nur für
  echte 1:1-Stundenmetriken auch in Stundentabellen
  (CORRIDOR_METRIC_TO_HOUR_KEY: temp_max_c/wind_max_kmh/gust_max_kmh/
  thunder_level_max) — Tages-Aggregat-Korridore (precip_sum_mm, uv_index_max,
  visibility_min_m) werden NICHT gegen Einzelstunden geprüft; precip_sum_mm
  hat zudem keine Übersichts-Zeile und bleibt daher vorerst unmarkiert
  (Ausbau-Kandidat, #1199). (2) range=[None,None]+mark markiert defensiv
  alles (im Editor per AC-12 nicht speicherbar).
- 2026-07-13: Fakten-Korrektur Slice 4 (transparent, keine AC-Änderung): Der
  vergleich-Metrik-Namensraum umfasst für `mark`-Korridore ALLE 14
  Compare-Metriken aus `compareMetricDefs.ts::ALL_METRICS` (nicht nur die 10
  Alarm-Keys aus `migrate_1191::FULL_METRIC_SET` — die Slice-2-Migration hat
  ideal_ranges ALLER Metriken migriert, reale Bestände wie `sunny_hours_h`
  existieren als Corridors). `notify` wird nur für die 10 Alarm-Keys
  angeboten (Δ-Alarm-Brücke kennt nur diese). PO-Entscheidung 2026-07-12
  („Go"): `thunder_level_max` als 3-Stufen-Ordinal-Band (kein/mittel/hoch),
  kein %-Slider (Design-JSX-%-Skala hat kein Daten-Backing).
- 2026-07-12: Slice 2 implementiert + Adversary VERIFIED (3 Runden, 1 Fix-Loop,
  5 Findings an echten Datenkopien). Transparente Präzisierungen der
  Migrations-Semantik gegenüber dem ursprünglichen Spec-Text (keine
  AC-Änderung, AC-6 gilt weiter für strukturell Malformtes):
  (1) **Kategoriale/nicht-numerische Idealwert-Grenzen** (real: thunder_level_max
  Enum „NONE") werden NICHT migriert, sondern mit SKIP-Report-Zeile übersprungen
  und bleiben in `ideal_ranges` erhalten — verhaltenstreu, da die alte
  isIdealGood-Logik nicht-numerische Grenzen bereits ignoriert und das Design
  Gewitter im Korridor-Pool als %-Skala führt; Editor-Behandlung kategorialer
  Compare-Metriken ist Slice-4-Thema.
  (2) **Invertierte Bereiche (min>max, reale Bestandsdaten)** werden AS-IS
  migriert (verhaltenstreu „nie im Bereich") + WARNUNG-Report-Zeile.
  (3) **Level-Synthese:** Da der Go-Self-Heal von `alert_rules` nicht
  persistiert (Bestand: leere `alert_rules[]` trotz konfigurierter
  `metric_alert_levels`), synthetisiert die Migration Corridors direkt aus
  `metric_alert_levels`-Einträgen ohne AlertRule-Pendant, range aus
  DefaultDeltaThreshold (Go-gespiegelt), Report-Kennzeichnung
  „(synthetisiert aus Level)". range bleibt per PO-A Anzeige-Geometrie.
- 2026-07-12: Fakten-Korrektur nach Slice-1-Implementierung (transparent, keine
  AC-Änderung): (1) FE-Util-Pfad `frontend/src/lib/shared/…` →
  `frontend/src/lib/components/shared/…` (Ordner `lib/shared/` existiert nicht,
  Repo-Konvention ist `lib/components/shared/`, Präzedenz ltIdealRange/VersandTab);
  (2) Go-JSON-Tag `corridors,omitempty` → `corridors` ohne omitempty (Konsistenz
  zu Python-Serialisierung, die das Feld immer emittiert; analog `alert_rules`).
- 2026-07-12: Slice 1 implementiert + Adversary VERIFIED (4 Runden, 2 Fix-Loops:
  F001 float-Cast, F002 malformed-range-Crash, F003 Skalar-range-Crash,
  NaN/Infinity-Härtung — alle in `src/app/loader.py` gefixt und getestet).
- 2026-07-12: Initial spec erstellt — Issue #1231, Sub-Issue von Epic #29,
  inkl. AC-Übertrag aus #1232-Kommentar (Wertebereiche-Tab = reiner
  CorridorEditor, Tab-Umbenennungen).
