<!-- gregor-zwanzig-handoff: stable_id=uebersicht-listen-tabelle -->
## Problem

Die beiden Workspace-Übersichten hatten **unterschiedliche Layouts** für
funktional identische Inhalte:

- **Trips** (`/trips`) → Tabelle (Zeilen, Spalten Name · Etappen · Zeitraum · Aktionen).
- **Orts-Vergleiche** (`/compare`) → Kachel-Grid (`CompareTile`, Charter §3 v1.1, 2026-05-31).

Beide sind dasselbe: eine Liste von einzurichtenden/zu überwachenden Abos, jede
Zeile/Kachel ein Einstiegspunkt ins Setup/Detail plus Sekundär-Aktionen. Es gab
keinen inhaltlichen Grund für die Divergenz — die Kachel-Umstellung (§3 v1.1)
wurde nie auf Trips angewandt, und die Trip-Tabelle nie auf die Vergleiche.

> **PO-Entscheid 2026-07-16 (Henning):** *„Führe beide als Tabelle. Verwende
> den gleichen Code / Atoms / Elemente."*

Begründung (Tech-Lead, bestätigt): Das Produkt ist ein **Monitoring-/Setup-
Werkzeug**, kein Galerie-/Browse-Erlebnis. Der User scannt Status, Zeitraum,
„was läuft" — dafür ist eine dichte, links-ausgerichtete Tabelle mit fester
Spalten-Reihenfolge überlegen und deckt sich mit dem Cockpit-/Hochkontrast-
Prinzip (CLAUDE.md). Dies **kehrt die Kachel-Entscheidung aus §3 v1.1 / #10 für
die Desktop-Übersicht bewusst um.**

## Lösung (verbindlich = kanonisches Mockup)

**Ein geteiltes Tabellen-Organism `ListTable`** (in `organisms.jsx`), das beide
Übersichten rendern. Fachliche Unterschiede stecken NUR in den `columns`-
Definitionen + Aktions-Listen, die der jeweilige Screen übergibt — Chassis,
Zeilen-Verhalten, Overflow-Menü und Tabellenkopf sind identisch.

Maßgeblich sind die kanonischen JSX-Mockups
`claude-code-handoff/current/jsx/screen-trips.jsx`,
`current/jsx/screen-compare-list.jsx` und `current/jsx/organisms.jsx`
(1:1-Quelle für Epic #575) sowie die SOLL-Bilder unten.

### `ListTable`-API (organisms.jsx)

```
ListTable({
  columns,      // [{ key, header, align?, width?, render(row) }]
  rows,         // Daten-Array
  getRowId,     // (row) => stabile Key/Id
  onRowClick,   // (row) => void — ganze Zeile klickbar → Detail/Setup
  rowActions,   // (row) => [{ key, label, danger? }] | null — Overflow-Menü (⋯)
  rowPrimary,   // (row) => { label, onClick } | null — inline Quick-Action
  onAction,     // (key, row) => void — Auswahl aus dem Overflow-Menü
  emptyText,    // Text bei leerer Liste
})
```

Zugehörige Sub-Organismen (ebenfalls in `organisms.jsx`, auf `window`
exportiert): `ListTableRow`, `ListActionsMenu`, `ListNameCell`
(Status-Dot + Name + Status-Label; `dotColor` beliebig, da die Status-Paletten
von Trip und Vergleich unterschiedlich sind).

### Gemeinsames Zeilen-Verhalten (beide Übersichten)

1. **Ganze Zeile klickbar** → Detail/Setup (`onRowClick`). Hover-Highlight
   (`--g-card-alt`), Zebra-Streifen (`--g-paper-deep` auf ungeraden Zeilen),
   Chevron (`›`) am rechten Rand.
2. **Alle Sekundär-Aktionen in EINEM Overflow-Menü (`⋯`)** — kein
   Icon-Geschwader (konsistent zu #04).
3. **Aktive Einträge** zeigen zusätzlich **eine** inline Quick-Action
   „Briefing senden" links vom `⋯`.
4. Tabellenkopf mono-caps auf `--g-paper-deep`; rechte Spalte immer „Aktionen".

### Spalten

**Trips** (`screen-trips.jsx`): Name (Status-Dot + Label) · Etappen · Zeitraum.
Overflow-Menü unverändert zu #04 (Briefing senden nur aktiv · Email-Vorschau ·
Alert-Konfiguration · Wetter-Metriken · Bearbeiten · Löschen).

**Orts-Vergleiche** (`screen-compare-list.jsx`): Name (Status-Dot + Label) ·
Orte · Profil (`N Orte · Region` + `profileLabel`) · Kanäle (Mono-Pills) ·
Zeitplan (`schedule` + `zuletzt lastSent`, bei Draft „Setup unvollständig").
Overflow-Menü = `compareActions(status)` (unverändert). Klick → `onOpen(id)`
öffnet den Detail-Hub (nicht das Tages-Briefing).

### Status-Paletten (unverändert übernommen)

- Trip: aktiv `--g-accent` · geplant `#3d6b3a` · fertig `--g-ink-3` · draft `--g-ink-4`
- Vergleich: aktiv `--g-good` · pausiert `--g-ink-3` · draft `--g-ink-4`

## Was bleibt / entfällt

- `CompareTile` / `CompareKebab` (molecules.jsx) bleiben — sie tragen weiterhin
  die **Mobile-Kachelliste** (`screen-compare-list-mobile.jsx`) und die
  **Home-Kachel**. Nur die **Desktop-Übersicht** nutzt sie nicht mehr.
- Die frühere lokale `TripRow` / `TripsActionsMenu` / `tripsIcon` in
  `screen-trips.jsx` sind durch `ListTable` ersetzt (Inline-Drift aufgelöst).
- Der Trips-Summary-Streifen nutzt jetzt das `Stat`-Molecule (`layout="inline"`)
  statt der lokalen `SummaryStat` — identisch zur Compare-Übersicht.

## Mobile

**Kein Change.** Beide Mobile-Übersichten bleiben karten-basiert
(`TripCardM` bzw. `CompareTile dense`) — auf schmalen Viewports sind Karten
korrekt und dort sind beide Übersichten bereits konsistent. Tabellen sind eine
reine Desktop-Angleichung.

## Acceptance Criteria

- [ ] `ListTable` + `ListTableRow` + `ListActionsMenu` + `ListNameCell` existieren als geteilte Komponenten (kein Fork je Screen).
- [ ] `/trips` und `/compare` (Desktop) rendern beide über `ListTable` mit identischem Zeilen-Verhalten (ganze Zeile klickbar · Zebra · Hover · Chevron · ⋯-Menü · inline „Briefing senden" nur aktiv).
- [ ] Trip-Overflow-Menü = 6 Einträge wie #04; Compare-Overflow-Menü = `compareActions(status)`.
- [ ] Compare-Zeile-Klick öffnet den Detail-Hub (Übersicht), nicht das Tages-Briefing.
- [ ] Keine Inline-Tabellen-/Kachel-Variante mehr in den Desktop-Screens (Atomic-Disziplin).
- [ ] Mobile unverändert (Karten).
- [ ] `data-testid` / bestehende Selektoren, wo vorhanden, erhalten.

## SOLL-Bilder

![Trips als Tabelle](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-uebersicht-listen-tabelle-trips.png)

![Orts-Vergleiche als Tabelle](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-uebersicht-listen-tabelle-compare.png)

## Bezug / Cross-Links (Regel 6 — vor Anlegen prüfen)

- **#04** (`screen-trips-list`) — Trips-Zeilen-Verhalten (⋯-Menü, ganze Zeile
  klickbar, inline „Briefing senden") bleibt gültig; dieses Issue hebt es auf
  die geteilte `ListTable` und wendet es auf die Vergleiche an. Cross-linken.
- **#10** (`ortsvergleich-wizard`) — dessen **Kachel-Grid-Übersicht (§3 v1.1)**
  wird für Desktop durch die Tabelle **ersetzt**. Body von #10 cross-linken/
  annotieren, nicht duplizieren.
- **#1256** (`compare-ui-fragen-1256`) — rendert die Compare-Liste-SOLL-Bilder
  neu; dieses Issue liefert das neue Tabellen-SOLL. Abgleichen.
- **Epic #575** — kanonische Snapshots `current/jsx/screen-trips.jsx`,
  `current/jsx/screen-compare-list.jsx`, `current/jsx/organisms.jsx` und die
  SOLL-Bilder `current/soll/E-trips-list-variant.png` +
  `current/soll/G-compare-uebersicht-tabelle.png` sind mitgezogen; das 1:1-Sub-
  Issue der Compare-Liste zieht auf die Tabelle um (SOLL-COVERAGE aktualisiert,
  `G-compare-uebersicht-kacheln.png` = superseded).
