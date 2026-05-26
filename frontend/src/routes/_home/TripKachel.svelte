<script lang="ts">
	import type { Trip, Stage } from '$lib/types.js';
	import { tripStatus } from '$lib/utils/tripStatus.js';

	let { trip }: { trip: Trip } = $props();

	function computeRange(t: Trip): string {
		const dates = t.stages?.map((s: Stage) => s.date).filter(Boolean).sort() ?? [];
		if (!dates.length) return '';
		const fmt = (d: string) =>
			new Date(d).toLocaleDateString('de-DE', { day: 'numeric', month: 'short' });
		return dates.length === 1 ? fmt(dates[0]) : `${fmt(dates[0])} – ${fmt(dates[dates.length - 1])}`;
	}

	const status = $derived(tripStatus(trip));
	const range = $derived(computeRange(trip));
	const stageCount = $derived(trip.stages?.length ?? 0);

	const statusColors: Record<string, string> = {
		aktiv: 'var(--g-accent-deep)',
		geplant: 'var(--g-success)',
		fertig: 'var(--g-ink-muted)',
		draft: 'var(--g-ink-muted)'
	};
</script>

<a href="/trips/{trip.id}" data-testid="trip-card" class="kachel">
	<div class="kachel__row">
		<span class="kachel__type">Trip</span>
		<span class="kachel__status" style:color={statusColors[status]}>
			<span class="kachel__dot" style:background={statusColors[status]}></span>
			{status}
		</span>
	</div>
	<div class="kachel__name">{trip.name}</div>
	{#if range}
		<div class="kachel__when">{range}</div>
	{/if}
	<div class="kachel__meta">{stageCount} {stageCount === 1 ? 'Etappe' : 'Etappen'}</div>
</a>

<style>
	.kachel {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
		padding: var(--g-s-4);
		background: var(--g-surface-1);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-lg);
		text-decoration: none;
		color: var(--g-ink);
		transition: border-color 120ms, box-shadow 120ms;
	}
	.kachel:hover {
		border-color: var(--g-accent);
		box-shadow: var(--g-elev-1);
	}
	.kachel__row {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.kachel__type {
		font-family: var(--g-font-data);
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--g-ink-muted);
	}
	.kachel__status {
		display: inline-flex;
		align-items: center;
		gap: var(--g-s-1);
		font-family: var(--g-font-data);
		font-size: 9px;
		letter-spacing: 0.16em;
		text-transform: uppercase;
	}
	.kachel__dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.kachel__name {
		font-size: 15px;
		font-weight: 600;
	}
	.kachel__when {
		font-family: var(--g-font-data);
		font-size: 12px;
		color: var(--g-ink-muted);
	}
	.kachel__meta {
		font-size: 12px;
		color: var(--g-ink-muted);
	}
</style>
