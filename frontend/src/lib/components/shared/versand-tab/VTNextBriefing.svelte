<script lang="ts">
	// VTNextBriefing — Issue #1969 (AC-16/AC-17/AC-19/AC-22).
	// Geteilter Baustein des Versand-Reiters für Trip (context="route") UND
	// Ortsvergleich (context="vergleich") — es gibt bewusst keine
	// Compare-eigene Pendant-Komponente. Zeigt den Backend-Wert
	// (GET /api/next-briefings) über formatNextBriefing; nicht geladen bzw.
	// Fehler ⇒ „—", nie eine erfundene Zeit.
	import { api } from '$lib/api.js';
	import { formatNextBriefing, type NextBriefing } from './nextBriefingText.ts';
	import { erstelleNaechstesBriefingLader } from './naechstesBriefingLader.svelte.ts';
	import { t, locale } from '$lib/i18n';

	interface Props {
		/** Backend-Wert von aussen; gesetzt ⇒ kein eigener Abruf. */
		nextBriefing?: NextBriefing | null;
		context?: 'route' | 'vergleich';
		/** Gespeichertes Objekt (Trip- bzw. Vergleichs-ID); fehlt (Anlege-Seite) ⇒ „—". */
		id?: string;
		/** Jede Aenderung laedt neu — der Versand-Reiter reicht `saveController.savedAt`
		 *  durch, das nur ein ERFOLGREICHES Speichern stempelt (AC-18): ungespeicherte
		 *  Eingaben erscheinen nie als Versandzeit. */
		reloadKey?: unknown;
	}
	let { nextBriefing, context = 'route', id, reloadKey }: Props = $props();

	// Laden, Neuladen bei `reloadKey` und Schutz gegen veraltete Antworten: geteilter Lader.
	const lader = erstelleNaechstesBriefingLader(
		() => ({ context, id, neuLaden: reloadKey, extern: nextBriefing }),
		(p) => api.get(p)
	);

	// #2655 (F6): formatNextBriefing liest die Sprache per tr(); `$locale` macht den Wechsel reaktiv.
	const wert = $derived.by(() => (void $locale, formatNextBriefing(lader.wert, context)));
</script>

<div class="vt-next-briefing" data-testid="vt-next-briefing">
	<span class="vt-next-briefing-label">{$t('versand.naechstes.titel')}</span>
	<span class="vt-next-briefing-value">{wert}</span>
</div>

<style>
	.vt-next-briefing {
		display: flex;
		align-items: baseline;
		gap: 10px;
		flex-wrap: wrap;
		font-size: 14px;
		color: var(--g-ink);
	}
	.vt-next-briefing-label {
		font-family: var(--g-font-mono);
		font-size: 11px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--g-ink-3);
	}
	.vt-next-briefing-value {
		font-weight: 600;
	}
</style>
