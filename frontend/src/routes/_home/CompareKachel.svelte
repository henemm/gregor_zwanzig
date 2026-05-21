<script lang="ts">
	import type { Subscription } from '$lib/types.js';

	let { sub }: { sub: Subscription } = $props();

	const DAYS = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];

	function scheduleLabel(s: Subscription): string {
		if (s.schedule === 'daily_morning') return 'tägl. 07:00';
		if (s.schedule === 'daily_evening') return 'tägl. 18:00';
		if (s.schedule === 'weekly') {
			const day = DAYS[s.weekday ?? 0];
			const hour = String(s.time_window_start ?? 7).padStart(2, '0');
			return `${day} ${hour}:00`;
		}
		return s.schedule;
	}

	const label = $derived(scheduleLabel(sub));
	const firstLoc = $derived(
		sub.locations?.length > 0 && sub.locations[0] !== '*' ? sub.locations[0] : null
	);
	const statusColor = $derived(sub.enabled ? 'var(--g-success)' : 'var(--g-ink-faint)');
	const statusLabel = $derived(sub.enabled ? 'aktiv' : 'pausiert');
</script>

<a href="/compare" data-testid="subscription-card" class="kachel">
	<div class="kachel__row">
		<span class="kachel__type">Vergleich</span>
		<span class="kachel__status" style:color={statusColor}>
			<span class="kachel__dot" style:background={statusColor}></span>
			{statusLabel}
		</span>
	</div>
	<div class="kachel__name">{sub.name}</div>
	<div class="kachel__when">{label}</div>
	{#if firstLoc}
		<div class="kachel__meta">{firstLoc}</div>
	{/if}
</a>

<style>
	.kachel {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 14px 16px;
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
		color: var(--g-ink-faint);
	}
	.kachel__status {
		display: inline-flex;
		align-items: center;
		gap: 5px;
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
