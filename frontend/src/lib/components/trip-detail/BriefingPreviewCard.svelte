<script lang="ts">
	// Epic #135 Step 5 — Briefing-Preview-Karte fuer die rechte Spalte im
	// Trip-Detail Overview-Tab (Issue #159).
	//
	// Spec: docs/specs/modules/epic_135_step5_right_column.md §2.

	import type { Trip } from '$lib/types';
	import { GCard } from '$lib/components/ui/g-card';
	import { Eyebrow } from '$lib/components/atoms';
	import { getReportSchedule } from '$lib/utils/rightColumn';

	interface Props {
		trip: Trip;
	}

	let { trip }: Props = $props();

	const schedule = $derived(getReportSchedule(trip));
	const isEmpty = $derived(!schedule.enabled && !schedule.morning && !schedule.evening);
</script>

<GCard data-testid="right-card-briefings" class="briefing-card">
	<Eyebrow>Briefings</Eyebrow>
	<h3 class="card-title">Tägliche Reports</h3>

	{#if isEmpty}
		<p class="empty-state">Briefings deaktiviert</p>
	{:else}
		<ul class="schedule-list">
			<li data-testid="right-card-briefings-morning" class="schedule-row">
				<span
					class="dot"
					data-tone={schedule.enabled && schedule.morning ? 'success' : 'muted'}
				></span>
				<span>Morgens · {schedule.morning ?? '—'}</span>
			</li>
			<li data-testid="right-card-briefings-evening" class="schedule-row">
				<span
					class="dot"
					data-tone={schedule.enabled && schedule.evening ? 'success' : 'muted'}
				></span>
				<span>Abends · {schedule.evening ?? '—'}</span>
			</li>
			<li data-testid="right-card-briefings-alerts" class="schedule-row">
				<span class="dot" data-tone={schedule.alertOnChanges ? 'success' : 'muted'}></span>
				<span>Alerts bei Änderungen · {schedule.alertOnChanges ? 'an' : 'aus'}</span>
			</li>
		</ul>
	{/if}

	<a href="#briefings" data-testid="right-card-briefings-edit-link" class="edit-link">
		Bearbeiten →
	</a>
</GCard>

<style>
	:global([data-testid='right-card-briefings']) {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 1rem;
		border: 1px solid var(--g-ink-faint);
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
		color: var(--g-ink-muted);
		margin: 0;
	}
	.schedule-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}
	.schedule-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.875rem;
	}
	.dot {
		display: inline-block;
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 9999px;
		background: var(--g-ink-faint, #9ca3af);
	}
	.dot[data-tone='success'] {
		background: var(--g-success, #16a34a);
	}
	.edit-link {
		display: inline-block;
		font-size: 0.875rem;
		color: var(--g-accent-deep);
		text-decoration: none;
		margin-top: 0.25rem;
	}
	.edit-link:hover {
		text-decoration: underline;
	}
</style>
