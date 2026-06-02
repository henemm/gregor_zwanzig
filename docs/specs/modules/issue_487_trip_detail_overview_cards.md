---
entity_id: issue_487_trip_detail_overview_cards
type: module
created: 2026-05-31
updated: 2026-05-31
status: implemented
version: "1.0"
tags: [frontend, svelte, trip-detail, overview, design-compliance, issue-487]
---

# Issue #487 — TripOverview: 4-Karten-2×2-Dashboard (Design-Compliance)

## Approval

- [x] Approved

## Purpose

Design-Compliance-Änderung: Der Übersicht-Tab (`TripOverview.svelte`) zeigt aktuell
ein zweispaltiges Layout mit Höhenprofil, Etappen-Liste und rechten Preview-Karten
(implementiert in Issue #409). Das aktuelle Soll-Mockup (`soll-flow7B-trip-detail.png`,
handoff `stable_id=trip-detail-page`) sieht stattdessen ein 2×2-Grid aus 4 `DetailCard`-
Komponenten vor — einen kompakten Dashboard-Überblick, der in die vertiefenden Tabs
weiterleitet.

### Was sich ändert

`TripOverview.svelte` wird auf das 4-Karten-Grid umgestellt. Die bisher dort eingebundenen
Komponenten `FullProfile`, `StageList`, `BriefingPreviewCard`, `WeatherMetricsPreviewCard`,
`AlertsPreviewCard` und `PreviewCard` werden aus dem Übersicht-Tab entfernt. Die Komponenten
selbst bleiben im Codebase erhalten.

Alle anderen Teile der Trip-Detail-Seite (TripHeader, TripTabs, Danger Zone) sind bereits
korrekt implementiert und werden **nicht** geändert.

## Source

- **Files:**
  - `frontend/src/lib/components/trip-detail/TripOverview.svelte` — Komplett-Neubau (~100 LoC)

Kein Go-Backend, kein Python-Backend betroffen. Keine neuen Komponenten nötig — `DetailCard.svelte` existiert bereits.

## Scope

**Nur Frontend, eine Datei.**

Nicht geändert:
- `TripHeader.svelte` — bleibt wie durch Issue #302 implementiert
- `TripTabs.svelte` — bleibt wie durch Issue #302 implementiert
- `+page.svelte` — bleibt wie durch Issue #302 implementiert (inkl. Danger Zone)
- `DetailCard.svelte` — bereits vorhanden, keine Änderung nötig
- `FullProfile.svelte`, `StageList.svelte`, `BriefingPreviewCard.svelte` etc. — bleiben im Codebase, werden nur nicht mehr von TripOverview eingebunden

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `frontend/src/lib/components/trip-detail/DetailCard.svelte` | Svelte-Komponente (vorhanden) | Props: `{ eyebrow, title, items, actionText, actionHref, testid }` |
| `frontend/src/lib/utils/rightColumn.ts` | Utility (vorhanden) | `getReportSchedule(trip)` → Briefing-Zeiten + Kanal-Flags |
| `frontend/src/lib/utils/tripStats.ts` | Utility (vorhanden) | `computeTripStats(trip)` → `{ stages, kmTotal, ascentM }` |
| `frontend/src/lib/utils/tripStatus.ts` | Utility (vorhanden) | `deriveTripStatus(trip, now)` — für Stage-Progress |
| `frontend/src/lib/types.ts` | TypeScript | `Trip`, `AlertRule` |

## Implementation Details

### TripOverview.svelte — Neubau

**Props:** `{ trip: Trip, now?: Date }`

**Layout:** 2×2-Grid aus 4 `DetailCard`-Instanzen.

```svelte
<section data-testid="trip-overview" class="trip-overview">
  <div class="overview-grid">
    <DetailCard eyebrow="Reports" title="Was geht raus" … testid="card-reports" />
    <DetailCard eyebrow="Alarmregeln · N" title="Alarm-Schwellen" … testid="card-alerts" />
    <DetailCard eyebrow="N Etappen" title="Route & Etappen" … testid="card-stages" />
    <DetailCard eyebrow="Briefings" title="Datenstand" … testid="card-schedule" />
  </div>
</section>
```

CSS: `grid-template-columns: 1fr 1fr` (Desktop), `1fr` (≤ 899px).

### Karte 1 — „Was geht raus" (Reports)

**Eyebrow:** `"Reports"`
**Title:** `"Was geht raus"`
**testid:** `"card-reports"`
**actionText:** `"Reports & Kanäle"`
**actionHref:** `"#briefings"`

**Items** (abgeleitet aus `getReportSchedule(trip)`):

| label | meta | state |
|-------|------|-------|
| `"Abend-Briefing"` | `"täglich " + evening + " Uhr"` falls `evening_enabled` | `'on'` / `'off'` |
| `"Morgen-Update"` | `"täglich " + morning + " Uhr"` falls `morning_enabled` | `'on'` / `'off'` |
| `"Alerts bei Änderungen"` | `"aktiv"` / `"deaktiviert"` | `'on'` / `'off'` |

Falls `schedule.enabled === false`: alle Items mit `state: 'off'`, meta `"deaktiviert"`.

### Karte 2 — „Alarm-Schwellen" (Alert Rules)

**Eyebrow:** `N + " Alarmregeln"` (N = Anzahl enabled rules, min 0)
**Title:** `"Alarm-Schwellen"`
**testid:** `"card-alerts"`
**actionText:** `"Alarmregeln verwalten"`
**actionHref:** `"#alerts"`

**Items** (aus `(trip.alert_rules ?? []).filter(r => r.enabled).slice(0, 4)`):
- Falls leer: 1 Item `{ label: "Noch keine Regeln", state: 'off' }`
- Sonst: Jede Regel → `{ label: rule.metric, meta: String(rule.threshold), state: 'on' }`
  - Label: nutzt `normalizeAlertMetric` + `ALERT_METRIC_LABELS` aus `$lib/utils/alertMetricLabels`
  - Bei thunder_level: `{ label: "Gewitter", meta: thunderLevelLabel(threshold), state: 'on' }`

### Karte 3 — „Route & Etappen"

**Eyebrow:** `stats.stages + " Etappen"`
**Title:** `"Route & Etappen"`
**testid:** `"card-stages"`
**actionText:** `"Etappen öffnen"`
**actionHref:** `"#stages"`

**Items:**
| label | meta | state |
|-------|------|-------|
| `"Distanz"` | `stats.kmTotal.toFixed(1) + " km"` | `'on'` |
| `"Aufstieg"` | `Math.round(stats.ascentM).toLocaleString("de-DE") + " m"` | `'on'` |
| `"Etappen"` | `stats.stages + " geplant"` | `'on'` |

Falls `stages.length === 0`: alle Items `state: 'off'`, meta `"—"`.

### Karte 4 — „Datenstand"

**Eyebrow:** `"Briefings"`
**Title:** `"Datenstand"`
**testid:** `"card-schedule"`
**actionText:** `"Briefing-Vorschau"`
**actionHref:** `"#preview"`

**Items** (aus `getReportSchedule(trip)`):
| label | meta | state |
|-------|------|-------|
| `"Nächstes Briefing"` | früheste aktivierte Zeit (`morning` oder `evening`, falls vorhanden, sonst `"—"`) | `schedule.enabled ? 'on' : 'off'` |
| `"Zeitplan"` | `schedule.morning_enabled && schedule.evening_enabled ? "2× täglich" : schedule.morning_enabled ? "Morgens" : schedule.evening_enabled ? "Abends" : "inaktiv"` | entsprechend |
| `"Warnungen"` | enabled alert count + `" Regeln aktiv"` | `alertCount > 0 ? 'on' : 'off'` |

## Acceptance Criteria

**AC-1:** Given a Trip mit aktiven Report-Zeiten, When `/trips/[id]` geladen wird (Übersicht-Tab), Then zeigt `[data-testid="trip-overview"]` genau 4 `[data-testid^="detail-card-"]` Elemente im 2×2-Grid.

**AC-2:** Given eine Karte „Was geht raus", When evening_enabled=true und morning_enabled=false, Then zeigt `[data-testid="detail-card-card-reports"]` das Evening-Item mit state='on' und das Morning-Item mit state='off'.

**AC-3:** Given Karte „Alarm-Schwellen" mit 3 aktiven Regeln, When der Tab geladen wird, Then zeigt `[data-testid="detail-card-card-alerts"]` genau 3 Zeilen mit state='on'.

**AC-4:** Given Karte „Route & Etappen" mit 5 Stages, When der Tab geladen wird, Then zeigt `[data-testid="detail-card-card-stages"]` Distanz, Aufstieg und Etappenanzahl.

**AC-5:** Given alle 4 Karten, When ein Action-Link geklickt wird, Then navigiert der Link zum entsprechenden Tab-Hash (`#briefings`, `#alerts`, `#stages`, `#preview`).

**AC-6:** Given Trip ohne Stages und ohne Report-Config, When der Tab geladen wird, Then zeigen alle 4 Karten sinnvolle Fallback-Werte (keine undefined, keine Leerstrings, kein Crash).

## Tests

Tests werden als `node:test`-Einheitstests in `frontend/src/lib/components/trip-detail/TripOverview.test.ts` geschrieben (kein Mock!):

- AC-1: 4 Karten vorhanden
- AC-2: Evening/Morning-State korrekt
- AC-3: Alerts-Zeilen-Anzahl
- AC-4: Stage-Statistiken
- AC-6: Fallback bei leerem Trip

Für AC-5 (Navigation) genügt ein Attribute-Check auf `href`.
