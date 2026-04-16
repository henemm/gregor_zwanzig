<script lang="ts">
	import type { Location } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import LocationForm from '$lib/components/LocationForm.svelte';
	import WeatherConfigDialog from '$lib/components/WeatherConfigDialog.svelte';
	import SearchIcon from '@lucide/svelte/icons/search';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import CloudSunIcon from '@lucide/svelte/icons/cloud-sun';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';

	let { data } = $props();

	let locations: Location[] = $state(data.locations);
	let search = $state('');
	let filteredLocations = $derived(
		locations.filter(l => l.name.toLowerCase().includes(search.toLowerCase()))
	);
	let dialogMode: 'create' | 'edit' | null = $state(null);
	let editTarget: Location | null = $state(null);
	let deleteTarget: Location | null = $state(null);
	let weatherTarget: Location | null = $state(null);
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

	async function handleWeatherSave(config: Record<string, unknown>) {
		if (!weatherTarget) return;
		error = null;
		try {
			await api.put(`/api/locations/${weatherTarget.id}/weather-config`, config);
			locations = await api.get<Location[]>('/api/locations');
			weatherTarget = null;
		} catch (e: unknown) {
			error = (e as { error?: string; detail?: string })?.detail
				?? (e as { error?: string })?.error
				?? 'Fehler beim Speichern der Wetter-Konfiguration';
		}
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
		<div data-testid="empty-state" class="rounded-lg border border-dashed p-10 text-center">
			<MapPinIcon class="mx-auto mb-3 size-10 text-muted-foreground/40" />
			<p class="font-medium">Keine Locations vorhanden</p>
			<p class="mt-1 text-sm text-muted-foreground">Fuege Orte hinzu, um Wetter-Daten abzurufen und zu vergleichen.</p>
			<Button variant="outline" class="mt-4" onclick={openCreate}>Erste Location erstellen</Button>
		</div>
	{:else}
		<div class="relative mb-3 max-w-xs">
			<SearchIcon class="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
			<Input placeholder="Suchen..." class="pl-8" bind:value={search} />
		</div>
		<div class="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head>Name</Table.Head>
					<Table.Head class="hidden sm:table-cell">Koordinaten</Table.Head>
					<Table.Head class="hidden sm:table-cell">Höhe</Table.Head>
					<Table.Head class="hidden md:table-cell">Profil</Table.Head>
					<Table.Head class="text-right">Aktionen</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each filteredLocations as loc}
					<Table.Row>
						<Table.Cell class="font-medium">{loc.name}</Table.Cell>
						<Table.Cell class="hidden sm:table-cell text-sm text-muted-foreground">
							{loc.lat.toFixed(4)}, {loc.lon.toFixed(4)}
						</Table.Cell>
						<Table.Cell class="hidden sm:table-cell text-sm">
							{loc.elevation_m != null ? `${loc.elevation_m} m` : '—'}
						</Table.Cell>
						<Table.Cell class="hidden md:table-cell">
							{#if loc.activity_profile}
								<Badge variant="secondary">{loc.activity_profile}</Badge>
							{/if}
						</Table.Cell>
						<Table.Cell class="text-right">
							<div class="inline-flex gap-0.5">
								<Button variant="ghost" size="icon-sm" title="Wetter" onclick={() => (weatherTarget = loc)}><CloudSunIcon class="size-3.5" /></Button>
								<Button variant="ghost" size="icon-sm" title="Bearbeiten" onclick={() => openEdit(loc)}><PencilIcon class="size-3.5" /></Button>
								<Button variant="ghost" size="icon-sm" class="hidden sm:inline-flex" title="Löschen" onclick={() => (deleteTarget = loc)}><Trash2Icon class="size-3.5" /></Button>
							</div>
						</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
		</div>
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

<!-- Weather Config Dialog -->
<WeatherConfigDialog
	open={weatherTarget !== null}
	entityName={weatherTarget?.name ?? ''}
	currentConfig={weatherTarget?.display_config}
	onsave={handleWeatherSave}
	onclose={() => (weatherTarget = null)}
/>

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
