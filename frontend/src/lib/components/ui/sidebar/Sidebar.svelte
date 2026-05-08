<script lang="ts">
	import LayoutDashboard from '@lucide/svelte/icons/layout-dashboard';
	import RouteIcon from '@lucide/svelte/icons/route';
	import GitCompare from '@lucide/svelte/icons/git-compare';
	import MonitorIcon from '@lucide/svelte/icons/monitor';
	import UserIcon from '@lucide/svelte/icons/user';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import LogOut from '@lucide/svelte/icons/log-out';
	import MoonIcon from '@lucide/svelte/icons/moon';
	import SunIcon from '@lucide/svelte/icons/sun';

	interface SidebarProps {
		userId: string | null | undefined;
		currentPath: string;
		darkMode: boolean;
		ontoggleDark: () => void;
	}

	let { userId, currentPath, darkMode, ontoggleDark }: SidebarProps = $props();

	let mobileMenuOpen = $state(false);
	let userMenuOpen = $state(false);

	const navItems = [
		{ href: '/',        label: 'Startseite',    icon: LayoutDashboard },
		{ href: '/trips',   label: 'Meine Touren',  icon: RouteIcon },
		{ href: '/compare', label: 'Orts-Vergleich', icon: GitCompare },
	];

	function closeMobileMenu() {
		mobileMenuOpen = false;
	}

	function closeUserMenu() {
		userMenuOpen = false;
	}

	function userInitial(id: string | null | undefined): string {
		return (id ?? '?').charAt(0).toUpperCase();
	}
</script>

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
<nav class="fixed z-50 flex h-full w-60 flex-col bg-sidebar text-sidebar-foreground p-4 transition-transform duration-200 md:static md:translate-x-0
	{mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}"
>
	<h1 class="mb-6 text-lg font-bold">Gregor 20</h1>
	{#each navItems as item}
		<a
			href={item.href}
			class="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent"
			class:bg-sidebar-accent={currentPath === item.href}
			class:font-medium={currentPath === item.href}
			onclick={closeMobileMenu}
		>
			<svelte:component this={item.icon} class="size-4 shrink-0 opacity-70" />
			{item.label}
		</a>
	{/each}

	<!-- Sidebar Footer — Avatar Badge with Dropdown -->
	<div class="mt-auto border-t border-border/50 pt-3 relative">
		<button
			onclick={() => userMenuOpen = !userMenuOpen}
			class="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent transition-colors"
		>
			<span class="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
				{userInitial(userId)}
			</span>
			<span class="truncate">{userId ?? ''}</span>
			<ChevronUp class="ml-auto size-4 text-muted-foreground transition-transform {userMenuOpen ? '' : 'rotate-180'}" />
		</button>

		{#if userMenuOpen}
			<!-- Backdrop to close on outside click -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="fixed inset-0 z-[70]"
				onclick={closeUserMenu}
				onkeydown={(e) => e.key === 'Escape' && closeUserMenu()}
			></div>

			<!-- Dropdown -->
			<div class="absolute bottom-full left-2 right-2 z-[80] mb-1 rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
				<a
					href="/account"
					class="flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground transition-colors"
					onclick={() => { closeUserMenu(); closeMobileMenu(); }}
				>
					<UserIcon class="size-4 opacity-70" />
					Konto
				</a>
				<a
					href="/account#system-status"
					class="flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground transition-colors"
					onclick={() => { closeUserMenu(); closeMobileMenu(); }}
				>
					<MonitorIcon class="size-4 opacity-70" />
					System-Status
				</a>
				<button
					onclick={() => { ontoggleDark(); closeUserMenu(); }}
					class="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground transition-colors"
				>
					{#if darkMode}
						<SunIcon class="size-4 opacity-70" />
						Light Mode
					{:else}
						<MoonIcon class="size-4 opacity-70" />
						Dark Mode
					{/if}
				</button>
				<div class="my-1 h-px bg-border"></div>
				<form method="POST" action="/logout">
					<button type="submit" class="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-destructive hover:bg-destructive/10 transition-colors">
						<LogOut class="size-4 opacity-70" />
						Abmelden
					</button>
				</form>
			</div>
		{/if}
	</div>
</nav>
