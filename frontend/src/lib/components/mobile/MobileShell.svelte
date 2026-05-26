<script lang="ts">
	// Issue #373 — MobileShell (Template, kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// App-Chrome-Layout fuer Mobile: TopAppBar + scrollender ScreenScroll-Slot +
	// BottomNav, plus Slots fuer Drawer/Sheet/Toast-Overlays. Token-basiert,
	// SSR-fest. KEIN PhoneFrame-Bezel (Demo-Rahmen gehoeren in Showcase #374).
	//
	// Spec: docs/specs/modules/issue_373_mobile.md
	import type { Snippet } from 'svelte';
	import TopAppBar from './TopAppBar.svelte';
	import BottomNav from './BottomNav.svelte';
	import ScreenScroll from './ScreenScroll.svelte';

	interface Props {
		active?: string;
		title?: string;
		eyebrow?: string;
		leftIcon?: string;
		darkMode?: boolean;
		mobileMenuOpen?: boolean;
		ontoggleDark?: () => void;
		onChange?: (id: string) => void;
		showTopBar?: boolean;
		showBottomNav?: boolean;
		background?: string;
		right?: Snippet;
		children?: Snippet;
		drawer?: Snippet;
		sheet?: Snippet;
		toast?: Snippet;
	}

	let {
		active = undefined,
		title = undefined,
		eyebrow = undefined,
		leftIcon = undefined,
		darkMode = false,
		mobileMenuOpen = $bindable(false),
		ontoggleDark = () => {},
		onChange = undefined,
		showTopBar = true,
		showBottomNav = true,
		background = 'var(--g-paper)',
		right = undefined,
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
	{#if showTopBar}
		<TopAppBar
			bind:mobileMenuOpen
			{darkMode}
			{ontoggleDark}
			{eyebrow}
			{leftIcon}
			{right}
		/>
	{/if}

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
