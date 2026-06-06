<script lang="ts">
	// Issue #496 — "Pro Kanal"-Vorschau neu gedacht.
	// Loest die alte 4-Kachel-Mini-Tabelle (Issue #365) ab: links die Konsequenz
	// pro Kanal (Schicht 1), rechts die echte Vorschau in Original-Breite des
	// aktiven Kanals (Schicht 2). Ein-Kanal-Fokus mit Wechsler (Option B).
	import * as Card from '$lib/components/ui/card/index.js';
	import { Eyebrow } from '$lib/components/atoms';
	import { CHANNEL_COL_BUDGET, type MetricEntry } from './metricsEditor.ts';
	import ChannelPreviewCard from './ChannelPreviewCard.svelte';
	import ChannelFidelityEmail from './ChannelFidelityEmail.svelte';
	import ChannelFidelityBubble from './ChannelFidelityBubble.svelte';
	import ChannelFidelitySMS from './ChannelFidelitySMS.svelte';

	interface Props {
		primary: string[];
		secondary: string[];
		metricById: Record<string, MetricEntry>;
		shortById: Record<string, string>;
	}
	let { primary, secondary, metricById, shortById }: Props = $props();

	type ChannelId = 'email' | 'telegram' | 'sms';

	const CHANNELS: Array<{ id: ChannelId; label: string; glyph: string; maxCols: number }> = [
		{ id: 'email',    label: 'Email',    glyph: '✉', maxCols: CHANNEL_COL_BUDGET.email },
		{ id: 'telegram', label: 'Telegram', glyph: '✈', maxCols: CHANNEL_COL_BUDGET.telegram },
		{ id: 'sms',      label: 'SMS',      glyph: '✱', maxCols: CHANNEL_COL_BUDGET.sms },
	];

	let activeChannel = $state<ChannelId>('telegram');
	const activeMeta = $derived(CHANNELS.find((c) => c.id === activeChannel) ?? CHANNELS[0]);
</script>

<Card.Root class="overflow-visible" data-testid="channel-preview-block">
	<div class="head">
		<Eyebrow>Vorschau · so kommt es beim Empfänger an</Eyebrow>
		<div class="title-row">
			<div class="title">Pro Kanal</div>
			<div class="counts mono">
				{primary.length} {primary.length === 1 ? 'Spalte' : 'Spalten'} · {secondary.length} Detail
			</div>
		</div>
		<p class="hint">
			Eine Konfiguration, drei Kanäle mit unterschiedlicher Kapazität. Links
			siehst du <strong>für jeden Kanal die Konsequenz</strong> deiner Auswahl —
			klick einen Kanal an, um <strong>die echte Vorschau</strong> in
			Original-Breite zu sehen.
		</p>
	</div>

	<div class="body">
		<aside class="layer1" aria-label="Konsequenz pro Kanal">
			<div class="section-label mono">1 · KONSEQUENZ PRO KANAL</div>
			<div class="cards">
				{#each CHANNELS as c}
					<ChannelPreviewCard
						channelId={c.id}
						label={c.label}
						glyph={c.glyph}
						maxCols={c.maxCols}
						{primary}
						{secondary}
						{metricById}
						active={activeChannel === c.id}
						onSelect={() => (activeChannel = c.id)}
					/>
				{/each}
			</div>
		</aside>

		<section class="layer2" aria-label="Vorschau {activeMeta.label}">
			<div class="section-row">
				<div class="section-label mono">2 · SO SIEHT {activeMeta.label.toUpperCase()} AUS</div>
				<div class="example-hint mono">Beispielwerte · kein Live-Wetter</div>
			</div>

			{#if activeChannel === 'email'}
				<ChannelFidelityEmail {primary} {secondary} {metricById} {shortById} />
			{:else if activeChannel === 'sms'}
				<ChannelFidelitySMS {primary} {secondary} {metricById} />
			{:else}
				<ChannelFidelityBubble
					channelId={activeChannel}
					{primary}
					{secondary}
					{metricById}
					{shortById}
				/>
			{/if}
		</section>
	</div>
</Card.Root>

<style>
	.head {
		padding: var(--g-s-4) var(--g-s-5) var(--g-s-3);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.title-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--g-s-2);
		flex-wrap: wrap;
	}
	.title {
		font-size: var(--g-text-xl);
		font-weight: 600;
		margin-top: 2px;
		letter-spacing: var(--g-track-tight);
	}
	.counts {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
	}
	.hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin-top: var(--g-s-2);
		line-height: 1.5;
		max-width: 760px;
	}

	.body {
		display: grid;
		grid-template-columns: 340px 1fr;
		background: var(--g-surface-1);
	}
	.layer1 {
		padding: var(--g-s-4);
		background: var(--g-card-alt);
		border-right: 1px solid var(--g-rule-soft);
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
	}
	.layer2 {
		padding: var(--g-s-4);
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
		min-width: 0;
	}
	.section-label {
		font-size: 10px;
		letter-spacing: var(--g-track-caps);
		text-transform: uppercase;
		color: var(--g-ink-muted);
		font-weight: 600;
	}
	.section-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--g-s-2);
		flex-wrap: wrap;
	}
	.example-hint {
		font-size: 10px;
		letter-spacing: var(--g-track-wide);
		color: var(--g-ink-muted);
		font-style: italic;
	}
	.cards {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}

	@media (max-width: 899px) {
		.body {
			grid-template-columns: 1fr;
		}
		.layer1 {
			border-right: 0;
			border-bottom: 1px solid var(--g-rule-soft);
		}
		.cards {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: var(--g-s-2);
		}
	}
	@media (max-width: 500px) {
		.cards {
			grid-template-columns: 1fr;
		}
	}
</style>
