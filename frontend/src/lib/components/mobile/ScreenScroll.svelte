<script lang="ts">
	// Issue #373 — ScreenScroll (interner Helfer, aus mobile-shell.jsx).
	//
	// Vertikal scrollender Main-Bereich zwischen TopBar und BottomNav.
	// Token-basiert (bg optional).
	//
	// Spec: docs/specs/modules/issue_373_mobile.md
	import type { Snippet } from 'svelte';

	interface Props {
		padding?: number | string;
		bg?: string;
		children?: Snippet;
	}

	let { padding = 16, bg = 'transparent', children }: Props = $props();
	const pad = $derived(typeof padding === 'number' ? `${padding}px` : padding);
</script>

<div
	style:flex="1"
	style:overflow="auto"
	style:padding={pad}
	style:background={bg || 'transparent'}
	style:-webkit-overflow-scrolling="touch"
>
	{@render children?.()}
</div>
