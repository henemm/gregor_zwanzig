<script lang="ts">
	// Issue #3319 (AC-12) — Themen-Navigation der Funktions-Unterseiten: alle
	// Unterseiten aus der Seitenliste, die aktuelle mit aria-current="page".
	// Desktop: Spalte links neben dem Inhalt; Handy: Liste unter dem Inhalt.
	import { t } from '$lib/i18n';
	import { FUNKTIONEN_SEITEN, funktionenPfad, type FunktionenSlug } from '$lib/funktionen_seiten';
	import { seitenTitel } from './inhalt';

	let { aktuell }: { aktuell: FunktionenSlug } = $props();
</script>

<nav class="themen" data-testid="themen-navigation" aria-label={$t('funktionen.navigation.label')}>
	<p class="kopf">{$t('funktionen.themen.titel')}</p>
	<ul>
		{#each FUNKTIONEN_SEITEN as s (s.slug)}
			<li>
				<a href={funktionenPfad(s.slug)} aria-current={s.slug === aktuell ? 'page' : undefined}
					>{$t(seitenTitel(s.slug))}</a
				>
			</li>
		{/each}
	</ul>
</nav>

<style>
	.themen {
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-4);
		padding: var(--g-s-3);
	}
	.kopf {
		margin: 0 0 var(--g-s-2) var(--g-s-2);
		font-size: var(--g-text-12px);
		font-weight: 600;
		letter-spacing: var(--g-size-0-08em);
		text-transform: uppercase;
		color: var(--g-ink-2);
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: var(--g-size-2px);
	}
	a {
		display: block;
		padding: var(--g-s-2) var(--g-s-3);
		border-left: var(--g-size-3px) solid transparent;
		border-radius: var(--g-r-2);
		color: var(--g-ink);
		text-decoration: none;
		font-size: var(--g-text-md);
		line-height: 1.3;
	}
	a:hover {
		background: var(--g-card-alt);
		text-decoration: underline;
	}
	a:focus-visible {
		outline: var(--g-size-2px) solid var(--g-ink);
		outline-offset: var(--g-size-2px);
	}
	a[aria-current='page'] {
		border-left-color: var(--g-ink);
		background: var(--g-card-alt);
		font-weight: 600;
	}
</style>
