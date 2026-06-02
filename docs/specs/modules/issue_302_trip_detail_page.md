---
entity_id: issue_302_trip_detail_page
type: module
created: 2026-05-22
updated: 2026-05-22
status: implemented
version: "1.0"
tags: [frontend, svelte, trip-detail, redesign, issue-302]
---

# Issue #302 — Trip-Detail-Seite: vollständiges Redesign nach Soll-Mockup

## Approval

- [ ] Approved

## Purpose

Baut die Trip-Detail-Seite `/trips/[id]` nach dem Soll-Mockup `soll-flow7B-trip-detail.png`
vollständig um: Der Header erhält Breadcrumb, große H1, Status-Zeile und drei Aktions-Buttons;
die Tab-Leiste bekommt korrekte Labels mit Badge-Zählern; der Übersicht-Tab ersetzt
Fließtext durch ein 2×2-Card-Grid mit direkten Links in die Konfigurations-Tabs; die
Danger-Zone bündelt seltene destruktive Aktionen am Seitenende.

Das Redesign zielt auf sofortige Orientierung beim Öffnen eines Trips: Der User sieht auf
einen Blick, was gerade aktiv ist (Reports, Alarmregeln, Route) und erreicht jede Aktion
mit maximal einem Klick — ohne in Tabs suchen zu müssen.

## Source

- **Files:**
  - `frontend/src/lib/components/trip-detail/TripHeader.svelte` (vollständiger Umbau)
  - `frontend/src/lib/components/trip-detail/TripTabs.svelte` (Tab-Labels + Badge-Zähler)
  - `frontend/src/lib/components/trip-detail/TripOverview.svelte` (Übersicht-Tab redesign)
  - `frontend/src/lib/components/trip-detail/DetailCard.svelte` (NEU)
  - `frontend/src/lib/utils/tripStats.ts` (NEU)
  - `frontend/src/routes/trips/[id]/+page.svelte` (Danger-Zone ergänzen)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `frontend/src/lib/utils/tripHero.ts` | Utility (vorhanden) | `getActiveStageDisplay()`, `formatDateRange()`, `getDaysLabel()` für Header-Statuszeile |
| `frontend/src/lib/utils/tripStatus.ts` | Utility (vorhanden) | `deriveTripStatus()` → 'active'\|'planned'\|'paused'\|'archived' für Header-Farbwahl |
| `frontend/src/lib/utils/rightColumn.ts` | Utility (vorhanden) | `getReportSchedule()` für Reports-Card-Inhalt |
| `frontend/src/lib/components/email-preview/headerStats.ts` | Utility (vorhanden) | `computeHeaderStats(stage)` — Haversine km + Höhenmeter je Etappe, summiert in tripStats.ts |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | Svelte-Komponente (vorhanden) | Liefert enabled Alert-Rules für Alarmregeln-Card |
| `frontend/src/lib/components/ui/Btn.svelte` | Design-System | Aktions-Buttons im Header (variant="outline"\|"accent") |
| `frontend/src/lib/components/ui/Eyebrow.svelte` | Design-System | Eyebrow-Texte in Header, Cards, Danger-Zone |
| `frontend/src/lib/components/ui/Dot.svelte` | Design-System | Status-Indikatoren in Card-Rows (on/off/warn) |
| `frontend/src/lib/api.ts` | Utility | POST `/api/scheduler/trip-reports?hour=18` für Test-Briefing |
| `frontend/src/lib/types.ts` | TypeScript | `Trip`, `Stage`, `AlertRule` — keine Änderung nötig |
| `docs/specs/modules/epic_135_step2_trip_detail_actions.md` | Spec (vorhanden) | Pause/Archivieren-Logik bleibt unverändert, wandert nur in Danger-Zone |
| `frontend/e2e/trip-detail-tabs.spec.ts` | E2E-Test | Tab-Label-Anpassungen (Zeilen 5–10) |
| `frontend/e2e/trip-detail-actions.spec.ts` | E2E-Test | Pause/Archiv-Buttons in Danger-Zone (testids identisch) |

## Scope

**Nur Frontend.** Kein Go-Backend-Endpoint geändert. Kein Python-Backend betroffen.

Nicht geändert:
- `internal/` — kein neuer API-Endpoint nötig
- `frontend/src/lib/types.ts` — Datenmodell vollständig
- Pause/Archivieren-Geschäftslogik — nur Verschiebung in Danger-Zone, testids bleiben

## Implementation Details

### 1. `tripStats.ts` (NEU)

```typescript
// frontend/src/lib/utils/tripStats.ts
import { computeHeaderStats } from '$lib/components/email-preview/headerStats';
import type { Trip } from '$lib/types';

export interface TripStats {
  stages: number;
  kmTotal: number;
  ascentM: number;
}

export function computeTripStats(trip: Trip): TripStats {
  const stages = trip.stages ?? [];
  let kmTotal = 0;
  let ascentM = 0;
  for (const stage of stages) {
    const s = computeHeaderStats(stage);
    kmTotal += s.distanceKm ?? 0;
    ascentM += s.ascentM ?? 0;
  }
  return { stages: stages.length, kmTotal, ascentM };
}
```

### 2. `DetailCard.svelte` (NEU)

Generische Karten-Komponente für das 2×2-Grid im Übersicht-Tab.

**Props:**

```typescript
export let eyebrow: string;         // z.B. "REPORTS"
export let title: string;           // z.B. "Was geht raus"
export let items: Array<{
  label: string;                    // Zeilenbeschriftung
  meta?: string;                    // rechtsbündige Zusatzinfo (z.B. "18:00 · Email+Signal")
  state?: 'on' | 'off' | 'warn';   // Dot-Farbe: on=accent/success, off=muted, warn=warning
}>;
export let actionText: string;      // z.B. "Reports anpassen →"
export let actionHref: string;      // z.B. "?tab=briefings"
```

**Template-Struktur:**

```svelte
<div class="detail-card" data-testid="detail-card-{eyebrow.toLowerCase()}">
  <Eyebrow>{eyebrow}</Eyebrow>
  <h3 class="card-title">{title}</h3>
  <ul class="card-rows">
    {#each items as item}
      <li class="card-row">
        <Dot state={item.state ?? 'on'} />
        <span class="row-label">{item.label}</span>
        {#if item.meta}
          <span class="row-meta">{item.meta}</span>
        {/if}
      </li>
    {/each}
  </ul>
  <a href={actionHref} class="card-action">{actionText}</a>
</div>
```

**Styling:** `var(--g-*)` Tokens ausschließlich. Keine Inline-Hex, keine Magic-Pixel.
Card-Hintergrund `var(--g-surface)`, Border `1px solid var(--g-ink-faint)`,
Border-Radius `var(--g-radius-md)`, Padding `var(--g-space-4)`.

### 3. `TripHeader.svelte` — vollständiger Umbau

**Layout:** Zweispaltig — Links: Breadcrumb + H1 + Statuszeile. Rechts: 3 Buttons.

**Breadcrumb:**
```svelte
<Eyebrow>MEINE TOUREN › {trip.shortcode?.toUpperCase() ?? trip.name?.toUpperCase()}</Eyebrow>
```

**H1:**
```svelte
<h1 class="trip-h1">{trip.shortcode} · {trip.name}</h1>
```
Styling: `font-size: var(--g-text-3xl)`, `font-weight: 700`, `letter-spacing: -0.025em`.

**Statuszeile:**
```svelte
<div class="trip-status-line">
  <span class="status-badge status-{deriveTripStatus(trip, now)}" data-testid="trip-status-badge">
    {statusLabel} · {getDaysLabel(trip, now)}
  </span>
  <span class="trip-meta">
    {formatDateRange(trip)} · {stats.kmTotal.toFixed(1)} km · ↑{stats.ascentM.toLocaleString()} m
  </span>
</div>
```
`statusLabel` aus `deriveTripStatus()`: 'active'→'AKTIV', 'planned'→'GEPLANT',
'paused'→'PAUSIERT', 'archived'→'ARCHIVIERT'.
Farb-Mapping: active=`var(--g-accent)`, planned=`var(--g-info)`,
paused=`var(--g-warning)`, archived=`var(--g-ink-faint)`.

**Buttons (rechts):**
```svelte
<div class="header-actions">
  <Btn variant="outline" onclick={() => goto(`?tab=preview`)}>Briefing-Vorschau</Btn>
  <Btn variant="outline" onclick={() => goto(`/trips/${trip.id}/edit`)}>Bearbeiten</Btn>
  <Btn variant="accent" data-testid="trip-detail-action-test-briefing" onclick={sendTestBriefing}>
    Test-Briefing senden
  </Btn>
</div>
```

**Test-Briefing-Handler:**
```typescript
async function sendTestBriefing() {
  await api.post('/api/scheduler/trip-reports?hour=18', {});
  // Inline-Flash: "Briefings für alle aktiven Trips ausgelöst."
}
```
Button-Tooltip/Subtext im UI: "Sendet Briefings für alle aktiven Trips."

### 4. `TripTabs.svelte` — Tab-Labels + Badges

Tab-Definitionen anpassen:

| value | Label (alt) | Label (neu) | Badge |
|---|---|---|---|
| `overview` | Übersicht | Übersicht | — |
| `stages` | Etappen | Etappen | `{trip.stages?.length ?? 0}` |
| `weather` | Wetter-Briefing | Wetter-Briefing | — |
| `briefings` | Reports & Kanäle | Reports & Kanäle | — |
| `alarms` | Alarmregeln | Alarmregeln | `{enabledAlertCount}` |
| `preview` | Vorschau | Vorschau | — |

Badge-Rendering: `{#if badge}<span class="tab-badge">{badge}</span>{/if}` im Tab-Button.
`enabledAlertCount` = `trip.alert_rules?.filter(r => r.enabled).length ?? 0`.

### 5. `TripOverview.svelte` — 2×2 Card-Grid

Ersetzt bisherigen Fließtext. Vier `DetailCard`-Instanzen in einem CSS-Grid
(`grid-template-columns: 1fr 1fr`, `gap: var(--g-space-4)`).

**Karte 1 — Reports:**
```typescript
eyebrow="REPORTS"
title="Was geht raus"
items={buildReportItems(getReportSchedule(trip))}
actionText="Reports anpassen →"
actionHref="?tab=briefings"
```
`buildReportItems()`: lokale Hilfsfunktion, die `ReportSchedule` in `items[]` mappt.
Beispiel-Rows: "Abend-Briefing · 18:00 · Email+Signal" (state='on'),
"Morgen-Update · 07:00 · Email" (state='on'),
"Warnungen · 5 Schwellen · Signal" (state='on'),
"Trend-Vorschau · deaktiviert" (state='off').

**Karte 2 — Alarmregeln:**
```typescript
eyebrow={`ALARMREGELN · ${enabledAlertCount}`}
title="Alarm-Schwellen"
items={buildAlertItems(trip.alert_rules ?? [])}
actionText="Regeln verwalten →"
actionHref="?tab=alarms"
```
`buildAlertItems()`: mappt die ersten 4 enabled Rules auf `{label, meta, state}`.
Format: label="Böen > 51 km/h", meta="Absolut · Warnung".

**Karte 3 — Route:**
```typescript
eyebrow={`${stats.stages} ETAPPEN`}
title="Route & Etappen"
items={[
  { label: 'Gesamtdistanz', meta: `${stats.kmTotal.toFixed(1)} km` },
  { label: 'Höhenmeter', meta: `↑${stats.ascentM.toLocaleString()} m` },
  { label: 'Etappen', meta: `${stats.stages}` },
]}
actionText="Etappen-Editor öffnen →"
actionHref="?tab=stages"
```

**Karte 4 — Datenstand:**
```typescript
eyebrow="LETZTER BRIEFING-LAUF"
title="Datenstand"
items={[
  { label: 'Wegpunkte', meta: `${trip.stages?.flatMap(s => s.waypoints ?? []).length ?? 0}` },
  { label: 'Datenquelle', meta: trip.data_source ?? 'Open-Meteo' },
  { label: 'Letzte Änderung', meta: formatLastUpdated(trip.updated_at) },
]}
actionText="Etappen →"
actionHref="?tab=stages"
```

### 6. Danger-Zone in `+page.svelte`

Unterhalb von `<TripTabs>` einfügen:

```svelte
<section class="danger-zone" data-testid="danger-zone">
  <Eyebrow>Selten gebraucht</Eyebrow>
  <div class="danger-zone-layout">
    <div class="danger-zone-left">
      <Btn variant="outline" disabled>Trip duplizieren</Btn>
      <Btn variant="outline" disabled>GPX neu importieren</Btn>
      <Btn variant="outline" data-testid="trip-detail-action-pause" onclick={onPause}>
        Briefings pausieren
      </Btn>
      <Btn variant="outline" data-testid="trip-detail-action-archive" onclick={onArchive}>
        {trip.status === 'archived' ? 'Dearchivieren' : trip.status === 'paused' ? 'Reaktivieren' : 'Archivieren'}
      </Btn>
    </div>
    <div class="danger-zone-right">
      <Btn variant="danger" data-testid="trip-detail-action-delete" onclick={onDelete}>
        Trip löschen
      </Btn>
    </div>
  </div>
</section>
```

Pause/Archivieren/Löschen-Handler: unverändert aus Epic #135 Step 2
(`docs/specs/modules/epic_135_step2_trip_detail_actions.md`). Nur die
Render-Position wechselt von Header-Bereich in Danger-Zone.

## Expected Behavior

- **Input:** `trip: Trip` mit optionalen Feldern `stages[]`, `alert_rules[]`, `report_config`, `updated_at`
- **Output:**
  - Header mit Breadcrumb, H1, Statuszeile, 3 Buttons — live aus Trip-Daten
  - Tab-Leiste mit korrekten Labels und Badge-Zählern (stages.length, enabled alerts)
  - Übersicht-Tab mit 4 DetailCards als 2×2 Grid
  - Danger-Zone am Seitenende mit allen seltenen Aktionen
- **Side effects:**
  - "Briefing-Vorschau"-Button navigiert zu `?tab=preview`
  - "Bearbeiten"-Button navigiert zu `/trips/{id}/edit`
  - "Test-Briefing senden": POST `/api/scheduler/trip-reports?hour=18`; Inline-Flash
  - Pause/Archivieren/Löschen: unveränderte Logik aus Epic #135

## Acceptance Criteria

**AC-1:** Given ein Trip mit `shortcode="KHW"` und `name="Karnischer Höhenweg"` ist geöffnet /
When die Detail-Seite lädt /
Then zeigt der Header-Breadcrumb "MEINE TOUREN › KHW" und die H1 "KHW · Karnischer Höhenweg" — kein alter Platzhalter-Text.

**AC-2:** Given ein Trip hat `status='active'` und `stages` mit berechneten km und Höhenmetern /
When die Detail-Seite geöffnet wird /
Then zeigt die Statuszeile "AKTIV · TAG N VON M" in Accent-Farbe sowie "km-Zahl km · ↑Höhe m" in derselben Zeile.

**AC-3:** Given ein Trip hat 5 enabled Alert-Rules /
When die Tab-Leiste gerendert wird /
Then zeigt der "Alarmregeln"-Tab ein Badge mit "5" und der "Etappen"-Tab ein Badge mit der korrekten Etappenanzahl.

**AC-4:** Given der Übersicht-Tab ist aktiv /
When die Seite gerendert wird /
Then erscheinen genau 4 DetailCards im 2×2-Grid: "REPORTS", "ALARMREGELN · N", "N ETAPPEN", "LETZTER BRIEFING-LAUF".

**AC-5:** Given die Reports-Card zeigt eine deaktivierte Option (z.B. "Trend-Vorschau") /
When der User die Karte betrachtet /
Then hat diese Zeile einen Dot im state='off' (muted-Farbe) — alle aktiven Zeilen haben state='on' (accent-Farbe).

**AC-6:** Given der User klickt "Reports anpassen →" in der Reports-Card /
When der Link aufgerufen wird /
Then wechselt die Tab-Ansicht zum "Reports & Kanäle"-Tab (`?tab=briefings`) ohne Seitenneuladen.

**AC-7:** Given der User klickt "Test-Briefing senden" im Header /
When der POST-Call an `/api/scheduler/trip-reports?hour=18` erfolgreich antwortet /
Then erscheint ein Inline-Flash "Briefings für alle aktiven Trips ausgelöst." und der Button ist während des Calls disabled.

**AC-8:** Given die Danger-Zone ist am Seitenende sichtbar /
When der User die Seite scrollt /
Then sind "Briefings pausieren" (testid: `trip-detail-action-pause`) und "Reaktivieren/Archivieren" (testid: `trip-detail-action-archive`) in der linken Spalte und "Trip löschen" (testid: `trip-detail-action-delete`) in der rechten Spalte — "Trip duplizieren" und "GPX neu importieren" sind disabled.

**AC-9:** Given ein Trip hat 13 Etappen mit Wegpunkten /
When `computeTripStats(trip)` aufgerufen wird /
Then liefert die Funktion `{ stages: 13, kmTotal: <Summe aller Etappen-km>, ascentM: <Summe aller Höhenmeter> }` ohne Abrundungsfehler.

**AC-10:** Given der User klickt "Bearbeiten" im Header /
When der Button aktiviert wird /
Then navigiert der Browser zu `/trips/{id}/edit` — kein neuer Tab, kein Seitenneuladen via Router.

## Affected Files

| Datei | Änderung |
|-------|---------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | Vollständiger Umbau: Breadcrumb, H1, Statuszeile, 3 Buttons |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab-Labels + Badge-Zähler |
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` | 2×2 DetailCard-Grid statt Fließtext |
| `frontend/src/lib/components/trip-detail/DetailCard.svelte` | NEU — generische Karten-Komponente |
| `frontend/src/lib/utils/tripStats.ts` | NEU — `computeTripStats()` summiert Haversine-km + Höhenmeter |
| `frontend/src/routes/trips/[id]/+page.svelte` | Danger-Zone unter TripTabs ergänzen |
| `frontend/e2e/trip-detail-tabs.spec.ts` | Tab-Label-Anpassungen (Zeilen 5–10) |
| `frontend/e2e/trip-detail-actions.spec.ts` | Pause/Archiv-Buttons in Danger-Zone (testids identisch) |

## LoC Estimate

~220 LoC gesamt: TripHeader ~60, TripOverview ~70, DetailCard ~40, tripStats.ts ~20,
TripTabs ~15, +page.svelte ~25. E2E-Tests ~10 LoC Anpassungen.

## Known Limitations

- "Trip duplizieren" und "GPX neu importieren" sind in dieser Iteration disabled (noch nicht implementiert). Sie erscheinen als deaktivierte Buttons in der Danger-Zone, damit die Danger-Zone vollständig ist und User wissen, wo sie künftig landen.
- Test-Briefing löst Briefings für **alle** aktiven Trips aus, nicht nur den aktuell angezeigten. Dieser Scope ist eine Backend-Limitierung. Das UI kommuniziert dies explizit im Button-Subtext.
- `computeTripStats()` greift auf `computeHeaderStats(stage)` zurück, das intern Haversine über `stage.waypoints[]` berechnet. Fehlen Waypoints, ist die Distanz 0 — das ist korrekt für leere Etappen.

## Changelog

- 2026-05-22: Implementierung abgeschlossen. DetailCard-Komponente, tripStats-Utility, TripHeader/TripTabs/TripOverview redesigned, Danger-Zone integriert. E2E-Tests angepasst.
- 2026-05-22: Initial spec erstellt (Issue #302 — Trip-Detail-Seite vollständiges Redesign).
