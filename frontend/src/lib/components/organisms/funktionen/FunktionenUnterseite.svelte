<script lang="ts">
	// Issue #3319 / #3320 — Inhalt einer Funktions-Unterseite /funktionen/<slug>.
	// Spec: docs/specs/modules/oeffentliche_doku_3319.md (v1.1, AC-6/AC-8/AC-10/AC-12)
	// Brotkrumen, Titel mit Einleitung, je Inventarpunkt ein Abschnitt mit
	// Zwischenueberschrift und Bildern, Level-Hinweis, Themen-Navigation (Desktop
	// seitlich, Handy unter dem Inhalt), Zurueck/Weiter, Aufruf zur Registrierung.
	// Welche Inventarpunkte hier stehen, legt allein $lib/funktionen_seiten fest.
	import { Eyebrow } from '$lib/components/atoms';
	import { t } from '$lib/i18n';
	import {
		FUNKTIONEN_SEITEN,
		FUNKTIONEN_UEBERSICHT,
		funktionenPfad,
		funktionenSeite,
		type FunktionenSlug
	} from '$lib/funktionen_seiten';
	import { INVENTAR, seitenEinleitung, seitenTitel } from './inhalt';
	import FunktionenKopf from './FunktionenKopf.svelte';
	import FunktionsBild from './FunktionsBild.svelte';
	import Befehlsliste from './Befehlsliste.svelte';
	import ThemenNavigation from './ThemenNavigation.svelte';
	import Registrierungsaufruf from './Registrierungsaufruf.svelte';
	import LevelTabelleInhalt from './LevelTabelleInhalt.svelte';
	import Bildergalerie from './Bildergalerie.svelte';
	import { galerieBilder } from './galerie';

	let { slug, oeffentlich = true }: { slug: FunktionenSlug; oeffentlich?: boolean } = $props();

	const index = $derived(FUNKTIONEN_SEITEN.findIndex((s) => s.slug === slug));
	const seite = $derived(funktionenSeite(slug) ?? FUNKTIONEN_SEITEN[0]);
	const zurueck = $derived(index > 0 ? FUNKTIONEN_SEITEN[index - 1] : undefined);
	const weiter = $derived(index >= 0 && index < FUNKTIONEN_SEITEN.length - 1 ? FUNKTIONEN_SEITEN[index + 1] : undefined);
	const titel = $derived($t(seitenTitel(seite.slug)));
	// AC-13: Galerie ueber die Bilder dieser Seite, in Seitenreihenfolge.
	const bilder = $derived(galerieBilder(seite.slug));
	let galerieIndex = $state<number | null>(null);
	let ausloeser = $state<HTMLElement | null>(null);
	function oeffnen(name: string, knopf: HTMLButtonElement): void {
		ausloeser = knopf;
		galerieIndex = Math.max(0, bilder.findIndex((b) => b.name === name));
	}
</script>

<div class="rahmen" data-testid="funktionen-unterseite" data-oeffentlich={oeffentlich ? 'ja' : 'nein'}>
	<FunktionenKopf />

	<nav class="brotkrumen" data-testid="brotkrumen" aria-label={$t('funktionen.brotkrumen.label')}>
		<ol>
			<li><a href={FUNKTIONEN_UEBERSICHT}>{$t('funktionen.brotkrumen.uebersicht')}</a></li>
			<li><span aria-current="page">{titel}</span></li>
		</ol>
	</nav>

	<div class="gitter">
		<main class="inhalt">
			<header>
				<Eyebrow>{$t('funktionen.eyebrow')}</Eyebrow>
				<h1>{titel}</h1>
				<p class="lead">{$t(seitenEinleitung(seite.slug))}</p>
			</header>

			{#each seite.inventar as id (id)}
				{@const a = INVENTAR[id]}
				<section class="abschnitt" data-inventar={id} aria-labelledby="titel-{id}">
					<h2 id="titel-{id}">{$t(a.titel)}</h2>
					{#each a.absaetze as p (p)}
						<p>{$t(p)}</p>
					{/each}
					{#if a.verfuegbar}
						<p class="verfuegbar"><strong>{$t('funktionen.verfuegbar.label')}</strong> {$t(a.verfuegbar)}</p>
					{/if}
					{#if id === 'befehle'}
						<Befehlsliste />
					{/if}
					{#if a.bilder.length > 0}
						<div class="bilder" class:bilder--mehrere={a.bilder.length > 1}>
							{#each a.bilder as b (b.name)}
								<FunktionsBild bild={b} onoeffnen={(k) => oeffnen(b.name, k)} />
							{/each}
						</div>
					{/if}
				</section>
			{/each}

			{#if seite.slug === 'level'}
				<div class="abschnitt" data-testid="level-abschnitt">
					<h2>{$t('funktionen.level.tabelle.titel')}</h2>
					<LevelTabelleInhalt umfang="voll" />
					<p class="nach-tabelle">{$t('funktionen.level.text')}</p>
				</div>
				<div class="abschnitt">
					<h2>{$t('funktionen.level.wechsel.titel')}</h2>
					<p>{$t('funktionen.level.wechsel.text')}</p>
				</div>
			{/if}

			<nav class="blaettern" aria-label={$t('funktionen.blaettern.label')}>
				{#if zurueck}
					<a class="karte" data-testid="seite-zurueck" href={funktionenPfad(zurueck.slug)}>
						<span class="richtung"><span aria-hidden="true">←</span> {$t('funktionen.blaettern.zurueck')}</span>
						<span class="ziel">{$t(seitenTitel(zurueck.slug))}</span>
					</a>
				{/if}
				{#if weiter}
					<a class="karte karte--weiter" data-testid="seite-weiter" href={funktionenPfad(weiter.slug)}>
						<span class="richtung">{$t('funktionen.blaettern.weiter')} <span aria-hidden="true">→</span></span>
						<span class="ziel">{$t(seitenTitel(weiter.slug))}</span>
					</a>
				{/if}
			</nav>

			<Registrierungsaufruf />

			<a class="zurueck-start" href="/">{$t('funktionen.zur_startseite')}</a>
		</main>

		<aside class="seitenleiste">
			<ThemenNavigation aktuell={seite.slug} />
		</aside>
	</div>
</div>

<Bildergalerie {bilder} bind:index={galerieIndex} {ausloeser} />

<style>
	.rahmen {
		max-width: var(--g-size-1100px);
		margin: 0 auto;
		padding: var(--g-s-5) var(--g-s-4) var(--g-s-12);
		display: flex;
		flex-direction: column;
		gap: var(--g-s-5);
		min-width: 0;
	}
	.brotkrumen ol {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: var(--g-size-6px);
		font-size: var(--g-text-md);
		color: var(--g-ink-2);
	}
	.brotkrumen li + li::before {
		content: '›';
		margin-right: var(--g-size-6px);
	}
	.brotkrumen a {
		color: var(--g-ink);
		text-decoration: underline;
	}
	.brotkrumen [aria-current='page'] {
		color: var(--g-ink);
		font-weight: 600;
	}
	.gitter {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--g-s-6);
	}
	.inhalt {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-5);
		min-width: 0;
	}
	h1 {
		font-size: clamp(var(--g-text-3xl), 6vw, var(--g-text-4xl));
		line-height: 1.15;
		margin: var(--g-s-2) 0;
		color: var(--g-ink);
	}
	.lead {
		max-width: 62ch;
		margin: 0;
		font-size: var(--g-text-lg);
		line-height: 1.55;
		color: var(--g-ink-2);
	}
	.abschnitt {
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-4);
		padding: var(--g-s-5);
		min-width: 0;
	}
	h2 {
		font-size: var(--g-text-xl);
		line-height: 1.3;
		font-weight: 600;
		margin: 0 0 var(--g-s-3);
		color: var(--g-ink);
	}
	.abschnitt p {
		color: var(--g-ink-2);
		line-height: 1.6;
		margin: 0 0 var(--g-s-3);
		max-width: 70ch;
		overflow-wrap: break-word;
	}
	.abschnitt .verfuegbar {
		padding: var(--g-s-2) var(--g-s-3);
		border-left: var(--g-size-3px) solid var(--g-ink);
		background: var(--g-card-alt);
	}
	.verfuegbar strong {
		color: var(--g-ink);
	}
	.abschnitt .nach-tabelle {
		margin-top: var(--g-s-3);
	}
	.bilder {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--g-s-4);
		margin-top: var(--g-s-4);
	}
	.blaettern {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: var(--g-s-3);
	}
	.karte {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
		padding: var(--g-s-4);
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-4);
		color: var(--g-ink);
		text-decoration: none;
		min-width: 0;
	}
	.karte:hover {
		border-color: var(--g-ink);
	}
	.karte:focus-visible {
		outline: var(--g-size-2px) solid var(--g-ink);
		outline-offset: var(--g-size-2px);
	}
	.karte--weiter {
		text-align: right;
		grid-column: -2 / -1;
	}
	.richtung {
		font-size: var(--g-text-sm);
		color: var(--g-ink-2);
	}
	.ziel {
		font-size: var(--g-text-lg);
		font-weight: 600;
		text-decoration: underline;
	}
	.zurueck-start {
		color: var(--g-ink);
		font-weight: 600;
		text-decoration: underline;
	}
	@media (min-width: 640px) {
		.blaettern,
		.bilder--mehrere {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (min-width: 960px) {
		.gitter {
			grid-template-columns: minmax(var(--g-size-180px), 22%) minmax(0, 1fr);
			align-items: start;
		}
		.seitenleiste {
			grid-column: 1;
			grid-row: 1;
			position: sticky;
			top: var(--g-s-4);
		}
		.inhalt {
			grid-column: 2;
			grid-row: 1;
		}
	}
</style>
