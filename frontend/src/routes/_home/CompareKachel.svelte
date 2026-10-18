<script lang="ts">
	// Issue #492 / #2278 — Thin-Wrapper auf die geteilte SubscriptionCard (kind="vergleich").
	// Klick navigiert zum Hub; das Kebab bietet nur "Bearbeiten" (ebenfalls Hub), siehe kachelActions.

	import { goto } from '$app/navigation';
	import SubscriptionCard from '$lib/components/organisms/SubscriptionCard.svelte';
	import { compareKachelActions } from './kachelActions.js';
	import type { ComparePreset } from '$lib/types.js';

	let { sub }: { sub: ComparePreset } = $props();
</script>

<SubscriptionCard
	kind="vergleich"
	{sub}
	compact
	actions={compareKachelActions()}
	onclick={() => goto('/compare/' + sub.id)}
	onAction={(id) => {
		// Epic #1273 S3: Ziel ist der Hub, nicht mehr die alte /edit-Route.
		if (id === 'edit') goto('/compare/' + sub.id);
	}}
/>
