<script lang="ts">
	import { page } from '$app/stores';
	import type { ActionData } from './$types.js';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';

	let { form }: { form: ActionData } = $props();
	const registered = $derived($page.url.searchParams.get('registered') === '1');
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
					value={form?.username ?? ''}
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
		<div class="space-y-2">
			<a href="/register" class="block text-center text-sm text-muted-foreground hover:underline">
				Noch kein Konto? Konto erstellen
			</a>
			<a href="/forgot-password" class="block text-center text-sm text-muted-foreground hover:underline">
				Passwort vergessen?
			</a>
		</div>
	</div>
</div>
