<script lang="ts">
	// Issue #489 — CompareLayoutRow-Molecule (Svelte 5).
	//
	// Kanal-Layout-Zeile fuer Compare-Detail-Seite: Kanal-Label links,
	// Spalten-Chips rechts. SMS-Sonderfall (cols===0) zeigt Hint-Text
	// "flach · ohne Spalten" statt Chips.
	//
	// Erstes Chip (i===0) -> tone=accent, restliche -> tone=default.
	//
	// Spec: docs/specs/modules/issue_489_compare_row_molecules.md (AC-3)

	import { Pill } from '$lib/components/atoms';

	interface Props {
		channel: string;
		cols: number;
		dense?: boolean;
	}

	let { channel, cols, dense = false }: Props = $props();

	const isSmsFlat = $derived(channel.toLowerCase() === 'sms' && cols === 0);
	const chipIndices = $derived(cols > 0 ? Array.from({ length: cols }, (_, i) => i + 1) : []);
	const label = $derived(channel.toUpperCase());
</script>

<div
	style:display="flex"
	style:flex-direction={dense ? 'column' : 'row'}
	style:align-items={dense ? 'flex-start' : 'center'}
	style:gap={dense ? '6px' : '12px'}
	style:padding={dense ? '8px 16px' : '12px 16px'}
	style:border-bottom="1px solid var(--g-rule-soft)"
>
	<span
		style:font-family="var(--g-font-mono)"
		style:color="var(--g-ink-3)"
		style:font-size="11px"
		style:letter-spacing="0.08em"
		style:flex-shrink="0"
	>{label}</span>
	{#if isSmsFlat}
		<span
			style:color="var(--g-ink-3)"
			style:font-size="11px"
			style:font-style="italic"
			style:flex="1"
		>flach · ohne Spalten</span>
	{:else}
		<div
			style:display="flex"
			style:flex-wrap="wrap"
			style:gap="6px"
			style:flex="1"
			style:justify-content={dense ? 'flex-start' : 'flex-end'}
		>
			{#each chipIndices as i, idx (i)}
				<Pill tone={idx === 0 ? 'accent' : 'default'}>{i}</Pill>
			{/each}
		</div>
	{/if}
</div>
