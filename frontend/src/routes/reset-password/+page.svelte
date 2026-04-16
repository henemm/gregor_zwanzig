<script lang="ts">
	import { enhance } from '$app/forms';
	let { data, form } = $props();
</script>

<div class="flex min-h-screen items-center justify-center">
	<div class="w-full max-w-sm space-y-4 p-6">
		<h1 class="text-xl font-bold">Neues Passwort setzen</h1>

		{#if form?.success}
			<div class="rounded-md bg-green-50 p-3 text-sm text-green-800">
				Passwort wurde erfolgreich geändert.
			</div>
			<a href="/login" class="block text-sm text-blue-600 hover:underline">Zum Login</a>
		{:else}
			<form method="POST" use:enhance class="space-y-3">
				{#if form?.error}
					<div class="rounded-md bg-red-50 p-3 text-sm text-red-800">{form.error}</div>
				{/if}
				<input
					name="username"
					type="text"
					placeholder="Username"
					value={form?.username ?? data.user}
					class="w-full rounded-md border px-3 py-2 text-sm"
					required
				/>
				<input
					name="token"
					type="text"
					placeholder="Reset-Token"
					value={form?.token ?? data.token}
					class="w-full rounded-md border px-3 py-2 text-sm"
					required
				/>
				<input
					name="new_password"
					type="password"
					placeholder="Neues Passwort (min. 8 Zeichen)"
					class="w-full rounded-md border px-3 py-2 text-sm"
					required
					minlength="8"
				/>
				<button type="submit" class="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">
					Passwort ändern
				</button>
			</form>
			<a href="/login" class="block text-sm text-muted-foreground hover:underline">Zurück zum Login</a>
		{/if}
	</div>
</div>
