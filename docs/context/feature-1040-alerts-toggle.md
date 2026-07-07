# Context: feature-1040-alerts-toggle

## Request Summary

Issue #1040 (Epic #1033, Slice 5): Neues bool-Feld am Compare-Preset **„Amtliche Warnungen
anzeigen"** (Default `true`). Bei `false` werden die #1034-Official-Alert-Quellen für diesen
Vergleich **gar nicht erst abgefragt** (kein Fetch), nicht nur ausgeblendet. Full-Stack-Slice:
Go-Model + Go-Handler + Python-Scheduler/-Engine + Svelte-Editor.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/model/compare_preset.go:13-34` | `ComparePreset`-Struct — neues Feld hier einfügen |
| `internal/handler/compare_preset.go:166-237` | `UpdateComparePresetHandler` — Read-Modify-Write-Merge |
| `src/services/scheduler_dispatch_service.py:198-259` | `send_one_compare_preset()` — ruft `ComparisonEngine.run()` auf, genutzt von Daily-Scheduler (Zeile ~65-71) UND manuellem Send (#627) |
| `src/services/comparison_engine.py:38-45,180-187` | `ComparisonEngine.run()` Signatur + Aufruf von `get_official_alerts_for_location()` |
| `src/services/official_alerts/base.py` | Registry aus #1034 (`get_official_alerts_for_location`, `register_official_alert_source`) |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts:36,201` | State-Deklaration + Save-Payload-Aufnahme (Vorbild: `forecastHours`) |
| `frontend/src/lib/components/compare/compareEditorSave.ts:13-24,32-72` | `CompareEditorEdits`-Interface + `buildComparePresetSavePayload()` (Round-Trip-Spread-Prinzip) |
| `frontend/src/lib/components/compare/steps/Step4Layout.svelte` | Kandidat für die Checkbox (Anzeige-Optionen) — Alternative: `Step5Versand.svelte` |
| `docs/specs/modules/issue_1034_official_alerts_foundation.md` | Fundament-Spec, nennt Config-Checkbox explizit als Out-of-Scope-Punkt für #1040 |

## Existing Patterns

- **Go optionale Felder — ZWEI verschiedene Muster, nicht verwechseln:**
  1. **Pointer-Pattern** (`Weekday *int`, `DisplayConfig map[...]`, `ArchivedAt *time.Time`):
     `nil` = "im JSON nicht gesetzt", Handler prüft `if updated.X == nil { updated.X = original.X }`.
     Eindeutig, keine Mehrdeutigkeit zwischen "fehlt" und "bewusst auf Zero-Value gesetzt".
  2. **Zero-Value-Heuristik** (`ForecastHours int`, `PreviousSchedule string`):
     `if updated.ForecastHours == 0 { ... }` — funktioniert NUR weil `0`/`""` für diese Felder
     nie ein gültiger, bewusst gesetzter Wert ist.
  - **Für #1040 zwingend Pointer-Pattern (`*bool`)**, NICHT Zero-Value-Heuristik: Ein reines
    `bool official_alerts_enabled` würde bei fehlendem JSON-Feld (alte Clients/Presets) auf Go's
    Zero-Value `false` decodieren — nicht unterscheidbar von einer bewussten Abschaltung durch
    den Nutzer. Das würde AC-3 (Default „true" bei Altdaten) brechen und im schlimmsten Fall
    bestehende, funktionierende Presets bei jedem Save durch einen Client, der das Feld nicht
    kennt, unbemerkt auf „aus" umstellen. `*bool` + `omitempty` verhält sich exakt wie
    `Weekday`/`DisplayConfig`: fehlt im JSON → `nil` → Python/Handler interpretieren das als
    Default `true`, ohne dass beim Schreiben ein Wert erzwungen wird.
- **Python-Scheduler:** `preset.get("<feld>", <default>)` liest optionale Preset-Felder mit
  Fallback (Vorbild `forecast_hours`, Zeile 241). Funktioniert korrekt mit obigem Pointer-Pattern,
  weil ein `nil`-Pointer beim JSON-Marshal (mit `omitempty`) komplett aus dem Objekt verschwindet.
- **ComparisonEngine.run():** Neuer Parameter mit Default (analog `forecast_hours: int = 48`),
  Official-Alerts-Aufruf (Zeile 181-182) wird conditional: `get_official_alerts_for_location(...)
  if official_alerts_enabled else []` bzw. Schleife komplett überspringen (kein Fetch — Spec
  verlangt "nicht nur ausgeblendet").
- **Svelte:** `$state(true)`-Deklaration + optionales Feld in `CompareEditorEdits` (Vorbild
  `forecastHours?: number`, `activeMetricKeys?: string[]` — beide als "optional, rückwärtskompatibel"
  kommentiert) + Spread-Pattern in `buildComparePresetSavePayload()`.
- **Mandanten-Tests:** `tests/tdd/test_issue_1004_startzeit_ssot.py` (User-A/User-B mit eigenen
  Verzeichnissen), `tests/tdd/test_compare_preset_send.py` (Preset-Versand mit User-Isolation)
  — Vorlage für AC-3-Test (zwei Nutzer, Alt-Preset ohne Feld).

## Dependencies

- **Upstream:** #1034 (Official-Alerts-Registry, `get_official_alerts_for_location`) — bereits
  implementiert, wird hier nur conditional aufgerufen, keine Änderung an #1034 selbst.
- **Downstream:** Kein Consumer von `ComparePreset` außerhalb von Handler/Scheduler bekannt, der
  brechen könnte (grep zeigt nur Store/Handler/Scheduler als Nutzer der Struct).
- **Drei Aufrufer von `ComparisonEngine.run()` insgesamt** (verifiziert per grep):
  1. `src/services/scheduler_dispatch_service.py:237` (Preset-Versand, Daily+Manual) — bekommt
     `official_alerts_enabled` aus dem Preset durchgereicht.
  2. `api/routers/compare.py:53` (Ad-hoc-Compare-API, kein Preset-Objekt) — **unberührt**,
     bekommt keinen expliziten Wert, fällt auf Default `True` zurück (Verhalten unverändert).
  3. `src/services/compare_subscription.py:90` (Legacy-`CompareSubscription`-Pfad, #456,
     explizit Out-of-Scope laut Issue) — **unberührt**, gleicher Grund.
  Beide unberührten Call-Sites müssen in der Spec explizit als "Default greift, unverändert"
  vermerkt werden, damit der Adversary-Agent sie nicht als vergessene/kaputte Stellen markiert.

## Existing Specs

- `docs/specs/modules/issue_1034_official_alerts_foundation.md` — Registry-Fundament, nennt
  Config-Checkbox explizit als künftigen Slice (= dieses Issue).
- `docs/specs/modules/issue_458_compare_preset_backend.md` — ursprüngliche `ComparePreset`-Spec.
- `docs/specs/modules/issue_764_...` (Vorhersage-Horizont) — engster Präzedenzfall für ein
  optionales, rückwärtskompatibles Preset-Feld über den gesamten Stack.

## Open Question (für /20-analyse)

Checkbox-Platzierung: Issue schlägt `Step4Layout.svelte` primär vor (Anzeige-Optionen-Kontext),
alternativ `Step5Versand.svelte` (Kanal-Optionen-Nähe). Step3Idealwerte.svelte passt inhaltlich
nicht (reine Metrik-Wertebereiche). Muss in der Analyse-Phase entschieden werden — PO hat beide
Optionen offen gelassen ("triviale zusätzliche Checkbox").

## Risks & Considerations

- **Go-Typ-Falle:** Plain `bool` statt `*bool` wäre der naheliegende, aber falsche erste Impuls
  (siehe Existing Patterns oben) — würde AC-3 strukturell verletzen. Muss in der Spec explizit
  als `*bool` festgeschrieben werden.
- **Kein Fetch bei `false`:** Muss strukturell (Skip der Schleife/des Aufrufs), nicht nur
  UI-seitig ausgeblendet werden — AC-1 verlangt einen Call-Counter-Beweis von 0.
- **Mandanten-Pflicht (CLAUDE.md):** AC-3 verlangt bereits Zwei-Nutzer-Test — nicht optional.
- **Scheduler ist Produktions-kritischer Pfad** (täglicher Job) — Änderung an `ComparisonEngine.run()`-Signatur
  muss abwärtskompatibel bleiben (Default-Parameter, kein Breaking Change für andere Aufrufer).
- **Zwei zusätzliche `ComparisonEngine.run()`-Aufrufer** (`api/routers/compare.py`,
  `compare_subscription.py`) müssen in der Spec explizit als "unberührt/Default greift"
  dokumentiert werden (siehe Dependencies) — sonst potenzielles Adversary-Finding "vergessene
  Call-Site".

## Analysis

### Type
Feature (Full-Stack, additiv, kein Bugfix).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/model/compare_preset.go` | MODIFY | Neues Feld `OfficialAlertsEnabled *bool \`json:"official_alerts_enabled,omitempty"\`` |
| `internal/handler/compare_preset.go` | MODIFY | Read-Modify-Write-Merge (`if updated.OfficialAlertsEnabled == nil { ... }`), analog `DisplayConfig` |
| `src/services/comparison_engine.py` | MODIFY | Neuer Parameter `official_alerts_enabled: bool = True`, conditional Skip des Fetch-Aufrufs |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `preset.get("official_alerts_enabled", True)` an `ComparisonEngine.run()` durchreichen |
| `frontend/.../compareWizardState.svelte.ts` | MODIFY | `$state(true)`, Laden im Edit-Modus, Aufnahme in Save-Payload |
| `frontend/.../compareEditorSave.ts` | MODIFY | Feld in `CompareEditorEdits` + Spread in `buildComparePresetSavePayload()` |
| `frontend/.../steps/Step5Versand.svelte` | MODIFY | Neue Checkbox (Vorbild: `forecastHours`-Kachel), NICHT Step4Layout |
| `tests/tdd/test_issue_1040_alerts_toggle.py` | CREATE | AC-1 bis AC-3, Zwei-Nutzer-Test für AC-3 |

**Unberührt (explizit dokumentieren, nicht ändern):** `api/routers/compare.py:53`,
`src/services/compare_subscription.py:90` — beide rufen `ComparisonEngine.run()` ohne den neuen
Parameter auf, Default `True` greift, Verhalten unverändert.

### Scope Assessment
- Files: 7 geändert + 1 neu = 8
- Estimated LoC: ~150-200 (Großteil in Tests, analog #1034/#1035)
- Risk Level: LOW — additiver Parameter mit sicherem Default, etabliertes Pointer-Pattern,
  keine Breaking Changes an bestehenden Aufrufern.

### Technical Approach
Bestätigt wie im Kontext-Dokument beschrieben: `*bool` + `omitempty` (Go), Nil-Check-Merge im
Handler, `preset.get(..., True)` (Python), neuer Default-Parameter an `ComparisonEngine.run()`
mit conditional Skip des Fetch-Aufrufs (kein Fetch bei `False`, nicht nur Ausblenden), Svelte
State+Payload analog `forecastHours`. Checkbox-Platzierung: **Step5Versand.svelte** (dort steht
bereits `forecastHours` als nächstliegendes Vorbild — "was wird abgerufen", kein Layout-Feld;
Step4Layout ist reine Tabellen-Spalten-Konfiguration pro Kanal, thematisch falsch).

### Dependencies
Siehe oben (Dependencies-Abschnitt) — #1034 als Upstream, drei `ComparisonEngine.run()`-Aufrufer,
zwei davon unberührt.

### Implementierungsreihenfolge
Go-Model → Go-Handler (mit Zwei-Nutzer-Test AC-3) → Python-Engine → Python-Scheduler
(AC-1-Call-Counter-Beweis) → Svelte (State → Save-Payload → Checkbox in Step5). Backend zuerst,
da AC-1/AC-3 dort ohne Frontend beweisbar sind; Svelte zuletzt (additiv, keine Rückwirkung auf
Backend-Tests).

### Open Questions
Keine offenen Fragen mehr — Checkbox-Platzierung entschieden (Step5Versand.svelte).
