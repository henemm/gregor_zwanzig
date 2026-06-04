<script lang="ts">
	import type { Trip } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { goto } from '$app/navigation';
	import { Btn, Input, Dot, Eyebrow, Pill } from '$lib/components/atoms';
	import { ConfirmDialog, ReportConfigDialog, TestReportDialog } from '$lib/components/molecules';
	import { DropdownMenu } from 'bits-ui';
	import SearchIcon from '@lucide/svelte/icons/search';
	import BellIcon from '@lucide/svelte/icons/bell';
	import CloudSunIcon from '@lucide/svelte/icons/cloud-sun';
	import PlayIcon from '@lucide/svelte/icons/play';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import EllipsisVerticalIcon from '@lucide/svelte/icons/ellipsis-vertical';
	import SendIcon from '@lucide/svelte/icons/send';
	import { deriveTripStatus, tripStatus, type HomeTripStatus } from '$lib/utils/tripStatus';

	const now = new Date();

	let { data } = $props();

	let trips: Trip[] = $state(data.trips);
	let refetching = $state(false);
	async function refetchTrips() {
		refetching = true;
		try { trips = await api.get<Trip[]>('/api/trips'); }
		finally { refetching = false; }
	}
	let search = $state('');
	let filteredTrips = $derived(
		trips.filter(t => t.name.toLowerCase().includes(search.toLowerCase()))
	);
	let mobileFilter = $state<'all' | HomeTripStatus>('all');
	let mobileFiltered = $derived(
		filteredTrips.filter(t => mobileFilter === 'all' || tripStatus(t, now) === mobileFilter)
	);
	let deleteTarget: Trip | null = $state(null);
	let archiveTarget: Trip | null = $state(null);
	let error: string | null = $state(null);

	// Report Config Dialog
	let reportConfigTarget: Trip | null = $state(null);
	let reportConfigLoading = $state(false);
	let reportConfigSaving = $state(false);
	let reportConfigError: string | null = $state(null);
	let reportConfig = $state({
		morning_time: '07:00:00',
		evening_time: '18:00:00',
		enabled: true,
		send_email: true,
		send_sms: false,
		send_signal: false,
		send_telegram: false,
		alert_on_changes: true,
		change_threshold_temp_c: 5,
		change_threshold_wind_kmh: 20,
		change_threshold_precip_mm: 10,
		show_compact_summary: true,
		show_daylight: true,
		wind_exposition_min_elevation_m: null as number | null,
		multi_day_trend_reports: ['evening'] as string[]
	});

	// Test Report
	let testReportTarget: Trip | null = $state(null);
	let testReportHour: 7 | 18 | null = $state(null);
	let testReportRunning = $state(false);
	let testReportResult: string | null = $state(null);
	let testReportError: string | null = $state(null);

	// Mobile Action Sheet (Issue #268)
	let sheetTrip: Trip | null = $state(null);

	let primaryActionLoading: string | null = $state(null);

	function statusTone(trip: Trip): 'success' | 'info' | 'warning' | 'danger' {
		const status = deriveTripStatus(trip, now);
		if (status === 'active') return 'success';
		if (status === 'planned') return 'info';
		if (status === 'paused') return 'warning';
		return 'danger';
	}

	function primaryLabel(trip: Trip): string {
		const s = tripStatus(trip, now);
		if (s === 'aktiv' || s === 'geplant') return 'Briefing-Vorschau';
		if (s === 'draft') return 'Fertigstellen';
		return trip.archived_at ? 'Dearchivieren' : 'Archivieren';
	}

	async function handlePrimaryAction(trip: Trip) {
		const s = tripStatus(trip, now);
		if (s === 'aktiv' || s === 'geplant') {
			goto(`/trips/${trip.id}?tab=preview`);
			return;
		}
		if (s === 'draft') {
			goto(`/trips/${trip.id}/wizard`);
			return;
		}
		if (!trip.archived_at) {
			archiveTarget = trip;
			return;
		}
		primaryActionLoading = trip.id;
		try {
			const res = await fetch(`/api/trips/${trip.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ archived: false })
			});
			if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
			await refetchTrips();
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Fehler beim Statuswechsel';
		} finally {
			primaryActionLoading = null;
		}
	}

	async function handleArchive() {
		if (!archiveTarget) return;
		primaryActionLoading = archiveTarget.id;
		try {
			const res = await fetch(`/api/trips/${archiveTarget.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ archived: true })
			});
			if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
			archiveTarget = null;
			await refetchTrips();
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Fehler beim Archivieren';
		} finally {
			primaryActionLoading = null;
		}
	}

	async function handlePauseToggle(trip: Trip) {
		try {
			const res = await fetch(`/api/trips/${trip.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ paused: !trip.paused_at })
			});
			if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
			await refetchTrips();
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Fehler beim Pausieren';
		}
	}

	function dateRange(trip: Trip): string {
		if (!trip.stages.length) return '-';
		const dates = trip.stages.map((s) => s.date).sort();
		if (dates.length === 1) return dates[0];
		return `${dates[0]} — ${dates[dates.length - 1]}`;
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
		goto('/trips/new');
	}

	function openEdit(trip: Trip) {
		goto(`/trips/${trip.id}/edit`);
	}

	async function openReportConfig(trip: Trip) {
		reportConfigTarget = trip;
		reportConfigError = null;
		reportConfigLoading = true;
		try {
			const full = await api.get<Trip>(`/api/trips/${trip.id}`);
			if (full.report_config) {
				const rc = full.report_config as typeof reportConfig;
				reportConfig = {
					morning_time: rc.morning_time ?? '07:00:00',
					evening_time: rc.evening_time ?? '18:00:00',
					enabled: rc.enabled ?? true,
					send_email: rc.send_email ?? true,
					send_sms: rc.send_sms ?? false,
					send_signal: rc.send_signal ?? false,
					send_telegram: rc.send_telegram ?? false,
					alert_on_changes: rc.alert_on_changes ?? true,
					change_threshold_temp_c: rc.change_threshold_temp_c ?? 5,
					change_threshold_wind_kmh: rc.change_threshold_wind_kmh ?? 20,
					change_threshold_precip_mm: rc.change_threshold_precip_mm ?? 10,
					show_compact_summary: rc.show_compact_summary ?? true,
					show_daylight: rc.show_daylight ?? true,
					wind_exposition_min_elevation_m: rc.wind_exposition_min_elevation_m ?? null,
					multi_day_trend_reports: rc.multi_day_trend_reports ?? ['evening']
				};
			} else {
				reportConfig = {
					morning_time: '07:00:00',
					evening_time: '18:00:00',
					enabled: true,
					send_email: true,
					send_sms: false,
					send_signal: false,
					send_telegram: false,
					alert_on_changes: true,
					change_threshold_temp_c: 5,
					change_threshold_wind_kmh: 20,
					change_threshold_precip_mm: 10,
					show_compact_summary: true,
					show_daylight: true,
					wind_exposition_min_elevation_m: null as number | null,
					multi_day_trend_reports: ['evening'] as string[]
				};
			}
		} catch (e: unknown) {
			reportConfigError = (e as { error?: string })?.error ?? 'Fehler beim Laden';
		} finally {
			reportConfigLoading = false;
		}
	}

	async function saveReportConfig() {
		if (!reportConfigTarget) return;
		reportConfigSaving = true;
		reportConfigError = null;
		try {
			const full = await api.get<Trip>(`/api/trips/${reportConfigTarget.id}`);
			await api.put<Trip>(`/api/trips/${reportConfigTarget.id}`, {
				...full,
				report_config: reportConfig
			});
			await refetchTrips();
			reportConfigTarget = null;
		} catch (e: unknown) {
			reportConfigError = (e as { error?: string; detail?: string })?.detail
				?? (e as { error?: string })?.error
				?? 'Fehler beim Speichern';
		} finally {
			reportConfigSaving = false;
		}
	}

	async function runTestReport(trip: Trip, hour: 7 | 18) {
		testReportTarget = trip;
		testReportHour = hour;
		testReportRunning = true;
		testReportResult = null;
		testReportError = null;
		try {
			await api.post(`/api/scheduler/trip-reports?hour=${hour}`, {});
			testReportResult = `Test-Report (${hour === 7 ? 'Morning' : 'Evening'}) wurde ausgelöst. Alle aktiven Trips für ${hour}:00 Uhr werden verarbeitet.`;
		} catch (e: unknown) {
			testReportError = (e as { error?: string; detail?: string })?.detail
				?? (e as { error?: string })?.error
				?? 'Fehler beim Auslösen des Test-Reports';
		} finally {
			testReportRunning = false;
		}
	}

</script>

<div class="space-y-4">
	<div class="flex items-start justify-between gap-4">
		<div>
			<Eyebrow>WORKSPACE · TRIPS</Eyebrow>
			<h1 class="text-3xl font-semibold tracking-tight mt-1">Meine Trips</h1>
			<p class="text-sm text-muted-foreground mt-1">Alle Trips auf einen Blick — Status, Zeitraum und Aktionen.</p>
		</div>
		<Btn variant="accent" onclick={() => goto('/trips/new')}>+ Neuer Trip</Btn>
	</div>

	{#if trips.length > 0}
		<div class="hidden desktop:flex items-center gap-6 pb-3 border-b border-muted">
			{#each [
				{ label: 'Aktiv',         status: 'aktiv'   as const },
				{ label: 'Geplant',       status: 'geplant' as const },
				{ label: 'Abgeschlossen', status: 'fertig'  as const },
				{ label: 'Drafts',        status: 'draft'   as const },
			] as stat (stat.status)}
				{@const count = trips.filter(t => tripStatus(t, now) === stat.status).length}
				<div class="flex items-center gap-2">
					<span style="font-size:22px;font-weight:700;color:var(--g-accent);line-height:1">{count}</span>
					<span style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--g-ink-muted)">{stat.label}</span>
				</div>
			{/each}
		</div>
	{/if}

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	{#if trips.length === 0}
		<div class="flex flex-col items-center gap-3 py-12">
			<Eyebrow>Noch keine Trips</Eyebrow>
			<p class="text-sm text-muted-foreground mt-1">Erstelle deinen ersten Trip, um Briefings zu erhalten.</p>
			<Btn onclick={openCreate} variant="primary">Neuer Trip</Btn>
		</div>
	{:else}
		<div class="relative mb-3 max-w-[380px]">
			<SearchIcon class="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
			<Input placeholder="Suchen..." class="pl-8 rounded-full" bind:value={search} />
		</div>
		{#if refetching}
			<div class="space-y-3">
				{#each Array(3) as _}
					<div class="h-12 w-full animate-pulse rounded-lg bg-muted"></div>
				{/each}
			</div>
		{:else}
		<!-- Mobile Filter-Pills (Issue #413) -->
		<div class="desktop:hidden flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
			{#each [
				{ label: 'Alle',    value: 'all'     as const, count: filteredTrips.length },
				{ label: 'Aktiv',   value: 'aktiv'   as const, count: filteredTrips.filter(t => tripStatus(t, now) === 'aktiv').length },
				{ label: 'Geplant', value: 'geplant' as const, count: filteredTrips.filter(t => tripStatus(t, now) === 'geplant').length },
				{ label: 'Fertig',  value: 'fertig'  as const, count: filteredTrips.filter(t => tripStatus(t, now) === 'fertig').length },
			] as f (f.value)}
				<button
					class="shrink-0 cursor-pointer"
					aria-pressed={mobileFilter === f.value}
					onclick={() => { mobileFilter = f.value; }}
				>
					<Pill tone={mobileFilter === f.value ? 'accent' : 'default'}>
						{f.label} ({f.count})
					</Pill>
				</button>
			{/each}
		</div>
		<!-- Mobile Card-Stack (Issue #268 + #413) -->
		<div data-testid="trip-card-stack" class="desktop:hidden flex flex-col gap-2">
			{#each mobileFiltered as trip (trip.id)}
				<div data-testid="trip-card" data-slot="g-card" class="flex flex-col px-3 py-2">
					<div class="flex items-center gap-3">
						<Dot tone={statusTone(trip)} size="sm" class="shrink-0" />
						<button
							data-testid="trip-card-content-btn"
							class="flex-1 flex flex-col items-start text-left min-h-[44px] justify-center min-w-0"
							onclick={() => goto(`/trips/${trip.id}`)}
						>
							<span class="font-medium text-sm truncate w-full">
								{trip.name}
								<span class="text-[10px] font-normal tracking-wider uppercase text-muted-foreground ml-1">· {tripStatus(trip, now)}</span>
							</span>
							{#if trip.region}
								<span class="text-xs text-muted-foreground truncate w-full">{trip.region}</span>
							{/if}
							<span class="text-xs text-muted-foreground truncate w-full">
								{trip.stages.length} Etappen · {dateRange(trip)}
							</span>
						</button>
						<button
							data-testid="trip-card-menu-btn"
							class="shrink-0 flex items-center justify-center min-h-[44px] min-w-[44px] rounded-lg -mr-1 hover:bg-muted/60 transition-colors"
							onclick={(e) => { e.stopPropagation(); sheetTrip = trip; }}
							aria-label="Aktionen für {trip.name}"
						>
							<EllipsisVerticalIcon class="size-5" />
						</button>
					</div>
				</div>
			{/each}
		</div>
		<div class="hidden desktop:block overflow-x-auto -mx-4 px-4 desktop:mx-0 desktop:px-0">
		<table class="w-full caption-bottom text-sm">
			<thead class="[&_tr]:border-b">
				<tr class="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
					<th class="h-10 px-2 text-left align-middle font-medium text-muted-foreground">Name</th>
					<th class="h-10 px-2 text-left align-middle font-medium text-muted-foreground hidden sm:table-cell">Zeitraum</th>
					<th class="h-10 px-2 text-right align-middle font-medium text-muted-foreground">Aktionen</th>
				</tr>
			</thead>
			<tbody class="[&_tr:last-child]:border-0">
				{#each filteredTrips as trip}
					<tr onclick={function() { goto(`/trips/${trip.id}`); }} class="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted cursor-pointer">
						<td class="p-2 align-middle">
							<div class="flex flex-col min-w-0">
								<div class="flex items-baseline gap-0">
									<a href="/trips/{trip.id}" class="trip-link font-medium truncate hover:underline decoration-[var(--g-accent)] underline-offset-2">
										{trip.name}
									</a><span class="status-caption font-mono text-[9px] uppercase tracking-widest text-[var(--g-ink-4)] ml-1.5">· {tripStatus(trip, now)}</span>
								</div>
								<span class="font-mono text-xs text-muted-foreground tabular-nums">
									{trip.stages?.length ?? 0} Etappen
								</span>
							</div>
						</td>
						<td class="p-2 align-middle hidden sm:table-cell font-mono tabular-nums text-sm text-muted-foreground">
							{dateRange(trip)}
						</td>
						<td class="p-2 align-middle text-right" onclick={(e) => e.stopPropagation()}>
							<div class="inline-flex items-center gap-2">
								<Btn
									variant="outline"
									size="sm"
									onclick={() => handlePrimaryAction(trip)}
									disabled={primaryActionLoading === trip.id}
								>{primaryLabel(trip)}</Btn>
								<DropdownMenu.Root>
									<DropdownMenu.Trigger>
										{#snippet child({ props })}
											<Btn
												{...props}
												variant="ghost"
												size="icon-sm"
												title="Weitere Aktionen"
												aria-label="Weitere Aktionen"
											>⋯</Btn>
										{/snippet}
									</DropdownMenu.Trigger>
									<DropdownMenu.Content
										align="end"
										sideOffset={4}
										class="z-50 min-w-[200px] rounded-md border bg-popover shadow-md py-1"
									>
										<DropdownMenu.Item
											data-testid="trip-edit-btn"
											class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted cursor-default outline-none"
											onSelect={() => openEdit(trip)}
										>Bearbeiten</DropdownMenu.Item>
										<DropdownMenu.Item
											class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted cursor-default outline-none"
											onSelect={() => handlePauseToggle(trip)}
										>{trip.paused_at ? 'Reaktivieren' : 'Pausieren'}</DropdownMenu.Item>
										<DropdownMenu.Item
											class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted cursor-default outline-none"
											onSelect={() => runTestReport(trip, 7)}
										>Test-Briefing Morgen</DropdownMenu.Item>
										<DropdownMenu.Item
											class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted cursor-default outline-none"
											onSelect={() => runTestReport(trip, 18)}
										>Test-Briefing Abend</DropdownMenu.Item>
										<DropdownMenu.Item
											class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted cursor-default outline-none"
											onSelect={() => goto(`/trips/${trip.id}#weather`)}
										>Wetter-Konfiguration</DropdownMenu.Item>
										<DropdownMenu.Item
											class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted cursor-default outline-none"
											onSelect={() => openReportConfig(trip)}
										>Alerts justieren</DropdownMenu.Item>
										<DropdownMenu.Separator class="my-1 h-px bg-border" />
										<DropdownMenu.Item
											class="w-full text-left px-3 py-1.5 text-sm text-destructive hover:bg-muted cursor-default outline-none"
											onSelect={() => { deleteTarget = trip; }}
										>Löschen</DropdownMenu.Item>
									</DropdownMenu.Content>
								</DropdownMenu.Root>
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="hidden desktop:block mt-2">
			<span class="font-mono text-xs uppercase tracking-widest">
				{filteredTrips.length} Trips · {trips.length - filteredTrips.length} versteckt
			</span>
		</p>
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

<ConfirmDialog
	open={archiveTarget !== null}
	title="Trip archivieren?"
	description="Archivierte Trips erhalten keine Briefings mehr."
	confirmLabel="Archivieren"
	onConfirm={handleArchive}
	onCancel={() => (archiveTarget = null)}
	onOpenChange={(o) => { if (!o) archiveTarget = null; }}
/>

<ReportConfigDialog
	open={reportConfigTarget !== null}
	trip={reportConfigTarget}
	bind:config={reportConfig}
	loading={reportConfigLoading}
	saving={reportConfigSaving}
	error={reportConfigError}
	onSave={saveReportConfig}
	onClose={() => (reportConfigTarget = null)}
/>

<TestReportDialog
	open={testReportTarget !== null}
	hour={testReportHour}
	running={testReportRunning}
	result={testReportResult}
	error={testReportError}
	onClose={() => { testReportTarget = null; testReportResult = null; testReportError = null; }}
/>

<!-- Bottom-Sheet Backdrop + Panel (Issue #268) -->
{#if sheetTrip !== null}
	<div
		class="fixed inset-0 z-[70] bg-black/50 desktop:hidden"
		onclick={() => (sheetTrip = null)}
		role="presentation"
	></div>
	<div
		data-testid="trip-action-sheet"
		class="fixed bottom-0 left-0 right-0 z-[75] desktop:hidden rounded-t-2xl border-t"
		style="background: var(--g-paper-deep); border-color: var(--g-rule-soft); padding-bottom: env(safe-area-inset-bottom);"
		role="dialog"
		aria-modal="true"
		aria-label="Aktionen"
	>
	<div class="flex justify-center pt-3 pb-1">
		<div class="w-10 h-1 rounded-full bg-muted-foreground/25"></div>
	</div>
	<div class="px-4 py-2 text-sm font-semibold truncate">{sheetTrip?.name ?? ''}</div>
	<div class="h-px mx-4 bg-border"></div>
	<div class="py-2">
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; goto(`/trips/${t.id}?tab=preview`); }}>
			<SendIcon class="size-4 text-muted-foreground shrink-0" /> Briefing senden
		</button>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; openReportConfig(t); }}>
			<BellIcon class="size-4 text-muted-foreground shrink-0" /> Alerts justieren
		</button>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; goto(`/trips/${t.id}#weather`); }}>
			<CloudSunIcon class="size-4 text-muted-foreground shrink-0" /> Wetter-Konfiguration
		</button>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; openEdit(t); }}>
			<PencilIcon class="size-4 text-muted-foreground shrink-0" /> Bearbeiten
		</button>
		<div class="h-px mx-4 bg-border"></div>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; runTestReport(t, 7); }}>
			<PlayIcon class="size-4 text-muted-foreground shrink-0" /> Test Morgen-Report
		</button>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; runTestReport(t, 18); }}>
			<PlayIcon class="size-4 text-muted-foreground shrink-0" /> Test Abend-Report
		</button>
		<div class="h-px mx-4 bg-border"></div>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm text-destructive hover:bg-destructive/10 active:bg-destructive/15"
			onclick={() => { const t = sheetTrip!; sheetTrip = null; deleteTarget = t; }}>
			<Trash2Icon class="size-4 shrink-0" /> Löschen
		</button>
	</div>
	<div class="h-2"></div>
	</div>
{/if}
