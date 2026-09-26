<script lang="ts">
	// MTabBar — geteilter mobiler Tab-Band-Baustein (Mobile Usability Paket 2,
	// Spec: docs/specs/modules/mobile_tab_leisten_mtabbar.md, Iteration 1).
	// Katalog: COMPONENTS.md §7 (Mobile-Shell).
	//
	// Verallgemeinert das bisher in TripTabs.svelte lokal gepflegte Muster
	// (Band + Fade, #1231) statt es zu kopieren (AP-006). Desktop-Optik
	// (Underline) und Mobile-Band (Pills) leben hier in einem Baustein;
	// Konsumenten tragen nur noch ihre Item-Daten.
	//
	// Verhalten:
	// - Aktiver Tab ist nach Mount und jedem Wechsel ohne User-Gese am Anfang
	//   des sichtbaren Bandbereichs (scrollIntoView inline:start, 12px Padding).
	// - WAI-ARIA: role=tablist/tab, aria-selected, roving tabindex (nur der
	//   aktive Tab tabindex=0), ←/→ aktiviert den Folge-Tab inkl. Fokus.
	// - Mobile (<900px): horizontales Band + 16px-Fade + Scroll-Snap,
	//   Trigger min-height 44px, Pill-Optik, Badges neutral.
	// - Desktop (>=900px): Underline-Optik 1:1 wie bisheriger TripTabs-Stand
	//   (padding 0.5rem/1rem, 0.875rem, Accent-Unterstrich, Accent-Fill-Badges).
	// - data-slot-Vertrag (segmented/segmented-item/segmented-badge) bleibt
	//   bestehen — bestehende Test-IDs und der app.css-Fallback greifen weiter.
	import { tick } from 'svelte';

	export interface MTabBarItem {
		value: string;
		label: string;
		badge?: number;
		testid?: string;
		badge_testid?: string;
	}

	interface Props {
		items: MTabBarItem[];
		active: string;
		onChange: (value: string) => void;
		/** Beschriftung der Leiste für Screenreader. */
		ariaLabel: string;
	}

	let { items, active, onChange, ariaLabel }: Props = $props();

	let bandEl = $state<HTMLDivElement | null>(null);

	function itemButtons(): HTMLButtonElement[] {
		return Array.from(bandEl?.querySelectorAll<HTMLButtonElement>('[data-slot="segmented-item"]') ?? []);
	}

	// Positionierung: aktiver Tab immer am Anfang des sichtbaren Bandbereichs
	// (Deep-Link/Mount ebenso wie jeder Wechsel). tick() wartet das Render.
	$effect(() => {
		const current = active;
		void items.length;
		const band = bandEl;
		if (!band || !current) return;
		void tick().then(() => {
			band
				.querySelector('[data-slot="segmented-item"][data-state="active"]')
				?.scrollIntoView({ inline: 'start', block: 'nearest' });
		});
	});

	function handleKeydown(e: KeyboardEvent, index: number): void {
		if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
		e.preventDefault();
		const next = (index + (e.key === 'ArrowRight' ? 1 : -1) + items.length) % items.length;
		const value = items[next]?.value;
		if (value == null) return;
		onChange(value);
		void tick().then(() => itemButtons()[next]?.focus());
	}
</script>

<div
	bind:this={bandEl}
	class="mtabbar"
	role="tablist"
	aria-label={ariaLabel}
	data-slot="segmented"
>
	{#each items as item, i (item.value)}
		{@const isActive = item.value === active}
		<button
			type="button"
			role="tab"
			data-slot="segmented-item"
			data-value={item.value}
			data-active={isActive ? 'true' : 'false'}
			data-state={isActive ? 'active' : 'inactive'}
			aria-selected={isActive ? 'true' : 'false'}
			tabindex={isActive ? 0 : -1}
			data-testid={item.testid ?? undefined}
			onclick={() => onChange(item.value)}
			onkeydown={(e) => handleKeydown(e, i)}
		>
			{item.label}
			{#if item.badge !== undefined && item.badge >= 1}
				<span data-slot="segmented-badge" data-testid={item.badge_testid ?? undefined}>{item.badge}</span>
			{/if}
		</button>
	{/each}
</div>

<style>
	/* Desktop (>=900px): Underline-Optik — 1:1 der bisherigen TripTabs-Regeln. */
	.mtabbar {
		display: flex;
		border-bottom: 1px solid var(--g-ink-faint);
	}
	.mtabbar :global([data-slot='segmented-item']) {
		position: relative;
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		font-weight: 500;
		border-bottom: 2px solid transparent;
		background: transparent;
		color: var(--g-ink);
		cursor: pointer;
		white-space: nowrap;
		font-family: var(--g-font-sans);
	}
	/* Override des app.css-globalen data-active-Fills (WeatherConfigDialog-Stil) —
	   TripTabs braucht transparenten Hintergrund + nur Unterstrich. */
	.mtabbar :global([data-slot='segmented-item'][data-active='true']) {
		background: transparent;
		color: var(--g-ink);
	}
	.mtabbar :global([data-slot='segmented-item'][data-state='active']) {
		border-bottom-color: var(--g-accent);
	}
	.mtabbar :global([data-slot='segmented-badge']) {
		display: inline-block;
		margin-left: 0.375rem;
		padding: 0.125rem 0.375rem;
		border-radius: 9999px;
		background: var(--g-accent);
		color: #fff;
		font-size: 0.75rem;
		font-weight: 600;
	}

	/* Mobile (<900px): horizontales Band + Fade (#1231) + Pill-Trigger. */
	@media (max-width: 899px) {
		.mtabbar {
			overflow-x: auto;
			white-space: nowrap;
			scrollbar-width: none;
			-ms-overflow-style: none;
			scroll-snap-type: x proximity;
			scroll-padding-inline: 12px;
			border-bottom: none;
			mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);
			-webkit-mask-image: linear-gradient(to right, transparent, black 16px, black calc(100% - 16px), transparent);
		}
		.mtabbar::-webkit-scrollbar {
			display: none;
		}
		.mtabbar :global([data-slot='segmented-item']) {
			white-space: nowrap;
			flex-shrink: 0;
			scroll-snap-align: start;
			min-height: 44px;
			display: inline-flex;
			align-items: center;
			gap: 6px;
			padding: var(--g-s-2) var(--g-s-3);
			border: 1px solid var(--g-rule);
			border-bottom: 1px solid var(--g-rule);
			border-radius: var(--g-r-pill);
			background: var(--g-card);
			color: var(--g-ink-2);
			font-size: var(--g-text-sm);
		}
		.mtabbar :global([data-slot='segmented-item'][data-state='active']) {
			background: var(--g-accent);
			border-color: var(--g-accent);
			color: var(--g-paper);
			font-weight: 600;
			border-bottom-color: var(--g-accent);
		}
		/* Badge neutral statt Accent-Fill (Design-Doc Paket 2, offener #585-Punkt
		   als Vorschlag umgesetzt): inaktiv paper-deep/ink-3, aktiv transluzent. */
		.mtabbar :global([data-slot='segmented-badge']) {
			background: var(--g-paper-deep);
			color: var(--g-ink-3);
			font-family: var(--g-font-mono);
			font-size: var(--g-text-xs);
			font-weight: 600;
			margin-left: 0;
		}
		.mtabbar :global([data-slot='segmented-item'][data-state='active'] [data-slot='segmented-badge']) {
			background: rgba(255, 255, 255, 0.22);
			color: var(--g-paper);
		}
		.mtabbar :global([data-slot='segmented-item']:focus-visible) {
			outline: 2px solid var(--g-accent);
			outline-offset: 2px;
		}
	}
</style>
