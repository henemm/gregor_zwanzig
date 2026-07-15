<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { browser } from '$app/environment';
	import { Sidebar } from '$lib/components/ui/sidebar';
	import TopAppBar from '$lib/components/ui/sidebar/TopAppBar.svelte';
	import BottomNav from '$lib/components/ui/sidebar/BottomNav.svelte';
	// Issue #1256 Scheibe 8d — Seiten befüllen die EINE globale Design-Kopfleiste
	// über diesen Store (title/eyebrow/leftIcon/backHref/right); Default (leer)
	// = unverändertes Wordmark/Bell/Plus-Erscheinungsbild auf allen Seiten.
	import { topAppBarStore } from '$lib/stores/topAppBar.svelte';

	let { children, data } = $props();

	const darkVars: Record<string, string> = {
		'--color-background': 'oklch(0.145 0 0)',
		'--color-foreground': 'oklch(0.95 0 0)',
		'--color-popover': 'oklch(0.18 0 0)',
		'--color-popover-foreground': 'oklch(0.95 0 0)',
		'--color-card': 'oklch(0.18 0 0)',
		'--color-card-foreground': 'oklch(0.95 0 0)',
		'--color-muted': 'oklch(0.22 0 0)',
		'--color-muted-foreground': 'oklch(0.60 0 0)',
		'--color-border': 'oklch(0.28 0 0)',
		'--color-input': 'oklch(0.28 0 0)',
		'--color-ring': 'oklch(0.55 0 0)',
		'--color-primary': 'oklch(0.92 0 0)',
		'--color-primary-foreground': 'oklch(0.15 0 0)',
		'--color-accent': 'oklch(0.22 0 0)',
		'--color-accent-foreground': 'oklch(0.92 0 0)',
		'--color-sidebar': 'oklch(0.12 0 0)',
		'--color-sidebar-foreground': 'oklch(0.90 0 0)',
		'--color-sidebar-accent': 'oklch(0.20 0 0)',
	};

	let darkMode = $state(false);
	let mobileMenuOpen = $state(false);

	function applyDarkMode(dark: boolean) {
		const el = document.documentElement;
		if (dark) {
			for (const [key, value] of Object.entries(darkVars)) {
				el.style.setProperty(key, value);
			}
		} else {
			for (const key of Object.keys(darkVars)) {
				el.style.removeProperty(key);
			}
		}
	}

	if (browser) {
		darkMode = localStorage.getItem('gz-dark') === '1';
		if (darkMode) applyDarkMode(true);
	}

	function toggleDark() {
		darkMode = !darkMode;
		applyDarkMode(darkMode);
		localStorage.setItem('gz-dark', darkMode ? '1' : '0');
	}

	const publicPages = ['/login', '/register', '/forgot-password', '/reset-password', '/verify-email'];
	const isLogin = $derived(publicPages.includes(page.url.pathname));
	const isWizard = $derived(page.url.pathname.startsWith('/trips/new'));
	// Showcase-Route (#370): ohne App-Chrome (TopAppBar/Sidebar/BottomNav), damit
	// die Brand-Demos die einzigen App-Bausteine auf der Seite sind.
	const isShowcase = $derived(page.url.pathname === '/_design');
</script>

{#if isLogin || isShowcase}
	{@render children()}
{:else}
	<TopAppBar
		bind:mobileMenuOpen
		{darkMode}
		ontoggleDark={toggleDark}
		title={topAppBarStore.fill.title}
		eyebrow={topAppBarStore.fill.eyebrow}
		leftIcon={topAppBarStore.fill.leftIcon}
		backHref={topAppBarStore.fill.backHref}
		right={topAppBarStore.fill.right}
	/>
	<div class="flex h-screen">
		<Sidebar
			userId={data.userId}
			displayName={data.displayName}
			currentPath={page.url.pathname}
			{darkMode}
			ontoggleDark={toggleDark}
			bind:mobileMenuOpen
		/>
		<main class="mobile-scroll-pad flex-1 overflow-auto px-4 desktop:p-6 desktop:pt-6">
			{@render children()}
		</main>
	</div>
	{#if !isWizard}
		<BottomNav />
	{/if}
{/if}
