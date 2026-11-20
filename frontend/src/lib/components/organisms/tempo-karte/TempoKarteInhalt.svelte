<script lang="ts">
	// Issue #3196 (ADR-0108 Nr. 2): Organismus der Karte „Fortbewegung + Grundtempo" (Seite:
	// shared/TempoKarte.svelte, ADR-0112). EINE Komponente für Anlegen und Bearbeiten. Auf-/Abstiegsraten
	// folgen dem Grundtempo und sind nirgends sichtbar. Wechsel der Fortbewegung setzt das
	// Grundtempo auf den Vorschlagswert (wechsleFortbewegung). Kein eigenes Speichern:
	// `onchange` meldet den neuen Stand, der Aufrufer speichert (Autosave/ETag-Pfad).
	// Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md (AC-1, AC-4, AC-7, AC-9).
	import type { Fortbewegung, Tempo } from '$lib/types';
	import { FORTBEWEGUNGEN, MIN_GRUNDTEMPO_KMH, MAX_GRUNDTEMPO_KMH, wechsleFortbewegung } from '$lib/utils/naismith';
	import { t, type MessageKey } from '$lib/i18n';

	interface Props {
		tempo: Tempo;
		onchange?: (tempo: Tempo) => void;
	}
	let { tempo, onchange }: Props = $props();

	const NAME: Record<Fortbewegung, MessageKey> = {
		fuss: 'trip.tempo.fuss',
		rad: 'trip.tempo.rad',
		mtb: 'trip.tempo.mtb',
		ski: 'trip.tempo.ski'
	};

	function waehle(f: Fortbewegung): void {
		if (f === tempo.fortbewegung) return;
		onchange?.(wechsleFortbewegung(tempo, f));
	}
	function grundtempo(e: Event): void {
		const v = Number((e.currentTarget as HTMLInputElement).value);
		if (!Number.isFinite(v) || v < MIN_GRUNDTEMPO_KMH || v > MAX_GRUNDTEMPO_KMH) return;
		onchange?.({ ...tempo, grundtempo_kmh: v });
	}
</script>

<div class="tempo-karte" data-testid="tempo-karte">
	<div class="tempo-feld">
		<span class="tempo-label">{$t('trip.tempo.fortbewegung')}</span>
		<div data-slot="segmented" data-variant="kompakt" role="group" aria-label={$t('trip.tempo.fortbewegung')}>
			{#each FORTBEWEGUNGEN as f (f)}
				<button
					type="button"
					data-slot="segmented-item"
					data-active={tempo.fortbewegung === f ? 'true' : 'false'}
					aria-pressed={tempo.fortbewegung === f}
					data-testid="tempo-fortbewegung-{f}"
					onclick={() => waehle(f)}>{$t(NAME[f])}</button
				>
			{/each}
		</div>
	</div>
	<label class="tempo-feld">
		<span class="tempo-label">{$t('trip.tempo.grundtempo')}</span>
		<input
			class="tempo-zahl"
			type="number"
			min={MIN_GRUNDTEMPO_KMH}
			max={MAX_GRUNDTEMPO_KMH}
			step="0.5"
			inputmode="decimal"
			value={tempo.grundtempo_kmh}
			data-testid="tempo-grundtempo"
			onchange={grundtempo}
		/>
		<!-- Handy: Beschriftung nur für Screenreader, die Einheit steht sichtbar hinter der Zahl. -->
		<span class="tempo-einheit" aria-hidden="true">{$t('trip.tempo.einheit')}</span>
	</label>
	<span class="tempo-hinweis">{$t('trip.tempo.hinweis')}</span>
</div>

<style>
	.tempo-karte {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: var(--g-s-4) var(--g-s-5);
		padding: var(--g-size-14px) var(--g-s-5);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	/* Tastaturfokus sichtbar wie beim Segmented als radiogroup (app.css, #2881). */
	.tempo-karte button:focus-visible {
		outline: var(--g-size-2px) solid var(--g-accent);
		outline-offset: calc(-1 * var(--g-size-3px));
	}
	.tempo-feld {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-6px);
	}
	.tempo-label {
		font-size: var(--g-size-12-5px);
		font-weight: 600;
		color: var(--g-ink-2);
	}
	.tempo-zahl {
		width: var(--g-size-120px);
		min-height: var(--g-tap-min);
		padding: 0 var(--g-s-3);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: var(--g-card);
		color: var(--g-ink);
		font: inherit;
	}
	.tempo-hinweis {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
		max-width: var(--g-size-420px);
	}
	.tempo-einheit {
		display: none;
		font-size: var(--g-text-sm);
		color: var(--g-ink-2);
	}
	/* Handy: eine Zeile (Segmente + Zahl + Einheit), damit die Etappen-Liste über der
	   Navigation beginnt (Messung trip-hub-kopf-region-aktivitaet AC-13). Die Beschriftungen
	   bleiben für Screenreader im Baum (weggeschnitten, nicht entfernt); der Hinweis entfällt. */
	@media (max-width: 899px) {
		.tempo-karte {
			flex-wrap: nowrap;
			align-items: center;
			justify-content: space-between;
			gap: var(--g-s-3);
			padding: var(--g-size-10px) var(--g-s-4);
		}
		.tempo-feld {
			position: relative;
		}
		/* Vier Segmente in EINER Reihe neben der Zahl (sonst bricht die Gruppe auf 375 px um). */
		.tempo-karte [data-slot='segmented'] {
			flex-wrap: nowrap;
		}
		.tempo-karte [data-slot='segmented-item'] {
			padding: var(--g-s-1) var(--g-size-6px);
			white-space: nowrap;
		}
		label.tempo-feld {
			flex-direction: row;
			align-items: center;
		}
		.tempo-label {
			position: absolute;
			clip-path: inset(50%);
			overflow: hidden;
			white-space: nowrap;
		}
		.tempo-hinweis {
			display: none;
		}
		.tempo-einheit {
			display: inline;
		}
		.tempo-zahl {
			width: var(--g-size-56px);
			padding: 0 var(--g-size-6px);
		}
	}
</style>
