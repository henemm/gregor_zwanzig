<script lang="ts">
	// Issue #472 — /compare Listenansicht (Design: screen-compare-list.jsx)
	import type { ComparePreset } from '$lib/types.js';
	import { Eyebrow, Btn } from '$lib/components/atoms';
	import CompareGrid from '$lib/components/compare/CompareGrid.svelte';
	import { deriveStatusFromPreset } from '$lib/components/compare/subscriptionHelpers.js';

	let { data } = $props();
	let presets: ComparePreset[] = $state(data.presets ?? []);

	let counts = $derived({
		active: presets.filter((p) => deriveStatusFromPreset(p) === 'active').length,
		paused: presets.filter((p) => deriveStatusFromPreset(p) === 'paused').length,
		draft: presets.filter((p) => deriveStatusFromPreset(p) === 'draft').length
	});
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

	<CompareGrid bind:presets />
</div>
