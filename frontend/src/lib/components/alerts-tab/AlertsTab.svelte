<script lang="ts">
	// Issue #180 — Container fuer den Alerts-Tab im Trip-Detail.
	// Spec: docs/specs/modules/issue_180_alert_metric_table.md §AlertsTab.svelte.
	//
	// Aufgaben:
	//  - Lokaler State fuer alertRules, cooldown, quiet_from, quiet_to
	//  - Speichern via PUT /api/trips/{id}
	//  - Inline-Erfolg (3s Flash) + Inline-Fehler

	import AlertMetricTable from './AlertMetricTable.svelte';
	import AlertCooldownCard from './AlertCooldownCard.svelte';
	import AlertQuietHoursCard from './AlertQuietHoursCard.svelte';
	import AlertPreviewCard from './AlertPreviewCard.svelte';
	import { api } from '$lib/api';
	import type { Trip, AlertRule } from '$lib/types';

	let { trip }: { trip: Trip } = $props();

	let alertRules = $state<AlertRule[]>(trip.alert_rules ?? []);
	let cooldownMinutes = $state<number | undefined>(trip.alert_cooldown_minutes ?? undefined);
	let quietFrom = $state<string | undefined>(trip.alert_quiet_from ?? undefined);
	let quietTo = $state<string | undefined>(trip.alert_quiet_to ?? undefined);

	let saving = $state(false);
	let saveSuccess = $state(false);
	let saveError = $state<string | null>(null);

	async function save() {
		saving = true;
		saveSuccess = false;
		saveError = null;
		try {
			await api.put(`/api/trips/${trip.id}`, {
				alert_rules: alertRules,
				alert_cooldown_minutes: cooldownMinutes ?? null,
				alert_quiet_from: quietFrom || null,
				alert_quiet_to: quietTo || null
			});
			saveSuccess = true;
			setTimeout(() => {
				saveSuccess = false;
			}, 3000);
		} catch (e: unknown) {
			const msg =
				e && typeof e === 'object' && 'error' in e
					? String((e as { error: unknown }).error)
					: e instanceof Error
						? e.message
						: 'Speichern fehlgeschlagen';
			saveError = msg;
		} finally {
			saving = false;
		}
	}
</script>

<div class="alerts-tab" data-testid="alerts-tab">
	<AlertMetricTable bind:alert_rules={alertRules} />

	<div class="cards-row">
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
</div>

<style>
	.alerts-tab {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: 1rem;
	}
	.cards-row {
		display: grid;
		gap: 1rem;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
	}
	@media (max-width: 720px) {
		.cards-row {
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
		border: 1px solid var(--g-primary, #2563eb);
		background: var(--g-primary, #2563eb);
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
</style>
