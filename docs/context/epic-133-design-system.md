# Context: Epic #133 — Design System & Tokens

## Request Summary
Design-Tokens, Typografie, Atom-Komponenten und Sidebar aus dem Redesign v2 in SvelteKit portieren. Dieses Epic ist das Fundament für alle weiteren Epics (#134–#140). Sub-Issues: #141 (Tokens), #142 (Schriften), #143 (Topo-Muster), #144 (Atom-Komponenten), #145 (Sidebar), #146 (ElevSparkline).

## Related Files

| File | Relevanz |
|------|---------|
| `frontend/src/app.css` | **Haupt-Änderung**: `@theme`-Block + `--g-*`-Tokens hinzufügen |
| `frontend/src/app.html` | Google Fonts `<link>` einbinden |
| `frontend/src/routes/+layout.svelte` | Sidebar-Code wird zu `<Sidebar>`-Komponente extrahiert |
| `frontend/src/lib/components/ui/button/button.svelte` | Referenz-Pattern: shadcn + `tv()` + `cn()` |
| `frontend/src/lib/components/ui/card/card.svelte` | Referenz-Pattern: `data-slot`, Varianten |
| `frontend/src/lib/components/ui/badge/badge.svelte` | Referenz-Pattern: Pill-ähnlich |
| `frontend/src/lib/utils/cn.ts` | `cn()` — wird von allen neuen Komponenten genutzt |
| `frontend/src/lib/utils.ts` | Re-exportiert `cn` + `WithElementRef` |

## Neue Dateien (zu erstellen)

| File | Zuständig für |
|------|--------------|
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | Issue #145 — Sidebar-Komponente |
| `frontend/src/lib/components/ui/sidebar/index.ts` | Re-Export |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | Issue #144 — Btn Atom |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Issue #144 — Pill Atom |
| `frontend/src/lib/components/ui/eyebrow/Eyebrow.svelte` | Issue #144 — Eyebrow Atom |
| `frontend/src/lib/components/ui/dot/Dot.svelte` | Issue #144 — Dot Atom |
| `frontend/src/lib/components/ui/topo/TopoBg.svelte` | Issue #143 — Topo-Hintergrundmuster |
| `frontend/src/lib/components/ui/elev-sparkline/ElevSparkline.svelte` | Issue #146 — SVG Höhenprofil |

## Design-Token-Spec (aus Epic-Text)

```css
/* Primärfarben */
--g-accent:  #c45a2a;   /* burnt orange — Akzente, CTAs */
--g-paper:   #f6f4ee;   /* warm off-white — Seiten-Hintergrund */
--g-ink:     #1a1a18;   /* fast schwarz — Text */
```

Fehlende Token-Gruppen (Issue #141 Scope, müssen in Phase 3/Spec definiert werden):
- Surface-Tokens (bg-Stufen: paper, card, overlay)
- Semantic (destructive, warning, success, info)
- Wetter-Farben (Regen, Sonne, Wind, Schnee)
- Typography (font-sizes, line-heights)
- Spacing-Skala
- Radii
- Elevation (box-shadow-Stufen)

## Schriften (Issue #142)

- **Inter Tight** — UI-Text (Labels, Menü, Headings)
- **JetBrains Mono** — Daten, Koordinaten, Uhrzeiten
- Einbindung via Google Fonts `<link>` in `app.html`

## Topo-Hintergrundmuster (Issue #143)

CSS `radial-gradient` Pattern → `.g-topo`-Klasse in `app.css` + `<TopoBg opacity={0.04}>` Svelte-Komponente.

## ElevSparkline (Issue #146)

SVG-Komponente mit Props: `data: number[]`, `width: number`, `height: number`, `active?: boolean`. Kein externer Chart-Chart-Library — reines SVG.

## Existing Patterns

- **Komponenten-Muster**: `shadcn-svelte` — `tv()` für Varianten, `cn()` für class-Merging, `data-slot`-Attribut, `WithElementRef<HTMLAttributes>` als Props-Typ
- **Tailwind 4**: `@theme`-Block in `app.css` statt `tailwind.config.js` — CSS Custom Properties als Token
- **Token-Namespace**: Bestehend `--color-*` (shadcn/Tailwind-intern). Neu: `--g-*` (gregor-eigene Tokens). Beide koexistieren.
- **Dark Mode**: Derzeit via JS in `+layout.svelte` (CSS-Props auf `documentElement` setzen) — `prefers-color-scheme` noch nicht genutzt
- **Icons**: `@lucide/svelte` — Import per Icon-Name

## Dependencies

- **Upstream**: SvelteKit 2, Svelte 5 (Runes), Tailwind CSS 4, `tailwind-variants`, shadcn-svelte, `@lucide/svelte`
- **Downstream**: Alle anderen Epics (#134–#140) bauen auf diesen Tokens + Komponenten auf. Die `<Sidebar>`-Komponente wird direkt in `+layout.svelte` eingebunden.

## Existing Specs

- `docs/specs/modules/design_optimierungen.md` — Ältere Design-Anpassungen (F74/F76), bereits implementiert
- `docs/specs/modules/nav_redesign_phase_a.md` — Nav-Redesign Phase A (bereits implementiert)
- `docs/specs/ux_redesign_navigation.md` — UX-Redesign Gesamt-Vision

## Analyse-Ergebnisse (Phase 2)

### Kritischer Bug: E2E-Tests rot
`nav-redesign.spec.ts` (7 Tests) erwartet `'Meine Touren'`, `+layout.svelte` liefert `'Meine Trips'`. Tests sind **aktuell rot**. Muss im Rahmen von Issue #145 (Sidebar-Extraktion) behoben werden.

### ElevSparkline-Datenprovider
`Waypoint.ElevationM` existiert bereits in `internal/model/trip.go`. Kein neuer Backend-Endpunkt nötig. Consumer extrahieren: `trip.stages.flatMap(s => s.waypoints.map(w => w.elevation_m))`.

### `WithElementRef`-Import
Neue Atoms können `WithElementRef` direkt aus `"bits-ui"` importieren oder darauf verzichten — beides ist sicherer als der Re-Export-Pfad.

### Empfohlene Implementierungsreihenfolge
`#141` (Tokens) → `#142` (Fonts) → `#145` (Sidebar, behebt E2E-Bug) → `#143` (Topo) → `#144` (Atoms) → `#146` (ElevSparkline)

### Zwei Developer-Läufe empfohlen
- **Lauf A**: #141 + #142 + #145 (~194 LoC) — ändert bestehende Dateien, E2E-Tests verifizierbar
- **Lauf B**: #143 + #144 + #146 (~378 LoC) — nur neue Dateien, kein Regressions-Risiko

### Gesamt-Scope
~572 LoC, 14 neue Dateien, 3 geänderte Dateien. Keine neuen npm-Pakete nötig.

## Kritische Entscheidungen für Phase 3 (Spec)

1. **Token-Vollständigkeit**: Die Epic-Beschreibung nennt Primärfarben + Schriften, aber Issue #141 fordert 9 Token-Gruppen. Die fehlenden Gruppen müssen in der Spec mit konkreten Werten definiert werden — ohne tokens.css-Quelldatei müssen wir die Werte selbst festlegen (abgestimmt auf Design-Intent).

2. **Atom-Komponenten vs. shadcn**: `Btn`, `Card` etc. koexistieren mit bestehenden shadcn-Komponenten. Die neuen Atoms sind `--g-*`-aware und werden für neue Epics genutzt, die shadcn-Komponenten bleiben für bestehende Screens erhalten.

3. **Sidebar-Extraktion**: Der Sidebar-Code aus `+layout.svelte` (~80 LoC) wird in `<Sidebar>`-Komponente extrahiert — bestehende Funktionalität bleibt 1:1 erhalten, nur refaktoriert.

4. **Schriften-Fallback**: Google Fonts erfordern Internetverbindung. Lokal-Hosting als Alternative, falls Offline-First wichtig ist.

## Risks & Considerations

- **tokens.css fehlt**: Die referenzierte Quelldatei existiert nicht im Repo. Die Spec muss Token-Werte selbst definieren.
- **Kein Breaking Change**: Bestehende shadcn-Komponenten dürfen nicht verändert werden — alle neuen Atoms sind additiv.
- **Sidebar-Extraktion**: Ist rein strukturell, kein Feature-Change — Risiko gering.
- **ElevSparkline**: Kein Höhenprofil-Datenprovider vorhanden — Komponente bekommt `data: number[]` als Prop und wird von übergeordneten Komponenten befüllt.
