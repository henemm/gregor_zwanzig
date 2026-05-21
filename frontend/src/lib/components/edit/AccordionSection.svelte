<script lang="ts">
	import type { Snippet } from 'svelte';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';

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
	class="border rounded-[var(--g-radius-md)] mb-3 overflow-hidden {open ? 'shadow-sm' : ''}"
>
	<button
		type="button"
		data-testid="edit-section-{id}-header"
		class="w-full flex justify-between items-center px-4 py-3 text-left font-medium min-h-[48px] hover:opacity-90 active:opacity-80"
		style="background: var(--g-surface-2); color: var(--g-ink);"
		aria-expanded={open}
		onclick={onToggle}
	>
		<span>{title}</span>
		<ChevronDown
			size={14}
			style="color: var(--g-ink-muted); transform: rotate({open ? 180 : 0}deg); transition: transform 150ms ease; flex-shrink: 0;"
		/>
	</button>
	{#if open}
		<div class="p-4">
			{@render children()}
		</div>
	{/if}
</div>
