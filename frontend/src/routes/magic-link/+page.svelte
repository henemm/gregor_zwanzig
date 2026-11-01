<script lang="ts">
	import type { ActionData } from './$types.js';
	import { t } from '$lib/i18n';
	let { form }: { form: ActionData } = $props();
</script>

<div class="flex min-h-screen items-center justify-center bg-background">
	<div class="w-full max-w-sm space-y-6 p-6">
		<div class="space-y-2 text-center">
			<h1 class="text-2xl font-bold">{$t('auth.magic.titel')}</h1>
			<p class="text-muted-foreground text-sm">{$t('auth.magic.untertitel')}</p>
		</div>

		{#if form?.sent}
			<div class="rounded-md border border-green-300 bg-green-50 p-4 text-sm text-green-800">
				{$t('auth.magic.gesendet')}
			</div>
			<div class="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
				{$t('auth.magic.profil_hinweis')}
			</div>
			<a
				href="/magic-link/verify?email={encodeURIComponent(form.email ?? '')}"
				class="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
			>
				{$t('auth.code.titel')}
			</a>
		{:else}
			{#if form?.error}
				<div class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
					{form.error}
				</div>
			{/if}

			<form method="POST" class="space-y-4">
				<div class="space-y-2">
					<label for="email" class="text-sm font-medium">{$t('auth.feld.email_adresse')}</label>
					<input
						id="email"
						name="email"
						type="email"
						required
						value={form?.email ?? ''}
						class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					/>
				</div>
				<button
					type="submit"
					class="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
				>
					{$t('auth.magic.knopf')}
				</button>
			</form>
		{/if}

		<a href="/login" class="block text-center text-sm text-muted-foreground hover:underline">
			{$t('auth.zurueck_login')}
		</a>
	</div>
</div>
