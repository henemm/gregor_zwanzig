<script lang="ts">
	// Issue #2913 Teil 2 (AC-14, K-4): Lade-Platzhalter (Mockup Fassung 3, `.skel`).
	// Für Hilfstechnik ein Status „wird geladen“: role="status", aria-busy, aria-label vom Aufrufer
	// (aus dessen Katalog); ohne Aufrufer-Text der Standardtext aus dem Allgemein-Katalog.
	// Maße und Farben nur aus Tokens (app.css, [data-slot="skelett"]); Breiten der Zeilen in %.
	import { t } from '$lib/i18n';

	interface Props {
		/** Beschriftung für Hilfstechnik (Katalogtext des Aufrufers). */
		label?: string;
		/** Breite je Platzhalter-Zeile in Prozent. */
		breiten?: number[];
		testid?: string;
	}
	let { label, breiten = [72, 90, 55, 80, 64], testid }: Props = $props();
</script>

<div data-slot="skelett" role="status" aria-busy="true" aria-label={label ?? $t('bausteine.skelett.laedt')} data-testid={testid}>
	{#each breiten as breite, i (i)}
		<span data-slot="skelett-zeile" aria-hidden="true" style:width="{breite}%"></span>
	{/each}
</div>
