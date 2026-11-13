<script lang="ts">
	// Issue #2795 S3b, Teilschritt 1b (AC-2, AC-3, AC-4, AC-8, AC-39/AC-40): zwei Karten Morgen-/
	// Abend-Briefing mit Uhrzeitfeld (frei eintippbar, Viertelstunden-Raster) und Schalter, keine
	// Schnellwahl. Traegt den Anker `#versand` (Sprungziel Uebersicht „Bearbeiten →“, „Setup
	// abschliessen“). Speichert nicht selbst: jede Aenderung geht als neuer Stand an den Reiter.
	import { Switch } from '$lib/components/atoms';
	import UhrzeitFeld from '$lib/components/molecules/UhrzeitFeld.svelte';
	import { t, locale } from '$lib/i18n';
	import { versandSprungNachTick } from '../../shared/versandSprungNachfuehren.ts';
	import { briefingUnterzeilen, zeitFehler, type Kontext, type ZustellungStand } from '../../shared/zustellung-tab/zustellungModell.ts';

	interface Props {
		context: Kontext;
		stand: ZustellungStand;
		onaendern: (neu: ZustellungStand) => void;
		/** Zaehler des Hubs: jede Erhoehung scrollt zu dieser Karte (Sprung `#versand`). */
		versandSprung?: number;
	}
	let { context, stand, onaendern, versandSprung = 0 }: Props = $props();

	const unter = $derived.by(() => (void $locale, briefingUnterzeilen(context)));
	const fehlerMorgen = $derived.by(() => (void $locale, zeitFehler(stand.morgenZeit)));
	const fehlerAbend = $derived.by(() => (void $locale, zeitFehler(stand.abendZeit)));

	let anker = $state<HTMLElement | null>(null);
	$effect(() => {
		if (versandSprung <= 0 || !anker) return;
		const ziel = anker;
		return versandSprungNachTick(ziel);
	});
</script>

<div id="versand" class="zt-zeiten" data-abschnitt="briefing-zeiten" bind:this={anker}>
	{#each [{ slot: 'morgen', titel: $t('zustellung.briefing.morgen'), zeit: stand.morgenZeit, an: stand.morgenAn, fehler: fehlerMorgen, unterzeile: unter.morgen, aria: $t('zustellung.briefing.uhrzeit_morgen') }, { slot: 'abend', titel: $t('zustellung.briefing.abend'), zeit: stand.abendZeit, an: stand.abendAn, fehler: fehlerAbend, unterzeile: unter.abend, aria: $t('zustellung.briefing.uhrzeit_abend') }] as k (k.slot)}
		<div class="zt-karte" data-testid="zustellung-{k.slot}-karte">
			<div class="zt-zeile">
				<div class="zt-text">
					<b>{k.titel}</b>
					<small data-testid="zustellung-{k.slot}-unterzeile">{k.unterzeile}</small>
				</div>
				<div class="zt-bedienung">
					<UhrzeitFeld
						value={k.zeit}
						testid="zustellung-{k.slot}-zeit"
						ariaLabel={k.aria}
						onchange={(hhmm) => onaendern(k.slot === 'morgen' ? { ...stand, morgenZeit: hhmm } : { ...stand, abendZeit: hhmm })}
					/>
					<Switch
						checked={k.an}
						tap
						aria-label={k.titel}
						testid="zustellung-{k.slot}-schalter"
						onchange={(an) => onaendern(k.slot === 'morgen' ? { ...stand, morgenAn: an } : { ...stand, abendAn: an })}
					/>
				</div>
			</div>
			{#if k.fehler}
				<p class="zt-fehler" role="alert" data-testid="zustellung-{k.slot}-zeit-fehler">{k.fehler}</p>
			{/if}
		</div>
	{/each}
</div>

<style>
	.zt-zeiten {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--g-s-4);
		scroll-margin-top: var(--g-size-72px);
	}
	.zt-karte {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.zt-zeile {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-size-10px) var(--g-s-4);
		padding: var(--g-size-14px) var(--g-s-5);
	}
	.zt-text {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-2px);
	}
	.zt-text small {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.zt-bedienung {
		display: flex;
		align-items: center;
		gap: var(--g-s-3);
	}
	.zt-fehler {
		margin: 0;
		padding: 0 var(--g-s-5) var(--g-size-14px);
		font-size: var(--g-size-12-5px);
		color: var(--g-danger);
	}
	@media (max-width: 899px) {
		.zt-zeiten {
			grid-template-columns: 1fr;
		}
	}
</style>
