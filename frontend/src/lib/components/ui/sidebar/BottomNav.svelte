<script lang="ts">
	import { page } from '$app/state';
	import LayoutDashboard from '@lucide/svelte/icons/layout-dashboard';
	import RouteIcon from '@lucide/svelte/icons/route';
	import GitCompare from '@lucide/svelte/icons/git-compare';
	import MapPin from '@lucide/svelte/icons/map-pin';

	const navItems = [
		{ href: '/',          label: 'Übersicht', icon: LayoutDashboard, testid: 'bottom-nav-item-home'     },
		{ href: '/trips',     label: 'Trips',     icon: RouteIcon,       testid: 'bottom-nav-item-trips'    },
		{ href: '/compare',   label: 'Vergleich', icon: GitCompare,      testid: 'bottom-nav-item-compare'  },
		{ href: '/locations', label: 'Locations', icon: MapPin,          testid: 'bottom-nav-item-locations' },
	];
</script>

<nav
	data-testid="bottom-nav"
	class="fixed bottom-0 left-0 right-0 z-50 grid grid-cols-4 border-t desktop:hidden"
	style="height: 64px; background: var(--g-paper-deep); border-color: var(--g-rule-soft); padding-bottom: env(safe-area-inset-bottom);"
>
	{#each navItems as item}
		{@const isActive = item.href === '/' ? page.url.pathname === item.href : page.url.pathname.startsWith(item.href)}
		<a
			href={item.href}
			data-testid={item.testid}
			aria-current={isActive ? 'page' : undefined}
			class="flex flex-col items-center justify-center gap-1 text-[10px] transition-colors"
			style={isActive
				? 'box-shadow: inset 0 2px 0 var(--g-accent); color: var(--g-ink); font-weight: 600;'
				: 'color: var(--g-ink-muted); font-weight: 500;'}
		>
			<svelte:component this={item.icon} class="size-[22px]" />
			<span>{item.label}</span>
		</a>
	{/each}
</nav>
