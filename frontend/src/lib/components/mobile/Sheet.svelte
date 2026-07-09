<script lang="ts" module>
	export type SheetSnap = 'full' | 'half' | 'peek' | 'collapsed';
</script>

<script lang="ts">
	// Issue #373 — Sheet (Bottom-Sheet, kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// Overlay + von unten einfahrendes Panel. snap full|half|peek steuert die
	// Hoehe (84%/55%/32%). Body-Scroll-Lock nur im browser-Guard (SSR-fest).
	// Inhalt + footer via Snippet. Unbekanntes snap -> full. Token-basiert.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md (AC-4, AC-6)
	import { browser } from '$app/environment';
	import type { Snippet } from 'svelte';
	import IconBtn from './IconBtn.svelte';

	interface Props {
		open?: boolean;
		onClose?: () => void;
		title?: string;
		eyebrow?: string;
		snap?: SheetSnap;
		variant?: 'modal' | 'embedded';
		footer?: Snippet;
		children?: Snippet;
		onHandleToggle?: () => void;
	}

	let {
		open = false,
		onClose,
		title,
		eyebrow,
		snap = 'full',
		variant = 'modal',
		footer,
		children,
		onHandleToggle
	}: Props = $props();

	// Issue #1158 — collapsed ist eine feste Pixel-Hoehe (nicht prozentual wie
	// die anderen drei Stufen), sonst waere "eingeklappt" auf grossen Displays
	// immer noch zu hoch.
	const heights = { full: '84%', half: '55%', peek: '32%', collapsed: '56px' } as const;
	const height = $derived(heights[snap] ?? heights.full);

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

{#if open || variant === 'embedded'}
	{#if variant !== 'embedded'}
		<div
			role="presentation"
			onclick={onClose}
			style:position="fixed"
			style:inset="0"
			style:background="rgba(26,26,24,0.42)"
			style:z-index="60"
		></div>
	{/if}
	<div
		data-snap={snap}
		style:position={variant === 'embedded' ? 'absolute' : 'fixed'}
		style:left="0"
		style:right="0"
		style:bottom="0"
		style:height={height}
		style:background="var(--g-card)"
		style:z-index="61"
		style:border-top-left-radius="18px"
		style:border-top-right-radius="18px"
		style:box-shadow="0 -8px 32px rgba(26,26,24,0.18)"
		style:display="flex"
		style:flex-direction="column"
		style:overflow="hidden"
	>
		<div
			data-testid="sheet-handle"
			onclick={onHandleToggle}
			style:display="flex"
			style:justify-content="center"
			style:padding-top="8px"
			style:padding-bottom="4px"
			style:flex-shrink="0"
			style:cursor={onHandleToggle ? 'pointer' : 'default'}
		>
			<span
				style:width="36px"
				style:height="4px"
				style:border-radius="2px"
				style:background="var(--g-rule)"
			></span>
		</div>
		{#if title || eyebrow}
			<div
				style:padding="8px 20px 12px"
				style:flex-shrink="0"
				style:display="flex"
				style:align-items="flex-start"
				style:gap="8px"
			>
				<div style:flex="1" style:min-width="0">
					{#if eyebrow}
						<div
							class="mono"
							style:font-size="10px"
							style:letter-spacing="0.12em"
							style:text-transform="uppercase"
							style:color="var(--g-ink-4)"
							style:margin-bottom="4px"
						>{eyebrow}</div>
					{/if}
					{#if title}
						<div style:font-size="18px" style:font-weight="600" style:letter-spacing="-0.01em">{title}</div>
					{/if}
				</div>
				{#if onClose}
					<IconBtn kind="close" onclick={onClose} label="Schliessen" />
				{/if}
			</div>
		{/if}
		<div style:flex="1" style:overflow="auto" style:padding="0 20px 20px">
			{@render children?.()}
		</div>
		{#if footer}
			<div
				style:padding="12px 20px calc(12px + env(safe-area-inset-bottom))"
				style:border-top="1px solid var(--g-rule-soft)"
				style:background="var(--g-card)"
				style:flex-shrink="0"
			>
				{@render footer()}
			</div>
		{/if}
	</div>
{/if}
