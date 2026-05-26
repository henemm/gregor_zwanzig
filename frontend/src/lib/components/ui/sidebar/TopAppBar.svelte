<script lang="ts">
	import Menu from '@lucide/svelte/icons/menu';
	import XIcon from '@lucide/svelte/icons/x';
	import MoonIcon from '@lucide/svelte/icons/moon';
	import SunIcon from '@lucide/svelte/icons/sun';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';

	interface Props {
		mobileMenuOpen?: boolean;
		// Issue #373: darkMode/ontoggleDark optional (Default) — erlaubt TopAppBar
		// ohne Dark-Toggle (z.B. via MobileShell-Wrapper) und behebt den Wrapper-
		// Typfehler. #267-Aufrufer übergeben beide weiter → unverändertes Verhalten.
		darkMode?: boolean;
		ontoggleDark?: () => void;
		// Issue #373 — additive mobile-shell-Props (backward-compatible, Default
		// undefined; bestehendes #267-Verhalten/CSS bleibt unveraendert).
		eyebrow?: string;
		leftIcon?: string;
		right?: import('svelte').Snippet;
		dense?: boolean;
		scrolled?: boolean;
	}

	let {
		mobileMenuOpen = $bindable(false),
		darkMode = false,
		ontoggleDark = () => {},
		eyebrow = undefined,
		leftIcon = undefined,
		right = undefined,
		dense = undefined,
		scrolled = undefined
	}: Props = $props();
</script>

<div
	data-testid="top-app-bar"
	data-dense={dense ? '' : undefined}
	data-scrolled={scrolled ? '' : undefined}
	data-left-icon={leftIcon}
	class="fixed top-0 left-0 right-0 z-[60] flex h-14 items-center gap-3 border-b bg-background px-4 desktop:hidden"
	style="border-color: var(--g-rule-soft);"
>
	<button
		data-testid="top-app-bar-hamburger"
		onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
		class="rounded-md p-1.5 hover:bg-accent"
		aria-label="Menu"
	>
		{#if mobileMenuOpen}
			<XIcon class="h-5 w-5" />
		{:else}
			<Menu class="h-5 w-5" />
		{/if}
	</button>
	<span class="flex-1">
		{#if eyebrow}
			<span
				class="mono block"
				style="font-size: 9px; color: var(--g-ink-muted); letter-spacing: 0.12em; text-transform: uppercase; line-height: 1;"
				>{eyebrow}</span
			>
		{/if}
		<Wordmark size="sm" />
	</span>
	{#if right}
		{@render right()}
	{/if}
	<button
		data-testid="top-app-bar-toggle-dark"
		onclick={ontoggleDark}
		class="rounded-md p-1.5 hover:bg-accent"
		aria-label="Dark Mode"
	>
		{#if darkMode}
			<SunIcon class="h-5 w-5" />
		{:else}
			<MoonIcon class="h-5 w-5" />
		{/if}
	</button>
</div>
