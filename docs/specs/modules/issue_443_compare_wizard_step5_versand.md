---
entity_id: issue_443_compare_wizard_step5_versand
type: module
created: 2026-05-29
updated: 2026-05-29
status: implemented
version: "1.0"
issue: 443
tags: [compare, wizard, step5, versand, subscriptions, frontend, svelte, epic-438]
---

# Issue #443 — Orts-Vergleich · Wizard Step 5 — Versand + Aktivierung

## Approval

- [ ] Approved

## Purpose

Implementiert Step 5 des Orts-Vergleich-Wizards als Versand- und Aktivierungs-Konfiguration: Der User wählt Kanäle (E-Mail / Signal / Telegram), stellt Horizont, Zeitfenster und Versandzeit ein und aktiviert die Subscription. Der Step schließt den Wizard-Fluss ab und ist zwingend notwendig, damit eine Subscription tatsächlich versendet werden kann — ohne valide Kanal-Auswahl und Zeitkonfiguration kann die Subscription nicht gespeichert werden.

> **Schicht-Zuordnung:** Rein Frontend (`frontend/src/`). Kein Backend-Change — das Go-Backend-Modell enthält alle benötigten Felder bereits. Neuer Werte werden über den bestehenden `PUT /api/subscriptions/{id}`-Endpunkt gespeichert.

## Source

- **NEW** `frontend/src/lib/components/compare/steps/Step5Versand.svelte` — Step-Komponente (~130 LoC): Kanal-Toggles, Kontaktinfo-Anzeige, Horizont-Dropdown, Zeitfenster-Inputs, Versandzeit-Toggle, Inline-Fehler, Aktivierungs-Banner
- **UPDATE** `frontend/src/lib/components/compare/compareWizardState.svelte.ts` — 10 neue `$state`-Felder, Getter `canAdvanceStep5`, `canAdvanceCurrent` case 5 (~50 LoC)
- **UPDATE** `frontend/src/lib/components/compare/CompareWizard.svelte` — Step-5-Branch im Render-Switch, Import `Step5Versand`, Activate-Button-Disabled-Logik (~10 LoC)
- **UPDATE** `frontend/src/routes/compare/new/+page.server.ts` — `Promise.all([locationsRes, profileRes])`, Profil fail-soft (~15 LoC)
- **UPDATE** `frontend/src/routes/compare/new/+page.svelte` — `setContext('compare-wizard-profile', data.profile ?? null)` (~5 LoC)
- **UPDATE** `frontend/src/routes/compare/[id]/edit/+page.server.ts` — Profil-Fetch ergänzen, fail-soft (~15 LoC)
- **UPDATE** `frontend/src/routes/compare/[id]/edit/+page.svelte` — `setContext` + 10 State-Felder aus `data.subscription` prefüllen (~25 LoC)
- **NEW** `frontend/src/lib/components/compare/__tests__/issue_443_step5.test.ts` — Source-inspection Tests (node:test, keine Mocks) (~30 LoC)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ChannelToggle.svelte` (`frontend/src/lib/components/trip-wizard/steps/ChannelToggle.svelte`) | intern | Wiederverwendbare Toggle-Komponente für E-Mail/Signal/Telegram — Cross-Folder-Import |
| `maskPhone()` (`frontend/src/lib/components/trip-wizard/wizardHelpers.ts`) | intern | Maskiert Telefonnummern für Kontaktinfo-Anzeige im UI |
| `compareWizardState.svelte.ts` (`frontend/src/lib/components/compare/compareWizardState.svelte.ts`) | intern | Zentraler Wizard-State; wird durch 10 neue Versand-Felder und Getter `canAdvanceStep5` erweitert |
| `CompareWizard.svelte` (`frontend/src/lib/components/compare/CompareWizard.svelte`) | intern | Shell-Komponente, die Step 5 im Render-Switch einbindet und den Activate-Button steuert |
| `getContext('compare-wizard-profile')` (SvelteKit Context API) | intern | Liefert Profil-Kontaktdaten (`mail_to`, `signal_phone`, `telegram_chat_id`) aus dem SSR-Loader |
| `/api/auth/profile` (Go-API, `internal/handler/auth.go`) | intern | Profil-Endpoint — liefert `{ mail_to, signal_phone, telegram_chat_id }`, fail-soft wenn nicht erreichbar |
| `PUT /api/subscriptions/{id}` (`internal/handler/subscription.go`) | intern | Full-Replace — speichert alle 10 neuen Versand-Felder beim Aktivieren/Speichern |
| `+page.server.ts` (new + edit) | intern | SSR-Loader — muss Profil via `Promise.all` parallel zu Locations laden und als `data.profile` liefern |
| `$app/navigation` → `goto` | intern | Navigation zu `/compare` nach erfolgreichem Aktivieren (Create-Modus) |
| `Subscription` Interface (`frontend/src/lib/types.ts`) | intern | Typdefinition — muss `send_email`, `send_signal`, `send_telegram`, `forecast_hours`, `time_window_start`, `time_window_end`, `schedule`, `weekday`, `include_hourly`, `top_n` enthalten |

## Implementation Details

### §1 Neue State-Felder in `compareWizardState.svelte.ts`

```ts
// Neue $state-Felder (Defaults entsprechen Backend-Defaults):
sendEmail: boolean = true;
sendSignal: boolean = false;
sendTelegram: boolean = false;
timeWindowStart: number = 9;
timeWindowEnd: number = 16;
forecastHours: number = 48;
schedule: 'daily_morning' | 'daily_evening' | 'weekly' = 'daily_morning';
weekday: number = 0;
includeHourly: boolean = false;
topN: number = 3;

// Neuer Getter:
get canAdvanceStep5(): boolean {
  return this.sendEmail || this.sendSignal || this.sendTelegram;
}

// canAdvanceCurrent case 5:
case 5: return this.canAdvanceStep5;
```

`save()` und `toggleEnabled()` lesen diese State-Felder statt hartcodierter Werte.

### §2 `Step5Versand.svelte` — Aufbau

**Context lesen:**
```ts
import { getContext } from 'svelte';
const profile = getContext('compare-wizard-profile'); // { mail_to?, signal_phone?, telegram_chat_id? } | null
```

**Kanal-Toggles + Kontaktinfo:**
- `<ChannelToggle>` für E-Mail: `bind:checked={state.sendEmail}`, darunter `profile?.mail_to` (maskiert)
- `<ChannelToggle>` für Signal: `bind:checked={state.sendSignal}`, darunter `maskPhone(profile?.signal_phone)`
- `<ChannelToggle>` für Telegram: `bind:checked={state.sendTelegram}`, darunter `profile?.telegram_chat_id`
- Inline-Error `data-testid="compare-step5-channel-error"`: sichtbar wenn `!state.canAdvanceStep5`

**Horizont-Dropdown:**
```svelte
<select data-testid="compare-step5-forecast-hours" bind:value={state.forecastHours}>
  <option value={24}>24 Stunden</option>
  <option value={48}>48 Stunden</option>
  <option value={72}>72 Stunden</option>
</select>
```

**Zeitfenster Von/Bis:**
```svelte
<input type="number" min="0" max="23" data-testid="compare-step5-time-window-start"
  bind:value={state.timeWindowStart} />
<input type="number" min="0" max="23" data-testid="compare-step5-time-window-end"
  bind:value={state.timeWindowEnd} />
```
Inline-Error `data-testid="compare-step5-time-overlap-error"`: sichtbar wenn `state.timeWindowStart >= state.timeWindowEnd`.

**Versandzeit-Toggle (Morning / Evening):**
```svelte
<!-- Zwei Buttons, aktiv-Styling über CSS wenn schedule === Wert -->
<button data-testid="compare-step5-schedule"
  on:click={() => state.schedule = 'daily_morning'}>Morgen (07:00)</button>
<button on:click={() => state.schedule = 'daily_evening'}>Abend (18:00)</button>
```

**Aktivierungs-Banner (nur Create-Modus):**
```svelte
{#if !state.isEditMode}
  <div data-testid="compare-step5-activation-banner"
       style:background="var(--g-good)">
    Nach dem Aktivieren erhältst du ab dem nächsten Versandzeitpunkt automatisch Berichte.
  </div>
{/if}
```

**TestID-Container:**
```svelte
<div data-testid="compare-wizard-step-5">
  <!-- gesamter Step-Inhalt -->
</div>
```

### §3 `CompareWizard.svelte` — Step-5-Integration

```svelte
{:else if state.currentStep === 5}
  <Step5Versand />
```

Activate-Button im Create-Footer:
```svelte
<Btn variant="accent"
  disabled={!state.canAdvanceStep5 || state.saveStatus === 'saving'}
  on:click={handleActivate}>
  Aktivieren
</Btn>
```

`handleActivate` ruft `state.save()` auf und navigiert danach via `goto('/compare')`.

### §4 SSR-Loader-Änderungen (`+page.server.ts`, Create + Edit)

```ts
// Profil fail-soft laden:
const [locationsRes, profileRes] = await Promise.all([
  fetch('/api/locations', { headers }),
  fetch('/api/auth/profile', { headers }).catch(() => null),
]);
const profile = profileRes?.ok ? await profileRes.json() : null;
return { locations, profile };
```

### §5 Edit-Modus: Prefill aus Subscription

In `+page.svelte` (edit) werden die 10 Felder aus `data.subscription` in den Wizard-State übernommen:
```ts
state.sendEmail = data.subscription.send_email ?? true;
state.sendSignal = data.subscription.send_signal ?? false;
state.sendTelegram = data.subscription.send_telegram ?? false;
state.timeWindowStart = data.subscription.time_window_start ?? 9;
state.timeWindowEnd = data.subscription.time_window_end ?? 16;
state.forecastHours = data.subscription.forecast_hours ?? 48;
state.schedule = data.subscription.schedule ?? 'daily_morning';
state.weekday = data.subscription.weekday ?? 0;
state.includeHourly = data.subscription.include_hourly ?? false;
state.topN = data.subscription.top_n ?? 3;
```

### §6 LoC-Schätzung

| Datei | Änderung | LoC |
|-------|----------|-----|
| `Step5Versand.svelte` | Neue Komponente | ~130 |
| `compareWizardState.svelte.ts` | 10 Felder + Getter | ~50 |
| `CompareWizard.svelte` | Step-5-Branch + Activate-Button | ~10 |
| `compare/new/+page.server.ts` | Promise.all + Profil | ~15 |
| `compare/new/+page.svelte` | setContext | ~5 |
| `compare/[id]/edit/+page.server.ts` | Profil-Fetch | ~15 |
| `compare/[id]/edit/+page.svelte` | setContext + Prefill | ~25 |
| `issue_443_step5.test.ts` | Source-inspection Tests | ~30 |
| **Summe** | | **~280 LoC** |

LoC-Override vor Implementierungsstart: `workflow.py set-field loc_limit_override 350`

## Expected Behavior

- **Input:**
  - `data.profile` aus SSR-Loader (`mail_to`, `signal_phone`, `telegram_chat_id` — nullable, fail-soft)
  - User-Interaktionen: Kanal-Toggles, Horizont-Dropdown, Zeitfenster-Inputs, Versandzeit-Toggle
  - `state.isEditMode` (bool) — steuert Aktivierungs-Banner-Sichtbarkeit
  - Im Edit-Modus: `data.subscription` mit allen 10 Versand-Feldern zum Prefill
- **Output:**
  - Gerenderte Step-5-Oberfläche mit allen Steuerelementen
  - `state.canAdvanceStep5` steuert Activate-Button-Zustand in `CompareWizard.svelte`
  - Nach Aktivieren (Create): `goto('/compare')` — Redirect zur Übersichtsseite
  - Nach Speichern (Edit): bestehender Wizard-Save-Flow ohne Redirect-Änderung
- **Side effects:**
  - `PUT /api/subscriptions/{id}` beim Speichern/Aktivieren mit allen 10 neuen Feldern
  - Kein separater API-Call beim Rendern (Profil kommt aus SSR)

## Acceptance Criteria

**AC-1:** Given der Wizard-State hat `sendEmail=true`, `sendSignal=false`, `sendTelegram=false` / When Step 5 gerendert wird / Then ist der E-Mail-Toggle aktiv, Signal- und Telegram-Toggle inaktiv, und kein Channel-Error (`data-testid="compare-step5-channel-error"`) ist sichtbar.
  - Test: (populated after /tdd-red)

**AC-2:** Given alle drei Kanal-Toggles werden deaktiviert (`sendEmail=false`, `sendSignal=false`, `sendTelegram=false`) / When der State aktualisiert wird / Then wird der Inline-Error `data-testid="compare-step5-channel-error"` sichtbar, und `state.canAdvanceStep5` gibt `false` zurück, sodass der Activate-Button in `CompareWizard.svelte` `disabled` ist.
  - Test: (populated after /tdd-red)

**AC-3:** Given `timeWindowStart=9` und `timeWindowEnd=16` / When der User `timeWindowStart` auf 17 ändert (größer als `timeWindowEnd=16`) / Then wird der Inline-Error `data-testid="compare-step5-time-overlap-error"` sichtbar mit einer Meldung zum ungültigen Zeitfenster.
  - Test: (populated after /tdd-red)

**AC-4:** Given das Horizont-Dropdown `data-testid="compare-step5-forecast-hours"` ist gerendert / When der User einen Wert wählt / Then sind genau die Optionen 24h, 48h und 72h verfügbar, und `state.forecastHours` wird auf den gewählten Wert gesetzt.
  - Test: (populated after /tdd-red)

**AC-5:** Given `state.schedule='daily_morning'` / When der User den Abend-Toggle klickt (`data-testid="compare-step5-schedule"`) / Then wechselt `state.schedule` auf `'daily_evening'`; bei erneutem Klick auf Morgen wechselt er zurück auf `'daily_morning'`.
  - Test: (populated after /tdd-red)

**AC-6:** Given der Wizard läuft im Create-Modus (`state.isEditMode=false`) / When Step 5 gerendert wird / Then ist der Aktivierungs-Banner `data-testid="compare-step5-activation-banner"` sichtbar mit `background: var(--g-good)`.
  - Test: (populated after /tdd-red)

**AC-7:** Given der Wizard läuft im Edit-Modus (`state.isEditMode=true`) und `data.subscription` enthält alle 10 Versand-Felder / When Step 5 gerendert wird / Then ist der Aktivierungs-Banner `data-testid="compare-step5-activation-banner"` NICHT sichtbar, und alle State-Felder sind mit den Subscription-Werten vorbelegt (z.B. `state.sendEmail === data.subscription.send_email`).
  - Test: (populated after /tdd-red)

**AC-8:** Given Step 5 ist vollständig ausgefüllt (mindestens ein Kanal aktiv, kein Zeitfenster-Overlap) und der User befindet sich im Create-Modus / When der Activate-Button geklickt wird / Then wird `PUT /api/subscriptions/{id}` mit allen 10 Versand-Feldern aufgerufen, danach navigiert die App zu `/compare`.
  - Test: (populated after /tdd-red)

**AC-9:** Given `data.profile` ist `null` (Profil-Fetch fehlgeschlagen) / When Step 5 gerendert wird / Then werden die Kanal-Toggles ohne Kontaktinfo-Unter-Text gerendert — kein Fehler, kein Crash; der Step bleibt vollständig bedienbar.
  - Test: (populated after /tdd-red)

**AC-10:** Given `data.profile` enthält `signal_phone="+491234567890"` / When Step 5 gerendert wird / Then wird die Nummer maskiert angezeigt (via `maskPhone()`) — nicht im Klartext, z.B. als `+49 *** *** 7890`.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein `weekly`-Schedule im UI:** Das Backend-Feld `schedule` kennt auch `'weekly'`, das UI bietet nur `'daily_morning'` und `'daily_evening'`. `weekday` ist State-Feld für spätere Erweiterung — kein UI-Element in diesem Issue.
- **`includeHourly` und `topN` ohne UI-Elemente:** Beide Felder werden als State geführt und im `save()`-Aufruf mitgesendet, aber nicht als sichtbare Steuerelemente in Step 5 angeboten. Defaults: `includeHourly=false`, `topN=3`.
- **Profil fail-soft ohne Hinweis:** Fehlt das Profil, sieht der User keine Kontaktinfo-Anzeige unter den Toggles. Es wird kein expliziter Hinweis gegeben, dass die Kontaktdaten nicht geladen werden konnten. Erweiterung ggf. in Folge-Issue.
- **Kein Mobile-Layout:** Diese Seite ist ein Desktop-Planungstool. Mobile-Optimierung ist kein Scope von #443.
- **Keine Backend-Validierung im Frontend dupliziert:** `forecast_hours ∈ {24, 48, 72}` und `schedule ∈ {'daily_morning', 'daily_evening', 'weekly'}` sind durch Dropdown/Toggle strukturell erzwungen — keine explizite Validator-Funktion nötig.

## Changelog

- 2026-05-29: Initial spec — Issue #443. Step 5 des Orts-Vergleich-Wizards: Versand-Kanal-Auswahl, Horizont, Zeitfenster, Morning/Evening-Toggle, Aktivierungs-Banner. 8 Dateien (~280 LoC), rein Frontend, kein Backend-Change. Teil von Epic #438.
