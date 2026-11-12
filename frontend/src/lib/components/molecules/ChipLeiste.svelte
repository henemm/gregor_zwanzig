<script lang="ts">
	// Issue #2913 Teil 2 (AC-15, K-2): Chip-Leiste (Mockup Fassung 3, `.more .chip`).
	// Je Eintrag ein Chip aus dem Atom Btn (Touch-Größe `tap`); ein Tipp meldet die id.
	// Beschriftungen kommen als Props aus dem Katalog des Aufrufers. Trip und Orts-Briefing gleich.
	// #2913 Scheibe (c) Fix-Loop 2: Chips sind kompakt wie im Mockup (Btn `tap` + `data-tap`: sichtbar
	// 26 px, Trefferfläche ≥ --g-tap-min). `imFluss`: die Chips fließen in die Flex-Zeile des Aufrufers
	// (Label links, Umbruch läuft unter dem Label weiter wie Mockup `.more`).
	import { Btn } from '$lib/components/atoms';

	interface Eintrag {
		id: string;
		label: string;
		testid?: string;
	}
	interface Props {
		eintraege: Eintrag[];
		onWahl: (id: string) => void;
		/** Chips sind direkte Flex-Kinder des Aufrufers (display: contents). */
		imFluss?: boolean;
	}
	let { eintraege, onWahl, imFluss = false }: Props = $props();
</script>

<div class="cl" class:cl-fluss={imFluss} data-slot="chip-leiste">
	{#each eintraege as e (e.id)}
		<Btn variant="ghost" size="tap" data-tap="true" data-testid={e.testid} onclick={() => onWahl(e.id)}>{e.label}</Btn>
	{/each}
</div>

<style>
	/* Zeilenabstand 18 px + Chiphöhe 26 px = 44 px: die Trefferflächen benachbarter Zeilen überlappen nicht. */
	.cl {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		column-gap: var(--g-s-2);
		row-gap: var(--g-size-18px);
	}
	.cl-fluss {
		display: contents;
	}
	.cl :global([data-slot='btn']) {
		border-color: var(--g-rule);
		border-radius: var(--g-r-pill);
		background: var(--g-card);
		color: var(--g-ink);
		font-weight: 400;
	}
	.cl :global([data-slot='btn']:hover) {
		background: var(--g-surface-2);
	}
</style>
