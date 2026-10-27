<script lang="ts">
	// Issue #373 — MobileShell (Template, kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// App-Chrome-Layout fuer Mobile: scrollender ScreenScroll-Slot + BottomNav,
	// plus Slots fuer Drawer/Sheet/Toast-Overlays. Token-basiert, SSR-fest.
	// KEIN PhoneFrame-Bezel (Demo-Rahmen gehoeren in Showcase #374).
	// Mobile-Shell S2: kein Top-Balken mehr — Seitentitel gehoeren in den
	// <PageHeader> des Inhalts (docs/design-requests/mobile_shell_ohne_topbar.md).
	//
	// Spec: docs/specs/modules/issue_373_mobile.md
	import type { Snippet } from 'svelte';
	import BottomNav from './BottomNav.svelte';
	import ScreenScroll from './ScreenScroll.svelte';

	interface Props {
		active?: string;
		onChange?: (id: string) => void;
		showBottomNav?: boolean;
		background?: string;
		children?: Snippet;
		drawer?: Snippet;
		sheet?: Snippet;
		toast?: Snippet;
	}

	let {
		active = undefined,
		onChange = undefined,
		showBottomNav = true,
		background = 'var(--g-paper)',
		children = undefined,
		drawer = undefined,
		sheet = undefined,
		toast = undefined
	}: Props = $props();
</script>

<div
	style:position="relative"
	style:display="flex"
	style:flex-direction="column"
	style:height="100%"
	style:background={background}
	style:overflow="hidden"
>
	<ScreenScroll>
		{@render children?.()}
	</ScreenScroll>

	{#if showBottomNav}
		<BottomNav {active} {onChange} />
	{/if}

	{@render drawer?.()}
	{@render sheet?.()}
	{@render toast?.()}
</div>
