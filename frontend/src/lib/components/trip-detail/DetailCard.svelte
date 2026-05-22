<script lang="ts">
	// Issue #302 — Generische Karten-Komponente für das 2×2-Übersicht-Grid.
	// Spec: docs/specs/modules/issue_302_trip_detail_page.md §2.
	//
	// Eyebrow + Titel + Liste aus {label, meta?, state?} + Aktions-Link.
	// Tokens ausschliesslich `var(--g-*)` — keine Inline-Hex, keine Magic-Pixel.
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { Dot } from '$lib/components/ui/dot';

	export type DetailCardItemState = 'on' | 'off' | 'warn';

	export interface DetailCardItem {
		label: string;
		meta?: string;
		state?: DetailCardItemState;
	}

	interface Props {
		eyebrow: string;
		title: string;
		items: readonly DetailCardItem[];
		actionText: string;
		actionHref: string;
		testid: string;
	}

	let { eyebrow, title, items, actionText, actionHref, testid }: Props = $props();

	// Mapping auf vorhandene Dot-Tones (siehe ui/dot/Dot.svelte):
	// on -> success, warn -> warning, off -> info (gedämpft via CSS-Override).
	function toneFor(state: DetailCardItemState | undefined): 'success' | 'warning' | 'info' {
		if (state === 'warn') return 'warning';
		if (state === 'off') return 'info';
		return 'success';
	}
</script>

<div class="detail-card" data-testid="detail-card-{testid}">
	<Eyebrow>{eyebrow}</Eyebrow>
	<h3 class="card-title">{title}</h3>
	<ul class="card-rows">
		{#each items as item}
			<li class="card-row" data-state={item.state ?? 'on'}>
				<Dot tone={toneFor(item.state)} size="sm" />
				<span class="row-label">{item.label}</span>
				{#if item.meta}
					<span class="row-meta">{item.meta}</span>
				{/if}
			</li>
		{/each}
	</ul>
	<a href={actionHref} class="card-action" data-testid="detail-card-action-{testid}">
		{actionText}
	</a>
</div>

<style>
	.detail-card {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding: 1.25rem;
		background: var(--g-surface-0);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md);
	}
	.card-title {
		margin: 0;
		font-size: 1.125rem;
		font-weight: 600;
		color: var(--g-ink);
		letter-spacing: -0.01em;
	}
	.card-rows {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.card-row {
		display: grid;
		grid-template-columns: auto 1fr auto;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.875rem;
		color: var(--g-ink);
	}
	.card-row[data-state='off'] {
		color: var(--g-ink-muted);
	}
	.row-label {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.row-meta {
		color: var(--g-ink-muted);
		font-variant-numeric: tabular-nums;
		font-size: 0.8125rem;
	}
	.card-action {
		margin-top: 0.25rem;
		align-self: flex-start;
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--g-accent);
		text-decoration: none;
	}
	.card-action:hover {
		text-decoration: underline;
	}
</style>
