<script lang="ts">
	// Issue #183 — Email-Preview Header (TDD GREEN).
	// Spec: docs/specs/modules/issue_183_email_preview_header.md
	import type { Trip, Stage } from '$lib/types';
	import { computeHeaderStats } from './headerStats';

	interface Props {
		trip: Trip;
		stage: Stage | null;
		reportType: 'morning' | 'evening';
		reportDate: string;
	}

	let { trip, stage, reportType, reportDate }: Props = $props();

	const eyebrowText = $derived(
		reportType === 'morning' ? 'Morgen-Briefing' : 'Abend-Briefing'
	);
	const stats = $derived(computeHeaderStats(stage));
	const title = $derived(trip.shortcode ? `${trip.name} · ${trip.shortcode}` : trip.name);
</script>

<header data-testid="email-preview-header" class="border rounded-lg p-4 bg-card">
	<span
		data-testid="email-preview-header-eyebrow"
		class="font-mono text-xs uppercase tracking-wider text-muted-foreground"
	>
		{eyebrowText} · {reportDate}
	</span>
	<h2 data-testid="email-preview-header-title" class="text-xl font-semibold mt-1 mb-3">
		{title}
	</h2>
	{#if stage}
		<div class="text-sm text-muted-foreground mb-3">{stage.name} · {stage.date}</div>
	{/if}
	<div
		data-testid="email-preview-header-stats"
		class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3"
	>
		<div class="flex flex-col">
			<span data-testid="email-preview-header-stats-label-distanz" class="text-xs text-muted-foreground">Distanz</span>
			<span class="text-sm font-medium">{stats.distanceKm} km</span>
		</div>
		<div class="flex flex-col">
			<span data-testid="email-preview-header-stats-label-aufstieg" class="text-xs text-muted-foreground">Aufstieg</span>
			<span class="text-sm font-medium">{stats.ascentM} m</span>
		</div>
		<div class="flex flex-col">
			<span data-testid="email-preview-header-stats-label-abstieg" class="text-xs text-muted-foreground">Abstieg</span>
			<span class="text-sm font-medium">{stats.descentM} m</span>
		</div>
		<div class="flex flex-col">
			<span data-testid="email-preview-header-stats-label-max-hoehe" class="text-xs text-muted-foreground">Max-Höhe</span>
			<span class="text-sm font-medium">{stats.maxElevationM} m</span>
		</div>
		<div class="flex flex-col">
			<span data-testid="email-preview-header-stats-label-segmente" class="text-xs text-muted-foreground">Segmente</span>
			<span class="text-sm font-medium">{stats.segmentCount}</span>
		</div>
	</div>
</header>
