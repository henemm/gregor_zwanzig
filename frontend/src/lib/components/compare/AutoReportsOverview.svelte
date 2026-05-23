<script lang="ts">
	// Issue #301 Lieferung B — Default-Content im Compare-Bereich als gestaltetes
	// Auto-Reports-Kachelraster (Eyebrow + H1 + responsives Grid). Drop-in-Ersatz
	// für das frühere Subscriptions-Panel mit identischer Props-Signatur.
	//
	// Spec: docs/specs/modules/issue_301b_auto_reports_overview.md (§2)

	import type { Subscription } from '$lib/types.js';
	import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';
	import AutoReportCard from './AutoReportCard.svelte';
	import AddReportCard from './AddReportCard.svelte';

	interface Props {
		subscriptions: Subscription[];
		onsavebriefing: () => void;
	}

	let { subscriptions, onsavebriefing }: Props = $props();
</script>

<section class="auto-reports-overview" data-testid="auto-reports-overview">
	<Eyebrow>Orts-Vergleich · Auto-Reports</Eyebrow>
	<h1 class="overview-heading">Deine Auto-Reports</h1>

	<div class="reports-grid" data-testid="reports-grid">
		{#each subscriptions as sub (sub.id)}
			<AutoReportCard subscription={sub} />
		{/each}
		<AddReportCard onclick={onsavebriefing} />
	</div>

	{#if subscriptions.length === 0}
		<p class="empty-hint" data-testid="empty-hint">
			Noch kein Auto-Report angelegt. Starte mit dem Vergleich und speichere ihn.
		</p>
	{/if}
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
		font-size: 0.875rem;
		color: var(--g-ink-faint);
		margin-top: var(--g-s-2);
	}
</style>
