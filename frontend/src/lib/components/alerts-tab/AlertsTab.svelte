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

	// Issue #946: metric_alert_levels ist die EINZIGE Quelle. Sind weder
	// metric_alert_levels noch alert_preset gesetzt → Onboarding-Zustand
	// (kein stiller Fallback auf 'standard').
	let isOnboarding = $state<boolean>(
		!trip.display_config?.metric_alert_levels && !trip.display_config?.alert_preset,
	);

	// Initialisierung: metric_alert_levels → Legacy alert_preset.
	// Im Onboarding-Zustand leere Startbelegung (Tabelle wird ohnehin ausgeblendet).
	let currentLevels = $state<Record<AlertMetric, SensLevel>>(
		trip.display_config?.metric_alert_levels
			? (trip.display_config.metric_alert_levels as Record<AlertMetric, SensLevel>)
			: trip.display_config?.alert_preset
				? migrateAlertPreset(
						trip.display_config.alert_preset,
						ALERTABLE_METRICS as AlertMetric[],
					)
				: ({} as Record<AlertMetric, SensLevel>),
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

	// AC-5: Nutzer übernimmt bewusst die Standard-Konfiguration; verlässt Onboarding.
	function activateStandard() {
		currentLevels = migrateAlertPreset('standard', displayMetrics as AlertMetric[]);
		isOnboarding = false;
		saveController?.schedule(buildSaveFn());
	}
</script>

<div class="alerts-tab" data-testid="alerts-tab">
	<Eyebrow>Alerts · Sofort-Meldung</Eyebrow>
	<h2 class="alerts-h2" data-testid="alerts-tab-heading">Sofort-Meldung zwischen den Briefings</h2>

	{#if isOnboarding}
		<div class="onboarding" data-testid="alerts-onboarding">
			<p>Keine Alerts konfiguriert.</p>
			<button type="button" onclick={activateStandard} data-testid="alerts-activate-standard">
				Standard-Konfiguration übernehmen
			</button>
		</div>
	{:else}
		<AlertMetricLevelTable
			activeMetrics={displayMetrics as AlertMetric[]}
			levels={currentLevels}
			{onLevelChange}
		/>
	{/if}

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

	.onboarding {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 12px;
		padding: 24px;
		background: var(--g-card, #ffffff);
		border: 1px solid var(--g-line, #e2ddd2);
		border-radius: 12px;
	}

	.onboarding p {
		margin: 0;
		color: var(--g-ink);
		font-size: 16px;
	}

	.onboarding button {
		padding: 10px 18px;
		min-height: 44px;
		border: 1px solid var(--g-line, #c9c2b4);
		border-radius: 8px;
		background: var(--g-accent, #2f6f4f);
		color: #ffffff;
		font-size: 15px;
		font-weight: 600;
		cursor: pointer;
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
