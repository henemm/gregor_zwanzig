## Problem

Across the app, `<input type="checkbox">` and `<select>` are used with raw Tailwind class hints (`class="rounded border-input"`) — but browsers ignore those styles on form-control internals. Result: every checkbox in the app renders as the **OS default** (blue iOS/macOS checkmark) and every select renders with the native dropdown arrow + system focus ring.

This is the second-biggest visual issue after the token bug. See screenshots: in *Wetter*, *Reports*, *Alarmregeln*, *Orts-Vergleich*, and *Reports → Trend* — every checkbox is system-blue.

## Files affected (search to confirm full scope)

```bash
rg 'type="checkbox"' src
rg '<select' src
```

Known callsites:
- `src/lib/components/edit/EditWeatherSection.svelte` — metric checkboxes (lines ~150–165)
- `src/lib/components/edit/EditReportConfigSection.svelte` — channel checkboxes, trend checkbox
- `src/lib/components/alert-rules-editor/AlertRuleRow.svelte` — `enabled` toggle, metric `<select>`, severity `<select>`
- `src/routes/trips/+page.svelte` — report-config dialog (channels, options, hour selects)
- `src/lib/components/compare/LocationsRail.svelte` — location-select checkboxes
- `src/lib/components/WeatherConfigDialog.svelte`

## Required changes

### 1. Create a `<Checkbox>` component

`src/lib/components/ui/checkbox/Checkbox.svelte` — accessible, brand-styled, supports indeterminate.

API:
```svelte
<Checkbox bind:checked={enabled} disabled={false} indeterminate={false}>
  Label text
</Checkbox>
```

Implementation outline (no UI library; raw Svelte + CSS):
```svelte
<script lang="ts">
  let { checked = $bindable(false), disabled = false, indeterminate = false, children, onchange } = $props();
</script>

<label class="g-check" class:disabled>
  <input
    type="checkbox"
    bind:checked
    {disabled}
    onchange={onchange}
    bind:this={inputEl}
  />
  <span class="g-check__box" aria-hidden="true">
    {#if indeterminate}
      <svg viewBox="0 0 16 16"><path d="M4 8h8" stroke="currentColor" stroke-width="2"/></svg>
    {:else if checked}
      <svg viewBox="0 0 16 16"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
    {/if}
  </span>
  {#if children}<span class="g-check__label">{@render children()}</span>{/if}
</label>

<style>
  .g-check {
    display: inline-flex;
    align-items: center;
    gap: var(--g-s-2);
    cursor: pointer;
    font-size: var(--g-text-sm);
    color: var(--g-ink);
    user-select: none;
  }
  .g-check input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }
  .g-check__box {
    width: 16px; height: 16px;
    border: 1px solid var(--g-ink-faint);
    border-radius: var(--g-radius-xs);
    background: var(--g-paper);
    display: inline-flex; align-items: center; justify-content: center;
    color: var(--g-paper);
    transition: background-color 120ms ease, border-color 120ms ease;
  }
  .g-check input:checked ~ .g-check__box,
  .g-check input:indeterminate ~ .g-check__box {
    background: var(--g-ink);
    border-color: var(--g-ink);
  }
  .g-check input:focus-visible ~ .g-check__box {
    outline: 2px solid var(--g-accent);
    outline-offset: 2px;
  }
  .g-check.disabled { opacity: 0.5; cursor: not-allowed; }
</style>
```

Export from `src/lib/components/ui/checkbox/index.ts`.

### 2. Create a `<Select>` component

`src/lib/components/ui/select/Select.svelte` — wraps native `<select>` with a custom chevron and ink-toned border. Keep the native popup (don't rebuild it — accessibility + mobile picker are free).

```svelte
<script lang="ts">
  let { value = $bindable(), disabled = false, children, ...rest } = $props();
</script>

<span class="g-select">
  <select bind:value {disabled} {...rest}>
    {@render children()}
  </select>
  <svg class="g-select__chevron" viewBox="0 0 16 16" aria-hidden="true">
    <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>
</span>

<style>
  .g-select { position: relative; display: inline-block; width: 100%; }
  .g-select select {
    appearance: none;
    width: 100%;
    padding: 6px 32px 6px 10px;
    font-family: var(--g-font-ui);
    font-size: var(--g-text-sm);
    color: var(--g-ink);
    background: var(--g-paper);
    border: 1px solid var(--g-ink-faint);
    border-radius: var(--g-radius-sm);
    cursor: pointer;
  }
  .g-select select:focus-visible {
    outline: 2px solid var(--g-accent);
    outline-offset: 1px;
  }
  .g-select__chevron {
    position: absolute; right: 10px; top: 50%;
    width: 14px; height: 14px;
    transform: translateY(-50%);
    color: var(--g-ink-muted);
    pointer-events: none;
  }
</style>
```

### 3. Replace all native usages

Codemod or manual replacement. Example for `EditWeatherSection.svelte`:

```diff
- <input
-   type="checkbox"
-   data-testid="metric-checkbox-{metric.id}"
-   class="rounded border-input"
-   checked={enabledMap[metric.id] ?? false}
-   onchange={(e) => toggleMetric(metric.id, (e.target as HTMLInputElement).checked)}
- />
- <span>{metric.label}</span>
+ <Checkbox
+   data-testid="metric-checkbox-{metric.id}"
+   checked={enabledMap[metric.id] ?? false}
+   onchange={(e) => toggleMetric(metric.id, e.currentTarget.checked)}
+ >
+   {metric.label}
+ </Checkbox>
```

Keep all existing `data-testid` attributes — Playwright tests depend on them. Forward unknown props (`...rest`) on both components.

## Acceptance criteria

- [ ] `src/lib/components/ui/checkbox/Checkbox.svelte` exists with the API above.
- [ ] `src/lib/components/ui/select/Select.svelte` exists with the API above.
- [ ] `rg 'type="checkbox"' src` returns matches **only** inside `Checkbox.svelte`.
- [ ] `rg '<select\\b' src` returns matches **only** inside `Select.svelte`.
- [ ] **Visual:** All checkboxes are square, ink-on-paper, no system-blue. Tested in: Wetter, Reports, Alarmregeln, Compare-Rail, Trip-Edit Reports tab.
- [ ] All existing Playwright tests still pass (data-testid forwarded).
- [ ] Keyboard navigation: Space toggles checkbox, focus ring is the accent color.

## 📎 Attachments (drag into the issue)

- `uploads/CleanShot 2026-05-20 at 15.08.16@2x.png` — Wetter section with system-blue checkboxes everywhere
- `uploads/CleanShot 2026-05-20 at 15.09.03@2x.png` — Reports section with system-blue checkboxes
- `uploads/CleanShot 2026-05-20 at 15.06.43@2x.png` — Orts-Vergleich Location list, all checkboxes blue