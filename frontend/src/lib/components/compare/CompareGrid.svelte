<script lang="ts">
	// Issue #490 — CompareGrid: Kachel-Grid für /compare-Übersicht.
	//
	// Spec: docs/specs/modules/issue_490_compare_grid.md
	// Ersetzt die Tabellen-Ansicht (CompareList/CompareRow) durch ein
	// responsives CSS-Grid mit CompareTile-Molecules (Issue #488).
	//
	// Eltern-Komponente: routes/compare/+page.svelte
	// Kind-Komponente: CompareTile (via molecules-Barrel)

	import { goto } from '$app/navigation';
	import type { ComparePreset } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Input, Btn } from '$lib/components/atoms';
	import { ConfirmDialog } from '$lib/components/molecules';
	import CompareTile from './CompareTile.svelte';
	import { deriveStatusFromPreset } from './subscriptionHelpers.js';
	import SearchIcon from '@lucide/svelte/icons/search';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';

	interface Props {
		presets: ComparePreset[];
	}

	let { presets = $bindable([]) }: Props = $props();

	let search = $state('');
	let deleteTarget: ComparePreset | null = $state(null);
	let error: string | null = $state(null);

	const items = $derived(
		presets.filter((p) => (p.name ?? '').toLowerCase().includes(search.toLowerCase()))
	);

	function handleAction(preset: ComparePreset, id: string) {
		if (id === 'delete') {
			deleteTarget = preset;
		}
		// Weitere Aktionen (pause, send, preview, edit) folgen in späteren Issues
	}

	async function confirmDelete() {
		if (!deleteTarget) return;
		error = null;
		const target = deleteTarget;
		try {
			await api.del(`/api/compare/presets/${target.id}`);
			presets = presets.filter((p) => p.id !== target.id);
			deleteTarget = null;
		} catch {
			error = 'Löschen fehlgeschlagen. Bitte versuche es erneut.';
			deleteTarget = null;
		}
	}
</script>

{#if presets.length > 0}
	<div class="relative mb-4 max-w-[380px]">
		<SearchIcon class="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
		<Input placeholder="Vergleich suchen …" class="pl-8 rounded-full" bind:value={search} />
	</div>
{/if}

{#if error}
	<p class="text-sm text-destructive mb-3">{error}</p>
{/if}

{#if presets.length === 0}
	<div class="flex flex-col items-center gap-3 py-12 text-center">
		<MapPinIcon class="size-8 text-[var(--g-ink-4)]" />
		<p class="text-sm text-[var(--g-ink-3)]">Noch keine Orts-Vergleiche — leg deinen ersten an</p>
		<Btn variant="outline" href="/compare/new">+ Neuer Vergleich</Btn>
	</div>
{:else if items.length === 0}
	<p class="text-sm text-[var(--g-ink-3)]">Keine Vergleiche für »{search}« gefunden.</p>
{:else}
	<div
		style:display="grid"
		style:grid-template-columns="repeat(auto-fill, minmax(300px, 1fr))"
		style:gap="var(--g-space-4, 16px)"
	>
		{#each items as preset (preset.id)}
			<CompareTile
				sub={preset}
				accent={deriveStatusFromPreset(preset) === 'active'}
				onclick={() => goto('/compare/' + preset.id)}
				onAction={(id) => handleAction(preset, id)}
			/>
		{/each}
	</div>
{/if}

<ConfirmDialog
	open={deleteTarget !== null}
	title="Vergleich löschen?"
	description={'"' + (deleteTarget?.name ?? '') + '" wird unwiderruflich gelöscht.'}
	confirmLabel="Löschen"
	confirmVariant="destructive"
	onConfirm={confirmDelete}
	onCancel={() => (deleteTarget = null)}
	onOpenChange={(open) => { if (!open) deleteTarget = null; }}
/>
