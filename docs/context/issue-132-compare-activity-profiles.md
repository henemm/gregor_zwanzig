# Context: Issue #132 — Ortsvergleich auf Aktivitätsprofile abstimmen

## Request Summary

Der Compare-Screen hat ein globales Aktivitätsprofil-Dropdown (z.B. "Wintersport", "Wandern"). Locations können ebenfalls ein Aktivitätsprofil gespeichert haben. Beide Welten sind derzeit nicht verbunden: Ein User, der nur Wintersport-Locations auswählt, muss das Profil im Dropdown manuell setzen; die LocationsRail zeigt keine Profil-Indikatoren. Issue #132 verlangt, beide Dimensionen zu verbinden.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/compare/+page.svelte` | Compare-Page: hält `activityProfile` State, leitet an PresetHeader + CompareMatrix weiter |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | Sidebar mit Location-Checkboxen; hat Gruppen-Chip-Filter, aber keine Profil-Anzeige/-Filter |
| `frontend/src/lib/components/compare/PresetHeader.svelte` | Steuerungs-Card: Datum, Zeitfenster, Profil-Dropdown, Run-Button |
| `frontend/src/lib/components/compare/CompareMatrix.svelte` | Vergleichsmatrix: PROFILE_METRICS map steuert welche Metriken je Profil gezeigt werden |
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | 3-Schritt-Wizard: Step 3 setzt `activity_profile` bei neuer Location |
| `frontend/src/lib/types.ts:71` | `ActivityProfile` Typ + `ACTIVITY_PROFILE_OPTIONS` Array + `toCompareProfile()` Adapter |
| `internal/model/location.go` | Go-Struct: `ActivityProfile *string` (optional, omitempty) |
| `internal/compare/scoring.go` | 4 Profil-Gewichtungen; `wandern` → `ALPINE_TOURING` im Adapter |

## Existing Patterns

- **Gruppen-Chip-Filter** in LocationsRail: Klick auf Gruppen-Chip → zeigt nur Locations dieser Gruppe. Analoges Pattern wäre für Profile anwendbar.
- **`toCompareProfile()` Adapter** (types.ts:251): Übersetzt Frontend-Enum (`wandern`) → Go-Engine-Enum (`ALPINE_TOURING`). Muss bei neuen Profil-Nutzungen konsistent verwendet werden.
- **`ACTIVITY_PROFILE_OPTIONS`** (types.ts:73): Kanonische Liste aller Profile mit Label — Single Source of Truth für Dropdowns und Badges.
- **Reaktive State-Ableitung** (`$derived.by()`): Pattern in der Page für groupedLocations — für automatische Profil-Erkennung aus selectedIds verwendbar.

## Dependencies

- **Upstream:** `Location.activity_profile` (optional, kann `undefined` sein) — nicht alle Locations haben ein Profil
- **Downstream:** `activityProfile` State in `+page.svelte` → fließt in `runComparison()` → POST `/api/compare/run` → Go-Engine Scoring
- **Keine Backend-Änderungen nötig:** Profil-Logik ist rein Frontend-seitig

## Profil-Mapping (Achtung: Semantik!)

`wandern` → `ALPINE_TOURING` (Go-Engine) — das ist die aktuelle Implementierung. Alpine Touring bedeutet Skitour/Hochtour, nicht normales Wandern. Diese Mapping-Inkonsistenz ist bekannt aber nicht Teil von Issue #132.

## Feature-Analyse: Was Issue #132 braucht

### 1. Profil-Badges in LocationsRail (visuell)
Neben jeder Location in der Sidebar ein kleines Icon/Label mit dem gespeicherten Aktivitätsprofil zeigen, z.B.:
- "⛷ Wintersport" als Pill-Badge
- Nur wenn `activity_profile` gesetzt — keine leere Anzeige bei undefined

### 2. Profil-Chip-Filter in LocationsRail (Interaktion)
Analog zum bestehenden Gruppen-Chip-Filter: Profil-Chips oben in der Sidebar, Klick filtert die Location-Liste. Wenn User auf "Wintersport" klickt, sieht er nur Locations mit `activity_profile === 'wintersport'`.

### 3. Auto-Profil-Selektion (smarte Verknüpfung)
Wenn die ausgewählten Locations mehrheitlich ein Profil teilen, setzt die Seite das Compare-Profil-Dropdown automatisch. Kandidaten-Formel:
- `dominantProfile(selectedIds, locations)`: zählt Profile der ausgewählten Locations → wenn >50% ein Profil → return that profile, else 'allgemein'
- Wird als `$derived` auf Basis von `selectedIds` + `locations` berechnet
- User kann das Dropdown danach manuell überschreiben (kein Lock)

## Welche Variante macht Sinn?

Alle drei Varianten zusammen ergeben das vollständige Feature. Variante 3 (Auto-Select) ist der Kern des Issues ("abstimmen" = angleichen/synchronisieren). Variante 1+2 sind die visuelle Infrastruktur dafür.

## Existing Specs

- `docs/specs/modules/issue_249_locations_rail.md` — LocationsRail-Spec (Gruppen-Filter, Suche)
- `docs/specs/modules/issue_250_compare_engine.md` — Compare-Engine (Profil-Scoring-Gewichtungen)
- `docs/specs/modules/issue_251_compare_main_stage.md` — Compare-Hauptbühne (PresetHeader, CompareMatrix)

## Risks & Considerations

- **Locations ohne Profil**: `activity_profile` ist optional. Auto-Select darf nicht crashen bei `undefined`.
- **Profile-Mischung**: Wenn User 2 Wintersport + 2 Wandern-Locations auswählt → kein eindeutiges Profil → 'allgemein' beibehalten. Kein Autozwang.
- **User-Override respektieren**: Auto-Select setzt Profil nur wenn es sich aus Selection eindeutig ergibt. Manuelle Änderung im Dropdown darf nicht durch Selection-Change überschrieben werden (nach manuellem Override: kein Auto mehr für diese Session oder bis Selection sich ändert).
- **LocationsRail ist presentational**: Neue Profil-Filter-State muss in die Page-Logik oder als lokaler State in LocationsRail — analog zu `search` und `activeGroup` die bereits lokal sind.
- **Kein Backend**: Rein Frontend — kein Go/Python-Change nötig.
