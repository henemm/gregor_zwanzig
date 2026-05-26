<script lang="ts">
	// Issue #373 — MInput (kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// Touch-Eingabefeld mit optionalem Left-Icon. font-size 16px verhindert
	// iOS-Safari-Auto-Zoom (Bug #272). Token-basiert.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md (AC-3)
	import type { MIconKind } from './MIcon.svelte';
	import MIcon from './MIcon.svelte';

	interface Props {
		value?: string;
		type?: string;
		placeholder?: string;
		leftIcon?: MIconKind | string;
		oninput?: (e: Event) => void;
	}

	let {
		value = $bindable(''),
		type = 'text',
		placeholder,
		leftIcon,
		oninput
	}: Props = $props();
</script>

<div
	style:display="flex"
	style:align-items="center"
	style:gap="10px"
	style:background="var(--g-card)"
	style:border="1px solid var(--g-rule)"
	style:border-radius="var(--g-r-3)"
	style:padding="0 14px"
	style:min-height="48px"
>
	{#if leftIcon}
		<MIcon kind={leftIcon} size={18} color="var(--g-ink-4)" />
	{/if}
	<input
		data-testid="m-input"
		{type}
		bind:value
		{placeholder}
		{oninput}
		style:flex="1"
		style:border="none"
		style:outline="none"
		style:background="transparent"
		style:font-size="16px"
		style:font-family="var(--g-font-sans)"
		style:color="var(--g-ink)"
		style:min-height="44px"
		style:padding="0"
	/>
</div>
