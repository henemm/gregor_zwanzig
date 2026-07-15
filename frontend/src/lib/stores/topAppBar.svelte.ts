// Issue #1256 Scheibe 8d — Befüllungs-Store für die EINE globale
// Design-Kopfleiste (`ui/sidebar/TopAppBar.svelte`, kanonisch aus #373).
// Seiten setzen title/eyebrow/leftIcon/backHref/right via $effect beim
// Mount und räumen per Effect-Cleanup wieder auf (SSR-fest: $effect läuft
// nur im Browser, Default = {} → unbefüllte Seiten zeigen weiterhin den
// bisherigen Wordmark/Bell/Plus-Default ohne Flackern).
//
// Bewusst ein einziges Singleton (anders als SaveStatus/#758): es gibt
// exakt EINE globale TopAppBar-Instanz (in +layout.svelte gemountet), kein
// Bedarf für mehrere unabhängige Instanzen.
import type { Snippet } from 'svelte';

export interface TopAppBarFill {
	title?: string;
	eyebrow?: string;
	leftIcon?: string;
	backHref?: string;
	right?: Snippet;
}

class TopAppBarStore {
	fill = $state<TopAppBarFill>({});

	set(next: TopAppBarFill): void {
		this.fill = next;
	}

	reset(): void {
		this.fill = {};
	}
}

export const topAppBarStore = new TopAppBarStore();
