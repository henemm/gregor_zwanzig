# Context: Nav-Redesign Phase A

## Request Summary
Navigation von 6+2 Eintraegen auf 3+Konto umbauen. Sidebar: Startseite, Meine Touren, Orts-Vergleich. User-Menu: Konto (inkl. System-Status). Alte Routen bleiben erreichbar, werden aber nicht mehr in der Nav angezeigt.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/+layout.svelte` | **Hauptdatei** — navGroups (Z.82-99), User-Menu (Z.190-226), Sidebar-Rendering |
| `frontend/src/routes/+page.svelte` | Dashboard — Link zu /locations (Z.37), Link zu /trips (Z.24) |
| `frontend/src/routes/+page.server.ts` | Dashboard-Daten (trips, locations, health) |
| `docs/specs/ux_redesign_navigation.md` | Approved Spec fuer Gesamt-Redesign |

## Seitenrouten (bleiben alle erreichbar)
| Route | Seite | Nav-Sichtbarkeit NEU |
|-------|-------|---------------------|
| `/` | Startseite | Sidebar |
| `/trips` | Meine Touren | Sidebar |
| `/locations` | Locations | Nicht in Nav (spaeter Teil von Orts-Vergleich) |
| `/subscriptions` | Abos | Nicht in Nav (spaeter Teil von Orts-Vergleich) |
| `/compare` | Orts-Vergleich | Sidebar |
| `/weather` | Wetter | Nicht in Nav (spaeter Drill-Down) |
| `/gpx-upload` | GPX Upload | Nicht in Nav (spaeter Wizard) |
| `/account` | Konto | User-Menu (bleibt) |
| `/settings` | System-Status | User-Menu (bleibt) |

## Existing Patterns
- navGroups Array mit label+items-Struktur (Z.82-99)
- Icons via @lucide/svelte
- Active-State via `page.url.pathname === item.href`
- User-Menu als Dropdown im Sidebar-Footer (Z.168-227)

## Dependencies
- **Upstream:** SvelteKit page router, $app/state (page), Lucide Icons
- **Downstream:** Alle Seiten bleiben via URL erreichbar, nur Nav-Sichtbarkeit aendert sich

## Existing Specs
- `docs/specs/ux_redesign_navigation.md` — Approved, beschreibt Gesamt-Redesign

## Risks & Considerations
- Alte Routen MUESSEN erreichbar bleiben (Bookmarks, direkte URLs)
- User die /locations oder /subscriptions direkt kennen, verlieren Navigation dahin
- Phase A aendert NUR die Sidebar — kein Inhalt der Seiten aendert sich
- Compare-Route wird umbenannt zu "Orts-Vergleich" aber bleibt auf /compare
