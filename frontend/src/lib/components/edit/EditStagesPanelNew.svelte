<script lang="ts">
	// EditStagesPanelNew — Profil-basierter Etappen-Editor (Issue #296-FE, KEINE Karte).
	// Spec: docs/specs/modules/issue_296_fe_profile_editor.md §5
	//
	// Architektur-Vorbild: WaypointsPanel.svelte (epic_137). Unterschiede:
	//   - KEIN MapCanvas (nur Hoehenprofil)
	//   - KEIN eigener Save — `stages` ist gebunden, Container (TripEditView) speichert
	//   - ProfileEditor erhaelt onProfileAdd → Klick auf Profil fuegt Wegpunkt ein
	//   - WaypointCard erhaelt arrival (computeArrivalTimes)

	import EtappenStrip from '$lib/components/trip-detail/waypoints/EtappenStrip.svelte';
	import ProfileEditor from '$lib/components/trip-detail/waypoints/ProfileEditor.svelte';
	import WaypointCard from '$lib/components/trip-detail/waypoints/WaypointCard.svelte';
	import PauseStageView from '$lib/components/trip-detail/waypoints/PauseStageView.svelte';
	import { computeArrivalTimes } from '$lib/utils/naismith';
	import { interpolateWaypoint } from '$lib/utils/waypointEditor';
	import type { Stage, Waypoint } from '$lib/types';

	interface Props {
		stages: Stage[];
	}
	let { stages = $bindable() }: Props = $props();

	// Pausentag = Etappe ohne Wegpunkte (Spec-Definition §5/AC-10).
	const isPause = (s: Stage): boolean => s.waypoints.length === 0;

	let activeStageId = $state<string>(
		stages.find((s) => !isPause(s))?.id ?? stages[0]?.id ?? ''
	);
	let activeWaypointId = $state<string | null>(null);

	const activeStage = $derived(stages.find((s) => s.id === activeStageId) ?? null);
	const activeIsPause = $derived(activeStage ? isPause(activeStage) : false);
	const activeStageIndex = $derived(stages.findIndex((s) => s.id === activeStageId));
	const prevStage = $derived(activeStageIndex > 0 ? stages[activeStageIndex - 1] : null);
	const nextStage = $derived(
		activeStageIndex >= 0 && activeStageIndex < stages.length - 1
			? stages[activeStageIndex + 1]
			: null
	);
	const arrivals = $derived(
		activeStage ? computeArrivalTimes(activeStage, activeStage.start_time) : []
	);

	const newId = (): string => crypto.randomUUID().slice(0, 8);

	// EtappenStrip-Handler
	function handleStagesReorder(reordered: Stage[]): void {
		stages = reordered;
	}
	function handleStageActivate(stageId: string): void {
		activeStageId = stageId;
		activeWaypointId = null;
	}
	function handlePauseInsert(afterIndex: number): void {
		const newPause: Stage = { id: newId(), name: 'Pausentag', date: '', waypoints: [] };
		const updated = [...stages];
		updated.splice(afterIndex + 1, 0, newPause);
		stages = updated;
	}

	// Profil-Klick → interpolierten Wegpunkt einfuegen (suggested).
	function handleProfileAdd(fraction: number): void {
		if (!activeStage) return;
		const { lat, lon, elevation_m, insertAfterIndex } = interpolateWaypoint(
			activeStage.waypoints,
			fraction
		);
		const newWp: Waypoint = {
			id: newId(),
			name: 'Neuer Punkt',
			lat,
			lon,
			elevation_m,
			suggested: true
		};
		stages = stages.map((s) => {
			if (s.id !== activeStage.id) return s;
			const wps = [...s.waypoints];
			wps.splice(insertAfterIndex + 1, 0, newWp);
			return { ...s, waypoints: wps };
		});
		activeWaypointId = newWp.id;
	}

	// ProfileEditor erwartet (waypointId) => void — direkte Funktion (kein Factory).
	function handleWaypointActivate(waypointId: string): void {
		activeWaypointId = waypointId;
	}

	// Waypoint-Mutations (Factory-Pattern fuer WaypointCard-Callbacks).
	function makeActivateHandler(waypointId: string) {
		return function handleActivate() {
			activeWaypointId = waypointId;
		};
	}
	function makeConfirmHandler(stageId: string, waypointId: string) {
		return function handleConfirm() {
			stages = stages.map((s) =>
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
			stages = stages.map((s) =>
				s.id !== stageId ? s : { ...s, waypoints: s.waypoints.filter((w) => w.id !== waypointId) }
			);
		};
	}
	function makeRenameHandler(stageId: string, waypointId: string) {
		return function handleRename() {
			const newName = prompt('Neuer Name:');
			if (!newName) return;
			stages = stages.map((s) =>
				s.id !== stageId
					? s
					: {
							...s,
							waypoints: s.waypoints.map((w) => (w.id !== waypointId ? w : { ...w, name: newName }))
						}
			);
		};
	}
	function makeDeleteHandler(stageId: string, waypointId: string) {
		return function handleDelete() {
			stages = stages.map((s) =>
				s.id !== stageId ? s : { ...s, waypoints: s.waypoints.filter((w) => w.id !== waypointId) }
			);
		};
	}
</script>

<div data-testid="edit-stages-panel" class="flex flex-col gap-4">
	<!-- EtappenStrip -->
	<EtappenStrip
		{stages}
		{activeStageId}
		onStagesReorder={handleStagesReorder}
		onStageActivate={handleStageActivate}
		onPauseInsert={handlePauseInsert}
	/>

	{#if activeStage}
		{#if activeIsPause}
			<PauseStageView stage={activeStage} {prevStage} {nextStage} />
		{:else}
			<div class="flex gap-4">
				<!-- Links: Hoehenprofil mit Add-Klick -->
				<div class="flex-1">
					<ProfileEditor
						stage={activeStage}
						{activeWaypointId}
						onWaypointActivate={handleWaypointActivate}
						onProfileAdd={handleProfileAdd}
					/>
				</div>

				<!-- Rechts: Wegpunkt-Liste mit Ankunftszeiten -->
				<div class="flex w-64 flex-col gap-1">
					{#each activeStage.waypoints as waypoint, i (waypoint.id)}
						<WaypointCard
							{waypoint}
							index={i}
							active={waypoint.id === activeWaypointId}
							arrival={arrivals[i] ?? null}
							onActivate={makeActivateHandler(waypoint.id)}
							onConfirm={makeConfirmHandler(activeStage.id, waypoint.id)}
							onReject={makeRejectHandler(activeStage.id, waypoint.id)}
							onRename={makeRenameHandler(activeStage.id, waypoint.id)}
							onDelete={makeDeleteHandler(activeStage.id, waypoint.id)}
						/>
					{/each}
					{#if activeStage.waypoints.length === 0}
						<p class="text-sm text-[var(--g-ink-faint)]">Keine Wegpunkte.</p>
					{/if}
				</div>
			</div>
		{/if}
	{/if}
</div>
