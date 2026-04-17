<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import { api } from '$lib/api.js';

	let { data } = $props();

	let mailTo = $state(data.profile?.mail_to ?? '');
	let signalPhone = $state(data.profile?.signal_phone ?? '');
	let signalApiKey = $state('');
	let telegramChatId = $state(data.profile?.telegram_chat_id ?? '');
	let successMsg = $state<string | null>(null);
	let errorMsg = $state<string | null>(null);
	let deleteErrorMsg = $state<string | null>(null);

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
				<input
					id="mailTo"
					name="mail_to"
					type="email"
					bind:value={mailTo}
					placeholder="z.B. dein@email.com"
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			<div class="space-y-2">
				<label for="signalPhone" class="text-sm font-medium">Signal-Nummer</label>
				<input
					id="signalPhone"
					name="signal_phone"
					type="text"
					bind:value={signalPhone}
					placeholder="z.B. +43664..."
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
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
				<input
					id="telegramChatId"
					name="telegram_chat_id"
					type="text"
					bind:value={telegramChatId}
					placeholder="z.B. 123456789"
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
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
