<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: „Nicht im Briefing" — Metriken, die nicht gewaehlt sind,
	// als „+ Name" (AC-19). Neu hinzugefuegte Metriken haengen hinten an; die Meldung nennt,
	// wo Roh/Einfach eingestellt wird. Trip und Orts-Briefing gleich.
	import { t } from '$lib/i18n';

	interface Props {
		metriken: { id: string; name: string }[];
		/** Name der zuletzt hinzugefuegten Metrik (Meldung), sonst null. */
		hinzugefuegt: string | null;
		onHinzufuegen: (id: string) => void;
	}
	let { metriken, hinzugefuegt, onHinzufuegen }: Props = $props();
</script>

<div class="wt-mehr" data-testid="wetter-nicht-im-briefing">
	<span class="wt-titel">{$t('wetter.nicht_im_briefing.titel')}</span>
	<div class="wt-chips">
		{#each metriken as m (m.id)}
			<button type="button" class="wt-chip" data-testid="wetter-nicht-im-briefing-plus-{m.id}" onclick={() => onHinzufuegen(m.id)}>
				{$t('wetter.nicht_im_briefing.hinzufuegen', { metrik: m.name })}
			</button>
		{/each}
	</div>
	{#if hinzugefuegt}
		<p class="wt-meldung" role="status" data-testid="wetter-hinzugefuegt-meldung">{$t('wetter.nicht_im_briefing.hinzugefuegt', { metrik: hinzugefuegt })}</p>
	{/if}
</div>

<style>
	.wt-mehr {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 14px 20px;
		border-top: 1px solid var(--g-rule-soft);
	}
	.wt-titel {
		font-size: 12.5px;
		color: var(--g-ink-2);
	}
	.wt-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.wt-chip {
		min-height: 44px;
		min-width: 44px;
		padding: 0 12px;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-pill);
		background: var(--g-card);
		color: var(--g-ink);
		font: inherit;
		font-size: 13px;
		cursor: pointer;
	}
	.wt-meldung {
		margin: 0;
		font-size: 13px;
		color: var(--g-ink-2);
	}
	@media (max-width: 899px) {
		.wt-mehr {
			padding: 14px 16px;
		}
	}
</style>
