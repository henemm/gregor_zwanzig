<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn, type WithElementRef } from '$lib/utils.js';

	interface Props extends WithElementRef<HTMLAttributes<HTMLSpanElement>> {
		// Issue #371: optionaler color-Prop (additiv). KEIN Default → ohne color
		// gewinnt die app.css-Regel [data-slot="eyebrow"] (var(--g-ink-faint)),
		// bestehende Aufrufer bleiben unveraendert (AC-5/C6). Inline-Override nur
		// bei explizit gesetztem color (z.B. Sandbox-Atom mit --g-ink-3).
		color?: string;
		children?: Snippet;
	}

	let {
		class: className,
		color = undefined,
		ref = $bindable(null),
		children,
		...rest
	}: Props = $props();
</script>

<span
	data-slot="eyebrow"
	class={cn(className)}
	style:color={color}
	bind:this={ref}
	{...rest}
>
	{@render children?.()}
</span>
