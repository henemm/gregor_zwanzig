<script lang="ts">
	// Issue #2913 Teil 2 (AC-15, K-2): generische Einstellungszeile (Mockup Fassung 3, `.lrow`).
	// Links Titel und optionaler Hinweis, rechts der Bereich für das Bedienelement (Snippet).
	// Texte kommen als Props aus dem Katalog des Aufrufers. Trip und Orts-Briefing gleich.
	// Issue #3007 (AC-2): optional klickbar (`onclick`): dann role="button", tabindex="0",
	// aria-expanded (`offen`), Enter und Leertaste lösen den Klick aus. Optional ein Element vor
	// dem Text (`vorne`, z. B. Ziehgriff) und weitere Attribute (`data-*`) am Zeilen-Element.
	// Ohne diese Optionen ist die Zeile unverändert.
	import type { Snippet } from 'svelte';

	interface Props {
		titel: string;
		hinweis?: string;
		testid?: string;
		/** Testid am Hinweis (z. B. Zähler, der in Prüfungen gelesen wird). */
		hinweisTestid?: string;
		/** #3007: macht die Zeile klickbar (Tastatur: Enter, Leertaste). */
		onclick?: () => void;
		/** #3007: Aufklapp-Zustand der klickbaren Zeile (aria-expanded). */
		offen?: boolean;
		/** #3007: Element vor dem Text (z. B. Ziehgriff). */
		vorne?: Snippet;
		children?: Snippet;
		[attr: `data-${string}`]: unknown;
	}
	let { titel, hinweis, testid, hinweisTestid, onclick, offen = false, vorne, children, ...attrs }: Props = $props();

	function taste(e: KeyboardEvent): void {
		if (!onclick || e.target !== e.currentTarget) return;
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			onclick();
		}
	}
</script>

<!-- role="button" und tabindex nur mit onclick (dynamisch), Tastatur über `taste` (AC-2). -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_static_element_interactions -->
<div
	class="ez"
	class:ez-klickbar={!!onclick}
	class:ez-mit-vorne={!!vorne}
	data-slot="einstellungszeile"
	data-testid={testid}
	{...attrs}
	role={onclick ? 'button' : undefined}
	tabindex={onclick ? 0 : undefined}
	aria-expanded={onclick ? (offen ? 'true' : 'false') : undefined}
	{onclick}
	onkeydown={onclick ? taste : undefined}
>
	{#if vorne}<div class="ez-vorne">{@render vorne()}</div>{/if}
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
	.ez-klickbar {
		cursor: pointer;
	}
	.ez-klickbar:hover {
		background: var(--g-paper-deep);
	}
	.ez-klickbar:focus-visible {
		outline: var(--g-size-2px) solid var(--g-accent);
		outline-offset: calc(-1 * var(--g-size-2px));
	}
	.ez-vorne {
		display: flex;
		align-items: center;
		flex-shrink: 0;
	}
	.ez-mit-vorne .ez-text {
		flex: 1;
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
