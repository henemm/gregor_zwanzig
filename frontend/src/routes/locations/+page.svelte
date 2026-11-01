<script lang="ts">
	import type { Location } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Btn, Input } from '$lib/components/atoms';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import LocationForm from '$lib/components/LocationForm.svelte';
	import LocationNewModal from '$lib/components/compare/LocationNewModal.svelte';
	import WeatherConfigDialog from '$lib/components/WeatherConfigDialog.svelte';
	import { ortInUseHinweis, type OrtInUseHinweis } from '$lib/utils/ortLoeschenSperre';
	import { EmptyState } from '$lib/components/ui/empty-state/index.js';
	import SearchIcon from '@lucide/svelte/icons/search';
	import MapPinIcon from '@lucide/svelte/icons/map-pin';
	import CloudSunIcon from '@lucide/svelte/icons/cloud-sun';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import { t, tr } from '$lib/i18n/index.js';

	let { data } = $props();

	let locations: Location[] = $state(data.locations);
	let refetching = $state(false);
	async function refetchLocations() {
		refetching = true;
		try {
			const res = await fetch('/api/locations');
			if (res.ok) {
				locations = await res.json();
			}
		} finally {
			refetching = false;
		}
	}
	let search = $state('');
	let filteredLocations = $derived(
		locations.filter(l => l.name.toLowerCase().includes(search.toLowerCase()))
	);
	let dialogMode: 'create' | 'edit' | null = $state(null);
	let editTarget: Location | null = $state(null);
	let deleteTarget: Location | null = $state(null);
	let weatherTarget: Location | null = $state(null);
	let error: string | null = $state(null);
	let inUse: OrtInUseHinweis | null = $state(null);

	async function handleSave(loc: Location) {
		error = null;
		try {
			if (dialogMode === 'create') {
				await api.post<Location>('/api/locations', loc);
			} else {
				await api.put<Location>(`/api/locations/${loc.id}`, loc);
			}
			await refetchLocations();
			dialogMode = null;
			editTarget = null;
		} catch (e: unknown) {
			error =
				(e as { detail?: string })?.detail ??
				(e as { error?: string })?.error ??
				tr('listen.meldung.fehler_speichern');
		}
	}

	function handleNewLocationSave() {
		refetchLocations();
		dialogMode = null;
	}

	async function handleDelete() {
		if (!deleteTarget) return;
		error = null;
		inUse = null;
		try {
			await api.del(`/api/locations/${deleteTarget.id}`);
			locations = locations.filter((l) => l.id !== deleteTarget!.id);
			deleteTarget = null;
		} catch (e: unknown) {
			inUse = ortInUseHinweis(e);
			error = inUse ? null : ((e as { error?: string })?.error ?? tr('listen.meldung.fehler_loeschen'));
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
			await refetchLocations();
			weatherTarget = null;
		} catch (e: unknown) {
			error = (e as { error?: string; detail?: string })?.detail
				?? (e as { error?: string })?.error
				?? tr('listen.meldung.fehler_wetter_konfiguration');
		}
	}
</script>

<div class="space-y-4">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-bold">{$t('listen.orte.titel')}</h1>
		<Btn variant="primary" onclick={openCreate}>{$t('listen.orte.neu')}</Btn>
	</div>

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}
	{#if locations.length === 0}
		<EmptyState icon={MapPinIcon} title={$t('listen.orte.leer_titel')} description={$t('listen.orte.leer_text')}>
			<Btn variant="outline" onclick={openCreate}>{$t('listen.orte.hinzufuegen')}</Btn>
		</EmptyState>
	{:else}
		<div class="relative mb-3 max-w-xs">
			<SearchIcon class="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
			<Input placeholder={$t('listen.suche.platzhalter_punkte')} class="pl-8" bind:value={search} />
		</div>
		{#if refetching}
			<div class="space-y-3">
				{#each Array(3) as _}
					<div class="h-12 w-full animate-pulse rounded-lg bg-muted"></div>
				{/each}
			</div>
		{:else}
		<div class="overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head>{$t('listen.spalte.name')}</Table.Head>
					<Table.Head class="hidden sm:table-cell">{$t('listen.spalte.koordinaten')}</Table.Head>
					<Table.Head class="hidden sm:table-cell">{$t('listen.spalte.hoehe')}</Table.Head>
					<Table.Head class="hidden md:table-cell">{$t('listen.spalte.profil')}</Table.Head>
					<Table.Head class="text-right">{$t('listen.tabelle.aktionen')}</Table.Head>
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
								<Btn variant="ghost" size="icon-sm" title={$t('listen.orte.wetter')} onclick={() => (weatherTarget = loc)}><CloudSunIcon class="size-3.5" /></Btn>
								<Btn variant="ghost" size="icon-sm" title={$t('home.kachel.bearbeiten')} onclick={() => openEdit(loc)}><PencilIcon class="size-3.5" /></Btn>
								<Btn variant="ghost" size="icon-sm" title={$t('listen.aktion.loeschen')} onclick={() => { inUse = null; deleteTarget = loc; }}><Trash2Icon class="size-3.5" /></Btn>
							</div>
						</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
		</div>
		{/if}
	{/if}
</div>

<!-- Create Modal (eigenes Overlay, kein Shadcn Dialog-Wrapper) -->
{#if dialogMode === 'create'}
	<LocationNewModal
		onsave={handleNewLocationSave}
		oncancel={closeDialog}
	/>
{/if}

<!-- Edit Dialog -->
<Dialog.Root
	open={dialogMode === 'edit'}
	onOpenChange={(open) => { if (!open) closeDialog(); }}
>
	<Dialog.Content class="max-h-[80vh] max-w-lg overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>{$t('listen.orte.bearbeiten_titel')}</Dialog.Title>
		</Dialog.Header>
		{#if dialogMode === 'edit'}
			<LocationForm
				location={editTarget ?? undefined}
				{locations}
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
	entityType="location"
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
			<Dialog.Title>{$t('listen.orte.loeschen_titel')}</Dialog.Title>
			<Dialog.Description>
				{$t('listen.orte.loeschen_text', { name: deleteTarget?.name ?? '' })}
			</Dialog.Description>
		</Dialog.Header>
		{#if inUse}
			<p class="text-sm text-destructive" data-testid="ort-in-use-hinweis">
				{inUse.text}
				{#each inUse.links as l (l.href)}
					<a href={l.href} class="underline ml-1">{l.name}</a>
				{/each}
			</p>
		{/if}
		<Dialog.Footer>
			<Btn variant="outline" onclick={() => (deleteTarget = null)}>{$t('aktionen.abbrechen')}</Btn>
			<Btn variant="destructive" onclick={handleDelete}>{$t('listen.aktion.loeschen')}</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
