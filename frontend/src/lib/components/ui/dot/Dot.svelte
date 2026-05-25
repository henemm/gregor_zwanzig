<script lang="ts">
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn, type WithElementRef } from '$lib/utils.js';

	type WeatherTone = 'rain' | 'sun' | 'wind' | 'snow' | 'thunder' | 'fog';
	type SemanticTone = 'default' | 'success' | 'warning' | 'danger' | 'info';

	interface Props extends WithElementRef<HTMLAttributes<HTMLSpanElement>> {
		// Issue #371: numerische size zusaetzlich akzeptieren (px, inline), tone-Default 'good'. Additiv.
		tone?: WeatherTone | SemanticTone | 'good' | 'warn' | 'bad' | 'neutral' | 'accent';
		size?: 'xs' | 'sm' | 'md' | number;
	}

	let {
		tone = 'good',
		size = 'sm',
		class: className,
		ref = $bindable(null),
		'aria-label': ariaLabel,
		...rest
	}: Props = $props();

	const numericSize = $derived(typeof size === 'number' ? size : undefined);
	const tokenSize = $derived(typeof size === 'number' ? undefined : size);
</script>

<span
	data-slot="dot"
	data-tone={tone}
	data-size={tokenSize}
	class={cn(className)}
	style:width={numericSize ? `${numericSize}px` : undefined}
	style:height={numericSize ? `${numericSize}px` : undefined}
	aria-hidden={ariaLabel ? undefined : 'true'}
	aria-label={ariaLabel}
	bind:this={ref}
	{...rest}
></span>
