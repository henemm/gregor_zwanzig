<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { browser } from '$app/environment';
	import favicon from '$lib/assets/favicon.svg';

	let { children, data } = $props();

	let mobileMenuOpen = $state(false);

	import MoonIcon from '@lucide/svelte/icons/moon';
	import SunIcon from '@lucide/svelte/icons/sun';

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

	import LayoutDashboard from '@lucide/svelte/icons/layout-dashboard';
	import RouteIcon from '@lucide/svelte/icons/route';
	import MapPin from '@lucide/svelte/icons/map-pin';
	import Bell from '@lucide/svelte/icons/bell';
	import GitCompare from '@lucide/svelte/icons/git-compare';
	import CloudSun from '@lucide/svelte/icons/cloud-sun';
	import SettingsIcon from '@lucide/svelte/icons/settings';

	const navGroups = [
		{
			label: 'Daten',
			items: [
				{ href: '/', label: 'Übersicht', icon: LayoutDashboard },
				{ href: '/trips', label: 'Trips', icon: RouteIcon },
				{ href: '/locations', label: 'Locations', icon: MapPin },
				{ href: '/subscriptions', label: 'Abos', icon: Bell },
			]
		},
		{
			label: 'System',
			items: [
				{ href: '/compare', label: 'Vergleich', icon: GitCompare },
				{ href: '/weather', label: 'Wetter', icon: CloudSun },
				{ href: '/settings', label: 'Einstellungen', icon: SettingsIcon },
			]
		}
	];

	const publicPages = ['/login', '/register', '/forgot-password', '/reset-password'];
	const isLogin = $derived(publicPages.includes(page.url.pathname));

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
			{#each navGroups as group, gi}
				{#if gi > 0}<div class="mt-4"></div>{/if}
				<p class="mb-1 px-3 text-[0.65rem] font-semibold uppercase tracking-wider text-muted-foreground/60">{group.label}</p>
				{#each group.items as item}
					<a
						href={item.href}
						class="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent"
						class:bg-sidebar-accent={page.url.pathname === item.href}
						class:font-medium={page.url.pathname === item.href}
						onclick={closeMobileMenu}
					>
						<svelte:component this={item.icon} class="size-4 shrink-0 opacity-70" />
						{item.label}
					</a>
				{/each}
			{/each}
			<!-- Dark Mode Toggle -->
			<div class="mt-6 mb-4 px-3">
				<button
					onclick={toggleDark}
					class="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors"
					title={darkMode ? 'Light Mode' : 'Dark Mode'}
				>
					{#if darkMode}
						<SunIcon class="size-3.5" />
						Light Mode
					{:else}
						<MoonIcon class="size-3.5" />
						Dark Mode
					{/if}
				</button>
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
