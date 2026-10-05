---
entity_id: mobile_stage_datum_zeit_edit
type: feature
created: 2026-10-04
updated: 2026-10-05
status: implemented
version: "1.0"
tags: [mobile, usability, frontend, trip-detail, stages, issue-2496]
---

<!-- Issue #2496 — Folgefrage Mobile aus PR #2495.
     Verbindlicher Soll: docs/design-requests/mobile_stage_datum_zeit_soll.md
     (alle PO-Entscheide F1–F4 vom 2026-10-04). -->

# Mobile: Etappen-Datum & -Startzeit im Etappen-Tab bearbeiten

## Approval

- [x] Approved (PO „approved", 2026-10-04; Design-Entscheide F1–F4 vom 2026-10-04)

## Purpose

Seit der Listen-only-Umstellung (PR #2495, PO-Entscheid F5) kann auf Mobile
kein Etappen-Datum mehr bearbeitet werden — das Datumsfeld existierte nur im
entfernten Desktop-Karten-Editor. Die Kaskaden-Rückfrage ist damit ebenfalls
nicht mehr auslösbar. Diese Spec macht Datum (F1) und Startzeit (F4) je
Etappen-Karte auf Mobile direkt editierbar und harmoniertert die
Pausentag-Heuristik (F3). Die Kaskaden-Rückfrage bleibt Inline-Banner (F2).

## Source

- **File:** `frontend/src/lib/components/mobile/StageCardM.svelte`
  (Kartenkopf-Zeile: statisches `.date`-Span → kompaktes Editierfeld)
- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`
  (Mobile-Zweig: Callbacks an `handleDateChange`/`handleStartTimeChange`
  verdrahten; `handleMobileAddPause` benennt den Pausentag; lokale
  `isPause`-Kopie durch `isPauseStage` ersetzen)
- **File:** `frontend/src/lib/components/shared/wizardHelpers.ts`
  (`isPauseStage()`: `'Pausentag'` als Pause-Synonym, #559-Regel sonst
  unverändert)
- **File:** `frontend/src/lib/components/edit/StageDateField.svelte` +
  `StageTimeField.svelte` (`variant`-Prop `'default' | 'inline'`, Logik geteilt)

> **Schicht-Hinweis:** reine Frontend-/User-UI-Änderung (`frontend/src/...`,
> SvelteKit). Der schreibende Endpunkt `PUT /api/trips/{id}` (Go,
> `internal/handler/trip.go`) wird unverändert genutzt — kein API-Change,
> keine serverseitige Kaskaden-Logik (speichert `stages` wortgleich).

## Affected Files

| Datei | Änderung | Iteration |
|---|---|---|
| `frontend/src/lib/components/edit/StageDateField.svelte` | `variant`-Prop: `inline` = Label-los, horizontal einbettbar; Wochentag-Chip-/Change-Logik unverändert geteilt | 1 |
| `frontend/src/lib/components/mobile/StageCardM.svelte` | Props `onDateChange?`/`onStartTimeChange?`/`isFirst?`; Kartenkopf rendert bei Callback inline-Varianten; Tap/Keydown-Stop gegen Karten-Toggle; ohne Callback statisches Datum wie bisher | 1 |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Mobile-Zweig: Callbacks an `handleDateChange`/`handleStartTimeChange` verdrahten (beide viewport-unabhängig vorhanden) | 1 |
| `frontend/src/lib/components/edit/StageTimeField.svelte` | `variant`-Prop analog StageDateField | 2 |
| `frontend/src/lib/components/shared/wizardHelpers.ts` | `isPauseStage()`: `'Pausentag'` → Pause; Docstring/#559-Kommentar aktualisieren | 2 |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` (F3) | `handleMobileAddPause` → `name: 'Pausentag'`; lokale `isPause`-Kopie (Z. ~160) durch `isPauseStage` ersetzen | 2 |
| `docs/design-system/COMPONENTS.md` | `StageCardM`-Eintrag: Editier-Modus dokumentieren; Feld-Varianten vermerken | 2 |

## Estimated Scope

- **LoC:** Iteration 1 ~180 · Iteration 2 ~120 (gesamt ~300, Tests eingerechnet)
- **Files:** 6
- **Effort:** medium

> **Scope-Guard:** `max_loc_delta: 250` pro Iteration — deshalb Aufteilung:
> Iteration 1 = Datum + Kaskaden-Verdrahtung (F1/F2), Iteration 2 = Startzeit
> + Pausentag-Harmonisierung (F4/F3). Keine Massen-Umbenennung des
> Testbestands; neue E2E-Spec mit Verhaltensname.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `handleDateChange`/`applyCascade`/`dismissCascade`/`cascadeBanner` (`EditStagesPanelNew.svelte`) | logic | Kaskaden-Ablauf viewport-unabhängig vorhanden (#1389/#1390/#1393) — unverändert wiederverwenden |
| `handleStartTimeChange` (`EditStagesPanelNew.svelte`) | logic | Startzeit-Save-Trigger vorhanden (#675/#1010) |
| `SortableList`/`DragHandle` (ADR-0024) | component | Liste unverändert; Griff-only-Drag kollidiert nicht mit den Eingabefeldern |
| `Sheet.svelte` | component | Bewusst NICHT genutzt (PO F1/F2: Inline statt Sheet) |

## Implementation Details

### Iteration 1 — Datum + Kaskade (F1/F2)

- `StageDateField`: Prop `variant?: 'default' | 'inline'` (default `'default'` =
  heutige Darstellung). `inline` rendert nur die `.box` (Wochentag-Chip +
  Input), ohne Label/Spalten-Layout, mit `min-width: 0` für Kartenkontext.
- `StageCardM`: neue Props `onDateChange?: (iso: string) => void`,
  `onStartTimeChange?: (hhmm: string) => void`, `isFirst?: boolean`.
  Kopfzeile: `{#if onDateChange}` → `<StageDateField variant="inline"
  value={stage.date} isFirst={isFirst} onchange={onDateChange} />`, sonst
  bisheriges statisches `.date`-Span. Eingabefelder stoppen
  `onclick`/`onkeydown`-Propagation (Karten-Toggle darf nicht feuern).
- `EditStagesPanelNew` Mobile-Zweig: `onDateChange={(d) =>
  handleDateChange(stage.id, d)}`, `isFirst={i === 0}`.
- Kein Change an `handleDateChange` selbst — Defer-Save, Reentrancy-Riegel
  (`cascadeBusy`) und Banner-Logik greifen unverändert.

### Iteration 2 — Startzeit + Pausentag (F4/F3)

- `StageTimeField`: `variant`-Prop analog; `inline` kompakt neben dem Datum.
- `EditStagesPanelNew`: `onStartTimeChange={(t) =>
  handleStartTimeChange(stage.id, t)}` im Mobile-Zweig.
- `wizardHelpers.ts` `isPauseStage`:
  `if (name.length > 0 && name !== 'Pause' && name !== 'Pausentag') return false;`
  — #559-Regel (benannte Vorlagen-Etappen ohne Wegpunkte = normale Etappe)
  gilt weiter für alle anderen Namen.
- `handleMobileAddPause`: `name: 'Pausentag'` (statt `''`); Kommentar
  aktualisieren.
- Drift-Beseitigung: `const isPause = (s) => s.waypoints.length === 0`
  (Panel-lokal, ohne #559-Regel) → `isPauseStage`; Auswahl der
  Start-Etappe/`activeIsPause` folgt damit derselben Heuristik wie
  `StageCardM`, `PauseStageView` und die Kaskaden-Helfer.

## Expected Behavior

- **Input:** Tap auf Datum/Zeit in einer Etappen-Karte (Mobile <900 px).
- **Output:** Natives iOS/Android-Picker-Rad; nach Bestätigung Auto-Save
  (debounced) bzw. bei Folge-Etappen zuerst die Kaskaden-Rückfrage
  (Inline-Banner über der Liste).
- **Side effects:** `PUT /api/trips/{id}` mit komplettem `stages`-Array
  (Status quo); bei Kaskade exakt ein PUT erst nach Antwort.

## Acceptance Criteria

- **AC-1 (F1):** Given Mobile-Ansicht eines Trips mit ≥2 Etappen / When der
  Nutzer das Datum der ersten Etappe tippt und ein neues Datum wählt / Then
  wird der Wochentag-Chip aktualisiert und der neue Stand gespeichert (nach
  Reload sichtbar), ohne die Karte auf-/zuzuklappen.
  - Test: E2E 390×844 — Datum ändern, Reload, Datum steht; `aria-expanded`
    der Karte unverändert.

- **AC-2 (F2a):** Given dieselbe Situation, aber die geänderte Etappe hat
  datierte Folge-Etappen / Then erscheint die Kaskaden-Rückfrage als
  Inline-Banner über der Liste („Sollen die N folgenden Etappen lückenlos
  anschließen?").
  - Test: E2E — Banner sichtbar, Speichern erst nach Antwort (ein PUT).

- **AC-3 (F2b):** Given die sichtbare Kaskaden-Rückfrage / When der Nutzer
  „Lückenlos anschließen" wählt / Then erhalten alle Folge-Etappen
  lückenlose Daten (Anker+1, +2, …), ein Erfolgs-Banner zeigt Anzahl und
  Startdatum.
  - Test: E2E — Folgedaten geprüft (inkl. Pausentag rückt mit, Etappe ohne
    Datum verbraucht keinen Tag — #1393-Regeln unverändert).

- **AC-4 (F2c):** Given die sichtbare Kaskaden-Rückfrage / When der Nutzer
  „Nur diese Etappe" wählt / Then ändert sich nur die auslösende Etappe;
  Folge-Etappen behalten ihre Daten.
  - Test: E2E — Folgedatum unverändert nach Reload.

- **AC-5 (F4):** Given Mobile-Ansicht / When der Nutzer die Startzeit einer
  Etappe ändert / Then wird die neue Zeit gespeichert und die ETA-Zeilen
  der aufgeklappten Wegpunkte rechnen damit.
  - Test: E2E — Zeit ändern, Reload, Wert steht; Wegpunkt-ETA aktualisiert.

- **AC-6 (F3a):** Given Mobile-Ansicht / When der Nutzer „+ Etappe →
  Pausentag" wählt / Then entsteht eine Karte mit sichtbarem Titel
  „Pausentag", die als Pause gerendert wird (`data-pause`), und die
  Datumsbearbeitung funktioniert auch auf der Pausen-Karte.
  - Test: E2E — Karte `data-pause=true`, Datum editierbar, nach Reload
    identisch.

- **AC-7 (F3b):** Given eine Desktop-Pause (`name: 'Pausentag'`, keine
  Wegpunkte) im Bestand / Then erkennen `isPauseStage()` und das Panel sie
  konsistent als Pause (kein gemischtes Verhalten mehr zwischen
  Panel-Heuristik und `isPauseStage`).
  - Test: Unit `wizardHelpers.test.ts` — `Pausentag` → true; benannte
    Vorlagen-Etappe (`Zustieg`) → false (#559 unverändert).

- **AC-8 (Desktop-Regression):** Given Desktop-Ansicht (≥900 px) / When der
  Nutzer den Etappen-Tab öffnet / Then ist die Darstellung zeichen-identisch
  zum Stand vor dieser Spec (EtappenStrip + Karten-Editor, Datumsfeld im
  aktiven Stage-Header).
  - Test: E2E Desktop-Smoke — kein `input[type=date]` innerhalb der Karten;
    Bestands-Specs `issue-498` (38 Tests) und `issue-675` grün.

## Known Limitations

- iOS zeigt den nativen Wheel-Picker; ein eigenständiger Calendar-Baustein
  ist bewusst nicht Teil dieser Spec.
- GPX-Upload und Routen-Zeichnen bleiben Desktop-only (F5 der Vor-Runde).
- Die lokale `isPause`-Ersetzung (Iteration 2) ändert die Auswahl der
  initial aktiven Etappe für benannte Vorlagen-Etappen ohne Wegpunkte
  (#559-Fall): sie gelten jetzt überall als normale Etappen — das ist die
  intendierte Konsolidierung, Abweichungen werden in den Alt-Suites
  beobachtet (Baseline-Diff im Changelog).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (kein `src/output/`-, `src/providers/`-,
  Metrics- oder Hook-Change; reine Frontend-Komponenten-Änderung).
- **Rationale:** Varianten-Prop statt Komponenten-Kopie entspricht AP-006
  (Bausteine werden geteilt, nicht kopiert). Kaskaden-Logik bleibt
  clientseitig im Panel — der Go-`UpdateTripHandler` ersetzt `stages`
  wortgleich; eine Server-Kaskade wäre ein eigener, größerer Eingriff.

## Changelog

- 2026-10-04: Initial spec created (PO-Entscheide F1–F4 vom 2026-10-04,
  Design-Doc `mobile_stage_datum_zeit_soll.md`)
- 2026-10-05: Umsetzung abgeschlossen und validiert. Iteration 1 (8686e04a0):
  `StageDateField variant="inline"`, editierbares Datum in `StageCardM`
  (Event-Stop gegen Karten-Toggle), Verdrahtung an `handleDateChange` im
  Mobile-Zweig — Red-Beleg `mobile-stage-date-edit-red.log` (4× RED),
  E2E 6/6, Unit 4132/0. Iteration 2 (453ca8224): `StageTimeField`
  inline-Variante + `onStartTimeChange` (F4), `isPauseStage` erkennt
  'Pausentag', beide Anlage-Pfade benennen einheitlich, Panel-Drift
  (lokale isPause-Kopie) durch `isPauseStage` ersetzt (F3), COMPONENTS.md
  v1.7 — Red-Beleg `mobile-stage-date-time-edit-red-iter2.log`, E2E 8/8,
  Unit 4134/0. Baselines: issue-498 AC-37 und issue-675 AC-3/4 verifiziert
  pre-existing (auf gestashtem Stand rot). Desktop-Zweig zeichen-identisch
  (AC-8).
