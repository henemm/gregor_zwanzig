<script lang="ts">
	// StageCardM — vertikale Etappen-Karte der mobilen Listen-Ansicht
	// (Spec: docs/specs/modules/mobile_stages_tab_listen_only.md, Iteration 1).
	// Muster: docs/design/mobile/screen-trip-detail-mobile.jsx:208-234
	// (StageCardM im Trip-Detail-Mock). Katalog: COMPONENTS.md §7 (Mobile-Shell).
	//
	// Reine Präsentations-Komponente: DragHandle und SortableList verdrahtet
	// der Aufrufer (EditStagesPanelNew), analog CompareLocationRow im
	// Orte-Tab (ADR-0024 — Sortier-Infrastruktur wird geteilt, nicht kopiert).
	// Wegpunkt-Zeilen (F7) folgen in Iteration 2.
	import { Pill } from '$lib/components/atoms';
	import { isPauseStage, formatStageNumber } from '$lib/components/shared/wizardHelpers';
	import { riskToPill, type StageRisk } from '$lib/utils/stageRisk';
	import type { Stage } from '$lib/types';

	interface Props {
		stage: Stage;
		index: number;
		/** Wetter-Risiko (lazy via fetchStageRisk geladen, fail-soft null). */
		risk?: StageRisk | undefined;
	}
	let { stage, index, risk = undefined }: Props = $props();

	const isPause = $derived(isPauseStage(stage));
	const stageLabel = $derived(formatStageNumber(index));
	const riskPill = $derived(riskToPill(risk));

	const stats = $derived(
		(() => {
			const wps = stage.waypoints ?? [];
			let km: number | null = null;
			let ascent: number | null = null;
			if (wps.length >= 2) {
				let dist = 0;
				let up = 0;
				for (let i = 1; i < wps.length; i++) {
					const a = wps[i - 1];
					const b = wps[i];
					const dlat = (b.lat - a.lat) * 111.32;
					const dlon = (b.lon - a.lon) * 111.32 * Math.cos((a.lat * Math.PI) / 180);
					dist += Math.sqrt(dlat * dlat + dlon * dlon);
					const diff = (b.elevation_m ?? 0) - (a.elevation_m ?? 0);
					if (diff > 0) up += diff;
				}
				km = dist;
				ascent = up > 0 ? up : null;
			}
			return { km, ascent, wpCount: wps.length };
		})()
	);
</script>

<div class="stage-cardm" data-testid="stage-cardm" data-pause={isPause ? 'true' : undefined}>
	<div class="body">
		<div class="top">
			<span class="code">{stageLabel}{#if stage.code} · {stage.code}{/if}</span>
			{#if stage.date}<span class="date">{stage.date}</span>{/if}
		</div>
		{#if isPause}
			<div class="title pause-title">Pausentag</div>
			<div class="meta">{#if stage.location}⌂ {stage.location}{:else}⌂ Pause{/if}</div>
		{:else}
			<div class="title">{stage.name}</div>
			<div class="meta">
				{#if stats.km !== null}{stats.km.toFixed(1)} km{/if}{#if stats.km !== null && stats.ascent !== null} · {/if}{#if stats.ascent !== null}↑{Math.round(stats.ascent)}{/if}
				{#if stats.wpCount > 0} · {stats.wpCount} WP{/if}
			</div>
		{/if}
	</div>
	{#if !isPause}
		<div class="risk"><Pill tone={riskPill.tone}>{riskPill.label}</Pill></div>
	{/if}
</div>

<style>
	.stage-cardm {
		display: flex;
		align-items: flex-start;
		gap: var(--g-s-3);
		min-width: 0;
		min-height: 44px;
		padding: var(--g-s-3);
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		box-shadow: var(--g-shadow-1);
	}
	.stage-cardm[data-pause='true'] {
		background: var(--g-card-alt);
		border-style: dashed;
	}
	.body {
		flex: 1;
		min-width: 0;
	}
	.top {
		display: flex;
		align-items: baseline;
		gap: var(--g-s-2);
	}
	.code {
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		font-weight: 600;
		letter-spacing: var(--g-track-wide);
		color: var(--g-ink-3);
	}
	.date {
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		color: var(--g-ink-4);
	}
	.title {
		font-size: var(--g-text-sm);
		font-weight: 600;
		line-height: 1.3;
		margin-top: var(--g-s-1);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.pause-title {
		font-style: italic;
		color: var(--g-ink-2);
	}
	.meta {
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		color: var(--g-ink-3);
		margin-top: var(--g-s-1);
	}
	.risk {
		flex-shrink: 0;
		padding-top: var(--g-s-1);
	}
</style>
