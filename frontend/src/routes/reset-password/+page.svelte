<script lang="ts">
	import { enhance } from '$app/forms';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
	import { t } from '$lib/i18n';
	let { data, form } = $props();
</script>

<div class="flex min-h-screen items-center justify-center">
	<div class="w-full max-w-sm space-y-4 p-6">
		<div class="space-y-2 text-center">
			<Wordmark size="lg" href="/" />
		</div>
		<h1 class="text-xl font-bold">{$t('auth.reset.titel')}</h1>

		{#if form?.success}
			<div class="rounded-md bg-green-50 p-3 text-sm text-green-800">
				{$t('auth.reset.erfolg')}
			</div>
			<a href="/login" class="block text-sm text-blue-600 hover:underline">{$t('auth.reset.zum_login')}</a>
		{:else}
			<form method="POST" use:enhance class="space-y-3">
				{#if form?.error}
					<div class="rounded-md bg-red-50 p-3 text-sm text-red-800">{form.error}</div>
				{/if}
				<input
					name="username"
					type="text"
					placeholder={$t('auth.feld.username_platzhalter')}
					value={form?.username ?? data.user}
					class="w-full rounded-md border px-3 py-2 text-sm"
					required
				/>
				{#if form?.token || data.token}
					<input name="token" type="hidden" value={form?.token ?? data.token} required />
				{:else}
					<input
						name="token"
						type="text"
						placeholder={$t('auth.reset.token_platzhalter')}
						class="w-full rounded-md border px-3 py-2 text-sm"
						required
					/>
				{/if}
				<input
					name="new_password"
					type="password"
					placeholder={$t('auth.reset.passwort_platzhalter')}
					class="w-full rounded-md border px-3 py-2 text-sm"
					required
					minlength="8"
				/>
				<button type="submit" class="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">
					{$t('auth.reset.knopf')}
				</button>
			</form>
			<a href="/login" class="block text-sm text-muted-foreground hover:underline">{$t('auth.zurueck_login')}</a>
		{/if}
	</div>
</div>
