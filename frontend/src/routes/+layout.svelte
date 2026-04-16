<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { browser } from '$app/environment';
	import favicon from '$lib/assets/favicon.svg';

	let { children, data } = $props();

	let mobileMenuOpen = $state(false);

	type ThemeDef = Record<string, string>;

	const themeColors: Record<string, ThemeDef> = {
		alpine: {
			'--color-background': 'oklch(0.98 0.005 240)',
			'--color-foreground': 'oklch(0.15 0.02 250)',
			'--color-muted': 'oklch(0.94 0.01 240)',
			'--color-muted-foreground': 'oklch(0.45 0.02 250)',
			'--color-border': 'oklch(0.88 0.02 240)',
			'--color-input': 'oklch(0.88 0.02 240)',
			'--color-ring': 'oklch(0.55 0.15 250)',
			'--color-primary': 'oklch(0.45 0.18 250)',
			'--color-primary-foreground': 'oklch(0.98 0 0)',
			'--color-accent': 'oklch(0.92 0.03 240)',
			'--color-accent-foreground': 'oklch(0.25 0.10 250)',
			'--color-sidebar': 'oklch(0.22 0.05 250)',
			'--color-sidebar-foreground': 'oklch(0.92 0.01 240)',
			'--color-sidebar-accent': 'oklch(0.30 0.06 250)',
		},
		forest: {
			'--color-background': 'oklch(0.98 0.005 150)',
			'--color-foreground': 'oklch(0.15 0.02 155)',
			'--color-muted': 'oklch(0.94 0.015 150)',
			'--color-muted-foreground': 'oklch(0.45 0.03 155)',
			'--color-border': 'oklch(0.88 0.025 150)',
			'--color-input': 'oklch(0.88 0.025 150)',
			'--color-ring': 'oklch(0.55 0.12 155)',
			'--color-primary': 'oklch(0.45 0.15 155)',
			'--color-primary-foreground': 'oklch(0.98 0 0)',
			'--color-accent': 'oklch(0.92 0.03 150)',
			'--color-accent-foreground': 'oklch(0.25 0.10 155)',
			'--color-sidebar': 'oklch(0.20 0.04 155)',
			'--color-sidebar-foreground': 'oklch(0.92 0.015 150)',
			'--color-sidebar-accent': 'oklch(0.28 0.05 155)',
		},
		sunset: {
			'--color-background': 'oklch(0.98 0.005 60)',
			'--color-foreground': 'oklch(0.18 0.02 40)',
			'--color-muted': 'oklch(0.95 0.01 55)',
			'--color-muted-foreground': 'oklch(0.45 0.03 40)',
			'--color-border': 'oklch(0.89 0.02 55)',
			'--color-input': 'oklch(0.89 0.02 55)',
			'--color-ring': 'oklch(0.60 0.15 40)',
			'--color-primary': 'oklch(0.55 0.20 35)',
			'--color-primary-foreground': 'oklch(0.98 0 0)',
			'--color-accent': 'oklch(0.93 0.03 55)',
			'--color-accent-foreground': 'oklch(0.30 0.10 35)',
			'--color-sidebar': 'oklch(0.25 0.05 35)',
			'--color-sidebar-foreground': 'oklch(0.93 0.01 55)',
			'--color-sidebar-accent': 'oklch(0.33 0.07 35)',
		},
		slate: {
			'--color-background': 'oklch(0.98 0.003 265)',
			'--color-foreground': 'oklch(0.13 0.02 265)',
			'--color-muted': 'oklch(0.94 0.005 265)',
			'--color-muted-foreground': 'oklch(0.45 0.015 265)',
			'--color-border': 'oklch(0.88 0.01 265)',
			'--color-input': 'oklch(0.88 0.01 265)',
			'--color-ring': 'oklch(0.55 0.10 265)',
			'--color-primary': 'oklch(0.45 0.15 265)',
			'--color-primary-foreground': 'oklch(0.98 0 0)',
			'--color-accent': 'oklch(0.93 0.01 265)',
			'--color-accent-foreground': 'oklch(0.25 0.08 265)',
			'--color-sidebar': 'oklch(0.18 0.02 265)',
			'--color-sidebar-foreground': 'oklch(0.93 0.005 265)',
			'--color-sidebar-accent': 'oklch(0.25 0.03 265)',
		},
	};

	const themes = [
		{ id: '', label: 'Neutral', color: '#333' },
		{ id: 'alpine', label: 'Alpine', color: '#3b6cc7' },
		{ id: 'forest', label: 'Forest', color: '#2d8a4e' },
		{ id: 'sunset', label: 'Sunset', color: '#c8612a' },
		{ id: 'slate', label: 'Slate', color: '#5b6abf' },
	];

	let currentTheme = $state('');

	function applyTheme(id: string) {
		const el = document.documentElement;
		// Remove all theme properties first
		for (const vars of Object.values(themeColors)) {
			for (const key of Object.keys(vars)) {
				el.style.removeProperty(key);
			}
		}
		// Apply new theme
		if (id && themeColors[id]) {
			for (const [key, value] of Object.entries(themeColors[id])) {
				el.style.setProperty(key, value);
			}
		}
	}

	if (browser) {
		currentTheme = localStorage.getItem('gz-theme') ?? '';
		if (currentTheme) applyTheme(currentTheme);
	}

	function setTheme(id: string) {
		currentTheme = id;
		applyTheme(id);
		localStorage.setItem('gz-theme', id);
	}

	const nav = [
		{ href: '/', label: 'Übersicht' },
		{ href: '/trips', label: 'Trips' },
		{ href: '/locations', label: 'Locations' },
		{ href: '/subscriptions', label: 'Abos' },
		{ href: '/compare', label: 'Vergleich' },
		{ href: '/weather', label: 'Wetter' },
		{ href: '/settings', label: 'Einstellungen' }
	];

	const isLogin = $derived(page.url.pathname === '/login');

	function closeMobileMenu() {
		mobileMenuOpen = false;
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{#if isLogin}
	{@render children()}
{:else}
	<div class="flex h-screen">
		<!-- Mobile top bar -->
		<div class="fixed top-0 left-0 right-0 z-[60] flex items-center gap-3 border-b bg-background px-4 py-3 md:hidden">
			<button
				onclick={() => mobileMenuOpen = !mobileMenuOpen}
				class="rounded-md p-1.5 hover:bg-accent"
				aria-label="Menu"
			>
				<svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					{#if mobileMenuOpen}
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					{:else}
						<path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
					{/if}
				</svg>
			</button>
			<span class="text-sm font-bold">Gregor 20</span>
		</div>

		<!-- Mobile overlay -->
		{#if mobileMenuOpen}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="fixed inset-0 z-40 bg-black/50 md:hidden"
				onclick={closeMobileMenu}
				onkeydown={(e) => e.key === 'Escape' && closeMobileMenu()}
			></div>
		{/if}

		<!-- Sidebar: hidden on mobile, slide-in when open -->
		<nav class="fixed z-50 h-full w-60 border-r bg-sidebar text-sidebar-foreground p-4 transition-transform duration-200 md:static md:translate-x-0
			{mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}"
		>
			<h1 class="mb-6 text-lg font-bold">Gregor 20</h1>
			{#each nav as item}
				<a
					href={item.href}
					class="block rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent"
					class:bg-sidebar-accent={page.url.pathname === item.href}
					class:font-medium={page.url.pathname === item.href}
					onclick={closeMobileMenu}
				>
					{item.label}
				</a>
			{/each}
			<!-- Theme Switcher -->
			<div class="mt-6 mb-4">
				<p class="mb-2 px-3 text-xs text-muted-foreground">Design</p>
				<div class="flex gap-1.5 px-3">
					{#each themes as theme}
						<button
							onclick={() => setTheme(theme.id)}
							class="h-5 w-5 rounded-full border-2 transition-transform hover:scale-110"
							class:border-foreground={currentTheme === theme.id}
							class:border-transparent={currentTheme !== theme.id}
							style="background-color: {theme.color}"
							title={theme.label}
						></button>
					{/each}
				</div>
			</div>
			<div class="mt-auto pt-2 text-xs text-muted-foreground">
				{data.userId ?? ''}
				<form method="POST" action="/logout" class="mt-2">
					<button type="submit" class="hover:text-foreground">Logout</button>
				</form>
			</div>
		</nav>

		<!-- Main content: add top padding on mobile for the top bar -->
		<main class="flex-1 overflow-auto bg-muted/20 p-4 pt-16 md:p-6 md:pt-6">
			{@render children()}
		</main>
	</div>
{/if}
