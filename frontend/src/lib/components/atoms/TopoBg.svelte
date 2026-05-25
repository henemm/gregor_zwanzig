<script lang="ts">
	// Issue #371 — Re-Export-Wrapper: atoms/TopoBg -> ui/topo.
	// Duenner Bridge-Wrapper, reicht alle Props 1:1 durch (inkl. children-Snippet).
	import TopoBg from '$lib/components/ui/topo/TopoBg.svelte';
	let props = $props();
</script>

<TopoBg {...props} />
