<script lang="ts">
	import type { Trip } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import TripForm from '$lib/components/TripForm.svelte';
	import WeatherConfigDialog from '$lib/components/WeatherConfigDialog.svelte';

	let { data } = $props();

	let trips: Trip[] = $state(data.trips);
	let dialogMode: 'create' | 'edit' | null = $state(null);
	let editTarget: Trip | null = $state(null);
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
		wind_exposition_min_elevation_m: 2000,
		multi_day_trend_reports: ['morning', 'evening'] as string[]
	});

	// Weather Config Dialog
	let weatherConfigTarget: Trip | null = $state(null);

	// Test Report
	let testReportTarget: Trip | null = $state(null);
	let testReportHour: 7 | 18 | null = $state(null);
	let testReportRunning = $state(false);
	let testReportResult: string | null = $state(null);
	let testReportError: string | null = $state(null);

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
					wind_exposition_min_elevation_m: rc.wind_exposition_min_elevation_m ?? 2000,
					multi_day_trend_reports: rc.multi_day_trend_reports ?? ['morning', 'evening']
				};
			} else {
				reportConfig = {
					morning_time: '07:00:00',
					evening_time: '18:00:00',
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
					wind_exposition_min_elevation_m: 2000,
					multi_day_trend_reports: ['morning', 'evening']
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
			trips = await api.get<Trip[]>('/api/trips');
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
			testReportResult = `Test-Report (${hour === 7 ? 'Morning' : 'Evening'}) wurde ausgelöst. Alle aktiven Trips für ${hour}:00 Uhr werden verarbeitet.`;
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
			trips = await api.get<Trip[]>('/api/trips');
			weatherConfigTarget = null;
		} catch (e: unknown) {
			error = (e as { error?: string; detail?: string })?.detail
				?? (e as { error?: string })?.error
				?? 'Fehler beim Speichern der Wetter-Konfiguration';
		}
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
							<div class="inline-flex flex-wrap justify-end gap-1">
								<Button variant="outline" size="sm" onclick={() => openReportConfig(trip)}>Reports</Button>
								<Button variant="outline" size="sm" onclick={() => (weatherConfigTarget = trip)}>Wetter</Button>
								<Button variant="outline" size="sm" onclick={() => runTestReport(trip, 7)}>Test Morgen</Button>
								<Button variant="outline" size="sm" onclick={() => runTestReport(trip, 18)}>Test Abend</Button>
								<Button variant="ghost" size="sm" onclick={() => openEdit(trip)}>Bearbeiten</Button>
								<Button variant="ghost" size="sm" onclick={() => (deleteTarget = trip)}>Löschen</Button>
							</div>
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
						<select
							id="morning-hour"
							class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
							value={getHour(reportConfig.morning_time)}
							onchange={(e) => {
								reportConfig.morning_time = setHour(reportConfig.morning_time, Number((e.target as HTMLSelectElement).value));
							}}
						>
							{#each Array.from({ length: 24 }, (_, i) => i) as h}
								<option value={h}>{String(h).padStart(2, '0')}:00</option>
							{/each}
						</select>
					</div>
					<div class="space-y-1">
						<label class="text-sm font-medium" for="evening-hour">Abend-Report (Stunde)</label>
						<select
							id="evening-hour"
							class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
							value={getHour(reportConfig.evening_time)}
							onchange={(e) => {
								reportConfig.evening_time = setHour(reportConfig.evening_time, Number((e.target as HTMLSelectElement).value));
							}}
						>
							{#each Array.from({ length: 24 }, (_, i) => i) as h}
								<option value={h}>{String(h).padStart(2, '0')}:00</option>
							{/each}
						</select>
					</div>
				</div>

				<!-- Channels -->
				<div class="space-y-2">
					<p class="text-sm font-medium">Kanäle</p>
					<div class="space-y-2">
						<label class="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								class="rounded border-input"
								bind:checked={reportConfig.send_email}
							/>
							E-Mail senden
						</label>
						<label class="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								class="rounded border-input"
								bind:checked={reportConfig.send_signal}
							/>
							Signal senden
						</label>
						<label class="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								class="rounded border-input"
								bind:checked={reportConfig.send_telegram}
							/>
							Telegram senden
						</label>
					</div>
				</div>

				<!-- Options -->
				<div class="space-y-2">
					<p class="text-sm font-medium">Optionen</p>
					<div class="space-y-2">
						<label class="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								class="rounded border-input"
								bind:checked={reportConfig.alert_on_changes}
							/>
							Alert bei Änderungen
						</label>
						<label class="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								class="rounded border-input"
								bind:checked={reportConfig.show_compact_summary}
							/>
							Kompakte Zusammenfassung anzeigen
						</label>
						<label class="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								class="rounded border-input"
								bind:checked={reportConfig.show_daylight}
							/>
							Tageslicht anzeigen
						</label>
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
			<Button variant="outline" onclick={() => (reportConfigTarget = null)}>Abbrechen</Button>
			<Button onclick={saveReportConfig} disabled={reportConfigLoading || reportConfigSaving}>
				{reportConfigSaving ? 'Speichern…' : 'Speichern'}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<!-- Weather Config Dialog -->
<WeatherConfigDialog
	open={weatherConfigTarget !== null}
	entityName={weatherConfigTarget?.name ?? ''}
	currentConfig={weatherConfigTarget?.display_config}
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
			<Button onclick={() => { testReportTarget = null; testReportResult = null; testReportError = null; }}>
				Schließen
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
