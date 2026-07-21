---
entity_id: issue_234_dropdown_coverage
type: module
created: 2026-05-16
updated: 2026-05-16
status: draft
version: "1.0"
tags: [frontend, ux, refactor, drift, data-loss]
issue: 234
---

<!-- Issue #234 — Dropdown-Coverage: 'summer_trekking' fehlt in 3 Selects -->

# Issue #234 — Dropdown-Coverage `summer_trekking`

## Approval

- [ ] Approved

## Zweck

Drei `<select>`-Dropdowns im Frontend bieten nur 3 von 4 kanonischen
`ActivityProfile`-Werten an (`allgemein | wintersport | wandern`) — der
seit Issue #207 (Type-Alias) und Issue #232 (Backend-Dispatch) etablierte
vierte Wert `summer_trekking` fehlt:

| Dropdown | Konsequenz |
|----------|------------|
| `LocationForm.svelte:137-141` | Bestehende Location mit `activity_profile='summer_trekking'` verliert den Wert beim Edit (Datenverlust). |
| `SubscriptionForm.svelte:152-157` | Gleiches Datenverlust-Risiko für Subscriptions. |
| `compare/+page.svelte:417-419` | Flüchtige UI-Auswahl, kein Persistenz-Pfad — reine UX-Lücke. |

Zusätzlich sind zwei `$state(...)`-Variablen in den Forms nicht als
`ActivityProfile` typisiert (`SubscriptionForm.svelte:44` explizit `string`,
`LocationForm.svelte:52` implizit weit), wodurch der TypeScript-Compiler
zukünftige Drift nicht erkennt.

**Tech-Lead-Entscheidung:** Statt drei separat hardcodierte `<option>`-Listen
einführen wir eine **zentrale Konstante** mit `satisfies`-Constraint. Dadurch
bricht jede zukünftige Erweiterung von `ActivityProfile` (z.B. `'klettern'`)
den TypeScript-Compiler an einer einzigen Stelle, statt die UI still abweichen
zu lassen.

Aufgedeckt vom Adversary-Validator während Issue #233 GREEN-Verifikation
(Findings F001/F002), in `docs/specs/modules/issue_233_type_drift.md` als
Out-of-Scope für #233 dokumentiert.

## Quelle / Source

- `frontend/src/lib/types.ts` — neue exportierte Konstante `ACTIVITY_PROFILE_OPTIONS` direkt unter dem `ActivityProfile`-Alias (Zeile 68)
- `frontend/src/lib/components/LocationForm.svelte` (Zeilen 52, 137-141) — State-Typing + Dropdown
- `frontend/src/lib/components/SubscriptionForm.svelte` (Zeilen 44, 90, 152-157) — State-Typing + Dropdown + Cast in Save-Pfad
- `frontend/src/routes/compare/+page.svelte` (Zeilen 417-419) — Dropdown (State ist seit #233 schon typisiert)

## Acceptance Criteria

- **AC-1:** Given `frontend/src/lib/types.ts` / When der Build läuft / Then exportiert die Datei eine Konstante `ACTIVITY_PROFILE_OPTIONS` vom Typ `ReadonlyArray<{ value: ActivityProfile; label: string }>` mit `as const satisfies`-Constraint, sodass Erweitern der `ActivityProfile`-Union ohne entsprechenden Array-Eintrag den TypeScript-Compiler bricht (Exhaustiveness-Check)

- **AC-2:** Given `LocationForm.svelte` / When der User eine bestehende Location mit `activity_profile='summer_trekking'` editiert und speichert ohne das Dropdown anzufassen / Then bleibt der Wert `'summer_trekking'` erhalten — keine stille Reset auf `''` oder anderen Wert

- **AC-3:** Given `SubscriptionForm.svelte` / When der User eine bestehende Subscription mit `activity_profile='summer_trekking'` editiert und speichert / Then bleibt der Wert `'summer_trekking'` erhalten, ebenso muss `'Sommer-Trekking'` als Auswahl-Option verfügbar sein

- **AC-4:** Given `compare/+page.svelte` Compare-Tool / When der User das Profil-Dropdown öffnet / Then ist `'Sommer-Trekking'` als 4. Option verfügbar und beim Auswählen wird das Compare-Result für dieses Profil korrekt vom Backend angefordert

- **AC-5:** Given die State-Variablen `activityProfile` in `LocationForm.svelte:52` und `SubscriptionForm.svelte:44` / When der Code durch svelte-check geprüft wird / Then sind beide als `ActivityProfile` (bzw. `ActivityProfile | ''` für LocationForm-Default) typisiert; die expliziten `as Subscription['activity_profile']` / `as Location['activity_profile']` Casts in den Save-Pfaden (Zeilen 74 LocationForm, 90 SubscriptionForm) sind entfernbar — der Compiler validiert die Zuweisung jetzt ohne Cast

- **AC-6:** Given die drei Dropdowns / When sie rendern / Then iterieren sie jeweils über `ACTIVITY_PROFILE_OPTIONS` (`{#each ACTIVITY_PROFILE_OPTIONS as opt}`), nicht über hardcodierte `<option>`-Listen — Single Source

- **AC-7:** Given svelte-check vor und nach den Edits / When die Anzahl Type-Errors gezählt wird / Then ist Post-Edit-Count ≤ Pre-Edit-Count — keine neuen Type-Errors entstehen

## Erwartetes Verhalten

### `types.ts` — neue Konstante (nach Zeile 68 einfügen)

```typescript
export type ActivityProfile = 'wintersport' | 'wandern' | 'allgemein' | 'summer_trekking';

export const ACTIVITY_PROFILE_OPTIONS = [
  { value: 'allgemein',       label: 'Allgemein' },
  { value: 'wintersport',     label: 'Wintersport' },
  { value: 'wandern',         label: 'Wandern' },
  { value: 'summer_trekking', label: 'Sommer-Trekking' },
] as const satisfies ReadonlyArray<{ value: ActivityProfile; label: string }>;
```

Reihenfolge: alltagstauglich (`Allgemein` als Default zuerst, dann Saison-Profile).

### `LocationForm.svelte`

```svelte
<script lang="ts">
  import type { Location, ActivityProfile } from '$lib/types.js';
  import { ACTIVITY_PROFILE_OPTIONS } from '$lib/types.js';
  // ...
  let activityProfile = $state<ActivityProfile | ''>(location?.activity_profile ?? '');
  // ...
  function save() {
    const result: Location = {
      // ...
      activity_profile: activityProfile || undefined,  // Cast entfernt
      // ...
    };
    onsave(result);
  }
</script>

<select bind:value={activityProfile} ...>
  <option value="">— Kein Profil —</option>
  {#each ACTIVITY_PROFILE_OPTIONS as opt}
    <option value={opt.value}>{opt.label}</option>
  {/each}
</select>
```

### `SubscriptionForm.svelte`

```svelte
<script lang="ts">
  import type { Subscription, ActivityProfile } from '$lib/types.js';
  import { ACTIVITY_PROFILE_OPTIONS } from '$lib/types.js';
  // ...
  let activityProfile = $state<ActivityProfile>(subscription?.activity_profile ?? 'allgemein');
  // ...
  function save() {
    const updated: Subscription = {
      // ...
      activity_profile: activityProfile,  // Cast entfernt
    };
    onsave(updated);
  }
</script>

<select bind:value={activityProfile} ...>
  {#each ACTIVITY_PROFILE_OPTIONS as opt}
    <option value={opt.value}>{opt.label}</option>
  {/each}
</select>
```

### `compare/+page.svelte`

```svelte
<script lang="ts">
  import { ACTIVITY_PROFILE_OPTIONS, type ActivityProfile, /* ... */ } from '$lib/types.js';
  // State ist seit #233 schon typisiert: $state<ActivityProfile>('allgemein')
</script>

<select id="cmp-profile" bind:value={activityProfile} ...>
  {#each ACTIVITY_PROFILE_OPTIONS as opt}
    <option value={opt.value}>{opt.label}</option>
  {/each}
</select>
```

## Out-of-Scope

- **Migration anderer Dropdown-Patterns** (z.B. Subscription-Schedule
  `daily_morning|daily_evening|weekly` hardcodiert) — nicht Teil dieses Issues.
- **Trip-Wizard-Activity-Dropdown** — verwendet `ActivityType` (skitour/trekking/...),
  nicht `ActivityProfile`. Separates Konzept, separates Schema.
- **`wizardHelpers.ts::AggregationProfile`-Alias-Konsolidierung** — eigener Tech-Debt-Issue,
  nicht hier.
- **Component-Tests für die Forms** — bisher keine Vitest-Tests für `LocationForm`/`SubscriptionForm`
  im Repo; das Schema einzuführen sprengt den Scope. Verifikation über svelte-check
  + manuelle Staging-Probe.

## Tests / Verifikation

- **svelte-check:** Keine neuen Errors, idealerweise Pre-Count ≥ Post-Count.
- **Type-Exhaustiveness-Probe (manuell):** Temporär `ActivityProfile` um
  `'klettern'` erweitern → svelte-check muss Error in `types.ts` an der
  `ACTIVITY_PROFILE_OPTIONS`-Konstanten melden. Revert nach Verifikation.
- **Staging-Manual-Test:**
  1. Subscription per API mit `activity_profile='summer_trekking'` anlegen.
  2. UI: Subscription editieren ohne Profil zu ändern → speichern.
  3. API-Read → `activity_profile` muss noch `'summer_trekking'` sein.
  Gleiche Probe für `Location`.
- **Compare-Tool:** Im Staging-UI Profil-Dropdown öffnen → `Sommer-Trekking`
  muss sichtbar und auswählbar sein.

## Risiken & Migration

- **Risiko gering:** Konstante ist neu, bestehende Werte werden lediglich
  konsistent angezeigt. Backend-Validierung bleibt unverändert.
- **Wire-Format unverändert:** API-Payloads übertragen `activity_profile`
  weiterhin als String.
- **Keine Daten-Migration nötig:** `grep -r summer_trekking data/users/`
  liefert aktuell keine Treffer — Datenverlust war bisher theoretisch.
  Der Fix schließt die Tür präventiv.
- **Drift-Resistenz dokumentiert:** Mit `satisfies`-Constraint wird der
  Compiler künftig zur Single Source of Truth für die UI-Optionen.
