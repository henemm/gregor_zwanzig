<script lang="ts">
	// Test-Stand-in (#2660): der bits-ui-Dialog gibt unter svelte/server keinen
	// Inhalt aus (Portal + Presence). Dieser Rahmen reicht Kinder und Attribute
	// unveraendert durch, damit der ECHTE Inhalt von ConfirmDialog/SendConfirmDialog
	// (Titel, Knoepfe, aria-label) im SSR-Render messbar wird.
	import type { Snippet } from 'svelte';
	let {
		children,
		open = true,
		onOpenChange: _onOpenChange,
		...rest
	}: { children?: Snippet; open?: boolean; onOpenChange?: unknown; [k: string]: unknown } = $props();
</script>

{#if open}<div data-dialog-teil {...rest}>{@render children?.()}</div>{/if}
