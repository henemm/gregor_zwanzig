<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    checked = $bindable(false),
    disabled = false,
    onchange,
    children,
    ...restProps
  }: {
    checked?: boolean;
    disabled?: boolean;
    onchange?: (e: Event) => void;
    children?: Snippet;
    [key: string]: unknown;
  } = $props();
</script>

<label class="gz-checkbox" class:disabled>
  <span class="gz-checkbox__box" class:checked>
    <input
      type="checkbox"
      bind:checked
      {disabled}
      {onchange}
      {...restProps}
    />
    {#if checked}
      <svg class="gz-checkbox__check" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M3.5 8.5l3 3 6-7" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    {/if}
  </span>
  {#if children}
    <span class="gz-checkbox__label">{@render children()}</span>
  {/if}
</label>

<style>
  .gz-checkbox {
    display: inline-flex;
    align-items: center;
    gap: var(--g-s-2);
    cursor: pointer;
    user-select: none;
    font-size: var(--g-text-sm);
    color: var(--g-ink);
  }
  .gz-checkbox.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .gz-checkbox__box {
    position: relative;
    width: 16px;
    height: 16px;
    flex-shrink: 0;
    border: 1.5px solid var(--g-ink-faint);
    border-radius: var(--g-radius-xs);
    background: var(--g-paper);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: background-color 120ms ease, border-color 120ms ease;
  }
  .gz-checkbox__box.checked {
    background: var(--g-ink);
    border-color: var(--g-ink);
  }
  .gz-checkbox__box input {
    position: absolute;
    inset: 0;
    opacity: 0;
    margin: 0;
    cursor: inherit;
    width: 100%;
    height: 100%;
  }
  .gz-checkbox__box:focus-within {
    outline: 2px solid var(--g-accent);
    outline-offset: 2px;
  }
  .gz-checkbox__check {
    width: 10px;
    height: 10px;
  }
  .gz-checkbox__label {
    line-height: 1.4;
  }
</style>
