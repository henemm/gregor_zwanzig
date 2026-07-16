<script lang="ts">
	// Issue #489 / #1267 — CompareLayoutRow-Molecule (Svelte 5).
	//
	// Kanal-Layout-Zeile fuer Compare-Detail-Seite: Kanal-Kopf links (fetter
	// Kanal-Name + mono Constraint-Unterzeile), benannte Spalten-Chips
	// (Ortsnamen) rechts. SMS-Sonderfall (cols.length===0) zeigt Hint-Text
	// "flach · ohne Spalten" statt Chips.
	//
	// Erstes Chip (idx===0) -> tone=accent, restliche -> tone=default.
	//
	// Design-Vorbild: claude-code-handoff/current/jsx/molecules.jsx:1236-1272.
	// Spec: docs/specs/modules/issue_1267_compare_layout_row_named_chips.md

	import { Pill } from '$lib/components/atoms';

	interface Props {
		channel: string;
		cols: string[];
		dense?: boolean;
	}

	let { channel, cols, dense = false }: Props = $props();

	// Kein `signal` — Signal als Channel entfernt (Issue #610).
	const CHANNEL_LABEL: Record<string, string> = { email: 'Email', telegram: 'Telegram', sms: 'SMS' };
	const CHANNEL_CONSTRAINT: Record<string, string> = { email: 'alle Spalten', telegram: 'max 8', sms: 'flach' };

	const isSmsFlat = $derived(channel.toLowerCase() === 'sms' && cols.length === 0);
	const label = $derived(CHANNEL_LABEL[channel] ?? channel);
	const constraint = $derived(CHANNEL_CONSTRAINT[channel] ?? '');
</script>

<div
	style:display="flex"
	style:flex-direction={dense ? 'column' : 'row'}
	style:align-items={dense ? 'flex-start' : 'center'}
	style:gap={dense ? '6px' : '12px'}
	style:padding={dense ? '8px 16px' : '12px 16px'}
	style:border-bottom="1px solid var(--g-rule-soft)"
>
	<span style:flex-shrink="0">
		<span style:font-weight="600" style:font-size="13px">{label}</span>
		<span
			style:display="block"
			style:font-family="var(--g-font-mono)"
			style:color="var(--g-ink-4)"
			style:font-size="10px"
			style:letter-spacing="0.06em"
			style:text-transform="uppercase"
			style:margin-top="2px"
		>{constraint}</span>
	</span>
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
			{#each cols as name, idx (idx)}
				<Pill tone={idx === 0 ? 'accent' : 'default'}>{name}</Pill>
			{/each}
		</div>
	{/if}
</div>
