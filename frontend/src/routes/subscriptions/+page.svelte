<script lang="ts">
	import type { Subscription, Location } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import SubscriptionForm from '$lib/components/SubscriptionForm.svelte';
	import WeatherConfigDialog from '$lib/components/WeatherConfigDialog.svelte';
	import SearchIcon from '@lucide/svelte/icons/search';
	import BellIcon from '@lucide/svelte/icons/bell';
	import CloudSunIcon from '@lucide/svelte/icons/cloud-sun';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';

	let { data } = $props();

	const WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];

	let subscriptions: Subscription[] = $state(data.subscriptions);
	let search = $state('');
	let filteredSubs = $derived(
		subscriptions.filter(s => s.name.toLowerCase().includes(search.toLowerCase()))
	);
	let locations: Location[] = $state(data.locations);
	let dialogMode: 'create' | 'edit' | null = $state(null);
	let editTarget: Subscription | null = $state(null);
	let deleteTarget: Subscription | null = $state(null);
	let weatherTarget: Subscription | null = $state(null);
	let error: string | null = $state(null);

	function scheduleLabel(sub: Subscription): string {
		if (sub.schedule === 'daily_morning') return 'Täglich 07:00';
		if (sub.schedule === 'daily_evening') return 'Täglich 18:00';
		if (sub.schedule === 'weekly') return `Wöchentlich ${WEEKDAYS[sub.weekday] ?? ''}`;
		return sub.schedule;
	}

	function locationsLabel(sub: Subscription): string {
		if (!sub.locations || sub.locations.length === 0 || sub.locations[0] === '*') {
			return 'Alle';
		}
		return sub.locations
			.map((id) => locations.find((l) => l.id === id)?.name ?? id)
			.join(', ');
	}

	async function handleSave(sub: Subscription) {
		error = null;
		try {
			if (dialogMode === 'create') {
				await api.post<Subscription>('/api/subscriptions', sub);
			} else {
				await api.put<Subscription>(`/api/subscriptions/${sub.id}`, sub);
			}
			subscriptions = await api.get<Subscription[]>('/api/subscriptions');
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
			await api.del(`/api/subscriptions/${deleteTarget.id}`);
			subscriptions = subscriptions.filter((s) => s.id !== deleteTarget!.id);
			deleteTarget = null;
		} catch (e: unknown) {
			error = (e as { error?: string })?.error ?? 'Fehler beim Löschen';
		}
	}

	async function handleToggleEnabled(sub: Subscription) {
		error = null;
		try {
			const updated: Subscription = { ...sub, enabled: !sub.enabled };
			await api.put<Subscription>(`/api/subscriptions/${sub.id}`, updated);
			subscriptions = subscriptions.map((s) => (s.id === sub.id ? updated : s));
		} catch (e: unknown) {
			error = (e as { error?: string })?.error ?? 'Fehler beim Aktualisieren';
		}
	}

	function openCreate() {
		editTarget = null;
		dialogMode = 'create';
	}

	function openEdit(sub: Subscription) {
		editTarget = sub;
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
			await api.put(`/api/subscriptions/${weatherTarget.id}/weather-config`, config);
			subscriptions = await api.get<Subscription[]>('/api/subscriptions');
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
		<h1 class="text-2xl font-bold">Abos</h1>
		<Button onclick={openCreate}>Neues Abo</Button>
	</div>

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	{#if subscriptions.length === 0}
		<div data-testid="empty-state" class="rounded-lg border border-dashed p-10 text-center">
			<BellIcon class="mx-auto mb-3 size-10 text-muted-foreground/40" />
			<p class="font-medium">Keine Abos vorhanden</p>
			<p class="mt-1 text-sm text-muted-foreground">Erstelle dein erstes Abo fuer automatische Wetter-Vergleiche.</p>
			<Button variant="outline" class="mt-4" onclick={openCreate}>Erstes Abo erstellen</Button>
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
					<Table.Head>Zeitplan</Table.Head>
					<Table.Head class="hidden sm:table-cell">Zeitfenster</Table.Head>
					<Table.Head class="hidden md:table-cell">Locations</Table.Head>
					<Table.Head class="hidden sm:table-cell">Kanäle</Table.Head>
					<Table.Head class="hidden md:table-cell">Status</Table.Head>
					<Table.Head class="text-right">Aktionen</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each filteredSubs as sub}
					<Table.Row>
						<Table.Cell class="font-medium">
							{sub.name}
							{#if !sub.enabled}
								<Badge variant="secondary" class="ml-2">Deaktiviert</Badge>
							{/if}
						</Table.Cell>
						<Table.Cell class="text-sm">{scheduleLabel(sub)}</Table.Cell>
						<Table.Cell class="hidden sm:table-cell text-sm text-muted-foreground">
							{sub.time_window_start}:00 – {sub.time_window_end}:00
						</Table.Cell>
						<Table.Cell class="hidden md:table-cell text-sm text-muted-foreground max-w-[180px] truncate">
							{locationsLabel(sub)}
						</Table.Cell>
						<Table.Cell class="hidden sm:table-cell">
							<div class="flex gap-1">
								{#if sub.send_email}
									<Badge variant="outline">E-Mail</Badge>
								{/if}
								{#if sub.send_signal}
									<Badge variant="outline">Signal</Badge>
								{/if}
								{#if sub.send_telegram}
									<Badge variant="outline">Telegram</Badge>
								{/if}
							</div>
						</Table.Cell>
						<Table.Cell class="hidden md:table-cell">
							<Button
								variant="ghost"
								size="sm"
								onclick={() => handleToggleEnabled(sub)}
							>
								{sub.enabled ? 'Deaktivieren' : 'Aktivieren'}
							</Button>
						</Table.Cell>
						<Table.Cell class="text-right">
							<div class="inline-flex gap-0.5">
								<Button variant="ghost" size="icon-sm" title="Wetter-Konfiguration" onclick={() => (weatherTarget = sub)}><CloudSunIcon class="size-3.5" /></Button>
								<Button variant="ghost" size="icon-sm" title="Bearbeiten" onclick={() => openEdit(sub)}><PencilIcon class="size-3.5" /></Button>
								<Button variant="ghost" size="icon-sm" title="Löschen" onclick={() => (deleteTarget = sub)}><Trash2Icon class="size-3.5" /></Button>
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
			<Dialog.Title>{dialogMode === 'create' ? 'Neues Abo' : 'Abo bearbeiten'}</Dialog.Title>
		</Dialog.Header>
		{#if dialogMode}
			<SubscriptionForm
				subscription={editTarget ?? undefined}
				{locations}
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
			<Dialog.Title>Subscription löschen</Dialog.Title>
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

<!-- Weather Config Dialog -->
<WeatherConfigDialog
	open={weatherTarget !== null}
	entityName={weatherTarget?.name ?? ''}
	currentConfig={weatherTarget?.display_config}
	onsave={handleWeatherSave}
	onclose={() => (weatherTarget = null)}
/>
