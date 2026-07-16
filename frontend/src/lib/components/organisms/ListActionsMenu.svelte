<script lang="ts">
	// Issue #1277 — ListActionsMenu: Overflow-Menü (⋯) für ListTable-Zeilen.
	//
	// Geteilter Baustein für Trips + Orts-Vergleiche. Übernimmt das Portal-/
	// Flip-Positionierungs-Muster aus trips/+page.svelte (openMenuAtBtn +
	// $effect-Flip-Korrektur, #706) und die role="menu"-Semantik aus
	// CompareKebab.svelte — vereinheitlicht in EINER Komponente.
	//
	// Jede Instanz verwaltet ihren eigenen Offen-Zustand. Das Menü wird via
	// portal an document.body gehängt (kein overflow-Ancestor clippt es) und
	// bei Außenklick / Scroll / Resize geschlossen.
	//
	// Spec: docs/specs/feature/issue_1277_list_table_unify.md

	import { untrack } from 'svelte';

	interface Action {
		key: string;
		label: string;
		danger?: boolean;
		// Optionaler expliziter Testid für den Menüpunkt (z.B. bestehender
		// `trip-edit-btn`-Selektor). Fällt sonst auf `${testid}-${key}` zurück.
		testid?: string;
	}

	let {
		actions,
		onSelect,
		label = 'Weitere Aktionen',
		testid
	}: {
		actions: Action[];
		onSelect: (key: string) => void;
		label?: string;
		testid?: string;
	} = $props();

	// #706 — Portal-Action: hängt das Element an document.body statt in den
	// overflow-Baum.
	function portal(node: HTMLElement) {
		document.body.appendChild(node);
		return {
			destroy() {
				node.remove();
			}
		};
	}

	let open = $state(false);
	let menuPos = $state({ top: 0, right: 0 });
	let menuAnchorRect = $state<DOMRect | null>(null);
	let menuEl = $state<HTMLElement | null>(null);

	function toggle(e: MouseEvent) {
		e.stopPropagation();
		if (open) {
			close();
			return;
		}
		const btn = e.currentTarget as HTMLElement;
		const rect = btn.getBoundingClientRect();
		menuAnchorRect = rect;
		menuPos = { top: rect.bottom + 6, right: window.innerWidth - rect.right };
		open = true;
	}

	function close() {
		open = false;
		menuAnchorRect = null;
	}

	function pick(key: string) {
		close();
		onSelect(key);
	}

	// Flip-Korrektur nach dem Rendern: ragt das Menü aus dem Viewport, oben
	// öffnen bzw. links clampen. untrack() verhindert eine Reaktiv-Schleife
	// (der Effekt schreibt menuPos, darf es aber nicht als Dependency lesen).
	$effect(() => {
		if (!menuEl || !menuAnchorRect) return;
		const menuRect = menuEl.getBoundingClientRect();
		const vp = window.innerHeight;
		const GAP = 6;
		const MARGIN = 8;
		const currentPos = untrack(() => ({ ...menuPos }));
		if (menuRect.bottom > vp) {
			const flippedTop = menuAnchorRect.top - menuRect.height - GAP;
			menuPos = { ...currentPos, top: Math.max(MARGIN, flippedTop) };
		}
		const menuWidth = menuRect.width;
		const rightFromLeft = window.innerWidth - currentPos.right;
		if (rightFromLeft - menuWidth < MARGIN) {
			menuPos = { ...currentPos, right: window.innerWidth - (menuWidth + MARGIN) };
		}
	});

	// Schließen bei Scroll/Resize — Listener um einen Frame verzögert, damit
	// Playwrights scroll-into-view (durch den Klick ausgelöst) das frisch
	// geöffnete Menü nicht sofort wieder schließt.
	$effect(() => {
		if (!open) return;
		let timerId: ReturnType<typeof setTimeout>;
		timerId = setTimeout(() => {
			window.addEventListener('scroll', close, { capture: true, passive: true });
			window.addEventListener('resize', close, { passive: true });
		}, 0);
		return () => {
			clearTimeout(timerId);
			window.removeEventListener('scroll', close, { capture: true });
			window.removeEventListener('resize', close);
		};
	});
</script>

<button
	data-testid={testid}
	title={label}
	aria-label={label}
	aria-haspopup="menu"
	aria-expanded={open}
	type="button"
	onclick={toggle}
	style="width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; background: {open
		? 'var(--g-paper-deep)'
		: 'transparent'}; border: 1px solid var(--g-rule); border-radius: var(--g-r-2); cursor: pointer;"
>
	<svg width="15" height="15" viewBox="0 0 24 24" fill="none">
		<circle cx="5" cy="12" r="1.4" fill="var(--g-ink-2)" />
		<circle cx="12" cy="12" r="1.4" fill="var(--g-ink-2)" />
		<circle cx="19" cy="12" r="1.4" fill="var(--g-ink-2)" />
	</svg>
</button>

{#if open}
	<!-- Overlay zum Schließen bei Außenklick (portal → document.body) -->
	<div
		use:portal
		role="presentation"
		onkeydown={(e) => {
			if (e.key === 'Escape') close();
		}}
		onclick={(e) => {
			e.stopPropagation();
			close();
		}}
		style="position: fixed; inset: 0; z-index: 40;"
	></div>
	<!-- Overflow-Menü (#706: portal → document.body, kein overflow-Ancestor) -->
	<div
		use:portal
		bind:this={menuEl}
		role="menu"
		style="position: fixed; top: {menuPos.top}px; right: {menuPos.right}px; z-index: 41; min-width: 232px; background: var(--g-card); border: 1px solid var(--g-rule); border-radius: var(--g-r-3); box-shadow: var(--g-shadow-2, 0 8px 28px rgba(30,26,18,.16)); padding: 6px;"
	>
		{#each actions as action (action.key)}
			<button
				role="menuitem"
				data-testid={action.testid ?? (testid ? `${testid}-${action.key}` : undefined)}
				onclick={(e) => {
					e.stopPropagation();
					pick(action.key);
				}}
				onmouseenter={(e) => {
					(e.currentTarget as HTMLElement).style.background = 'var(--g-paper-deep)';
				}}
				onmouseleave={(e) => {
					(e.currentTarget as HTMLElement).style.background = 'transparent';
				}}
				style="display: flex; align-items: center; gap: 10px; width: 100%; padding: 9px 10px; min-height: 40px; text-align: left; background: transparent; border: none; border-radius: var(--g-r-2); cursor: pointer; font-size: 13px; font-family: var(--g-font-sans); color: {action.danger
					? 'var(--g-bad, #a83232)'
					: 'var(--g-ink)'};"
			>
				{action.label}
			</button>
		{/each}
	</div>
{/if}
