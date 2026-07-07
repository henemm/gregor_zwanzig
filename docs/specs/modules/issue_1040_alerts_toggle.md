---
entity_id: issue_1040_alerts_toggle
type: module
created: 2026-07-07
updated: 2026-07-07
status: implemented
version: "1.0"
tags: [compare, alerts, official-alerts, preset]
---

# Amtliche Alerts Slice 5 — Konfiguration pro Orts-Vergleich

## Approval

- [x] Approved

## Purpose

Ergänzt den Compare-Preset um ein Bool-Feld „Amtliche Warnungen anzeigen" (Default `true`), mit
dem ein Nutzer pro Orts-Vergleich die #1034–#1037-Official-Alert-Quellen **strukturell abschalten**
kann. Bei `false` werden diese Quellen für den betroffenen Vergleich gar nicht erst abgefragt (kein
Fetch), nicht nur im Rendering ausgeblendet — schont API-Kontingente und vermeidet unnötige
Netzwerk-Calls für Nutzer, die amtliche Warnungen für ihren Vergleich nicht wünschen.

## Source

- **File:** `internal/model/compare_preset.go`, `src/services/comparison_engine.py`
- **Identifier:** `ComparePreset.OfficialAlertsEnabled`, `ComparisonEngine.run(official_alerts_enabled=...)`

## Estimated Scope

- **LoC:** ~150–200 (Großteil in Tests, analog #1034/#1035)
- **Files:** 9 (8 geändert + 1 neu: `tests/tdd/test_issue_1040_alerts_toggle.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py::get_official_alerts_for_location()` (#1034) | Upstream, unverändert | Wird conditional aufgerufen; keine Änderung an der Funktion selbst |
| `internal/model/compare_preset.go::Weekday *int` | Muster-Referenz | Pointer-Pattern für optionale, rückwärtskompatible Preset-Felder |
| `internal/handler/compare_preset.go::DisplayConfig`-Merge (Zeile 199-201) | Muster-Referenz | Read-Modify-Write-Nil-Check im Update-Handler |
| `src/services/comparison_engine.py::forecast_hours: int = 48` | Muster-Referenz | Default-Parameter-Pattern für additive, abwärtskompatible Engine-Parameter |
| `frontend/.../compareWizardState.svelte.ts::forecastHours` (Zeile 36) | Muster-Referenz | `$state`-Deklaration + Aufnahme in alle drei Save-Pfade |
| `frontend/.../compareEditorSave.ts::CompareEditorEdits.forecastHours` (Zeile 22-23, 68) | Muster-Referenz | Optionales Edit-Feld + Round-Trip-Spread-Prinzip |
| `frontend/.../steps/Step5Versand.svelte::ChannelToggle` (Zeile 80-108) | Muster-Referenz | Bestehender Bool-Toggle für Checkbox-UI (E-Mail/Telegram/SMS) |

## Implementation Details

```go
// internal/model/compare_preset.go — neues Feld in ComparePreset-Struct
// Pointer-Pattern (wie Weekday *int), NICHT plain bool: fehlt das Feld im
// JSON (Altdaten), decodiert Go zu nil statt zum Zero-Value false. Ein
// plain bool würde Bestandspresets beim nächsten Speichern durch einen
// Client, der das Feld nicht kennt, unbemerkt auf "aus" umstellen.
OfficialAlertsEnabled *bool `json:"official_alerts_enabled,omitempty"`
```

```go
// internal/handler/compare_preset.go — UpdateComparePresetHandler, analog
// zum DisplayConfig-Merge (Zeile 199-201), NICHT dem ForecastHours-Zero-
// Value-Pattern (Zeile 207-209), weil false ein gültiger, bewusst gesetzter
// Wert ist und nicht mit "Feld fehlte" verwechselt werden darf.
if updated.OfficialAlertsEnabled == nil {
    updated.OfficialAlertsEnabled = original.OfficialAlertsEnabled
}
```

```python
# src/services/comparison_engine.py — ComparisonEngine.run(), neuer
# Default-Parameter analog forecast_hours: int = 48. Zeile ~180-182 wird
# conditional: kein Fetch bei False (strukturell, nicht nur Ausblenden).
@staticmethod
def run(
    locations: List[SavedLocation],
    time_window: tuple[int, int],
    target_date: "date",
    forecast_hours: int = 48,
    profile: Optional["ActivityProfile"] = None,
    official_alerts_enabled: bool = True,
) -> ComparisonResult:
    ...
    if official_alerts_enabled:
        from services.official_alerts import get_official_alerts_for_location
        official_alerts = get_official_alerts_for_location(loc.lat, loc.lon)
    else:
        official_alerts = []
```

```python
# src/services/scheduler_dispatch_service.py:237-243 — send_one_compare_preset()
result = ComparisonEngine.run(
    locations=locations,
    time_window=(hour_from, hour_to),
    target_date=date.today(),
    forecast_hours=preset.get("forecast_hours", 48),
    profile=profile,
    official_alerts_enabled=preset.get("official_alerts_enabled", True),
)
```

**Renderer-Konsequenz (kein eigener Code nötig):** Sowohl `render_compare_html()`
(`src/output/renderers/email/compare_html.py`) als auch der Text-Renderer
(`src/output/renderers/comparison.py:419`, `for alert in loc_result.official_alerts`) iterieren
bereits ausschließlich über `LocationResult.official_alerts`. Da dieses Feld bei
`official_alerts_enabled=False` durch den Skip in `ComparisonEngine.run()` leer bleibt (statt
befüllt zu werden), zeigen beide Renderer automatisch keine Warnzeile — analog zum
byte-identischen Verhalten bei leerer Registry aus #1034 AC-1. Kein Renderer-Datei-Edit in diesem
Slice nötig, kein Renderer-Commit-Gate (#811) betroffen.

```typescript
// frontend/src/lib/types.ts — ComparePreset-Interface, optionales Feld
// (technische Notwendigkeit für TS-Typsicherheit beim Spread in
// buildComparePresetSavePayload(); im Analyse-Dokument nicht separat
// gelistet, aber ohne dieses Feld schlägt der TS-Compile fehl)
official_alerts_enabled?: boolean;
```

```typescript
// frontend/.../compareWizardState.svelte.ts — Zeile 36 (State), analog
// forecastHours; Aufnahme in saveComparePreset() (Zeile 190-213) über
// CompareEditorEdits
officialAlertsEnabled = $state(true);
```

```typescript
// frontend/.../compareEditorSave.ts — CompareEditorEdits (Zeile 13-24) +
// Spread in buildComparePresetSavePayload() (Zeile 60-69), Round-Trip-
// Prinzip identisch zu forecastHours (Zeile 22-23, 68)
officialAlertsEnabled?: boolean;
...
...(edits.officialAlertsEnabled !== undefined
    ? { official_alerts_enabled: edits.officialAlertsEnabled }
    : {})
```

```svelte
<!-- frontend/.../steps/Step5Versand.svelte — neue Checkbox im
     Kanal-Bereich (Zeile 74-120), Vorbild ChannelToggle-Komponente
     (bereits importiert, Zeile 8), NICHT Step4Layout.svelte -->
<ChannelToggle
    label="Amtliche Warnungen"
    checked={state.officialAlertsEnabled}
    onchange={(checked) => (state.officialAlertsEnabled = checked)}
    testid="compare-step5-official-alerts-toggle"
/>
```

Beim Laden eines bestehenden Presets im Edit-Modus (`+page.svelte`, analog Zeile 35
`state.forecastHours = data.preset.forecast_hours ?? 48`) wird
`state.officialAlertsEnabled = data.preset.official_alerts_enabled ?? true` gesetzt.

## Expected Behavior

- **Input:** `ComparePreset.official_alerts_enabled` (Bool oder fehlend/`null`).
- **Output:** Ist der Wert `false`, ruft `ComparisonEngine.run()` `get_official_alerts_for_location()`
  für keinen der verglichenen Orte auf; die resultierende Compare-Mail (HTML und Text) enthält
  keine amtliche-Warnungen-Zeile. Ist der Wert `true` oder fehlt er (Altdaten), ist das Verhalten
  identisch zu #1034–#1037 (Quellen werden abgefragt, Badges/Zeilen erscheinen bei Treffern).
- **Side effects:** Bei `false` entfallen die HTTP-Calls der registrierten Official-Alert-Quellen
  für diesen Vergleichslauf (weniger externe Requests, kein sonstiger Effekt).

## Acceptance Criteria

- **AC-1:** Given ein Compare-Preset mit `official_alerts_enabled=false` und einer registrierten
  Test-Fake-Quelle, die bei Aufruf einen Treffer liefern würde, When `ComparisonEngine.run()` mit
  `official_alerts_enabled=False` aufgerufen wird, Then wird die Fake-Quelle nachweislich **nicht**
  aufgerufen (Call-Counter der Fake-Quelle = 0) und die resultierende Compare-Mail enthält keine
  Warnzeile für amtliche Alerts.
  - Test: Test-Fake-Quelle mit einem Aufruf-Zähler über `register_official_alert_source()`
    registrieren, echten `ComparisonEngine.run(..., official_alerts_enabled=False)`-Aufruf
    durchführen, `fetch()`-Zähler auf 0 prüfen, anschließend `render_compare_html()` /
    `render_comparison_text()` aufrufen und die Abwesenheit der Warn-Zeile im generierten HTML/Text
    verifizieren.

- **AC-2:** Given dieselbe Test-Fake-Quelle und ein Compare-Preset mit `official_alerts_enabled=true`
  (bzw. ohne explizite Übergabe, Default), When `ComparisonEngine.run()` aufgerufen wird, Then wird
  die Fake-Quelle aufgerufen (Call-Counter ≥ 1) und das Verhalten ist identisch zu #1034–#1037
  (Badge/Zeile erscheint für den betroffenen Ort in HTML und Text).
  - Test: Gleicher Aufbau wie AC-1, aber `official_alerts_enabled=True` bzw. Default-Aufruf ohne
    den Parameter; Call-Counter ≥ 1 und Vorhandensein der Warn-Zeile in HTML/Text prüfen.

- **AC-3:** Given ein bestehendes, persistiertes Compare-Preset **ohne** das Feld
  `official_alerts_enabled` (simuliert Altdaten vor diesem Slice) für Nutzer A, When dieses Preset
  über `PUT /api/compare/presets/{id}` gespeichert wird, **ohne** dass der Request-Body das Feld
  `official_alerts_enabled` mitschickt (nur ein anderes Feld wird geändert, z.B. `name`), Then
  bleibt `official_alerts_enabled` nach dem Speichern `nil`/nicht gesetzt (Handler übernimmt aus
  `original`), das tatsächliche Laufzeitverhalten interpretiert dies als `true` (Quellen werden
  abgefragt), und alle anderen, unveränderten Felder des Presets (z.B. `location_ids`,
  `forecast_hours`, `empfaenger`) sind byte-identisch zum Zustand vor dem Save (Read-Modify-Write-
  Beweis, kein Datenverlust). Der identische Testablauf wird zusätzlich für Nutzer B mit einem
  eigenen, unabhängigen Preset wiederholt, um Cross-User-Datenlecks im Handler auszuschließen.
  - Test: Über den Go-Handler `UpdateComparePresetHandler` (bzw. den echten HTTP-Endpoint gegen
    `internal/store`) ein Preset ohne `official_alerts_enabled` anlegen, PUT mit geändertem `name`
    und ohne das Feld senden, danach das gespeicherte Preset laden und `OfficialAlertsEnabled == nil`
    sowie Unverändertheit der übrigen Felder prüfen; zusätzlich `ComparisonEngine`-seitig
    `preset.get("official_alerts_enabled", True)` auf `True` bei fehlendem Schlüssel verifizieren.
    Kompletter Testlauf für zwei getrennte `user_id`-Verzeichnisse (Pattern:
    `tests/tdd/test_issue_1004_startzeit_ssot.py::test_ac6_zwei_nutzer_isolation`), um zu
    beweisen, dass Nutzer A's Preset-Update Nutzer B's Preset nicht berührt.

## Known Limitations

- **Legacy-Pfad `CompareSubscription` (#456) bewusst unverändert:** `src/services/compare_subscription.py:90`
  ruft `ComparisonEngine.run()` ohne den neuen Parameter auf; der Default `True` greift, das
  Verhalten bleibt exakt wie vor diesem Slice. Dieser Pfad ist laut Issue #1040 explizit
  Out-of-Scope — eine Konfigurierbarkeit für `CompareSubscription` müsste separat spezifiziert
  werden.
- **Ad-hoc-Compare-API (`api/routers/compare.py:53`) bewusst unverändert:** Ruft
  `ComparisonEngine.run()` ohne Preset-Objekt und ohne den neuen Parameter auf; Default `True`
  greift, Verhalten unverändert. Kein Preset-Kontext vorhanden, aus dem ein Wert abgeleitet werden
  könnte.
- **Kein Renderer-Code-Edit:** Weder `compare_html.py` noch `comparison.py` (Text-Renderer) werden
  in diesem Slice verändert — beide respektieren den leeren `official_alerts`-State strukturell
  über die bereits bestehende Iterationslogik (siehe Implementation Details).

## Out of Scope

- **`CompareSubscription`-Legacy-Pfad (#456):** Keine Konfigurationsoption für den alten
  Subscription-Mechanismus in diesem Slice.
- **Ad-hoc-Compare-API (`api/routers/compare.py`):** Kein Preset-Kontext, daher keine
  Konfigurierbarkeit über diesen Pfad.
- **Granularität pro Alert-Quelle:** Das Feld schaltet ALLE Official-Alert-Quellen gemeinsam
  ein/aus, keine Auswahl einzelner Quellen (z.B. nur Vigilance, nicht andere zukünftige Quellen).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additives, optionales Konfigurationsfeld nach etabliertem Pointer-Pattern
  (`Weekday *int`, `DisplayConfig`) — keine neue Architekturentscheidung nötig, folgt
  vollständig bestehenden, bereits per ADR-0016 (#1034) legitimierten Mustern für das
  Official-Alerts-Fundament.

## Changelog

- 2026-07-07: Initial spec created (Epic #1033, Issue #1040).
- 2026-07-07: Implementierung abgeschlossen, Adversary VERIFIED. Alle drei Schichten (Go-Preset-Modell/Handler, Python-Engine/Scheduler-Dispatch, Svelte-Editor) wie spezifiziert umgesetzt.
