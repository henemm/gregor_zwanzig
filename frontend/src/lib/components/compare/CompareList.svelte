<script lang="ts">
	// Issue #472 — Tabellen-Skelett der Orts-Vergleich-Übersicht (ComparePreset-basiert).
	//
	// Spec: docs/specs/modules/issue_472_compare_list_restore.md §3
	// Eltern-Komponente: routes/compare/+page.svelte
	// Kind-Komponente: CompareRow.svelte
	//
	// History: Ursprünglich #439 (Subscription); auf ComparePreset migriert in #472.

	import type { ComparePreset } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Input, Btn } from '$lib/components/atoms';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { EmptyState } from '$lib/components/ui/empty-state/index.js';
	import SearchIcon from '@lucide/svelte/icons/search';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import CompareRow from './CompareRow.svelte';

	interface Props {
		presets: ComparePreset[];
	}

	let { presets = $bindable([]) }: Props = $props();

	let search = $state('');
	let deleteTarget: ComparePreset | null = $state(null);
	let error: string | null = $state(null);

	let items = $derived(
		presets.filter((p) => (p.name ?? '').toLowerCase().includes(search.toLowerCase()))
	);

	async function confirmDelete() {
		if (!deleteTarget) return;
		error = null;
		const target = deleteTarget;
		try {
			await api.del(`/api/compare/presets/${target.id}`);
			presets = presets.filter((p) => p.id !== target.id);
			deleteTarget = null;
		} catch {
			error = 'Löschen fehlgeschlagen';
		}
	}
</script>

{#if presets.length > 0}
	<div class="relative mb-3 max-w-[380px]">
		<SearchIcon class="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
		<Input placeholder="Suchen..." class="pl-8 rounded-full" bind:value={search} />
	</div>
{/if}

{#if error}
	<p class="text-sm text-destructive">{error}</p>
{/if}

{#if presets.length === 0}
	<EmptyState
		icon={MapPinIcon}
		title="Noch kein Orts-Vergleich"
		description="Lege deinen ersten Orts-Vergleich an."
	>
		<Btn variant="outline" href="/compare/new">+ Neuer Vergleich</Btn>
	</EmptyState>
{:else if items.length === 0}
	<p class="text-sm text-muted-foreground">Keine Vergleiche für »{search}« gefunden.</p>
{:else}
	<div class="overflow-x-auto -mx-4 px-4 desktop:mx-0 desktop:px-0">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head>Name</Table.Head>
					<Table.Head>Orte</Table.Head>
					<Table.Head>Profil</Table.Head>
					<Table.Head>Kanäle</Table.Head>
					<Table.Head>Versand</Table.Head>
					<Table.Head class="text-right">Aktionen</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each items as preset (preset.id)}
					<CompareRow
						{preset}
						ondelete={() => (deleteTarget = preset)}
					/>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
{/if}

<!-- Delete-Confirm-Dialog -->
<Dialog.Root
	open={deleteTarget !== null}
	onOpenChange={(open) => { if (!open) deleteTarget = null; }}
>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>Vergleich löschen?</Dialog.Title>
		</Dialog.Header>
		<p class="text-sm">„{deleteTarget?.name}" wird unwiderruflich gelöscht.</p>
		<Dialog.Footer>
			<Btn variant="outline" onclick={() => (deleteTarget = null)}>Abbrechen</Btn>
			<Btn variant="destructive" onclick={confirmDelete}>Löschen</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
