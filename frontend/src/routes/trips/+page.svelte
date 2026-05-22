<script lang="ts">
	import type { Trip } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { goto } from '$app/navigation';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import WeatherConfigDialog from '$lib/components/WeatherConfigDialog.svelte';
	import SearchIcon from '@lucide/svelte/icons/search';
	import RouteIcon from '@lucide/svelte/icons/route';
	import BellIcon from '@lucide/svelte/icons/bell';
	import CloudSunIcon from '@lucide/svelte/icons/cloud-sun';
	import PlayIcon from '@lucide/svelte/icons/play';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import EllipsisVerticalIcon from '@lucide/svelte/icons/ellipsis-vertical';
	import { Dot } from '$lib/components/ui/dot';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Select } from '$lib/components/ui/select';
	import { Eyebrow } from '$lib/components/ui/eyebrow/index.js';
	import { deriveTripStatus } from '$lib/utils/tripStatus';

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
	let deleteTarget: Trip | null = $state(null);
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

	// Weather Config Dialog
	let weatherConfigTarget: Trip | null = $state(null);

	// Test Report
	let testReportTarget: Trip | null = $state(null);
	let testReportHour: 7 | 18 | null = $state(null);
	let testReportRunning = $state(false);
	let testReportResult: string | null = $state(null);
	let testReportError: string | null = $state(null);

	// Mobile Action Sheet (Issue #268)
	let sheetTrip: Trip | null = $state(null);

	// Bug #295: Kebab-Menü State
	let kebabOpenId: string | null = $state(null);
	let primaryActionLoading: string | null = $state(null);

	function statusTone(trip: Trip): 'success' | 'info' | 'warning' | 'danger' {
		const status = deriveTripStatus(trip, now);
		if (status === 'active') return 'success';
		if (status === 'planned') return 'info';
		if (status === 'paused') return 'warning';
		return 'danger';
	}

	function primaryLabel(trip: Trip): string {
		const s = deriveTripStatus(trip, now);
		if (s === 'active' || s === 'planned') return 'Briefing-Vorschau';
		if (s === 'paused') return 'Reaktivieren';
		return 'Dearchivieren';
	}

	async function handlePrimaryAction(trip: Trip) {
		const s = deriveTripStatus(trip, now);
		if (s === 'active' || s === 'planned') {
			goto(`/trips/${trip.id}#preview`);
			return;
		}
		primaryActionLoading = trip.id;
		try {
			const res = await fetch(`/api/trips/${trip.id}/state`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(s === 'paused' ? { paused: false } : { archived: false })
			});
			if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
			await refetchTrips();
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Fehler beim Statuswechsel';
		} finally {
			primaryActionLoading = null;
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

	function getHour(timeStr: string): number {
		return parseInt(timeStr.split(':')[0], 10);
	}

	function setHour(timeStr: string, hour: number): string {
		const parts = timeStr.split(':');
		parts[0] = String(hour).padStart(2, '0');
		return parts.join(':');
	}

	async function runTestReport(trip: Trip, hour: 7 | 18) {
		testReportTarget = trip;
		testReportHour = hour;
		testReportRunning = true;
		testReportResult = null;
		testReportError = null;
		try {
			await api.post(`/api/scheduler/trip-reports?hour=${hour}`, {});
			testReportResult = `Test-Report (${hour === 7 ? 'Morning' : 'Evening'}) wurde ausgelöst. Alle aktiven Touren für ${hour}:00 Uhr werden verarbeitet.`;
		} catch (e: unknown) {
			testReportError = (e as { error?: string; detail?: string })?.detail
				?? (e as { error?: string })?.error
				?? 'Fehler beim Auslösen des Test-Reports';
		} finally {
			testReportRunning = false;
		}
	}

	async function handleWeatherSave(config: Record<string, unknown>) {
		if (!weatherConfigTarget) return;
		error = null;
		try {
			await api.put(`/api/trips/${weatherConfigTarget.id}/weather-config`, config);
			await refetchTrips();
			weatherConfigTarget = null;
		} catch (e: unknown) {
			error = (e as { error?: string; detail?: string })?.detail
				?? (e as { error?: string })?.error
				?? 'Fehler beim Speichern der Wetter-Konfiguration';
		}
	}
</script>

<svelte:window
	onkeydown={(e: KeyboardEvent) => {
		if (e.key === 'Escape' && kebabOpenId !== null) kebabOpenId = null;
	}}
/>

<div class="space-y-4">
	<div class="flex items-start justify-between gap-4">
		<div>
			<Eyebrow>WORKSPACE · TOUREN</Eyebrow>
			<h1 class="text-3xl font-semibold tracking-tight mt-1">Meine Touren</h1>
			<p class="text-sm text-muted-foreground mt-1">Alle Touren auf einen Blick — Status, Zeitraum und Aktionen.</p>
		</div>
		<Btn variant="accent" onclick={() => goto('/trips/new')}>+ Neue Tour</Btn>
	</div>

	{#if trips.length > 0}
		<div class="hidden desktop:flex items-center gap-6 pb-3 border-b border-muted">
			{#each [
				{ label: 'Aktiv',      status: 'active',   tone: 'success' as const },
				{ label: 'Geplant',    status: 'planned',  tone: 'info'    as const },
				{ label: 'Pausiert',   status: 'paused',   tone: 'warning' as const },
				{ label: 'Archiviert', status: 'archived', tone: 'danger'  as const },
			] as stat}
				{@const count = trips.filter(t => deriveTripStatus(t, now) === stat.status).length}
				<div class="flex items-center gap-1.5 text-sm">
					<Dot tone={stat.tone} size="sm" />
					<span class="font-mono tabular-nums">{count}</span>
					<div class="text-muted-foreground">{stat.label}</div>
				</div>
			{/each}
		</div>
	{/if}

	{#if error}
		<p class="text-sm text-destructive">{error}</p>
	{/if}

	{#if trips.length === 0}
		<div data-testid="empty-state" class="rounded-lg border border-dashed p-10 text-center">
			<RouteIcon class="mx-auto mb-3 size-10 text-muted-foreground/40" />
			<p class="font-medium">Noch keine Tour.</p>
			<p class="mt-1 text-sm text-muted-foreground">Lege deine erste Tour an — Wizard in 4 Schritten.</p>
			<Btn variant="outline" class="mt-4" onclick={() => goto('/trips/new')}>+ Neue Tour</Btn>
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
		<!-- Mobile Card-Stack (Issue #268) -->
		<div data-testid="trip-card-stack" class="desktop:hidden flex flex-col gap-2">
			{#each filteredTrips as trip (trip.id)}
				<div data-testid="trip-card" data-slot="g-card" class="flex items-center gap-3 px-3 py-2">
					<Dot tone={statusTone(trip)} size="sm" class="shrink-0" />
					<button
						data-testid="trip-card-content-btn"
						class="flex-1 flex flex-col items-start text-left min-h-[44px] justify-center min-w-0"
						onclick={() => goto(`/trips/${trip.id}`)}
					>
						<span class="font-medium text-sm truncate w-full">{trip.name}</span>
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
			{/each}
		</div>
		<div class="hidden desktop:block overflow-x-auto -mx-4 px-4 desktop:mx-0 desktop:px-0">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head>Name</Table.Head>
					<Table.Head class="hidden sm:table-cell">Zeitraum</Table.Head>
					<Table.Head class="text-right">Aktionen</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each filteredTrips as trip}
					<Table.Row>
						<Table.Cell>
							<div class="flex flex-col min-w-0">
								<a href="/trips/{trip.id}" class="font-medium truncate hover:underline decoration-[var(--g-accent)] underline-offset-2">
									{trip.name}
								</a>
								<span class="font-mono text-xs text-muted-foreground tabular-nums">
									{trip.stages?.length ?? 0} Etappen
								</span>
							</div>
						</Table.Cell>
						<Table.Cell class="hidden sm:table-cell font-mono tabular-nums text-sm text-muted-foreground">
							{dateRange(trip)}
						</Table.Cell>
						<Table.Cell class="text-right">
							<div class="inline-flex items-center gap-2">
								<Btn
									variant="outline"
									size="sm"
									onclick={() => handlePrimaryAction(trip)}
									disabled={primaryActionLoading === trip.id}
								>{primaryLabel(trip)}</Btn>
								<div class="relative">
									<Btn
										variant="ghost"
										size="icon-sm"
										title="Weitere Aktionen"
										aria-label="Weitere Aktionen"
										onclick={(e: MouseEvent) => {
											e.stopPropagation();
											kebabOpenId = kebabOpenId === trip.id ? null : trip.id;
										}}
									>⋯</Btn>
									{#if kebabOpenId === trip.id}
										<div
											role="menu"
											class="absolute right-0 top-full mt-1 z-50 min-w-[200px] rounded-md border bg-popover shadow-md py-1"
											tabindex="-1"
											onkeydown={(e: KeyboardEvent) => { if (e.key === 'Escape') kebabOpenId = null; }}
											onfocusout={(e: FocusEvent) => {
												if (!(e.currentTarget as Element).contains(e.relatedTarget as Node)) {
													kebabOpenId = null;
												}
											}}
										>
											<button
												data-testid="trip-edit-btn"
												class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
												onclick={() => { kebabOpenId = null; openEdit(trip); }}
											>Bearbeiten</button>
											<button
												class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
												onclick={() => { kebabOpenId = null; runTestReport(trip, 7); }}
											>Test-Briefing Morgen</button>
											<button
												class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
												onclick={() => { kebabOpenId = null; runTestReport(trip, 18); }}
											>Test-Briefing Abend</button>
											<button
												class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
												onclick={() => { kebabOpenId = null; weatherConfigTarget = trip; }}
											>Wetter-Konfiguration</button>
											<button
												class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
												onclick={() => { kebabOpenId = null; openReportConfig(trip); }}
											>Report-Konfiguration</button>
											<hr class="my-1 border-border" />
											<button
												class="w-full text-left px-3 py-1.5 text-sm text-destructive hover:bg-muted"
												onclick={() => { kebabOpenId = null; deleteTarget = trip; }}
											>Löschen</button>
										</div>
									{/if}
								</div>
							</div>
						</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
		<p class="hidden desktop:block mt-2 font-mono text-xs uppercase tracking-wide text-muted-foreground">
			{filteredTrips.length} von {trips.length} Touren
		</p>
		</div>
		{/if}
	{/if}
</div>

<!-- Delete Confirmation Dialog -->
<Dialog.Root
	open={deleteTarget !== null}
	onOpenChange={(open) => { if (!open) deleteTarget = null; }}
>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>Tour löschen</Dialog.Title>
			<Dialog.Description>
				Möchtest du "{deleteTarget?.name}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Btn variant="outline" onclick={() => (deleteTarget = null)}>Abbrechen</Btn>
			<Btn variant="destructive" onclick={handleDelete}>Löschen</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<!-- Report Config Dialog -->
<Dialog.Root
	open={reportConfigTarget !== null}
	onOpenChange={(open) => { if (!open) reportConfigTarget = null; }}
>
	<Dialog.Content class="max-h-[85vh] max-w-lg overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>Report-Konfiguration — {reportConfigTarget?.name}</Dialog.Title>
			<Dialog.Description>Zeiten und Kanäle für automatische Wetterreports</Dialog.Description>
		</Dialog.Header>

		{#if reportConfigLoading}
			<p class="py-4 text-sm text-muted-foreground">Lade Konfiguration…</p>
		{:else}
			<div class="space-y-5 py-2">
				<!-- Times -->
				<div class="grid grid-cols-2 gap-4">
					<div class="space-y-1">
						<label class="text-sm font-medium" for="morning-hour">Morgen-Report (Stunde)</label>
						<Select
							id="morning-hour"
							class="w-full"
							value={getHour(reportConfig.morning_time)}
							onchange={(e) => {
								reportConfig.morning_time = setHour(reportConfig.morning_time, Number((e.target as HTMLSelectElement).value));
							}}
						>
							{#each Array.from({ length: 24 }, (_, i) => i) as h}
								<option value={h}>{String(h).padStart(2, '0')}:00</option>
							{/each}
						</Select>
					</div>
					<div class="space-y-1">
						<label class="text-sm font-medium" for="evening-hour">Abend-Report (Stunde)</label>
						<Select
							id="evening-hour"
							class="w-full"
							value={getHour(reportConfig.evening_time)}
							onchange={(e) => {
								reportConfig.evening_time = setHour(reportConfig.evening_time, Number((e.target as HTMLSelectElement).value));
							}}
						>
							{#each Array.from({ length: 24 }, (_, i) => i) as h}
								<option value={h}>{String(h).padStart(2, '0')}:00</option>
							{/each}
						</Select>
					</div>
				</div>

				<!-- Enabled -->
				<div class="flex items-center gap-3 text-sm font-medium">
					<Checkbox bind:checked={reportConfig.enabled}>Reports aktiv</Checkbox>
				</div>

				<!-- Channels -->
				<div class="space-y-2">
					<p class="text-sm font-medium">Kanäle</p>
					<div class="space-y-2 text-sm">
						<div><Checkbox bind:checked={reportConfig.send_email}>E-Mail senden</Checkbox></div>
						<div><Checkbox bind:checked={reportConfig.send_signal}>Signal senden</Checkbox></div>
						<div><Checkbox bind:checked={reportConfig.send_telegram}>Telegram senden</Checkbox></div>
					</div>
				</div>

				<!-- Options -->
				<div class="space-y-2">
					<p class="text-sm font-medium">Optionen</p>
					<div class="space-y-2 text-sm">
						<div><Checkbox bind:checked={reportConfig.alert_on_changes}>Alert bei Änderungen</Checkbox></div>
						<div><Checkbox bind:checked={reportConfig.show_compact_summary}>Kompakte Zusammenfassung anzeigen</Checkbox></div>
						<div><Checkbox bind:checked={reportConfig.show_daylight}>Tageslicht anzeigen</Checkbox></div>
					</div>
				</div>

				<!-- Thresholds -->
				<div class="space-y-2">
					<p class="text-sm font-medium">Änderungs-Schwellwerte</p>
					<div class="grid grid-cols-3 gap-3">
						<div class="space-y-1">
							<label class="text-xs text-muted-foreground" for="thresh-temp">Temperatur (°C)</label>
							<input
								id="thresh-temp"
								type="number"
								class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
								bind:value={reportConfig.change_threshold_temp_c}
							/>
						</div>
						<div class="space-y-1">
							<label class="text-xs text-muted-foreground" for="thresh-wind">Wind (km/h)</label>
							<input
								id="thresh-wind"
								type="number"
								class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
								bind:value={reportConfig.change_threshold_wind_kmh}
							/>
						</div>
						<div class="space-y-1">
							<label class="text-xs text-muted-foreground" for="thresh-precip">Niederschlag (mm)</label>
							<input
								id="thresh-precip"
								type="number"
								class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
								bind:value={reportConfig.change_threshold_precip_mm}
							/>
						</div>
					</div>
				</div>

				{#if reportConfigError}
					<p class="text-sm text-destructive">{reportConfigError}</p>
				{/if}
			</div>
		{/if}

		<Dialog.Footer>
			<Btn variant="outline" onclick={() => (reportConfigTarget = null)}>Abbrechen</Btn>
			<Btn variant="primary" onclick={saveReportConfig} disabled={reportConfigLoading || reportConfigSaving}>
				{reportConfigSaving ? 'Speichern…' : 'Speichern'}
			</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<!-- Weather Config Dialog -->
<WeatherConfigDialog
	open={weatherConfigTarget !== null}
	entityName={weatherConfigTarget?.name ?? ''}
	currentConfig={weatherConfigTarget?.display_config as Record<string, unknown> | undefined}
	onsave={handleWeatherSave}
	onclose={() => (weatherConfigTarget = null)}
/>

<!-- Test Report Result Dialog -->
<Dialog.Root
	open={testReportTarget !== null}
	onOpenChange={(open) => { if (!open) { testReportTarget = null; testReportResult = null; testReportError = null; } }}
>
	<Dialog.Content class="max-w-sm">
		<Dialog.Header>
			<Dialog.Title>
				Test-Report — {testReportHour === 7 ? 'Morgen' : 'Abend'}
			</Dialog.Title>
		</Dialog.Header>
		<div class="py-4 text-sm">
			{#if testReportRunning}
				<p class="text-muted-foreground">Report wird ausgelöst…</p>
			{:else if testReportResult}
				<p class="text-green-700 dark:text-green-400">{testReportResult}</p>
			{:else if testReportError}
				<p class="text-destructive">{testReportError}</p>
			{/if}
		</div>
		<Dialog.Footer>
			<Btn variant="primary" onclick={() => { testReportTarget = null; testReportResult = null; testReportError = null; }}>
				Schließen
			</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

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
			onclick={() => { const t = sheetTrip!; sheetTrip = null; openReportConfig(t); }}>
			<BellIcon class="size-4 text-muted-foreground shrink-0" /> Report-Konfiguration
		</button>
		<button class="w-full flex items-center gap-3 px-4 min-h-[44px] text-sm hover:bg-muted/60 active:bg-muted"
			onclick={() => { const t = sheetTrip!; weatherConfigTarget = t; sheetTrip = null; }}>
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
