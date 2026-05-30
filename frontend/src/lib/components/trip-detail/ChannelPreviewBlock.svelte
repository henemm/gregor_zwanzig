<script lang="ts">
	// Issue #365 — 4-Kanal-Live-Vorschau (Email/Telegram/Signal/SMS). Zeigt beim
	// Editieren sofort, welche Spalten je Kanal in die Tabelle wandern und was in
	// die Detail-Zeile rutscht. Reagiert reaktiv auf Bucket-Änderungen.
	// Auf schmalen Viewports (<900px): Kanal-Dropdown + 1 Karte statt 4er-Grid.
	// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx (Z. 555-650)
	import * as Card from '$lib/components/ui/card/index.js';
	import { Eyebrow } from '$lib/components/atoms';
	import { Select } from '$lib/components/ui/select';
	import { CHANNEL_COL_BUDGET, type MetricEntry } from './metricsEditor.ts';
	import ChannelPreviewCard from './ChannelPreviewCard.svelte';

	interface Props {
		primary: string[];
		secondary: string[];
		metricById: Record<string, MetricEntry>;
		shortById: Record<string, string>;
	}
	let { primary, secondary, metricById, shortById }: Props = $props();

	const CHANNELS = [
		{ id: 'email', label: 'Email', budget: CHANNEL_COL_BUDGET.email, hint: 'alle Werte als Spalten' },
		{ id: 'telegram', label: 'Telegram', budget: CHANNEL_COL_BUDGET.telegram, hint: 'max 7 Spalten' },
		{ id: 'signal', label: 'Signal', budget: CHANNEL_COL_BUDGET.signal, hint: 'max 5 Spalten' },
		{ id: 'sms', label: 'SMS', budget: CHANNEL_COL_BUDGET.sms, hint: 'keine Tabelle, max 140 Zeichen' },
	] as const;

	// Repräsentative Beispielwerte je Katalog-Metrik (Layout-Vorschau, NICHT die
	// Live-Wetterdaten — die liefert der Output-Vorschau-Tab über #363).
	const SAMPLE_BY_ID: Record<string, string> = {
		temperature: '11.6', wind_chill: '8', humidity: '78 %', dewpoint: '4',
		wind: '11', gust: '30', wind_direction: 'NO',
		precipitation: '0', rain_probability: '0 %', thunder: '0 %', cape: '0',
		snowfall_limit: '2400', precip_type: '—',
		cloud_total: '80 %', cloud_low: '30 %', cloud_mid: '45 %', cloud_high: '70 %',
		visibility: 'gut', sunshine: '35', uv_index: '3', pressure: '1018',
		freezing_level: '2400', snow_depth: '0', fresh_snow: '0', confidence: '85 %',
	};

	// Mobile: nur eine Karte (per Dropdown gewählt).
	let mobileChannel = $state<'email' | 'telegram' | 'signal' | 'sms'>('signal');
	const mobileCard = $derived(CHANNELS.find((c) => c.id === mobileChannel) ?? CHANNELS[2]);
</script>

<Card.Root data-testid="channel-preview-block">
	<div class="head">
		<Eyebrow>Vorschau · so kommt es beim Empfänger an</Eyebrow>
		<div class="title">Pro Kanal</div>
		<p class="hint">
			Identische Spalten-Konfiguration, vier Kanäle. Wenn die Spalten-Anzahl das
			Kanal-Limit übersteigt, wandern die hinteren automatisch in die Detail-Zeile.
		</p>
	</div>

	<!-- Desktop: 4er-Grid -->
	<div class="grid desktop-only">
		{#each CHANNELS as c}
			<ChannelPreviewCard
				label={c.label}
				channelId={c.id}
				budget={c.budget}
				hint={c.hint}
				{primary}
				{secondary}
				{metricById}
				{shortById}
				sampleById={SAMPLE_BY_ID}
			/>
		{/each}
	</div>

	<!-- Mobile: Kanal-Dropdown + 1 Karte -->
	<div class="mobile-only mobile-preview">
		<label class="ch-select">
			<span class="select-label">Kanal</span>
			<Select bind:value={mobileChannel} data-testid="channel-preview-mobile-select">
				{#each CHANNELS as c}
					<option value={c.id}>{c.label}</option>
				{/each}
			</Select>
		</label>
		<ChannelPreviewCard
			label={mobileCard.label}
			channelId={mobileCard.id}
			budget={mobileCard.budget}
			hint={mobileCard.hint}
			{primary}
			{secondary}
			{metricById}
			{shortById}
			sampleById={SAMPLE_BY_ID}
		/>
	</div>
</Card.Root>

<style>
	.head {
		padding: var(--g-s-4) var(--g-s-5) var(--g-s-3);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.title {
		font-size: var(--g-text-xl);
		font-weight: 600;
		margin-top: 2px;
		letter-spacing: var(--g-track-tight);
	}
	.hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin-top: var(--g-s-2);
		line-height: 1.5;
		max-width: 760px;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: var(--g-s-3);
		padding: var(--g-s-4);
		background: var(--g-surface-1);
	}
	.mobile-preview {
		padding: var(--g-s-4);
		background: var(--g-surface-1);
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
	}
	.ch-select {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
	}
	.select-label {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		letter-spacing: var(--g-track-caps);
		text-transform: uppercase;
	}
	.mobile-only {
		display: none;
	}
	@media (max-width: 899px) {
		.desktop-only {
			display: none;
		}
		.mobile-only {
			display: flex;
		}
	}
	@media (max-width: 767px) {
		.ch-select :global(.gz-select select) {
			font-size: 16px; /* iOS-Zoom-Guard (#272) — überschreibt --g-text-sm aus Select.svelte */
		}
	}
</style>
