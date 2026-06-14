<script lang="ts">
	// Issue #182 — Alert-Konfigurator: Alert-Vorschau (Email).
	// Issue #586 — h4 entfernt, Card-Styling nach JSX.

	import { api } from '$lib/api';
	import type { Trip, AlertRule } from '$lib/types';
	import { buildAlertPreviewPayload } from './alertPreviewHelpers';

	let { trip, alertRules }: { trip: Trip; alertRules: AlertRule[] } = $props();

	let html = $state('');
	let loading = $state(false);
	let error = $state<string | null>(null);

	const enabledRules = $derived(alertRules.filter((r) => r.enabled));

	// Issue #809: Nach Self-Heal hat ein Trip ohne alert-fähige Metriken
	// alert_rules=[] (kein Ergebnis aus SyncAlertRules).
	// Leere alert_rules = keine alert-fähigen Metriken aktiv → ehrlicher Hinweis.
	const hasNoAlertableMetrics = $derived(alertRules.length === 0);

	async function loadPreview() {
		loading = true;
		error = null;
		html = '';
		try {
			const payload = buildAlertPreviewPayload(alertRules, trip.stages);
			const result = await api.post<{ html: string; plain: string }>(
				`/api/trips/${trip.id}/alert-preview`,
				payload
			);
			html = result.html;
		} catch (e: unknown) {
			error =
				e && typeof e === 'object' && 'error' in e
					? String((e as { error: unknown }).error)
					: e instanceof Error
						? e.message
						: 'Vorschau konnte nicht geladen werden';
		} finally {
			loading = false;
		}
	}
</script>

<div class="preview-card" data-testid="alert-preview-card">
	{#if hasNoAlertableMetrics}
		<!-- Issue #809: Kein alert_rules nach Self-Heal = keine alert-fähigen Metriken -->
		<p class="empty" data-testid="alert-preview-no-metrics">
			Keine alert-fähigen Wetter-Metriken aktiv. Aktiviere zuerst
			Wetter-Metriken (z.B. Windböen, Temperatur) im Tab
			<strong>Wetter-Metriken</strong>.
		</p>
	{:else if enabledRules.length === 0}
		<p class="empty" data-testid="alert-preview-empty">
			Aktiviere mindestens eine Alert-Regel, um die Vorschau zu laden.
		</p>
		<button type="button" class="btn" data-testid="alert-preview-load-btn" disabled>
			Vorschau laden
		</button>
	{:else}
		<button
			type="button"
			class="btn"
			data-testid="alert-preview-load-btn"
			disabled={loading}
			onclick={loadPreview}
		>
			{loading ? 'Lade…' : 'Vorschau laden'}
		</button>
	{/if}

	{#if html !== ''}
		<iframe
			data-testid="alert-preview-iframe"
			srcdoc={html}
			sandbox="allow-same-origin"
			title="Alert-Vorschau"
		></iframe>
	{/if}

	{#if error !== null}
		<p class="error" data-testid="alert-preview-error">{error}</p>
	{/if}
</div>

<style>
	.preview-card {
		padding: 1rem;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-radius-md, 0.5rem);
		background: var(--g-surface-1, #fff);
		max-width: 720px;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.btn {
		align-self: flex-start;
		min-height: 36px;
		padding: 0.5rem 1rem;
		border-radius: 0.375rem;
		border: 1px solid var(--g-ink);
		background: var(--g-ink);
		color: #fff;
		font-size: 0.875rem;
		cursor: pointer;
	}
	.btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.empty {
		margin: 0;
		font-size: 0.8125rem;
		color: var(--g-ink-muted);
	}
	.error {
		margin: 0;
		font-size: 0.875rem;
		color: var(--g-danger, #dc2626);
	}
	iframe {
		width: 100%;
		min-height: 350px;
		border: 0;
	}
</style>
