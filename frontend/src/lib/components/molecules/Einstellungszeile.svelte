<script lang="ts">
	// Issue #2913 Teil 2 (AC-15, K-2): generische Einstellungszeile (Mockup Fassung 3, `.lrow`).
	// Links Titel und optionaler Hinweis, rechts der Bereich für das Bedienelement (Snippet).
	// Texte kommen als Props aus dem Katalog des Aufrufers. Trip und Orts-Briefing gleich.
	import type { Snippet } from 'svelte';

	interface Props {
		titel: string;
		hinweis?: string;
		testid?: string;
		/** Testid am Hinweis (z. B. Zähler, der in Prüfungen gelesen wird). */
		hinweisTestid?: string;
		children?: Snippet;
	}
	let { titel, hinweis, testid, hinweisTestid, children }: Props = $props();
</script>

<div class="ez" data-slot="einstellungszeile" data-testid={testid}>
	<div class="ez-text">
		<b>{titel}</b>
		{#if hinweis}<small data-slot="einstellungszeile-hinweis" data-testid={hinweisTestid}>{hinweis}</small>{/if}
	</div>
	<div class="ez-bedienung" data-slot="einstellungszeile-bedienung">
		{@render children?.()}
	</div>
</div>

<style>
	.ez {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-size-10px) var(--g-s-4);
		padding: var(--g-size-14px) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
	}
	.ez:first-child {
		border-top: 0;
	}
	.ez-text {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-2px);
		min-width: 0;
	}
	.ez-text b {
		font-size: var(--g-size-14px);
		font-weight: 600;
		color: var(--g-ink);
	}
	.ez-text small {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.ez-bedienung {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--g-s-3);
	}
	@media (max-width: 899px) {
		.ez {
			padding: var(--g-size-14px) var(--g-s-4);
		}
	}
</style>
