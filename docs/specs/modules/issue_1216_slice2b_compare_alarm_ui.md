---
entity_id: issue_1216_slice2b_compare_alarm_ui
type: module
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [official-alerts, compare, alert-trigger, ui, scheduler, convergence]
workflow: feature-1216-compare-alarm-ui
---

# Ortsvergleich-Standalone-Alarm für amtliche Warnungen (#1216 Slice 2b, Editor-UI + Go-Scheduler)

## Approval

- [x] Approved (PO 'go', 2026-07-11)

## Purpose

Der amtliche Standalone-Alarm für den Ortsvergleich (Slice 2a, Backend, bereits live)
feuert heute nur bei manuellem Endpoint-Aufruf, und seine drei steuernden
Preset-Felder (`official_alert_triggers_enabled`, `send_telegram`, `send_sms`) sind
weder persistierbar noch im Editor sichtbar. Diese Slice macht den Alarm
**steuerbar** (ein sichtbarer An/Aus-Schalter im Alarme-Tab des Ortsvergleich-Editors,
plus Wiederverwendung der bestehenden Kanal-Toggles E-Mail/Telegram/SMS aus dem
Versand-Tab) und **automatisch** (neuer Go-Scheduler-Job, der den bestehenden
Python-Endpoint alle 15 Minuten für alle Nutzer aufruft).

## Source

- **File:** `internal/model/compare_preset.go` (MODIFY — `ComparePreset` +3 Pointer-Felder)
- **File:** `internal/handler/compare_preset.go` (MODIFY — `UpdateComparePresetHandler` RMW-Merge der 3 Felder)
- **File:** `internal/scheduler/scheduler.go` (MODIFY — Job-Methode `compareOfficialAlertChecks` + Jobs-Tabelle + Log „8"→„9")
- **File:** `internal/scheduler/scheduler_test.go` (MODIFY — `len(jobs)` 8→9 + Job-Assertion)
- **File:** `internal/handler/compare_preset_official_alerts_test.go` (CREATE/MODIFY — Roundtrip-Test, zwei User)
- **File:** `frontend/src/lib/types.ts` (MODIFY — `ComparePreset` +3 optionale Felder)
- **File:** `frontend/src/lib/components/compare/compareWizardState.svelte.ts` (MODIFY — neue Rune `officialAlertTriggersEnabled`; `sendTelegram`/`sendSms` zusätzlich in `saveNewPreset()`-Payload)
- **File:** `frontend/src/lib/components/compare/CompareAlarmSection.svelte` (MODIFY — neuer `ChannelToggle` „Amtliche-Warnungen-Alarm")
- **File:** `frontend/src/lib/components/compare/compareEditorSave.ts` (MODIFY — `CompareEditorEdits` +3 Felder + Spread-Guards)
- **File:** `frontend/src/lib/components/compare/CompareEditor.svelte` (MODIFY — Dirty-Baseline/Snapshot an 5 Stellen für den Trigger, plus Aufnahme der Kanal-Toggles in Dirty-Tracking + PUT-Payload)
- **Identifier:** `compareOfficialAlertChecks`, `UpdateComparePresetHandler`, `CompareWizardState.officialAlertTriggersEnabled`, `buildComparePresetSavePayload`
- **Python:** KEINE Änderung — `src/services/compare_official_alert.py` liest die Keys bereits (Slice 2a).

Schicht: **Go-API** (`internal/`) + **Frontend** (`frontend/src/lib/components/compare/`).

## Estimated Scope

- **LoC:** ~+130 / −5 (inkl. Tests)
- **Files:** ~10–12 (6 Go/Frontend-Produktivdateien + Tests)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ComparePreset.OfficialAlertsEnabled` / `RadarAlertEnabled` (`compare_preset.go:39,46`) | Go-Vorbild | Pointer-Pattern (`*bool`, nil=Default) für die 3 neuen Felder |
| `UpdateComparePresetHandler` RMW-Block (`compare_preset.go:213-239`) | Go-Vorbild | nil-Merge-Muster für neue Felder |
| `compareRadarAlertChecks` (`scheduler.go:174-180`) | Go-Vorbild | Schlanker Job-Wrapper `recordRun(id, runForAllUsers(id, path))` |
| `runForAllUsers` / `triggerEndpointForUser` (`scheduler.go:124-147`) | Go-Baustein | Ruft Endpoint für alle registrierten User auf |
| `POST /api/scheduler/compare-official-alert-checks` (Slice 2a, `api/routers/scheduler.py:90-98`) | bestehender Endpoint | Ziel des neuen Scheduler-Jobs — unverändert |
| `src/services/compare_official_alert.py:71,151,153` | bestehender Python-Service | Liest die 3 Preset-Keys bereits — kein Code-Änderungsbedarf |
| `ChannelToggle` (`$lib/components/shared/ChannelToggle.svelte`) | Frontend-Atom | Callback-Toggle (`onchange`, kein `bind:`) — Vorbild „Radar-Alarm" (`CompareAlarmSection.svelte:52-57`) |
| `buildComparePresetSavePayload` Spread-Guard-Muster (`compareEditorSave.ts:105-121`) | Frontend-Vorbild | `...(edits.X !== undefined ? {json_key: edits.X} : {})` für Round-Trip-sicheres PUT |
| `CompareEditor.svelte` Dirty-Baseline (`:77-93,94-108,167-217`) | Frontend-Vorbild | 5-Stellen-Snapshot-Pattern (initial-Objekt, dirty-Derived, gespeicherte Konstante vor async, Edits-Objekt, Post-Save-Reset) |
| `CompareWizardState.saveNewPreset()` (`compareWizardState.svelte.ts:165-206`) | Frontend-Bestand | Create-Pfad (POST `/api/compare/presets`) — muss die 3 Felder ebenfalls senden |

## Implementation Details

### 1. Go-Modell — drei neue Pointer-Felder auf `ComparePreset`

In `internal/model/compare_preset.go` nach dem bestehenden `AlertQuietTo`-Feld:

```go
OfficialAlertTriggersEnabled *bool `json:"official_alert_triggers_enabled,omitempty"`
SendTelegram                 *bool `json:"send_telegram,omitempty"`
SendSms                      *bool `json:"send_sms,omitempty"`
```

Pointer-Pattern wie `OfficialAlertsEnabled`: `nil` = Feld fehlte im JSON (Altdaten) →
Python-Default (`True` für den Trigger, `False`/falsy für die Kanäle) greift beim
Lesen; ein gesetzter Wert ist eine bewusste Nutzer-Entscheidung.

### 2. Go-Handler — Read-Modify-Write-Merge

In `UpdateComparePresetHandler` (`internal/handler/compare_preset.go`), analog zum
bestehenden Block für `OfficialAlertsEnabled`/`RadarAlertEnabled`
(`:213-239`), je neuem Feld:

```go
if updated.OfficialAlertTriggersEnabled == nil {
    updated.OfficialAlertTriggersEnabled = original.OfficialAlertTriggersEnabled
}
if updated.SendTelegram == nil {
    updated.SendTelegram = original.SendTelegram
}
if updated.SendSms == nil {
    updated.SendSms = original.SendSms
}
```

Kein Replace — `SaveComparePresets` serialisiert nur Struct-Felder, ein fehlender
Merge würde die Felder beim nächsten PUT stillschweigend löschen (Daten-Schema-Regel,
CLAUDE.md). `user_id` bleibt wie im Bestandscode aus `middleware.UserIDFromContext` +
`s.WithUser` (Zeile 175) — niemals `"default"`.

### 3. Go-Scheduler — neuer Job

In `internal/scheduler/scheduler.go`:
- Neue Job-Methode nach Vorbild `compareRadarAlertChecks` (`:174-180`):
  ```go
  func (s *Scheduler) compareOfficialAlertChecks() {
      s.recordRun("compare_official_alert_checks", func() error {
          return s.runForAllUsers("compare_official_alert_checks", "/api/scheduler/compare-official-alert-checks")
      })
  }
  ```
- Neue Zeile in der Jobs-Tabelle (`:91-102`): `{"*/15 * * * *", s.compareOfficialAlertChecks, "compare_official_alert_checks", "Compare Official Alert Checks (every 15 min)"}`
- Job-Anzahl an **zwei** Stellen synchron 8→9 anheben: Log `"Started: 8 jobs"` (`:114`)
  → `"Started: 9 jobs"`, und in `internal/scheduler/scheduler_test.go` die Assertion
  `len(jobs) != 8` (`:199-201`) → `!= 9`.

### 4. Frontend — Typ, State, Render, Save (6 Stellen)

- **Typ** (`frontend/src/lib/types.ts`, nach `alert_quiet_to`): `official_alert_triggers_enabled?: boolean`,
  `send_telegram?: boolean`, `send_sms?: boolean`.
- **State-Rune** (`compareWizardState.svelte.ts`, nach `hourlyEnabled`): neue Rune
  `officialAlertTriggersEnabled = $state(true)` (Default AN). Die Runen `sendTelegram`/
  `sendSms` (`:34-35`) existieren bereits — **werden wiederverwendet**, keine neue
  Kanal-Rune. Sie fließen heute nur in den Legacy-Subscription-Save
  (`toggleEnabled`/`save()`, `:90-92,133-135`); dieser Pfad bleibt unverändert.
- **Render** (`CompareAlarmSection.svelte`): neuer `ChannelToggle` „Amtliche-Warnungen-Alarm"
  direkt neben dem bestehenden „Radar-Alarm"-Toggle (`:52-57`), `testid="compare-alarm-official-toggle"`.
  **Kein neuer Kanal-Selektor** in diesem Tab — Kanäle bleiben in Step5Versand (Design-Entscheidung, wahrt #1169-Kommentar).
- **PUT-Save** (`compareEditorSave.ts`): `CompareEditorEdits` +
  `officialAlertTriggersEnabled?: boolean`, `sendTelegram?: boolean`, `sendSms?: boolean`;
  im `body`-Objekt je ein Spread-Guard analog `radarAlertEnabled` (`:110-113`):
  ```ts
  ...(edits.officialAlertTriggersEnabled !== undefined
      ? { official_alert_triggers_enabled: edits.officialAlertTriggersEnabled } : {}),
  ...(edits.sendTelegram !== undefined ? { send_telegram: edits.sendTelegram } : {}),
  ...(edits.sendSms !== undefined ? { send_sms: edits.sendSms } : {})
  ```
- **POST-Save** (`saveNewPreset()`, `compareWizardState.svelte.ts:165-198`): Payload
  ergänzt um `official_alert_triggers_enabled: this.officialAlertTriggersEnabled`,
  `send_telegram: this.sendTelegram`, `send_sms: this.sendSms` — heute fehlen dort
  alle drei, der Create-Pfad persistiert sie sonst nie.
- **Dirty-Baseline** (`CompareEditor.svelte:77-217`): an den 5 bestehenden Snapshot-
  Stellen (initial-Objekt `:77-93`, `dirty`-Derived `:94-108`, `savedX`-Konstanten vor
  dem `api.put`-Aufruf `:167-180`, `edits`-Objekt an `buildComparePresetSavePayload`
  `:181-201`, Post-Save-Reset `:204-217`) werden `officialAlertTriggersEnabled`,
  `sendTelegram`, `sendSms` ergänzt — analog zum bestehenden `radarAlertEnabled`/
  `officialAlertsEnabled`-Muster, damit Änderungen an den neuen Toggles die
  Speichern-Pille aktivieren und tatsächlich im PUT landen.

### 5. Label-Abgrenzung (UI-Text)

- Versand-Tab, bestehend, unverändert: **„Amtliche Warnungen"** (`official_alerts_enabled`,
  steuert nur Abfrage/Anzeige der Quellen).
- Alarme-Tab, neu: **„Amtliche-Warnungen-Alarm"** (`official_alert_triggers_enabled`,
  steuert ob der Standalone-Alarm für diesen Vergleich feuert). Exakter Label-Text ist
  PO-freizugeben (siehe Known Limitations).

## Expected Behavior

- **Input:** Nutzer schaltet im Alarme-Tab „Amtliche-Warnungen-Alarm" um und/oder
  aktiviert Telegram/SMS im Versand-Tab; speichert den Vergleich (Edit- oder Create-Pfad).
- **Output:** Preset-JSON (`data/users/<uid>/compare_presets.json`) enthält die drei
  Felder; `CompareOfficialAlertService` (Slice 2a) respektiert sie beim nächsten
  Scheduler-Lauf ohne Code-Änderung.
- **Side effects:** Go-Scheduler ruft `/api/scheduler/compare-official-alert-checks`
  alle 15 Minuten für jeden registrierten Nutzer auf; `last_run` erscheint im
  Status-Endpoint (`/api/scheduler/status`).

## Test Plan

| # | Ebene | Test | Deckt AC |
|---|-------|------|----------|
| T1 | Go (Kern) | `compare_preset_official_alerts_test.go`: PUT-Roundtrip — Trigger `true`/`false` landet unverändert im gespeicherten Preset, GET liest ihn zurück | AC-1, AC-3 |
| T2 | Go (Kern) | Kanal-Roundtrip — `send_telegram`/`send_sms` `true` persistieren im Preset-JSON | AC-2 |
| T3 | Go (Kern) | RMW-Merge — partieller PUT (nur ein neues Feld) erhält `alert_cooldown_minutes` + die anderen zwei neuen Felder | AC-5 |
| T4 | Go (Kern) | Multi-User — zwei User-IDs, isolierte Store-Pfade, keine Cross-User-Werte, nie `"default"` | AC-6 |
| T5 | Go (Kern) | `scheduler_test.go`: `len(jobs) == 9`; neuer Job `compare_official_alert_checks` mit Cron `*/15 * * * *` registriert | AC-4 |
| T6 | Go (Kern) | Status-Endpoint listet den neuen Job mit `next_run`/`last_run` nach manuellem Trigger | AC-4 |
| T7 | Frontend (Kern) | Save-Payload-Test (`compareEditorSave.ts` + `saveNewPreset()`): PUT- und POST-Body enthalten alle drei Keys mit den State-Werten | AC-1, AC-2, AC-8 |
| T8 | Frontend (Kern) | Dirty-Tracking — Umschalten des Trigger- bzw. Kanal-Toggles aktiviert die Speichern-Pille, Reset nach Save | AC-8 |
| T9 | Frontend (Kern) | Label-/Tab-Abgrenzung — „Amtliche Warnungen" (Versand) und „Amtliche-Warnungen-Alarm" (Alarme) sind getrennte, unabhängig schaltbare Elemente | AC-9 |
| T10 | Python (Non-Regression) | Bestehende Suiten für `compare_alert.py`/`compare_radar_alert.py` bleiben grün — keine neue Kanal-Verzweigung, E-Mail-only unverändert | AC-7 |

Kein Mock-Theater: Go-Tests fahren echten Handler+Store, Frontend-Tests konstruieren echte Payloads. Python-Gating (Trigger AUS → Vergleich übersprungen) ist bereits durch die Slice-2a-Suite abgedeckt und wird hier nicht dupliziert.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer aktiviert im Alarme-Tab den Schalter „Amtliche-Warnungen-Alarm" und speichert / When das Preset über PUT gespeichert und danach neu geladen wird / Then enthält das persistierte JSON `official_alert_triggers_enabled: true`, und ein Alt-Preset ohne das Feld verhält sich beim Lesen durch `compare_official_alert.py:71` weiterhin als „an" (Default).
  - Test: echter Preset-Save-Roundtrip (FE-Payload → PUT-Handler → Store → erneutes GET), Assert Feldwert; separat Assert dass ein Fixture-Preset ohne den Key den Python-Default nicht bricht (Slice-2a-Testabdeckung).

- **AC-2:** Given ein Preset mit aktivierten Kanal-Toggles Telegram/SMS im Versand-Tab / When der Vergleich gespeichert wird / Then stehen `send_telegram: true` und `send_sms: true` im persistierten Preset-JSON, und ohne diesen Opt-in bleibt der amtliche Alarm E-Mail-only (Slice-2a-Verhalten unverändert).
  - Test: Save-Payload-Test (`compareEditorSave.ts` bzw. `saveNewPreset()`-Payload) prüft beide Keys im Body; kein Mock des HTTP-Layers, echte Payload-Konstruktion.

- **AC-3:** Given ein Nutzer schaltet „Amtliche-Warnungen-Alarm" aus und speichert / When `compare_official_alert.py` das persistierte Preset liest / Then überspringt der Service diesen Vergleich vollständig (Gating bereits in Slice-2a-AC-6 verifiziert) — diese Slice liefert lediglich den funktionierenden Persistenz-Pfad dorthin, ohne den Python-Code zu ändern.
  - Test: Go-Roundtrip bestätigt `false` landet unverändert im JSON; Python-seitiges Gating wird durch die bestehende Slice-2a-Testsuite abgedeckt (kein Duplikat).

- **AC-4:** Given der Go-Scheduler startet / When er initialisiert / Then ist der neue Job `compare_official_alert_checks` mit Cron `*/15 * * * *` registriert, der Scheduler meldet „Started: 9 jobs" im Log, `/api/scheduler/status` listet 9 Jobs, und nach einem Lauf zeigt der Job-Eintrag `last_run`.
  - Test: `scheduler_test.go` — `len(jobs) == 9`; Status-Endpoint-Test bestätigt den neuen Job mit `next_run`/`last_run`.

- **AC-5:** Given ein bestehendes Preset mit gesetztem `alert_cooldown_minutes` / When ein PUT nur `official_alert_triggers_enabled` ändert (restlicher Body ohne die anderen Felder) / Then bleiben `alert_cooldown_minutes`, `send_telegram`, `send_sms` und alle übrigen zuvor gesetzten Felder unverändert erhalten (Read-Modify-Write-Merge greift für alle drei neuen Felder).
  - Test: Go-Handler-Test — PUT mit partiellem Body, Assert alle Nicht-Zielfelder unverändert im gespeicherten Preset.

- **AC-6:** Given zwei verschiedene Nutzer A und B mit je einem eigenen Compare-Preset / When beide unabhängig `official_alert_triggers_enabled`/`send_telegram`/`send_sms` setzen und speichern / Then bleibt jede Änderung strikt im `user_id`-Scope (aus `middleware.UserIDFromContext`) — Nutzer A's Preset beeinflusst Nutzer B's Preset nicht, niemals `"default"`.
  - Test: `compare_preset_official_alerts_test.go` — zwei User-IDs, Assert isolierte Store-Pfade + keine Cross-User-Werte.

- **AC-7:** Given der bestehende Deviation-Alarm (#1169, `compare_alert.py:206`) und Radar-Onset-Alarm (`compare_radar_alert.py:115`) / When die neuen Kanal-Felder auf einem Preset gesetzt sind / Then bleiben beide Alarme strukturell E-Mail-only (hartkodiert) — die neuen Felder wirken ausschließlich auf den amtlichen Standalone-Alarm.
  - Test: Nicht-Regressions-Check der bestehenden Python-Testsuite für `compare_alert.py`/`compare_radar_alert.py` (unverändert grün, keine neue Kanal-Verzweigung dort).

- **AC-8:** Given der Compare-Editor im Edit-Modus / When der Nutzer den „Amtliche-Warnungen-Alarm"-Schalter oder einen Kanal-Toggle in Versand ändert / Then springt die Speichern-Pille von „gespeichert" auf „ungespeichert" (Dirty-Tracking erkennt die Änderung), und der PUT-Payload beim Speichern enthält die geänderten Felder; nach erfolgreichem Save springt die Pille zurück auf „gespeichert".
  - Test: Playwright/Component-Test — Toggle klicken, Assert Dirty-Indikator-Zustand, Assert PUT-Body-Feld gesetzt, Assert Reset nach Save.

- **AC-9:** Given der Ortsvergleich-Editor zeigt sowohl den bestehenden „Amtliche Warnungen"-Toggle (Versand-Tab, Fetch/Anzeige) als auch den neuen „Amtliche-Warnungen-Alarm"-Toggle (Alarme-Tab, Trigger) / When ein Nutzer beide Tabs öffnet / Then sind die beiden Schalter durch Label und Tab-Platzierung eindeutig unterscheidbar und unabhängig voneinander schaltbar.
  - Test: Component-Test prüft `data-testid`-getrennte Elemente in unterschiedlichen Tabs mit unterschiedlichem sichtbarem Label-Text.

## Known Limitations

- **Label-Text PO-freizugeben:** Der genaue sichtbare Text für „Amtliche-Warnungen-Alarm"
  ist ein UX-Detail und wird vor Implementierungsabschluss dem PO zur Freigabe vorgelegt
  (Abgrenzung zum bestehenden „Amtliche Warnungen"-Toggle muss für Endnutzer eindeutig sein).
- **Trigger-Default AN für Alt-Presets ist bewusst:** Bestehende Vergleiche ohne das Feld
  feuern den amtlichen Alarm sofort nach Deploy (kein Opt-in nötig) — analog
  `OfficialAlertsEnabled`. Begründung: amtliche Warnungen sind sicherheitsrelevant,
  Default-an ist der sichere Fehlerfall (Gegenteil von `RadarAlertEnabled`, das aus
  Netzwerkkosten-Gründen bewusst opt-in ist).
- **Kanal-Toggles bleiben global pro Preset, nicht pro Kanal-Empfänger:** Telegram/SMS
  nutzen die globale User-Konfiguration (wie beim Trip-Alarm), keine pro-Preset-Empfänger.
- **Deviation-/Radar-Compare-Alarme bleiben strukturell E-Mail-only** — außerhalb des
  Scopes dieser Slice, unverändert (Non-Regression, AC-7).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (additive Verdrahtung bestehender, in ADR-0011/ADR-0021 bereits
  entschiedener Muster: geteilter Official-Alert-Renderer bzw. geteilter Dispatch,
  jetzt erweitert um Persistenz + Scheduler nach dem in Slice 2a etablierten Vorbild)
- **Rationale:** Reine Persistenz-/Scheduler-Verdrahtung ohne neue Architektur-Entscheidung
  — folgt 1:1 den bestehenden Pointer-Pattern-/RMW-/Scheduler-Job-Konventionen
  (`OfficialAlertsEnabled`, `RadarAlertEnabled`, `compareRadarAlertChecks`).

## Changelog

- 2026-07-11: Initial spec (Slice 2b) erstellt
