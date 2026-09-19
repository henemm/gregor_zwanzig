<script lang="ts">
	import { page } from '$app/state';
	import LayoutDashboard from '@lucide/svelte/icons/layout-dashboard';
	import RouteIcon from '@lucide/svelte/icons/route';
	import GitCompare from '@lucide/svelte/icons/git-compare';
	import ArchiveIcon from '@lucide/svelte/icons/archive';

	// Issue #373 — additive mobile-shell-Props (backward-compatible, Default
	// undefined; ohne sie laeuft die route-basierte #267-Aktiv-Logik unveraendert).
	//
	// Mobile-Shell S2 — Konto-Kreis (User-Badge mit Initialen) rechts neben der
	// Leiste. Er ist Navigation, kein FAB (AP-012): Glas wie die Leiste, kein
	// Akzent-Fill ausser dem Avatar selbst, auf jedem Screen gleich. Er erscheint
	// nur, wenn der Rahmen `onKonto` liefert (Showcase-MobileShell zeigt keinen).
	// Konzept: docs/design-requests/mobile_shell_ohne_topbar.md §2–§4.
	interface Props {
		active?: string;
		onChange?: (id: string) => void;
		initials?: string;
		onKonto?: () => void;
		kontoOpen?: boolean;
	}

	let {
		active = undefined,
		onChange = undefined,
		initials = '?',
		onKonto = undefined,
		kontoOpen = false
	}: Props = $props();

	const navItems = [
		{ href: '/',          id: 'home',    label: 'Übersicht', icon: LayoutDashboard, testid: 'bottom-nav-item-home'     },
		{ href: '/trips',     id: 'trips',   label: 'Trips',    icon: RouteIcon,       testid: 'bottom-nav-item-trips'    },
		{ href: '/compare',   id: 'compare', label: 'Vergleich', icon: GitCompare,      testid: 'bottom-nav-item-compare'  },
		{ href: '/archiv',    id: 'archive', label: 'Archiv',    icon: ArchiveIcon,     testid: 'bottom-nav-item-archive'   },
	];
</script>

<!-- Schwebende Glas-Leiste im iOS-27-Stil: Geometrie und Glas kommen
     ausschliesslich aus den --g-nav-* Tokens (app.css), damit Content-Padding
     und Toast-Anker dieselbe Oberkante kennen. Der Rahmen (`bottom-shell`)
     traegt die Position, Leiste und Konto-Kreis teilen sich das Glas. -->
<div data-testid="bottom-shell" class="bottom-shell fixed z-50 flex desktop:hidden">
	<nav data-testid="bottom-nav" class="bottom-nav nav-glass grid grid-cols-4">
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
				class="bottom-nav__item flex flex-col items-center justify-center"
				class:is-active={isActive}
			>
				<span class="bottom-nav__icon inline-flex">
					<svelte:component this={item.icon} class="size-6" />
				</span>
				<span class="bottom-nav__label">{item.label}</span>
			</a>
		{/each}
	</nav>
	{#if onKonto}
		<button
			type="button"
			data-testid="konto-kreis"
			class="konto-kreis nav-glass"
			aria-label="Konto"
			aria-haspopup="dialog"
			aria-expanded={kontoOpen}
			onclick={onKonto}
		>
			<span class="konto-kreis__avatar mono" aria-hidden="true">{initials}</span>
		</button>
	{/if}
</div>

<style>
	.bottom-shell {
		left: var(--g-nav-inset);
		right: var(--g-nav-inset);
		bottom: calc(var(--g-nav-gap) + env(safe-area-inset-bottom));
		height: var(--g-nav-h);
		gap: var(--g-nav-konto-gap);
		align-items: stretch;
	}

	.nav-glass {
		box-sizing: border-box;
		border-radius: var(--g-r-pill);
		background: var(--g-nav-glass);
		-webkit-backdrop-filter: blur(var(--g-nav-blur)) saturate(180%);
		backdrop-filter: blur(var(--g-nav-blur)) saturate(180%);
		border: 1px solid var(--g-nav-hairline);
		box-shadow: var(--g-shadow-3), inset 0 1px 0 var(--g-nav-highlight);
	}

	/* Ohne Backdrop-Filter (alte Engines) oder bei reduzierter Transparenz
	   (iOS-Bedienungshilfe) werden Leiste und Kreis opak — Lesbarkeit vor Optik. */
	@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
		.nav-glass {
			background: var(--g-paper-deep);
		}
	}
	@media (prefers-reduced-transparency: reduce) {
		.nav-glass {
			background: var(--g-paper-deep);
			-webkit-backdrop-filter: none;
			backdrop-filter: none;
		}
	}

	.bottom-nav {
		flex: 1 1 auto;
		min-width: 0;
		height: var(--g-nav-h);
		padding: var(--g-s-1);
		gap: var(--g-s-1);
	}

	.bottom-nav__item {
		min-height: 44px;
		gap: var(--g-s-1);
		border-radius: var(--g-r-pill);
		color: var(--g-ink-2); /* 8:1 auf Papier — lesbar auch bei Sonne */
		font-size: var(--g-text-xs);
		font-weight: 500;
		line-height: 1;
		letter-spacing: -0.005em;
		text-decoration: none;
	}
	.bottom-nav__item.is-active {
		background: var(--g-nav-active);
		color: var(--g-ink);
		font-weight: 600;
	}
	.bottom-nav__item.is-active .bottom-nav__icon {
		color: var(--g-accent);
	}

	/* Konto-Kreis: Glas-Scheibe in Leistenhoehe, Avatar-Badge 36 px in Akzent —
	   der einzige Akzent-Fill der ganzen Gruppe (Canvas „TabBar"). */
	.konto-kreis {
		flex: 0 0 var(--g-nav-h);
		width: var(--g-nav-h);
		height: var(--g-nav-h);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		cursor: pointer;
		color: inherit;
	}
	.konto-kreis__avatar {
		width: 36px;
		height: 36px;
		border-radius: 18px;
		background: var(--g-accent);
		color: #ffffff;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 13px;
		font-weight: 600;
		letter-spacing: 0.02em;
	}
	.konto-kreis[aria-expanded='true'] {
		background: var(--g-nav-active);
	}

	@media (prefers-reduced-motion: no-preference) {
		.bottom-nav__item,
		.konto-kreis {
			transition: background-color 160ms ease, color 160ms ease;
		}
	}
</style>
