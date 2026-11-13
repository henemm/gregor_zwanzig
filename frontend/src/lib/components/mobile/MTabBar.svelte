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
	//   #2913 c2 (Mockup): der aktive Reiter trägt zusätzlich aria-current="page".
	// - Mobile (<900px): horizontales Band + 16px-Fade + Scroll-Snap,
	//   Trigger min-height 44px, Pill-Optik, Badges neutral.
	// - Desktop (>=900px): ADR-0111 Punkt 1 (= ADR-0109 Punkt 7, Mockup Fassung 3):
	//   kein Kasten, EINE Grundlinie 1px --g-rule, Reiter 13px/500 --g-ink, aktiv 600
	//   mit 2px-Unterstrich --g-accent, Zähler Mono 10px neutral, Radius 3px. Eine
	//   Optik für Trip und Vergleich, ohne Varianten-Prop (#2845).
	// - Kein Kasten durch Struktur (#2794 S3a, §7 AC-3): die Wurzel trägt KEIN
	//   data-slot="segmented", die Segmented-Box aus app.css (Rahmen, Rundung) greift
	//   also nicht; der Block bleibt für das Segmented-Atom (WeatherConfigDialog).
	//   Nur die Trennstriche an segmented-item hält `border: none` fern. Der
	//   data-slot-Vertrag segmented-item/segmented-badge (Test-IDs) bleibt bestehen.
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
			aria-current={isActive ? 'page' : undefined}
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
	/* Desktop (>=900px): ADR-0111 Punkt 1 — kein Kasten (Wurzel ohne data-slot="segmented",
	   #2794 S3a), nur die eine Grundlinie --g-rule. */
	.mtabbar {
		display: flex;
		border-bottom: 1px solid var(--g-rule);
	}
	.mtabbar :global([data-slot='segmented-item']) {
		position: relative;
		padding: 0.5rem 1rem;
		font-size: 0.8125rem;
		font-weight: 500;
		/* #2794 S3a: keine senkrechten Segmented-Trenner aus app.css (`:not(:last-child)`). */
		border: none;
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
		/* #2794 S3a (AC-3): aktiver Reiter 600 stark. */
		font-weight: 600;
	}
	.mtabbar :global([data-slot='segmented-badge']) {
		display: inline-block;
		margin-left: 0.375rem;
		padding: 0.125rem 0.375rem;
		border-radius: 3px;
		/* #2837 S1 (ADR-0110, AC-10): Zähler neutral für Trip UND Vergleich (ink-3 auf
		   paper-deep ≈ 4,7:1, WCAG-AA) — Standard, ohne Variante (#2845).
		   Accent bleibt allein der Unterstrich des aktiven Reiters. */
		background: var(--g-paper-deep);
		color: var(--g-ink-3);
		font-family: var(--g-font-mono);
		/* #2794 S3a (AC-3): Badge Mono 10 px. */
		font-size: 10px;
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
			/* #2794 B2 (AC-4): seitlich 10 statt 12 px — vier DE-Pills passen bei 360 px
			   mit 15 px Reserve (vorher 1 px Überlauf); Höhe hält min-height 44 px. */
			padding: var(--g-s-2) var(--g-size-10px);
			border: 1px solid var(--g-rule);
			border-bottom: 1px solid var(--g-rule);
			border-radius: var(--g-r-pill);
			background: var(--g-card);
			color: var(--g-ink-2);
			font-size: var(--g-text-sm);
		}
		/* #2879: aktiver Reiter --g-accent-deep (Papier darauf 6,77:1, WCAG-AA). */
		.mtabbar :global([data-slot='segmented-item'][data-state='active']) {
			background: var(--g-accent-deep);
			border-color: var(--g-accent-deep);
			color: var(--g-on-accent);
			font-weight: 600;
			border-bottom-color: var(--g-accent-deep);
		}
		/* Badge neutral statt Accent-Fill (Design-Doc Paket 2, offener #585-Punkt
		   als Vorschlag umgesetzt): paper-deep/ink-3 — seit #2879 auch im aktiven
		   Reiter (vorher transluzent, 2,79:1; ADR-0110 „Zähler neutral"). */
		.mtabbar :global([data-slot='segmented-badge']) {
			background: var(--g-paper-deep);
			color: var(--g-ink-3);
			font-family: var(--g-font-mono);
			/* #2601 Runde 2 (AC-13): am Handy kein Text unter 11 px — Token statt 10 px. */
			font-size: var(--g-text-xs);
			font-weight: 600;
			margin-left: 0;
			/* Handy-Pillen unverändert (ADR-0111 Punkt 1 gilt nur am Computer). */
			border-radius: 9999px;
		}
		.mtabbar :global([data-slot='segmented-item']:focus-visible) {
			outline: 2px solid var(--g-accent);
			outline-offset: 2px;
		}
	}
</style>
