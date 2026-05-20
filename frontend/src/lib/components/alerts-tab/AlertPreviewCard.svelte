<script lang="ts">
	// Issue #182 — Alert-Konfigurator: Alert-Vorschau (Email).
	// Spec: docs/specs/modules/issue_182_alert_preview.md
	//
	// Rendert eine Vorschau der Alert-E-Mail in einem sandgeboxten iframe.
	// Nutzt buildAlertPreviewPayload() + POST /api/trips/{id}/alert-preview.
	// Kein Speichern, kein Versand — reine Vorschau auf Basis der lokalen alertRules.

	import { api } from '$lib/api';
	import type { Trip, AlertRule } from '$lib/types';
	import { buildAlertPreviewPayload } from './alertPreviewHelpers';

	let { trip, alertRules }: { trip: Trip; alertRules: AlertRule[] } = $props();

	let html = $state('');
	let loading = $state(false);
	let error = $state<string | null>(null);

	const enabledRules = $derived(alertRules.filter((r) => r.enabled));

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
	<h4 class="card-title">Alert-Vorschau</h4>

	{#if enabledRules.length === 0}
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
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md, 0.5rem);
		background: var(--g-surface-1, #fff);
		box-shadow: var(--g-elev-1, 0 1px 2px rgba(0, 0, 0, 0.05));
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.card-title {
		font-size: 0.875rem;
		font-weight: 600;
		margin: 0;
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
