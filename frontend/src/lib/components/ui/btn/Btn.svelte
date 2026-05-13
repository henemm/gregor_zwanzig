<script lang="ts" module>
	import { cn, type WithElementRef } from '$lib/utils.js';
	import type { HTMLAnchorAttributes, HTMLButtonAttributes } from 'svelte/elements';
	import type { Snippet } from 'svelte';

	export type BtnVariant =
		| 'primary'
		| 'accent'
		| 'outline'
		| 'ghost'
		| 'secondary'
		| 'destructive'
		| 'link';

	export type BtnSize =
		| 'xs'
		| 'sm'
		| 'md'
		| 'lg'
		| 'icon'
		| 'icon-xs'
		| 'icon-sm'
		| 'icon-lg';

	export type BtnProps = WithElementRef<HTMLButtonAttributes> &
		Partial<HTMLAnchorAttributes> & {
			variant?: BtnVariant;
			size?: BtnSize;
			href?: string;
			disabled?: boolean;
			children?: Snippet;
		};
</script>

<script lang="ts">
	let {
		class: className,
		variant = 'primary',
		size = 'md',
		ref = $bindable(null),
		href = undefined,
		type = 'button',
		disabled = false,
		children,
		...restProps
	}: BtnProps = $props();
</script>

{#if href}
	<a
		bind:this={ref}
		data-slot="btn"
		data-variant={variant}
		data-size={size}
		class={cn(className)}
		href={disabled ? undefined : href}
		aria-disabled={disabled ? 'true' : undefined}
		role={disabled ? 'link' : undefined}
		tabindex={disabled ? -1 : undefined}
		{...restProps}
	>
		{@render children?.()}
	</a>
{:else}
	<button
		bind:this={ref}
		data-slot="btn"
		data-variant={variant}
		data-size={size}
		class={cn(className)}
		{type}
		{disabled}
		{...restProps}
	>
		{@render children?.()}
	</button>
{/if}
