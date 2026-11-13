<script lang="ts">
	// Issue #2795 S3b, Teilschritt 1b (AC-9, AC-10): Laufzeit. Trip: Satz aus den Etappendaten und
	// „Etappen öffnen →“ (Sprung in den Reiter Etappen). Orte: „Bis auf Weiteres · Bis Datum“ mit
	// Datumsfeld (`end_date`, leer = bis auf Weiteres), je Wahl ein eigener Erklaersatz.
	// Speichert nicht selbst: jede Aenderung geht als neuer Stand an den Reiter.
	import { untrack } from 'svelte';
	import { Btn } from '$lib/components/atoms';
	import DatumFeld from '$lib/components/molecules/DatumFeld.svelte';
	import { t, locale } from '$lib/i18n';
	import type { Stage } from '$lib/types';
	import { laufzeitOrte, laufzeitTrip, type Kontext, type ZustellungStand } from '../../shared/zustellung-tab/zustellungModell.ts';

	interface Props {
		context: Kontext;
		stand: ZustellungStand;
		onaendern: (neu: ZustellungStand) => void;
		/** Nur route: Etappen des Trips (Quelle der Daten). */
		stages?: Stage[];
		/** Nur route: Reiterwechsel („Etappen öffnen →“). */
		onJump?: (tab: string) => void;
	}
	let { context, stand, onaendern, stages = [], onJump }: Props = $props();

	// Kontext-Unterschied als Daten (Ratsche context_herkunft_zweige_eingefroren): Trip zeigt die
	// Laufzeit aus den Etappen, Orte waehlen selbst (Segment + Datum).
	const ART: Record<Kontext, 'etappen' | 'enddatum'> = { route: 'etappen', vergleich: 'enddatum' };
	const art = $derived(ART[context]);

	// Orte: die Wahl kann „Bis Datum“ sein, bevor ein Datum eingetragen ist.
	let wahl = $state<'offen' | 'datum'>(untrack(() => laufzeitOrte(stand.endDate).wahl));

	const tripSatz = $derived.by(() => (void $locale, art === 'etappen' ? laufzeitTrip({ stages }) : ''));

	function waehle(neu: 'offen' | 'datum'): void {
		wahl = neu;
		if (neu === 'offen' && stand.endDate) onaendern({ ...stand, endDate: null });
	}
</script>

<div class="zt-karte" data-abschnitt="laufzeit" data-testid="zustellung-laufzeit">
	<div class="zt-zeile">
		<div class="zt-text">
			<b>{$t('zustellung.laufzeit.titel')}</b>
			{#if art === 'etappen'}
				<small data-testid="zustellung-laufzeit-satz">{tripSatz}</small>
			{:else}
				<small data-testid="zustellung-laufzeit-satz">{$t(wahl === 'datum' ? 'zustellung.laufzeit.datum_satz' : 'zustellung.laufzeit.offen_satz')}</small>
			{/if}
		</div>
		<div class="zt-bedienung">
			{#if art === 'etappen'}
				<Btn variant="ghost" size="sm" data-testid="zustellung-etappen-oeffnen" onclick={() => onJump?.('etappen')}>
					{$t('zustellung.laufzeit.etappen_oeffnen')}
				</Btn>
			{:else}
				<div class="zt-segment" role="group" aria-label={$t('zustellung.laufzeit.titel')}>
					<Btn variant={wahl === 'offen' ? 'primary' : 'ghost'} size="sm" aria-pressed={wahl === 'offen'} data-testid="zustellung-laufzeit-offen" onclick={() => waehle('offen')}>
						{$t('zustellung.laufzeit.offen')}
					</Btn>
					<Btn variant={wahl === 'datum' ? 'primary' : 'ghost'} size="sm" aria-pressed={wahl === 'datum'} data-testid="zustellung-laufzeit-bis-datum" onclick={() => waehle('datum')}>
						{$t('zustellung.laufzeit.bis_datum')}
					</Btn>
				</div>
				{#if wahl === 'datum'}
					<div class="zt-datum">
						<DatumFeld
							value={stand.endDate ?? ''}
							testid="zustellung-laufzeit-datum"
							ariaLabel={$t('zustellung.laufzeit.enddatum')}
							onchange={(iso) => onaendern({ ...stand, endDate: iso || null })}
						/>
					</div>
				{/if}
			{/if}
		</div>
	</div>
</div>

<style>
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
		max-width: 60ch;
	}
	.zt-text small {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.zt-bedienung {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--g-s-3);
	}
	.zt-segment {
		display: inline-flex;
		gap: var(--g-s-1);
	}
	.zt-datum {
		width: var(--g-size-160px);
	}
</style>
