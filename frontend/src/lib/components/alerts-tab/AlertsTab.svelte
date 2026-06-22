<script lang="ts">
	// Issue #846 — AlertsTab: Preset-Dropdown ersetzt Karten-Modell (Epic #813 Slice 3).
	// Spec: docs/specs/modules/issue_846_alert_preset.md

	import AlertCooldownCard from './AlertCooldownCard.svelte';
	import AlertQuietHoursCard from './AlertQuietHoursCard.svelte';
	import AlertPreviewCard from './AlertPreviewCard.svelte';
	import AlertPresetSelector from './AlertPresetSelector.svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import { api } from '$lib/api';
	import type { Trip, AlertRule } from '$lib/types';
	import type { PresetName } from './alertMetricTable.ts';

	let { trip }: { trip: Trip } = $props();

	// Issue #846: Preset-Name aus display_config laden, Default "standard"
	let alertPreset = $state<PresetName>(
		(trip.display_config?.alert_preset as PresetName) ?? 'standard'
	);
	// alert_rules für AlertPreviewCard weiterhin laden (Backward Compat)
	let alertRules = $state<AlertRule[]>(trip.alert_rules ?? []);
	let cooldownMinutes = $state<number | undefined>(trip.alert_cooldown_minutes ?? undefined);
	let quietFrom = $state<string | undefined>(trip.alert_quiet_from ?? undefined);
	let quietTo = $state<string | undefined>(trip.alert_quiet_to ?? undefined);

	let saving = $state(false);
	let saveSuccess = $state(false);
	let saveError = $state<string | null>(null);

	function handlePresetChange(preset: PresetName) {
		alertPreset = preset;
	}

	async function save() {
		saving = true;
		saveSuccess = false;
		saveError = null;
		try {
			// Issue #846: Preset in display_config persistieren
			const existingDisplayConfig = trip.display_config ?? {};
			await api.put(`/api/trips/${trip.id}`, {
				display_config: {
					...existingDisplayConfig,
					alert_preset: alertPreset,
				},
				alert_cooldown_minutes: cooldownMinutes ?? null,
				alert_quiet_from: quietFrom || null,
				alert_quiet_to: quietTo || null
			});
			saveSuccess = true;
			setTimeout(() => { saveSuccess = false; }, 3000);
		} catch (e: unknown) {
			const msg =
				e && typeof e === 'object' && 'error' in e
					? String((e as { error: unknown }).error)
					: e instanceof Error ? e.message : 'Speichern fehlgeschlagen';
			saveError = msg;
		} finally {
			saving = false;
		}
	}
</script>

<div class="alerts-tab" data-testid="alerts-tab">
	<!-- Header -->
	<Eyebrow>Alerts</Eyebrow>
	<h2 class="alerts-h2" data-testid="alerts-tab-heading">Sofort-Meldung bei kritischen Werten</h2>

	<!-- Preset-Selector (Issue #846) -->
	<div class="preset-section">
		<label class="preset-label">Alert-Empfindlichkeit</label>
		<AlertPresetSelector bind:value={alertPreset} onchange={handlePresetChange} />
	</div>

	<div class="extra-cards">
		<AlertCooldownCard bind:cooldown_minutes={cooldownMinutes} />
		<AlertQuietHoursCard bind:quiet_from={quietFrom} bind:quiet_to={quietTo} />
	</div>

	<AlertPreviewCard {trip} {alertRules} />

	<div class="actions">
		<button
			type="button"
			class="btn-primary"
			data-testid="alerts-tab-save"
			disabled={saving}
			onclick={save}
		>{saving ? 'Speichere…' : 'Speichern'}</button>

		{#if saveSuccess}
			<span class="success-msg" data-testid="alerts-tab-save-success">Gespeichert.</span>
		{/if}
		{#if saveError}
			<span class="error-msg" data-testid="alerts-tab-save-error">{saveError}</span>
		{/if}
	</div>

	<!-- Mobile footer -->
	<div class="mobile-footer" data-testid="alerts-tab-mobile-footer">
		<button
			type="button"
			class="btn-primary"
			data-testid="alerts-tab-save"
			disabled={saving}
			onclick={save}
		>{saving ? 'Speichere…' : 'Speichern'}</button>

		{#if saveSuccess}
			<span class="success-msg" data-testid="alerts-tab-save-success">Gespeichert.</span>
		{/if}
		{#if saveError}
			<span class="error-msg" data-testid="alerts-tab-save-error">{saveError}</span>
		{/if}
	</div>
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

	.preset-section {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 16px;
		background: var(--g-card, #fff);
		border: 1px solid var(--g-rule, #e5e5e5);
		border-radius: var(--g-r-2, 6px);
	}

	.preset-label {
		font-size: 12.5px;
		font-weight: 600;
		color: var(--g-ink-2, #555);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.extra-cards {
		display: grid;
		gap: 1rem;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
	}
	@media (max-width: 720px) {
		.extra-cards {
			grid-template-columns: 1fr;
		}
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.btn-primary {
		min-height: 40px;
		padding: 0.5rem 1rem;
		border-radius: 0.375rem;
		border: 1px solid var(--g-ink);
		background: var(--g-ink);
		color: #fff;
		font-size: 0.875rem;
		cursor: pointer;
	}
	.btn-primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.success-msg {
		color: var(--g-success, #16a34a);
		font-size: 0.875rem;
	}
	.error-msg {
		color: var(--g-danger, #dc2626);
		font-size: 0.875rem;
	}

	.mobile-footer {
		display: none;
	}

	@media (max-width: 899px) {
		.alerts-tab {
			padding: 1rem;
			padding-bottom: 120px;
			max-width: 100%;
		}
		.mobile-footer {
			display: flex;
			align-items: center;
			gap: var(--g-s-3);
			position: fixed;
			bottom: 0;
			left: 0;
			right: 0;
			z-index: 55;
			padding: var(--g-s-3) var(--g-s-4);
			padding-bottom: calc(var(--g-s-4) + env(safe-area-inset-bottom, 0px));
			background: var(--g-paper);
			border-top: 1px solid var(--g-ink-faint);
		}
		.actions {
			display: none;
		}
	}
</style>
