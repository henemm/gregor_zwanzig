<script lang="ts">
	// Issue #491 — CompareDetail: Kapselt alle 5 Cards + Monitoring-Streifen.
	import type { ComparePreset, Location } from '$lib/types.js';
	import { Card, Dot, Pill, KV } from '$lib/components/atoms';
	import { deriveStatusFromPreset, presetScheduleLabel, formatLastSent, STATUS_MAP } from '$lib/components/compare/subscriptionHelpers.js';

	interface Props {
		preset: ComparePreset;
		locations: Location[];
	}

	let { preset, locations }: Props = $props();

	let status = $derived(deriveStatusFromPreset(preset));
	let statusInfo = $derived(STATUS_MAP[status]);

	let resolvedLocations = $derived(
		preset.location_ids.map((id, idx) => ({
			rank: idx + 1,
			loc: locations.find((l) => l.id === id)
		}))
	);

	let idealRanges = $derived(
		preset.display_config?.ideal_ranges as Record<string, { min: number; max: number; unit?: string }> | undefined
	);

	let channelLayouts = $derived(
		preset.display_config?.channel_layouts as Record<string, unknown> | undefined
	);
</script>

<!-- Monitoring-Streifen -->
<div class="flex gap-8 py-3 px-4 mb-6 rounded-lg bg-[var(--g-paper)] border border-[var(--g-rule-soft)] text-sm">
	<div class="flex items-center gap-2">
		<Dot style="background:{statusInfo.dot}" />
		<span class="font-medium">{statusInfo.label}</span>
	</div>
	<div class="flex flex-col">
		<span class="text-xs text-[var(--g-ink-3)] uppercase tracking-wider font-mono">Nächster Versand</span>
		<span>{presetScheduleLabel(preset)}</span>
	</div>
	<div class="flex flex-col">
		<span class="text-xs text-[var(--g-ink-3)] uppercase tracking-wider font-mono">Zuletzt</span>
		<span>{formatLastSent(preset.letzter_versand)}</span>
	</div>
	<div class="flex flex-col">
		<span class="text-xs text-[var(--g-ink-3)] uppercase tracking-wider font-mono">Kanäle</span>
		<span class="text-xs">{preset.empfaenger.join(', ') || '—'}</span>
	</div>
</div>

<!-- 2-Spalten-Grid -->
<div style="display:grid;grid-template-columns:1.7fr 1fr;gap:1.5rem;">
	<!-- Linke Spalte -->
	<div class="flex flex-col gap-4">
		<!-- Card: Verglichene Orte -->
		<Card>
			<h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--g-ink-3)] mb-3">Verglichene Orte</h2>
			{#if resolvedLocations.length === 0}
				<p class="text-sm text-[var(--g-ink-3)]">Noch keine Orte ausgewählt.</p>
			{:else}
				{#each resolvedLocations as { rank, loc }}
					<div class="flex items-center gap-3 py-2 border-b border-[var(--g-rule-soft)] last:border-0">
						<span class="text-xs font-mono text-[var(--g-ink-3)] w-6">{String(rank).padStart(2, '0')}</span>
						<span class="flex-1 font-medium">{loc?.name ?? '—'}</span>
						<span class="text-xs text-[var(--g-ink-3)]">{loc?.elevation_m != null ? `${loc.elevation_m} m` : '—'}</span>
					</div>
				{/each}
			{/if}
		</Card>

		<!-- Card: Idealwerte -->
		<Card>
			<h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--g-ink-3)] mb-3">Idealwerte</h2>
			{#if idealRanges && Object.keys(idealRanges).length > 0}
				{#each Object.entries(idealRanges) as [metric, range]}
					<KV label={metric} value="{range.min}–{range.max}{range.unit ? ' ' + range.unit : ''}" />
				{/each}
			{:else}
				<p class="text-sm text-[var(--g-ink-3)]">Keine Idealwerte konfiguriert.</p>
			{/if}
		</Card>

		<!-- Card: Layout pro Kanal -->
		<Card>
			<h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--g-ink-3)] mb-3">Layout pro Kanal</h2>
			{#if channelLayouts && Object.keys(channelLayouts).length > 0}
				{#each Object.entries(channelLayouts) as [channel, layout]}
					<KV label={channel} value={JSON.stringify(layout)} />
				{/each}
			{:else}
				<p class="text-sm text-[var(--g-ink-3)]">Kein Layout konfiguriert.</p>
			{/if}
		</Card>
	</div>

	<!-- Rechte Spalte -->
	<div class="flex flex-col gap-4">
		<!-- Card: Versand -->
		<Card>
			<h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--g-ink-3)] mb-3">Versand</h2>
			<KV label="Zeitplan" value={presetScheduleLabel(preset)} />
			<KV label="Profil" value={String(preset.profil)} />
			<div class="mt-3">
				<span class="text-xs text-[var(--g-ink-3)] font-mono uppercase tracking-wider">Empfänger</span>
				<div class="flex flex-wrap gap-1 mt-1">
					{#each preset.empfaenger as email}
						<Pill>{email}</Pill>
					{:else}
						<span class="text-sm text-[var(--g-ink-3)]">Keine Empfänger</span>
					{/each}
				</div>
			</div>
		</Card>

		<!-- Card: Vorschau & Prüfung -->
		<Card>
			<h2 class="text-sm font-semibold uppercase tracking-wider text-[var(--g-ink-3)] mb-3">Vorschau · Prüfung</h2>
			<p class="text-sm text-[var(--g-ink-3)]">
				Briefing-Vorschau und manuelle Versandauslösung folgen in Issue #488.
			</p>
		</Card>
	</div>
</div>
