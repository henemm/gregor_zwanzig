<script lang="ts">
	// Issue #2521 S1: Sprechblase (bits-ui Popover) nach Muster ui/dialog.
	// Farben ausdruecklich als Tokens (WCAG-AA, Spec AC-14): Text --g-ink-2
	// auf Karte --g-card. Schliessen per Esc oder Tippen daneben (bits-ui),
	// der Fokus kehrt dabei auf den Ausloeser zurueck.
	import { Popover as PopoverPrimitive } from "bits-ui";

	let {
		ref = $bindable(null),
		sideOffset = 6,
		children,
		...restProps
	}: PopoverPrimitive.ContentProps = $props();
</script>

<PopoverPrimitive.Portal>
	<PopoverPrimitive.Content
		bind:ref
		data-slot="popover-content"
		{sideOffset}
		style="z-index: 1000; max-width: min(300px, calc(100vw - 24px)); padding: 10px 12px; border: 1px solid var(--g-rule); border-radius: 8px; background: var(--g-card); color: var(--g-ink-2); font-size: 13px; line-height: 1.5; box-shadow: 0 6px 20px rgba(26, 26, 24, 0.14); outline: none;"
		{...restProps}
	>
		{@render children?.()}
	</PopoverPrimitive.Content>
</PopoverPrimitive.Portal>
