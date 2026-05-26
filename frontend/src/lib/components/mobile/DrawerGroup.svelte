<script lang="ts">
	// Issue #373 — DrawerGroup (interner Helfer, aus mobile-shell.jsx).
	//
	// Beschriftete Gruppe von Drawer-Eintraegen. Token-basiert.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md
	import type { Snippet } from 'svelte';

	interface Props {
		label?: string;
		children?: Snippet;
	}

	let { label, children }: Props = $props();
</script>

<div style:padding="8px 0 16px">
	{#if label}
		<div
			class="mono"
			style:padding="0 10px 6px"
			style:font-size="10px"
			style:letter-spacing="0.14em"
			style:text-transform="uppercase"
			style:color="var(--g-ink-4)"
			style:font-weight="500"
		>{label}</div>
	{/if}
	{@render children?.()}
</div>
