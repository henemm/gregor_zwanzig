<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import type { ActionData } from './$types.js';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
	import { isWebAuthnSupported, loginWithPasskey } from '$lib/passkey';

	let { form, data }: { form: ActionData; data: { googleEnabled: boolean } } = $props();
	const registered = $derived($page.url.searchParams.get('registered') === '1');

	// Issue #450 — Passkey-Login
	let webAuthnSupported = $state(false);
	let username = $state(form?.username ?? '');
	let passkeyError = $state<string | null>(null);
	let passkeyBusy = $state(false);

	onMount(() => {
		webAuthnSupported = isWebAuthnSupported();
	});

	async function handlePasskey() {
		passkeyError = null;
		if (!username) return;
		passkeyBusy = true;
		try {
			await loginWithPasskey(username);
			// loginWithPasskey already redirects on success.
		} catch (e: unknown) {
			const err = e as { name?: string; message?: string };
			if (err?.name === 'NotAllowedError') {
				passkeyError = 'Anmeldung abgebrochen.';
			} else if (err?.name === 'TimeoutError') {
				passkeyError = 'Zeitüberschreitung. Bitte erneut versuchen.';
			} else {
				passkeyError = 'Kein passender Passkey gefunden.';
			}
		} finally {
			passkeyBusy = false;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-background">
	<div class="w-full max-w-sm space-y-6 p-6">
		<div class="space-y-2 text-center">
			<Wordmark size="lg" href="/" />
			<p class="text-muted-foreground text-sm">Anmelden um fortzufahren</p>
		</div>

		{#if registered}
			<div class="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-800">
				Konto erfolgreich erstellt. Bitte melde dich an.
			</div>
		{/if}

		{#if form?.error}
			<div class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
				{form.error}
			</div>
		{/if}

		<form method="POST" class="space-y-4">
			<div class="space-y-2">
				<label for="username" class="text-sm font-medium">Benutzername</label>
				<input
					id="username"
					name="username"
					type="text"
					required
					bind:value={username}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			<div class="space-y-2">
				<label for="password" class="text-sm font-medium">Passwort</label>
				<input
					id="password"
					name="password"
					type="password"
					required
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			<button
				type="submit"
				class="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			>
				Anmelden
			</button>
		</form>
		{#if data.googleEnabled}
			<div class="relative">
				<div class="absolute inset-0 flex items-center">
					<span class="w-full border-t border-input"></span>
				</div>
				<div class="relative flex justify-center text-xs uppercase">
					<span class="bg-background px-2 text-muted-foreground">oder</span>
				</div>
			</div>
			<a
				href="/api/auth/google/init"
				class="inline-flex h-10 w-full items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground ring-offset-background hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			>
				Mit Google anmelden
			</a>
		{/if}

		{#if webAuthnSupported}
			<div class="space-y-2 pt-2">
				<div class="flex items-center gap-3 text-xs text-muted-foreground">
					<span class="h-px flex-1 bg-border"></span>
					<span>oder</span>
					<span class="h-px flex-1 bg-border"></span>
				</div>
				<button
					type="button"
					data-testid="login-passkey-btn"
					disabled={!username || passkeyBusy}
					onclick={handlePasskey}
					class="inline-flex h-10 w-full items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium ring-offset-background hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				>
					{passkeyBusy ? 'Verbinde…' : 'Mit Passkey anmelden'}
				</button>
				{#if passkeyError}
					<p class="text-sm text-destructive">{passkeyError}</p>
				{/if}
			</div>
		{/if}

		<div class="space-y-2">
			<a href="/register" class="block text-center text-sm text-muted-foreground hover:underline">
				Noch kein Konto? Konto erstellen
			</a>
			<a href="/forgot-password" class="block text-center text-sm text-muted-foreground hover:underline">
				Passwort vergessen?
			</a>
			<a href="/magic-link" class="block text-center text-sm text-muted-foreground hover:underline">
				Mit E-Mail-Code anmelden
			</a>
		</div>
	</div>
</div>
