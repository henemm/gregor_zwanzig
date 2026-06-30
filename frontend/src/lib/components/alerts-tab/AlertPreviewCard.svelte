<script lang="ts">
	// Issue #182 — Alert-Konfigurator: Alert-Vorschau (Email).
	// Issue #586 — h4 entfernt, Card-Styling nach JSX.

	import { api } from '$lib/api';
	import type { Trip, AlertRule } from '$lib/types';
	import { buildAlertPreviewPayload } from './alertPreviewHelpers';

	let { trip, alertRules }: { trip: Trip; alertRules: AlertRule[] } = $props();

	let subject = $state('');
	let emailHtml = $state('');
	let telegram = $state('');
	let sms = $state('');
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
		subject = '';
		emailHtml = '';
		telegram = '';
		sms = '';
		try {
			const payload = buildAlertPreviewPayload(alertRules, trip.stages);
			const result = await api.post<{
				subject: string;
				email_html: string;
				email_plain: string;
				telegram: string;
				sms: string;
			}>(`/api/trips/${trip.id}/alert-preview`, payload);
			subject = result.subject;
			emailHtml = result.email_html;
			telegram = result.telegram;
			sms = result.sms;
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
		<!-- Issue #850: Link direkt auf Inhalt-Tab -->
		<p class="empty" data-testid="alert-preview-no-metrics">
			Keine alert-fähigen Wetter-Metriken aktiv. Aktiviere zuerst
			Wetter-Metriken (z.B. Windböen, Temperatur) im Tab
			<a href="?tab=weather" data-testid="alert-preview-no-metrics-link"><strong>Wetter-Metriken</strong></a>.
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

	{#if emailHtml !== '' || subject !== ''}
		<div class="channel-section">
			<p class="channel-label" data-testid="alert-preview-subject">{subject}</p>
			<iframe
				data-testid="alert-preview-iframe"
				srcdoc={emailHtml}
				sandbox="allow-same-origin"
				title="Alert-Vorschau E-Mail"
			></iframe>
			<pre class="channel-text" data-testid="alert-preview-telegram">{telegram}</pre>
			<div class="sms-block" data-testid="alert-preview-sms">
				<pre class="sms-text">{sms}</pre>
				<span class="sms-count">{sms.length}/140</span>
			</div>
		</div>
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
	.channel-section {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.channel-label {
		margin: 0;
		font-weight: 600;
		font-size: 0.875rem;
	}
	.channel-text {
		margin: 0;
		font-size: 0.8125rem;
		white-space: pre-wrap;
		background: var(--g-surface-2, #f5f5f5);
		padding: 0.5rem;
		border-radius: 0.25rem;
	}
	.sms-block {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.sms-text {
		margin: 0;
		font-family: monospace;
		font-size: 0.8125rem;
		white-space: pre-wrap;
		background: var(--g-surface-2, #f5f5f5);
		padding: 0.5rem;
		border-radius: 0.25rem;
	}
	.sms-count {
		font-size: 0.75rem;
		color: var(--g-ink-muted);
		text-align: right;
	}
</style>
