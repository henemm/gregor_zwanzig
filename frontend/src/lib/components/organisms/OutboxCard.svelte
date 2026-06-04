<script lang="ts">
	// Issue #578 — OutboxCard-Organism.
	// Kanonische Quelle: screen-home.jsx::HomeOutboxCard
	//
	// Zeigt die heutigen Versand-Einträge für den aktiven Kontext.

	import { Card, Pill, Eyebrow } from '$lib/components/atoms';
	import BriefingTimelineRow from '../molecules/BriefingTimelineRow.svelte';

	interface Report {
		when: string;
		kind: string;
		etappe?: string;
		channels?: string[];
		status?: 'sent' | 'planned' | string;
	}

	interface Props {
		contextName?: string;
		reports?: Report[];
		class?: string;
	}

	let { contextName = '—', reports = [], class: className = '' }: Props = $props();
</script>

<Card padding={20} class={className}>
	<div
		style:display="flex"
		style:justify-content="space-between"
		style:align-items="center"
		style:margin-bottom="14px"
		style:gap="12px"
	>
		<div style:min-width="0">
			<Eyebrow style="margin-bottom: 4px">Versand · heute</Eyebrow>
			<div
				style:font-size="17px"
				style:font-weight="600"
				style:white-space="nowrap"
				style:overflow="hidden"
				style:text-overflow="ellipsis"
			>
				Was geht raus · <span style:color="var(--g-ink-2)" style:font-weight="600">{contextName}</span>
			</div>
		</div>
		<Pill tone="good">Alle Kanäle ok</Pill>
	</div>

	<div style:display="flex" style:flex-direction="column" style:gap="8px">
		{#each reports.slice(0, 3) as report, i (i)}
			<BriefingTimelineRow {report} />
		{/each}
	</div>
</Card>
