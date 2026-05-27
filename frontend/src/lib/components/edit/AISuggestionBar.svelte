<script lang="ts">
	// AISuggestionBar — KI-Vorschlag-Bar fuer den Mobile-Bottom-Sheet (Issue #407).
	// Spec: docs/specs/modules/issue_407_waypoint_editor_screen.md §3
	//
	// Erscheint wenn die aktive Etappe mindestens einen `suggested`-Wegpunkt hat.
	// Zeigt Infos zum ersten Vorschlag + zwei Buttons (Uebernehmen / Verwerfen).
	// Nach Bestaetigung/Verwerfung verschwindet die Bar reaktiv (hasSuggested → false).

	import { Btn } from '$lib/components/ui/btn';
	import { computeArrivalTimes } from '$lib/utils/naismith';
	import type { Stage } from '$lib/types';

	interface Props {
		stage: Stage;
		onAccept: (waypointId: string) => void;
		onReject: (waypointId: string) => void;
	}
	let { stage, onAccept, onReject }: Props = $props();

	const firstSuggested = $derived(stage.waypoints.find((w) => w.suggested === true) ?? null);
	const suggestedIndex = $derived(
		firstSuggested ? stage.waypoints.findIndex((w) => w.id === firstSuggested.id) : -1
	);
	const arrivals = $derived(computeArrivalTimes(stage, stage.start_time));
	const eta = $derived(suggestedIndex >= 0 ? (arrivals[suggestedIndex] ?? null) : null);

	// Factory-Pattern (Safari-Closure-Schutz, siehe CLAUDE.md / WaypointsPanel-Vorbild).
	function makeAcceptHandler(waypointId: string) {
		return function handleAccept() {
			onAccept(waypointId);
		};
	}
	function makeRejectHandler(waypointId: string) {
		return function handleReject() {
			onReject(waypointId);
		};
	}
</script>

{#if firstSuggested}
	<div data-testid="ai-suggestion-bar" class="ai-bar">
		<div class="ai-bar__info">
			<span class="ai-bar__eyebrow mono">KI-Vorschlag</span>
			<span class="ai-bar__name">{firstSuggested.name}</span>
			<span class="ai-bar__meta">
				{#if firstSuggested.elevation_m}<span class="mono">{firstSuggested.elevation_m} m</span>{/if}
				{#if eta}<span class="mono">{eta}</span>{/if}
			</span>
		</div>
		<div class="ai-bar__actions">
			<Btn
				variant="primary"
				size="sm"
				data-testid="ai-suggestion-accept-btn"
				onclick={makeAcceptHandler(firstSuggested.id)}
			>
				KI-Vorschlag übernehmen
			</Btn>
			<Btn
				variant="ghost"
				size="sm"
				data-testid="ai-suggestion-reject-btn"
				onclick={makeRejectHandler(firstSuggested.id)}
			>
				Verwerfen
			</Btn>
		</div>
	</div>
{/if}

<style>
	.ai-bar {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
		padding: var(--g-s-3);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md);
		background: var(--g-surface-raised);
	}
	.ai-bar__info {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
	}
	.ai-bar__eyebrow {
		font-size: var(--g-text-xs);
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--g-accent-deep);
	}
	.ai-bar__name {
		font-size: var(--g-text-sm);
		font-weight: 600;
		color: var(--g-ink);
	}
	.ai-bar__meta {
		display: flex;
		gap: var(--g-s-3);
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
	}
	.ai-bar__actions {
		display: flex;
		gap: var(--g-s-2);
	}
</style>
