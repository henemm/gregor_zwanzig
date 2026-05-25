<script lang="ts">
	import type { HTMLInputAttributes, HTMLInputTypeAttribute } from "svelte/elements";
	import { cn, type WithElementRef } from "$lib/utils.js";

	type InputType = Exclude<HTMLInputTypeAttribute, "file">;

	// Issue #371: additive Atom-Bridge-Props (size/error). lg setzt fontSize 16px
	// (verhindert iOS-Auto-Zoom). Backward-compatible: ohne size unveraendert.
	type InputSize = "sm" | "md" | "lg";

	type Props = WithElementRef<
		Omit<HTMLInputAttributes, "type" | "size"> &
			({ type: "file"; files?: FileList } | { type?: InputType; files?: undefined }) & {
				size?: InputSize;
				error?: boolean;
			}
	>;

	let {
		ref = $bindable(null),
		value = $bindable(),
		type,
		files = $bindable(),
		class: className,
		size = undefined,
		error = false,
		"data-slot": dataSlot = "input",
		...restProps
	}: Props = $props();

	// lg -> 16px (kein iOS-Zoom); sm/md erben die bestehende Tailwind-Groesse.
	const sizeClass: Record<InputSize, string> = {
		sm: "text-sm",
		md: "text-base",
		lg: "text-[16px]"
	};
	const sizeCls = $derived(size ? sizeClass[size] : "");
</script>

{#if type === "file"}
	<input
		bind:this={ref}
		data-slot={dataSlot}
		data-testid="input"
		data-error={error || undefined}
		aria-invalid={error || undefined}
		class={cn(
			"dark:bg-input/30 border-input focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:aria-invalid:border-destructive/50 disabled:bg-input/50 dark:disabled:bg-input/80 h-8 rounded-lg border bg-transparent px-2.5 py-1 text-base transition-colors file:h-6 file:text-sm file:font-medium focus-visible:ring-3 aria-invalid:ring-3 md:text-sm file:text-foreground placeholder:text-muted-foreground w-full min-w-0 outline-none file:inline-flex file:border-0 file:bg-transparent disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
			sizeCls,
			className
		)}
		type="file"
		bind:files
		bind:value
		{...restProps}
	/>
{:else}
	<input
		bind:this={ref}
		data-slot={dataSlot}
		data-testid="input"
		data-error={error || undefined}
		aria-invalid={error || undefined}
		class={cn(
			"dark:bg-input/30 border-input focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:aria-invalid:border-destructive/50 disabled:bg-input/50 dark:disabled:bg-input/80 h-8 rounded-lg border bg-transparent px-2.5 py-1 text-base transition-colors file:h-6 file:text-sm file:font-medium focus-visible:ring-3 aria-invalid:ring-3 md:text-sm file:text-foreground placeholder:text-muted-foreground w-full min-w-0 outline-none file:inline-flex file:border-0 file:bg-transparent disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
			sizeCls,
			className
		)}
		{type}
		bind:value
		{...restProps}
	/>
{/if}
