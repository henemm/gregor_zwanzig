<script lang="ts">
	// Issue #251/#455 — RecommendationBanner: Empfehlungs-Banner mit Winner-Score und Tags.
	// Issue #454: Tags sind jetzt CompareTag[] ({type, label}) statt string[].

	import type { RankingEntry, Location } from '$lib/types.js';
	import { Pill } from '$lib/components/atoms';
	import * as Card from '$lib/components/ui/card/index.js';

	interface Props {
		topEntry: RankingEntry;
		locations: Location[];
	}

	let { topEntry, locations }: Props = $props();

	let locName = $derived(
		locations.find((l) => l.id === topEntry.location_id)?.name ?? topEntry.location_id
	);
</script>

<Card.Root
	data-testid="compare-recommendation-banner"
	class="border-l-4 border-l-[color:var(--g-success)] bg-[color:color-mix(in_oklab,var(--g-success)_8%,var(--g-surface-2))]"
>
	<Card.Content class="flex flex-wrap items-center gap-4 py-4">
		<div
			data-testid="compare-banner-score"
			class="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[color:var(--g-success)] text-xl font-bold text-white"
		>
			{Math.round(topEntry.score)}
		</div>
		<div class="flex-1 min-w-0">
			<p class="text-xs uppercase tracking-wide text-muted-foreground">Empfehlung</p>
			<p data-testid="compare-banner-location-name" class="text-lg font-semibold">
				{locName}
			</p>
			{#if topEntry.tags && topEntry.tags.length > 0}
				<div data-testid="compare-banner-tags" class="mt-2 flex flex-wrap gap-1.5">
					{#each topEntry.tags as tag}
						<Pill tone="success" class="px-2 py-0.5 text-xs rounded-full">{tag.label}</Pill>
					{/each}
				</div>
			{/if}
		</div>
	</Card.Content>
</Card.Root>
