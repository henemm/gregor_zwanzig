<script lang="ts">
	// Issue #373 — MField (kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// Label + Sub-Text-Rahmen um ein Eingabe-Snippet (Touch-Padding).
	// Token-basiert.
	//
	// Issue #2880: `pflicht` (Sternchen aria-hidden, aria-required setzt der Aufrufer) und
	// `side` (Hinweis rechtsbündig in der Beschriftungszeile, wie molecules/Field). Die
	// Beschriftung ist die Mono-Eyebrow des Design-Systems (vorher wirkungslose Klasse `mono`).
	//
	// Spec: docs/specs/modules/issue_373_mobile.md
	import type { Snippet } from 'svelte';

	interface Props {
		label?: string;
		sub?: string;
		side?: string;
		pflicht?: boolean;
		children?: Snippet;
	}

	let { label, sub, side, pflicht = false, children }: Props = $props();
</script>

<div style:margin-bottom="14px">
	{#if label || side}
		<div class="mfield-zeile">
			{#if label}
				<span class="mfield-label">{label}{#if pflicht}<span class="field-pflicht" aria-hidden="true">*</span>{/if}</span>
			{/if}
			{#if side}
				<span class="mfield-side">{side}</span>
			{/if}
		</div>
	{/if}
	{@render children?.()}
	{#if sub}
		<div
			style:font-size="12px"
			style:color="var(--g-ink-4)"
			style:margin-top="6px"
			style:line-height="1.4"
		>{sub}</div>
	{/if}
</div>

<style>
	.mfield-zeile {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 12px;
		margin-bottom: 6px;
	}
	.mfield-label {
		font-family: var(--g-font-mono);
		font-size: 11px;
		color: var(--g-ink-3);
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	.mfield-side {
		font-size: 12px;
		color: var(--g-ink-3);
	}
	.field-pflicht {
		margin-left: 3px;
		color: var(--g-bad);
	}
</style>
