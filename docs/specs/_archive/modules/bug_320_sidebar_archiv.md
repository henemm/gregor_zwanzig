---
entity_id: bug_320_sidebar_archiv
type: bugfix
created: 2026-05-21
updated: 2026-05-21
status: draft
version: "1.0"
tags: [bugfix, frontend, sidebar, navigation, design-compliance, issue-320]
---

<!-- Issue #320 — Bug: Sidebar-Nav hat nur 3 Items — "Archiv" fehlt (CHARTER §2) -->

# Issue #320 — Bug-Fix: Sidebar + BottomNav — "Archiv" als 4. Nav-Item ergänzen

## Approval

- [ ] Approved

## Zweck

CHARTER §2 schreibt exakt 4 Haupt-Nav-Bereiche vor: **Startseite · Touren · Orts-Vergleich · Archiv**. Das aktuelle 4. Item in `Sidebar.svelte` und `BottomNav.svelte` ist "Standorte" (`/locations`) — "Archiv" (`/archiv`) fehlt vollständig. Außerdem existiert die Route `/archiv` noch nicht.

Der Fix ersetzt `/locations` als 4. Nav-Item durch `/archiv` in beiden Navigationskomponenten und legt eine Placeholder-Seite für das Archiv an.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` — 4. navItem von `/locations`→Standorte auf `/archiv`→Archiv umstellen; Icon-Import tauschen
- `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` — 4. navItem von `/locations`→Locations auf `/archiv`→Archiv umstellen; Icon-Import tauschen; testid anpassen
- `frontend/src/routes/archiv/+page.svelte` — Neu: Placeholder-Seite mit Empty-State (Kachel-Grid-Layout gemäß CHARTER §3 + SCREENS.json)

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Die `/locations`-Route bleibt unverändert bestehen — Account-Seite und Compare-Bereich verlinken dorthin.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `@lucide/svelte/icons/archive` | Lucide-Icon | Ersetzt `map-pin` als Nav-Icon für Archiv — existiert in node_modules |
| `frontend/src/routes/+layout.svelte` | SvelteKit-Layout | Bindet Sidebar + BottomNav ein; keine Änderung nötig |
| `frontend/src/routes/locations/+page.svelte` | Bestehende Route | Bleibt unberührt — fliegt nur aus der Haupt-Nav |
| `docs/design-system/CHARTER.md §2` | Design-Autorität | Schreibt genau 4 Nav-Items und deren Reihenfolge vor |
| `docs/design-system/SCREENS.json` (id: "archiv") | Screen-Spec | Route `/archiv`, eyebrow `ARCHIV · VERGANGENE TOUREN`, title `Archiv`, layout `kachel-grid` |

## Implementation Details

### 1. `Sidebar.svelte` — Icon-Import + navItem tauschen

Import ersetzen:
```diff
-import MapPinIcon from '@lucide/svelte/icons/map-pin';
+import ArchiveIcon from '@lucide/svelte/icons/archive';
```

navItems[3] ersetzen:
```diff
-{ href: '/locations', label: 'Standorte',     icon: MapPinIcon       },
+{ href: '/archiv',    label: 'Archiv',         icon: ArchiveIcon      },
```

### 2. `BottomNav.svelte` — Icon-Import + navItem tauschen

Import ersetzen:
```diff
-import MapPin from '@lucide/svelte/icons/map-pin';
+import Archive from '@lucide/svelte/icons/archive';
```

navItems[3] ersetzen:
```diff
-{ href: '/locations', label: 'Locations', icon: MapPin,     testid: 'bottom-nav-item-locations' },
+{ href: '/archiv',    label: 'Archiv',    icon: Archive,    testid: 'bottom-nav-item-archive'   },
```

### 3. `frontend/src/routes/archiv/+page.svelte` — Placeholder anlegen

Neue Datei gemäß SCREENS.json (id: `archiv`):
- Eyebrow: `ARCHIV · VERGANGENE TOUREN`
- Title: `Archiv`
- Layout: Kachel-Grid
- Empty-State: Text "Noch keine abgeschlossenen Touren im Archiv." ohne CTA (Archiv befüllt sich automatisch)
- Kein `+page.server.ts` nötig — Placeholder hat keinen API-Call

### 4. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | ±2 (1 Import-Swap + 1 Item-Swap) | nein (Frontend-Asset) |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | ±2 (1 Import-Swap + 1 Item-Swap) | nein (Frontend-Asset) |
| `frontend/src/routes/archiv/+page.svelte` | +25 (neu) | nein (Frontend-Asset) |
| **Gesamt (zählend)** | **0** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Angemeldeter User ruft eine beliebige Seite der App auf
- **Output:** Sidebar (Desktop) und BottomNav (Mobile) zeigen 4 Items: Startseite · Meine Touren · Orts-Vergleich · Archiv — in dieser Reihenfolge. Klick auf "Archiv" führt zu `/archiv` mit Empty-State.
- **Side effects:** `/locations` ist weiterhin über `/account`-Links und den Compare-Bereich erreichbar, erscheint aber nicht mehr in der Haupt-Navigation.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter User auf einer beliebigen Desktop-Seite / When er die Sidebar betrachtet / Then zeigt sie genau 4 Items in dieser Reihenfolge: Startseite, Meine Touren, Orts-Vergleich, Archiv — und kein Item namens "Standorte" oder "Locations"
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein angemeldeter User auf einem Mobil-Viewport (<900px) / When er die BottomNav betrachtet / Then zeigt sie genau 4 Items: Übersicht, Trips, Vergleich, Archiv — und `data-testid="bottom-nav-item-archive"` existiert, `data-testid="bottom-nav-item-locations"` existiert nicht mehr
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein User der in der Sidebar oder BottomNav auf "Archiv" klickt / When die Navigation abgeschlossen ist / Then ist die URL `/archiv` und die Seite zeigt Eyebrow `ARCHIV · VERGANGENE TOUREN` sowie einen Empty-State-Text
  - Test: (populated after /tdd-red)

- **AC-4:** Given die `/locations`-Route / When ein User sie direkt aufruft (z.B. via Link in der Konto-Seite) / Then antwortet sie weiterhin mit Status 200 und zeigt die Standorte-Liste — kein Breaking Change durch den Nav-Umbau
  - Test: (populated after /tdd-red)

## Known Limitations

- Die `/archiv`-Seite ist ein Placeholder ohne Daten — die Logik, Trips nach Abschluss ins Archiv zu verschieben, ist separater Scope (nicht Teil dieses Fixes).
- Das Archiv-Icon (`archive`) weicht vom bisherigen `map-pin`-Icon ab — kein visueller Regression-Risk, da der Slot klar neu belegt wird.

## Out of Scope

- Archiv-Backend-Logik (Trip-Status-Filter, abgeschlossene Trips anzeigen)
- Entfernung oder Umgestaltung der `/locations`-Seite selbst
- Umbenennung von Nav-Labels der anderen 3 Items (separates Issue #321)

## Changelog

- 2026-05-21: Initial spec erstellt. Behebt CHARTER-§2-Verstoß: 4. Nav-Item in Sidebar + BottomNav von `/locations` auf `/archiv` umstellen + Placeholder-Seite anlegen. 3 Frontend-Dateien, ~30 LoC.
