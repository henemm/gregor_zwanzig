<script lang="ts">
	// Issue #371 — KV-Atom (kanonisch aus atoms.jsx, Svelte 5).
	//
	// Key/Value-Zeile: label links (mono, muted), value rechts. Flex space-between,
	// gestrichelter unterer Rand (var(--g-rule-soft)).
	//
	// Legacy-Hinweis (Spec): neue Verwendung bevorzugt DetailRow (Molecule #372).
	//
	// Spec: docs/specs/modules/issue_371_atoms.md (AC-6)

	interface Props {
		label?: string;
		value?: string | number;
		mono?: boolean;
		class?: string;
	}

	let { label = '', value = '', mono = true, class: className = '' }: Props = $props();
</script>

<div
	data-slot="kv"
	class={className}
	style:display="flex"
	style:justify-content="space-between"
	style:gap="16px"
	style:padding="6px 0"
	style:border-bottom="1px dashed var(--g-rule-soft)"
	style:font-size="13px"
>
	<span
		style:color="var(--g-ink-3)"
		style:font-family="var(--g-font-mono)"
		style:font-size="12px"
		style:letter-spacing="0.02em"
	>
		{label}
	</span>
	<span
		style:color="var(--g-ink)"
		style:font-family={mono ? 'var(--g-font-mono)' : 'var(--g-font-sans)'}
		style:font-weight={mono ? 500 : 600}
	>
		{value}
	</span>
</div>
