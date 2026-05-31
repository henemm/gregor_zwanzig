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
	import StageDateField from './StageDateField.svelte';
	import { addDays, computeCascadeDelta } from './cascade.ts';
	import { Eyebrow, Btn, Dot } from '$lib/components/atoms';
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

	// Issue #498 — Kaskaden-Strip: bei Tourstart-Verschiebung Folge-Etappen mitnehmen?
	interface CascadeState {
		days: number;
		count: number;
		done: boolean;
	}
	let cascade = $state<CascadeState | null>(null);

	function handleDateChange(stageId: string, newDate: string): void {
		const idx = stages.findIndex((s) => s.id === stageId);
		if (idx < 0) return;
		const oldDate = stages[idx].date;

		// Datum + dateOverridden-Flag setzen, ohne andere Stages anzufassen.
		stages = stages.map((s, i) =>
			i === idx ? { ...s, date: newDate, dateOverridden: true } : s,
		);

		// Kaskaden-Vorschlag nur bei erster Etappe und gültigem altem Datum.
		if (idx === 0 && oldDate) {
			const delta = computeCascadeDelta(oldDate, newDate);
			if (delta !== 0 && stages.length > 1) {
				cascade = { days: delta, count: stages.length - 1, done: false };
			} else {
				cascade = null; // F001: stalen Cascade zurücksetzen wenn delta=0
			}
		}
	}

	function applyCascade(): void {
		if (!cascade || cascade.done) return;
		const days = cascade.days;
		stages = stages.map((s, i) => {
			if (i === 0) return s;
			if (!s.date) return s;
			return { ...s, date: addDays(s.date, days), dateOverridden: true };
		});
		cascade = { ...cascade, done: true };
	}

	function dismissCascade(): void {
		cascade = null;
	}

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
			<PauseStageView
				stage={activeStage}
				{prevStage}
				{nextStage}
				onDateChange={(newDate) => handleDateChange(activeStage!.id, newDate)}
			/>
		{:else}
			<!-- Issue #498 — Etappen-Header mit editierbarem Datum oben rechts -->
			<div class="flex items-start justify-between gap-8">
				<div class="min-w-0 flex-1">
					<Eyebrow>Etappe</Eyebrow>
					<p class="truncate text-lg font-semibold">{activeStage.name}</p>
				</div>
				<StageDateField
					value={activeStage.date}
					isFirst={activeStageIndex === 0}
					onchange={(newDate) => handleDateChange(activeStage!.id, newDate)}
				/>
			</div>

			{#if cascade && activeStageIndex === 0}
				{#if !cascade.done}
					<div class="cascade-prompt" data-testid="cascade-strip">
						<p>
							<strong
								>Tourstart um {cascade.days > 0 ? '+' : ''}{cascade.days}
								{Math.abs(cascade.days) === 1 ? 'Tag' : 'Tage'} verschoben.</strong
							>
							Sollen die {cascade.count} Folge-Etappen um denselben Betrag mitverschoben werden?
						</p>
						<div class="cascade-actions">
							<Btn variant="accent" size="sm" onclick={applyCascade}>Alle mitverschieben</Btn>
							<Btn variant="outline" size="sm" onclick={dismissCascade}>Nur diese Etappe</Btn>
						</div>
					</div>
				{:else}
					<div class="cascade-done" data-testid="cascade-done">
						<Dot tone="success" />
						<span>
							<strong>{cascade.count} Folge-Etappen verschoben</strong> · alle Daten um
							{cascade.days > 0 ? '+' : ''}{cascade.days}
							{Math.abs(cascade.days) === 1 ? 'Tag' : 'Tage'} angepasst.
						</span>
						<Btn variant="ghost" size="sm" onclick={dismissCascade}>Schließen</Btn>
					</div>
				{/if}
			{/if}

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
						<p class="text-sm text-[var(--g-ink-muted)]">Keine Wegpunkte.</p>
					{/if}
				</div>
			</div>
		{/if}
	{/if}
</div>

<style>
	/* Issue #498 — Cascade-Strip (Tourstart-Verschiebung Folge-Etappen?) */
	.cascade-prompt,
	.cascade-done {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px 14px;
		background: var(--g-accent-tint);
		border: 1px solid var(--g-rule);
		border-left: 3px solid var(--g-accent-deep);
		border-radius: 4px;
		font-size: 13px;
		color: var(--g-ink);
	}
	.cascade-prompt p {
		flex: 1;
		margin: 0;
	}
	.cascade-actions {
		display: flex;
		gap: 6px;
		flex-shrink: 0;
	}
	.cascade-done span {
		flex: 1;
	}
</style>
