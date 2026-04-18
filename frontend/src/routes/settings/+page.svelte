<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';

	let { data } = $props();

	function timeAgo(iso: string): string {
		const diff = Date.now() - new Date(iso).getTime();
		const mins = Math.floor(diff / 60000);
		if (mins < 1) return 'gerade eben';
		if (mins < 60) return `vor ${mins} Min`;
		const hours = Math.floor(mins / 60);
		if (hours < 24) return `vor ${hours} Std`;
		const days = Math.floor(hours / 24);
		return `vor ${days} Tag${days > 1 ? 'en' : ''}`;
	}

	function formatNextRun(iso: string | null | undefined): string {
		if (!iso) return '—';
		try {
			const date = new Date(iso);
			const now = new Date();
			const today = new Date(now.toLocaleString('en-US', { timeZone: 'Europe/Vienna' }));
			const target = new Date(date.toLocaleString('en-US', { timeZone: 'Europe/Vienna' }));
			const time = date.toLocaleString('de-AT', { timeZone: 'Europe/Vienna', hour: '2-digit', minute: '2-digit' });

			const todayDate = new Date(today.getFullYear(), today.getMonth(), today.getDate());
			const targetDate = new Date(target.getFullYear(), target.getMonth(), target.getDate());
			const diffDays = Math.round((targetDate.getTime() - todayDate.getTime()) / 86400000);

			if (diffDays === 0) return `heute um ${time}`;
			if (diffDays === 1) return `morgen um ${time}`;
			return date.toLocaleString('de-AT', { timeZone: 'Europe/Vienna', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
		} catch { return iso; }
	}

	function getProvider(lat: number, lon: number): string {
		return (lat >= 45 && lat <= 50 && lon >= 8 && lon <= 18)
			? 'GeoSphere (Alpen)' : 'OpenMeteo';
	}

	const userJobs: Record<string, string> = {
		morning_subscriptions: 'Morgen-Report',
		evening_subscriptions: 'Abend-Report',
		trip_reports_hourly: 'Trip-Checks',
	};
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-bold">Mein Service</h1>

	<!-- Sektion 1: Deine Reports -->
	<Card.Root>
		<Card.Header>
			<Card.Title>Deine Reports</Card.Title>
		</Card.Header>
		<Card.Content>
			{#if data.scheduler === null}
				<p class="text-sm text-muted-foreground">Report-Zeitplan nicht verfügbar.</p>
			{:else if data.scheduler.jobs && data.scheduler.jobs.length > 0}
				<div class="space-y-3">
					{#each data.scheduler.jobs.filter((j: any) => j.id in userJobs) as job}
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2">
								<span class="inline-block size-2 rounded-full"
									class:bg-green-500={job.last_run?.status === 'ok'}
									class:bg-red-500={job.last_run?.status === 'error'}
									class:bg-gray-300={!job.last_run?.time}
								></span>
								<span class="font-medium">{userJobs[job.id]}</span>
							</div>
							<div class="flex items-center gap-4 text-sm text-muted-foreground">
								<span>Nächster: {formatNextRun(job.next_run)}</span>
								<span>Zuletzt: {job.last_run?.time ? timeAgo(job.last_run.time) : '—'}</span>
							</div>
						</div>
						{#if job.last_run?.status === 'error'}
							<p class="ml-4 text-sm text-destructive">Letzter Lauf fehlgeschlagen{job.last_run?.error ? `: ${job.last_run.error}` : ''}</p>
						{/if}
					{/each}
				</div>
			{:else}
				<p class="text-sm text-muted-foreground">Keine Reports konfiguriert.</p>
			{/if}
		</Card.Content>
	</Card.Root>

	<!-- Sektion 2: Dein Account -->
	<Card.Root data-testid="account-section">
		<Card.Header>
			<Card.Title>Dein Account</Card.Title>
		</Card.Header>
		<Card.Content>
			<!-- Zähler -->
			<div class="space-y-2 mb-4">
				<div class="flex items-center justify-between text-sm">
					<span>Aktive Trips</span>
					<a href="/trips" class="font-medium hover:underline">{data.trips.length}</a>
				</div>
				<div class="flex items-center justify-between text-sm">
					<span>Aktive Abos</span>
					<a href="/subscriptions" class="font-medium hover:underline">{data.subscriptions.filter((s: any) => s.enabled).length}</a>
				</div>
				<div class="flex items-center justify-between text-sm">
					<span>Locations</span>
					<a href="/locations" class="font-medium hover:underline">{data.locations.length}</a>
				</div>
			</div>

			<!-- Benachrichtigungskanäle -->
			<div data-testid="channels" class="mb-4">
				<p class="text-sm font-medium mb-2">Benachrichtigungen</p>
				{#if data.profile && (data.profile.mail_to || data.profile.signal_phone || data.profile.telegram_chat_id)}
					<div class="flex flex-wrap gap-2">
						{#if data.profile.mail_to}
							<Badge variant="secondary">E-Mail: {data.profile.mail_to}</Badge>
						{/if}
						{#if data.profile.signal_phone}
							<Badge variant="secondary">Signal: {data.profile.signal_phone}</Badge>
						{/if}
						{#if data.profile.telegram_chat_id}
							<Badge variant="secondary">Telegram: {data.profile.telegram_chat_id}</Badge>
						{/if}
					</div>
				{:else}
					<p class="text-sm text-muted-foreground">
						Keine Benachrichtigungen konfiguriert — <a href="/account" class="underline hover:text-foreground">einrichten</a>
					</p>
				{/if}
			</div>

			<!-- Wetter-Modelle -->
			<div data-testid="weather-models">
				<p class="text-sm font-medium mb-2">Wetter-Modelle</p>
				{#if data.locations.length > 0}
					<div class="space-y-1">
						{#each data.locations as loc}
							<p class="text-sm text-muted-foreground">
								{loc.name} → {getProvider(loc.lat, loc.lon)}
							</p>
						{/each}
					</div>
				{:else}
					<p class="text-sm text-muted-foreground">
						Noch keine Locations angelegt — <a href="/locations" class="underline hover:text-foreground">anlegen</a>
					</p>
				{/if}
			</div>
		</Card.Content>
	</Card.Root>

	<!-- Sektion 3: Verfügbarkeit -->
	<Card.Root>
		<Card.Header>
			<Card.Title>Verfügbarkeit</Card.Title>
		</Card.Header>
		<Card.Content>
			<div class="flex items-center gap-2">
				{#if data.health === null}
					<span class="inline-block size-3 rounded-full bg-red-500"></span>
					<span class="font-medium">Nicht erreichbar</span>
				{:else if data.health.status === 'ok'}
					<span class="inline-block size-3 rounded-full bg-green-500"></span>
					<span class="font-medium">System läuft</span>
				{:else if data.health.status === 'degraded'}
					<span class="inline-block size-3 rounded-full bg-yellow-500"></span>
					<span class="font-medium">Eingeschränkt</span>
				{:else}
					<span class="inline-block size-3 rounded-full bg-red-500"></span>
					<span class="font-medium">Nicht erreichbar</span>
				{/if}
			</div>
			{#if data.health?.version}
				<p class="mt-1 text-sm text-muted-foreground">v{data.health.version}</p>
			{/if}
		</Card.Content>
	</Card.Root>
</div>
