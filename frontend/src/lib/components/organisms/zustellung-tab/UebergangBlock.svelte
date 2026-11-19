<script lang="ts">
	// Issue #2795 S3b, Teilschritt 1b (AC-30, Spec §5): klar abgegrenzter Uebergangsblock am Ende des
	// Reiters Zustellung. Enthaelt die Pausieren-/Aktivieren-Karte des Orts-Briefings und den Beispiel-Alarm.
	// Issue #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 14, AC-30): die Listen je Kanal,
	// Stundenverlauf, Ausblick, Telegram-Kurzstil, Mehrtages-Trend, E-Mail-Format, Etappen-Kennzahlen,
	// Vortag-Vergleich und Nacht-Stundentabelle bedient allein die Karte „Was steht wo“ im Reiter Wetter;
	// die Metrik-Oberflaeche (WetterMetrikenVersandPanel) und KanalStil sind hier entfernt.
	import type { ComponentProps, Snippet } from 'svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import AlertPreviewCard from '$lib/components/alerts-tab/AlertPreviewCard.svelte';
	import { t } from '$lib/i18n';
	import type { AlertRule, ComparePreset, Trip } from '$lib/types';

	interface Props {
		context: 'route' | 'vergleich';
		trip?: Trip;
		preset?: ComparePreset;
		/** Orts-Briefing: Pausieren/Aktivieren-Karte des Hubs. */
		activation?: Snippet;
		/** Orts-Briefing: Regeln des Beispiel-Alarms (aus der Metrik-Auswahl des Hubs). */
		beispielAlarmRegeln?: AlertRule[];
	}
	let { context, trip, preset, activation, beispielAlarmRegeln = [] }: Props = $props();

	// Beispiel-Alarm wie bisher im Alarm-Baustein: Trip mit seinen Regeln und Etappen, Orte mit den
	// Regeln aus der Metrik-Auswahl und den Orten (Kontext-Unterschied als Daten, Ratsche
	// context_herkunft_zweige_eingefroren).
	const BEISPIEL: Record<'route' | 'vergleich', () => ComponentProps<typeof AlertPreviewCard>> = {
		route: () => ({ kind: 'route', id: trip?.id ?? '', alertRules: trip?.alert_rules ?? [], stages: trip?.stages ?? [] }),
		vergleich: () => ({ kind: 'vergleich', id: preset?.id ?? '', alertRules: beispielAlarmRegeln, locationIds: preset?.location_ids ?? [] })
	};
	const beispiel = $derived(BEISPIEL[context]());
</script>

<section class="zt-uebergang" data-abschnitt="uebergang" data-testid="zustellung-uebergang">
	<div class="zt-uebergang-kopf">
		<b>{$t('zustellung.uebergang.titel')}</b>
		<small>{$t('zustellung.uebergang.hinweis')}</small>
	</div>
	{#if activation}
		<div class="zt-aktivierung">{@render activation()}</div>
	{/if}
	<div class="zt-beispiel">
		<Eyebrow>{$t('alarme.beispiel_warnung')}</Eyebrow>
		<AlertPreviewCard {...beispiel} />
	</div>
</section>

<style>
	.zt-uebergang {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-4);
		padding-top: var(--g-s-5);
		border-top: 1px dashed var(--g-rule);
	}
	.zt-uebergang-kopf {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-2px);
	}
	.zt-beispiel {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}
	.zt-uebergang-kopf small {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
</style>
