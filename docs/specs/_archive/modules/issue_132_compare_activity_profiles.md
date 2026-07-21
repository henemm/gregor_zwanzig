---
entity_id: issue_132_compare_activity_profiles
type: module
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [compare, frontend, activity-profile, locations-rail, svelte]
---

# Issue #132 — Compare-Screen: Aktivitätsprofil-Integration

## Approval

- [ ] Approved

## Purpose

Reichert den Compare-Screen um drei zusammenhängende Aktivitätsprofil-Funktionen an: sichtbare Profil-Badges pro Location in der `LocationsRail`, ein Chip-Filter zum Einschränken der Liste auf ein Profil sowie eine automatische Profil-Vorauswahl im Vergleichs-Dropdown, wenn eine klare Mehrheit der gewählten Locations dasselbe Profil trägt. Das Ziel ist, den Nutzer bei der sinnvollen Vergleichskonfiguration zu führen, ohne manuelle Freiheit einzuschränken — die automatische Vorauswahl kann jederzeit überschrieben werden und setzt sich erst zurück, wenn sich die Locations-Auswahl ändert.

## Source

- **Files:**
  - `frontend/src/lib/components/compare/LocationsRail.svelte` (geändert)
  - `frontend/src/lib/components/compare/locationHelpers.ts` (geändert)
  - `frontend/src/routes/compare/+page.svelte` (geändert)
  - `frontend/src/lib/components/compare/PresetHeader.svelte` (geändert)
  - `frontend/e2e/compare-activity-profiles.spec.ts` (NEU)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `frontend/src/lib/utils/profileSignature.ts` | Utility (vorhanden) | Liefert `icon`, `eyebrow`, `accent` je `ActivityProfile` — wird für Badge-Icon und Chip-Label verwendet |
| `ACTIVITY_PROFILE_OPTIONS` aus `frontend/src/lib/types.ts` | TypeScript-Konstante (vorhanden) | Kanonische Profil-Liste; bestimmt die Sortier-Reihenfolge der Profile-Chips |
| `ActivityProfile` aus `frontend/src/lib/types.ts` | TypeScript-Type (vorhanden) | Typ für `activeProfile`-State und `dominantProfile`-Derived |
| `Pill` aus `frontend/src/lib/components/ui/pill/index.js` | UI-Komponente (vorhanden) | Chip-Buttons für Profil-Filter — bereits in `LocationsRail` importiert |
| `frontend/src/lib/components/compare/locationHelpers.ts` | Utility (vorhanden) | `filterLocations()` wird um den optionalen `activeProfile`-Parameter erweitert |
| `frontend/src/lib/components/compare/PresetHeader.svelte` | Svelte-Komponente (vorhanden) | Enthält das Profil-Dropdown; erhält neuen `onprofilechange`-Callback |

## Scope

**Nur Frontend.** 5 Dateien, kein Go-Backend-Eingriff:

- **Geändert:** `frontend/src/lib/components/compare/LocationsRail.svelte` (~+55 LoC)
- **Geändert:** `frontend/src/lib/components/compare/locationHelpers.ts` (~+12 LoC)
- **Geändert:** `frontend/src/routes/compare/+page.svelte` (~+25 LoC)
- **Geändert:** `frontend/src/lib/components/compare/PresetHeader.svelte` (~+3 LoC)
- **Neu:** `frontend/e2e/compare-activity-profiles.spec.ts` (~+65 LoC)

Keine Änderungen an Go-Backend, `types.ts` (das `activity_profile`-Feld ist seit Issue #247 vorhanden), oder anderen Komponenten.

## Implementation Details

### 1. locationHelpers.ts — filterLocations um `activeProfile` erweitern

Den vierten Parameter `activeProfile` mit Default `null` ergänzen. Die Funktion gibt alle Locations zurück, wenn alle drei Filter `null`/leer sind, was den Normalfall ohne extra Iteration abdeckt:

```typescript
export function filterLocations(
  locations: Location[],
  search: string,
  activeGroup: string | null,
  activeProfile: ActivityProfile | null = null,
): Location[] {
  if (search === '' && activeGroup === null && activeProfile === null) {
    return locations;
  }
  const q = search.toLowerCase();
  return locations.filter((l) => {
    const matchesSearch = search === '' || l.name.toLowerCase().includes(q) || (l.group ?? '').toLowerCase().includes(q);
    const matchesGroup = activeGroup === null || l.group === activeGroup;
    const matchesProfile = activeProfile === null || l.activity_profile === activeProfile;
    return matchesSearch && matchesGroup && matchesProfile;
  });
}
```

Alle bestehenden Aufrufe ohne das vierte Argument bleiben unverändert lauffähig (`null` als Default).

### 2. LocationsRail.svelte — activeProfile-State + profilesInLocations-Derived

Neuer State direkt neben `activeGroup`:

```typescript
let activeProfile = $state<ActivityProfile | null>(null);
```

Neues Derived, das nur Nicht-allgemein-Profile berechnet, die tatsächlich in der Locations-Liste vorkommen, und sie in einer festen Reihenfolge sortiert:

```typescript
let profilesInLocations = $derived(
  [...new Set(
    locations
      .map(l => l.activity_profile)
      .filter((p): p is ActivityProfile => Boolean(p) && p !== 'allgemein')
  )].sort((a, b) => {
    const order = ['wintersport', 'wandern', 'summer_trekking'];
    return order.indexOf(a) - order.indexOf(b);
  })
);
```

Den `filteredGrouped`-Derived aktualisieren, damit er `activeProfile` weiterreicht:

```typescript
let filteredGrouped = $derived.by(() => {
  const filtered = filterLocations(locations, search, activeGroup, activeProfile);
  // ... bestehende Gruppierungs-Logik unverändert ...
});
```

### 3. LocationsRail.svelte — Profil-Chip-UI

Unterhalb der Gruppen-Chips und oberhalb der "Alle auswählen"-Checkbox einfügen. Der Block erscheint nur, wenn `profilesInLocations.length > 0`:

```svelte
{#if profilesInLocations.length > 0}
  <div class="flex flex-wrap gap-1">
    {#each profilesInLocations as p}
      {@const sig = profileSignature(p)}
      <button
        data-testid="compare-rail-profile-chip"
        aria-label={sig.eyebrow}
        aria-pressed={activeProfile === p}
        onclick={() => (activeProfile = activeProfile === p ? null : p)}
        class="cursor-pointer"
      >
        <Pill tone={activeProfile === p ? 'accent' : 'default'}>{sig.icon} {sig.eyebrow}</Pill>
      </button>
    {/each}
  </div>
{/if}
```

Klick auf den aktiven Chip setzt `activeProfile = null` (Toggle-Verhalten, analog zum Gruppen-Chip-Filter).

### 4. LocationsRail.svelte — Profil-Badge pro Location-Zeile

In jeder Location-Zeile (sowohl in Gruppen als auch in `ungrouped`) zwischen dem Namen-`<span>` und dem Wetter-Icon-Button einfügen. Der Badge erscheint nur bei Nicht-allgemein-Profilen:

```svelte
{#if loc.activity_profile && loc.activity_profile !== 'allgemein'}
  {@const sig = profileSignature(loc.activity_profile)}
  <span title={sig.eyebrow} class="text-xs opacity-60">{sig.icon}</span>
{/if}
```

### 5. PresetHeader.svelte — onprofilechange-Callback

Neues optionales Prop `onprofilechange` ergänzen; beim `onchange`-Event des Profil-`<select>` feuern:

```typescript
interface Props {
  // ...bestehende Props unverändert...
  onprofilechange?: () => void;
}
let { ..., onprofilechange }: Props = $props();
```

```svelte
<select ... onchange={() => onprofilechange?.()}>
```

### 6. +page.svelte — dominantProfile-Derived + Auto-Select-Logik

Neuer State für das manuelle Override-Flag:

```typescript
let profileManuallyOverridden = $state(false);
```

Neues Derived, das das dominante Profil der aktuell gewählten Locations berechnet. Ein Profil gilt als dominant, wenn es auf mehr als 50 % der profilierten (nicht-allgemein) Locations zutrifft:

```typescript
let dominantProfile = $derived.by((): ActivityProfile | null => {
  const ids = allSelected ? locations.map(l => l.id) : selectedIds;
  const profiled = ids
    .map(id => locations.find(l => l.id === id)?.activity_profile)
    .filter((p): p is ActivityProfile => Boolean(p) && p !== 'allgemein');
  if (profiled.length === 0) return null;
  const counts = new Map<ActivityProfile, number>();
  for (const p of profiled) counts.set(p, (counts.get(p) ?? 0) + 1);
  const [top] = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  return top[1] / profiled.length > 0.5 ? top[0] : null;
});
```

Zwei `$effect`-Blöcke: Der erste wendet das dominante Profil an, solange kein manuelles Override aktiv ist. Der zweite setzt das Override-Flag zurück, wenn sich die Locations-Auswahl ändert:

```typescript
$effect(() => {
  if (!profileManuallyOverridden && dominantProfile && activityProfile !== dominantProfile) {
    activityProfile = dominantProfile;
  }
});

$effect(() => {
  selectedIds; allSelected; // Abhängigkeiten tracken
  profileManuallyOverridden = false;
});
```

`PresetHeader`-Einbindung mit dem neuen Callback:

```svelte
<PresetHeader
  ...
  onprofilechange={() => (profileManuallyOverridden = true)}
/>
```

### 7. E2E-Tests (compare-activity-profiles.spec.ts)

Playwright-Spec mit mindestens diesen Test-Cases:
- Badge-Sichtbarkeit für Nicht-allgemein-Profil (Selektor `data-testid="compare-rail-profile-chip"`)
- Kein Badge für allgemein/undefined
- Chip-Filter-Erscheinung nur wenn passende Profile vorhanden
- Chip-Filter filtert korrekt (Location-Zeilen-Count vor/nach Klick)
- Toggle-Verhalten des Chips (zweiter Klick hebt Filter auf)
- Auto-Profil-Select bei klarer Mehrheit (Dropdown-Wert nach Auswahl prüfen)
- Kein Auto-Profil bei 50/50-Verteilung
- Manuelles Override bleibt bestehen (nach Dropdown-Änderung bleibt Wert)
- Override-Reset bei Auswahl-Änderung (nach `selectedIds`-Änderung greift Auto-Logik erneut)

## Expected Behavior

- **Input (filterLocations):** `locations[]`, `search: string`, `activeGroup: string | null`, `activeProfile: ActivityProfile | null` — alle außer `locations` können leer/null sein
- **Output (filterLocations):** Gefiltertes `Location[]`; bei allen Filtern leer/null wird das Original-Array direkt zurückgegeben (keine Kopie)
- **Input (LocationsRail):** Unverändertes Props-Interface aus Issue #249; `locations` enthält `activity_profile` je Location
- **Output (LocationsRail):** Gefilterte, gruppierte Locations-Liste mit Profil-Chips und Badges; kein eigener API-Aufruf
- **Input (+page.svelte):** `selectedIds`, `allSelected`, `locations` — vorhandene State-Variablen
- **Output (+page.svelte):** `activityProfile` wird automatisch gesetzt, wenn `dominantProfile !== null && !profileManuallyOverridden`
- **Side effects:** Keine neuen API-Aufrufe; `profileManuallyOverridden` wird durch `$effect` verwaltet und ist nicht persistent

## Acceptance Criteria

**AC-1:** Given a location with activity_profile "wintersport" exists / When the Compare sidebar renders / Then the icon from `profileSignature('wintersport').icon` appears next to that location's name with `title` attribute set to `profileSignature('wintersport').eyebrow`

**AC-2:** Given a location with activity_profile "allgemein" or no profile set / When the Compare sidebar renders / Then no profile icon badge element appears next to that location's name

**AC-3:** Given all locations have no activity_profile or only "allgemein" / When the Compare sidebar renders / Then no element with `data-testid="compare-rail-profile-chip"` is present in the DOM

**AC-4:** Given locations include some with activity_profile "wintersport" / When user clicks the Wintersport profile chip (`aria-pressed=false` → `true`) / Then only locations with `activity_profile === 'wintersport'` are shown in the sidebar list

**AC-5:** Given the Wintersport chip is active (`aria-pressed=true`) / When user clicks it again / Then `aria-pressed` returns to `false` and all locations (matching any other active filters) are shown again

**AC-6:** Given >50% of selectedIds map to locations with activity_profile "wintersport" / When selectedIds is updated to this set / Then the compare profile dropdown in PresetHeader displays "Wintersport" (auto-set via `dominantProfile` + `$effect`)

**AC-7:** Given selected locations split exactly 50/50 between "wintersport" and "wandern" / When the comparison setup renders / Then the compare profile dropdown keeps its previous value unchanged (no auto-change because neither profile exceeds 50%)

**AC-8:** Given auto-profile has set the dropdown to "Wintersport" / When user manually changes the dropdown to "Allgemein" (firing `onprofilechange`) / Then `profileManuallyOverridden` is `true` and the dropdown stays at "Allgemein" even without a selection change

**AC-9:** Given user manually set profile to "Allgemein" overriding auto-select / When user changes selectedIds to a different set / Then `profileManuallyOverridden` resets to `false` and auto-profile logic re-applies if `dominantProfile` is non-null for the new selection

## Known Limitations

- **Sortier-Reihenfolge der Profil-Chips** ist fest codiert als `['wintersport', 'wandern', 'summer_trekking']`. Falls `ACTIVITY_PROFILE_OPTIONS` neue Profile erhält, muss die `order`-Liste in `LocationsRail.svelte` manuell gepflegt werden.
- **`dominantProfile` bei 50/50** bleibt bei gleichem Zählerstand immer das erste nach `sort()` — da der Rückgabewert bei `top[1] / profiled.length > 0.5` false ist, greift die Auto-Logik gar nicht. Kein stiller Fehler.
- **Badge-Icon** basiert auf `profileSignature()` — falls diese Funktion für ein unbekanntes Profil keinen Eintrag hat, sollte sie einen Leerstring zurückgeben. Defensive Prüfung nicht explizit implementiert; bei neuen Profilen muss `profileSignature.ts` zuerst erweitert werden.

## Changelog

- 2026-06-02: AC-6–9 in separatem Wizard-Issue #547 implementiert — dies Spec bleibt der Referenz-Status für die orphaned Compare-Screen-Komponenten (AC-1–5). Wizard-Implementierung siehe `docs/specs/modules/issue_547_auto_profile_preselect.md`.
- 2026-05-20: Initial spec erstellt (Issue #132 — Compare-Screen Aktivitätsprofil-Integration).
