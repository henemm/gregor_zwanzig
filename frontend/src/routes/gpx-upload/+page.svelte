<script lang="ts">
	import type { Waypoint } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';

	interface ParsedStage {
		name: string;
		date: string;
		waypoints: Waypoint[];
	}

	let fileList: FileList | undefined = $state(undefined);
	let stageDate: string = $state('');
	let startHour: number = $state(8);
	let loading: boolean = $state(false);
	let error: string | null = $state(null);

	let parsedStage: ParsedStage | null = $state(null);
	let tripName: string = $state('');
	let saving: boolean = $state(false);
	let saveError: string | null = $state(null);
	let savedTripId: string | null = $state(null);

	const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

	async function handleUpload() {
		if (!fileList?.length) {
			error = 'Bitte eine GPX-Datei auswählen.';
			return;
		}
		if (fileList[0].size > MAX_FILE_SIZE) {
			error = 'Datei zu groß (max. 10 MB).';
			return;
		}
		if (!fileList[0].name.toLowerCase().endsWith('.gpx')) {
			error = 'Nur .gpx Dateien erlaubt.';
			return;
		}

		error = null;
		parsedStage = null;
		savedTripId = null;
		loading = true;

		try {
			const formData = new FormData();
			formData.append('file', fileList[0]);
			if (stageDate) formData.append('stage_date', stageDate);
			formData.append('start_hour', String(startHour));

			const res = await fetch('/api/gpx/parse', {
				method: 'POST',
				body: formData
			});

			if (!res.ok) {
				const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
				throw err;
			}

			const data: ParsedStage = await res.json();
			parsedStage = data;
			tripName = data.name;
		} catch (e: unknown) {
			error =
				(e as { detail?: string })?.detail ??
				(e as { error?: string })?.error ??
				'Fehler beim Hochladen der GPX-Datei.';
		} finally {
			loading = false;
		}
	}

	function generateId(name: string): string {
		return name
			.toLowerCase()
			.replace(/\s+/g, '-')
			.replace(/[^a-z0-9-]/g, '')
			.replace(/-+/g, '-')
			.replace(/^-|-$/g, '');
	}

	async function handleSave() {
		if (!parsedStage) return;
		const id = generateId(tripName);
		if (!id) {
			saveError = 'Trip-Name muss mindestens einen Buchstaben oder eine Zahl enthalten.';
			return;
		}
		saveError = null;
		saving = true;

		try {
			const trip = {
				id: generateId(tripName),
				name: tripName,
				stages: [
					{
						name: parsedStage.name,
						date: parsedStage.date,
						waypoints: parsedStage.waypoints
					}
				]
			};

			const result = await api.post<{ id: string }>('/api/trips', trip);
			savedTripId = result?.id ?? trip.id;
		} catch (e: unknown) {
			saveError =
				(e as { detail?: string })?.detail ??
				(e as { error?: string })?.error ??
				'Fehler beim Speichern des Trips.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-bold">GPX hochladen</h1>
	</div>

	<!-- Upload Section -->
	<Card.Root>
		<Card.Header>
			<Card.Title>GPX-Datei importieren</Card.Title>
			<Card.Description>
				Lade eine GPX-Datei hoch, um daraus eine Etappe und einen Trip zu erstellen.
			</Card.Description>
		</Card.Header>
		<Card.Content>
			<div class="space-y-4">
				<div class="space-y-1">
					<label for="gpx-file" class="text-sm font-medium">GPX-Datei</label>
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
						<label for="stage-date" class="text-sm font-medium">Datum (optional)</label>
						<Input
							id="stage-date"
							type="date"
							bind:value={stageDate}
							placeholder="YYYY-MM-DD"
						/>
					</div>

					<div class="space-y-1">
						<label for="start-hour" class="text-sm font-medium">Startzeit (Stunde)</label>
						<Input
							id="start-hour"
							type="number"
							min="0"
							max="23"
							bind:value={startHour}
						/>
					</div>
				</div>

				{#if error}
					<p class="text-sm text-destructive">{error}</p>
				{/if}

				<Button onclick={handleUpload} disabled={loading}>
					{loading ? 'Wird hochgeladen...' : 'Hochladen'}
				</Button>
			</div>
		</Card.Content>
	</Card.Root>

	<!-- Preview Section -->
	{#if parsedStage}
		<Card.Root>
			<Card.Header>
				<Card.Title>Etappen-Vorschau</Card.Title>
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
							<Table.Head>Name</Table.Head>
							<Table.Head>Lat</Table.Head>
							<Table.Head>Lon</Table.Head>
							<Table.Head>Höhe</Table.Head>
							<Table.Head>Zeitfenster</Table.Head>
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
					<Card.Title>Als Trip speichern</Card.Title>
				</Card.Header>
				<Card.Content>
					<div class="space-y-4">
						<div class="space-y-1">
							<label for="trip-name" class="text-sm font-medium">Trip-Name</label>
							<Input
								id="trip-name"
								type="text"
								bind:value={tripName}
								placeholder="Trip-Name eingeben"
							/>
						</div>

						{#if saveError}
							<p class="text-sm text-destructive">{saveError}</p>
						{/if}

						<Button onclick={handleSave} disabled={saving || !tripName.trim()}>
							{saving ? 'Wird gespeichert...' : 'Als Trip speichern'}
						</Button>
					</div>
				</Card.Content>
			</Card.Root>
		{/if}

		<!-- Success Message -->
		{#if savedTripId}
			<Card.Root class="border-green-200 bg-green-50">
				<Card.Content class="pt-6">
					<p class="text-sm font-medium text-green-800">
						Trip wurde erfolgreich gespeichert.
					</p>
					<a href="/trips" class="mt-2 inline-block text-sm text-green-700 underline hover:text-green-900">
						Zu den Trips
					</a>
				</Card.Content>
			</Card.Root>
		{/if}
	{/if}
</div>
