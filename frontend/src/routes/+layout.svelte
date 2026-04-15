<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import favicon from '$lib/assets/favicon.svg';

	let { children, data } = $props();

	const nav = [
		{ href: '/', label: 'Dashboard' },
		{ href: '/trips', label: 'Trips' },
		{ href: '/locations', label: 'Locations' },
		{ href: '/subscriptions', label: 'Subscriptions' },
		{ href: '/weather', label: 'Wetter' },
		{ href: '/settings', label: 'Settings' }
	];

	const isLogin = $derived(page.url.pathname === '/login');
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{#if isLogin}
	{@render children()}
{:else}
	<div class="flex h-screen">
		<nav class="w-60 border-r bg-muted/40 p-4">
			<h1 class="mb-6 text-lg font-bold">Gregor 20</h1>
			{#each nav as item}
				<a
					href={item.href}
					class="block rounded-md px-3 py-2 text-sm hover:bg-accent"
					class:bg-accent={page.url.pathname === item.href}
					class:font-medium={page.url.pathname === item.href}
				>
					{item.label}
				</a>
			{/each}
			<div class="mt-auto pt-6 text-xs text-muted-foreground">
				{data.userId ?? ''}
			</div>
		</nav>
		<main class="flex-1 overflow-auto p-6">
			{@render children()}
		</main>
	</div>
{/if}
