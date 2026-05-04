---
entity_id: orts_vergleich_master_detail
type: module
created: 2026-04-18
updated: 2026-04-18
status: draft
version: "1.0"
tags: [sveltekit, frontend, ux, f76, compare, locations]
---

# F76 Phase C1 — Master-Detail Layout fuer Orts-Vergleich

## Approval

- [ ] Approved

## Purpose

Die /compare Seite bekommt ein zweispaltiges Master-Detail Layout: Links eine Sidebar mit der Locations-Liste und Checkboxen zur Auswahl, rechts der bestehende Compare-Content. Die Location-Checkboxen wandern aus der "Einstellungen"-Card in die Sidebar. Struktureller Umbau, keine neue Funktionalität.

Teil des UX-Redesigns (#76), Eltern-Spec: `docs/specs/ux_redesign_navigation.md` Abschnitt 3.

## Ist-Zustand

```
┌─────────────────────────────────────┐
│ Vergleich (h1)                      │
│                                     │
│ ┌─ Einstellungen Card ────────────┐ │
│ │ Locations: ☑ Alle (N)           │ │
│ │   ☑ Ort A  ☑ Ort B  ☑ Ort C    │ │
│ │ Datum | Von | Bis | Forecast    │ │
│ │ Aktivitaetsprofil               │ │
│ │ [Vergleichen]                   │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─ Ergebnis-Tabelle ──────────────┐ │
│ │ ...                             │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

## Soll-Zustand

```
┌──────────────┐┌─────────────────────┐
│ Meine Orte   ││ Orts-Vergleich (h1) │
│              ││                     │
│ ☑ Alle (N)   ││ ┌─ Einstellungen ─┐ │
│ ☑ Ort A      ││ │ Datum | Von     │ │
│ ☑ Ort B      ││ │ Bis | Forecast  │ │
│ ☐ Ort C      ││ │ Profil          │ │
│              ││ │ [Vergleichen]   │ │
│ [+ Ort]      ││ └─────────────────┘ │
│              ││                     │
│              ││ ┌─ Ergebnis ──────┐ │
│              ││ │ ...             │ │
│              ││ └─────────────────┘ │
└──────────────┘└─────────────────────┘
```

**Mobile (< md):** Sidebar ausgeblendet. Location-Checkboxen bleiben inline im Einstellungen-Content (wie bisher), gesteuert ueber `showMobileLocs` Toggle.

## Source

- **File:** `frontend/src/routes/compare/+page.svelte` **(EDIT, ~120 LoC netto)**
- **Identifier:** Layout-Container, Sidebar-Section, Location-Checkboxen

## Aenderungen im Detail

### 1. Layout-Container (Wurzel-Element)

**Vorher:** `<div class="space-y-6">` (volle Breite, vertikal gestapelt)

**Nachher:** Flexbox mit Sidebar + Content:

```svelte
<div class="flex gap-6">
  <!-- Sidebar: Desktop only -->
  <aside class="hidden w-60 shrink-0 md:block">
    ...Location-Liste...
  </aside>

  <!-- Content -->
  <div class="min-w-0 flex-1 space-y-6">
    ...Compare-Logik...
  </div>
</div>
```

### 2. Sidebar-Inhalt

- Ueberschrift "Meine Orte"
- "Alle" Checkbox (toggleAll)
- Location-Liste mit Checkboxen (toggleLocation) — gleiche Logik wie bisher
- "Neuer Ort" Button → oeffnet LocationForm Dialog
- Styling: Kompakte Liste, kein Card-Wrapper, dezenter Border-Right

### 3. Einstellungen-Card anpassen

- Location-Checkboxen-Block (`<div>` mit "Locations" Label) aus der Card **entfernen** (Desktop)
- Auf Mobile: Location-Checkboxen bleiben in der Card (conditional rendering via `md:hidden`)
- Rest der Card bleibt: Datum, Zeitfenster, Forecast, Profil, Button

### 4. Location-CRUD in Sidebar

- Import: `LocationForm` aus `$lib/components/LocationForm.svelte`
- Import: `Dialog` aus shadcn-svelte
- Import: `api` aus `$lib/api.js`
- "Neuer Ort" Button → oeffnet Dialog mit LocationForm
- Nach Speichern: Location zur Liste hinzufuegen (optimistic update oder refetch)
- Kein Edit/Delete in C1 — das bleibt auf der /locations Seite

### 5. Titel aendern

- `<h1>` von "Vergleich" auf "Orts-Vergleich" (konsistent mit Nav-Label)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ux_redesign_navigation` | spec | Eltern-Spec, definiert Gesamt-Vision |
| `compare/+page.server.ts` | file | Bleibt unveraendert, laedt Locations |
| `LocationForm.svelte` | component | Wiederverwendung fuer "Neuer Ort" |
| `$lib/api.ts` | module | POST /api/locations fuer neue Orte |
| `$lib/types.ts` | types | Location interface |

## Was sich NICHT aendert

- Compare-Logik (runComparison, result-Rendering, bestIdx, fmt, degToCompass)
- +page.server.ts (laedt bereits Locations)
- API-Endpunkte
- Ergebnis-Tabelle und Winner-Card
- /locations Seite (bleibt erreichbar und funktional)
- /subscriptions Seite (bleibt erreichbar)
- toggleAll/toggleLocation Logik (wird nur visuell verschoben)

## Expected Behavior

- **Desktop:** Sidebar links (240px) mit Locations + Checkboxen, Content rechts mit Compare
- **Mobile:** Keine Sidebar, Locations inline im Einstellungen-Block
- **"Neuer Ort":** Oeffnet Dialog, nach Speichern erscheint Ort in Sidebar-Liste
- **Checkbox-State:** Synchron zwischen Sidebar und Compare (gleiche State-Variablen)

## Known Limitations

- Kein Edit/Delete fuer Locations in der Sidebar (bleibt auf /locations)
- Keine Gruppen/Kategorien (kommt in Phase C4)
- Keine Auto-Reports Ansicht (kommt in Phase C3)
- Kein Drag & Drop fuer Reihenfolge

## Risiken

- **Gering:** CSS-Layout — Page-Level Sidebar neben globaler Nav-Sidebar. Geloest durch relative Positionierung (kein fixed/absolute)
- **Gering:** Mobile Breakpoint — konsistent mit bestehendem md: Pattern

## Changelog

- 2026-04-18: Initial spec fuer Phase C1
