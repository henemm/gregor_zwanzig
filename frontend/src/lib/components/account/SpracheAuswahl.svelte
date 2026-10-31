<script lang="ts" module>
	// Issue #2648 (i18n S3) — Spracheinstellung im Konto. Gespeichert wird NUR
	// `{ language }` (keine Adressfelder, also keine Bestaetigungsmail); die
	// user_id kommt in Go aus der eigenen Sitzung. Erst nach Erfolg wechselt
	// die Oberflaeche, bei Fehler bleibt sie in der bisherigen Sprache.
	import { api } from '$lib/api.js';
	import { invalidateAll } from '$app/navigation';
	import { locale, tr, type Lang } from '$lib/i18n';

	export async function speichereSprache(neu: Lang): Promise<{ meldung: string; fehler: string }> {
		try {
			await api.put('/api/auth/profile', { language: neu });
		} catch {
			return { meldung: '', fehler: tr('konto.sprache.fehler') };
		}
		locale.set(neu);
		await invalidateAll();
		return { meldung: tr('konto.sprache.gespeichert'), fehler: '' };
	}
</script>

<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import { t, locale as sprache } from '$lib/i18n';

	let meldung = $state('');
	let fehler = $state('');
	let laeuft = $state(false);

	async function geaendert(e: Event) {
		const auswahl = e.currentTarget as HTMLSelectElement;
		const wert = auswahl.value;
		if (wert !== 'de' && wert !== 'en') return;
		laeuft = true;
		({ meldung, fehler } = await speichereSprache(wert));
		laeuft = false;
		// Fehler: Auswahl zeigt wieder die weiterhin gueltige Sprache.
		if (fehler) auswahl.value = $sprache;
	}
</script>

<Card.Root data-testid="sprache-card">
	<Card.Header>
		<Card.Title>{$t('konto.sprache.titel')}</Card.Title>
	</Card.Header>
	<Card.Content class="space-y-2">
		<select
			id="sprache"
			aria-label={$t('konto.sprache.titel')}
			value={$sprache}
			disabled={laeuft}
			onchange={geaendert}
			data-testid="sprache-auswahl"
			class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
		>
			<option value="de">{$t('konto.sprache.option_de')}</option>
			<option value="en">{$t('konto.sprache.option_en')}</option>
		</select>
		{#if meldung}
			<p class="text-sm" role="status" data-testid="sprache-gespeichert">{meldung}</p>
		{/if}
		{#if fehler}
			<p class="text-sm" role="alert" style="color: var(--g-bad);" data-testid="sprache-fehler">{fehler}</p>
		{/if}
	</Card.Content>
</Card.Root>
