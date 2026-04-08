# User Story: SvelteKit-Migration

**Epic:** Tech Stack Migration
**Erstellt:** 2026-04-08
**Status:** Draft

## Story

Als PO moechte ich den Tech-Stack von Python/NiceGUI auf Go (Backend) + SvelteKit (Frontend) migrieren, damit die AI-gestuetzte Entwicklung weniger Fehler produziert und Features schneller produktionsreif werden.

## Motivation

### Problem

- AI (Claude) macht mit Python signifikant mehr Fehler als mit Go (dynamische Typen, Import-System, NiceGUI-Magie)
- NiceGUI ist Nische — wenig Trainingsdaten, subtile Bugs (Safari-Closures, Session-Isolation)
- Multi-User (F13) ist in NiceGUI extrem aufwaendig
- Jeder Feature-Zyklus hat zu viele Iterationen (Code → Test → Fix → Test → Fix)

### Ziel-Stack

| Komponente | Aktuell | Neu | Warum |
|---|---|---|---|
| Backend | Python + httpx | **Go + Chi** | Compile-Time Safety, explizites Error Handling, Single Binary |
| Frontend | NiceGUI (Python) | **SvelteKit** | Stabile Trainingsdaten, fertige UI-Komponenten (Skeleton UI / shadcn-svelte), eingebaute Auth |
| API | Intern (Python-Funktionsaufrufe) | **REST API** | Klare Trennung Backend/Frontend |
| Deploy | Python venv + systemd | **Go Binary + Node/SvelteKit** | Einfacher, zuverlaessiger |
| Tests | pytest + Playwright | **go test + Playwright** | Go-Tests sind schneller und expliziter |

### Bewertung der Frontend-Alternativen

| Framework | Trainingsdaten Menge | Trainingsdaten Qualitaet | UI-Komponenten | Stabilitaet |
|---|---|---|---|---|
| React | Riesig | Schlecht — veraltete Patterns, Paradigmenwechsel (Classes→Hooks→Server Components) | Sehr viele | Mittel (churn) |
| Svelte/SvelteKit | Mittel | Gut — wenig Paradigmenwechsel, konsistente Patterns | Gut (Skeleton UI, shadcn-svelte) | Hoch (Vercel-backed) |
| Vue | Mittel | Gut | Viele | Hoch |
| HTMX + Templ | Klein (HTMX) / Sehr klein (Templ) | Gut, aber duenn | Keine — alles selbst bauen | Mittel (Templ ist jung) |

**Entscheidung: SvelteKit** — beste Balance aus Trainingsdaten-Qualitaet, UI-Oekosystem und Stabilitaet.

## Scope & Phasen

### Phase 0: Parallel-Setup (Grundlage)

**Ziel:** Go-Backend + SvelteKit-Frontend neben bestehendem Python-Stack aufsetzen. Kein Feature-Freeze.

| Task | Beschreibung | Aufwand |
|---|---|---|
| Go-Modul initialisieren | `go mod init`, Chi Router, Projektstruktur | Gering |
| SvelteKit-Projekt aufsetzen | Vite, Skeleton UI / shadcn-svelte, Auth-Setup (Lucia) | Gering |
| REST API Design | OpenAPI-Spec fuer Trip/Location/Weather Endpoints | Mittel |
| CI/CD erweitern | GitHub Actions fuer Go + SvelteKit Build/Test | Gering |

### Phase 1: Backend-Kern portieren (Go)

**Ziel:** Weather-Pipeline in Go. Python-Frontend laeuft noch parallel.

| Modul | Python LOC (ca.) | Prioritaet | Abhaengigkeiten |
|---|---|---|---|
| Config & DTOs | 500 | P0 | — |
| Provider (OpenMeteo) | 800 | P0 | Config |
| Normalizer | 300 | P0 | Provider |
| Risk Engine | 600 | P1 | Normalizer |
| Formatter (Email/SMS) | 1500 | P1 | Risk Engine |
| Scheduler | 400 | P1 | Formatter |
| GPX Parser | 500 | P1 | — |
| Segment Builder | 400 | P1 | GPX Parser |

**Reihenfolge:** Config → Provider → Normalizer → Risk Engine → Formatter → Scheduler

**Validierung pro Modul:** Gleicher Output wie Python-Version (Regressions-Check).

### Phase 2: Frontend portieren (SvelteKit)

**Ziel:** NiceGUI komplett ersetzen. Multi-User (F13) direkt einbauen.

| Page | Python LOC (ca.) | Prioritaet | Anmerkung |
|---|---|---|---|
| Login / Auth | — | P0 | Neu (Lucia Auth) — loest F13 |
| Trips (CRUD) | 800 | P0 | Kernfunktionalitaet |
| Locations (CRUD) | 600 | P0 | Inkl. Metrik-Auswahl |
| Weather-Tabelle | 500 | P0 | HTMX-artige Live-Updates via SvelteKit |
| GPX Upload | 400 | P1 | Drag & Drop |
| Etappen-Config | 500 | P1 | Segment-Uebersicht |
| Subscriptions | 300 | P1 | Compare-Emails |
| Report-Config | 200 | P1 | Morning/Evening Zeiten |
| Settings | 200 | P2 | Channel-Switch (F12) |

### Phase 3: Cutover & Cleanup

| Task | Beschreibung |
|---|---|
| DNS/Reverse Proxy | Nginx auf Go+SvelteKit umstellen |
| Python-Code entfernen | `src/` + NiceGUI komplett loeschen |
| Systemd-Service anpassen | Go Binary als Service |
| E2E-Tests migrieren | Playwright gegen neues Frontend |
| Monitoring | BetterStack Heartbeats auf Go umstellen |

## Risiken

| Risiko | Schwere | Mitigation |
|---|---|---|
| Feature-Freeze waehrend Migration | Hoch | Phasen-Ansatz: Python laeuft parallel bis Cutover |
| SvelteKit-Paradigmenwechsel (Svelte 5→6) | Niedrig | Vercel investiert in Stabilitaet, Migration Guides |
| Go-Libraries fuer Spezialfaelle (astral, gpxpy) | Mittel | Go-Alternativen pruefen: go-sunrise, go-gpx |
| Zwei Stacks gleichzeitig warten | Mittel | Phase 1+2 zuegig durchziehen, kein Langzeit-Parallel-Betrieb |
| Templ/HTMX vs SvelteKit Fehlentscheidung | Niedrig | SvelteKit hat groesseres Oekosystem, einfacher rueckgaengig |

## Abhaengigkeiten zu bestehenden Features

| Feature | Auswirkung |
|---|---|
| F13 (Multi-User) | Wird durch SvelteKit Auth (Lucia) direkt geloest |
| F12 (Channel-Switch) | In Phase 2 als SvelteKit-Page implementieren |
| F14a/b (Subscription Metriken) | In Phase 2 als SvelteKit-Page implementieren |
| F1 (SMS-Kanal) | In Phase 1 als Go-Service implementieren |
| BUG-TZ-01 (Timezone) | In Phase 1 beim Provider-Port direkt fixen |

## Erfolgskriterien

1. **Gleicher Feature-Umfang** wie Python-Version nach Cutover
2. **Multi-User funktional** (Login, User-Isolation, Session-Management)
3. **AI-Fehlerrate messbar reduziert** (weniger Fix-Iterationen pro Feature)
4. **Alle E2E-Tests gruen** (Playwright gegen SvelteKit-Frontend)
5. **Deploy ist einfacher** (Go Binary + SvelteKit Static/Node)

## Nicht-Ziele

- Keine neuen Features waehrend der Migration (ausser F13 Multi-User, das durch Auth direkt abfaellt)
- Kein Over-Engineering: REST API nur so komplex wie noetig
- Kein Microservice-Schnitt: Go-Backend bleibt ein Monolith

## Offene Entscheidungen

| Frage | Optionen | Status |
|---|---|---|
| SvelteKit Deploy-Modus | Node-Server vs. Static Adapter + Go serves files | Offen |
| Auth-Library | Lucia vs. eigene Session-Middleware | Offen |
| UI-Component-Library | Skeleton UI vs. shadcn-svelte vs. Flowbite Svelte | Offen |
| Go-GPX-Library | tkrajina/gpxgo vs. eigener Parser | Offen |
| Parallel-Betrieb Dauer | Max 4 Wochen vs. "bis fertig" | Offen |
