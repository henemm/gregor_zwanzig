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
	//   (padding 0.5rem/1rem, 0.875rem, Accent-Unterstrich); Zähler-Badges neutral
	//   in jeder Breite (#2837 S1, ADR-0110). Eine Optik für Trip und Vergleich,
	//   ohne Varianten-Prop (#2845, Spec rework_2845_hub_reiterleiste).
	// - data-slot-Vertrag (segmented-item/segmented-badge) bleibt bestehen —
	//   bestehende Test-IDs greifen weiter. Issue #2794 S3a (§7, AC-3): die Wurzel
	//   traegt KEIN data-slot="segmented" mehr — die Segmented-Box aus app.css
	//   (Rahmen, Rundung) gilt damit nicht fuer die Reiterleiste; der Block bleibt
	//   fuer das Segmented-Atom (WeatherConfigDialog) bestehen.
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
		border-radius: 9999px;
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
			padding: var(--g-s-2) var(--g-s-3);
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
			color: var(--g-paper);
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
			font-size: 10px;
			font-weight: 600;
			margin-left: 0;
		}
		.mtabbar :global([data-slot='segmented-item']:focus-visible) {
			outline: 2px solid var(--g-accent);
			outline-offset: 2px;
		}
	}
</style>
