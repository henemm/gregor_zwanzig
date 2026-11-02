<script lang="ts">
	import { api } from '$lib/api.js';
	import { Btn, Input } from '$lib/components/atoms';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { t, type MessageKey } from '$lib/i18n';
	import { gpxDateiFehler, gpxHochladen, baueGpxTrip, gpxTripId, type GpxEtappe } from './gpxTrip.ts';

	type ParsedStage = GpxEtappe;

	let fileList: FileList | undefined = $state(undefined);
	let stageDate: string = $state('');
	let startHour: number = $state(8);
	let loading: boolean = $state(false);
	// Issue #2657 (i18n F8): eigener Hinweis als Katalogschluessel (folgt der Sprache),
	// ein Servertext (`detail`/`error`) wird unveraendert gezeigt.
	let error: string | null = $state(null);
	let errorKey: MessageKey | null = $state(null);

	let parsedStage: ParsedStage | null = $state(null);
	let tripName: string = $state('');
	let saving: boolean = $state(false);
	let saveError: string | null = $state(null);
	let saveErrorKey: MessageKey | null = $state(null);
	let savedTripId: string | null = $state(null);

	/** Servertext aus dem Fehlerobjekt (`detail` vor `error`), sonst `null`. */
	function serverText(e: unknown): string | null {
		return (e as { detail?: string })?.detail ?? (e as { error?: string })?.error ?? null;
	}

	async function handleUpload() {
		error = null;
		errorKey = gpxDateiFehler(fileList?.[0]);
		if (errorKey || !fileList?.length) return;

		parsedStage = null;
		savedTripId = null;
		loading = true;

		try {
			const data = await gpxHochladen(fileList[0], stageDate, startHour);
			parsedStage = data;
			tripName = data.name;
		} catch (e: unknown) {
			error = serverText(e);
			if (error === null) errorKey = 'layout.gpx.fehler_hochladen';
		} finally {
			loading = false;
		}
	}

	async function handleSave() {
		if (!parsedStage) return;
		saveError = null;
		saveErrorKey = null;
		if (!gpxTripId(tripName)) {
			saveErrorKey = 'layout.gpx.fehler_name';
			return;
		}
		saving = true;

		try {
			const trip = baueGpxTrip(tripName, parsedStage);
			const result = await api.post<{ id: string }>('/api/trips', trip);
			savedTripId = result?.id ?? trip.id;
		} catch (e: unknown) {
			saveError = serverText(e);
			if (saveError === null) saveErrorKey = 'layout.gpx.fehler_speichern';
		} finally {
			saving = false;
		}
	}
</script>

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-bold">{$t('layout.gpx.titel')}</h1>
	</div>

	<!-- Upload Section -->
	<Card.Root>
		<Card.Header>
			<Card.Title>{$t('layout.gpx.import_titel')}</Card.Title>
			<Card.Description>
				{$t('layout.gpx.import_text')}
			</Card.Description>
		</Card.Header>
		<Card.Content>
			<div class="space-y-4">
				<div class="space-y-1">
					<label for="gpx-file" class="text-sm font-medium">{$t('layout.gpx.datei')}</label>
					<Input
						id="gpx-file"
						type="file"
						accept=".gpx"
						bind:files={fileList}
						class="cursor-pointer"
					/>
				</div>

				<div class="grid grid-cols-2 gap-4">
					<div class="space-y-1">
						<label for="stage-date" class="text-sm font-medium">{$t('layout.gpx.datum')}</label>
						<Input
							id="stage-date"
							type="date"
							bind:value={stageDate}
							placeholder={'YYYY-MM-DD'}
						/>
					</div>

					<div class="space-y-1">
						<label for="start-hour" class="text-sm font-medium">{$t('layout.gpx.startzeit')}</label>
						<Input
							id="start-hour"
							type="number"
							min="0"
							max="23"
							bind:value={startHour}
						/>
					</div>
				</div>

				{#if errorKey || error}
					<p class="text-sm text-destructive">{errorKey ? $t(errorKey) : error}</p>
				{/if}

				<Btn variant="primary" onclick={handleUpload} disabled={loading}>
					{loading ? $t('layout.gpx.wird_hochgeladen') : $t('layout.gpx.hochladen')}
				</Btn>
			</div>
		</Card.Content>
	</Card.Root>

	<!-- Preview Section -->
	{#if parsedStage}
		<Card.Root>
			<Card.Header>
				<Card.Title>{$t('layout.gpx.vorschau')}</Card.Title>
				<Card.Description>
					<span class="font-medium">{parsedStage.name}</span>
					{#if parsedStage.date}
						&nbsp;·&nbsp;
						<Badge variant="secondary">{parsedStage.date}</Badge>
					{/if}
				</Card.Description>
			</Card.Header>
			<Card.Content>
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head>{$t('layout.gpx.spalte_name')}</Table.Head>
							<Table.Head>{$t('layout.gpx.spalte_lat')}</Table.Head>
							<Table.Head>{$t('layout.gpx.spalte_lon')}</Table.Head>
							<Table.Head>{$t('layout.gpx.spalte_hoehe')}</Table.Head>
							<Table.Head>{$t('layout.gpx.spalte_zeitfenster')}</Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each parsedStage.waypoints as wp}
							<Table.Row>
								<Table.Cell class="font-medium">{wp.name}</Table.Cell>
								<Table.Cell class="text-sm text-muted-foreground">{wp.lat.toFixed(5)}</Table.Cell>
								<Table.Cell class="text-sm text-muted-foreground">{wp.lon.toFixed(5)}</Table.Cell>
								<Table.Cell class="text-sm">
									{wp.elevation_m != null ? `${wp.elevation_m} m` : '—'}
								</Table.Cell>
								<Table.Cell class="text-sm">
									{#if wp.time_window}
										<Badge variant="outline">{wp.time_window}</Badge>
									{:else}
										—
									{/if}
								</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</Card.Content>
		</Card.Root>

		<!-- Save Section -->
		{#if !savedTripId}
			<Card.Root>
				<Card.Header>
					<Card.Title>{$t('layout.gpx.als_trip_speichern')}</Card.Title>
				</Card.Header>
				<Card.Content>
					<div class="space-y-4">
						<div class="space-y-1">
							<label for="trip-name" class="text-sm font-medium">{$t('layout.gpx.trip_name')}</label>
							<Input
								id="trip-name"
								type="text"
								bind:value={tripName}
								placeholder={$t('layout.gpx.trip_name_eingeben')}
							/>
						</div>

						{#if saveErrorKey || saveError}
							<p class="text-sm text-destructive">{saveErrorKey ? $t(saveErrorKey) : saveError}</p>
						{/if}

						<Btn variant="primary" onclick={handleSave} disabled={saving || !tripName.trim()}>
							{saving ? $t('layout.gpx.wird_gespeichert') : $t('layout.gpx.als_trip_speichern')}
						</Btn>
					</div>
				</Card.Content>
			</Card.Root>
		{/if}

		<!-- Success Message -->
		{#if savedTripId}
			<Card.Root class="border-green-200 bg-green-50">
				<Card.Content class="pt-6">
					<p class="text-sm font-medium text-green-800">
						{$t('layout.gpx.gespeichert')}
					</p>
					<a href="/trips" class="mt-2 inline-block text-sm text-green-700 underline hover:text-green-900">
						{$t('layout.gpx.zu_den_trips')}
					</a>
				</Card.Content>
			</Card.Root>
		{/if}
	{/if}
</div>
