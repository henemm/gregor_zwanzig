---
entity_id: issue_416_mobile_trip_kennzahlen
type: module
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
tags: [frontend, svelte, mobile, metrics, trip-detail, kennzahlen, issue-416]
---

# Issue #416 — Mobile Trip-Kennzahlen-Kacheln im Trip-Detail-Header

## Approval

- [ ] Approved

## Purpose

Ergänzt den Trip-Detail-Header um drei mobile-exklusive Kennzahlen-Kacheln (ETAPPE, BRIEFING,
START IN / TAG), die unterhalb des Status-Badges auf Viewports ≤ 899px erscheinen und dem User
sofortige Orientierung geben, ohne in Sub-Tabs navigieren zu müssen.

Die Kacheln sind nötig, weil der Desktop-Header seine Orientierungsfunktion über drei Aktions-Buttons
und die Statuszeile mit km/Höhenmeterdaten erfüllt — auf Mobile ist diese Information unsichtbar
(Buttons kollabieren, Statuszeile ist zu schmal), sodass ein Blick auf Etappenstand, Briefing-Zeit
und Abreisecountdown fehlt.

## Source

- **Files:**
  - `frontend/src/lib/components/trip-detail/TripHeader.svelte` (PRIMARY: Kacheln, Logik, CSS, ~40 LoC Änderung)
  - `frontend/src/routes/trips/[id]/+page.svelte` (MINOR: `{now}`-Prop an TripHeader, ~1 LoC)
  - `frontend/src/lib/components/trip-detail/TripHeader.mobile-metrics.test.ts` (NEU: ~35 LoC Source-Inspection-Tests)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `frontend/src/lib/components/molecules/Stat.svelte` | Svelte-Komponente (vorhanden) | Kachel-Display (Label + Wert); bereits in `TripOverview.svelte` eingesetzt |
| `frontend/src/lib/utils/tripStatus.ts` → `deriveTripStatus`, `todayStageIndex` | TypeScript-Utility (vorhanden) | Trip-Status ('active'\|'planned'\|'paused'\|'archived') + heutiger Etappen-Index für ETAPPE- und TAG-Kachel |
| `frontend/src/lib/utils/rightColumn.ts` → `getReportSchedule` | TypeScript-Utility (vorhanden) | Schedule-Objekt mit `morning_enabled`, `morning`, `evening_enabled`, `evening` für BRIEFING-Kachel |
| `frontend/src/lib/utils/tripHero.ts` | TypeScript-Utility (vorhanden) | `sortedStageDates` ist intern (nicht exportiert) — Tage-bis-Start werden inline aus `trip.stages` berechnet |
| `frontend/src/lib/utils/tripStats.ts` → `computeTripStats` | TypeScript-Utility (vorhanden) | Bereits importiert in TripHeader; kein neuer Import nötig |

## Scope

**Nur Frontend.** Kein Go-Backend-Endpoint geändert. Kein Python-Backend betroffen.

Nicht geändert:
- `internal/` — kein neuer API-Endpoint nötig
- `frontend/src/lib/types.ts` — Datenmodell vollständig
- `frontend/src/lib/utils/tripStats.ts` — wird weiterverwendet, nicht verändert
- Desktop-Layout von TripHeader — Kacheln sind via `display: none` auf ≥ 900px unsichtbar

## Implementation Details

### 1. Kachel-Logik (inline in `TripHeader.svelte`)

Die gesamte Logik (~15 LoC) lebt direkt in TripHeader — keine neue Utility-Datei, da nur
ein Abnehmer existiert.

**Abhängigkeiten aus vorhandenen Utilities:**

```typescript
import { deriveTripStatus, todayStageIndex } from '$lib/utils/tripStatus';
import { getReportSchedule } from '$lib/utils/rightColumn';
import Stat from '$lib/components/molecules/Stat.svelte';
// Hinweis: sortedStageDates ist in tripHero.ts intern (nicht exportiert).
// Tage-bis-Start werden direkt aus trip.stages berechnet.

// now wird als Prop von +page.svelte übergeben
export let now: Date = new Date();
```

**Kachel 1 — ETAPPE ("X/Y")**

```typescript
const etappeValue = $derived((() => {
  const total = trip.stages?.length ?? 0;
  const status = deriveTripStatus(trip, now);
  if (status === 'planned' || status === 'paused') return `—/${total}`;
  if (status === 'active') {
    const idx = todayStageIndex(trip, now);
    return `${idx + 1}/${total}`;
  }
  // archived
  return `${total}/${total}`;
})());
```

**Kachel 2 — BRIEFING ("HH:MM" oder "—")**

```typescript
const briefingValue = $derived((() => {
  const sched = getReportSchedule(trip);
  if (!sched.enabled) return '—';
  if (sched.morning_enabled && sched.morning) return sched.morning.slice(0, 5);
  if (sched.evening_enabled && sched.evening) return sched.evening.slice(0, 5);
  return '—';
})());
```

**Kachel 3 — START IN / TAG / STATUS (dynamisches Label)**

```typescript
const startLabel = $derived((() => {
  const status = deriveTripStatus(trip, now);
  if (status === 'planned') return 'START IN';
  if (status === 'active') return 'TAG';
  return 'STATUS';
})());

const startValue = $derived((() => {
  const status = deriveTripStatus(trip, now);
  if (status === 'planned') {
    const dates = (trip.stages ?? []).map(s => s.date).filter(Boolean).sort() as string[];
    if (!dates.length) return '—';
    const firstDay = new Date(dates[0] + 'T00:00:00');
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const diff = Math.ceil((firstDay.getTime() - today.getTime()) / 86_400_000);
    return diff > 0 ? `${diff} Tg` : '—';
  }
  if (status === 'active') {
    const idx = todayStageIndex(trip, now);
    return `Tag ${idx + 1}`;
  }
  return '—';
})());
```

### 2. Template-Erweiterung in `TripHeader.svelte`

Kacheln werden nach dem Status-Badge als separate Row eingefügt:

```svelte
<div class="mobile-metrics" data-testid="trip-header-mobile-metrics">
  <Stat label="ETAPPE" value={etappeValue} data-testid="metric-etappe" />
  <Stat label="BRIEFING" value={briefingValue} data-testid="metric-briefing" />
  <Stat label={startLabel} value={startValue} data-testid="metric-start" />
</div>
```

### 3. CSS-Breakpoint

```css
.mobile-metrics {
  display: none;
}

@media (max-width: 899px) {
  .mobile-metrics {
    display: flex;
    gap: var(--g-s-3);
    padding-top: var(--g-s-2);
  }
}
```

Konsistent mit dem rest der Codebase (`@media (max-width: 899px)`, gleicher Breakpoint
wie in `WeatherMetricsMobileView.svelte`, `MSwitch.svelte` etc.).
Alle Spacing-Werte via `--g-s-*` Tokens, keine Magic-Pixel-Werte.

### 4. Prop-Ergänzung in `+page.svelte` (~1 LoC)

```svelte
<TripHeader {trip} {now} />
```

`now` existiert bereits als reaktive Variable in `+page.svelte` (wird an `deriveTripStatus`
für die Statuszeile genutzt). Die Prop wird nur durchgereicht.

### 5. Source-Inspection-Test `TripHeader.mobile-metrics.test.ts`

Pattern: Liest `.svelte`-Datei als String, prüft Vorkommen von Schlüssel-Patterns.
Analog zu `TripHeader.spacing.test.ts` im selben Verzeichnis.

Geprüfte Assertions:
- `data-testid="trip-header-mobile-metrics"` vorhanden
- `data-testid="metric-etappe"` vorhanden
- `data-testid="metric-briefing"` vorhanden
- `data-testid="metric-start"` vorhanden
- `@media (max-width: 899px)` im CSS-Block vorhanden
- `display: none` für `.mobile-metrics` vorhanden (Desktop-Versteckung)
- `getReportSchedule` importiert
- `sortedStageDates` importiert
- `todayStageIndex` importiert
- `deriveTripStatus` importiert

## Expected Behavior

- **Input:** `trip: Trip` (mit optionalen `stages[]`, `report_config`, `schedule`) + `now: Date`
- **Output:**
  - Auf Viewport ≤ 899px: drei `Stat`-Kacheln (ETAPPE, BRIEFING, START IN/TAG/STATUS) unterhalb
    des Status-Badges als horizontale Flex-Row
  - Auf Viewport ≥ 900px: `.mobile-metrics` via `display: none` vollständig versteckt
- **Side effects:** keine (rein display-logisch, keine API-Calls, keine State-Mutationen)

## Acceptance Criteria

**AC-1:** Given ein aktiver Trip mit 5 Etappen und heute ist Etappe 2 /
When der Trip-Detail-Header auf einem Mobile-Viewport (≤ 899px) gerendert wird /
Then zeigt die ETAPPE-Kachel den Wert "2/5" mit `data-testid="metric-etappe"`.
  - Test: (populated after /tdd-red)

**AC-2:** Given ein Trip mit `schedule.enabled = true`, `morning_enabled = true`, `morning = "06:00"` /
When der Trip-Detail-Header auf Mobile gerendert wird /
Then zeigt die BRIEFING-Kachel "06:00"; bei `schedule.enabled = false` zeigt sie "—".
  - Test: (populated after /tdd-red)

**AC-3:** Given ein geplanter Trip, dessen erster Stage-Termin in 3 Tagen liegt /
When der Trip-Detail-Header auf Mobile gerendert wird /
Then zeigt die dritte Kachel Label "START IN" mit Wert "3 Tg"; bei einem aktiven Trip auf Tag 2 zeigt sie Label "TAG" mit Wert "Tag 2".
  - Test: (populated after /tdd-red)

**AC-4:** Given der Trip-Detail-Header wird auf Desktop (≥ 900px) gerendert /
When die Seite geladen wird /
Then ist das Element `[data-testid="trip-header-mobile-metrics"]` via `display: none` in CSS unsichtbar und beeinflusst das Desktop-Layout nicht.
  - Test: (populated after /tdd-red)

**AC-5:** Given die Komponente `TripHeader.svelte` ist implementiert /
When der Source-Inspection-Test ausgeführt wird /
Then sind alle fünf `data-testid`-Attribute (`trip-header-mobile-metrics`, `metric-etappe`, `metric-briefing`, `metric-start`) und der `@media (max-width: 899px)`-Block im Quelltext vorhanden.
  - Test: (populated after /tdd-red)

## Affected Files

| Datei | Änderung |
|-------|---------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | PRIMARY — Kachel-Template, $derived-Logik, CSS-Breakpoint, Import von `getReportSchedule`/`sortedStageDates`/`todayStageIndex`/`Stat` (~40 LoC) |
| `frontend/src/routes/trips/[id]/+page.svelte` | MINOR — `{now}`-Prop an TripHeader übergeben (~1 LoC) |
| `frontend/src/lib/components/trip-detail/TripHeader.mobile-metrics.test.ts` | NEU — Source-Inspection-Tests (~35 LoC) |

Nicht geändert (nur wiederverwendet):
- `frontend/src/lib/components/molecules/Stat.svelte`
- `frontend/src/lib/utils/tripStatus.ts`
- `frontend/src/lib/utils/rightColumn.ts`
- `frontend/src/lib/utils/tripHero.ts`
- `frontend/src/lib/utils/tripStats.ts`

## LoC Estimate

~76 LoC gesamt: TripHeader.svelte ~40, +page.svelte ~1, Test ~35.

## Known Limitations

- `sortedStageDates` liefert ISO-Date-Strings; die Tage-bis-Start-Berechnung verwendet
  `Math.ceil` mit UTC-Millisekunden — bei Ortszeit-Abweichungen kann der Wert um ±1 Tag
  abweichen. Für eine Orientierungskachel ist diese Toleranz akzeptabel.
- Bei einem pausiertem Trip ist die dritte Kachel `STATUS / —`, weil ein eindeutiger
  Countdown nicht darstellbar ist (der Trip hat kein neues Start-Datum). Das ist bewusst.
- ETAPPE zeigt bei 'archived' immer `Y/Y`, auch wenn tatsächlich nicht alle Etappen absolviert
  wurden — es gibt kein Completion-Tracking auf Stage-Ebene.

## Changelog

- 2026-05-29: Initial spec erstellt (Issue #416 — Mobile Trip-Kennzahlen-Kacheln).
