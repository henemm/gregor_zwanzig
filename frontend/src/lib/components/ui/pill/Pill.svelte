<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn, type WithElementRef } from '$lib/utils.js';

	interface Props extends WithElementRef<HTMLAttributes<HTMLSpanElement>> {
		tone?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'accent';
		children?: Snippet;
	}

	let {
		tone = 'default',
		class: className,
		ref = $bindable(null),
		children,
		...rest
	}: Props = $props();
</script>

<span
	data-slot="pill"
	data-tone={tone}
	class={cn(className)}
	bind:this={ref}
	{...rest}
>
	{@render children?.()}
</span>
