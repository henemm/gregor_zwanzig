<script lang="ts">
	// Issue #578 — Sidebar 1:1 nach brand-kit.jsx::BrandSidebar (Zeilen 266–351).
	// Desktop: Inline-Styles + eigene SVG-Icons (kein Lucide, kein Tailwind im aside).
	// Mobile: Slide-in-Drawer bleibt funktional (Lucide im Footer erlaubt).
	import UserIcon from '@lucide/svelte/icons/user';
	import MonitorIcon from '@lucide/svelte/icons/monitor';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import LogOut from '@lucide/svelte/icons/log-out';
	import MoonIcon from '@lucide/svelte/icons/moon';
	import SunIcon from '@lucide/svelte/icons/sun';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';

	interface SidebarProps {
		userId: string | null | undefined;
		displayName?: string | null | undefined;
		currentPath: string;
		darkMode: boolean;
		ontoggleDark: () => void;
		mobileMenuOpen: boolean;
	}

	let { userId, displayName, currentPath, darkMode, ontoggleDark, mobileMenuOpen = $bindable(false) }: SidebarProps = $props();

	// Issue #642 — Anzeigename hat Vorrang vor dem Login-Namen.
	const shownName = $derived((displayName && displayName.trim()) || userId || '');

	let userMenuOpen = $state(false);

	// Nav-Items fest nach JSX BRAND_NAV_ITEMS (brand-kit.jsx Zeile 259–264).
	const navItems = [
		{ id: 'home',    href: '/',        label: 'Startseite',     icon: 'home'    },
		{ id: 'trips',   href: '/trips',   label: 'Meine Trips',    icon: 'trip'    },
		{ id: 'compare', href: '/compare', label: 'Orts-Vergleich', icon: 'compare' },
		{ id: 'archive', href: '/archiv',  label: 'Archiv',         icon: 'archive' },
	];

	// Bestimme aktives Item per href-Match (wie bisher currentPath).
	function isActive(href: string): boolean {
		if (href === '/') return currentPath === '/';
		return currentPath.startsWith(href);
	}

	function closeMobileMenu() { mobileMenuOpen = false; }
	function closeUserMenu() { userMenuOpen = false; }
	function userInitial(id: string | null | undefined): string {
		return (id ?? '?').charAt(0).toUpperCase();
	}
</script>

<!-- Mobile overlay backdrop — z-50 damit Backdrop VOR Drawer liegt (AC-9-Fix). -->
{#if mobileMenuOpen}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 bg-black/50 desktop:hidden"
		onclick={closeMobileMenu}
		onkeydown={(e) => e.key === 'Escape' && closeMobileMenu()}
	></div>
{/if}

<!--
  DESKTOP: Statische aside mit Inline-Styles 1:1 nach brand-kit.jsx::BrandSidebar.
  Kein Tailwind bg-sidebar* im Desktop-Block (AC-10).
-->
<aside
	data-testid="desktop-sidebar"
	style="
		width: 220px;
		flex: 0 0 220px;
		background: var(--g-paper-deep);
		border-right: 1px solid var(--g-rule);
		flex-direction: column;
		padding: 24px 0 0;
		height: 100%;
		font-family: var(--g-font-sans);
		position: relative;
		z-index: 40;
	"
	class="hidden desktop:flex"
>
	<!-- Wordmark-Header, Padding 1:1 nach JSX -->
	<div style="padding: 0 18px 24px;">
		<Wordmark size="md" />
	</div>

	<!-- Nav-Liste, gap: 2px, padding: 0 12px -->
	<nav style="display: flex; flex-direction: column; gap: 2px; padding: 0 12px;">
		{#each navItems as item}
			{@const active = isActive(item.href)}
			<a
				href={item.href}
				style="
					display: flex;
					align-items: center;
					gap: 10px;
					padding: 8px 12px;
					border-radius: var(--g-r-3);
					background: {active ? 'rgba(196,90,42,0.10)' : 'transparent'};
					color: {active ? 'var(--g-accent-deep)' : 'var(--g-ink-2)'};
					font-size: 13px;
					font-weight: {active ? 600 : 500};
					text-decoration: none;
					cursor: pointer;
					transition: background 120ms;
				"
			>
				<!-- Inline-SVG-Icons 1:1 nach brand-kit.jsx::BrandSidebarIcon -->
				{#if item.icon === 'home'}
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none"
						stroke={active ? 'var(--g-accent)' : 'var(--g-ink-3)'}
						stroke-width="1.7" stroke-linejoin="round">
						<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>
					</svg>
				{:else if item.icon === 'trip'}
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none"
						stroke={active ? 'var(--g-accent)' : 'var(--g-ink-3)'}
						stroke-width="1.7" stroke-linejoin="round">
						<path d="M3 19l5-9 4 6 4-3 5 6"/>
						<circle cx="8" cy="10" r="1.2" fill={active ? 'var(--g-accent)' : 'var(--g-ink-3)'}/>
						<circle cx="16" cy="13" r="1.2" fill={active ? 'var(--g-accent)' : 'var(--g-ink-3)'}/>
					</svg>
				{:else if item.icon === 'compare'}
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none"
						stroke={active ? 'var(--g-accent)' : 'var(--g-ink-3)'}
						stroke-width="1.7">
						<path d="M5 8h7M5 12h5M5 16h7M14 8l4-3v14l-4-3"/>
					</svg>
				{:else if item.icon === 'archive'}
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none"
						stroke={active ? 'var(--g-accent)' : 'var(--g-ink-3)'}
						stroke-width="1.7" stroke-linejoin="round">
						<rect x="3" y="5" width="18" height="4" rx="1"/>
						<path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/>
					</svg>
				{/if}
				<span style="flex: 1;">{item.label}</span>
			</a>
		{/each}
	</nav>

	<!-- Spacer -->
	<div style="flex: 1;"></div>

	<!-- Footer mit User-Badge + Dropdown (Container per Inline-Style, Lucide im Dropdown erlaubt) -->
	<div style="padding: 16px 18px; border-top: 1px solid var(--g-rule-soft); position: relative;">
		<button
			onclick={() => userMenuOpen = !userMenuOpen}
			class="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors hover:bg-[rgba(196,90,42,0.10)]"
		>
			<span class="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
				{userInitial(shownName)}
			</span>
			<span class="truncate">{shownName}</span>
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
					onclick={() => { closeUserMenu(); }}
				>
					<UserIcon class="size-4 opacity-70" />
					Konto
				</a>
				<a
					href="/account#system-status"
					class="flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground transition-colors"
					onclick={() => { closeUserMenu(); }}
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
</aside>

<!-- MOBILE: Slide-in Drawer — z-[55] damit Drawer VOR Backdrop (z-50) liegt, TopAppBar z-[60] bleibt oben -->
<nav
	data-testid="mobile-drawer"
	class="fixed z-[55] h-full w-60 flex-col bg-sidebar text-sidebar-foreground p-4 transition-transform duration-200 desktop:hidden
	{mobileMenuOpen ? 'flex translate-x-0' : 'hidden -translate-x-full'}"
>
	<div class="mb-6"><Wordmark size="md" /></div>

	<!-- Mobile: Nav-Items -->
	{#each navItems as item}
		<a
			href={item.href}
			class="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent"
			class:bg-sidebar-accent={isActive(item.href)}
			onclick={closeMobileMenu}
		>
			{item.label}
		</a>
	{/each}

	<!-- Mobile drawer: Secondary items (Lucide erlaubt hier laut Spec) -->
	<div class="flex flex-col gap-1 mt-2">
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

	<!-- Mobile Footer: Logout -->
	<div class="mt-auto border-t border-border/50 pt-3">
		<form method="POST" action="/logout">
			<button type="submit" class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-destructive hover:bg-destructive/10">
				<LogOut class="size-4 opacity-70" />
				Abmelden
			</button>
		</form>
	</div>
</nav>
