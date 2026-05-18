# Context: Epic 138 — Wetter-Metriken-Editor (Block B)

## Request Summary

Block B: Fünf offene Issues (#174–#178) ergänzen den bereits teilweise
implementierten `WeatherMetricsTab` um fehlende Komponenten: MetricGroup/
MetricCheckbox als Sub-Komponenten, TablePreview (Live-Vorschau), SavePresetDialog
(Modal), und dirty-State mit Ungespeichert-Warnung.

**Stand 2026-05-18 (nach Kontext-Update):**
- Issues #173, #173-TDD, Epic #138 Grundgerüst: CLOSED / implementiert
- Issues #174–#178: OPEN — diese sind der Scope dieses Workflows

## Aktueller Codebase-Stand (nach vorherigen Workflows)

### Bereits implementiert ✓

| Datei | Status |
|-------|--------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Existiert, ~240 LoC — Grundgerüst läuft |
| `frontend/src/lib/components/trip-detail/PresetRow.svelte` | Issue #173 CLOSED — fertig |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | `<WeatherMetricsTab>` bereits eingehängt |
| `e2e/epic-138-metriken-editor.spec.ts` | E2E-Tests AC-1–AC-10 vorhanden |
| Backend: `GET/PUT /api/trips/{id}/weather-config` | Fertig, kein Backend-Touch nötig |
| Backend: `GET /api/metrics` + `GET /api/templates` | Fertig |

### Was `WeatherMetricsTab.svelte` bereits hat

- Lädt Katalog + Templates via `Promise.all`
- Preset-Liste mit `<PresetRow>` (Issue #173)
- 26 Metrik-Checkboxen (`<input type="checkbox">`) nach Kategorien geordnet
- Roh/Indikator-Toggle als einfache `<button>` pro Metrik (wenn `has_friendly_format`)
- Save-Button mit Erfolgs-/Fehlermeldung
- PUT `/api/trips/{id}/weather-config` mit `use_friendly_format` im Payload

### Was FEHLT (Issues #174–#178)

| Issue | Was fehlt | Dateien |
|-------|-----------|---------|
| #174 | `MetricGroup.svelte` (Eyebrow + aktive Zähler-Pill) + `MetricCheckbox.svelte` (Custom-Checkbox mit Label, Unit, Short-Text) | NEU |
| #175 | `ModeBtn.svelte` — Pill-Buttons im Design-System-Stil (statt raw `<button>`) | NEU |
| #176 | `TablePreview.svelte` — Live-Tabelle mit 4 Beispiel-Zeilen, Indikator-Werte kursiv+accent, ·skala-Marker in Header | NEU |
| #177 | `SavePresetDialog.svelte` — Modal mit Name, Beschreibung, Zusammenfassung (X aktiv/Y Roh/Z Indikator), "Als Standard"-Checkbox | NEU |
| #178 | `dirty`-State-Tracking in WeatherMetricsTab + "Ungespeicherte Änderungen"-Pill + Verwerfen-Button | EDIT `WeatherMetricsTab.svelte` |

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Haupt-Komponente — wird um dirty-State erweitert (#178) |
| `frontend/src/lib/components/trip-detail/PresetRow.svelte` | Referenz-Implementierung für Komponenten-Stil |
| `frontend/src/lib/components/ui/eyebrow/` | Eyebrow-Atom für MetricGroup (#174) |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Pill-Atom für dirty-State-Anzeige (#178) |
| `frontend/src/lib/components/ui/dialog/` | Dialog-Atom für SavePresetDialog (#177) |
| `frontend/src/lib/components/ui/table/` | Table-Atom — Basis für TablePreview (#176) |
| `frontend/src/lib/components/ui/btn/` | Btn-Atom — Verwerfen-Button (#178) |
| `src/app/metric_catalog.py` | 26 MetricDefinitions, 9 mit `has_friendly_format=True` |
| `e2e/epic-138-metriken-editor.spec.ts` | AC-1–AC-10 E2E-Tests (gegen localhost:4173) |

## Verfügbare UI-Atome

`badge`, `btn`, `card`, `dialog`, `dot`, `elev-sparkline`, `eyebrow`,
`g-card`, `input`, `label`, `pill`, `sidebar`, `table`, `topo`

Dialog-Atom hat: `dialog.svelte`, `dialog-content.svelte`, `dialog-header.svelte`,
`dialog-footer.svelte`, `dialog-trigger.svelte`, `dialog-overlay.svelte`

## Metriken mit Indikator-Format (9 Stück, hat_friendly_format=True)

`wind_direction`, `thunder`, `cape`, `cloud_total`, `cloud_low`,
`cloud_mid`, `cloud_high`, `visibility`, `sunshine`

*(Achtung: ursprünglicher Kontext sagte 12, E2E-Tests sagen 9 — metric_catalog.py
ist die einzige Quelle der Wahrheit, vor Implementierung verifizieren)*

## API-Kontrakt: Save-Payload (bereits korrekt implementiert)

```json
{ "metrics": [{"metric_id": "temperature", "enabled": true, "use_friendly_format": true}] }
```

`WeatherMetricsTab.handleSave()` schreibt `use_friendly_format` bereits korrekt.

## Dependencies

- **Upstream:** `GET /api/metrics`, `GET /api/templates`, `GET /api/trips/{id}/weather-config` (alle fertig)
- **Downstream:** E2E-Tests AC-1–AC-10 testen das Endergebnis

## Risks & Considerations

- **Komponentenextraktion (#174, #175):** WeatherMetricsTab hat inline-HTML für Checkboxen
  und Toggle-Buttons. Extraktion in Sub-Komponenten muss Verhalten 1:1 erhalten — keine
  versteckten Regressions in bestehenden E2E-Tests (AC-1–AC-9 bereits grün?).
- **TablePreview (#176):** Braucht Beispieldaten. Welche 4 Beispiel-Zeilen? Müssen aus
  dem Katalog generiert werden (keine hardcodierten Fake-Werte).
- **SavePresetDialog (#177):** Wo werden User-Presets persistiert? Backend-Endpoint nötig
  oder nur Frontend-State? Klären in Analyse.
- **dirty-State (#178):** Initial-State = `trip.display_config`. Jede Änderung an
  `enabledMap` oder `friendlyMap` → dirty = true. Reset (Verwerfen) = Reload aus trip-Prop.
- **LoC-Limit:** 5 neue Komponenten + Edit WeatherMetricsTab. Schätzung ~400 LoC → braucht
  `workflow.py set-field loc_limit_override 500` vor Implementierung.
- **Keine Mocks:** Alle Tests müssen echte Daten nutzen (CLAUDE.md-Pflicht).
