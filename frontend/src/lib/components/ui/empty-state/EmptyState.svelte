<script lang="ts">
	import type { Component, Snippet } from 'svelte';

	interface EmptyStateProps {
		icon?: Component;
		title: string;
		description?: string;
		children?: Snippet;
	}

	let { icon: Icon, title, description, children }: EmptyStateProps = $props();
</script>

<div data-slot="empty-state" data-testid="empty-state">
	{#if Icon}
		<Icon {...{ 'data-slot': 'empty-state-icon' }} />
	{/if}
	<p data-slot="empty-state-title">{title}</p>
	{#if description}
		<p data-slot="empty-state-desc">{description}</p>
	{/if}
	{@render children?.()}
</div>
