---
entity_id: issue_313_design_showcase
type: module
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [frontend, design-system, showcase, svelte, issue-313]
---

# Issue #313 — `/_design` Showcase vervollständigen

## Approval

- [ ] Approved

## Purpose

Die `/_design`-Seite ist die interne Komponentenbibliothek der App. Sie zeigt aktuell nur einen Bruchteil der verfügbaren UI-Komponenten. Dieses Modul erweitert die bestehende Seite so, dass alle Komponenten aus `frontend/src/lib/components/ui/` mit allen Varianten und States sichtbar sind — als visuelle Verifikation ohne App-Navigation.

> **Schicht-Hinweis:** Ausschließlich Frontend-Layer. Kein Go-API-Code, kein Python-Backend betroffen.

## Source

- **File:** `frontend/src/routes/_design/+page.svelte`
- **Identifier:** `+page.svelte` (SvelteKit Route)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `$lib/components/ui/badge` | Svelte-Komponente (vorhanden) | Badge in 6 Varianten |
| `$lib/components/ui/checkbox` | Svelte-Komponente (vorhanden) | Checkbox unchecked/checked/disabled |
| `$lib/components/ui/input` | Svelte-Komponente (vorhanden) | Input default/disabled/error |
| `$lib/components/ui/label` | Svelte-Komponente (vorhanden) | Label im Label+Input-Paar |
| `$lib/components/ui/select` | Svelte-Komponente (vorhanden) | Select default/disabled |
| `$lib/components/ui/segmented` | Svelte-Komponente (vorhanden, default-export) | Segmented-Control mit options/selected/onselect |
| `$lib/components/ui/wicon` | Svelte-Komponente (vorhanden) | WIcon alle 8 kinds |
| `$lib/components/ui/wordmark/Wordmark.svelte` | Svelte-Komponente (vorhanden, kein index.ts) | Wordmark in sm/md/lg |
| `$lib/components/ui/card/index.js` | shadcn-Komponente (vorhanden, als `* as Card`) | Card.Root/Header/Title/Description/Content/Footer |
| `$lib/components/ui/table/index.js` | shadcn-Komponente (vorhanden, als `* as Table`) | Table.Root/Header/Body/Row/Head/Cell |
| `$lib/components/ui/dialog/index.js` | shadcn-Komponente (vorhanden, als `* as Dialog`) | Dialog.Root/Content/Header/Title/Description/Footer |
| `$lib/components/edit/AccordionSection.svelte` | Svelte-Komponente (vorhanden) | AccordionSection open/closed |
| `@lucide/svelte/icons/loader-2` | Lucide-Icon (vorhanden) | Loader2 für Btn-Loading-State |
| `frontend/src/app.css` | CSS (vorhanden) | Design-Tokens, `[data-slot="pill"][data-outlined]` |

## Implementation Details

### Script-Block (`<script lang="ts">`)

```typescript
import { Badge } from '$lib/components/ui/badge';
import { Checkbox } from '$lib/components/ui/checkbox';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { Select } from '$lib/components/ui/select';
import Segmented from '$lib/components/ui/segmented';
import WIcon from '$lib/components/ui/wicon';
import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
import * as Card from '$lib/components/ui/card/index.js';
import * as Table from '$lib/components/ui/table/index.js';
import * as Dialog from '$lib/components/ui/dialog/index.js';
import AccordionSection from '$lib/components/edit/AccordionSection.svelte';
import Loader2 from '@lucide/svelte/icons/loader-2';
// bestehende Imports (Btn, Pill, Dot, etc.) bleiben unverändert

let dialogOpen = $state(false);
let accordionAOpen = $state(true);
let accordionBOpen = $state(false);
let segmentedSelected = $state('etappe');
let checkboxChecked = $state(true);
```

### Section-Reihenfolge und `data-testid`

Jede `<section>` erhält ein `data-testid`-Attribut:

| data-testid | Inhalt |
|-------------|--------|
| `atoms-section` | Bestehend + erweitert (siehe unten) |
| `wordmark-section` | NEU |
| `form-controls-section` | NEU |
| `card-section` | NEU |
| `table-section` | NEU |
| `dialog-section` | NEU |
| `accordion-section` | NEU |
| `nav-hint-section` | NEU |
| `topo-section` | Bestehend, unverändert |
| `sparkline-section` | Bestehend, unverändert |
| `profile-signatures-section` | Bestehend, unverändert |

### atoms-section — Erweiterungen

Zum bestehenden Block hinzufügen (nicht ersetzen):

**Btn Loading-State:**
```svelte
<Btn variant="default" disabled>
  <Loader2 class="animate-spin" size={16} />
  Lädt…
</Btn>
```

**Pill Outlined (3 Tones):**
```svelte
<Pill tone="warning" data-outlined>Outlined Warning</Pill>
<Pill tone="danger" data-outlined>Outlined Danger</Pill>
<Pill tone="info" data-outlined>Outlined Info</Pill>
```
Das `data-outlined`-Attribut ist kein Svelte-Prop — es wird als HTML-Attribut übergeben und von der CSS-Regel `[data-slot="pill"][data-outlined]` in `app.css` gestylt. Gültige Tones für Outlined: `warning`, `danger`, `info`, `default`.

**Dot Semantic-Tones + Sizes:**
```svelte
<Dot tone="success" size="xs" /> <Dot tone="success" size="sm" /> <Dot tone="success" size="md" />
<Dot tone="warning" size="xs" /> <Dot tone="warning" size="sm" /> <Dot tone="warning" size="md" />
<Dot tone="danger"  size="xs" /> <Dot tone="danger"  size="sm" /> <Dot tone="danger"  size="md" />
<Dot tone="info"    size="xs" /> <Dot tone="info"    size="sm" /> <Dot tone="info"    size="md" />
```

**Badge alle 6 Varianten:**
```svelte
<Badge variant="default">Default</Badge>
<Badge variant="secondary">Secondary</Badge>
<Badge variant="destructive">Destructive</Badge>
<Badge variant="outline">Outline</Badge>
<Badge variant="ghost">Ghost</Badge>
<Badge variant="link">Link</Badge>
```

**WIcon alle 8 kinds:**
```svelte
<WIcon kind="sun" />
<WIcon kind="cloud" />
<WIcon kind="rain" />
<WIcon kind="thunder" />
<WIcon kind="snow" />
<WIcon kind="wind" />
<WIcon kind="moon" />
<WIcon kind="headlamp" />
```

### wordmark-section (NEU)

```svelte
<section data-testid="wordmark-section">
  <h2>Wordmark</h2>
  <div style="display: flex; gap: var(--g-s-6); align-items: flex-end;">
    <Wordmark size="sm" />
    <Wordmark size="md" />
    <Wordmark size="lg" />
  </div>
</section>
```

### form-controls-section (NEU)

```svelte
<section data-testid="form-controls-section">
  <h2>Form Controls</h2>

  <!-- Checkbox -->
  <Checkbox bind:checked={checkboxChecked} /> Checked
  <Checkbox /> Unchecked
  <Checkbox disabled /> Disabled

  <!-- Segmented -->
  <Segmented
    options={[{ value: 'etappe', label: 'Etappe' }, { value: 'tag', label: 'Tag' }]}
    selected={segmentedSelected}
    onselect={(v) => segmentedSelected = v}
  />

  <!-- Label + Input -->
  <Label for="demo-input">Name</Label>
  <Input id="demo-input" placeholder="Eingabe…" />
  <Input placeholder="Disabled" disabled />
  <Input placeholder="Fehler" aria-invalid="true" />

  <!-- Select -->
  <Select>
    <option value="a">Option A</option>
    <option value="b">Option B</option>
  </Select>
  <Select disabled>
    <option value="a">Disabled</option>
  </Select>
</section>
```

### card-section (NEU)

```svelte
<section data-testid="card-section">
  <h2>Card</h2>
  <Card.Root>
    <Card.Header>
      <Card.Title>Kartentitel</Card.Title>
      <Card.Description>Beschreibungstext der Karte.</Card.Description>
    </Card.Header>
    <Card.Content>Inhalt der Karte.</Card.Content>
    <Card.Footer>
      <Btn variant="ghost" size="sm">Aktion</Btn>
    </Card.Footer>
  </Card.Root>
</section>
```

### table-section (NEU)

```svelte
<section data-testid="table-section">
  <h2>Table</h2>
  <Table.Root>
    <Table.Header>
      <Table.Row>
        <Table.Head>Etappe</Table.Head>
        <Table.Head>Distanz</Table.Head>
        <Table.Head>Status</Table.Head>
      </Table.Row>
    </Table.Header>
    <Table.Body>
      <Table.Row>
        <Table.Cell>Calenzana → Ortu</Table.Cell>
        <Table.Cell>16 km</Table.Cell>
        <Table.Cell>Aktiv</Table.Cell>
      </Table.Row>
      <Table.Row>
        <Table.Cell>Ortu → Carrozzu</Table.Cell>
        <Table.Cell>12 km</Table.Cell>
        <Table.Cell>Geplant</Table.Cell>
      </Table.Row>
    </Table.Body>
  </Table.Root>
</section>
```

### dialog-section (NEU)

```svelte
<section data-testid="dialog-section">
  <h2>Dialog</h2>
  <Btn variant="outline" onclick={() => dialogOpen = true}>Dialog öffnen</Btn>
  <Dialog.Root bind:open={dialogOpen}>
    <Dialog.Content>
      <Dialog.Header>
        <Dialog.Title>Beispiel-Dialog</Dialog.Title>
        <Dialog.Description>Beschreibungstext des Dialogs.</Dialog.Description>
      </Dialog.Header>
      <Dialog.Footer>
        <Btn variant="ghost" onclick={() => dialogOpen = false}>Schliessen</Btn>
      </Dialog.Footer>
    </Dialog.Content>
  </Dialog.Root>
</section>
```

### accordion-section (NEU)

```svelte
<section data-testid="accordion-section">
  <h2>Accordion</h2>
  <AccordionSection id="demo-a" title="Sektion A (offen)" open={accordionAOpen} onToggle={() => accordionAOpen = !accordionAOpen}>
    Inhalt von Sektion A ist sichtbar.
  </AccordionSection>
  <AccordionSection id="demo-b" title="Sektion B (geschlossen)" open={accordionBOpen} onToggle={() => accordionBOpen = !accordionBOpen}>
    Inhalt von Sektion B ist verborgen.
  </AccordionSection>
</section>
```
Hinweis: `AccordionSection` hat kein `$bindable()`-Open-Prop — es verwendet `open: boolean` + `onToggle: () => void` als Interface.

### nav-hint-section (NEU)

```svelte
<section data-testid="nav-hint-section">
  <h2>Navigation</h2>
  <p>Sidebar, TopAppBar und BottomNav sind in dieser Seite nicht live darstellbar,
     da sie $app/state-Abhängigkeiten haben. Visuell prüfbar über normale App-Navigation.</p>
</section>
```

### LoC-Budget

Die Seite wächst von ~166 auf ~470 Zeilen (+304 LoC). `loc_limit_override` vor Implementierung auf `400` setzen:

```bash
python3 .claude/hooks/workflow.py set-field loc_limit_override 400
```

### Constraints

- AP-001: Keine rohen `<button>` oder `<input>` außerhalb der Komponentendemos
- AP-007: Kein Hex-Inline-CSS
- AP-008: Spacing-Overrides nur via `--g-s-*`-Tokens (Tailwind-Klassen sind ok)
- AP-009: Keine Emojis — ausschließlich WIcon/Lucide-Icons
- Bestehende sections `topo-section`, `sparkline-section`, `profile-signatures-section` nicht anfassen

## Expected Behavior

- **Input:** Keine — die Seite ist rein statisch/interaktiv, keine API-Calls
- **Output:** Vollständige visuelle Komponentengalerie unter `/_design` mit allen 11 Sections und ihren `data-testid`-Attributen
- **Side effects:** Dialog öffnet/schließt via `dialogOpen`; AccordionSection B öffnet sich beim Klick; Segmented-Control und Checkbox reagieren auf User-Interaktion

## Acceptance Criteria

**AC-1:** Given die `/_design`-Seite, when ich sie öffne, then sehe ich alle 11 Sections im DOM mit korrekten `data-testid`-Attributen: `atoms-section`, `wordmark-section`, `form-controls-section`, `card-section`, `table-section`, `dialog-section`, `accordion-section`, `nav-hint-section`, `topo-section`, `sparkline-section`, `profile-signatures-section`.

**AC-2:** Given die `atoms-section`, when ich sie betrachte, then sehe ich Badge in allen 6 Varianten (default/secondary/destructive/outline/ghost/link) und WIcon in allen 8 kinds (sun/cloud/rain/thunder/snow/wind/moon/headlamp).
  - Test: (populated after /tdd-red)

**AC-3:** Given die `atoms-section`, when ich den Btn-Loading-Block betrachte, then sehe ich einen `disabled`-Btn mit einem rotierenden Loader2-Icon aus `@lucide/svelte`.
  - Test: (populated after /tdd-red)

**AC-4:** Given die `atoms-section`, when ich die Pill-Outlined-Section betrachte, then sehe ich mindestens 3 Pills mit gesetztem `data-outlined`-HTML-Attribut in unterschiedlichen Tones.
  - Test: (populated after /tdd-red)

**AC-5:** Given die `atoms-section`, when ich den Dot-Block betrachte, then sehe ich alle 4 Semantic-Tones (success/warning/danger/info) jeweils in allen 3 Sizes (xs/sm/md) — insgesamt 12 Dot-Instanzen.
  - Test: (populated after /tdd-red)

**AC-6:** Given die `wordmark-section`, when ich sie betrachte, then sehe ich Wordmark in sm, md und lg Größe nebeneinander im selben Container.
  - Test: (populated after /tdd-red)

**AC-7:** Given die `form-controls-section`, when ich sie betrachte, then sehe ich Checkbox (checked/unchecked/disabled), Segmented-Control mit 2 Options, ein Label+Input-Paar und Select (default/disabled).
  - Test: (populated after /tdd-red)

**AC-8:** Given die `card-section`, when ich sie betrachte, then sehe ich Card.Root mit Card.Header (Title + Description), Card.Content und Card.Footer.
  - Test: (populated after /tdd-red)

**AC-9:** Given die `table-section`, when ich sie betrachte, then sehe ich eine Tabelle mit einer Header-Zeile (3 Spalten) und mindestens 2 Daten-Zeilen.
  - Test: (populated after /tdd-red)

**AC-10:** Given die `dialog-section`, when ich den Trigger-Btn "Dialog öffnen" klicke, then öffnet sich der Dialog mit Titel und Beschreibung. When ich "Schliessen" klicke, then ist der Dialog nicht mehr sichtbar.
  - Test: (populated after /tdd-red)

**AC-11:** Given die `accordion-section`, when ich sie betrachte, then ist AccordionSection A sichtbar geöffnet (Inhalt im DOM) und AccordionSection B geschlossen (Inhalt verborgen). When ich den Header von B klicke, öffnet sich B und ihr Inhalt wird sichtbar.
  - Test: (populated after /tdd-red)

## Known Limitations

- Sidebar, TopAppBar und BottomNav sind wegen `$app/state`-Abhängigkeiten nicht live darstellbar — die `nav-hint-section` enthält stattdessen einen Texthinweis.
- Die Seite ist nur unter `/_design` erreichbar und nicht über die reguläre App-Navigation verlinkt.

## Changelog

- 2026-05-22: Initial spec erstellt (Issue #313 — `/_design` Showcase vervollständigen).
