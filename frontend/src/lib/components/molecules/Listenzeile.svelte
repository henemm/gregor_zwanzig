<script lang="ts">
	// Issue #3007 (Epic #2913, ADR-0097/ADR-0112): EINE Listenzeile für die Reiter Etappen (Trip)
	// und Orte (Orts-Briefing), Mockup Fassung 3 `.lrow` (viewEtappen Z. 577-587, viewOrte Z. 588-591).
	// Setzt auf der Einstellungszeile auf (kein zweites `.lrow`): links Titel (fett) und Zweitzeile,
	// rechts Meta (Mono) vor der Aktion. Optional klickbar (`onclick`, `offen` → aria-expanded) und
	// mit Ziehgriff (`griff`). Texte kommen fertig aus dem Katalog des Aufrufers.
	// Spec: docs/specs/modules/feat_3007_etappen_orte_listen.md (AC-1 bis AC-3).
	import type { Snippet } from 'svelte';
	import Einstellungszeile from './Einstellungszeile.svelte';

	interface Props {
		titel: string;
		zweitzeile?: string;
		meta?: string;
		testid?: string;
		onclick?: () => void;
		offen?: boolean;
		griff?: Snippet;
		children?: Snippet;
		[attr: `data-${string}`]: unknown;
	}
	let { titel, zweitzeile, meta, testid, onclick, offen = false, griff, children, ...attrs }: Props = $props();
</script>

<Einstellungszeile {titel} hinweis={zweitzeile} {testid} {onclick} {offen} vorne={griff} data-listenzeile="" {...attrs}>
	{#if meta}<span class="lz-meta" data-slot="listenzeile-meta">{meta}</span>{/if}
	{@render children?.()}
</Einstellungszeile>

<style>
	.lz-meta {
		font-family: var(--g-font-mono);
		font-size: var(--g-size-13px);
		color: var(--g-ink-3);
	}
</style>
