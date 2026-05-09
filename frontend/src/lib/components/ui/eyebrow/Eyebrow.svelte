<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn, type WithElementRef } from '$lib/utils.js';

	interface Props extends WithElementRef<HTMLAttributes<HTMLSpanElement>> {
		children?: Snippet;
	}

	let {
		class: className,
		ref = $bindable(null),
		children,
		...rest
	}: Props = $props();
</script>

<span
	data-slot="eyebrow"
	class={cn(className)}
	bind:this={ref}
	{...rest}
>
	{@render children?.()}
</span>
