<!-- gregor-zwanzig-handoff: stable_id=edit-report-config-controls -->
## Problem

The Reports section of the trip editor has multiple inconsistencies vs the design:

- **Time picker** is a native `type="time"` input — works, but the design pairs it with **quick chips** ("Morgens 07:00", "Abends 18:00") so users can re-set with one click.
- **"Trend über mehrere Tage zeigen"** uses native checkbox.
- **Channels (E-Mail / Signal / Telegram)** use native checkboxes; the "fehlt — im Account einrichten" link is underlined raw blue.
- **Advanced section** ("Erweitert ausblenden / anzeigen") is a plain bold-text button — design uses a small ghost chevron toggle.
- **Wind-Exposition Mindesthöhe** is a plain number input — design adds a faint `m` suffix (same pattern as elevation in issue #06).

## Files

- `src/lib/components/edit/EditReportConfigSection.svelte`

## Dependencies

- **#01** (Checkbox component)
- **#06** has the `m`-suffix input pattern (reuse it)

## Required changes

### 1. Time picker with quick chips

Currently looks like:

```svelte
<Input type="time" bind:value={morningTime} />
<Btn variant="outline" size="xs">Morgens 07:00</Btn>
<Btn variant="outline" size="xs">Abends 18:00</Btn>
```

Restyle: make the chips visually subordinate (ghost variant, tiny) and align them with the time input:

```svelte
<div class="flex items-center gap-2">
  <label class="g-num-with-unit">
    <Input type="time" bind:value={morningTime} class="g-num-input w-[88px]" />
  </label>
  <button type="button" class="g-quick-chip"
          onclick={() => morningTime = '07:00'}>Morgens 07:00</button>
  <button type="button" class="g-quick-chip"
          onclick={() => morningTime = '18:00'}>Abends 18:00</button>
</div>

<style>
  .g-quick-chip {
    padding: 4px 10px;
    border: 1px solid var(--g-ink-faint);
    border-radius: var(--g-radius-pill);
    font-family: var(--g-font-data);
    font-size: 11px;
    color: var(--g-ink-muted);
    background: transparent;
    cursor: pointer;
  }
  .g-quick-chip:hover { background: var(--g-surface-2); color: var(--g-ink); }
</style>
```

### 2. Channel rows — replace native checkboxes

```diff
- <input type="checkbox" ... />
- E-Mail (henning.emmrich@gmail.com)
+ <Checkbox bind:checked={...}>
+   E-Mail
+   <span class="text-[var(--g-ink-muted)] font-mono text-xs">
+     ({userEmail})
+   </span>
+ </Checkbox>
```

For disabled channels (Signal-Nummer fehlt / Telegram-Chat-ID fehlt), wrap the inline-help in an `<aside>`:

```svelte
<aside class="ml-7 text-xs text-[var(--g-ink-muted)]">
  Signal-Nummer fehlt —
  <a href="/account#signal" class="text-[var(--g-accent)] underline underline-offset-2 decoration-1">
    im Account einrichten
  </a>
</aside>
```

The link color was raw blue browser-default — should be `var(--g-accent)`.

### 3. "Trend über mehrere Tage zeigen" — branded checkbox

Same `<Checkbox>` swap.

### 4. Advanced toggle — ghost chevron

```diff
- <button class="font-bold">Erweitert anzeigen</button>
+ <Btn variant="ghost" size="sm" onclick={() => advancedOpen = !advancedOpen}>
+   <ChevronDownIcon class="size-3.5 transition-transform"
+     class:rotate-180={advancedOpen} />
+   Erweitert {advancedOpen ? 'ausblenden' : 'anzeigen'}
+ </Btn>
```

### 5. Wind-Exposition Mindesthöhe with unit suffix

Reuse the `g-num-with-unit` + `g-num-unit` classes from issue #06:

```svelte
<label class="g-num-with-unit block w-full sm:w-40">
  <Input type="number" bind:value={config.wind_exposition_min_elevation_m}
         class="g-num-input pr-7" placeholder="1800" />
  <span class="g-num-unit">m</span>
</label>
```

### 6. Section group containers

Each grouped block (Morgen-Report / Abend-Report / Kanäle) is in a card-alt container. Currently they look like raw bordered boxes. Replace with the existing `<Card.Root>`:

```svelte
<Card.Root class="p-4 bg-[var(--g-surface-1)]">
  <Checkbox bind:checked={config.enabled_morning}>
    <span class="font-semibold">Morgen-Report aktivieren</span>
  </Checkbox>
  <!-- ...inner controls indented... -->
</Card.Root>
```

## Acceptance criteria

- [ ] All checkboxes use `<Checkbox>` — no native blue.
- [ ] Time inputs use the mono numeric class.
- [ ] Quick chips ("Morgens 07:00", "Abends 18:00") visually subordinate to the time input.
- [ ] "im Account einrichten" link is accent-orange, not blue.
- [ ] Advanced toggle is a single ghost button with rotating chevron.
- [ ] Wind-exposition input has `m` unit suffix.
- [ ] No regression in existing report-config tests / testids.

## 📎 Attachments

- `uploads/CleanShot 2026-05-20 at 15.09.03@2x.png` — full reports section (advanced visible)
- `uploads/CleanShot 2026-05-20 at 15.09.15@2x.png` — reports section collapsed