---
issue: 222
workflow: w2
title: "Frontend: Wizard-Save + AlertsPreviewCard für alert_rules"
created: 2026-05-14
phase: phase1_context
---

# Context: Issue #222 — Workflow 2: Frontend

## Request Summary

Workflow 1 (Backend) ist live: `TripAlertService` liest `trip.alert_rules`.
Workflow 2 schließt die User-sichtbare Lücke im Frontend: Der neue Trip-Wizard
schreibt strukturierte Rules in `trip.alert_rules`, und die
`AlertsPreviewCard` rendert sie auf der Trip-Detailseite.

## Scope-Cut

**In Scope (W2):**
- **Wizard `/trips/new` Step 4 → `alert_rules`** — `toTripPayload()` mappt
  `briefings.thresholds` zu vier `AlertRule`s (kind=absolute, severity=warning,
  enabled=true).
- **`AlertsPreviewCard.svelte` Rendering** — pro `enabled=true`-Rule eine
  Zeile mit Metric-Label, Schwellwert+Unit, Severity-Pill, Edit-Link.
- **Frontend Metric-Label-Map** (4 Einträge).
- **Empty-State** bleibt für 0 enabled-Rules.

**Out of Scope (Folge-Issue):**
- **`TripEditView` / `WizardStep4ReportConfig`** — Edit-Pfad für Bestandstrips
  nutzt einen eigenen Component-Stack (Accordion, nicht 4-Step-Wizard).
  Diese Komponente schreibt heute nur `report_config`. Editing von
  `alert_rules` auf Bestandstrips wird in einem separaten Issue umgesetzt.
- **Re-Open-Pfad des neuen Wizards** mit existierendem Trip — der Wizard wird
  nur für `/trips/new` benutzt, nicht für Edits. AC-2 aus dem Issue
  ("Re-Open des Wizards liest aus `alert_rules`") wird zurückgestellt.

**Begründung des Cuts:** Edit-View ist ein eigener Code-Pfad
(`TripEditView.svelte` mit `WizardStep4ReportConfig`-Component) und würde
W2 über das LoC-Limit treiben. Migration aus Issue #205 hat Bestandstrips
schon `alert_rules` gegeben — `AlertsPreviewCard` zeigt sie für jeden Trip
an. Editieren erfolgt via Folge-Issue.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/types.ts:41-79` | AlertRule/AlertMetric/AlertSeverity-Types — Read-only. |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts:15-31` | `BriefingConfig.thresholds` Type-Def. |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts:312-373` | `toTripPayload()` — **erweitern** um `alert_rules`-Mapping. |
| `frontend/src/lib/components/trip-detail/AlertsPreviewCard.svelte` | **Skeleton, neu implementieren**: Rules iterieren, Severity-Pill, Edit-Link. |
| **NEU:** `frontend/src/lib/components/trip-detail/AlertRow.svelte` | Eine Zeile pro Rule. |
| **NEU:** `frontend/src/lib/utils/alertMetricLabels.ts` | Metric→{label, unit, comparison-symbol} Map. |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Pill-Komponente mit `tone`-Prop (`info/warning/danger/...`) — Vorbild für Severity-Pill. |
| `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` | Mapping-Pattern (Enum → Tone). |
| `frontend/src/lib/components/trip-detail/BriefingPreviewCard.svelte:26-74` | Empty-State CSS-Pattern (`.empty-state`). |

## Existing Patterns

### 1. `BriefingConfig.thresholds`
```typescript
thresholds: {
  gust_kmh: number | null;
  precip_mm: number | null;
  thunder_level: 'NONE' | 'MED' | 'HIGH' | null;
  snow_line_m: number | null;
}
```

### 2. AlertRule JSON (kanonisch, aus Issue #205)
```json
{ "id": "uuid", "kind": "absolute", "metric": "wind_gust",
  "threshold": 50.0, "unit": "km/h", "severity": "warning", "enabled": true }
```

### 3. Mapping Wizard → AlertRule (NEU)
| Wizard-Feld | metric | unit | comparison (im UI anzeigen) |
|---|---|---|---|
| `gust_kmh` (number) | `wind_gust` | `km/h` | `>` |
| `precip_mm` (number) | `precipitation_sum` | `mm` | `>` |
| `thunder_level` ('MED'/'HIGH') | `thunder_level` | `` | `≥` (MED=1.0, HIGH=2.0) |
| `snow_line_m` (number) | `snow_line` | `m` | `>` |

Plus: **TEMPERATURE_MIN** (Kältealarm) — nicht im aktuellen Wizard-UI. Bleibt
für Folge-Issue mit Severity-Editor + Custom-Rule-Form. W2 schreibt nur die 4
oben.

### 4. Severity-Tone-Mapping (für Pill)
- `info` → `tone="info"` (blau)
- `warning` → `tone="warning"` (gelb/orange) — Wizard-Default
- `critical` → `tone="danger"` (rot)

### 5. Empty-State-Pattern
Inline-CSS: `.empty-state { font-size: 0.875rem; color: var(--g-ink-faint); }`
(siehe `BriefingPreviewCard.svelte:71-74`).

## Acceptance Criteria (Kandidat)

- **AC-1:** Wenn der User in `/trips/new` Step 4 mindestens einen Schwellwert
  setzt (z.B. `gust_kmh=50`) und speichert, enthält das resultierende `trip`
  in `alert_rules` eine entsprechende AlertRule.
- **AC-2:** `AlertsPreviewCard` zeigt für jeden Trip mit ≥1
  `enabled=true`-Rule eine Zeile pro Rule mit Metric-Label,
  Schwellwert+Unit, Severity-Pill.
- **AC-3:** Für Trips mit leerem `alert_rules` ODER nur disabled rules zeigt
  die Card weiter den Empty-State.
- **AC-4:** Beim Speichern bleibt `report_config.alert_thresholds` parallel
  bestehen (Fallback für Scheduler/Channels — Architektur-Entscheidung
  Workflow 1).
- **AC-5:** Re-Render der Card mit neuen `alert_rules` (via `$state`-Reaktivität)
  funktioniert ohne Page-Reload.
- **AC-6:** Bestehende Trips ohne Wizard-Save (aus Issue #205-Migration)
  zeigen ihre migrierten Delta-Rules in der Card.

## Dependencies

**Upstream:**
- Issue #205 — AlertRule-Datenmodell + Migration (live)
- Issue #222 W1 — Backend Service-Switch (live, Commit `1d1b306`)

**Downstream (was Tests treffen werden):**
- `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` (Vitest)
- `frontend/e2e/trip-wizard-step4.spec.ts` (Playwright)
- `frontend/e2e/trip-detail-overview-right.spec.ts` (Playwright)
- NEU: Tests für `AlertsPreviewCard.svelte` und `alertMetricLabels.ts`

## Risks & Considerations

1. **THUNDER_LEVEL `>=` im UI anzeigen vs. JSON-threshold:** Backend nutzt
   `>=` für THUNDER_LEVEL (siehe W1-Fix F003). UI sollte das Comparison-Symbol
   passend zeigen — `≥ MED` statt `> MED`.
2. **Snow-Line Defaultrichtung:** Backend default ist `above`. Wizard-UI sollte
   das klar machen (z.B. "Schneefallgrenze über N m alarmieren") oder neutral
   sein.
3. **Card-Re-Render:** Trip-Detail-Seite nutzt `$state<Trip>(data.trip)` — bei
   Wizard-Save erfolgt Navigation via `goto()`, sodass Re-Fetch normalerweise
   greift. Edge-Case: client-seitiges Update ohne Navigation muss `trip.alert_rules`
   reaktiv updaten.
4. **ID-Generierung:** `crypto.randomUUID()` ist im Browser verfügbar (Svelte 5).
5. **LoC-Budget:** Schätzung 160-220 LoC für W2. Innerhalb Limit 250.

## Phase 2 — Analyse-Ergebnisse

### Pill-Komponente (verifiziert)

`Pill.svelte` ist token-basiert (`tone="info|warning|danger|success|accent|default"`), CSS-Regeln in `app.css:278-292`. Direkt nutzbar für Severity ohne extra Styling.

### Architektur-Entscheidungen (Plan-Agent)

**A — Edit-Link in `AlertsPreviewCard`:** **Entfernen** in W2. Der heutige `href="#alerts"` und der TestID `right-card-alerts-edit-link` werden zurückgebaut. Begründung: Der Edit-Pfad (`/trips/[id]/edit`) ist Out-of-Scope und schreibt nur `report_config` — ein Edit-Link wäre eine "kaputte Affordance" (User würde unsichtbar nur Legacy-Felder editieren). Wiedereinführung erfolgt im Folge-Issue zusammen mit `WizardStep4ReportConfig`-Umbau.

**B — Mapping-Helper:** Pure Function `mapBriefingsToAlertRules(thresholds): AlertRule[]` in neuer Datei `frontend/src/lib/utils/alertMapping.ts`. Daneben `frontend/src/lib/utils/alertMetricLabels.ts` für die Label/Unit/Comparison-Map. Beide ohne State-Zugriff → direkt mit Vitest testbar, ohne Svelte-Runes-Setup. `toTripPayload` ruft den Helper auf. Optional: gleiche Map wird auch in `AlertsPreviewCard` für Label-Rendering benutzt → keine Duplikation.

**C — Test-Strategie:** Vitest-schwer + Playwright-leicht:
- ~6 Vitest-Tests für `alertMapping.ts` (alle null, jedes Feld einzeln, alle vier, `thunder_level=NONE`)
- ~3 Vitest-Tests in `wizardState.test.ts` (toTripPayload schreibt alert_rules parallel zu report_config; leere Thresholds; ID-Generierung)
- 1 Playwright-Test in `trip-detail-overview-right.spec.ts` (Trip mit rules → N Rows; ohne → Empty-State)
- 1 Playwright-Assertion in `trip-wizard-step4.spec.ts` (Request-Body enthält `alert_rules`)

Kein Browser-Mock-Setup nötig — pure Funktionen + echtes E2E. Compliant zur CLAUDE.md-Regel "KEINE MOCKS".

### Finale ACs (revidiert)

- **AC-1:** Wenn User in `/trips/new` Step 4 ≥1 Schwellwert setzt und speichert, enthält der POST-Body `alert_rules` mit entsprechenden AlertRules.
- **AC-2:** `AlertsPreviewCard` zeigt für jeden Trip mit ≥1 `enabled=true`-Rule eine Zeile pro Rule mit Metric-Label, Schwellwert+Unit (mit korrektem Vergleichssymbol: `≥` für THUNDER_LEVEL, sonst `>`), Severity-Pill.
- **AC-3:** Trips mit leerem `alert_rules` ODER nur disabled-Rules zeigen weiter den Empty-State.
- **AC-4:** `report_config.alert_thresholds` bleibt parallel bestehen (W1-Architektur).
- **AC-5:** `mapBriefingsToAlertRules({})` mit allen null-Werten gibt leeres Array zurück.
- **AC-6:** `thunder_level='NONE'` erzeugt KEINE AlertRule (semantisch: "kein Alarm gewünscht").

### Scope-Schätzung

| Bereich | LoC |
|---------|-----|
| `alertMapping.ts` (pure function) | ~40 |
| `alertMetricLabels.ts` (4 Einträge + Severity-Tone-Map) | ~30 |
| `wizardState.svelte.ts` (toTripPayload erweitern) | ~10 |
| `AlertsPreviewCard.svelte` (Rendering, Empty-State bleibt) | ~50 |
| `AlertRow.svelte` (neu) | ~40 |
| Tests (Vitest + Playwright-Erweiterung) | ~80 |
| **Total** | **~250 LoC** |

Knapp am Limit. Override-Reserve falls nötig: `loc_limit_override 350`.

## Next

Phase 3 (Spec) für **Workflow 2 Frontend Alert-Konfigurator**.
