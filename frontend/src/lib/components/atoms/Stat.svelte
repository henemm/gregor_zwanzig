<script lang="ts">
	// Issue #578 — Stat-Atom.
	// Kanonische Quelle: molecules.jsx::Stat (Zähler-Label-Wert-Paar)

	interface Props {
		label: string;
		value: string | number;
		sub?: string;
		unit?: string;
		tone?: 'default' | 'accent';
		layout?: 'stack' | 'inline';
		size?: 'sm' | 'md' | 'lg';
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

	const SIZES = { sm: { value: 18, label: 9 }, md: { value: 22, label: 10 }, lg: { value: 28, label: 10 } };
	const s = $derived(SIZES[size] ?? SIZES.md);
	const valueColor = $derived(tone === 'accent' ? 'var(--g-accent)' : 'var(--g-ink)');
	const valueFontSize = $derived(layout === 'inline' ? Math.max(s.value, 22) : s.value);
</script>

{#if layout === 'inline'}
	<div class={className} style:display="flex" style:align-items="baseline" style:gap="8px">
		<span
			style:font-size="{valueFontSize}px"
			style:font-weight="600"
			style:color={valueColor}
			style:letter-spacing="-0.02em"
			style:font-family={mono ? 'var(--g-font-mono)' : undefined}
			style:font-variant-numeric="tabular-nums"
			style:line-height="1"
			style:display="inline-flex"
			style:align-items="baseline"
			style:gap="4px"
		>{value}{#if unit}<span style:font-size="12px" style:color="var(--g-ink-4)" style:font-weight="500">{unit}</span>{/if}</span>
		<span
			class="mono"
			style:font-size="{s.label}px"
			style:color="var(--g-ink-3)"
			style:letter-spacing="0.12em"
			style:text-transform="uppercase"
			style:font-weight="500"
		>{label}</span>
	</div>
{:else}
	<div class={className}>
		<div style:margin-bottom="4px">
			<span
				class="mono"
				style:font-size="{s.label}px"
				style:color="var(--g-ink-3)"
				style:letter-spacing="0.12em"
				style:text-transform="uppercase"
				style:font-weight="500"
			>{label}</span>
		</div>
		<span
			style:font-size="{valueFontSize}px"
			style:font-weight="600"
			style:color={valueColor}
			style:letter-spacing="0"
			style:font-family={mono ? 'var(--g-font-mono)' : undefined}
			style:font-variant-numeric="tabular-nums"
			style:line-height="1"
			style:display="inline-flex"
			style:align-items="baseline"
			style:gap="4px"
		>{value}{#if unit}<span style:font-size="12px" style:color="var(--g-ink-4)" style:font-weight="500">{unit}</span>{/if}</span>
		{#if sub}
			<div style:font-size="11px" style:color="var(--g-ink-4)" style:margin-top="4px">{sub}</div>
		{/if}
	</div>
{/if}
