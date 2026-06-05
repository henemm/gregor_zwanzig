<script lang="ts">
	// Issue #372 — Field-Molecule (kanonisch aus molecules.jsx, Svelte 5).
	//
	// Form-Field-Wrapper: Label oben (+ optional Side rechts) + Children +
	// optional Hint/Error darunter. Vereinheitlicht trip-wizard::Field und
	// auth::AuthField.
	//
	// Kontrast: hint nutzt --g-ink-3 statt des Vorlagen-Werts --g-ink-4
	// (WCAG-AA fuer echten Hilfstext, #377).
	//
	// Spec: docs/specs/modules/issue_372_molecules.md (AC-1)

	import type { Snippet } from 'svelte';

	interface Props {
		label?: string;
		hint?: string; // zarter Hilfstext unter dem Feld
		error?: string; // Error-String — ueberschreibt hint visuell
		side?: string; // z. B. "Passwort vergessen?" rechts neben dem Label
		dense?: boolean;
		children?: Snippet;
		class?: string;
	}

	let {
		label,
		hint,
		error,
		side,
		dense = true,
		children,
		class: className = ''
	}: Props = $props();
</script>

<div class={className} style:margin-bottom={dense ? '14px' : '18px'}>
	{#if label || side}
		<div
			style:display="flex"
			style:justify-content="space-between"
			style:align-items="baseline"
			style:margin-bottom={dense ? '6px' : '8px'}
		>
			{#if label}
				<span
					style:font-family="var(--g-font-mono)"
					style:font-size="10px"
					style:letter-spacing="0.08em"
					style:text-transform="uppercase"
					style:color="var(--g-ink-3)"
					style:font-weight="500"
				>{label}</span>
			{/if}
			{#if side}
				<span style:font-size="11px" style:color="var(--g-ink-3)">{side}</span>
			{/if}
		</div>
	{/if}
	{@render children?.()}
	{#if hint || error}
		<div
			style:font-size="11px"
			style:margin-top="5px"
			style:line-height="1.4"
			style:color={error ? 'var(--g-bad)' : 'var(--g-ink-4)'}
		>{error || hint}</div>
	{/if}
</div>
