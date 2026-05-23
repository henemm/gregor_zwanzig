<script lang="ts">
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn, type WithElementRef } from '$lib/utils.js';

	type WeatherTone = 'rain' | 'sun' | 'wind' | 'snow' | 'thunder' | 'fog';
	type SemanticTone = 'default' | 'success' | 'warning' | 'danger' | 'info';

	interface Props extends WithElementRef<HTMLAttributes<HTMLSpanElement>> {
		tone: WeatherTone | SemanticTone;
		size?: 'xs' | 'sm' | 'md';
	}

	let {
		tone,
		size = 'sm',
		class: className,
		ref = $bindable(null),
		'aria-label': ariaLabel,
		...rest
	}: Props = $props();
</script>

<span
	data-slot="dot"
	data-tone={tone}
	data-size={size}
	class={cn(className)}
	aria-hidden={ariaLabel ? undefined : 'true'}
	aria-label={ariaLabel}
	bind:this={ref}
	{...rest}
></span>
