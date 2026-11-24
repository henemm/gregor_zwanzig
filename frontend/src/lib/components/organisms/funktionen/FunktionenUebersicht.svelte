<script lang="ts">
	// Issue #3319 / #3320 — Inhalt der oeffentlichen Funktionsuebersicht /funktionen.
	// Spec: docs/specs/modules/oeffentliche_doku_3319.md (v1.1, „Seitenstruktur“)
	// Aufbau nach gaengiger Praxis fuer Produkt-Doku: Einleitung, „In drei Schritten“,
	// je Unterseite eine Themenkachel (Bild, Titel, ein Satz, Link), Aufruf zur
	// Registrierung. Keine Nutzerdaten, kein API-Aufruf. Alle Texte aus dem Katalog.
	import { Eyebrow } from '$lib/components/atoms';
	import { t, type MessageKey } from '$lib/i18n';
	import { FUNKTIONEN_SEITEN, funktionenPfad } from '$lib/funktionen_seiten';
	import { kachelBild, seitenKachel, seitenTitel } from './inhalt';
	import FunktionenKopf from './FunktionenKopf.svelte';
	import FunktionsBild from './FunktionsBild.svelte';
	import Registrierungsaufruf from './Registrierungsaufruf.svelte';

	let { oeffentlich = true }: { oeffentlich?: boolean } = $props();

	const SCHRITTE: readonly { titel: MessageKey; text: MessageKey }[] = [
		{ titel: 'funktionen.schritte.eins.titel', text: 'funktionen.schritte.eins.text' },
		{ titel: 'funktionen.schritte.zwei.titel', text: 'funktionen.schritte.zwei.text' },
		{ titel: 'funktionen.schritte.drei.titel', text: 'funktionen.schritte.drei.text' }
	];
</script>

<div class="rahmen" data-testid="funktionen" data-oeffentlich={oeffentlich ? 'ja' : 'nein'}>
	<FunktionenKopf />

	<main class="inhalt">
		<header class="einleitung">
			<Eyebrow>{$t('funktionen.eyebrow')}</Eyebrow>
			<h1>{$t('funktionen.titel')}</h1>
			<p class="lead">{$t('funktionen.lead')}</p>
		</header>

		<section class="schritte" aria-labelledby="schritte-titel">
			<h2 id="schritte-titel">{$t('funktionen.schritte.titel')}</h2>
			<ol>
				{#each SCHRITTE as s, i (s.titel)}
					<li>
						<span class="nr" aria-hidden="true">{i + 1}</span>
						<div>
							<h3>{$t(s.titel)}</h3>
							<p>{$t(s.text)}</p>
						</div>
					</li>
				{/each}
			</ol>
		</section>

		<section class="themen" aria-labelledby="themen-titel">
			<h2 id="themen-titel">{$t('funktionen.themen.titel')}</h2>
			<ul class="raster">
				{#each FUNKTIONEN_SEITEN as s (s.slug)}
					{@const b = kachelBild(s.inventar)}
					<li>
						<a class="kachel" data-testid="kachel" href={funktionenPfad(s.slug)}>
							{#if b}
								<!-- AC-13: Vorschaubild ist Teil des Links (keine Galerie auf der Uebersicht) -->
								<FunktionsBild bild={b} beschriftung={false} />
							{/if}
							<span class="kachel-text">
								<span class="kachel-titel">{$t(seitenTitel(s.slug))}</span>
								<span class="kachel-satz">{$t(seitenKachel(s.slug))}</span>
							</span>
						</a>
					</li>
				{/each}
			</ul>
		</section>

		<Registrierungsaufruf />

		<p class="hinweis">{$t('start.footer.hinweis')}</p>
		<a class="zurueck" href="/">{$t('funktionen.zur_startseite')}</a>
	</main>
</div>

<style>
	.rahmen {
		max-width: var(--g-size-1100px);
		margin: 0 auto;
		padding: var(--g-s-5) var(--g-s-4) var(--g-s-12);
		display: flex;
		flex-direction: column;
		gap: var(--g-s-6);
		min-width: 0;
	}
	.inhalt {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-8);
		min-width: 0;
	}
	h1 {
		font-size: clamp(var(--g-text-3xl), 6vw, var(--g-text-4xl));
		line-height: 1.15;
		margin: var(--g-s-2) 0;
		color: var(--g-ink);
	}
	h2 {
		font-size: var(--g-text-2xl);
		line-height: 1.3;
		font-weight: 600;
		margin: 0 0 var(--g-s-4);
		color: var(--g-ink);
	}
	h3 {
		margin: var(--g-size-2px) 0 var(--g-s-1);
		font-size: var(--g-text-16px);
		font-weight: 600;
		color: var(--g-ink);
	}
	.lead {
		max-width: 62ch;
		margin: 0;
		font-size: var(--g-text-lg);
		line-height: 1.55;
		color: var(--g-ink-2);
	}
	.schritte ol {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--g-s-3);
	}
	.schritte li {
		display: flex;
		gap: var(--g-s-3);
		align-items: flex-start;
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-4);
		padding: var(--g-s-4);
	}
	.nr {
		flex: none;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: var(--g-s-8);
		height: var(--g-s-8);
		border-radius: var(--g-r-pill);
		background: var(--g-ink);
		color: var(--g-card);
		font-weight: 700;
	}
	.schritte p {
		margin: 0;
		color: var(--g-ink-2);
		line-height: 1.5;
	}
	.raster {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--g-s-4);
	}
	.kachel {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
		height: 100%;
		padding: var(--g-s-3);
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-4);
		color: var(--g-ink);
		text-decoration: none;
		min-width: 0;
	}
	.kachel:hover {
		border-color: var(--g-ink);
	}
	.kachel:focus-visible {
		outline: var(--g-size-2px) solid var(--g-ink);
		outline-offset: var(--g-size-2px);
	}
	.kachel :global(img) {
		aspect-ratio: 16 / 10;
		object-fit: cover;
		object-position: top left;
	}
	.kachel-text {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
	}
	.kachel-titel {
		font-size: var(--g-text-lg);
		font-weight: 600;
		text-decoration: underline;
	}
	.kachel-satz {
		color: var(--g-ink-2);
		line-height: 1.5;
	}
	.hinweis {
		margin: 0;
		font-size: var(--g-text-sm);
		color: var(--g-ink-2);
	}
	.zurueck {
		color: var(--g-ink);
		font-weight: 600;
		text-decoration: underline;
	}
	@media (min-width: 640px) {
		.raster {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (min-width: 900px) {
		.schritte ol,
		.raster {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
	}
</style>
