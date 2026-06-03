<script lang="ts" module>
	// Glyph-Mapping: Slug → Mono-Symbol (ASCII/Unicode-Fallback, kein Lucide-Hard-Dep).
	// Hält die Komponente leichtgewichtig und SSR-sicher.
	export function quickActionGlyph(slug: string): string {
		switch (String(slug || '').toLowerCase()) {
			case 'route':
				return '◆';
			case 'metrics':
				return '~';
			case 'clock':
				return '◷';
			case 'eye':
				return '◉';
			case 'bell':
				return '◐';
			case 'send':
				return '▸';
			case 'pause':
				return '‖';
			default:
				return '·';
		}
	}
</script>

<script lang="ts">
	// Issue #568 — QuickAction-Molecule (Startseite-Cockpit).
	// Spec: docs/specs/modules/issue_568_home_redesign.md
	//
	// Anchor-based Navigations-Kachel mit Glyph + Label + Sub + Chevron.
	// Mobile Touch-Target ≥ 44 px (AC-7). Kein onClick, direkter href.

	interface Props {
		glyph: string;
		label: string;
		sub: string;
		href: string;
		tone?: 'default' | 'accent';
		size?: 'md' | 'lg';
		class?: string;
	}

	let {
		glyph,
		label,
		sub,
		href,
		tone = 'default',
		size = 'md',
		class: className = ''
	}: Props = $props();

	const symbol = $derived(quickActionGlyph(glyph));
	const isAccent = $derived(tone === 'accent');
	const isLarge = $derived(size === 'lg');

	// Touch-Target: md = 44 px (Mobile-Minimum, AC-7), lg = 56 px.
	const minH = $derived(isLarge ? '56px' : '44px');
	const padY = $derived(isLarge ? '14px' : '10px');
</script>

<a
	class={className}
	{href}
	data-tone={tone}
	data-size={size}
	style:display="flex"
	style:align-items="center"
	style:gap="12px"
	style:min-height={minH}
	style:padding="{padY} 14px"
	style:background="var(--g-card)"
	style:border="1px solid var(--g-rule-soft)"
	style:border-radius="var(--g-r-3)"
	style:color="var(--g-ink)"
	style:text-decoration="none"
	style:transition="border-color 150ms ease"
>
	<span
		style:display="inline-flex"
		style:align-items="center"
		style:justify-content="center"
		style:width="32px"
		style:height="32px"
		style:flex-shrink="0"
		style:border-radius="var(--g-r-2)"
		style:background={isAccent ? 'var(--g-accent-tint)' : 'var(--g-paper-deep)'}
		style:color={isAccent ? 'var(--g-accent-deep)' : 'var(--g-ink-2)'}
		style:font-family="var(--g-font-mono)"
		style:font-size="15px"
		style:font-weight="600"
	>{symbol}</span>

	<span style:flex="1" style:min-width="0" style:display="flex" style:flex-direction="column" style:gap="2px">
		<span
			style:font-size="14px"
			style:font-weight="600"
			style:line-height="1.25"
			style:color="var(--g-ink)"
			style:white-space="nowrap"
			style:overflow="hidden"
			style:text-overflow="ellipsis"
		>{label}</span>
		<span
			style:font-size="12px"
			style:line-height="1.3"
			style:color="var(--g-ink-3)"
			style:white-space="nowrap"
			style:overflow="hidden"
			style:text-overflow="ellipsis"
		>{sub}</span>
	</span>

	<span
		style:font-family="var(--g-font-mono)"
		style:font-size="14px"
		style:color="var(--g-ink-3)"
		style:flex-shrink="0"
		aria-hidden="true"
	>›</span>
</a>

<style>
	a:hover {
		border-color: var(--g-accent) !important;
	}
	a:focus-visible {
		outline: 2px solid var(--g-accent);
		outline-offset: 2px;
	}
</style>
