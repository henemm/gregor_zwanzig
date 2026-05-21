<script lang="ts">
	import Menu from '@lucide/svelte/icons/menu';
	import X from '@lucide/svelte/icons/x';
	import MoonIcon from '@lucide/svelte/icons/moon';
	import SunIcon from '@lucide/svelte/icons/sun';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';

	interface Props {
		mobileMenuOpen: boolean;
		darkMode: boolean;
		ontoggleDark: () => void;
	}

	let { mobileMenuOpen = $bindable(), darkMode, ontoggleDark }: Props = $props();
</script>

<div
	data-testid="top-app-bar"
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
			<X class="h-5 w-5" />
		{:else}
			<Menu class="h-5 w-5" />
		{/if}
	</button>
	<span class="flex-1"><Wordmark size="sm" /></span>
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
