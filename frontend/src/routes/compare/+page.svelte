<script lang="ts">
	// Issue #490 — /compare Übersicht mit Kachel-Grid (Block B, Epic #485).
	// Issue #493 — Mobile-Responsive: Stack unter 900 px (Block E).
	// Issue #582 — Design-Fidelity: JSX 1:1 (Block A).
	import type { ComparePreset } from '$lib/types.js';
	import { Eyebrow, Btn, Card, Stat } from '$lib/components/atoms';
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

	// Issue #582 — Suche immer sichtbar (nach JSX-Vorlage).
	let searchQuery = $state('');
	const filteredPresets = $derived(
		searchQuery
			? presets.filter((p) => p.name.toLowerCase().includes(searchQuery.toLowerCase()))
			: presets
	);

	// Issue #611 — Archivieren aus dem mobilen Kachel-Stack (Desktop läuft über
	// CompareGrid). Setzt archived_at und entfernt den Vergleich aus der Liste.
	async function handleTileAction(preset: ComparePreset, id: string) {
		if (id !== 'archive') return;
		try {
			const res = await fetch(`/api/compare/presets/${preset.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ archived: true })
			});
			if (res.ok) presets = presets.filter((p) => p.id !== preset.id);
		} catch {
			/* fail-soft: Liste bleibt unverändert */
		}
	}
</script>

<div style="background: var(--g-paper)">
	<main style="flex: 1; padding: 32px 40px 60px; overflow: auto">
		<div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 28px">
			<div>
				<Eyebrow>Workspace · Orts-Vergleiche</Eyebrow>
				<div style="font-size: 32px; font-weight: 600; letter-spacing: -0.025em; margin-top: 4px">Orts-Vergleiche</div>
				<div style="font-size: 14px; color: var(--g-ink-3); margin-top: 6px; max-width: 620px">
					Tägliche Briefings, die mehrere Orte gegeneinander stellen und eine
					Empfehlung mitliefern („heute ist Ort X am besten — weil …").
					Einmalig eingerichtet, läuft pro Vergleich automatisch.
				</div>
			</div>
			<Btn variant="primary" href="/compare/new">+ Neuer Vergleich</Btn>
		</div>

		<!-- Suche — immer sichtbar (Issue #582) -->
		<div style="position: relative; max-width: 380px; margin-bottom: 20px">
			<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-4)" stroke-width="2"
				style="position: absolute; top: 11px; left: 12px">
				<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>
			</svg>
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Suchen…"
				style="width: 100%; padding: 9px 14px 9px 34px; border: 1px solid var(--g-rule); border-radius: var(--g-r-pill); background: var(--g-card); font-size: 13px; font-family: var(--g-font-sans); color: var(--g-ink); outline: none; box-sizing: border-box"
			/>
		</div>

		<!-- Stats-Zeile — Stat-Molecule (Issue #582) -->
		<div style="display: flex; gap: 24px; margin-bottom: 22px; padding-bottom: 16px; border-bottom: 1px solid var(--g-rule-soft)">
			<Stat label="Aktiv"    value={counts.active} layout="inline" tone="accent" mono/>
			<Stat label="Pausiert" value={counts.paused} layout="inline" mono/>
			<Stat label="Drafts"   value={counts.draft}  layout="inline" mono/>
		</div>

		<!-- Mobiler Kachel-Stack (#493): vertikal, unter 900 px -->
		<div class="desktop:hidden flex flex-col gap-3">
			{#if filteredPresets.length === 0}
				<Card padding={40} style="text-align: center; color: var(--g-ink-3); font-size: 13px">
					{searchQuery ? `Keine Vergleiche für »${searchQuery}« gefunden.` : 'Noch keine Vergleiche angelegt.'}
				</Card>
			{:else}
				{#each filteredPresets as preset (preset.id)}
					<a href="/compare/{preset.id}" class="block min-h-[44px]">
						<CompareTile
							sub={preset}
							dense={true}
							onAction={(id) => handleTileAction(preset, id)}
						/>
					</a>
				{/each}
			{/if}
		</div>

		<!-- Desktop Kachel-Grid (#490) -->
		<div class="hidden desktop:block">
			{#if filteredPresets.length === 0}
				<Card padding={40} style="text-align: center; color: var(--g-ink-3); font-size: 13px">
					{searchQuery ? `Keine Vergleiche für »${searchQuery}« gefunden.` : 'Noch keine Vergleiche angelegt.'}
				</Card>
			{:else}
				<CompareGrid bind:presets {searchQuery} />
			{/if}
		</div>

		<!-- Footer-Zähler (Issue #582) -->
		<div style="margin-top: 16px; font-size: 11px; color: var(--g-ink-4); font-family: var(--g-font-mono); letter-spacing: 0.06em">
			{filteredPresets.length} von {presets.length} Vergleichen
		</div>
	</main>
</div>
