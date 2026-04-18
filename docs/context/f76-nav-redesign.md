# Context: F76 — UX Redesign Navigation

## Request Summary
Neuorganisation der Navigation entlang zweier Kern-Use-Cases (Trips + Orts-Vergleich) statt entlang der Datenstruktur. Von 8 Nav-Eintraegen auf 3 + Startseite. Genehmigte Spec: `docs/specs/ux_redesign_navigation.md`.

## Phasen-Ansatz

Das Redesign ist zu gross fuer einen Schritt. Sinnvolle Aufteilung:

| Phase | Scope | Aufwand |
|-------|-------|---------|
| **A: Nav umbauen** | Sidebar: 6→3 Eintraege, Labels umbenennen | Klein (~20 LoC) |
| **B: Startseite** | Kachel-Uebersicht (Trips + Vergleiche) | Mittel |
| **C: Orts-Vergleich** | Sidebar+Content Layout, Locations/Compare/Subscriptions zusammenfuehren | Gross |
| **D: Trip-Wizard** | 4-Schritt-Wizard statt verteilte Dialoge | Gross |
| **E: Konto erweitern** | Templates, System-Status integrieren | Mittel |

Phase A hat bereits eine Spec (Draft): `docs/specs/modules/nav_redesign_phase_a.md`

## Related Files

### Frontend (SvelteKit)
| File | Relevance |
|------|-----------|
| `frontend/src/routes/+layout.svelte` | **Hauptdatei** — Sidebar, navGroups, User-Menu |
| `frontend/src/routes/+page.svelte` | Dashboard/Startseite — wird in Phase B umgebaut |
| `frontend/src/routes/+page.server.ts` | Dashboard-Daten (trips, locations, health) |
| `frontend/src/routes/trips/+page.svelte` | Trip-Liste (bleibt in Phase A) |
| `frontend/src/routes/locations/+page.svelte` | Locations-Seite (Phase C: in Orts-Vergleich integrieren) |
| `frontend/src/routes/compare/+page.svelte` | Vergleichs-Seite (Phase C: wird Hauptcontent) |
| `frontend/src/routes/subscriptions/+page.svelte` | Abo-Seite (Phase C: Auto-Reports in Orts-Vergleich) |
| `frontend/src/routes/weather/+page.svelte` | Wetter-Seite (wird Drill-Down, kein Nav-Punkt) |
| `frontend/src/routes/gpx-upload/+page.svelte` | GPX Upload (Phase D: Wizard Schritt 1) |
| `frontend/src/routes/account/+page.svelte` | Konto (Phase E: Templates, Status) |
| `frontend/src/routes/settings/+page.svelte` | System-Status (Phase E: in Konto integrieren) |

### Shared Components
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/TripForm.svelte` | Trip-Erstellung (Phase D: wird Wizard) |
| `frontend/src/lib/components/LocationForm.svelte` | Location-Erstellung (Phase C: wiederverwenden) |
| `frontend/src/lib/components/SubscriptionForm.svelte` | Abo-Erstellung (Phase C: wiederverwenden) |
| `frontend/src/lib/components/WeatherConfigDialog.svelte` | Wetter-Config (Phase D: Wizard Schritt 3) |
| `frontend/src/lib/types.ts` | TypeScript Interfaces (Location, Trip, Subscription) |
| `frontend/src/lib/api.ts` | Fetch-Wrapper fuer Go-API |

### Go API (41 Endpoints)
| Endpoint-Gruppe | Relevanz |
|-----------------|----------|
| `/api/locations` CRUD | Phase C: Gruppen-Konzept (neue Felder?) |
| `/api/subscriptions` CRUD | Phase C: Auto-Reports |
| `/api/trips` CRUD | Phase D: Wizard |
| `/api/compare` | Phase C: Orts-Vergleich Content |
| `/api/forecast` | Phase C/D: Wetter-Drill-Down |
| `/api/auth/profile` | Phase E: Templates im Profil speichern |

## Existing Specs
- `docs/specs/ux_redesign_navigation.md` — **Approved**, Gesamt-Vision
- `docs/specs/modules/nav_redesign_phase_a.md` — **Draft**, Phase A Detail-Spec

## Existing Patterns
- `navGroups` Array mit label+items-Struktur (Layout Z.82-99)
- Icons via `@lucide/svelte`
- Active-State via `page.url.pathname === item.href`
- User-Menu als Dropdown im Sidebar-Footer
- shadcn-svelte UI-Komponenten (Card, Dialog, Table, Button, etc.)
- API-Proxy: `frontend/src/routes/api/[...path]/+server.ts`

## Dependencies
- **Upstream:** SvelteKit, Svelte 5 (Runes), Tailwind 4, shadcn-svelte, Lucide Icons, Go API (chi/v5)
- **Downstream:** E2E-Tests navigieren via `page.goto()` (kein Sidebar-Klick) → kein Bruch

## Risks & Considerations
- Alte Routen MUESSEN erreichbar bleiben (Bookmarks, direkte URLs)
- Phase A ist risikoarm (~20 LoC, eine Datei)
- Spaetere Phasen brauchen ggf. API-Erweiterungen (Gruppen fuer Locations)
- Wizard (Phase D) ist der komplexeste Teil
