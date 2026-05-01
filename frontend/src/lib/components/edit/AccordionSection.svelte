<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		id: string;
		title: string;
		open: boolean;
		onToggle: () => void;
		children: Snippet;
	}
	let { id, title, open, onToggle, children }: Props = $props();
</script>

<div
	data-testid="edit-section-{id}"
	class="border rounded-lg mb-3 overflow-hidden {open ? 'border-primary shadow-sm' : ''}"
>
	<button
		type="button"
		data-testid="edit-section-{id}-header"
		class="w-full flex justify-between items-center px-4 py-3 text-left
		       font-medium min-h-[48px]
		       {open ? 'bg-primary/10 text-primary' : 'bg-muted/50 hover:bg-muted active:bg-muted'}"
		aria-expanded={open}
		onclick={onToggle}
	>
		<span>{title}</span>
		<span aria-hidden="true" class="text-lg leading-none">{open ? '−' : '+'}</span>
	</button>
	{#if open}
		<div class="p-4">
			{@render children()}
		</div>
	{/if}
</div>
