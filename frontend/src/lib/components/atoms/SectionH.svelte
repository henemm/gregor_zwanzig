<script lang="ts">
	// Issue #371 — SectionH-Atom (kanonisch aus atoms.jsx, Svelte 5).
	//
	// Abschnitts-Header: Eyebrow + Titel + optionaler Kicker, optional rechts
	// ausgerichteter Slot (right). Flex space-between.
	//
	// Spec: docs/specs/modules/issue_371_atoms.md (AC-6)

	import type { Snippet } from 'svelte';
	import Eyebrow from '$lib/components/ui/eyebrow/Eyebrow.svelte';

	interface Props {
		eyebrow?: string;
		title?: string;
		kicker?: string;
		right?: Snippet;
		class?: string;
	}

	let {
		eyebrow = '',
		title = '',
		kicker = '',
		right,
		class: className = ''
	}: Props = $props();
</script>

<div
	data-slot="section-h"
	class={className}
	style:display="flex"
	style:align-items="flex-end"
	style:justify-content="space-between"
	style:flex-wrap="wrap"
	style:gap="12px 24px"
	style:margin-bottom="16px"
>
	<div>
		{#if eyebrow}
			<Eyebrow style="margin-bottom: 6px;">{eyebrow}</Eyebrow>
		{/if}
		<div style:font-size="22px" style:font-weight="600" style:letter-spacing="-0.01em">
			{title}
		</div>
		{#if kicker}
			<div style:color="var(--g-ink-3)" style:font-size="13px" style:margin-top="2px">
				{kicker}
			</div>
		{/if}
	</div>
	{#if right}
		<div>{@render right()}</div>
	{/if}
</div>
