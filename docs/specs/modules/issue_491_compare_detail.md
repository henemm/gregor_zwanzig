---
entity_id: issue_491_compare_detail
type: module
created: 2026-05-31
updated: 2026-05-31
status: implemented
version: "1.0"
issue: 491
tags: [compare, frontend, svelte, detail-page, backend, go, epic-485]
---

# Issue #491 — Orts-Vergleich Detail-Seite `/compare/[id]`

## Approval

- [ ] Approved

## Purpose

Implementiert die neue SvelteKit-Route `/compare/[id]` als Klick-Ziel jeder Compare-Kachel in der Übersicht. Die Seite zeigt Setup-Übersicht, Monitoring-Status und Aktionen für einen einzelnen Orts-Vergleich — ohne Tages-Briefing im Browser. Sie schließt die Navigation zwischen Übersicht und Bearbeiten-Wizard und ist Block C von Epic #485.

## Source

- **NEW:** `frontend/src/routes/compare/[id]/+page.server.ts` — SSR-Loader: lädt Preset per ID + Locations parallel, wirft 404 bei unbekannter ID (~35 LoC)
- **NEW:** `frontend/src/routes/compare/[id]/+page.svelte` — Page-Shell: Topbar, Primäraktion, delegiert Inhalt an `CompareDetail` (~40 LoC)
- **NEW:** `frontend/src/lib/components/compare/CompareDetail.svelte` — alle 5 Cards + Monitoring-Streifen, Props: `preset` + `locations` (~180 LoC)
- **EXTEND:** `internal/handler/compare_preset.go` — neuer `GetComparePresetHandler` für `GET /api/compare/presets/{id}` (~40 LoC)
- **EXTEND:** `cmd/server/main.go` — Route `r.Get("/api/compare/presets/{id}", ...)` ergänzen (~2 LoC)

> **Schicht-Zuordnung:** Frontend `frontend/src/` (SvelteKit) + Go-API `internal/handler/` + Route-Registration `cmd/server/main.go`. Kein Python-Backend-Change.

## Estimated Scope

- **LoC:** ~297
- **Files:** 5
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `GET /api/compare/presets/{id}` (`internal/handler/compare_preset.go`) | intern | Neuer Endpoint — lädt einzelnes Preset per ID für den eingeloggten User; 404 bei unbekanntem Preset |
| `GET /api/locations` (`internal/handler/location.go`) | intern | Liefert `Location[]` für den eingeloggten User; für Name/Höhen-Anreicherung der `location_ids` |
| `ComparePreset` Interface (`frontend/src/lib/types.ts:446`) | intern | TypeScript-Typ mit `id`, `name`, `location_ids`, `schedule`, `profil`, `hour_from`, `hour_to`, `empfaenger`, `letzter_versand`, `display_config` |
| `Location` Interface (`frontend/src/lib/types.ts`) | intern | TypeScript-Typ mit `id`, `name`, `elevation_m`, `region` |
| `deriveStatusFromPreset` (`frontend/src/lib/subscriptionHelpers.ts`) | intern | Ableitung `active` / `paused` / `draft` aus Preset-Feldern |
| `presetScheduleLabel` (`frontend/src/lib/subscriptionHelpers.ts`) | intern | Formatierter Versand-Zeitplan, z.B. „Täglich 06–08 Uhr" |
| `formatLastSent` (`frontend/src/lib/subscriptionHelpers.ts`) | intern | Formatiert `letzter_versand` auf „TT.MM.JJJJ" oder „Noch kein Versand" |
| `Dot`, `Pill`, `Card`, `Btn`, `Eyebrow`, `KV` (`frontend/src/lib/components/atoms/index.ts`) | intern | Atom-Komponenten für Monitoring-Streifen, Pills, Karten-Shell, Buttons |
| `DetailRow`, `ChannelRow`, `ChannelChip` (`frontend/src/lib/components/molecules/index.ts`) | intern | Molecule-Komponenten für Zeilen in den Cards |
| `CompareStatusPill` Stub | intern | Status-Badge (active/paused/draft) — #488/#489 OPEN; wird als Inline-Stub implementiert und später durch echte Komponente ersetzt |
| `CompareKebab` Stub | intern | Aktions-Menü (Pausieren, Briefing senden, Vorschau, Löschen) — #488/#489 OPEN; wird als Inline-Stub implementiert |
| `CompareLocationRow` Stub | intern | Orts-Zeile mit Rang, Name, Höhe — #488/#489 OPEN; Inline-Stub |
| `CompareIdealRow` Stub | intern | Idealwerte-Zeile aus `display_config.ideal_ranges` — #488/#489 OPEN; Inline-Stub |
| `CompareLayoutRow` Stub | intern | Layout-pro-Kanal-Zeile aus `display_config.channel_layouts` — #488/#489 OPEN; Inline-Stub |
| `frontend/src/routes/compare/[id]/edit/+page.server.ts` | intern | Auth-Pattern + 404-Muster für SSR-Loader |
| `frontend/src/routes/compare/+page.svelte` | intern | Breadcrumb-Stil (Eyebrow-Komponente) als Referenz |
| `internal/handler/compare_preset.go` (bestehend) | intern | Vorhandener List-Handler als Pattern-Referenz für neuen Get-Handler |
| `error` SvelteKit (`@sveltejs/kit`) | intern | `error(404, '...')` für unbekannte Preset-ID im SSR-Loader |

## Implementation Details

### §1 Backend — `GetComparePresetHandler` in `internal/handler/compare_preset.go`

Neuer Handler analog zum bestehenden List-Handler:

```go
func GetComparePresetHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        userID := auth.UserIDFromContext(r.Context())
        id := chi.URLParam(r, "id")
        preset, err := s.GetComparePreset(userID, id)
        if err != nil || preset == nil {
            http.Error(w, "preset not found", http.StatusNotFound)
            return
        }
        json.NewEncoder(w).Encode(preset)
    }
}
```

`store.GetComparePreset(userID, id string)` muss im Store vorhanden sein oder neu implementiert werden — prüfen ob `GetComparePresetByID` o.ä. bereits existiert.

### §2 Backend — Route in `cmd/server/main.go`

```go
r.Get("/api/compare/presets/{id}", handler.GetComparePresetHandler(s))
```

Einfügen direkt nach der bestehenden List-Route `r.Get("/api/compare/presets", ...)`.

### §3 Frontend — `+page.server.ts`

Lädt Preset und Locations parallel; wirft 404 wenn Preset nicht gefunden:

```typescript
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, fetch, locals }) => {
    const [presetRes, locationsRes] = await Promise.all([
        fetch(`/api/compare/presets/${params.id}`),
        fetch('/api/locations'),
    ]);

    if (presetRes.status === 404) {
        throw error(404, 'Orts-Vergleich nicht gefunden');
    }
    if (!presetRes.ok || !locationsRes.ok) {
        throw error(500, 'Fehler beim Laden');
    }

    return {
        preset: await presetRes.json(),
        locations: await locationsRes.json(),
    };
};
```

Auth-Handling: `fetch` im SSR-Loader leitet Cookies automatisch weiter (SvelteKit-Standard) — analog zu `edit/+page.server.ts`.

### §4 Frontend — `+page.svelte` (Page-Shell)

```svelte
<script lang="ts">
  import type { PageData } from './$types';
  import { Eyebrow, Btn } from '$lib/components/atoms';
  import CompareDetail from '$lib/components/compare/CompareDetail.svelte';
  export let data: PageData;
</script>

<Eyebrow>WORKSPACE · ORTS-VERGLEICHE / DETAIL</Eyebrow>
<h1>{data.preset.name}</h1>
<!-- CompareStatusPill-Stub + CompareKebab-Stub inline bis #488/#489 -->

<Btn variant="accent" href="/compare/{data.preset.id}/edit">Bearbeiten</Btn>

<CompareDetail preset={data.preset} locations={data.locations} />
```

### §5 Frontend — `CompareDetail.svelte`

**Props:**
```typescript
export let preset: ComparePreset;
export let locations: Location[];
```

**Monitoring-Streifen** (über den Cards, volle Breite):
- Status-Dot (Farbe aus `deriveStatusFromPreset`) + Label (aktiv/pausiert/draft)
- Nächster Versand: `presetScheduleLabel(preset)`
- Zuletzt: `formatLastSent(preset.letzter_versand)`
- Kanäle: `preset.empfaenger` als kommaseparierte Adressen

**Layout:** CSS-Grid `grid-template-columns: 1.7fr 1fr`

**Linke Spalte (3 Cards):**

1. Card „Verglichene Orte" — iteriert `preset.location_ids`, findet `Location` aus `locations`-Array per ID:
   ```typescript
   const resolvedLocations = preset.location_ids.map((id, idx) => ({
       rank: idx + 1,
       loc: locations.find(l => l.id === id),
   }));
   ```
   Jede Zeile (CompareLocationRow-Stub): Rang-Index, Name, Höhe (`elevation_m ?? '—'`).
   Draft-Sonderfall: `preset.location_ids.length === 0` → Hinweis „Noch keine Orte ausgewählt."

2. Card „Idealwerte" — iteriert `preset.display_config?.ideal_ranges ?? {}`:
   Jede Zeile (CompareIdealRow-Stub): Metrik-Name, Wert-Bereich.
   Draft-Sonderfall: Leere Card wenn kein `display_config` vorhanden.

3. Card „Layout pro Kanal" — iteriert `preset.display_config?.channel_layouts ?? {}`:
   Jede Zeile (CompareLayoutRow-Stub): Kanal-Name, Layout-Bezeichnung.
   Draft-Sonderfall: Leere Card wenn kein `display_config` vorhanden.

**Rechte Spalte (2 Cards):**

4. Card „Versand" — KV-Zeilen:
   - Zeitplan: `presetScheduleLabel(preset)`
   - Profil: `preset.profil`
   - Kanäle: `preset.empfaenger.map(e => <Pill>{e}</Pill>)` — ein Pill pro Adresse

5. Card „Vorschau · Prüfung" — statischer Hinweis-Text:
   „Briefing-Vorschau und manuelle Versandauslösung folgen in Issue #488."

### §6 Stub-Komponenten

Alle fünf abhängigen Komponenten (#488/#489 OPEN) werden als Inline-Implementierungen gebaut — keine eigene Datei, kein `import`. Sie bestehen aus einfachen `<div>`- oder `<tr>`-Zeilen mit den übergebenen Daten. Bei Fertigstellung von #488/#489 werden sie durch die echten Komponenten ersetzt.

### §7 LoC-Schätzung

| Datei | Änderung | LoC |
|-------|----------|-----|
| `internal/handler/compare_preset.go` | Erweiterung | ~40 |
| `cmd/server/main.go` | Erweiterung | ~2 |
| `frontend/src/routes/compare/[id]/+page.server.ts` | Neu | ~35 |
| `frontend/src/routes/compare/[id]/+page.svelte` | Neu | ~40 |
| `frontend/src/lib/components/compare/CompareDetail.svelte` | Neu | ~180 |
| **Summe** | | **~297 LoC** |

LoC-Override vor Implementierungsstart: `workflow.py set-field loc_limit_override 300`

## Expected Behavior

- **Input:**
  - URL-Parameter `id` aus SvelteKit-Route
  - `GET /api/compare/presets/{id}` → `ComparePreset` JSON
  - `GET /api/locations` → `Location[]` JSON
  - User-Auth via Session-Cookie (SvelteKit-Standard-Forwarding)
- **Output:**
  - Gerenderte Detail-Seite mit Breadcrumb, H1 (Preset-Name), StatusPill-Stub, Sub-Zeile (Region · Profil · N Orte), Primäraktion „Bearbeiten", Monitoring-Streifen, 5 Cards im 1.7fr/1fr-Grid
  - Korrekte 404-Fehlerseite bei unbekannter ID
  - Draft-Cards (leer/Hinweis) wenn `location_ids.length === 0`
- **Side effects:**
  - Keine Mutations — reine Lese-Seite
  - Navigation zu `/compare/{id}/edit` bei Klick auf „Bearbeiten"

## Acceptance Criteria

**AC-1:** Given `/compare/{id}` mit gültigem Preset / When geladen / Then zeigt die Seite Breadcrumb `WORKSPACE · ORTS-VERGLEICHE / DETAIL`, H1 mit dem Preset-Namen, einen CompareStatusPill-Stub, eine Sub-Zeile mit Region · Profil · N Orte und den Button „Bearbeiten" der auf `/compare/{id}/edit` zeigt.
  - Test: (populated after /tdd-red)

**AC-2:** Given die Detail-Seite lädt / When der Monitoring-Streifen gerendert wird / Then sind vier Felder sichtbar: Status-Dot + Label (aktiv/pausiert/draft), Nächster Versand (formatierter Zeitplan), Zuletzt (formatiertes Datum oder „Noch kein Versand"), Kanäle (Empfänger-Adressen aus `empfaenger`).
  - Test: (populated after /tdd-red)

**AC-3:** Given die Card „Verglichene Orte" mit befüllten `location_ids` / When gerendert / Then listet jede Zeile Rang-Index, Orts-Name und Höhe (via Location-Lookup aus dem `locations`-Array); bei leerem `location_ids` erscheint stattdessen der Hinweis „Noch keine Orte ausgewählt."
  - Test: (populated after /tdd-red)

**AC-4:** Given `/compare/unbekannte-id` / When der SSR-Loader ausgeführt wird / Then antwortet der Server mit HTTP 404 und zeigt die SvelteKit-Fehlerseite.
  - Test: (populated after /tdd-red)

**AC-5:** Given `cd frontend && npm run build` / When ausgeführt / Then läuft der Build ohne TypeScript- oder Svelte-Kompilierfehler durch und alle 5 Cards rendern ohne JavaScript-Fehler im Browser.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Stub-Komponenten:** CompareStatusPill, CompareKebab, CompareLocationRow, CompareIdealRow, CompareLayoutRow sind Inline-Stubs ohne vollständige Funktionalität — werden durch #488/#489 ersetzt.
- **CompareKebab ohne API:** Kebab-Aktionen (Pausieren, Briefing senden, Löschen) sind in diesem Issue als Stubs ohne API-Anbindung implementiert.
- **Kein Mobile-Layout:** Desktop-Planungstool; 2-Spalten-Grid auf kleinen Bildschirmen nicht optimiert.
- **display_config optional:** Wenn ein Preset ohne `display_config` geladen wird (ältere Daten), bleiben Cards „Idealwerte" und „Layout pro Kanal" leer — kein Fehler, nur leere Darstellung.
- **Store-Abhängigkeit:** `store.GetComparePreset` muss im Go-Store vorhanden sein — vor Implementierung prüfen, ob eine Einzelabfrage bereits existiert oder neu implementiert werden muss.

## Changelog

- 2026-05-31: Initial spec — Issue #491. Neue `/compare/[id]` Detail-Route (Block C, Epic #485): 3 neue Frontend-Dateien + 2 Backend-Erweiterungen (~297 LoC), Stub-Komponenten für #488/#489-Abhängigkeiten, neuer `GET /api/compare/presets/{id}`-Endpoint.
