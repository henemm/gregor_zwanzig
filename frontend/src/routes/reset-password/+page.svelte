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
			<div class="rounded-md border border-[var(--g-ok-fg)] bg-[var(--g-ok-bg)] p-3 text-sm text-[var(--g-ok-fg)]">
				{$t('auth.reset.erfolg')}
			</div>
			<a href="/login" class="block py-3 text-sm text-[var(--g-info)] hover:underline">{$t('auth.reset.zum_login')}</a>
		{:else}
			<form method="POST" use:enhance class="space-y-3">
				{#if form?.error}
					<div class="rounded-md border border-[var(--g-danger-fg)] bg-[var(--g-danger-bg)] p-3 text-sm text-[var(--g-danger-fg)]">{form.error}</div>
				{/if}
				<input name="username" type="hidden" value={form?.username ?? data.user} />
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
				<!-- Issue #2961 (ADR-0115): Vorgabe aktiv. Die Marke zeigt der Action,
				     dass die Auswahl mitgeschickt wurde (ein abgewaehltes Kaestchen fehlt im Formular). -->
				<input type="hidden" name="andere_zugangswege_gewaehlt" value="1" />
				<label class="flex items-start gap-2 text-sm">
					<input
						type="checkbox"
						name="remove_other_access"
						value="1"
						checked
						class="mt-1"
						data-testid="reset-remove-other-access"
					/>
					<span>
						{$t('auth.reset.andere_zugangswege')}
						<span class="block text-muted-foreground">{$t('auth.reset.andere_zugangswege_hinweis')}</span>
					</span>
				</label>
				<button type="submit" class="w-full rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">
					{$t('auth.reset.knopf')}
				</button>
			</form>
			<a href="/login" class="block py-3 text-sm text-muted-foreground hover:underline">{$t('auth.zurueck_login')}</a>
		{/if}
	</div>
</div>
