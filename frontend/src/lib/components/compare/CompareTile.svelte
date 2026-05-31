<script lang="ts">
	// Issue #488 — CompareTile (Molecule, Svelte 5).
	//
	// Kachel für einen ComparePreset im Vergleichs-Dashboard (Epic #485).
	// Drei Layout-Varianten via Props:
	//   dense=true    → reduziertes Padding/Gap (Mobile)
	//   compact=true  → Kanal-Pills weggelassen (Home-Kachel)
	//   accent=true   → border-left mit var(--g-accent) (aktive Auswahl)
	//
	// Kein API-Call hier: Kachel-Klick → onclick(); Kebab-Aktionen → onAction(id).
	// Die Elternkomponente (CompareGrid / Home) ist für Backend-Calls zuständig.
	//
	// Spec: docs/specs/modules/issue_488_compare_tile_atoms.md §3

	import type { ComparePreset } from '$lib/types.js';
	import { deriveStatusFromPreset, presetLocationsLabel } from './subscriptionHelpers.js';
	import CompareStatusPill from './CompareStatusPill.svelte';
	import CompareKebab from './CompareKebab.svelte';
	import { ChannelChip } from '$lib/components/molecules';

	interface Props {
		sub: ComparePreset;
		dense?: boolean;
		compact?: boolean;
		accent?: boolean;
		onclick?: () => void;
		onAction?: (id: string) => void;
		class?: string;
	}

	let {
		sub,
		dense = false,
		compact = false,
		accent = false,
		onclick,
		onAction,
		class: className = ''
	}: Props = $props();

	const status = $derived(deriveStatusFromPreset(sub));
	const locationsText = $derived(presetLocationsLabel(sub));
	// Kanäle aus preset.empfaenger ableiten (analog CompareRow.svelte):
	// Enthält E-Mail-Adressen → "E-Mail"; Signal/Telegram aktuell nicht
	// im ComparePreset abgebildet.
	const activeChannels = $derived(sub.empfaenger.length > 0 ? ['Email'] : []);

	const padding = $derived(dense ? '10px 12px' : '14px 16px');
	const gap = $derived(dense ? '6px' : '10px');

	function handleClick() {
		onclick?.();
	}

	function handleKey(e: KeyboardEvent) {
		if (!onclick) return;
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			onclick();
		}
	}
</script>

<div
	class={'compare-tile ' + (compact ? 'compact ' : '') + (dense ? 'dense ' : '') + className}
	data-status={status}
	role={onclick ? 'button' : undefined}
	tabindex={onclick ? 0 : undefined}
	onclick={onclick ? handleClick : undefined}
	onkeydown={onclick ? handleKey : undefined}
	style:border-left={accent ? '3px solid var(--g-accent)' : '1px solid var(--g-rule-soft)'}
	style:border-top="1px solid var(--g-rule-soft)"
	style:border-right="1px solid var(--g-rule-soft)"
	style:border-bottom="1px solid var(--g-rule-soft)"
	style:border-radius="var(--g-r-3)"
	style:background="var(--g-card, #ffffff)"
	style:padding={padding}
	style:display="flex"
	style:flex-direction="column"
	style:gap={gap}
	style:cursor={onclick ? 'pointer' : 'default'}
	style:transition="border-color 120ms ease, box-shadow 120ms ease"
>
	<!-- Header: Name + Kebab -->
	<div
		style:display="flex"
		style:align-items="flex-start"
		style:justify-content="space-between"
		style:gap="8px"
		style:min-width="0"
	>
		<h3
			style:margin="0"
			style:font-size={dense ? '14px' : '15px'}
			style:font-weight="600"
			style:color="var(--g-ink-1)"
			style:line-height="1.3"
			style:overflow="hidden"
			style:text-overflow="ellipsis"
			style:white-space="nowrap"
			style:min-width="0"
			style:flex="1"
		>{sub.name || '(ohne Namen)'}</h3>
		<CompareKebab {status} onSelect={(id) => onAction?.(id)} />
	</div>

	<!-- Status + Orte -->
	<div style:display="flex" style:align-items="center" style:gap="8px" style:flex-wrap="wrap">
		<CompareStatusPill {status} />
		<span
			style:font-size="12px"
			style:color="var(--g-ink-3)"
			style:font-family="var(--g-font-mono)"
		>{locationsText}</span>
	</div>

	<!-- Kanal-Pills (nicht im compact-Modus) -->
	{#if !compact && activeChannels.length > 0}
		<div
			class="compare-tile-channels"
			style:display="flex"
			style:gap="6px"
			style:flex-wrap="wrap"
		>
			{#each activeChannels as ch (ch)}
				<ChannelChip kind={ch} />
			{/each}
		</div>
	{/if}
</div>

<style>
	.compare-tile:hover {
		border-color: var(--g-ink-3);
		box-shadow: var(--g-shadow-2);
	}
</style>
