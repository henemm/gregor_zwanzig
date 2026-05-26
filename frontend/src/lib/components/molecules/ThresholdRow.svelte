<script lang="ts">
	// Issue #372 — ThresholdRow-Molecule (kanonisch aus molecules.jsx, Svelte 5).
	//
	// Sans-Label + Mono-Value-Paar, kompakt.
	//   divider="none"   — keine Trennlinie (Default)
	//   divider="solid"  — durchgezogene Linie unten
	//   divider="dashed" — gestrichelt
	//   last=true        — unterdrueckt die Linie fuer die letzte Zeile
	//   editable=true    — pointer-Cursor + onEdit-Callback (Inline-Edit folgt)
	//
	// Spec: docs/specs/modules/issue_372_molecules.md (AC-1)

	type Divider = 'none' | 'solid' | 'dashed';

	interface Props {
		label?: string;
		value?: string | number;
		divider?: Divider;
		last?: boolean;
		editable?: boolean;
		onEdit?: () => void;
		class?: string;
	}

	let {
		label,
		value,
		divider = 'none',
		last = false,
		editable = false,
		onEdit,
		class: className = ''
	}: Props = $props();

	// Unbekannte divider -> none-Fallback (kein Crash).
	const resolvedDivider = $derived(
		divider === 'none' || divider === 'solid' || divider === 'dashed' ? divider : 'none'
	);
	const hasDivider = $derived(resolvedDivider !== 'none');
	const showDivider = $derived(!last && hasDivider);

	function handleClick() {
		if (editable) onEdit?.();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (editable && (e.key === 'Enter' || e.key === ' ')) {
			e.preventDefault();
			handleClick();
		}
	}
</script>

<svelte:element
	this={'div'}
	class={className}
	role={editable ? 'button' : undefined}
	tabindex={editable ? 0 : undefined}
	onclick={handleClick}
	onkeydown={handleKeydown}
	style:display="flex"
	style:justify-content="space-between"
	style:align-items="center"
	style:padding={hasDivider ? '10px 0' : '6px 0'}
	style:border-bottom={showDivider ? `1px ${resolvedDivider} var(--g-rule-soft)` : 'none'}
	style:cursor={editable ? 'pointer' : 'default'}
>
	<span style:font-size="13px" style:color="var(--g-ink-2)">{label}</span>
	<span
		style:font-family="var(--g-font-mono)"
		style:font-size="13px"
		style:color="var(--g-ink)"
		style:font-weight="600"
	>{value}</span>
</svelte:element>
