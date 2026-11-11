<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: „Alarm ab für alle" mit Zaehler (AC-14, A3, A5).
	// Wirkt nur auf alarmfaehige gewaehlte Metriken (Modell `alarmAbFuerAlle`); ohne alarmfaehige
	// Metrik steht der Hinweis statt der Segmente. Trip und Orts-Briefing gleich.
	import { Segmented } from '$lib/components/atoms';
	import { t } from '$lib/i18n';
	import type { AlarmAb, KatalogModell } from '../../shared/wetter-tab/ampelModell.ts';

	interface Props {
		zaehler: KatalogModell<'zaehler' | 'keine_alarmfaehig'>;
		onAlle: (stufe: AlarmAb) => void;
	}
	let { zaehler, onAlle }: Props = $props();

	const STUFEN: AlarmAb[] = ['never', 'yellow', 'orange', 'red'];
	// i18n-dynamic: alarme.alarm_ab.stufe.
	const optionen = $derived(
		STUFEN.map((s) => ({ value: s, label: $t(`alarme.alarm_ab.stufe.${s}` as 'alarme.alarm_ab.stufe.never'), testid: `wetter-alarm-ab-alle-${s}` }))
	);
	const mitSegmenten = $derived(zaehler.art === 'zaehler');
</script>

<div class="wt-kopf" data-testid="wetter-alarm-ab-alle">
	<div class="wt-text">
		<b>{$t('wetter.alarm_ab.fuer_alle')}</b>
		<small data-testid="wetter-alarm-zaehler">{$t(zaehler.schluessel as 'wetter.alarm_ab.zaehler', zaehler.werte)}</small>
	</div>
	{#if mitSegmenten}
		<div class="wt-seg">
			<Segmented rolle="radio" ariaLabel={$t('wetter.alarm_ab.fuer_alle')} options={optionen} value="" onChange={(s: string) => onAlle(s as AlarmAb)} />
		</div>
	{/if}
</div>

<style>
	.wt-kopf {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-size-10px) var(--g-s-4);
		padding: var(--g-size-14px) var(--g-s-5);
		background: var(--g-card-alt);
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
	.wt-seg :global([data-slot='segmented-item']) {
		min-height: var(--g-tap-min);
		min-width: var(--g-tap-min);
		color: var(--g-ink-2);
	}
	@media (max-width: 899px) {
		.wt-kopf {
			padding: var(--g-size-14px) var(--g-s-4);
		}
	}
</style>
