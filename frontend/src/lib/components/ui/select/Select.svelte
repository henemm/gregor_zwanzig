<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    value = $bindable(),
    onchange,
    children,
    class: className,
    ...restProps
  }: {
    value?: unknown;
    onchange?: (e: Event) => void;
    children?: Snippet;
    class?: string;
    [key: string]: unknown;
  } = $props();
</script>

<span class="gz-select {className ?? ''}">
  <select bind:value {onchange} {...restProps}>
    {@render children?.()}
  </select>
  <svg class="gz-select__chevron" viewBox="0 0 16 16" aria-hidden="true" fill="none">
    <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>
</span>

<style>
  .gz-select {
    position: relative;
    display: inline-block;
  }
  .gz-select select {
    appearance: none;
    -webkit-appearance: none;
    width: 100%;
    padding: 6px 32px 6px 10px;
    font-family: var(--g-font-ui);
    font-size: var(--g-text-sm);
    color: var(--g-ink);
    background: var(--g-paper);
    border: 1px solid var(--g-ink-faint);
    border-radius: var(--g-radius-sm);
    cursor: pointer;
    line-height: 1.4;
  }
  .gz-select select:focus-visible {
    outline: 2px solid var(--g-accent);
    outline-offset: 2px;
  }
  .gz-select select:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .gz-select__chevron {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    width: 14px;
    height: 14px;
    color: var(--g-ink-muted);
    pointer-events: none;
  }
  @media (max-width: 767px) {
    .gz-select select {
      font-size: 16px; /* iOS zoom guard (#272, #382) */
    }
  }
</style>
