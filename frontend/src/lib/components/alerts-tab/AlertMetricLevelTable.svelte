<script lang="ts">
	// Issue #864/#859 — Tabelle aus AlertMetricLevelRow.
	// Issue #2793 S2b (Spec feat_2793_s2_alarm_stufenwechsel.md §6): bis S3a NUR
	// LESBAR. Alarme folgen der Ampel (`ampel.metrics.<id>.alarm_ab`); Regler und
	// Schnellwahl „Alle Metriken auf" entfallen, damit nichts still wirkungslos
	// bleibt (PO-Entscheid E2, S1). Oben EIN Hinweis aus dem Katalog.
	import type { AlertMetric } from '$lib/types';
	import AlertMetricLevelRow from './AlertMetricLevelRow.svelte';
	import { alarmAbZeile, type VorlagenAmpeln } from './alarmAbAnzeige.ts';
	// #1401 Scheibe B: die Beschriftungen kommen aus dem geteilten Register.
	import { alertMetricLabel } from '$lib/utils/alertMetricLabels';
	import { t, locale } from '$lib/i18n';

	interface Props {
		activeMetrics: AlertMetric[];
		/** Gespeicherte Altstufen — nur noch fuer die D4-Zeilen gelesen. */
		levels: Partial<Record<AlertMetric, string>>;
		/** Abo-Ampel (`display_config.ampel`), darf Teilmenge sein. */
		aboAmpel?: VorlagenAmpeln[string];
		/** Aufgeloeste Vorlage des Abos (Rueckfall fuer fehlende `alarm_ab`). */
		vorlage?: VorlagenAmpeln[string];
	}

	let { activeMetrics, levels, aboAmpel = null, vorlage = null }: Props = $props();
</script>

<div class="alert-metric-table" data-testid="alert-metric-level-table">
	<p class="umbau-hinweis" data-testid="alert-metric-umbau-hinweis">
		{$t('alarme.alarm_ab.umbau_hinweis')}
	</p>

	{#if activeMetrics.length === 0}
		<p class="empty-hint" data-testid="alert-metric-empty">
			{$t('alarme.tabelle.leer')}
		</p>
	{:else}
		<table>
			<thead>
				<tr>
					<th>{$t('alarme.tabelle.metrik')}</th>
					<th>{$t('alarme.alarm_ab.titel')}</th>
				</tr>
			</thead>
			<tbody>
				{#each activeMetrics as metric (metric)}
					<AlertMetricLevelRow
						{metric}
						label={alertMetricLabel(metric, $locale)}
						zeile={alarmAbZeile(metric, aboAmpel, vorlage, levels)}
					/>
				{/each}
			</tbody>
		</table>
	{/if}
</div>

<style>
	.umbau-hinweis {
		margin: 0 0 12px;
		padding: 8px 12px;
		border-left: 3px solid var(--g-accent, #2563eb);
		font-size: 14px;
		color: var(--g-ink);
	}

	table {
		width: 100%;
		border-collapse: collapse;
	}
	th {
		text-align: left;
		padding: 8px;
		border-bottom: 1px solid var(--g-rule, #ddd);
		font-size: 12px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--g-ink-2, #555);
	}

	.empty-hint {
		color: var(--g-ink-3, #888);
		font-style: italic;
	}

	@media (max-width: 899px) {
		table {
			display: block; /* Zeilen werden in AlertMetricLevelRow als Block gerendert */
		}
		thead {
			display: none;
		}
		tbody {
			display: block;
		}
	}
</style>
