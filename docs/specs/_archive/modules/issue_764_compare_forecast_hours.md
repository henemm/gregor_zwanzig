---
entity_id: issue_764_compare_forecast_hours
type: module
created: 2026-06-12
updated: 2026-06-12
status: draft
version: "1.0"
tags: [compare, preset, persistence, bug]
---

# ComparePreset — forecast_hours (Vorhersage-Horizont) persistieren & konsumieren

## Approval

- [ ] Approved

## Purpose

Der im Orts-Vergleich-Editor gewählte Vorhersage-Horizont (`forecast_hours`, 24/48/72 h)
wird derzeit nicht gespeichert: Er ist kein Feld des `ComparePreset`-Modells, wird beim
Anlegen/Bearbeiten nicht mitgesendet und beim erneuten Öffnen nicht zurückgeladen. Diese
Spec macht den Wert persistent, round-trip-fest und funktional wirksam beim täglichen Versand.

## Source

- **File:** `internal/model/compare_preset.go`
- **Identifier:** `ComparePreset` (Go-Struct)

## Estimated Scope

- **LoC:** ~40
- **Files:** 6 (Go-Modell, Go-Store-Load-Default, TS-Type, compareWizardState, compareEditorSave, edit/+page.svelte, Python-Konsum)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/compare_preset.go` | Go-Handler | Create/Update — decodiert neues Feld automatisch (Full-Replace mit Preserve) |
| `internal/store/store.go` | Go-Store | `LoadComparePresets` Legacy-Default; `SaveComparePresets` plain JSON Marshal |
| `frontend/.../compareEditorSave.ts` | TS Pure-Function | Round-Trip-Spread, muss Edit-Wert explizit überschreiben |
| `api/routers/scheduler.py` | Python-Versand | `_send_one_compare_preset` konsumiert Horizont |

## Implementation Details

```
1. Go-Modell (internal/model/compare_preset.go):
   ForecastHours int `json:"forecast_hours"`  // 24|48|72 — Vorhersage-Horizont

2. Go-Store-Load-Default (internal/store/store.go, LoadComparePresets):
   // Legacy-Presets ohne Feld: Go-Zero-Value 0 → auf 48 defaulten (kein gültiger Horizont 0)
   if presets[i].ForecastHours == 0 { presets[i].ForecastHours = 48 }

3. Go-Update-Handler (internal/handler/compare_preset.go, UpdateComparePresetHandler):
   // Preserve: wenn Body forecast_hours nicht trägt (==0), Original-Wert erhalten
   if updated.ForecastHours == 0 { updated.ForecastHours = original.ForecastHours }

4. TS-Type (frontend/src/lib/types.ts, interface ComparePreset):
   forecast_hours: number;

5. saveNewPreset() (compareWizardState.svelte.ts) — POST-Payload:
   forecast_hours: this.forecastHours,

6. buildComparePresetSavePayload() (compareEditorSave.ts):
   // edits um forecastHours erweitern, im body explizit setzen (überschreibt ...original-Spread)
   forecast_hours: edits.forecastHours,
   und saveComparePreset() reicht this.forecastHours in edits durch.

7. Edit-Hydration (compare/[id]/edit/+page.svelte):
   state.forecastHours = data.preset.forecast_hours ?? 48;

8. Python-Konsum (api/routers/scheduler.py, _send_one_compare_preset):
   forecast_hours=preset.get("forecast_hours", 48)   // statt hartkodiert 48
```

## Expected Behavior

- **Input:** Nutzer wählt im Compare-Editor Horizont 72 h (Versand-Step), speichert.
- **Output:** `compare_presets.json` enthält `"forecast_hours": 72`; beim erneuten Bearbeiten
  ist 72 h vorausgewählt; der tägliche Versand rechnet mit 72 h.
- **Side effects:** Legacy-Presets ohne Feld laden als 48 h (kein Bruch, kein Datenverlust
  anderer Felder — Read-Modify-Write bleibt intakt).

## Acceptance Criteria

- **AC-1:** Given ein neuer Orts-Vergleich im Editor mit Horizont „Übermorgen (72 h)" im
  Versand-Step / When der Nutzer „Briefing aktivieren"/Speichern klickt / Then wird das Preset
  mit `forecast_hours = 72` persistiert (nicht 48).
  - Test: Playwright-E2E gegen Staging — Vergleich mit 72 h anlegen, danach GET des Presets
    (oder Reload der Detail-/Edit-Seite) zeigt 72 h. Beweist Persistenz beim ersten Speichern.

- **AC-2:** Given ein gespeichertes Preset mit `forecast_hours = 72` / When der Nutzer den
  Bearbeiten-Modus öffnet / Then ist im Horizont-Select „Übermorgen (72 h)" vorausgewählt
  (nicht der Default „Morgen 48 h").
  - Test: Playwright-E2E gegen Staging — Edit-Route öffnen, Select-Wert == 72 auslesen.

- **AC-3:** Given das in AC-2 geöffnete Preset / When der Nutzer ohne Änderung am Horizont
  speichert / Then bleibt `forecast_hours = 72` erhalten (kein Reset auf 48, keine anderen
  Felder — Empfänger, Region, Metriken — verloren).
  - Test: Playwright-E2E gegen Staging — nach Speichern Reload, Horizont == 72 und ein
    weiteres Feld (z.B. Name/Region) unverändert. Round-Trip-Beweis.

- **AC-4:** Given ein Legacy-Preset in `compare_presets.json` ohne `forecast_hours`-Feld /
  When es geladen wird (Edit-Modus oder Versand) / Then wird es als 48 h behandelt (kein
  ungültiges „0 h", kein Crash).
  - Test: echter Go-Store-Test — Preset-JSON ohne Feld schreiben, `LoadComparePresets`,
    `ForecastHours == 48` assert. Reales Datei-/Store-Verhalten.

- **AC-5:** Given zwei fällige Daily-Presets, identisch bis auf `forecast_hours` (48 vs. 72) /
  When der tägliche Compare-Versand läuft / Then verwendet der Versandpfad den jeweils
  gespeicherten Horizont (nicht hartkodiert 48) — nachweisbar an der unterschiedlichen
  Berechnungs-Tiefe.
  - Test: echter Python-Test gegen die reale `ComparisonEngine` (keine Mocks) — beide Presets
    durch `_send_one_compare_preset` (SMTP-Versand-Grenze abgefangen wie in bestehenden
    Briefing-Tests), das 72 h-Preset liefert eine Vergleichsberechnung mit echtem
    Horizont 72 h, das 48 h-Preset mit 48 h. Beweist funktionale Wirksamkeit (kein totes Setting).
