<script lang="ts">
	// Issue #3320 (AC-8) — ein Bild der Funktionsseiten: eigene Datei je
	// Sprache, feste Masse (kein Layoutsprung), lazy Loading, Alt-Text aus dem Katalog.
	// Issue #3319 (AC-13) — mit `onoeffnen` (Unterseiten) ist das Bild eine Schaltflaeche
	// (Klick, Enter, Leertaste), die die Bildergalerie der Seite oeffnet; `onoeffnen`
	// bekommt die Schaltflaeche, damit der Fokus nach dem Schliessen dorthin zurueckkehrt.
	// Ohne `onoeffnen` (Vorschaubild in der Kachel der Uebersicht, die selbst ein Link
	// ist) ein reines, nicht interaktives <img> — kein <button> im <a>.
	import { locale, t } from '$lib/i18n';
	import { bildQuelle, type Bild } from './inhalt';
	import { GALERIE_TEXTE } from './galerie';

	let {
		bild,
		beschriftung = true,
		onoeffnen
	}: { bild: Bild; beschriftung?: boolean; onoeffnen?: (ausloeser: HTMLButtonElement) => void } = $props();

	const q = $derived(bildQuelle(bild.name, $locale === 'en' ? 'en' : 'de'));
	const alt = $derived($t(bild.alt));
</script>

<figure class="bild">
	{#if onoeffnen}
		<button
			type="button"
			class="oeffnen"
			data-testid="bild-oeffnen"
			data-bild={bild.name}
			aria-haspopup="dialog"
			aria-label={$t(GALERIE_TEXTE.oeffnen, { bild: alt })}
			onclick={(e) => onoeffnen(e.currentTarget)}
		><img src={q.src} {alt} width={q.width} height={q.height} loading="lazy" decoding="async" /></button>
	{:else}
		<img src={q.src} {alt} width={q.width} height={q.height} loading="lazy" decoding="async" />
	{/if}
	{#if beschriftung}
		<figcaption>{$t(bild.caption)}</figcaption>
	{/if}
</figure>

<style>
	.bild {
		margin: 0;
		min-width: 0;
	}
	.oeffnen {
		display: block;
		width: 100%;
		padding: 0;
		margin: 0;
		border: 0;
		background: none;
		cursor: zoom-in;
		border-radius: var(--g-r-3);
	}
	.oeffnen:focus-visible {
		outline: var(--g-size-2px) solid var(--g-ink);
		outline-offset: var(--g-size-2px);
	}
	img {
		display: block;
		width: 100%;
		height: auto;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.oeffnen:hover img {
		border-color: var(--g-ink);
	}
	figcaption {
		margin-top: var(--g-size-6px);
		font-size: var(--g-text-sm);
		color: var(--g-ink-2);
	}
</style>
