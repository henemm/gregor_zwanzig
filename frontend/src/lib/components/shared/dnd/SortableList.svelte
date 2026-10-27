<script lang="ts">
	// Issue #1272 / ADR-0024 — DER geteilte Sortier-Baustein.
	//
	// Kapselt genau den Teil, der bisher an vier Flächen kopiert wurde:
	//   1. den $state-Spiegel + $effect-Sync gegen die Quell-Liste,
	//   2. die dndzone-Bindung samt consider/finalize,
	//   3. den <div animate:flip>-Wrapper je Zeile.
	//
	// EIN Vertrag: `onDndReorder(newOrder: string[])`, gefeuert AUSSCHLIESSLICH
	// bei `finalize` — nie während `consider`. Die Form `(fromId, toId)` gibt es
	// nicht mehr.
	//
	// Bedingtes Markup zwischen Zeilen (Telegram-Trenner, Cut-Line) gehört INS
	// Snippet, also in den Item-Wrapper — nie als Sibling in die Zone: dndzone
	// duldet keine Nicht-Item-Kinder und würde sie aus dem DOM entfernen.
	import {
		dndzone,
		SHADOW_PLACEHOLDER_ITEM_ID,
		SOURCES,
		TRIGGERS,
		type DndEvent,
	} from 'svelte-dnd-action';
	import { flip } from 'svelte/animate';
	import { untrack, type Snippet } from 'svelte';

	interface Props {
		/** Quell-Reihenfolge (IDs). */
		items: string[];
		/** Feuert NUR bei finalize mit der vollständigen neuen Reihenfolge. */
		onDndReorder: (newOrder: string[]) => void;
		/** Optional: feuert DIREKT nach onDndReorder beim Loslassen (finalize) —
		 *  z.B. Kaskaden-Settling, das erst auf die FERTIGE Reihenfolge reagiert. */
		onDndReorderEnd?: () => void;
		/** Zeileninhalt. Parameter: (id, index) — erlaubt bedingtes Markup im Wrapper. */
		row: Snippet<[string, number]>;
		/** Beschriftung der Zone für Screenreader (Folgepflicht ADR-0024). */
		ariaLabel: string;
		/** Beschriftung je Zeile; `svelte-dnd-action` liest sie für seine Ansagen. */
		itemLabel?: (id: string, index: number) => string;
		/** Verhindert das Ablegen von Zeilen aus anderen Zonen (z.B. Cross-Bucket-Drag). */
		dropFromOthersDisabled?: boolean;
		flipDurationMs?: number;
		/** Optionale Klasse auf der Zone bzw. auf jedem Item-Wrapper. */
		zoneClass?: string;
		itemClass?: string;
		/** Laufrichtung der Zone; Default 'vertical' (alle Bestandskonsumenten). */
		direction?: 'vertical' | 'horizontal';
	}

	let {
		items,
		onDndReorder,
		onDndReorderEnd = undefined,
		row,
		ariaLabel,
		itemLabel,
		dropFromOthersDisabled = false,
		flipDurationMs = 200,
		zoneClass = '',
		itemClass = '',
		direction = 'vertical',
	}: Props = $props();

	// dndzone braucht Array<{id: string}>. Ein $effect (NICHT die abgeleitete
	// Variante!) synct `items` in den lokalen DnD-State, weil dndzone die Liste
	// während der consider-Phase mit einem Phantom-Placeholder mutiert — eine
	// abgeleitete Variable würde den Drag-Zustand pro Tick zurücksetzen und den
	// Drag abbrechen (Falle dokumentiert in issue_433_layout_dnd.md:70-83).
	let dndItems = $state<{ id: string }[]>(untrack(() => items.map((id) => ({ id }))));

	$effect(() => {
		dndItems = items.map((id) => ({ id }));
	});

	// Horizontale Zone (#2288): der Platzhalter der Bibliothek hat eine eigene ID.
	// Rendert der Konsument dafuer nichts, ist er 0 px breit; die Bibliothek
	// verschiebt den gezogenen Klon dann um den Breitenunterschied (morph) und er
	// sitzt dauerhaft versetzt — Ablegen landet auf dem falschen Platz. Darum
	// bekommt der Platzhalter dieselbe Zeile wie das gezogene Element.
	let draggedId: string | null = null;
	function rowId(id: string): string {
		return direction === 'horizontal' && id === SHADOW_PLACEHOLDER_ITEM_ID && draggedId ? draggedId : id;
	}

	// Tastatur-Pfad (ADR-0024 AC-4, #2288): die Bibliothek feuert `finalize` nach
	// JEDEM Pfeilschritt (keyboardAction.js, Fall ArrowDown/Right/Up/Left); das
	// Ablegen per Leertaste/Escape/Klick daneben liefert nur ein `consider` mit
	// `dragStopped`. Gemeldet wird deshalb erst beim Ablegen — genau EIN Report mit
	// der Endreihenfolge. Zwischenschritte gelten nur lokal (dndItems).
	let zoneEl: HTMLElement | undefined = $state();
	let keyboardPending = false;
	// Dieser Griff hat die Tastatur-Geste GESTARTET (consider/dragStarted). Nur dann
	// wird gepuffert. Landet ein Item per Tab aus einer ANDEREN Zone hier (kein
	// dragStarted in dieser Zone), laeuft alles wie vor #2288 sofort durch — sonst
	// meldet die Quellzone "Item weg" sofort und die Zielzone koennte es per Escape
	// verwerfen: das Item ginge verloren (F004).
	let keyboardGesture = false;
	let keyboardDraggedId = '';
	let reemitting = false;
	let escapePressed = false;

	function flushKeyboard(): void {
		if (!keyboardPending) return;
		keyboardPending = false;
		// Von aussen (Tests, Zuhoerer an der Zone) ist `finalize` = "festgeschrieben":
		// die Zwischenschritte wurden unterdrueckt, jetzt kommt genau EIN Ereignis.
		reemitting = true;
		zoneEl?.dispatchEvent(
			new CustomEvent('finalize', {
				detail: {
					items: dndItems,
					info: { trigger: TRIGGERS.DROPPED_INTO_ZONE, id: keyboardDraggedId, source: SOURCES.KEYBOARD },
				},
			})
		);
		reemitting = false;
		onDndReorder(dndItems.map((x) => x.id));
		onDndReorderEnd?.();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') escapePressed = true;
	}

	// Fokus verlassen, ohne abzulegen: nach kurzer Frist (die Bibliothek setzt den
	// Fokus nach jedem Schritt selbst zurueck) den Stand melden, statt ihn zu verlieren.
	function handleFocusout() {
		if (!keyboardPending) return;
		setTimeout(() => {
			if (keyboardPending && !(zoneEl && zoneEl.contains(document.activeElement))) flushKeyboard();
		}, 150);
	}

	function handleDndConsider(e: CustomEvent<DndEvent<{ id: string }>>) {
		const { trigger, id, source } = e.detail.info;
		if (source === SOURCES.KEYBOARD) {
			if (trigger === TRIGGERS.DRAG_STARTED) {
				flushKeyboard(); // Rest eines anderen Griffs (Klick auf anderes Item)
				escapePressed = false;
				keyboardGesture = true;
			} else if (trigger === TRIGGERS.DRAG_STOPPED) {
				keyboardGesture = false;
				if (escapePressed && keyboardPending) {
					// Escape bricht ab: Ausgangszustand, nichts melden.
					keyboardPending = false;
					dndItems = items.map((x) => ({ id: x }));
				} else {
					dndItems = e.detail.items;
					flushKeyboard();
				}
				escapePressed = false;
				return;
			}
		}
		if (trigger === TRIGGERS.DRAG_STARTED) draggedId = id;
		dndItems = e.detail.items;
	}

	function handleDndFinalize(e: CustomEvent<DndEvent<{ id: string }>>) {
		const { trigger, source, id } = e.detail.info;
		if (reemitting) return; // eigenes, gebuendeltes Ereignis aus flushKeyboard()
		if (source === SOURCES.KEYBOARD && trigger === TRIGGERS.DROPPED_INTO_ANOTHER) {
			keyboardGesture = false; // Item wandert in eine andere Zone: sofort melden
			keyboardPending = false; // ein offener Zwischenstand steckt schon in dieser Meldung
		}
		if (source === SOURCES.KEYBOARD && trigger === TRIGGERS.DROPPED_INTO_ZONE && keyboardGesture) {
			e.stopImmediatePropagation(); // Zwischenschritt: nicht nach aussen melden
			dndItems = e.detail.items;
			keyboardPending = true;
			keyboardDraggedId = id;
			return;
		}
		draggedId = null;
		dndItems = e.detail.items;
		onDndReorder(dndItems.map((x) => x.id));
		onDndReorderEnd?.();
	}
</script>

<div
	class="sortable-zone {zoneClass}"
	aria-label={ariaLabel}
	style={direction === 'horizontal' ? 'flex-direction: row;' : undefined}
	use:dndzone={{
		items: dndItems,
		flipDurationMs,
		dropTargetStyle: {},
		dropFromOthersDisabled,
	}}
	onconsider={handleDndConsider}
	onfinalize={handleDndFinalize}
	onkeydown={handleKeydown}
	onfocusout={handleFocusout}
	bind:this={zoneEl}
>
	{#each dndItems as item, i (item.id)}
		<div
			class="sortable-item {itemClass}"
			style={direction === 'horizontal' ? 'flex-shrink: 0;' : undefined}
			animate:flip={{ duration: flipDurationMs }}
			aria-label={itemLabel?.(rowId(item.id), i) ?? rowId(item.id)}
		>
			{@render row(rowId(item.id), i)}
		</div>
	{/each}
</div>

<style>
	/* Die Zone bringt ihr Spalten-Layout selbst mit: eine ueber `zoneClass`
	   durchgereichte Klasse traegt den Scope-Hash des KONSUMENTEN nicht, seine
	   Regeln greifen hier also nicht. */
	.sortable-zone {
		display: flex;
		flex-direction: column;
	}
	.sortable-zone:focus-visible,
	.sortable-item:focus-visible {
		outline: 2px solid var(--g-accent);
		outline-offset: -2px;
	}
</style>
