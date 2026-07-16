<script lang="ts">
	// Issue #1272 / ADR-0024 — Griff-Atom des geteilten Sortier-Bausteins.
	//
	// Der Griff ist der FOKUS-Träger des Tastatur-Sortier-Pfads: er ist
	// fokussierbar (tabindex=0, role="button") und liegt INNERHALB der
	// dndzone-Item-Zeile. Leertaste/Enter auf dem Griff blubbern zur Item-Zeile
	// hoch, wo `svelte-dnd-action` den Tastatur-Drag startet
	// (node_modules/svelte-dnd-action/src/keyboardAction.js:171-186).
	//
	// Bewusst KEIN <button>: `keyboardAction.js:177` ignoriert Space/Enter, wenn
	// `e.target.disabled !== undefined` — das trifft auf jedes <button> zu und
	// würde den Tastatur-Pfad still abschalten.
	interface Props {
		/** Beschriftung für Screenreader (Folgepflicht ADR-0024). */
		label?: string;
		/** Kantenlänge des Punkt-Icons in px. */
		size?: number;
	}
	let {
		label = 'Zum Sortieren ziehen — oder mit Leertaste greifen und mit den Pfeiltasten verschieben',
		size = 16,
	}: Props = $props();
</script>

<span
	class="drag-handle"
	data-testid="drag-handle"
	role="button"
	tabindex="0"
	aria-label={label}
>
	<svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
		<circle cx="9" cy="6" r="1.6" /><circle cx="15" cy="6" r="1.6" />
		<circle cx="9" cy="12" r="1.6" /><circle cx="15" cy="12" r="1.6" />
		<circle cx="9" cy="18" r="1.6" /><circle cx="15" cy="18" r="1.6" />
	</svg>
</span>

<style>
	.drag-handle {
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		color: var(--g-ink-4);
		cursor: grab;
		border-radius: var(--g-radius-xs, 3px);
	}
	.drag-handle:active {
		cursor: grabbing;
	}
	.drag-handle:focus-visible {
		outline: 2px solid var(--g-accent);
		outline-offset: 2px;
	}
</style>
