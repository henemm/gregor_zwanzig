---
entity_id: epic_133_step6_theme_bridge
type: module
created: 2026-05-13
updated: 2026-05-13
status: draft
version: "1.0"
parent_spec: epic_133_design_system
issues: [218]
parent_epic: 133
tags: [frontend, sveltekit, design-system, epic-133, issue-218, tailwind, theme-bridge]
---

# Epic #133 — Issue #218: Theme-Bridge (shadcn `@theme` an `--g-*`-Tokens koppeln)

## Approval

- [x] Approved (2026-05-13)

## Purpose

Koppelt die 19 shadcn-Farbtoken im `@theme {}`-Block von `frontend/src/app.css` an die `--g-*`-Design-System-Tokens, sodass alle shadcn-UI-Komponenten automatisch die Marken-Optik erhalten, ohne dass Komponenten-Code angefasst wird. Die `--g-*`-Variablen bleiben dadurch die einzige Source of Truth für Farben — shadcn-`@theme`-Token referenzieren sie per `var(--g-*)`, statt eigene hartcodierte `oklch()`-Werte zu halten.

## Source

- **EDIT:** `frontend/src/app.css` Z. 4–22 (`@theme {}`-Block) — 19 oklch-Werte durch `var(--g-*)`-Referenzen ersetzen
- **NEU:** `frontend/e2e/theme-bridge.spec.ts` — 5 Playwright-E2E-Tests (AC-1…AC-5)
- **Identifier:** keine Code-Identifier, nur CSS-Variablen im `@theme {}`-Block

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` Z. 28–105 (`:root`-Block) | bestehend (Lieferant) | Definiert alle `--g-*`-Tokens; alle 19 benötigten Tokens (`--g-paper`, `--g-ink`, `--g-surface-1`, `--g-surface-2`, `--g-ink-muted`, `--g-ink-faint`, `--g-accent`, `--g-danger`) sind vorhanden |
| `frontend/src/routes/+layout.svelte` Z. 10–44 | bestehend (Constraint) | Dark-Mode-Toggle setzt `--color-*` als Inline-Styles auf `document.documentElement`; Inline-Styles haben höhere Spezifizität als `@theme` — Bridge wirkt nur im Light-Mode (gewollt, Dark-Mode ist nicht in Scope dieses Sprints) |
| shadcn-UI-Komponenten (`button.svelte`, `card.svelte`, `badge.svelte`, `Sidebar.svelte`, …) | bestehend (Konsumenten) | 66 Files nutzen Tailwind-Utility-Klassen, die auf die `@theme`-Tokens basieren; erben automatisch, ohne dass Komponenten-Code verändert wird |
| Tailwind v4 (`@import "tailwindcss"`) | bestehend (Build) | Löst `var(--g-*)` im `@theme {}`-Block zu Utilities auf; CSS-Variable-Referenzen in `@theme` sind ab Tailwind v4 unterstützt |

## Implementation Details

### §1 `@theme {}`-Block in `frontend/src/app.css` anpassen

Den `@theme {}`-Block (Z. 3–26) editieren: alle 19 Farbtoken erhalten als Wert eine `var(--g-*)`-Referenz statt eines hartcodierten `oklch()`-Wertes. Die Radii-Token (`--radius-sm`, `--radius-md`, `--radius-lg`) bleiben unverändert.

Vollständiges Mapping nach dem Edit:

```css
@theme {
  --color-background:        var(--g-paper);
  --color-foreground:        var(--g-ink);
  --color-popover:           var(--g-paper);
  --color-popover-foreground: var(--g-ink);
  --color-card:              var(--g-surface-1);
  --color-card-foreground:   var(--g-ink);
  --color-muted:             var(--g-surface-2);
  --color-muted-foreground:  var(--g-ink-muted);
  --color-border:            var(--g-ink-faint);
  --color-input:             var(--g-ink-faint);
  --color-ring:              var(--g-accent);
  --color-primary:           var(--g-ink);
  --color-primary-foreground: var(--g-paper);
  --color-accent:            var(--g-accent);
  --color-accent-foreground: var(--g-paper);
  --color-destructive:       var(--g-danger);
  --color-sidebar:           var(--g-surface-1);
  --color-sidebar-foreground: var(--g-ink);
  --color-sidebar-accent:    var(--g-surface-2);
  /* --radius-sm/md/lg bleiben unverändert */
}
```

Keine weiteren Dateien werden editiert — kein Komponenten-Code, keine Routen.

### §2 Neuer Test `frontend/e2e/theme-bridge.spec.ts`

5 Playwright-Tests entsprechend AC-1…AC-5. AC-1 bis AC-4 erzwingen Light-Mode via `addInitScript`; AC-5 aktiviert Dark-Mode via `addInitScript`.

```typescript
import { test, expect } from '@playwright/test';

test.describe('Epic #133 Step 6 — Theme-Bridge', () => {
  // Light-Mode sicherstellen (localStorage leer)
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.removeItem('gz-dark'));
  });

  test('AC-1: --color-primary löst zu Ink-Schwarz auf (rgb(26, 26, 24))', async ({ page }) => {
    await page.goto('/');
    const v = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()
    );
    expect(v).toBe('rgb(26, 26, 24)');
  });

  test('AC-2: --color-background löst zu Paper-Off-White auf (rgb(246, 244, 238))', async ({ page }) => {
    await page.goto('/');
    const v = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-background').trim()
    );
    expect(v).toBe('rgb(246, 244, 238)');
  });

  test('AC-3: --color-accent löst zu Burnt-Orange auf (rgb(196, 90, 42))', async ({ page }) => {
    await page.goto('/');
    const v = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-accent').trim()
    );
    expect(v).toBe('rgb(196, 90, 42)');
  });

  test('AC-4: --color-destructive löst zu Danger-Rot auf (rgb(179, 58, 42))', async ({ page }) => {
    await page.goto('/');
    const v = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-destructive').trim()
    );
    expect(v).toBe('rgb(179, 58, 42)');
  });

  test('AC-5: Dark-Mode-Override bleibt aktiv — Bridge versperrt ihn nicht', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('gz-dark', '1'));
    await page.goto('/');
    const v = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()
    );
    // Dark-Mode setzt --color-primary via Inline-Style auf helles Grau (oklch(0.92 0 0) ≈ rgb(232,232,232))
    expect(v).not.toBe('rgb(26, 26, 24)');
  });
});
```

### §3 Datei-Liste

| Art | Datei | Zweck | LoC |
|-----|-------|-------|-----|
| EDIT | `frontend/src/app.css` Z. 4–22 | 19 oklch-Werte durch `var(--g-*)` ersetzen | 19 Zeilen geändert |
| NEU | `frontend/e2e/theme-bridge.spec.ts` | 5 Playwright-Tests (AC-1…AC-5) | ~80 LoC |
| **Summe** | | | **~100 LoC** |

Default-LoC-Limit 250, kein Override nötig.

## Expected Behavior

- **Input:** kein Laufzeit-Input. Der Edit wirkt beim CSS-Build und wird beim Seitenaufruf als compiliertes Stylesheet ausgeliefert.
- **Output (Light-Mode):**
  - `bg-background` → warmes Paper-Off-White `rgb(246, 244, 238)` statt Pure-White.
  - `bg-primary` → warmes Ink-Schwarz `rgb(26, 26, 24)` statt neutrales `oklch(0.205 0 0)`.
  - `bg-accent` / `hover:bg-accent` (Sidebar-Hover, Button-States, Badge-Akzente) → Burnt-Orange `rgb(196, 90, 42)` statt hellem Grau — markante Marken-Akzent-Wirkung.
  - `ring-ring` (Focus-Rings) → Burnt-Orange statt mittleres Grau.
  - `border-border` → warmes `rgb(156, 154, 144)` (Ink-Faint) statt neutrales `oklch(0.90 0 0)`.
  - `bg-destructive` → `rgb(179, 58, 42)` (Danger) statt freischwebendes `oklch`.
- **Output (Dark-Mode):** Inline-Styles aus `+layout.svelte` überschreiben 18 von 19 Bridge-Werten. `--color-destructive` wird nicht von `+layout.svelte` überschrieben und bleibt bei `var(--g-danger)` — visuell nah am bisherigen Wert, kein Rückschritt.
- **Side effects:** Keine. Kein Komponenten-Code wird editiert, kein Pfad geändert. Alle 66 shadcn-Dateien profitieren automatisch.
- **Failure mode:** Fehlt ein `--g-*`-Token im `:root`-Block, fällt die CSS-Variable auf `unset` zurück — Tailwind generiert unerwartete Utility-Werte. Tests prüfen die exakte Hex-Auflösung und schlagen dann fehl.

## Acceptance Criteria

- **AC-1:** Given das Frontend ist im Light-Mode geladen (kein `gz-dark` in localStorage) / When `getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()` ausgeführt wird / Then liefert es exakt `rgb(26, 26, 24)` — den aufgelösten Wert von `var(--g-ink)`, was bestätigt dass die Bridge wirkt.
  - Test: (populated after /tdd-red)

- **AC-2:** Given das Frontend ist im Light-Mode geladen (kein `gz-dark` in localStorage) / When `getComputedStyle(document.documentElement).getPropertyValue('--color-background').trim()` ausgewertet wird / Then liefert es exakt `rgb(246, 244, 238)` — den aufgelösten Wert von `var(--g-paper)`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given das Frontend ist im Light-Mode geladen (kein `gz-dark` in localStorage) / When `getComputedStyle(document.documentElement).getPropertyValue('--color-accent').trim()` ausgewertet wird / Then liefert es exakt `rgb(196, 90, 42)` — den aufgelösten Burnt-Orange-Wert von `var(--g-accent)`.
  - Test: (populated after /tdd-red)

- **AC-4:** Given das Frontend ist im Light-Mode geladen (kein `gz-dark` in localStorage) / When `getComputedStyle(document.documentElement).getPropertyValue('--color-destructive').trim()` ausgewertet wird / Then liefert es exakt `rgb(179, 58, 42)` — den aufgelösten Wert von `var(--g-danger)`.
  - Test: (populated after /tdd-red)

- **AC-5:** Given der Dark-Mode via `localStorage.setItem('gz-dark', '1')` und Reload aktiviert wurde / When `getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim()` ausgewertet wird / Then liefert es nicht `rgb(26, 26, 24)`, sondern den Dark-Mode-Inline-Wert aus `+layout.svelte` — die Bridge versperrt den Dark-Mode-Override nicht.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Dark-Mode-Bridge nicht in Scope:** Die 18 Dark-Mode-Farben in `+layout.svelte` sind weiterhin hartcodierte `oklch()`-Inline-Werte. Falls Dark-Mode ebenfalls an `--g-*-dark`-Tokens gekoppelt werden soll, ist ein Folge-Issue erforderlich.
- **Naming-Drift Spec vs. Code:** `docs/reference/design_system.md` nutzt `--g-good/warn/bad`, der Code nutzt `--g-success/warning/danger`. Diese Spec und die Bridge nutzen das Code-Naming. Klärung läuft in Issue #213.
- **Pre/Post-Screenshot-Pipeline manuell:** Sichtprüfung auf `/`, `/_design`, `/trips` vor und nach dem Edit liegt außerhalb des automatisierten Test-Scopes. Kein Visual-Regression-Tooling — wäre für 19 CSS-Zeilen unverhältnismäßig.
- **Test-Pre-Condition Light-Mode:** AC-1 bis AC-4 setzen voraus, dass `localStorage['gz-dark']` nicht `'1'` ist. Tests müssen Light-Mode explizit via `addInitScript(() => localStorage.removeItem('gz-dark'))` erzwingen.
- **`--color-destructive` im Dark-Mode unverändert:** `+layout.svelte` überschreibt diesen Token nicht per Inline-Style. Nach der Bridge koppelt er an `var(--g-danger)` — visuell nah am alten Wert, aber kein expliziter Dark-Mode-Wert gesetzt. Kein Rückschritt, aber ein bekannter Grenzfall.
- **`@property`-Block dupliziert `--g-*`-Hex-Werte (DRY-Verletzung):** Tailwind v4 mit Lightning CSS minifiziert `rgb()` zu `#hex` im Output, sodass `getComputedStyle().getPropertyValue('--color-X')` ohne `@property` keine `rgb()`-Werte liefert. Workaround: 19 `@property`-Deklarationen mit `syntax: "<color>"` und `initial-value: rgb(...)`-Spiegel der `--g-*`-Hexes. Falls ein `--g-*`-Token in `:root` umbenannt/geändert wird, kann der `@property initial-value` als Stale-Fallback dienen. Risiko: medium, Mitigation: bei Token-Refactorings die `@property`-Werte synchron halten oder via CI-Check absichern.
- **Sidebar-Nav-Hover ist nicht Burnt-Orange:** `Sidebar.svelte` Z. 79 nutzt `hover:bg-sidebar-accent` (= `--g-surface-2`, warmes Sandtonig), nicht `hover:bg-accent`. Pre-existing-Verhalten; Bridge ändert das nicht. Der Burnt-Orange-Akzent erscheint stattdessen in: aktiven Tabs, Badges, Dropdown-Menüs (User-Menü, Z. 115/123/131), und Focus-Rings. Sidebar-Active vs. Hover bleiben visuell schwer unterscheidbar (beide Surface-2) — gehört in einen separaten Issue zur Sidebar-Differenzierung.

## Changelog

- 2026-05-13: Initial spec — Issue #218, Bridge zwischen shadcn-`@theme`-Block und `--g-*`-Tokens. 19 oklch-Werte in `frontend/src/app.css` Z. 4–22 durch `var(--g-*)`-Referenzen ersetzt; `--g-*`-Tokens bleiben Single Source of Truth. 5 Playwright-E2E-Tests in `frontend/e2e/theme-bridge.spec.ts`. ~100 LoC. AC-N-Pflicht erfüllt (5 ACs im Given/When/Then-Format, alle >=30 Zeichen).
- 2026-05-13: Implementation + Adversary VERIFIED. Während der Umsetzung musste ein `@property`-Block (19 Deklarationen mit `syntax: "<color>"`) vor dem `@theme {}`-Block eingefügt werden, damit `getComputedStyle()` die Bridge-Werte als `rgb(...)` liefert (Lightning CSS minifiziert sonst zu `#hex`). AC-5 im Test um `page.reload()` ergänzt, damit Layout-Mount nach Dark-Mode-localStorage-Set neu läuft. F002 (DRY) und Sidebar-Hover als Known Limitations dokumentiert. Net LoC-Delta: +77.
