<script lang="ts">
	import type { Trip } from '$lib/types.js';
	import { api } from '$lib/api.js';
	// Issue #1395 S3: PATCH /state laeuft am Trichter vorbei und veraendert die
	// Trip-Datei, ohne einen neuen Stempel zu liefern (S2 AC-15) — danach muss der
	// gemerkte Stand verworfen werden.
	import { discardEtag } from '$lib/etagRegistry';
	import { goto } from '$app/navigation';
	import { Btn, Input, Eyebrow, Stat, PageHeader } from '$lib/components/atoms';
	import { ConfirmDialog } from '$lib/components/molecules';
	import SendConfirmDialog from '$lib/components/molecules/SendConfirmDialog.svelte';
	import StatusFilterPills from '$lib/components/molecules/StatusFilterPills.svelte';
	import ListTable from '$lib/components/organisms/ListTable.svelte';
	import SubscriptionCard from '$lib/components/organisms/SubscriptionCard.svelte';
	import SubscriptionActionSheet from '$lib/components/mobile/SubscriptionActionSheet.svelte';
	import SearchIcon from '@lucide/svelte/icons/search';
	import { subscriptionActions, subscriptionLifecycle } from '$lib/components/shared/subscriptionActions';
	import { setPaused, deleteSubscription, sendSubscription } from '$lib/components/shared/subscriptionExec';
	import { tripStatus } from '$lib/utils/tripStatus';

	const now = new Date();

	let { data } = $props();

	let trips: Trip[] = $state(data.trips);
	let refetching = $state(false);
	// Issue #2278 AC-11: die Liste blendet Archiviertes aus (wie der Loader).
	async function refetchTrips() {
		refetching = true;
		try { trips = (await api.get<Trip[]>('/api/trips')).filter((t) => t.archived_at == null); }
		finally { refetching = false; }
	}
	let search = $state('');
	let filteredTrips = $derived(
		trips.filter(t => t.name.toLowerCase().includes(search.toLowerCase()))
	);
	let mobileFilter = $state<'all' | 'aktiv' | 'geplant' | 'pausiert' | 'fertig'>('all');
	let mobileFiltered = $derived(
		filteredTrips.filter(t => mobileFilter === 'all' || tripStatus(t, now) === mobileFilter)
	);
	let pillCounts = $derived({
		all: filteredTrips.length,
		aktiv: filteredTrips.filter(t => tripStatus(t, now) === 'aktiv').length,
		geplant: filteredTrips.filter(t => tripStatus(t, now) === 'geplant').length,
		pausiert: filteredTrips.filter(t => tripStatus(t, now) === 'pausiert').length,
		fertig: filteredTrips.filter(t => tripStatus(t, now) === 'fertig').length
	});
	let deleteTarget: Trip | null = $state(null);
	let sendTarget: Trip | null = $state(null);
	let sendInfo: string | null = $state(null);
	let error: string | null = $state(null);

	// Mobiles Aktionsblatt (Issue #268, #2278: geteilter Baustein)
	let actionTrip: Trip | null = $state(null);

	// Issue #1277 — Desktop-Übersicht über das geteilte ListTable-Organism.
	function tripDotColor(trip: Trip): string {
		const st = tripStatus(trip, now);
		if (st === 'aktiv') return 'var(--g-accent)';
		if (st === 'geplant') return '#3d6b3a';
		if (st === 'pausiert') return 'var(--g-warning)';
		if (st === 'fertig') return 'var(--g-ink-3)';
		return 'var(--g-ink-4)';
	}

	const tripColumns = [
		{
			key: 'name',
			header: 'Name',
			width: '1.6fr',
			render: (row: unknown) => {
				const t = row as Trip;
				return { nameCell: { name: t.name, statusLabel: tripStatus(t, now), dotColor: tripDotColor(t) } };
			}
		},
		{
			key: 'stages',
			header: 'Etappen',
			width: '0.8fr',
			render: (row: unknown) => {
				const n = (row as Trip).stages?.length ?? 0;
				return `${n} ${n === 1 ? 'Etappe' : 'Etappen'}`;
			}
		},
		{
			key: 'range',
			header: 'Zeitraum',
			width: '1.4fr',
			mono: true,
			render: (row: unknown) => dateRange(row as Trip)
		}
	];

	// "Briefing senden" oeffnet den Sende-Dialog (AC-3/AC-17: nie ohne Rueckfrage).
	function tripRowPrimary(row: unknown) {
		const t = row as Trip;
		return tripStatus(t, now) === 'aktiv'
			? { label: 'Briefing senden', onClick: () => (sendTarget = t) }
			: null;
	}

	// EIN Dispatch fuer Desktop-Zeilenmenue und mobiles Blatt (AC-1, AC-8, AC-16).
	function onTripAction(key: string, row: unknown) {
		const t = row as Trip;
		if (key === 'pause') void togglePause(t, true);
		else if (key === 'resume') void togglePause(t, false);
		else if (key === 'send') sendTarget = t;
		else if (key === 'alarms') goto(`/trips/${t.id}?tab=alarme`);
		else if (key === 'weather') goto(`/trips/${t.id}?tab=wetter-metriken`);
		else if (key === 'edit') goto(`/trips/${t.id}`);
		else if (key === 'continue-setup') goto(`/trips/${t.id}`);
		else if (key === 'delete') deleteTarget = t;
	}

	async function togglePause(trip: Trip, paused: boolean) {
		error = null;
		try {
			await setPaused('trip', trip.id, paused);
			discardEtag(trip.id);
			await refetchTrips();
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Fehler beim Pausieren';
		}
	}

	function dateRange(trip: Trip): string {
		if (!trip.stages?.length) return '-';
		const dates = (trip.stages?.map((s) => s.date) ?? []).sort();
		if (dates.length === 1) return dates[0];
		return `${dates[0]} — ${dates[dates.length - 1]}`;
	}

	async function handleDelete() {
		if (!deleteTarget) return;
		error = null;
		const target = deleteTarget;
		try {
			await deleteSubscription('trip', target.id);
			trips = trips.filter((t) => t.id !== target.id);
		} catch (e: unknown) {
			error = (e as Error)?.message ?? 'Fehler beim Löschen';
		}
		deleteTarget = null;
	}

	async function confirmSend(berichtsart: 'morning' | 'evening' | undefined) {
		if (!sendTarget) return;
		const target = sendTarget;
		sendTarget = null;
		error = null;
		sendInfo = null;
		// Issue #2124: geteilter Laufzustand (trip:<id>) + Klassifikation.
		const o = await sendSubscription('trip', target.id, { reportType: berichtsart });
		if (o.kind === 'ok') sendInfo = 'Briefing wurde versendet.';
		else error = o.message;
	}

	function openCreate() {
		goto('/trips/new');
	}

</script>

{#snippet neuerTripMobil()}
	<Btn href="/trips/new" variant="ghost" size="sm" data-testid="trip-list-new-mobile">+ Neuer Trip</Btn>
{/snippet}

<div class="space-y-4">
	<!-- Desktop-Kopf (≥900px unverändert). Steht im DOM VOR dem mobilen Kopf,
	     damit `h1`/Eyebrow-`.first()` auf Desktop das sichtbare Element trifft
	     (#2347 S4, Fix F003). -->
	<div class="hidden desktop:flex items-start justify-between gap-4">
		<div>
			<Eyebrow>WORKSPACE · TRIPS</Eyebrow>
			<h1 style="font-size: 32px; font-weight: 600; letter-spacing: -0.025em; margin-top: 4px;">Trips</h1>
			<p class="text-sm text-muted-foreground mt-1">Alle aktiven, geplanten und abgeschlossenen Mehrtages-Trips. Pro Trip kannst du Alerts justieren oder ein Briefing direkt schicken.</p>
		</div>
		<Btn variant="accent" onclick={() => goto('/trips/new')}>+ Neuer Trip</Btn>
	</div>

	<!-- Mobiler Seitenkopf (#2347 S4, HL-1/HL-2/HL-4): gleich gebaut wie die
	     Ortsvergleich-Liste (routes/compare/+page.svelte) — PageHeader mit
	     Eyebrow, Titel und „Neu"-Knopf, kurzer Intro-Satz, kompakte Stats. -->
	<div class="desktop:hidden">
		<PageHeader eyebrow="Workspace · {trips.length}" title="Trips" right={neuerTripMobil} compact />
		<div style="font-size: 13px; color: var(--g-ink-3); line-height: 1.5; margin: 14px 0">
			Mehrtages-Trips mit Briefings je Etappe — morgens für heute, abends für morgen.
		</div>
	</div>

	{#if trips.length > 0}
		{@const countAktiv = trips.filter(t => tripStatus(t, now) === 'aktiv').length}
		{@const countGeplant = trips.filter(t => tripStatus(t, now) === 'geplant').length}
		{@const countFertig = trips.filter(t => tripStatus(t, now) === 'fertig').length}
		{@const countDraft = trips.filter(t => tripStatus(t, now) === 'draft').length}
		<div class="hidden desktop:flex" style="gap: 24px; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--g-rule-soft);">
			<Stat label="Aktiv"        value={countAktiv}   layout="inline" tone="accent" />
			<Stat label="Geplant"      value={countGeplant} layout="inline" />
			<Stat label="Abgeschlossen" value={countFertig} layout="inline" />
			<Stat label="Drafts"       value={countDraft}   layout="inline" />
		</div>
		<!-- Mobile Stats (kompakt, size="sm" wie im Vergleich), vor den Filter-Pillen -->
		<div class="flex desktop:hidden" style="gap: 20px; padding: 4px 2px 16px; border-bottom: 1px solid var(--g-rule-soft); flex-wrap: wrap;">
			<Stat label="Aktiv"        value={countAktiv}   layout="inline" size="sm" tone="accent" />
			<Stat label="Geplant"      value={countGeplant} layout="inline" size="sm" />
			<Stat label="Abgeschlossen" value={countFertig} layout="inline" size="sm" />
			<Stat label="Drafts"       value={countDraft}   layout="inline" size="sm" />
		</div>
	{/if}

	{#if sendInfo}
		<p class="text-sm" style="color: var(--g-accent)" data-testid="trips-send-info">{sendInfo}</p>
	{/if}

	{#if error}
		<p class="text-sm text-destructive" data-testid="trips-error">{error}</p>
	{/if}

	{#if trips.length === 0}
		<div class="flex flex-col items-center gap-3 py-12">
			<Eyebrow>Noch keine Trips</Eyebrow>
			<p class="text-sm text-muted-foreground mt-1">Erstelle deinen ersten Trip, um Briefings zu erhalten.</p>
			<Btn onclick={openCreate} variant="primary">Neuer Trip</Btn>
		</div>
	{:else}
		<!-- Suche nur Desktop (#2347 S4, HL-3; wie die Ortsvergleich-Liste).
		     Äußerer Rahmen `hidden desktop:flex` (nicht `desktop:block`): das
		     Desktop-Raster bleibt das EINZIGE Element mit `.hidden.desktop:block`,
		     auf das issue-486-trips-overflow.spec.ts strikt zielt (Fix F001). -->
		<div class="hidden desktop:flex mb-3">
			<div class="relative w-full max-w-[380px]">
				<SearchIcon class="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
				<Input placeholder="Suchen..." class="pl-8 rounded-full" bind:value={search} />
			</div>
		</div>
		{#if refetching}
			<div class="space-y-3">
				{#each Array(3) as _}
					<div class="h-12 w-full animate-pulse rounded-lg bg-muted"></div>
				{/each}
			</div>
		{:else}
		<!-- Mobile Filter-Pills (Issue #413, #2278: geteilter Baustein) -->
		<div class="desktop:hidden">
			<StatusFilterPills active={mobileFilter} counts={pillCounts} onSelect={(v) => { mobileFilter = v; }} />
		</div>
		<!-- Mobile Card-Stack (Issue #268 + #413, #2278: geteilte Karte) -->
		<div data-testid="trip-card-stack" class="desktop:hidden flex flex-col gap-2">
			{#each mobileFiltered as trip (trip.id)}
				<SubscriptionCard
					kind="trip"
					sub={trip}
					{now}
					dense
					onclick={() => goto(`/trips/${trip.id}`)}
					onAction={() => { actionTrip = trip; }}
				/>
			{/each}
		</div>
		<!-- Desktop-Übersicht über das geteilte ListTable-Organism (Issue #1277) -->
		<div class="hidden desktop:block">
			<ListTable
				columns={tripColumns}
				rows={filteredTrips}
				getRowId={(row) => (row as Trip).id}
				onRowClick={(row) => goto(`/trips/${(row as Trip).id}`)}
				rowActions={(row) =>
					subscriptionActions('trip', subscriptionLifecycle('trip', row as Trip, now), 'list').map((a) => ({
						key: a.id,
						label: a.label,
						danger: a.danger,
						testid: a.id === 'edit' ? 'trip-edit-btn' : undefined
					}))}
				rowPrimary={tripRowPrimary}
				onAction={onTripAction}
				emptyText={`Keine Trips für »${search}« gefunden.`}
				rowTestid={(row) => `trip-row-${(row as Trip).id}`}
				menuTestid={() => 'trip-row-menu-btn'}
			/>
			<div style="margin-top: 14px; font-size: 11px; color: var(--g-ink-4); font-family: var(--g-font-mono); letter-spacing: 0.06em;">
				{filteredTrips.length} von {trips.length} Trips
			</div>
		</div>
		{/if}
	{/if}
</div>

<ConfirmDialog
	open={deleteTarget !== null}
	title="Trip löschen"
	description="Diese Aktion kann nicht rückgängig gemacht werden."
	confirmLabel="Löschen"
	confirmVariant="destructive"
	onConfirm={handleDelete}
	onCancel={() => (deleteTarget = null)}
	onOpenChange={(o) => { if (!o) deleteTarget = null; }}
/>

<SendConfirmDialog
	open={sendTarget !== null}
	kind="trip"
	profile={data.profile}
	subscription={sendTarget}
	onConfirm={confirmSend}
	onCancel={() => (sendTarget = null)}
/>

<SubscriptionActionSheet
	open={actionTrip !== null}
	onClose={() => (actionTrip = null)}
	kind="trip"
	status={actionTrip ? subscriptionLifecycle('trip', actionTrip, now) : 'active'}
	name={actionTrip?.name}
	onAction={(id) => { if (actionTrip) onTripAction(id, actionTrip); }}
/>
