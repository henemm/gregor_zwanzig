<script lang="ts">
	// Issue #371 — Re-Export-Wrapper: atoms/Eyebrow -> ui/eyebrow.
	// Duenner Bridge-Wrapper, reicht alle Props 1:1 durch.
	import Eyebrow from '$lib/components/ui/eyebrow/Eyebrow.svelte';
	let props = $props();
</script>

<Eyebrow {...props} />
