<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: eingeklappte Karte „Anpassen" mit dem Tagesfenster (AC-21,
	// ADR-0035). Die Bedienung ist die bestehende DayWindowCard (Select-Atom, Clamp unveraendert);
	// gespeichert wird ueber den Reiter (Trip report_config, Orte top-level).
	import { t } from '$lib/i18n';
	import DayWindowCard from '../weather-metrics-tab/DayWindowCard.svelte';
	import type { Tagesfenster } from './wetterZustand.ts';

	interface Props {
		tagesfenster: Tagesfenster;
		onStart: (h: number) => void;
		onEnde: (h: number) => void;
	}
	let { tagesfenster, onStart, onEnde }: Props = $props();

	let offen = $state(false);
</script>

<div class="wt-karte" data-testid="wetter-anpassen-karte">
	<button type="button" class="wt-auf" data-testid="wetter-anpassen-aufklappen" aria-expanded={offen} onclick={() => (offen = !offen)}>
		<span aria-hidden="true">{offen ? '▾' : '▸'}</span>
		{$t('wetter.anpassen.titel')}
	</button>
	{#if offen}
		<div class="wt-inhalt">
			<DayWindowCard
				startHour={tagesfenster.start}
				endHour={tagesfenster.end}
				onStartHour={onStart}
				onEndHour={onEnde}
				titel={$t('wetter.anpassen.tagesfenster')}
				vonLabel={$t('wetter.anpassen.von')}
				bisLabel={$t('wetter.anpassen.bis')}
			/>
		</div>
	{/if}
</div>

<style>
	.wt-karte {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.wt-auf {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		min-height: 44px;
		padding: 0 20px;
		border: none;
		background: transparent;
		color: var(--g-ink);
		font: inherit;
		font-size: 14px;
		font-weight: 600;
		text-align: left;
		cursor: pointer;
	}
	.wt-inhalt {
		padding: 0 12px 12px;
	}
</style>
