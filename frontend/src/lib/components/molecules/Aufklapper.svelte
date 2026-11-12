<script lang="ts">
	// Issue #2913 Scheibe (c) (AC-4): Aufklapper (Mockup Fassung 3, `details.adv`, CSS Z.164–167).
	// Natives <details>/<summary>: Titel links, „＋“ zugeklappt bzw. „－“ aufgeklappt rechts;
	// aria-expanded am <summary> folgt dem Zustand. Der Inhalt steht immer im DOM (das native
	// <details> blendet ihn zugeklappt aus). Texte kommen als Props aus dem Katalog des Aufrufers.
	// Trip und Orts-Briefing gleich; wiederverwendet in Scheiben (d)/(e).
	import { untrack, type Snippet } from 'svelte';

	interface Props {
		titel: string;
		/** Startzustand (Default zu). */
		offen?: boolean;
		/** Testid am <details>. */
		testid?: string;
		/** Testid am <summary>. */
		summaryTestid?: string;
		children: Snippet;
	}
	let { titel, offen = false, testid, summaryTestid, children }: Props = $props();

	let auf = $state(untrack(() => offen));
</script>

<details class="aufklapper" data-slot="aufklapper" data-testid={testid} bind:open={auf}>
	<summary data-testid={summaryTestid} aria-expanded={auf ? 'true' : 'false'}>
		<span>{titel}</span>
		<span class="aufklapper-zeichen" aria-hidden="true">{auf ? '－' : '＋'}</span>
	</summary>
	{@render children()}
</details>

<style>
	.aufklapper {
		border-top: 1px solid var(--g-rule-soft);
	}
	.aufklapper:first-child {
		border-top: 0;
	}
	.aufklapper summary {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-s-3);
		min-height: var(--g-tap-min);
		box-sizing: border-box;
		padding: var(--g-size-14px) var(--g-s-5);
		list-style: none;
		cursor: pointer;
		/* #2913 Scheibe (c) Fix-Loop 2: Kopf wie Mockup `details.adv summary` (14 px, 600). */
		font-size: var(--g-size-14px);
		font-weight: 600;
		color: var(--g-ink);
	}
	.aufklapper summary::-webkit-details-marker {
		display: none;
	}
	.aufklapper summary:focus-visible {
		outline: var(--g-size-2px) solid var(--g-accent);
		outline-offset: calc(-1 * var(--g-size-2px));
	}
	.aufklapper-zeichen {
		color: var(--g-ink-2);
		font-weight: 400;
	}
	@media (max-width: 899px) {
		.aufklapper summary {
			padding: var(--g-size-14px) var(--g-s-4);
		}
	}
</style>
