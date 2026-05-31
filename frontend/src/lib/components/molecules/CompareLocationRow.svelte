<script lang="ts">
	// Issue #489 — CompareLocationRow-Molecule (Svelte 5).
	//
	// Standort-Zeile fuer Compare-Detail-Seite: Rang-Badge, Name, optionale
	// Gruppe, Hoehenangabe rechts.
	//
	// Spec: docs/specs/modules/issue_489_compare_row_molecules.md (AC-1)

	import type { Location } from '$lib/types.js';

	interface Props {
		loc: Location;
		index: number;
		dense?: boolean;
		alt?: boolean;
	}

	let { loc, index, dense = false, alt = false }: Props = $props();

	const rank = $derived(String(index).padStart(2, '0'));
</script>

<div
	style:display="flex"
	style:align-items="center"
	style:gap="12px"
	style:padding={dense ? '8px 16px' : '12px 16px'}
	style:background={alt ? 'var(--g-card-alt)' : 'transparent'}
	style:border-bottom="1px solid var(--g-rule-soft)"
>
	<span
		style:font-family="var(--g-font-mono)"
		style:color="var(--g-accent)"
		style:width="2.5rem"
		style:flex-shrink="0"
		style:font-size="13px"
		style:font-weight="600"
	>{rank}</span>
	<div style:flex="1" style:min-width="0">
		<div
			style:color="var(--g-ink)"
			style:font-size="14px"
			style:white-space="nowrap"
			style:overflow="hidden"
			style:text-overflow="ellipsis"
		>{loc.name}</div>
		{#if loc.group}
			<div
				style:color="var(--g-ink-3)"
				style:font-size="11px"
				style:margin-top="2px"
			>{loc.group}</div>
		{/if}
	</div>
	{#if loc.elevation_m != null}
		<span
			style:font-family="var(--g-font-mono)"
			style:color="var(--g-ink-3)"
			style:font-size="12px"
			style:flex-shrink="0"
		>{loc.elevation_m} m</span>
	{/if}
</div>
