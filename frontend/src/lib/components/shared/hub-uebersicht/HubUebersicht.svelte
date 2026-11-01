<script lang="ts">
	// Issue #2682 (Epic #2345) — EIN Baustein für die Übersicht im Detail-Hub,
	// Trip (context="route") und Ortsvergleich (context="vergleich").
	// Spec: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md
	//
	// Aufbau (Entscheidung 1): Kennzahlen (Desktop-Leiste / mobil 2×2), darunter
	// die art-eigene Hauptfläche (Trip: `children` = Etappen/Wetter-Metriken aus
	// trip-detail/HubOverview), darunter Zusammenfassungs-Karten bzw. mobile
	// Pfeil-Zeilen (Vergleich: Orte, Wertebereiche; beide: Versand) und die
	// Versand-Historie. Alle Texte kommen aus hubUebersichtModell.ts — der
	// Baustein verzweigt nicht nach der Art, er rendert das Modell.
	// Herkunft des Vergleichs-Markups: compare/CompareTabs.svelte (Issue #1256
	// Scheiben 3/8/S8c, #1360, #1743, #2281), verhaltensgleich umgezogen.
	import type { Snippet } from 'svelte';
	import { onMount } from 'svelte';
	import { Card, Dot, Eyebrow } from '$lib/components/atoms';
	import BriefingHistory from '$lib/components/shared/BriefingHistory.svelte';
	import { api } from '$lib/api.js';
	import type { ComparePreset, Trip } from '$lib/types';
	import { deriveTripStatus } from '$lib/utils/tripStatus';
	import { deriveStatusFromPreset, type CompareStatus } from '$lib/components/compare/subscriptionHelpers';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';
	import type { NextBriefing } from '../versand-tab/nextBriefingText.ts';
	import { erstelleNaechstesBriefingLader } from '../versand-tab/naechstesBriefingLader.svelte.ts';
	import { erstelleBriefingHistoryLader } from '../briefingHistoryLader.svelte.ts';
	import { deriveRouteKennzahlen, deriveVergleichKennzahlen, type Sprungziel } from './hubUebersichtModell.ts';

	interface Props {
		context: 'route' | 'vergleich';
		/** route */
		trip?: Trip;
		/** vergleich */
		preset?: ComparePreset;
		/** vergleich: Status inkl. lokalem Pausieren/Aktivieren des Hubs (CompareTabs `status`). */
		status?: CompareStatus;
		/** vergleich: aufgelöste Orte in Hub-Reihenfolge (CompareTabs `resolvedLocations`). */
		orte?: Array<{ rank: number; loc?: { id: string; name: string } }>;
		/** `savedAt` lädt „Nächster Versand" nach jedem erfolgreichen Speichern neu (#1969). */
		saveController?: SaveStatus;
		onJump?: (tab: string, anchor?: 'versand') => void;
		/** Art-eigene Hauptfläche; bekommt den geladenen „Nächster Versand"-Wert (kein zweiter Abruf). */
		children?: Snippet<[NextBriefing | null]>;
	}

	let { context, trip, preset, status, orte, saveController, onJump, children }: Props = $props();

	const briefingId = $derived(trip?.id ?? preset?.id);

	// Issue #1969 (AC-23/AC-24): Backend-Wert aus GET /api/next-briefings, neu geladen nach Speichern.
	const naechstesBriefing = erstelleNaechstesBriefingLader(
		() => ({ context, id: briefingId, neuLaden: saveController?.savedAt }),
		(p) => api.get(p)
	);
	// Entscheidung 3 / AC-12: EIN Abruf der Versand-Historie für „Zuletzt raus" und die Liste.
	const historie = erstelleBriefingHistoryLader(
		() => ({ kind: context, id: briefingId }),
		(p) => api.get(p)
	);

	const modell = $derived(
		trip
			? deriveRouteKennzahlen(trip, deriveTripStatus(trip, new Date()), naechstesBriefing.wert, historie)
			: deriveVergleichKennzahlen(
					preset as ComparePreset,
					status ?? deriveStatusFromPreset(preset as ComparePreset),
					naechstesBriefing.wert,
					orte ?? []
				)
	);
	const mobileKennzahlen = $derived(modell.kennzahlen.filter((k) => k.mobil));

	// Issue #1256 Scheibe 8 (AC-22): Viewport-Weiche Desktop-Leiste vs. mobiles 2×2.
	let isMobileViewport = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(max-width: 899px)');
		isMobileViewport = mq.matches;
		const onChange = (e: MediaQueryListEvent) => { isMobileViewport = e.matches; };
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});

	// Kein `anchor?:` — die SSR-Pruefstaende strippen optionale Parameter nicht.
	function springe(ziel: Sprungziel) {
		return function doJump() {
			if (ziel.anchor) onJump?.(ziel.tab, ziel.anchor);
			else onJump?.(ziel.tab);
		};
	}
</script>

<div style="display: flex; flex-direction: column; gap: 22px">
	<!-- Kennzahlen — mobil 4 im 2×2 (Soll: screen-compare-detail-mobile.jsx:79-85), Desktop 5 in einer Leiste. -->
	{#if isMobileViewport}
		<div data-testid={modell.rasterTestid} class="hub-mobile-grid">
			{#each mobileKennzahlen as k (k.id)}
				<Card padding={14}>
					<div class="hub-mobile-stat-label">{k.label}</div>
					<div class="hub-mobile-stat-value" data-testid={k.testidMobil}>
						{#if k.punkt}
							<span class="hub-mobile-stat-inline"><Dot tone={k.punkt} size={7}/>{k.kurz}</span>
						{:else}
							{k.kurz}
						{/if}
					</div>
				</Card>
			{/each}
		</div>
	{:else}
		<Card padding={0} style="overflow: hidden">
			<div style="padding: 18px 24px; display: flex; align-items: center; gap: 40px; flex-wrap: wrap">
				{#each modell.kennzahlen as k (k.id)}
					<div>
						<div style="font-size: 11px; color: var(--g-ink-4); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 5px; font-family: var(--g-font-mono)">{k.label}</div>
						<div data-testid={k.testid} style="font-size: 14px; color: var(--g-ink); font-weight: 500">
							{#if k.punkt}
								<span style="display: inline-flex; align-items: center; gap: 7px"><Dot tone={k.punkt} size={7}/> {k.lang}</span>
							{:else}
								{k.lang}
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</Card>
	{/if}

	{@render children?.(naechstesBriefing.wert ?? null)}

	<!-- Zusammenfassungs-Karten (Desktop) / Pfeil-Zeilen (mobil) — Issue #1256 S8c (AC-3..AC-7). -->
	{#snippet summaryChevron()}
		<span class="hub-summary-row-chevron" aria-hidden="true">
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
		</span>
	{/snippet}
	{#if isMobileViewport}
		<div class="hub-summary-stack-mobile" data-testid={modell.stapelTestid}>
			{#each [modell.orteKarte, modell.wertebereicheKarte] as karte, i (i)}
				{#if karte}
					<button type="button" class="hub-summary-row-mobile" data-testid="hub-summary-row-mobile" onclick={springe(karte.sprungziel)}>
						<span class="hub-summary-row-body">
							<span class="hub-summary-row-eyebrow">{karte.eyebrow}</span>
							<span class="hub-summary-row-title">{karte.titel}</span>
							<span class="hub-summary-row-desc">{karte.beschreibungKurz}</span>
						</span>
						{@render summaryChevron()}
					</button>
				{/if}
			{/each}
			<button type="button" class="hub-summary-row-mobile" data-testid="hub-summary-row-mobile" onclick={springe(modell.versandKarte.sprungziel)}>
				<span class="hub-summary-row-body">
					<span class="hub-summary-row-eyebrow">Versand</span>
					<span class="hub-summary-row-title">{modell.versandKarte.titelKurz}</span>
					<span class="hub-summary-row-desc">{modell.versandKarte.beschreibungKurz}</span>
				</span>
				{@render summaryChevron()}
			</button>
		</div>
	{:else}
		<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px">
			{#each [modell.orteKarte, modell.wertebereicheKarte] as karte, i (i)}
				{#if karte}
					<Card padding={20} style="display: flex; flex-direction: column">
						<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
							<Eyebrow>{karte.eyebrow}</Eyebrow>
							<button onclick={springe(karte.sprungziel)} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
						</div>
						<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{karte.titel}</div>
						<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">{karte.beschreibungLang}</div>
					</Card>
				{/if}
			{/each}
			<Card padding={20} style="display: flex; flex-direction: column">
				<div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px">
					<Eyebrow>Versand</Eyebrow>
					<button data-testid={modell.versandKarte.testid} onclick={springe(modell.versandKarte.sprungziel)} style="background: none; border: none; cursor: pointer; padding: 0; font-size: 12px; font-weight: 600; color: var(--g-accent-deep); font-family: var(--g-font-sans)">Bearbeiten →</button>
				</div>
				<div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.01em">{modell.versandKarte.titelLang}</div>
				<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.6">{modell.versandKarte.beschreibungLang}</div>
			</Card>
		</div>
	{/if}

	<!-- Issue #2281: Versand-Historie (mobil und Desktop); Issue #2682: aus dem geteilten Lader. -->
	<BriefingHistory id={briefingId ?? ''} kind={context} lader={historie} />
</div>

<style>
	/* Issue #1256 Scheibe 8 (AC-22) — mobiler 4-Stat-2×2-Monitoring-Block */
	.hub-mobile-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	.hub-mobile-stat-label {
		font-size: 11px;
		color: var(--g-ink-4);
		letter-spacing: 0.16em;
		text-transform: uppercase;
		margin-bottom: 5px;
		font-family: var(--g-font-mono);
	}
	.hub-mobile-stat-value {
		font-size: 14px;
		color: var(--g-ink);
		font-weight: 500;
	}
	.hub-mobile-stat-inline {
		display: inline-flex;
		align-items: center;
		gap: 7px;
	}

	/* Issue #1256 S8c (AC-7) — mobiler Chevron-Summary-Stack (Soll:
	   screen-compare-detail-mobile.jsx:276-293). */
	.hub-summary-stack-mobile {
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3, 10px);
		overflow: hidden;
	}
	.hub-summary-row-mobile {
		display: flex;
		align-items: center;
		gap: 12px;
		width: 100%;
		text-align: left;
		padding: 13px 14px;
		background: transparent;
		border: none;
		border-top: 1px solid var(--g-rule-soft);
		cursor: pointer;
	}
	.hub-summary-stack-mobile .hub-summary-row-mobile:first-child {
		border-top: none;
	}
	.hub-summary-row-body {
		flex: 1;
		min-width: 0;
	}
	.hub-summary-row-eyebrow {
		display: block;
		font-family: var(--g-font-mono);
		font-size: 11px;
		color: var(--g-ink-4);
		letter-spacing: 0.12em;
		text-transform: uppercase;
		margin-bottom: 3px;
	}
	.hub-summary-row-title {
		display: block;
		font-size: 14.5px;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.hub-summary-row-desc {
		display: block;
		font-size: 12px;
		color: var(--g-ink-3);
		margin-top: 2px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.hub-summary-row-chevron {
		flex-shrink: 0;
		color: var(--g-ink-4);
		display: flex;
	}
</style>
