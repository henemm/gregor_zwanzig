<script lang="ts">
	// Issue #578 — ScoreToggle-Molecule.
	// Kanonische Quelle: molecules.jsx::ScoreToggle
	//
	// Ein einzelner Pill-Toggle „Im Score / Nicht im Score" für Ort/Abo-Kontext.

	interface Props {
		on?: boolean;
		onToggle?: () => void;
		compact?: boolean;
		class?: string;
	}

	let { on = false, onToggle, compact = false, class: className = '' }: Props = $props();
</script>

<button
	class={className}
	onclick={onToggle}
	aria-pressed={on}
	style:padding={compact ? '3px 9px' : '4px 11px'}
	style:font-size={compact ? '10px' : '10.5px'}
	style:font-weight="600"
	style:letter-spacing="0.08em"
	style:font-family="var(--g-font-mono)"
	style:background={on ? 'var(--g-accent-tint)' : 'var(--g-paper-deep)'}
	style:color={on ? 'var(--g-accent-deep)' : 'var(--g-ink-4)' /* audit:exempt: inactive toggle (JSX canonical) */}
	style:border={on ? '1px solid var(--g-accent)' : '1px solid var(--g-rule)'}
	style:border-radius="var(--g-r-pill)"
	style:cursor="pointer"
	style:display="inline-flex"
	style:gap="6px"
	style:align-items="center"
>
	<span
		style:width="6px"
		style:height="6px"
		style:border-radius="50%"
		style:background={on ? 'var(--g-accent)' : 'var(--g-rule)'}
	></span>
	{on ? 'Im Score' : 'Nicht im Score'}
</button>
