<script lang="ts">
	// Issue #2913 Teil 2 (AC-15, K-2): Chip-Leiste (Mockup Fassung 3, `.more .chip`).
	// Je Eintrag ein Chip aus dem Atom Btn (Touch-Größe `tap`); ein Tipp meldet die id.
	// Beschriftungen kommen als Props aus dem Katalog des Aufrufers. Trip und Orts-Briefing gleich.
	import { Btn } from '$lib/components/atoms';

	interface Eintrag {
		id: string;
		label: string;
		testid?: string;
	}
	interface Props {
		eintraege: Eintrag[];
		onWahl: (id: string) => void;
	}
	let { eintraege, onWahl }: Props = $props();
</script>

<div class="cl" data-slot="chip-leiste">
	{#each eintraege as e (e.id)}
		<Btn variant="ghost" size="tap" data-testid={e.testid} onclick={() => onWahl(e.id)}>{e.label}</Btn>
	{/each}
</div>

<style>
	.cl {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--g-s-2);
	}
	.cl :global([data-slot='btn']) {
		padding: 0 var(--g-s-3);
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
