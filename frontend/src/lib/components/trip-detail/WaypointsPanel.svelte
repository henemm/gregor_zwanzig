<script lang="ts">
	// WaypointsPanel — Parent/State-Owner fuer den Wegpunkt-Editor.
	// Spec: docs/specs/modules/epic_137_wegpunkt_editor.md §1, §11, §12

	import { api } from '$lib/api';
	import { invalidateAll } from '$app/navigation';
	import EtappenStrip from './waypoints/EtappenStrip.svelte';
	import MapCanvas from './waypoints/MapCanvas.svelte';
	import ProfileEditor from './waypoints/ProfileEditor.svelte';
	import WaypointCard from './waypoints/WaypointCard.svelte';
	import PauseStageView from './waypoints/PauseStageView.svelte';
	import { isPauseStage } from '$lib/components/trip-wizard/wizardHelpers';
	import type { Trip, Stage } from '$lib/types';

	interface Props {
		trip: Trip;
		onSaved?: () => void;
	}
	let { trip, onSaved }: Props = $props();

	// State
	let localStages = $state<Stage[]>(JSON.parse(JSON.stringify(trip.stages)));
	let activeStageId = $state<string>(trip.stages.find((s) => !isPauseStage(s))?.id ?? '');
	let activeWaypointId = $state<string | null>(null);
	let saving = $state(false);
	let saveError = $state<string | null>(null);

	// Derivations
	const activeStage = $derived(localStages.find((s) => s.id === activeStageId) ?? null);
	const activeIsPause = $derived(activeStage ? isPauseStage(activeStage) : false);
	const activeStageIndex = $derived(localStages.findIndex((s) => s.id === activeStageId));
	const prevStage = $derived(activeStageIndex > 0 ? localStages[activeStageIndex - 1] : null);
	const nextStage = $derived(
		activeStageIndex < localStages.length - 1 ? localStages[activeStageIndex + 1] : null
	);

	// Save-Handler
	async function handleSave(): Promise<void> {
		saving = true;
		saveError = null;
		try {
			await api.put(`/api/trips/${trip.id}`, { ...trip, stages: localStages });
			await invalidateAll();
			onSaved?.();
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Speichern fehlgeschlagen';
		} finally {
			saving = false;
		}
	}

	// Callback-Handler (Factory-Pattern)
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
	function handlePauseInsert(afterIndex: number): void {
		const newPause: Stage = {
			id: crypto.randomUUID().slice(0, 8),
			name: 'Pausentag',
			date: '',
			waypoints: []
		};
		const updated = [...localStages];
		updated.splice(afterIndex + 1, 0, newPause);
		localStages = updated;
	}

	// Waypoint-Mutations (Factory-Pattern fuer WaypointCard-Callbacks)
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
					: {
							...s,
							waypoints: s.waypoints.filter((w) => w.id !== waypointId)
						}
			);
		};
	}
	function makeActivateHandler(waypointId: string) {
		return function handleActivate() {
			activeWaypointId = waypointId;
		};
	}
</script>

<div data-testid="waypoints-panel" class="flex flex-col gap-4 p-4">
	<!-- Save-Bar -->
	<div class="flex justify-end gap-2">
		{#if saveError}
			<span data-testid="waypoints-save-error" class="text-sm text-[var(--g-danger)]">
				{saveError}
			</span>
		{/if}
		<button
			data-testid="waypoints-save-btn"
			onclick={handleSave}
			disabled={saving}
			class="rounded bg-[var(--g-accent)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
		>
			{saving ? 'Speichert…' : 'Speichern'}
		</button>
	</div>

	<!-- EtappenStrip -->
	<EtappenStrip
		stages={localStages}
		{activeStageId}
		onStagesReorder={handleStagesReorder}
		onStageActivate={handleStageActivate}
		onPauseInsert={handlePauseInsert}
	/>

	<!-- Hauptbereich: Karte+Profil links, Waypoints rechts -->
	{#if activeStage}
		<div class="flex gap-4">
			<!-- Links: Karte + Profil (oder PauseStageView) -->
			<div class="flex flex-col gap-3 flex-1">
				{#if activeIsPause}
					<PauseStageView stage={activeStage} {prevStage} {nextStage} />
				{:else}
					{#key activeStageId}
						<MapCanvas
							stage={activeStage}
							{activeWaypointId}
							onWaypointActivate={handleWaypointActivate}
						/>
					{/key}
					<ProfileEditor
						stage={activeStage}
						{activeWaypointId}
						onWaypointActivate={handleWaypointActivate}
					/>
				{/if}
			</div>

			<!-- Rechts: Waypoint-Liste -->
			{#if !activeIsPause}
				<div class="flex flex-col gap-1 w-64">
					{#each activeStage.waypoints as waypoint, i (waypoint.id)}
						<WaypointCard
							{waypoint}
							index={i}
							active={waypoint.id === activeWaypointId}
							onActivate={makeActivateHandler(waypoint.id)}
							onRename={makeRenameHandler(activeStage.id, waypoint.id)}
							onDelete={makeDeleteHandler(activeStage.id, waypoint.id)}
						/>
					{/each}
					{#if activeStage.waypoints.length === 0}
						<p class="text-sm text-[var(--g-ink-muted)]">Keine Wegpunkte.</p>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>
