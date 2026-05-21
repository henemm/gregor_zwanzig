---
entity_id: issue_287_compare_polish
type: module
created: 2026-05-21
updated: 2026-05-21
status: draft
version: "1.0"
tags: [frontend, design-system, compare, ui-polish, svelte, issue-287]
---

# Issue #287 — Orts-Vergleich (Compare): Brand Checkboxes, Profile Pills, Settings Card Polish

## Approval

- [ ] Approved

## Purpose

Die drei Compare-Komponenten `LocationsRail`, `PresetHeader` und `CompareSubscriptionsPanel` verwenden noch Emoji-Zeichen für Aktivitätsprofile, Tailwind-Utility-Klassen für Status-Elemente und ein nacktes Datum-Input ohne Mono-Schrift. Dieses Modul ersetzt diese Ad-hoc-Muster durch Design-System-Komponenten (`Dot`, `Pill`) und Brand-Token-konforme CSS, sodass der Compare-Screen visuell konsistent mit dem übrigen Frontend ist.

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Frontend-Layer (`frontend/src/`). Kein Go-API-Code, kein Python-Backend-Code ist betroffen.

## Source

- **Layer:** Frontend / User-UI (`frontend/src/`)
- **Scope:** 3 Dateien, ~50 LoC netto

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/compare/LocationsRail.svelte` | Emoji → `[data-slot="dot"]`, Border-Divider via Token |
| `frontend/src/lib/components/compare/PresetHeader.svelte` | "Preset laden" → ghost variant, Datum-Input mono |
| `frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte` | Status-Dot → `<Dot>`, Badges → `<Pill>`, Bearbeiten-Button ergänzen |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/ui/dot/index.js` | Svelte-Komponente (vorhanden) | Ersetzt rohe Tailwind-Klassen für Status-Indikatoren in `CompareSubscriptionsPanel`; Props: `tone` (success/default), `size` (sm) |
| `frontend/src/lib/components/ui/pill/index.js` | Svelte-Komponente (vorhanden) | Ersetzt rohe Tailwind-Badge-Klassen; Props: `tone` (success/danger) |
| `frontend/src/lib/components/ui/btn` | Svelte-Komponente (vorhanden) | Ersetzt nativen `<button>` für "Preset laden" und neuen "Bearbeiten"-Button; Varianten: ghost; Größen: icon-sm |
| `@lucide/svelte/icons/pencil` | Icon-Bibliothek (vorhanden) | Icon für den "Bearbeiten"-Button in `CompareSubscriptionsPanel` |
| `frontend/src/app.css` | CSS-Datei (vorhanden) | `[data-slot="dot"]` und `--g-ink-faint` Token werden für den Divider in `LocationsRail` genutzt |
| `sig.accent` (ActivityProfile-Signatur) | Laufzeit-Datenproperty (vorhanden) | Hex-Farbe aus dem Aktivitätsprofil, wird als Inline-`background`-Style des Dots gesetzt |

## Implementation Details

### 1. `LocationsRail.svelte` — Emoji durch farbigen Dot ersetzen

**Grouped-Item-Rendering (~Zeilen 160–162):**

```diff
- <span>{sig.icon}</span>
+ <span data-slot="dot" data-size="xs" style="background: {sig.accent}; flex-shrink: 0;" title={sig.eyebrow}></span>
```

**Ungrouped-Item-Rendering (~Zeilen 185–187):** Identische Ersetzung wie oben.

**Profil-Filter-Pills (~Zeilen 114–123):** Emoji vor dem Eyebrow-Text durch Dot mit rechtem Abstand ersetzen:

```diff
- {sig.icon} {sig.eyebrow}
+ <span data-slot="dot" data-size="xs" style="background: {sig.accent}; flex-shrink: 0; margin-right: 4px;" title={sig.eyebrow}></span>{sig.eyebrow}
```

**Border-Divider:** Dem äußersten `<div>` der Rail den rechten Trennstrich per Token-basiertem Inline-Style geben, statt der Tailwind-Klasse `border-r` ohne Token:

```diff
- class="... border-r ..."
+ style="border-right: 1px solid color-mix(in srgb, var(--g-ink-faint) 40%, transparent);"
```

### 2. `PresetHeader.svelte` — Button-Variante + Mono-Datum

**"Preset laden"-Button (~Zeile 112):** Von `outline` auf `ghost` umstellen, da der Button deaktiviert ist und keine visuelle Gewichtung benötigt:

```diff
- <Btn variant="outline" disabled={true}>Preset laden</Btn>
+ <Btn variant="ghost" disabled={true}>Preset laden</Btn>
```

**Datum-Input (`id="cmp-date"`):** Klasse `font-mono` ergänzen, damit Ziffern in Mono-Schrift (`var(--g-font-data)`) erscheinen und horizontal stabil bleiben:

```diff
- <input id="cmp-date" type="date" ...>
+ <input id="cmp-date" type="date" class="... font-mono" ...>
```

Falls keine Tailwind-Klasse verwendet wird, alternativ Inline-Style: `style="font-family: var(--g-font-data);"`.

### 3. `CompareSubscriptionsPanel.svelte` — Dot, Pill, Bearbeiten-Button

**Imports am Dateianfang ergänzen:**

```svelte
import Dot from '$lib/components/ui/dot/index.js';
import Pill from '$lib/components/ui/pill/index.js';
import Btn from '$lib/components/ui/btn';
import PencilIcon from '@lucide/svelte/icons/pencil';
```

**Status-Dot (~Zeilen 56–61):** Rohe Tailwind-Klassen durch `<Dot>`-Komponente ersetzen:

```diff
- <div class="mt-1 h-2 w-2 shrink-0 rounded-full {sub.enabled ? 'bg-green-500' : 'bg-gray-300'}"></div>
+ <Dot tone={sub.enabled ? 'success' : 'default'} size="sm" />
```

**Status-Badges (~Zeilen 70–80):** Rohe Tailwind-Badge-Spans durch `<Pill>`-Komponenten ersetzen:

```diff
- <span class="... bg-green-100 text-green-700 ...">ok</span>
+ <Pill tone="success">ok</Pill>

- <span class="... bg-red-100 text-red-700 ...">Fehler</span>
+ <Pill tone="danger">Fehler</Pill>
```

**"Bearbeiten"-Button im Card-Header:** Nach dem bestehenden Karten-Titel-Element einfügen:

```svelte
<Btn variant="ghost" size="icon-sm" title="Bearbeiten">
  <PencilIcon class="size-3.5" />
</Btn>
```

Der Button benötigt keine `onclick`-Logik im Scope dieser Aufgabe — er ist ein visuelles Placeholder-Element, das die Bearbeiten-Affordance signalisiert. Eine konkrete Aktion (z.B. Öffnen eines Bearbeiten-Dialogs) ist Gegenstand eines eigenen Issues.

### Umsetzungsreihenfolge

1. `LocationsRail.svelte` — keine Import-Abhängigkeiten, reine Inline-Style-Änderungen
2. `PresetHeader.svelte` — keine neuen Imports, Klassen- und Varianten-Änderung
3. `CompareSubscriptionsPanel.svelte` — benötigt neue Imports (Dot, Pill, Btn, PencilIcon)

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/lib/components/compare/LocationsRail.svelte` | ~+10 / -6 | ja |
| `frontend/src/lib/components/compare/PresetHeader.svelte` | ~+3 / -2 | ja |
| `frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte` | ~+20 / -8 | ja |
| **Gesamt** | **~+17 netto** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Bestehende Compare-Daten (Location-Signaturen mit `sig.accent`/`sig.eyebrow`/`sig.icon`, Subscription-Objekte mit `sub.enabled` und Status-Text)
- **Output (visuell):**
  - Aktivitätsprofil-Dots in der Rail-Liste und in den Filter-Pills zeigen einen farbigen Kreis (Farbe aus `sig.accent`) statt eines Emoji-Zeichens
  - Filter-Pills zeigen farbigen Dot + Eyebrow-Text, kein Emoji mehr
  - Outer-Rail hat einen Token-konformen Trennstrich rechts (`--g-ink-faint` mit 40 % Opacity via `color-mix`)
  - "Preset laden"-Button ist visuell ruhig (ghost, disabled), kein outlined Border
  - Datum-Input im PresetHeader zeigt Ziffern in Mono-Schrift
  - Status-Indikatoren in Auto-Report-Karten sind `<Dot>`-Komponenten mit `tone="success"` (grün) oder `tone="default"` (grau)
  - Status-Badges "ok" und "Fehler" nutzen `<Pill tone="success">` bzw. `<Pill tone="danger">`
  - Jede Auto-Report-Karte hat einen "Bearbeiten"-Icon-Button (ghost, icon-sm) im Header
- **Side effects:** Keine. Alle Änderungen sind lokal zu den drei Komponenten. Keine gemeinsamen CSS-Regeln werden verändert.

## Acceptance Criteria

**AC-1:** Given der Compare-Screen mit mindestens einem Location-Eintrag mit zugewiesenem Aktivitätsprofil / When die LocationsRail gerendert wird / Then enthält kein Location-Listen-Item mehr ein Emoji-Zeichen (`sig.icon`) — stattdessen ist ein `<span data-slot="dot">` mit Inline-`background`-Color aus `sig.accent` vorhanden.
  - Test: (populated after /tdd-red)

**AC-2:** Given der Compare-Screen mit aktiven Profil-Filter-Pills in der LocationsRail / When die Pill-Chips gerendert werden / Then zeigt jede Pill einen farbigen Dot-Span (`data-slot="dot"`) gefolgt vom Eyebrow-Text, und kein Emoji-Zeichen ist im Text-Content der Pill enthalten.
  - Test: (populated after /tdd-red)

**AC-3:** Given der PresetHeader im Compare-Screen / When die Komponente gerendert wird / Then hat der "Preset laden"-Button das Attribut `data-variant="ghost"` (oder entsprechende Klasse) und nicht `data-variant="outline"`, und ist deaktiviert.
  - Test: (populated after /tdd-red)

**AC-4:** Given der PresetHeader im Compare-Screen / When die Komponente gerendert wird / Then hat das Datum-Input-Element (`id="cmp-date"`) die Klasse `font-mono` oder den Inline-Style `font-family: var(--g-font-data)`, sodass Ziffern in Mono-Schrift erscheinen.
  - Test: (populated after /tdd-red)

**AC-5:** Given der CompareSubscriptionsPanel mit mindestens einer aktiven Subscription (`sub.enabled = true`) und einer inaktiven (`sub.enabled = false`) / When die Karten gerendert werden / Then ist der Status-Indikator der aktiven Subscription ein `<Dot>` mit `tone="success"` (grüne Farbe aus Design-Token) und der der inaktiven ein `<Dot>` mit `tone="default"` (grau), und keine rohen Tailwind-Klassen `bg-green-500` oder `bg-gray-300` sind im DOM-Output vorhanden.
  - Test: (populated after /tdd-red)

**AC-6:** Given der CompareSubscriptionsPanel mit Subscriptions, die Status-Text "ok" oder "Fehler" aufweisen / When die Karten gerendert werden / Then erscheint "ok" als `<Pill tone="success">` (grüner Hintergrund, grüner Text via `--g-success`) und "Fehler" als `<Pill tone="danger">` (roter Hintergrund, roter Text via `--g-danger`), und kein roher Tailwind-Badge-Span ist im Quelltext vorhanden.
  - Test: `grep -c "bg-green-100\|bg-red-100" frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte` → `0`

**AC-7:** Given der CompareSubscriptionsPanel mit mindestens einer Subscription-Karte / When die Karte gerendert wird / Then ist im Card-Header ein `<Btn variant="ghost" size="icon-sm">` mit einem `<PencilIcon>`-Element enthalten und `title="Bearbeiten"` gesetzt.
  - Test: (populated after /tdd-red)

## Known Limitations

- Der "Bearbeiten"-Button in `CompareSubscriptionsPanel` hat in dieser Spec keine `onclick`-Logik. Die Bearbeiten-Funktion selbst ist einem separaten Issue vorbehalten.
- `color-mix(in srgb, ...)` wird in Safari < 16.2 nicht unterstützt. Da das Frontend laut CLAUDE.md ein Desktop-Planungstool ist und Safari < 16.2 auf Desktop kaum noch vorkommt, ist das akzeptabel. Als Fallback bleibt der Divider bei nicht-unterstützten Browsern unsichtbar.
- Der `data-slot="dot"`-Span in `LocationsRail` ist ein natives HTML-Element, kein `<Dot>`-Komponent, da die Farbe dynamisch aus `sig.accent` kommt und die `<Dot>`-Komponente nur Token-basierte Tones unterstützt. Dieser Unterschied ist beabsichtigt und dokumentiert.

## Changelog

- 2026-05-21: Initial spec created (Issue #287 — Compare Polish: Profile Dots, Ghost Button, Mono Date, Dot/Pill in Subscriptions Panel)
