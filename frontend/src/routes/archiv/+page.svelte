<script lang="ts">
	import { onMount } from 'svelte';
	import type { Trip } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import Segmented from '$lib/components/ui/segmented';
	import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';
	import { EmptyState } from '$lib/components/ui/empty-state/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import SearchIcon from '@lucide/svelte/icons/search';
	import ArchiveIcon from '@lucide/svelte/icons/archive';
	import { filterArchived, sortArchive, type ArchiveSortMode } from './archiveHelpers.js';

	const now = new Date();

	let trips: Trip[] = $state([]);
	let loading = $state(true);
	let loadError: string | null = $state(null);
	let actionError: string | null = $state(null);

	let search = $state('');
	let sortMode: ArchiveSortMode = $state('recent');

	let restoringId: string | null = $state(null);
	let deleteTarget: Trip | null = $state(null);
	let deleting = $state(false);

	const SORT_OPTIONS = [
		{ value: 'recent', label: 'Neueste' },
		{ value: 'stages', label: 'Etappen' }
	];

	onMount(async () => {
		try {
			const all = await api.get<Trip[]>('/api/trips');
			trips = filterArchived(Array.isArray(all) ? all : [], now);
		} catch (e: unknown) {
			loadError = (e as { error?: string })?.error ?? 'Fehler beim Laden des Archivs';
		} finally {
			loading = false;
		}
	});

	let visibleTrips = $derived(
		sortArchive(
			trips.filter((t) => t.name.toLowerCase().includes(search.toLowerCase())),
			sortMode
		)
	);

	/** Zeitraum aus Etappen-Daten (Muster wie Touren-Liste). */
	function dateRange(trip: Trip): string {
		const dates = (trip.stages ?? []).map((s) => s.date).filter((d): d is string => !!d).sort();
		if (!dates.length) return '–';
		if (dates.length === 1) return dates[0];
		return `${dates[0]} — ${dates[dates.length - 1]}`;
	}

	function stageLabel(trip: Trip): string {
		const n = trip.stages?.length ?? 0;
		return `${n} ${n === 1 ? 'Etappe' : 'Etappen'}`;
	}

	async function restoreTrip(trip: Trip) {
		actionError = null;
		restoringId = trip.id;
		try {
			await api.patch(`/api/trips/${trip.id}`, { archived: false });
			trips = trips.filter((t) => t.id !== trip.id);
		} catch (e: unknown) {
			actionError = (e as { error?: string })?.error ?? 'Fehler beim Wiederherstellen';
		} finally {
			restoringId = null;
		}
	}

	async function confirmDelete() {
		if (!deleteTarget) return;
		actionError = null;
		deleting = true;
		const target = deleteTarget;
		try {
			await api.del(`/api/trips/${target.id}`);
			trips = trips.filter((t) => t.id !== target.id);
			deleteTarget = null;
		} catch (e: unknown) {
			actionError = (e as { error?: string })?.error ?? 'Fehler beim Löschen';
		} finally {
			deleting = false;
		}
	}
</script>

<div class="space-y-4">
	<div>
		<Eyebrow>WORKSPACE · VERGANGENE TRIPS</Eyebrow>
		<h1 class="text-3xl font-semibold tracking-tight mt-1">Archiv</h1>
		<p class="text-sm text-muted-foreground mt-1">
			Abgeschlossene und archivierte Trips. Wiederherstellen holt einen Trip zurück in die aktive Liste.
		</p>
	</div>

	{#if loadError}
		<p class="text-sm text-destructive">{loadError}</p>
	{/if}
	{#if actionError}
		<p class="text-sm text-destructive">{actionError}</p>
	{/if}

	{#if loading}
		<div class="space-y-3">
			{#each Array(3) as _}
				<div class="h-14 w-full animate-pulse rounded-lg bg-muted"></div>
			{/each}
		</div>
	{:else if trips.length === 0}
		<EmptyState
			icon={ArchiveIcon}
			title="Noch keine archivierten Trips."
			description="Archivierte Trips erscheinen hier — du kannst sie jederzeit wiederherstellen."
		/>
	{:else}
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div class="relative max-w-[380px] flex-1 min-w-[200px]">
				<SearchIcon class="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
				<Input placeholder="Suchen..." class="pl-8 rounded-full" bind:value={search} />
			</div>
			<Segmented
				options={SORT_OPTIONS}
				selected={sortMode}
				onselect={(v) => (sortMode = v as ArchiveSortMode)}
			/>
		</div>

		<Card.Root>
			<Card.Content class="p-0">
				<ul class="divide-y divide-[var(--g-rule-soft)]">
					{#each visibleTrips as trip (trip.id)}
						<li class="flex items-center gap-3 px-4 py-3">
							<div class="flex min-w-0 flex-1 flex-col">
								<a
									href="/trips/{trip.id}"
									class="truncate font-medium hover:underline decoration-[var(--g-accent)] underline-offset-2"
								>{trip.name}</a>
								<span class="font-mono text-xs text-muted-foreground tabular-nums">
									{stageLabel(trip)} · {dateRange(trip)}
								</span>
							</div>
							<div class="flex shrink-0 items-center gap-2">
								<Btn
									variant="outline"
									size="sm"
									onclick={() => restoreTrip(trip)}
									disabled={restoringId === trip.id}
								>{restoringId === trip.id ? 'Wiederherstellen…' : 'Wiederherstellen'}</Btn>
								<Btn
									variant="ghost"
									size="sm"
									class="text-destructive"
									onclick={() => (deleteTarget = trip)}
								>Löschen</Btn>
							</div>
						</li>
					{/each}
				</ul>
			</Card.Content>
		</Card.Root>

		<p class="font-mono text-xs uppercase tracking-wide text-muted-foreground">
			{visibleTrips.length} von {trips.length} archivierte Trips
		</p>
	{/if}
</div>

<!-- Löschen-Bestätigung (endgültig, irreversibel) -->
<Dialog.Root
	open={deleteTarget !== null}
	onOpenChange={(open) => { if (!open) deleteTarget = null; }}
>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>Trip endgültig löschen</Dialog.Title>
			<Dialog.Description>
				Möchtest du "{deleteTarget?.name}" endgültig löschen? Diese Aktion ist irreversibel und kann
				nicht rückgängig gemacht werden.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Btn variant="outline" onclick={() => (deleteTarget = null)} disabled={deleting}>Abbrechen</Btn>
			<Btn variant="destructive" onclick={confirmDelete} disabled={deleting}>
				{deleting ? 'Löschen…' : 'Endgültig löschen'}
			</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
