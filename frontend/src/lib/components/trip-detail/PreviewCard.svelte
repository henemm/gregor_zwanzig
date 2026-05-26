<script lang="ts">
	// Epic #135 Step 5 — Vorschau-Karte fuer die rechte Spalte im
	// Trip-Detail Overview-Tab (Issue #159, blockiert auf #189).
	//
	// Spec: docs/specs/modules/epic_135_step5_right_column.md §5.

	import type { Trip } from '$lib/types';
	import { GCard } from '$lib/components/ui/g-card';
	import { Eyebrow } from '$lib/components/ui/eyebrow';

	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	interface Props {
		trip: Trip;
	}

	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	let { trip }: Props = $props();
</script>

<GCard data-testid="right-card-preview" class="preview-card">
	<Eyebrow>Vorschau</Eyebrow>
	<h3 class="card-title">Wie sehen Reports aus?</h3>

	<div class="cta-stack">
		<a
			href="#preview"
			data-channel="email"
			data-testid="right-card-preview-email"
			class="cta-link"
		>
			E-Mail-Vorschau →
		</a>
		<a
			href="#preview"
			data-channel="sms"
			data-testid="right-card-preview-sms"
			class="cta-link"
		>
			SMS-Vorschau →
		</a>
	</div>
</GCard>

<style>
	:global([data-testid='right-card-preview']) {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 1rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 0.5rem;
		background: var(--g-surface-1, #fff);
	}
	.card-title {
		font-size: 1rem;
		font-weight: 600;
		margin: 0;
	}
	.cta-stack {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}
	.cta-link {
		font-size: 0.875rem;
		color: var(--g-accent-deep);
		text-decoration: none;
	}
	.cta-link:hover {
		text-decoration: underline;
	}
</style>
