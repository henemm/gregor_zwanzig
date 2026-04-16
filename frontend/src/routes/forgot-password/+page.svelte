<script lang="ts">
	import { enhance } from '$app/forms';
	let { form } = $props();
</script>

<div class="flex min-h-screen items-center justify-center">
	<div class="w-full max-w-sm space-y-4 p-6">
		<h1 class="text-xl font-bold">Passwort vergessen</h1>

		{#if form?.success}
			<div class="rounded-md bg-green-50 p-3 text-sm text-green-800">
				Falls der Account existiert, wurde ein Reset-Link generiert. Bitte den Server-Admin kontaktieren.
			</div>
			<a href="/login" class="block text-sm text-blue-600 hover:underline">Zurück zum Login</a>
		{:else}
			<form method="POST" use:enhance class="space-y-3">
				{#if form?.error}
					<div class="rounded-md bg-red-50 p-3 text-sm text-red-800">{form.error}</div>
				{/if}
				<input
					name="username"
					type="text"
					placeholder="Username"
					value={form?.username ?? ''}
					class="w-full rounded-md border px-3 py-2 text-sm"
					required
				/>
				<button type="submit" class="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">
					Reset anfordern
				</button>
			</form>
			<a href="/login" class="block text-sm text-muted-foreground hover:underline">Zurück zum Login</a>
		{/if}
	</div>
</div>
