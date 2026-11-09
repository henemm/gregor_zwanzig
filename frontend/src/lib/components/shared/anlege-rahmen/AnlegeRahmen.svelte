<script lang="ts">
	// Issue #2837 S2 (Epic #2345, ADR-0110) — geteilter Anlege-Rahmen für /trips/new
	// (`context="route"`) und /compare/new (`context="vergleich"`).
	// Spec: docs/specs/modules/rework_2837_s2_anlege_rahmen.md
	//
	// EIN Markup, keine Verzweigung nach `context`: es wählt nur Textschlüssel, Elternteil-Link,
	// Datenmarke (`data-kind`) und Testid-Präfix. Desktop-Rahmen: Breadcrumb (Elternteil Link,
	// Kind kein Link), Eyebrow, Titel, Fortschritt, Inhalt, Fuß (Abbrechen links; Hinweis,
	// Standardwerte, Hauptaktion rechts). Der mobile Kopf und Fuß bleiben in den Editoren.
	// Fachlich Verschiedenes (Whitelist) kommt über Props und Snippets. Keine API-Aufrufe.
	// #2837 S2b: der Fortschritt ist Teil des Rahmens (AnlegeFortschritt, variante="desktop");
	// der frühere Snippet-Slot `fortschritt` entfällt.
	import type { Snippet } from 'svelte';
	import { Btn, Eyebrow, TopoBg } from '$lib/components/atoms';
	import EditorStickyFooter from '$lib/components/shared/EditorStickyFooter.svelte';
	import AnlegeFortschritt from './AnlegeFortschritt.svelte';
	import { t, type MessageKey } from '$lib/i18n';

	type Context = 'route' | 'vergleich';

	interface Props {
		context: Context;
		/** Eingegebener Name (Titel); leer ⇒ Katalogtext „kein Name". */
		name: string;
		/** Trip: Abbrechen ohne Autosave (Editor setzt intentionalCancel). Gesetzt ⇒ Knopf statt Link. */
		onCancel?: () => void;
		/** Ziel von „Abbrechen", wenn kein `onCancel` gesetzt ist (Vergleich). */
		cancelHref: string;
		abschlussLabel: string;
		/** testid der Hauptaktion (Trip `trip-new-save-btn`, Vergleich `compare-editor-activate`). */
		abschlussTestid: string;
		canFinish: boolean;
		onFinish: () => void;
		/** `tn` | `cm` ⇒ `${testidPrefix}-desktop-footer`, `${testidPrefix}-desktop-breadcrumb`. */
		testidPrefix: string;
		navClearance?: boolean;
		hinweis?: Snippet;
		standardwerte?: Snippet;
		/** #2837 S2b: Schritt-Kennungen (PROGRESS_STEPS) für den Fortschritt im Kopf. */
		steps: readonly string[];
		/** #2837 S2b: Zahl erledigter Schritte (Ergebnis von `progressCount`). */
		done: number;
		/** #2837 S2b F003: Menge erledigter Schritte — Segmentfarbe je Schritt. */
		erledigt?: ReadonlySet<string>;
		/** #2837 S2b: aktiver Schritt — nur aria-current, keine Optik. */
		aktiv?: string;
		children?: Snippet;
	}

	let {
		context, name, onCancel, cancelHref, abschlussLabel, abschlussTestid, canFinish, onFinish,
		testidPrefix, navClearance = false, hinweis, standardwerte, steps, done, erledigt, aktiv, children
	}: Props = $props();

	// Whitelist Nr. 5: Texte und Elternteil-Link je Art — reine Datentabelle.
	const ART: Record<Context, { eltern: MessageKey; neu: MessageKey; href: string }> = {
		route: { eltern: 'listen.trips.titel', neu: 'trip.anlegen.neuer_trip', href: '/trips' },
		vergleich: { eltern: 'listen.vergleiche.titel', neu: 'vergleich.neu.neuer_vergleich', href: '/compare' }
	};
	// #2837 S2b: Testid des Desktop-Fortschritts je Art (bestehende Kennungen bleiben erhalten).
	const FORTSCHRITT_TESTID: Record<Context, string> = { route: 'trip-new-progress', vergleich: 'compare-editor-progress' };
	const art = $derived(ART[context]);

	// Trip: der Pfad-Link ruft Abbrechen (kein Autosave); die Adresse bleibt als href erhalten.
	function elternKlick(e: MouseEvent) {
		if (!onCancel) return;
		e.preventDefault();
		onCancel();
	}
</script>

<div class="anlege-rahmen" data-kind={context}>
	<TopoBg opacity={0.12}>
		<div class="ar-kopf" data-testid={`${testidPrefix}-desktop-breadcrumb`}>
			<div class="ar-pfad">
				<a href={art.href} class="ar-pfad-link" onclick={elternKlick}>{$t(art.eltern)}</a>
				<span class="ar-trenner">/</span>
				<span class="ar-kind">{$t(art.neu)}</span>
			</div>
		</div>
		<div class="ar-held">
			<Eyebrow>{$t(art.neu)}</Eyebrow>
			<h1 class="ar-titel" class:ar-titel-leer={!name.trim()}>{name.trim() || $t('trip.anlegen.kein_name')}</h1>
			<AnlegeFortschritt {steps} {done} {erledigt} {aktiv} variante="desktop" testidPrefix={FORTSCHRITT_TESTID[context]} />
		</div>
	</TopoBg>

	<div class="ar-inhalt">
		{@render children?.()}
	</div>

	<EditorStickyFooter {context} {navClearance} testid={`${testidPrefix}-desktop-footer`}>
		<div class="ar-fuss">
			<Btn variant="ghost" size="sm" href={onCancel ? undefined : cancelHref} onclick={onCancel}>{$t('aktionen.abbrechen')}</Btn>
			<div class="ar-fuss-rechts">
				{@render hinweis?.()}
				{@render standardwerte?.()}
				<Btn variant="primary" size="sm" data-testid={abschlussTestid} disabled={!canFinish} onclick={onFinish}>{abschlussLabel}</Btn>
			</div>
		</div>
	</EditorStickyFooter>
</div>

<style>
	.anlege-rahmen {
		position: relative;
		flex: 1 0 auto;
		display: flex;
		flex-direction: column;
	}
	.ar-kopf {
		position: relative;
		padding: 14px 40px;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.ar-pfad {
		font-family: var(--g-font-mono);
		font-size: 11px;
		letter-spacing: 0.06em;
		color: var(--g-ink-3);
	}
	.ar-pfad-link {
		color: inherit;
		text-decoration: none;
	}
	.ar-pfad-link:hover,
	.ar-pfad-link:focus-visible {
		color: var(--g-ink);
		text-decoration: underline;
	}
	.ar-trenner {
		margin: 0 8px;
	}
	.ar-kind {
		color: var(--g-ink);
	}
	.ar-held {
		position: relative;
		padding: 20px 40px 14px;
	}
	.ar-titel {
		font-size: 32px;
		font-weight: 600;
		letter-spacing: -0.02em;
		margin: 4px 0 0;
		line-height: 1.1;
		color: var(--g-ink);
	}
	.ar-titel-leer {
		color: var(--g-ink-3);
	}
	.ar-inhalt {
		flex: 1 0 auto;
	}
	.ar-fuss {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
	}
	.ar-fuss-rechts {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-left: auto;
	}
</style>
