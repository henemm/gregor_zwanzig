<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { api } from '$lib/api.js';

	let { data } = $props();

	let mailTo = $state(data.profile?.mail_to ?? '');
	let signalPhone = $state(data.profile?.signal_phone ?? '');
	let signalApiKey = $state('');
	let telegramChatId = $state(data.profile?.telegram_chat_id ?? '');
	let successMsg = $state<string | null>(null);
	let errorMsg = $state<string | null>(null);
	let deleteErrorMsg = $state<string | null>(null);

	type TestStatus = 'idle' | 'loading' | 'ok' | 'error';
	let testStatus = $state<Record<string, TestStatus>>({email: 'idle', signal: 'idle', telegram: 'idle'});
	let testError = $state<Record<string, string | null>>({email: null, signal: null, telegram: null});

	async function sendTest(channel: string) {
		testStatus[channel] = 'loading';
		testError[channel] = null;
		try {
			const resp = await api.post('/api/notify/test', { channel });
			if (resp?.error) {
				testError[channel] = resp.error;
				testStatus[channel] = 'error';
			} else {
				testStatus[channel] = 'ok';
				setTimeout(() => (testStatus[channel] = 'idle'), 4000);
			}
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			testError[channel] = body?.detail ?? body?.error ?? 'Senden fehlgeschlagen';
			testStatus[channel] = 'error';
		}
	}

	let oldPassword = $state('');
	let newPassword = $state('');
	let confirmNewPassword = $state('');
	let pwSuccessMsg = $state<string | null>(null);
	let pwErrorMsg = $state<string | null>(null);

	async function changePassword() {
		pwSuccessMsg = null;
		pwErrorMsg = null;

		if (newPassword !== confirmNewPassword) {
			pwErrorMsg = 'Die neuen Passwörter stimmen nicht überein';
			return;
		}

		try {
			await api.put('/api/auth/password', {
				old_password: oldPassword,
				new_password: newPassword,
			});
			pwSuccessMsg = 'Passwort geändert';
			oldPassword = '';
			newPassword = '';
			confirmNewPassword = '';
			setTimeout(() => (pwSuccessMsg = null), 4000);
		} catch (e: unknown) {
			const body = e as { error?: string };
			if (body?.error === 'wrong password') {
				pwErrorMsg = 'Aktuelles Passwort ist falsch';
			} else {
				pwErrorMsg = body?.error ?? 'Passwort ändern fehlgeschlagen';
			}
		}
	}

	function formatDate(iso: string | null | undefined): string {
		if (!iso) return '—';
		try {
			return new Date(iso).toLocaleDateString('de-AT', {
				year: 'numeric',
				month: '2-digit',
				day: '2-digit',
			});
		} catch {
			return iso;
		}
	}

	async function save() {
		errorMsg = null;
		successMsg = null;
		try {
			const payload: Record<string, string> = {
				mail_to: mailTo,
				signal_phone: signalPhone,
				telegram_chat_id: telegramChatId,
			};
			if (signalApiKey !== '') {
				payload.signal_api_key = signalApiKey;
			}
			await api.put('/api/auth/profile', payload);
			signalApiKey = '';
			successMsg = 'Profil gespeichert';
			setTimeout(() => (successMsg = null), 4000);
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			errorMsg = body?.detail ?? body?.error ?? 'Speichern fehlgeschlagen';
		}
	}

	function formatDate(iso: string | null | undefined): string {
		if (!iso) return '—';
		try {
			return new Date(iso).toLocaleDateString('de-AT', {
				year: 'numeric',
				month: '2-digit',
				day: '2-digit',
			});
		} catch {
			return iso;
		}
	}

	// --- System-Status helpers (migrated from settings) ---

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

	async function deleteAccount() {
		const confirmed = window.confirm(
			'Bist du sicher? Alle deine Daten werden unwiderruflich gelöscht.'
		);
		if (!confirmed) return;

		try {
			await api.del('/api/auth/account');
			window.location.href = '/login';
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			deleteErrorMsg = body?.detail ?? body?.error ?? 'Löschen fehlgeschlagen';
		}
	}
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-bold">Mein Konto</h1>

	{#if successMsg}
		<div class="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-800">
			{successMsg}
		</div>
	{/if}

	{#if errorMsg}
		<div class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
			{errorMsg}
		</div>
	{/if}

	<Card.Root>
		<Card.Header>
			<Card.Title>Profil</Card.Title>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="grid gap-1">
				<span class="text-sm font-medium text-muted-foreground">Benutzername</span>
				<span class="text-sm">{data.profile?.id ?? '—'}</span>
			</div>
			<div class="grid gap-1">
				<span class="text-sm font-medium text-muted-foreground">Mitglied seit</span>
				<span class="text-sm">{formatDate(data.profile?.created_at)}</span>
			</div>
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header>
			<Card.Title>Kanäle</Card.Title>
			<Card.Description>Wohin sollen deine Wetter-Reports gesendet werden?</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="space-y-2">
				<label for="mailTo" class="text-sm font-medium">E-Mail für Reports</label>
				<div class="flex items-center gap-2">
					<input
						id="mailTo"
						name="mail_to"
						type="email"
						bind:value={mailTo}
						placeholder="z.B. dein@email.com"
						class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					/>
					{#if mailTo}
						<button
							onclick={() => sendTest('email')}
							disabled={testStatus.email === 'loading'}
							class="shrink-0 text-sm text-blue-600 hover:underline disabled:opacity-50"
						>
							{testStatus.email === 'loading' ? '...' : 'Test senden'}
						</button>
					{/if}
				</div>
				{#if testStatus.email === 'ok'}
					<span class="text-sm text-green-600">Gesendet</span>
				{/if}
				{#if testStatus.email === 'error'}
					<span class="text-sm text-red-600">{testError.email}</span>
				{/if}
			</div>

			<div class="space-y-2">
				<label for="signalPhone" class="text-sm font-medium">Signal-Nummer</label>
				<div class="flex items-center gap-2">
					<input
						id="signalPhone"
						name="signal_phone"
						type="text"
						bind:value={signalPhone}
						placeholder="z.B. +43664..."
						class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					/>
					{#if signalPhone}
						<button
							onclick={() => sendTest('signal')}
							disabled={testStatus.signal === 'loading'}
							class="shrink-0 text-sm text-blue-600 hover:underline disabled:opacity-50"
						>
							{testStatus.signal === 'loading' ? '...' : 'Test senden'}
						</button>
					{/if}
				</div>
				{#if testStatus.signal === 'ok'}
					<span class="text-sm text-green-600">Gesendet</span>
				{/if}
				{#if testStatus.signal === 'error'}
					<span class="text-sm text-red-600">{testError.signal}</span>
				{/if}
			</div>

			<div class="space-y-2">
				<label for="signalApiKey" class="text-sm font-medium">Signal API Key</label>
				<input
					id="signalApiKey"
					name="signal_api_key"
					type="password"
					bind:value={signalApiKey}
					placeholder="Callmebot API Key"
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
				<p class="text-xs text-muted-foreground">Callmebot API Key für Signal-Benachrichtigungen</p>
			</div>

			<div class="space-y-2">
				<label for="telegramChatId" class="text-sm font-medium">Telegram-ID</label>
				<div class="flex items-center gap-2">
					<input
						id="telegramChatId"
						name="telegram_chat_id"
						type="text"
						bind:value={telegramChatId}
						placeholder="z.B. 123456789"
						class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					/>
					{#if telegramChatId}
						<button
							onclick={() => sendTest('telegram')}
							disabled={testStatus.telegram === 'loading'}
							class="shrink-0 text-sm text-blue-600 hover:underline disabled:opacity-50"
						>
							{testStatus.telegram === 'loading' ? '...' : 'Test senden'}
						</button>
					{/if}
				</div>
				{#if testStatus.telegram === 'ok'}
					<span class="text-sm text-green-600">Gesendet</span>
				{/if}
				{#if testStatus.telegram === 'error'}
					<span class="text-sm text-red-600">{testError.telegram}</span>
				{/if}
			</div>

			<button
				onclick={save}
				class="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			>
				Speichern
			</button>
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header>
			<Card.Title>Passwort ändern</Card.Title>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="space-y-2">
				<label for="oldPassword" class="text-sm font-medium">Aktuelles Passwort</label>
				<input
					id="oldPassword"
					type="password"
					bind:value={oldPassword}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			<div class="space-y-2">
				<label for="newPassword" class="text-sm font-medium">Neues Passwort</label>
				<input
					id="newPassword"
					type="password"
					bind:value={newPassword}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			<div class="space-y-2">
				<label for="confirmNewPassword" class="text-sm font-medium">Neues Passwort bestätigen</label>
				<input
					id="confirmNewPassword"
					type="password"
					bind:value={confirmNewPassword}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			{#if pwSuccessMsg}
				<div class="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-800">
					{pwSuccessMsg}
				</div>
			{/if}

			{#if pwErrorMsg}
				<div class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
					{pwErrorMsg}
				</div>
			{/if}

			<button
				onclick={changePassword}
				class="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			>
				Passwort ändern
			</button>
		</Card.Content>
	</Card.Root>

	<!-- System-Status Section (migrated from settings) -->
	<div id="system-status" class="space-y-6">
		<!-- Card: Deine Reports -->
		<Card.Root>
			<Card.Header>
				<Card.Title>Deine Reports</Card.Title>
			</Card.Header>
			<Card.Content>
				{#if data.scheduler === null}
					<p class="text-sm text-muted-foreground">Report-Zeitplan nicht verfügbar.</p>
				{:else if data.scheduler?.jobs && data.scheduler.jobs.length > 0}
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

		<!-- Card: Dein Account -->
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

		<!-- Card: Verfügbarkeit -->
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

	<!-- Wetter-Templates Card -->
	<Card.Root>
		<Card.Header>
			<Card.Title>Wetter-Templates</Card.Title>
			<Card.Description>Systemweite Report-Vorlagen (nur lesend)</Card.Description>
		</Card.Header>
		<Card.Content>
			{#if !data.templates || data.templates.length === 0}
				<p class="text-sm text-muted-foreground">Keine Templates verfügbar.</p>
			{:else}
				<div class="space-y-2">
					{#each data.templates as tpl}
						<div class="flex items-center justify-between text-sm">
							<span class="font-medium">{tpl.label ?? tpl.name ?? tpl.id}</span>
							{#if tpl.metrics}
								<Badge variant="secondary">{tpl.metrics.length} Metriken</Badge>
							{:else if tpl.description ?? tpl.type}
								<span class="text-muted-foreground">{tpl.description ?? tpl.type}</span>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

	<Card.Root class="border-red-200">
		<Card.Header>
			<Card.Title class="text-red-700">Gefahrenzone</Card.Title>
		</Card.Header>
		<Card.Content>
			<p class="mb-4 text-sm text-muted-foreground">
				Das Löschen deines Accounts ist unwiderruflich. Alle deine Daten werden permanent gelöscht.
			</p>
			<button
				onclick={deleteAccount}
				class="inline-flex h-10 items-center justify-center rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white ring-offset-background hover:bg-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
			>
				Account löschen
			</button>
			{#if deleteErrorMsg}
				<p class="mt-2 text-sm text-red-600">{deleteErrorMsg}</p>
			{/if}
		</Card.Content>
	</Card.Root>
</div>
