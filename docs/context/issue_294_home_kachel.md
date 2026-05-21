# Context: Issue #294 — Home-Seite: Cockpit → Kachel-Übersicht

## Request Summary

Die Home-Seite (`/`) zeigt aktuell ein operatives Trip-Cockpit (ActiveTripCard, StageStrip, BriefingsTimeline, AlertFeed). Das widerspricht dem Produkt-Konzept: Das Frontend ist ein Vorbereitungs-Tool, kein Live-Tracking. Ziel ist ein Kachel-Layout (Trips + Orts-Vergleiche) analog der genehmigten UX-Spec.

## Betroffene Dateien

| Datei | Was ändert sich |
|-------|-----------------|
| `frontend/src/routes/+page.svelte` | Komplett ersetzen — kein Cockpit, stattdessen Kachel-Grid |
| `frontend/src/routes/+page.server.ts` | `forecastCoords` raus, `subscriptions` (für CompareKacheln) rein |
| `frontend/src/routes/_cockpit/` | Alle 6 Komponenten löschen oder in Trip-Detail verschieben |
| `frontend/src/routes/_home/TripKachel.svelte` | Neu erstellen |
| `frontend/src/routes/_home/CompareKachel.svelte` | Neu erstellen |
| `frontend/src/routes/_home/EmptyKachel.svelte` | Neu erstellen |

## _cockpit-Komponenten (Schicksal)

| Komponente | Wohin |
|------------|-------|
| `ActiveTripCard.svelte` | Ggf. nach `/trips/[id]`-Detail verschieben (ist in Issue #294 optional) |
| `StageStrip.svelte` + `StagePill.svelte` | Bereits auf Trip-Detail-Seite. Bug #281/#290 hat das bereits gepatcht. Prüfen ob Import dort existiert |
| `BriefingsTimeline.svelte` | Löschen (war Platzhalter) |
| `AlertFeed.svelte` | Löschen (war Platzhalter) |
| `BottomRow.svelte` | Löschen |

## Datenquellen für die neue Home-Page

| Daten | API-Endpoint | Bereits in server.ts? |
|-------|-------------|----------------------|
| Trips | `GET /api/trips` | ✅ Ja |
| Subscriptions (CompareKacheln) | `GET /api/subscriptions` | ❌ Nein, muss rein |
| Scheduler-Status | `GET /api/scheduler/status` | ✅ Ja (kann bleiben oder raus) |
| forecastCoords | — | ❌ Raus |

## Typen

- `Trip` aus `$lib/types.ts` — hat `stages[]`, `name`, `id`, `archived_at`, `paused_at`
- `Subscription` aus `$lib/types.ts` — hat `name`, `id`, `schedule`, `enabled`, `last_run`, `last_status`

## TripStatus-Logik

```ts
function tripStatus(trip: Trip): 'aktiv' | 'geplant' | 'fertig' | 'draft' {
  const dates = trip.stages?.map(s => s.date).filter(Boolean).sort() ?? [];
  if (!dates.length) return 'draft';
  if (dates[dates.length-1] < today) return 'fertig';
  if (dates[0] <= today) return 'aktiv';
  return 'geplant';
}
```

## Datum-Range-Logik für TripKachel

```ts
function computeRange(trip: Trip): string {
  const dates = trip.stages?.map(s => s.date).filter(Boolean).sort() ?? [];
  if (!dates.length) return '–';
  const fmt = (d: string) => new Date(d).toLocaleDateString('de-DE', { day: 'numeric', month: 'short' });
  return dates.length === 1 ? fmt(dates[0]) : `${fmt(dates[0])} – ${fmt(dates[dates.length-1])}`;
}
```

## Design-System Tokens (aus docs/reference/design_system.md)

- Card-Surface: `--g-surface-1` (`#edeae1`)
- Border: `--g-ink-faint`
- Radius: `--g-radius-lg`
- Primärtext: `--g-ink`
- Sekundärtext: `--g-ink-muted`
- Tertiär: `--g-ink-faint`
- Akzent: `--g-accent` (`#c45a2a`)
- Erfolg: `--g-success` (`#3a7d44`)
- Data-Font: `--g-font-data` (JetBrains Mono)

## Bestehende UI-Komponenten

- `Btn` aus `$lib/components/ui/btn` — unterstützt `href`, `variant="primary"|"outline"|"accent"`, `size="lg"|"sm"`
- `Eyebrow` aus `$lib/components/ui/eyebrow`
- `GCard` aus `$lib/components/ui/g-card` — generische Card-Wrapper, kein eigenes Styling
- `TopoBg` aus `$lib/components/ui/topo` — Topo-Hintergrundgrafik

## CompareKachel — Datenmapping

| Feld | Quelle in Subscription |
|------|----------------------|
| Name | `subscription.name` |
| Schedule | `subscription.schedule` (`daily_morning` → `täglich 07:00`, `daily_evening` → `täglich 18:00`, `weekly` → `wöchentlich`) |
| Letzter Lauf | `subscription.last_run` + `subscription.last_status` |
| Aktiv | `subscription.enabled` |

## Bestehende Muster

- Server-Load-Pattern: `frontend/src/routes/compare/+page.server.ts` — zeigt wie Subscriptions geladen werden
- Kachel-ähnliches Muster: `frontend/src/routes/trips/+page.svelte` — Card-Stack (Issue #268)

## Spec-Referenz

- `docs/specs/ux_redesign_navigation.md §1 "Startseite"` — genehmigtes Layout
- Issue #294 enthält vollständigen Svelte-Pseudo-Code als Vorlage

## Risiken & Überlegungen

1. **StageStrip-Import-Dopplung**: StageStrip/StagePill wurden durch Bug #281/#290 gepatcht. Prüfen ob sie in `/trips/[id]` bereits importiert sind (dann _cockpit löschen = kein Verlust).
2. **Test-Briefing-Button**: Wandert laut Issue auf Trip-Detail-Seite, aber der Issue sagt das ist ein separates Issue (#07-detail). Für #294 nur entfernen.
3. **Mobile-Grid**: 1-spaltig `< sm`, 2-spaltig `sm`, 3-spaltig `lg` — per CSS Grid, kein Tailwind-Breakpoint-Overload.
4. **activeTrip-Logik entfernt**: Keine `$derived`-Chains mehr für activeTrip/todayStage — deutlich weniger JS im Bundle.
5. **forecastCoords-Removal**: Der Forecast-API-Call entfällt komplett. Kein `$effect` mehr.
