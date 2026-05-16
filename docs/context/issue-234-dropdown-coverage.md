# Context: Issue #234 — Dropdown-Coverage `summer_trekking`

## Request Summary

In drei Frontend-Dropdowns fehlt die Auswahl-Option `summer_trekking`, obwohl
der kanonische `ActivityProfile`-Alias diesen Wert seit Issue #207 enthält
und das Backend ihn vollwertig akzeptiert (Issue #232: `rightColumn.ts`
Dispatch). Aufgedeckt vom Adversary-Validator während Issue #233 GREEN-
Verifikation (Findings F001/F002 — Issue #233 selbst hat den dritten
Dropdown in `compare/+page.svelte` ergänzt).

## Drei Dropdown-Stellen (alle mit identischem Bug-Muster)

| Datei | Zeilen | Persistenz-Pfad | Risiko |
|-------|--------|-----------------|--------|
| `LocationForm.svelte:137-141` | 3 Optionen | Speichert in `Location.activity_profile` | **Datenverlust** beim Edit bestehender Location mit summer_trekking |
| `SubscriptionForm.svelte:152-157` | 3 Optionen | Speichert in `Subscription.activity_profile` | **Datenverlust** beim Edit bestehender Subscription mit summer_trekking |
| `compare/+page.svelte:417-419` | 3 Optionen | Fluechtige Compare-Auswahl, nicht persistiert | UX-Luecke (kein Datenverlust) |

## Sekundär-Bugs (TypeScript-Schwächen)

| Datei | Zeile | Problem |
|-------|-------|---------|
| `SubscriptionForm.svelte:44` | `let activityProfile = $state<string>(...)` | Explizit auf `string` geweitert — umgeht `ActivityProfile`-Alias komplett, TS-Compiler erkennt zukünftige Drift nicht |
| `LocationForm.svelte:52` | `let activityProfile = $state(location?.activity_profile ?? '')` | Inferierter Typ ist `string | ActivityProfile`, expliziter Cast `as Location['activity_profile']` in Zeile 74 maskiert das |

Beide State-Variablen sollten als typisierter `ActivityProfile`-Alias deklariert
werden — sonst bleibt der nächste neue Profilwert (z.B. `'klettern'`) wieder
unsichtbar für den Compiler und reproduziert das gleiche Drift-Muster.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/LocationForm.svelte` | Dropdown + State-Variable + Save-Pfad (Zeilen 52, 74, 137-141) |
| `frontend/src/lib/components/SubscriptionForm.svelte` | Dropdown + State-Variable + Save-Pfad (Zeilen 44, 90, 152-157) |
| `frontend/src/routes/compare/+page.svelte` | Dropdown (Zeilen 417-419) — State ist seit #233 bereits `$state<ActivityProfile>` typisiert |
| `frontend/src/lib/types.ts:68` | Kanonischer `ActivityProfile`-Alias — Single Source |
| `frontend/src/lib/components/trip-wizard/wizardHelpers.ts:71-84` | `mapActivityToProfile`: Trip-Wizard mappt `trekking/hochtour/klettersteig` → `'summer_trekking'`. Trips bekommen das Profil automatisch, aber Standalone-Locations/-Subscriptions können es nur via API setzen |

## Existing Patterns

- `compare/+page.svelte:417-419` — drei Optionen ohne `summer_trekking`,
  aber `bind:value` an typisiertes `$state<ActivityProfile>`. Die HTML-Option-Liste
  ist nicht TypeScript-validiert (kein Compile-Check).
- Andere `<select>`-Stellen (z.B. Subscriptions-Schedule mit
  `daily_morning|daily_evening|weekly`) sind ebenfalls hardcodiert.
  Keine bestehende Konvention für Single-Source-Dropdown-Listen.

## Drift-Resistente Lösung (Bonus aus Spec-Empfehlung)

Const-Array mit `satisfies`-Constraint, gemeinsam für alle 3 Dropdowns:

```typescript
// types.ts oder dedicated profileOptions.ts
export const ACTIVITY_PROFILE_OPTIONS = [
  { value: 'allgemein',       label: 'Allgemein' },
  { value: 'wintersport',     label: 'Wintersport' },
  { value: 'wandern',         label: 'Wandern' },
  { value: 'summer_trekking', label: 'Sommer-Trekking' },
] as const satisfies ReadonlyArray<{ value: ActivityProfile; label: string }>;
```

Bricht zukünftiges Profil-Hinzufügen (`'klettern'` etc.) den TypeScript-Compiler
in `types.ts:68`, statt nur die UI still abweichen zu lassen.

## Dependencies

- **Upstream:** Issue #207 (strukturiertes Typing, `ActivityProfile`-Alias).
- **Upstream:** Issue #232 (`summer_trekking` als Backend-Profil aktiv).
- **Upstream:** Issue #233 (Type-Drift in `types.ts` behoben; Adversary entdeckte
  diese verbleibende Dropdown-Lücke).

## Dependents

- `Location.activity_profile`-Konsumenten: `locations/+page.svelte:149-150` (nur Badge-Anzeige, kein Bug).
- `Subscription.activity_profile`-Konsumenten: `SubscriptionForm` (selbst), keine weiteren.
- Backend akzeptiert seit jeher alle 4 Werte (validiert via `src/app/profile.py`).

## Existing Specs

- `docs/specs/modules/activity_profile.md` — Single Source des kanonischen Enums.
- `docs/specs/modules/issue_233_type_drift.md` — listet F001/F002 in Out-of-Scope: "Eigene Konsolidierung, eigener Issue."
- `docs/specs/modules/epic_136_trip_wizard.md` — Master-Spec mit `mapActivityToProfile`-Mapping.

## Risks & Considerations

- **Datenverlust-Risiko aktuell theoretisch:** `grep -r summer_trekking data/users/` liefert keine Treffer. Aber:
  - Sobald ein User via API oder via Subscription-Form-Future-Update `summer_trekking` setzt, wird der nächste UI-Edit den Wert verlieren.
  - Trip-Wizard erzeugt automatisch `aggregation.profile='summer_trekking'` für `trekking/hochtour/klettersteig`-Trips — diese Trips sind aber im `Trip`-Schema, nicht in `Location`/`Subscription`.
- **Scope-Empfehlung:** Const-Array-Lösung (1× definiert, 3× verwendet) statt 3× hardcodierte `<option>`-Listen. Investition ~5 LoC mehr, dafür drift-resistent.
- **Test-Strategie:** Pro Form-Komponente ein Component-Test (Vitest/Svelte-Testing-Library) — kein E2E nötig, weil Bug HTML-Level ist.
- **LoC-Schätzung:** ~25 LoC. Weit unter 250-Limit.
