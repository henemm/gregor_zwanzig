# Context: Issue #386 — Home-Screen auf Atomic-Bibliothek migrieren

## Request Summary

Die Startseite `/` (Epic #368 Phase 2, Position 1/6) soll auf die Atomic-Bibliothek migriert werden. Zieldesign ist `soll-flow1A-home-kacheln.png` (Kachel-Layout, explizit KEIN Cockpit laut Design-Annotation im Screenshot).

## Soll vs. Ist — Unterschiede

### `+page.svelte`
| Ist | Soll |
|-----|------|
| H1 „Startseite" | H1 „Deine Touren & Vergleiche" |
| Kein Subtext | Subtext „Was du jetzt vorbereitest, läuft unterwegs autark..." |
| `<h2>` Sektions-Headers „Meine Touren" / „Orts-Vergleiche" | Keine Sektions-Headers (soll-flow1A zeigt flache Kachel-Liste) |
| Btn `variant="accent"` und `variant="outline"` | Btn-CTAs vorhanden, Varianten prüfen |

### `TripKachel.svelte`
| Ist | Soll |
|-----|------|
| `.kachel` = inline CSS-Klasse mit Duplikat-Styling | `data-slot="g-card"` auf `<a>`-Element (GCard-Token nutzen) |
| `.kachel__status` = inline Dot + Text mit `statusColors` Record | `Pill`-Atom mit tone-Mapping |
| Zeigt: Name + Datumsrange + „N Etappe(n)" | Zeigt: Name + Datumsrange + „N Etappen · Reports ✓" |

### `CompareKachel.svelte`
| Ist | Soll |
|-----|------|
| Gleiche `.kachel` Inline-CSS | `data-slot="g-card"` auf `<a>`-Element |
| `.kachel__status` Inline-Dot + Text | `Pill`-Atom |
| Zeigt: Name + Schedule + erste Location | „N Orte · letzter: heute" oder Schedule |

### `EmptyKachel.svelte`
Bereits vollständig migriert: nutzt `EmptyState` + `Btn`-Atome. **Keine Änderung nötig.**

## Relevante Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/+page.svelte` | Haupt-Route — Header + Grid-Layout |
| `frontend/src/routes/_home/TripKachel.svelte` | Trip-Kachel — Card + Pill Migration |
| `frontend/src/routes/_home/CompareKachel.svelte` | Compare-Kachel — Card + Pill Migration |
| `frontend/src/routes/_home/EmptyKachel.svelte` | Bereits migriert, kein Edit |
| `frontend/src/lib/components/ui/g-card/GCard.svelte` | GCard-Atom (`data-slot="g-card"`) |
| `frontend/src/lib/components/ui/pill/Pill.svelte` | Pill-Atom (tones: accent/success/ghost) |
| `frontend/src/lib/components/ui/btn/Btn.svelte` | Btn-Atom (variants: accent/outline/quiet) |
| `frontend/src/lib/components/ui/eyebrow/index.ts` | Eyebrow-Atom (bereits in Nutzung) |
| `frontend/src/app.css` | Token-Bridge + `[data-slot="g-card"]`-Styles |
| `docs/design-requests/issue_15_atomic_design/spec/screen-home.jsx` | Claude-Design-Vorlage (Cockpit) |
| `claude-code-handoff/screenshots/soll-flow1A-home-kacheln.png` | Kanonisches Soll-Screenshot |

## Library-Atoms — verfügbare API

### GCard (`$lib/components/ui/g-card`)
- `data-slot="g-card"` auf beliebigem Element → app.css styles: `background: var(--g-surface-1)`, `border-radius: var(--g-radius-lg)`, `box-shadow: var(--g-elev-1)`, hover: `var(--g-elev-2)`
- Für klickbare Kachel: `data-slot="g-card"` direkt auf `<a>` setzen (kein separates Div-Wrapper nötig)

### Pill (`$lib/components/ui/pill`)
- `tone="accent"` → orange Hintergrund (`--g-accent`) + `--g-ink` Text → für Status „aktiv"
- `tone="success"` → grüner Hintergrund (`--g-success`) + weißer Text → für Status „geplant"
- `tone="ghost"` → transparent + `--g-rule` border + `--g-ink-3` Text → für „fertig"/„draft"
- Sandbox-Aliase: `tone="good"` = success, `tone="bad"` = danger, `tone="warn"` = warning

### Btn (`$lib/components/ui/btn`)
- Bereits in `+page.svelte` in Nutzung
- Soll-CTA: `variant="accent"` für „+ Neue Tour", `variant="outline"` für „+ Neuer Vergleich"

## Pill-Tone-Mapping für Trip-Status

```
aktiv   → tone="accent"   (orange, auffällig — läuft gerade)
geplant → tone="success"  (grün — steht bevor)
fertig  → tone="ghost"    (grau — abgeschlossen)
draft   → tone="ghost"    (grau — unvollständig)
```

Hinweis: Soll-Screenshot zeigt Status als farbiges „● AKTIV"-Label (kleiner Dot + Text, kein Pill-Hintergrund). Die Pill-Variante mit `tone="accent"` gibt Hintergrund → Abweichung möglich. Klärung in Phase 2 erforderlich.

## Daten-Mapping

### Trip.status (abgeleitet)
Trip.status existiert NICHT im TypeScript-Interface — wird in `TripKachel.svelte` via `tripStatus()`-Funktion aus Stage-Dates berechnet.

### „Reports ✓" Indikator
- Prüfung: `trip.report_config?.morning_enabled || trip.report_config?.evening_enabled`
- Anzeige als Text-Suffix: `N Etappen · Reports ✓` (analog zu Soll-Screenshot)

### CompareKachel „N Orte"
- `sub.locations?.length` (Locations-Array, `*` = alle)
- `last_run` Feld: `Subscription` hat kein `last_run` in types.ts → ggf. weglassen oder als „letzter: unbekannt"

## Existierende Muster

- **Atomic-Card-Pattern in anderen Komponenten:** `StageCard.svelte`, `CompareKachel.svelte` im Compare-Screen nutzen GCard
- **Pill-Einsatz:** `TripRow` in Trips-Liste, `StatusBadge` Migration (DELIVERY-NOTE screen-trip-detail.jsx)
- **Anchor-als-Card:** Pattern bisher nicht kanonisch — TripKachel wäre erster Einsatz

## DELIVERY-NOTE Einschränkungen

- **screen-home.jsx: KEINE Inline-Helper zu ersetzen** (Mapping-Tabelle listet nur trips/trip-detail/wizard/compare/archive)
- TripKachel/CompareKachel sind page-lokale Komposita — bleiben page-lokal
- Token-Namen 1:1 aus JSX committen (Bridge #369 aktiv, kein Rename nötig)
- Weiße Karten (#378) Voraussetzung — seit commit 30bf513 live ✓

## Risiken

1. **GCard auf `<a>`-Element:** `data-slot="g-card"` auf Anchor-Tag gesetzt — CSS-Selektor [data-slot="g-card"] ist element-agnostisch, sollte funktionieren. Hover-Styles (box-shadow) überschreiben den bisherigen border-color-hover.
2. **Pill-Tone vs. Dot+Text-Design:** Soll-Screenshot zeigt farbigen Text (kein Pill-Hintergrund). Pill mit `tone="accent"` hätte Hintergrund-Fill. Abstimmung in Phase 3 (Spec).
3. **`last_run` fehlt in Subscription:** Compare-Kachel kann „letzter: heute" nicht aus echten Daten ableiten — ggf. nur Schedule zeigen.
4. **contrast-audit.test.ts:** Nach Änderungen muss Test-Suite grün bleiben.
