<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';

	let { data } = $props();

	function formatDate(iso: string | null | undefined): string {
		if (!iso) return '—';
		try {
			return new Date(iso).toLocaleString('de-AT', {
				year: 'numeric',
				month: '2-digit',
				day: '2-digit',
				hour: '2-digit',
				minute: '2-digit'
			});
		} catch {
			return iso;
		}
	}

	const configLabels: Record<string, string> = {
		latitude: 'Breitengrad',
		longitude: 'Längengrad',
		location_name: 'Standort',
		provider: 'Wetter-Provider',
		report_type: 'Report-Typ',
		channel: 'Kanal',
		debug_level: 'Debug-Level',
		forecast_hours: 'Vorhersage (Stunden)'
	};

	// Keys die auf der Settings-Seite nicht angezeigt werden sollen
	const hiddenConfigKeys = new Set([
		'elevation_m', 'dry_run', 'include_snow'
	]);
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-bold">System-Status</h1>

	<!-- Scheduler Status -->
	<Card.Root>
		<Card.Header>
			<Card.Title>Zeitplaner</Card.Title>
			<Card.Description>Geplante Jobs und deren letzter Ausführungsstatus</Card.Description>
		</Card.Header>
		<Card.Content>
			{#if data.scheduler === null}
				<p class="text-sm text-muted-foreground">Scheduler nicht erreichbar.</p>
			{:else}
				<div class="mb-4 flex items-center gap-4 text-sm">
					<span>
						Status:
						<span class="inline-flex items-center gap-1.5 font-medium"
							class:text-green-600={data.scheduler.running}
							class:text-red-600={!data.scheduler.running}
						>
							<span class="inline-block size-2 rounded-full" class:bg-green-500={data.scheduler.running} class:bg-red-400={!data.scheduler.running}></span>
							{data.scheduler.running ? 'Läuft' : 'Gestoppt'}
						</span>
					</span>
					<span class="text-muted-foreground">Zeitzone: {data.scheduler.timezone ?? '—'}</span>
				</div>

				{#if data.scheduler.jobs && data.scheduler.jobs.length > 0}
					<Table.Root>
						<Table.Header>
							<Table.Row>
								<Table.Head>Job</Table.Head>
								<Table.Head>Nächster Lauf</Table.Head>
								<Table.Head>Letzter Lauf</Table.Head>
								<Table.Head>Status</Table.Head>
							</Table.Row>
						</Table.Header>
						<Table.Body>
							{#each data.scheduler.jobs as job}
								<Table.Row>
									<Table.Cell class="font-medium">{job.name ?? job.id}</Table.Cell>
									<Table.Cell class="text-sm">{formatDate(job.next_run)}</Table.Cell>
									<Table.Cell class="text-sm text-muted-foreground">
										{job.last_run?.time ? formatDate(job.last_run.time) : 'Noch nie'}
									</Table.Cell>
									<Table.Cell>
										<span class="inline-flex items-center gap-1.5 text-sm">
											{#if !job.last_run?.time}
												<span class="inline-block size-2 rounded-full bg-gray-300"></span>
												<span class="text-muted-foreground">nie</span>
											{:else if job.last_run?.status === 'ok'}
												<span class="inline-block size-2 rounded-full bg-green-500"></span>
												ok
											{:else if job.last_run?.status === 'error'}
												<span class="inline-block size-2 rounded-full bg-red-500"></span>
												<span class="text-destructive">Fehler</span>
											{:else}
												<span class="inline-block size-2 rounded-full bg-gray-400"></span>
												{job.last_run?.status ?? '—'}
											{/if}
										</span>
									</Table.Cell>
								</Table.Row>
							{/each}
						</Table.Body>
					</Table.Root>
				{:else}
					<p class="text-sm text-muted-foreground">Keine Jobs konfiguriert.</p>
				{/if}
			{/if}
		</Card.Content>
	</Card.Root>

	<!-- System Config -->
	<Card.Root>
		<Card.Header>
			<Card.Title>Konfiguration</Card.Title>
			<Card.Description>Aktive Konfiguration des Backends</Card.Description>
		</Card.Header>
		<Card.Content>
			{#if data.config === null}
				<p class="text-sm text-muted-foreground">Konfiguration nicht erreichbar.</p>
			{:else}
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head class="w-1/3">Parameter</Table.Head>
							<Table.Head>Wert</Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each Object.entries(data.config).filter(([k]) => !hiddenConfigKeys.has(k)) as [key, value]}
							<Table.Row>
								<Table.Cell class="font-medium text-muted-foreground">
									{configLabels[key] ?? key}
								</Table.Cell>
								<Table.Cell class="font-mono text-sm">{value ?? '—'}</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			{/if}
		</Card.Content>
	</Card.Root>

	<!-- Service Health -->
	<Card.Root>
		<Card.Header>
			<Card.Title>System-Status</Card.Title>
			<Card.Description>Aktueller Zustand aller Systemkomponenten</Card.Description>
		</Card.Header>
		<Card.Content>
			{#if data.health === null}
				<p class="text-sm text-destructive">Health-Endpoint nicht erreichbar.</p>
			{:else}
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head class="w-1/3">Komponente</Table.Head>
							<Table.Head>Status</Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						<Table.Row>
							<Table.Cell class="font-medium">API (Go)</Table.Cell>
							<Table.Cell>
								{#if data.health.status === 'ok'}
									<Badge variant="default" class="bg-green-600 text-white">ok</Badge>
								{:else if data.health.status === 'degraded'}
									<Badge variant="secondary" class="bg-yellow-500 text-white">degraded</Badge>
								{:else}
									<Badge variant="destructive">{data.health.status}</Badge>
								{/if}
							</Table.Cell>
						</Table.Row>
						<Table.Row>
							<Table.Cell class="font-medium">Python Core</Table.Cell>
							<Table.Cell>
								{#if data.health.python_core === 'ok'}
									<Badge variant="default" class="bg-green-600 text-white">ok</Badge>
								{:else if data.health.python_core === 'unavailable'}
									<Badge variant="destructive">unavailable</Badge>
								{:else}
									<Badge variant="secondary">{data.health.python_core ?? '—'}</Badge>
								{/if}
							</Table.Cell>
						</Table.Row>
						{#if data.health.version}
							<Table.Row>
								<Table.Cell class="font-medium">Version</Table.Cell>
								<Table.Cell class="font-mono text-sm text-muted-foreground">
									v{data.health.version}
								</Table.Cell>
							</Table.Row>
						{/if}
						{#each Object.entries(data.health).filter(([k]) => !['status', 'python_core', 'version'].includes(k)) as [key, value]}
							<Table.Row>
								<Table.Cell class="font-medium text-muted-foreground">{key}</Table.Cell>
								<Table.Cell class="font-mono text-sm">{value}</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			{/if}
		</Card.Content>
	</Card.Root>
</div>
