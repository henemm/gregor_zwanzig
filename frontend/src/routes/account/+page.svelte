<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import { api } from '$lib/api.js';

	let { data } = $props();

	let mailTo = $state(data.profile?.mail_to ?? '');
	let signalPhone = $state(data.profile?.signal_phone ?? '');
	let telegramChatId = $state(data.profile?.telegram_chat_id ?? '');
	let successMsg = $state<string | null>(null);
	let errorMsg = $state<string | null>(null);

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
				mail_to: mailTo,
				signal_phone: signalPhone,
				telegram_chat_id: telegramChatId,
			});
			successMsg = 'Profil gespeichert';
			setTimeout(() => (successMsg = null), 4000);
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			errorMsg = body?.detail ?? body?.error ?? 'Speichern fehlgeschlagen';
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
</div>
