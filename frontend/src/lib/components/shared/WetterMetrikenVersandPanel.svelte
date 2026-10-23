<script lang="ts">
	// Issue #1743: EIN geteilter Baustein „Wetter-Metriken + Versand" fuer Trip-Hub,
	// Ortsvergleich-Hub und beide Anlege-Seiten (`context="route"|"vergleich"`).
	// Reihenfolge: Wetter-Metriken-Inhalt, darunter der Versand-Abschnitt
	// `<section id="versand">` (Sprungziel `#versand`). Der Baustein haelt KEINE
	// Speicherlogik — beide Inhalte speichern selbst ueber den gemeinsamen
	// saveController (Besitzer 'wetter-metriken' bzw. 'versand', #1743 S1).
	// Trip-Hub: Versand ueber den Wrapper `BriefingScheduleTab` (Gesten-Gate +
	// report_config-Speicherweg); Vergleich und Trip-Anlegen (`createMode`): der
	// EINE `VersandTab` im Abschnitt (Anlegen haelt den Blob per `bind:reportConfig`,
	// kein PUT — persistiert wird erst beim POST der Anlege-Seite).
	import { tick } from 'svelte';
	import type { ComponentProps, Snippet } from 'svelte';
	import type { ReportConfig } from '$lib/types';
	import WeatherMetricsTab from './WeatherMetricsTab.svelte';
	import VersandTab from './VersandTab.svelte';
	import BriefingScheduleTab from '../trip-detail/BriefingScheduleTab.svelte';

	type WetterProps = ComponentProps<typeof WeatherMetricsTab>;
	type VersandProps = ComponentProps<typeof VersandTab>;

	interface Props extends Omit<WetterProps, 'context'> {
		context: 'route' | 'vergleich';
		/** Reiter-Sprung aus dem Versand-Inhalt ("Etappen öffnen →"). Nur route. */
		onJump?: (tab: string) => void;
		/** Aktivierungs-Karte (Pausieren/Aktivieren) im Versand-Abschnitt. Nur vergleich. */
		activation?: Snippet;
		/** Wertprops + Rueckrufe des Versand-Inhalts (`compare/versandPropsAus.ts`). Nur vergleich. */
		versand?: Partial<VersandProps>;
		vergleichTelegramStyle?: 'rich' | 'kurzform';
		/** report_config-Blob der Trip-Anlege-Seite (nur route + createMode). */
		reportConfig?: ReportConfig;
		/** Zaehler: jede Erhoehung scrollt zum Versand-Abschnitt (Sprung `#versand`).
		 *  Der Hub setzt ihn bei jedem Reiterwechsel ohne Anker auf 0 zurueck. */
		versandSprung?: number;
	}

	let {
		context,
		onJump,
		activation,
		versand = {},
		vergleichTelegramStyle = 'rich',
		reportConfig = $bindable(),
		versandSprung = 0,
		...wetter
	}: Props = $props();

	let abschnitt = $state<HTMLElement | null>(null);

	// Sprung zum Versand-Abschnitt erst NACH dem Mount (der Hub mountet den Baustein
	// im Vergleich erst nach der Versand-Hydration — keine Platzhalterwerte im Blick).
	// Massgeblich ist allein der Zaehler des Hubs (nicht die Adresszeile, die im
	// Trip-Hub wegen des asynchronen goto hinterherhinkt); ohne Sprung (0) scrollt
	// auch ein Remount nicht.
	$effect(() => {
		if (versandSprung <= 0 || !abschnitt) return;
		const ziel = abschnitt;
		void tick().then(() => ziel.scrollIntoView?.({ block: 'start' }));
	});
</script>

<WeatherMetricsTab {context} {...wetter} />

<section id="versand" data-testid="versand-abschnitt" class="wmv-versand" bind:this={abschnitt}>
	{#if context === 'route' && !wetter.createMode}
		{#if wetter.trip}
			<BriefingScheduleTab
				trip={wetter.trip}
				onTripUpdate={wetter.onTripUpdate}
				saveController={wetter.saveController}
				{onJump}
			/>
		{/if}
	{:else}
		<VersandTab
			{context}
			{...versand}
			trip={wetter.trip}
			bind:reportConfig
			{onJump}
			{vergleichTelegramStyle}
			{activation}
			preset={wetter.preset}
			saveController={wetter.saveController}
			enqueueHubWrite={wetter.enqueueHubWrite}
			onCompareUpdate={wetter.onCompareUpdate}
			showInfobox={wetter.showInfobox}
		/>
	{/if}
</section>

<style>
	.wmv-versand {
		scroll-margin-top: 72px;
	}
</style>
