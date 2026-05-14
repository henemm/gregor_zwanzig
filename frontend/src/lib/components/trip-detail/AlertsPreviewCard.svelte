<script lang="ts">
	// Issue #222 W2 — Alert-Preview-Karte fuer die rechte Spalte im
	// Trip-Detail Overview-Tab.
	// Spec: docs/specs/modules/issue_222_w2_frontend_alert_konfigurator.md §4.
	//
	// Rendert pro `enabled=true`-Rule eine `AlertRow` mit Pill und Comparison-Symbol.
	// Bei keiner enabled-Rule: Empty-State.
	// Edit-Link entfernt (eigenes Folge-Issue fuer Edit-Pfad).

	import type { Trip } from '$lib/types';
	import { GCard } from '$lib/components/ui/g-card';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import AlertRow from './AlertRow.svelte';

	interface Props {
		trip: Trip;
	}

	let { trip }: Props = $props();

	let enabledRules = $derived((trip.alert_rules ?? []).filter((r) => r.enabled));
</script>

<GCard data-testid="right-card-alerts" class="alerts-card">
	<Eyebrow>Alerts</Eyebrow>
	<h3 class="card-title">Wetter-Warnungen</h3>

	{#if enabledRules.length === 0}
		<p class="empty-state" data-testid="right-card-alerts-empty">
			Noch keine Alerts konfiguriert
		</p>
	{:else}
		<ul class="rules-list" data-testid="right-card-alerts-rules">
			{#each enabledRules as rule (rule.id)}
				<li><AlertRow {rule} /></li>
			{/each}
		</ul>
	{/if}
</GCard>

<style>
	:global([data-testid='right-card-alerts']) {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 1rem;
		border: 1px solid var(--g-border, #e5e7eb);
		border-radius: 0.5rem;
		background: var(--g-surface-1, #fff);
	}
	.card-title {
		font-size: 1rem;
		font-weight: 600;
		margin: 0;
	}
	.empty-state {
		font-size: 0.875rem;
		color: var(--g-ink-faint, #6b7280);
		margin: 0;
	}
	.rules-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.rules-list li {
		padding: 0.25rem 0;
	}
</style>
