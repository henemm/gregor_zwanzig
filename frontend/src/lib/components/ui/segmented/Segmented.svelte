<script lang="ts">
  // Issue #418 — Dual-API: SOLL-Props (items/value/onChange/size) als primäre API,
  // IST-Props (options/selected/onselect) als rückwärtskompatibles Alias.
  type SollItem = { id: string; label: string; badge?: number };
  type IstOption = { value: string; label: string; badge?: number; testid?: string; badge_testid?: string };

  let {
    items,
    value,
    onChange,
    size,
    options,
    selected,
    onselect,
  }: {
    items?: SollItem[];
    value?: string;
    onChange?: (id: string) => void;
    size?: 'sm' | 'md';
    options?: IstOption[];
    selected?: string;
    onselect?: (value: string) => void;
  } = $props();

  const resolvedItems = $derived(
    items
      ? items.map(i => ({ value: i.id, label: i.label, badge: i.badge, testid: undefined, badge_testid: undefined }))
      : (options ?? [])
  );
  const resolvedValue = $derived(value ?? selected ?? '');
  const resolvedChange = $derived(
    onChange
      ? (v: string) => onChange(v)
      : (onselect ?? (() => {}))
  );
</script>

<div data-slot="segmented" data-size={size ?? undefined}>
  {#each resolvedItems as item}
    <button
      type="button"
      role="tab"
      data-slot="segmented-item"
      data-value={item.value ?? undefined}
      data-active={item.value === resolvedValue ? "true" : "false"}
      data-state={item.value === resolvedValue ? "active" : "inactive"}
      aria-selected={item.value === resolvedValue ? "true" : "false"}
      data-testid={item.testid ?? undefined}
      onclick={() => resolvedChange(item.value ?? '')}
    >{item.label}{#if item.badge !== undefined && item.badge >= 1}<span data-slot="segmented-badge" data-testid={item.badge_testid ?? undefined}>{item.badge}</span>{/if}</button>
  {/each}
</div>
