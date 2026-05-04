---
entity_id: nav_redesign_phase_a
type: module
created: 2026-04-18
updated: 2026-04-18
status: draft
version: "1.0"
tags: [sveltekit, frontend, navigation, ux, f76]
---

# F76 Phase A — Navigation umbauen (3 Eintraege)

## Approval

- [ ] Approved

## Purpose

Reduziert die Sidebar-Navigation von 6 Eintraegen (in 2 Gruppen) auf 3 Eintraege (flach, ohne Gruppen-Header). Labels werden Use-Case-zentriert umbenannt. Alle bisherigen Routen bleiben erreichbar — nur die Sichtbarkeit in der Sidebar aendert sich.

Teil des UX-Redesigns (#76), Eltern-Spec: `docs/specs/ux_redesign_navigation.md` (approved).

## Ist-Zustand

```
Daten:   Uebersicht (/) | Trips (/trips) | Locations (/locations) | Abos (/subscriptions)
System:  Vergleich (/compare) | Wetter (/weather)
```

User-Menu (unveraendert): Konto (/account) | System-Status (/settings)

## Soll-Zustand

```
Startseite (/), Meine Touren (/trips), Orts-Vergleich (/compare)
```

User-Menu: Konto (/account) | System-Status (/settings) — bleibt wie es ist.

## Source

- **File:** `frontend/src/routes/+layout.svelte` **(EDIT, ~20 LoC)**
- **Identifier:** `navGroups` (Zeile 82-99), Icon-Imports (Zeile 61-70)

## Aenderungen im Detail

### 1. navGroups ersetzen (Z.82-99)

**Vorher:** 2 Gruppen-Objekte mit je label + items Array (6 Eintraege).

**Nachher:** 1 flaches Array `navItems` mit 3 Eintraegen:

| Label | href | Icon | Mapping |
|-------|------|------|---------|
| Startseite | `/` | `LayoutDashboard` | war "Uebersicht" |
| Meine Touren | `/trips` | `RouteIcon` | war "Trips" |
| Orts-Vergleich | `/compare` | `GitCompare` | war "Vergleich" |

### 2. Icon-Imports aufraeumen (Z.61-70)

**Entfernen:** `MapPin`, `Bell`, `CloudSun` (nicht mehr in Nav genutzt).
**Behalten:** `LayoutDashboard`, `RouteIcon`, `GitCompare` + alle User-Menu-Icons.

### 3. Sidebar-Rendering anpassen (Z.150-165)

Gruppen-Schleife (`#each navGroups as group`) ersetzen durch flache Schleife (`#each navItems as item`). Gruppen-Header (`<p>` mit Label "Daten"/"System") entfaellt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ux_redesign_navigation` | spec | Eltern-Spec, definiert Gesamt-Vision |
| `+layout.svelte` | file | Einzige betroffene Datei |

## Was sich NICHT aendert

- Keine Routen werden geloescht oder umbenannt
- `/locations`, `/subscriptions`, `/weather`, `/gpx-upload` bleiben erreichbar via URL
- User-Menu bleibt identisch (Konto, System-Status, Dark Mode, Abmelden)
- Mobile Menu folgt derselben Struktur (automatisch, da gleiche Daten)
- Dashboard-Seite (`+page.svelte`) mit Links zu /trips und /locations — unveraendert
- E2E-Tests navigieren via `page.goto()`, nicht Sidebar — kein Bruch

## Expected Behavior

- **Input:** User oeffnet die App
- **Output:** Sidebar zeigt 3 Eintraege: Startseite, Meine Touren, Orts-Vergleich
- **Active-State:** Highlighting funktioniert wie bisher (pathname-Match)
- **Side effects:** Keine — rein kosmetische Aenderung

## Known Limitations

- Seiten ohne Nav-Eintrag (/locations, /subscriptions, /weather) sind nur per Direktlink erreichbar — das ist gewollt, sie werden in Folge-Phasen zusammengefuehrt
- Dashboard-Links zu /locations zeigen noch auf die alte Seite — wird in Phase B (Startseite) bereinigt

## Risiken

- **Minimal** — eine Datei, ~20 LoC, keine Logik-Aenderung
- E2E-Tests: Kein Risiko (navigieren per URL, nicht per Sidebar-Klick)

## Changelog

- 2026-04-18: Initial spec fuer Phase A
