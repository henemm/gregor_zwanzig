<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: Karte „Amtliche Warnungen & Radar" (AC-20, AC-21).
	// Ein Schalter fuer die amtlichen Warnungen (ODER-Regel beim Lesen, beide Felder beim Schreiben,
	// amtlicheWarnungen.ts); der Radar-Schalter nur, wenn der Aufrufer `mitRadar` setzt
	// (Orts-Briefing; Trip folgt mit S8 #2800).
	import { t } from '$lib/i18n';

	interface Props {
		warnungenAn: boolean;
		radarAn: boolean;
		mitRadar: boolean;
		onWarnungen: (an: boolean) => void;
		onRadar: (an: boolean) => void;
	}
	let { warnungenAn, radarAn, mitRadar, onWarnungen, onRadar }: Props = $props();
</script>

{#snippet schalter(an: boolean, testid: string, label: string, umlegen: (an: boolean) => void)}
	<button type="button" class="wt-switch" role="switch" aria-checked={an} aria-label={label} data-testid={testid} onclick={() => umlegen(!an)}>
		<span class="wt-track" class:an><span class="wt-knopf"></span></span>
	</button>
{/snippet}

<div class="wt-karte">
	<div class="wt-zeile">
		<div class="wt-text">
			<b>{$t('wetter.warnungen.titel')}</b>
			<small>{$t('wetter.warnungen.beschreibung')}</small>
		</div>
		{@render schalter(warnungenAn, 'wetter-warnungen-schalter', $t('wetter.warnungen.titel'), onWarnungen)}
	</div>
	{#if mitRadar}
		<div class="wt-zeile">
			<div class="wt-text">
				<b>{$t('wetter.radar.titel')}</b>
				<small>{$t('wetter.radar.beschreibung', { orte: $t('wetter.radar.deine_orte') })}</small>
			</div>
			{@render schalter(radarAn, 'wetter-radar-schalter', $t('wetter.radar.titel'), onRadar)}
		</div>
	{/if}
</div>

<style>
	.wt-karte {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.wt-zeile {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-s-4);
		padding: var(--g-s-3) var(--g-s-5);
	}
	.wt-zeile + .wt-zeile {
		border-top: 1px solid var(--g-rule-soft);
	}
	.wt-text {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-2px);
		min-width: 0;
	}
	.wt-text b {
		font-size: var(--g-size-14px);
		color: var(--g-ink);
	}
	.wt-text small {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.wt-switch {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: var(--g-size-56px);
		min-height: var(--g-tap-min);
		padding: 0;
		border: none;
		background: transparent;
		cursor: pointer;
		flex-shrink: 0;
	}
	.wt-switch:focus-visible {
		outline: var(--g-size-2px) solid var(--g-accent);
		outline-offset: var(--g-size-2px);
	}
	.wt-track {
		position: relative;
		display: block;
		width: var(--g-tap-min);
		height: var(--g-size-26px);
		border-radius: var(--g-size-13px);
		background: var(--g-ink-3);
		transition: background 120ms;
	}
	.wt-track.an {
		background: var(--g-success);
	}
	.wt-knopf {
		position: absolute;
		top: var(--g-size-2px);
		left: var(--g-size-2px);
		width: var(--g-size-22px);
		height: var(--g-size-22px);
		border-radius: 50%;
		background: var(--g-paper);
		transition: left 120ms;
	}
	.wt-track.an .wt-knopf {
		left: var(--g-s-5);
	}
	@media (max-width: 899px) {
		.wt-zeile {
			padding: var(--g-s-3) var(--g-s-4);
		}
	}
</style>
