<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { Btn } from '$lib/components/atoms';
	import { api } from '$lib/api.js';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import CheckIcon from '@lucide/svelte/icons/check';
	import XIcon from '@lucide/svelte/icons/x';
	import type { MetricPreset, UserTier } from '$lib/types';
	import { metricCountLabel, showDefaultBadge, isValidRename, applyRename, removePreset, isEmpty } from '$lib/utils/presetCardHelpers';
	let { data } = $props();

	let displayName = $state(data.profile?.display_name ?? '');
	let mailTo = $state(data.profile?.mail_to ?? '');
	let smsTo = $state(data.profile?.sms_to ?? '');
	let telegramConnected = $state(!!data.profile?.telegram_chat_id);
	let telegramChatIdSuffix = $state(
		data.profile?.telegram_chat_id
			? '...' + data.profile.telegram_chat_id.slice(-3)
			: ''
	);
	let telegramConnecting = $state(false);
	let telegramPollInterval: ReturnType<typeof setInterval> | null = null;
	let successMsg = $state<string | null>(null);
	let errorMsg = $state<string | null>(null);
	let deleteErrorMsg = $state<string | null>(null);

	type TestStatus = 'idle' | 'loading' | 'ok' | 'error';
	let testStatus = $state<Record<string, TestStatus>>({email: 'idle', telegram: 'idle'});
	let testError = $state<Record<string, string | null>>({email: null, telegram: null});

	// Issue #344 — Wetter-Profile (User-MetricPresets)
	let presets = $state<MetricPreset[]>(data.metricPresets ?? []);
	let editingId = $state<string | null>(null);
	let editName = $state('');
	let presetError = $state<string | null>(null);
	let deletePresetTarget: MetricPreset | null = $state(null);
	let showDeleteAccountDialog = $state(false);

	// Issue #1068 — Nutzerlevel-Badge (immer sichtbar). Der Wert kommt aus
	// data.profile.tier (Response-Feld ist serverseitig immer gesetzt, Default "free").
	const TIER_LABELS: Record<UserTier, string> = {
		free: 'Free',
		standard: 'Standard',
		premium: 'Premium'
	};
	function tierLabel(tier: unknown): string {
		return TIER_LABELS[(tier as UserTier)] ?? 'Free';
	}

	function startEdit(p: MetricPreset) {
		editingId = p.id;
		editName = p.name;
		presetError = null;
	}

	function cancelEdit() {
		editingId = null;
		editName = '';
	}

	async function saveRename(id: string) {
		if (!isValidRename(editName)) return;
		try {
			const updated = await api.patch<MetricPreset>(`/api/metric-presets/${id}`, { name: editName.trim() });
			presets = applyRename(presets, updated);
			editingId = null;
			editName = '';
		} catch (e: unknown) {
			const body = e as { error?: string };
			presetError = body?.error ?? 'Umbenennen fehlgeschlagen';
		}
	}

	function deletePreset(p: MetricPreset) {
		deletePresetTarget = p;
	}

	async function confirmDeletePreset() {
		if (!deletePresetTarget) return;
		const p = deletePresetTarget;
		deletePresetTarget = null;
		try {
			await api.del(`/api/metric-presets/${p.id}`);
			presets = removePreset(presets, p.id);
		} catch (e: unknown) {
			const body = e as { error?: string };
			presetError = body?.error ?? 'Löschen fehlgeschlagen';
		}
	}

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
			await api.put('/api/auth/profile', {
				display_name: displayName,
				mail_to: mailTo,
				sms_to: smsTo,
			});
			successMsg = 'Profil gespeichert';
			setTimeout(() => (successMsg = null), 4000);
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			errorMsg = body?.detail ?? body?.error ?? 'Speichern fehlgeschlagen';
		}
	}

	async function connectTelegram() {
		telegramConnecting = true;
		try {
			const resp = await api.get<{ link: string }>('/api/auth/telegram-link');
			window.open(resp.link, '_blank');
			let attempts = 0;
			telegramPollInterval = setInterval(async () => {
				attempts++;
				try {
					const status = await api.get<{ connected: boolean; chat_id_suffix?: string }>(
						'/api/auth/telegram-status'
					);
					if (status.connected) {
						telegramConnected = true;
						telegramChatIdSuffix = status.chat_id_suffix ?? '';
						telegramConnecting = false;
						clearInterval(telegramPollInterval!);
					} else if (attempts >= 20) {
						telegramConnecting = false;
						clearInterval(telegramPollInterval!);
					}
				} catch {
					telegramConnecting = false;
					clearInterval(telegramPollInterval!);
				}
			}, 3000);
		} catch {
			telegramConnecting = false;
		}
	}

	async function disconnectTelegram() {
		await api.put('/api/auth/profile', { telegram_chat_id: '' });
		telegramConnected = false;
		telegramChatIdSuffix = '';
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
		trip_reports_hourly: 'Trip-Checks',
	};

	function deleteAccount() {
		showDeleteAccountDialog = true;
	}

	async function confirmDeleteAccount() {
		showDeleteAccountDialog = false;
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
			<div class="space-y-2">
				<label for="displayName" class="text-sm font-medium">Anzeigename</label>
				<input
					id="displayName"
					name="display_name"
					type="text"
					maxlength="50"
					bind:value={displayName}
					placeholder={data.profile?.id ?? 'Anzeigename'}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
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
							class="shrink-0 inline-flex items-center min-h-[44px] text-sm text-blue-600 hover:underline disabled:opacity-50"
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
				<label for="smsTo" class="block text-sm font-medium">Handynummer (SMS)</label>
				<input
					id="smsTo"
					name="sms_to"
					type="tel"
					bind:value={smsTo}
					placeholder="+49XXXXXXXXXX"
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
				<p class="mt-1 text-xs text-gray-500">Internationales Format, z.B. +49151XXXXXXXX</p>
			</div>

			<div class="space-y-2">
				<label class="text-sm font-medium">Telegram</label>
				{#if telegramConnected}
					<div class="flex items-center gap-3">
						<span class="text-sm text-green-700">Verbunden ({telegramChatIdSuffix})</span>
						<button
							onclick={() => sendTest('telegram')}
							disabled={testStatus.telegram === 'loading'}
							class="shrink-0 inline-flex items-center min-h-[44px] text-sm text-blue-600 hover:underline disabled:opacity-50"
						>
							{testStatus.telegram === 'loading' ? '...' : 'Test senden'}
						</button>
						<button
							onclick={disconnectTelegram}
							class="shrink-0 inline-flex items-center min-h-[44px] text-sm text-destructive hover:underline"
						>
							Trennen
						</button>
					</div>
				{:else}
					<div class="flex items-center gap-3">
						<span class="text-sm text-muted-foreground">Nicht verbunden</span>
						<button
							onclick={connectTelegram}
							disabled={telegramConnecting}
							class="shrink-0 inline-flex items-center min-h-[44px] text-sm text-blue-600 hover:underline disabled:opacity-50"
						>
							{telegramConnecting ? 'Warte auf Verbindung…' : 'Mit Telegram verbinden'}
						</button>
					</div>
				{/if}
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

	<!-- Issue #344 — Wetter-Profile (User-MetricPresets) -->
	<Card.Root data-testid="wetter-profile-card">
		<Card.Header>
			<Card.Title>Wetter-Profile</Card.Title>
			<Card.Description>Deine gespeicherten Metrik-Auswahlen</Card.Description>
		</Card.Header>
		<Card.Content>
			{#if isEmpty(presets)}
				<p data-testid="wetter-profile-empty" class="text-sm text-muted-foreground">
					Du hast noch keine Wetter-Profile angelegt. Speichere ein Profil im Trip-Wetter-Tab.
				</p>
			{:else}
				<div class="space-y-2">
					{#each presets as p (p.id)}
						<div data-testid="wetter-profile-row-{p.id}" class="flex items-center justify-between gap-2 text-sm">
							{#if editingId === p.id}
								<input
									data-testid="wetter-profile-rename-input-{p.id}"
									bind:value={editName}
									onkeydown={(e) => { if (e.key === 'Enter') saveRename(p.id); if (e.key === 'Escape') cancelEdit(); }}
									class="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
								/>
								<div class="flex items-center gap-1">
									<button
										onclick={() => saveRename(p.id)}
										aria-label="Speichern"
										class="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent"
									>
										<CheckIcon class="h-4 w-4" />
									</button>
									<button
										onclick={cancelEdit}
										aria-label="Abbrechen"
										class="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent"
									>
										<XIcon class="h-4 w-4" />
									</button>
								</div>
							{:else}
								<span data-testid="wetter-profile-name-{p.id}" class="font-medium">{p.name}</span>
								<div class="flex items-center gap-2">
									<Badge variant="secondary" data-testid="wetter-profile-count-{p.id}">{metricCountLabel(p)}</Badge>
									{#if showDefaultBadge(p)}
										<Badge variant="secondary" data-testid="wetter-profile-default-{p.id}">Standard</Badge>
									{/if}
									<button
										data-testid="wetter-profile-edit-{p.id}"
										onclick={() => startEdit(p)}
										aria-label="Umbenennen"
										class="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent"
									>
										<PencilIcon class="h-4 w-4" />
									</button>
									<button
										data-testid="wetter-profile-delete-{p.id}"
										onclick={() => deletePreset(p)}
										aria-label="Löschen"
										class="inline-flex h-9 w-9 items-center justify-center rounded-md text-destructive hover:bg-destructive/10"
									>
										<Trash2Icon class="h-4 w-4" />
									</button>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
			{#if presetError}
				<p class="mt-2 text-sm text-destructive">{presetError}</p>
			{/if}
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
				<!-- Nutzerlevel (Issue #1068) — immer sichtbar -->
				<div data-testid="tier" class="mb-4">
					<p class="text-sm font-medium mb-2">Level</p>
					<Badge variant="secondary">{tierLabel(data.profile?.tier)}</Badge>
				</div>

				<!-- Zähler -->
				<div class="space-y-2 mb-4">
					<div class="flex items-center justify-between text-sm">
						<span>Aktive Trips</span>
						<a href="/trips" class="font-medium hover:underline">{data.trips.length}</a>
					</div>
					<div class="flex items-center justify-between text-sm">
						<span>Aktive Abos</span>
						<a href="/compare" class="font-medium hover:underline">{data.subscriptions.filter((s: any) => s.enabled).length}</a>
					</div>
					<div class="flex items-center justify-between text-sm">
						<span>Locations</span>
						<a href="/locations" class="font-medium hover:underline">{data.locations.length}</a>
					</div>
				</div>

				<!-- Benachrichtigungskanäle -->
				<div data-testid="channels" class="mb-4">
					<p class="text-sm font-medium mb-2">Benachrichtigungen</p>
					{#if data.profile && (data.profile.mail_to || data.profile.telegram_chat_id)}
						<div class="flex flex-wrap gap-2">
							{#if data.profile.mail_to}
								<Badge variant="secondary">E-Mail: {data.profile.mail_to}</Badge>
							{/if}
							{#if data.profile.telegram_chat_id}
								<Badge variant="secondary">Telegram: ...{data.profile.telegram_chat_id.slice(-3)}</Badge>
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

	<!-- Preset löschen Dialog -->
	<Dialog.Root
		open={deletePresetTarget !== null}
		onOpenChange={(open) => { if (!open) deletePresetTarget = null; }}
	>
		<Dialog.Content>
			<Dialog.Header>
				<Dialog.Title>Profil löschen</Dialog.Title>
				<Dialog.Description>
					Möchtest du „{deletePresetTarget?.name}" wirklich löschen?
				</Dialog.Description>
			</Dialog.Header>
			<Dialog.Footer>
				<Btn variant="outline" onclick={() => (deletePresetTarget = null)}>Abbrechen</Btn>
				<Btn variant="destructive" onclick={confirmDeletePreset}>Löschen</Btn>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Root>

	<!-- Account löschen Dialog -->
	<Dialog.Root
		open={showDeleteAccountDialog}
		onOpenChange={(open) => { if (!open) showDeleteAccountDialog = false; }}
	>
		<Dialog.Content>
			<Dialog.Header>
				<Dialog.Title>Account löschen</Dialog.Title>
				<Dialog.Description>
					Bist du sicher? Alle deine Daten werden unwiderruflich gelöscht.
				</Dialog.Description>
			</Dialog.Header>
			<Dialog.Footer>
				<Btn variant="outline" onclick={() => (showDeleteAccountDialog = false)}>Abbrechen</Btn>
				<Btn variant="destructive" onclick={confirmDeleteAccount}>Account löschen</Btn>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Root>
</div>
