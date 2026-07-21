---
entity_id: issue_1041c_radar_toggle_frontend
type: module
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [compare, radar, alerts, frontend, issue-1041, slice-2]
---

<!-- Issue #1041 — Slice 2 von 3 (Frontend). Macht das in Slice 1b (LIVE) gelieferte
     Backend-Feld `radar_alert_enabled` (Default AUS) im Compare-Editor editierbar.
     Reiner Frontend-Slice nach exaktem #1040-Muster (`official_alerts_enabled`).
     Backend (Go-Feld, RMW-Merge, Service, Scheduler) ist bereits live — NICHT Teil dieser Spec. -->

# Issue #1041 — Radar-Alarm-Schalter im Compare-Editor (Slice 2/3, Frontend)

## Approval

- [x] Approved — PO „go" 2026-07-10

## Purpose

Ein Ein/Aus-Schalter „Radar-Alarm" im „Alarme"-Tab des Orts-Vergleichs-Editors, der
das in Slice 1b bereits live gelieferte Backend-Feld `radar_alert_enabled`
(Default **AUS**, opt-in) für Nutzer ohne direktes JSON-Editieren aktivierbar macht.
Folgt exakt der bestehenden `official_alerts_enabled`-Kette (#1040) — additiv, keine
Änderung bestehender Controls.

## Source

- **File:** `frontend/src/lib/types.ts` (MODIFY, ~1 LoC) — im `ComparePreset`-Typ
  (neben `official_alerts_enabled?: boolean`, Zeile 497) neues Feld
  `radar_alert_enabled?: boolean;`.
- **File:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts`
  (MODIFY, ~3 LoC) — (a) Deklaration `radarAlertEnabled = $state(false);` (Default
  AUS, neben `officialAlertsEnabled = $state(true)`, Zeile 40); (b) Create-Payload
  `radar_alert_enabled: this.radarAlertEnabled` (neben Zeile 175); (c) Edit-`edits`
  `radarAlertEnabled: this.radarAlertEnabled` (neben Zeile 227).
- **File:** `frontend/src/lib/components/compare/compareEditorSave.ts` (MODIFY,
  ~4 LoC) — (a) Interface `CompareEditorEdits`: `radarAlertEnabled?: boolean;`
  (neben Zeile 27); (b) konditionaler Spread ins PUT-Body (Muster Zeilen 104-107):
  `...(edits.radarAlertEnabled !== undefined ? { radar_alert_enabled: edits.radarAlertEnabled } : {}),`.
- **File:** `frontend/src/routes/compare/[id]/edit/+page.svelte` (MODIFY, ~1 LoC) —
  Hydration `state.radarAlertEnabled = data.preset.radar_alert_enabled ?? false;`
  (Default **AUS** — bewusst `?? false`, NICHT `?? true` wie #1040; neben Zeile 36).
- **File:** `frontend/src/lib/components/compare/CompareAlarmSection.svelte`
  (MODIFY, ~10 LoC) — `ChannelToggle`-Import ergänzen
  (`$lib/components/trip-wizard/steps/ChannelToggle.svelte`) und einen Toggle-Block
  einfügen (Muster Step5Versand.svelte:135-142), gebunden an die geteilte
  `wiz`-Instanz:
  ```svelte
  <ChannelToggle
      label="Radar-Alarm"
      checked={wiz.radarAlertEnabled}
      onchange={(checked) => (wiz.radarAlertEnabled = checked)}
      testid="compare-alarm-radar-toggle"
  />
  ```
  Platzierung als eigener Block im Alarme-Tab (z.B. nach `<Eyebrow>` Zeile 49 / vor
  `<div class="extra-cards">` Zeile 63). Exakte Prop-Namen aus der echten
  `ChannelToggle.svelte` übernehmen (JSX/Svelte ist die Wahrheit).
- **File:** `frontend/src/lib/components/compare/CompareEditor.svelte` (MODIFY,
  ~18 LoC) — **während der Umsetzung entdeckt, nicht in der ursprünglichen 5-Datei-
  Schätzung:** Der echte Speichern-Button ruft `handleSave()` (Zeile ~155/329/623),
  das ein EIGENES `edits`-Objekt für `buildComparePresetSavePayload` baut (Zeile
  ~172-188) — der in der Recherche genannte `saveComparePreset`-Pfad ist toter Code.
  Dieses `edits`-Objekt ließ `radarAlertEnabled` (und auch `officialAlertsEnabled`
  aus #1040) aus → der Toggle würde im Edit-Pfad nie persistieren. Fix: beide Felder
  ins `edits`-Objekt ergänzt (+ Dirty-Snapshot/Save-Snapshot konsistent). Bündelt
  die Behebung des identischen #1040-Edit-Persistenz-Bugs. Weitere gleichartig
  betroffene Felder (`hourly_enabled`/`top_n`/`forecast_hours`) → eigenes Folge-Issue
  #1221 (nicht Teil dieser Scheibe).
- **File:** `frontend/e2e/compare-radar-toggle.spec.ts` (NEU) — Playwright-Roundtrip-
  Test (Vorbild `frontend/e2e/compare-alarm-config.spec.ts`: `createPreset`-Helper,
  login-Fixture, Desktop 1280×900). Post-Save-Nachweis über Save-Indikator
  (`data-state=idle`) + `page.reload()` (KEIN Redirect — `handleSave` navigiert seit
  #758 bewusst nicht mehr weg).

> **Schicht-Hinweis:** Reiner Frontend-Code (`frontend/src/...`, SvelteKit). Kein
> Go, kein Python. Das Backend-Feld `radar_alert_enabled` (Go-Modell + RMW-Merge +
> Service + Scheduler) ist bereits in Slice 1b live und wird hier nur bedient.

## Estimated Scope

- **LoC:** Produktivcode ~19 (5 Dateien, additiv), E2E-Test ~40-60 → Summe ~60-80.
  Innerhalb 250/Workflow.
- **Files:** 5 MODIFY Frontend + 1 neuer E2E-Test.
- **Effort:** low.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ChannelToggle.svelte` (`$lib/components/trip-wizard/steps/`) | intern (Frontend) | Wiederverwendete Toggle-Komponente (label/checked/onchange/testid) |
| `CompareWizardState` (`compareWizardState.svelte.ts`) | intern | Geteilter State (Step5 als `state`, CompareAlarmSection als `wiz`) — hält `radarAlertEnabled` |
| `buildComparePresetSavePayload` (`compareEditorSave.ts`) | intern | Baut das PUT-Body — konditionaler Spread des neuen Felds |
| `official_alerts_enabled` (#1040-Kette) | intern | Exaktes Copy-Vorbild über alle 5 Frontend-Dateien |
| Backend `radar_alert_enabled` (Slice 1b, LIVE) | intern (Go+Python) | Empfängt/persistiert (RMW) + liest das Feld — bereits fertig |

## Implementation Details

### Datenfluss (Roundtrip)
```
Toggle im Alarme-Tab (ChannelToggle)
  → wiz.radarAlertEnabled ($state, Default false)
  → Create-Payload (saveNew) ODER Edit-edits → buildComparePresetSavePayload → PUT-Body radar_alert_enabled
  → Go-Handler RMW-Merge (Slice 1b, live) → compare_presets.json
Edit-Seite laden:
  → data.preset.radar_alert_enabled ?? false → state.radarAlertEnabled → Toggle-Zustand
```

### Default-AUS-Invariante
Anders als #1040 (`?? true`) ist der Radar-Alarm opt-in: Hydration `?? false`,
`$state(false)`. Ein Altpreset ohne das Feld zeigt den Schalter AUS.

## Expected Behavior

- **Input:** Nutzer öffnet den Compare-Editor („Alarme"-Tab), sieht den „Radar-Alarm"-
  Schalter (bei neuem/Altpreset AUS), schaltet ihn ein und speichert.
- **Output:** `radar_alert_enabled: true` wird ins PUT-Body gespreadet und
  persistiert; erneutes Öffnen der Edit-Seite zeigt den Schalter AN. Ausschalten +
  Speichern persistiert `false`.
- **Side effects:** keine — additives optionales Feld, nutzt die bestehende
  Save-/Load-Mechanik.

## Acceptance Criteria

- **AC-1:** Given ein Orts-Vergleich im Editor, dessen Preset `radar_alert_enabled`
  nicht gesetzt hat (Altpreset/neu) / When der Nutzer den „Alarme"-Tab öffnet / Then
  ist der „Radar-Alarm"-Schalter sichtbar und steht auf **AUS** (Default-AUS-Invariante).
  - Test: Playwright — Preset ohne das Feld anlegen, Edit-Seite/Alarme-Tab öffnen,
    Toggle vorhanden und nicht aktiv (`toBeChecked` false).

- **AC-2:** Given der „Radar-Alarm"-Schalter ist AUS / When der Nutzer ihn einschaltet
  und das Preset speichert / Then wird `radar_alert_enabled: true` persistiert und
  nach erneutem Laden der Edit-Seite steht der Schalter auf AN.
  - Test: Playwright-Roundtrip — Toggle klicken, Speichern-Button klicken (echter
    Klickpfad), Seite neu laden, Toggle ist aktiv; zusätzlich GET/Preset-Prüfung
    `radar_alert_enabled === true`.

- **AC-3:** Given ein Preset mit `radar_alert_enabled=true` / When der Nutzer nur ein
  anderes Feld ändert (z.B. Name) und speichert / Then bleibt `radar_alert_enabled`
  erhalten (kein Verlust durch den Save — Zusammenspiel mit dem Go-RMW-Merge aus 1b).
  - Test: Playwright — Radar-Alarm an, dann nur Namen ändern + speichern, neu laden:
    Schalter weiterhin AN.

## Known Limitations

- Nur der An/Aus-Schalter — keine editierbare Onset-Schwelle (die 20-Minuten-Schwelle
  bleibt wie beim Trip hartkodiert, Backend-Entscheidung aus Slice 1b).
- Der Schalter sitzt im „Alarme"-Tab (nicht im Versand-Tab, wo #1040 sitzt) — bewusst,
  weil Radar-Alarm semantisch ein Alarm ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** Reine additive Frontend-Verdrahtung nach einem bereits etablierten,
  mehrfach verwendeten Muster (#1040 `official_alerts_enabled`, #1170 Alarme-Tab).
  Keine neue Architektur, keine neuen Datenflüsse, kein neues Persistenz-Schema.

## Test Plan

E2E gegen Staging (Playwright, echter Klickpfad — kein DB-Direktzugriff). Neue Datei:
`frontend/e2e/compare-radar-toggle.spec.ts` (Vorbild `compare-alarm-config.spec.ts`).

- `test_radar_toggle_default_off_on_new_preset` (AC-1) — Preset ohne Feld anlegen,
  Alarme-Tab öffnen, Toggle vorhanden + nicht aktiv.
- `test_radar_toggle_enable_persists_roundtrip` (AC-2) — Toggle an, speichern, neu
  laden, Toggle aktiv (+ Preset `radar_alert_enabled === true`).
- `test_radar_toggle_preserved_on_unrelated_save` (AC-3) — Radar an, nur Name ändern
  + speichern, neu laden: Toggle weiterhin an (RMW-Zusammenspiel).

## Changelog

- 2026-07-10: Initial spec erstellt — Issue #1041, Slice 2 von 3 (Frontend-Schalter
  für `radar_alert_enabled`, Default AUS, #1040-Muster).
