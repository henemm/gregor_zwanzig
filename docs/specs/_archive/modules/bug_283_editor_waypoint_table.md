---
entity_id: bug_283_editor_waypoint_table
type: bugfix
created: 2026-05-21
updated: 2026-05-21
status: implemented
version: "1.0"
tags: [frontend, editor, waypoints, design-system, css-tokens, typography, accordion]
---

# Bug 283 — Trip-Editor: Wegpunkte als echte Tabelle mit Mono-Koordinaten und Höheneinheit

## Approval

- [ ] Approved

## Purpose

Der Trip-Editor zeigt Wegpunkte aktuell ohne Spaltenbeschriftung und ohne typografische Differenzierung zwischen Namen und numerischen Koordinaten. Dieser Fix bringt den Editor in Einklang mit dem Design-System: Koordinaten- und Höheneingaben erhalten JetBrains Mono mit tabellarischer Zahlausrichtung, eine Desktop-Kopfzeile benennt die vier Spalten, und die `m`-Einheit erscheint als visueller Suffix am Höhenfeld. Gleichzeitig werden die Accordion-Abschnitte (Stage-Karten) auf Design-Token-Farben und ein Chevron-Icon statt ASCII `+`/`-` umgestellt.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`)
- **Scope:** 3 Dateien — 1 Editor-Komponente, 1 shared Accordion-Komponente, 1 globales CSS

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/app.css` | Zwei neue Utility-Klassen: `.g-num-input`, `.g-th` |
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | Kopfzeile für Wegpunkt-Spalten, Mono-Klassen auf numerischen Inputs, `m`-Einheitssuffix |
| `frontend/src/lib/components/edit/AccordionSection.svelte` | Design-Token-Farben für offen/geschlossen, ChevronDown-Icon statt ASCII |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` `:root` | Upstream | Definiert `--g-font-data` (JetBrains Mono, Z. 94), `--g-surface-2`, `--g-ink`, `--g-ink-faint`, `--g-ink-muted`, `--g-text-sm`, `--g-radius-md` |
| `lucide-svelte` | Package | Liefert `ChevronDown`-Icon (bereits installiert) |
| iOS-Safari-Media-Query in `app.css` | Constraint | `@media (max-width: 767px)` setzt Eingabefelder auf `font-size: 16px` — muss unverändert bleiben, damit Auto-Zoom auf iOS ausbleibt (Bug #272) |
| `data-testid`-Attribute in EditStagesSection | Constraint | `waypoint-{wi}`, `wp-name`, `wp-lat`, `wp-lon`, `wp-ele`, `wp-trash-mobile`, `stage-card-{si}` dürfen nicht entfernt oder umbenannt werden |

## Implementation Details

### Schritt 1: `app.css` — 2 neue Utility-Klassen

```css
.g-num-input {
  font-family: var(--g-font-data);
  font-variant-numeric: tabular-nums;
  font-size: var(--g-text-sm);
}

.g-th {
  font-family: var(--g-font-data);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--g-ink-faint);
}
```

Beide Klassen werden nach den bestehenden globalen Utility-Blöcken eingefügt. `.g-num-input` greift für alle numerischen Eingaben (Koordinaten, Höhe, Datum). `.g-th` dient als Tabellenkopf-Caption — identisch zum Pattern aus dem Compare-Screen.

### Schritt 2: `EditStagesSection.svelte` — Kopfzeile + Mono-Klassen + Einheitssuffix

**Kopfzeile vor `{#each stage.waypoints}`:**

```svelte
<!-- Desktop-only header row, hidden on mobile -->
<div class="hidden sm:grid grid-cols-[1fr_88px_88px_88px_32px] gap-1 px-1 mb-1">
  <span class="g-th">Name</span>
  <span class="g-th text-right">Lat</span>
  <span class="g-th text-right">Lon</span>
  <span class="g-th text-right">Höhe</span>
  <span></span>
</div>
```

**Lat/Lon-Inputs:** Klassen `g-num-input text-right` ergänzen, Breite `sm:w-[88px]` setzen. Bestehende `data-testid`-Attribute (`wp-lat`, `wp-lon`) bleiben unverändert.

**Elevation-Input:** Input erhält `g-num-input text-right`. Wrapper-Label `.g-num-with-unit` positioniert ein `<span>` mit `m` (faint) am rechten Rand per `position: absolute; right: 6px`. Das `data-testid="wp-ele"` bleibt am Input-Element.

**Stage-Datum-Input:** Klasse `g-num-input` ergänzen, damit Datumsangaben tabellarisch ausrichten.

### Schritt 3: `AccordionSection.svelte` — Token-Farben + Chevron

**Geschlossener Zustand:** `bg-muted/50` → `style="background: var(--g-surface-2)"` (oder entsprechende Token-Klasse).

**Offener Zustand:** `bg-primary/10 text-primary` → `style="background: var(--g-surface-2); color: var(--g-ink)"`.

**Border im offenen Zustand:** `border-primary` → `border-[var(--g-ink-faint)]`.

**Radius:** `rounded-lg` → `rounded-[var(--g-radius-md)]` (beide Zustände).

**Icon:** ASCII `+`/`-` durch ChevronDown-Icon ersetzen:

```svelte
<script>
  import { ChevronDown } from 'lucide-svelte';
</script>

<!-- Im Header-Button statt + / - : -->
<ChevronDown
  size={14}
  style="color: var(--g-ink-muted); transform: rotate({open ? 180 : 0}deg); transition: transform 0.2s;"
/>
```

### Umsetzungsreihenfolge

1. `app.css` — `.g-num-input` und `.g-th` ergänzen
2. `EditStagesSection.svelte` — Kopfzeile, Mono-Klassen, `m`-Suffix
3. `AccordionSection.svelte` — Token-Farben, Radius, Chevron-Icon

## Expected Behavior

- **Input:** Trip-Editor mit mindestens einer Stage und einem Wegpunkt geöffnet
- **Output:** Auf Desktop (≥640px) erscheint eine Kopfzeile mit den Spalten Name / Lat / Lon / Höhe in Mono-Uppercase-Caption; Koordinaten- und Höheneingaben werden in JetBrains Mono rechtsbündig mit tabellarischen Ziffern gerendert; hinter dem Höhenwert steht ein faint `m`; Stage-Karten zeigen `--g-surface-2`-Hintergrund mit Chevron-Icon; auf Mobile (≤639px) bleibt die Kopfzeile ausgeblendet
- **Side effects:** `.g-num-input` und `.g-th` werden als globale Klassen in `app.css` verfügbar und können von anderen Komponenten genutzt werden — unkritisch, da rein additive Ergänzungen

## Acceptance Criteria

- **AC-1:** Given der Trip-Editor auf einem Desktop-Viewport (≥640px) mit mindestens einem Wegpunkt / When die Stage-Karte geöffnet ist / Then ist eine Kopfzeile mit den Beschriftungen "NAME", "LAT", "LON", "HÖHE" in Uppercase-Mono-Schrift oberhalb der Wegpunkt-Zeilen sichtbar
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Wegpunkt mit ausgefüllten Koordinaten im Trip-Editor / When der Editor gerendert wird / Then verwenden die Lat- und Lon-Eingabefelder `font-family: var(--g-font-data)` mit `font-variant-numeric: tabular-nums` und sind rechtsbündig ausgerichtet
  - Test: (populated after /tdd-red)

- **AC-3:** Given das Höhen-Eingabefeld eines Wegpunkts im Trip-Editor / When der Wegpunkt gerendert wird / Then erscheint rechts neben dem Eingabewert ein faint `m`-Suffix, der die Einheit signalisiert ohne das `wp-ele`-Testid-Attribut zu entfernen
  - Test: (populated after /tdd-red)

- **AC-4:** Given das Datumsfeld einer Stage im Trip-Editor / When die Stage-Karte gerendert wird / Then verwendet das Datums-Eingabefeld die Klasse `g-num-input` mit JetBrains Mono und tabellarischen Ziffern
  - Test: (populated after /tdd-red)

- **AC-5:** Given eine Stage-Karte im geschlossenen und geöffneten Zustand / When der Accordion-Header gerendert wird / Then zeigt der Header `var(--g-surface-2)` als Hintergrund und ein rotierendes ChevronDown-Icon (14px, `--g-ink-muted`) statt ASCII `+`/`-`
  - Test: (populated after /tdd-red)

- **AC-6:** Given alle bestehenden Wegpunkt-Testids im EditStagesSection (`waypoint-{wi}`, `wp-name`, `wp-lat`, `wp-lon`, `wp-ele`, `wp-trash-mobile`, `stage-card-{si}`) / When Playwright-Tests nach dem Fix ausgeführt werden / Then liefern alle Selektoren die gleichen Elemente wie vor dem Fix — keine Regression
  - Test: (populated after /tdd-red)

## Known Limitations

- Die Kopfzeile ist Desktop-only (`hidden sm:grid`); auf Mobile-Viewports (≤639px) entfällt die Spaltenbeschriftung — akzeptiert, da der Editor ein Desktop-Planungstool ist (vgl. project_frontend_purpose.md)
- `.g-num-with-unit` für den `m`-Suffix benötigt `position: relative` am Wrapper-Label; falls andere Stellen dieses Pattern nutzen wollen, sollte die Klasse ebenfalls in `app.css` aufgenommen werden — für diesen Fix inline gelöst
- Der Chevron-Rotations-Übergang (`transition: transform 0.2s`) erfordert, dass `open` als reaktive Svelte-Variable vorliegt — bei anderen AccordionSection-Nutzern ist zu prüfen, ob die Variable den gleichen Namen trägt

## Changelog

- 2026-05-21: Initial spec created (Bug #283)
