## Problem

The Wetter section in trip edit (Temperatur / Wind / Niederschlag / Atmosphäre / Winter-Schnee) renders:

- All metric checkboxes as **native blue** OS checkboxes.
- The "Roh / Indikator" toggle as **two small buttons** with a tiny ink-toned border — they don't read as a segmented control. The active state uses `bg-primary text-primary-foreground` (Tailwind) which fights with the brand tokens.
- Wetter-Profil `<select>` is a native dropdown with the OS focus ring.
- Category headings (Temperatur / Wind / etc) are too quiet — design has them as bold ink with a hairline underline.

## Files

- `src/lib/components/edit/EditWeatherSection.svelte`

## Dependencies

This issue depends on **#01 (Checkbox + Select components)**. Do that first.

## Required changes

### 1. Replace native checkboxes with `<Checkbox>`

```diff
- <label class="flex cursor-pointer items-center gap-2 flex-1 min-w-0">
-   <input
-     type="checkbox"
-     data-testid="metric-checkbox-{metric.id}"
-     class="rounded border-input"
-     checked={enabledMap[metric.id] ?? false}
-     onchange={(e) => toggleMetric(metric.id, (e.target as HTMLInputElement).checked)}
-   />
-   <span>{metric.label}</span>
- </label>
+ <Checkbox
+   data-testid="metric-checkbox-{metric.id}"
+   checked={enabledMap[metric.id] ?? false}
+   onchange={(e) => toggleMetric(metric.id, e.currentTarget.checked)}
+ >
+   {metric.label}
+ </Checkbox>
```

### 2. Replace template `<select>` with `<Select>`

```diff
- <select id="weather-template" data-testid="weather-template-select"
-   class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
-   bind:value={selectedTemplate}>
+ <Select id="weather-template" data-testid="weather-template-select"
+   bind:value={selectedTemplate}>
```

### 3. Roh / Indikator — proper segmented control

Extract into a small helper inline:

```svelte
<span class="g-segmented" role="radiogroup" aria-label="Format">
  <button type="button"
    class="g-segmented__seg"
    aria-checked={!(friendlyMap[metric.id] ?? true)}
    role="radio"
    onclick={() => setFormat(metric.id, false)}
  >Roh</button>
  <button type="button"
    class="g-segmented__seg"
    aria-checked={friendlyMap[metric.id] ?? true}
    role="radio"
    onclick={() => setFormat(metric.id, true)}
  >Indikator</button>
</span>

<style>
  .g-segmented {
    display: inline-flex;
    border: 1px solid var(--g-ink-faint);
    border-radius: var(--g-radius-sm);
    padding: 2px;
    background: var(--g-paper);
    gap: 2px;
  }
  .g-segmented__seg {
    padding: 3px 8px;
    font-size: 11px;
    font-family: var(--g-font-data);
    letter-spacing: 0.04em;
    color: var(--g-ink-muted);
    background: transparent;
    border: none;
    border-radius: calc(var(--g-radius-sm) - 2px);
    cursor: pointer;
  }
  .g-segmented__seg[aria-checked="true"] {
    background: var(--g-ink);
    color: var(--g-paper);
  }
  .g-segmented__seg:not([aria-checked="true"]):hover {
    background: var(--g-surface-2);
    color: var(--g-ink);
  }
</style>
```

Better: extract `Segmented.svelte` and `Segmented.Item` into `src/lib/components/ui/segmented/` so this control can be reused (it's also needed in the Alert mode toggle ModeCard if we ever consolidate).

### 4. Category headers — design polish

```diff
- <h4 class="text-sm font-semibold">{CATEGORY_LABELS[cat] ?? cat}</h4>
+ <h4 class="text-sm font-semibold text-[var(--g-ink)] pb-1 border-b border-[var(--g-ink-faint)]/30">
+   {CATEGORY_LABELS[cat] ?? cat}
+ </h4>
```

### 5. Row hover state

The current `hover:bg-muted/50` is fine but make sure the row contains a `min-h` so it doesn't jitter on hover when the segmented control wraps to a new line on narrow widths:

```diff
- <div class="flex items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-muted/50">
+ <div class="flex items-center gap-2 rounded px-2 py-1 text-sm min-h-[28px] hover:bg-[var(--g-surface-2)]/60">
```

## Acceptance criteria

- [ ] No `<input type="checkbox">` in this file.
- [ ] No raw `<select>` in this file.
- [ ] "Roh / Indikator" renders as a single segmented control widget (one outer border, two cells inside), not two adjacent buttons.
- [ ] Active segment is ink-on-paper, inactive segments are muted.
- [ ] Category headings have a faint hairline underline.
- [ ] `metric-checkbox-{id}` and `weather-template-select` testids preserved.

## 📎 Attachments

- `uploads/CleanShot 2026-05-20 at 15.08.16@2x.png` — full Wetter section with blue checkboxes + Roh/Indikator buttons