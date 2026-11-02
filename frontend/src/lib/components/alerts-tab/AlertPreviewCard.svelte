<script lang="ts">
	// Issue #182 — Alert-Konfigurator: Alert-Vorschau (Email).
	// Issue #586 — h4 entfernt, Card-Styling nach JSX.
	// Issue #2283 S5: kind-neutral — derselbe Baustein im Trip (Segmente) und im
	// Ortsvergleich (Orte); Abruf ueber POST /api/briefings/{id}/alert-preview?kind=….

	import { alarmVorschau } from '$lib/api';
	import type { AlertRule, Stage } from '$lib/types';
	import { buildAlertPreviewBody, vorschauFehlerText } from './alertPreviewHelpers';
	import { t } from '$lib/i18n';
	import { textTeile } from '$lib/i18n/textTeile';

	interface Props {
		kind: 'route' | 'vergleich';
		/** Trip- bzw. Vergleichs-ID; leer (Anlege-Seite) ⇒ kein Abruf moeglich. */
		id: string;
		alertRules: AlertRule[];
		stages?: Stage[];
		locationIds?: string[];
	}
	let { kind, id, alertRules, stages = [], locationIds = [] }: Props = $props();

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
			const payload = buildAlertPreviewBody(kind, { rules: alertRules, stages, locationIds });
			// #2361: eigenes Budget 40 s (Go-Proxy ca. 30 s), s. `alarmVorschau` in api.ts.
			const result = await alarmVorschau<{
				subject: string;
				email_html: string;
				email_plain: string;
				telegram: string;
				sms: string;
			}>(kind, id, payload);
			subject = result.subject;
			emailHtml = result.email_html;
			telegram = result.telegram;
			sms = result.sms;
		} catch (e: unknown) {
			error = vorschauFehlerText(e);
		} finally {
			loading = false;
		}
	}
</script>

<div class="preview-card" data-testid="alert-preview-card" data-kind={kind}>
	{#if hasNoAlertableMetrics}
		<!-- Issue #809: Kein alert_rules nach Self-Heal = keine alert-fähigen Metriken -->
		<!-- Issue #850: Link direkt auf Inhalt-Tab -->
		<p class="empty" data-testid="alert-preview-no-metrics">
			{#each textTeile($t('alarme.vorschau.keine_metriken')) as teil}{#if teil.platzhalter === 'link'}<a href="?tab=wetter-metriken" data-testid="alert-preview-no-metrics-link"><strong>{$t('alarme.vorschau.reiter_wetter_metriken')}</strong></a>{:else}{teil.text}{/if}{/each}
		</p>
	{:else if id === ''}
		<!-- Issue #2283 S5: Anlege-Seite — es gibt noch keinen gespeicherten Eintrag. -->
		<p class="empty" data-testid="alert-preview-unsaved">
			{$t('alarme.vorschau.nach_speichern')}
		</p>
	{:else if kind === 'vergleich' && locationIds.length === 0}
		<!-- Issue #2283 (F006b): ohne Orte gibt es nichts vorzuschauen — kein Abruf
		     (das Backend antwortete sonst 422), analog zum „0 Orte"-Hinweis der Vorschau. -->
		<p class="empty" data-testid="alert-preview-no-locations">
			{#each textTeile($t('alarme.vorschau.keine_orte')) as teil}{#if teil.platzhalter === 'reiter'}<strong>{$t('alarme.vorschau.reiter_orte')}</strong>{:else}{teil.text}{/if}{/each}
		</p>
	{:else if enabledRules.length === 0}
		<p class="empty" data-testid="alert-preview-empty">
			{$t('alarme.vorschau.regel_aktivieren')}
		</p>
		<button type="button" class="btn" data-testid="alert-preview-load-btn" disabled>
			{$t('alarme.vorschau.laden')}
		</button>
	{:else}
		<button
			type="button"
			class="btn"
			data-testid="alert-preview-load-btn"
			disabled={loading}
			onclick={loadPreview}
		>
			{loading ? $t('alarme.vorschau.lade') : $t('alarme.vorschau.laden')}
		</button>
	{/if}

	{#if emailHtml !== '' || subject !== ''}
		<div class="channel-section">
			<p class="channel-label" data-testid="alert-preview-subject">{subject}</p>
			<iframe
				data-testid="alert-preview-iframe"
				srcdoc={emailHtml}
				sandbox="allow-same-origin"
				title={$t('alarme.vorschau.iframe_titel')}
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
