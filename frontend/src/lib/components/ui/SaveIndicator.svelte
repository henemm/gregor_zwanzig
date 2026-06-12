<script lang="ts">
	// Issue #758 — SaveIndicator Atom.
	// Renders a compact, high-contrast save-state label in the TripHeader and CompareEditor.
	// Prop: controller — eine SaveStatus-Instanz (nie global singleton — AC-6).
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';

	interface Props {
		controller: SaveStatus;
	}
	let { controller }: Props = $props();
</script>

<span
	data-testid="save-indicator"
	data-state={controller.state}
	class="save-indicator"
	class:save-indicator--idle={controller.state === 'idle'}
	class:save-indicator--dirty={controller.state === 'dirty'}
	class:save-indicator--saving={controller.state === 'saving'}
	class:save-indicator--error={controller.state === 'error'}
>
	{#if controller.state === 'idle'}
		<span class="save-indicator__icon" aria-hidden="true">✓</span>
		<span>Gespeichert</span>
	{:else if controller.state === 'dirty'}
		<span class="save-indicator__icon" aria-hidden="true">●</span>
		<span>Nicht gespeichert</span>
	{:else if controller.state === 'saving'}
		<span class="save-indicator__spinner" aria-hidden="true"></span>
		<span>Speichere …</span>
	{:else if controller.state === 'error'}
		<span class="save-indicator__icon" aria-hidden="true">!</span>
		<span>Fehler beim Speichern{controller.error ? ': ' + controller.error : ''}</span>
	{/if}
</span>

<style>
	.save-indicator {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		font-size: 12px;
		font-family: var(--g-font-mono, ui-monospace, monospace);
		letter-spacing: 0.02em;
		padding: 3px 8px;
		border-radius: 4px;
		transition: background 200ms, color 200ms;
		white-space: nowrap;
		font-weight: 500;
	}
	.save-indicator--idle {
		color: var(--g-good, #2e7d32);
		background: rgba(46, 125, 50, 0.08);
	}
	.save-indicator--dirty {
		color: var(--g-warn, #b87800);
		background: rgba(200, 140, 0, 0.1);
	}
	.save-indicator--saving {
		color: var(--g-ink-3, #6b6b68);
		background: var(--g-surface-2, #f0ede8);
	}
	.save-indicator--error {
		color: var(--g-danger, #b34a2a);
		background: rgba(179, 74, 42, 0.09);
	}

	.save-indicator__icon {
		font-size: 11px;
		line-height: 1;
	}

	/* Spinner: CSS-only, no bits-ui dependency */
	.save-indicator__spinner {
		display: inline-block;
		width: 10px;
		height: 10px;
		border: 1.5px solid var(--g-ink-4, #b0afa8);
		border-top-color: var(--g-ink-3, #6b6b68);
		border-radius: 50%;
		animation: gz-spin 600ms linear infinite;
		flex-shrink: 0;
	}
	@keyframes gz-spin {
		to { transform: rotate(360deg); }
	}
</style>
