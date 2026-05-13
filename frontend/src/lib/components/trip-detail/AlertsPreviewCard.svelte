<script lang="ts">
	// Epic #135 Step 5 — Alert-Preview-Karte fuer die rechte Spalte im
	// Trip-Detail Overview-Tab (Issue #159, Skeleton bis #205).
	//
	// Spec: docs/specs/modules/epic_135_step5_right_column.md §4.

	import type { Trip } from '$lib/types';
	import { GCard } from '$lib/components/ui/g-card';
	import { Eyebrow } from '$lib/components/ui/eyebrow';

	// Skeleton-Karte: Trip-Prop wird derzeit nicht gelesen — Inhalt blockiert
	// auf Issue #205 (`Trip.alert_rules` im Datenmodell).
	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	interface Props {
		trip: Trip;
	}

	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	let { trip }: Props = $props();
</script>

<GCard data-testid="right-card-alerts" class="alerts-card">
	<Eyebrow>Alerts</Eyebrow>
	<h3 class="card-title">Wetter-Warnungen</h3>

	<p class="empty-state" data-testid="right-card-alerts-empty">
		Noch keine Alerts konfiguriert
	</p>

	<a href="#alerts" data-testid="right-card-alerts-edit-link" class="edit-link">
		Konfigurieren →
	</a>
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
	.edit-link {
		display: inline-block;
		font-size: 0.875rem;
		color: var(--g-accent, #2563eb);
		text-decoration: none;
		margin-top: 0.25rem;
	}
	.edit-link:hover {
		text-decoration: underline;
	}
</style>
