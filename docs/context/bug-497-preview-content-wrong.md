# Context: Bug #497 — Trip/Preview ist inhaltlich falsch

## Request Summary
Die Vorschau-Seite (`/trips/{id}#preview`) zeigt (a) einen falschen SMS-Etappennamen und
(b) leere Zellen bei Metriken, die der User aktiviert hat — Ursache: fehlerhafte String-Verarbeitung
im Preview-Service und unvollständige Fixture-Daten im Demo-Modus.

## Zwei Root-Cause-Bugs

### Bug 1 — SMS-Präfix falsch (`preview_service.py:151`)
```python
# FALSCH (aktuell):
clean_stage = (stage_name or "Etappe").replace(":", "").strip()
# Resultat: "KHW_10: von Egger Alm..." → "KHW_10 von Egger Alm..." → [:10] = "KHW_10 von"

# RICHTIG:
clean_stage = (stage_name or "Etappe").split(":", 1)[0].strip()
# Resultat: "KHW_10: von Egger Alm..." → "KHW_10" → korrekt
```

### Bug 2 — FixtureProvider fehlt 4 Felder (`src/providers/fixture.py`)
`fetch_forecast()` befüllt `ForecastDataPoint` nur mit 13 von ~17 relevanten Feldern.
Fehlend:
- `cloud_low_pct` → Spalte „CtdLow" zeigt „-"
- `pop_pct` → Spalte „R%" (Regenwahrscheinlichkeit) zeigt „-"
- `snow_limit_m` → Spalte „Snowl" (Schneefallgrenze) zeigt „-"
- `wind_dir_deg` → Spalte „WDir" zeigt „-"

Die Fixture-JSON-Dateien (`fixtures/openmeteo/*.json`) enthalten diese Felder bereits
(sie sind Teil des Open-Meteo-API-Formats), werden aber in `fetch_forecast()` nicht gemappt.

## Related Files

| File | Relevanz |
|------|----------|
| `src/services/preview_service.py:151` | Bug 1: falsche `replace`-Logik im SMS-Präfix |
| `src/providers/fixture.py` | Bug 2: `fetch_forecast()` mappt 4 Felder nicht |
| `fixtures/openmeteo/*.json` | Fixture-Rohdaten — enthalten fehlende Felder bereits |
| `src/output/tokens/builder.py:31` | `_sanitize_stage_name()` — korrekte Referenz-Impl. (split-Logik) |
| `src/services/preview_service.py` | `render_sms_preview()`, `_build_report()`, `_resolve_target_date()` |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Vorschau-Tab, Demo-Banner, demoMode State |
| `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` | Kanal-Layout-Vorschau (Issue #496 betrifft dies) |
| `data/users/henning/trips/5f534011.json` | KHW 403 Trip — 15 aktivierte Metriken, davon 4 ohne Fixture-Daten |

## Existing Patterns

- `_sanitize_stage_name()` in `builder.py:31` macht es richtig: `name.translate(_UMLAUT)[:10]` — kein `replace(":", "")`, kein `split` nötig dort, weil der Name schon der reine Segment-Name ohne Präfix ist. Aber in `preview_service.py` kommt der Name aus den Trip-Stage-Daten, die das Format `"ID: Beschreibung"` haben.
- `FixtureProvider._FIXTURE_LOCATIONS` hat 3 Standorte (Innsbruck, Stubai, Zillertal). Die JSON-Fixtures sind vollständige Open-Meteo-Antworten und enthalten alle Felder — nur das Mapping in Python fehlt.
- Demo-Modus wird per `demo=True` in `_build_report()` aktiviert; `TripTabs.svelte` setzt `demoMode=$state(true)` als Default.

## Dependencies

- **Upstream:** `fixtures/openmeteo/*.json` → `FixtureProvider.fetch_forecast()` → `ForecastDataPoint` → Render-Pipeline
- **Downstream:** `PreviewService.render_sms_preview()` / `render_email_preview()` → `/api/preview/{trip_id}/sms` → Frontend-Vorschau

## Design-Kontext: Issue #496 (separates Issue, Handoff vorhanden)

Design-Handoff wurde heruntergeladen nach `/tmp/design-497/`:
- `screen-channel-preview-redesign.jsx` — Redesign `ChannelPreviewBlock` im WeatherMetricsTab (Issue #496)
- `screen-output-preview.jsx` — Neues E-Mail-/SMS-Format (Grouped Column Headers, Quick-Take, Risk Dots)

**#497 (dieser Fix) ist von #496 unabhängig** — wir korrigieren das inhaltliche Fehlverhalten,
das neue Design kommt als separater Workflow.

## Risks & Considerations

- `pop_pct` wird von Open-Meteo als `precipitation_probability` geliefert — muss der JSON-Key im Fixture gecheckt werden
- `snow_limit_m` → Open-Meteo heißt `snowfall_height` oder `freezing_level_height` — Fixture-Key verifizieren
- `wind_dir_deg` → Open-Meteo: `wind_direction_10m` — ebenfalls Fixture-Key checken
- Nur die **Demo**-Fixtures patchen; der echte `OpenMeteoProvider` ist korrekt und unverändert
- Kein Mocking in Tests — Fixtures sind echte JSON-Daten, Tests gegen `FixtureProvider` direkt
