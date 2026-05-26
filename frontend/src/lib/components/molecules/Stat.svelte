<script lang="ts">
	// Issue #372 — Stat-Molecule (kanonisch aus molecules.jsx, Svelte 5).
	//
	// Tile-Statistik: Label + grosser Zahlenwert, optional Einheit & Sub-Text.
	// Zwei Layouts:
	//   layout="stack"  — Label oben (mono caps), Value unten gross. Default.
	//   layout="inline" — Value gross links, Label rechts (mono caps).
	// tone="accent" hebt den Value-Text hervor; size sm|md|lg skaliert.
	// Leerer/null value -> Em-Dash »—«.
	//
	// Kontrast: tone=accent nutzt --g-accent-deep (AA) statt Vorlagen-Wert
	// --g-accent (4.34:1, nicht AA); unit/sub nutzen --g-ink-3 statt
	// --g-ink-4 (WCAG-AA fuer echte Daten/Labels, #377).
	//
	// Spec: docs/specs/modules/issue_372_molecules.md (AC-3)

	type Tone = 'default' | 'accent';
	type Layout = 'stack' | 'inline';
	type Size = 'sm' | 'md' | 'lg';

	interface Props {
		label?: string;
		value?: string | number | null;
		sub?: string;
		unit?: string;
		tone?: Tone;
		layout?: Layout;
		size?: Size;
		mono?: boolean;
		class?: string;
	}

	let {
		label,
		value,
		sub,
		unit,
		tone = 'default',
		layout = 'stack',
		size = 'md',
		mono = false,
		class: className = ''
	}: Props = $props();

	const SIZES = {
		sm: { value: 18, label: 9 },
		md: { value: 22, label: 10 },
		lg: { value: 28, label: 10 }
	} as const;

	// Unbekannte size/layout/tone -> Default-Fallback (kein Crash).
	const s = $derived(SIZES[size] ?? SIZES.md);
	const isInline = $derived(layout === 'inline');
	const valueColor = $derived(tone === 'accent' ? 'var(--g-accent-deep)' : 'var(--g-ink)');
	const valueFontSize = $derived(isInline ? Math.max(s.value, 22) : s.value);

	// Leerer/null value -> Em-Dash.
	const displayValue = $derived(
		value == null || value === '' ? '—' : value
	);
</script>

{#snippet labelEl()}
	<span
		style:font-family="var(--g-font-mono)"
		style:font-size="{s.label}px"
		style:color="var(--g-ink-3)"
		style:letter-spacing="0.12em"
		style:text-transform="uppercase"
		style:font-weight="500"
	>{label}</span>
{/snippet}

{#snippet valueEl()}
	<span
		style:font-size="{valueFontSize}px"
		style:font-weight="600"
		style:color={valueColor}
		style:letter-spacing={isInline ? '-0.02em' : '0'}
		style:font-family={mono ? 'var(--g-font-mono)' : undefined}
		style:font-variant-numeric="tabular-nums"
		style:line-height="1"
		style:display="inline-flex"
		style:align-items="baseline"
		style:gap="4px"
	>
		{displayValue}
		{#if unit}
			<span style:font-size="12px" style:color="var(--g-ink-3)" style:font-weight="500">{unit}</span>
		{/if}
	</span>
{/snippet}

{#if isInline}
	<div class={className} style:display="flex" style:align-items="baseline" style:gap="8px">
		{@render valueEl()}
		{@render labelEl()}
	</div>
{:else}
	<div class={className}>
		<div style:margin-bottom="4px">{@render labelEl()}</div>
		{@render valueEl()}
		{#if sub}
			<div style:font-size="11px" style:color="var(--g-ink-3)" style:margin-top="4px">{sub}</div>
		{/if}
	</div>
{/if}
