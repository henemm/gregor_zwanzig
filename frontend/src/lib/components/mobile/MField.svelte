<script lang="ts">
	// Issue #373 — MField (kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// Label + Sub-Text-Rahmen um ein Eingabe-Snippet (Touch-Padding).
	// Token-basiert.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md
	import type { Snippet } from 'svelte';

	interface Props {
		label?: string;
		sub?: string;
		children?: Snippet;
	}

	let { label, sub, children }: Props = $props();
</script>

<div style:margin-bottom="14px">
	{#if label}
		<div
			class="mono"
			style:font-size="11px"
			style:color="var(--g-ink-3)"
			style:letter-spacing="0.08em"
			style:text-transform="uppercase"
			style:margin-bottom="6px"
		>{label}</div>
	{/if}
	{@render children?.()}
	{#if sub}
		<div
			style:font-size="12px"
			style:color="var(--g-ink-4)"
			style:margin-top="6px"
			style:line-height="1.4"
		>{sub}</div>
	{/if}
</div>
