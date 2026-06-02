<script lang="ts">
	import LayoutDashboard from '@lucide/svelte/icons/layout-dashboard';
	import RouteIcon from '@lucide/svelte/icons/route';
	import GitCompare from '@lucide/svelte/icons/git-compare';
	import ArchiveIcon from '@lucide/svelte/icons/archive';
	import MonitorIcon from '@lucide/svelte/icons/monitor';
	import UserIcon from '@lucide/svelte/icons/user';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import LogOut from '@lucide/svelte/icons/log-out';
	import MoonIcon from '@lucide/svelte/icons/moon';
	import SunIcon from '@lucide/svelte/icons/sun';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';

	interface SidebarProps {
		userId: string | null | undefined;
		currentPath: string;
		darkMode: boolean;
		ontoggleDark: () => void;
		mobileMenuOpen: boolean;
	}

	let { userId, currentPath, darkMode, ontoggleDark, mobileMenuOpen = $bindable(false) }: SidebarProps = $props();

	let userMenuOpen = $state(false);

	const navItems = [
		{ href: '/',          label: 'Startseite',    icon: LayoutDashboard },
		{ href: '/trips',     label: 'Meine Touren', icon: RouteIcon        },
		{ href: '/compare',   label: 'Orts-Vergleich', icon: GitCompare      },
		{ href: '/archiv',    label: 'Archiv',         icon: ArchiveIcon      },
	];

	function closeMobileMenu() { mobileMenuOpen = false; }
	function closeUserMenu() { userMenuOpen = false; }
	function userInitial(id: string | null | undefined): string {
		return (id ?? '?').charAt(0).toUpperCase();
	}
</script>

<!-- Mobile overlay backdrop -->
{#if mobileMenuOpen}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-40 bg-black/50 desktop:hidden"
		onclick={closeMobileMenu}
		onkeydown={(e) => e.key === 'Escape' && closeMobileMenu()}
	></div>
{/if}

<!-- Sidebar: Desktop = static und immer sichtbar; Mobile = slide-in drawer (hidden when closed) -->
<nav
	data-testid="desktop-sidebar"
	class="fixed z-50 h-full w-60 flex-col bg-sidebar text-sidebar-foreground p-4 transition-transform duration-200 desktop:static desktop:translate-x-0 desktop:flex
	{mobileMenuOpen ? 'flex translate-x-0' : 'hidden -translate-x-full'}"
>
	<div class="mb-6"><Wordmark size="md" /></div>

	<!-- Desktop: Full workspace nav. Mobile (drawer): secondary items only via CSS -->
	{#each navItems as item}
		<a
			href={item.href}
			class="hidden desktop:flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent"
			class:bg-sidebar-accent={currentPath === item.href}
			class:font-medium={currentPath === item.href}
			onclick={closeMobileMenu}
		>
			<svelte:component this={item.icon} class="size-4 shrink-0 opacity-70" />
			{item.label}
		</a>
	{/each}

	<!-- Mobile drawer: Secondary items (Konto, Logout) — sichtbar auf Mobile, versteckt auf Desktop -->
	<div class="desktop:hidden flex flex-col gap-1">
		<a
			href="/account"
			class="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent"
			onclick={closeMobileMenu}
		>
			<UserIcon class="size-4 shrink-0 opacity-70" />
			Konto
		</a>
		<a
			href="/account#system-status"
			class="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent"
			onclick={closeMobileMenu}
		>
			<MonitorIcon class="size-4 shrink-0 opacity-70" />
			System-Status
		</a>
		<button
			onclick={() => { ontoggleDark(); closeMobileMenu(); }}
			class="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent text-left"
		>
			{#if darkMode}
				<SunIcon class="size-4 opacity-70" />
				Light Mode
			{:else}
				<MoonIcon class="size-4 opacity-70" />
				Dark Mode
			{/if}
		</button>
	</div>

	<!-- Sidebar Footer (Desktop only) — Avatar Badge with Dropdown -->
	<div class="hidden desktop:block mt-auto border-t border-border/50 pt-3 relative">
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
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="fixed inset-0 z-[70]"
				onclick={closeUserMenu}
				onkeydown={(e) => e.key === 'Escape' && closeUserMenu()}
			></div>

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

	<!-- Mobile Footer: Logout direct (not in dropdown) -->
	<div class="desktop:hidden mt-auto border-t border-border/50 pt-3">
		<form method="POST" action="/logout">
			<button type="submit" class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-destructive hover:bg-destructive/10">
				<LogOut class="size-4 opacity-70" />
				Abmelden
			</button>
		</form>
	</div>
</nav>
