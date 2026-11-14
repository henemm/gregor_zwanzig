<script lang="ts">
	// Issue #2795 S3b, Teilschritt 1b (AC-30, Uebergangsblock): Telegram-Kurzstil (Trip und Orte) und
	// Mehrtages-Trend (nur Trip) — bis Teil 2 („Inhalt je Kanal“ im Reiter Wetter). Speichert nicht
	// selbst: jede Aenderung geht an den Reiter (kanalStilSpeicherung.ts, Felder wie bisher).
	import { Checkbox } from '$lib/components/ui/checkbox';
	import TelegramKurzstilToggle from '$lib/components/shared/TelegramKurzstilToggle.svelte';
	import { t } from '$lib/i18n';
	import { MIT_TREND, type KanalStilStand } from '../../shared/zustellung-tab/kanalStilSpeicherung.ts';

	interface Props {
		context: 'route' | 'vergleich';
		stand: KanalStilStand;
		/** Telegram ist als Kanal an (sonst ist der Kurzstil-Schalter gesperrt). */
		telegramAn: boolean;
		onaendern: (neu: KanalStilStand) => void;
	}
	let { context, stand, telegramAn, onaendern }: Props = $props();
</script>

<div class="zt-stil">
	<TelegramKurzstilToggle {context} style={stand.stil} disabled={!telegramAn} onchange={(s) => onaendern({ ...stand, stil: s })} />
	{#if MIT_TREND[context]}
		<div class="zt-trend">
			<b>{$t('versand.zeitplan.trend')}</b>
			<small>{$t('versand.zeitplan.trend_sub')}</small>
			<div class="zt-trend-wahl">
				<span data-testid="report-morning-trend">
					<Checkbox checked={stand.trendMorgen} onchange={(e: Event) => onaendern({ ...stand, trendMorgen: (e.target as HTMLInputElement).checked })}
						>{$t('versand.zeitplan.im_morgen')}</Checkbox
					>
				</span>
				<span data-testid="report-evening-trend">
					<Checkbox checked={stand.trendAbend} onchange={(e: Event) => onaendern({ ...stand, trendAbend: (e.target as HTMLInputElement).checked })}
						>{$t('versand.zeitplan.im_abend')}</Checkbox
					>
				</span>
			</div>
		</div>
	{/if}
</div>

<style>
	.zt-stil {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-4);
		padding: var(--g-size-14px) var(--g-s-5);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.zt-trend {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-2px);
	}
	.zt-trend small {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.zt-trend-wahl {
		display: flex;
		flex-wrap: wrap;
		gap: var(--g-s-4);
		margin-top: var(--g-s-2);
	}
</style>
