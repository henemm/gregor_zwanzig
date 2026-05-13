<script lang="ts">
	// Epic #135 Step 4 (Issue #157) — Stage-Detail-Row.
	// Spec: docs/specs/modules/epic_135_step4_left_column.md §5.
	//
	// Native <button> mit onclick={onSelect} — Safari-tauglich, da onSelect
	// bereits in StageList pro Stage gebunden wird.

	import type { Stage } from '$lib/types';
	import { computeHeaderStats } from '$lib/components/email-preview/headerStats';
	import { Pill } from '$lib/components/ui/pill';

	interface Props {
		stage: Stage;
		index: number;
		code: string;
		selected: boolean;
		active: boolean;
		onSelect: () => void;
		now?: Date;
	}

	let {
		stage,
		index: _index, // wird derzeit nicht im Markup gebraucht, Spec-Kontrakt
		code,
		selected,
		active,
		onSelect,
		now: _now = new Date()
	}: Props = $props();

	const stats = $derived(computeHeaderStats(stage));
	const wptCount = $derived(stage.waypoints?.length ?? 0);

	// Lokaler Date-Helper — deutsches Kurzformat "DD.MM."
	function formatDate(iso: string | undefined | null): string {
		if (!iso) return '';
		const clean = iso.split('T')[0];
		const parts = clean.split('-');
		if (parts.length < 3) return '';
		const [, m, d] = parts;
		return `${d}.${m}.`;
	}

	const dateLabel = $derived(formatDate(stage.date));
</script>

<button
	type="button"
	data-testid="trip-stage-row-{stage.id}"
	data-selected={selected ? 'true' : 'false'}
	data-active={active ? 'true' : 'false'}
	class="g-card stage-row"
	onclick={onSelect}
>
	<header class="stage-row-header">
		<Pill
			tone={active ? 'accent' : 'default'}
			data-testid="trip-stage-row-code-{stage.id}"
			class="stage-code-pill"
		>
			{code}
		</Pill>
		<span class="eyebrow">{dateLabel}</span>
	</header>

	<h3 class="stage-row-title">{stage.name}</h3>

	<dl class="stat-strip">
		<div>
			<dt class="eyebrow">Distanz</dt>
			<dd>{stats.distanceKm.toFixed(1)} km</dd>
		</div>
		<div>
			<dt class="eyebrow">Aufstieg</dt>
			<dd>{stats.ascentM} Hm</dd>
		</div>
		<div>
			<dt class="eyebrow">Abstieg</dt>
			<dd>{stats.descentM} Hm</dd>
		</div>
		<div>
			<dt class="eyebrow">Wegpunkte</dt>
			<dd>{wptCount}</dd>
		</div>
	</dl>
</button>

<style>
	.stage-row {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		width: 100%;
		text-align: left;
		padding: 0.75rem 1rem;
		border-radius: 0.5rem;
		background: var(--g-surface-1, transparent);
		border: 1px solid var(--g-border, rgba(0, 0, 0, 0.08));
		cursor: pointer;
	}
	.stage-row[data-selected='true'] {
		border-color: var(--g-accent);
		box-shadow: 0 0 0 1px var(--g-accent);
	}
	.stage-row-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.stage-row-title {
		font-size: 1rem;
		font-weight: 600;
		line-height: 1.2;
		margin: 0;
	}
	.eyebrow {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.6875rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--g-ink-faint, #6b7280);
	}
	.stat-strip {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.5rem;
		margin: 0;
	}
	.stat-strip > div {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}
	.stat-strip dt {
		margin: 0;
	}
	.stat-strip dd {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--g-ink, inherit);
	}
	:global(.stage-code-pill) {
		display: inline-block;
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		background: var(--g-surface-2, rgba(0, 0, 0, 0.05));
		font-size: 0.75rem;
		font-weight: 600;
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
	}
	:global(.stage-code-pill[data-tone='accent']) {
		background: var(--g-accent, #3b82f6);
		color: white;
	}
</style>
