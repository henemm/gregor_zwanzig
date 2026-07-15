<script lang="ts">
	// Issue #490 — /compare Übersicht mit Kachel-Grid (Block B, Epic #485).
	// Issue #493 — Mobile-Responsive: Stack unter 900 px (Block E).
	// Issue #582 — Design-Fidelity: JSX 1:1 (Block A).
	// Issue #1256 Scheibe 8d (AC-1..AC-5): kompakter mobiler Kopf über die
	// geteilte Design-Kopfleiste (TopAppBar) statt reflowtem Desktop-Kopf;
	// Suchfeld mobil ersatzlos entfernt (Handoff-5-P3), Stats mobil size="sm",
	// kompaktes Content-Padding (12px 16px 24px, ohne main-px-4-Doppelung).
	import type { ComparePreset } from '$lib/types.js';
	import { Eyebrow, Btn, Card, Stat } from '$lib/components/atoms';
	import CompareGrid from '$lib/components/compare/CompareGrid.svelte';
	import CompareTile from '$lib/components/compare/CompareTile.svelte';
	import { deriveStatusFromPreset } from '$lib/components/compare/subscriptionHelpers.js';
	import MIcon from '$lib/components/mobile/MIcon.svelte';
	import { topAppBarStore } from '$lib/stores/topAppBar.svelte';

	let { data } = $props();
	let presets: ComparePreset[] = $state(data.presets ?? []);

	let counts = $derived({
		active: presets.filter((p) => deriveStatusFromPreset(p) === 'active').length,
		paused: presets.filter((p) => deriveStatusFromPreset(p) === 'paused').length,
		draft: presets.filter((p) => deriveStatusFromPreset(p) === 'draft').length
	});

	// Issue #582 — Suche immer sichtbar (nach JSX-Vorlage); Issue #1256 S8d
	// AC-3: nur noch Desktop, mobil ersatzlos entfernt (Handoff-5-P3).
	let searchQuery = $state('');
	const filteredPresets = $derived(
		searchQuery
			? presets.filter((p) => p.name.toLowerCase().includes(searchQuery.toLowerCase()))
			: presets
	);

	// Issue #611 archivierte die mobile Kachel selbst (onAction/handleTileAction);
	// Issue #1256 Scheibe 8 (AC-21) macht die dense-Kachel zur reinen Navigation —
	// Aktionen (inkl. Archivieren) leben mobil jetzt ausschließlich im Detail-Hub.

	// Issue #1256 Scheibe 8d (AC-1): mobile Design-Kopfleiste befüllen
	// (title/eyebrow/rechte Plus-Aktion → /compare/new). $effect-Cleanup
	// setzt beim Verlassen der Seite zurück (SSR-fest, kein Flackern).
	$effect(() => {
		topAppBarStore.set({
			title: 'Orts-Vergleiche',
			eyebrow: `Workspace · ${presets.length}`,
			right: topAppBarNewCompare
		});
		return () => topAppBarStore.reset();
	});
</script>

{#snippet topAppBarNewCompare()}
	<a
		href="/compare/new"
		data-testid="top-app-bar-new-compare"
		aria-label="Neuer Vergleich"
		class="flex items-center justify-center rounded-md hover:bg-accent"
		style="width: 44px; height: 44px;"
	>
		<MIcon kind="plus" size={20} />
	</a>
{/snippet}

<div style="background: var(--g-paper)">
	<main style="flex: 1; overflow: auto">
		<!-- Desktop-Kopf (Issue #582, ≥900px unverändert) -->
		<div class="hidden desktop:block" style="padding: 32px 40px 60px">
			<div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 28px">
				<div>
					<Eyebrow>Workspace · Orts-Vergleiche</Eyebrow>
					<div style="font-size: 32px; font-weight: 600; letter-spacing: -0.025em; margin-top: 4px">Orts-Vergleiche</div>
					<div style="font-size: 14px; color: var(--g-ink-3); margin-top: 6px; max-width: 620px">
						Stehende Monitore: dieselben Orte im Blick. Briefings wie beim Trip —
						Morgen-Briefing für heute, Abend-Briefing für morgen, zur gewählten
						Uhrzeit. Werte nebeneinander, ohne Ranking. Einmal eingerichtet, läuft
						jeder Vergleich, bis du ihn stoppst.
					</div>
				</div>
				<Btn variant="primary" href="/compare/new">+ Neuer Vergleich</Btn>
			</div>

			<!-- Suche — Desktop-only (Issue #582; Issue #1256 S8d AC-3 entfernt sie mobil) -->
			<div class="hidden desktop:block" style="position: relative; max-width: 380px; margin-bottom: 20px">
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

			<!-- Desktop Kachel-Grid (#490) -->
			{#if filteredPresets.length === 0}
				<Card padding={40} style="text-align: center; color: var(--g-ink-3); font-size: 13px">
					{searchQuery ? `Keine Vergleiche für »${searchQuery}« gefunden.` : 'Noch keine Vergleiche angelegt.'}
				</Card>
			{:else}
				<CompareGrid bind:presets {searchQuery} />
			{/if}

			<!-- Footer-Zähler (Issue #582) -->
			<div style="margin-top: 16px; font-size: 11px; color: var(--g-ink-4); font-family: var(--g-font-mono); letter-spacing: 0.06em">
				{filteredPresets.length} von {presets.length} Vergleichen
			</div>
		</div>

		<!-- Mobiler Kopf (Issue #493; Issue #1256 S8d AC-2/AC-4/AC-5). -mx-4
		     hebt das main-px-4 (S8-Falle Doppel-Padding) auf, bevor die eigene
		     12/16/24-Polsterung greift — Netto-Abstand bleibt 16px. -->
		<div class="desktop:hidden -mx-4" style="padding: 12px 16px 24px">
			<div style="font-size: 13px; color: var(--g-ink-3); line-height: 1.5; margin-bottom: 14px">
				Stehende Monitore: dieselben Orte im Blick. Briefings wie beim Trip —
				morgens für heute, abends für morgen. Ohne Ranking — läuft, bis du stoppst.
			</div>

			<!-- Stats (Stat-Molecule, inline, kompakt — JSX-M Z.42-44) -->
			<div style="display: flex; gap: 20px; padding: 4px 2px 16px; border-bottom: 1px solid var(--g-rule-soft); margin-bottom: 16px">
				<Stat label="Aktiv"    value={counts.active} layout="inline" size="sm" tone="accent" mono/>
				<Stat label="Pausiert" value={counts.paused} layout="inline" size="sm" mono/>
				<Stat label="Drafts"   value={counts.draft}  layout="inline" size="sm" mono/>
			</div>

			<!-- Mobiler Kachel-Stack (#493): vertikal, unter 900 px -->
			<div style="display: flex; flex-direction: column; gap: 10px">
				{#if presets.length === 0}
					<Card padding={40} style="text-align: center; color: var(--g-ink-3); font-size: 13px">
						Noch keine Vergleiche angelegt.
					</Card>
				{:else}
					{#each presets as preset (preset.id)}
						<a href="/compare/{preset.id}" class="block min-h-[44px]">
							<CompareTile sub={preset} dense={true} />
						</a>
					{/each}
				{/if}
			</div>
		</div>
	</main>
</div>
