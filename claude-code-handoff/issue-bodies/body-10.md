## Problem

Aktuelles `/compare` zeigt eine flache Ortsliste mit Checkboxes. Die Spec (`ux_redesign_navigation.md §3`) verlangt **Master-Detail-Layout**:
- Sidebar links: Orte in **Gruppen / Ordnern** (Skigebiete Tirol, Surfspots Portugal, Wandern Mallorca…)
- Content rechts: Default = Auto-Reports-Übersicht; nach Vergleich = Ergebnis-Tabelle
- „Locations" und „Subscriptions" als eigene Nav-Punkte **entfallen** — sie werden hier zusammengeführt

## Files

- `src/routes/compare/+page.svelte` — Layout-Umbau auf 2-Spalten
- `src/lib/components/compare/LocationsRail.svelte` — Gruppen + Klappbarkeit
- `src/lib/components/compare/GroupSection.svelte` — **neu**
- `src/lib/components/compare/AutoReportsOverview.svelte` — **neu**, Default-Content
- `src/lib/components/compare/CreateGroupDialog.svelte` — **neu**

Routes die entfallen:
- `/locations` → wird in den Compare-Sidebar absorbiert
- `/subscriptions` → wird zu Auto-Reports-Übersicht im Compare-Content

## Datenmodell

`Location` benötigt `group_id` Feld (nullable, oder default „Ungruppiert"). `Group` ist neues Entity:

```ts
export interface Group {
  id: string;
  name: string;
  default_profile?: 'wintersport' | 'wandern' | 'summer-trekking' | 'allgemein';
  order: number;
}
```

API-Endpoints:
- `GET /api/groups` → Liste
- `POST /api/groups` → Anlegen
- `PATCH /api/groups/:id` → Umbenennen, default_profile
- `DELETE /api/groups/:id` → Group löschen (Orte werden auf null gesetzt)
- `PATCH /api/locations/:id` → `group_id` ändern (Drag-Move)

→ Vor diesem Issue: Backend muss `Group`-Entity und Endpoints liefern. Separates Backend-Issue erstellen.

## Required UI

### Sidebar

```svelte
<aside class="locations-sidebar">
  <header>
    <h3>Meine Orte</h3>
    <span class="meta">{totalLocs} Orte · {groups.length} Gruppen</span>
  </header>
  <SearchInput bind:value={query} />
  {#each groups as g}
    <GroupSection
      group={g}
      locations={locationsByGroup[g.id]}
      expanded={expandedGroups[g.id]}
      selected={selectedIds}
      onToggle={toggleGroup}
      onCheckLoc={checkLoc}
    />
  {/each}
  <footer>
    <Btn variant="outline" size="sm" onclick={openGroupDialog}>+ Gruppe</Btn>
    <Btn variant="primary" size="sm" onclick={openLocationDialog}>+ Ort</Btn>
  </footer>
</aside>
```

### GroupSection

- Klappbar (▶/▼)
- Header zeigt: Name, Profil-Dot (color by default_profile), Locations-Count
- Locations inside: branded Checkbox + Name + optional ProfileChip
- Shift-Klick auf Group-Header = alle Locations dieser Gruppe (de)select

### Default-Content: AutoReportsOverview

Statt der heutigen `CompareSubscriptionsPanel` mit Subscriptions:

```svelte
<section class="auto-reports">
  <Eyebrow>Orts-Vergleich · Auto-Reports</Eyebrow>
  <h1>Deine Auto-Reports</h1>
  <div class="auto-reports__grid">
    {#each autoReports as r}
      <AutoReportCard
        report={r}
        onclick={() => openEdit(r)}
      />
    {/each}
    <AddReportCard onclick={() => goto('/compare/new')} />
  </div>
</section>
```

### AutoReportCard

Spec design (siehe Soll-Mockup):
- Status-Dot (aktiv = green, pausiert = grey)
- Name + Group-Label
- Schedule mono ("täglich 07:00")
- "Letzter Lauf: …" als Footer

## Acceptance criteria

- [ ] `/compare` rendert 2-Spalten-Layout (Sidebar 320px + Content fill)
- [ ] Sidebar zeigt Orte gruppiert mit klappbaren Gruppen-Headers
- [ ] Default-Content (keine Selektion) zeigt Auto-Reports als Karten-Grid
- [ ] Suche filtert Orte sidebar-weit
- [ ] Klick auf einen Ortsnamen (ohne Checkbox) öffnet Edit-Dialog
- [ ] „+ Gruppe" und „+ Ort" Buttons in Sidebar-Footer
- [ ] Nav-Items `/locations` und `/subscriptions` aus der Sidebar entfernt

## 📎 Screenshots

**Soll: Master-Detail mit Gruppen-Sidebar**

![soll-3A](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-flow3A-sidebar-overview.png)