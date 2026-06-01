<script lang="ts">
	// WaypointCard — Listeneintrag für einen Wegpunkt in der rechten Spalte.
	// Spec: docs/specs/modules/issue_522_waypoint_card_design.md
	//
	// Visual-Redesign (Issue #522):
	//   Normal:   [Kreis-Pin (weiß+accent-Rand+accent-Zahl)] NAME / Typ · Höhe · Ankunft
	//   Aktiv:    Left-Border accent 3px + leichter Tint + Text-Buttons (Umbenennen / Verschieben / Löschen)
	//
	// `onConfirm`/`onReject` bleiben als optionale @deprecated Props erhalten
	// (Backward-Compat mit WaypointsPanel.svelte / EditStagesPanelNew.svelte).

	import { Btn } from '$lib/components/atoms';
	import type { Waypoint } from '$lib/types';

	interface Props {
		waypoint: Waypoint;
		index: number;
		active?: boolean;
		onActivate: () => void;
		/** @deprecated Issue #503: KI-Bestätigen entfernt; Prop bleibt für Backward-Compat. */
		onConfirm?: () => void;
		/** @deprecated Issue #503: KI-Verwerfen entfernt; Prop bleibt für Backward-Compat. */
		onReject?: () => void;
		onRename: () => void;
		onDelete: () => void;
		// Issue #296-FE: berechnete Ankunftszeit "HH:MM" (computeArrivalTimes).
		// Nur im Trip-Editor gesetzt; Detail-View gibt das Prop NICHT → unverändert.
		arrival?: string | null;
	}

	let {
		waypoint,
		index,
		active = false,
		onActivate,
		onRename,
		onDelete,
		arrival = null
	}: Props = $props();

	function handleKeydown(e: KeyboardEvent): void {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			onActivate();
		}
	}

	// Factory-Pattern für Button-Handler (Safari-Kompatibilität)
	function makeRenameClick() {
		return (e: MouseEvent) => {
			e.stopPropagation();
			onRename();
		};
	}
	function makeMoveClick() {
		return (e: MouseEvent) => {
			e.stopPropagation();
			onActivate();
		};
	}
	function makeDeleteClick() {
		return (e: MouseEvent) => {
			e.stopPropagation();
			onDelete();
		};
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	data-testid="waypoint-card-{index}"
	class="waypoint-card {active ? 'waypoint-card--active' : ''}"
	onclick={onActivate}
	onkeydown={handleKeydown}
	role="button"
	tabindex="0"
>
	<div class="waypoint-card-row">
		<!-- Kreis-Pin (22×22 px, accent-Rand) -->
		<span class="waypoint-pin {active ? 'waypoint-pin--active' : ''}" aria-hidden="true">
			{index + 1}
		</span>

		<!-- Text-Block: Name + Meta -->
		<div class="waypoint-body">
			<div class="waypoint-name">{waypoint.name}</div>
			{#if waypoint.elevation_m || arrival}
				<div class="waypoint-meta">
					{#if waypoint.elevation_m}<span>{waypoint.elevation_m} m</span>{/if}
					{#if waypoint.elevation_m && arrival}
						<span class="waypoint-meta-sep">·</span>
					{/if}
					{#if arrival}
						<span data-testid="wp-arrival-{index}">{arrival}</span>
					{/if}
				</div>
			{/if}
		</div>
	</div>

	{#if active}
		<div class="waypoint-actions">
			<Btn
				variant="ghost"
				size="xs"
				data-testid="waypoint-rename-{index}"
				onclick={makeRenameClick()}
				aria-label="Wegpunkt umbenennen"
			>
				Umbenennen
			</Btn>
			<Btn
				variant="ghost"
				size="xs"
				data-testid="waypoint-move-{index}"
				onclick={makeMoveClick()}
				aria-label="Wegpunkt verschieben"
			>
				Verschieben
			</Btn>
			<Btn
				variant="ghost"
				size="xs"
				data-testid="waypoint-delete-{index}"
				onclick={makeDeleteClick()}
				aria-label="Wegpunkt löschen"
			>
				Löschen
			</Btn>
		</div>
	{/if}
</div>

<style>
	.waypoint-card {
		padding: 12px 18px;
		border-left: 3px solid transparent;
		cursor: pointer;
		transition: background 0.1s ease;
	}
	.waypoint-card:hover {
		background: rgba(196, 90, 42, 0.03);
	}
	.waypoint-card--active {
		background: rgba(196, 90, 42, 0.05);
		border-left: 3px solid var(--g-accent);
	}
	.waypoint-card-row {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.waypoint-pin {
		width: 22px;
		height: 22px;
		border-radius: 50%;
		border: 2px solid var(--g-accent);
		background: white;
		color: var(--g-accent-deep, var(--g-accent));
		font-family: var(--g-font-data);
		font-size: 10px;
		font-weight: 700;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		line-height: 1;
	}
	.waypoint-pin--active {
		background: var(--g-accent);
		color: white;
	}
	.waypoint-body {
		flex: 1;
		min-width: 0;
	}
	.waypoint-name {
		font-size: 13px;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--g-ink-1, inherit);
	}
	.waypoint-meta {
		font-size: 10px;
		font-family: var(--g-font-data);
		color: var(--g-ink-3);
		display: flex;
		gap: 4px;
		align-items: center;
	}
	.waypoint-meta-sep {
		opacity: 0.6;
	}
	.waypoint-actions {
		display: flex;
		gap: 6px;
		margin-top: 8px;
		margin-left: 32px;
	}
</style>
