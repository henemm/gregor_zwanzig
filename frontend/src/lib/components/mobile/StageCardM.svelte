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
	import { t, locale } from '$lib/i18n';
	import { etappenZeile } from '$lib/components/edit/etappenListe';
	import TempoKarteInhalt from '$lib/components/organisms/tempo-karte/TempoKarteInhalt.svelte';
	import { isPauseStage, formatStageNumber } from '$lib/components/shared/wizardHelpers';
	import StageDateField from '$lib/components/edit/StageDateField.svelte';
	import StageTimeField from '$lib/components/edit/StageTimeField.svelte';
	import { riskToPill, type StageRisk } from '$lib/utils/stageRisk';
	import { computeArrivalTimes, stageTempo } from '$lib/utils/naismith';
	import { computeHeaderStats } from '$lib/components/email-preview/headerStats';
	import type { Stage, Tempo } from '$lib/types';

	interface Props {
		stage: Stage;
		index: number;
		/** Wetter-Risiko (lazy via fetchStageRisk geladen, fail-soft null). */
		risk?: StageRisk | undefined;
		/** F7: aufgeklappt → Wegpunkt-Zeilen sichtbar. */
		open?: boolean;
		/** Issue #3196: Tempo des Trips für die ETA-Berechnung der Wegpunkt-Zeilen (DAV). */
		tempo?: Tempo | undefined;
		/** #2496 F1: gesetzt → Kartenkopf rendert ein inline-Datumsfeld. */
		onDateChange?: ((iso: string) => void) | undefined;
		/** #2496 F4: gesetzt → Kartenkopf rendert ein inline-Startzeitfeld. */
		onStartTimeChange?: ((hhmm: string) => void) | undefined;
		/** #2496 F1: erste Etappe → „· Trip-Start"-Marker. */
		isFirst?: boolean;
		/** Issue #3197: gesetzt → Knopf „Tempo ändern" (Etappe mit Wegpunkten) schaltet die Karte. */
		ontempoaendern?: (() => void) | undefined;
		/** Issue #3197: Etappen-Tempo-Karte dieser Etappe offen (Zustand hält das Panel). */
		tempoOffen?: boolean;
		/** Issue #3197: neues Etappen-Grundtempo (derselbe Handler wie Desktop). */
		onetappentempo?: ((tempo: Tempo) => void) | undefined;
		/** Issue #3197: „Trip-Tempo verwenden" (derselbe Handler wie Desktop). */
		ontriptempo?: (() => void) | undefined;
	}
	let {
		stage,
		index,
		risk = undefined,
		open = false,
		tempo = undefined,
		onDateChange = undefined,
		onStartTimeChange = undefined,
		isFirst = false,
		ontempoaendern = undefined,
		tempoOffen = false,
		onetappentempo = undefined,
		ontriptempo = undefined
	}: Props = $props();

	// Issue #3197: Gehzeit, Kennzeichen und Knopf aus derselben Quelle wie die Desktop-Liste
	// (etappenZeile: Pausentag bzw. < 2 Wegpunkte ohne Gehzeit und ohne Knopf).
	const zeile = $derived(tempo ? etappenZeile(stage, index, $locale, $t, tempo) : null);

	const isPause = $derived(isPauseStage(stage));
	const stageLabel = $derived(formatStageNumber(index));
	const riskPill = $derived(riskToPill(risk));

	// ETAs der Wegpunkt-Zeilen (F7) — dieselbe Naismith-Quelle wie die
	// Desktop-Sidebar; pro Etappe ab deren Startzeit.
	// Issue #3197: mit dem Tempo dieser Etappe (eigenes Grundtempo vor Trip-Tempo).
	const arrivals = $derived(
		computeArrivalTimes(stage, stage.start_time, tempo ? stageTempo(stage, tempo) : tempo)
	);

	const stats = $derived(
		(() => {
			const wps = stage.waypoints ?? [];
			let km: number | null = null;
			let ascent: number | null = null;
			if (wps.length >= 2) {
				let up = 0;
				for (let i = 1; i < wps.length; i++) {
					const diff = (wps[i].elevation_m ?? 0) - (wps[i - 1].elevation_m ?? 0);
					if (diff > 0) up += diff;
				}
				km = computeHeaderStats(stage).distanceKm;
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
			{#if onDateChange || onStartTimeChange}
				<!-- #2496 F1/F4: Tap/Enter auf den Feldern darf den Karten-Toggle der
				     Zeile (onclick/onkeydown im Aufrufer) nicht auslösen. -->
				<span
					class="date-edit"
					role="presentation"
					onclick={(e) => e.stopPropagation()}
					onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') e.stopPropagation(); }}
				>
					{#if onDateChange}
						<StageDateField variant="inline" value={stage.date} {isFirst} onchange={onDateChange} />
					{/if}
					{#if onStartTimeChange}
						<StageTimeField variant="inline" value={stage.start_time} onchange={onStartTimeChange} />
					{/if}
				</span>
			{:else if stage.date}
				<span class="date">{stage.date}</span>
			{/if}
		</div>
		{#if isPause}
			<div class="title pause-title">{$t('bausteine.etappe.pausentag')}</div>
			<div class="meta">{#if stage.location}⌂ {stage.location}{:else}⌂ {$t('bausteine.etappe.pause')}{/if}</div>
		{:else}
			<div class="title">{stage.name}</div>
			<div class="meta">
				{#if stats.km !== null}{$t('bausteine.etappe.km', { km: stats.km.toFixed(1) })}{/if}{#if stats.km !== null && stats.ascent !== null} · {/if}{#if stats.ascent !== null}↑{Math.round(stats.ascent)}{/if}
				{#if stats.wpCount > 0} · {$t('bausteine.etappe.wegpunkte', { anzahl: stats.wpCount })}{/if}
			</div>
			<!-- Issue #3197: Gehzeit mit Etappen-Tempo, Kennzeichen, Knopf „Tempo ändern" und die Karte
			     (nurGrundtempo). Taps hier dürfen den Karten-Toggle der Zeile nicht auslösen. -->
			{#if zeile?.meta || zeile?.tempoAendern}
				<div
					class="tempo-zeile"
					role="presentation"
					onclick={(e) => e.stopPropagation()}
					onkeydown={(e) => e.stopPropagation()}
				>
					{#if zeile.meta}<span class="gehzeit" data-testid="stage-cardm-gehzeit">{zeile.meta}</span>{/if}
					{#if zeile.eigenesTempo}<span class="eigenes-tempo" data-testid="stage-cardm-eigenes-tempo">{$t('trip.tempo.eigenes_tempo')}</span>{/if}
					{#if zeile.tempoAendern && ontempoaendern}
						<button
							type="button"
							class="tempo-knopf"
							data-testid="mobile-etappen-tempo-aendern"
							aria-expanded={tempoOffen}
							onclick={() => ontempoaendern?.()}
						>{$t('trip.hub.tempo_aendern')}</button>
					{/if}
				</div>
				{#if tempoOffen && zeile.tempoAendern && tempo}
					<div
						class="tempo-karte-mobil"
						role="presentation"
						onclick={(e) => e.stopPropagation()}
						onkeydown={(e) => e.stopPropagation()}
					>
						<TempoKarteInhalt
							tempo={stageTempo(stage, tempo)}
							nurGrundtempo
							onchange={(neu) => onetappentempo?.(neu)}
							ontriptempo={() => ontriptempo?.()}
						/>
					</div>
				{/if}
			{/if}
		{/if}
		{#if open && !isPause && stage.waypoints.length > 0}
			<div class="wp-rows" data-testid="stage-cardm-wp-rows">
				{#each stage.waypoints as wp, i (wp.id)}
					<div class="wp-row" data-testid="stage-cardm-wp-row">
						<span class="wp-num">{i + 1}</span>
						<span class="wp-name">{wp.name ?? $t('bausteine.etappe.wegpunkt', { nr: i + 1 })}</span>
						<span class="wp-meta">
							{#if wp.elevation_m != null}{$t('bausteine.etappe.hoehe', { hoehe: Math.round(wp.elevation_m) })}{/if}
							{#if arrivals[i]} · {$t('bausteine.etappe.eta', { zeit: arrivals[i] })}{/if}
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
		flex-wrap: wrap; /* #2601: Datum + Zeit brechen auf 390px um statt zu überlaufen */
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
		color: var(--g-ink-3);
	}
	.date-edit {
		min-width: 0;
		display: inline-flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--g-s-2);
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
	/* #3197: Gehzeit-Zeile mit „Tempo ändern" und Etappen-Tempo-Karte. */
	.tempo-zeile {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--g-s-2);
		margin-top: var(--g-s-2);
	}
	.gehzeit {
		font-family: var(--g-font-mono);
		font-size: var(--g-text-xs);
		color: var(--g-ink-2);
	}
	.eigenes-tempo {
		font-size: var(--g-text-xs);
		font-weight: 600;
		color: var(--g-ink-2);
	}
	.tempo-knopf {
		min-height: 44px;
		padding: 0 var(--g-s-3);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		background: var(--g-card);
		color: var(--g-ink);
		font: inherit;
		font-size: var(--g-text-xs);
		cursor: pointer;
	}
	.tempo-knopf:focus-visible {
		outline: 2px solid var(--g-accent);
		outline-offset: 2px;
	}
	.tempo-karte-mobil {
		margin-top: var(--g-s-2);
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
