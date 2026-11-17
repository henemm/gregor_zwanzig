<script lang="ts">
	// Issue #3006 (Epic #2913): Bereichskopf eines Reiters der Einstellungen (Mockup Fassung 3,
	// `.sectionh`, CSS Z. 69–71): Überschrift, Erklärsatz, optional eine Aktion rechts.
	// Ersetzt die Einzelkopien von Wetter (`wt-kopf`) und Zustellung (`ZustellungKopf`) und steht
	// in allen acht Reitern von Trip und Orts-Briefing (ADR-0097, ADR-0112). Texte kommen als Props
	// aus dem Katalog des Aufrufers (ADR-0104).
	//
	// Warum nicht `atoms/SectionH`: SectionH ist ein anderes Muster (Eyebrow/Titel über Karten,
	// vielfach genutzt) und bleibt unverändert; der Bereichskopf trägt den Abschnitts-Marker
	// `abschnittskopf` für den Elementlisten-Abgleich.
	//
	// Grid statt verschachteltem Flex: h2, p und Aktion sind DIREKTE Kinder des Roots, damit der
	// Titel-Elternknoten die Linie trägt (#2980 AC-28) und der Abgleich die Reihenfolge Titel,
	// Satz, Knopf liest.
	import type { Snippet } from 'svelte';

	interface Props {
		titel: string;
		erklaerung: string;
		/** Testid-Präfix: ergibt `<präfix>-titel` und `<präfix>-erklaer`. */
		testid: string;
		/** Optionale Aktion rechts im Kopf (z. B. „+ Ort hinzufügen“). */
		aktion?: Snippet;
	}
	let { titel, erklaerung, testid, aktion }: Props = $props();
</script>

<div class="bereichskopf" class:mit-aktion={!!aktion} data-abschnitt="abschnittskopf">
	<h2 data-testid="{testid}-titel">{titel}</h2>
	<p data-testid="{testid}-erklaer">{erklaerung}</p>
	{#if aktion}
		<div class="bereichskopf-aktion">{@render aktion()}</div>
	{/if}
</div>

<style>
	/* Mockup `.sectionh`: Linie --g-rule-soft, 12 px Abstand darüber, 12 px Lücke. */
	.bereichskopf {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		column-gap: var(--g-s-3);
		padding-bottom: var(--g-s-3);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.bereichskopf.mit-aktion {
		grid-template-columns: minmax(0, 1fr) auto;
	}
	.bereichskopf h2 {
		grid-column: 1;
		margin: 0px;
		font-size: var(--g-size-22px);
		font-weight: 600;
		/* Mockup -.01em = halbe Stufe von --g-track-tight (-0.02em). */
		letter-spacing: calc(var(--g-track-tight) / 2);
		color: var(--g-ink);
	}
	.bereichskopf p {
		grid-column: 1;
		margin: var(--g-size-2px) 0 0;
		max-width: 68ch;
		font-size: var(--g-size-13px);
		color: var(--g-ink-3);
	}
	/* Aktion rechts, am unteren Rand ausgerichtet (Mockup `align-items: flex-end`). */
	.bereichskopf-aktion {
		grid-column: 2;
		grid-row: 1 / span 2;
		align-self: end;
	}
	/* Wenig Platz: die Aktion bricht unter den Text um (Mockup `flex-wrap: wrap`). */
	@media (max-width: 899px) {
		.bereichskopf.mit-aktion {
			grid-template-columns: minmax(0, 1fr);
		}
		.bereichskopf-aktion {
			grid-column: 1;
			grid-row: auto;
			justify-self: start;
			margin-top: var(--g-s-3);
		}
	}
</style>
