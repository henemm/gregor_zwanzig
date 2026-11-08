<script lang="ts">
	// Issue #864/#859 — Eine Metrik-Zeile im Alerts-Tab.
	// Issue #2793 S2b (Spec feat_2793_s2_alarm_stufenwechsel.md §6): bis S3a NUR
	// LESBAR — statt des Reglers steht die wirksame Stufe „Alarm ab" der Ampel
	// (Vorboten: „kein Alarm (Vorbote)", D4-Metriken: ihre heutige Stufe).
	import type { AlertMetric } from '$lib/types';
	import type { AlarmAbZeile } from './alarmAbAnzeige.ts';
	import BegriffErklaerung from '$lib/components/molecules/BegriffErklaerung.svelte';
	import { METRIK_BEGRIFF } from '$lib/components/shared/infoboxKeys';
	import { t } from '$lib/i18n';
	import type { MessageKey } from '$lib/i18n';

	interface Props {
		metric: AlertMetric;
		label: string;
		zeile: AlarmAbZeile;
	}

	let { metric, label, zeile }: Props = $props();

	const STUFE: Record<string, MessageKey> = {
		never: 'alarme.alarm_ab.stufe.never',
		yellow: 'alarme.alarm_ab.stufe.yellow',
		orange: 'alarme.alarm_ab.stufe.orange',
		red: 'alarme.alarm_ab.stufe.red'
	};
	const D4_STUFE: Record<string, MessageKey> = {
		off: 'alarme.empfindlichkeit.aus',
		entspannt: 'alarme.preset.entspannt',
		standard: 'alarme.preset.standard',
		sensibel: 'alarme.preset.sensibel'
	};

	const wert = $derived(
		zeile.art === 'vorbote'
			? $t('alarme.alarm_ab.vorbote')
			: zeile.art === 'd4'
				? $t(D4_STUFE[zeile.level] ?? 'alarme.preset.standard')
				: $t('alarme.alarm_ab.wert', { stufe: zeile.stufe ? $t(STUFE[zeile.stufe]) : '—' })
	);
	const kennung = $derived(
		zeile.art === 'ampel' ? (zeile.stufe ?? 'offen') : zeile.art === 'd4' ? `d4-${zeile.level}` : 'vorbote'
	);
	const isDimmed = $derived(
		zeile.art === 'vorbote' || (zeile.art === 'ampel' && zeile.stufe === 'never') || (zeile.art === 'd4' && zeile.level === 'off')
	);
	const begriff = $derived(METRIK_BEGRIFF[metric]);
</script>

<tr class:dimmed={isDimmed} data-testid="alert-metric-row-{metric}" data-metric={metric} data-alarm-ab={kennung}>
	<td class="metric-label">
		{label}
		{#if begriff}<BegriffErklaerung {begriff} suffix="alarm-{metric}" />{/if}
	</td>
	<td class="alarm-ab" data-testid="alert-alarm-ab-{metric}">{wert}</td>
</tr>

<style>
	tr.dimmed {
		opacity: 0.6;
	}

	.metric-label {
		padding: 8px;
		font-size: 14px;
		color: var(--g-ink);
	}

	.alarm-ab {
		padding: 8px;
		font-size: 14px;
		color: var(--g-ink);
		white-space: nowrap;
	}

	@media (max-width: 899px) {
		tr {
			display: block;
			margin-bottom: 12px;
			border-bottom: 1px solid var(--g-rule-soft, #eee);
			padding-bottom: 8px;
		}

		td {
			display: block;
		}

		.metric-label {
			font-weight: 600;
		}
	}
</style>
