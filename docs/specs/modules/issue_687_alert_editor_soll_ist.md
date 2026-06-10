---
entity_id: issue_687_alert_editor_soll_ist
type: module
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [alerts, frontend, channels, severity, consistency]
---

# Alert-Regel-Editor an #638-Karten-Modell angleichen (Severity raus, Kanal pro Alert rein)

## Approval

- [x] Approved (PO 'go' 2026-06-09)

## Purpose

Der Alert-Regel-**Editor** (`AlertRuleRow` / `AlertRulesEditor`), über den Alarmregeln beim Trip-Anlegen, Trip-Bearbeiten und im Wizard (Step 4) tatsächlich konfiguriert werden, wird mit der Issue-#638-Entscheidung in Einklang gebracht: die **Severity-Auswahl** (Info/Warnung/Kritisch) entfällt (Wert bleibt im Datenmodell erhalten), und jeder Alert erhält — wie im Anzeige-Tab (`AlertCard`) — eine **Kanal-Auswahl pro Regel** (E-Mail/Telegram/SMS), vorbelegt aus den aktiven Briefing-Kanälen und pro Alert überschreibbar.

## Source

- **Datei:** `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` (Severity raus + Kanal-Chips)
- **Datei:** `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` (neuer Prop `activeChannels`, Durchreichen)
- **Datei:** `frontend/src/lib/components/trip-new/TripNewEditor.svelte` (activeChannels aus `channels`)
- **Datei:** `frontend/src/lib/components/edit/TripEditView.svelte` (activeChannels aus `reportConfig.send_*`)
- **Datei:** `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` (activeChannels aus `wizard.briefings.channels`)
- **Identifier:** `AlertRuleRow`, `AlertRulesEditor`

> **Schicht:** Frontend / User-UI → `frontend/src/...` (SvelteKit). **Kein Backend-Eingriff**: `AlertRule.channels` und `AlertRule.severity` existieren bereits im Schema (TS/Go/Python), und der kanalbewusste Versand (`trip_alert.py`) wurde in #638 implementiert. Diese Spec verdrahtet nur die UI.

## Estimated Scope

- **LoC:** ~120 (Editor-Komponenten + 3 Einbau-Orte; reine UI-Verdrahtung)
- **Files:** 5 Produktiv-Dateien (+ Tests)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertCard.svelte` (#638) | Referenz | Vorbild für effectiveChannels-Logik + Chip-Rendering (Konsistenz) |
| `AlertRule` (`types.ts` / `models.py` / `trip.go`) | Schema | `channels`/`severity` bereits vorhanden — keine Schema-Änderung |
| `expandRules()` (`alertRuleDefaults.ts`) | upstream | Spreadt `...rest` → trägt `channels` (und `severity`) unverändert durch alle Modi |
| `report_config` / `wizard.briefings.channels` | Datenquelle | Vorbelegung der aktiven Kanäle |
| `trip_alert.py` (#638) | downstream | Respektiert `rule.channels` beim Versand (unverändert) |

## Implementation Details

### 1. Severity-Auswahl entfernen (`AlertRuleRow.svelte`)

- **Edit-Mode:** `<Select bind:value={draft.severity}>` mit Optionen Info/Warnung/Kritisch (Z. 235–242) **entfällt**.
- **View-Mode:** Severity-`<Pill>` (`SEVERITY_LABEL_DE[rule.severity]`, Z. 281–283) **entfällt**.
- Die Abs/Δ-Pill (Z. 278–280) **bleibt** (Modus-Info, nicht Severity).
- Ungenutzte Imports `SEVERITY_LABEL_DE`, `ALERT_SEVERITY_TONE` entfernen.
- **Datenerhalt (PFLICHT, BUG-DATALOSS-GR221):** `rule.severity` wird NICHT entfernt. `newDefaultRule()` setzt weiterhin `severity:'warning'`; `startEdit()` kopiert via `draft = {...rule}`; `saveEdit()` spreadt `...draft` → `severity` überlebt jeden Roundtrip unverändert.

### 2. Kanal-Auswahl pro Alert (analog `AlertCard`)

- `AlertRulesEditor` erhält Prop `activeChannels: string[]` (Default `[]`) und reicht ihn an jede `AlertRuleRow` weiter.
- `AlertRuleRow` erhält Prop `activeChannels: string[]` (Default `[]`).
- **effectiveChannels-Logik (1:1 wie AlertCard):**
  `draft.channels?.length ? draft.channels : [...activeChannels]` — leere/fehlende `channels` = „erbt alle aktiven Briefing-Kanäle".
- **Edit-Mode:** pro `ch` in `activeChannels` ein Toggle-Chip; Klick fügt `ch` zu `draft.channels` hinzu / entfernt ihn (immutabel: `draft = {...draft, channels: [...]}`). Persistenz via `saveEdit` → `expandRules` (`...rest` trägt `channels`) → `onSave`.
- **View-Mode:** Kanal-Chips read-only (`effectiveChannels` aus `rule.channels`/`activeChannels`) an Stelle der entfernten Severity-Pill — konsistent mit `AlertCard`.
- Chip-Labels konsistent zu `AlertCard`: `email→E-Mail`, `telegram→Telegram`, `sms→SMS`.

### 3. activeChannels an den drei Einbau-Orten ableiten

- **TripNewEditor:** `$derived` aus `channels` → `(['email','telegram','sms'] as const).filter(c => channels[c])`. An beide `<AlertRulesEditor>`-Instanzen (Desktop + Mobile) durchreichen.
- **TripEditView:** `$derived` aus `reportConfig` → `send_email/send_telegram/send_sms`.
- **Step4Briefings:** `$derived` aus `wizard.briefings.channels`.

## Expected Behavior

- **Input:** Nutzer öffnet den Alert-Editor (anlegen/bearbeiten/Wizard), bearbeitet eine Regel.
- **Output:** Kein Severity-Dropdown mehr; stattdessen Kanal-Chips, vorbelegt aus den aktiven Briefing-Kanälen, pro Alert umschaltbar.
- **Side effects:** Gesetzte Kanäle landen in `trip.alert_rules[].channels` und werden vom (bestehenden) kanalbewussten Versand respektiert. `severity` bleibt unverändert im Datensatz.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer im Trip-Bearbeiten-Editor mit mindestens einer Alarmregel / When er eine Regel in den Bearbeiten-Modus schaltet / Then erscheint **kein** Severity-Auswahlfeld (kein „Info/Warnung/Kritisch"-Dropdown) mehr im Editor.
  - Test: Playwright-E2E gegen Staging — Regel editieren, `[data-testid="alert-rule-severity"]` existiert nicht mehr im DOM.
- **AC-2:** Given eine Alarmregel im Ansichts-Modus (View) / When sie gerendert wird / Then erscheint **keine** Severity-Pill mehr, aber die Modus-Pill (Abs / Δ) bleibt erhalten.
  - Test: Playwright-E2E gegen Staging — Severity-Label (Info/Warnung/Kritisch) nicht im View; Abs/Δ-Pill sichtbar.
- **AC-3:** Given ein Trip, dessen aktive Briefing-Kanäle E-Mail und Telegram sind, und eine neue Alarmregel ohne eigene Kanäle / When der Editier-Modus geöffnet wird / Then sind die Kanal-Chips E-Mail und Telegram als aktiv (vorbelegt/geerbt) markiert, SMS inaktiv.
  - Test: Playwright-E2E gegen Staging — Chips-Zustand entspricht den aktiven Briefing-Kanälen.
- **AC-4:** Given eine Regel im Editier-Modus mit vorbelegten Kanälen / When der Nutzer den Telegram-Chip deaktiviert und speichert / Then wird die Regel mit ausschließlich E-Mail als Kanal persistiert und nach Reload zeigt der Editor weiterhin nur E-Mail aktiv.
  - Test: Playwright-E2E gegen Staging — Chip togglen, speichern, Seite neu laden, DB-Roundtrip über die UI bestätigt (Telegram-Chip inaktiv).
- **AC-5:** Given ein persistierter Bestands-Trip mit Alarmregeln, die ein `severity`-Feld tragen / When der Trip über den Editor geöffnet, eine Regel ohne Kanal-Änderung gespeichert und neu geladen wird / Then bleiben alle Regeln samt `severity`-Wert erhalten (kein Datenverlust), und `channels` defaultet weiterhin auf „erbt Briefing-Kanäle".
  - Test: Python/HTTP-Roundtrip-Verhaltenstest — Trip mit `severity`-tragenden Regeln laden → über Editor-PUT speichern → wieder laden → `severity` unverändert, Regel-Anzahl gleich.
- **AC-6:** Given der Alert-Editor im Trip-**Anlegen**, im Trip-**Bearbeiten** und im **Wizard** Step 4 / When jeweils eine Regel editiert wird / Then verhält sich die Kanal-Auswahl an allen drei Orten identisch (vorbelegt aus den dort aktiven Kanälen, überschreibbar) und keiner der drei zeigt noch ein Severity-Feld.
  - Test: Playwright-E2E gegen Staging — alle drei Einbau-Orte durchklicken; Severity-Feld nirgends, Kanal-Chips überall.

## Changelog

- 2026-06-09: Initial spec — Issue #687 (Alert-Editor Soll-Ist-Abgleich zu #638: Severity-Auswahl raus, Kanal pro Alert rein). PO-Scope-Entscheidung „Severity raus + Kanal pro Alert rein" am 2026-06-09.
