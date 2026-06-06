<script lang="ts">
	// Issue #372 — ChannelRow-Molecule (kanonisch aus molecules.jsx, Svelte 5).
	//
	// Kanal-Konfigurations-Zeile: Kind + Target-Adresse + Switch + optional Sub.
	// Zwei Layouts:
	//   default      — als Card-alt-Karte mit Rundung (Desktop, Wizard-Listen)
	//   dense=true   — reihen-style, mit Bottom-Border (--g-rule-soft)
	// onToggle=undefined -> Switch rendert read-only (kein Crash).
	//
	// Kontrast: sub nutzt --g-ink-3 statt Vorlagen-Wert --g-ink-4 (WCAG-AA, #377).
	//
	// Spec: docs/specs/modules/issue_372_molecules.md (AC-2)

	import { Switch } from '$lib/components/atoms';

	interface Props {
		kind: string; // "Email" | "Telegram" | "SMS"
		target?: string; // z. B. "gregor_zwanzig@henemm.com"
		active?: boolean;
		sub?: string;
		onToggle?: (next: boolean) => void; // ohne -> read-only
		dense?: boolean;
		last?: boolean;
		class?: string;
	}

	let {
		kind,
		target,
		active = false,
		sub,
		onToggle,
		dense = false,
		last = false,
		class: className = ''
	}: Props = $props();
</script>

{#if dense}
	<div
		class={className}
		style:display="flex"
		style:align-items="center"
		style:padding="10px 0"
		style:border-bottom={last ? 'none' : '1px solid var(--g-rule-soft)'}
		style:gap="12px"
	>
		<span
			style:font-family="var(--g-font-mono)"
			style:font-size="10px"
			style:width="60px"
			style:text-transform="uppercase"
			style:letter-spacing="0.08em"
			style:color="var(--g-ink-3)"
		>{kind}</span>
		<div style:flex="1" style:min-width="0">
			<div
				style:font-family="var(--g-font-mono)"
				style:font-size="12px"
				style:color="var(--g-ink)"
				style:white-space="nowrap"
				style:overflow="hidden"
				style:text-overflow="ellipsis"
			>{target}</div>
			{#if sub}
				<div style:font-size="10px" style:color="var(--g-ink-3)" style:margin-top="2px">{sub}</div>
			{/if}
		</div>
		<Switch checked={active} onchange={onToggle} disabled={onToggle === undefined} size="lg" tone="good" />
	</div>
{:else}
	<div
		class={className}
		style:display="flex"
		style:align-items="center"
		style:gap="12px"
		style:padding="10px 14px"
		style:background="var(--g-card-alt)"
		style:border-radius="var(--g-r-2)"
	>
		<span
			style:font-family="var(--g-font-mono)"
			style:font-size="9px"
			style:width="56px"
			style:text-transform="uppercase"
			style:letter-spacing="0.08em"
			style:color="var(--g-ink-3)"
		>{kind}</span>
		<div style:flex="1" style:min-width="0">
			<div
				style:font-family="var(--g-font-mono)"
				style:font-size="12px"
				style:color="var(--g-ink)"
				style:white-space="nowrap"
				style:overflow="hidden"
				style:text-overflow="ellipsis"
			>{target}</div>
			{#if sub}
				<div style:font-size="10px" style:color="var(--g-ink-3)" style:margin-top="2px">{sub}</div>
			{/if}
		</div>
		<Switch checked={active} onchange={onToggle} disabled={onToggle === undefined} tone="good" />
	</div>
{/if}
