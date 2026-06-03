<script lang="ts">
	// Issue #573 — PageHeader Atom: kanonischer Seiten-Header mit Eyebrow/Titel/Sub + optionalem Right-Slot.
	// Spec: docs/specs/modules/issue_573_charter_fix_cockpit.md
	import type { Snippet } from 'svelte';
	import Eyebrow from '$lib/components/ui/eyebrow/Eyebrow.svelte';

	interface Props {
		eyebrow?: string;
		title?: string;
		sub?: string | null;
		right?: Snippet;
		class?: string;
	}

	let { eyebrow = '', title = '', sub = null, right, class: className = '' }: Props = $props();
</script>

<header
	data-slot="page-header"
	class={className}
	style:padding="var(--g-s-5) 0"
	style:border-bottom="1px solid var(--g-rule-soft)"
	style:margin-bottom="var(--g-s-8)"
	style:display="flex"
	style:align-items="center"
	style:justify-content="space-between"
>
	<div>
		{#if eyebrow}<Eyebrow>{eyebrow}</Eyebrow>{/if}
		{#if title}
			<h1
				style:margin="0"
				style:font-size="var(--g-text-xl)"
				style:font-weight="600"
				style:letter-spacing="var(--g-track-tight)"
				style:line-height="1.2"
				style:color="var(--g-ink)"
			>{title}</h1>
		{/if}
		{#if sub}
			<p
				style:margin="var(--g-s-1) 0 0"
				style:font-size="var(--g-text-md)"
				style:color="var(--g-ink-muted)"
				style:line-height="1.5"
			>{sub}</p>
		{/if}
	</div>
	{#if right}
		<div style:display="flex" style:gap="var(--g-s-2)" style:align-items="center">
			{@render right()}
		</div>
	{/if}
</header>
