<script lang="ts">
	// Issue #1277 — ListNameCell: Status-Dot + Name + Status-Label.
	//
	// Geteilter Baustein der ListTable-Namensspalte (Trips + Orts-Vergleiche).
	// Die Status-Paletten von Trip und Vergleich unterscheiden sich, daher ist
	// `dotColor` eine Prop (kein internes Status-Mapping).
	//
	// Spec: docs/specs/feature/issue_1277_list_table_unify.md

	let {
		name,
		statusLabel = '',
		dotColor = 'var(--g-ink-4)'
	}: { name: string; statusLabel?: string; dotColor?: string } = $props();
</script>

<div style="display: flex; align-items: center; gap: 10px; min-width: 0;">
	<span
		style="width: 7px; height: 7px; border-radius: 50%; background: {dotColor}; flex-shrink: 0;"
	></span>
	<span
		style="font-size: 14px; font-weight: 600; letter-spacing: -0.01em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
		>{name}</span
	>
	{#if statusLabel}
		<span
			class="status-caption"
			style="font-size: 10px; font-family: var(--g-font-mono); color: var(--g-ink-4); text-transform: uppercase; letter-spacing: 0.16em; flex-shrink: 0;"
			>· {statusLabel}</span
		>
	{/if}
</div>
