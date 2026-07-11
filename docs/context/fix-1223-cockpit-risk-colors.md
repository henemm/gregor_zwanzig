# Context: fix-1223-cockpit-risk-colors

## Request Summary
Die live gemountete Cockpit-Etappenkachel (`HubOverview` → `TripStageRow`) zeigt nie die Wetter-Risiko-Ampel (grün/gelb/rot) — sie ruft den Risiko-Endpoint gar nicht auf und das Pill-Mapping passt nicht zum Response-Format. Ziel: pro Etappe echte Risiko-Farbe anzeigen (client-seitig/lazy, nicht im SSR-Home-Loader).

## Doppelter Defekt (Root Cause)
1. **Kein Fetch:** `HubOverview.svelte` mountet `TripStageRow` (`TripTabs.svelte:142` → `HubOverview:44-50`), lädt aber `GET /api/trips/{id}/stages/weather` nie. `TripStageRow.svelte:13` liest `stage.risk` — ein Feld, das das Backend-`Stage`-Modell nie füllt → immer leer.
2. **Mapping-Mismatch:** Selbst mit Fetch passt es nicht: Endpoint liefert `risk: 'green'|'yellow'|'red'|null` (`types.ts:448-451`), aber `TripStageRow.svelte:15-20` matcht auf `'high'|'med'` → alles fällt in `else` = Ton `good`/Label `OK` (immer grün).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | Live-Mount; braucht lazy Client-Fetch + Merge von `risk` in die an `TripStageRow` gereichten Etappen |
| `frontend/src/lib/components/trip-detail/TripStageRow.svelte` | Pill-Mapping `high/med` → `red/yellow/green` korrigieren; No-Data-Zustand definieren |
| `frontend/src/lib/components/trip-detail/StageList.svelte` | **Toter Referenz-Pfad** — zeigt den korrekten lazy `$effect`-Fetch (Z. 29-37) |
| `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | **Toter Referenz-Pfad** — korrektes `green/yellow/red`-Mapping (Z. 35-53), `null` bei fehlenden Daten |
| `frontend/src/lib/types.ts` | `StageWeatherResult` (Z. 448) + `StagesWeatherResponse` (Z. 453) — Response-Format |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Tone-Aliase: `good→success`, `warn→warning`, `bad→danger` (Z. 27-29) |

## Existing Patterns
- **Lazy Client-Fetch** (`StageList.svelte:29-37`): `$effect` mit `if (!trip?.id) return;`, `fetch('/api/trips/${id}/stages/weather')`, Ergebnis in `$state`-Record `Record<stageId, StageWeatherResult|null>`, `.catch(() => {})` fail-soft.
- **Risk→Pill-Mapping** (`StageDetailRow.svelte:35-53`): `green→(success,'Gering')`, `yellow→(warning,'Mittel')`, `red→(danger,'Hoch')`, sonst `null` (kein Pill).
- **Endpoint** ist ein Go-Backend-Endpoint (keine SvelteKit-Route unter `routes/`), proxied nach #1212 R2 auf den Python-Kern. Live.

## Dependencies
- **Upstream:** `GET /api/trips/{id}/stages/weather` (Go-Proxy → Python-SSoT-Risiko, #1212 R1/R2 live). `Pill`-Atom, `Trip`/`Stage`-Typen.
- **Downstream:** Nur der Übersicht-Tab (`HubOverview` in `TripTabs`). Kein anderer Konsument. Home-Liste/SSR-Loader bleibt unberührt.

## Existing Specs / Issues
- #1212 R1 ✅ live: Python-Endpoint `/api/_internal/trips/{id}/stages-weather` (SSoT).
- #1212 R2 ✅ live: Go-Handler → Proxy, alte Go-Risk-Logik gelöscht.
- #386/#395: Home-Loader darf den Wetter-Endpoint **nicht** aufrufen (sonst hängt `/` ~57 s).

## Risks & Considerations
- **#386/#395-Footgun (kritisch):** Fetch ausschließlich client-seitig/lazy im Cockpit-Tab — **niemals** im SSR-Home-Loader. Bricht sonst die Startseite.
- **Falsch-Grün-Regression:** Aktuell zeigt die Kachel bei fehlenden Daten „OK"/grün. Das ist irreführend (das ist genau der Bug). Bei `null`/lade-/Fehler-Zustand darf **keine** grüne „OK"-Pille erscheinen — analog `StageDetailRow` (kein Pill bzw. neutraler Platzhalter).
- **Merge-Weg:** `risk` in die an `TripStageRow` gereichten Etappen einspielen (expliziter `risk`-Prop sauberer als der bestehende `as Stage & {risk?}`-Cast).
- **Test-Namensregel:** Neue Testdatei verhaltensbenannt (z. B. `cockpit_stage_risk_colors.test.ts`), **nicht** issue-nummeriert (`test_naming_gate.py`).

## Analysis

### Type
Bug (nutzersichtbar: Cockpit zeigt keine Risiko-Farben; doppelter Defekt — fehlender Fetch + Mapping-Mismatch).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/trip-detail/HubOverview.svelte` | MODIFY | Lazy Client-`$effect`-Fetch von `/api/trips/{id}/stages/weather` (Muster aus `StageList.svelte:29-37`), Ergebnis als `$state`-Record `Record<stageId, StageWeatherResult\|null>`; `risk` je Etappe als expliziten Prop an `TripStageRow` durchreichen |
| `frontend/src/lib/components/trip-detail/TripStageRow.svelte` | MODIFY | Neuen `risk?: 'green'\|'yellow'\|'red'\|null`-Prop; Pill-Mapping `high/med` → `red/yellow/green`; No-Data-Zustand = neutrale „—"-Pille |
| `frontend/src/lib/cockpit_stage_risk_colors.test.ts` | CREATE | Verhaltenstest: Mapping red→bad/„Risiko", yellow→warn/„Achten", green→good/„OK"; `null` → neutral „—" (kein Grün) |

### Scope Assessment
- Files: 3 (2 MODIFY, 1 CREATE)
- Estimated LoC: ~+45 / -6
- Risk Level: LOW–MEDIUM (isoliert auf Cockpit-Tab; einzige echte Gefahr = #386/#395-Regel, hier strukturell vermieden, da `HubOverview` nur im Trip-Cockpit clientseitig rendert, nie im SSR-Home-Loader)

### Technical Approach (Design-Entscheidungen, PO-bestätigt)
1. **Fetch:** In `HubOverview` per `$effect` clientseitig/lazy — 1:1 nach `StageList.svelte`-Muster, `.catch(() => {})` fail-soft. **Nie** im Home-Loader.
2. **Merge:** Expliziter `risk`-Prop an `TripStageRow` (statt `as Stage & {risk?}`-Cast) — `risk={stageWeather[stage.id]?.risk ?? null}`.
3. **Mapping (PO):** `red→(bad,'Risiko')`, `yellow→(warn,'Achten')`, `green→(good,'OK')`, `null/undefined→(neutral,'—')`.
4. **No-Data (PO):** Bei fehlenden/ladenden Daten neutrale „—"-Pille (Ton `neutral`) — **kein** irreführendes Grün. Layout bleibt stabil (Spalte 4 behält Breite).

### Dependencies
- Upstream: Go-Endpoint `/api/trips/{id}/stages/weather` (Proxy → Python-SSoT, #1212 live); `Pill`-Atom (`neutral`-Ton in ui/pill:9 vorhanden).
- Downstream: Nur `HubOverview`/Übersicht-Tab. Kein weiterer Konsument.

### Open Questions
- Keine offen — beide Design-Fragen (No-Data-Pille, Labels) PO-bestätigt.
