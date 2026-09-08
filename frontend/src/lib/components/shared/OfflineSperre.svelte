<script lang="ts">
	// Bearbeitungssperre ohne Netz (Issue #2131, AC-9/AC-10/AC-11).
	//
	// Warum die Sperre am DOM durchgesetzt wird und nicht als Prop durch jeden
	// Baum gereicht: eine offline sichtbare, aber ungesperrte Schaltflaeche ist
	// genau das „scheinbar bedienbar", das das Ticket ausschliesst. Das
	// Sperr-Inventar der beiden vorgehaltenen Ansichten umfasst mehrere Dutzend
	// Bedienelemente in verschachtelten Bausteinen; ein durchgereichtes Prop
	// waere an jeder einzelnen Stelle vergessbar, und jede kuenftige Flaeche
	// waere erneut vergessbar. Hier ist die Zusicherung an der Stelle
	// durchgesetzt, an der sie WIRKT — am ausgelieferten Bedienelement.
	//
	// Ausgenommen sind ausschliesslich Elemente, die NICHT schreiben:
	// Reiter (`role="tab"`) und ausdrueckliche Ausnahmen. Reiter zu sperren
	// hiesse, die vorgehaltene Ansicht offline halb unlesbar zu machen.

	import { onMount } from 'svelte';
	import { verbindung } from '$lib/stores/verbindung.svelte';
	import { deriveOfflineGate } from './offlineGate.ts';

	/** Merker an Elementen, die DIESE Sperre gesperrt hat (und nur die). */
	const MERKER = 'data-gz-offline-gesperrt';

	/** Merker an der Bedien-Gruppe, die ihre Begruendung traegt (AC-9). */
	const GRUPPE = 'data-gz-sperr-gruppe';

	/** Der Begruendungstext AN der Bedien-Gruppe. */
	const GRUND = 'data-gz-offline-grund';

	/** Schmaler als das darf eine Gruppe nicht sein, sonst traegt sie den Satz nicht. */
	const MINDESTBREITE = 160;

	/** Blaettern und Lesen bleiben moeglich — sie schreiben nichts. */
	const AUSNAHME = '[role="tab"], [data-offline-erlaubt]';

	const gate = $derived(
		deriveOfflineGate({ offline: verbindung.offline, ausSpeicher: verbindung.ausSpeicher })
	);

	type Schaltflaeche = HTMLElement & { disabled?: boolean };

	function flaechen(): Schaltflaeche[] {
		const treffer = document.querySelectorAll<Schaltflaeche>(
			'main button, main input, main select, main textarea'
		);
		return [...treffer].filter((el) => !el.matches(AUSNAHME) && !el.closest('[data-offline-erlaubt]'));
	}

	/**
	 * Die Bedien-Gruppe eines gesperrten Elements: sein unmittelbarer Container
	 * — die Segmentleiste einer Metrik-Zeile, die Kanal-Zeile, die Knopfleiste
	 * eines Karten-Abschnitts.
	 *
	 * Bewusst NICHT der naechste Block-Vorfahr: der ist in dieser Oberflaeche
	 * regelmaessig die ganze Karte, und der Hinweis landete dann am Ende einer
	 * langen Tabelle — live gemessen 1429px vom erklaerten Knopf entfernt und
	 * damit ausser Sicht, also genau der Zustand, den AC-9 („jeweils") und
	 * Abschnitt H („das gesperrte Element traegt SEINE Begruendung")
	 * ausschliessen. Ein Container mit mehreren Bedienelementen bekommt genau
	 * EINEN Hinweis; denselben Satz je Schaltflaeche zu wiederholen waere
	 * unlesbar und verdeckte die Elemente, die er erklaert.
	 */
	function gruppeVon(el: Element): HTMLElement | null {
		let gruppe = el.parentElement;
		let stufen = 0;
		// Ein Container, der kaum breiter ist als das Bedienelement selbst (das
		// Kaestchen einer Checkbox, ein Symbolknopf), kann den Satz nicht
		// aufnehmen — dort stuende er als schmale Spalte ueber der Beschriftung.
		// In diesem Fall eine Ebene hoeher, aber hoechstens vier.
		while (
			gruppe &&
			gruppe.parentElement &&
			gruppe !== document.body &&
			gruppe.clientWidth < MINDESTBREITE &&
			stufen < 4
		) {
			gruppe = gruppe.parentElement;
			stufen += 1;
		}
		if (!gruppe || gruppe === document.body) return null;
		return gruppe;
	}

	/** AC-9: „tragen JEWEILS eine sichtbare Begruendung" — je Bedien-Gruppe eine. */
	function gruendeSetzen(text: string): void {
		for (const el of document.querySelectorAll(`main [${MERKER}]`)) {
			// Schnellweg: liegt an der Gruppe dieses Elements schon ein Grund, ist
			// nichts zu tun — spart im Dauertakt den Aufstieg samt Breitenmessung.
			const bekannt = el.closest(`[${GRUPPE}]`);
			if (bekannt?.querySelector(`:scope > [${GRUND}]`)) continue;
			const gruppe = gruppeVon(el);
			if (!gruppe || gruppe.querySelector(`:scope > [${GRUND}]`)) continue;
			gruppe.setAttribute(GRUPPE, '');
			const knoten = document.createElement('p');
			knoten.setAttribute(GRUND, '');
			// Nicht selbst wieder Gegenstand der Sperre werden (er schreibt nichts).
			knoten.setAttribute('data-offline-erlaubt', '');
			knoten.textContent = text;
			gruppe.append(knoten);
		}
	}

	function gruendeEntfernen(): void {
		for (const el of document.querySelectorAll(`[${GRUND}]`)) el.remove();
		for (const el of document.querySelectorAll(`[${GRUPPE}]`)) el.removeAttribute(GRUPPE);
	}

	function durchsetzen(gesperrt: boolean): void {
		for (const el of flaechen()) {
			if (gesperrt) {
				// Bereits von der Anwendung selbst gesperrte Elemente NICHT
				// anfassen — sonst gaebe die Entsperrung sie faelschlich frei.
				if (el.disabled === true) continue;
				el.setAttribute(MERKER, '');
				el.disabled = true;
			} else if (el.hasAttribute(MERKER)) {
				el.removeAttribute(MERKER);
				el.disabled = false;
			}
		}
		if (gesperrt) gruendeSetzen(gate.kurz ?? '');
		else gruendeEntfernen();
	}

	onMount(() => {
		verbindung.starte();
		// Nachgereichte Bedienelemente (Reiterwechsel, Dialoge) muessen dieselbe
		// Sperre erben. Beobachtet werden nur Knoten-Aenderungen: das Setzen von
		// `disabled` ist eine Attribut-Aenderung und wuerde sich sonst selbst
		// ausloesen.
		const beobachter = new MutationObserver(() => {
			if (gate.disabled) durchsetzen(true);
		});
		beobachter.observe(document.body, { childList: true, subtree: true });
		// Sicherheitsnetz gegen Bausteine, die ihr `disabled` selbst neu setzen
		// (Attribut-Aenderung, vom Beobachter oben bewusst nicht erfasst).
		const takt = setInterval(() => {
			if (gate.disabled) durchsetzen(true);
		}, 300);
		return () => {
			beobachter.disconnect();
			clearInterval(takt);
		};
	});

	$effect(() => {
		durchsetzen(gate.disabled);
		// Der Schreibweg selbst muss die Sperre kennen (api.ts) — ein gesperrtes
		// Bedienelement kann von aussen trotzdem ein Ereignis erhalten.
		window.dispatchEvent(
			new CustomEvent('gz-schreibsperre', { detail: { gesperrt: gate.disabled } })
		);
	});
</script>

{#if gate.disabled}
	<!-- `data-gz-offline-band`: das Band steht AUSSERHALB von <main> und braucht
	     deshalb die mobile Kompensation der fixierten Kopfleiste selbst
	     (app.css, Abschnitt „Offline-Baender"). -->
	<div
		data-testid="offline-sperre-hinweis"
		data-gz-offline-band
		data-offline-erlaubt
		role="status"
		style="padding: 8px 16px; background: rgba(198,40,40,0.10); color: #8a1f1f;
		       border-bottom: 1px solid #c62828; font-size: 13px; font-weight: 600;
		       line-height: 1.4;"
	>
		{gate.hint}
	</div>
{/if}

<style>
	/*
	 * Sichtbarer Sperr-Zustand AM Element (AC-9, Adversary-Finding F005).
	 *
	 * Ohne diese Regel sind gesperrte Bedienelemente optisch nicht von
	 * bedienbaren zu unterscheiden: Autoren-CSS der Bausteine setzt
	 * `cursor: pointer` und volle Einfaerbung ohne jede `:disabled`-Praezisierung
	 * und ueberschreibt damit die (ohnehin schwache) Voreinstellung des Browsers.
	 * Deshalb `!important` und deshalb hier zentral: die Sperre wird am DOM
	 * durchgesetzt (s. Modulkommentar), ihre Kennzeichnung gehoert an dieselbe
	 * Stelle — in jedem Baustein einzeln waere sie an jeder kuenftigen Flaeche
	 * erneut vergessbar.
	 *
	 * Kein blasses Ausgrauen (Design-Leitprinzip: Lesbarkeit vor weicher Optik):
	 * die Schrift behaelt ihre Farbe, das Merkmal traegt die Schraffur, der
	 * gestrichelte Rand und der Zeiger. `grayscale` nimmt einer aktiven
	 * Auswahl die Akzentfarbe — sonst sieht „aktiv und gesperrt" aus wie
	 * „aktiv und bedienbar".
	 */
	:global([data-gz-offline-gesperrt]) {
		cursor: not-allowed !important;
		filter: grayscale(1) !important;
		border-style: dashed !important;
		background-image: repeating-linear-gradient(
			135deg,
			transparent 0 5px,
			rgba(26, 26, 24, 0.16) 5px 10px
		) !important;
	}

	/* Die Begruendung an der Bedien-Gruppe. Farbe wie das Band oben (8,6:1 auf
	   Weiss, WCAG-AA) — sie ist eine Aussage ueber den Zustand, kein Beiwerk. */
	:global([data-gz-offline-grund]) {
		display: block;
		/* Bedienleisten sind fast immer `display: flex`. Ohne diese beiden
		   Angaben waere der Hinweis ein weiteres Element IN der Reihe und
		   quetschte die Schaltflaechen zusammen, die er erklaert; so nimmt er
		   eine eigene Zeile unter der Gruppe ein. */
		flex: 0 0 100%;
		grid-column: 1 / -1;
		margin: 4px 0 0;
		font-size: 12px;
		font-weight: 600;
		line-height: 1.35;
		color: #8a1f1f;
	}

	/* Nur waehrend der Sperre: die Gruppe muss den Hinweis umbrechen duerfen. */
	:global([data-gz-sperr-gruppe]) {
		flex-wrap: wrap;
	}
</style>
