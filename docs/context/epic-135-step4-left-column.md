---
entity_id: epic_135_step4_left_column
type: context
created: 2026-05-12
issues: [156, 157]
related: [epic_135_step3_trip_hero, epic_136_step3_waypoints]
---

# Context: Epic #135 Step 4 — Linke Spalte (Full-Profil SVG + Stage-Row-Liste)

## Request Summary

Linke Spalte des Overview-Tabs unterhalb des `TripHero` (Step 3): kombiniertes Höhenprofil-SVG aller Etappen (#156, klickbar, aktive Etappe orange) + Stage-Row-Liste (#157, Code/Titel/Datum/km/Hm/Wpt-Count, Wetter-Summary, Risiko-Pill, klickbar → markiert Etappe im Profil).

## Related Files

| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/types.ts` | `Stage` (id, name, date, waypoints) + `Trip` (shortcode, stages, activity) + `Waypoint` (lat, lon, elevation_m, suggested) |
| `frontend/src/routes/trips/[id]/+page.server.ts` | API-Fetch `GET /api/trips/{id}` mit Session-Cookie |
| `frontend/src/routes/trips/[id]/+page.svelte` | `$state(data.trip)`, gibt Trip an TripTabs |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` Z. 33–34 | Overview-Panel — hier ersetzen wir den Placeholder durch `TripHero` + neue linke Spalte |
| `frontend/src/lib/components/trip-detail/TripHero.svelte` | Existiert (Step 3) — bleibt unverändert, nur darunter erweitern |
| `frontend/src/lib/components/trip-wizard/steps/ProfileChart.svelte` | SVG-Polyline + Waypoint-Pins, suggested=orange-gestrichelt — **Vorbild für #156**, muss aber Multi-Stage werden |
| `frontend/src/lib/components/ui/elev-sparkline/ElevSparkline.svelte` | Mini-Sparkline 120×24 — Pattern, zu klein für linke Spalte |
| `frontend/src/lib/components/email-preview/headerStats.ts` | `computeHeaderStats(stage)` → distanceKm, ascentM, descentM, maxElevationM aus Waypoints (Haversine) — **Direkt nutzbar für #157** |
| `frontend/src/lib/utils/weatherEmoji.ts` | `weatherEmoji(wmoCode, isDay, dniWm2, cloudPct)` + `degToCardinal(deg)` — wenn Wetter-Daten verfügbar |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | `tone='accent'|'success'|'warning'|'danger'|'info'` — direkt für Risiko-Pill |
| `frontend/src/routes/_cockpit/ActiveTripCard.svelte` | Layout-Vorbild: GCard + Eyebrow + h2 + Pill + Sparkline + Wetter — Style-Referenz für Stage-Rows |
| `frontend/src/routes/_cockpit/StagePill.svelte` | StagePill mit `tone='accent'` wenn aktiv — Pattern für aktive Markierung |
| `frontend/src/app.css` Z. 28–142 | Tokens `--g-accent: #c45a2a` (aktiv), `--g-warning: #c8882a`, `--g-success`, `--g-danger`, `--g-info`; `[data-slot="pill"]` |
| `frontend/e2e/global.setup.ts` Z. 19–52 | `e2e-cockpit-test` — 3 Stages mit 1–2 Waypoints, elevation_m (800/1200/600/400 m) |
| `docs/specs/modules/epic_135_step3_trip_hero.md` | Spec-Vorbild für AC-N-Format und Datei-Liste |

## Existing Patterns

- **SVG-Profil:** `ProfileChart.svelte` rendert Polyline + Pins für eine Stage. Multi-Stage ist neu — entweder pro Stage einen Pfad oder eine durchgehende Polyline mit Stage-Grenzen-Markern.
- **Card-Layout:** GCard + Eyebrow + Pill + Stat-Strip (Cockpit `ActiveTripCard`) — direktes Vorbild für `StageDetailRow`.
- **Aktive-Etappe-Heuristik:** `deriveTripStatus(trip, now)` + `stages.findIndex(s => s.date === today)` — bereits in `tripHero.ts` Step 3 implementiert, kann via Helper geteilt werden.
- **Interaktivität ohne Store:** Selected-Stage-ID im Parent (`Overview-Panel`) als `$state` halten, in beide Komponenten reichen (Single Source of Truth).

## Dependencies

**Upstream (was wir nutzen):**
- `Trip`, `Stage`, `Waypoint` aus `lib/types.ts`
- `computeHeaderStats(stage)` aus `email-preview/headerStats.ts`
- `Pill` aus `lib/components/ui/pill`
- Design-Tokens aus `app.css`

**Downstream (was uns nutzen wird):**
- Nichts — wir sind Endpunkte im Overview-Panel.

## Existing Specs

- `docs/specs/modules/epic_135_step3_trip_hero.md` — TripHero (Step 3), bleibt unverändert
- `docs/specs/modules/epic_135_step2_trip_detail_actions.md` — Step 2 Header
- `docs/specs/modules/epic_136_step3_waypoints.md` — ProfileChart-Pattern aus Wizard

## Risks & Considerations

1. **Wetter-Summary + Risiko-Pill in Issue #157** — Trip/Stage-Modell hat **kein** `weather_summary`- oder `risk`-Feld. Optionen:
   - **(a) Out of scope:** Stage-Row zeigt nur Code/Titel/Datum/km/Hm/Wpt; Wetter/Risiko in Folge-Issue.
   - **(b) Skeleton mit Platzhaltern:** Pill „Daten lädt…" + Folge-Issue für Daten-Anbindung.
   - **(c) Endpoint integrieren:** GET `/api/trips/{id}/stages/summary` — sprengt Step-4-Scope.
   - **Empfehlung:** (a) — Risiko-Pill UND Wetter-Summary aus Step-4 herauslösen, Issue #207 (neu) trackt das. Issue #157 explizit auf KPIs + Klick-Interaktion + Code/Titel/Datum scopen.

2. **Stage-Code:** `Stage` hat kein `code`-Feld, nur `name`. Im Wizard wird `T01`, `T02` aus Index abgeleitet (Pause-Stages ausgenommen). → Wir nutzen denselben Helper `formatStageNumber(index)`.

3. **Multi-Stage-Profil:** ProfileChart ist single-stage. Neu: durchgehende Polyline über alle Waypoints aller Stages, Stage-Grenzen als vertikale Trennlinien, Stage-Codes als Labels unten. Distanz-Achse statt Index.

4. **Active-Highlight-Reaktivität:** Selected-Stage-ID + Active-Stage (today) müssen unterschieden werden. Active = orange Hintergrund; Selected = stärkere Outline. Beim ersten Render ohne User-Klick wird Active = Selected.

5. **Mobile-Layout:** „Linke Spalte" auf Mobile = volle Breite, Profil über Liste (vertikal). Auf Desktop nebeneinander oder Profil oben + Liste darunter? Im Hauptlayout der Cockpit-Vorlage steht alles untereinander — sicherer Default.

6. **LoC-Schätzung:** Neue Dateien `FullProfile.svelte` (~120), `StageDetailRow.svelte` (~80), `StageList.svelte` (~40), `fullProfile.ts` Utils (~80), Tests Unit (~150) + E2E (~100), Edit TripTabs (+15), index.ts (+2) → **~580 LoC**. Hard-Limit 250, Override 600 zur Sicherheit.

## PO-Entscheidungen (2026-05-12)

| # | Frage | Entscheidung |
|---|------|---|
| D1 | Wetter-Summary + Risiko-Pill in Step 4? | **Nein.** Aus Scope herausgelöst → Folge-Issue [#203](https://github.com/henemm/gregor_zwanzig/issues/203). Stage-Modell hat heute keine Wetter-/Risiko-Felder. |
| D2 | Layout linke Spalte | **Profil oben über Liste**, beide volle Spaltenbreite. Profil = breites SVG. |
| D3 | Sektionsstruktur | **Neue `TripOverview.svelte`** kapselt Hero + 2-Spalten-Grid; `TripTabs` rendert nur noch `<TripOverview {trip} />` im Overview-Panel. |

## Frontend-Zielplattform

Desktop-Planung von Zuhause. Side-by-Side-Layouts und breite Komponenten sind die Norm; Mobile-Responsivität ist „nice to have", nicht Treiber. Reports unterwegs gehen über E-Mail/SMS-Channels.

## Phase 2 — Analyse

### Algorithmus: Multi-Stage Full-Profile

**Datenpunkte:** Alle Waypoints aller Stages in Reihenfolge `(stages[i].waypoints[j])`. Jeder Waypoint: `lat`, `lon`, `elevation_m`.

**X-Achse — kumulative Distanz:**
- `distance(i, j) = haversineKm(prevWaypoint, currentWaypoint)` (analog `headerStats.ts`)
- Kumulative Distanz wächst stage-übergreifend monoton; Stage-Wechsel = Distanz an Stage-Boundary
- Pause-Stages (kein Datum-Übergang, nur "Ruhetag") → kein zusätzlicher Distanz-Sprung; werden gemerged mit angrenzendem Tag

**Y-Achse — Elevation:** `elevation_m` direkt; Range `[min(elevation), max(elevation)] × Padding 5 %`.

**Stage-Boundaries:**
- Pro Stage berechnen wir `xStart` und `xEnd` (kumulative km am ersten/letzten Waypoint der Stage)
- Vertikale Trennlinien an `xEnd` jeder Stage (außer letzte)
- Stage-Label (Code z.B. `T01`) zentriert unter dem Segment `(xStart + xEnd) / 2`

**Aktive-Stage-Highlight (orange Fill):**
- `deriveTripStatus(trip, now) === 'active'` + `stages.findIndex(s => s.date === today)` = `activeStageIndex`
- Rendert Rechteck `[xStart, 0] → [xEnd, height]` mit `fill: var(--g-accent)` und Opacity 0.15

**Selected-Stage-Highlight (Outline):**
- `selectedStageId` (state) → finde Stage-Index → Outline-Rechteck mit `stroke: var(--g-accent)`, `stroke-width: 2`, kein Fill
- Wenn `selectedStageId === null` und Trip ist active → automatisch aktive Stage als selected behandeln; sonst kein Outline

**Interaktion:**
- Click auf Profil-Segment (transparente `<rect>` pro Stage als Hit-Area) → `selectedStageId = stage.id`
- Click auf `StageDetailRow` → `selectedStageId = stage.id`
- Beide Wege setzen denselben State, das Highlight aktualisiert sich reaktiv (Svelte 5 `$derived`)

### Edge-Cases

| Fall | Verhalten |
|------|-----------|
| Trip ohne Stages | Profil zeigt Hinweistext „Keine Etappen geplant"; Liste zeigt Hinweis |
| Stage ohne Waypoints | Stage erscheint in der Liste mit `0 km`, im Profil als „Lücke" (kein Polyline-Segment), Label-Code trotzdem unten |
| Waypoint ohne `elevation_m` (null) | Vom Polyline-Berechnen ausschließen, Stage-Stats berücksichtigen ihn distanzmäßig nicht (analog `headerStats.ts`) |
| Nur 1 Waypoint einer Stage | Punkt + Stage-Boundary, kein Segment |
| Stage = Pause | nicht in Liste anzeigen? Doch: zeigen mit Label „Ruhetag" und 0 km/Hm |

### Stage-Code

`Stage`-Interface hat **kein** `code`-Feld. Wizard nutzt `formatStageNumber(nonPauseIndex)` → `T01`, `T02`, … Pause-Stages bekommen `P`. Wir nutzen dieselbe Logik aus `wizardHelpers.ts`.

### Datei-Plan

| Art | Datei | Zweck | LoC |
|-----|-------|-------|-----|
| NEU | `frontend/src/lib/components/trip-detail/TripOverview.svelte` | Wrapper: Hero + 2-Spalten-Grid `[2fr_1fr]`, `selectedStageId` als `$state` | ~60 |
| NEU | `frontend/src/lib/components/trip-detail/FullProfile.svelte` | SVG-Profil, Multi-Stage-Polyline, Active+Selected Highlights, Klick-Hit-Areas | ~160 |
| NEU | `frontend/src/lib/components/trip-detail/StageList.svelte` | Container für StageDetailRow + Empty-State | ~50 |
| NEU | `frontend/src/lib/components/trip-detail/StageDetailRow.svelte` | Stage-Card mit Code/Titel/Datum/km/Hm/Wpt-Count, Selected/Active-State, Klick-Handler | ~90 |
| NEU | `frontend/src/lib/utils/fullProfile.ts` | Pure-Functions: `buildProfilePoints`, `computeStageBoundaries`, `formatStageCode`, `getActiveStageId` | ~130 |
| NEU | `frontend/src/lib/utils/fullProfile.test.ts` | Unit-Tests, mind. 20 | ~180 |
| NEU | `frontend/e2e/trip-detail-overview-left.spec.ts` | E2E Klick-Interaktion + Render-Checks, mind. 10 | ~120 |
| EDIT | `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Overview-Panel: `<TripOverview {trip} />` statt direktem Hero | +2/-3 |
| EDIT | `frontend/src/lib/components/trip-detail/index.ts` | Barrel-Export 4 neuer Komponenten | +4 |
| EDIT | `frontend/e2e/global.setup.ts` (evtl.) | Test-Trip mit komplexerem Stage-Set für E2E-Stabilität — nur falls bestehendes Setup zu dünn | ~+30 |
| **Summe** | | | **~825 LoC** |

LoC-Override 850 vor Phase 6 setzen (`workflow.py set-field loc_limit_override 850`).

### Test-Strategie

**Unit (`fullProfile.test.ts`):**
- `buildProfilePoints` mit 0/1/N Stages
- Haversine-Akkumulation: 3 Waypoints, Distanzen prüfen
- `computeStageBoundaries`: xStart/xEnd pro Stage über mehrere Stages
- `formatStageCode`: T01/T02, Pause-Stage als `P`
- `getActiveStageId`: heute → active; planned → null; archived → null
- Edge: leere Stages, fehlende elevation_m, Single-Waypoint-Stage

**E2E (`trip-detail-overview-left.spec.ts`):**
- AC: Profil-SVG sichtbar, Anzahl Stage-Segmente korrekt
- AC: StageList rendert N Cards
- AC: Klick auf StageDetailRow #2 → Outline im Profil bei Segment #2
- AC: Klick auf Profil-Segment #1 → Card #1 ist als selected markiert (CSS-Klasse oder `data-selected`)
- AC: Heutige Stage (active) ist automatisch orange im Profil
- AC: Trip ohne Stages → Empty-State sichtbar, keine Crashes
- Reaktivität-Guard: Hero bleibt sichtbar, Tabs bleiben klickbar (Step 2 + 3 regressions-frei)

**Test-Daten:** `e2e-cockpit-test` Setup (3 Stages, je 1-2 Waypoints mit elevation_m) reicht für die meisten ACs. Für Profil-Algorithmus-Tests sind synthetische Trip-Objekte in Unit-Tests besser (deterministisch, keine API-Calls).

### Risiken

| # | Risiko | Mitigation |
|---|--------|-----------|
| R1 | Multi-Stage-Polyline mit Pause-Stages und fehlenden elevations wird komplex | Pure-Function `buildProfilePoints` mit 8+ Unit-Tests, deterministisch testbar |
| R2 | LoC-Limit-Sprengung | Override 850 explizit setzen; State + Computation in Pure-Functions auslagern hält Komponenten klein |
| R3 | Reaktivität: Selected-State zwischen FullProfile und StageList synchronisieren | `selectedStageId` als `$state` in `TripOverview`, beide Kinder via Props + Callback-Funktionen — Standardpattern, Vorbild Step 3 |
| R4 | Bestehende E2E-Tests (`trip-detail-hero.spec.ts`) brechen, weil TripTabs.svelte editiert wird | Hero rendert weiterhin (via TripOverview), TestIDs bleiben unverändert; Regression im Adversary-Lauf abprüfen |
| R5 | Fehlendes `Stage.code`-Feld führt zu Drift zwischen Wizard und Trip-Detail | Gemeinsamer Helper `formatStageNumber` aus `wizardHelpers.ts` nutzen; nicht neu erfinden |

### Bekannte Limitierungen (für Spec-„Known Limitations")

- Wetter-Summary + Risiko-Pill in Stage-Rows: Folge-Issue (Backend-Anbindung erforderlich)
- Touch-/Hover-Tooltip im Profil mit elevation-Wert: nicht in Scope (kann später nachgerüstet werden)
- Drag-to-Zoom oder Profil-Detail-Modus: out of scope
