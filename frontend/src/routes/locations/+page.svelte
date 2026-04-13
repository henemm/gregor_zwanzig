<script lang="ts">
	import type { Location } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import LocationForm from '$lib/components/LocationForm.svelte';

	let { data } = $props();

	let locations: Location[] = $state(data.locations);
	let dialogMode: 'create' | 'edit' | null = $state(null);
	let editTarget: Location | null = $state(null);
	let deleteTarget: Location | null = $state(null);
	let error: string | null = $state(null);

	async function handleSave(loc: Location) {
		error = null;
		try {
			if (dialogMode === 'create') {
				await api.post<Location>('/api/locations', loc);
			} else {
				await api.put<Location>(`/api/locations/${loc.id}`, loc);
			}
			locations = await api.get<Location[]>('/api/locations');
			dialogMode = null;
			editTarget = null;
		} catch (e: unknown) {
			error =
				(e as { detail?: string })?.detail ??
				(e as { error?: string })?.error ??
				'Fehler beim Speichern';
		}
	}

	async function handleDelete() {
		if (!deleteTarget) return;
		error = null;
		try {
			await api.del(`/api/locations/${deleteTarget.id}`);
			locations = locations.filter((l) => l.id !== deleteTarget!.id);
			deleteTarget = null;
		} catch (e: unknown) {
			error = (e as { error?: string })?.error ?? 'Fehler beim Löschen';
		}
	}

	function openCreate() {
		editTarget = null;
		dialogMode = 'create';
	}

	function openEdit(loc: Location) {
		editTarget = loc;
		dialogMode = 'edit';
	}

	function closeDialog() {
		dialogMode = null;
		editTarget = null;
		error = null;
	}
</script>

<div class="space-y-4">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-bold">Locations</h1>
		<Button onclick={openCreate}>Neue Location</Button>
	</div>

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	{#if locations.length === 0}
		<div data-testid="empty-state" class="rounded-lg border border-dashed p-8 text-center">
			<p class="text-muted-foreground">Keine Locations vorhanden</p>
			<Button variant="outline" class="mt-4" onclick={openCreate}>Erste Location erstellen</Button>
		</div>
	{:else}
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head>Name</Table.Head>
					<Table.Head>Koordinaten</Table.Head>
					<Table.Head>Höhe</Table.Head>
					<Table.Head>Profil</Table.Head>
					<Table.Head class="text-right">Aktionen</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each locations as loc}
					<Table.Row>
						<Table.Cell class="font-medium">{loc.name}</Table.Cell>
						<Table.Cell class="text-sm text-muted-foreground">
							{loc.lat.toFixed(4)}, {loc.lon.toFixed(4)}
						</Table.Cell>
						<Table.Cell class="text-sm">
							{loc.elevation_m != null ? `${loc.elevation_m} m` : '—'}
						</Table.Cell>
						<Table.Cell>
							{#if loc.activity_profile}
								<Badge variant="secondary">{loc.activity_profile}</Badge>
							{/if}
						</Table.Cell>
						<Table.Cell class="text-right">
							<Button variant="ghost" size="sm" onclick={() => openEdit(loc)}>Bearbeiten</Button>
							<Button variant="ghost" size="sm" onclick={() => (deleteTarget = loc)}>Löschen</Button>
						</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	{/if}
</div>

<!-- Create/Edit Dialog -->
<Dialog.Root
	open={dialogMode !== null}
	onOpenChange={(open) => { if (!open) closeDialog(); }}
>
	<Dialog.Content class="max-h-[80vh] max-w-lg overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>{dialogMode === 'create' ? 'Neue Location' : 'Location bearbeiten'}</Dialog.Title>
		</Dialog.Header>
		{#if dialogMode}
			<LocationForm
				location={editTarget ?? undefined}
				onsave={handleSave}
				oncancel={closeDialog}
			/>
		{/if}
	</Dialog.Content>
</Dialog.Root>

<!-- Delete Confirmation Dialog -->
<Dialog.Root
	open={deleteTarget !== null}
	onOpenChange={(open) => { if (!open) deleteTarget = null; }}
>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>Location löschen</Dialog.Title>
			<Dialog.Description>
				Möchtest du "{deleteTarget?.name}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Button variant="outline" onclick={() => (deleteTarget = null)}>Abbrechen</Button>
			<Button variant="destructive" onclick={handleDelete}>Löschen</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
