# Context: Sport-Aware Comparison (#35)

## Request Summary
Die Compare-Engine ist fest auf Skifahren ausgelegt (Schnee-Bonus, Neuschnee-Bonus). Das Scoring muss sportartabhaengig werden — was "gutes Wetter" ist, haengt von der Aktivitaet ab (Wandern: Sonne+trocken gut, Skifahren: Neuschnee gut). Dazu: Rename "Ski Comparison" → "Weather Comparison".

## Kernproblem
`calculate_score()` in `src/web/pages/compare.py:45-216` bewertet Wetter NUR aus Ski-Perspektive:
- Schnehoehe: bis +15 Punkte
- Neuschnee: bis +25 Punkte
- Sonnenstunden: bis +15
- Wind: bis -20 Strafe

Fuer Wandern waere z.B. Niederschlag viel schlimmer, Schnee irrelevant, Gewitter kritisch.

## Related Files

| File | Relevance |
|------|-----------|
| `src/web/pages/compare.py` | Compare-Engine + Scoring (Zeilen 45-216), ComparisonEngine (222-391) |
| `src/app/user.py:117-138` | CompareSubscription — KEIN activity_profile Feld |
| `src/app/user.py:20-24` | LocationActivityProfile Enum (wintersport, wandern, allgemein) |
| `src/app/metric_catalog.py:382-397` | PROFILE_METRIC_IDS — Metriken pro Aktivitaet |
| `src/formatters/wintersport.py` | Wintersport-spezifischer Formatter |
| `src/services/risk_engine.py` | Risk Engine — aktivitaetsneutral (absolute Schwellen) |
| `internal/risk/engine.go` | Go Risk Engine — ebenfalls aktivitaetsneutral |
| `src/web/pages/subscriptions.py` | Subscription-UI (Dialog Zeilen 275-446) |
| `frontend/src/lib/types.ts` | Frontend Location-Type hat activity_profile |
| `docs/specs/compare_email.md` | E-Mail Spec — fest auf Ski-Metriken |
| `docs/specs/wintersport_extension.md` | Wintersport-spezifische Metriken-Spec |

## Existing Patterns

### Activity-Profile existieren bereits auf Location-Ebene
- `LocationActivityProfile` Enum: `wintersport`, `wandern`, `allgemein`
- `PROFILE_METRIC_IDS` definiert welche Metriken pro Profil relevant sind
- Location-Model (Python + Go + Frontend) hat `activity_profile` Feld

### Compare-Subscription hat KEIN Sport-Feld
- `CompareSubscription` kennt nur Locations, Schedule, Zeitfenster
- Kein `activity_profile` oder aehnliches Feld
- `display_config` (F14a) ist optional aber nicht sport-gekoppelt

### Risk Engine ist aktivitaetsneutral
- Bewertet absolute Wetterwerte (Wind >70 km/h = HIGH)
- Keine Unterscheidung nach Sportart
- Das ist KORREKT so — Risiko ist objektiv

## Luecken & Design-Fragen

1. **Wo lebt das Sport-Profil?** Auf Subscription-Ebene? Oder von den Locations abgeleitet?
2. **Scoring-Funktionen:** Braucht jede Sportart eigene Gewichtungen, oder reicht ein generisches Gewichtungs-Schema mit Sport-Presets?
3. **Neue Sportarten:** Nur wandern/wintersport/allgemein, oder erweiterbar (Klettern, Radfahren, Trailrunning)?
4. **E-Mail-Rendering:** Muessen die angezeigten Metriken auch sport-abhaengig sein? (Wandern: kein Schnee zeigen)
5. **Risk Engine:** Bleibt aktivitaetsneutral oder sollen Schwellen auch sport-abhaengig werden?
6. **Naming:** "Ski Comparison" → "Weather Comparison" in UI, E-Mail-Subject, Code

## Dependencies

- **Upstream:** OpenMeteo Provider (Wetterdaten), MetricCatalog (Metriken-Definition)
- **Downstream:** Compare-E-Mail-Renderer, Subscription-Scheduler, Frontend-UI

## Existing Specs
- `docs/specs/compare_email.md` — E-Mail Format (v4.3)
- `docs/specs/wintersport_extension.md` — Wintersport-Metriken
- `docs/specs/modules/risk_engine.md` — Risk Engine (v2.0)

## Aktueller Stand (April 2026)

- SvelteKit-Migration ist ABGESCHLOSSEN (M4b Cutover + M6a-f)
- NiceGUI ist deaktiviert → nur noch SvelteKit-Frontend relevant
- Compare-Seite existiert in SvelteKit (`frontend/src/routes/compare/`)
- Compare-API existiert (`api/routers/compare.py`)
- Go Proxy existiert (`cmd/server/main.go`)
- Subscription-Seite in SvelteKit existiert mit CRUD

## Betroffene Dateien (aktualisiert)

### Python (Scoring + API)
- `src/web/pages/compare.py:45-137` — `calculate_score()` umbauen
- `src/web/pages/compare.py:222-390` — `ComparisonEngine.run()` Profil weiterreichen
- `src/services/compare_subscription.py` — Profil aus Subscription extrahieren
- `api/routers/compare.py` — `activity_profile` Query-Parameter
- `src/app/user.py` — `CompareSubscription` um `activity_profile` erweitern

### Go (Model + Validation)
- `internal/model/subscription.go` — `ActivityProfile` Feld
- `internal/handler/subscription.go` — Validierung

### SvelteKit (UI)
- `frontend/src/lib/types.ts` — Subscription Type
- `frontend/src/routes/compare/+page.svelte` — Profil-Auswahl
- `frontend/src/lib/components/SubscriptionForm.svelte` — Profil-Dropdown

## Risks & Considerations
- Compare-Score ist tief in E-Mail-Rendering und UI verwoben — Aenderung hat breiten Impact
- Subscription-Profil statt Location-Profil: Ein Vergleich hat EIN Profil, nicht pro Location
- Bestehende Subscriptions brauchen Default = `allgemein` (nicht wintersport, um nichts zu brechen)
- E-Mail Subject: "Ski Resort Comparison" → "Wetter-Vergleich: {name}"
