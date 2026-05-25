<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn, type WithElementRef } from '$lib/utils.js';

	// #371: Sandbox-Tone-Aliase (atoms.jsx) additiv akzeptiert + ghost-Tone.
	type PillTone =
		| 'default' | 'success' | 'warning' | 'danger' | 'info' | 'accent' | 'ghost'
		| 'neutral' | 'good' | 'warn' | 'bad';

	interface Props extends WithElementRef<HTMLAttributes<HTMLSpanElement>> {
		tone?: PillTone;
		children?: Snippet;
	}

	let {
		tone = 'default',
		class: className,
		ref = $bindable(null),
		children,
		...rest
	}: Props = $props();

	// Sandbox-Namen auf bestehende data-tone-Werte mappen (backward-compatible).
	const TONE_ALIAS: Record<string, string> = {
		neutral: 'default',
		good: 'success',
		warn: 'warning',
		bad: 'danger'
	};
	const effectiveTone = $derived(TONE_ALIAS[tone] ?? tone);
</script>

<span
	data-slot="pill"
	data-tone={effectiveTone}
	class={cn(className)}
	bind:this={ref}
	{...rest}
>
	{@render children?.()}
</span>
