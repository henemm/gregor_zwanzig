<script lang="ts">
	// Issue #488 — CompareStatusPill (Molecule, Svelte 5).
	//
	// Visuelles Status-Badge für eine Compare-Kachel. Zwei Varianten:
	//   active           → Filled (grün gefüllt, weiß) via --g-accent
	//   paused | draft   → Outline (transparenter Hintergrund, --g-ink-3)
	//
	// Label-Text kommt aus STATUS_MAP[status] (single source).
	//
	// Spec: docs/specs/modules/issue_488_compare_tile_atoms.md §2

	import type { CompareStatus } from './subscriptionHelpers.js';
	import { STATUS_MAP } from './subscriptionHelpers.js';

	interface Props {
		status: CompareStatus;
		class?: string;
	}

	let { status, class: className = '' }: Props = $props();

	const label = $derived(STATUS_MAP[status]?.label ?? status);
	const isFilled = $derived(status === 'active');
</script>

{#if isFilled}
	<!-- Filled-Variante (success / g-accent): grün gefüllt -->
	<span
		class={className}
		data-variant="filled"
		data-status={status}
		style:display="inline-flex"
		style:align-items="center"
		style:gap="4px"
		style:font-size="11px"
		style:font-family="var(--g-font-mono)"
		style:padding="2px 8px"
		style:border-radius="var(--g-r-pill)"
		style:background="var(--g-accent)"
		style:color="#fff"
		style:font-weight="500"
		style:letter-spacing="0.02em"
	>{label}</span>
{:else}
	<!-- Outline-Variante (paused / draft): transparent + Border -->
	<span
		class={className}
		data-variant="outline"
		data-status={status}
		style:display="inline-flex"
		style:align-items="center"
		style:gap="4px"
		style:font-size="11px"
		style:font-family="var(--g-font-mono)"
		style:padding="2px 8px"
		style:border-radius="var(--g-r-pill)"
		style:background="transparent"
		style:border="1px solid var(--g-ink-3)"
		style:color="var(--g-ink-3)"
		style:letter-spacing="0.02em"
	>{label}</span>
{/if}
