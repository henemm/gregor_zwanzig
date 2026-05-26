<script lang="ts">
	// Issue #301 Lieferung B — Gestrichelte "+"-Kachel als feste letzte Position
	// im Auto-Reports-Grid. Klick öffnet den Speichern-Dialog (onsavebriefing).
	//
	// Spec: docs/specs/modules/issue_301b_auto_reports_overview.md (§4)

	import PlusIcon from '@lucide/svelte/icons/plus';

	interface Props {
		onclick: () => void;
	}

	let { onclick }: Props = $props();
</script>

<button
	class="add-report-card"
	{onclick}
	data-testid="add-report-card"
	aria-label="Neuer Auto-Report"
>
	<PlusIcon size={24} />
	<span>Neuer Auto-Report</span>
</button>

<style>
	.add-report-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--g-s-2);
		min-height: var(--g-s-20);
		width: 100%;
		padding: var(--g-s-4);
		border: 2px dashed var(--g-ink-faint);
		border-radius: var(--g-s-3);
		background: transparent;
		color: var(--g-ink-muted);
		font-size: 0.875rem;
		font-weight: 600;
		cursor: pointer;
		transition: background-color 0.2s ease, color 0.2s ease;
	}

	.add-report-card:hover {
		background: color-mix(in oklab, var(--g-ink-faint) 12%, transparent);
		color: var(--g-ink);
	}
</style>
