<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import favicon from '$lib/assets/favicon.svg';

	let { children, data } = $props();

	let mobileMenuOpen = $state(false);

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
		<nav class="fixed z-50 h-full w-60 border-r bg-background p-4 transition-transform duration-200 md:static md:translate-x-0 md:bg-muted/40
			{mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}"
		>
			<h1 class="mb-6 text-lg font-bold">Gregor 20</h1>
			{#each nav as item}
				<a
					href={item.href}
					class="block rounded-md px-3 py-2 text-sm hover:bg-accent"
					class:bg-accent={page.url.pathname === item.href}
					class:font-medium={page.url.pathname === item.href}
					onclick={closeMobileMenu}
				>
					{item.label}
				</a>
			{/each}
			<div class="mt-auto pt-6 text-xs text-muted-foreground">
				{data.userId ?? ''}
				<form method="POST" action="/logout" class="mt-2">
					<button type="submit" class="hover:text-foreground">Logout</button>
				</form>
			</div>
		</nav>

		<!-- Main content: add top padding on mobile for the top bar -->
		<main class="flex-1 overflow-auto p-4 pt-16 md:p-6 md:pt-6">
			{@render children()}
		</main>
	</div>
{/if}
