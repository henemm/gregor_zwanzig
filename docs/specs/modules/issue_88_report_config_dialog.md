---
entity_id: issue_88_report_config_dialog
type: module
created: 2026-05-15
updated: 2026-05-15
status: draft
version: "1.0"
tags: [frontend, sveltekit, trip-edit, report-config, ui-rework]
---

# Issue #88 — Dialog "Report Konfiguration" optimieren

## Approval

- [ ] Approved

## Purpose

Der Trip-Edit-Dialog für Report-Konfiguration wird auf eine 2-Report-Struktur (Morgen / Abend) umgestellt; die "Änderungs-Alerts" sind in `TripEditView.svelte` bereits als eigenes Accordion-Panel "Alarmregeln" mit `AlertRulesEditor` umgesetzt (Issue #223). Uhrzeit und Trend-Schalter werden pro Report gruppiert und nur aktiv, wenn der jeweilige Report eingeschaltet ist. Die alten `change_threshold_*`-Felder im Report-Dialog werden ersatzlos entfernt (Duplikat zur Alarmregeln-Sektion). Kanäle werden nur angeboten, wenn sie im User-Profil konfiguriert sind (sonst Link zur Konfiguration). Time-Picker bleibt native (`<input type="time">`) plus Quick-Picks.

## Source

- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte`
- **Identifier:** Gesamte Komponente — strukturelle Umstellung

> **PFLICHT — Schicht-Hinweis:** Frontend (SvelteKit) — keine Go-API- oder Python-Backend-Änderungen nötig, weil die `Trip.report_config`-Form schon flexibel ist und `Trip.alert_rules` via Wizard akzeptiert wird.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `AlertRulesEditor.svelte` | Frontend-Komponente | Wird in der "Änderungen"-Sektion eingebettet. Spec: `issue_224_wizard_alert_rules_editor.md`. |
| `Trip.report_config` | DTO-Feld | JSON-Blob. Felder: `enabled`, `morning_time`, `evening_time`, `send_email`, `send_signal`, `send_telegram`, `send_sms`, `multi_day_trend_morning`, `multi_day_trend_evening`, `show_compact_summary`, `show_daylight`, `wind_exposition_min_elevation_m`. |
| `Trip.alert_rules: AlertRule[]` | DTO-Feld | Wird beim Speichern aus dem AlertRulesEditor übernommen — Go-API akzeptiert das bereits (Wizard nutzt es). |
| `user.profile.{mail_to,signal_phone,telegram_chat_id}` | Endpunkt `/api/account` | Kanal-Verfügbarkeit. Wenn leer → "nicht konfiguriert"-Hinweis + Link `/account`. |
| `Step4Briefings.svelte` + `ReportRow.svelte` | Wizard-Komponenten | Visuelles Vorbild für 3-Report-Struktur und Time-Picker-Reihe. Nicht direkt importieren — eigene Edit-Variante mit gleicher Optik. |

## Implementation Details

### Neue Struktur des Dialogs (Accordion-Panel "Reports")

```
┌─ Morgen-Report ────────────────────────────────────┐
│ [✓] Morgen-Report aktivieren                        │
│   Uhrzeit: [07:00 ▼] [Morgens 07:00] [Abends 18:00] │
│   [✓] Trend über mehrere Tage zeigen               │
└─────────────────────────────────────────────────────┘
┌─ Abend-Report ─────────────────────────────────────┐
│ [✓] Abend-Report aktivieren                         │
│   Uhrzeit: [18:00 ▼] [Morgens 07:00] [Abends 18:00] │
│   [✓] Trend über mehrere Tage zeigen               │
└─────────────────────────────────────────────────────┘
┌─ Kanäle ───────────────────────────────────────────┐
│ [✓] E-Mail (mail.user@example.com)                  │
│ [ ] SMS  — nicht konfiguriert (Link: /account)      │
│ [✓] Signal (+43...)                                 │
└─────────────────────────────────────────────────────┘
┌─ Erweitert (collapsed) ────────────────────────────┐
│  [✓] Kompakte Zusammenfassung                       │
│  [✓] Tageslicht-Daten anzeigen                      │
│  Wind-Exposition ab Höhe: [1500] m                  │
└─────────────────────────────────────────────────────┘
```

> Die dritte Issue-#88-Sektion "Änderungs-Alerts" lebt bereits als eigenes Accordion-Panel **"Alarmregeln"** über dem "Reports"-Panel (Issue #223). Diese Spec touchiert das Alarmregeln-Panel nicht.

### Datenfluss

1. **Laden** (`onMount` / `$effect`):
   - `reportConfig` aus `Trip.report_config` lesen
   - **Alte `change_threshold_*`-Felder werden NICHT mehr gelesen** (ersatzlos raus aus der Komponente). Bleiben in `Trip.report_config` als Read-only-Mitfahr-Felder via Read-Modify-Write erhalten, falls Backend sie noch konsumiert — werden aber von der UI ignoriert. Alarm-Regeln werden ausschließlich im Accordion-Panel "Alarmregeln" gepflegt.
   - **Channel-Verfügbarkeit:** Aus `/api/account` (oder bereits geladenem Profile-Store) `mail_to`, `signal_phone`, `telegram_chat_id` lesen → `availableChannels: { email: boolean, signal: boolean, telegram: boolean, sms: boolean }`
2. **Edit:**
   - Master-Switch pro Report togglet `morning_enabled` / `evening_enabled` (lokaler Component-State)
   - Time-Inputs, Quick-Picks und Trend-Toggles sind `disabled={!morning_enabled}` bzw. `!evening_enabled`
   - Kanal-Checkboxen sind `disabled={!availableChannels[channel]}` und zeigen bei `disabled=true` einen `<a href="/account">nicht konfiguriert</a>`-Hinweis
3. **Speichern** (über bestehende `bind:reportConfig` aufwärts):
   - `reportConfig.morning_time`, `evening_time`, `multi_day_trend_morning`, `multi_day_trend_evening` wie heute
   - **Neu:** `reportConfig.morning_enabled`, `evening_enabled` (statt globalem `enabled`)
   - Backwards-Compat: synthetisches `enabled = morning_enabled || evening_enabled` zusätzlich mitschreiben, bis Backend explizit auf die neuen Flags umgestellt ist
   - **Read-Modify-Write:** Alle bestehenden, von der UI nicht angefassten Felder in `reportConfig` (inklusive `change_threshold_*`) bleiben byte-identisch erhalten — die UI tippt nur ausgewählte Felder an

### Time-Picker

- Native `<input type="time" bind:value={morning_time}>` (mobile iOS/Android öffnen native Picker)
- Direkt darunter 2 Quick-Pick-Buttons:
  - `<button on:click={() => morning_time = '07:00'}>Morgens 07:00</button>`
  - `<button on:click={() => evening_time = '18:00'}>Abends 18:00</button>` (in der Abend-Sektion)
- Buttons greifen visuell auf bestehende Token aus `design_system.md` zurück (Variant "secondary")

### Kanal-Verfügbarkeit

Mapping `channel ↔ profile-Feld`:
| Channel | Profile-Feld | Wenn leer |
|---------|-------------|-----------|
| `send_email` | `profile.mail_to` | Checkbox disabled, Hinweis "E-Mail-Adresse fehlt — [im Account einrichten](/account)" |
| `send_signal` | `profile.signal_phone` | Hinweis "Signal-Nummer fehlt — [im Account einrichten](/account)" |
| `send_telegram` | `profile.telegram_chat_id` | Hinweis "Telegram-Chat-ID fehlt — [im Account einrichten](/account)" |
| `send_sms` | `profile.sms_phone` *(falls vorhanden)* — sonst dauerhaft disabled bis Feature da | Hinweis "SMS nicht verfügbar" |

## Expected Behavior

- **Pre-Refactor:** Edit-Dialog hat 4 Checkboxen für Kanäle (immer aktiv), separate Schwellwert-Felder (Drift zum Wizard), alle Time-Inputs immer aktiv, "Erweitert" mit Trend-Schaltern.
- **Post-Refactor:** 3 logisch getrennte Sektionen, Disabled-Logik konsistent, Kanal-Conditional aktiv, AlertRulesEditor in "Änderungen"-Sektion, Bestands-Daten werden migriert (kein Datenverlust).
- **Side effects:** Wizard ist unverändert. Backend ist unverändert.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `report_config = {morning_time: "07:00", evening_time: "18:00", enabled: true}` / When der Edit-Dialog geöffnet wird / Then werden im "Reports"-Panel **zwei Sektionen** angezeigt: "Morgen-Report" und "Abend-Report", jede mit eigenem Master-Switch. Beide sind enabled (Migration: `enabled=true` + Zeit gesetzt → Master-Switch an).
  - Test: (populated after /tdd-red)

- **AC-2:** Given der Edit-Dialog ist offen, "Morgen-Report" Master-Switch ist AUS / When der User die Sektion anschaut / Then sind das Uhrzeit-Eingabefeld, beide Quick-Pick-Buttons und der Trend-Schalter **disabled** (HTML-`disabled`-Attribut + visuell ausgegraut). Dasselbe analog für "Abend-Report".
  - Test: (populated after /tdd-red)

- **AC-3:** Given die alten `change_threshold_*`-Felder existierten bisher in `EditReportConfigSection.svelte` / When der Refactor durch ist / Then enthält die Komponente **keine Eingabefelder mehr für Temperatur-, Wind-, Niederschlags-Schwellen**. Alarm-Regeln werden ausschließlich im "Alarmregeln"-Panel über `AlertRulesEditor` gepflegt.
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein User-Profil mit `mail_to` befüllt und `signal_phone` leer / When der Edit-Dialog geöffnet wird / Then ist die E-Mail-Kanal-Checkbox aktivierbar; die Signal-Kanal-Checkbox ist **disabled** und zeigt den Hinweis "Signal-Nummer fehlt — [im Account einrichten](/account)" als anklickbaren Link.
  - Test: (populated after /tdd-red)

- **AC-5:** Given die Morgen-Sektion ist AN, der User klickt den Quick-Pick-Button "Morgens 07:00" / When er den Klick auslöst / Then wird `morning_time` auf `"07:00"` gesetzt und im Time-Input angezeigt. Analog für "Abends 18:00" in der Abend-Sektion.
  - Test: (populated after /tdd-red)

- **AC-6:** Given die Morgen-Sektion ist AN / When der User den "Trend über mehrere Tage zeigen"-Schalter innerhalb der Morgen-Sektion togglet / Then ändert sich `reportConfig.multi_day_trend_morning` entsprechend. Beim Speichern landet der Wert korrekt in `Trip.report_config`.
  - Test: (populated after /tdd-red)

- **AC-7:** Given ein Trip mit unbekannten Feldern in `report_config` (z. B. `change_threshold_temp_c`, oder eigene Custom-Felder) / When der User den Edit-Dialog öffnet, nichts ändert und speichert / Then sind diese unbekannten Felder **byte-identisch** wie vorher erhalten (Read-Modify-Write — keine Daten-Drift).
  - Test: (populated after /tdd-red)

## Out of Scope

- Änderungen am Wizard (`Step4Briefings.svelte`) — der ist bereits konform mit dieser Struktur
- Änderungen an der Go-API oder am Python-Backend (`Trip.alert_rules` wird vom Wizard schon geschrieben, Backend akzeptiert es)
- SMS-Channel-Implementierung (`profile.sms_phone` existiert nicht — falls SMS in Zukunft kommt, wird die Disabled-Logik konsistent dranbleiben)
- Custom Time-Picker-Bibliothek einführen (native + Quick-Picks ist die Lösung)
- E2E-Tests gegen das Verschicken echter Reports (nur Frontend-Unit-/Integration-Tests im Scope)

## Verification

- **Frontend Unit-Tests** (Vitest, falls vorhanden): Component-Tests gegen `EditReportConfigSection.svelte` mit Mock-`Trip.report_config` und Mock-`profile`. Pro AC mindestens 1 Assertion.
- **Visuell** (Playwright/Safari Hard-Reload):
  - Trip öffnen, Edit-Dialog auf https://staging.gregor20.henemm.com
  - Beobachtbar: 3 Sektionen sichtbar, Master-Switches togglen die Disabled-Logik, Kanal-Hinweise erscheinen wenn Profile-Felder leer
- **Backend-Roundtrip (Integration):** Trip via API laden → Edit-Dialog speichern → Trip erneut laden → `report_config` und `alert_rules` byte-identisch (außer geänderten Feldern). Validator-Smoke deckt das ab.

## LoC-Estimate

- **EditReportConfigSection.svelte:** ~190 → ~280 LoC (+ ~90 LoC für 3-Sektionen-Struktur, Channel-Conditional, Migration)
- **Bestehende `change_threshold_*`-Felder:** ~30 LoC ersatzlos raus
- **AlertRulesEditor-Integration:** ~15 LoC neu
- **Quick-Pick-Buttons + Styling:** ~20 LoC
- **Tests:** ~150 LoC (8 ACs)
- **Erwartetes LoC-Delta:** +250-300 (innerhalb Standard-Limit)

## Risks

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Bestehende Trips mit `change_threshold_*` verlieren Daten beim ersten Edit | mittel | AC-7 erzwingt Migration in `onMount`; Read-Modify-Write in AC-8 schützt unbekannte Felder |
| Backend akzeptiert `Trip.alert_rules` aus Edit nicht (nur aus Wizard) | niedrig | Wizard nutzt selbe API-Route — wenn das ginge, geht das auch hier; vor Push manuell verifizieren mit Validator |
| Native `<input type="time">` rendert auf Safari Desktop hässlich | niedrig | Bekanntes Verhalten, Quick-Picks kompensieren. Falls UX schlecht: spätere Iteration |
| AlertRulesEditor's `disabled`-Prop existiert nicht oder verhält sich anders als erwartet | niedrig | Vor Implementation Editor-API prüfen (`AlertRulesEditor.svelte` Props), notfalls Editor-Wrapper |
| Channel-Verfügbarkeit aus Profile-Store nicht reaktiv | niedrig | Svelte's `$state`/`$derived` macht das automatisch — bei Bedarf `$effect` |

## Changelog

- 2026-05-15: Initial spec created (Issue #88)
