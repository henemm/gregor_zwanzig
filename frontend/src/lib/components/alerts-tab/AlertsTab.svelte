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
	import { normalizeAlertMetric } from '$lib/utils/alertMetricLabels';
	import { deriveAlertMode } from './alertMetricTable.js';
	import type { Trip, AlertRule } from '$lib/types';

	let { trip }: { trip: Trip } = $props();

	// Issue #414 — Mobile Modus-Picker.
	type AlertMode = 'absolute' | 'delta' | 'both';
	const MODES: { id: AlertMode; eyebrow: string; title: string; desc: string; example: string }[] = [
		{ id: 'delta',    eyebrow: 'REAKTIV',   title: 'Δ-Änderung',  desc: 'Wert ändert sich seit letztem Report stark', example: 'z.B. Wind +20 km/h' },
		{ id: 'absolute', eyebrow: 'ABSOLUT',   title: 'Schwellwert', desc: 'Wert über-/unterschreitet eine Grenze',       example: 'z.B. Wind > 50 km/h' },
		{ id: 'both',     eyebrow: 'EMPFOHLEN', title: 'Beides',      desc: 'Δ und absolut kombiniert',                   example: 'Standard für aktive Trips' },
	];
	let selectedMode = $state<AlertMode>(deriveAlertMode(trip.alert_rules ?? []));

	let alertRules = $state<AlertRule[]>((trip.alert_rules ?? []).map(r => ({
		...r,
		metric: normalizeAlertMetric(r.metric) ?? r.metric,
	})));
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
	<div class="mobile-header" data-testid="alerts-tab-mobile-header">
		<h1 class="mobile-h1">Wann soll ein Alert ausgelöst werden?</h1>
		<p class="mobile-subtext">Alerts kommen zwischen Morgen- und Abend-Briefing. Wähle den Modus.</p>
	</div>

	<div class="mode-picker" role="radiogroup" aria-label="Auslöse-Modus" data-testid="mode-picker">
		{#each MODES as m}
			<button
				type="button"
				role="radio"
				aria-checked={selectedMode === m.id}
				class="mode-card"
				class:active={selectedMode === m.id}
				onclick={() => { selectedMode = m.id; }}
				data-testid="mode-card-{m.id}"
			>
				<span class="mode-eyebrow">{m.eyebrow}</span>
				<span class="mode-title">{m.title}</span>
				<span class="mode-desc">{m.desc}</span>
				<span class="mode-example">{m.example}</span>
			</button>
		{/each}
	</div>

	<p class="section-heading" data-testid="metrics-section-heading">METRIKEN &amp; SCHWELLEN</p>

	<AlertMetricTable bind:alert_rules={alertRules} requestedMode={selectedMode} />

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

	<div class="mobile-footer" data-testid="alerts-tab-mobile-footer">
		<button type="button" class="btn-ghost" disabled data-testid="alerts-tab-test-alert">
			Test-Alert senden
		</button>
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
		color: var(--g-good, #16a34a);
		font-size: 0.875rem;
	}
	.error-msg {
		color: var(--g-danger, #dc2626);
		font-size: 0.875rem;
	}

	/* F002 — Sektions-Heading nur auf Mobile sichtbar. */
	.section-heading {
		display: none;
	}
	@media (max-width: 899px) {
		.section-heading {
			display: block;
			font-size: 0.65rem;
			text-transform: uppercase;
			letter-spacing: 0.1em;
			color: var(--g-ink-muted);
			margin: var(--g-s-3) 0 var(--g-s-1) 0;
		}
	}

	/* Issue #414 — Mobile-only Header, Modus-Picker, fixierter Footer. */
	.mobile-header,
	.mode-picker,
	.mobile-footer {
		display: none;
	}

	@media (max-width: 899px) {
		.alerts-tab {
			padding-bottom: 120px;
		}
		.mobile-header {
			display: block;
		}
		.mobile-h1 {
			font-size: 1.25rem;
			font-weight: 700;
			letter-spacing: -0.025em;
			color: var(--g-ink);
			margin: 0 0 var(--g-s-2) 0;
		}
		.mobile-subtext {
			font-size: 0.875rem;
			color: var(--g-ink-muted);
			margin: 0;
		}
		.mode-picker {
			display: flex;
			gap: var(--g-s-2);
		}
		.mode-card {
			flex: 1;
			display: flex;
			flex-direction: column;
			gap: 0.2rem;
			padding: var(--g-s-3);
			border: 1px solid var(--g-ink-faint);
			border-radius: var(--g-radius-md, 0.5rem);
			background: var(--g-surface-1, #fff);
			text-align: left;
			cursor: pointer;
			font: inherit;
			color: inherit;
		}
		.mode-card.active {
			border-color: var(--g-accent);
			box-shadow: 0 0 0 1px var(--g-accent) inset;
		}
		.mode-eyebrow {
			font-size: 0.6rem;
			text-transform: uppercase;
			letter-spacing: 0.08em;
			color: var(--g-ink-muted);
		}
		.mode-title {
			font-weight: 600;
			font-size: 0.875rem;
		}
		.mode-desc {
			font-size: 0.75rem;
			color: var(--g-ink-muted);
		}
		.mode-example {
			font-size: 0.7rem;
			color: var(--g-ink-muted);
			font-family: var(--g-font-data, monospace);
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
		.btn-ghost {
			min-height: 40px;
			padding: 0.5rem 1rem;
			border-radius: 0.375rem;
			border: 1px solid var(--g-ink-faint);
			background: transparent;
			color: var(--g-ink-muted);
			font-size: 0.875rem;
			cursor: not-allowed;
			opacity: 0.6;
		}
	}
</style>
