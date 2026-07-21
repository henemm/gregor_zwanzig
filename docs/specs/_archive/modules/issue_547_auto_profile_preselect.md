---
entity_id: issue_547_auto_profile_preselect
type: module
created: 2026-06-02
updated: 2026-06-02
status: draft
version: "1.0"
tags: [compare, frontend, wizard, activity-profile, auto-select, svelte]
---

# Issue #547 — Auto-Profil-Vorauswahl im Compare-Wizard (AC-6–9)

## Approval

- [ ] Approved

## Purpose

Ergänzt den Compare-Wizard um die fehlende automatische Profil-Vorauswahl (AC-6 bis AC-9 aus der ursprünglichen Spec `issue_132_compare_activity_profiles.md`). Wenn der Nutzer in Step 2 Locations auswählt und davon mehr als 50 % dasselbe Aktivitätsprofil tragen, wird das Profil in Step 1 automatisch gesetzt — solange der Nutzer es nicht zuvor manuell überschrieben hat. Ein manuelles Override bleibt bestehen, bis der Nutzer die Location-Auswahl ändert.

## Source

- **Geändert:** `frontend/src/lib/components/compare/CompareWizard.svelte`
- **Geändert:** `frontend/src/lib/components/compare/steps/Step1Vergleich.svelte`
- **Neu:** `frontend/src/lib/components/compare/__tests__/issue_547_auto_profile_preselect.test.ts`
- **Ersetzt:** `frontend/e2e/compare-activity-profiles.spec.ts` (komplett neu für Wizard-Flow)

## Dependencies

| Abhängigkeit | Art | Zweck |
|---|---|---|
| `CompareWizardState` aus `compareWizardState.svelte.ts` | State-Klasse (vorhanden) | `activityProfile`, `pickedIds`, `idealRanges` |
| `ActivityProfile` aus `$lib/types` | TypeScript-Type (vorhanden) | Typ für `dominantProfile` |
| `locations: Location[]` in `CompareWizard.svelte` | Prop (vorhanden) | Basis für dominantProfile-Berechnung |

## Scope

**Nur Frontend.** 4 Dateien, kein Go-Backend-Eingriff:

- **Geändert:** `CompareWizard.svelte` (~+28 LoC)
- **Geändert:** `Step1Vergleich.svelte` (~+6 LoC)
- **Neu:** `issue_547_auto_profile_preselect.test.ts` (~+80 LoC)
- **Ersetzt:** `compare-activity-profiles.spec.ts` (~+120 LoC)

## Implementation Details

### 1. Step1Vergleich.svelte — onManualProfileChange Callback

Neues optionales Prop `onManualProfileChange`:

```typescript
interface Props {
  onManualProfileChange?: () => void;
}
let { onManualProfileChange }: Props = $props();
```

In `handleProfileSelect` nach `state.activityProfile = value` aufrufen:

```typescript
function handleProfileSelect(value: ActivityProfile) {
  if (Object.keys(state.idealRanges).length > 0 && value !== state.activityProfile) {
    if (!confirm('Aktivitätsprofil wechseln? Deine Idealwert-Einstellungen werden zurückgesetzt.')) {
      return;
    }
    state.idealRanges = {};
  }
  state.activityProfile = value;
  onManualProfileChange?.();
}
```

Der Callback wird **nur** bei Nutzer-Tile-Klick gefeuert. Auto-Set durch `$effect` schreibt `wiz.activityProfile` direkt — ruft `handleProfileSelect` nicht auf — löst keinen Dialog und keinen Callback aus.

### 2. CompareWizard.svelte — dominantProfile + $effects

Import ergänzen:

```typescript
import type { ActivityProfile, Location } from '$lib/types';
```

Neue State/Derived-Variablen und Effekte nach den bestehenden Variablen:

```typescript
// AC-8: Override-Flag — true wenn Nutzer das Profil manuell gewählt hat
let profileManuallyOverridden = $state(false);

// AC-6/7: dominantProfile — Profil das >50% der ausgewählten Locations trägt
const dominantProfile = $derived.by((): ActivityProfile | null => {
  const profiled = wiz.pickedIds
    .map((id) => locations.find((l) => l.id === id)?.activity_profile)
    .filter((p): p is ActivityProfile => Boolean(p) && p !== 'allgemein');
  if (profiled.length === 0) return null;
  const counts = new Map<ActivityProfile, number>();
  for (const p of profiled) counts.set(p, (counts.get(p) ?? 0) + 1);
  const [top] = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  return top[1] / profiled.length > 0.5 ? top[0] : null;
});

// AC-6: Auto-Apply — nur wenn kein Override und keine Idealwerte bereits konfiguriert
$effect(() => {
  if (
    !profileManuallyOverridden &&
    dominantProfile &&
    wiz.activityProfile !== dominantProfile &&
    Object.keys(wiz.idealRanges).length === 0
  ) {
    wiz.activityProfile = dominantProfile;
  }
});

// AC-9: Override-Reset bei pickedIds-Änderung
$effect(() => {
  wiz.pickedIds; // Abhängigkeit tracken
  profileManuallyOverridden = false;
});

function handleManualProfileChange() {
  profileManuallyOverridden = true;
}
```

Step1-Einbindung im Template aktualisieren:

```svelte
{#if wiz.currentStep === 1}
  <Step1Vergleich onManualProfileChange={handleManualProfileChange} />
```

### 3. Unit-Tests (Source-Inspection)

Die Testdatei `issue_547_auto_profile_preselect.test.ts` prüft via Source-Inspection (gleiche Technik wie alle anderen `__tests__/issue_*.test.ts`):

- `CompareWizard.svelte` enthält `profileManuallyOverridden` als `$state`
- `CompareWizard.svelte` enthält `dominantProfile` als `$derived.by`
- `CompareWizard.svelte` enthält zwei `$effect`-Blöcke mit den richtigen Abhängigkeiten
- `CompareWizard.svelte` übergibt `onManualProfileChange` an `Step1Vergleich`
- `Step1Vergleich.svelte` deklariert `onManualProfileChange` im Props-Interface
- `Step1Vergleich.svelte` ruft `onManualProfileChange?.()` in `handleProfileSelect` auf

### 4. E2E-Tests (Wizard-Flow)

Die Datei `compare-activity-profiles.spec.ts` wird komplett neu geschrieben für den Wizard-Flow. AC-1–5 entfallen aus diesem File (die Komponenten sind orphaned und werden in einer separaten Maßnahme eingebunden). Fokus: AC-6 und AC-8.

Aufbau:
- `test.beforeEach`: Login + `/compare/new`
- Step 1: Name eingeben, Weiter
- Step 2: Locations auswählen (Wintersport-Mehrheit via `compare-step2-library`)
- Zurück zu Step 1 (Footer-Button `compare-wizard-footer-prev`)
- Assert: Wintersport-Tile ist aktiv (`compare-step1-tile-wintersport` hat border-accent-Klasse)

## Expected Behavior

- **Normalfall (neu):** Nutzer wählt in Step 2 mehrheitlich Wintersport-Locations → beim Wechsel zu Step 1 ist Wintersport-Tile aktiv
- **50/50:** Kein Auto-Set, Profil bleibt unverändert
- **Manuelle Überschreibung:** Nutzer klickt in Step 1 auf Wandern → Override-Flag gesetzt → auch bei weiterer pickedIds-Stabilität bleibt Wandern
- **Override-Reset:** Nutzer wechselt zurück zu Step 2 und ändert Auswahl → Override-Flag zurückgesetzt → Auto-Set greift wieder
- **Edit-Modus mit Idealwerten:** Bereits konfigurierte Idealwerte (Step 3) blockieren Auto-Set — kein ungewollter Profil-Wechsel

## Acceptance Criteria

**AC-6:** Given >50% der pickedIds zeigen auf Locations mit activity_profile "wintersport" / When pickedIds sich ändert (durch Nutzer-Klick in Step 2) / Then wiz.activityProfile wird auf "wintersport" gesetzt (via $effect Auto-Apply), sofern profileManuallyOverridden false ist und idealRanges leer sind

**AC-7:** Given pickedIds enthält genau 1 "wintersport"- und 1 "wandern"-Location (50/50) / When der Wizard rendert / Then wiz.activityProfile bleibt unverändert — kein Auto-Set, weil kein Profil >50% hat

**AC-8:** Given Auto-Set hat wiz.activityProfile auf "wintersport" gesetzt / When Nutzer in Step 1 das Wandern-Tile klickt (onManualProfileChange wird gefeuert) / Then profileManuallyOverridden ist true und wiz.activityProfile bleibt auf "wandern" auch wenn dominantProfile weiterhin "wintersport" ist

**AC-9:** Given profileManuallyOverridden ist true nach manuellem Override / When wiz.pickedIds sich ändert (Nutzer in Step 2 fügt/entfernt Location) / Then profileManuallyOverridden wird auf false zurückgesetzt und der Auto-Apply-$effect kann beim nächsten dominantProfile-Wechsel erneut greifen

## Known Limitations

- **AC-1–5 bleiben orphaned:** Die Badges und Chips in `LocationsRail.svelte` sind implementiert aber nicht in eine aktive Route eingebunden. Das wird in einem separaten Issue adressiert.
- **E2E-Tests für AC-7/9 als reine Unit-Tests:** Echte Location-Testdaten in der E2E-Umgebung haben keine garantierte Profil-Verteilung — AC-7 und AC-9 werden via Source-Inspection-Tests abgedeckt.
- **Auto-Set blockiert bei vorhandenen Idealwerten:** Im Edit-Modus mit bereits konfigurierten Idealwerten findet kein Auto-Set statt. Dies ist eine bewusste Entscheidung zum Schutz bestehender Konfigurationen.

## Changelog

- 2026-06-02: Spec erstellt (Issue #547 — fehlende AC-6–9 aus issue_132_compare_activity_profiles.md).
