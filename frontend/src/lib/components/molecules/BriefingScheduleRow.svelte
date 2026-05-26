<script lang="ts">
	// Issue #372 — BriefingScheduleRow-Molecule (kanonisch aus molecules.jsx, Svelte 5).
	//
	// Konfigurations-Zeile aus dem Trip-Wizard:
	// »Morgen-Briefing · 06:00 · [on]«. Toggle-getrieben. Time als Mono-Display.
	// `last` unterdrueckt den Bottom-Border. Nutzt Switch.
	//
	// Spec: docs/specs/modules/issue_372_molecules.md (AC-5)

	import { Switch } from '$lib/components/atoms';

	interface Props {
		label?: string;
		sub?: string;
		time?: string;
		enabled?: boolean;
		onToggle?: (next: boolean) => void;
		last?: boolean;
		class?: string;
	}

	let {
		label,
		sub,
		time,
		enabled = false,
		onToggle,
		last = false,
		class: className = ''
	}: Props = $props();
</script>

<div
	class={className}
	style:display="flex"
	style:align-items="center"
	style:padding="10px 0"
	style:border-bottom={last ? 'none' : '1px solid var(--g-rule-soft)'}
	style:gap="12px"
>
	<div style:flex="1" style:min-width="0">
		<div style:font-size="13px" style:font-weight="600">{label}</div>
		{#if sub}
			<div style:font-size="11px" style:color="var(--g-ink-3)" style:margin-top="2px">{sub}</div>
		{/if}
	</div>
	{#if time}
		<div
			style:font-family="var(--g-font-mono)"
			style:font-size="13px"
			style:font-weight="600"
			style:color="var(--g-accent-deep)"
			style:white-space="nowrap"
		>{time}</div>
	{/if}
	<Switch checked={enabled} onchange={onToggle} disabled={onToggle === undefined} tone="good" />
</div>
