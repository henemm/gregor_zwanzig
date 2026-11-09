<script lang="ts">
  // Issue #2881 Lieferung B (R2, ADR-0111): Auswahl als Design-System-Baustein — bits-ui Select
  // (eigene Liste, Rolle listbox, Tastatur: Enter/Leertaste/Pfeile öffnen, Pfeile wählen vor,
  // Enter übernimmt) statt nativem <select>. EINE Art für alle Aufrufer: Optionen als
  // `options: {value,label}[]`, Wert als String, Änderung über `onValueChange`.
  // Weitere Attribute (data-testid, id, aria-*, style) landen am Auslöser (Knopf, aria-haspopup=listbox).
  import { Select as SelectPrimitive } from 'bits-ui';

  type Option = { value: string; label: string };

  let {
    options,
    value = $bindable(''),
    onValueChange,
    disabled = false,
    class: className,
    style,
    ...restProps
  }: {
    options: Option[];
    value?: string;
    onValueChange?: (value: string) => void;
    disabled?: boolean;
    class?: string;
    style?: string;
    [key: string]: unknown;
  } = $props();

  // bits-ui wertet '' als „nichts gewählt" — eine echte Leer-Option (z. B. „Standard") bekommt
  // intern einen Platzhalterwert und geht nach außen wieder als '' hinaus.
  const LEER = '__gz_leer__';
  const innen = (v: string) => (v === '' ? LEER : v);
  const aussen = (v: string) => (v === LEER ? '' : v);

  const items = $derived(options.map((o) => ({ value: innen(o.value), label: o.label })));
  const anzeige = $derived(options.find((o) => o.value === (value ?? ''))?.label ?? '');

  function gewaehlt(neu: string): void {
    const v = aussen(neu);
    if (v === value) return;
    value = v;
    onValueChange?.(v);
  }
</script>

<SelectPrimitive.Root type="single" value={innen(value ?? '')} onValueChange={gewaehlt} {items} {disabled}>
  <SelectPrimitive.Trigger class="gz-select {className ?? ''}" {style} {...restProps}>
    <span class="gz-select__wert">{anzeige}</span>
    <svg class="gz-select__chevron" viewBox="0 0 16 16" aria-hidden="true" fill="none">
      <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </SelectPrimitive.Trigger>
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content data-slot="gz-select-liste" sideOffset={4}>
      <SelectPrimitive.Viewport>
        {#each items as o (o.value)}
          <SelectPrimitive.Item value={o.value} label={o.label} data-slot="gz-select-option">
            {o.label}
          </SelectPrimitive.Item>
        {/each}
      </SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
</SelectPrimitive.Root>

<style>
  :global(.gz-select) {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    box-sizing: border-box;
    min-width: 0;
    padding: 6px 32px 6px 10px;
    font-family: var(--g-font-ui);
    font-size: var(--g-text-sm);
    color: var(--g-ink);
    background: var(--g-paper);
    border: 1px solid var(--g-ink-faint);
    border-radius: var(--g-radius-sm);
    cursor: pointer;
    line-height: 1.4;
    text-align: left;
  }
  :global(.gz-select:focus-visible) {
    outline: 2px solid var(--g-accent);
    outline-offset: 2px;
  }
  :global(.gz-select[data-disabled]) {
    opacity: 0.5;
    cursor: not-allowed;
  }
  :global(.gz-select__wert) {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  :global(.gz-select__chevron) {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    width: 14px;
    height: 14px;
    color: var(--g-ink-muted);
    pointer-events: none;
  }
  /* Liste im Portal (außerhalb des Bausteins im DOM). */
  :global([data-slot='gz-select-liste']) {
    z-index: 1000;
    max-height: min(320px, var(--bits-select-content-available-height, 320px));
    min-width: var(--bits-select-anchor-width);
    overflow-y: auto;
    padding: 4px;
    border: 1px solid var(--g-rule);
    border-radius: 8px;
    background: var(--g-card);
    color: var(--g-ink);
    box-shadow: 0 6px 20px rgba(26, 26, 24, 0.14);
    font-family: var(--g-font-ui);
    font-size: var(--g-text-sm);
  }
  :global([data-slot='gz-select-option']) {
    display: flex;
    align-items: center;
    min-height: 32px;
    padding: 6px 10px;
    border-radius: var(--g-r-2);
    cursor: pointer;
    user-select: none;
    outline: none;
  }
  :global([data-slot='gz-select-option'][data-highlighted]) {
    background: var(--g-paper-deep);
  }
  :global([data-slot='gz-select-option'][data-selected]) {
    font-weight: 600;
  }
  @media (max-width: 899px), (pointer: coarse) {
    :global(.gz-select) {
      font-size: 16px; /* iOS zoom guard (#272, #382); #2601: auch Querformat/Touch */
      min-height: 44px;
    }
    :global([data-slot='gz-select-option']) {
      min-height: 44px;
      font-size: 16px;
    }
  }
</style>
