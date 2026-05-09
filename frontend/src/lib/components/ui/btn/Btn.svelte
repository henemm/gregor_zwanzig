<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import { cn, type WithElementRef } from '$lib/utils.js';

	interface Props extends WithElementRef<HTMLButtonAttributes> {
		variant?: 'accent' | 'ghost' | 'outline';
		size?: 'sm' | 'md' | 'lg';
		children?: Snippet;
	}

	let {
		variant = 'accent',
		size = 'md',
		class: className,
		ref = $bindable(null),
		children,
		...rest
	}: Props = $props();
</script>

<button
	data-slot="btn"
	data-variant={variant}
	data-size={size}
	class={cn(className)}
	bind:this={ref}
	{...rest}
>
	{@render children?.()}
</button>
