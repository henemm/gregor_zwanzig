# Context: #932 — Aktivitätstyp auf ersten Screen

## Request Summary

Das Aktivitätstyp-Dropdown in der Touren-Erstellung soll auf den ersten Screen ("Route") verschoben werden. Es soll dort sofort die Wettermetriken vorauswählen. Zusätzlich ein "Speichern"-Button-Problem im Wetter-Tab beheben.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | Hauptdatei — Aktivitätstyp-Dropdown hier von "Metriken"-Tab in "Route"-Tab verschieben |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Speichern-Button in createMode ausblenden; activityType→Template-Vorauswahl |
| `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` | Referenz: so macht's der Wizard bereits (Aktivität → Wizard-State) |
| `frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte` | Referenz: Step 1 ohne Aktivitätstyp (deprecated, nicht zu ändern) |
| `src/app/metric_catalog.py` | Backend-Seite: WEATHER_TEMPLATES definiert Aktivität→Metriken-Mapping |

## Existing Patterns

**Aktivitätstyp-Dropdown in Step3Weather.svelte (Referenz):**
```svelte
const ACTIVITY_OPTIONS = [
  { value: '', label: 'Standard (kein Profil)' },
  { value: 'trekking', label: 'Alpen-Trekking' },
  ...
];
const OPTION_TO_ACTIVITY = { trekking: 'trekking', ski_touring: 'skitour', ... };
```

**Template-Vorauswahl in WeatherMetricsTab:**
`applyPreset(templateId)` wendet ein Backend-Template an (lädt via `/api/templates`).
Template-IDs: `alpen-trekking`, `wandern`, `skitouren`, `radtour`, `allgemein`, etc.

**Aktivitätstyp → Template-ID Mapping (noch nicht implementiert):**
```
trekking / hochtour / mountaineering → alpen-trekking
skiing / ski_touring                 → skitouren
hiking                               → wandern
fahrrad_* / mtb                      → radtour
'' / null                            → (kein Template)
```

**stubTrip in TripNewEditor:** `$derived<Trip>({id:'__new__', name, stages:[], display_config:{...}})`
→ wird an WeatherMetricsTab als `trip`-Prop übergeben.

**Speichern-Button in WeatherMetricsTab:**
```svelte
{#if !saveController}
    <Btn ... disabled={!isDirty}>Speichern</Btn>
{/if}
```
Im createMode immer sichtbar (nur disabled wenn nicht dirty). Fix: `!saveController && !createMode`.

## Dependencies

- **Upstream:** TripNewEditor.svelte hängt an `tripNewLogic.ts` (unlockedTabs, doneTabs)
- **Downstream:** `WeatherMetricsTab` wird auch in TripEditView und Cockpit-Detail genutzt — createMode-Bedingung darf dort nichts brechen

## Existing Specs

- `docs/specs/modules/issue_300_wizard_redesign.md` — Wizard-Redesign (Step-Layout)
- `docs/specs/modules/issue_432_step3_step5_polish.md` — Step3-Weather-Umbau (Referenz für Aktivitätsprofil)

## Risks & Considerations

1. **WeatherMetricsTab createMode-Änderung** betrifft auch andere Aufrufer von WeatherMetricsTab — aber `createMode` wird nur in TripNewEditor auf `true` gesetzt, alle anderen Stellen sind `false` (Default). Kein Regress.
2. **Reaktivität**: Wenn User Aktivitätstyp wählt, dann zum Metriken-Tab wechselt → der $effect muss nach Template-Load feuern, nicht vorher.
3. **Idempotenz**: Template-Vorauswahl nur wenn `!isDirty` UND keine bestehenden Metriken (neue Tour). Nicht auf schon angepasste Metriken drüberfahren.
4. **Mobile + Desktop**: In TripNewEditor gibt es zwei Renderäste (`.tn-desktop`, `.tn-mobile`) — Dropdown an beiden Stellen verschieben.
5. **Keine Breaking Change**: `activityType` wird als optionale Erweiterung des `stubTrip`-Objekts mitgegeben — `Trip.activity` ist bereits typisiert (`activity?: string`).
