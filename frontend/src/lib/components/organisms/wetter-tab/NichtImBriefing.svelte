<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: „Nicht im Briefing" — Metriken, die nicht gewaehlt sind,
	// als „+ Name" (AC-19). Neu hinzugefuegte Metriken haengen hinten an; die Meldung nennt,
	// wo Roh/Einfach eingestellt wird. Trip und Orts-Briefing gleich.
	// #2913 Teil 2 (AC-15, K-2): die Chips kommen aus dem Molekül ChipLeiste (Btn-Chips).
	// #2913 Scheibe (c) (AC-1): Label und Chips stehen in einer waagrechten Zeile (Mockup `.more`).
	import { ChipLeiste } from '$lib/components/molecules';
	import { t } from '$lib/i18n';

	interface Props {
		metriken: { id: string; name: string }[];
		/** Name der zuletzt hinzugefuegten Metrik (Meldung), sonst null. */
		hinzugefuegt: string | null;
		onHinzufuegen: (id: string) => void;
	}
	let { metriken, hinzugefuegt, onHinzufuegen }: Props = $props();

	const chips = $derived(
		metriken.map((m) => ({
			id: m.id,
			label: $t('wetter.nicht_im_briefing.hinzufuegen', { metrik: m.name }),
			testid: `wetter-nicht-im-briefing-plus-${m.id}`
		}))
	);
</script>

<div class="wt-mehr" data-testid="wetter-nicht-im-briefing">
	<span class="wt-titel">{$t('wetter.nicht_im_briefing.titel')}</span>
	<ChipLeiste eintraege={chips} onWahl={onHinzufuegen} />
	{#if hinzugefuegt}
		<p class="wt-meldung" role="status" data-testid="wetter-hinzugefuegt-meldung">{$t('wetter.nicht_im_briefing.hinzugefuegt', { metrik: hinzugefuegt })}</p>
	{/if}
</div>

<style>
	/* #2913 Scheibe (c) (AC-1): Label und Chips in EINER waagrechten, umbrechenden Zeile (Mockup `.more`). */
	.wt-mehr {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--g-s-2);
		padding: var(--g-s-3) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
	}
	.wt-titel {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.wt-meldung {
		flex-basis: 100%;
		margin: 0;
		font-size: var(--g-text-sm);
		color: var(--g-ink-2);
	}
	@media (max-width: 899px) {
		.wt-mehr {
			padding: var(--g-s-3) var(--g-s-4);
		}
	}
</style>
