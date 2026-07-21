---
entity_id: official_alerts_config_toggle
type: module
created: 2026-07-06
updated: 2026-07-07
status: superseded
version: "1.0"
tags: [compare, alerts, official-alerts, config]
---

# Official Alerts — Konfiguration: „Amtliche Warnungen anzeigen" pro Orts-Vergleich

> **SUPERSEDED (2026-07-07):** Dies ist der Vor-Analyse-Entwurf für #1040, geschrieben vor der
> Analyse-Phase. Er nennt u.a. `include_official_alerts` als Parametername und
> `Step4Layout.svelte` als Ort der Checkbox — implementiert wurde stattdessen
> `official_alerts_enabled` (Engine-Parameter) und die Checkbox in `Step5Versand.svelte`
> (Vorbild `ChannelToggle`, nicht `Step4Layout.svelte`). Die verbindliche, implementierte Spec ist
> **`docs/specs/modules/issue_1040_alerts_toggle.md`**. Diese Datei bleibt nur als
> Analyse-Historie erhalten, nicht als aktuelle Referenz.

## Approval

- [ ] Approved

## Purpose

PO-Anforderung (2026-07-06): Amtliche Warnungen (#1034–#1037) müssen pro Orts-Vergleich
ein-/ausschaltbar sein. Default an (Warnungen erscheinen automatisch); bei "aus" wird nicht nur
die Anzeige unterdrückt, sondern gar nicht erst gefetcht. Full-Stack-Slice: Go-Preset-Modell,
Python-Engine, Svelte-Editor.

## Source

- **File:** `internal/model/compare_preset.go`, `internal/handler/compare_preset.go`,
  `src/services/comparison_engine.py`, `src/services/scheduler_dispatch_service.py`,
  `frontend/src/lib/components/compare/compareWizardState.svelte.ts`,
  `frontend/src/lib/components/compare/compareEditorSave.ts`,
  `frontend/src/lib/components/compare/steps/Step4Layout.svelte`
- **Identifier:** `ComparePreset.OfficialAlertsEnabled`, `ComparisonEngine.run(include_official_alerts=...)`

> **Schicht-Hinweis:** Dieses Slice berührt alle drei Schichten (Go-API, Python-Core, Svelte-UI)
> — siehe `docs/specs/_template.md` Hinweis zur richtigen Verortung. Betroffene Dateien sind
> oben explizit nach Schicht aufgeführt.

## Estimated Scope

- **LoC:** ~150-200
- **Files:** 5-6 (2 Go, 2 Python, 2-3 Svelte — siehe Issue #1040 für Details; ggf. Aufteilung in
  Backend-Teilslice + Frontend-Teilslice, falls die Svelte-Seite allein bereits knapp wird)
- **Effort:** medium (Full-Stack, aber pro Schicht jeweils kleine, gut etablierte Muster)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py` (`get_official_alerts_for_location`, #1034) | Fundament | wird bei `include_official_alerts=False` nicht aufgerufen |
| `internal/handler/compare_preset.go` (`UpdateComparePresetHandler`, bestehendes `ForecastHours`/`PreviousSchedule`-Merge-Muster) | Muster-Referenz | Read-Modify-Write für das neue Feld |
| `internal/model/subscription.go` (`Weekday *int`-Pointer-Muster) | Muster-Referenz | Pointer statt `bool` mit `omitempty`, um "nicht gesetzt" von "explizit false" zu unterscheiden |
| `src/services/scheduler_dispatch_service.py::send_one_compare_preset` | Integration | einziger produktiver Python-Einstiegspunkt (täglicher Scheduler + manueller Send) |
| `frontend/src/lib/components/atoms/Switch.svelte` bzw. `ui/checkbox/Checkbox.svelte` | Wiederverwendung | bestehendes Form-Atom, keine neue UI-Architektur |

## Implementation Details

```go
// internal/model/compare_preset.go
type ComparePreset struct {
    // ... bestehende Felder ...
    // Issue #1040 — additiv, omitempty. nil = "im JSON nicht gesetzt" (Default true beim Lesen
    // interpretieren, NICHT beim Schreiben erzwingen — sonst verlieren Altdaten ihre "kein Feld
    // gesetzt"-Semantik beim naechsten Save).
    OfficialAlertsEnabled *bool `json:"official_alerts_enabled,omitempty"`
}
```

```go
// internal/handler/compare_preset.go, UpdateComparePresetHandler — Read-Modify-Write
// analog dem bestehenden ForecastHours/PreviousSchedule-Muster:
if updated.OfficialAlertsEnabled == nil {
    updated.OfficialAlertsEnabled = original.OfficialAlertsEnabled
}
```

```python
# src/services/comparison_engine.py
class ComparisonEngine:
    @staticmethod
    def run(
        locations, time_window, target_date, forecast_hours=48, profile=None,
        include_official_alerts: bool = True,
    ) -> ComparisonResult:
        for loc in locations:
            ...
            if include_official_alerts:
                loc_result.official_alerts = get_official_alerts_for_location(loc.lat, loc.lon)
            # sonst: gar kein Aufruf, official_alerts bleibt leere Default-Liste
```

```python
# src/services/scheduler_dispatch_service.py::send_one_compare_preset
include_official_alerts = preset.get("official_alerts_enabled", True)
result = ComparisonEngine.run(..., include_official_alerts=include_official_alerts)
```

Svelte: `officialAlertsEnabled = $state(true)` in `compareWizardState.svelte.ts`, Laden aus
`preset.official_alerts_enabled ?? true`, Aufnahme in `buildComparePresetSavePayload()`
(`compareEditorSave.ts`, analog dem bestehenden `forecast_hours`-Muster), Checkbox in
`Step4Layout.svelte` (Anzeige-/Layout-Step — inhaltlich am nächsten zur bestehenden
Metrik-/Anzeige-Auswahl).

## Expected Behavior

- **Input:** Checkbox-Zustand im Editor, persistiert am Compare-Preset.
- **Output:** Bei `false` enthält die Compare-Mail keinen amtlichen-Warnungen-Block, und es
  erfolgt kein HTTP-Call an irgendeine Official-Alert-Quelle für diesen Versand. Bei `true`
  (oder fehlendem Feld) verhält sich die Mail wie in #1034–#1037 spezifiziert.
- **Side effects:** keine über die Fetch-Unterdrückung hinaus.

## Acceptance Criteria

- **AC-1:** Given ein Compare-Preset mit `official_alerts_enabled: false`, When der
  Orts-Vergleich gesendet wird, Then enthält die Mail keinen amtlichen-Warnungen-Block UND es
  wird für keine der verglichenen Locations eine Official-Alert-Quelle aufgerufen.
  - Test: echten Compare-Versand mit einer registrierten Fake-Quelle (Call-Counter) durchführen;
    bei `false` muss der Zähler bei 0 bleiben und das HTML keinen Warnungs-Badge enthalten.

- **AC-2:** Given ein Compare-Preset mit `official_alerts_enabled: true` (oder Default), When der
  Orts-Vergleich gesendet wird, Then verhält sich die Mail identisch zum Verhalten aus
  #1034–#1037.
  - Test: identischer Compare-Versand wie AC-1, aber mit `true` — Fake-Quelle wird aufgerufen,
    Badge erscheint im HTML.

- **AC-3:** Given ein Bestands-Preset ohne `official_alerts_enabled`-Feld, When es geladen und
  ohne Änderung an diesem Feld erneut gespeichert wird, Then verhält es sich beim Versand wie
  "an" (Default true) UND alle anderen Preset-Felder (`empfaenger`, `display_config`, `schedule`
  etc.) bleiben unverändert erhalten.
  - Test: mit zwei verschiedenen Nutzern je ein Alt-Preset ohne das Feld laden, editieren (z. B.
    Name ändern) und speichern, dann per GET verifizieren, dass `official_alerts_enabled` fehlt
    oder `true` ist und alle übrigen Felder identisch zum Vorherzustand sind (Mandanten-Pflicht:
    zwei Nutzer, kein Cross-User-Leck).

## Known Limitations

- Ein einziges An/Aus-Feld für alle amtlichen Warnungsquellen zusammen — keine granulare Auswahl
  einzelner Quellen (z. B. nur Vigilance an, Massiv-Sperrungen aus). Entspricht der PO-Anforderung
  ("triviale zusätzliche Checkbox").
- Der Legacy-Pfad `CompareSubscription`/`compare_subscriptions.json` (Issue #456) wird nicht
  angepasst — außerhalb des produktiven Scheduler-/Editor-Flusses.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (Slice-lokale Konfigurationserweiterung, kein neues Grundsatzkonzept —
  nutzt bereits etablierte Merge- und Pointer-Muster des Projekts)
- **Rationale:** Das Fail-soft-Grundprinzip aus ADR-0016 bleibt unberührt; dieses Slice fügt nur
  eine Nutzer-gesteuerte Ein/Aus-Schicht oberhalb der bestehenden Registry hinzu.

## Changelog

- 2026-07-06: Initial spec created (Epic #1033, Issue #1040, PO-Anforderung)
