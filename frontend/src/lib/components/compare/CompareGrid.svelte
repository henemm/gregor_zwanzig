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
	import { ConfirmDialog } from '$lib/components/molecules';
	import CompareTile from './CompareTile.svelte';
	import { deriveStatusFromPreset } from './subscriptionHelpers.js';
	import { Card } from '$lib/components/atoms';

	interface Props {
		presets: ComparePreset[];
		searchQuery?: string;
	}

	// Issue #531 — Such-Input lebt jetzt in /compare/+page.svelte;
	// CompareGrid bekommt den Query als Prop und filtert intern.
	// `bind:presets` bleibt erhalten — Lösch-Operationen modifizieren die Liste.
	let { presets = $bindable([]), searchQuery = '' }: Props = $props();

	let deleteTarget: ComparePreset | null = $state(null);
	let error: string | null = $state(null);

	const items = $derived(
		searchQuery
			? presets.filter((p) => (p.name ?? '').toLowerCase().includes(searchQuery.toLowerCase()))
			: presets
	);

	function handleAction(preset: ComparePreset, id: string) {
		if (id === 'delete') {
			deleteTarget = preset;
		} else if (id === 'archive') {
			void archivePreset(preset);
		} else if (id === 'edit' || id === 'setup') {
			void goto('/compare/' + preset.id + '/edit');
		} else if (id === 'preview') {
			void goto('/compare/' + preset.id + '?tab=vorschau');
		} else if (id === 'pause') {
			void togglePause(preset);
		}
	}

	// Bug #626 — Pause/Aktivieren: Read-Modify-Write, nur schedule überschreiben.
	// Muster wie CompareTabs.handleToggleActive (schedule 'manual' = pausiert).
	async function togglePause(preset: ComparePreset) {
		error = null;
		const isPaused = deriveStatusFromPreset(preset) === 'paused';
		const nextSchedule = isPaused ? 'daily' : 'manual';
		try {
			const res = await fetch(`/api/compare/presets/${preset.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ ...preset, schedule: nextSchedule })
			});
			if (!res.ok) throw new Error(`PUT failed: ${res.status}`);
			presets = presets.map((p) =>
				p.id === preset.id ? { ...p, schedule: nextSchedule } : p
			);
		} catch {
			error = 'Status-Änderung fehlgeschlagen. Bitte versuche es erneut.';
		}
	}

	// Issue #611 — Vergleich archivieren: archived_at serverseitig setzen, danach
	// aus der aktiven Liste entfernen (er erscheint dann im Archiv).
	async function archivePreset(preset: ComparePreset) {
		error = null;
		try {
			const res = await fetch(`/api/compare/presets/${preset.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ archived: true })
			});
			if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
			presets = presets.filter((p) => p.id !== preset.id);
		} catch {
			error = 'Archivieren fehlgeschlagen. Bitte versuche es erneut.';
		}
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

{#if error}
	<p class="text-sm text-destructive mb-3">{error}</p>
{/if}

{#if presets.length === 0}
	<Card padding={40} style="text-align: center; color: var(--g-ink-3); font-size: 13px">
		Noch keine Orts-Vergleiche — leg deinen ersten an.
	</Card>
{:else if items.length === 0}
	<Card padding={40} style="text-align: center; color: var(--g-ink-3); font-size: 13px">
		Keine Vergleiche für »{searchQuery}« gefunden.
	</Card>
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
