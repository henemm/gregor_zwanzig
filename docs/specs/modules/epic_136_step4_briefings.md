---
entity_id: epic_136_step4_briefings
type: module
created: 2026-05-09
updated: 2026-05-11
status: draft
version: "1.0"
parent_spec: epic_136_trip_wizard
related: epic_136_trip_wizard
issue: 164
tags: [sveltekit, frontend, wizard, step4, briefings, channels, epic-136]
---

# Epic 136 — Sub-Spec #164: Step 4 Briefings & Kanaele

## Approval

- [ ] Approved

## Status

**Draft** — bereit zur Freigabe durch User.

## Purpose

Definiert das UI-Detail von Schritt 4 des Trip-Wizards (`Step4Briefings.svelte`,
`ChannelToggle.svelte`, `ReportRow.svelte`, `ThresholdRow.svelte`): Drei Sektionen
(Kanaele, Reports, Alert-Schwellwerte) mit Toggles, Zeit-Inputs und Schwellwert-
Eingaben, die an `WizardState.briefings` gebunden sind. Step 4 ist der letzte Schritt
des Wizards und schaltet die Save-Pipeline scharf: Klick auf den Speichern-Button loest
`state.save()` aus, das intern `toTripPayload()` aufruft — neu erweitert um das
Mapping `briefings` → `trip.report_config`. Die TestID des Platzhalters wird von
`trip-wizard-step4-briefings` auf `trip-wizard-step4-container` umgestellt (Konvention
aus Sub-Spec #163 §10).

## Source

- **Komponente (EDIT, Stub fuellen):** `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte`
- **Komponente (NEU):** `frontend/src/lib/components/trip-wizard/steps/ChannelToggle.svelte`
- **Komponente (NEU):** `frontend/src/lib/components/trip-wizard/steps/ReportRow.svelte`
- **Komponente (NEU):** `frontend/src/lib/components/trip-wizard/steps/ThresholdRow.svelte`
- **State-Erweiterung (EDIT):** `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts`
- **E2E-Tests (NEU):** `frontend/e2e/trip-wizard-step4.spec.ts`
- **Identifier:** `Step4Briefings` (default export), `ChannelToggle` (default export),
  `ReportRow` (default export), `ThresholdRow` (default export),
  `WizardState.canAdvanceStep4`, `WizardState.toTripPayload` (erweitert)

## Verweis auf Master-Spec

Diese Sub-Spec ist eine Detail-Spezifikation der approved Master-Spec
[`docs/specs/modules/epic_136_trip_wizard.md`](./epic_136_trip_wizard.md). Konkret
konsumiert sie:

- **§3.1 `BriefingConfig`-Interface + `defaultBriefingConfig`** — kanonisches
  Schema fuer `channels`, `reports`, `thresholds`. Step 4 liest und mutiert
  `WizardState.briefings` direkt.
- **§1.4 Save-Pipeline** — `state.save()` ist bereits vollstaendig implementiert.
  Step 4 schaltet das Mapping `briefings → report_config` in `toTripPayload()` scharf.
- **§3.1 `canAdvanceCurrent`-Pattern** — Sub-Spec ergaenzt `canAdvanceStep4`-Getter
  und case 4 im Switch.
- **§4 Vertraege Master-Spec ↔ Sub-Specs** — Erweiterung erfolgt mit
  Master-Spec-Changelog-Eintrag (§12 dieser Spec).

Vorgaenger-Sub-Specs:
- [`epic_136_step3_waypoints.md`](./epic_136_step3_waypoints.md) (#163 — Layout-Pattern,
  TestID-Konvention, `fillStepN`-Helper-Form, `canAdvanceStep3`-Getter)
- [`epic_136_step1_profile.md`](./epic_136_step1_profile.md) (#161 — Factory-Handler-
  Pattern fuer Safari-Kompatibilitaet)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WizardState` (Master-Spec §3.1) | class | Single Source of Truth fuer `briefings.*` + Save-Pipeline |
| `wizardState.svelte.ts` | file (edit) | `canAdvanceStep4`-Getter, `canAdvanceCurrent` Switch-Update, `toTripPayload()`-Mapping |
| `BriefingConfig` (Master-Spec §3.1) | interface | Kanonisches Schema: channels/reports/thresholds |
| `defaultBriefingConfig` (`wizardState.svelte.ts`) | const | Initialwerte: email=true, signal/telegram/sms=false, morning 06:00/evening 18:00, alle thresholds=null |
| `$lib/components/ui/eyebrow/Eyebrow.svelte` | component (Epic #133) | Abschnitts-Header ("Kanaele", "Reports", "Alert-Schwellwerte") |
| `$lib/components/ui/g-card/GCard.svelte` | component (Epic #133) | aeusserer Container fuer Step-4-Inhalt |
| `$lib/components/trip-wizard/TripWizardShell.svelte` | file (referenz, mini-edit) | TestID-Update `trip-wizard-step4-briefings` → `trip-wizard-step4-container` |
| `frontend/src/lib/types.ts` | file (lesen) | `Trip.report_config?: Record<string, unknown>` — kein Edit |
| `internal/model/trip.go` | file (referenz) | `ReportConfig map[string]interface{}` mit `omitempty` — kein Edit |
| `src/app/models.py` Z.572-619 | file (referenz) | `TripReportConfig` — alte Felder, die Backward-Compat-Mapping erfordert |
| `svelte` (`getContext`) | api | Step4Briefings liest State via `getContext('trip-wizard-state')` |
| `frontend/e2e/helpers.ts` | file (edit) | `fillStep4`-Helper + `Step4Input`-Typ; `fillStep3`-Wartet-auf-Selektor anpassen |
| `frontend/e2e/trip-wizard-shell.spec.ts` | file (edit) | AC#5a, AC#8, AC#11: `trip-wizard-step4-briefings` → `trip-wizard-step4-container` |

## Implementation Details

### §1 Layout-Wireframe

```
+------------------------------------------------------------------------+
| Eyebrow: "Kanaele"                                                     |
|                                                                        |
| [GCard]                                                                |
|  data-testid: trip-wizard-step4-channels-list                         |
|                                                                        |
|  [x] E-Mail          (ChannelToggle, testid: ...channel-email)         |
|  [ ] Signal          (ChannelToggle, testid: ...channel-signal)        |
|  [ ] Telegram        (ChannelToggle, testid: ...channel-telegram)      |
|  [x] SMS (gesperrt)  (ChannelToggle disabled, testid: ...channel-sms)  |
|      "demnaechst verfuegbar"  (testid: ...channel-sms-hint)            |
|                                                                        |
| Eyebrow: "Reports"                                                     |
|                                                                        |
| [GCard]                                                                |
|  data-testid: trip-wizard-step4-reports-list                          |
|                                                                        |
|  [x] Morgen-Briefing  [06:00]  (ReportRow, morning)                   |
|  [x] Abend-Briefing   [18:00]  (ReportRow, evening)                   |
|                                                                        |
| Eyebrow: "Alert-Schwellwerte"                                          |
|                                                                        |
| [GCard]                                                                |
|  data-testid: trip-wizard-step4-thresholds-list                       |
|                                                                        |
|  Boeen          [____] km/h   (ThresholdRow, gust)                    |
|  Niederschlag   [____] mm     (ThresholdRow, precip)                  |
|  Gewitter       [____v]       (ThresholdRow, thunder — select)         |
|  Schneefallgr.  [____] m      (ThresholdRow, snow)                    |
|                                                                        |
+------------------------------------------------------------------------+
```

Aeusserer Container: `data-testid="trip-wizard-step4-container"`. Innere Sektionen
in eigenstaendigen `<GCard>` mit Eyebrow davor. Vertikaler Stack mit `space-y-6`.
Mobile-Kompatibilitaet: alle Sektionen sind single-column — kein Grid.

### §2 Datenmodell-Erweiterung

Keine Aenderung an `types.ts` oder `trip.go`. `BriefingConfig` und
`defaultBriefingConfig` sind bereits in `wizardState.svelte.ts` vollstaendig definiert:

```typescript
// Bestehend (keine Aenderung):
export interface BriefingConfig {
  channels: { email: boolean; signal: boolean; telegram: boolean; sms: boolean };
  reports: {
    morning: { enabled: boolean; time: string }; // 'HH:MM'
    evening: { enabled: boolean; time: string }; // 'HH:MM'
  };
  thresholds: {
    gust_kmh: number | null;
    precip_mm: number | null;
    thunder_level: 'NONE' | 'MED' | 'HIGH' | null;
    snow_line_m: number | null;
  };
}

export const defaultBriefingConfig: BriefingConfig = {
  channels: { email: true, signal: false, telegram: false, sms: false },
  reports: {
    morning: { enabled: true, time: '06:00' },
    evening: { enabled: true, time: '18:00' }
  },
  thresholds: { gust_kmh: null, precip_mm: null, thunder_level: null, snow_line_m: null }
};
```

Step 4 beruehrt keine Typ-Definitionen — alle Felder sind bereits vorhanden.

### §3 WizardState-Erweiterungen

Alle Aenderungen sind additiv. Bestehender `canAdvanceCurrent`-Switch hat
`case 4: return true` (literal) — wird durch den neuen Getter abgesichert.

#### §3.1 `canAdvanceStep4`-Getter (NEU)

```typescript
/**
 * Sub-Spec #164 §3.1: Trip ohne Kanaele speicherbar — kein Validierungs-Gate
 * (User-Entscheidung 2026-05-11). Begruendung: ad-hoc-Trips koennen nachtraeglich
 * konfiguriert werden. Konsistenz mit canAdvanceStep3-Pattern (#163).
 */
get canAdvanceStep4(): boolean {
  return true;
}
```

#### §3.2 `canAdvanceCurrent`-Switch-Update

Case 4 von `return true` auf `return this.canAdvanceStep4` umstellen.
Wert ist aktuell identisch, aber der Getter macht die Semantik explizit und
ermoeglicht spaetere Aenderung ohne Switch-Refactor.

```typescript
get canAdvanceCurrent(): boolean {
  switch (this.currentStep) {
    case 1: return this.canAdvanceStep1;
    case 2: return this.canAdvanceStep2;
    case 3: return this.canAdvanceStep3;
    case 4: return this.canAdvanceStep4;
  }
}
```

#### §3.3 `toTripPayload()`-Erweiterung — Mapping `briefings` → `report_config`

Die bestehende `toTripPayload()`-Methode schreibt `report_config` noch nicht.
Sie wird um den folgenden Block erweitert (nach dem `aggregation`-Block):

```typescript
// Sub-Spec #164 §3.3: Mapping briefings -> report_config
// Zwei Bloecke: Backward-Compat (alte Felder, Scheduler/Alert lesen diese)
// und neue alert_thresholds (konsumiert ab Epic #139).
const b = this.briefings;
const rc: Record<string, unknown> = {
  // --- Backward-Compat-Block (TripReportConfig.py Z.589-605) ---------------
  // Synthetisch abgeleitet: enabled = morning.enabled || evening.enabled
  // (Phase-2-Entscheidung #4, 2026-05-11)
  enabled: b.reports.morning.enabled || b.reports.evening.enabled,
  morning_time: b.reports.morning.time,      // 'HH:MM'; Python liest time.fromisoformat
  evening_time: b.reports.evening.time,
  send_email: b.channels.email,
  send_signal: b.channels.signal,
  send_telegram: b.channels.telegram,
  send_sms: b.channels.sms,
};

// --- Neuer Block: alert_thresholds (Phase-2-Entscheidung #1, 2026-05-11) ---
// Nur schreiben wenn mindestens ein Feld gesetzt ist (nicht alle null).
const t = b.thresholds;
if (
  t.gust_kmh !== null ||
  t.precip_mm !== null ||
  t.thunder_level !== null ||
  t.snow_line_m !== null
) {
  rc.alert_thresholds = {
    gust_kmh:      t.gust_kmh,
    precip_mm:     t.precip_mm,
    thunder_level: t.thunder_level,
    snow_line_m:   t.snow_line_m
  };
}

trip.report_config = rc;
```

Hinweis: Die alten `change_threshold_temp_c / change_threshold_wind_kmh /
change_threshold_precip_mm`-Felder werden NICHT geschrieben — sie sind semantisch
verschieden (Aenderungs-Deltas) und werden weiterhin nur ueber `TripEditView`
gepflegt. Das neue Schema unter `alert_thresholds` enthaelt Absolutwert-Schwellen
und wird von Epic #139 (Alert-Konfigurator) konsumiert.

### §4 `ChannelToggle.svelte` (NEU, ~40 LoC)

Generischer Toggle fuer einen Briefing-Kanal.

**Props:**

```typescript
interface Props {
  label: string;
  checked: boolean;
  onchange: (checked: boolean) => void;
  disabled?: boolean;          // default false
  hint?: string;               // optionaler Hilfetext (z.B. SMS: "demnaechst verfuegbar")
  testid?: string;             // data-testid fuer den Toggle-Container
}
let { label, checked, onchange, disabled = false, hint, testid }: Props = $props();
```

**Factory-Pattern (Safari-Pflicht aus CLAUDE.md):**

```typescript
// In aufrufender Komponente (Step4Briefings.svelte):
function makeChannelHandler(channel: keyof BriefingConfig['channels']) {
  return function doToggleChannel(e: Event): void {
    wizard.briefings.channels[channel] = (e.target as HTMLInputElement).checked;
  };
}
```

**Layout:** `flex items-center gap-3`. Toggle (native `<input type="checkbox">`),
Label-Text, optional darunter Hint-Text (`text-xs text-[var(--g-ink-faint)]`).
Bei `disabled`: `opacity-50 cursor-not-allowed` auf den Container.

**TestIDs:**
- Container: `data-testid={testid}` (z.B. `trip-wizard-step4-channel-email`)
- Hint: `data-testid="{testid}-hint"` (z.B. `trip-wizard-step4-channel-sms-hint`)

### §5 `ReportRow.svelte` (NEU, ~50 LoC)

Row-Komponente fuer einen einzelnen Report-Typ (Morgen / Abend).

**Props:**

```typescript
interface Props {
  label: string;               // z.B. "Morgen-Briefing"
  enabled: boolean;
  time: string;                // 'HH:MM'
  onEnabledChange: (enabled: boolean) => void;
  onTimeChange: (time: string) => void;
  testidToggle: string;        // z.B. 'trip-wizard-step4-report-morning-toggle'
  testidTime: string;          // z.B. 'trip-wizard-step4-report-morning-time'
}
let { label, enabled, time, onEnabledChange, onTimeChange,
      testidToggle, testidTime }: Props = $props();
```

**Factory-Pattern:**

```typescript
// In aufrufender Komponente:
function makeReportEnabledHandler(report: 'morning' | 'evening') {
  return function doToggleReport(e: Event): void {
    wizard.briefings.reports[report].enabled = (e.target as HTMLInputElement).checked;
  };
}
function makeReportTimeHandler(report: 'morning' | 'evening') {
  return function doSetReportTime(e: Event): void {
    wizard.briefings.reports[report].time = (e.target as HTMLInputElement).value;
  };
}
```

**Layout (horizontal, `flex items-center gap-4`):**
1. `<input type="checkbox">` mit `data-testid={testidToggle}`.
2. Label-Text, Klasse `flex-1 text-sm`.
3. `<input type="time">` mit `data-testid={testidTime}`, Wert = `time`, disabled
   wenn `!enabled`.

### §6 `ThresholdRow.svelte` (NEU, ~50 LoC)

Row-Komponente fuer einen einzelnen Schwellwert.

**Props:**

```typescript
type ThunderLevel = 'NONE' | 'MED' | 'HIGH' | null;

interface Props {
  label: string;               // z.B. "Boeen"
  type: 'number' | 'thunder'; // number → input[type=number], thunder → select
  value: number | ThunderLevel | null;
  unit?: string;               // nur bei type='number', z.B. 'km/h', 'mm', 'm'
  onchange: (v: number | ThunderLevel | null) => void;
  testid: string;              // z.B. 'trip-wizard-step4-threshold-gust'
}
let { label, type, value, unit, onchange, testid }: Props = $props();
```

**Factory-Pattern:**

```typescript
// In aufrufender Komponente:
function makeThresholdHandler(field: keyof BriefingConfig['thresholds']) {
  return function doSetThreshold(e: Event): void {
    const target = e.target as HTMLInputElement | HTMLSelectElement;
    if (field === 'thunder_level') {
      const v = (target as HTMLSelectElement).value;
      wizard.briefings.thresholds.thunder_level =
        v === '' ? null : (v as ThunderLevel);
    } else {
      const raw = (target as HTMLInputElement).value;
      (wizard.briefings.thresholds as Record<string, unknown>)[field] =
        raw === '' ? null : Number(raw);
    }
  };
}
```

**Layout (horizontal, `flex items-center gap-3`):**
1. Label-Text, Klasse `w-40 text-sm flex-shrink-0`.
2. Bei `type='number'`: `<input type="number" min="0" step="1">`, Klasse `w-24`.
   Leer wenn `value === null` (`value={value ?? ''}`). `data-testid={testid}`.
3. Bei `type='thunder'`: `<select>` mit Optionen:
   - leere Option (Wert `""`) → null — Label "—"
   - `NONE` — Label "Kein"
   - `MED` — Label "Mittel"
   - `HIGH` — Label "Hoch"
   Ausgewaehlt: `value ?? ''`. `data-testid={testid}`.
4. Einheit (`unit`, nur bei `type='number'`): `<span class="text-sm text-[var(--g-ink-faint)]">`.

### §7 `Step4Briefings.svelte` (FUELLEN, ~120 LoC)

Fuellt den Platzhalter-Stub. Liest `wizard = getContext<WizardState>('trip-wizard-state')`.

**Struktur:**

```
<div data-testid="trip-wizard-step4-container" class="space-y-6">

  <Eyebrow>Kanaele</Eyebrow>
  <GCard>
    <div data-testid="trip-wizard-step4-channels-list" class="space-y-3">
      <ChannelToggle label="E-Mail"   checked={wizard.briefings.channels.email}
        onchange={makeChannelHandler('email')}
        testid="trip-wizard-step4-channel-email" />
      <ChannelToggle label="Signal"   checked={wizard.briefings.channels.signal}
        onchange={makeChannelHandler('signal')}
        testid="trip-wizard-step4-channel-signal" />
      <ChannelToggle label="Telegram" checked={wizard.briefings.channels.telegram}
        onchange={makeChannelHandler('telegram')}
        testid="trip-wizard-step4-channel-telegram" />
      <ChannelToggle label="SMS" checked={false} disabled
        hint="demnaechst verfuegbar"
        onchange={() => {}}
        testid="trip-wizard-step4-channel-sms" />
    </div>
  </GCard>

  <Eyebrow>Reports</Eyebrow>
  <GCard>
    <div data-testid="trip-wizard-step4-reports-list" class="space-y-3">
      <ReportRow label="Morgen-Briefing"
        enabled={wizard.briefings.reports.morning.enabled}
        time={wizard.briefings.reports.morning.time}
        onEnabledChange={makeReportEnabledHandler('morning')}
        onTimeChange={makeReportTimeHandler('morning')}
        testidToggle="trip-wizard-step4-report-morning-toggle"
        testidTime="trip-wizard-step4-report-morning-time" />
      <ReportRow label="Abend-Briefing"
        enabled={wizard.briefings.reports.evening.enabled}
        time={wizard.briefings.reports.evening.time}
        onEnabledChange={makeReportEnabledHandler('evening')}
        onTimeChange={makeReportTimeHandler('evening')}
        testidToggle="trip-wizard-step4-report-evening-toggle"
        testidTime="trip-wizard-step4-report-evening-time" />
    </div>
  </GCard>

  <Eyebrow>Alert-Schwellwerte</Eyebrow>
  <GCard>
    <div data-testid="trip-wizard-step4-thresholds-list" class="space-y-3">
      <ThresholdRow label="Boeen"          type="number"  unit="km/h"
        value={wizard.briefings.thresholds.gust_kmh}
        onchange={makeThresholdHandler('gust_kmh')}
        testid="trip-wizard-step4-threshold-gust" />
      <ThresholdRow label="Niederschlag"   type="number"  unit="mm"
        value={wizard.briefings.thresholds.precip_mm}
        onchange={makeThresholdHandler('precip_mm')}
        testid="trip-wizard-step4-threshold-precip" />
      <ThresholdRow label="Gewitter"       type="thunder"
        value={wizard.briefings.thresholds.thunder_level}
        onchange={makeThresholdHandler('thunder_level')}
        testid="trip-wizard-step4-threshold-thunder" />
      <ThresholdRow label="Schneefallgrenze" type="number" unit="m"
        value={wizard.briefings.thresholds.snow_line_m}
        onchange={makeThresholdHandler('snow_line_m')}
        testid="trip-wizard-step4-threshold-snow" />
    </div>
  </GCard>

</div>
```

Kein Save-Button in Step4Briefings — der Save-Button kommt von `TripWizardShell`
(Z.131: `{#if state.currentStep === 4}`). Step 4 triggert keinen direkten API-Call;
das erledigt `state.save()` in der Shell.

### §8 `TripWizardShell.svelte` — Mini-Edit TestID

Der Platzhalter-Stub (`Step4Briefings.svelte`) traegt aktuell
`data-testid="trip-wizard-step4-briefings"`. Nach dem Fuellen des Stubs wird
der Root-Container-TestID auf `trip-wizard-step4-container` umgestellt (§7 oben).
`TripWizardShell.svelte` selbst muss nicht angefasst werden — die TestID lebt
im gemounteten Step-Komponenten, nicht in der Shell. Shell-Tests (AC#5a, AC#8,
AC#11) verweisen auf `trip-wizard-step4-briefings`; diese werden in §11 migriert.

### §9 TestID-Inventar

| TestID | Komponente | Zweck |
|--------|------------|-------|
| `trip-wizard-step4-container` | `Step4Briefings.svelte` (Root) | Schritt-4-Sichtbarkeit; ersetzt `trip-wizard-step4-briefings` |
| `trip-wizard-step4-channels-list` | Kanaele-Sektion | Container der Channel-Toggles |
| `trip-wizard-step4-channel-email` | `ChannelToggle` Email | Toggle-Container |
| `trip-wizard-step4-channel-signal` | `ChannelToggle` Signal | Toggle-Container |
| `trip-wizard-step4-channel-telegram` | `ChannelToggle` Telegram | Toggle-Container |
| `trip-wizard-step4-channel-sms` | `ChannelToggle` SMS (disabled) | Toggle-Container, disabled |
| `trip-wizard-step4-channel-sms-hint` | Hint-Text unter SMS | "demnaechst verfuegbar" |
| `trip-wizard-step4-reports-list` | Reports-Sektion | Container der ReportRows |
| `trip-wizard-step4-report-morning-toggle` | `ReportRow` Morgen Toggle | Morgen-Report aktivieren |
| `trip-wizard-step4-report-morning-time` | `ReportRow` Morgen Zeit | Zeitpunkt Morgen-Report |
| `trip-wizard-step4-report-evening-toggle` | `ReportRow` Abend Toggle | Abend-Report aktivieren |
| `trip-wizard-step4-report-evening-time` | `ReportRow` Abend Zeit | Zeitpunkt Abend-Report |
| `trip-wizard-step4-thresholds-list` | Schwellwerte-Sektion | Container der ThresholdRows |
| `trip-wizard-step4-threshold-gust` | `ThresholdRow` Boeen | Boen-Schwellwert-Input |
| `trip-wizard-step4-threshold-precip` | `ThresholdRow` Niederschlag | Niederschlag-Schwellwert-Input |
| `trip-wizard-step4-threshold-thunder` | `ThresholdRow` Gewitter | Gewitter-Level-Select |
| `trip-wizard-step4-threshold-snow` | `ThresholdRow` Schneefallgrenze | Schneefallgrenze-Input |

### §10 E2E-Helper `fillStep4`

Datei: `frontend/e2e/helpers.ts`

```typescript
export interface Step4Input {
  channels?: {
    email?: boolean;
    signal?: boolean;
    telegram?: boolean;
    // sms: nicht konfigurierbar (disabled)
  };
  reports?: {
    morning?: { enabled?: boolean; time?: string };
    evening?: { enabled?: boolean; time?: string };
  };
  thresholds?: {
    gust_kmh?: number | null;
    precip_mm?: number | null;
    thunder_level?: 'NONE' | 'MED' | 'HIGH' | null;
    snow_line_m?: number | null;
  };
  expectSaveSuccess?: boolean; // default true — wartet auf Redirect nach Save
}

export async function fillStep4(page: Page, input: Step4Input = {}): Promise<void> {
  await page.getByTestId('trip-wizard-step4-container').waitFor({ state: 'visible' });

  // Channels
  if (input.channels) {
    for (const [ch, val] of Object.entries(input.channels)) {
      const toggle = page.getByTestId(`trip-wizard-step4-channel-${ch}`)
        .locator('input[type="checkbox"]');
      const current = await toggle.isChecked();
      if (val !== undefined && current !== val) {
        await toggle.click();
      }
    }
  }

  // Report-Toggles und Zeiten
  if (input.reports) {
    for (const [rep, cfg] of Object.entries(input.reports)) {
      if (!cfg) continue;
      if (cfg.enabled !== undefined) {
        const toggle = page.getByTestId(`trip-wizard-step4-report-${rep}-toggle`);
        const current = await toggle.isChecked();
        if (current !== cfg.enabled) await toggle.click();
      }
      if (cfg.time !== undefined) {
        await page.getByTestId(`trip-wizard-step4-report-${rep}-time`)
          .fill(cfg.time);
      }
    }
  }

  // Schwellwerte
  if (input.thresholds) {
    const { gust_kmh, precip_mm, thunder_level, snow_line_m } = input.thresholds;
    if (gust_kmh !== undefined) {
      await page.getByTestId('trip-wizard-step4-threshold-gust')
        .fill(gust_kmh === null ? '' : String(gust_kmh));
    }
    if (precip_mm !== undefined) {
      await page.getByTestId('trip-wizard-step4-threshold-precip')
        .fill(precip_mm === null ? '' : String(precip_mm));
    }
    if (thunder_level !== undefined) {
      await page.getByTestId('trip-wizard-step4-threshold-thunder')
        .selectOption(thunder_level === null ? '' : thunder_level);
    }
    if (snow_line_m !== undefined) {
      await page.getByTestId('trip-wizard-step4-threshold-snow')
        .fill(snow_line_m === null ? '' : String(snow_line_m));
    }
  }

  // Save-Button
  await page.getByTestId('trip-wizard-save').click();

  if (input.expectSaveSuccess !== false) {
    // Redirect auf /trips/{id} abwarten (Master-Spec §1.4 Schritt 6)
    await page.waitForURL(/\/trips\/[^/]+$/, { timeout: 10000 });
  }
}
```

Zusaetzlich: In `fillStep3` (bestehend, Z.113) wird der Wartet-auf-Selektor
von `trip-wizard-step4-briefings` auf `trip-wizard-step4-container` umgestellt —
diese Zeile war lt. Sub-Spec #163 §10 explizit als temporaer markiert:

```typescript
// Vor (temporaer aus #163 §10):
// await page.getByTestId('trip-wizard-step4-briefings').waitFor({ state: 'visible' });

// Nach (mit #164 final):
// (kein explizites Warten in fillStep3 auf Step-4-Container noetig —
//  fillStep4 macht das selbst. fillStep3 klickt nur Weiter.)
```

Hinweis: `fillStep3` klickt intern `trip-wizard-next` — der Step-4-Container
erscheint danach automatisch. `fillStep4` wartet mit eigenem `waitFor` auf
`trip-wizard-step4-container` am Anfang. Kein doppeltes Warten noetig.

### §11 Migration `trip-wizard-shell.spec.ts`

Tests AC#5a, AC#8, AC#11 referenzieren `trip-wizard-step4-briefings`. Nach dem
TestID-Wechsel auf `-container` muessen diese drei Tests angepasst werden:

**AC#5a (Weiter-Button enabled in Steps 3+4):**

```typescript
// Keine Aenderung noetig — AC#5a navigiert nur bis Step 3 (fillStep3),
// prueft Weiter-Button, navigiert nicht mehr weiter zu Step 4.
// Kein TestID-Verweis auf step4 in AC#5a.
```

**AC#8 (Speichern-Button erscheint nur in Step 4):**

```typescript
// Vor:
// await fillStep3(page);  // wartet intern auf trip-wizard-step4-briefings
// Nach:
await fillStep3(page);     // wartet jetzt auf trip-wizard-step4-container (§10)
await expect(page.getByTestId('trip-wizard-save')).toBeVisible();
```

**AC#11 (alle 4 Step-Slot-Container sichtbar):**

```typescript
// Vor:
// await expect(page.getByTestId('trip-wizard-step4-briefings')).toBeVisible();
// Nach:
await expect(page.getByTestId('trip-wizard-step4-container')).toBeVisible();
```

Betroffene Tests: AC#8 und AC#11 brauchen explizite Anpassung. AC#5a ist
unberuehrt (kein direkter Verweis auf step4-Selektor). Alle anderen Shell-Tests:
keine Aenderung.

### §12 Master-Spec-Changelog-Eintrag

`docs/specs/modules/epic_136_trip_wizard.md` erhaelt einen neuen Changelog-Eintrag
(kein Approval-Reset, weil rein additive Erweiterungen):

```markdown
- 2026-05-11: §3.1 und §1.4 erweitert um additive Methoden/Getter (Sub-Spec #164):
  `get canAdvanceStep4(): boolean` (immer true — kein Kanal-Validierungs-Gate,
  User-Entscheidung 2026-05-11). `canAdvanceCurrent` case 4 zeigt auf
  `canAdvanceStep4` statt literal `true`. `toTripPayload()` erweitert um Mapping
  `briefings -> report_config`: Backward-Compat-Block (enabled, morning_time,
  evening_time, send_email/signal/telegram/sms) und neuer `alert_thresholds`-Sub-Block
  (gust_kmh, precip_mm, thunder_level, snow_line_m; wird nur geschrieben wenn min.
  ein Feld nicht null). Alte change_threshold_*-Felder unberuehrt.
  Detail in Sub-Spec epic_136_step4_briefings.md.
```

## Expected Behavior

- **Input:** User in Step 4, nachdem Step 1-3 durchlaufen wurden. `WizardState.briefings`
  enthaelt `defaultBriefingConfig`-Werte (email=true, Signal/Telegram/SMS=false,
  Morgen 06:00 und Abend 18:00 aktiviert, alle Schwellwerte null).
- **Output:**
  - Drei Sektionen sichtbar (Kanaele, Reports, Alert-Schwellwerte).
  - Channel-Toggles binden an `wizard.briefings.channels.*`. SMS ist sichtbar aber
    disabled mit Hinweis "demnaechst verfuegbar".
  - Report-Rows binden Toggle an `wizard.briefings.reports.{morning|evening}.enabled`
    und Zeit-Input an `.time`.
  - Threshold-Rows binden an `wizard.briefings.thresholds.*`; leeres Feld = null.
  - Save-Button (aus Shell) immer enabled (`canAdvanceStep4 = true`).
  - Klick Save: `state.save()` → `toTripPayload()` schreibt `report_config` mit
    Backward-Compat-Block + optionalem `alert_thresholds`-Block → `POST /api/trips`
    → Redirect auf `/trips/{id}`.
  - Bei Save-Fehler: Inline-Fehlermeldung am Save-Button (aus Shell), kein Toast.
- **Side effects:**
  - `WizardState.briefings` wird bei jedem Toggle/Input-Aenderung mutiert.
  - Kein API-Call in Step 4 ausser beim Save-Klick.
  - `WizardState.saveStatus` wechselt bei Save: `idle → saving → ok|error`.

## Acceptance Criteria

| # | Kriterium | Pruefung |
|---|-----------|----------|
| 1 | `Step4Briefings.svelte` rendert Container mit TestID `trip-wizard-step4-container` | E2E |
| 2 | Sektion "Kanaele" rendert `trip-wizard-step4-channels-list` mit 4 Toggles | E2E |
| 3 | Email-Toggle ist standardmaessig aktiviert (`defaultBriefingConfig`) | E2E (kein Benutzer-Eingriff: `isChecked()` true) |
| 4 | Signal- und Telegram-Toggle sind standardmaessig deaktiviert | E2E |
| 5 | SMS-Toggle rendert mit TestID `trip-wizard-step4-channel-sms` und ist `disabled` | E2E (`isDisabled()`) |
| 6 | SMS-Hint mit TestID `trip-wizard-step4-channel-sms-hint` zeigt "demnaechst verfuegbar" | E2E (Text-Content-Check) |
| 7 | Klick auf Email-Toggle aendert `wizard.briefings.channels.email` | E2E (Toggle klicken, neuen State per Evaluate oder zweiten Check pruefen) |
| 8 | Sektion "Reports" rendert `trip-wizard-step4-reports-list` mit 2 ReportRows | E2E |
| 9 | Morgen-Toggle ist standardmaessig aktiviert, Zeit-Input zeigt "06:00" | E2E |
| 10 | Abend-Toggle ist standardmaessig aktiviert, Zeit-Input zeigt "18:00" | E2E |
| 11 | Morgen-Zeit-Input deaktiviert wenn Morgen-Toggle deaktiviert | E2E (Toggle aus → input disabled) |
| 12 | Aenderung der Morgen-Zeit auf "07:30" persistiert im State | E2E (fill + evaluate state) |
| 13 | Sektion "Schwellwerte" rendert `trip-wizard-step4-thresholds-list` mit 4 Rows | E2E |
| 14 | Schwellwert-Inputs zeigen initial keinen Wert (alle null) | E2E (value === '') |
| 15 | Number-Inputs (gust, precip, snow) nehmen numerische Werte entgegen; leeres Feld = null im State | E2E + Unit-Test (`toTripPayload`) |
| 16 | Gewitter-Select bietet Optionen "—", "Kein", "Mittel", "Hoch" | E2E (options pruefe via evaluate) |
| 17 | `canAdvanceStep4` gibt immer `true` zurueck | Unit-Test |
| 18 | `canAdvanceCurrent` mit currentStep=4 delegiert auf `canAdvanceStep4` | Unit-Test |
| 19 | Save-Button aus TripWizardShell ist in Step 4 immer sichtbar und enabled | E2E (nur `saveStatus !== 'saving'` bremst den Button) |
| 20 | `toTripPayload()` schreibt `report_config.enabled = morning.enabled \|\| evening.enabled` | Unit-Test |
| 21 | `toTripPayload()` schreibt `report_config.morning_time` und `evening_time` als 'HH:MM'-String | Unit-Test |
| 22 | `toTripPayload()` schreibt `report_config.send_email/signal/telegram/sms` korrekt | Unit-Test |
| 23 | `toTripPayload()` schreibt `report_config.alert_thresholds` nur wenn mindestens ein Threshold nicht null | Unit-Test (2 Cases: alle null → kein Block; gust_kmh=80 → Block mit gust_kmh=80) |
| 24 | `toTripPayload()` schreibt `report_config.alert_thresholds.thunder_level` als String-Enum ('NONE'/'MED'/'HIGH') oder null | Unit-Test |
| 25 | `fillStep4()` ohne Parameter klickt Save und wartet auf Redirect zu `/trips/*` | E2E (Helper-Test, Mock-Server oder Staging) |
| 26 | Shell-Tests AC#8 und AC#11 verweisen auf `trip-wizard-step4-container` (nicht mehr `-briefings`) | E2E (grep + Lauf) |
| 27 | `npm run check` und `npm run build` im `frontend/` gruen | CI-Output |

## Datei-Liste

### NEU

| Datei | Zweck | LoC (Schaetzung) |
|-------|-------|------------------|
| `frontend/src/lib/components/trip-wizard/steps/ChannelToggle.svelte` | Generischer Channel-Toggle (Label, Checkbox, optional disabled + Hint) | ~40 |
| `frontend/src/lib/components/trip-wizard/steps/ReportRow.svelte` | Toggle + Zeit-Input fuer einen Report-Typ | ~50 |
| `frontend/src/lib/components/trip-wizard/steps/ThresholdRow.svelte` | Label + Number-Input oder Select fuer Schwellwerte | ~50 |
| `frontend/e2e/trip-wizard-step4.spec.ts` | E2E-Tests AC#1–#26 | ~180 |

### EDIT

| Datei | Aenderung | LoC |
|-------|-----------|-----|
| `frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte` | Stub gefuellt: 3 Sektionen mit ChannelToggle/ReportRow/ThresholdRow, getContext, Factory-Handler | ~120 |
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | `canAdvanceStep4`-Getter + Switch-Update case 4 + `toTripPayload()`-Mapping `briefings -> report_config` | +~40 |
| `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` | Neue Test-Cases fuer `canAdvanceStep4`, `canAdvanceCurrent` case 4, `toTripPayload()` mit Mapping (5 Cases) | +~60 |
| `frontend/e2e/helpers.ts` | `fillStep4`-Helper + `Step4Input`-Typ; `fillStep3` Wartet-Kommentar aktualisieren | +~45 |
| `frontend/e2e/trip-wizard-shell.spec.ts` | AC#8 und AC#11: `trip-wizard-step4-briefings` → `trip-wizard-step4-container` | +~3 |
| `docs/specs/modules/epic_136_trip_wizard.md` | Master-Spec-Changelog-Eintrag | +~10 |

### NICHT BERUEHRT

- `frontend/src/lib/types.ts` (kein Edit — `Trip.report_config` als `Record<string,unknown>` genuegt)
- `internal/model/trip.go` (kein Edit — `ReportConfig map[string]interface{}` nimmt neues Schema auf)
- `internal/handler/trip.go` (kein Edit — `CreateTripHandler` nimmt `report_config` als freies Map)
- `src/app/models.py` (kein Edit — `TripReportConfig` bleibt kanonisch fuer Scheduler/Alert)
- `frontend/src/lib/components/trip-wizard/wizardHelpers.ts`
- `frontend/src/lib/components/trip-wizard/TripWizardShell.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte`
- `frontend/src/lib/components/trip-wizard/steps/Step3Waypoints.svelte`
- `frontend/src/lib/components/edit/TripEditView.svelte` (Folge-Issue, nicht in Scope)
- `frontend/src/lib/components/wizard/WizardStep4ReportConfig.svelte` (zu loeschen, Cleanup-Issue)

## Known Limitations

- **Edit-Pfad: `TripEditView` zerstoert `report_config.alert_thresholds` beim Speichern.**
  `TripEditView.svelte` verwendet das alte `WizardStep4ReportConfig`, das die neuen
  `alert_thresholds`-Felder nicht kennt. Ein Save ueber den Edit-Pfad ueberschreibt
  `report_config` ohne den `alert_thresholds`-Block. Temporaer akzeptiert, weil das
  Backend (Epic #139) die neuen Felder noch nicht konsumiert — kein fachlicher Verlust
  bis Epic #139 aktiv wird. Ein Code-Kommentar in `TripEditView.svelte` mit Verweis auf
  das Folge-Issue ist Pflicht bei Deploy (Phase 7).
- **SMS-Channel ohne Backend-Pipeline.** SMS-Toggle ist sichtbar aber gesperrt.
  `send_sms = false` wird persistiert, hat aber keinen Effekt bis ein SMS-Provider
  integriert ist.
- **Keine Validierung von Schwellwert-Bereichen.** Ein User kann `gust_kmh = 9999`
  eingeben — das UI verhindert das nicht. Sinnvolle Bereichsgrenzen sind Epic-#139-
  Concern.
- **`thunder_level`-Semantik nicht erklaert.** Die UI zeigt "Kein/Mittel/Hoch" ohne
  Erklaerung, was die Werte bedeuten. Tooltip oder Hilfetext ist not-in-scope fuer #164.
- **Kein Persist beim Browser-Close.** WizardState ist reines In-Memory-Svelte-State.
  Schliesst der User den Browser in Step 4 vor dem Save, sind alle Eingaben verloren.
  localStorage-Persistenz ist not-in-scope fuer Epic #136.

## Not In Scope

- **Backend-Verwertung von `alert_thresholds`** — ist Epic #139 (Alert-Konfigurator).
- **TripEditView-Refactor** — Cleanup-Folge-Issue (Master-Spec §Delete-Liste).
- **SMS-Provider-Integration** — unbekannter Folge-Sprint.
- **Neue Channels ueber die 4 hinaus** (z.B. WhatsApp, Push) — Folge-Issue.
- **Schwellwert-Bereichsvalidierung** (min/max-Constraints) — Epic #139.
- **Historische `change_threshold_*`-Felder im neuen Wizard anzeigen** — die alten
  Aenderungs-Deltas (Temperatur, Wind, Niederschlag) werden im neuen Wizard nicht
  gezeigt. Sie bleiben ueber `TripEditView` konfigurierbar bis zum Refactor.
- **`multi_day_trend_reports`-Felder** aus `TripReportConfig` — der alte Wizard zeigte
  diese; der neue Wizard schreibt sie nicht (Defaults aus Python).
- **`show_compact_summary` / `show_daylight`-Optionen** — der alte Wizard hatte
  einen "Erweitert"-Bereich; der neue Wizard laesst diese Felder weg.
- **A11y-Erweiterungen** ueber ARIA-Labels hinaus (z.B. Tastaturnavigation im Select).
- **Lokale State-Persistenz** (localStorage) bei Browser-Close.

## Verweise

- **Master-Spec:** [`epic_136_trip_wizard.md`](./epic_136_trip_wizard.md)
  - §3.1 `BriefingConfig`-Interface + `defaultBriefingConfig`
  - §1.4 Save-Pipeline (`state.save()`, `toTripPayload()`, `POST /api/trips`)
  - §3.1 `canAdvanceCurrent`-Pattern
- **Vorgaenger-Sub-Spec:** [`epic_136_step3_waypoints.md`](./epic_136_step3_waypoints.md)
  (#163 — Layout-Pattern, TestID-Konvention, `fillStepN`-Helper-Form,
  `canAdvanceStepN`-Getter, TestID `-container`-Konvention)
- **Vorgaenger-Sub-Spec:** [`epic_136_step1_profile.md`](./epic_136_step1_profile.md)
  (#161 — Factory-Handler-Pattern fuer Safari-Kompatibilitaet)
- **Atom-Komponenten:** Epic #133 (`Btn`, `GCard`, `Eyebrow`)
- **Python-Schema-Referenz:** `src/app/models.py` Z.572-619 (`TripReportConfig`)
- **Altes UI (Referenz, zu loeschen):** `frontend/src/lib/components/wizard/WizardStep4ReportConfig.svelte`
- **Phase-1+2-Kontext:** `docs/context/issue-164-wizard-step4-channels.md`
- **Issue:** [#164 — Step 4: Briefings & Kanaele](https://github.com/henemm/gregor_zwanzig/issues/164)
- **Epic:** [#136 — EPIC 4 Trip-Wizard](https://github.com/henemm/gregor_zwanzig/issues/136)

## Changelog

- 2026-05-11: Stub ausgefuellt — Layout-Wireframe (3 Sektionen: Kanaele/Reports/
  Alert-Schwellwerte), 3 neue Hilfskomponenten (ChannelToggle ~40 LoC, ReportRow ~50
  LoC, ThresholdRow ~50 LoC), Step4Briefings-Fuellen (~120 LoC), WizardState-
  Erweiterungen (canAdvanceStep4=true, Switch-Update case 4, toTripPayload-Mapping
  mit Backward-Compat-Block + alert_thresholds-Sub-Block), SMS-Toggle als disabled
  mit Hint "demnaechst verfuegbar", canAdvanceStep4 immer true (kein Validierungs-
  Gate), enabled synthetisch aus morning.enabled||evening.enabled, TestID-Umbenennung
  trip-wizard-step4-briefings -> trip-wizard-step4-container, fillStep4-E2E-Helper
  (channels/reports/thresholds/expectSaveSuccess), fillStep3-Kommentar aktualisiert,
  Migration AC#8+AC#11 in trip-wizard-shell.spec.ts, 27 Acceptance Criteria,
  Datei-Liste (4 NEU + 6 EDIT), Known Limitations (Edit-Pfad-Bruch, SMS-Pipeline,
  Schwellwert-Bereichs-Validierung), Not-In-Scope, Master-Spec-Changelog-Eintrag.
  Status stub -> draft, Version 0.1 -> 1.0.
- 2026-05-09: Stub angelegt (Phase 3 der Epic-Master-Spec).
