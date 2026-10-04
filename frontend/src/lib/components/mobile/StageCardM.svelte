<script lang="ts">
	// StageCardM — vertikale Etappen-Karte der mobilen Listen-Ansicht
	// (Spec: docs/specs/modules/mobile_stages_tab_listen_only.md).
	// Muster: docs/design/mobile/screen-trip-detail-mobile.jsx:208-234
	// (StageCardM im Trip-Detail-Mock). Katalog: COMPONENTS.md §7 (Mobile-Shell).
	//
	// Reine Präsentations-Komponente: DragHandle und SortableList verdrahtet
	// der Aufrufer (EditStagesPanelNew), analog CompareLocationRow im
	// Orte-Tab (ADR-0024 — Sortier-Infrastruktur wird geteilt, nicht kopiert).
	// F7: Tap auf die Karte klappt die Wegpunkt-Zeilen auf (auf/zu via `open`).
	import { Pill } from '$lib/components/atoms';
	import { isPauseStage, formatStageNumber } from '$lib/components/shared/wizardHelpers';
	import StageDateField from '$lib/components/edit/StageDateField.svelte';
	import { riskToPill, type StageRisk } from '$lib/utils/stageRisk';
	import { computeArrivalTimes, activityToSpeed } from '$lib/utils/naismith';
	import type { Stage, ActivityType } from '$lib/types';

	interface Props {
		stage: Stage;
		index: number;
		/** Wetter-Risiko (lazy via fetchStageRisk geladen, fail-soft null). */
		risk?: StageRisk | undefined;
		/** F7: aufgeklappt → Wegpunkt-Zeilen sichtbar. */
		open?: boolean;
		/** Aktivität für die ETA-Berechnung der Wegpunkt-Zeilen. */
		activityType?: ActivityType | undefined;
		/** #2496 F1: gesetzt → Kartenkopf rendert ein inline-Datumsfeld. */
		onDateChange?: ((iso: string) => void) | undefined;
		/** #2496 F1: erste Etappe → „· Trip-Start"-Marker. */
		isFirst?: boolean;
	}
	let {
		stage,
		index,
		risk = undefined,
		open = false,
		activityType = undefined,
		onDateChange = undefined,
		isFirst = false
	}: Props = $props();

	const isPause = $derived(isPauseStage(stage));
	const stageLabel = $derived(formatStageNumber(index));
	const riskPill = $derived(riskToPill(risk));

	// ETAs der Wegpunkt-Zeilen (F7) — dieselbe Naismith-Quelle wie die
	// Desktop-Sidebar; pro Etappe ab deren Startzeit.
	const arrivals = $derived(
		computeArrivalTimes(stage, stage.start_time, activityToSpeed(activityType))
	);

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

<div
	class="stage-cardm"
	data-testid="stage-cardm"
	data-pause={isPause ? 'true' : undefined}
	data-open={open ? 'true' : undefined}
>
	<div class="body">
		<div class="top">
			<span class="code">{stageLabel}{#if stage.code} · {stage.code}{/if}</span>
			{#if onDateChange}
				<!-- #2496 F1: Tap/Enter auf dem Feld darf den Karten-Toggle der Zeile
				     (onclick/onkeydown im Aufrufer) nicht auslösen. -->
				<span
					class="date-edit"
					role="presentation"
					onclick={(e) => e.stopPropagation()}
					onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') e.stopPropagation(); }}
				>
					<StageDateField variant="inline" value={stage.date} {isFirst} onchange={onDateChange} />
				</span>
			{:else if stage.date}
				<span class="date">{stage.date}</span>
			{/if}
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
		{#if open && !isPause && stage.waypoints.length > 0}
			<div class="wp-rows" data-testid="stage-cardm-wp-rows">
				{#each stage.waypoints as wp, i (wp.id)}
					<div class="wp-row" data-testid="stage-cardm-wp-row">
						<span class="wp-num">{i + 1}</span>
						<span class="wp-name">{wp.name ?? `Wegpunkt ${i + 1}`}</span>
						<span class="wp-meta">
							{#if wp.elevation_m != null}{Math.round(wp.elevation_m)} m{/if}
							{#if arrivals[i]} · ETA {arrivals[i]}{/if}
						</span>
					</div>
				{/each}
			</div>
		{/if}
	</div>
	{#if !isPause}
		<div class="risk"><Pill tone={riskPill.tone}>{riskPill.label}</Pill></div>
	{/if}
	<span class="chevron" data-testid="stage-cardm-chevron" class:open aria-hidden="true">
		<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
	</span>
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
	.date-edit {
		flex-shrink: 0;
		min-width: 0;
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
	.chevron {
		flex-shrink: 0;
		align-self: center;
		color: var(--g-ink-4);
		transition: transform 200ms ease-out;
	}
	.chevron.open {
		transform: rotate(180deg);
	}
	/* F7 — aufklappbare Wegpunkt-Zeilen (Muster: #503-Sheet-Liste,
	   screen-waypoint-editor-mobile.jsx:356-379) */
	.wp-rows {
		margin-top: var(--g-s-2);
		border-top: 1px solid var(--g-rule-soft);
	}
	.wp-row {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		min-height: 44px;
		padding: var(--g-s-1) 0;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.wp-row:last-child {
		border-bottom: none;
	}
	.wp-num {
		width: 22px;
		height: 22px;
		border-radius: 50%;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--g-card);
		border: 2px solid var(--g-accent);
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		font-weight: 700;
		color: var(--g-accent-deep);
	}
	.wp-name {
		flex: 1;
		min-width: 0;
		font-size: var(--g-text-sm);
		font-weight: 500;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.wp-meta {
		flex-shrink: 0;
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		color: var(--g-ink-3);
	}
</style>
