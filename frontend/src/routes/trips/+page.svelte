<script lang="ts">
	import type { Trip } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import TripForm from '$lib/components/TripForm.svelte';

	let { data } = $props();

	let trips: Trip[] = $state(data.trips);
	let dialogMode: 'create' | 'edit' | null = $state(null);
	let editTarget: Trip | null = $state(null);
	let deleteTarget: Trip | null = $state(null);
	let error: string | null = $state(null);

	function dateRange(trip: Trip): string {
		if (!trip.stages.length) return '-';
		const dates = trip.stages.map((s) => s.date).sort();
		if (dates.length === 1) return dates[0];
		return `${dates[0]} — ${dates[dates.length - 1]}`;
	}

	async function handleSave(trip: Trip) {
		error = null;
		try {
			if (dialogMode === 'create') {
				await api.post<Trip>('/api/trips', trip);
			} else {
				await api.put<Trip>(`/api/trips/${trip.id}`, trip);
			}
			trips = await api.get<Trip[]>('/api/trips');
			dialogMode = null;
			editTarget = null;
		} catch (e: unknown) {
			error = (e as { error?: string; detail?: string })?.detail
				?? (e as { error?: string })?.error
				?? 'Fehler beim Speichern';
		}
	}

	async function handleDelete() {
		if (!deleteTarget) return;
		error = null;
		try {
			await api.del(`/api/trips/${deleteTarget.id}`);
			trips = trips.filter((t) => t.id !== deleteTarget!.id);
			deleteTarget = null;
		} catch (e: unknown) {
			error = (e as { error?: string })?.error ?? 'Fehler beim Löschen';
		}
	}

	function openCreate() {
		editTarget = null;
		dialogMode = 'create';
	}

	function openEdit(trip: Trip) {
		editTarget = trip;
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
		<h1 class="text-2xl font-bold">Trips</h1>
		<Button onclick={openCreate}>Neuer Trip</Button>
	</div>

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	{#if trips.length === 0}
		<div data-testid="empty-state" class="rounded-lg border border-dashed p-8 text-center">
			<p class="text-muted-foreground">Keine Trips vorhanden</p>
			<Button variant="outline" class="mt-4" onclick={openCreate}>Ersten Trip erstellen</Button>
		</div>
	{:else}
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head>Name</Table.Head>
					<Table.Head>Etappen</Table.Head>
					<Table.Head>Zeitraum</Table.Head>
					<Table.Head class="text-right">Aktionen</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each trips as trip}
					<Table.Row>
						<Table.Cell class="font-medium">{trip.name}</Table.Cell>
						<Table.Cell>
							<Badge variant="secondary">{trip.stages.length} Etappen</Badge>
						</Table.Cell>
						<Table.Cell class="text-sm text-muted-foreground">{dateRange(trip)}</Table.Cell>
						<Table.Cell class="text-right">
							<Button variant="ghost" size="sm" onclick={() => openEdit(trip)}>Bearbeiten</Button>
							<Button variant="ghost" size="sm" onclick={() => (deleteTarget = trip)}>Löschen</Button>
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
	<Dialog.Content class="max-h-[80vh] max-w-2xl overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>{dialogMode === 'create' ? 'Neuer Trip' : 'Trip bearbeiten'}</Dialog.Title>
		</Dialog.Header>
		{#if dialogMode}
			<TripForm
				trip={editTarget ?? undefined}
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
			<Dialog.Title>Trip löschen</Dialog.Title>
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
