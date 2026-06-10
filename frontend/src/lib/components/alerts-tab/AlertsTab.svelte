<script lang="ts">
	// Issue #638 — AlertsTab: Karten-Modell (JSX TE2_AlertsTab 1:1).
	// Ersetzt Tabellen-Paradigma (AlertMetricTable + Modus-Picker) durch AlertCard pro Regel.
	// Keine Severity-Auswahl mehr. Kanal-Chips pro Alert.

	import AlertCard from './AlertCard.svelte';
	import AlertCooldownCard from './AlertCooldownCard.svelte';
	import AlertQuietHoursCard from './AlertQuietHoursCard.svelte';
	import AlertPreviewCard from './AlertPreviewCard.svelte';
	import { Eyebrow } from '$lib/components/atoms';
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

	// Active briefing channels from report_config → Vorbelegung für Kanal-Chips.
	// Svelte 5: $derived.by für Multi-Statement-Derivations (nicht $derived(() => ...)).
	const activeChannels = $derived.by(() => {
		const rc = trip.report_config;
		const chs: string[] = [];
		if (rc?.send_email) chs.push('email');
		if (rc?.send_telegram) chs.push('telegram');
		if (rc?.send_sms) chs.push('sms');
		return chs;
	});

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
	<!-- Header (JSX TE2_AlertsTab) -->
	<Eyebrow>Alerts</Eyebrow>
	<h2 class="alerts-h2" data-testid="alerts-tab-heading">Sofort-Meldung bei kritischen Werten</h2>

	<!-- Infozeile (JSX) -->
	<div class="info-row" data-testid="alerts-channel-info">
		<span class="info-dot"></span>
		Alert-Kanäle werden aus den <strong>Wetter-Metriken</strong>-Einstellungen übernommen.
	</div>

	<!-- Karten-Liste -->
	<div class="cards-list" data-testid="alert-cards-list">
		{#each alertRules as rule, idx}
			<AlertCard
				bind:rule={alertRules[idx]}
				activeChannels={activeChannels}
			/>
		{/each}
	</div>

	<!-- Info: Alert-Regeln werden automatisch aus Metriken abgeleitet (Issue #701) -->
	<p class="alerts-auto-info">Alert-Regeln werden automatisch aus den aktiven Wetter-Metriken abgeleitet.</p>

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

	.info-row {
		padding: 9px 14px;
		background: var(--g-card-alt);
		border: 1px solid var(--g-rule-soft);
		border-radius: var(--g-r-2);
		font-size: 12.5px;
		color: var(--g-ink-2);
		margin-bottom: 20px;
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.info-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--g-info);
		flex-shrink: 0;
	}

	.cards-list {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.alerts-auto-info {
		font-size: 0.85rem;
		color: var(--g-ink-3, #666);
		margin: 0.5rem 0 1rem;
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
