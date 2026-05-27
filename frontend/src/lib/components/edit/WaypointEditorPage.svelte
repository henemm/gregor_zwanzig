<script lang="ts">
	// WaypointEditorPage — dedizierter Vollbild-Wegpunkt-Editor fuer /trips/[id]/edit.
	// Spec: docs/specs/modules/issue_407_waypoint_editor_screen.md
	//
	// Uebernimmt das State-/Mutation-Pattern aus WaypointsPanel.svelte (Architektur-Vorbild),
	// ergaenzt um Navigation nach Save (goto('/trips')) und Mobile-Layout (Sheet + StageNav).
	// Desktop ≥900px: EtappenStrip oben, Karte+Profil links, Wegpunkt-Sidebar rechts, Footer.
	// Mobile ≤899px: TopAppBar + StageNavDropdown + Vollbreite-Karte + Bottom-Sheet.

	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import EtappenStrip from '$lib/components/trip-detail/waypoints/EtappenStrip.svelte';
	import MapCanvas from '$lib/components/trip-detail/waypoints/MapCanvas.svelte';
	import ProfileEditor from '$lib/components/trip-detail/waypoints/ProfileEditor.svelte';
	import WaypointCard from '$lib/components/trip-detail/waypoints/WaypointCard.svelte';
	import PauseStageView from '$lib/components/trip-detail/waypoints/PauseStageView.svelte';
	import { Btn } from '$lib/components/ui/btn';
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
				<h1 class="mobile-title">Wegpunkt-Editor</h1>
				<span class="mobile-topbar__spacer"></span>
			</header>

			<StageNavDropdown
				stages={localStages}
				{activeStageId}
				prev={prevStage}
				next={nextStage}
				onActivate={handleStageActivate}
			/>

			{#if activeStage}
				{#if activeIsPause}
					<PauseStageView stage={activeStage} {prevStage} {nextStage} />
				{:else}
					<div class="mobile-map">
						<MapCanvas
							stage={activeStage}
							{activeWaypointId}
							onWaypointActivate={handleWaypointActivate}
						/>
					</div>

					<!--
						Bottom-Sheet als nicht-modales Inline-Panel: die Wegpunkt-Liste
						bleibt persistent sichtbar, ohne den StageNavDropdown / die TopAppBar
						mit einem Overlay-Backdrop zu blockieren (Voraussetzung fuer die
						Prev/Next-Navigation, AC-11). Optisch ueber die Sheet-Komponente
						hinaus eigenstaendig getokent.
					-->
					<section data-testid="wp-editor-sheet" class="mobile-sheet">
						<div class="mobile-sheet__grip" aria-hidden="true"></div>
						<div class="sheet-body">
							<ProfileEditor
								stage={activeStage}
								{activeWaypointId}
								onWaypointActivate={handleWaypointActivate}
								onProfileAdd={handleProfileAdd}
							/>
							{#if hasSuggested}
								<AISuggestionBar
									stage={activeStage}
									onAccept={handleAcceptSuggested}
									onReject={handleRejectSuggested}
								/>
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
						</div>
					</section>
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
			<EtappenStrip
				stages={localStages}
				{activeStageId}
				onStagesReorder={handleStagesReorder}
				onStageActivate={handleStageActivate}
			/>

			<div class="wp-editor-body">
				<div class="wp-editor-left">
					{#if activeStage}
						{#if activeIsPause}
							<PauseStageView stage={activeStage} {prevStage} {nextStage} />
						{:else}
							<MapCanvas
								stage={activeStage}
								{activeWaypointId}
								onWaypointActivate={handleWaypointActivate}
							/>
							<ProfileEditor
								stage={activeStage}
								{activeWaypointId}
								onWaypointActivate={handleWaypointActivate}
								onProfileAdd={handleProfileAdd}
							/>
						{/if}
					{/if}
				</div>

				<div data-testid="wp-editor-sidebar" class="wp-editor-sidebar">
					<p class="sidebar-count">{activeStage?.waypoints?.length ?? 0} Wegpunkte</p>
					{#if activeStage && !activeIsPause}
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
					{/if}
				</div>
			</div>

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
		gap: var(--g-s-4);
		padding: var(--g-s-4);
	}
	.wp-editor-body {
		display: grid;
		grid-template-columns: 1fr 380px;
		gap: var(--g-s-4);
		align-items: start;
	}
	.wp-editor-left {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
	}
	.wp-editor-sidebar {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
	}
	.sidebar-count {
		font-size: var(--g-text-sm);
		font-weight: 600;
		color: var(--g-ink);
		margin-bottom: var(--g-s-1);
	}
	.sidebar-empty {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
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
	}
	.mobile-topbar {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		padding: var(--g-s-2) var(--g-s-3);
		border-bottom: 1px solid var(--g-ink-faint);
	}
	.mobile-title {
		flex: 1;
		font-size: var(--g-text-md);
		font-weight: 600;
		color: var(--g-ink);
		text-align: center;
	}
	.mobile-topbar__spacer {
		display: inline-block;
		width: var(--g-s-8);
	}
	.mobile-map {
		display: flex;
		justify-content: center;
		padding: var(--g-s-3);
	}
	.mobile-map :global([data-testid='map-canvas']) {
		width: 100% !important;
		max-width: 100%;
	}
	.mobile-sheet {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
		margin-top: auto;
		padding: var(--g-s-2) var(--g-s-4) var(--g-s-4);
		background: var(--g-card);
		border-top-left-radius: var(--g-radius-md);
		border-top-right-radius: var(--g-radius-md);
		border-top: 1px solid var(--g-ink-faint);
	}
	.mobile-sheet__grip {
		align-self: center;
		width: var(--g-s-8);
		height: var(--g-s-1);
		border-radius: var(--g-radius-sm);
		background: var(--g-rule);
	}
	.sheet-body {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
	}
	.sheet-list {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
	}
</style>
