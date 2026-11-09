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
		<h1 class="text-xl font-bold">{$t('auth.bestaetigen.titel')}</h1>

		{#if form?.success}
			<div class="rounded-md border border-[var(--g-ok-fg)] bg-[var(--g-ok-bg)] p-3 text-sm text-[var(--g-ok-fg)]">
				{$t('auth.bestaetigen.erfolg')}
			</div>
			<a href="/" class="block text-sm text-[var(--g-info)] hover:underline">{$t('auth.bestaetigen.zur_app')}</a>
		{:else if (form?.user ?? data.user) && (form?.token ?? data.token)}
			<form method="POST" use:enhance class="space-y-3">
				{#if form?.error}
					<div class="rounded-md border border-[var(--g-danger-fg)] bg-[var(--g-danger-bg)] p-3 text-sm text-[var(--g-danger-fg)]">{form.error}</div>
				{/if}
				<input name="user" type="hidden" value={form?.user ?? data.user} />
				<input name="token" type="hidden" value={form?.token ?? data.token} />
				<button type="submit" class="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">
					{$t('auth.bestaetigen.titel')}
				</button>
			</form>
		{:else}
			<div class="rounded-md border border-[var(--g-danger-fg)] bg-[var(--g-danger-bg)] p-3 text-sm text-[var(--g-danger-fg)]">
				{$t('auth.bestaetigen.unvollstaendig')}
			</div>
		{/if}
	</div>
</div>
