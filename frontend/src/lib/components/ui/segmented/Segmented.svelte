<script lang="ts">
  type Option = { value: string; label: string; badge?: number; testid?: string; badge_testid?: string };

  let {
    options,
    selected,
    onselect
  }: {
    options: Option[];
    selected: string;
    onselect: (v: string) => void;
  } = $props();
</script>

<div data-slot="segmented">
  {#each options as opt}
    <button
      type="button"
      data-slot="segmented-item"
      data-active={opt.value === selected ? "true" : "false"}
      data-state={opt.value === selected ? "active" : "inactive"}
      data-testid={opt.testid ?? undefined}
      onclick={() => onselect(opt.value)}
    >{opt.label}{#if opt.badge !== undefined && opt.badge >= 1}<span data-slot="segmented-badge" data-testid={opt.badge_testid ?? undefined}>{opt.badge}</span>{/if}</button>
  {/each}
</div>
