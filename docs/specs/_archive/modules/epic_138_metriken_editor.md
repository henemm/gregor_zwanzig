---
entity_id: epic_138_metriken_editor
type: module
created: 2026-05-17
updated: 2026-05-17
status: draft
version: "1.0"
tags: [frontend, sveltekit, weather-config, trip-detail, metrics, epic-138, bugfix]
---

# Epic 138 — Wetter-Metriken-Editor Tab (Trip-Detail)

## Approval

- [ ] Approved

## Purpose

Ersetzt den Platzhaltertext im „Wetter-Metriken"-Tab der Trip-Detail-Ansicht durch einen vollständigen Inline-Editor, der alle 26 Metriken in 5 Kategorien mit Checkboxen zeigt, 7 Template-Presets zur schnellen Vorauswahl bietet und für 9 eligible Metriken einen Roh/Indikator-Umschalter anbietet. Gleichzeitig behebt der Epic einen stillen Datenverlust-Bug: `WeatherConfigDialog.svelte` und `EditWeatherSection.svelte` schließen `use_friendly_format` bisher nicht in ihre Save-Payloads ein, wodurch der Go-Handler (Full-Replace) `use_friendly_format` bei jedem Speichern auf den Default `true` zurücksetzt.

## Source

- **CREATE:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
- **MODIFY:** `frontend/src/lib/components/trip-detail/TripTabs.svelte`
- **MODIFY:** `frontend/src/lib/components/trip-detail/index.ts`
- **MODIFY:** `frontend/src/lib/components/WeatherConfigDialog.svelte`
- **MODIFY:** `frontend/src/lib/components/edit/EditWeatherSection.svelte`
- **MODIFY:** `frontend/src/lib/types.ts`
- **MODIFY:** `api/routers/config.py`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/metrics` | Go-API-Endpunkt | Liefert 26 Metriken in 5 Kategorien inkl. neuem Feld `has_friendly_format` |
| `GET /api/templates` | Go-API-Endpunkt | Liefert 7 Template-Presets für die Dropdown-Auswahl |
| `GET /api/trips/{id}/weather-config` | Go-API-Endpunkt | Lädt bestehende Metriken-Konfiguration des Trips |
| `PUT /api/trips/{id}/weather-config` | Go-API-Endpunkt | Speichert neue Konfiguration (Full-Replace — alle 26 IDs müssen mitgeschickt werden) |
| `WeatherConfigDialog.svelte` | Svelte-Komponente | Bestehende Dialog-Variante für Locations/Subscriptions; Bug-Fix: `use_friendly_format` in Save-Payload aufnehmen |
| `EditWeatherSection.svelte` | Svelte-Komponente | Bestehende Inline-Variante im Wizard; Bug-Fix: `use_friendly_format` in `displayConfig` emittieren |
| `WeatherConfigMetric` | TypeScript-Interface (`frontend/src/lib/types.ts`) | Bekommt optionales Feld `use_friendly_format?: boolean` |
| `TripTabs.svelte` | Svelte-Komponente | Rendert WeatherMetricsTab an Stelle des Platzhaltertexts |
| Trip-Report-Formatter | Python-Backend | Konsumiert `use_friendly_format` aus persistierter Config — Downstream-Abhängigkeit, die korrekte Persistenz voraussetzt |

## Implementation Details

### §1 Python-API `api/routers/config.py` — `has_friendly_format` Feld

Im `/api/metrics`-Endpunkt-Handler jedes Metrik-Objekt um das Feld `has_friendly_format: bool` erweitern. Die 9 eligible Metriken erhalten `true`, alle anderen `false`:

```
Eligible (has_friendly_format=true):
  wind_direction, thunder, cape, cloud_total, cloud_low,
  cloud_mid, cloud_high, visibility, sunshine
```

Änderungsumfang: +1 Feld pro Metrik in der Serialisierung, ca. +1 LoC im Handler.

### §2 TypeScript `frontend/src/lib/types.ts`

Im `WeatherConfigMetric`-Interface optionales Feld ergänzen:

```typescript
export interface WeatherConfigMetric {
    metric_id: string;
    enabled: boolean;
    use_friendly_format?: boolean;   // NEU
}
```

### §3 Bug-Fix `WeatherConfigDialog.svelte`

**Problem:** Beim Speichern fehlt `use_friendly_format` im Payload, Go-Handler setzt es auf Default `true` zurück.

**Fix:**
1. Neuen State `friendlyMap: Record<string, boolean> = $state({})` anlegen.
2. Bei Initialisierung aus der bestehenden Konfiguration: `friendlyMap[m.metric_id] = m.use_friendly_format ?? true` für jede Metrik befüllen.
3. Im Save-Handler für jede Metrik `use_friendly_format: friendlyMap[metric_id] ?? true` in das Payload-Objekt aufnehmen.
4. Die Roh/Indikator-Buttons (gleiche UX wie WeatherMetricsTab, §5) im Dialog für die 9 eligible Metriken rendern.

Änderungsumfang: ca. +25 LoC.

### §4 Bug-Fix `EditWeatherSection.svelte`

**Problem:** `displayConfig`-Emission enthält kein `use_friendly_format`.

**Fix:**
1. Neuen State `friendlyMap: Record<string, boolean> = $state({})` anlegen.
2. Initialisierung aus `displayConfig.metrics[].use_friendly_format` analog zu §3.
3. Beim Aufbau des emittierten `displayConfig`-Objekts: `use_friendly_format: friendlyMap[metric_id] ?? true` je Metrik setzen.
4. Roh/Indikator-Buttons für eligible Metriken rendern.

Änderungsumfang: ca. +20 LoC.

### §5 Neue Komponente `WeatherMetricsTab.svelte`

**Architektur:** Inline-Editor mit eigenem Save-Lifecycle (kein Dialog-Wrapper, kein Two-Way-Binding). Muster: `EditWeatherSection` für State-Struktur, eigener `PUT`-Call anstatt Two-Way-Binding.

**State:**

```typescript
let enabledMap: Record<string, boolean> = $state({});
let friendlyMap: Record<string, boolean> = $state({});
let selectedTemplate: string = $state('');
let saveSuccess = $state(false);
let saveError: string | null = $state(null);
let saving = $state(false);
```

**Initialisierung:**

```typescript
// Parallel laden
const [catalogRes, templatesRes] = await Promise.all([
    fetch('/api/metrics'),
    fetch('/api/templates')
]);
// enabledMap aus trip.display_config.metrics[].enabled
// Fallback wenn Metrik nicht in display_config: m.default_enabled
// friendlyMap aus trip.display_config.metrics[].use_friendly_format
// Fallback: true
```

**Template-Anwendung:**
- Setzt nur `enabledMap` (Templates haben keine Format-Präferenz).
- `lastAppliedTemplate`-Guard verhindert Re-Trigger (analog `EditWeatherSection`).
- Manuelle Änderung an einer Checkbox setzt `selectedTemplate = '__custom__'`.

**Roh/Indikator-Toggle (UX):**
- Zwei-Button-Segment-Gruppe (Roh | Indikator) pro Metrik-Zeile.
- Wird nur gerendert wenn `metric.has_friendly_format === true`.
- „Indikator" entspricht `use_friendly_format: true`, „Roh" entspricht `use_friendly_format: false`.
- Standardmäßig auf „Indikator" (Fallback `true`).

**Save-Payload (kritisch — Full-Replace):**
Alle 26 Metrik-IDs müssen bei jedem Speichern mitgesendet werden. Fehlende IDs werden vom Go-Handler dauerhaft gelöscht.

```json
{
  "metrics": [
    { "metric_id": "temperature",  "enabled": true,  "use_friendly_format": true },
    { "metric_id": "cloud_total",  "enabled": true,  "use_friendly_format": false },
    ...
  ]
}
```

Aufbau: `catalog` (aus API) iterieren und für jede Metrik `enabledMap[id]` und `friendlyMap[id]` einsetzen — nie `enabledMap`-Keys iterieren (unvollständig wenn Metrik noch nicht angefasst wurde).

**data-testid-Inventar:**

| TestID | Element | Zweck |
|--------|---------|-------|
| `weather-metrics-tab` | Outer Container | Komponenten-Root |
| `weather-metrics-tab-template` | `<select>` | Template-Dropdown |
| `weather-metrics-tab-checkbox-{id}` | `<input type="checkbox">` | Metrik-Checkbox je ID |
| `weather-metrics-tab-format-raw-{id}` | `<button>` | „Roh"-Button (nur eligible) |
| `weather-metrics-tab-format-indicator-{id}` | `<button>` | „Indikator"-Button (nur eligible) |
| `weather-metrics-tab-save` | `<button>` | Speichern-Button |
| `weather-metrics-tab-success` | `<span>` oder `<p>` | Erfolgsmeldung (transient) |
| `weather-metrics-tab-error` | `<span>` oder `<p>` | Fehlermeldung |

Änderungsumfang: ca. +220 LoC.

### §6 `TripTabs.svelte` und `index.ts`

- `WeatherMetricsTab` in `TripTabs.svelte` importieren und in dem Tab-Panel rendern, das bisher den Platzhaltertext zeigt.
- Den Platzhalter-Eintrag aus dem `PLACEHOLDERS`-Objekt (oder äquivalentem Guard) für den Metriken-Tab entfernen.
- `WeatherMetricsTab` aus `frontend/src/lib/components/trip-detail/index.ts` re-exportieren.

Änderungsumfang: ca. +5 / -3 LoC.

### §7 LoC-Budget

| Datei | Aktion | Est. LoC |
|-------|--------|----------|
| `api/routers/config.py` | +`has_friendly_format`-Feld | +1 |
| `frontend/src/lib/types.ts` | +`use_friendly_format` in Interface | +1 |
| `WeatherConfigDialog.svelte` | Bug-Fix + friendlyMap + Buttons | +25 |
| `EditWeatherSection.svelte` | Bug-Fix + friendlyMap + Buttons | +20 |
| `WeatherMetricsTab.svelte` | NEU | +220 |
| `TripTabs.svelte` | Import + Render + Placeholder entfernen | +5 / -3 |
| `frontend/src/lib/components/trip-detail/index.ts` | Re-Export | +1 |
| **Summe netto** | | **~270 LoC** |

LoC-Limit-Override auf 300 setzen vor Implementierung: `workflow.py set-field loc_limit_override 300`.

## Expected Behavior

- **Input:** Benutzer öffnet Trip-Detail und wechselt auf den „Wetter-Metriken"-Tab.
- **Output:** Vollständiger Inline-Editor mit 26 Metriken in 5 Kategorien, Template-Dropdown mit 7 Presets, Roh/Indikator-Buttons für die 9 eligible Metriken, Speichern-Button.
- **Input (Speichern):** Benutzer wählt Metriken + Format und klickt Speichern.
- **Output (Speichern):** `PUT /api/trips/{id}/weather-config` mit allen 26 Metrik-IDs und `use_friendly_format` pro Metrik; Erfolgsmeldung erscheint kurz.
- **Side effects:** `WeatherConfigDialog` und `EditWeatherSection` schließen ab sofort `use_friendly_format` in alle Save-Payloads ein — kein stiller Reset mehr durch den Go-Full-Replace-Handler.

## Acceptance Criteria

- **AC-1:** Given die Trip-Detail-Seite ist geladen und der Metriken-Tab wird geöffnet / When der Tab aktiv ist / Then ist `data-testid="weather-metrics-tab"` im DOM sichtbar und kein Platzhaltertext ist zu sehen — stattdessen sind Metrik-Checkboxen und ein Speichern-Button vorhanden.
  - Test: (populated after /tdd-red)

- **AC-2:** Given der Metriken-Tab ist geöffnet / When die Komponente geladen hat / Then sind genau 26 Metrik-Checkboxen mit `data-testid="weather-metrics-tab-checkbox-{id}"` im DOM, gruppiert in 5 sichtbare Kategorie-Abschnitte.
  - Test: (populated after /tdd-red)

- **AC-3:** Given der Metriken-Tab ist geöffnet / When das Template-Dropdown (`data-testid="weather-metrics-tab-template"`) aufgeklappt wird / Then sind genau 7 Preset-Optionen plus eine „Eigene Auswahl"-Option sichtbar.
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein Template wird im Dropdown ausgewählt / When die Auswahl bestätigt wird / Then werden alle Metrik-Checkboxen entsprechend des Templates aktiviert oder deaktiviert — ohne dass `use_friendly_format`-Werte verändert werden.
  - Test: (populated after /tdd-red)

- **AC-5:** Given der Metriken-Tab ist geladen / When die Metrik-Liste gerendert ist / Then haben genau die 9 eligible Metriken (wind_direction, thunder, cape, cloud_total, cloud_low, cloud_mid, cloud_high, visibility, sunshine) sowohl `data-testid="weather-metrics-tab-format-raw-{id}"` als auch `data-testid="weather-metrics-tab-format-indicator-{id}"` im DOM — alle anderen 17 Metriken haben diese Buttons nicht.
  - Test: (populated after /tdd-red)

- **AC-6:** Given der Benutzer wählt Metriken aus und klickt auf `data-testid="weather-metrics-tab-save"` / When der Save-Request erfolgreich abgeschlossen ist / Then enthält der gesendete PUT-Body genau 26 Metrik-Objekte mit je `metric_id`, `enabled` und `use_friendly_format` — keine Metrik-ID fehlt im Payload.
  - Test: (populated after /tdd-red)

- **AC-7:** Given der Benutzer setzt für eine eligible Metrik den Format-Toggle auf „Roh" und speichert / When der Tab neu geladen wird (Seite neu öffnen) / Then zeigt der Toggle für diese Metrik weiterhin „Roh" — der Wert wurde korrekt persistiert und nicht durch Go-Default überschrieben.
  - Test: (populated after /tdd-red)

- **AC-8:** Given ein Benutzer öffnet den Wetter-Konfigurations-Dialog (`WeatherConfigDialog`) für eine Location / When er eine Änderung speichert / Then enthält der gesendete Payload für jede Metrik das Feld `use_friendly_format` mit dem tatsächlich gesetzten Wert — ein anschließender GET liefert den gespeicherten Wert zurück, nicht den Go-Default.
  - Test: (populated after /tdd-red)

- **AC-9:** Given ein Benutzer bearbeitet die Wetter-Konfiguration in `EditWeatherSection` im Wizard / When die Sektion ihren `displayConfig`-Wert emittiert / Then enthält jedes Metrik-Objekt im emittierten `displayConfig` das Feld `use_friendly_format` mit dem aktuellen Toggle-Zustand — kein stiller Verlust durch fehlendes Feld.
  - Test: (populated after /tdd-red)

- **AC-10:** Given der Metriken-Tab ist geöffnet und der Benutzer klickt Speichern / When der PUT erfolgreich ist / Then erscheint `data-testid="weather-metrics-tab-success"` kurz im DOM; bei einem API-Fehler erscheint stattdessen `data-testid="weather-metrics-tab-error"` mit einer lesbaren Fehlermeldung.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Full-Replace-Semantik:** Der Go-Handler `PUT /api/trips/{id}/weather-config` ersetzt die gesamte Metrik-Liste. Wenn neue Metriken in Zukunft zur API-Katalog hinzukommen und ein älteres Frontend speichert, werden diese fehlenden IDs gelöscht. Eine Read-Modify-Write-Umstellung des Go-Handlers liegt außerhalb dieses Epics.
- **Kein Undo:** Es gibt keine Discard-Funktion; ungespeicherte Änderungen gehen beim Tab-Wechsel verloren (wie in `EditWeatherSection`).
- **Keine Echtzeit-Vorschau:** Der Metriken-Editor ändert nicht sofort den Report-Output — Änderungen sind erst im nächsten geplanten oder manuell getriggerten Report sichtbar.
- **Template-Anwendung überschreibt manuelle Checkboxen:** Wer ein Template auswählt und danach einzelne Metriken anpasst, verliert bei erneutem Template-Wechsel seine manuelle Auswahl. Dieses Verhalten ist identisch mit `EditWeatherSection`.

## Changelog

- 2026-05-17: Initial spec — Epic #138. Neuer `WeatherMetricsTab.svelte` (ca. 220 LoC) + Bug-Fix `use_friendly_format` in `WeatherConfigDialog` und `EditWeatherSection` + `has_friendly_format`-Feld in `/api/metrics`. 7 Dateien betroffen, ~270 LoC netto. 10 Acceptance Criteria im AC-N-Format.
