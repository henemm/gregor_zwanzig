---
entity_id: issue_224_wizard_alert_rules_editor
type: module
created: 2026-05-15
updated: 2026-05-15
status: active
version: "1.0"
title: Wizard-Umstellung auf AlertRulesEditor
issue: 224
related: [223, 222, 205, 164, 136]
tags: [alerts, frontend, wizard, trip-new, issue-224, refactor]
approved_by: User
approved_date: 2026-05-15
---

<!-- Issue #224 — Wizard Step 4 auf AlertRulesEditor umstellen -->

# Issue 224 — Wizard-Umstellung auf AlertRulesEditor

## Approval

- [x] Approved (2026-05-15)

## Purpose

Heute haben Wizard (`/trips/new`) und Edit-Pfad (`/trips/[id]/edit`) unterschiedliche
UI-Konzepte für dasselbe Datenmodell (`Trip.alert_rules: AlertRule[]`): Der Wizard zeigt
vier feste Threshold-Felder mit fixem severity=warning, der Edit-Pfad nutzt seit Issue
#223 den `AlertRulesEditor` mit freier Metric (inkl. TEMPERATURE_MIN), freier Severity
und Add/Edit/Delete.

Dieser Workflow schließt diese Inkonsistenz durch vollständigen Rückbau des Wizard-eigenen
Threshold-Blocks und Integration der `AlertRulesEditor`-Komponente in Step 4 — eine
UI für ein Datenmodell. Die Bridge-Schicht (`mapBriefingsToAlertRules`, `BriefingConfig.thresholds`,
`report_config.alert_thresholds`) entfällt ersatzlos, weil für `alert_thresholds` null
Konsumenten im Codebase existieren (Phase-2-Verifikation: Grep über `src/`, `internal/`,
`api/`, `cmd/` ohne Fund).

## Source

- **MODIFY:** `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts`
  — `BriefingConfig.thresholds` und `defaultBriefingConfig.thresholds` entfallen;
  neuer Top-Level-State `alertRules: AlertRule[] = $state([])` (analog `stages`);
  `toTripPayload()`: `rc.alert_thresholds`-Block und `mapBriefingsToAlertRules`-Aufruf
  weg, ersetzt durch direktes `if (this.alertRules.length > 0) trip.alert_rules = JSON.parse(JSON.stringify(this.alertRules))`.
- **MODIFY:** `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte`
  — Sektion 3 ("Alert-Schwellwerte") wird ersetzt durch `<AlertRulesEditor bind:rules={wizard.alertRules} />`;
  Eyebrow-Label von "Alert-Schwellwerte" auf "Alarmregeln"; ThresholdRow-Imports und
  vier Threshold-Factory-Handler entfallen.
- **MODIFY:** `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts`
  — Threshold→AlertRule-Tests (Z. 77–135, 720–762) löschen, neue Tests für direkten
  `alertRules`-State und `toTripPayload`-Verhalten schreiben.
- **MODIFY:** `frontend/e2e/trip-wizard-step4.spec.ts`
  — AC#9/AC#10 (Threshold-TestIDs) auf `alert-rules-editor`/`alert-rule-row` umstellen;
  neuer Test: TEMPERATURE_MIN + critical-Severity über Wizard anlegbar (AC-8).
- **MODIFY:** `frontend/e2e/helpers.ts`
  — `Step4Input.thresholds` und `fillStep4`-Threshold-Block (Z. 136–141, 195–218)
  auf `Step4Input.alertRules: AlertRule[]` umstellen.
- **DELETE:** `frontend/src/lib/utils/alertMapping.ts`
- **DELETE:** `frontend/src/lib/utils/alertMapping.test.ts`
- **DELETE:** `frontend/src/lib/components/trip-wizard/steps/ThresholdRow.svelte`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertRulesEditor.svelte` | Svelte-Komponente | Wiederverwendbarer Editor aus Issue #223 (`bind:rules`) |
| `AlertRuleRow.svelte` | Svelte-Komponente | Zeile mit View/Edit-Modi, aus Issue #223 |
| `alertRuleDefaults.ts` (`newDefaultRule()`) | TS-Funktion | Default-Regel für Add-Button (wind_gust=50 km/h, warning) |
| `AlertRule`, `AlertMetric`, `AlertSeverity` | TS-Type | `frontend/src/lib/types.ts:41-79` |
| `Trip.alert_rules` | `AlertRule[] | undefined` | Datenmodell aus Issue #205 |
| `WizardState` | Klasse | `wizardState.svelte.ts` — `alertRules`-State, `toTripPayload()`, `briefings` |
| `BriefingConfig` | interface | Nur `channels` und `reports` bleiben erhalten; `thresholds` entfällt |
| `TripEditView.svelte:26–28` | Referenz-Implementierung | Muster für `alertRules`-Initialisierung und Save-Tiefkopie |
| `crypto.randomUUID()` | Browser-API | ID für neue Rules (via `newDefaultRule()`) |

## Implementation Details

### 1. `WizardState` — State-Umbau

`BriefingConfig` verliert den `thresholds`-Block vollständig:

```typescript
// VORHER (wizardState.svelte.ts, BriefingConfig):
export interface BriefingConfig {
  channels: { email: boolean; signal: boolean; telegram: boolean; sms: boolean };
  reports: {
    morning: { enabled: boolean; time: string };
    evening: { enabled: boolean; time: string };
  };
  thresholds: {                           // <-- ENTFÄLLT
    gust_kmh: number | null;
    precip_mm: number | null;
    thunder_level: 'NONE' | 'MED' | 'HIGH' | null;
    snow_line_m: number | null;
  };
}

// NACHHER:
export interface BriefingConfig {
  channels: { email: boolean; signal: boolean; telegram: boolean; sms: boolean };
  reports: {
    morning: { enabled: boolean; time: string };
    evening: { enabled: boolean; time: string };
  };
  // thresholds entfernt — ersetzt durch WizardState.alertRules (AlertRule[])
}
```

Neuer Top-Level-State in der `WizardState`-Klasse (parallel zu `stages`):

```typescript
alertRules: AlertRule[] = $state([]);
```

`defaultBriefingConfig` verliert den `thresholds`-Sub-Block entsprechend.
`cloneBriefingConfig` (falls vorhanden) muss `thresholds` nicht mehr klonen.

### 2. `WizardState.toTripPayload()` — Rückbau der Bridge-Schicht

Der `alert_thresholds`-Block in `report_config` und der `mapBriefingsToAlertRules`-Aufruf
entfallen. Stattdessen direktes Schreiben von `alertRules` (Tiefkopie-Pattern analog
Edit-Pfad `TripEditView.svelte:26–28`):

```typescript
// ENTFERNT (wizardState.svelte.ts, toTripPayload):
// import { mapBriefingsToAlertRules } from '$lib/utils/alertMapping';
// const alertRules = mapBriefingsToAlertRules(b.thresholds);
// if (alertRules.length > 0) { payload.alert_rules = alertRules; }
//
// Auch in rc: alert_thresholds-Block entfällt komplett.

// NEU:
if (this.alertRules.length > 0) {
    trip.alert_rules = JSON.parse(JSON.stringify(this.alertRules));
}
```

Der `report_config`-Block (`rc`) schreibt weiterhin den Backward-Compat-Block
(`enabled`, `morning_time`, `evening_time`, `send_email`, `send_signal`, etc.),
aber KEINEN `alert_thresholds`-Sub-Block mehr.

### 3. `Step4Briefings.svelte` — Sektion 3 ersetzen

```svelte
<!-- VORHER (Sektion 3, ~40 LoC): -->
<Eyebrow>Alert-Schwellwerte</Eyebrow>
<GCard>
    <div data-testid="trip-wizard-step4-thresholds-list" class="space-y-3">
        <ThresholdRow label="Boeen" type="number" unit="km/h" ... />
        <ThresholdRow label="Niederschlag" type="number" unit="mm" ... />
        <ThresholdRow label="Gewitter" type="thunder" ... />
        <ThresholdRow label="Schneefallgrenze" type="number" unit="m" ... />
    </div>
</GCard>

<!-- NACHHER: -->
<Eyebrow>Alarmregeln</Eyebrow>
<AlertRulesEditor bind:rules={wizard.alertRules} />
```

Ebenfalls zu entfernen: Import von `ThresholdRow`, vier `makeThresholdHandler`-
Funktionen und der `ThunderLevel`-Typ-Import, die nur für Sektion 3 benötigt werden.
Die anderen Sektionen (Channels, Reports) und ihr Factory-Pattern bleiben unverändert.

### 4. `helpers.ts` — `fillStep4` auf AlertRules umstellen

```typescript
// VORHER:
export interface Step4Input {
  // ...
  thresholds?: {
    gust_kmh?: number | null;
    precip_mm?: number | null;
    thunder_level?: 'NONE' | 'MED' | 'HIGH' | null;
    snow_line_m?: number | null;
  };
}

// NACHHER:
export interface Step4Input {
  channels?: { email?: boolean; signal?: boolean; telegram?: boolean };
  reports?: {
    morning?: { enabled?: boolean; time?: string };
    evening?: { enabled?: boolean; time?: string };
  };
  alertRules?: AlertRule[];   // NEU — ersetzt thresholds
  expectSaveSuccess?: boolean;
}
```

`fillStep4` fügt für jeden Eintrag in `alertRules` eine neue Regel über den Add-Button
hinzu und befüllt die Edit-Felder (`alert-rule-metric`, `alert-rule-threshold`,
`alert-rule-severity`) pro Regel.

### 5. Dateien löschen

| Datei | Grund |
|-------|-------|
| `frontend/src/lib/utils/alertMapping.ts` | Wird nur von `wizardState.svelte.ts:toTripPayload()` aufgerufen — entfällt mit dem Aufruf |
| `frontend/src/lib/utils/alertMapping.test.ts` | Testet ausschließlich die gelöschte Funktion |
| `frontend/src/lib/components/trip-wizard/steps/ThresholdRow.svelte` | Wird ausschließlich in `Step4Briefings.svelte` Sektion 3 verwendet — entfällt mit dem Block |

## Migration / Rückbau

| Artefakt | Aktion | Hinweis |
|----------|--------|---------|
| `alertMapping.ts` + Test | Löschen | Keine anderen Aufrufer; `grep -r mapBriefingsToAlertRules` findet nur `wizardState.svelte.ts` |
| `ThresholdRow.svelte` | Löschen | Nur in Sektion 3 von `Step4Briefings.svelte` verwendet |
| `BriefingConfig.thresholds` | Typ-Schnitt | Aus Interface und `defaultBriefingConfig` entfernen |
| `report_config.alert_thresholds` | Nicht mehr schreiben | Null Konsumenten; bestehende Trips mit gespeichertem `alert_thresholds` laufen weiter (Feld wird von Go-Backend und Python-Loader ignoriert) |
| Issue #205-Migration `_migrate_legacy_alert_rules()` | Nicht berührt | Diese Migration konvertiert `change_threshold_*` → `alert_rules`, nicht `alert_thresholds` — unabhängig von Issue #224 |
| `epic_136_step4_briefings.md` AC#9/#10/#14/#18/#18b/#19 | Als obsolet markieren | Threshold-TestIDs (`trip-wizard-step4-threshold-*`, `trip-wizard-step4-thresholds-list`) existieren nach Umbau nicht mehr |

Bestehende Trips mit `report_config.alert_thresholds` aus der W2-Bridge brechen nicht:
Es gibt keinen Reader für dieses Feld im Code — es wird beim nächsten Save des Trips
stillschweigend verworfen. Die maßgebliche Quelle ist `alert_rules` (seit W1 / Issue #205).

## TestIDs

### Neu (durch AlertRulesEditor-Integration)

| TestID | Komponente | Zweck |
|--------|------------|-------|
| `alert-rules-editor` | `AlertRulesEditor.svelte` (Root) | Haupt-Container des Editors in Step 4 |
| `alert-rules-editor-empty` | `AlertRulesEditor.svelte` | Empty-State "Noch keine Alarmregeln konfiguriert" |
| `alert-rules-editor-add` | Add-Button in `AlertRulesEditor.svelte` | Neue Regel hinzufügen |
| `alert-rule-row` | `AlertRuleRow.svelte` (View-Mode) | Einzelne Regel in der Liste (View) |
| `alert-rule-edit` | `AlertRuleRow.svelte` (Edit-Mode) | Edit-Form einer Regel |
| `alert-rule-metric` | Select in Edit-Form | Metric-Auswahl |
| `alert-rule-threshold` | Input/Select in Edit-Form | Schwellwert-Eingabe |
| `alert-rule-severity` | Select in Edit-Form | Severity-Auswahl |
| `alert-rule-save` | Button in Edit-Form | Änderung bestätigen |
| `alert-rule-cancel` | Button in Edit-Form | Änderung verwerfen |
| `alert-rule-edit-btn` | Button in View-Mode | Edit-Modus starten |
| `alert-rule-delete` | Button in View-Mode | Regel löschen |

### Entfernt (Threshold-Block)

| TestID | War in |
|--------|--------|
| `trip-wizard-step4-thresholds-list` | Sektion-3-Container in `Step4Briefings.svelte` |
| `trip-wizard-step4-threshold-gust` | `ThresholdRow` Böen |
| `trip-wizard-step4-threshold-precip` | `ThresholdRow` Niederschlag |
| `trip-wizard-step4-threshold-thunder` | `ThresholdRow` Gewitter |
| `trip-wizard-step4-threshold-snow` | `ThresholdRow` Schneefallgrenze |

## Expected Behavior

- **Input:** Wizard Step 4 wird geöffnet, `WizardState.alertRules` ist `[]`.
- **Sichtbar:** Sektion 1 (Kanäle) und Sektion 2 (Reports) unverändert;
  Sektion 3 zeigt `<AlertRulesEditor>` mit Empty-State und Add-Button.
- **Add-Regel:** Klick auf "+ Regel hinzufügen" erzeugt Default-Regel (wind_gust=50 km/h, warning,
  enabled). User kann Metric, Threshold und Severity frei editieren, inkl. TEMPERATURE_MIN
  und critical-Severity.
- **Save:** `state.save()` → `toTripPayload()` schreibt `trip.alert_rules` aus `this.alertRules`
  (Tiefkopie) — kein `alert_thresholds`-Block in `report_config`. POST `/api/trips`.
- **Kein Save bei leer:** Bei 0 Regeln fehlt `trip.alert_rules` im Payload (oder ist undefined).
- **Bestehende Trips (Read):** `AlertsPreviewCard` liest unverändert `trip.alert_rules` —
  keine Änderung am Read-Pfad.
- **Side effects:** `mapBriefingsToAlertRules` wird nicht mehr aufgerufen. Gelöschte Dateien
  sind nicht mehr importierbar.

## Acceptance Criteria

- **AC-1:** Given Wizard Step 4 wird geladen
  When User auf `/trips/new` navigiert und bis Step 4 voranschreitet
  Then ist `[data-testid="alert-rules-editor"]` sichtbar und kein Element mit `data-testid="trip-wizard-step4-threshold-gust"` (oder anderen alten Threshold-TestIDs) existiert im DOM.
  - Test: (populated after /tdd-red)

- **AC-2:** Given `WizardState` wird frisch instanziiert (kein bestehender Trip)
  When `wizardState.alertRules` gelesen wird ohne vorherige Mutation
  Then ist der Wert ein leeres Array (`alertRules.length === 0`).
  - Test: (populated after /tdd-red)

- **AC-3:** Given Step 4 mit leerem `AlertRulesEditor` (Empty-State sichtbar)
  When User auf den Add-Button (`[data-testid="alert-rules-editor-add"]`) klickt
  Then ist `wizard.alertRules.length === 1` und `[data-testid="alert-rule-row"]` erscheint einmal im DOM.
  - Test: (populated after /tdd-red)

- **AC-4:** Given `wizard.alertRules` enthält eine Regel
  When `toTripPayload()` aufgerufen wird
  Then enthält der zurückgegebene Trip-Payload ein `alert_rules`-Array mit genau dieser Regel (Tiefkopie, keine Referenz-Gleichheit).
  - Test: (populated after /tdd-red)

- **AC-5:** Given `wizard.alertRules` ist leer (`[]`)
  When `toTripPayload()` aufgerufen wird
  Then enthält der Payload kein `alert_rules`-Feld (oder `undefined`/leeres Array) — keine leere Liste wird persistiert.
  - Test: (populated after /tdd-red)

- **AC-6:** Given `wizard.alertRules` enthält eine oder mehrere Regeln
  When `toTripPayload()` aufgerufen wird
  Then enthält `payload.report_config` keinen `alert_thresholds`-Key (Block vollständig entfernt).
  - Test: (populated after /tdd-red)

- **AC-7:** Given TypeScript-Compiler prüft `wizardState.svelte.ts` nach dem Umbau
  When `tsc --noEmit` oder `npm run check` ausgeführt wird
  Then existiert `BriefingConfig.thresholds` nicht mehr als Typ-Member und kein Zugriff auf `.thresholds` kompiliert ohne Fehler.
  - Test: (populated after /tdd-red)

- **AC-8:** Given User startet einen neuen Trip, öffnet Step 4 und fügt eine Regel mit `metric=temperature_min` und `severity=critical` über den AlertRulesEditor hinzu
  When User auf Speichern klickt und der Trip angelegt wird
  Then zeigt die `AlertsPreviewCard` auf der Trip-Detailseite die Tiefsttemperatur-Regel mit Pill-Tone "danger" (critical→danger-Mapping).
  - Test: (populated after /tdd-red)

- **AC-9:** Given das Dateisystem nach Abschluss des Workflows
  When `frontend/src/lib/utils/alertMapping.ts` und `alertMapping.test.ts` gesucht werden
  Then existieren beide Dateien nicht mehr; `grep -r mapBriefingsToAlertRules frontend/src` liefert keinen Treffer.
  - Test: (populated after /tdd-red)

- **AC-10:** Given das Dateisystem nach Abschluss des Workflows
  When `frontend/src/lib/components/trip-wizard/steps/ThresholdRow.svelte` gesucht wird
  Then existiert die Datei nicht mehr; kein Import von `ThresholdRow` in `Step4Briefings.svelte`.
  - Test: (populated after /tdd-red)

- **AC-11:** Given ein bestehender Trip mit persistiertem `report_config.alert_thresholds` aus einer früheren W2-Bridge-Session
  When der Trip über `GET /api/trips/:id` geladen und in der `AlertsPreviewCard` angezeigt wird
  Then bricht die Anzeige nicht ab und `alert_rules` (aus dem gleichen oder einem früheren Save) wird korrekt gelesen; `alert_thresholds` wird stillschweigend ignoriert.
  - Test: (populated after /tdd-red)

- **AC-12:** Given User legt über den Wizard einen Trip mit einer Alarmregel (`metric=wind_gust`, `threshold=65`, `severity=warning`) an
  When der Trip gespeichert und anschließend über `GET /api/trips/:id` neu geladen wird
  Then enthält `trip.alert_rules[0]` die Felder `metric='wind_gust'`, `threshold=65`, `severity='warning'` mit korrekten Typen (keine String-/Typ-Konversion-Verluste).
  - Test: (populated after /tdd-red)

## Out of Scope

- **Aktivitätsspezifische Wizard-Vorlagen** (z.B. "Sommer-Wandern" mit vorkonfigurierten Regeln) — Folge-Issue.
- **Δ-Schwellen-UI im Reports-Block** (`change_threshold_*`-Felder in `WizardStep4ReportConfig`) — bleiben unverändert in `report_config`, werden nur über den Edit-Pfad konfiguriert.
- **Backend-Änderungen** — `alert_rules`-Read-Pfad ist seit Issue #205 und W1 (Issue #222) etabliert; keine Go-/Python-Änderungen nötig.
- **SMS-Channel und andere neue Channels** — bleiben wie in Sub-Spec #164 definiert.
- **`AlertsPreviewCard` Edit-Link** — wurde in Issue #223 wiederhergestellt; keine Änderung in Issue #224.

## Risiken & Open Questions

Alle Phase-2-Fragen sind entschieden:

- `alert_thresholds`-BC-Block: Null Konsumenten verifiziert → kann entfallen (AC-6).
- Default-Start leeres Array: konsistent mit Edit-Pfad und bisherigem Null-Threshold-Verhalten (AC-2).
- End-to-End-Severity-Roundtrip: durch Phase-2-Code-Recherche bis `weather_change_detection.py:282–286` bestätigt (AC-8, AC-12).
- `fillStep4`-Signatur-Bruch: nur `helpers.ts` selbst verwendet `Step4Input.thresholds` → kein externer Aufrufer betroffen.

Keine offenen Fragen.

## Known Limitations

- **`BriefingConfig.thresholds`-Entfernung ist breaking** für jeglichen Code, der dieses Interface direkt nutzt. Gemäß Phase-2-Analyse gibt es keine externen Konsumenten außer `wizardState.svelte.ts` selbst — TypeScript-Compiler deckt verbliebene Referenzen auf.
- **Tiefkopie via `JSON.parse(JSON.stringify(...))` verliert `undefined`-Werte** falls einzelne `AlertRule`-Felder optional undefined sind. Das `AlertRule`-Interface aus Issue #205/#223 ist vollständig definiert (kein optionales Feld mit `undefined`) — kein praktisches Risiko.
- **Aktivitätsspezifische Alert-Vorlagen fehlen weiterhin.** Für GR20-Trips (Sommer-Trekking) wären Böen=70 km/h + Gewitter=HOCH sinnvolle Defaults — das ist Folge-Issue-Material.

## Changelog

- 2026-05-15: Initial spec für Issue #224 (Wizard-Umstellung auf AlertRulesEditor). Strategie aus Phase-2-Kontext-Analyse übernommen: `BriefingConfig.thresholds` entfällt, `alertRules: AlertRule[] = $state([])` als Top-Level-State, `mapBriefingsToAlertRules` und `alert_thresholds`-Block gelöscht (null Konsumenten), 12 Acceptance Criteria (AC-N-Format), TestID-Inventar (neu + entfernt), Migration-Tabelle, Out-of-Scope explizit.
