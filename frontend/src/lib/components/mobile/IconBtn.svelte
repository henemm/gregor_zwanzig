<script lang="ts">
	// Issue #373 — IconBtn (interner Helfer, kanonisch aus mobile-shell.jsx).
	//
	// 44x44px Touch-Target um ein MIcon, optionaler Badge.
	// Genutzt von TopAppBar-Wrapper / Drawer / Sheet.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md
	import MIcon, { type MIconKind } from './MIcon.svelte';

	interface Props {
		kind?: MIconKind | string;
		onclick?: () => void;
		label?: string;
		badge?: string | number | null;
	}

	let { kind = 'menu', onclick, label, badge = null }: Props = $props();
</script>

<button
	type="button"
	{onclick}
	aria-label={label}
	style:width="44px"
	style:height="44px"
	style:display="inline-flex"
	style:align-items="center"
	style:justify-content="center"
	style:background="transparent"
	style:border="none"
	style:cursor="pointer"
	style:position="relative"
	style:padding="0"
>
	<MIcon {kind} />
	{#if badge != null}
		<span
			class="mono"
			style:position="absolute"
			style:top="8px"
			style:right="8px"
			style:min-width="16px"
			style:height="16px"
			style:padding="0 4px"
			style:background="var(--g-accent)"
			style:color="#fff"
			style:border-radius="8px"
			style:font-size="10px"
			style:font-weight="600"
			style:font-family="var(--g-font-mono)"
			style:display="inline-flex"
			style:align-items="center"
			style:justify-content="center"
		>{badge}</span>
	{/if}
</button>
