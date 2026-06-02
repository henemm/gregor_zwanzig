<script lang="ts">
	// Issue #490 — /compare Übersicht mit Kachel-Grid (Block B, Epic #485).
	// Issue #493 — Mobile-Responsive: Stack unter 900 px (Block E).
	import type { ComparePreset } from '$lib/types.js';
	import { Eyebrow, Btn } from '$lib/components/atoms';
	import CompareGrid from '$lib/components/compare/CompareGrid.svelte';
	import CompareTile from '$lib/components/compare/CompareTile.svelte';
	import { deriveStatusFromPreset } from '$lib/components/compare/subscriptionHelpers.js';

	let { data } = $props();
	let presets: ComparePreset[] = $state(data.presets ?? []);

	let counts = $derived({
		active: presets.filter((p) => deriveStatusFromPreset(p) === 'active').length,
		paused: presets.filter((p) => deriveStatusFromPreset(p) === 'paused').length,
		draft: presets.filter((p) => deriveStatusFromPreset(p) === 'draft').length
	});

	// Issue #531 — Suchleiste: lokaler case-insensitive Name-Filter,
	// nur sichtbar wenn mehr als 3 Vergleiche vorhanden sind.
	let searchQuery = $state('');
	const showSearch = $derived(presets.length > 3);
	const filteredPresets = $derived(
		searchQuery
			? presets.filter((p) => p.name.toLowerCase().includes(searchQuery.toLowerCase()))
			: presets
	);
</script>

<div class="p-8 max-w-5xl mx-auto">
	<div class="flex items-start justify-between mb-6">
		<div>
			<Eyebrow>WORKSPACE · ORTS-VERGLEICHE</Eyebrow>
			<h1 class="text-3xl font-semibold tracking-tight mt-1">Orts-Vergleiche</h1>
			<p class="text-sm text-[var(--g-ink-3)] mt-2 max-w-[560px]">
				Tägliche Briefings, die mehrere Orte gegeneinander stellen und eine Empfehlung mitliefern.
				Einmalig eingerichtet, läuft pro Vergleich automatisch.
			</p>
		</div>
		<Btn variant="primary" href="/compare/new">+ Neuer Vergleich</Btn>
	</div>

	<!-- Issue #531 — Suchfeld (nur sichtbar bei mehr als 3 Vergleichen) -->
	{#if showSearch}
		<div class="relative max-w-[380px] mb-4">
			<svg class="absolute top-[11px] left-3 w-3.5 h-3.5 text-[var(--g-ink-4)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>
			</svg>
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Suchen…"
				class="w-full py-2 pr-4 pl-8 border border-[var(--g-rule)] rounded-full bg-[var(--g-card)] text-sm text-[var(--g-ink)] outline-none"
			/>
		</div>
	{/if}

	<!-- Stats-Zeile -->
	{#if presets.length > 0}
		<div class="flex gap-6 mb-5 pb-4 border-b border-[var(--g-rule-soft)]">
			<div class="flex items-baseline gap-2">
				<span class="text-2xl font-semibold text-[var(--g-accent)]">{counts.active}</span>
				<span class="text-xs font-mono uppercase tracking-widest text-[var(--g-ink-3)]">Aktiv</span>
			</div>
			<div class="flex items-baseline gap-2">
				<span class="text-2xl font-semibold">{counts.paused}</span>
				<span class="text-xs font-mono uppercase tracking-widest text-[var(--g-ink-3)]">Pausiert</span>
			</div>
			<div class="flex items-baseline gap-2">
				<span class="text-2xl font-semibold">{counts.draft}</span>
				<span class="text-xs font-mono uppercase tracking-widest text-[var(--g-ink-3)]">Drafts</span>
			</div>
		</div>
	{/if}

	<!-- Mobiler Kachel-Stack (#493): vertikal, unter 900 px -->
	<div class="desktop:hidden flex flex-col gap-3">
		{#if filteredPresets.length === 0 && searchQuery}
			<div class="text-sm text-center text-[var(--g-ink-3)] py-8 border border-[var(--g-rule)] rounded-lg">
				Keine Vergleiche für »{searchQuery}« gefunden.
			</div>
		{:else}
			{#each filteredPresets as preset (preset.id)}
				<a href="/compare/{preset.id}" class="block min-h-[44px]">
					<CompareTile sub={preset} dense={true} />
				</a>
			{/each}
		{/if}
	</div>

	<!-- Desktop Kachel-Grid (#490) -->
	<div class="hidden desktop:block">
		<CompareGrid bind:presets {searchQuery} />
	</div>
</div>
