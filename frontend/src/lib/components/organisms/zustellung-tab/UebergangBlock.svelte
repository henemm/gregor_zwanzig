<script lang="ts">
	// Issue #2795 S3b, Teilschritt 1b (AC-30, Spec §5): klar abgegrenzter Uebergangsblock am Ende des
	// Reiters Zustellung — bis Teil 2 („Inhalt je Kanal“ im Reiter Wetter) und S5 („Test schicken“).
	// Enthaelt unveraendert: Telegram-Kurzstil und Mehrtages-Trend (KanalStil), die
	// Zustellungs-Abschnitte der Metrik-Oberflaeche (Layout je Kanal, Stundenverlauf, Ausblick,
	// Mail-Inhalt, Nachtblock, SMS-Schwellen) OHNE den alten Versand-Abschnitt, die Pausieren-/
	// Aktivieren-Karte des Orts-Briefings und den Beispiel-Alarm. Jeder Baustein speichert wie vorher.
	import type { ComponentProps, Snippet } from 'svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import AlertPreviewCard from '$lib/components/alerts-tab/AlertPreviewCard.svelte';
	import WetterMetrikenVersandPanel from '../../shared/WetterMetrikenVersandPanel.svelte';
	import KanalStil from './KanalStil.svelte';
	import type { KanalStilStand } from '../../shared/zustellung-tab/kanalStilSpeicherung.ts';
	import { t } from '$lib/i18n';
	import type { AlertRule } from '$lib/types';

	type PanelProps = ComponentProps<typeof WetterMetrikenVersandPanel>;

	interface Props extends Omit<PanelProps, 'context' | 'bereich' | 'mitVersandAbschnitt' | 'activation'> {
		context: 'route' | 'vergleich';
		/** Telegram ist als Briefing- oder Alarm-Kanal an (Kurzstil-Schalter sonst gesperrt). */
		telegramAn: boolean;
		/** Orts-Briefing: Pausieren/Aktivieren-Karte des Hubs. */
		activation?: Snippet;
		/** Orts-Briefing: Regeln des Beispiel-Alarms (aus der Metrik-Auswahl des Hubs). */
		beispielAlarmRegeln?: AlertRule[];
		/** Telegram-Kurzstil und Mehrtages-Trend (Stand und Aenderung, gespeichert vom Reiter). */
		kanalStil: KanalStilStand;
		onKanalStil: (neu: KanalStilStand) => void;
	}
	let { context, telegramAn, activation, beispielAlarmRegeln = [], kanalStil, onKanalStil, ...panel }: Props = $props();

	// Beispiel-Alarm wie bisher im Alarm-Baustein: Trip mit seinen Regeln und Etappen, Orte mit den
	// Regeln aus der Metrik-Auswahl und den Orten (Kontext-Unterschied als Daten, Ratsche
	// context_herkunft_zweige_eingefroren).
	const BEISPIEL: Record<'route' | 'vergleich', () => ComponentProps<typeof AlertPreviewCard>> = {
		route: () => ({ kind: 'route', id: panel.trip?.id ?? '', alertRules: panel.trip?.alert_rules ?? [], stages: panel.trip?.stages ?? [] }),
		vergleich: () => ({ kind: 'vergleich', id: panel.preset?.id ?? '', alertRules: beispielAlarmRegeln, locationIds: panel.preset?.location_ids ?? [] })
	};
	const beispiel = $derived(BEISPIEL[context]());
</script>

<section class="zt-uebergang" data-abschnitt="uebergang" data-testid="zustellung-uebergang">
	<div class="zt-uebergang-kopf">
		<b>{$t('zustellung.uebergang.titel')}</b>
		<small>{$t('zustellung.uebergang.hinweis')}</small>
	</div>
	<KanalStil {context} stand={kanalStil} {telegramAn} onaendern={onKanalStil} />
	<WetterMetrikenVersandPanel {context} {...panel} bereich="zustellung" mitVersandAbschnitt={false} />
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
