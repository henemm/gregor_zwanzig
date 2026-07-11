<script lang="ts">
	import { enhance } from '$app/forms';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
	let { data, form } = $props();
</script>

<div class="flex min-h-screen items-center justify-center">
	<div class="w-full max-w-sm space-y-4 p-6">
		<div class="space-y-2 text-center">
			<Wordmark size="lg" href="/" />
		</div>
		<h1 class="text-xl font-bold">E-Mail-Adresse bestätigen</h1>

		{#if form?.success}
			<div class="rounded-md bg-green-50 p-3 text-sm text-green-800">
				Deine E-Mail-Adresse wurde bestätigt. Du erhältst ab jetzt wieder Wetter-Briefings an diese
				Adresse.
			</div>
			<a href="/" class="block text-sm text-blue-600 hover:underline">Zur App</a>
		{:else if (form?.user ?? data.user) && (form?.token ?? data.token)}
			<form method="POST" use:enhance class="space-y-3">
				{#if form?.error}
					<div class="rounded-md bg-red-50 p-3 text-sm text-red-800">{form.error}</div>
				{/if}
				<input name="user" type="hidden" value={form?.user ?? data.user} />
				<input name="token" type="hidden" value={form?.token ?? data.token} />
				<button type="submit" class="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">
					E-Mail-Adresse bestätigen
				</button>
			</form>
		{:else}
			<div class="rounded-md bg-red-50 p-3 text-sm text-red-800">
				Dieser Bestätigungslink ist unvollständig. Bitte öffne den Link aus der E-Mail erneut.
			</div>
		{/if}
	</div>
</div>
