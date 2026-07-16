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
	import { dndzone, type DndEvent } from 'svelte-dnd-action';
	import { flip } from 'svelte/animate';
	import type { Snippet } from 'svelte';

	interface Props {
		/** Quell-Reihenfolge (IDs). */
		items: string[];
		/** Feuert NUR bei finalize mit der vollständigen neuen Reihenfolge. */
		onDndReorder: (newOrder: string[]) => void;
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
	}

	let {
		items,
		onDndReorder,
		row,
		ariaLabel,
		itemLabel,
		dropFromOthersDisabled = false,
		flipDurationMs = 200,
		zoneClass = '',
		itemClass = '',
	}: Props = $props();

	// dndzone braucht Array<{id: string}>. Ein $effect (NICHT die abgeleitete
	// Variante!) synct `items` in den lokalen DnD-State, weil dndzone die Liste
	// während der consider-Phase mit einem Phantom-Placeholder mutiert — eine
	// abgeleitete Variable würde den Drag-Zustand pro Tick zurücksetzen und den
	// Drag abbrechen (Falle dokumentiert in issue_433_layout_dnd.md:70-83).
	let dndItems = $state<{ id: string }[]>([]);

	$effect(() => {
		dndItems = items.map((id) => ({ id }));
	});

	function handleDndConsider(e: CustomEvent<DndEvent<{ id: string }>>) {
		dndItems = e.detail.items;
	}

	function handleDndFinalize(e: CustomEvent<DndEvent<{ id: string }>>) {
		dndItems = e.detail.items;
		onDndReorder(dndItems.map((x) => x.id));
	}
</script>

<div
	class="sortable-zone {zoneClass}"
	aria-label={ariaLabel}
	use:dndzone={{
		items: dndItems,
		flipDurationMs,
		dropTargetStyle: {},
		dropFromOthersDisabled,
	}}
	onconsider={handleDndConsider}
	onfinalize={handleDndFinalize}
>
	{#each dndItems as item, i (item.id)}
		<div
			class="sortable-item {itemClass}"
			animate:flip={{ duration: flipDurationMs }}
			aria-label={itemLabel?.(item.id, i) ?? item.id}
		>
			{@render row(item.id, i)}
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
