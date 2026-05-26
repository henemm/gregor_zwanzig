<script lang="ts">
	// Issue #372 — DetailRow-Molecule (kanonisch aus molecules.jsx, Svelte 5).
	//
	// Label-Value-Zeile, optional mit Icon links (Snippet/WIcon), Sub-Text,
	// Right-Slot (Snippet), gestricheltem Bottom-Border (Default). KV-
	// Verallgemeinerung.
	//
	// Kontrast: sub nutzt --g-ink-3 statt Vorlagen-Wert --g-ink-4 (WCAG-AA, #377).
	//
	// Spec: docs/specs/modules/issue_372_molecules.md (AC-1)

	import type { Snippet } from 'svelte';

	type Divider = 'dashed' | 'solid' | 'none';

	interface Props {
		label?: string;
		value?: string | number | null;
		sub?: string;
		icon?: Snippet; // Snippet/WIcon links
		right?: Snippet; // Right-Slot
		mono?: boolean; // Value-Font: mono (Default) oder sans
		divider?: Divider;
		class?: string;
	}

	let {
		label,
		value,
		sub,
		icon,
		right,
		mono = true,
		divider = 'dashed',
		class: className = ''
	}: Props = $props();

	// Unbekannte divider -> dashed-Fallback (kein Crash).
	const resolvedDivider = $derived(
		divider === 'none' || divider === 'solid' || divider === 'dashed' ? divider : 'dashed'
	);
	const borderStyle = $derived(
		resolvedDivider === 'none' ? 'none' : `1px ${resolvedDivider} var(--g-rule-soft)`
	);
</script>

<div
	class={className}
	style:display="flex"
	style:align-items="center"
	style:gap="12px"
	style:padding="8px 0"
	style:border-bottom={borderStyle}
	style:font-size="13px"
>
	{#if icon}
		<span style:display="inline-flex" style:flex-shrink="0">{@render icon()}</span>
	{/if}
	<div style:flex="1" style:min-width="0">
		<span
			style:font-family="var(--g-font-mono)"
			style:font-size="12px"
			style:color="var(--g-ink-3)"
			style:letter-spacing="0.02em"
		>{label}</span>
		{#if sub}
			<div style:font-size="11px" style:color="var(--g-ink-3)" style:margin-top="2px">{sub}</div>
		{/if}
	</div>
	{#if value != null}
		<span
			style:color="var(--g-ink)"
			style:font-family={mono ? 'var(--g-font-mono)' : 'var(--g-font-sans)'}
			style:font-weight={mono ? 500 : 600}
			style:font-size="13px"
			style:font-variant-numeric={mono ? 'tabular-nums' : 'normal'}
		>{value}</span>
	{/if}
	{@render right?.()}
</div>
