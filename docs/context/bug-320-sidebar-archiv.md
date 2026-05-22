# Context: Bug #320 — Sidebar-Nav fehlt "Archiv"

## Request Summary
CHARTER §2 schreibt genau 4 Nav-Items vor: Startseite · Touren · Orts-Vergleich · **Archiv**. Das 4. Item zeigt derzeit "Standorte" (`/locations`) — Archiv fehlt komplett in Sidebar und BottomNav.

## IST-Zustand

### `Sidebar.svelte` navItems (Zeile 26–31)
```
{ href: '/',          label: 'Startseite',     icon: LayoutDashboard }
{ href: '/trips',     label: 'Meine Touren',   icon: RouteIcon }
{ href: '/compare',   label: 'Orts-Vergleich', icon: GitCompare }
{ href: '/locations', label: 'Standorte',       icon: MapPinIcon }   ← falsch
```

### `BottomNav.svelte` navItems (Zeile 8–13)
```
{ href: '/',          label: 'Übersicht',  icon: LayoutDashboard }
{ href: '/trips',     label: 'Trips',      icon: RouteIcon }
{ href: '/compare',   label: 'Vergleich',  icon: GitCompare }
{ href: '/locations', label: 'Locations',  icon: MapPin }            ← falsch
```

### Routen
- `/archiv` existiert **nicht** — Verzeichnis fehlt

## SOLL-Zustand (CHARTER §2 + SCREENS.json)

4. Item: `href: '/archiv'`, Label: `Archiv`, Icon: `ArchiveIcon` (Lucide `archive`)  
Archiv-Page: `layout: kachel-grid`, eyebrow `ARCHIV · VERGANGENE TOUREN`, title `Archiv`

## Relevante Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | navItems Array — 4. Item ersetzen |
| `frontend/src/lib/components/ui/sidebar/BottomNav.svelte` | navItems Array — 4. Item ersetzen |
| `frontend/src/routes/archiv/+page.svelte` | Neu anlegen — Placeholder mit Empty-State |
| `frontend/src/routes/archiv/+page.server.ts` | Neu anlegen — einfacher Load (kein API-Call nötig) |
| `docs/design-system/CHARTER.md §2` | Autorität: genau 4 Nav-Items, Reihenfolge fix |
| `docs/design-system/SCREENS.json` (id: "archiv") | Soll-Screen-Spec |

## Bestehende Patterns

- Lucide Icon `archive` existiert: `@lucide/svelte/icons/archive`
- `/locations` bleibt als Route erhalten (Account-Page und Compare verlinken darauf), fliegt nur aus Nav
- Placeholder-Pages folgen dem Kachel-Grid-Pattern mit `PageEmpty` (wie in COMPONENTS.md §PageEmpty dokumentiert: `kind: "archive"`)

## Dependencies

- Upstream: keine API-Änderung nötig (Archiv ist Placeholder)
- Downstream: Sidebar + BottomNav sind zentral in `+layout.svelte` — kein anderes Modul betroffen

## Risks & Considerations

- `/locations` muss weiterhin erreichbar bleiben (Account verlinkt via `<a href="/locations">`)
- Kein Backend-Endpoint für `/archiv` nötig — erst wenn Feature ausgebaut wird
- BottomNav hat `data-testid` pro Item — `testid: 'bottom-nav-item-archive'` für neues Item vergeben
- CHARTER §2: "Mobile Nav: Bottom-Nav mit denselben 4 Bereichen" — beide Dateien synchron ändern
