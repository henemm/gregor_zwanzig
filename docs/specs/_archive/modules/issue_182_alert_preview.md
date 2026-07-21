---
entity_id: issue_182_alert_preview
type: module
created: 2026-05-19
updated: 2026-05-19
status: draft
version: "1.0"
tags: [frontend, alerts, svelte, epic-139, issue-182, preview, iframe]
parent: epic-139-alert-konfigurator
---

# Issue #182 — Alert-Konfigurator: Alert-Vorschau (E-Mail)

## Approval

- [ ] Approved

## Purpose

Fügt am Ende des Alerts-Tabs eine "Alert-Vorschau"-Karte hinzu, die dem User zeigt, wie eine Alert-E-Mail mit seinen aktuellen Schwellwert-Einstellungen tatsächlich aussehen würde. Die Karte generiert synthetische Wetterdaten aus den aktiven Alert-Regeln, ruft `POST /api/trips/{id}/alert-preview` auf und rendert das zurückgegebene HTML in einem sandgeboxten iframe — ohne eine echte E-Mail zu senden.

## Source

- **Files:**
  - `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` (NEU)
  - `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` (ÄNDERN: Import + Tag einfügen)

> Beide Dateien liegen im Frontend (SvelteKit). Der Backend-Endpoint `POST /api/trips/{id}/alert-preview` existiert bereits (Python FastAPI via Go-Proxy, Issue #221) — kein Backend-Change in diesem Issue.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/api.ts` | Utility | `api.post()` für den HTTP-Call zu `POST /api/trips/{id}/alert-preview` |
| `frontend/src/lib/types.ts` | Types | `Trip`, `AlertRule`, `AlertMetric` |
| `frontend/src/lib/utils/alertMetricLabels.ts` | Utility | `ALERT_METRIC_LABELS` — Python-Feldnamen + Einheiten pro Metric |
| `POST /api/trips/{id}/alert-preview` | Backend-Endpoint | Go-Proxy → Python FastAPI; Payload: `{changes, segment_times}`; Response: `{html, plain}` |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | Parent Component | Empfängt `trip` und `alertRules` als Props, rendert `<AlertPreviewCard>` nach der `cards-row` |

## Affected Files

| Datei | Änderung |
|-------|---------|
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` | NEU |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | `<AlertPreviewCard>` nach `</div>` der `cards-row` einfügen, vor `<div class="actions">` |

## Expected Behavior

- **Input:** `trip: Trip` (für `trip.id` und `trip.stages[0]?.id`) und `alertRules: AlertRule[]` (lokaler State aus AlertsTab, vor dem Speichern aktuell)
- **Output:** iframe mit gerendertem Alert-E-Mail-HTML; bei leerem `enabledRules`-Array: Empty-State-Text statt Button
- **Side effects:** `POST /api/trips/{id}/alert-preview` wird beim Klick auf "Vorschau laden" aufgerufen; kein Speichern, kein Versand

## Data Model

### Interner State von AlertPreviewCard

```typescript
let html: string = $state('');
let loading: boolean = $state(false);
let error: string | null = $state(null);
```

### Synthetische Change-Generierung (vor dem API-Call)

Für jede aktivierte AlertRule in `alertRules` (d.h. `rule.enabled === true`):

```typescript
// Metric-Name-Mapping: TypeScript AlertMetric → Python-Feldname + direction
const METRIC_MAP: Record<AlertMetric, { metric: string; direction: string }> = {
  wind_gust:            { metric: 'gust_max_kmh',      direction: 'above' },
  precipitation_sum:    { metric: 'precip_sum_mm',     direction: 'above' },
  temperature_min:      { metric: 'temp_min_c',        direction: 'below' },
  temperature_max:      { metric: 'temp_max_c',        direction: 'above' },
  thunder_level:        { metric: 'thunder_level_max', direction: 'above' },
  snow_line:            { metric: 'freezing_level_m',  direction: 'above' },
  temperature_change:   { metric: 'temp_min_c',        direction: 'increase' },
  wind_change:          { metric: 'wind_max_kmh',      direction: 'increase' },
  precipitation_change: { metric: 'precip_sum_mm',     direction: 'increase' },
};

// Severity-Mapping: AlertSeverity → ChangeSeverity
const SEVERITY_MAP = { info: 'minor', warning: 'moderate', critical: 'major' };

// Werte-Generierung
const newValue = rule.threshold * 1.2;
const oldValue = (rule.kind === 'delta') ? 0 : rule.threshold * 0.8;
const delta = newValue - oldValue;
const segmentId = trip.stages[0]?.id ?? '1';

// ChangePayload-Eintrag
{
  metric: METRIC_MAP[rule.metric].metric,
  old_value: oldValue,
  new_value: newValue,
  delta: delta,
  threshold: rule.threshold,
  severity: SEVERITY_MAP[rule.severity],
  direction: METRIC_MAP[rule.metric].direction,
  segment_id: segmentId,
}
```

`segment_times`: ein einzelner Eintrag `[{ segment_id: segmentId, start: '08:00', end: '17:00' }]`.

### API-Payload

```typescript
{
  changes: ChangePayload[],      // eine Eintrag pro aktivierter Regel
  segment_times: [{ segment_id: string, start: '08:00', end: '17:00' }]
}
```

Response: `{ html: string, plain: string }` — nur `html` wird verwendet.

## Components

### AlertPreviewCard.svelte

**Props:**
```typescript
interface Props {
  trip: Trip;
  alertRules: AlertRule[];
}
```

**Computed:**
```typescript
const enabledRules = $derived(alertRules.filter(r => r.enabled));
```

**Rendering-Regeln:**

1. `enabledRules.length === 0` → Card-Body zeigt nur Empty-State:
   `"Aktiviere mindestens eine Alert-Regel, um die Vorschau zu laden."`
   Button "Vorschau laden" ist disabled oder ausgeblendet.

2. `enabledRules.length > 0` und `html === ''` (noch kein Aufruf) → Button "Vorschau laden" aktiv, kein iframe.

3. `loading === true` → Button zeigt "Lade…" (disabled), kein iframe.

4. `error !== null` → Inline-Fehlermeldung unterhalb des Buttons (kein iframe).

5. `html !== ''` → iframe mit `srcdoc={html}`, `sandbox="allow-same-origin"`, min-height: 350px, width: 100%.

**Layout:**
```
┌─────────────────────────────────────────┐
│ Alert-Vorschau                          │  ← Card-Header
├─────────────────────────────────────────┤
│ [Vorschau laden]                        │  ← Button (oder Empty-State-Text)
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │         iframe (srcdoc=html)        │ │  ← nur wenn html !== ''
│ └─────────────────────────────────────┘ │
│ <Fehlermeldung>                         │  ← nur wenn error !== null
└─────────────────────────────────────────┘
```

**data-testids:**
- `data-testid="alert-preview-card"` — äußerer Container
- `data-testid="alert-preview-load-btn"` — Button "Vorschau laden"
- `data-testid="alert-preview-iframe"` — iframe
- `data-testid="alert-preview-empty"` — Empty-State-Text
- `data-testid="alert-preview-error"` — Fehlermeldung

### AlertsTab.svelte — Änderung

Bestehende Struktur nach der Änderung:
```svelte
<div class="alerts-tab" data-testid="alerts-tab">
  <AlertMetricTable bind:alert_rules={alertRules} />

  <div class="cards-row">
    <AlertCooldownCard bind:cooldown_minutes={cooldownMinutes} />
    <AlertQuietHoursCard bind:quiet_from={quietFrom} bind:quiet_to={quietTo} />
  </div>

  <AlertPreviewCard {trip} {alertRules} />   <!-- NEU -->

  <div class="actions">
    ...
  </div>
</div>
```

Import hinzufügen:
```typescript
import AlertPreviewCard from './AlertPreviewCard.svelte';
```

`alertRules` ist bereits als `$state` in AlertsTab vorhanden — kein weiterer State nötig.

## Implementation Details

### loadPreview()-Funktion (in AlertPreviewCard.svelte)

```typescript
async function loadPreview() {
  loading = true;
  error = null;
  html = '';
  try {
    const segmentId = trip.stages[0]?.id ?? '1';
    const changes = enabledRules.map(rule => {
      const mapped = METRIC_MAP[rule.metric];
      const newValue = rule.threshold * 1.2;
      const oldValue = rule.kind === 'delta' ? 0 : rule.threshold * 0.8;
      return {
        metric: mapped.metric,
        old_value: oldValue,
        new_value: newValue,
        delta: newValue - oldValue,
        threshold: rule.threshold,
        severity: SEVERITY_MAP[rule.severity],
        direction: mapped.direction,
        segment_id: segmentId,
      };
    });
    const result = await api.post<{ html: string; plain: string }>(
      `/api/trips/${trip.id}/alert-preview`,
      { changes, segment_times: [{ segment_id: segmentId, start: '08:00', end: '17:00' }] }
    );
    html = result.html;
  } catch (e: unknown) {
    error = e && typeof e === 'object' && 'error' in e
      ? String((e as { error: unknown }).error)
      : e instanceof Error ? e.message : 'Vorschau konnte nicht geladen werden';
  } finally {
    loading = false;
  }
}
```

### LoC-Schätzung

- `AlertPreviewCard.svelte`: ~70 LoC (Script ~35, Template ~20, Style ~15)
- `AlertsTab.svelte`: +3 LoC (1 Import, 1 Tag, 1 Leerzeile)
- Gesamt: ~73 LoC (gut unter dem 250-LoC-Limit)

## Acceptance Criteria

**AC-1:** Given der Alerts-Tab wird geöffnet und keine Alert-Regel ist aktiviert /
When die AlertPreviewCard gerendert wird /
Then ist der Button "Vorschau laden" disabled und der Text "Aktiviere mindestens eine Alert-Regel, um die Vorschau zu laden." ist sichtbar (`data-testid="alert-preview-empty"`).

**AC-2:** Given mindestens eine Alert-Regel ist aktiviert (z.B. `wind_gust`, threshold=60, severity='warning') /
When der User auf "Vorschau laden" klickt /
Then wird `POST /api/trips/{id}/alert-preview` mit einem `changes`-Array aufgerufen, das einen Eintrag mit `metric="gust_max_kmh"`, `severity="moderate"`, `direction="above"`, `new_value=72.0`, `old_value=48.0` enthält.

**AC-3:** Given der API-Call zu `alert-preview` gibt `{ html: "<html>...</html>", plain: "..." }` zurück /
When die Response empfangen wird /
Then wird ein iframe mit `srcdoc` auf das HTML gesetzt (`data-testid="alert-preview-iframe"`) und der Button zeigt wieder "Vorschau laden" (nicht mehr "Lade…").

**AC-4:** Given eine delta-Regel ist aktiviert (z.B. `temperature_change`, threshold=10) /
When der Change-Payload generiert wird /
Then hat der zugehörige Eintrag `old_value=0`, `new_value=12.0`, `delta=12.0` und `direction="increase"`.

**AC-5:** Given der API-Call zu `alert-preview` gibt einen HTTP-Fehler zurück /
When der User auf "Vorschau laden" klickt /
Then erscheint eine Inline-Fehlermeldung (`data-testid="alert-preview-error"`) und kein iframe — kein Absturz, kein leerer Screen.

**AC-6:** Given der User ändert eine Schwellwert-Eingabe in der Metric-Tabelle (z.B. Böen von 60 auf 80 kmh) ohne zu speichern /
When er dann auf "Vorschau laden" klickt /
Then wird der neue Wert 80 als Basis für `new_value = 80 * 1.2 = 96.0` verwendet, da `alertRules` der lokale State vor dem Speichern ist.

## Known Limitations

- Die Vorschau verwendet immer das erste Segment (`trip.stages[0]`) als `segment_id` und feste Zeiten 08:00–17:00. Mehrere Etappen werden nicht differenziert.
- Deaktivierte Regeln (enabled=false) erzeugen keine Einträge im Payload — bei leerem `changes`-Array ist der Button disabled, das Backend würde jedoch auch ein leeres Array akzeptieren.
- Die Vorschau aktualisiert sich nicht automatisch bei Änderungen an den Regeln; der User muss erneut auf "Vorschau laden" klicken.

## Changelog

- 2026-05-19: Initial spec (Issue #182 — Alert-Vorschau im Alert-Konfigurator-Tab).
