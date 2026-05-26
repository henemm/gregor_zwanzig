<script lang="ts">
	// Issue #373 — Drawer (kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// Hamburger-Panel: Overlay + Slide-In von links. Body-Scroll-Lock nur im
	// browser-Guard (SSR-fest). Inhalt via Snippet. Token-basiert.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md (AC-4)
	import { browser } from '$app/environment';
	import type { Snippet } from 'svelte';
	import IconBtn from './IconBtn.svelte';

	interface Props {
		open?: boolean;
		onClose?: () => void;
		children?: Snippet;
	}

	let { open = false, onClose, children }: Props = $props();

	// Body-Scroll-Lock waehrend offen — ausschliesslich im Browser, nie bei SSR.
	$effect(() => {
		if (!browser) return;
		if (open) {
			const prev = document.body.style.overflow;
			document.body.style.overflow = 'hidden';
			return () => {
				document.body.style.overflow = prev;
			};
		}
	});
</script>

{#if open}
	<div
		role="presentation"
		onclick={onClose}
		style:position="absolute"
		style:inset="0"
		style:background="rgba(26,26,24,0.42)"
		style:z-index="50"
	></div>
	<aside
		style:position="absolute"
		style:top="0"
		style:left="0"
		style:bottom="0"
		style:width="296px"
		style:z-index="51"
		style:background="var(--g-paper-deep)"
		style:box-shadow="var(--g-shadow-3)"
		style:display="flex"
		style:flex-direction="column"
	>
		<div
			style:padding="12px 20px 18px"
			style:display="flex"
			style:justify-content="flex-end"
			style:align-items="center"
		>
			<IconBtn kind="close" onclick={onClose} label="Schliessen" />
		</div>
		<div style:padding="0 12px" style:flex="1" style:overflow="auto">
			{@render children?.()}
		</div>
	</aside>
{/if}
