<script lang="ts">
	import { page } from '$app/state';
	import LayoutDashboard from '@lucide/svelte/icons/layout-dashboard';
	import RouteIcon from '@lucide/svelte/icons/route';
	import GitCompare from '@lucide/svelte/icons/git-compare';
	import ArchiveIcon from '@lucide/svelte/icons/archive';

	// Issue #373 — additive mobile-shell-Props (backward-compatible, Default
	// undefined; ohne sie laeuft die route-basierte #267-Aktiv-Logik unveraendert).
	interface Props {
		active?: string;
		onChange?: (id: string) => void;
	}

	let { active = undefined, onChange = undefined }: Props = $props();

	const navItems = [
		{ href: '/',          id: 'home',    label: 'Übersicht', icon: LayoutDashboard, testid: 'bottom-nav-item-home'     },
		{ href: '/trips',     id: 'trips',   label: 'Touren',    icon: RouteIcon,       testid: 'bottom-nav-item-trips'    },
		{ href: '/compare',   id: 'compare', label: 'Vergleich', icon: GitCompare,      testid: 'bottom-nav-item-compare'  },
		{ href: '/archiv',    id: 'archive', label: 'Archiv',    icon: ArchiveIcon,     testid: 'bottom-nav-item-archive'   },
	];
</script>

<nav
	data-testid="bottom-nav"
	class="fixed bottom-0 left-0 right-0 z-50 grid grid-cols-4 border-t desktop:hidden"
	style="height: 64px; background: var(--g-paper-deep); border-color: var(--g-rule-soft); padding-bottom: env(safe-area-inset-bottom);"
>
	{#each navItems as item}
		{@const isActive =
			active !== undefined
				? active === item.id
				: item.href === '/'
					? page.url.pathname === item.href
					: page.url.pathname.startsWith(item.href)}
		<a
			href={item.href}
			data-testid={item.testid}
			aria-current={isActive ? 'page' : undefined}
			onclick={onChange ? () => onChange(item.id) : undefined}
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
