<script lang="ts">
	// Issue #2283 (Epic #2345 P3) — EIN geteilter Vorschau-Reiter fuer Trip-Hub
	// (context="route") und Ortsvergleich-Hub (context="vergleich").
	// Spec: docs/specs/modules/shared_preview_tab.md (AC-8 bis AC-15).
	//
	// Gleiche Anordnung in beiden Hubs: Kanalumschalter E-Mail · SMS · Telegram,
	// Premium-SMS-Hinweis, SMS im Telefonrahmen, E-Mail Desktop/Mobil, Telegram
	// als Chat-Blase. Der Reiter zeigt AUSSCHLIESSLICH den Zustand des Laders
	// (shared/previewLoader.ts): genau EIN Abruf beim Oeffnen (onMount), keiner
	// beim Kanal-/Ansichtswechsel. Morgen/Abend + Demo nur, wo der Lader
	// Trip-Optionen kennt. Kein Sende-Knopf — Senden nur im Hub-Kopf (#2278).
	import { onMount, untrack } from 'svelte';
	import type { ComparePreset } from '$lib/types';
	import CompareChannelSwitch from '$lib/components/molecules/CompareChannelSwitch.svelte';
	import CompareChatBubble from '$lib/components/molecules/CompareChatBubble.svelte';
	import EmailIframe from '$lib/components/preview/EmailIframe.svelte';
	import SmsPhoneFrame from '$lib/components/preview/SmsPhoneFrame.svelte';
	import type { ReportType } from '$lib/components/preview/previewHelpers';
	import { premiumSmsPreviewNote } from '$lib/components/compare/subscriptionHelpers';
	import { SMS_COMPARE_CHAR_LIMIT } from './layout-tab/ltChannels';
	import {
		createPreviewLoader,
		hatTripOptionen,
		type EmailView,
		type PreviewChannel,
		type PreviewLoader
	} from './previewLoader';

	interface Props {
		context: 'route' | 'vergleich';
		id: string;
		loader?: PreviewLoader;
		/** Premium-SMS eingeschaltet → Hinweis beim SMS-Kanal (ADR-0049, #2229). */
		premiumSms?: boolean;
		/** Konfigurierte Kanaele (Kleinschreibung); fehlt die Liste, gelten alle als konfiguriert. */
		configuredChannels?: string[];
	}
	let { context, id, loader: loaderProp, premiumSms = false, configuredChannels }: Props = $props();

	// Der Lader wird EINMAL angelegt — nie abgeleitet, sonst loeste jede
	// Prop-Aenderung im Hub einen neuen Abruf aus.
	const loader = untrack(() => loaderProp ?? createPreviewLoader({ kind: context, id }));
	let s = $state(loader.getState());
	onMount(() => {
		// Zwischen Instanz-Anlage (s = getState()) und onMount aendert sich der
		// Lader nicht (gleicher synchroner Durchlauf) — subscribe genuegt.
		const ab = loader.subscribe((neu) => (s = neu));
		void loader.load();
		return ab;
	});

	const tripOptionen = hatTripOptionen(loader.kind);
	const smsLimit = tripOptionen ? 160 : SMS_COMPARE_CHAR_LIMIT;
	const kanaele = $derived(configuredChannels ?? ['email', 'sms', 'telegram']);
	const note = $derived(premiumSmsPreviewNote({ send_premium_sms: premiumSms } as ComparePreset, s.channel));
	const VIEWS: [EmailView, string][] = [['desktop', 'Desktop'], ['mobile', 'Mobil']];
</script>

<div class="preview-tab" data-testid="preview-tab" data-context={context}>
	{#if tripOptionen}
		{#if s.options.demo}
			<div class="demo-banner" role="status" data-testid="preview-demo-banner">
				<span>Vorschau mit Beispieldaten.</span>
				<button
					type="button"
					class="demo-banner-action"
					onclick={() => void loader.setOptions({ demo: false })}
					data-testid="preview-demo-disable"
				>
					Echte Wetterdaten laden
				</button>
			</div>
		{/if}
		<div class="preview-controls" data-testid="preview-controls">
			{#each [['morning', 'Morgen'], ['evening', 'Abend']] as [wert, label] (wert)}
				<label>
					<input
						type="radio"
						name="preview-type-{id}"
						value={wert}
						checked={s.options.type === wert}
						onchange={() => void loader.setOptions({ type: wert as ReportType })}
					/>
					{label}
				</label>
			{/each}
		</div>
	{/if}

	<div class="preview-switches">
		<CompareChannelSwitch
			value={s.channel}
			onChange={(c: string) => loader.setChannel(c as PreviewChannel)}
			channels={kanaele}
			{note}
		/>
		{#if s.channel === 'email'}
			<div class="view-switch">
				{#each VIEWS as [v, label] (v)}
					<button
						type="button"
						class:on={s.emailView === v}
						onclick={() => loader.setEmailView(v)}
						data-testid="preview-email-view-{v}"
					>
						{label}
					</button>
				{/each}
			</div>
		{/if}
		{#if !kanaele.includes(s.channel)}
			<span class="mono hint" data-testid="preview-channel-not-configured">Kanal nicht konfiguriert · Beispiel-Render</span>
		{/if}
	</div>

	{#if s.status === 'error'}
		<p class="state-msg error" data-testid="preview-error">{s.error}</p>
	{:else if s.status !== 'ready' || !s.data}
		<p class="state-msg" data-testid="preview-loading">Vorschau wird geladen…</p>
	{:else if s.channel === 'email'}
		<EmailIframe html={s.data.email_html} view={s.emailView} />
	{:else if s.channel === 'sms'}
		<SmsPhoneFrame text={s.data.sms.text} charCount={s.data.sms.char_count} limit={smsLimit} tripToken={tripOptionen} />
	{:else}
		<div class="telegram-blasen" data-testid="preview-telegram">
			<!-- Mehrere Telegram-Nachrichten (bubbles) = mehrere Blasen, wie im Versand. -->
			{#each s.data.telegram.bubbles?.length ? s.data.telegram.bubbles : [s.data.telegram.body] as blase, i (i)}
				<CompareChatBubble text={blase} />
			{/each}
		</div>
	{/if}
</div>

<style>
	.preview-tab {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: 1rem 0;
	}
	.demo-banner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.625rem 0.875rem;
		background: var(--g-warning-soft, #fef3c7);
		color: var(--g-ink, #1a1a18);
		border: 1px solid var(--g-warning, #f59e0b);
		border-radius: var(--g-r-2, 0.5rem);
		font-size: 0.875rem;
	}
	.demo-banner-action {
		flex-shrink: 0;
		padding: 0.375rem 0.75rem;
		background: var(--g-ink, #1a1a18);
		color: var(--g-paper, #f6f4ee);
		border: 0;
		border-radius: var(--g-r-1, 0.375rem);
		font-size: 0.8125rem;
		font-weight: 500;
		cursor: pointer;
	}
	.preview-controls {
		display: flex;
		gap: 1.25rem;
		font-size: 0.875rem;
		color: var(--g-ink, #1a1a18);
	}
	.preview-controls label {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		cursor: pointer;
	}
	.preview-switches {
		display: flex;
		align-items: center;
		gap: 16px;
		flex-wrap: wrap;
	}
	.view-switch {
		display: inline-flex;
		background: var(--g-paper-deep);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		padding: 3px;
		gap: 2px;
	}
	.view-switch button {
		padding: 7px 13px;
		border: none;
		cursor: pointer;
		border-radius: 4px;
		font-size: 12.5px;
		font-family: var(--g-font-sans);
		font-weight: 500;
		background: transparent;
		color: var(--g-ink-3);
	}
	.view-switch button.on {
		font-weight: 600;
		background: var(--g-card);
		box-shadow: var(--g-shadow-1);
		color: var(--g-ink);
	}
	.telegram-blasen {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.hint {
		font-size: 11px;
		color: var(--g-ink-3);
		letter-spacing: 0.04em;
	}
	.state-msg {
		margin: 0;
		font-size: 0.875rem;
		color: var(--g-ink-3);
	}
	.state-msg.error {
		color: var(--g-danger, #dc2626);
	}
</style>
