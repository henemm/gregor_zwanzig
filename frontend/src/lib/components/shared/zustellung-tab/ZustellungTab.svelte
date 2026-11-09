<script lang="ts">
	// Issue #2794 S3a (Teil-PR 2, Spec feat_2794_s3a_teil2_leiste.md §3): Uebergangsreiter
	// „Zustellung" fuer Trip-Hub und Ortsvergleich-Hub (`context="route"|"vergleich"`).
	// Er nimmt die heutigen Bausteine UNVERAENDERT auf, damit kein Bedienelement
	// verschwindet (16-Punkte-Inventar, AC-7):
	//   1. die Zustellungs-Bloecke der Metrik-Oberflaeche (Layout je Kanal, Stundenverlauf,
	//      Ausblick, Mail-Inhalt, Nacht-Block) ueber den geteilten Baustein mit
	//      `bereich="zustellung"`, darunter der Versand-Abschnitt `<section id="versand">`
	//      (Trip-Hub: BriefingScheduleTab, Vergleich: VersandTab samt Aktivierungs-Karte);
	//   2. den Alarm-Baustein vollstaendig: im Trip ueber die Huelle AlarmeScheduleTab
	//      (AlarmeTab context="route"); im Vergleich rendert der Hub seinen bestehenden
	//      AlarmeTab-Mount (Buendel `alarmePropsAus(...)` im Markup des Hubs) als Snippet
	//      `alarmeBereich` hier hinein — Muster `activation`/`hubActivationCard`.
	// Keine eigene Speicherlogik: alle Bausteine speichern wie vorher selbst (Owner
	// 'wetter-metriken', 'wetter-metriken-report-config', 'versand', 'alarme').
	// Die Wahl haengt am uebergebenen Snippet, nicht an einer neuen Herkunfts-Weiche
	// (Ratsche #2276 S6a).
	import type { ComponentProps, Snippet } from 'svelte';
	import WetterMetrikenVersandPanel from '../WetterMetrikenVersandPanel.svelte';
	import AlarmeScheduleTab from '../../trip-detail/AlarmeScheduleTab.svelte';
	import type { MetricCatalog } from '../../trip-detail/metricsEditor.ts';

	type PanelProps = ComponentProps<typeof WetterMetrikenVersandPanel>;

	interface Props extends Omit<PanelProps, 'context' | 'bereich'> {
		context: 'route' | 'vergleich';
		/** Trip-Hub: der dort geladene Metrik-Katalog fuer die Alarm-Zeilen. */
		metricsCatalog?: MetricCatalog | null;
		/** Vergleichs-Hub: der AlarmeTab-Mount des Hubs (Snippet). */
		alarmeBereich?: Snippet;
	}

	let { context, metricsCatalog = null, alarmeBereich, ...panel }: Props = $props();
</script>

<div class="zustellung-tab" data-testid="zustellung-tab-{context}">
	<WetterMetrikenVersandPanel {context} {...panel} bereich="zustellung" />

	<div class="zustellung-alarme" data-testid="zustellung-alarme">
		{#if alarmeBereich}
			{@render alarmeBereich()}
		{:else if panel.trip}
			<AlarmeScheduleTab trip={panel.trip} onTripUpdate={panel.onTripUpdate} saveController={panel.saveController} {metricsCatalog} />
		{/if}
	</div>
</div>

<style>
	.zustellung-alarme {
		margin-top: 32px;
	}
</style>
