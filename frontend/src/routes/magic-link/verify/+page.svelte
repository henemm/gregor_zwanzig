<script lang="ts">
	import type { ActionData, PageData } from './$types.js';
	let { form, data }: { form: ActionData; data: PageData } = $props();
</script>

<div class="flex min-h-screen items-center justify-center bg-background">
	<div class="w-full max-w-sm space-y-6 p-6">
		<div class="space-y-2 text-center">
			<h1 class="text-2xl font-bold">Code eingeben</h1>
			<p class="text-muted-foreground text-sm">Gib den 6-stelligen Code aus deiner E-Mail ein</p>
		</div>

		{#if form?.error}
			<div class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
				{form.error}
			</div>
		{/if}

		<form method="POST" class="space-y-4">
			<input type="hidden" name="email" value={form?.email ?? data.email} />
			<div class="space-y-2">
				<label for="code" class="text-sm font-medium">Bestätigungscode</label>
				<input
					id="code"
					name="code"
					type="text"
					inputmode="numeric"
					maxlength="6"
					pattern="[0-9]{6}"
					required
					placeholder="000000"
					class="flex h-12 w-full rounded-md border border-input bg-background px-3 py-2 text-center text-xl font-mono tracking-[0.5em] ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>
			<button
				type="submit"
				class="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
			>
				Anmelden
			</button>
		</form>

		<a href="/magic-link" class="block text-center text-sm text-muted-foreground hover:underline">
			Neuen Code anfordern
		</a>
	</div>
</div>
