<script lang="ts">
	// Step 3: Wegpunkt-Vorschlaege bestaetigen (Epic #136 Sub-Spec #163).
	// Quelle: docs/specs/modules/epic_136_step3_waypoints.md
	//
	// Layout (Spec §1):
	//   - Linke Spalte: Etappen-Liste (Pausen sichtbar, nicht klickbar)
	//   - Rechte Spalte: ProfileChart (oben) + Waypoint-Liste (unten)
	//
	// State:
	//   - activeStageId — lokaler $state, init = erste Nicht-Pause-Stage
	//   - WizardState.stages[i].waypoints[j].suggested wird via
	//     wizard.confirmWaypoint / wizard.rejectWaypoint mutiert
	//
	// Empty-States (Spec §8):
	//   - §8a: keine Stages
	//   - §8b: alle Stages sind Pausen
	//   - §8c: aktive Stage hat 0 Waypoints
	//
	// Safari/Factory: benannte Handler (siehe StageRow.svelte als Vorbild).

	import { getContext } from 'svelte';
	import { Eyebrow, Pill } from '$lib/components/atoms';
	import type { Stage } from '$lib/types';
	import type { WizardState } from '../wizardState.svelte';
	import { formatStageNumber, isPauseStage } from '../wizardHelpers.ts';
	import ProfileChart from './ProfileChart.svelte';
	import WaypointRow from './WaypointRow.svelte';

	const wizard = getContext<WizardState>('trip-wizard-state');

	// --- Local UI-State -----------------------------------------------------

	function firstNonPauseId(stages: Stage[]): string {
		const found = stages.find((s) => !isPauseStage(s));
		return found?.id ?? '';
	}

	let activeStageId = $state<string>(firstNonPauseId(wizard.stages));

	// nonPauseIndex pro Stage berechnen (analog Step 2): -1 fuer Pausen.
	function computeNonPauseIndices(stages: Stage[]): number[] {
		let counter = 0;
		return stages.map((s) => (isPauseStage(s) ? -1 : counter++));
	}

	const nonPauseIndices = $derived(computeNonPauseIndices(wizard.stages));

	const activeStage = $derived(wizard.stages.find((s) => s.id === activeStageId) ?? null);

	const onlyPauses = $derived(
		wizard.stages.length > 0 && wizard.stages.every((s) => isPauseStage(s))
	);

	// --- Handlers -----------------------------------------------------------

	function makeStageSelectHandler(stage: Stage) {
		return function handleStageSelect() {
			if (isPauseStage(stage)) return;
			activeStageId = stage.id;
		};
	}

	function makeConfirmHandler(stageId: string, waypointId: string) {
		return function handleConfirm() {
			wizard.confirmWaypoint(stageId, waypointId);
		};
	}

	function makeRejectHandler(stageId: string, waypointId: string) {
		return function handleReject() {
			wizard.rejectWaypoint(stageId, waypointId);
		};
	}
</script>

<div data-testid="trip-wizard-step3-container" class="flex flex-row gap-6 py-4">
	{#if wizard.stages.length === 0}
		<!-- §8a: Keine Stages -->
		<div
			data-testid="trip-wizard-step3-empty-no-stages"
			class="w-full text-sm text-[var(--g-ink-muted)]"
		>
			Bitte zuerst in Schritt 2 GPX-Dateien hochladen.
		</div>
	{:else}
		<!-- Linke Etappen-Liste -->
		<div class="flex w-48 flex-col gap-2">
			<Eyebrow class="text-xs text-[var(--g-ink-muted)]">Etappen</Eyebrow>
			<div data-testid="trip-wizard-step3-stages-list" class="flex flex-col gap-1">
				{#each wizard.stages as stage, i (stage.id)}
					{@const isPause = isPauseStage(stage)}
					{@const isActive = stage.id === activeStageId}
					{#if isPause}
						<div
							data-testid="trip-wizard-step3-pause-marker-{i}"
							class="rounded-md border border-[var(--g-ink-faint)]/20 px-3 py-2 text-xs uppercase tracking-wide text-[var(--g-ink-muted)]"
							style="opacity: 0.5; pointer-events: none;"
						>
							Pausentag
						</div>
					{:else}
						<button
							type="button"
							data-testid="trip-wizard-step3-stage-row-{i}"
							data-active={isActive ? 'true' : 'false'}
							aria-current={isActive ? 'true' : undefined}
							onclick={makeStageSelectHandler(stage)}
							class="flex flex-col items-start gap-1 rounded-md border px-3 py-2 text-left transition-colors
								{isActive
								? 'border-[var(--g-accent)] bg-[var(--g-accent)]/10'
								: 'border-[var(--g-ink-faint)]/30 hover:bg-[var(--g-ink-faint)]/5'}"
						>
							<span data-testid="trip-wizard-step3-stage-pill-{i}">
								<Pill tone="accent">{formatStageNumber(nonPauseIndices[i])}</Pill>
							</span>
							<span class="text-sm truncate w-full">{stage.name}</span>
							{#if stage.date}
								<span class="text-xs text-[var(--g-ink-muted)]">{stage.date}</span>
							{/if}
						</button>
					{/if}
				{/each}
			</div>
		</div>

		<!-- Rechte Confirm-UI -->
		<div class="flex flex-1 flex-col gap-3">
			<Eyebrow class="text-xs text-[var(--g-ink-muted)]">Wegpunkte</Eyebrow>

			{#if activeStage}
				<ProfileChart stage={activeStage} />

				{#if activeStage.waypoints.length === 0}
					<!-- §8c: alle Waypoints der aktiven Etappe verworfen
						(ueberlagert §8b, weil eine aktive Stage existiert) -->
					<div
						data-testid="trip-wizard-step3-empty-no-waypoints"
						class="text-sm text-[var(--g-ink-muted)]"
					>
						Keine Wegpunkte mehr — alle verworfen.
					</div>
				{:else}
					<div data-testid="trip-wizard-step3-waypoints-list" class="flex flex-col gap-1">
						{#each activeStage.waypoints as waypoint, i (waypoint.id)}
							<WaypointRow
								{waypoint}
								index={i}
								onConfirm={makeConfirmHandler(activeStage.id, waypoint.id)}
								onReject={makeRejectHandler(activeStage.id, waypoint.id)}
							/>
						{/each}
					</div>
				{/if}
			{:else if onlyPauses}
				<!-- §8b: keine aktive Stage waehlbar — alle sind Pausen -->
				<div
					data-testid="trip-wizard-step3-empty-only-pauses"
					class="text-sm text-[var(--g-ink-muted)]"
				>
					Trip enthaelt nur Pausentage — keine Wegpunkte.
				</div>
			{/if}
		</div>
	{/if}
</div>
