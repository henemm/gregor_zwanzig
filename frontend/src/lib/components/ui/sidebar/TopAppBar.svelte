<script lang="ts">
	import Menu from '@lucide/svelte/icons/menu';
	import XIcon from '@lucide/svelte/icons/x';
	import MIcon from '$lib/components/mobile/MIcon.svelte';
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
		// Issue #1256 Scheibe 8d — additiv (mobile-shell.jsx:87-114, PO-Regel
		// 2026-07-15 "Design-Komponenten verwenden, nichts nachbauen"): title
		// ersetzt den Wordmark-Default, wenn gesetzt; backHref ist das Ziel des
		// Zurück-Pfeils bei leftIcon="back". Ohne Befüllung (title=undefined)
		// bleibt das Erscheinungsbild exakt wie vor #1256-S8d (Wordmark).
		title?: string;
		backHref?: string;
	}

	let {
		mobileMenuOpen = $bindable(false),
		darkMode = false,
		ontoggleDark = () => {},
		eyebrow = undefined,
		leftIcon = undefined,
		right = undefined,
		dense = undefined,
		scrolled = undefined,
		title = undefined,
		backHref = '/'
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
	{#if leftIcon === 'back'}
		<a
			href={backHref}
			data-testid="top-app-bar-back"
			aria-label="Zurück"
			class="rounded-md p-3 hover:bg-accent"
		>
			<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<path d="M19 12H5M12 5l-7 7 7 7"/>
			</svg>
		</a>
	{:else}
		<button
			data-testid="top-app-bar-hamburger"
			onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
			class="rounded-md p-3 hover:bg-accent"
			aria-label="Menu"
		>
			{#if mobileMenuOpen}
				<XIcon class="h-5 w-5" />
			{:else}
				<Menu class="h-5 w-5" />
			{/if}
		</button>
	{/if}
	<span class="flex-1 min-w-0">
		{#if eyebrow}
			<span
				class="mono block"
				style="font-size: 9px; color: var(--g-ink-muted); letter-spacing: 0.12em; text-transform: uppercase; line-height: 1;"
				>{eyebrow}</span
			>
		{/if}
		{#if title}
			<span
				data-testid="top-app-bar-title"
				class="block truncate"
				style="font-size: {dense ? '15px' : '17px'}; font-weight: 600; letter-spacing: -0.01em; line-height: 1.2;"
				>{title}</span
			>
		{:else}
			<Wordmark size="sm" />
		{/if}
	</span>
	{#if right}
		{@render right()}
	{:else}
		<button
			disabled
			data-testid="top-app-bar-bell"
			aria-label="Benachrichtigungen"
			class="rounded-md p-3 opacity-40"
		>
			<MIcon kind="bell" size={20} />
		</button>
		<a
			href="/trips/new"
			data-testid="top-app-bar-new-trip"
			aria-label="Neuer Trip"
			class="rounded-md p-3 hover:bg-accent"
		>
			<MIcon kind="plus" size={20} />
		</a>
	{/if}
</div>
