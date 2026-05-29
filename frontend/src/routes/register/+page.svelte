<script lang="ts">
	import type { ActionData } from './$types.js';

	let { form, data }: { form: ActionData; data: { googleEnabled: boolean } } = $props();
</script>

<div class="flex min-h-screen items-center justify-center bg-background">
	<div class="w-full max-w-sm space-y-6 p-6">
		<div class="space-y-2 text-center">
			<h1 class="text-2xl font-bold">Konto erstellen</h1>
			<p class="text-muted-foreground text-sm">Benutzerdaten eingeben</p>
		</div>

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

			<div class="space-y-2">
				<label for="confirmPassword" class="text-sm font-medium">Passwort bestätigen</label>
				<input
					id="confirmPassword"
					name="confirmPassword"
					type="password"
					required
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			<button
				type="submit"
				class="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			>
				Konto erstellen
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
				Mit Google registrieren
			</a>
		{/if}
		<a href="/login" class="block text-center text-sm text-muted-foreground hover:underline">
			Bereits registriert? Anmelden
		</a>
	</div>
</div>
