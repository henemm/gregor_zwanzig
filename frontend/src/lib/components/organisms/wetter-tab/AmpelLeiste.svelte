<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: Ampel-Leiste einer Metrik-Zeile (Mockup Fassung 3, `band`).
	// Geteilt fuer Trip und Orts-Briefing; Geometrie in ampelLeiste.ts.
	import type { Ampel, AmpelMetrik } from '$lib/types';
	import { t } from '$lib/i18n';
	import { gewitterLeiste, leisteVon, type LeisteFarbe } from '../../shared/wetter-tab/ampelLeiste.ts';

	interface Props {
		id: string;
		eintrag: AmpelMetrik | undefined;
		/** Gewitter-Zeile: Stufen statt Grenzzahlen. */
		gewitter?: Ampel['thunder'] | null;
	}
	let { id, eintrag, gewitter = null }: Props = $props();

	const leiste = $derived(gewitter ? { segmente: gewitterLeiste(gewitter), marken: [] } : leisteVon(eintrag));

	const FARBE: Record<LeisteFarbe, string> = {
		green: 'var(--g-success)',
		yellow: 'var(--g-wx-sun)',
		orange: 'var(--g-accent)',
		red: 'var(--g-danger)'
	};
	// i18n-dynamic: wetter.farbe.
	const farbwort = (f: LeisteFarbe) => $t(`wetter.farbe.${f}` as 'wetter.farbe.green');
</script>

<div class="wt-leiste" data-testid="wetter-ampel-leiste-{id}">
	{#if gewitter}
		<div class="wt-marken wt-marken--stufen" aria-hidden="true">
			<span>&nbsp;</span><span>{$t('wetter.gewitter.mittel')}</span><span>{$t('wetter.gewitter.hoch')}</span>
		</div>
	{:else}
		<div class="wt-marken" aria-hidden="true">
			{#each leiste.marken as m, i (i)}
				<i style:left="{m.pos.toFixed(1)}%">{m.wert}</i>
			{/each}
		</div>
	{/if}
	<div class="wt-band">
		{#each leiste.segmente as s, i (i)}
			<span title={farbwort(s.farbe)} style:width="{(Math.max(0, s.anteil) * 100).toFixed(2)}%" style:background={FARBE[s.farbe]}></span>
		{/each}
	</div>
</div>

<style>
	.wt-leiste {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-2px);
		min-width: 0;
	}
	.wt-marken {
		position: relative;
		height: var(--g-s-4);
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		color: var(--g-ink-2);
	}
	.wt-marken i {
		position: absolute;
		transform: translateX(-50%);
		font-style: normal;
		white-space: nowrap;
	}
	.wt-marken--stufen {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		text-align: center;
	}
	.wt-band {
		display: flex;
		height: var(--g-size-10px);
		border-radius: var(--g-size-5px);
		overflow: hidden;
		border: 1px solid var(--g-rule);
	}
	.wt-band span {
		display: block;
		height: 100%;
	}
</style>
