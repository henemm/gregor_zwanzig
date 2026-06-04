<script lang="ts">
	// Issue #420 — eigenständige Implementierung gemäß atoms.jsx-Vorlage.
	// Delegiert NICHT mehr an ui/card/card.svelte.
	import type { Snippet } from 'svelte';

	let {
		children,
		padding = 20,
		accent = false,
		background,
		class: className,
		...restProps
	}: {
		children?: Snippet;
		padding?: number;
		accent?: boolean;
		background?: string;
		class?: string;
		[key: string]: unknown;
	} = $props();
</script>

<div
	data-slot="card"
	class={className}
	style:background={background ?? "var(--g-card)"}
	style:border-radius="var(--g-r-3)"
	style:box-shadow="var(--g-shadow-1)"
	style:padding="{padding}px"
	style:border="1px solid var(--g-rule)"
	style:border-left={accent ? '3px solid var(--g-accent)' : undefined}
	{...restProps}
>
	{@render children?.()}
</div>
