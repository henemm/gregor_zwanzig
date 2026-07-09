---
entity_id: issue_1170_compare_alert_config
type: feature
created: 2026-07-09
updated: 2026-07-09
status: draft
workflow: feat-1170-compare-alert-config
tags: [compare, alerts, epic-1095]
---

<!-- Issue #1170 — Epic #1095 (Scheibe 3/3): Alarm-Konfiguration im Compare-Editor -->

# Issue 1170 — Alarm-Konfiguration im Compare-Editor

## Approval

- [x] Approved

## Purpose

Der Orts-Vergleich (Compare-Preset) wertet seit #1168/#1169 Wetter-Abweichungen aus
und verschickt Alarm-Mails — aber mit hartkodierter Config (standard-Empfindlichkeit,
120 Minuten Cooldown, nur E-Mail). Diese Scheibe macht die Alarm-Einstellungen pro
Compare-Preset editierbar, analog zum bestehenden Trip-Alerts-Tab: Empfindlichkeit
pro Wetter-Metrik, Cooldown und Ruhezeiten lassen sich im Compare-Editor konfigurieren
und werden von der Auswertung tatsächlich verwendet.

## Source

- **File:** `internal/model/compare_preset.go` — `ComparePreset`-Struct (neue Alarm-Felder)
- **File:** `internal/handler/compare_preset.go` — `UpdateComparePresetHandler` (RMW-Merge)
- **File:** `src/services/compare_alert.py` — `CompareAlertService._build_eval_config` (liest die Config)
- **File:** `frontend/src/lib/components/compare/CompareEditor.svelte` — neuer Tab „Alarme"

> **Schicht-Hinweis:** Go-API (`internal/model`, `internal/handler`) = Production-API Port 8090;
> Python-Core (`src/services/compare_alert.py`) = FastAPI Core; Frontend (`frontend/src/...`) =
> SvelteKit-UI. Diese Scheibe berührt alle drei Schichten additiv, kein Rendering-Change.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `#1168` DeviationAlertEngine | Upstream (live) | Location-generischer Auswertungskern, liest `AlertEvaluationConfig` |
| `#1169` CompareAlertService | Upstream (live) | Liest Alarm-Config bereits vorwärtskompatibel via `preset.get(feld, DEFAULT)` |
| `internal/model/trip.go:97-100` | Vorbild | Trip-Alarm-Felder (`AlertCooldownMinutes`, `AlertQuietFrom/To` als Pointer) — Struktur/Naming wird 1:1 übernommen |
| `frontend/src/lib/components/alerts-tab/*` | Wiederverwendung | `AlertMetricLevelTable`, `AlertCooldownCard`, `AlertQuietHoursCard`, `alertMetricTable.ts` — unverändert wiederverwendet |
| `internal/handler/compare_preset.go:217-223` | Vorbild | Nil-Merge-Muster für `OfficialAlertsEnabled *bool` — Blaupause für die 3 neuen Pointer-Felder |
| `#1182` PO-Entscheidung Cooldown-Granularität | Design-Entscheidung | Cooldown wirkt preset-weit, nicht pro Ort |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/model/compare_preset.go` | MODIFY | +3 Pointer-Felder: `AlertCooldownMinutes *int`, `AlertQuietFrom *string`, `AlertQuietTo *string` (Trip-identische JSON-Tags). `metric_alert_levels` nutzt das bestehende `DisplayConfig map[string]interface{}`, kein neues Struct-Feld |
| `internal/handler/compare_preset.go` | MODIFY | +3 nil-Merge-Blöcke im `UpdateComparePresetHandler` (RMW, analog `official_alerts_enabled`) |
| `src/services/compare_alert.py` | MODIFY | 4 Read-Zeilen in `_build_eval_config` auf Trip-Keys angleichen: `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to` (Top-Level) + `metric_alert_levels` aus `display_config` |
| `frontend/src/lib/components/compare/CompareEditor.svelte` | MODIFY | Neuer Tab „Alarme" in `TAB_DEFS`; `initial`/`dirty`/Post-Save-Reset um Alarm-Felder erweitert; `handleSave()`-Payload reicht Alarm-Felder durch |
| `frontend/src/lib/components/compare/CompareAlarmSection.svelte` | CREATE | Neue Sektion, verdrahtet `AlertMetricLevelTable`/`AlertCooldownCard`/`AlertQuietHoursCard` gegen `wiz.*`-State (kein Kanal-Selektor) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `CompareEditorEdits`-Interface +Alarm-Felder; `metric_alert_levels` → `display_config`, Cooldown/Ruhezeiten → Top-Level-Body |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | +4 `$state`-Felder; Pfad B (`saveComparePreset`) und Pfad C (`saveNewPreset`) führen sie im Payload |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` | MODIFY | Edit-Init: `data.preset.*` → `state.*` mit `?? default`-Fallback je neuem Feld |
| `frontend/src/lib/types.ts` | MODIFY | FE-Typ `ComparePreset` um Top-Level-Alarm-Felder erweitert (`display_config` bleibt `Record<string,unknown>`) |

Wiederverwendet ohne Änderung: `AlertMetricLevelTable.svelte`, `AlertCooldownCard.svelte`,
`AlertQuietHoursCard.svelte`, `alertMetricTable.ts` (`activeAlertableMetrics()`).

### Estimated Changes

- Files: 9 (1 CREATE, 8 MODIFY)
- LoC: +180/-20 (geschätzt, frontend-lastig)

## Implementation Details

**Backend (Go):** Drei neue Pointer-Felder auf `ComparePreset` — `AlertCooldownMinutes *int`,
`AlertQuietFrom *string`, `AlertQuietTo *string`, mit den gleichen JSON-Tags wie bei `Trip`
(`alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to`). Kein neues `AlertRules`-Feld
und kein Pointer-DTO nötig — die Auswertung liest keine gespeicherten Regeln, sondern baut sie
zur Laufzeit aus `metric_alert_levels` (lebt im bestehenden `DisplayConfig`-Map). Der Handler
merged die 3 neuen Felder nil-sicher (RMW): ist ein Feld im PUT-Body `null`/absent, bleibt der
gespeicherte Wert erhalten (Blaupause: `official_alerts_enabled`-Merge). `DisplayConfig` wird wie
bisher als Ganzes ersetzt, wenn im Request vorhanden — `metric_alert_levels` reist dort als
Sub-Key mit.

**Python-Core:** `compare_alert.py` liest aktuell (#1169) bereits vorwärtskompatibel via
`preset.get(feld, DEFAULT)`, aber mit provisorischen Compare-eigenen Key-Namen
(`cooldown_minutes`, `quiet_from`, `quiet_to`, Top-Level `metric_alert_levels`). Diese vier
Read-Zeilen werden auf die Trip-identischen Keys angeglichen (`alert_cooldown_minutes`,
`alert_quiet_from`, `alert_quiet_to` Top-Level; `metric_alert_levels` aus `display_config`
gelesen). Kein Verhaltensbruch, keine bestehenden Persistenzdaten betroffen (die alten Keys
wurden bisher von nichts geschrieben).

**Frontend:** Neuer Tab „Alarme" im `CompareEditor` neben `vergleich|orte|idealwerte|layout|versand`.
Eine neue Sektion `CompareAlarmSection.svelte` bindet die drei bestehenden Trip-Alarm-Controls
(`AlertMetricLevelTable`, `AlertCooldownCard`, `AlertQuietHoursCard`) unverändert ein — nur die
State-Anbindung ist neu (`wiz.*`-State statt Trip-Objekt). Kein Kanal-Selektor: Compare-Alarme
bleiben E-Mail-only (Festlegung aus Scheibe 2, #1169). Alle drei Save-Pfade müssen die neuen
Felder führen: Pfad A (`CompareEditor.handleSave()`), Pfad B (`wiz.saveComparePreset()`,
PUT-Edit), Pfad C (`wiz.saveNewPreset()`, POST-Create). Edit-Hydration
(`compare/[id]/edit/+page.svelte`) initialisiert die vier neuen `wiz`-State-Felder aus
`data.preset.*` mit Default-Fallback (`?? "standard"` / `?? 120` / `?? null`).

**Cooldown-Semantik (PO-Entscheidung #1182):** Der Cooldown wirkt preset-weit — eine Alarm-Mail
pro Zeitfenster, gebündelt über alle Orte des Presets. Das entspricht dem bestehenden
Cooldown-Store-Keying auf `preset_id` (#1169), daran ändert sich nichts. Die UI zeigt entsprechend
genau ein Cooldown-Feld (nicht pro Ort), analog zum Trip.

## Test Plan

**Grundsatz (CLAUDE.md „Keine Mocked Tests"):** Backend-Tests laufen als echte HTTP-Calls gegen
den laufenden Go-Server mit echter Persistenz (`data/users/<user>/compare_presets.json`).
Frontend-Tests laufen als Playwright-E2E gegen Staging, eingeloggt, mit echtem Klick-Pfad (Tab
anklicken, Werte setzen, speichern, Seite neu laden, Werte prüfen). Keine reinen
Dateiinhalt-Assertions (`assert 'xyz' in file.read_text()`).

### Automated Tests (TDD RED)

- [ ] Test 1 (AC-1, Playwright): GIVEN ein eingeloggter Nutzer öffnet den Compare-Editor eines
  bestehenden Presets mit mindestens 2 aktiven Metriken WHEN er auf den Tab „Alarme" klickt THEN
  sieht er für jede aktive Metrik ein Empfindlichkeits-Dropdown, ein Cooldown-Feld und
  Ruhezeiten-Felder (analog zum Trip-Alerts-Tab).
- [ ] Test 2 (AC-2, Playwright): GIVEN ein Nutzer öffnet ein bestehendes Preset im Editier-Modus,
  setzt Empfindlichkeit einer Metrik auf „sensibel", Cooldown auf 30 Minuten und Ruhezeit
  22:00-06:00 und klickt „Speichern" WHEN er die Seite danach neu lädt THEN zeigt der Alarme-Tab
  exakt diese drei Werte unverändert an (Round-Trip über den PUT-Pfad des CompareEditor).
- [ ] Test 3 (AC-2, HTTP): GIVEN ein Preset existiert WHEN `wiz.saveComparePreset()` (der zweite
  Edit-Pfad über den Wizard-State) mit geänderten Alarm-Werten per echtem PUT ausgeführt wird THEN
  liefert ein anschließendes GET des Presets dieselben Alarm-Werte zurück.
- [ ] Test 4 (AC-3, HTTP): GIVEN kein Preset existiert WHEN ein neues Preset per POST mit
  gesetzten Alarm-Feldern angelegt wird (Create-Pfad `saveNewPreset`) THEN enthält das
  zurückgelieferte bzw. per GET geladene Preset diese Alarm-Felder.
- [ ] Test 5 (AC-4, HTTP): GIVEN ein bestehendes Preset ohne die neuen Alarm-Felder (Altdaten vor
  dieser Scheibe) WHEN es per GET geladen wird THEN schlägt das Laden nicht fehl und die
  Auswertung/UI zeigt die Defaults (standard-Empfindlichkeit, 120 Minuten, keine Ruhezeit); WHEN
  anschließend ein PUT nur ein anderes Feld ändert (z.B. `top_n`) THEN bleiben alle client-fremden
  Bestandsfelder (z.B. `official_alerts_enabled`) erhalten (RMW-Beweis, kein Datenverlust).
- [ ] Test 6 (AC-5, HTTP/Integration): GIVEN ein Preset mit gespeichertem Cooldown von 5 Minuten
  und Empfindlichkeit „sensibel" für eine Metrik WHEN die Compare-Alarm-Auswertung für dieses
  Preset läuft (echter Aufruf von `CompareAlertService`) THEN wird tatsächlich mit 5 Minuten
  Cooldown und der „sensibel"-Schwelle ausgewertet, nicht mit den alten Defaults (standard/120).
- [ ] Test 7 (AC-6, HTTP, 2-Nutzer-Test): GIVEN zwei verschiedene Nutzer A und B mit je einem
  eigenen Compare-Preset WHEN Nutzer A seine Alarm-Einstellungen per PUT ändert THEN bleibt das
  Preset von Nutzer B über einen erneuten GET-Aufruf unverändert (echte `user_id`-Isolation, kein
  Cross-User-Leck).
- [ ] Test 8 (AC-7, Integration/HTTP): GIVEN ein Preset mit mehreren Orten und einer aktiven
  Alarm-Regel, die für mehrere Orte gleichzeitig auslöst, sowie einem gesetzten Cooldown WHEN die
  Auswertung mehrfach innerhalb des Cooldown-Fensters läuft THEN wird für das gesamte Preset nur
  eine Alarm-Mail verschickt (nicht eine pro Ort) — bestätigt das preset-weite Cooldown-Verhalten.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet den Compare-Editor eines Presets mit aktiven Metriken /
  When er den neuen Tab „Alarme" öffnet / Then kann er pro aktiv gewählter Wetter-Metrik eine
  Empfindlichkeitsstufe (off/entspannt/standard/sensibel), einen Cooldown in Minuten und
  Ruhezeiten (von/bis) einstellen — Bedienung analog zum bestehenden Trip-Alerts-Tab.

- **AC-2:** Given ein Nutzer ändert Alarm-Einstellungen im Editier-Modus eines bestehenden Presets
  und speichert / When er das Preset danach erneut lädt / Then sind die gespeicherten Werte
  unverändert vorhanden (Round-Trip, kein Datenverlust) — gilt für beide Editier-Speicherpfade
  (`CompareEditor.handleSave` und `wiz.saveComparePreset`).

- **AC-3:** Given ein Nutzer legt ein neues Compare-Preset an und setzt dabei Alarm-Einstellungen /
  When das Preset gespeichert und danach geladen wird / Then sind die Alarm-Einstellungen ebenso
  vorhanden wie beim Bearbeiten eines bestehenden Presets.

- **AC-4:** Given ein bestehendes Preset ohne die neuen Alarm-Felder (angelegt vor dieser Scheibe) /
  When es geladen wird / Then lädt es fehlerfrei und zeigt sinnvolle Defaults (standard-
  Empfindlichkeit, 120 Minuten Cooldown, keine Ruhezeit); wird danach ein anderes Feld des Presets
  aktualisiert, bleiben alle zuvor gespeicherten, dem Update-Request unbekannten Felder erhalten.

- **AC-5:** Given ein Preset mit explizit gespeicherten, von den Defaults abweichenden
  Alarm-Einstellungen (z.B. Cooldown 30 Minuten statt 120, Empfindlichkeit „sensibel" statt
  „standard") / When die Alarm-Auswertung für dieses Preset läuft / Then wird tatsächlich mit den
  gespeicherten Werten ausgewertet, nicht mit den bisherigen hartkodierten Defaults.

- **AC-6:** Given zwei verschiedene Nutzer mit jeweils eigenen Compare-Presets / When Nutzer A
  seine Alarm-Einstellungen ändert und speichert / Then bleibt das Preset von Nutzer B davon
  vollständig unberührt (Isolation zwischen Nutzern nachgewiesen durch einen Test mit zwei echten
  Nutzerkonten).

- **AC-7:** Given ein Preset mit mehreren Orten, für die im selben Auswertungslauf gleichzeitig ein
  Alarm ausgelöst würde, und einem gesetzten Cooldown / When innerhalb des Cooldown-Fensters
  mehrfach ausgewertet wird / Then wird für das gesamte Preset nur eine gebündelte Alarm-Mail
  verschickt, unabhängig von der Anzahl betroffener Orte (preset-weiter Cooldown, keine
  Pro-Ort-Zählung).

## Known Limitations

- Kein Kanal-Selektor: Compare-Alarme bleiben ausschließlich E-Mail (Festlegung aus Scheibe 2,
  #1169). Telegram/SMS für Compare-Alarme sind nicht Teil dieser Scheibe.
- Kein Editor für rohe `AlertRules`: Anders als der Trip persistiert Compare kein
  `alert_rules`-Array. Regeln werden weiterhin zur Laufzeit aus `metric_alert_levels` abgeleitet
  (`expand_per_metric_levels()`), das UI editiert nur die Empfindlichkeitsstufe pro Metrik.
- Metrik-Abdeckung der Alarm-Sektion: Nur Compare-Metriken mit einem alertfähigen `AlertMetric`-
  Gegenstück bekommen eine Alarm-Zeile (Mapping `COMPARE_TO_ALERT_METRIC` in
  `CompareAlarmSection.svelte`, 6 Zuordnungen: Wind, Niederschlag, Temp-Max, Gewitter, Neuschnee,
  Sicht). Nicht-alertfähige Compare-Metriken (z.B. Sonnenstunden, Bewölkung, UV) erscheinen
  bewusst nicht — analog zum Trip-Precedent `CATALOG_TO_ALERT_METRICS`.
- Mail-Rendering: Diese Scheibe fügt die **Mehr-Orte-Bündelung** hinzu (F001, PO-Entscheidung):
  gleichzeitig betroffene Orte eines Presets werden in EINER Alarm-Mail zusammengefasst
  (`to_multi_point_alert_message`, additives `AlertEvent.location_label`). Trip-Pfad
  (`to_alert_message`) und Einzel-Ort-Fall bleiben byte-identisch (Golden-Master-Regression).
  Renderer-Änderung an `src/output/renderers/alert/*` triggert das Commit-Gate #811.

## Non-Goals

- Keine Änderung am Cooldown-Keying (bleibt `preset_id`-basiert, PO-Entscheidung #1182).
- Keine rückwirkende Migration bestehender Presets auf neue Werte — Altdaten laufen über die
  dokumentierten Defaults weiter.
- Keine Änderung an der Auswertungslogik selbst (`DeviationAlertEngine`, `expand_per_metric_levels`)
  — nur an den Werten, die in die bestehende Konfiguration einfließen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Persistenz-Erweiterung nach etabliertem Muster (Pointer-Felder +
  RMW-Nil-Merge, identisch zu `official_alerts_enabled`); keine neue Architektur-Entscheidung,
  sondern konsequente Wiederverwendung bestehender Trip-Alert-Patterns für einen zweiten Consumer
  (Epic #1095, bereits in #1168/#1169 architektonisch entschieden).

## Changelog

- 2026-07-09: Initial spec created — Issue #1170, Epic #1095 Scheibe 3/3
