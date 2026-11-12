<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: Ampel-Leiste einer Metrik-Zeile (Mockup Fassung 3, `band`).
	// Geteilt fuer Trip und Orts-Briefing; Geometrie in ampelLeiste.ts.
	import type { Ampel, AmpelMetrik } from '$lib/types';
	import { t } from '$lib/i18n';
	import { entzerreMarken, gewitterLeiste, leisteVon, type LeisteFarbe } from '../../shared/wetter-tab/ampelLeiste.ts';

	interface Props {
		id: string;
		eintrag: AmpelMetrik | undefined;
		/** Gewitter-Zeile: Stufen statt Grenzzahlen. */
		gewitter?: Ampel['thunder'] | null;
	}
	let { id, eintrag, gewitter = null }: Props = $props();

	const leiste = $derived(gewitter ? { segmente: gewitterLeiste(gewitter), marken: [] } : leisteVon(eintrag));

	// #2913 AC-9: eng liegende Grenzzahlen (schmale Mittelspalte, z. B. 1024 px) nicht überlappen lassen.
	// Gemessene Breiten von Leiste und Zahlen; bis gemessen ist, stehen die Zahlen in Prozent wie bisher.
	const ABSTAND_PX = 3;
	let breite = $state(0);
	let zahlBreiten = $state<number[]>([]);
	const lagen = $derived.by(() => {
		const b = zahlBreiten.slice(0, leiste.marken.length);
		if (breite <= 0 || b.length !== leiste.marken.length || !b.every((w) => w > 0)) return null;
		return entzerreMarken(leiste.marken.map((m) => m.pos), b, breite, ABSTAND_PX);
	});

	// #2913 Teil 2 (AC-12): Ampelfarben aus --g-ampel-* (Light/Dark, je >= 3:1 gegen die Karte).
	// Ohne Farbe erkennbar: feste Reihenfolge, Grenzwerte/Stufenwörter darüber; für
	// Hilfstechnik je Segment role="img" mit dem Farbnamen aus dem Katalog.
	const FARBE: Record<LeisteFarbe, string> = {
		green: 'var(--g-ampel-gruen)',
		yellow: 'var(--g-ampel-gelb)',
		orange: 'var(--g-ampel-orange)',
		red: 'var(--g-ampel-rot)'
	};
	// i18n-dynamic: wetter.farbe.
	const farbwort = (f: LeisteFarbe) => $t(`wetter.farbe.${f}` as 'wetter.farbe.green');
</script>

<div class="wt-leiste" data-testid="wetter-ampel-leiste-{id}">
	{#if gewitter}
		<div class="wt-marken wt-marken--stufen" aria-hidden="true">
			<!-- #2913 Runde 2: alle drei Zonen beschriftet (Mockup `ticks` keins · mittel · hoch). -->
			<span>{$t('wetter.gewitter.keins')}</span><span>{$t('wetter.gewitter.mittel')}</span><span>{$t('wetter.gewitter.hoch')}</span>
		</div>
	{:else}
		<div class="wt-marken" aria-hidden="true" bind:clientWidth={breite}>
			{#each leiste.marken as m, i (i)}
				<i bind:offsetWidth={zahlBreiten[i]} style:left={lagen ? `${lagen[i].toFixed(1)}px` : `${m.pos.toFixed(1)}%`}>{m.wert}</i>
			{/each}
		</div>
	{/if}
	<div class="wt-band">
		{#each leiste.segmente as s, i (i)}
			<span role="img" aria-label={farbwort(s.farbe)} data-farbe={s.farbe} title={farbwort(s.farbe)} style:width="{(Math.max(0, s.anteil) * 100).toFixed(2)}%" style:background={FARBE[s.farbe]}></span>
		{/each}
	</div>
</div>

<style>
	.wt-leiste {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-3px);
		min-width: 0;
	}
	.wt-marken {
		position: relative;
		height: var(--g-size-14px);
		font-family: var(--g-font-mono);
		font-size: var(--g-size-10-5px);
		line-height: var(--g-size-14px);
		color: var(--g-ink-3);
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
		background: var(--g-rule-soft);
	}
	.wt-band span {
		display: block;
		height: 100%;
	}
</style>
