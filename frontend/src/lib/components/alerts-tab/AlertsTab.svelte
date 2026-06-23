<script lang="ts">
	// Issue #864/#859 — AlertsTab: Per-Metrik-Stufen + Auto-Save.
	// Spec: docs/specs/modules/feat_864_859_alert_presets.md

	import AlertCooldownCard from './AlertCooldownCard.svelte';
	import AlertQuietHoursCard from './AlertQuietHoursCard.svelte';
	import AlertPreviewCard from './AlertPreviewCard.svelte';
	import AlertMetricLevelTable from './AlertMetricLevelTable.svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import { api } from '$lib/api';
	import type { Trip, AlertRule, AlertMetric, SensLevel } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import { migrateAlertPreset, ALERTABLE_METRICS, activeAlertableMetrics } from './alertMetricTable.ts';

	interface Props {
		trip: Trip;
		onTripUpdate?: (t: Trip) => void;
		saveController?: SaveStatus;
	}

	let { trip, onTripUpdate, saveController }: Props = $props();

	// Initialisierung: metric_alert_levels → Legacy alert_preset → Standard
	let currentLevels = $state<Record<AlertMetric, SensLevel>>(
		trip.display_config?.metric_alert_levels
			? (trip.display_config.metric_alert_levels as Record<AlertMetric, SensLevel>)
			: migrateAlertPreset(
					trip.display_config?.alert_preset ?? 'standard',
					ALERTABLE_METRICS as AlertMetric[],
				),
	);

	let alertRules = $state<AlertRule[]>(trip.alert_rules ?? []);
	let cooldownMinutes = $state<number | undefined>(trip.alert_cooldown_minutes ?? undefined);
	let quietFrom = $state<string | undefined>(trip.alert_quiet_from ?? undefined);
	let quietTo = $state<string | undefined>(trip.alert_quiet_to ?? undefined);

	// Nur aktiv gewählte alertable Metriken anzeigen (AC-1)
	let displayMetrics = $derived(activeAlertableMetrics(trip.display_config?.metrics));
	let allOff = $derived(displayMetrics.every((m) => currentLevels[m] === 'off'));

	function buildSaveFn() {
		const levels = { ...currentLevels };
		return async () => {
			await api.put(`/api/trips/${trip.id}`, {
				display_config: {
					...trip.display_config,
					metric_alert_levels: levels,
				},
				alert_cooldown_minutes: cooldownMinutes ?? null,
				alert_quiet_from: quietFrom || null,
				alert_quiet_to: quietTo || null,
			});
		};
	}

	function onLevelChange(metric: AlertMetric, level: SensLevel) {
		currentLevels = { ...currentLevels, [metric]: level };
		saveController?.schedule(buildSaveFn());
	}
</script>

<div class="alerts-tab" data-testid="alerts-tab">
	<Eyebrow>Alerts · Sofort-Meldung</Eyebrow>
	<h2 class="alerts-h2" data-testid="alerts-tab-heading">Sofort-Meldung zwischen den Briefings</h2>

	<AlertMetricLevelTable
		activeMetrics={displayMetrics as AlertMetric[]}
		levels={currentLevels}
		{onLevelChange}
	/>

	<div class="extra-cards" class:subdued={allOff}>
		<AlertCooldownCard bind:cooldown_minutes={cooldownMinutes} />
		<AlertQuietHoursCard bind:quiet_from={quietFrom} bind:quiet_to={quietTo} />
	</div>

	<AlertPreviewCard {trip} {alertRules} />
</div>

<style>
	.alerts-tab {
		display: flex;
		flex-direction: column;
		gap: 14px;
		position: relative;
		padding: 28px 40px 60px;
		max-width: 900px;
	}

	.alerts-h2 {
		font-size: 26px;
		font-weight: 600;
		letter-spacing: -0.01em;
		margin: 6px 0 8px;
		color: var(--g-ink);
	}

	.extra-cards {
		display: grid;
		gap: 1rem;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		transition: opacity 0.2s;
	}

	.extra-cards.subdued {
		opacity: 0.5;
		pointer-events: none;
	}

	@media (max-width: 899px) {
		.alerts-tab {
			padding: 1rem;
			max-width: 100%;
		}

		.extra-cards {
			grid-template-columns: 1fr;
		}
	}
</style>
