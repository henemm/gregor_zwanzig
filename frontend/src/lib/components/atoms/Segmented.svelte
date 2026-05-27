<script lang="ts">
	// Issue #403 — Re-Export-Wrapper: atoms/Segmented -> ui/segmented.
	import Segmented from '$lib/components/ui/segmented/Segmented.svelte';
	let props = $props();
</script>

<Segmented {...props} />
