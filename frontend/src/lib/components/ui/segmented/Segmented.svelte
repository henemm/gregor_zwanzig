<script lang="ts">
  // Issue #418 — Dual-API: SOLL-Props (items/value/onChange/size) als primäre API,
  // IST-Props (options/selected/onselect) als rückwärtskompatibles Alias.
  // Issue #2881 Lieferung B (R2): `rolle="radio"` macht aus der Leiste eine Auswahl nach
  // WAI-ARIA-Radiogroup (statt nativer Radio-Knöpfe): Container `radiogroup`, Einträge `radio`
  // mit aria-checked, nur der gewählte in der Tab-Reihenfolge, Pfeiltasten wählen und fokussieren.
  // Ohne `rolle` bleibt alles wie bisher (Reiter, `role="tab"`).
  // Issue #2913 Teil 2 (K-4): `farbe` → Farbpunkt je Segment (data-slot="segmented-punkt", Farbe aus
  // --g-ampel-* in app.css); die items-API reicht testid/badge_testid/farbe durch wie die options-API.
  // #2913 Fix Metrik-Liste (AC-7): optionale `variant="kompakt"` → nur data-variant am Container,
  // Stil allein unter [data-slot="segmented"][data-variant="kompakt"] in app.css. Ohne Prop kein Attribut.
  type Farbe = 'green' | 'yellow' | 'orange' | 'red';
  type SollItem = { id: string; label: string; badge?: number; testid?: string; badge_testid?: string; farbe?: Farbe };
  type IstOption = { value: string; label: string; badge?: number; testid?: string; badge_testid?: string; farbe?: Farbe };

  let {
    items,
    value,
    onChange,
    size,
    options,
    selected,
    onselect,
    rolle = 'tabs',
    ariaLabel,
    testid,
    variant,
  }: {
    items?: SollItem[];
    value?: string;
    onChange?: (id: string) => void;
    size?: 'sm' | 'md';
    options?: IstOption[];
    selected?: string;
    onselect?: (value: string) => void;
    rolle?: 'tabs' | 'radio';
    ariaLabel?: string;
    testid?: string;
    variant?: 'kompakt';
  } = $props();

  const resolvedItems = $derived(
    items
      ? items.map((i): IstOption => ({ value: i.id, label: i.label, badge: i.badge, testid: i.testid, badge_testid: i.badge_testid, farbe: i.farbe }))
      : (options ?? [])
  );
  const resolvedValue = $derived(value ?? selected ?? '');
  const resolvedChange = $derived(
    onChange
      ? (v: string) => onChange(v)
      : (onselect ?? (() => {}))
  );
  const radio = $derived(rolle === 'radio');

  let leiste = $state<HTMLDivElement | undefined>();
  function taste(e: KeyboardEvent, i: number): void {
    if (!radio) return;
    const n = resolvedItems.length;
    const schritt: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (schritt[e.key] === undefined) return;
    e.preventDefault();
    const ziel = (i + schritt[e.key] + n) % n;
    resolvedChange(resolvedItems[ziel].value ?? '');
    leiste?.querySelectorAll<HTMLElement>('[data-slot="segmented-item"]')[ziel]?.focus();
  }
</script>

<div
  data-slot="segmented"
  data-size={size ?? undefined}
  data-variant={variant ?? undefined}
  bind:this={leiste}
  role={radio ? 'radiogroup' : undefined}
  aria-label={radio ? ariaLabel : undefined}
  data-testid={testid}
>
  {#each resolvedItems as item, i}
    {@const an = item.value === resolvedValue}
    <button
      type="button"
      role={radio ? 'radio' : 'tab'}
      data-slot="segmented-item"
      data-value={item.value ?? undefined}
      data-active={an ? "true" : "false"}
      data-state={an ? "active" : "inactive"}
      aria-selected={radio ? undefined : (an ? "true" : "false")}
      aria-checked={radio ? an : undefined}
      tabindex={radio ? (an ? 0 : -1) : undefined}
      data-testid={item.testid ?? undefined}
      onclick={() => resolvedChange(item.value ?? '')}
      onkeydown={(e) => taste(e, i)}
    >{#if item.farbe}<i data-slot="segmented-punkt" data-farbe={item.farbe} aria-hidden="true"></i>{/if}{item.label}{#if item.badge !== undefined && item.badge >= 1}<span data-slot="segmented-badge" data-testid={item.badge_testid ?? undefined}>{item.badge}</span>{/if}</button>
  {/each}
</div>
