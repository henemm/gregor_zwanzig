<script lang="ts">
	// Issue #2794 S3a, Teil-PR 3: „Alarm ab für alle" mit Zaehler (AC-14, A3, A5).
	// Wirkt nur auf alarmfaehige gewaehlte Metriken (Modell `alarmAbFuerAlle`); ohne alarmfaehige
	// Metrik steht der Hinweis statt der Segmente. Trip und Orts-Briefing gleich.
	// #2913 Teil 2 (K-6): Zeile aus dem Molekül Einstellungszeile, Stufen als Segmented mit Farbpunkt.
	import { Segmented } from '$lib/components/atoms';
	import { Einstellungszeile } from '$lib/components/molecules';
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
		STUFEN.map((s) => ({
			value: s,
			label: $t(`alarme.alarm_ab.stufe.${s}` as 'alarme.alarm_ab.stufe.never'),
			testid: `wetter-alarm-ab-alle-${s}`,
			farbe: s === 'never' ? undefined : s
		}))
	);
	const mitSegmenten = $derived(zaehler.art === 'zaehler');
</script>

<div class="wt-kopf">
	<Einstellungszeile
		titel={$t('wetter.alarm_ab.fuer_alle')}
		hinweis={$t(zaehler.schluessel as 'wetter.alarm_ab.zaehler', zaehler.werte)}
		testid="wetter-alarm-ab-alle"
		hinweisTestid="wetter-alarm-zaehler"
	>
		{#if mitSegmenten}
			<div class="wt-seg">
				<Segmented rolle="radio" ariaLabel={$t('wetter.alarm_ab.fuer_alle')} options={optionen} value="" onChange={(s: string) => onAlle(s as AlarmAb)} />
			</div>
		{/if}
	</Einstellungszeile>
</div>

<style>
	.wt-kopf {
		background: var(--g-card-alt);
	}
	.wt-seg :global([data-slot='segmented-item']) {
		min-height: var(--g-tap-min);
		min-width: var(--g-tap-min);
		color: var(--g-ink-2);
	}
</style>
