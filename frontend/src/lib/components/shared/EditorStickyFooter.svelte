<script lang="ts">
	// Mobile-Shell S2 — Sticky-Footer der Anlege-Editoren (geteilter Baustein,
	// Trip UND Vergleich; `context` nur als Datenmarke fuer Tests/Styling).
	// Traegt die Weiter-/Aktivieren-Aktion des aktiven Reiters und haelt sie
	// ueber der schwebenden Tabbar (--g-nav-clearance), wenn diese sichtbar ist.
	// Ersetzt fuer den Vergleich das „Aktivieren" in der abgeschafften TopAppBar
	// (docs/design-requests/mobile_shell_ohne_topbar.md §3).
	import type { Snippet } from 'svelte';

	interface Props {
		context: 'route' | 'vergleich';
		testid?: string;
		/** Schwebt die Tabbar unter dem Footer? (`/trips/new` blendet sie aus.) */
		navClearance?: boolean;
		children?: Snippet;
	}

	let { context, testid = 'editor-sticky-footer', navClearance = true, children }: Props = $props();
</script>

<div data-testid={testid} data-context={context} class="editor-sticky-footer" class:has-nav={navClearance}>
	{@render children?.()}
</div>

<style>
	.editor-sticky-footer {
		position: sticky;
		bottom: 0;
		z-index: 5;
		flex-shrink: 0;
		padding: 12px 16px;
		background: var(--g-paper);
		border-top: 1px solid var(--g-rule-soft);
	}
	@media (max-width: 899px) {
		.editor-sticky-footer.has-nav {
			padding-bottom: calc(12px + var(--g-nav-clearance));
		}
	}
</style>
