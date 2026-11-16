<script lang="ts">
	// #3047 N2: sichtbarer Hinweis bei bewusst leerer Grundauswahl -- geteilt von
	// Trip (alle Metriken `enabled:false`) und Ortsvergleich (`active_metrics: []`).
	// Die Mail zeigt dann keine Metrik, Stundenverlauf und Ausblick entfallen;
	// der Editor sagt das, statt leere Listen kommentarlos stehen zu lassen.
	// Gestaltung wie die Kanal-Warnbox der Zustellung (KanalTabelle.svelte).
	// Molecule (ADR-0112): Baustein mit Token-Stilen, eingehaengt im Wetter-Reiter.
	import { t } from '$lib/i18n';

	interface Props {
		/** Grundauswahl der Flaeche; `null` = nie eingestellt (kein Hinweis). */
		grundauswahl: readonly string[] | null;
	}
	let { grundauswahl }: Props = $props();
</script>

{#if grundauswahl !== null && grundauswahl.length === 0}
	<div class="gl-warnbox" role="alert" data-testid="grundauswahl-leer-hinweis">
		<b>{$t('wertebereiche.grundauswahl.leer_titel')}</b>
		<span>{$t('wertebereiche.grundauswahl.leer_text')}</span>
	</div>
{/if}

<style>
	.gl-warnbox {
		display: flex;
		flex-wrap: wrap;
		gap: var(--g-s-1);
		padding: var(--g-s-3) var(--g-s-4);
		border: 1px solid var(--g-danger);
		border-radius: var(--g-r-3);
		background: var(--g-danger-bg);
		color: var(--g-danger-fg);
		font-size: var(--g-size-13px);
		margin-top: var(--g-s-3);
	}
</style>
