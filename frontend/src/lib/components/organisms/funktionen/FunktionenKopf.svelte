<script lang="ts">
	// Issue #3319 (AC-6/AC-11) — Seitenkopf der Funktionsseiten: Logo und
	// Sprachumschalter als Banner AUSSERHALB von <main> (die Markenschrift ist als
	// Logo von der Kontrastpflicht ausgenommen; der Inhalt in <main> erfuellt WCAG-AA).
	// Issue #3337 — Angemeldete sehen statt des (fuer sie wirkungslosen) Umschalters
	// einen Hinweis mit Link zur Sprachwahl im Konto; Besucher ohne Anmeldung behalten
	// den Umschalter. Anmeldestatus nur aus den Layout-Daten (`page.data.userId`).
	// Spec: docs/specs/modules/sprachumschalter_angemeldet_3337.md
	import { page } from '$app/state';
	import { t } from '$lib/i18n';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
	import SprachUmschalter from '$lib/components/ui/SprachUmschalter.svelte';

	const angemeldet = $derived(Boolean(page.data?.userId));
</script>

<header class="kopf">
	<Wordmark size="md" />
	{#if angemeldet}
		<p class="sprach-hinweis" data-testid="sprach-hinweis">
			{$t('konto.sprache.hinweis_angemeldet')}
			<a href="/account#sprache">{$t('konto.sprache.hinweis_link')}</a>
		</p>
	{:else}
		<SprachUmschalter />
	{/if}
</header>

<style>
	.kopf {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-s-3);
	}
	/* Hoher Kontrast (Design-Leitprinzip): Primaertext-Tinte, kein gedaempftes Token. */
	.sprach-hinweis {
		margin: 0;
		font-size: 14px;
		color: var(--g-ink);
	}
	.sprach-hinweis a {
		color: var(--g-ink);
		text-decoration: underline;
	}
	.sprach-hinweis a:focus-visible {
		outline: 2px solid var(--g-accent);
		outline-offset: 2px;
	}
</style>
