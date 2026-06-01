<script lang="ts">
	// WaypointEditorPage — dedizierter Vollbild-Wegpunkt-Editor fuer /trips/[id]/edit.
	// Spec: docs/specs/modules/issue_503_wegpunkt_editor_fix.md
	//
	// Uebernimmt das State-/Mutation-Pattern aus WaypointsPanel.svelte (Architektur-Vorbild),
	// ergaenzt um Navigation nach Save (goto('/trips')) und Mobile-Layout (Sheet + StageNav).
	// Desktop ≥900px: Breadcrumb-Header, EtappenStrip-Wrapper, Stage-Header, Karte+Profil-Cards
	//   links, Wegpunkt-Sidebar-Card rechts, Footer.
	// Mobile ≤899px: TopAppBar mit Eyebrow + Titel, StageNavDropdown, Vollbreite-Karte mit
	//   floating Profil-Strip + FAB-Buttons, Bottom-Sheet mit 3 Snap-Positionen (peek/half/full).

	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import EtappenStrip from '$lib/components/trip-detail/waypoints/EtappenStrip.svelte';
	import MapCanvas from '$lib/components/trip-detail/waypoints/MapCanvas.svelte';
	import ProfileEditor from '$lib/components/trip-detail/waypoints/ProfileEditor.svelte';
	import WaypointCard from '$lib/components/trip-detail/waypoints/WaypointCard.svelte';
	import PauseStageView from '$lib/components/trip-detail/waypoints/PauseStageView.svelte';
	import { Btn } from '$lib/components/atoms';
	import StageNavDropdown from './StageNavDropdown.svelte';
	import AISuggestionBar from './AISuggestionBar.svelte';
	import { isPauseStage } from '$lib/components/trip-wizard/wizardHelpers';
	import { stripSuggested } from '$lib/utils/waypointEditor';
	import { computeArrivalTimes } from '$lib/utils/naismith';
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
	import type { Trip, Stage } from '$lib/types';

	interface Props {
		trip: Trip;
	}
	let { trip }: Props = $props();

	// State (identisch mit WaypointsPanel)
	let localStages = $state<Stage[]>(JSON.parse(JSON.stringify(trip.stages)));
	let activeStageId = $state<string>(trip.stages.find((s) => !isPauseStage(s))?.id ?? '');
	let activeWaypointId = $state<string | null>(null);
	let saving = $state(false);
	let saveError = $state<string | null>(null);

	// Mobile Bottom-Sheet Snaps (AC-11)
	const snapHeights = { peek: 92, half: 320, full: 540 } as const;
	type SnapState = 'peek' | 'half' | 'full';
	let mobileSnap = $state<SnapState>('half');

	function cycleSnap(): void {
		if (mobileSnap === 'peek') mobileSnap = 'half';
		else if (mobileSnap === 'half') mobileSnap = 'full';
		else mobileSnap = 'half';
	}

	// Viewport-Erkennung — rendert genau EIN Layout (vermeidet doppelte data-testids).
	let isMobile = $state(false);
	$effect(() => {
		if (!browser) return;
		const mq = window.matchMedia('(max-width: 899px)');
		isMobile = mq.matches;
		const onChange = (e: MediaQueryListEvent) => {
			isMobile = e.matches;
		};
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});

	// Derivations
	const activeStage = $derived(localStages.find((s) => s.id === activeStageId) ?? null);
	const activeIsPause = $derived(activeStage ? isPauseStage(activeStage) : false);
	const activeStageIndex = $derived(localStages.findIndex((s) => s.id === activeStageId));
	const prevStage = $derived(activeStageIndex > 0 ? localStages[activeStageIndex - 1] : null);
	const nextStage = $derived(
		activeStageIndex < localStages.length - 1 ? localStages[activeStageIndex + 1] : null
	);
	const arrivals = $derived(
		activeStage ? computeArrivalTimes(activeStage, activeStage.start_time) : []
	);
	const hasSuggested = $derived(activeStage?.waypoints.some((w) => w.suggested) ?? false);

	// Save-Handler — Read-Modify-Write: bestehenden Trip mergen, nur stages ersetzen.
	async function handleSave(): Promise<void> {
		saving = true;
		saveError = null;
		try {
			await api.put(`/api/trips/${trip.id}`, { ...trip, stages: stripSuggested(localStages) });
			goto('/trips');
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Speichern fehlgeschlagen';
		} finally {
			saving = false;
		}
	}

	function handleCancel(): void {
		goto('/trips');
	}

	// Stage-/Map-Handler
	function handleStagesReorder(stages: Stage[]): void {
		localStages = stages;
	}
	function handleStageActivate(stageId: string): void {
		activeStageId = stageId;
		activeWaypointId = null;
	}
	function handleWaypointActivate(waypointId: string): void {
		activeWaypointId = waypointId;
	}
	function handleProfileAdd(): void {
		// Issue #407: Hinzufuegen via Profil-Klick ist Out of Scope dieses Screens.
		// Prop bleibt fuer ProfileEditor-Kompatibilitaet gesetzt (no-op).
	}
	function handlePauseInsert(_afterIndex: number): void {
		// Issue #503: Pause-Insert ist Out of Scope dieses Screens (No-Op).
		// Prop bleibt fuer EtappenStrip-Kompatibilitaet gesetzt.
	}

	// Waypoint-Mutations (Factory-Pattern, Safari-Closure-Schutz — siehe WaypointsPanel-Vorbild).
	function makeConfirmHandler(stageId: string, waypointId: string) {
		return function handleConfirm() {
			localStages = localStages.map((s) =>
				s.id !== stageId
					? s
					: {
							...s,
							waypoints: s.waypoints.map((w) =>
								w.id !== waypointId ? w : { ...w, suggested: undefined }
							)
						}
			);
		};
	}
	function makeRejectHandler(stageId: string, waypointId: string) {
		return function handleReject() {
			localStages = localStages.map((s) =>
				s.id !== stageId
					? s
					: { ...s, waypoints: s.waypoints.filter((w) => w.id !== waypointId) }
			);
		};
	}
	function makeRenameHandler(stageId: string, waypointId: string) {
		return function handleRename() {
			const newName = prompt('Neuer Name:');
			if (!newName) return;
			localStages = localStages.map((s) =>
				s.id !== stageId
					? s
					: {
							...s,
							waypoints: s.waypoints.map((w) =>
								w.id !== waypointId ? w : { ...w, name: newName }
							)
						}
			);
		};
	}
	function makeDeleteHandler(stageId: string, waypointId: string) {
		return function handleDelete() {
			localStages = localStages.map((s) =>
				s.id !== stageId
					? s
					: { ...s, waypoints: s.waypoints.filter((w) => w.id !== waypointId) }
			);
		};
	}
	function makeActivateHandler(waypointId: string) {
		return function handleActivate() {
			activeWaypointId = waypointId;
		};
	}

	// KI-Vorschlag (Mobile): erster suggested-Wegpunkt uebernehmen/verwerfen.
	function handleAcceptSuggested(waypointId: string): void {
		if (!activeStage) return;
		makeConfirmHandler(activeStage.id, waypointId)();
	}
	function handleRejectSuggested(waypointId: string): void {
		if (!activeStage) return;
		makeRejectHandler(activeStage.id, waypointId)();
	}
</script>

<div data-testid="waypoint-editor-page" class="wp-editor">
	{#if isMobile}
		<!-- ============================ MOBILE (≤899px) ============================ -->
		<div class="wp-editor-mobile">
			<header data-testid="wp-editor-topbar" class="mobile-topbar">
				<Btn
					variant="ghost"
					size="icon-sm"
					data-testid="wp-editor-back-btn"
					onclick={handleCancel}
					aria-label="Zurück"
				>
					<ArrowLeftIcon class="size-5" />
				</Btn>
				<div class="mobile-topbar-title">
					<span class="mobile-eyebrow mono">{trip.name} · {localStages.length} Etappen</span>
					<h1 class="mobile-title">Wegpunkt-Editor</h1>
				</div>
				<span class="mobile-topbar__spacer"></span>
			</header>

			<StageNavDropdown
				stages={localStages}
				{activeStageId}
				prev={prevStage}
				next={nextStage}
				onActivate={handleStageActivate}
			/>

			<!-- (StageDateField folgt in Issue #498) -->

			{#if activeStage}
				{#if activeIsPause}
					<PauseStageView stage={activeStage} {prevStage} {nextStage} />
				{:else}
					<!-- Karten-Bereich mit floating Overlays -->
					<div class="mobile-map">
						<MapCanvas
							stage={activeStage}
							{activeWaypointId}
							onWaypointActivate={handleWaypointActivate}
						/>

						<!-- Profil-Strip floating links oben (AC-10) -->
						<div class="mobile-profile-strip" data-testid="wp-editor-profile-strip">
							<span class="profile-strip-name">{activeStage.name}</span>
							<span class="mono profile-strip-stats">
								{activeStage.waypoints.length} WP
							</span>
						</div>

						<!-- FAB-Buttons rechts (AC-10) -->
						<div class="mobile-fabs" data-testid="wp-editor-fabs">
							<button type="button" class="fab" data-testid="wp-editor-fab-add" disabled aria-label="Wegpunkt hinzufügen">+</button>
							<button type="button" class="fab" data-testid="wp-editor-fab-map" disabled aria-label="Kartentyp">⊞</button>
							<button type="button" class="fab" data-testid="wp-editor-fab-search" disabled aria-label="Suche">⌕</button>
						</div>

						<!-- Bottom-Sheet: 3 Snaps (peek/half/full) (AC-11) -->
						<div
							class="mobile-sheet"
							data-testid="wp-editor-sheet"
							style="height:{snapHeights[mobileSnap]}px"
						>
							<!-- Grip -->
							<button
								type="button"
								class="sheet-grip-btn"
								onclick={cycleSnap}
								aria-label="Sheet vergrößern/verkleinern"
							>
								<div class="mobile-sheet__grip" aria-hidden="true"></div>
							</button>

							<!-- Sheet-Header -->
							<div class="sheet-header">
								<div class="sheet-header-left">
									<span class="mono eyebrow-small">Höhenprofil &amp; Wegpunkte</span>
									{#if activeWaypointId}
										{@const activeWp = activeStage.waypoints.find((w) => w.id === activeWaypointId)}
										{#if activeWp}
											<span class="sheet-wp-name">{activeWp.name}</span>
										{/if}
									{/if}
								</div>
								{#if mobileSnap !== 'peek'}
									<button
										type="button"
										class="sheet-collapse-btn"
										onclick={() => (mobileSnap = 'peek')}
										aria-label="Sheet verkleinern"
									>↓</button>
								{/if}
							</div>

							<div class="sheet-body">
								<ProfileEditor
									stage={activeStage}
									{activeWaypointId}
									onWaypointActivate={handleWaypointActivate}
									onProfileAdd={handleProfileAdd}
								/>

								{#if mobileSnap !== 'peek'}
									<!-- KI-Aktions-Buttons oben wenn KI-Vorschlag aktiv (AC-12) -->
									{#if hasSuggested}
										<AISuggestionBar
											stage={activeStage}
											onAccept={handleAcceptSuggested}
											onReject={handleRejectSuggested}
										/>
									{/if}

									<!-- Prominente KI-Button-Zeile fuer aktiven Vorschlag (AC-12) -->
									{#if activeWaypointId}
										{@const activeWp = activeStage.waypoints.find((w) => w.id === activeWaypointId)}
										{#if activeWp?.suggested}
											<div class="sheet-ki-actions">
												<Btn
													variant="primary"
													data-testid="wp-editor-ki-accept"
													onclick={makeConfirmHandler(activeStage.id, activeWaypointId)}
												>
													KI-Vorschlag übernehmen
												</Btn>
												<Btn
													variant="ghost"
													data-testid="wp-editor-ki-reject"
													onclick={makeRejectHandler(activeStage.id, activeWaypointId)}
												>
													Verwerfen
												</Btn>
											</div>
										{/if}
									{/if}

									<div class="sheet-list">
										{#each activeStage.waypoints as waypoint, i (waypoint.id)}
											<WaypointCard
												{waypoint}
												index={i}
												active={waypoint.id === activeWaypointId}
												arrival={arrivals[i]}
												onActivate={makeActivateHandler(waypoint.id)}
												onConfirm={makeConfirmHandler(activeStage.id, waypoint.id)}
												onReject={makeRejectHandler(activeStage.id, waypoint.id)}
												onRename={makeRenameHandler(activeStage.id, waypoint.id)}
												onDelete={makeDeleteHandler(activeStage.id, waypoint.id)}
											/>
										{/each}
									</div>
								{/if}
							</div>
						</div>
					</div>
				{/if}
			{/if}

			<footer class="wp-editor-footer">
				<Btn
					variant="primary"
					data-testid="wp-editor-save-btn"
					disabled={saving}
					onclick={handleSave}
				>
					{saving ? 'Speichern…' : 'Speichern'}
				</Btn>
				<Btn
					variant="ghost"
					data-testid="wp-editor-cancel-btn"
					disabled={saving}
					onclick={handleCancel}
				>
					Abbrechen
				</Btn>
				{#if saveError}
					<span data-testid="wp-editor-save-error" class="save-error">{saveError}</span>
				{/if}
			</footer>
		</div>
	{:else}
		<!-- ============================ DESKTOP (≥900px) =========================== -->
		<div class="wp-editor-desktop">
			<!-- Breadcrumb-Header (AC-3) -->
			<header class="wp-header" data-testid="wp-editor-header">
				<nav class="wp-breadcrumb mono">
					<span class="breadcrumb-dim">{trip.name}</span>
					<span class="breadcrumb-sep">/</span>
					<span class="breadcrumb-dim">{activeStage?.name ?? '—'}</span>
					<span class="breadcrumb-sep">/</span>
					<span>Wegpunkte</span>
				</nav>
				<div class="wp-header-actions">
					<Btn variant="ghost" size="sm" data-testid="wp-editor-ki-btn" disabled>
						KI-Vorschläge neu berechnen
					</Btn>
					<Btn
						variant="primary"
						size="sm"
						data-testid="wp-editor-save-btn-header"
						disabled={saving}
						onclick={handleSave}
					>
						{saving ? 'Speichern…' : 'Speichern'}
					</Btn>
				</div>
			</header>

			<!-- EtappenStrip-Wrapper (AC-8) -->
			<div class="etappen-strip-wrapper">
				<div class="etappen-strip-head">
					<span class="mono eyebrow-text">Etappen · drag zum Sortieren · + Pause zwischen Etappen</span>
					<span class="mono strip-counter">
						{localStages.filter((s) => !isPauseStage(s)).length} GPX · {localStages.filter((s) => isPauseStage(s)).length} Pause
					</span>
				</div>
				<EtappenStrip
					stages={localStages}
					{activeStageId}
					onStagesReorder={handleStagesReorder}
					onStageActivate={handleStageActivate}
					onPauseInsert={handlePauseInsert}
				/>
				<button
					type="button"
					class="add-stage-btn mono"
					data-testid="wp-editor-add-stage-btn"
					disabled
				>+ Etappe</button>
			</div>

			<!-- Stage-Inhaltsbereich -->
			{#if activeStage}
				<div class="wp-editor-content">
					{#if activeIsPause}
						<PauseStageView stage={activeStage} {prevStage} {nextStage} />
					{:else}
						<!-- Stage-Header (StageDateField folgt in Issue #498) -->
						<div class="stage-header">
							<div class="stage-header-left">
								<span class="mono eyebrow-small">Etappe · {activeStage.name}</span>
								<h1 class="stage-title">{activeStage.name}</h1>
								<p class="stage-desc">
									Wegpunkte sind <strong>Wetterscheiden</strong> — Punkte, an denen sich Höhe, Exposition oder Geländekammer ändert.
									{#if activeStage.waypoints.filter((w) => w.suggested).length > 0}
										Die KI hat {activeStage.waypoints.filter((w) => w.suggested).length} Vorschläge gemacht.
									{/if}
								</p>
							</div>
							<!-- StageDateField: Issue #498 -->
						</div>

						<div class="wp-editor-body">
							<!-- Linke Spalte: Karte + Profil -->
							<div class="wp-editor-left">
								<!-- Karten-Card (AC-4) -->
								<div class="wp-card" data-testid="map-card">
									<div class="wp-card-header">
										<span class="mono eyebrow-small">Karte · OpenTopoMap (OSM + SRTM)</span>
										<span class="pill-topo mono">Topo</span>
									</div>
									<MapCanvas
										stage={activeStage}
										{activeWaypointId}
										onWaypointActivate={handleWaypointActivate}
									/>
								</div>

								<!-- Profil-Card (AC-6) -->
								<div class="wp-card wp-card--padded" data-testid="profile-card">
									<div class="wp-card-header">
										<span class="mono eyebrow-small">Höhenprofil · synchron mit Karte</span>
										<span class="mono profile-stats">
											{#if activeStage.waypoints.length >= 2}
												{activeStage.waypoints.length} WP
											{/if}
										</span>
									</div>
									<ProfileEditor
										stage={activeStage}
										{activeWaypointId}
										onWaypointActivate={handleWaypointActivate}
										onProfileAdd={handleProfileAdd}
									/>
								</div>
							</div>

							<!-- Rechte Spalte: Wegpunkte (AC-7) -->
							<div class="wp-editor-sidebar wp-card" data-testid="wp-editor-sidebar">
								<div class="wp-card-header sidebar-header">
									<div>
										<span class="mono eyebrow-small sidebar-eyebrow" data-eyebrow="Wegpunkte">Wegpunkte</span>
										<span class="sidebar-count-label">{activeStage.waypoints.length} insgesamt</span>
									</div>
									<Btn variant="ghost" size="sm" data-testid="wp-editor-add-waypoint-btn" disabled>
										+ auf Route
									</Btn>
								</div>
								<div class="sidebar-list">
									{#each activeStage.waypoints as waypoint, i (waypoint.id)}
										<WaypointCard
											{waypoint}
											index={i}
											active={waypoint.id === activeWaypointId}
											arrival={arrivals[i]}
											onActivate={makeActivateHandler(waypoint.id)}
											onConfirm={makeConfirmHandler(activeStage.id, waypoint.id)}
											onReject={makeRejectHandler(activeStage.id, waypoint.id)}
											onRename={makeRenameHandler(activeStage.id, waypoint.id)}
											onDelete={makeDeleteHandler(activeStage.id, waypoint.id)}
										/>
									{/each}
									{#if activeStage.waypoints.length === 0}
										<p class="sidebar-empty">Keine Wegpunkte.</p>
									{/if}
								</div>
								<div class="sidebar-hint">
									<span class="mono hint-label">Hinweis</span>
									<p class="hint-text">
										KI-Vorschläge sind <span class="hint-dash">orange gestrichelt</span>. Klicke „Bestätigen", um sie als manuelle Wegpunkte zu übernehmen.
									</p>
								</div>
							</div>
						</div>
					{/if}
				</div>
			{/if}

			<footer class="wp-editor-footer">
				<Btn
					variant="primary"
					data-testid="wp-editor-save-btn"
					disabled={saving}
					onclick={handleSave}
				>
					{saving ? 'Speichern…' : 'Speichern'}
				</Btn>
				<Btn
					variant="ghost"
					data-testid="wp-editor-cancel-btn"
					disabled={saving}
					onclick={handleCancel}
				>
					Abbrechen
				</Btn>
				{#if saveError}
					<span data-testid="wp-editor-save-error" class="save-error">{saveError}</span>
				{/if}
			</footer>
		</div>
	{/if}
</div>

<style>
	.wp-editor {
		display: flex;
		flex-direction: column;
		min-height: 0;
	}

	/* ---- Desktop ---- */
	.wp-editor-desktop {
		display: flex;
		flex-direction: column;
	}

	/* ---- Breadcrumb-Header (AC-3) ---- */
	.wp-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 40px;
		border-bottom: 1px solid var(--g-ink-faint);
		background: var(--g-card);
	}
	.wp-breadcrumb {
		font-size: 11px;
		color: var(--g-ink-muted);
		letter-spacing: 0.06em;
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.breadcrumb-dim { opacity: 0.6; }
	.breadcrumb-sep { opacity: 0.4; }
	.wp-header-actions {
		display: flex;
		gap: 8px;
	}

	/* ---- EtappenStrip-Wrapper (AC-8) ---- */
	.etappen-strip-wrapper {
		padding: 14px 40px 16px;
		background: rgba(255, 255, 255, 0.4);
		backdrop-filter: blur(2px);
		-webkit-backdrop-filter: blur(2px);
		border-bottom: 1px solid var(--g-ink-faint);
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.etappen-strip-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
	}
	.eyebrow-text {
		font-size: 10px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--g-ink-muted);
	}
	.strip-counter {
		font-size: 10px;
		color: var(--g-ink-muted);
		letter-spacing: 0.06em;
	}
	.add-stage-btn {
		align-self: flex-start;
		padding: 4px 16px;
		border: 1px dashed var(--g-rule, var(--g-ink-faint));
		background: transparent;
		color: var(--g-ink-muted);
		font-size: 11px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		cursor: not-allowed;
		border-radius: var(--g-radius-sm, 4px);
		opacity: 0.7;
	}

	/* ---- Content-Bereich ---- */
	.wp-editor-content {
		padding: 20px 40px 0;
	}
	.stage-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 32px;
		margin-bottom: 24px;
	}
	.stage-header-left { flex: 1; min-width: 0; }
	.eyebrow-small {
		font-size: 10px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--g-ink-muted);
		font-weight: 500;
		display: block;
		margin-bottom: 4px;
	}
	.stage-title {
		font-size: 32px;
		font-weight: 600;
		letter-spacing: -0.02em;
		margin: 0 0 4px;
		color: var(--g-ink);
	}
	.stage-desc {
		font-size: 14px;
		color: var(--g-ink-muted);
		margin: 0;
		max-width: 680px;
		line-height: 1.5;
	}

	/* ---- Body Grid ---- */
	.wp-editor-body {
		display: grid;
		grid-template-columns: 1fr 360px;
		gap: 24px;
		align-items: start;
		padding-bottom: 60px;
	}
	.wp-editor-left {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3, 12px);
	}

	/* ---- Cards ---- */
	.wp-card {
		background: var(--g-card);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md, 6px);
		overflow: hidden;
		box-shadow: var(--g-shadow-1, 0 1px 3px rgba(0, 0, 0, 0.08));
	}
	.wp-card-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 12px 18px;
		border-bottom: 1px solid var(--g-ink-faint);
	}
	.pill-topo {
		font-size: 10px;
		font-weight: 600;
		color: var(--g-ink-muted);
		background: var(--g-paper, #f6f4ee);
		border: 1px solid var(--g-ink-faint);
		border-radius: 100px;
		padding: 2px 10px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.profile-stats {
		font-size: 11px;
		color: var(--g-ink-muted);
	}

	/* ---- Sidebar (AC-7) ---- */
	.wp-editor-sidebar {
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	.sidebar-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.sidebar-eyebrow {
		display: block;
		margin-bottom: 2px;
	}
	.sidebar-count-label {
		font-size: 14px;
		font-weight: 600;
		color: var(--g-ink);
	}
	.sidebar-list {
		flex: 1;
		overflow-y: auto;
	}
	.sidebar-hint {
		padding: 14px;
		background: var(--g-paper, #f6f4ee);
		border-top: 1px solid var(--g-ink-faint);
	}
	.hint-label {
		font-size: 10px;
		color: var(--g-ink-muted);
		text-transform: uppercase;
		letter-spacing: 0.1em;
		display: block;
		margin-bottom: 6px;
	}
	.hint-text {
		font-size: 12px;
		color: var(--g-ink-muted);
		line-height: 1.5;
		margin: 0;
	}
	.hint-dash {
		border-bottom: 1.5px dashed var(--g-accent);
	}
	.sidebar-empty {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		padding: 14px;
	}

	/* ---- Footer (geteilt) ---- */
	.wp-editor-footer {
		display: flex;
		align-items: center;
		gap: var(--g-s-3);
		padding: var(--g-s-4);
		border-top: 1px solid var(--g-ink-faint);
	}
	.save-error {
		font-size: var(--g-text-sm);
		color: var(--g-danger);
	}

	/* ---- Mobile ---- */
	.wp-editor-mobile {
		display: flex;
		flex-direction: column;
		min-height: 100vh;
	}
	.mobile-topbar {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		padding: var(--g-s-2) var(--g-s-3);
		border-bottom: 1px solid var(--g-ink-faint);
	}
	.mobile-topbar-title {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
	}
	/* AC-9: Eyebrow ueber dem Titel */
	.mobile-eyebrow {
		font-size: 10px;
		color: var(--g-ink-muted);
		letter-spacing: 0.06em;
	}
	.mobile-title {
		font-size: var(--g-text-md);
		font-weight: 600;
		color: var(--g-ink);
		text-align: center;
		margin: 0;
	}
	.mobile-topbar__spacer {
		display: inline-block;
		width: var(--g-s-8);
	}

	/* ---- Mobile: Karten-Bereich mit Overlays (AC-10) ---- */
	.mobile-map {
		flex: 1;
		position: relative;
		overflow: hidden;
		min-height: 60vh;
	}
	.mobile-map :global([data-testid='map-canvas']) {
		width: 100% !important;
		height: 100% !important;
		max-width: 100%;
	}
	.mobile-profile-strip {
		position: absolute;
		top: 12px;
		left: 12px;
		right: 72px;
		background: rgba(246, 244, 238, 0.95);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md, 6px);
		padding: 8px 12px;
		box-shadow: var(--g-shadow-1, 0 1px 3px rgba(0, 0, 0, 0.1));
		pointer-events: none;
		z-index: 2;
	}
	.profile-strip-name {
		display: block;
		font-size: 13px;
		font-weight: 600;
		line-height: 1.2;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.profile-strip-stats {
		font-size: 10px;
		color: var(--g-ink-muted);
		display: block;
		margin-top: 2px;
	}
	.mobile-fabs {
		position: absolute;
		top: 12px;
		right: 12px;
		display: flex;
		flex-direction: column;
		gap: 8px;
		z-index: 2;
	}
	.fab {
		width: 44px;
		height: 44px;
		border-radius: var(--g-radius-md, 6px);
		background: var(--g-card);
		border: 1px solid var(--g-ink-faint);
		box-shadow: var(--g-shadow-2, 0 2px 8px rgba(0, 0, 0, 0.12));
		cursor: not-allowed;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 18px;
		color: var(--g-ink);
		opacity: 0.8;
	}

	/* ---- Mobile: Bottom-Sheet (AC-11) ---- */
	.mobile-sheet {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		background: var(--g-card);
		border-top-left-radius: 18px;
		border-top-right-radius: 18px;
		box-shadow: 0 -8px 24px rgba(26, 26, 24, 0.15);
		display: flex;
		flex-direction: column;
		transition: height 200ms ease-out;
		overflow: hidden;
		z-index: 3;
	}
	.sheet-grip-btn {
		background: none;
		border: none;
		cursor: pointer;
		padding: 8px 0 4px;
		display: flex;
		justify-content: center;
		flex-shrink: 0;
	}
	.mobile-sheet__grip {
		align-self: center;
		width: var(--g-s-8, 32px);
		height: 4px;
		border-radius: var(--g-radius-sm, 4px);
		background: var(--g-rule, var(--g-ink-faint));
	}
	.sheet-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		padding: 4px 16px 8px;
		flex-shrink: 0;
	}
	.sheet-header-left { flex: 1; min-width: 0; }
	.sheet-wp-name {
		display: block;
		font-size: 13px;
		font-weight: 600;
		margin-top: 2px;
	}
	.sheet-collapse-btn {
		width: 32px;
		height: 32px;
		border-radius: var(--g-radius-sm, 4px);
		background: transparent;
		border: 1px solid var(--g-ink-faint);
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 14px;
		color: var(--g-ink-muted);
		flex-shrink: 0;
	}
	.sheet-body {
		flex: 1;
		overflow-y: auto;
		padding: 0 16px 16px;
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2, 8px);
	}
	.sheet-ki-actions {
		display: flex;
		gap: 8px;
		margin-bottom: 4px;
	}
	.sheet-ki-actions :global(button:first-child) {
		flex: 1;
	}
	.sheet-list {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1, 4px);
	}
</style>
