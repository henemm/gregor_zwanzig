<script lang="ts">
	// Issue #459 — Sidepanel-Übersicht: gespeicherte Auto-Briefings (ComparePresets).
	//
	// Spec: docs/specs/modules/issue_459_auto_briefings_sidepanel.md (§4)
	// Vorher (#301): Subscription-Liste. Jetzt: ComparePreset-Kacheln + internes
	// SavePresetDialog (kein Callback nach oben).

	import type { ComparePreset } from '$lib/types.js';
	import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';
	import AutoReportCard from './AutoReportCard.svelte';
	import AddReportCard from './AddReportCard.svelte';
	import SavePresetDialog from './SavePresetDialog.svelte';

	interface Props {
		presets: ComparePreset[];
	}

	let { presets }: Props = $props();
	let saveDialogOpen = $state(false);
</script>

<section class="auto-reports-overview" data-testid="auto-reports-overview">
	<Eyebrow>AUTO-BRIEFINGS</Eyebrow>
	<h1 class="overview-heading">Deine Auto-Briefings</h1>

	{#if presets.length === 0}
		<p class="empty-hint" data-testid="auto-reports-empty">
			Noch kein Auto-Briefing gespeichert. Starte einen Vergleich und speichere
			ihn als Auto-Briefing.
		</p>
	{/if}

	<div class="reports-grid" data-testid="reports-grid">
		{#each presets as preset (preset.id)}
			<AutoReportCard {preset} />
		{/each}
		<AddReportCard onclick={() => (saveDialogOpen = true)} />
	</div>

	<SavePresetDialog bind:open={saveDialogOpen} />
</section>

<style>
	.auto-reports-overview {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}

	.overview-heading {
		font-size: 1.5rem;
		font-weight: 700;
		letter-spacing: -0.025em;
		margin-bottom: var(--g-s-2);
	}

	.reports-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: var(--g-s-4);
	}

	@media (min-width: 640px) {
		.reports-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	@media (min-width: 1024px) {
		.reports-grid {
			grid-template-columns: repeat(3, 1fr);
		}
	}

	.empty-hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin-top: var(--g-s-2);
	}
</style>
