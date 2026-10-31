<script lang="ts">
	// Issue #2648 (i18n S3) — Besucher-Umschalter DE | EN (Startseite, Anmeldung,
	// Registrierung). Ohne JavaScript nutzbar: echtes Formular an POST /lang,
	// das Cookie gz_lang setzt und auf die Seite zurueckleitet. Angemeldete
	// waehlen die Sprache im Konto (kein Umschalter in der Shell).
	import { locale, t, type Lang } from '$lib/i18n';

	const SPRACHEN: Lang[] = ['de', 'en'];
</script>

<form
	method="POST"
	action="/lang"
	class="sprach-umschalter"
	role="group"
	aria-label={$t('konto.sprache.umschalter_label')}
	data-testid="sprach-umschalter"
>
	{#each SPRACHEN as l (l)}
		<button
			type="submit"
			name="lang"
			value={l}
			aria-current={l === $locale ? 'true' : undefined}>{l.toUpperCase()}</button
		>
	{/each}
</form>

<style>
	/* Hoher Kontrast (Design-Leitprinzip): aktive Sprache vollflaechig in Tinte. */
	.sprach-umschalter {
		display: inline-flex;
		border: 1px solid var(--g-ink);
		border-radius: var(--g-radius-sm, 4px);
		overflow: hidden;
	}
	button {
		min-width: 44px;
		min-height: 36px;
		padding: 0 10px;
		font: inherit;
		font-size: 13px;
		font-weight: 600;
		letter-spacing: 0.04em;
		background: var(--g-paper);
		color: var(--g-ink);
		border: 0;
		cursor: pointer;
	}
	button + button {
		border-left: 1px solid var(--g-ink);
	}
	button[aria-current='true'] {
		background: var(--g-ink);
		color: var(--g-paper);
	}
	button:focus-visible {
		outline: 2px solid var(--g-accent);
		outline-offset: -2px;
	}
</style>
