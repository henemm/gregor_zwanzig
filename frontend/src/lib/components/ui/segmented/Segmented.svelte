<script lang="ts">
  type Option = { value: string; label: string };

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
      onclick={() => onselect(opt.value)}
    >{opt.label}</button>
  {/each}
</div>
